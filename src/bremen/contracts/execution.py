"""Public execution envelopes and readiness data; no scientific operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Workflow-specific types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowResult:
    """Result of a single workflow execution.

    ``failure_stage`` is an optional allowlisted public category for
    workflows that expose a structured failure taxonomy (PR0141, Aramina).
    It is ``None`` for workflows that do not, so Bremen behavior is
    unchanged.

    ``preprocessing_diagnostic`` is an optional allowlisted subdiagnostic
    (PR0142, Aramina). It contains only sanitized values and is ``None`` for
    every other workflow and for non-preprocessing failures.
    """

    workflow_id: str
    status: str  # "completed" | "failed" | "skipped"
    payload: dict[str, Any] | None = None
    error: str | None = None
    failure_stage: str | None = None
    preprocessing_diagnostic: dict[str, str] | None = None


@dataclass(frozen=True)
class WorkflowReadiness:
    """Independent readiness state for one workflow."""

    workflow_id: str
    configured: bool
    model_ready: bool
    scientifically_certified: bool

    @property
    def ready(self) -> bool:
        return self.configured and self.model_ready and self.scientifically_certified


# ---------------------------------------------------------------------------
# Multi-workflow result envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiWorkflowResult:
    """Result of a multi-workflow execution.

    One normalization produces one canonical case.  Each requested
    workflow runs independently against it.  Partial success is
    explicit: a working Bremen + failed Aramina produces
    ``overall_status = "partial_success"``.
    """

    request_id: str
    job_id: str
    normalization_status: str  # "completed" | "failed"
    source_checksum: str
    requested_workflows: tuple[str, ...]
    workflows: dict[str, WorkflowResult]
    overall_status: (
        str  # "completed" | "partial_success" | "failed" | "normalization_failed"
    )
    technical_demo_only: bool = True


# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionRequest:
    container_path: str
    workflow_id: str
    model_id: str = ""
    job_id: str = ""
    patient_id: str = ""
    target_side: str = ""
    parameters: Mapping[str, Any] = field(default_factory=dict)
