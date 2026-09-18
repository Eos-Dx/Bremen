"""Public execution trace metadata. Obsolete plugin stage carriers were removed.

No feature values, coefficients, raw arrays or private paths are exposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionStage:
    """Record of a single lifecycle stage within an execution trace."""

    stage_id: str
    label: str
    status: str  # "completed" | "failed" | "blocked" | "skipped" | "not_started"
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    safe_summary: dict[str, Any] = field(default_factory=dict)
    reason_code: str | None = None


# ---------------------------------------------------------------------------
# ExecutionTraceSummary — full trace of a workflow execution
# ---------------------------------------------------------------------------


@dataclass
class ExecutionTraceSummary:
    """Execution trace derived from stored events for one workflow."""

    workflow_id: str
    current_stage: str
    status: str  # "completed" | "failed" | "running" | "blocked" | "unavailable"
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    completed_stage_count: int = 0
    total_applicable_stage_count: int = 0
    stages: list[ExecutionStage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "current_stage": self.current_stage,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "completed_stage_count": self.completed_stage_count,
            "total_applicable_stage_count": self.total_applicable_stage_count,
            "stages": [
                {
                    "stage_id": s.stage_id,
                    "label": s.label,
                    "status": s.status,
                    "started_at": s.started_at,
                    "completed_at": s.completed_at,
                    "duration_ms": s.duration_ms,
                    "safe_summary": dict(s.safe_summary),
                    "reason_code": s.reason_code,
                }
                for s in self.stages
            ],
        }
