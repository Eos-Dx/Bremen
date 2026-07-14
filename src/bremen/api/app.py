"""Route-shaped handler functions for the Bremen API.

Standard-library only — no web framework dependency.  All handlers are
stateless pure functions (except the optional ``job_store`` parameter).
Designed to be plugged into any future web framework adapter.

This module may import safe types from ``model_package.py`` but must not
import ``joblib`` or ``pickle`` or deserialize any model artifact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import CloudConfig
from .jobs import InMemoryJobStore
from .schemas import (
    CompletedResult,
    HealthResponse,
    ModelVersionResponse,
    PredictionRequest,
    PredictionResponse,
    PredictionStatusResponse,
    STATUS_COMPLETED,
    STATUS_NOT_FOUND,
    build_accepted_response,
    build_health_response,
    build_not_configured_model_response,
    build_not_found_response,
    validate_prediction_request,
)
from .model_state import ModelState


def handle_health(version: str | None = None) -> HealthResponse:
    """Return service health information.

    Parameters
    ----------
    version : Optional package version string.

    Returns
    -------
    A ``HealthResponse`` with current status.
    """
    resp = build_health_response(version=version)
    return HealthResponse(
        status=resp.status,
        service=resp.service,
        version=resp.version,
        timestamp=resp.timestamp,
        model_ready=ModelState.is_ready(),
    )


class ModelNotReadyError(RuntimeError):
    """Model is not loaded and prediction cannot be submitted."""


def handle_model_version(
    explicit_path: str | Path | None = None,
    cloud: CloudConfig | None = None,
) -> ModelVersionResponse:
    """Return configured model package metadata.

    Resolves via source precedence:

    1. *explicit_path* argument (local package directory).
    2. ``BREMEN_MODEL_PACKAGE_DIR`` environment variable (local directory).
    3. Cloud metadata from ``read_cloud_config()`` — no S3 reads.
    4. ``not_configured`` — no model package source configured.

    Parameters
    ----------
    explicit_path : Optional explicit path to a local model package
        directory.  Takes precedence over all env vars.
    cloud : Optional ``CloudConfig``.  When explicitly provided,
        uses metadata-only cloud source rather than full precedence
        resolution (backward-compatible path).

    Returns
    -------
    A ``ModelVersionResponse``.

    Must not import ``joblib`` / ``pickle`` or deserialize artifacts.
    """
    if cloud is not None and explicit_path is None:
        # Cloud-only metadata path (backward compatible)
        from .model_source import derive_model_source  # noqa: PLC0415

        src = derive_model_source(cloud=cloud)
        return ModelVersionResponse(**src)
    # Check if model is actually loaded
    model_pkg = ModelState.get_model()
    if model_pkg is not None:
        # Model is loaded and validated — return live metadata with ready status
        state = ModelState.get_instance()
        plr = model_pkg.get("portable_logreg", {})
        return ModelVersionResponse(
            model_configured=True,
            model_version=state._model_version or plr.get("model_version"),
            model_checksum=state._model_checksum,
            feature_schema_version=plr.get("feature_schema_version"),
            threshold_version=plr.get("threshold_version"),
            threshold_value=float(plr.get("threshold", 0.0)) if plr.get("threshold") is not None else None,
            qc_criteria_version=None,
            model_status="ready",
            model_uri_configured=True,
            checksum_configured=True,
            error_category=None,
        )

    # Check if loading was attempted and failed
    if ModelState.was_load_attempted():
        state = ModelState.get_instance()
        load_error = ModelState.get_load_error()
        # Determine configured booleans from available state info
        uri_configured = bool(state._model_version) or (state._load_error not in (None, "model_uri_not_set"))
        checksum_configured = bool(state._model_checksum)
        return ModelVersionResponse(
            model_configured=True,
            model_version=state._model_version,
            model_checksum=state._model_checksum,
            feature_schema_version=None,
            threshold_version=None,
            threshold_value=None,
            qc_criteria_version=None,
            model_status="error",
            model_uri_configured=uri_configured,
            checksum_configured=checksum_configured,
            error_category=load_error,
        )

    # Loading not yet attempted — delegate to derive_model_source (config-only)
    src = derive_model_source(cloud=cloud)
    is_configured = src["model_configured"]
    return ModelVersionResponse(
        **src,
        model_uri_configured=is_configured,
        checksum_configured=bool(src.get("model_checksum")),
        error_category=None,
    )

    from ..model_package_source import resolve_model_package_source  # noqa: PLC0415

    source = resolve_model_package_source(explicit_path=explicit_path)
    return ModelVersionResponse(
        model_configured=source.model_configured,
        model_version=source.model_version,
        model_checksum=source.model_checksum,
        feature_schema_version=source.feature_schema_version,
        threshold_version=source.threshold_version,
        threshold_value=source.threshold_value,
        qc_criteria_version=source.qc_criteria_version,
        model_status=source.model_status,
    )


def handle_submit_prediction(
    raw_request: dict[str, Any],
    job_store: InMemoryJobStore,
) -> PredictionResponse:
    """Create an asynchronous prediction job.

    Parameters
    ----------
    raw_request : Raw request body as a dict.
    job_store : An ``InMemoryJobStore`` instance.

    Returns
    -------
    A ``PredictionResponse`` with an accepted job.

    Raises
    ------
    ValueError
        If ``target_scan_ref`` or ``control_scan_ref`` is missing or
        invalid.
    RuntimeError
        If model is not loaded (HTTP 503).
    """
    if not ModelState.is_ready():
        raise ModelNotReadyError(
            "Model is not loaded. Prediction cannot be submitted. "
            "Check BREMEN_MODEL_URI / BREMEN_MODEL_VERSION "
            "/ BREMEN_MODEL_CHECKSUM environment variables and "
            "model startup logs."
        )

    request = validate_prediction_request(raw_request)
    record = job_store.create_job(request=request)

    # Resolve H5 input path: stage from S3 or use filesystem path
    resolved_h5_path: str
    if request.h5_uri:
        from ..h5_inputs import stage_h5_input  # noqa: PLC0415

        staged = stage_h5_input(
            request.h5_uri,
            expected_checksum=request.h5_checksum,
        )
        resolved_h5_path = str(staged)
    else:
        # h5_path is guaranteed non-None by schema validation
        resolved_h5_path = request.h5_path  # type: ignore[union-attr]

    try:
        from .inference_handler import run_inference  # noqa: PLC0415

        # Determine input_mode for the decision-support report
        input_mode: str | None = None
        if request.h5_uri:
            input_mode = "h5_uri"
        elif request.h5_path:
            input_mode = "h5_path"

        result_dict = run_inference(
            h5_path=resolved_h5_path,
            patient_id=raw_request.get("patient_id"),
            target_scan_ref=request.target_scan_ref,
            control_scan_ref=request.control_scan_ref,
            input_mode=input_mode,
        )

        completed_result = CompletedResult(
            prediction_id=result_dict["prediction_id"],
            model_version=result_dict["model_version"],
            model_checksum=result_dict["model_checksum"],
            feature_schema_version=result_dict["feature_schema_version"],
            threshold_version=result_dict["threshold_version"],
            threshold_value=result_dict["threshold_value"],
            qc_status=result_dict["qc_status"],
            qc_flags=result_dict["qc_flags"],
            decision_support_report=result_dict.get("decision_support_report"),
        )

        job_store.update_status(
            record.job_id,
            STATUS_COMPLETED,
            result=completed_result,
        )
    except ValueError:
        raise  # Propagate for HTTP 400
    except Exception as exc:
        import logging
        _log = logging.getLogger(__name__)
        _log.error(
            "bremen.prediction.failed\t"
            "stage=prediction\tstatus=failed\t"
            "exception_class=%s\t"
            "safe_reason=%s\t"
            "job_id=%s",
            type(exc).__name__,
            str(exc)[:200],
            record.job_id,
        )
        job_store.update_status(
            record.job_id,
            "failed",
            error=str(exc),
        )

    return build_accepted_response(
        job_id=record.job_id,
        submitted_at=record.submitted_at,
    )


def handle_get_prediction(
    job_id: str,
    job_store: InMemoryJobStore,
) -> PredictionStatusResponse:
    """Return the status of an existing prediction job.

    Parameters
    ----------
    job_id : UUID string of the job.
    job_store : An ``InMemoryJobStore`` instance.

    Returns
    -------
    A ``PredictionStatusResponse`` with the current job status.
    Returns ``not_found`` for unknown job IDs.
    """
    record = job_store.get_job(job_id)

    if record is None:
        return build_not_found_response(job_id)

    result: dict[str, Any] | None = None
    if record.result is not None:
        result = {
            "prediction_id": record.result.prediction_id,
            "model_version": record.result.model_version,
            "model_checksum": record.result.model_checksum,
            "feature_schema_version": record.result.feature_schema_version,
            "threshold_version": record.result.threshold_version,
            "threshold_value": record.result.threshold_value,
            "qc_status": record.result.qc_status,
            "qc_flags": record.result.qc_flags,
        }
        if record.result.decision_support_report is not None:
            result["decision_support_report"] = (
                record.result.decision_support_report
            )

    return PredictionStatusResponse(
        job_id=record.job_id,
        status=record.status,
        submitted_at=record.submitted_at,
        updated_at=record.updated_at,
        result=result,
        error=record.error,
    )
