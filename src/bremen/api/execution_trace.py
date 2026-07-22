"""Execution trace projection from stored events.

Derives an ``ExecutionTraceSummary`` per workflow from the structured
``JobEvent`` records in ``BoundedEventStore``.  No second divergent
state machine — the trace is projected at query time.

PR0078 — model runtime plugin tracing and investor showcase.
"""

from __future__ import annotations

from typing import Any

from .event_store import BoundedEventStore
from .lifecycle_contracts import (
    ExecutionStage,
    ExecutionTraceSummary,
)
from .runtime_plugin import (
    BREMEN_STAGE_ORDER,
    BREMEN_STAGE_LABELS,
    ARAMIS_STAGE_ORDER,
    ALL_STAGE_LABELS,
)

# ---------------------------------------------------------------------------
# Stage mapping — event_type → stage_id
# ---------------------------------------------------------------------------

_STAGE_EVENT_MAP: dict[str, str] = {
    "runtime.artifact.verification.completed": "artifact_verification",
    "runtime.artifact.load.completed": "artifact_loaded",
    "runtime.artifact.adaptation.completed": "artifact_adapted",
    "runtime.model.validation.completed": "model_validated",
    "runtime.input.preparation.completed": "input_prepared",
    "runtime.features.completed": "features_produced",
    "runtime.features.validation.completed": "features_validated",
    "runtime.inference.completed": "inference_completed",
    "runtime.output.validation.completed": "output_validated",
    "runtime.decision.completed": "decision_completed",
    "runtime.report.completed": "report_completed",
}


def build_trace_from_events(
    store: BoundedEventStore, job_id: str, workflow_id: str,
) -> ExecutionTraceSummary | None:
    """Build an execution trace for *workflow_id* from stored events.

    Returns ``None`` if no events are found for the workflow.
    """
    all_events = store.get_events(job_id, since_sequence=0)
    wf_events = [
        e for e in all_events
        if e.workflow_id == workflow_id
    ]

    if not wf_events:
        return None

    # Determine stage order
    if workflow_id == "bremen":
        stage_order = BREMEN_STAGE_ORDER
    elif workflow_id == "aramis":
        stage_order = ARAMIS_STAGE_ORDER
    else:
        stage_order = BREMEN_STAGE_ORDER  # default

    # Map events to stages
    stage_info: dict[str, dict[str, Any]] = {}
    started_times: dict[str, str] = {}

    for ev in wf_events:
        sid = _STAGE_EVENT_MAP.get(ev.event_type)
        if sid is None:
            continue

        if sid not in stage_info:
            stage_info[sid] = {
                "stage_id": sid,
                "status": "completed",
                "duration_ms": ev.duration_ms or 0,
                "safe_summary": dict(ev.details),
            }

        # Capture started_at from the first event of this stage
        if sid not in started_times:
            started_times[sid] = ev.timestamp
            stage_info[sid]["started_at"] = ev.timestamp

        stage_info[sid]["completed_at"] = ev.timestamp

    # Build trace
    stages: list[ExecutionStage] = []
    completed_count = 0

    for sid in stage_order:
        info = stage_info.get(sid)
        if info and info.get("status") == "completed":
            stages.append(ExecutionStage(
                stage_id=sid,
                label=ALL_STAGE_LABELS.get(sid, sid),
                status="completed",
                started_at=info.get("started_at"),
                completed_at=info.get("completed_at"),
                duration_ms=info.get("duration_ms"),
                safe_summary=info.get("safe_summary", {}),
            ))
            completed_count += 1
        else:
            stages.append(ExecutionStage(
                stage_id=sid,
                label=ALL_STAGE_LABELS.get(sid, sid),
                status="not_started",
            ))

    first = wf_events[0]
    last = wf_events[-1]
    current = stages[-1].stage_id if stages else ""

    return ExecutionTraceSummary(
        workflow_id=workflow_id,
        current_stage=current,
        status=(
            "completed" if completed_count == len(stage_order)
            else "running" if completed_count > 0
            else "not_started"
        ),
        started_at=first.timestamp,
        completed_at=last.timestamp,
        duration_ms=sum(
            s.duration_ms or 0 for s in stages
        ),
        completed_stage_count=completed_count,
        total_applicable_stage_count=len(stage_order),
        stages=stages,
    )


# ---------------------------------------------------------------------------
# Event budget measurement
# ---------------------------------------------------------------------------


def measure_event_budget(
    workflow_id: str, staged_events: list[str],
) -> int:
    """Count expected events for a given workflow execution.

    Bremen normal path: ~22 events (11 stages × 2 started/completed).
    Worst-case with failures: ~26 events.
    """
    if workflow_id == "bremen":
        # 11 stages × 2 events (started+completed) + request events
        return len(BREMEN_STAGE_ORDER) * 2 + 4
    elif workflow_id == "aramis":
        return 2  # readiness check only
    return 0
