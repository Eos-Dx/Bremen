"""Public event trace ordering and projection; no execution interface."""

from typing import Any
from bremen.contracts.trace import ExecutionStage, ExecutionTraceSummary

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

NOVA_STAGE_ORDER: tuple[str, ...] = ("input_prepared",)

ARAMINA_STAGE_ORDER: tuple[str, ...] = ("readiness",)

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
    completed_stages: list[str],
    stage_order: tuple[str, ...],
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
    stages: list[ExecutionStage] = []

    completed = {s["stage_id"]: s for s in completed_stages}

    completed_count = 0
    for sid in stage_order:
        info = completed.get(sid)
        if info and info["status"] == "completed":
            stages.append(
                ExecutionStage(
                    stage_id=sid,
                    label=ALL_STAGE_LABELS.get(sid, sid),
                    status="completed",
                    started_at=info.get("started_at"),
                    completed_at=info.get("completed_at"),
                    duration_ms=info.get("duration_ms"),
                    safe_summary=info.get("safe_summary", {}),
                    reason_code=info.get("reason_code"),
                )
            )
            completed_count += 1
        elif info and info["status"] == "blocked":
            stages.append(
                ExecutionStage(
                    stage_id=sid,
                    label=ALL_STAGE_LABELS.get(sid, sid),
                    status="blocked",
                    reason_code=info.get("reason_code"),
                )
            )
        elif info and info["status"] == "failed":
            stages.append(
                ExecutionStage(
                    stage_id=sid,
                    label=ALL_STAGE_LABELS.get(sid, sid),
                    status="failed",
                    started_at=info.get("started_at"),
                    reason_code=info.get("reason_code"),
                )
            )
            completed_count += 1
        else:
            stages.append(
                ExecutionStage(
                    stage_id=sid,
                    label=ALL_STAGE_LABELS.get(sid, sid),
                    status="not_started",
                )
            )

    current = stages[-1].stage_id if stages else ""
    trace_status = (
        "completed"
        if completed_count == len(stage_order)
        else "running"
        if completed_count > 0
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
        duration_ms=sum(s.get("duration_ms") or 0 for s in completed_stages),
        completed_stage_count=completed_count,
        total_applicable_stage_count=len(stage_order),
        stages=stages,
    )
