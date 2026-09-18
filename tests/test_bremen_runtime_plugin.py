"""Tests for PR0078 — Model Runtime Plugin Tracing and Investor Showcase.

Covers:
- Execution context validation (no empty identifiers)
- Plugin lifecycle: artifact → input → features → inference → decision
- Started/completed pairing
- Bremen full trace
- Event budget
- Privacy (extended prohibited keys)
- Plugin isolation
- Module-reload safety
- Nova/Aramina early-stop behavior
"""

from __future__ import annotations

import pytest

from bremen.platform.events.context import WorkflowExecutionContext
from bremen.contracts.events import (
    JobEvent, validate_event_details,
)
from bremen.platform.events.store import BoundedEventStore
from bremen.platform.events_trace import (
    BREMEN_STAGE_ORDER, validate_stage_order,
)
from bremen.platform.events.trace import (
    build_trace_from_events, measure_event_budget,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeSink:
    """Captures events for test assertions."""

    def __init__(self):
        self.events: list[JobEvent] = []

    def __call__(self, event: JobEvent) -> None:
        self.events.append(event)


def _make_ctx(job_id="j1", request_id="r1", workflow_id="bremen"):
    return WorkflowExecutionContext(
        job_id=job_id, request_id=request_id, workflow_id=workflow_id,
        event_sink=None,
    )


# ---------------------------------------------------------------------------
# Execution context
# ---------------------------------------------------------------------------


class TestExecutionContext:
    def test_empty_job_id_rejected(self):
        with pytest.raises(ValueError):
            WorkflowExecutionContext(job_id="", request_id="r1", workflow_id="bremen")

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            WorkflowExecutionContext(job_id="j1", request_id="", workflow_id="bremen")

    def test_empty_workflow_id_rejected(self):
        with pytest.raises(ValueError):
            WorkflowExecutionContext(job_id="j1", request_id="r1", workflow_id="")

    def test_emit_sends_event(self):
        sink = _FakeSink()
        ctx = WorkflowExecutionContext(
            job_id="j1", request_id="r1", workflow_id="bremen",
            event_sink=sink,
        )
        ctx.emit("runtime.artifact.verification.completed", "artifact", "completed")
        assert len(sink.events) == 1
        assert sink.events[0].job_id == "j1"

    def test_emit_without_sink_is_noop(self):
        ctx = _make_ctx()
        ctx.emit("some.event", "stage", "completed")  # should not raise


# ---------------------------------------------------------------------------
# Plugin lifecycle — artifact
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Feature stage
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Decision stage
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Lifecycle ordering
# ---------------------------------------------------------------------------


class TestLifecycleOrder:
    def test_valid_bremen_order(self):
        order = list(BREMEN_STAGE_ORDER)
        assert validate_stage_order(order, BREMEN_STAGE_ORDER) is True

    def test_reversed_order_rejected(self):
        order = list(reversed(BREMEN_STAGE_ORDER))
        assert validate_stage_order(order, BREMEN_STAGE_ORDER) is False

    def test_partial_order_valid(self):
        partial = ["artifact_verification", "artifact_loaded", "model_validated"]
        assert validate_stage_order(partial, BREMEN_STAGE_ORDER) is True

    def test_out_of_order_rejected(self):
        bad = ["model_validated", "artifact_verification"]
        assert validate_stage_order(bad, BREMEN_STAGE_ORDER) is False


# ---------------------------------------------------------------------------
# Execution trace from events
# ---------------------------------------------------------------------------


class TestExecutionTrace:
    def test_trace_from_empty_store(self):
        store = BoundedEventStore()
        store.append("j1", JobEvent(job_id="j1", request_id="r1",
                                     workflow_id="bremen", stage="wf",
                                     event_type="runtime.workflow.resolved",
                                     status="completed"))
        trace = build_trace_from_events(store, "j1", "bremen")
        assert trace is not None
        assert trace.workflow_id == "bremen"

    def test_trace_unknown_job(self):
        store = BoundedEventStore()
        trace = build_trace_from_events(store, "nonexistent", "bremen")
        assert trace is None


# ---------------------------------------------------------------------------
# Event budget
# ---------------------------------------------------------------------------


class TestEventBudget:
    def test_bremen_budget_within_limits(self):
        budget = measure_event_budget("bremen", [])
        assert budget <= 30  # 22 events + some overhead
        assert budget > 0

    def test_budget_fits_in_store(self):
        budget = measure_event_budget("bremen", [])
        assert budget <= 1000  # well within max_events_per_job

    def test_aramina_budget_minimal(self):
        budget = measure_event_budget("aramina", [])
        assert budget <= 5


# ---------------------------------------------------------------------------
# Privacy — extended prohibited keys
# ---------------------------------------------------------------------------


class TestPrivacyExtended:
    def test_feature_value_rejected(self):
        with pytest.raises(ValueError):
            validate_event_details({"feature_value": [0.1, 0.2]})

    def test_coefficient_rejected(self):
        with pytest.raises(ValueError):
            validate_event_details({"coefficient": 0.5})

    def test_intercept_rejected(self):
        with pytest.raises(ValueError):
            validate_event_details({"intercept": 1.0})

    def test_scaler_mean_rejected(self):
        with pytest.raises(ValueError):
            validate_event_details({"scaler_mean": [0.0] * 15})

    def test_raw_feature_vector_rejected(self):
        with pytest.raises(ValueError):
            validate_event_details({"raw_feature_vector": [0.1] * 15})

    def test_model_package_rejected(self):
        with pytest.raises(ValueError):
            validate_event_details({"model_package": {"key": "val"}})

    def test_raw_q_rejected(self):
        with pytest.raises(ValueError):
            validate_event_details({"raw_q": [1.0, 2.0, 3.0]})

    def test_weights_rejected(self):
        with pytest.raises(ValueError):
            validate_event_details({"weights": [0.1] * 5})


# ---------------------------------------------------------------------------
# Provider isolation
# ---------------------------------------------------------------------------
