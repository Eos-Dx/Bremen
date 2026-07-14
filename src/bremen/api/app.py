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
    HealthResponse,
    ModelVersionResponse,
    PredictionRequest,
    PredictionResponse,
    PredictionStatusResponse,
    STATUS_NOT_FOUND,
    build_accepted_response,
    build_health_response,
    build_not_found_response,
    validate_prediction_request,
)


def handle_health(version: str | None = None) -> HealthResponse:
    """Return service health information.

    Parameters
    ----------
    version : Optional package version string.

    Returns
    -------
    A ``HealthResponse`` with current status.
    """
    return build_health_response(version=version)


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
    """
    request = validate_prediction_request(raw_request)
    record = job_store.create_job(request=request)
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

    return PredictionStatusResponse(
        job_id=record.job_id,
        status=record.status,
        submitted_at=record.submitted_at,
        updated_at=record.updated_at,
        result=result,
        error=record.error,
    )
