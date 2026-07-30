"""Dedicated showcase tests for PR0078 investor showcase mode.

Covers:
- Showcase route returns real workspace
- Showcase mode has showcase JS/CSS
- Safety banner present
- Pipeline CSS present
- Drawer CSS present
- Responsive CSS present
- Reduced-motion support
- Aria-live region
- No embedded static job
- Investor summary rendering
- Technical/scientific readiness
- Decision visualization
- Stage drawer
- Pipeline semantic ol
- Escape keyboard
- Prohibited fields absent
- Orchestrator behavior (direct function calls)
- Synthetic unavailable provider

Uses build_workspace_page() directly and direct function calls —
no real server, no sockets, no localhost HTTP requests.
"""

from __future__ import annotations

import json

import pytest

from bremen.api.job_api_handler import reset_for_tests
from bremen.api.workflow_orchestrator import run_workflow_request
from bremen.api.workflow_provider import (
    WorkflowProvider, WorkflowResult, WorkflowReadiness,
    CompatibilityResult, WorkflowFeatureVector,
)


# ---------------------------------------------------------------------------
# Synthetic unavailable provider
# ---------------------------------------------------------------------------


class SyntheticUnavailableProvider(WorkflowProvider):
    """Synthetic provider that always reports model_ready=False."""

    workflow_id: str = "synthetic_unavailable"

    def readiness(self) -> WorkflowReadiness:
        return WorkflowReadiness(
            workflow_id=self.workflow_id,
            configured=True,
            model_ready=False,
            scientifically_certified=False,
        )

    def validate_compatibility(self, canonical) -> CompatibilityResult:
        return CompatibilityResult(compatible=True)

    def build_features(self, canonical):
        return WorkflowFeatureVector(
            workflow_id=self.workflow_id,
            feature_names=(),
            feature_values=(),
        )

    def run_inference(self, features):
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="failed",
            error="Unavailable",
        )

    def execute(self, canonical, context=None):
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="failed",
            error="Workflow unavailable",
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def showcase_html():
    """Provide workspace page HTML in showcase mode (via build_workspace_page)."""
    from bremen.api.model_state import ModelState
    from bremen.api.server import _load_synthetic_model
    from bremen.workspace_ui import build_workspace_page

    reset_for_tests()
    ModelState.reset_for_tests()
    _load_synthetic_model()

    html = build_workspace_page(
        base_url="http://testserver",
        request_id="test-rid",
        job_id=None,
    )
    yield html
    reset_for_tests()


# ---------------------------------------------------------------------------
# Showcase route tests
# ---------------------------------------------------------------------------


class TestShowcaseRoute:
    """Showcase route returns the real workspace page."""

    def test_showcase_route_returns_html(self, showcase_html):
        assert "<html" in showcase_html

    def test_showcase_mode_has_showcase_js(self, showcase_html):
        assert "INVESTOR SHOWCASE MODE" in showcase_html
        assert "showcase-root" in showcase_html

    def test_showcase_mode_has_safety_banner(self, showcase_html):
        assert "Technical demo only" in showcase_html

    def test_showcase_mode_has_pipeline_css(self, showcase_html):
        assert ".pipeline" in showcase_html
        assert "stage-node" in showcase_html

    def test_showcase_mode_has_drawer_css(self, showcase_html):
        assert ".drawer" in showcase_html

    def test_showcase_mode_has_responsive_css(self, showcase_html):
        assert "max-width: 640px" in showcase_html or "max-width:640px" in showcase_html

    def test_showcase_mode_has_reduced_motion(self, showcase_html):
        assert "prefers-reduced-motion" in showcase_html

    def test_showcase_mode_has_aria_live_region(self, showcase_html):
        assert "aria-live" in showcase_html

    def test_showcase_no_embedded_static_job(self, showcase_html):
        assert '"probability":' not in showcase_html

    def test_showcase_investor_summary_rendering(self, showcase_html):
        assert "Investor Summary" in showcase_html or "renderInvestorSummary" in showcase_html

    def test_showcase_technical_readiness_separate(self, showcase_html):
        assert "Technical readiness" in showcase_html or "techReadiness" in showcase_html
        assert "Scientific certification" in showcase_html or "sciCert" in showcase_html

    def test_showcase_decision_visualization(self, showcase_html):
        assert "MRI Continuation Assessment" in showcase_html or "renderBremenDecision" in showcase_html
        assert "NOT CERTIFIED" in showcase_html or "scientifically_certified" in showcase_html

    def test_showcase_stage_drawer(self, showcase_html):
        assert "showcase-drawer" in showcase_html
        assert "showcase-drawer-overlay" in showcase_html

    def test_showcase_pipeline_semantic_ol(self, showcase_html):
        assert "<ol" in showcase_html and "Execution stages" in showcase_html

    def test_showcase_escape_keyboard(self, showcase_html):
        assert "Escape" in showcase_html

    def test_no_prohibited_fields_in_showcase(self, showcase_html):
        assert "coefficient" not in showcase_html
        assert "intercept" not in showcase_html
        assert "scaler_mean" not in showcase_html
        assert "raw_feature_vector" not in showcase_html
        assert "model_coefficients" not in showcase_html


# ---------------------------------------------------------------------------
# Orchestrator behavior tests (direct function calls, no server)
# ---------------------------------------------------------------------------


class TestOrchestratorBehavior:
    """Test orchestrator behavior without starting a server."""

    def test_unavailable_provider_returns_failed(self, tmp_path):
        """Synthetic unavailable provider returns failed status."""
        import h5py
        import numpy as np
        from bremen.api.workflow_registry import WorkflowRegistry
        from bremen.api.event_store import BoundedEventStore

        # Create minimal H5 file
        h5_path = tmp_path / "test.h5"
        with h5py.File(h5_path, "w") as f:
            scans = f.create_group("scans")
            for label in ("target", "contralateral"):
                grp = scans.create_group(label)
                arr = np.random.default_rng(42).normal(10.0, 2.0, 100).astype(np.float64)
                grp.create_dataset("measurements", data=arr.reshape(1, -1))

        provider = SyntheticUnavailableProvider()
        registry = WorkflowRegistry()
        registry.register(provider)

        event_store = BoundedEventStore()

        result = run_workflow_request(
            h5_path=str(h5_path),
            workflow_id="synthetic_unavailable",
            registry=registry,
            event_store=event_store,
        )

        wf_result = result.workflows.get("synthetic_unavailable")
        assert wf_result is not None
        assert wf_result.status == "failed"
        assert "unavailable" in wf_result.error.lower()

    def test_unavailable_provider_readiness(self):
        """Synthetic unavailable provider reports not ready."""
        provider = SyntheticUnavailableProvider()
        readiness = provider.readiness()
        assert readiness.model_ready is False
        assert readiness.configured is True
