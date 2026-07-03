"""Route-shaped handler functions for the Bremen API.

Standard-library only — no web framework dependency.  All handlers are
stateless pure functions (except the optional ``job_store`` parameter).
Designed to be plugged into any future web framework adapter.

This module may import safe types from ``model_package.py`` but must not
import ``joblib`` or ``pickle`` or deserialize any model artifact.
"""

from __future__ import annotations

from typing import Any

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
    build_not_configured_model_response,
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


def handle_model_version() -> ModelVersionResponse:
    """Return configured model package metadata (stub).

    Returns a safe ``not_configured`` response by default.
    Must not import ``joblib`` / ``pickle`` or deserialize model artifacts.
    """
    return build_not_configured_model_response()


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
