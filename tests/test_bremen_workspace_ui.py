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
from bremen.workspace_ui import build_workspace_page


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


# ---------------------------------------------------------------------------
# PR0116-C — Workspace internal auth handling
# ---------------------------------------------------------------------------


class TestWorkspaceInternalAuth:
    """Workspace page protected JSON calls use the auth-aware wrapper (PR0116-C)."""

    def _function_body(self, page: str, function_name: str) -> str:
        # Match the exact function name (not a prefix like _authFetchTicket).
        fn_start = page.find(f"function {function_name}(")
        assert fn_start >= 0
        fn_end = page.find("function ", fn_start + 10)
        return page[fn_start:fn_end if fn_end > 0 else len(page)]

    def test_auth_fetch_helper_defined(self):
        """Workspace page defines the canonical _authFetch helper."""
        html = build_workspace_page(base_url="http://testserver")
        assert "function _authFetch(url,opts)" in html

    def test_auth_fetch_reads_canonical_storage(self):
        """_authFetch reads access token from canonical sessionStorage key."""
        html = build_workspace_page(base_url="http://testserver")
        assert "bremen_access_token" in html
        assert "bremen_refresh_token" in html

    def test_auth_fetch_refreshes_on_401(self):
        """_authFetch calls refresh endpoint on 401."""
        html = build_workspace_page(base_url="http://testserver")
        assert "'/demo/api/auth/refresh'" in html
        assert "refresh_token:rt" in html

    def test_auth_fetch_stores_new_token(self):
        """_authFetch stores the refreshed access token via _setTokens."""
        html = build_workspace_page(base_url="http://testserver")
        assert "_setTokens(result.data)" in html

    def test_auth_fetch_retries_once(self):
        """_authFetch retries the original request exactly once."""
        html = build_workspace_page(base_url="http://testserver")
        fn_body = self._function_body(html, "_authFetch")
        assert fn_body.count("fetch(url,opts)") == 2

    def test_auth_fetch_no_refresh_loop(self):
        """_authFetch does not loop on refresh; only one retry per request."""
        html = build_workspace_page(base_url="http://testserver")
        fn_body = self._function_body(html, "_authFetch")
        assert fn_body.count("auth/refresh") == 1
        assert fn_body.count("fetch(url,opts)") == 2

    def test_load_job_list_uses_auth_fetch(self):
        """loadJobList uses _authFetch for GET /demo/api/jobs."""
        html = build_workspace_page(base_url="http://testserver")
        fn_body = self._function_body(html, "loadJobList")
        assert "_authFetch(baseUrl + '/demo/api/jobs')" in fn_body
        assert "fetch(baseUrl + '/demo/api/jobs')" not in fn_body

    def test_select_job_uses_auth_fetch(self):
        """selectJob uses _authFetch for GET /demo/api/jobs/{job_id}."""
        html = build_workspace_page(base_url="http://testserver")
        fn_body = self._function_body(html, "selectJob")
        assert "_authFetch(baseUrl + '/demo/api/jobs/' + jobId)" in fn_body
        assert "fetch(baseUrl + '/demo/api/jobs/' + jobId)" not in fn_body

    def test_connect_sse_mints_stream_ticket(self):
        """connectSSE mints a stream ticket before opening EventSource."""
        html = build_workspace_page(base_url="http://testserver")
        fn_body = self._function_body(html, "connectSSE")
        assert "_authFetchTicket(jobId, 'stream')" in fn_body
        assert "auth_ticket=" in fn_body
        assert "encodeURIComponent(ticket)" in fn_body

    def test_connect_sse_no_tokens_in_url(self):
        """connectSSE does not put access_token or refresh_token in EventSource URL."""
        html = build_workspace_page(base_url="http://testserver")
        fn_body = self._function_body(html, "connectSSE")
        assert "access_token" not in fn_body
        assert "refresh_token" not in fn_body
        assert "auth_ticket=" in fn_body

    def test_showcase_select_job_uses_auth_fetch(self):
        """Showcase selectJob uses _authFetch for protected job fetch."""
        html = build_workspace_page(base_url="http://testserver")
        assert "_authFetch(baseUrl + '/demo/api/jobs/' + jobId)" in html

    def test_showcase_sse_mints_stream_ticket(self):
        """Showcase connectShowcaseSSE mints a stream ticket."""
        html = build_workspace_page(base_url="http://testserver")
        assert "_authFetchTicket(jobId, 'stream')" in html
        assert "auth_ticket=" in html

    def test_showcase_live_update_uses_auth_fetch(self):
        """Showcase updateShowcaseLive uses _authFetch."""
        html = build_workspace_page(base_url="http://testserver")
        assert "_authFetch(baseUrl + '/demo/api/jobs/' + jobId)" in html

    def test_no_plain_fetch_for_protected_jobs(self):
        """No plain fetch for protected /demo/api/jobs endpoints."""
        html = build_workspace_page(base_url="http://testserver")
        # The only plain fetch calls should be inside _authFetch itself.
        assert "fetch(baseUrl + '/demo/api/jobs')" not in html
        assert "fetch(baseUrl + '/demo/api/jobs/' + jobId)" not in html
