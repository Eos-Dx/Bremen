"""Typed intermediate lifecycle contracts.

Safe dataclasses representing boundaries between plugin execution
stages.  They expose metadata, counts, versions, and validation
status — never feature values, model coefficients, raw arrays, or
private paths.

PR0078 — model runtime plugin tracing and investor showcase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# PreparedArtifact — model artifact ready for inference
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedArtifact:
    """Model artifact after verification, loading, and adaptation."""

    model_id: str
    model_version: str
    model_schema_version: str
    checksum_status: str  # "verified" | "not_configured" | "failed"
    adaptation_applied: bool
    validation_status: str  # "completed" | "failed"
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PreparedWorkflowInput — input ready for feature construction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedWorkflowInput:
    """Workflow input after compatibility and preparation."""

    layout: str
    measurement_count: int
    side_count: int
    position_count: int
    compatible: bool
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# FeatureSet — feature vector metadata (no values)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureSet:
    """Feature vector metadata — names, counts, schema identity.

    Feature *values* are intentionally omitted from this public type.
    """

    feature_schema_version: str
    feature_names: tuple[str, ...]
    produced_count: int
    missing_count: int
    non_finite_count: int
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# FeatureValidation — structural validation of a feature vector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureValidation:
    """Result of validating a feature vector against its schema."""

    feature_schema_version: str
    expected_count: int
    produced_count: int
    order_valid: bool
    all_finite: bool
    schema_matched: bool
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ModelOutput — inference result metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelOutput:
    """Model inference output metadata — names and counts only."""

    output_schema: str
    output_count: int
    output_names: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# OutputValidation — validation of inference output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutputValidation:
    """Result of validating inference output structure."""

    schema_valid: bool
    output_count: int
    all_finite: bool
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DecisionOutput — final decision from the model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionOutput:
    """Decision after applying policy to model output."""

    decision_policy_id: str
    decision_code: str
    scientifically_certified: bool
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ExecutionStage — single-stage record within a trace
# ---------------------------------------------------------------------------


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
