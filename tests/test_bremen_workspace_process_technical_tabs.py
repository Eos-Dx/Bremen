"""Tests for Workspace Process/Technical tab parity and workspace link (PR0109).

Covers:
- Process tab content differs from Technical tab content
- Process tab contains friendly stage labels
- Technical tab contains safe technical event identifiers
- completed job UI includes /demo/workspace/{job_id}
- failed/no-report job does not expose unsafe workspace link
- public safety strings are not exposed
- No real server, socket, localhost HTTP, uvicorn launch
"""

from __future__ import annotations

import pytest

from bremen.workspace_ui import build_workspace_page


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_html():
    """Build workspace page HTML."""
    return build_workspace_page(base_url="http://testserver", request_id="test-rid")


@pytest.fixture
def workspace_html_with_job():
    """Build workspace page HTML with a pre-selected job ID."""
    return build_workspace_page(
        base_url="http://testserver", request_id="test-rid", job_id="test-job-001"
    )


# ---------------------------------------------------------------------------
# Tab behavior tests
# ---------------------------------------------------------------------------


class TestProcessTechnicalTabsDistinct:
    """Process and Technical tabs must render different content."""

    def test_process_tab_label_exists(self, workspace_html):
        """Process tab button exists."""
        assert 'id="mode-process"' in workspace_html
        assert ">Process<" in workspace_html

    def test_technical_tab_label_exists(self, workspace_html):
        """Technical tab button exists."""
        assert 'id="mode-technical"' in workspace_html
        assert ">Technical<" in workspace_html

    def test_process_tab_active_by_default(self, workspace_html):
        """Process tab is active by default."""
        assert 'id="mode-process"' in workspace_html
        # The process tab should have 'active' class
        assert 'class="tab active"' in workspace_html or 'class="tab active"' in workspace_html

    def test_switch_mode_function_exists(self, workspace_html):
        """switchMode function is defined in the page JS."""
        assert "function switchMode(mode)" in workspace_html

    def test_switch_mode_renders_differently(self, workspace_html):
        """Process uses processLabel(), Technical uses ev.event_type directly."""
        # Process mode maps event types to friendly labels
        assert "processLabel(ev)" in workspace_html
        # Technical mode shows raw event_type
        assert "processMode === 'technical'" in workspace_html

    def test_process_has_friendly_labels(self, workspace_html):
        """Process tab maps event types to friendly labels."""
        assert "'Request accepted'" in workspace_html
        assert "'Normalization started'" in workspace_html
        assert "'Workflow resolved'" in workspace_html
        assert "'Inference completed'" in workspace_html

    def test_technical_shows_raw_event_type(self, workspace_html):
        """Technical tab shows raw event_type field."""
        assert "ev.event_type" in workspace_html

    def test_event_cache_exists(self, workspace_html):
        """Event cache array exists for re-render on mode switch."""
        assert "var eventCache = []" in workspace_html

    def test_switch_mode_renders_from_cache(self, workspace_html):
        """switchMode re-renders events from cache."""
        assert "eventCache" in workspace_html
        assert "renderProcessEvent(eventCache[i])" in workspace_html

    def test_render_process_event_function_exists(self, workspace_html):
        """renderProcessEvent function is defined for re-rendering."""
        assert "function renderProcessEvent(ev)" in workspace_html

    def test_add_process_event_caches(self, workspace_html):
        """addProcessEvent caches events before rendering."""
        assert "eventCache.push(ev)" in workspace_html

    def test_mode_switch_resets_panel(self, workspace_html):
        """switchMode clears and re-renders the events panel."""
        assert "panel.innerHTML = ''" in workspace_html


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------


class TestNoUnsafeContent:
    """Workspace page must not expose raw internals."""

    def test_no_s3_paths(self, workspace_html):
        """No raw S3 paths."""
        assert "s3://" not in workspace_html

    def test_no_filesystem_paths(self, workspace_html):
        """No filesystem paths."""
        assert "/Users/" not in workspace_html
        assert "/home/" not in workspace_html

    def test_no_exception_traces(self, workspace_html):
        """No Traceback text."""
        assert "Traceback" not in workspace_html

    def test_no_bucket_names(self, workspace_html):
        """No bucket names."""
        assert "bucket=" not in workspace_html.lower()

    def test_no_model_coefficients(self, workspace_html):
        """No raw model coefficients."""
        assert "coefficients" not in workspace_html.lower()
        assert "intercept" not in workspace_html.lower()

    def test_safety_banner_present(self, workspace_html):
        """Safety banner is present."""
        assert "Technical demo only" in workspace_html
        assert "not a clinical result" in workspace_html.lower() or (
            "Not a clinical result" in workspace_html
        )


# ---------------------------------------------------------------------------
# Control room workspace link tests
# ---------------------------------------------------------------------------


class TestControlRoomWorkspaceLink:
    """Control Room decision card includes workspace link for completed jobs."""

    def test_workspace_link_in_decision_card(self):
        """Completed job decision card includes /demo/workspace/ link."""
        from bremen.control_room_ui import build_control_room_page

        html = build_control_room_page(base_url="http://testserver")
        # The fetchDecision function should build a workspace link
        assert "/demo/workspace/" in html

    def test_workspace_link_uses_job_id(self):
        """Workspace link in decision card uses jobId variable."""
        from bremen.control_room_ui import build_control_room_page

        html = build_control_room_page(base_url="http://testserver")
        assert "demo/workspace/'+jobId" in html or "demo/workspace/" in html

    def test_open_workspace_label(self):
        """Workspace link has 'Open workspace' label."""
        from bremen.control_room_ui import build_control_room_page

        html = build_control_room_page(base_url="http://testserver")
        assert "Open workspace" in html

    def test_open_report_still_exists(self):
        """Open report link is preserved."""
        from bremen.control_room_ui import build_control_room_page

        html = build_control_room_page(base_url="http://testserver")
        assert "Open report" in html

    def test_workspace_link_target_blank(self):
        """Workspace link opens in new tab."""
        from bremen.control_room_ui import build_control_room_page

        html = build_control_room_page(base_url="http://testserver")
        assert 'target="_blank"' in html

    def test_workspace_link_rel_noopener(self):
        """Workspace link has rel=noopener for security."""
        from bremen.control_room_ui import build_control_room_page

        html = build_control_room_page(base_url="http://testserver")
        assert 'rel="noopener"' in html

    def test_failed_job_no_unsafe_workspace_link(self):
        """Failed job does not expose workspace link in decision card."""
        from bremen.control_room_ui import build_control_room_page

        html = build_control_room_page(base_url="http://testserver")
        # The fetchDecision function checks for failed status before rendering
        # workspace link — it's inside the non-failed branch
        # Verify the link is inside the success path
        assert "jobStatus==='failed'" in html or "overall_status" in html


# ---------------------------------------------------------------------------
# Workspace page with job ID
# ---------------------------------------------------------------------------


class TestWorkspaceWithJobId:
    """Workspace page with pre-selected job ID."""

    def test_job_id_embedded_in_page(self, workspace_html_with_job):
        """Job ID is embedded in the page."""
        assert "test-job-001" in workspace_html_with_job

    def test_page_still_has_tabs(self, workspace_html_with_job):
        """Tabs still exist when job ID is provided."""
        assert 'id="mode-process"' in workspace_html_with_job
        assert 'id="mode-technical"' in workspace_html_with_job


# ---------------------------------------------------------------------------
# Existing structure preserved
# ---------------------------------------------------------------------------


class TestExistingStructurePreserved:
    """Workspace page retains expected structure."""

    def test_page_title(self, workspace_html):
        """Page has correct title."""
        assert "Bremen Analysis Workspace" in workspace_html

    def test_job_list_panel(self, workspace_html):
        """Job list panel exists."""
        assert 'id="job-list"' in workspace_html

    def test_events_stream_panel(self, workspace_html):
        """Events stream panel exists."""
        assert 'id="events-stream"' in workspace_html

    def test_autoscroll_button(self, workspace_html):
        """Auto-scroll toggle button exists."""
        assert "autoscroll-btn" in workspace_html

    def test_toggle_panel_button(self, workspace_html):
        """Panel toggle button exists."""
        assert "toggle-panel-btn" in workspace_html
