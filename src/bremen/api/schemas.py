"""Request/response schemas for the Bremen API.

Standard-library dataclasses only.  No web framework dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_ACCEPTED = "accepted"
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_NOT_FOUND = "not_found"

ALL_STATUSES = frozenset({
    STATUS_ACCEPTED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_NOT_FOUND,
})

MODEL_STATUS_NOT_CONFIGURED = "not_configured"
MODEL_STATUS_CONFIGURED = "configured"
MODEL_STATUS_INVALID = "invalid"
MODEL_STATUS_UNAVAILABLE = "unavailable"

ALL_MODEL_STATUSES = frozenset({
    MODEL_STATUS_NOT_CONFIGURED,
    MODEL_STATUS_CONFIGURED,
    MODEL_STATUS_INVALID,
    MODEL_STATUS_UNAVAILABLE,
})

# ---------------------------------------------------------------------------
# Mandatory completed-result field names (from project_contract.yml)
# ---------------------------------------------------------------------------

COMPLETED_RESULT_FIELDS = [
    "prediction_id",
    "model_version",
    "model_checksum",
    "feature_schema_version",
    "threshold_version",
    "threshold_value",
    "qc_status",
    "qc_flags",
]

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass
class HealthResponse:
    """Response for ``GET /health``."""

    status: str
    service: str
    version: str | None
    timestamp: str
    model_ready: bool = False


@dataclass
class ModelVersionResponse:
    """Response for ``GET /model/version``."""

    model_configured: bool
    model_version: str | None
    model_checksum: str | None
    feature_schema_version: str | None
    threshold_version: str | None
    threshold_value: float | None
    qc_criteria_version: str | None
    model_status: str  # "not_configured" | "configured" | "invalid" | "unavailable"


@dataclass
class PredictionRequest:
    """Request body for ``POST /predictions``."""

    target_scan_ref: str
    control_scan_ref: str
    request_id: str | None = None


@dataclass
class PredictionResponse:
    """Immediate response for a submitted prediction job (HTTP 202)."""

    job_id: str
    status: str
    submitted_at: str
    links: dict[str, str] | None = None


@dataclass
class PredictionStatusResponse:
    """Response for ``GET /predictions/{job_id}``."""

    job_id: str
    status: str
    submitted_at: str | None
    updated_at: str | None
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class CompletedResult:
    """Mandatory fields for a completed prediction result."""

    prediction_id: str
    model_version: str
    model_checksum: str
    feature_schema_version: str
    threshold_version: str
    threshold_value: float
    qc_status: str
    qc_flags: list[str] | dict[str, Any]


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_prediction_request(data: dict[str, Any]) -> PredictionRequest:
    """Validate and build a ``PredictionRequest`` from a raw dict.

    Parameters
    ----------
    data : Raw request body as a dict.

    Returns
    -------
    A validated ``PredictionRequest``.

    Raises
    ------
    ValueError
        If ``target_scan_ref`` or ``control_scan_ref`` is missing, empty,
        or not a string.
    """
    target = data.get("target_scan_ref")
    if not target or not isinstance(target, str):
        raise ValueError(
            "target_scan_ref is required and must be a non-empty string"
        )

    control = data.get("control_scan_ref")
    if not control or not isinstance(control, str):
        raise ValueError(
            "control_scan_ref is required and must be a non-empty string"
        )

    request_id = data.get("request_id")
    if request_id is not None and not isinstance(request_id, str):
        raise ValueError("request_id must be a string if provided")

    return PredictionRequest(
        target_scan_ref=target,
        control_scan_ref=control,
        request_id=request_id,
    )


def validate_status(status: str) -> str:
    """Validate that *status* is a recognised job status.

    Raises
    ------
    ValueError
        If *status* is not in ``ALL_STATUSES``.
    """
    if status not in ALL_STATUSES:
        raise ValueError(
            f"Unknown status '{status}'. "
            f"Must be one of: {', '.join(sorted(ALL_STATUSES))}"
        )
    return status


# ---------------------------------------------------------------------------
# Safe response builders
# ---------------------------------------------------------------------------


def build_health_response(
    status: str = "ok",
    service: str = "bremen",
    version: str | None = None,
) -> HealthResponse:
    """Build a health check response with an ISO-8601 UTC timestamp."""
    from datetime import datetime, timezone

    return HealthResponse(
        status=status,
        service=service,
        version=version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def build_not_configured_model_response() -> ModelVersionResponse:
    """Build a safe ``not_configured`` model version response."""
    return ModelVersionResponse(
        model_configured=False,
        model_version=None,
        model_checksum=None,
        feature_schema_version=None,
        threshold_version=None,
        threshold_value=None,
        qc_criteria_version=None,
        model_status=MODEL_STATUS_NOT_CONFIGURED,
    )


def build_accepted_response(
    job_id: str,
    submitted_at: str,
) -> PredictionResponse:
    """Build an accepted response for a submitted prediction job."""
    return PredictionResponse(
        job_id=job_id,
        status=STATUS_ACCEPTED,
        submitted_at=submitted_at,
        links={"poll": f"/predictions/{job_id}"},
    )


def build_not_found_response(job_id: str) -> PredictionStatusResponse:
    """Build a ``not_found`` prediction status response."""
    return PredictionStatusResponse(
        job_id=job_id,
        status=STATUS_NOT_FOUND,
        submitted_at=None,
        updated_at=None,
    )
