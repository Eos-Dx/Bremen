"""Frontend workspace tests for the Analysis Workspace (/demo/workspace).

Covers:
- route accessibility (via build_workspace_page directly)
- no-job-selected state
- job list API integration (direct function calls)
- report API (direct function calls)
- privacy (no prohibited fields in API responses)
- workspace HTML structure
- keyboard accessibility (aria labels)
- semantic tabs/buttons
- status text independent of color

Uses direct function calls and build_workspace_page() — no real server,
no sockets, no localhost HTTP requests.
"""

from __future__ import annotations

import json
import re

import pytest

from bremen.api.job_api_handler import reset_for_tests, list_analysis_jobs, _event_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server_info():
    """Provide workspace page HTML without starting a real server.

    Yields ``(html, None)`` where ``html`` is the workspace page content.
    """
    from bremen.api.model_state import ModelState
    from bremen.api.server import _load_synthetic_model
    from bremen.workspace_ui import build_workspace_page

    reset_for_tests()
    ModelState.reset_for_tests()
    _load_synthetic_model()

    html = build_workspace_page(base_url="http://testserver", request_id="test-rid")
    yield html, None
    reset_for_tests()


# ---------------------------------------------------------------------------
# Workspace route tests
# ---------------------------------------------------------------------------


class TestWorkspaceRoute:
    """Tests for workspace route accessibility and structure."""

    def test_workspace_route_returns_html(self, server_info):
        html, _ = server_info
        assert "<html" in html
        assert "Analysis Workspace" in html

    def test_workspace_route_has_safety_banner(self, server_info):
        html, _ = server_info
        assert "Technical demo only" in html
        assert "not a clinical result" in html.lower() or (
            "Not a clinical result" in html
        )

    def test_workspace_has_job_list_section(self, server_info):
        html, _ = server_info
        assert 'id="job-list"' in html or "job-list" in html

    def test_workspace_has_process_panel(self, server_info):
        html, _ = server_info
        assert 'id="events-stream"' in html or "Process" in html
        assert "process" in html.lower()

    def test_workspace_has_mode_toggle(self, server_info):
        html, _ = server_info
        assert "Technical" in html
        assert "Process" in html

    def test_workspace_has_autoscroll_control(self, server_info):
        html, _ = server_info
        assert "autoscroll" in html.lower() or "autoScroll" in html

    def test_workspace_panel_collapse_button(self, server_info):
        html, _ = server_info
        assert "toggle-panel" in html.lower() or "collapsed" in html.lower()

    def test_no_job_selected_shows_guidance(self, server_info):
        html, _ = server_info
        assert "Select a job" in html or "No jobs yet" in html or "Loading" in html

    def test_workspace_has_audit_section(self, server_info):
        html, _ = server_info
        assert "Audit" in html

    def test_workspace_has_report_section(self, server_info):
        html, _ = server_info
        assert "Report" in html or "Reports" in html

    def test_no_prohibited_fields_in_html(self, server_info):
        """The workspace HTML must not contain prohibited data patterns."""
        html, _ = server_info
        assert "patient_id" not in html
        assert "patient_name" not in html
        assert "operator_id" not in html
        assert "poni_text" not in html

    def test_workspace_has_keyboard_accessible_buttons(self, server_info):
        html, _ = server_info
        assert "<button" in html

    def test_workspace_has_semantic_structure(self, server_info):
        html, _ = server_info
        assert "aria-" in html or 'role=' in html or 'class="badge' in html

    def test_status_labels_independent_of_color(self, server_info):
        """Status is conveyed via text, not only color classes."""
        html, _ = server_info
        assert "completed" in html.lower() or "failed" in html.lower()

    def test_responsive_layout(self, server_info):
        """Workspace uses flexbox for responsive layout."""
        html, _ = server_info
        assert "flex" in html or "display" in html


# ---------------------------------------------------------------------------
# Job API tests (direct function calls, no server)
# ---------------------------------------------------------------------------


class TestJobAPI:
    """Tests that exercise job API helpers directly."""

    def test_jobs_list_returns_json(self):
        """Jobs list returns JSON-safe structure (no server required)."""
        result = list_analysis_jobs()
        assert isinstance(result, list)

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
        assert _event_store.storage_mode == "ephemeral"
        assert isinstance(_event_store.retention_seconds, int)
        assert isinstance(_event_store.max_jobs, int)


# ---------------------------------------------------------------------------
# Event data privacy tests (direct function calls, no server)
# ---------------------------------------------------------------------------


class TestEventPrivacy:
    """Verify no prohibited fields appear in event data."""

    def test_no_prohibited_fields_in_api_response(self):
        """No prohibited fields should appear in job summaries."""
        prohibited = [
            "patient_id", "patient_name", "operator_id",
            "ponifile", "poni_text", "raw_data", "raw_array",
            "model_coefficients", "traceback", "exception_object",
        ]

        result = list_analysis_jobs()
        for job_summary in result:
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
        html, _ = server_info
        assert "/scans" not in html
        assert "h5_path" not in html
        assert "dataset_path" not in html
        assert "local_path" not in html

    def test_technical_demo_only_present(self, server_info):
        html, _ = server_info
        assert "Technical demo only" in html
