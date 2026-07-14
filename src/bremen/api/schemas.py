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
MODEL_STATUS_READY = "ready"
MODEL_STATUS_ERROR = "error"
MODEL_STATUS_INVALID = "invalid"  # kept for backward compatibility
MODEL_STATUS_UNAVAILABLE = "unavailable"  # kept for backward compatibility

ALL_MODEL_STATUSES = frozenset({
    MODEL_STATUS_NOT_CONFIGURED,
    MODEL_STATUS_CONFIGURED,
    MODEL_STATUS_READY,
    MODEL_STATUS_ERROR,
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
    model_status: str  # "not_configured" | "configured" | "ready" | "error"
    model_uri_configured: bool = False
    checksum_configured: bool = False
    error_category: str | None = None


@dataclass
class PredictionRequest:
    """Request body for ``POST /predictions``.

    Exactly one of ``h5_path`` or ``h5_uri`` must be provided.
    ``h5_checksum`` is optional and must match ``sha256:<64hex>``
    if provided.
    """

    target_scan_ref: str
    control_scan_ref: str
    h5_path: str | None = None
    h5_uri: str | None = None
    h5_checksum: str | None = None
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
    decision_support_report: dict[str, Any] | None = None


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
        If both ``h5_path`` and ``h5_uri`` are provided (mutual exclusivity).
        If neither ``h5_path`` nor ``h5_uri`` is provided.
        If ``h5_uri`` is present but does not start with ``s3://``.
        If ``h5_checksum`` is present but does not match ``sha256:<64hex>``.
    """
    import re

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

    h5_path = data.get("h5_path")
    h5_uri = data.get("h5_uri")
    h5_checksum = data.get("h5_checksum")

    # Validate h5_path / h5_uri mutual exclusivity
    if h5_path is not None and h5_uri is not None:
        raise ValueError(
            "Exactly one of h5_path or h5_uri must be provided, not both"
        )

    if h5_path is None and h5_uri is None:
        raise ValueError(
            "Either h5_path or h5_uri must be provided"
        )

    # Validate h5_uri format if present
    if h5_uri is not None:
        if not isinstance(h5_uri, str) or not h5_uri.startswith("s3://"):
            raise ValueError(
                "h5_uri must start with 's3://'"
            )

    # Validate h5_checksum format if present
    if h5_checksum is not None:
        if not isinstance(h5_checksum, str):
            raise ValueError("h5_checksum must be a string if provided")
        # Accept sha256:<64 hex chars> (case-insensitive hex)
        if not re.match(r"^sha256:[0-9a-fA-F]{64}$", h5_checksum):
            raise ValueError(
                "h5_checksum must match 'sha256:<64 hex chars>' pattern"
            )

    # Normalize h5_path: ensure it's a non-empty string if provided
    if h5_path is not None:
        if not isinstance(h5_path, str) or not h5_path:
            raise ValueError("h5_path must be a non-empty string if provided")

    return PredictionRequest(
        target_scan_ref=target,
        control_scan_ref=control,
        h5_path=h5_path,
        h5_uri=h5_uri,
        h5_checksum=h5_checksum,
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
        model_uri_configured=False,
        checksum_configured=False,
        error_category=None,
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
