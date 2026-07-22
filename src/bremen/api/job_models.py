"""Analysis job and workflow-run models for the multi-workflow workspace.

Typed, serialisation-safe dataclasses.  No raw arrays, no PONI text,
no private filesystem paths, no patient identifiers.

PR0077 — multi-workflow analysis workspace, event stream, and reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# WorkflowRun — per-workflow execution record
# ---------------------------------------------------------------------------


@dataclass
class WorkflowRun:
    """Independent execution record for a single workflow within a job.

    A failed Aramis run must not erase a completed Bremen run, and
    vice versa.
    """

    workflow_id: str
    status: str  # pending | running | completed | workflow_unavailable | workflow_incompatible | workflow_configuration_required | selection_required | model_invalid | inference_failed | report_failed
    model_identity: dict[str, str] = field(default_factory=dict)
    readiness_snapshot: dict[str, bool] = field(default_factory=dict)
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    result_summary: dict[str, Any] = field(default_factory=dict)
    report_metadata: dict[str, Any] | None = None
    failure: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "model_identity": dict(self.model_identity),
            "readiness_snapshot": dict(self.readiness_snapshot),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "result_summary": dict(self.result_summary),
            "report_metadata": self.report_metadata,
            "failure": self.failure,
        }


# ---------------------------------------------------------------------------
# ReportMetadata — lightweight report reference
# ---------------------------------------------------------------------------


@dataclass
class ReportMetadata:
    """Reference to a workflow-specific report without embedding its full payload."""

    report_id: str
    workflow_id: str
    report_schema_version: str
    status: str  # not_requested | pending | generating | available | failed | unavailable
    generated_at: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    scientifically_certified: bool = False


# ---------------------------------------------------------------------------
# AnalysisJob — top-level job envelope
# ---------------------------------------------------------------------------


@dataclass
class AnalysisJob:
    """Top-level analysis job record.

    Owns one normalisation, multiple independent workflow runs, and
    per-workflow report references.
    """

    job_id: str
    request_id: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    overall_status: str = "queued"  # queued | staging | normalizing | running | completed | partial_success | workflow_configuration_required | failed | cancelled | expired
    input_summary: dict[str, Any] = field(default_factory=dict)
    normalization_summary: dict[str, Any] = field(default_factory=dict)
    requested_workflows: tuple[str, ...] = ()
    workflow_runs: dict[str, WorkflowRun] = field(default_factory=dict)
    reports: dict[str, ReportMetadata] = field(default_factory=dict)
    event_cursor: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "request_id": self.request_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "overall_status": self.overall_status,
            "input_summary": dict(self.input_summary),
            "normalization_summary": dict(self.normalization_summary),
            "requested_workflows": list(self.requested_workflows),
            "workflow_runs": {
                wid: wr.to_dict() for wid, wr in self.workflow_runs.items()
            },
            "reports": {
                wid: {
                    "report_id": rm.report_id,
                    "workflow_id": rm.workflow_id,
                    "report_schema_version": rm.report_schema_version,
                    "status": rm.status,
                    "generated_at": rm.generated_at,
                    "model_id": rm.model_id,
                    "model_version": rm.model_version,
                    "scientifically_certified": rm.scientifically_certified,
                }
                for wid, rm in self.reports.items()
            },
            "event_cursor": self.event_cursor,
        }
