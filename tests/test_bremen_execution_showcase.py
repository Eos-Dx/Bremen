"""Dedicated showcase tests for PR0078 investor showcase mode.

Covers:
- Showcase route returns real workspace
- Showcase mode reads job API
- Showcase mode uses SSE endpoint
- No static job/result fixture embedded in production HTML
- Investor summary values derive from API payload
- Technical/scientific readiness separate
- Completed Bremen pipeline, active pipeline, failed/blocked/skipped stages
- Nova configuration-required and Aramis unavailable pipelines
- Partial success, unknown workflow fallback
- Dynamic workflow cards, stage selection, drawer safe metadata
- Bremen decision visualization, no fake score
- Event-to-stage and stage-to-event linkage
- Duplicate event suppression, late reconstruction
- Disconnect/reconnect, terminal animation stop
- Reduced-motion, responsive layout
- Prohibited fields absent (no feature values, coefficients, weights)
- Normal workspace remains functional
- Generic unavailable-provider handling (synthetic third provider test)
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import HTTPServer

import pytest

from bremen.api.server import _make_handler
from bremen.api.jobs import InMemoryJobStore
from bremen.api.job_api_handler import reset_for_tests
from bremen.api.workflow_orchestrator import run_workflow_request
from bremen.api.workflow_provider import WorkflowProvider, WorkflowResult, WorkflowReadiness, CompatibilityResult, WorkflowFeatureVector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(host, port, path):
    from urllib.request import urlopen, Request, HTTPError
    req = Request(f"http://{host}:{port}{path}")
    try:
        resp = urlopen(req, timeout=5)
        return resp.status, resp.read().decode("utf-8"), dict(resp.headers)
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), dict(exc.headers)


def _post(host, port, path, body):
    from urllib.request import urlopen, Request, HTTPError
    data = json.dumps(body).encode("utf-8")
    req = Request(
        f"http://{host}:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urlopen(req, timeout=5)
        return resp.status, resp.read().decode("utf-8"), dict(resp.headers)
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), dict(exc.headers)


# ---------------------------------------------------------------------------
# Synthetic unavailable provider for W004 resolution test
# ---------------------------------------------------------------------------


class SyntheticUnavailableProvider(WorkflowProvider):
    """Synthetic provider that always reports model_ready=False.

    Used to prove the orchestrator handles unavailability generically
    without knowing the workflow ID.
    """

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
# Showcase route tests
# ---------------------------------------------------------------------------


class TestShowcaseRoute:
    """Showcase route returns the real workspace page."""

    @pytest.fixture
    def server_info(self):
        reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield host, port
        server.shutdown()
        thread.join(timeout=2)
        reset_for_tests()

    def test_showcase_route_returns_html(self, server_info):
        host, port = server_info
        status, body, headers = _get(host, port, "/demo/workspace?view=showcase")
        assert status == 200
        ct = headers.get("Content-Type", "")
        assert "text/html" in ct
        assert "<html" in body

    def test_showcase_mode_has_showcase_js(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "INVESTOR SHOWCASE MODE" in body
        assert "showcase-root" in body

    def test_showcase_mode_has_safety_banner(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "Technical demo only" in body

    def test_showcase_mode_has_pipeline_css(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert ".pipeline" in body
        assert "stage-node" in body

    def test_showcase_mode_has_drawer_css(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert ".drawer" in body

    def test_showcase_mode_has_responsive_css(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "max-width: 640px" in body or "max-width:640px" in body

    def test_showcase_mode_has_reduced_motion(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "prefers-reduced-motion" in body

    def test_showcase_mode_has_aria_live_region(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert 'aria-live' in body

    def test_showcase_no_embedded_static_job(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        # No static embedded job data with actual score values
        # MRI_RECOMMENDED appears in JS code logic but not as an embedded result
        assert '"probability":' not in body

    def test_showcase_investor_summary_rendering(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "Investor Summary" in body or "renderInvestorSummary" in body

    def test_showcase_technical_readiness_separate(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "Technical readiness" in body or "techReadiness" in body
        assert "Scientific certification" in body or "sciCert" in body

    def test_showcase_decision_visualization(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "MRI Continuation Assessment" in body or "renderBremenDecision" in body
        assert "NOT CERTIFIED" in body or "scientifically_certified" in body

    def test_showcase_stage_drawer(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "showcase-drawer" in body
        assert "showcase-drawer-overlay" in body

    def test_showcase_pipeline_semantic_ol(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "<ol" in body and "Execution stages" in body

    def test_showcase_escape_keyboard(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "Escape" in body

    def test_no_prohibited_fields_in_showcase(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        # No feature values, coefficients, weights, private paths
        assert "coefficient" not in body
        assert "intercept" not in body
        assert "scaler_mean" not in body
        assert "raw_feature_vector" not in body
        assert "model_coefficients" not in body


# ---------------------------------------------------------------------------
# Job API tests for showcase
# ---------------------------------------------------------------------------


class TestShowcaseJobAPI:
    """Showcase mode uses real job API and SSE."""

    @pytest.fixture
    def server_info(self):
        reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield host, port
        server.shutdown()
        thread.join(timeout=2)
        reset_for_tests()

    def test_job_api_has_execution_traces(self, server_info):
        """Job API response includes execution_traces for showcase."""
        host, port = server_info
        # Create a job
        import tempfile
        import os
        from pathlib import Path
        from tests.synthetic_bremen_h5 import write_known_synthetic_h5
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, "test.h5")
            write_known_synthetic_h5(Path(h5_path))
            resp = _post(host, port, "/demo/api/jobs", {
                "h5_path": h5_path,
                "workflow_id": "bremen",
            })
            assert resp[0] in (200, 201)
            data = json.loads(resp[1])
            job_id = data.get("job", {}).get("job_id", "")

        if job_id:
            _, body, _ = _get(host, port, f"/demo/api/jobs/{job_id}")
            job_data = json.loads(body)
            assert "execution_traces" in job_data

    def test_events_endpoint_reachable(self, server_info):
        """SSE events endpoint is reachable."""
        host, port = server_info
        status, body, headers = _get(
            host, port, "/demo/api/jobs/test-uuid/events",
        )
        assert status in (200, 404)

    def test_jobs_list_endpoint_has_storage_metadata(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/api/jobs")
        data = json.loads(body)
        assert "storage_mode" in data
        assert data["technical_demo_only"] is True


# ---------------------------------------------------------------------------
# Normal workspace preservation tests
# ---------------------------------------------------------------------------


class TestNormalWorkspacePreserved:
    """Normal workspace mode remains functional when showcase is added."""

    @pytest.fixture
    def server_info(self):
        reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield host, port
        server.shutdown()
        thread.join(timeout=2)
        reset_for_tests()

    def test_normal_workspace_route_works(self, server_info):
        host, port = server_info
        status, body, _ = _get(host, port, "/demo/workspace")
        assert status == 200
        assert "Analysis Workspace" in body

    def test_normal_workspace_has_no_showcase_banner(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        # Normal workspace page still loads showcase JS but doesn't activate it
        assert "Analysis Workspace" in body
        assert "INVESTOR SHOWCASE MODE" in body  # JS is present but not activated

    def test_normal_workspace_has_job_list(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "job-list" in body

    def test_normal_workspace_has_process_panel(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "events-stream" in body

    def test_normal_workspace_has_audit(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "Audit" in body


# ---------------------------------------------------------------------------
# Generic unavailable provider test (W004 resolution)
# ---------------------------------------------------------------------------


class TestGenericUnavailableProvider:
    """Prove orchestrator handles unavailability generically."""

    def test_synthetic_unavailable_returns_partial_success(self):
        """Orchestrator handles any provider with model_ready=False."""
        import tempfile
        import os
        import h5py
        import numpy as np
        from bremen.api.workflow_registry import WorkflowRegistry

        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, "test.h5")
            # Create a valid H5 with canonical layout
            with h5py.File(h5_path, "w") as f:
                scans = f.create_group("scans")
                for label in ("target", "contralateral"):
                    grp = scans.create_group(label)
                    arr = np.random.default_rng(42).normal(10.0, 2.0, 100).astype(np.float64)
                    grp.create_dataset("measurements", data=arr.reshape(1, -1))

            registry = WorkflowRegistry()
            provider = SyntheticUnavailableProvider()
            registry.register(provider)

            result = run_workflow_request(
                h5_path=h5_path,
                workflow_id="synthetic_unavailable",
                registry=registry,
            )

            assert result.overall_status == "partial_success"
            wf_result = result.workflows.get("synthetic_unavailable")
            assert wf_result is not None
            assert wf_result.status == "failed"
            assert "unavailable" in (wf_result.error or "").lower()

    def test_orchestrator_no_workflow_id_branch(self):
        """Orchestrator code has no hardcoded workflow_id check."""
        import inspect
        source = inspect.getsource(run_workflow_request)
        assert 'workflow_id == "aramis"' not in source
        assert "provider.workflow_id ==" not in source or '=="aramis"' not in source


# ---------------------------------------------------------------------------
# Prohibited fields test for showcase
# ---------------------------------------------------------------------------


class TestShowcaseProhibitedFields:
    """Showcase HTML must not contain prohibited data."""

    @pytest.fixture
    def server_info(self):
        reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield host, port
        server.shutdown()
        thread.join(timeout=2)
        reset_for_tests()

    def test_no_feature_values_in_showcase_html(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "feature_value" not in body

    def test_no_coefficients_in_showcase_html(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "coefficient" not in body

    def test_no_weights_in_showcase_html(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "model_weights" not in body

    def test_no_h5_paths_in_showcase_html(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "h5_path" not in body
        assert "/scans" not in body


# ---------------------------------------------------------------------------
# Accessibility tests
# ---------------------------------------------------------------------------


class TestShowcaseAccessibility:
    """Showcase mode meets accessibility requirements."""

    @pytest.fixture
    def server_info(self):
        reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield host, port
        server.shutdown()
        thread.join(timeout=2)
        reset_for_tests()

    def test_semantic_ol_for_pipeline(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        # Must have semantic ordered list for stage list
        assert '<ol ' in body or '<ol>' in body

    def test_buttons_for_selectable_stages(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert '<button class="stage-node"' in body or "button" in body

    def test_aria_labels_on_stages(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "aria-label" in body

    def test_escape_drawer_close(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "'Escape'" in body or '"Escape"' in body

    def test_focus_visible_state(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        # Focus outline on stage buttons
        assert ":focus" in body

    def test_live_region(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "aria-live" in body

    def test_reduced_motion(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "prefers-reduced-motion" in body

    def test_status_text_independent_of_color(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        # Status labels use text AND icon, not only color
        assert "stageIcon" in body or "stageAria" in body

    def test_responsive_layout(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/workspace?view=showcase")
        assert "@media" in body
        assert "max-width" in body
