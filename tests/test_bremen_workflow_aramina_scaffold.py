"""Tests for Aramina workflow provider (PR0075).

Covers:
- Aramina provider scaffold
- Readiness state (unavailable)
- Typed WorkflowUnavailableError
- Compatibility verification
- Provider isolation from Bremen
- No cross-imports between Bremen and Aramina providers
- Lifecycle/availability behavior
"""

from __future__ import annotations

import pytest

from bremen.api.workflow_provider import (
    WorkflowFeatureVector,
    WorkflowResult,
    WorkflowReadiness,
)
from bremen.api.workflow_aramina_scaffold import (
    AraminaProvider,
    AraminaWorkflowError,
    WorkflowUnavailableError,
)


# ---------------------------------------------------------------------------
# Provider identity
# ---------------------------------------------------------------------------


class TestAraminaProviderIdentity:
    """Aramina provider identity and lifecycle."""

    def test_workflow_id_is_aramina(self):
        """Provider has correct workflow_id."""
        provider = AraminaProvider()
        assert provider.workflow_id == "aramina"

    def test_default_state_is_unavailable(self):
        """Default state is unavailable."""
        provider = AraminaProvider()
        readiness = provider.readiness()
        assert readiness.configured is True  # provider exists
        assert readiness.model_ready is False  # no model loaded
        assert readiness.ready is False

    def test_readiness_structured(self):
        """Readiness is a proper WorkflowReadiness."""
        provider = AraminaProvider()
        r = provider.readiness()
        assert isinstance(r, WorkflowReadiness)
        assert r.workflow_id == "aramina"
        assert r.configured is True
        assert r.model_ready is False
        assert r.scientifically_certified is False
        assert r.ready is False


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


class TestAraminaCompatibility:
    """Compatibility validation (always compatible as scaffold)."""

    def test_returns_compatible_result(self):
        """Compatibility check returns a valid result."""
        provider = AraminaProvider()
        result = provider.validate_compatibility(None)
        assert result.compatible is True


# ---------------------------------------------------------------------------
# Feature construction — unavailable
# ---------------------------------------------------------------------------


class TestAraminaFeaturesUnavailable:
    """Feature construction raises WorkflowUnavailableError."""

    def test_build_features_raises_unavailable(self):
        """build_features raises WorkflowUnavailableError."""
        provider = AraminaProvider()
        with pytest.raises(WorkflowUnavailableError, match="not available"):
            provider.build_features(None)

    def test_unavailable_error_is_typed(self):
        """WorkflowUnavailableError is typed (not generic ValueError)."""
        provider = AraminaProvider()
        with pytest.raises(WorkflowUnavailableError):
            provider.build_features(None)
        # Verify it's a typed exception, not ValueError
        assert issubclass(WorkflowUnavailableError, AraminaWorkflowError)


# ---------------------------------------------------------------------------
# Inference — unavailable
# ---------------------------------------------------------------------------


class TestAraminaInferenceUnavailable:
    """Inference returns unavailable result."""

    def test_run_inference_returns_failed(self):
        """run_inference returns failed result with explanation."""
        provider = AraminaProvider()
        fv = WorkflowFeatureVector(
            workflow_id="aramina",
            feature_names=(),
            feature_values=(),
        )
        result = provider.run_inference(fv)
        assert result.status == "failed"
        assert result.workflow_id == "aramina"
        assert result.error is not None
        assert "unavailable" in (result.error or "").lower()

    def test_execute_returns_failed(self):
        """execute returns failed result."""
        provider = AraminaProvider()
        result = provider.execute(None)
        assert result.status == "failed"
        assert "unavailable" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# Provider isolation
# ---------------------------------------------------------------------------


class TestAraminaIsolation:
    """Aramina is isolated from Bremen."""

    def test_no_cross_imports_from_bremen(self):
        """Aramina provider module does not import Bremen provider."""
        from bremen.api import workflow_aramina_scaffold as aramina_mod
        import ast
        import inspect
        source = inspect.getsource(aramina_mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "bremen" not in alias.name.lower() or alias.name == "bremen.api.workflow_provider", \
                        f"Unexpected import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "workflow_bremen" not in module, \
                    f"Imports from workflow_bremen: {module}"

    def test_aramina_failure_does_not_affect_bremen(self):
        """Aramina failure does not affect Bremen provider state."""
        from bremen.api.workflow_bremen import BremenProvider
        from bremen.api.workflow_aramina_scaffold import AraminaProvider

        aramina = AraminaProvider()
        # Aramina is unavailable
        aramina_readiness = aramina.readiness()
        assert aramina_readiness.ready is False

        # Bremen is independently configurable
        bremen = BremenProvider()
        bremen_readiness = bremen.readiness()
        # Bremen's readiness is independent of Aramina
        assert bremen_readiness.workflow_id == "bremen"
        assert hasattr(bremen_readiness, "configured")
        assert hasattr(bremen_readiness, "model_ready")
        assert hasattr(bremen_readiness, "scientifically_certified")


# ---------------------------------------------------------------------------
# No fallback behavior
# ---------------------------------------------------------------------------


class TestNoFallback:
    """Aramina unavailable does not fall back to Bremen."""

    def test_no_fallback_to_bremen(self):
        """When Aramina is unavailable, it returns unavailable — not Bremen."""
        provider = AraminaProvider()
        result = provider.execute(None)
        assert result.status == "failed"
        assert result.workflow_id == "aramina"
        # Result is specifically about Aramina, not Bremen
        assert "aramina" in (result.error or "").lower()
        assert "bremen" not in (result.error or "").lower()

    def test_no_auto_selection(self):
        """No automatic workflow selection from Aramina."""
        provider = AraminaProvider()
        # Provider has no auto-select behavior
        assert not hasattr(provider, "select_workflow")
        assert not hasattr(provider, "auto_detect")


# ---------------------------------------------------------------------------
# Scientific state
# ---------------------------------------------------------------------------


class TestAraminaScientific:
    """Scientific certification state."""

    def test_scientifically_not_certified_by_default(self):
        """Aramina is not scientifically certified in scaffold state."""
        provider = AraminaProvider()
        readiness = provider.readiness()
        assert readiness.scientifically_certified is False

    def test_no_fabricated_inference(self):
        """Aramina does not produce fabricated inference results."""
        provider = AraminaProvider()
        result = provider.execute(None)
        # Result has no payload (no fabricated scores/probabilities)
        assert result.payload is None
        assert result.error is not None
