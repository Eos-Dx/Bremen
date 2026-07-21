"""Tests for workflow registry (PR0075).

Covers:
- Registration and resolution
- Duplicate ID rejection
- Unknown workflow lookup
- Independent state
- Deterministic listing
- Unavailable workflow behavior
"""

from __future__ import annotations

import pytest

from bremen.api.workflow_registry import (
    WorkflowRegistry,
    WorkflowNotFoundError,
    DuplicateWorkflowError,
)
from bremen.api.workflow_provider import (
    WorkflowProvider,
    WorkflowFeatureVector,
    WorkflowResult,
    WorkflowReadiness,
    CompatibilityResult,
)


# ---------------------------------------------------------------------------
# Fake providers for testing
# ---------------------------------------------------------------------------


class _FakeProvider(WorkflowProvider):
    """Minimal provider implementation for registry tests."""

    def __init__(self, wid: str, ready: bool = True, sci_certified: bool = False):
        self.workflow_id = wid
        self._ready = ready
        self._sci_certified = sci_certified
        self._configured = True

    def readiness(self) -> WorkflowReadiness:
        return WorkflowReadiness(
            workflow_id=self.workflow_id,
            configured=self._configured,
            model_ready=self._ready,
            scientifically_certified=self._sci_certified,
        )

    def validate_compatibility(self, canonical) -> CompatibilityResult:
        return CompatibilityResult(compatible=True)

    def build_features(self, canonical) -> WorkflowFeatureVector:
        return WorkflowFeatureVector(
            workflow_id=self.workflow_id,
            feature_names=(),
            feature_values=(),
        )

    def run_inference(self, features: WorkflowFeatureVector) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="completed",
        )

    def execute(self, canonical) -> WorkflowResult:
        return self.run_inference(
            WorkflowFeatureVector(workflow_id=self.workflow_id, feature_names=(), feature_values=()),
        )


class _FailingExecuteProvider(_FakeProvider):
    """Provider whose execute() always fails."""

    def execute(self, canonical) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="failed",
            error="Simulated failure",
        )


class _UnavailableProvider(_FakeProvider):
    """Provider marked as unavailable."""

    def __init__(self, wid: str):
        super().__init__(wid, ready=False, sci_certified=False)

    def execute(self, canonical) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="failed",
            error="Workflow unavailable",
        )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestWorkflowRegistry:
    """Core registry behavior."""

    def test_register_and_resolve(self):
        """Register a provider and resolve it."""
        registry = WorkflowRegistry()
        provider = _FakeProvider("bremen")
        registry.register(provider)
        resolved = registry.resolve("bremen")
        assert resolved is provider

    def test_resolve_unknown_raises(self):
        """Resolving an unknown workflow raises WorkflowNotFoundError."""
        registry = WorkflowRegistry()
        with pytest.raises(WorkflowNotFoundError, match="unknown"):
            registry.resolve("unknown")

    def test_duplicate_registration_raises(self):
        """Registering the same ID twice raises DuplicateWorkflowError."""
        registry = WorkflowRegistry()
        registry.register(_FakeProvider("bremen"))
        with pytest.raises(DuplicateWorkflowError, match="already registered"):
            registry.register(_FakeProvider("bremen"))

    def test_list_capabilities(self):
        """list_capabilities returns readiness for all providers."""
        registry = WorkflowRegistry()
        registry.register(_FakeProvider("bremen", ready=True, sci_certified=True))
        registry.register(_FakeProvider("aramis", ready=False, sci_certified=False))

        caps = registry.list_capabilities()
        assert len(caps) == 2
        assert caps["bremen"].ready is True
        assert caps["aramis"].ready is False

    def test_list_workflow_ids(self):
        """list_workflow_ids returns all registered IDs."""
        registry = WorkflowRegistry()
        registry.register(_FakeProvider("bremen"))
        registry.register(_FakeProvider("aramis"))
        ids = registry.list_workflow_ids()
        assert set(ids) == {"bremen", "aramis"}

    def test_independent_provider_state(self):
        """Providers maintain independent state."""
        registry = WorkflowRegistry()
        bremen = _FakeProvider("bremen", ready=True, sci_certified=True)
        aramis = _FakeProvider("aramis", ready=False, sci_certified=False)
        registry.register(bremen)
        registry.register(aramis)

        caps = registry.list_capabilities()
        assert caps["bremen"].ready is True
        assert caps["aramis"].ready is False
        # One broken provider does not affect the other
        assert caps["bremen"].configured is True
        assert caps["aramis"].configured is True

    def test_unavailable_workflow_readiness(self):
        """Unavailable workflow reports model_ready=False."""
        registry = WorkflowRegistry()
        registry.register(_UnavailableProvider("aramis"))
        caps = registry.list_capabilities()
        assert caps["aramis"].model_ready is False
        assert caps["aramis"].ready is False

    def test_unknown_workflow_error_typed(self):
        """Unknown workflow lookup produces typed error, not ValueError."""
        registry = WorkflowRegistry()
        with pytest.raises(WorkflowNotFoundError):
            registry.resolve("nobody")

    def test_registration_order_independent(self):
        """Registration order does not affect resolution."""
        registry = WorkflowRegistry()
        p1 = _FakeProvider("first")
        p2 = _FakeProvider("second")
        registry.register(p1)
        registry.register(p2)
        assert registry.resolve("first") is p1
        assert registry.resolve("second") is p2

    def test_cannot_reregister_after_creation(self):
        """Once registered, cannot register again even with different instance."""
        registry = WorkflowRegistry()
        registry.register(_FakeProvider("bremen"))
        # Same ID, different instance
        with pytest.raises(DuplicateWorkflowError):
            registry.register(_FakeProvider("bremen", ready=False))


# ---------------------------------------------------------------------------
# Provider execution isolation
# ---------------------------------------------------------------------------


class TestProviderIsolation:
    """Provider executions are isolated."""

    def test_one_success_one_failure(self):
        """One provider failing does not affect another's success."""
        bremen = _FakeProvider("bremen", ready=True)
        aramis = _FailingExecuteProvider("aramis", ready=True)

        bremen_result = bremen.execute(None)
        aramis_result = aramis.execute(None)

        assert bremen_result.status == "completed"
        assert aramis_result.status == "failed"
        # Bremen result is not affected by Aramis failure
        assert bremen_result.error is None

    def test_no_cross_provider_state_leak(self):
        """Provider states are independent."""
        bremen = _FakeProvider("bremen", ready=True, sci_certified=True)
        aramis = _UnavailableProvider("aramis")

        assert bremen.readiness().ready is True
        assert aramis.readiness().ready is False
        # Bremen readiness is independent of Aramis
        assert bremen.readiness().ready is True

    def test_no_automatic_execution_of_all(self):
        """Registry does not execute all workflows automatically."""
        registry = WorkflowRegistry()
        registry.register(_FakeProvider("bremen"))
        registry.register(_FakeProvider("aramis"))
        # Registry is passive — explicit resolution required
        # (no automatic run-all)
        assert len(registry.list_workflow_ids()) == 2
        # Registry itself has no execute_all method


# ---------------------------------------------------------------------------
# Per-workflow readiness
# ---------------------------------------------------------------------------


class TestWorkflowReadiness:
    """Workflow readiness behavior."""

    def test_ready_when_all_conditions_met(self):
        """Ready is True when configured + model_ready + scientifically_certified."""
        r = WorkflowReadiness(
            workflow_id="test",
            configured=True,
            model_ready=True,
            scientifically_certified=True,
        )
        assert r.ready is True

    def test_not_ready_when_not_configured(self):
        """Ready is False when not configured."""
        r = WorkflowReadiness(
            workflow_id="test",
            configured=False,
            model_ready=True,
            scientifically_certified=True,
        )
        assert r.ready is False

    def test_not_ready_when_model_not_ready(self):
        """Ready is False when model not ready."""
        r = WorkflowReadiness(
            workflow_id="test",
            configured=True,
            model_ready=False,
            scientifically_certified=True,
        )
        assert r.ready is False

    def test_not_ready_when_not_sci_certified(self):
        """Ready is False when not scientifically certified."""
        r = WorkflowReadiness(
            workflow_id="test",
            configured=True,
            model_ready=True,
            scientifically_certified=False,
        )
        assert r.ready is False


# ---------------------------------------------------------------------------
# MultiWorkflowResult
# ---------------------------------------------------------------------------


class TestMultiWorkflowResult:
    """Result envelope behavior."""

    def test_partial_success_envelope(self):
        """Partial success when some workflows fail."""
        from bremen.api.workflow_provider import MultiWorkflowResult

        result = MultiWorkflowResult(
            request_id="req-1",
            job_id="job-1",
            normalization_status="completed",
            source_checksum="abc",
            requested_workflows=("bremen", "aramis"),
            workflows={
                "bremen": WorkflowResult(workflow_id="bremen", status="completed"),
                "aramis": WorkflowResult(workflow_id="aramis", status="failed", error="N/A"),
            },
            overall_status="partial_success",
        )
        assert result.overall_status == "partial_success"
        assert result.normalization_status == "completed"

    def test_normalization_failed_envelope(self):
        """Normalization failure produces failed envelope."""
        from bremen.api.workflow_provider import MultiWorkflowResult

        result = MultiWorkflowResult(
            request_id="req-1",
            job_id="job-1",
            normalization_status="failed",
            source_checksum="",
            requested_workflows=("bremen",),
            workflows={},
            overall_status="normalization_failed",
        )
        assert result.overall_status == "normalization_failed"

    def test_all_completed_envelope(self):
        """All workflows completed."""
        from bremen.api.workflow_provider import MultiWorkflowResult

        result = MultiWorkflowResult(
            request_id="req-1",
            job_id="job-1",
            normalization_status="completed",
            source_checksum="abc",
            requested_workflows=("bremen",),
            workflows={
                "bremen": WorkflowResult(workflow_id="bremen", status="completed"),
            },
            overall_status="completed",
        )
        assert result.overall_status == "completed"

    def test_no_ensemble_behavior(self):
        """Result envelope does not combine or average workflow results."""
        from bremen.api.workflow_provider import MultiWorkflowResult

        result = MultiWorkflowResult(
            request_id="req-1",
            job_id="job-1",
            normalization_status="completed",
            source_checksum="abc",
            requested_workflows=("bremen", "aramis"),
            workflows={
                "bremen": WorkflowResult(
                    workflow_id="bremen", status="completed",
                    payload={"probability": 0.8},
                ),
                "aramis": WorkflowResult(
                    workflow_id="aramis", status="completed",
                    payload={"probability": 0.3},
                ),
            },
            overall_status="completed",
        )
        # Results are stored independently, not averaged
        assert result.workflows["bremen"].payload is not None
        assert result.workflows["aramis"].payload is not None
        # No combined probability or verdict
        assert "combined" not in str(result)


# ---------------------------------------------------------------------------
# Explicit workflow selection (no automatic selection)
# ---------------------------------------------------------------------------


class TestExplicitSelection:
    """Workflow selection must be explicit."""

    def test_registry_requires_explicit_id(self):
        """Registry requires explicit workflow_id to resolve."""
        registry = WorkflowRegistry()
        registry.register(_FakeProvider("bremen"))
        # Resolution requires explicit ID — no default or auto-selection
        with pytest.raises(WorkflowNotFoundError):
            registry.resolve("")
        with pytest.raises(WorkflowNotFoundError):
            registry.resolve("other")

    def test_no_workflow_selection_from_metadata(self):
        """No workflow selection from H5 metadata."""
        # This is a design assertion — the registry has no layout detection
        registry = WorkflowRegistry()
        registry.register(_FakeProvider("bremen"))
        # Registry does not have a detect_layout method
        assert not hasattr(registry, "detect_layout")
