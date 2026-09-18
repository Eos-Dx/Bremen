"""Execution trace projection from stored events.

Derives an ``ExecutionTraceSummary`` per workflow from the structured
``JobEvent`` records in ``BoundedEventStore``.  No second divergent
state machine — the trace is projected at query time.

PR0078 — model runtime plugin tracing and investor showcase.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime

from bremen.platform.events.store import BoundedEventStore
from bremen.contracts.trace import (
    ExecutionStage,
    ExecutionTraceSummary,
)
from bremen.platform.events_trace import (
    BREMEN_STAGE_ORDER,
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
    "runtime.model.execution.completed": "inference_completed",
    "runtime.output.completed": "output_validated",
    "runtime.input.preparation.failed": "input_prepared",
    "runtime.features.failed": "features_produced",
    "runtime.model.execution.failed": "inference_completed",
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

    # Only recorded events prove execution. Aramina has no readiness-only
    # pipeline anymore; never invent unobserved scientific stages.
    stage_info: dict[str, dict[str, Any]] = {}
    terminal = None
    failing_stage = None
    for ev in wf_events:
        sid = _STAGE_EVENT_MAP.get(ev.event_type)
        if ev.event_type in {"runtime.workflow.completed", "runtime.workflow.failed",
                             "runtime.workflow.not_found"}:
            terminal = ev
            if ev.status == "failed":
                sid = ev.details.get("failure_stage") or failing_stage or "workflow"
            elif not stage_info:
                sid = "workflow"
        if sid is None:
            continue
        status = "failed" if ev.status == "failed" else "completed"
        if status == "failed":
            failing_stage = sid
        previous = stage_info.get(sid, {})
        stage_info[sid] = dict(
            stage_id=sid, label=ALL_STAGE_LABELS.get(sid, sid), status=status,
            started_at=previous.get("started_at", ev.timestamp),
            completed_at=ev.timestamp, duration_ms=ev.duration_ms,
            safe_summary=dict(ev.details),
            reason_code=ev.details.get("reason_code") or ev.details.get("reason")
                        or previous.get("reason_code"),
        )

    order = list(BREMEN_STAGE_ORDER) if workflow_id == "bremen" else []
    order.extend(sid for sid in stage_info if sid not in order)
    stages = [ExecutionStage(**stage_info[sid]) if sid in stage_info else
              ExecutionStage(sid, ALL_STAGE_LABELS.get(sid, sid), "not_started")
              for sid in order]
    completed_count = sum(stage.status == "completed" for stage in stages)
    status = "running"
    if failing_stage:
        status = "failed"
    elif terminal is not None and terminal.status == "completed":
        status = "completed"
    elif stages and completed_count == len(stages):
        status = "completed"
    first, last = wf_events[0], wf_events[-1]
    duration = (datetime.fromisoformat(last.timestamp) -
                datetime.fromisoformat(first.timestamp)).total_seconds() * 1000
    # The executor records full elapsed duration on request completion, which
    # is deliberately not workflow-scoped. Do not lose it in the filter above.
    recorded_duration = next((e.duration_ms for e in reversed(all_events)
                              if e.event_type == "runtime.request.completed"
                              and e.duration_ms is not None), None)
    return ExecutionTraceSummary(
        workflow_id=workflow_id,
        current_stage=failing_stage or next(reversed(stage_info), "workflow"),
        status=status, started_at=first.timestamp,
        completed_at=last.timestamp if status in {"completed", "failed"} else None,
        duration_ms=recorded_duration if recorded_duration is not None else round(duration),
        completed_stage_count=completed_count,
        total_applicable_stage_count=len(stages), stages=stages,
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
    elif workflow_id == "aramina":
        return 2  # readiness check only
    return 0
