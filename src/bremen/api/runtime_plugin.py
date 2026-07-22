"""Workflow runtime plugin contract and lifecycle state machine.

Defines the ``WorkflowRuntimePlugin`` interface (composed stage layer
owned by the provider, not a second registry) and a validated
lifecycle ordering state machine.

PR0078 — model runtime plugin tracing and investor showcase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .execution_context import WorkflowExecutionContext
from .lifecycle_contracts import (
    PreparedArtifact,
    PreparedWorkflowInput,
    FeatureSet,
    FeatureValidation,
    ModelOutput,
    OutputValidation,
    DecisionOutput,
    ExecutionStage,
    ExecutionTraceSummary,
)
from .workflow_provider import WorkflowReadiness


# ---------------------------------------------------------------------------
# Plugin interface
# ---------------------------------------------------------------------------


class WorkflowRuntimePlugin(ABC):
    """Composable runtime plugin owned by a ``WorkflowProvider``.

    Each lifecycle stage is a separate method.  The provider decides
    which stages to call based on readiness and compatibility.
    The orchestrator calls ``execute_with_trace()`` instead of
    ``execute()`` when the provider implements this interface.

    This is NOT a second workflow registry.  ``WorkflowRegistry``
    remains authoritative — the plugin is discovered via
    ``isinstance(provider, WorkflowRuntimePlugin)``.
    """

    workflow_id: str = ""
    plugin_id: str = ""
    plugin_version: str = ""

    @abstractmethod
    def readiness(
        self, context: WorkflowExecutionContext,
    ) -> WorkflowReadiness: ...

    @abstractmethod
    def prepare_artifact(
        self, context: WorkflowExecutionContext,
    ) -> PreparedArtifact: ...

    @abstractmethod
    def prepare_input(
        self, canonical_case: Any, context: WorkflowExecutionContext,
    ) -> PreparedWorkflowInput: ...

    @abstractmethod
    def build_features(
        self, prepared_input: Any, context: WorkflowExecutionContext,
    ) -> FeatureSet: ...

    @abstractmethod
    def validate_features(
        self, features: Any, context: WorkflowExecutionContext,
    ) -> FeatureValidation: ...

    @abstractmethod
    def run_model(
        self, artifact: Any, features: Any,
        context: WorkflowExecutionContext,
    ) -> ModelOutput: ...

    @abstractmethod
    def validate_output(
        self, output: Any, context: WorkflowExecutionContext,
    ) -> OutputValidation: ...

    @abstractmethod
    def apply_decision(
        self, output: Any, context: WorkflowExecutionContext,
    ) -> DecisionOutput: ...


# ---------------------------------------------------------------------------
# Lifecycle stage order (Bremen canonical path)
# ---------------------------------------------------------------------------

BREMEN_STAGE_ORDER: tuple[str, ...] = (
    "artifact_verification",
    "artifact_loaded",
    "artifact_adapted",
    "model_validated",
    "input_prepared",
    "features_produced",
    "features_validated",
    "inference_completed",
    "output_validated",
    "decision_completed",
    "report_completed",
)

BREMEN_STAGE_LABELS: dict[str, str] = {
    "artifact_verification": "Artifact verification",
    "artifact_loaded": "Artifact loaded",
    "artifact_adapted": "Artifact adapted",
    "model_validated": "Model validated",
    "input_prepared": "Input prepared",
    "features_produced": "Features produced",
    "features_validated": "Features validated",
    "inference_completed": "Inference completed",
    "output_validated": "Output validated",
    "decision_completed": "Decision completed",
    "report_completed": "Report completed",
}

NOVA_STAGE_ORDER: tuple[str, ...] = (
    "input_prepared",
)

ARAMIS_STAGE_ORDER: tuple[str, ...] = (
    "readiness",
)

ALL_STAGE_LABELS: dict[str, str] = {
    **BREMEN_STAGE_LABELS,
    "readiness": "Workflow readiness",
    "unavailable": "Workflow unavailable",
    "configuration_required": "Configuration required",
}


# ---------------------------------------------------------------------------
# Ordering validation
# ---------------------------------------------------------------------------


def validate_stage_order(
    completed_stages: list[str], stage_order: tuple[str, ...],
) -> bool:
    """Return ``True`` if *completed_stages* respects *stage_order*.

    Stages that appear in *completed_stages* must appear in
    *stage_order* order.  Missing stages are allowed (early stop).
    """
    order_map = {s: i for i, s in enumerate(stage_order)}
    last_idx = -1
    for stage in completed_stages:
        idx = order_map.get(stage)
        if idx is None:
            continue  # unknown stage — skip
        if idx < last_idx:
            return False  # out of order
        last_idx = idx
    return True


def build_execution_trace(
    completed_stages: list[dict[str, Any]],
    stage_order: tuple[str, ...],
    workflow_id: str,
) -> ExecutionTraceSummary:
    """Build an ``ExecutionTraceSummary`` from a list of completed stages.

    *completed_stages* is a list of dicts with keys:
    - stage_id, status, started_at, completed_at, duration_ms,
      safe_summary, reason_code
    """
    order_set = set(stage_order)
    stages: list[ExecutionStage] = []

    completed = {s["stage_id"]: s for s in completed_stages}

    completed_count = 0
    for sid in stage_order:
        info = completed.get(sid)
        if info and info["status"] == "completed":
            stages.append(ExecutionStage(
                stage_id=sid,
                label=ALL_STAGE_LABELS.get(sid, sid),
                status="completed",
                started_at=info.get("started_at"),
                completed_at=info.get("completed_at"),
                duration_ms=info.get("duration_ms"),
                safe_summary=info.get("safe_summary", {}),
                reason_code=info.get("reason_code"),
            ))
            completed_count += 1
        elif info and info["status"] == "blocked":
            stages.append(ExecutionStage(
                stage_id=sid,
                label=ALL_STAGE_LABELS.get(sid, sid),
                status="blocked",
                reason_code=info.get("reason_code"),
            ))
        elif info and info["status"] == "failed":
            stages.append(ExecutionStage(
                stage_id=sid,
                label=ALL_STAGE_LABELS.get(sid, sid),
                status="failed",
                started_at=info.get("started_at"),
                reason_code=info.get("reason_code"),
            ))
            completed_count += 1
        else:
            stages.append(ExecutionStage(
                stage_id=sid,
                label=ALL_STAGE_LABELS.get(sid, sid),
                status="not_started",
            ))

    current = stages[-1].stage_id if stages else ""
    trace_status = (
        "completed" if completed_count == len(stage_order)
        else "running" if completed_count > 0
        else "blocked"
    )

    first = completed_stages[0] if completed_stages else {}
    last = completed_stages[-1] if completed_stages else {}

    return ExecutionTraceSummary(
        workflow_id=workflow_id,
        current_stage=current,
        status=trace_status,
        started_at=first.get("started_at"),
        completed_at=last.get("completed_at"),
        duration_ms=sum(
            s.get("duration_ms") or 0 for s in completed_stages
        ),
        completed_stage_count=completed_count,
        total_applicable_stage_count=len(stage_order),
        stages=stages,
    )
