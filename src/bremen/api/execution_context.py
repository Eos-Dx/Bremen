"""Workflow execution context and event-sink protocol.

Provides an explicit, immutable execution context that is injected
into plugin lifecycle methods.  No hidden global state, no patient
identifiers, no private paths.

PR0078 — model runtime plugin tracing and investor showcase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .event_schema import JobEvent


# ---------------------------------------------------------------------------
# EventSink protocol
# ---------------------------------------------------------------------------


class EventSink(Protocol):
    """Callable protocol for decoupled event emission.

    Implementations wrap ``BoundedEventStore.append()`` so that
    plugins never touch the store directly.
    """

    def __call__(self, event: JobEvent) -> None: ...


# ---------------------------------------------------------------------------
# WorkflowExecutionContext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowExecutionContext:
    """Immutable execution context for a single workflow run.

    All identifiers are non-empty opaque strings.  The ``event_sink``
    is an explicit callable — no hidden lookup of global state.
    """

    job_id: str
    request_id: str
    workflow_id: str
    event_sink: EventSink | None = None
    runtime_build_version: str = ""
    model_id: str | None = None
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    deadline_seconds: int | None = None

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id must not be empty")
        if not self.request_id:
            raise ValueError("request_id must not be empty")
        if not self.workflow_id:
            raise ValueError("workflow_id must not be empty")

    def emit(
        self,
        event_type: str,
        stage: str,
        status: str,
        *,
        duration_ms: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Convenience: emit a single event via ``event_sink``.

        Does nothing when ``event_sink`` is ``None``.
        """
        if self.event_sink is None:
            return
        event = JobEvent(
            job_id=self.job_id,
            request_id=self.request_id,
            workflow_id=self.workflow_id,
            stage=stage,
            event_type=event_type,
            status=status,
            duration_ms=duration_ms,
            details=details or {},
        )
        self.event_sink(event)
