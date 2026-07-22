"""Versioned, structured job event model.

Immutable, serialisable events for the multi-workflow analysis lifecycle.
Every event carries a stable ``schema_version``, opaque event/job/request IDs,
a monotonic per-job ``sequence``, UTC ``timestamp``, and an allowlisted
``details`` mapping.

PR0077 — multi-workflow analysis workspace, event stream, and reports.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# Prohibited detail keys — fail-fast on append
# ---------------------------------------------------------------------------

_PROHIBITED_DETAIL_KEYS: frozenset[str] = frozenset({
    "patient_id",
    "patient_name",
    "operator_id",
    "scan_session_id",
    "specimen_id",
    "ponifile",
    "poni_text",
    "raw_data",
    "raw_array",
    "h5_path",
    "dataset_path",
    "local_path",
    "model_coefficients",
    "traceback",
    "exception_object",
})

# ---------------------------------------------------------------------------
# Event types enum
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    """Typed lifecycle events covering the full orchestration path."""

    # Request lifecycle
    REQUEST_ACCEPTED = "runtime.request.accepted"

    # Input staging
    INPUT_STAGING_STARTED = "runtime.input.staging.started"
    INPUT_STAGING_COMPLETED = "runtime.input.staging.completed"

    # Normalization
    NORMALIZATION_STARTED = "runtime.normalization.started"
    NORMALIZATION_COMPLETED = "runtime.normalization.completed"
    NORMALIZATION_FAILED = "runtime.normalization.failed"

    # Workflow resolution
    WORKFLOW_RESOLVED = "runtime.workflow.resolved"
    WORKFLOW_STARTED = "runtime.workflow.started"
    WORKFLOW_NOT_FOUND = "runtime.workflow.not_found"

    # Model loading
    MODEL_LOAD_STARTED = "runtime.model.load.started"
    MODEL_LOAD_COMPLETED = "runtime.model.load.completed"

    # Model validation
    MODEL_VALIDATION_STARTED = "runtime.model.validation.started"
    MODEL_VALIDATION_COMPLETED = "runtime.model.validation.completed"

    # Features
    FEATURES_STARTED = "runtime.features.started"
    FEATURES_COMPLETED = "runtime.features.completed"

    # Inference
    INFERENCE_STARTED = "runtime.inference.started"
    INFERENCE_COMPLETED = "runtime.inference.completed"

    # Decision
    DECISION_STARTED = "runtime.decision.started"
    DECISION_COMPLETED = "runtime.decision.completed"

    # Report
    REPORT_STARTED = "runtime.report.started"
    REPORT_COMPLETED = "runtime.report.completed"

    # Workflow completion
    WORKFLOW_COMPLETED = "runtime.workflow.completed"
    WORKFLOW_FAILED = "runtime.workflow.failed"

    # Request completion
    REQUEST_COMPLETED = "runtime.request.completed"


# ---------------------------------------------------------------------------
# JobEvent dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JobEvent:
    """A single immutable, versioned, structured job event.

    All IDs are opaque (UUIDs).  ``details`` is allowlisted to safe
    technical metadata — no patient identifiers, raw paths, PONI
    contents, model coefficients, or raw data.
    """

    schema_version: str = SCHEMA_VERSION
    event_id: str = field(default_factory=lambda: str(_uuid.uuid4()))
    sequence: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    job_id: str = ""
    request_id: str = ""
    workflow_id: str | None = None
    stage: str = ""
    event_type: str = ""
    status: str = ""
    duration_ms: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a deterministic JSON-safe dict."""
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "job_id": self.job_id,
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "stage": self.stage,
            "event_type": self.event_type,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "details": dict(self.details),
        }

    def __repr__(self) -> str:
        return (
            f"JobEvent(event_id={self.event_id!r}, sequence={self.sequence}, "
            f"event_type={self.event_type!r}, status={self.status!r})"
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_event_details(details: dict[str, Any] | None) -> None:
    """Raise ``ValueError`` if *details* contains any prohibited key.

    Parameters
    ----------
    details : The details dict to validate (may be ``None``).
    """
    if details is None:
        return
    for key in details:
        if key in _PROHIBITED_DETAIL_KEYS:
            raise ValueError(
                f"Event details contain prohibited key: {key!r}"
            )


def allowed_event_details(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *raw* with only safe allowed keys.

    Does NOT mutate the input.
    """
    return {k: v for k, v in raw.items() if k not in _PROHIBITED_DETAIL_KEYS}
