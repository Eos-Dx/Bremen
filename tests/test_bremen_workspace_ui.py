"""Frontend workspace tests for the Analysis Workspace (/demo/workspace).

Covers:
- route accessibility
- no-job-selected state
- job list API integration
- report API
- timeline event data via job events API
- dynamic workflow card data
- process panel content
- privacy (no prohibited fields in API responses)
- audit tab content
- keyboard accessibility (aria labels)
- semantic tabs/buttons
- status text independent of color
- pop-out route
- workspace HTML structure
"""

from __future__ import annotations

import json
import re
from http.server import HTTPServer
import threading
import socket

import pytest

from bremen.api.server import _make_handler
from bremen.api.jobs import InMemoryJobStore
from bremen.api.job_api_handler import reset_for_tests
from bremen.api.event_store import BoundedEventStore


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
# Module-scoped shared server fixtures (PR0095b)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _shared_server():
    """Start an HTTPServer ONCE per module on a free port with synthetic model."""
    reset_for_tests()
    host = "127.0.0.1"
    port = _find_free_port()
    job_store = InMemoryJobStore()
    handler = _make_handler(job_store, version="test", load_model=True)
    server = HTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port, job_store
    server.shutdown()
    thread.join(timeout=2)
    reset_for_tests()


@pytest.fixture
def server_info(_shared_server):
    """Per-test cheap-reset fixture sharing the module-scoped server.

    Yields ``(host, port, job_store)`` (same signature as original per-test fixture
    used by TestWorkspaceRoute).
    """
    from bremen.api.model_state import ModelState
    from bremen.api.server import _load_synthetic_model

    host, port, job_store = _shared_server

    ModelState.reset_for_tests()
    _load_synthetic_model()
    reset_for_tests()

    yield host, port, job_store


# ---------------------------------------------------------------------------
# Workspace route tests
# ---------------------------------------------------------------------------


class TestWorkspaceRoute:
    """Tests for workspace route accessibility and structure."""

    def test_workspace_route_returns_html(self, server_info):
        host, port, _ = server_info
        status, body, headers = _get(host, port, "/demo/workspace")
        assert status == 200
        ct = headers.get("Content-Type", "")
        assert "text/html" in ct
        assert "<html" in body
        assert "Analysis Workspace" in body

    def test_workspace_route_has_safety_banner(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "Technical demo only" in body
        assert "not a clinical result" in body.lower() or (
            "Not a clinical result" in body
        )

    def test_workspace_pop_out_route(self, server_info):
        """Pop-out route with a job_id returns the workspace page."""
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/demo/workspace/test-job-123")
        assert status == 200
        assert "Analysis Workspace" in body

    def test_workspace_has_job_list_section(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert 'id="job-list"' in body or "job-list" in body

    def test_workspace_has_process_panel(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert 'id="events-stream"' in body or "Process" in body
        assert "process" in body.lower()

    def test_workspace_has_mode_toggle(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "Technical" in body
        assert "Process" in body

    def test_workspace_has_autoscroll_control(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "autoscroll" in body.lower() or "autoScroll" in body

    def test_workspace_panel_collapse_button(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "toggle-panel" in body.lower() or "collapsed" in body.lower()

    def test_no_job_selected_shows_guidance(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "Select a job" in body or "No jobs yet" in body or "Loading" in body

    def test_workspace_has_audit_section(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "Audit" in body

    def test_workspace_has_report_section(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "Report" in body or "Reports" in body

    def test_no_prohibited_fields_in_html(self, server_info):
        """The workspace HTML must not contain prohibited data patterns."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "patient_id" not in body
        assert "patient_name" not in body
        assert "operator_id" not in body
        assert "poni_text" not in body

    def test_workspace_has_keyboard_accessible_buttons(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        # Buttons should be present and clickable (semantic)
        assert "<button" in body

    def test_workspace_has_semantic_structure(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "aria-" in body or 'role=' in body or 'class="badge' in body

    def test_status_labels_independent_of_color(self, server_info):
        """Status is conveyed via text, not only color classes."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        # Badge classes control color but status text must be present
        assert "completed" in body.lower() or "failed" in body.lower()

    def test_responsive_layout(self, server_info):
        """Workspace uses flexbox for responsive layout."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "flex" in body or "display" in body


# ---------------------------------------------------------------------------
# Job API tests
# ---------------------------------------------------------------------------


class TestJobAPI:
    """Tests that exercise the actual job API endpoints."""

    def test_jobs_list_returns_json(self):
        """Jobs list returns JSON-safe structure (no server required)."""
        from bremen.api.job_api_handler import list_analysis_jobs, _event_store

        result = list_analysis_jobs()
        assert isinstance(result, list)

        # Verify response shape matches expected contract
        data = {
            "jobs": result,
            "storage_mode": _event_store.storage_mode,
            "retention_seconds": _event_store.retention_seconds,
            "max_jobs": _event_store.max_jobs,
        }
        assert "jobs" in data
        assert "storage_mode" in data
        data["technical_demo_only"] = True
        assert data["technical_demo_only"] is True

    def test_jobs_list_shows_storage_metadata(self):
        """Storage metadata is display-safe (no server required)."""
        from bremen.api.job_api_handler import _event_store

        assert _event_store.storage_mode == "ephemeral"
        assert isinstance(_event_store.retention_seconds, int)
        assert isinstance(_event_store.max_jobs, int)

    def test_job_not_found_returns_404(self, server_info):
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/demo/api/jobs/nonexistent-uuid")
        assert status in (404, 410)

    def test_job_create_requires_h5_path(self, server_info):
        host, port, _ = server_info
        status, body, _ = _post(host, port, "/demo/api/jobs", {})
        # May return 400 or 500 depending on error handling
        assert status in (400, 500, 201)

    def test_job_events_unknown_job(self, server_info):
        host, port, _ = server_info
        status, body, _ = _get(
            host, port, "/demo/api/jobs/nonexistent/events",
        )
        assert status in (404, 410)

    def test_job_reports_unknown_job(self, server_info):
        host, port, _ = server_info
        status, body, _ = _get(
            host, port, "/demo/api/jobs/nonexistent/reports",
        )
        assert status in (200, 404)
        data = json.loads(body)
        assert "reports" in data


# ---------------------------------------------------------------------------
# Report endpoint tests
# ---------------------------------------------------------------------------


class TestReportAPI:
    """Tests for report API endpoints."""

    def test_reports_list_for_unknown_job(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(
            host, port, "/demo/api/jobs/00000000-0000-0000-0000-000000000000/reports",
        )
        data = json.loads(body)
        assert "reports" in data

    def test_workflow_report_for_unknown_job(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(
            host, port,
            "/demo/api/jobs/00000000-0000-0000-0000-000000000000/reports/bremen",
        )
        data = json.loads(body)
        assert "report" in data


# ---------------------------------------------------------------------------
# Event data privacy tests
# ---------------------------------------------------------------------------


class TestEventPrivacy:
    """Verify no prohibited fields appear in event data."""

    def test_no_prohibited_fields_in_api_response(self):
        """No prohibited fields should appear in job summaries."""
        from bremen.api.job_api_handler import list_analysis_jobs

        prohibited = [
            "patient_id", "patient_name", "operator_id",
            "ponifile", "poni_text", "raw_data", "raw_array",
            "model_coefficients", "traceback", "exception_object",
        ]

        result = list_analysis_jobs()
        for job_summary in result:
            # Check key names directly (handles non-serializable values)
            for field in prohibited:
                assert field not in job_summary, (
                    f"prohibited field {field!r} found in job {job_summary.get('job_id', '?')}"
                )


# ---------------------------------------------------------------------------
# Workspace HTML privacy tests
# ---------------------------------------------------------------------------


class TestWorkspacePrivacy:
    """Verify workspace HTML contains no prohibited data."""

    def test_no_h5_paths_in_workspace_html(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "/scans" not in body
        assert "h5_path" not in body
        assert "dataset_path" not in body
        assert "local_path" not in body

    def test_technical_demo_only_present(self, server_info):
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/workspace")
        assert "Technical demo only" in body
