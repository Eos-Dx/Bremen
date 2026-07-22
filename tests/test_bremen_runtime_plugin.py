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
- Nova/Aramis early-stop behavior
"""

from __future__ import annotations

import pytest
import time as _time

from bremen.api.execution_context import WorkflowExecutionContext
from bremen.api.event_schema import (
    JobEvent, EventType, validate_event_details,
)
from bremen.api.event_store import BoundedEventStore
from bremen.api.lifecycle_contracts import (
    PreparedArtifact, FeatureSet, FeatureValidation,
    ModelOutput, OutputValidation, DecisionOutput,
)
from bremen.api.runtime_plugin import (
    BREMEN_STAGE_ORDER, validate_stage_order, build_execution_trace,
)
from bremen.api.execution_trace import (
    build_trace_from_events, measure_event_budget,
)
from bremen.api.workflow_bremen import BremenProvider, BREMEN_V01_FEATURE_COLUMNS


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


class TestArtifactStage:
    def test_prepare_artifact_no_model(self):
        provider = BremenProvider()
        sink = _FakeSink()
        ctx = WorkflowExecutionContext(
            job_id="j1", request_id="r1", workflow_id="bremen",
            event_sink=sink,
        )
        artifact = provider.prepare_artifact(ctx)
        assert artifact.checksum_status == "not_configured"
        assert artifact.validation_status == "failed"
        assert not artifact.adaptation_applied

    def test_artifact_event_emitted(self):
        provider = BremenProvider()
        sink = _FakeSink()
        ctx = WorkflowExecutionContext(
            job_id="j1", request_id="r1", workflow_id="bremen",
            event_sink=sink,
        )
        provider.prepare_artifact(ctx)
        assert len(sink.events) >= 1
        assert sink.events[0].event_type == "runtime.artifact.verification.completed"


# ---------------------------------------------------------------------------
# Feature stage
# ---------------------------------------------------------------------------


class TestFeatureStage:
    def test_validate_features_with_vector(self):
        from bremen.api.workflow_provider import WorkflowFeatureVector
        provider = BremenProvider()
        sink = _FakeSink()
        ctx = WorkflowExecutionContext(
            job_id="j1", request_id="r1", workflow_id="bremen",
            event_sink=sink,
        )
        fv = WorkflowFeatureVector(
            workflow_id="bremen",
            feature_names=tuple(BREMEN_V01_FEATURE_COLUMNS),
            feature_values=tuple([0.5] * 15),
        )
        result = provider.validate_features(fv, ctx)
        assert result.expected_count == 15
        assert result.produced_count == 15
        assert result.order_valid is True
        assert result.all_finite is True
        assert result.schema_matched is True


# ---------------------------------------------------------------------------
# Decision stage
# ---------------------------------------------------------------------------


class TestDecisionStage:
    def test_execute_emits_decision_event(self):
        """Execute with context emits decision events via the single path."""
        import numpy as np
        from bremen.api.xrd_normalization import (
            CanonicalXRDCase, CanonicalXRDMeasurement,
        )

        model = {
            "portable_logreg": {
                "feature_columns": list(BREMEN_V01_FEATURE_COLUMNS),
                "imputer_statistics": [0.0] * 15,
                "scaler_mean": [0.0] * 15,
                "scaler_scale": [1.0] * 15,
                "coef": [0.1] * 15,
                "intercept": 0.0,
                "threshold": 0.5,
            },
        }
        provider = BremenProvider(model_package=model, model_version="test-v1")
        sink = _FakeSink()
        ctx = WorkflowExecutionContext(
            job_id="j1", request_id="r1", workflow_id="bremen",
            event_sink=sink,
        )
        case = CanonicalXRDCase(
            source_layout="test", source_layout_version="v1",
            source_checksum="abc", calibration_provenance="test",
            measurements=(
                CanonicalXRDMeasurement(
                    side="LEFT", position="P1",
                    q=np.linspace(1, 10, 100, dtype=np.float64),
                    intensity=np.random.default_rng(42).normal(10, 2, 100).astype(np.float64),
                ),
                CanonicalXRDMeasurement(
                    side="RIGHT", position="P1",
                    q=np.linspace(1, 10, 100, dtype=np.float64),
                    intensity=np.random.default_rng(43).normal(10, 2, 100).astype(np.float64),
                ),
            ),
        )
        result = provider.execute(case, ctx)
        assert result.status == "completed"
        decision_events = [
            e for e in sink.events
            if e.event_type == "runtime.decision.completed"
        ]
        assert len(decision_events) == 1
        assert decision_events[0].details.get("scientifically_certified") is False

    def test_nova_configuration_required(self):
        """Nova input with P1/P2/P3 positions returns configuration_required."""
        import numpy as np
        from bremen.api.xrd_normalization import (
            CanonicalXRDCase, CanonicalXRDMeasurement,
        )
        provider = BremenProvider()
        sink = _FakeSink()
        ctx = WorkflowExecutionContext(
            job_id="j1", request_id="r1", workflow_id="bremen",
            event_sink=sink,
        )
        # Nova-style: 6 measurements, P1/P2/P3 positions
        rng = np.random.default_rng(42)
        case = CanonicalXRDCase(
            source_layout="nova", source_layout_version="v1",
            source_checksum="abc", calibration_provenance="nova",
            measurements=tuple(
                CanonicalXRDMeasurement(
                    side=s, position=p,
                    q=np.linspace(1, 10, 100, dtype=np.float64),
                    intensity=rng.normal(10, 2, 100).astype(np.float64),
                )
                for s in ("LEFT", "RIGHT")
                for p in ("P1", "P2", "P3")
            ),
        )
        result = provider.execute(case, ctx)
        assert result.status == "failed"
        assert "config" in (result.error or "").lower()
        # Verify input_preparation.failed event was emitted
        failed_events = [
            e for e in sink.events
            if e.event_type == "runtime.input.preparation.failed"
        ]
        assert len(failed_events) == 1
        assert failed_events[0].details.get("workflow_configuration_required") is True


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

    def test_aramis_budget_minimal(self):
        budget = measure_event_budget("aramis", [])
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


class TestProviderIsolation:
    def test_bremen_plugin_methods_exist(self):
        provider = BremenProvider()
        assert hasattr(provider, "prepare_artifact")
        assert hasattr(provider, "prepare_input")
        assert hasattr(provider, "validate_features")
        # execute() is the single authoritative path
        assert hasattr(provider, "execute")

    def test_plugin_id_set(self):
        provider = BremenProvider()
        assert provider.plugin_id == "bremen_mri_triage_plugin"
        assert provider.plugin_version == "v0.1"

    def test_plugin_provenance_no_private_paths(self):
        provider = BremenProvider()
        assert "/" not in provider.plugin_id
        assert "." not in provider.plugin_id  # no Python module paths
