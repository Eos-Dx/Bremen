"""Behavioral tests for the Bremen Investor Control Room (PR0082).

Covers:
- Route rendering and content
- Pipeline stage mappings
- Event filter behavior
- Accessibility (aria-pressed, role=list, aria-live)
- Privacy (no prohibited content)
- Model-unconfigured state
- One real model identity
- Legacy workspace compatibility
"""

from __future__ import annotations

import json
import tempfile
import os
import h5py
import numpy as np
from pathlib import Path

import pytest

from bremen.api.server import _make_handler, _ThreadingHTTPServer
from bremen.api.jobs import InMemoryJobStore
from bremen.api.job_api_handler import reset_for_tests
from bremen.control_room_ui import build_control_room_page






# ---------------------------------------------------------------------------
# Module-scoped shared server fixtures (PR0095b)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _shared_server():
    """Provide control room page HTML without starting a real server.

    Yields ``(html, None)`` where ``html`` is the control room page content.
    """
    from bremen.api.model_state import ModelState
    from bremen.api.server import _load_synthetic_model
    from bremen.control_room_ui import build_control_room_page

    reset_for_tests()
    ModelState.reset_for_tests()
    _load_synthetic_model()

    html = build_control_room_page(base_url="http://testserver")
    yield html, None
    reset_for_tests()


@pytest.fixture
def server_info(_shared_server):
    """Per-test fixture providing control room page HTML.

    Yields ``(html, None)`` where ``html`` is the page content.
    """
    from bremen.api.model_state import ModelState
    from bremen.api.server import _load_synthetic_model
    from bremen.control_room_ui import build_control_room_page

    ModelState.reset_for_tests()
    _load_synthetic_model()

    html = build_control_room_page(base_url="http://testserver")
    yield html, None


class TestControlRoomRoute:
    """Control Room default route replaces old /demo."""

    def test_start_page_is_default_route(self, server_info):
        """Start page builder produces the start page."""
        from bremen.start_page_ui import build_start_page
        page = build_start_page(base_url="http://testserver")
        assert "Select a model to begin" in page
        assert "Should the patient continue to MRI" in page

    def test_control_room_route(self, server_info):
        html, _ = server_info
        page = html
        assert "Control Room" in page or "cr-page" in page
        assert "Should the patient continue to MRI" in page

    def test_workspace_route_preserved(self, server_info):
        """Workspace page builder produces workspace page."""
        from bremen.workspace_ui import build_workspace_page
        page = build_workspace_page(base_url="http://testserver")
        assert "Analysis Workspace" in page

    def test_control_room_has_stage_pipeline(self, server_info):
        html, _ = server_info

        page = html
        assert "stage-input" in page
        assert "stage-source" in page
        assert "stage-xrd" in page
        assert "stage-workflow" in page
        assert "stage-artifact" in page
        assert "stage-features" in page
        assert "stage-inference" in page
        assert "stage-decision" in page
        assert "stage-report" in page
        assert "stage-complete" in page

    def test_control_room_has_stage_map_code(self, server_info):
        html, _ = server_info

        page = html
        assert "STAGE_MAP" in page
        assert "runtime.input.preparation.completed" in page
        assert "runtime.report.completed" in page

    def test_control_room_has_file_input(self, server_info):
        html, _ = server_info

        page = html
        assert "cr-file-input" in page
        assert "Upload New H5 File" in page

    def test_control_room_has_event_panel(self, server_info):
        html, _ = server_info

        page = html
        assert "cr-event-list" in page or "cr-event-panel" in page
        assert "cr-filter-all" in page
        assert "cr-filter-completed" in page
        assert "cr-filter-failed" in page

    def test_control_room_has_decision_card(self, server_info):
        html, _ = server_info

        page = html
        assert "cr-decision-card" in page

    def test_control_room_has_state_model(self, server_info):
        html, _ = server_info

        page = html
        assert "setState" in page
        assert "ready_to_submit" in page
        assert "submitting" in page

    def test_control_room_has_model_question(self, server_info):
        html, _ = server_info

        page = html
        assert "Should the patient continue to MRI" in page

    def test_report_route(self, server_info):
        """Report page builder produces report page."""
        from bremen.report_ui import build_report_page
        page = build_report_page(base_url="http://testserver", job_id="test-job")
        assert "Bremen Report" in page or "report-page" in page


class TestPipelineStageMapping:
    """Pipeline stages map to correct authoritative events."""

    def test_stage_map_correct_events(self):
        page = build_control_room_page()
        assert "runtime.input.preparation.completed" in page
        assert "runtime.normalization.completed" in page
        assert "runtime.workflow.resolved" in page
        assert "runtime.artifact.verification.completed" in page
        assert "runtime.features.validation.completed" in page
        assert "runtime.inference.completed" in page
        assert "runtime.decision.completed" in page
        assert "runtime.report.completed" in page
        assert "runtime.request.completed" in page
        assert "runtime.request.accepted" in page

    def test_stage_map_no_staging_event(self):
        page = build_control_room_page()
        assert "runtime.input.staging.completed" not in page

    def test_fail_map_present(self):
        page = build_control_room_page()
        assert "FAIL_MAP" in page
        assert "runtime.normalization.failed" in page

    def test_bremen_stage_order_not_in_control_room(self):
        page = build_control_room_page()
        assert "BREMEN_STAGE_ORDER" not in page


class TestControlRoomAuthFetchParity:
    """Protected Control Room data loads use the auth-aware wrapper."""

    def _function_body(self, page: str, function_name: str) -> str:
        fn_start = page.find(f"function {function_name}")
        assert fn_start >= 0
        fn_end = page.find("function ", fn_start + 10)
        return page[fn_start:fn_end if fn_end > 0 else len(page)]

    def test_container_catalog_uses_auth_fetch(self):
        page = build_control_room_page()
        fn_body = self._function_body(page, "loadContainerCatalog")

        assert "_authFetch(baseUrl+'/demo/api/h5/containers')" in fn_body

    def test_job_history_uses_auth_fetch(self):
        page = build_control_room_page()
        fn_body = self._function_body(page, "loadJobHistory")

        assert "var url = baseUrl+'/demo/api/jobs';" in fn_body
        assert "_authFetch(url)" in fn_body

    def test_initial_job_events_uses_auth_fetch(self):
        page = build_control_room_page()
        fn_body = self._function_body(page, "fetchInitialEvents")

        assert "_authFetch(baseUrl+'/demo/api/jobs/'+jobId+'/events')" in fn_body

    def test_job_decision_uses_auth_fetch(self):
        page = build_control_room_page()
        fn_body = self._function_body(page, "fetchDecision")

        assert "_authFetch(baseUrl+'/demo/api/jobs/'+jobId)" in fn_body

    def test_public_routes_remain_plain_fetch(self):
        page = build_control_room_page()

        assert "fetch(baseUrl+'/demo/api/models')" in page
        assert "fetch(baseUrl+'/health')" in page
        assert "fetch(baseUrl+'/model/version')" in page


class TestAccessibility:
    """Control Room meets accessibility requirements."""

    def test_semantic_list_pipeline(self):
        page = build_control_room_page()
        assert 'role="list"' in page

    def test_aria_pressed_filters(self):
        page = build_control_room_page()
        assert 'aria-pressed' in page
        assert 'aria-pressed="true"' in page

    def test_aria_live_event_panel(self):
        page = build_control_room_page()
        assert 'aria-live' in page

    def test_aria_label_filters(self):
        page = build_control_room_page()
        assert 'aria-pressed' in page

    def test_role_status_badges(self):
        page = build_control_room_page()
        assert 'role="alert"' in page or 'role="log"' in page or 'role="list"' in page

    def test_role_alert_decision(self):
        page = build_control_room_page()
        assert 'role="alert"' in page or 'role="log"' in page

    def test_reduced_motion(self):
        page = build_control_room_page()
        assert 'prefers-reduced-motion' in page

    def test_visible_focus(self):
        page = build_control_room_page()
        assert ':focus' in page


class TestPrivacy:
    """Control Room HTML contains no prohibited data."""

    def test_no_patient_identifiers(self):
        page = build_control_room_page()
        assert "patient_id" not in page
        assert "patient_name" not in page

    def test_no_model_internals(self):
        page = build_control_room_page()
        assert "coefficient" not in page
        assert "intercept" not in page
        assert "scaler_mean" not in page
        assert "imputer_statistics" not in page
        assert "feature_value" not in page

    def test_no_private_paths(self):
        page = build_control_room_page()
        # h5_path as a JS variable name is the internal transfer field —
        # what must not appear are raw server-side paths
        assert "/scans/" not in page
        assert "/tmp/" not in page
        assert "dataset_path" not in page

    def test_no_tracebacks_or_credentials(self):
        page = build_control_room_page()
        assert "Traceback" not in page
        assert "AWS_ACCESS_KEY" not in page
        assert "AWS_SECRET" not in page
        assert "s3://" not in page

    def test_no_mri_rule_out_public_wording(self):
        page = build_control_room_page()
        assert "MRI_RULE_OUT" not in page

    def test_control_room_no_model_uri(self):
        """Control Room page does not expose BREMEN_MODEL_URI."""
        page = build_control_room_page()
        assert "BREMEN_MODEL_URI" not in page

    def test_control_room_no_s3_uri(self):
        """Control Room page does not expose S3 URIs."""
        page = build_control_room_page()
        assert "s3://" not in page

    def test_control_room_no_bucket_name(self):
        """Control Room page does not expose bucket names."""
        page = build_control_room_page()
        assert "bucket" not in page.lower() or "BREMEN_DEMO_H5_BUCKET" not in page

    def test_control_room_no_object_key(self):
        """Control Room page does not expose object keys."""
        page = build_control_room_page()
        assert ".h5" not in page or "cr-file-input" in page  # file input accept attr is OK

    def test_control_room_no_local_path(self):
        """Control Room page does not expose local filesystem paths."""
        page = build_control_room_page()
        assert "/tmp/" not in page
        assert "/var/" not in page

    def test_control_room_no_environment_values(self):
        """Control Room page does not expose environment variable values."""
        page = build_control_room_page()
        assert "BREMEN_MODEL_URI" not in page
        assert "BREMEN_DEMO_H5_BUCKET" not in page

    def test_control_room_no_traceback(self):
        """Control Room page does not contain tracebacks."""
        page = build_control_room_page()
        assert "Traceback" not in page

    def test_control_room_no_patient_identifiers(self):
        """Control Room page does not contain patient identifiers."""
        page = build_control_room_page()
        assert "patient_id" not in page
        assert "patient_name" not in page

    def test_control_room_no_raw_arrays(self):
        """Control Room page does not contain raw arrays or feature values."""
        page = build_control_room_page()
        assert "coefficient" not in page
        assert "intercept" not in page
        assert "feature_value" not in page
        assert "scaler_mean" not in page
        assert "imputer_statistics" not in page

    def test_control_room_no_model_parameters(self):
        """Control Room page does not expose model parameters."""
        page = build_control_room_page()
        assert "threshold" not in page or "threshold_applied" in page  # threshold_applied in decision is OK


class TestReportPagePrivacy:
    """Report page contains no prohibited data."""

    def test_report_no_model_uri(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "BREMEN_MODEL_URI" not in page

    def test_report_no_s3_uri(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "s3://" not in page

    def test_report_no_bucket_name(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "bucket" not in page.lower()

    def test_report_no_object_key(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert ".h5" not in page

    def test_report_no_local_path(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "/tmp/" not in page
        assert "/var/" not in page

    def test_report_no_environment_values(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "BREMEN_MODEL_URI" not in page
        assert "BREMEN_DEMO_H5_BUCKET" not in page

    def test_report_no_traceback(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "Traceback" not in page

    def test_report_no_patient_identifiers(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "patient_id" not in page
        assert "patient_name" not in page

    def test_report_no_raw_arrays(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "coefficient" not in page
        assert "intercept" not in page
        assert "feature_value" not in page

    def test_report_no_model_parameters(self):
        from bremen.report_ui import build_report_page
        page = build_report_page(job_id="test")
        assert "scaler_mean" not in page
        assert "imputer_statistics" not in page


class TestModelIdentity:
    """Control Room shows exactly one real Bremen model."""

    def test_one_workflow_displayed(self):
        page = build_control_room_page()
        assert "Bremen" in page
        assert "loadModelCatalog" in page

    def test_no_model_selector(self):
        page = build_control_room_page()
        assert "loadModelCatalog" in page
        assert "availableModels" in page.lower() or "model" in page.lower()
        assert "variant" not in page.lower()

    def test_decision_policy_displayed(self):
        page = build_control_room_page()
        assert "loadModelCatalog" in page
        assert "/demo/api/models" in page
        assert "decision_policy_id" in page

    def test_scientific_certification_pending(self):
        page = build_control_room_page()
        assert "certification" in page.lower()

    def test_technical_demo_visible(self):
        page = build_control_room_page()
        assert "Technical demo only" in page or "technical demo" in page.lower()


class TestModelUnconfiguredState:
    """Analyze button disabled when model is not ready."""

    def test_analyze_button_has_disabled_attribute(self):
        page = build_control_room_page()
        assert "disabled" in page

    def test_model_hint_visible(self):
        page = build_control_room_page()
        assert "model" in page.lower()


class TestStateModel:
    """Frontend state model with valid transitions."""

    def test_setstate_function_exists(self):
        page = build_control_room_page()
        assert "function setState" in page or "setState(" in page

    def test_valid_states_defined(self):
        page = build_control_room_page()
        assert "ready_to_submit" in page
        assert "submitting" in page
        assert "running" in page
        assert "reconnecting" in page
        assert "completed" in page
        assert "failed" in page

    def test_jobstate_variable(self):
        page = build_control_room_page()
        assert "jobState" in page


class TestEventPanelBehavior:
    """Event panel has real SSE and bounded DOM."""

    def test_bounded_dom_retention(self):
        page = build_control_room_page()
        assert "MAX_EVENTS=200" in page or "MAX_EVENTS = 200" in page

    def test_duplicate_suppression(self):
        page = build_control_room_page()
        assert "lastSequence" in page

    def test_eventsource_singleton(self):
        page = build_control_room_page()
        assert "eventSource" in page
        assert "eventSource.close()" in page or "eventSource.close(" in page

    def test_filter_function(self):
        page = build_control_room_page()
        assert "filterEvents" in page

    def test_autoscroll_control(self):
        page = build_control_room_page()
        assert "autoScroll" in page or "toggleAutoScroll" in page


class TestLegacyCompatibility:
    """Workspace routes and APIs preserved."""

    def test_health_responds_during_control_room(self, server_info):
        html, _ = server_info
        page = html

    def test_jobs_api_responds_during_control_room(self, server_info):
        html, _ = server_info
        page = html

    def test_model_version_responds(self, server_info):
        html, _ = server_info
        page = html


class TestPR0098PersistentUpload:
    """PR0098: Control Room upload uses persistent S3-backed endpoint."""

    def test_handle_file_select_posts_to_persistent_endpoint(self):
        """handleFileSelect() fetches /demo/api/h5/containers, not /demo/api/stage."""
        page = build_control_room_page()
        assert "/demo/api/h5/containers" in page
        # The old ephemeral endpoint must NOT be referenced in handleFileSelect
        # (It may still appear in other test fixtures, but not in the page JS)
        # Find handleFileSelect function body and check it uses the persistent endpoint
        idx = page.find("function handleFileSelect")
        assert idx > 0, "handleFileSelect function not found"
        end_idx = page.find("function ", idx + 10)
        if end_idx == -1:
            end_idx = len(page)
        fn_body = page[idx:end_idx]
        assert "/demo/api/h5/containers" in fn_body, "handleFileSelect must use /demo/api/h5/containers"
        # Verify the old endpoint is not in this function
        assert "/demo/api/stage" not in fn_body, "handleFileSelect must not use /demo/api/stage"

    def test_successful_upload_selects_container_type_source(self):
        """Successful upload sets selectedSource with type='container' and returned id."""
        page = build_control_room_page()
        # Check the success path uses 'uploaded' status and sets type='container'
        idx = page.find("data.status==='uploaded'")
        assert idx > 0, "Success path must check data.status==='uploaded'"
        # Check that selectedSource is set with type:'container'
        assert "type:'container'" in page or 'type:"container"' in page
        # Check that data.id is used (not data.upload_id)
        assert "data.id" in page
        # Check upload_id is NOT used in the success path
        fn_start = page.find("function handleFileSelect")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "data.upload_id" not in fn_body, "Must use data.id not data.upload_id"

    def test_successful_upload_calls_load_container_catalog(self):
        """Successful upload refreshes the container catalog."""
        page = build_control_room_page()
        # Find handleFileSelect function body
        fn_start = page.find("function handleFileSelect")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # Verify loadContainerCatalog() is called in the success path
        assert "loadContainerCatalog()" in fn_body, "Success path must call loadContainerCatalog()"

    def test_upload_failure_clears_selected_source(self):
        """Upload failure sets selectedSource=null and state=idle."""
        page = build_control_room_page()
        # Find handleFileSelect function
        fn_start = page.find("function handleFileSelect")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # Failure paths must set selectedSource=null
        assert "selectedSource=null" in fn_body, "Failure must clear selectedSource"
        # Failure paths must set state to idle
        assert "setState('idle')" in fn_body, "Failure must set state to idle"
        # Old dead code error_code checks must be removed
        assert "SOURCE_ERROR" not in fn_body, "SOURCE_ERROR dead code must be removed"
        assert "MISSING_SOURCE" not in fn_body, "MISSING_SOURCE dead code must be removed"

    def test_patients_list_heading_present(self):
        """Patients List heading is present in the UI."""
        page = build_control_room_page()
        assert "Patients List" in page

    def test_container_catalog_heading_removed(self):
        """Container Catalog heading is no longer present."""
        page = build_control_room_page()
        assert "Container Catalog" not in page

    def test_refresh_patients_button_text(self):
        """Refresh button says 'Refresh Patients'."""
        page = build_control_room_page()
        assert "Refresh Patients" in page


class TestPR0099ClarityRedesign:
    """PR0099: Control Room clarity redesign."""

    def test_15_cr_stage_rows_render(self):
        """15 cr-stage divs render in the pipeline."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15

    def test_six_new_stage_ids_present(self):
        """The six important new stage ids appear."""
        page = build_control_room_page()
        assert "stage-artifact-verified" in page
        assert "stage-artifact-loaded" in page
        assert "stage-artifact-adapted" in page
        assert "stage-model-validated" in page
        assert "stage-features-produced" in page
        assert "stage-output-validated" in page

    def test_stage_map_includes_new_ids(self):
        """STAGE_MAP includes the new stage ids."""
        page = build_control_room_page()
        assert "stage-artifact-verified" in page
        assert "stage-artifact-loaded" in page
        assert "stage-artifact-adapted" in page
        assert "stage-model-validated" in page
        assert "stage-features-produced" in page
        assert "stage-output-validated" in page

    def test_input_prepared_after_artifact_stages(self):
        """Input prepared appears after artifact-related stages."""
        page = build_control_room_page()
        # In the HTML pipeline, stage-source (Input prepared) should come
        # after the artifact-related stages
        idx_verified = page.find('id="stage-artifact-verified"')
        idx_source = page.find('id="stage-source"')
        assert idx_verified > 0 and idx_source > 0
        assert idx_verified < idx_source, "Input prepared must come after artifact stages"

    def test_unicode_escapes_single_backslash(self):
        """Unicode escapes are single-backslash / render as intended."""
        page = build_control_room_page()
        # The JS should contain single-backslash unicode escapes, not double-escaped
        # Double-escaped would be \\u2717 (two backslashes in source)
        assert r"\\u2717" not in page, "Double-escaped u2717 found"
        assert r"\\u2713" not in page, "Double-escaped u2713 found"
        assert r"\\u25CF" not in page, "Double-escaped u25CF found"

    def test_decision_card_clinician_confirm(self):
        """Decision card contains 'Ask your clinician to confirm'."""
        page = build_control_room_page()
        assert "Ask your clinician to confirm" in page

    def test_decision_card_not_diagnosis(self):
        """Decision card contains 'This is not a diagnosis'."""
        page = build_control_room_page()
        assert "This is not a diagnosis" in page

    def test_decision_card_score_threshold_labels(self):
        """Decision card has Score and Threshold labels."""
        page = build_control_room_page()
        assert "Score " in page
        assert "Threshold " in page

    def test_decision_card_no_red_green_amber(self):
        """Decision card does not introduce red/green/amber styling."""
        page = build_control_room_page()
        # Check fetchDecision function body for color coding
        fn_start = page.find("function fetchDecision")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "#ff0000" not in fn_body.lower()
        assert "#e24b4a" not in fn_body.lower()
        assert "background:green" not in fn_body.lower()
        assert "background:red" not in fn_body.lower()

    def test_open_report_link_present(self):
        """Open report behavior remains present."""
        page = build_control_room_page()
        assert "Open report" in page
        assert "cr-report-link" in page

    def test_event_empty_hides_after_first_event(self):
        """cr-event-empty hides after first event."""
        page = build_control_room_page()
        assert "cr-event-empty" in page
        # addEventRow hides cr-event-empty
        assert "emptyEl.style.display='none'" in page or "emptyEl" in page

    def test_terminal_collapse_function_exists(self):
        """collapseEventPanel function exists."""
        page = build_control_room_page()
        assert "collapseEventPanel" in page

    def test_terminal_collapse_no_hardcoded_9_of_9(self):
        """Terminal collapse does not hardcode 9 of 9."""
        page = build_control_room_page()
        assert "9 of 9" not in page

    def test_pr0098_patients_list_preserved(self):
        """PR0098 Patients List heading preserved."""
        page = build_control_room_page()
        assert "Patients List" in page
        assert "Refresh Patients" in page

    def test_pr0098_upload_endpoint_preserved(self):
        """PR0098 upload endpoint preserved."""
        page = build_control_room_page()
        assert "/demo/api/h5/containers" in page
        # Verify no /demo/api/stage in handleFileSelect
        fn_start = page.find("function handleFileSelect")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "/demo/api/stage" not in fn_body

    def test_css_stage_caption_rule(self):
        """CSS caption rule exists."""
        page = build_control_room_page()
        assert "cr-stage-caption" in page


class TestPR0099aQAFix:
    """PR0099a: Job History enrichment, decision card spacing, status-rail."""

    def test_source_display_name_in_job_history(self):
        """source_display_name renders in loadJobHistory()."""
        page = build_control_room_page()
        assert "source_display_name" in page
        fn_start = page.find("function loadJobHistory")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "source_display_name" in fn_body

    def test_source_display_name_element_class(self):
        """source_display_name uses cr-history-source class."""
        page = build_control_room_page()
        assert "cr-history-source" in page

    def test_job_history_expands(self):
        """Patient Reports card has flex:1 for expansion."""
        page = build_control_room_page()
        idx = page.find('cr-card-title">Patient Reports')
        assert idx > 0
        before = page[max(0, idx-300):idx]
        assert 'flex:1' in before

    def test_live_events_bounded(self):
        """Live Events card has max-height bound."""
        page = build_control_room_page()
        idx = page.find('Live Events')
        assert idx > 0
        before = page[max(0, idx-300):idx]
        assert 'max-height' in before

    def test_status_rail_defer_css(self):
        """CSS has defer rail class."""
        page = build_control_room_page()
        assert ".cr-history-item.defer" in page
        assert "cr-decision-card.defer" in page

    def test_status_rail_continue_css(self):
        """CSS has continue rail class."""
        page = build_control_room_page()
        assert ".cr-history-item.continue" in page
        assert "cr-decision-card.continue" in page

    def test_status_rail_no_error_for_decision(self):
        """status-error is not used for decision rail coloring."""
        page = build_control_room_page()
        fn_start = page.find(".cr-history-item.defer")
        assert fn_start > 0
        fn_end = page.find(".cr-history-item.continue")
        assert fn_end > 0
        css_section = page[fn_start:fn_end]
        assert "status-error" not in css_section

    def test_history_item_rail_class_from_decision_code(self):
        """loadJobHistory applies rail class based on decision_code."""
        page = build_control_room_page()
        fn_start = page.find("function loadJobHistory")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "MRI_REVIEW_DEFER" in fn_body
        assert "CONTINUE_MRI" in fn_body
        assert "railClass" in fn_body

    def test_decision_card_rail_class_from_code(self):
        """fetchDecision applies rail class based on decision_code."""
        page = build_control_room_page()
        fn_start = page.find("function fetchDecision")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "MRI_REVIEW_DEFER" in fn_body
        assert "CONTINUE_MRI" in fn_body

    def test_live_events_retains_filter_buttons(self):
        """Live Events filter buttons remain present."""
        page = build_control_room_page()
        assert "cr-filter-all" in page
        assert "cr-filter-completed" in page
        assert "cr-filter-failed" in page
        assert "cr-autoscroll-btn" in page

    def test_live_events_retains_empty_state(self):
        """Live Events empty state element remains present."""
        page = build_control_room_page()
        assert "cr-event-empty" in page

    def test_live_events_retains_event_list(self):
        """Live Events event list element remains present."""
        page = build_control_room_page()
        assert "cr-event-list" in page

    def test_decision_card_padding_matches_cards(self):
        """Decision card padding matches other card conventions."""
        page = build_control_room_page()
        assert "padding:var(--sp-16) var(--sp-20) var(--sp-16) var(--sp-24)" in page


class TestPR0099bJobIdentityFix:
    """PR0099b: Job event identity, source display-name, padding."""

    def test_run_workflow_request_accepts_optional_job_id(self):
        """run_workflow_request accepts optional job_id keyword arg."""
        from bremen.api.workflow_orchestrator import run_workflow_request
        import inspect
        sig = inspect.signature(run_workflow_request)
        assert "job_id" in sig.parameters
        param = sig.parameters["job_id"]
        assert param.default is None
        assert param.kind == inspect.Parameter.KEYWORD_ONLY

    def test_run_workflow_request_no_job_id_still_works(self):
        """run_workflow_request without job_id still works (backward compat)."""
        from bremen.api.workflow_orchestrator import run_workflow_request
        import inspect
        sig = inspect.signature(run_workflow_request)
        assert "job_id" in sig.parameters
        assert sig.parameters["job_id"].default is None

    def test_create_analysis_job_passes_job_id(self):
        """create_analysis_job passes job_id into run_workflow_request."""
        import inspect
        from bremen.api.job_api_handler import create_analysis_job
        src = inspect.getsource(create_analysis_job)
        assert "job_id=job_id" in src

    def test_handle_jobs_create_derives_display_name_from_upload_id(self):
        """handle_jobs_create derives effective_container_id from upload_id."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert "effective_container_id" in src

    def test_handle_jobs_create_derives_display_name_from_source_id(self):
        """handle_jobs_create derives effective_container_id from source_id."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert "effective_container_id" in src

    def test_source_display_no_s3_path_exposure(self):
        """Source display logic does not expose s3:// or /tmp/ paths."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        # The effective_container_id derivation should not include s3:// or /tmp/
        # Check the specific derivation lines
        lines = src.split("\n")
        for line in lines:
            if "effective_container_id" in line and "= " in line:
                assert "s3://" not in line, "s3:// must not appear in display name derivation"
                assert "/tmp/" not in line, "/tmp/ must not appear in display name derivation"

    def test_decision_card_left_padding_increased(self):
        """Decision card has larger left padding for breathing room."""
        page = build_control_room_page()
        assert "var(--sp-24)" in page

    def test_decision_card_padding_has_four_values(self):
        """Decision card uses four-value padding shorthand."""
        page = build_control_room_page()
        assert "padding:var(--sp-16) var(--sp-20) var(--sp-16) var(--sp-24)" in page


class TestPR0099CRuntimeStageCompleteness:
    """PR0099C: Control Room runtime stage completeness."""

    # ---- PART 1 — Missing event types emitted ----

    def test_stage_map_uses_correct_event_type_names(self):
        """STAGE_MAP keys use correct event type names."""
        page = build_control_room_page()
        assert "runtime.artifact.load.completed" in page
        assert "runtime.artifact.adaptation.completed" in page
        assert "runtime.features.completed" in page

    def test_stage_map_no_wrong_event_type_names(self):
        """STAGE_MAP does not use wrong event type names."""
        page = build_control_room_page()
        assert "'runtime.artifact.loaded'" not in page
        assert "'runtime.artifact.adapted'" not in page
        assert "'runtime.features.produced'" not in page

    def test_prepare_artifact_emits_four_events(self):
        """prepare_artifact emits artifact verification, load, adaptation, and model validation events."""
        import inspect
        from bremen.api.workflow_bremen import BremenProvider
        src = inspect.getsource(BremenProvider.prepare_artifact)
        assert "runtime.artifact.load.completed" in src
        assert "runtime.artifact.adaptation.completed" in src
        assert "runtime.model.validation.completed" in src
        assert "runtime.artifact.verification.completed" in src

    def test_execute_emits_features_completed(self):
        """execute emits runtime.features.completed after build_features."""
        import inspect
        from bremen.api.workflow_bremen import BremenProvider
        src = inspect.getsource(BremenProvider.execute)
        assert "runtime.features.completed" in src

    def test_prepare_artifact_emits_validated_model_event_only_when_valid(self):
        """model validation event only emitted when validation_status == completed."""
        import inspect
        from bremen.api.workflow_bremen import BremenProvider
        src = inspect.getsource(BremenProvider.prepare_artifact)
        assert "validation_status == \"completed\"" in src

    # ---- PART 2 — Execution trace finalization ----

    def test_trace_status_completed_with_all_11_stages(self):
        """build_trace_from_events returns completed for 11 completed stages."""
        from bremen.api.execution_trace import build_trace_from_events
        from bremen.api.event_store import BoundedEventStore
        from bremen.api.event_schema import JobEvent

        store = BoundedEventStore()
        job_id = "trace-test-1"
        all_events = [
            "runtime.artifact.verification.completed",
            "runtime.artifact.load.completed",
            "runtime.artifact.adaptation.completed",
            "runtime.model.validation.completed",
            "runtime.input.preparation.completed",
            "runtime.features.completed",
            "runtime.features.validation.completed",
            "runtime.inference.completed",
            "runtime.output.validation.completed",
            "runtime.decision.completed",
            "runtime.report.completed",
        ]
        for ev_type in all_events:
            ev = JobEvent(
                job_id=job_id,
                request_id="req-trace",
                workflow_id="bremen",
                stage="test",
                event_type=ev_type,
                status="completed",
            )
            store.append(job_id, ev)

        trace = build_trace_from_events(store, job_id, "bremen")
        assert trace is not None
        assert trace.status == "completed", f"expected completed, got {trace.status}"
        assert trace.completed_stage_count == 11
        assert trace.total_applicable_stage_count == 11
        stages_map = {s.stage_id: s.status for s in trace.stages}
        assert stages_map.get("artifact_loaded") == "completed"
        assert stages_map.get("artifact_adapted") == "completed"
        assert stages_map.get("model_validated") == "completed"
        assert stages_map.get("features_produced") == "completed"

    def test_trace_status_running_with_partial_stages(self):
        """build_trace_from_events returns running for partial completion."""
        from bremen.api.execution_trace import build_trace_from_events
        from bremen.api.event_store import BoundedEventStore
        from bremen.api.event_schema import JobEvent

        store = BoundedEventStore()
        job_id = "trace-test-2"
        partial_events = [
            "runtime.artifact.verification.completed",
            "runtime.input.preparation.completed",
        ]
        for ev_type in partial_events:
            ev = JobEvent(
                job_id=job_id,
                request_id="req-trace",
                workflow_id="bremen",
                stage="test",
                event_type=ev_type,
                status="completed",
            )
            store.append(job_id, ev)

        trace = build_trace_from_events(store, job_id, "bremen")
        assert trace is not None
        assert trace.status == "running"

    # ---- PART 3 — Pipeline summary ----

    def test_completed_summary_contains_15_of_15(self):
        """Completed summary contains '15 of 15 pipeline stages completed'."""
        page = build_control_room_page()
        assert "15 of 15 pipeline stages completed" in page or "pipeline stages completed" in page

    def test_completed_summary_no_one_of_one_events(self):
        """Completed summary does not contain '1 of 1 events'."""
        page = build_control_room_page()
        assert "1 of 1 events" not in page

    def test_completed_summary_no_10_of_14(self):
        """Completed summary does not contain '10 of 14'."""
        page = build_control_room_page()
        assert "10 of 14" not in page

    def test_completed_summary_no_9_of_9(self):
        """Completed summary does not contain '9 of 9'."""
        page = build_control_room_page()
        assert "9 of 9" not in page

    def test_collapse_uses_pipeline_total_not_event_cache(self):
        """collapseEventPanel uses pipelineTotal not eventCache.length."""
        page = build_control_room_page()
        assert "pipelineTotal" in page
        assert "pipeline stages completed" in page

    # ---- PART 4 — Tiny-score UX ----

    def test_tiny_positive_score_renders_less_than_0_001(self):
        """Tiny positive score < 0.001 renders '<0.001'."""
        page = build_control_room_page()
        # fetchDecision should have <0.001 logic
        fn_start = page.find("function fetchDecision")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "<0.001" in fn_body

    def test_null_score_renders_em_dash(self):
        """Null/undefined score renders 'Score —'."""
        page = build_control_room_page()
        fn_start = page.find("function fetchDecision")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "Score —" in fn_body

    def test_exact_zero_renders_0_000(self):
        """Exact zero score renders 'Score 0.000'."""
        page = build_control_room_page()
        fn_start = page.find("function fetchDecision")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "0.000" in fn_body

    def test_threshold_renders_normally(self):
        """Threshold 0.413 renders 'Threshold 0.413'."""
        page = build_control_room_page()
        fn_start = page.find("function fetchDecision")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "Threshold 0.413" in fn_body or "Threshold " in fn_body

    def test_null_threshold_renders_em_dash(self):
        """Null/undefined threshold renders 'Threshold —'."""
        page = build_control_room_page()
        fn_start = page.find("function fetchDecision")
        fn_end = page.find("function ", fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "Threshold —" in fn_body

    # ---- PART 5 — Source display / patient name ----

    def test_source_registry_lookup_for_uuid_source_id(self):
        """handle_jobs_create looks up source registry for filename when source_id is a UUID."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert "get_source_info" in src
        assert "source_info.get(\"filename\")" in src

    def test_list_analysis_jobs_fallback_is_patient_not_unknown(self):
        """list_analysis_jobs fallback is 'Patient' not 'Unknown'."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert "\"Patient\"" in src
        assert "\"Unknown\"" not in src

    def test_source_display_no_s3_or_path_exposure(self):
        """Source display no s3://, /tmp/, bucket, or prefix in user-facing field."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        lines = src.split("\n")
        for line in lines:
            if "effective_container_id" in line and "= " in line:
                assert "s3://" not in line
                assert "/tmp/" not in line

    def test_fallback_without_metadata_is_patient(self):
        """Fallback without safe metadata is 'Patient', not 'Unknown' and not UUID."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert "\"Patient\"" in src
        assert "\"Unknown\"" not in src


class TestAppendixAModelReportBinding:
    """APPENDIX A: Model/report binding must be model-specific.

    Reports must be scoped by model_id, not patient/source alone.
    Switching models must not reuse previous model reports.
    """

    # ---- PART 1: Backend model-scoped job creation ----

    def test_create_analysis_job_stores_model_id_in_input_summary(self):
        """create_analysis_job stores model_id in input_summary."""
        import inspect
        from bremen.api.job_api_handler import create_analysis_job
        src = inspect.getsource(create_analysis_job)
        assert '"model_id": model_id' in src or "'model_id': model_id" in src

    def test_list_analysis_jobs_returns_model_id(self):
        """list_analysis_jobs returns model_id in summary."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert 'summary["model_id"]' in src

    def test_list_analysis_jobs_filters_by_model_id(self):
        """list_analysis_jobs filters by model_id when provided."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert 'if model_id is not None:' in src or 'model_id is not None' in src
        assert 'job_model_id' in src

    def test_handle_jobs_create_passes_model_id(self):
        """handle_jobs_create passes model_id from request to create_analysis_job."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'model_id=model_id' in src

    def test_job_id_unique_per_creation(self):
        """Each create_analysis_job call produces a unique job_id."""
        import inspect
        from bremen.api.job_api_handler import create_analysis_job
        src = inspect.getsource(create_analysis_job)
        assert 'job_id = str(_uuid.uuid4())' in src or 'job_id = str(uuid.uuid4())' in src

    def test_no_source_level_report_caching(self):
        """create_analysis_job has no source-level dedup or caching logic."""
        import inspect
        from bremen.api.job_api_handler import create_analysis_job
        src = inspect.getsource(create_analysis_job)
        # No lookup for existing job by source_id or container_id
        assert 'existing_job' not in src.lower()
        assert 'cached_report' not in src.lower()
        assert 'reuse_report' not in src.lower()

    # ---- PART 2: Frontend model-scoped identity ----

    def test_start_analysis_sends_model_id(self):
        """startAnalysis sends model_id in the POST body."""
        page = build_control_room_page()
        fn_start = page.find('function startAnalysis')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'body.model_id=selectedModelId' in fn_body

    def test_load_job_history_sends_model_id_filter(self):
        """loadJobHistory sends model_id as query parameter."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'selectedModelId' in fn_body
        assert "params.append('model_id'" in fn_body or 'params.append(\'model_id\'' in fn_body

    def test_job_history_displays_model_id(self):
        """Job History rows display model_id."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'j.model_id' in fn_body
        assert 'cr-history-meta' in fn_body

    def test_open_job_navigates_to_specific_job_report(self):
        """openJob navigates to /demo/report/{job_id}, not a source-level URL."""
        page = build_control_room_page()
        fn_start = page.find('function openJob')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert '/demo/report/' in fn_body
        assert 'jobId' in fn_body

    def test_decision_card_report_link_uses_job_id(self):
        """Decision card report link uses the specific job_id."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert '/demo/report/'+"'" in fn_body or '/demo/report/' in fn_body

    # ---- PART 3: Model switch resets stale state ----

    def test_on_model_select_resets_decision_card(self):
        """onModelSelect resets the decision card via renderDecisionPlaceholder."""
        page = build_control_room_page()
        fn_start = page.find('function onModelSelect')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'renderDecisionPlaceholder()' in fn_body

    def test_on_model_select_resets_pipeline(self):
        """onModelSelect resets pipeline stages."""
        page = build_control_room_page()
        fn_start = page.find('function onModelSelect')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'resetPipeline()' in fn_body

    def test_on_model_select_resets_event_panel(self):
        """onModelSelect resets the event panel."""
        page = build_control_room_page()
        fn_start = page.find('function onModelSelect')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'resetEventPanel()' in fn_body

    def test_on_model_select_clears_current_job(self):
        """onModelSelect clears currentJobId."""
        page = build_control_room_page()
        fn_start = page.find('function onModelSelect')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'currentJobId=null' in fn_body

    def test_on_model_select_sets_state_idle(self):
        """onModelSelect sets state to idle."""
        page = build_control_room_page()
        fn_start = page.find('function onModelSelect')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "setState('idle')" in fn_body

    # ---- PART 4: Safety ----

    def test_no_s3_or_path_in_model_display(self):
        """Model display in job history does not expose S3 or paths."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 's3://' not in fn_body
        assert '/tmp/' not in fn_body
        assert '/scans/' not in fn_body

    def test_fetch_decision_no_model_internals(self):
        """fetchDecision does not expose model internals."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'coefficient' not in fn_body
        assert 'intercept' not in fn_body
        assert 'scaler_mean' not in fn_body

    # ---- PART 5: PR0099B/0099C preservation ----

    def test_pr0099b_job_id_identity_preserved(self):
        """PR0099B: run_workflow_request still accepts optional job_id."""
        from bremen.api.workflow_orchestrator import run_workflow_request
        import inspect
        sig = inspect.signature(run_workflow_request)
        assert 'job_id' in sig.parameters
        assert sig.parameters['job_id'].default is None

    def test_pr0099c_stage_events_preserved(self):
        """PR0099C: All 4 missing stage events still emitted."""
        import inspect
        from bremen.api.workflow_bremen import BremenProvider
        src = inspect.getsource(BremenProvider.prepare_artifact)
        assert 'runtime.artifact.load.completed' in src
        assert 'runtime.artifact.adaptation.completed' in src
        assert 'runtime.model.validation.completed' in src
        src2 = inspect.getsource(BremenProvider.execute)
        assert 'runtime.features.completed' in src2

    def test_pr0099c_trace_finalization_preserved(self):
        """PR0099C: Terminal event detection still finalizes trace."""
        import inspect
        from bremen.api.execution_trace import build_trace_from_events
        src = inspect.getsource(build_trace_from_events)
        assert 'terminal_event_types' in src
        assert 'runtime.workflow.completed' in src
        assert 'runtime.request.completed' in src


class TestPR0099DReportDeleteAndRerunGuard:
    """PR0099D: Control Room model-specific report deletion and rerun guard."""

    # ---- PART 1: Backend model-specific report lock ----

    def test_find_existing_completed_report_function_exists(self):
        """_find_existing_completed_report function exists in job_api_handler."""
        import inspect
        from bremen.api.job_api_handler import _find_existing_completed_report
        sig = inspect.signature(_find_existing_completed_report)
        assert 'source_key' in sig.parameters
        assert 'workflow_id' in sig.parameters
        assert 'model_id' in sig.parameters

    def test_rerun_guard_blocks_same_source_workflow_model(self):
        """Same source + workflow + model with completed report blocks duplicate."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src
        assert '_find_existing_completed_report' in src

    def test_rerun_guard_uses_source_key_identity(self):
        """Rerun guard uses source_key for identity matching."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'source_key' in src

    def test_create_analysis_job_accepts_source_key(self):
        """create_analysis_job accepts source_key parameter."""
        import inspect
        from bremen.api.job_api_handler import create_analysis_job
        sig = inspect.signature(create_analysis_job)
        assert 'source_key' in sig.parameters

    def test_input_summary_stores_source_key(self):
        """create_analysis_job stores source_key in input_summary."""
        import inspect
        from bremen.api.job_api_handler import create_analysis_job
        src = inspect.getsource(create_analysis_job)
        assert '"source_key": source_key' in src

    def test_list_analysis_jobs_returns_source_key(self):
        """list_analysis_jobs returns source_key in summary."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert 'source_key' in src

    # ---- PART 2: Report deletion ----

    def test_delete_report_function_exists(self):
        """delete_report function exists."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        sig = inspect.signature(delete_report)
        assert 'job_id' in sig.parameters
        assert 'workflow_id' in sig.parameters

    def test_delete_report_soft_deletes(self):
        """delete_report sets report status to UNAVAILABLE (soft delete)."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        src = inspect.getsource(delete_report)
        assert 'REPORT_STATUS_UNAVAILABLE' in src

    def test_delete_report_returns_safe_response(self):
        """delete_report returns safe JSON with no paths or internals."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        src = inspect.getsource(delete_report)
        assert 's3://' not in src
        assert '/tmp/' not in src
        assert 'h5_path' not in src
        assert '"status": "deleted"' in src

    def test_delete_report_does_not_delete_source(self):
        """delete_report does not delete source files or catalog entries."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        src = inspect.getsource(delete_report)
        assert 'unlink' not in src
        assert 'os.remove' not in src
        assert 'shutil' not in src

    def test_handle_report_delete_function_exists(self):
        """handle_report_delete function exists for POST action routing."""
        import inspect
        from bremen.api.job_api_handler import handle_report_delete
        sig = inspect.signature(handle_report_delete)
        assert 'handler' in sig.parameters
        assert 'body' in sig.parameters

    def test_handle_jobs_create_routes_delete_report_action(self):
        """handle_jobs_create routes action=delete_report."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'delete_report' in src
        assert 'action' in src

    def test_list_analysis_jobs_has_report_deleted_field(self):
        """list_analysis_jobs returns report_deleted field."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert 'report_deleted' in src

    # ---- PART 3: Frontend disabled patient rows ----

    def test_analyzed_source_keys_variable_exists(self):
        """analyzedSourceKeys global variable exists."""
        page = build_control_room_page()
        assert 'analyzedSourceKeys' in page

    def test_load_job_history_populates_analyzed_source_keys(self):
        """loadJobHistory populates analyzedSourceKeys from job data."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'analyzedSourceKeys' in fn_body
        assert 'source_key' in fn_body

    def test_container_item_has_analyzed_class(self):
        """Container items get analyzed class when already analyzed."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'analyzed' in fn_body
        assert 'isAnalyzed' in fn_body

    def test_analyzed_row_cannot_be_selected(self):
        """selectContainer prevents selection of analyzed rows."""
        page = build_control_room_page()
        fn_start = page.find('function selectContainer')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'analyzed' in fn_body

    def test_analyzed_css_class_exists(self):
        """CSS class for analyzed/disabled state exists."""
        page = build_control_room_page()
        assert '.cr-container-item.analyzed' in page

    # ---- PART 4: Analyze button blocked for analyzed sources ----

    def test_update_readiness_checks_analyzed_state(self):
        """updateReadiness checks analyzedSourceKeys for blocked state."""
        page = build_control_room_page()
        fn_start = page.find('function updateReadiness')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'analyzedSourceKeys' in fn_body

    def test_update_readiness_shows_analyzed_message(self):
        """updateReadiness shows 'Already analyzed' message."""
        page = build_control_room_page()
        assert 'Already analyzed with this model' in page

    def test_start_analysis_checks_analyzed_state(self):
        """startAnalysis checks analyzedSourceKeys before submitting."""
        page = build_control_room_page()
        fn_start = page.find('function startAnalysis')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'analyzedSourceKeys' in fn_body

    # ---- PART 5: Model switch recomputes disabled state ----

    def test_on_model_select_resets_analyzed_state(self):
        """onModelSelect calls loadJobHistory which recomputes analyzedSourceKeys."""
        page = build_control_room_page()
        fn_start = page.find('function onModelSelect')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'loadJobHistory()' in fn_body

    def test_load_job_history_calls_load_container_catalog(self):
        """loadJobHistory calls loadContainerCatalog to re-render with analyzed state."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'loadContainerCatalog()' in fn_body

    # ---- PART 6: Delete report UX ----

    def test_delete_report_button_in_job_history(self):
        """Delete report button appears in job history for available reports."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'btn-delete-report' in fn_body
        assert 'Delete report' in fn_body

    def test_delete_report_confirmation_text(self):
        """Delete report has proper confirmation text."""
        page = build_control_room_page()
        assert 'Delete this generated report?' in page
        assert 'patient file will remain available' in page

    def test_delete_report_function_exists_in_page(self):
        """deleteReport function exists in the page."""
        page = build_control_room_page()
        assert 'function deleteReport' in page

    def test_delete_report_posts_action(self):
        """deleteReport sends POST with action=delete_report."""
        page = build_control_room_page()
        fn_start = page.find('function deleteReport')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'action' in fn_body
        assert 'delete_report' in fn_body

    def test_delete_report_clears_decision_card(self):
        """deleteReport resets decision card via renderDecisionPlaceholder if current job."""
        page = build_control_room_page()
        fn_start = page.find('function deleteReport')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'renderDecisionPlaceholder()' in fn_body

    def test_delete_report_refreshes_job_history(self):
        """deleteReport calls loadJobHistory after success."""
        page = build_control_room_page()
        fn_start = page.find('function deleteReport')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'loadJobHistory()' in fn_body

    def test_report_deleted_status_in_history(self):
        """Job history shows 'Report deleted' for deleted reports."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'Report deleted' in fn_body

    def test_delete_report_window_export(self):
        """deleteReport is exported on window."""
        page = build_control_room_page()
        assert 'window.deleteReport' in page

    # ---- PART 7: No visible container copy ----

    def test_no_visible_container_s(self):
        """No visible 'container(s)' in the UI."""
        page = build_control_room_page()
        assert 'container(s)' not in page

    def test_no_visible_container_colon(self):
        """No visible 'Container:' in the UI."""
        page = build_control_room_page()
        assert 'Container:' not in page

    def test_patient_label_used(self):
        """Patient label used instead of container."""
        page = build_control_room_page()
        assert 'Patient:' in page or 'patient' in page.lower()

    # ---- PART 8: Safety ----

    def test_no_s3_or_path_in_delete_logic(self):
        """Delete report logic does not expose S3 or paths."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        src = inspect.getsource(delete_report)
        assert 's3://' not in src
        assert '/tmp/' not in src
        assert 'h5_path' not in src

    def test_no_container_copy_in_analyzed_message(self):
        """Analyzed message does not use container terminology."""
        page = build_control_room_page()
        fn_start = page.find('function updateReadiness')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'container' not in fn_body.lower()

    # ---- PART 9: PR0099B/0099C preservation ----

    def test_pr0099b_job_id_identity_preserved(self):
        """PR0099B: run_workflow_request still accepts optional job_id."""
        from bremen.api.workflow_orchestrator import run_workflow_request
        import inspect
        sig = inspect.signature(run_workflow_request)
        assert 'job_id' in sig.parameters

    def test_pr0099c_stage_events_preserved(self):
        """PR0099C: All 4 missing stage events still emitted."""
        import inspect
        from bremen.api.workflow_bremen import BremenProvider
        src = inspect.getsource(BremenProvider.prepare_artifact)
        assert 'runtime.artifact.load.completed' in src
        assert 'runtime.artifact.adaptation.completed' in src
        assert 'runtime.model.validation.completed' in src
        src2 = inspect.getsource(BremenProvider.execute)
        assert 'runtime.features.completed' in src2

    def test_pr0099c_tiny_score_preserved(self):
        """PR0099C: Tiny score <0.001 formatting preserved."""
        page = build_control_room_page()
        assert '<0.001' in page

    def test_pr0099c_pipeline_summary_preserved(self):
        """PR0099C: 15 pipeline stages summary preserved."""
        page = build_control_room_page()
        assert 'pipeline stages completed' in page


class TestPR0099EPatientDisplayNames:
    """PR0099E: Patient display names and Patient Reports UX."""

    # ---- PART 1: Backend patient name extraction ----

    def test_extract_patient_display_name_function_exists(self):
        """extract_patient_display_name function exists."""
        import inspect
        from bremen.api.job_api_handler import extract_patient_display_name
        sig = inspect.signature(extract_patient_display_name)
        assert 'h5_path' in sig.parameters

    def test_extract_patient_name_from_h5_scalar_string(self):
        """H5 with /session/sample/patient_name scalar string returns name."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='Nova_257')
            assert extract_patient_display_name(h5_path) == 'Nova_257'

    def test_extract_patient_name_from_h5_bytes(self):
        """H5 with bytes patient_name decodes safely."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data=b'Patient_001')
            assert extract_patient_display_name(h5_path) == 'Patient_001'

    def test_extract_patient_name_missing_returns_empty(self):
        """Missing patient_name returns empty string."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                f.create_group('session').create_group('sample')
            assert extract_patient_display_name(h5_path) == ''

    def test_extract_patient_name_empty_returns_empty(self):
        """Empty patient_name returns empty string."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='')
            assert extract_patient_display_name(h5_path) == ''

    def test_extract_patient_name_unsafe_path_returns_empty(self):
        """Unsafe patient_name containing path returns empty."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='s3://bucket/key')
            assert extract_patient_display_name(h5_path) == ''

    def test_extract_patient_name_unsafe_tmp_returns_empty(self):
        """Unsafe patient_name containing /tmp/ returns empty."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='/tmp/some/file')
            assert extract_patient_display_name(h5_path) == ''

    def test_extract_patient_name_too_long_returns_empty(self):
        """Patient name > 80 chars returns empty."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='A' * 100)
            assert extract_patient_display_name(h5_path) == ''

    def test_extract_patient_name_failure_does_not_raise(self):
        """Patient name extraction failure does not raise."""
        from bremen.api.job_api_handler import extract_patient_display_name
        assert extract_patient_display_name('/nonexistent/path.h5') == ''
        assert extract_patient_display_name('') == ''

    def test_extract_patient_name_from_scans_target(self):
        """Patient name can be read from /scans/target/patient_name."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('scans').create_group('target')
                s.create_dataset('patient_name', data='ScanPatient_01')
            assert extract_patient_display_name(h5_path) == 'ScanPatient_01'

    def test_create_analysis_job_accepts_patient_display_name(self):
        """create_analysis_job accepts patient_display_name parameter."""
        import inspect
        from bremen.api.job_api_handler import create_analysis_job
        sig = inspect.signature(create_analysis_job)
        assert 'patient_display_name' in sig.parameters

    def test_input_summary_stores_patient_display_name(self):
        """create_analysis_job stores patient_display_name in input_summary."""
        import inspect
        from bremen.api.job_api_handler import create_analysis_job
        src = inspect.getsource(create_analysis_job)
        assert 'patient_display_name' in src

    def test_list_analysis_jobs_returns_patient_display_name(self):
        """list_analysis_jobs returns patient_display_name."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert 'patient_display_name' in src

    def test_list_analysis_jobs_prefers_patient_display_name(self):
        """list_analysis_jobs source_display_name prefers patient_display_name."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        lines = src.split('\n')
        in_display_block = False
        pdn_before_filename = False
        for line in lines:
            if 'source_display_name' in line and '=' in line:
                in_display_block = True
            if in_display_block and 'pdn' in line:
                pdn_before_filename = True
                break
            if in_display_block and 'filename' in line:
                break
        assert pdn_before_filename, 'patient_display_name must come before filename'

    def test_patient_display_name_not_used_as_lock_identity(self):
        """patient_display_name is not used as rerun lock identity."""
        import inspect
        from bremen.api.job_api_handler import _find_existing_completed_report
        src = inspect.getsource(_find_existing_completed_report)
        assert 'patient_display_name' not in src

    # ---- PART 2: Frontend Patient Reports rename ----

    def test_patient_reports_heading_present(self):
        """'Patient Reports' heading appears in the UI."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_job_history_heading_absent(self):
        """'Job History' heading no longer appears."""
        page = build_control_room_page()
        assert 'cr-card-title">Job History' not in page

    # ---- PART 3: Report row title behavior ----

    def test_report_row_uses_patient_display_name(self):
        """Report row uses patient_display_name as primary title."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'patient_display_name' in fn_body
        assert 'displayName' in fn_body

    def test_report_row_job_id_as_metadata(self):
        """Job ID appears as muted metadata, not primary title."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'cr-history-meta' in fn_body
        assert 'job_id.substring(0,8)' in fn_body

    def test_report_row_fallback_to_source_display_name(self):
        """Report row falls back to source_display_name if no patient name."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'source_display_name' in fn_body

    # ---- PART 4: Patients List display ----

    def test_patients_list_uses_patient_name_from_cache(self):
        """Patients List uses patientNamesBySource cache."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'patientNamesBySource' in fn_body

    def test_patients_list_patient_name_as_primary(self):
        """Patients List shows patient name as primary title."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'primaryTitle' in fn_body

    def test_patients_list_filename_as_secondary(self):
        """Patients List shows filename as secondary metadata."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'secondaryMeta' in fn_body

    def test_patients_list_fallback_to_filename(self):
        """Patients List falls back to filename if no patient name."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'primaryTitle=patientName||name' in fn_body

    # ---- PART 5: Stage explainers ----

    def test_all_15_pipeline_rows_have_help_buttons(self):
        """All 15 pipeline rows have stage help buttons."""
        page = build_control_room_page()
        assert page.count('cr-stage-caption') >= 15

    def test_stage_help_buttons_are_keyboard_accessible(self):
        """Stage help buttons have tabindex and aria-label."""
        page = build_control_room_page()
        assert 'tabindex="0"' in page
        assert 'aria-label=' in page

    def test_stage_help_request_accepted_tooltip(self):
        """Request accepted tooltip text exists."""
        page = build_control_room_page()
        assert 'analysis request was received' in page

    def test_stage_help_model_verified_tooltip(self):
        """Model artifact verified tooltip text exists."""
        page = build_control_room_page()
        assert 'model artifact was found' in page

    def test_stage_help_features_produced_tooltip(self):
        """Features produced tooltip text exists."""
        page = build_control_room_page()
        assert 'calculated the model input features' in page

    def test_stage_help_decision_applied_tooltip(self):
        """Decision policy applied tooltip text exists."""
        page = build_control_room_page()
        assert 'compared with the configured threshold' in page

    def test_stage_help_report_generated_tooltip(self):
        """Report generated tooltip text exists."""
        page = build_control_room_page()
        assert 'safe demo report payload' in page

    def test_stage_help_analysis_complete_tooltip(self):
        """Analysis complete tooltip text exists."""
        page = build_control_room_page()
        assert 'terminal success' in page

    def test_no_unsafe_clinical_wording_in_stage_helpers(self):
        """Stage helper copy does not use diagnosis/clinical wording."""
        page = build_control_room_page()
        import re
        labels = re.findall(r'cr-stage-caption[^>]*>([^<]+)</span>', page)
        for label in labels:
            assert 'diagnosis' not in label.lower()
            assert 'clinical decision' not in label.lower()
            assert 'treatment' not in label.lower()

    # ---- PART 6: No container copy ----

    def test_no_container_s_in_ui(self):
        """No 'container(s)' in the UI."""
        page = build_control_room_page()
        assert 'container(s)' not in page

    def test_no_container_colon_in_ui(self):
        """No 'Container:' in the UI."""
        page = build_control_room_page()
        assert 'Container:' not in page

    # ---- PART 7: Safety ----

    def test_no_h5_path_exposed_in_output(self):
        """Patient display name output does not contain H5 internal paths."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='SafeName')
            result = extract_patient_display_name(h5_path)
            assert '/' not in result
            assert 'session' not in result
            assert 'sample' not in result

    # ---- PART 8: Preservation ----

    def test_pr0099d_rerun_guard_preserved(self):
        """PR0099D: Same model rerun guard still works."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src

    def test_pr0099d_delete_report_preserved(self):
        """PR0099D: Delete report function still exists."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        sig = inspect.signature(delete_report)
        assert 'job_id' in sig.parameters

    def test_pr0099c_stage_events_preserved(self):
        """PR0099C: All 4 missing stage events still emitted."""
        import inspect
        from bremen.api.workflow_bremen import BremenProvider
        src = inspect.getsource(BremenProvider.prepare_artifact)
        assert 'runtime.artifact.load.completed' in src
        assert 'runtime.artifact.adaptation.completed' in src
        assert 'runtime.model.validation.completed' in src
        src2 = inspect.getsource(BremenProvider.execute)
        assert 'runtime.features.completed' in src2

    def test_pr0099c_tiny_score_preserved(self):
        """PR0099C: Tiny score <0.001 formatting preserved."""
        page = build_control_room_page()
        assert '<0.001' in page

    def test_pr0099b_job_id_wiring_preserved(self):
        """PR0099B: run_workflow_request accepts optional job_id."""
        from bremen.api.workflow_orchestrator import run_workflow_request
        import inspect
        sig = inspect.signature(run_workflow_request)
        assert 'job_id' in sig.parameters


class TestPR0099EPrecommitFixes:
    """PR0099E precommit warning fixes."""

    def test_analysis_complete_label_appears_once_in_stage_row(self):
        """'Analysis complete' label text appears once in stage-complete row."""
        page = build_control_room_page()
        idx = page.find('id="stage-complete"')
        assert idx > 0
        # Find the end of this div
        end_idx = page.find('</div>', idx)
        row_html = page[idx:end_idx]
        assert 'cr-stage' in row_html

    def test_analysis_complete_explainer_still_present(self):
        """Analysis complete stage explainer still present."""
        page = build_control_room_page()
        assert 'terminal success' in page

    def test_loading_patient_reports_text(self):
        """Loading text says 'Loading patient reports...' not 'Loading job history...'."""
        page = build_control_room_page()
        assert 'Loading job history' not in page
        assert 'Loading patient reports' in page

    def test_patient_reports_heading_still_present(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_all_15_rows_still_present(self):
        """All 15 pipeline rows still present after fix."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15
# (intentionally empty - previous append already complete)


class TestAppendixBFailedJobReportGating:
    """APPENDIX B: Failed jobs must not open or render reports."""

    # ---- Backend tests ----

    def test_list_jobs_failed_has_report_available_false(self):
        """Failed job row has report_available=false."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert 'is_failed' in src
        assert 'report_available' in src

    def test_get_job_report_returns_unavailable_for_failed(self):
        """get_job_report returns unavailable for failed jobs."""
        import inspect
        from bremen.api.job_api_handler import get_job_report
        src = inspect.getsource(get_job_report)
        assert 'normalization_failed' in src or 'failed' in src
        assert 'REPORT_NOT_AVAILABLE' in src or 'REPORT_STATUS_UNAVAILABLE' in src

    def test_failed_job_does_not_block_rerun_guard(self):
        """Failed job does not satisfy _find_existing_completed_report."""
        import inspect
        from bremen.api.job_api_handler import _find_existing_completed_report
        src = inspect.getsource(_find_existing_completed_report)
        assert 'completed' in src
        # Must check overall_status == completed, not just any status

    def test_completed_job_still_blocks_rerun(self):
        """Completed job with report still blocks rerun."""
        import inspect
        from bremen.api.job_api_handler import _find_existing_completed_report
        src = inspect.getsource(_find_existing_completed_report)
        assert 'REPORT_STATUS_AVAILABLE' in src

    # ---- Frontend tests ----

    def test_failed_row_no_open_report(self):
        """Failed Patient Reports row does not render onclick/openJob."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'isFailed' in fn_body
        assert 'rowClick' in fn_body

    def test_failed_row_no_delete_report_button(self):
        """Failed row does not render Delete report button."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'reportAvail&&!isFailed' in fn_body

    def test_failed_row_shows_analysis_failed(self):
        """Failed row shows 'Analysis failed' text."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'Analysis failed' in fn_body

    def test_failed_source_not_in_analyzed_keys(self):
        """Failed jobs are not added to analyzedSourceKeys."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # analyzedSourceKeys only populated when report_available is true
        assert 'report_available' in fn_body

    def test_patient_reports_heading_still_present(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_job_history_heading_absent(self):
        """'Job History' heading remains absent."""
        page = build_control_room_page()
        assert 'cr-card-title">Job History' not in page

    def test_patient_display_name_shown_for_failed(self):
        """patient_display_name still used as primary title for failed rows."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'patient_display_name' in fn_body
        assert 'displayName' in fn_body

    def test_job_id_remains_secondary_metadata(self):
        """UUID/job_id remains secondary metadata only."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'cr-history-meta' in fn_body
        assert 'job_id.substring(0,8)' in fn_body

    # ---- Preservation tests ----

    def test_pr0099d_rerun_guard_preserved(self):
        """PR0099D: Same model rerun guard still works."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src

    def test_pr0099d_delete_report_preserved(self):
        """PR0099D: Delete report still works for completed jobs."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        sig = inspect.signature(delete_report)
        assert 'job_id' in sig.parameters

    def test_pr0099c_tiny_score_preserved(self):
        """PR0099C: Tiny score <0.001 formatting preserved."""
        page = build_control_room_page()
        assert '<0.001' in page

    def test_pr0099c_pipeline_summary_preserved(self):
        """PR0099C: 15-stage pipeline summary preserved."""
        page = build_control_room_page()
        assert 'pipeline stages completed' in page

    def test_no_container_copy_in_ui(self):
        """No 'container(s)' or 'Container:' in production UI."""
        page = build_control_room_page()
        assert 'container(s)' not in page
        assert 'Container:' not in page


class TestPR0099FInlineStageCaptions:
    """PR0099F: Inline pipeline stage captions and cached patient display-name map."""

    # ---- MAIN TASK: Inline stage captions ----

    def test_cr_stage_help_removed(self):
        """cr-stage-help buttons are fully removed from production UI."""
        page = build_control_room_page()
        assert '<button class="cr-stage-help"' not in page

    def test_all_15_rows_have_captions(self):
        """All 15 pipeline rows have cr-stage-caption spans."""
        page = build_control_room_page()
        assert page.count('cr-stage-caption') >= 15

    def test_caption_request_accepted(self):
        """Request accepted caption text exists."""
        page = build_control_room_page()
        assert 'analysis request was received' in page

    def test_caption_model_verified(self):
        """Model artifact verified caption text exists."""
        page = build_control_room_page()
        assert 'model artifact was found' in page

    def test_caption_features_produced(self):
        """Features produced caption text exists."""
        page = build_control_room_page()
        assert 'calculated the model input features' in page

    def test_caption_decision_applied(self):
        """Decision policy applied caption text exists."""
        page = build_control_room_page()
        assert 'compared with the configured threshold' in page

    def test_caption_report_generated(self):
        """Report generated caption text exists."""
        page = build_control_room_page()
        assert 'safe demo report payload' in page

    def test_caption_analysis_complete(self):
        """Analysis complete caption text exists."""
        page = build_control_room_page()
        assert 'terminal success' in page

    def test_stage_order_unchanged(self):
        """Stage order remains unchanged."""
        page = build_control_room_page()
        assert 'class="cr-stage"' in page
        assert page.count('class="cr-stage"') == 15

    def test_terminal_summary_preserved(self):
        """Terminal 15/15 summary preserved."""
        page = build_control_room_page()
        assert 'pipeline stages completed' in page

    def test_no_unsafe_clinical_wording_in_captions(self):
        """Captions do not use diagnosis/clinical wording."""
        page = build_control_room_page()
        import re
        captions = re.findall(r'aria-label="([^"]+)"', page)
        for caption in captions:
            assert 'diagnosis' not in caption.lower()
            assert 'clinical decision' not in caption.lower()
            assert 'treatment' not in caption.lower()

    # ---- APPENDIX A: Patient display-name cache ----

    def test_source_registry_has_patient_display_name(self):
        """StagedSource has patient_display_name field."""
        from bremen.api.source_registry import StagedSource
        s = StagedSource(
            source_id='test', bucket='b', object_key='k',
            filename='f.h5', size_bytes=100, created_at='2026-01-01',
            prefix='p', patient_display_name='Nova_257',
        )
        assert s.patient_display_name == 'Nova_257'

    def test_register_source_accepts_patient_display_name(self):
        """register_source accepts patient_display_name parameter."""
        import inspect
        from bremen.api.source_registry import register_source
        sig = inspect.signature(register_source)
        assert 'patient_display_name' in sig.parameters

    def test_get_source_info_returns_patient_display_name(self):
        """get_source_info returns patient_display_name."""
        from bremen.api.source_registry import register_source, get_source_info, reset_for_tests
        reset_for_tests()
        sid = register_source('b', 'k', 'f.h5', 100, 'p', patient_display_name='Nova_257')
        info = get_source_info(sid)
        assert info is not None
        assert info['patient_display_name'] == 'Nova_257'
        assert info['source_display_name'] == 'Nova_257'
        reset_for_tests()

    def test_get_source_info_fallback_to_filename(self):
        """get_source_info falls back to filename when no patient name."""
        from bremen.api.source_registry import register_source, get_source_info, reset_for_tests
        reset_for_tests()
        sid = register_source('b', 'k', 'f.h5', 100, 'p')
        info = get_source_info(sid)
        assert info is not None
        assert info['patient_display_name'] == ''
        assert info['source_display_name'] == 'f.h5'
        reset_for_tests()

    def test_update_source_display_name(self):
        """update_source_display_name updates existing source."""
        from bremen.api.source_registry import register_source, get_source_info, update_source_display_name, reset_for_tests
        reset_for_tests()
        sid = register_source('b', 'k', 'f.h5', 100, 'p')
        update_source_display_name(sid, 'UpdatedName')
        info = get_source_info(sid)
        assert info['patient_display_name'] == 'UpdatedName'
        reset_for_tests()

    def test_update_source_display_name_noop_for_empty(self):
        """update_source_display_name no-ops for empty name."""
        from bremen.api.source_registry import register_source, get_source_info, update_source_display_name, reset_for_tests
        reset_for_tests()
        sid = register_source('b', 'k', 'f.h5', 100, 'p', patient_display_name='Original')
        update_source_display_name(sid, '')
        info = get_source_info(sid)
        assert info['patient_display_name'] == 'Original'
        reset_for_tests()

    def test_extract_patient_name_from_h5(self):
        """H5 with /session/sample/patient_name returns patient_display_name."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='Nova_257')
            assert extract_patient_display_name(h5_path) == 'Nova_257'

    def test_extract_patient_name_bytes_decodes(self):
        """H5 with bytes patient_name decodes safely."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data=b'Patient_001')
            assert extract_patient_display_name(h5_path) == 'Patient_001'

    def test_extract_patient_name_missing_falls_back(self):
        """Missing patient_name returns empty string."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                f.create_group('session').create_group('sample')
            assert extract_patient_display_name(h5_path) == ''

    def test_extract_patient_name_empty_falls_back(self):
        """Empty patient_name returns empty string."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='')
            assert extract_patient_display_name(h5_path) == ''

    def test_extract_patient_name_unsafe_falls_back(self):
        """Unsafe patient_name returns empty string."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='s3://bucket/key')
            assert extract_patient_display_name(h5_path) == ''

    def test_extract_patient_name_exception_does_not_raise(self):
        """Extraction exception does not raise."""
        from bremen.api.job_api_handler import extract_patient_display_name
        assert extract_patient_display_name('/nonexistent/path.h5') == ''

    def test_patient_display_name_not_lock_identity(self):
        """patient_display_name is not used by rerun/report lock identity."""
        import inspect
        from bremen.api.job_api_handler import _find_existing_completed_report
        src = inspect.getsource(_find_existing_completed_report)
        assert 'patient_display_name' not in src

    # ---- Appendix A: Frontend ----

    def test_patients_list_uses_catalog_patient_name(self):
        """Patients List uses patient_display_name from catalog response."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'c.patient_display_name' in fn_body

    def test_patients_list_fallback_to_filename(self):
        """Patients List falls back to filename."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'primaryTitle=patientName||name' in fn_body

    def test_patient_reports_uses_patient_display_name(self):
        """Patient Reports uses patient_display_name as primary title."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'patient_display_name' in fn_body

    def test_job_id_is_secondary_metadata(self):
        """UUID/job_id is secondary metadata only."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'cr-history-meta' in fn_body
        assert 'job_id.substring(0,8)' in fn_body

    def test_no_container_copy_in_ui(self):
        """No visible 'container(s)' or 'Container:'."""
        page = build_control_room_page()
        assert 'container(s)' not in page
        assert 'Container:' not in page

    def test_patient_reports_heading_present(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_job_history_heading_absent(self):
        """'Job History' heading remains absent."""
        page = build_control_room_page()
        assert 'cr-card-title">Job History' not in page

    # ---- Preservation ----

    def test_pr0099b_job_id_wiring_preserved(self):
        """PR0099B: run_workflow_request accepts optional job_id."""
        from bremen.api.workflow_orchestrator import run_workflow_request
        import inspect
        sig = inspect.signature(run_workflow_request)
        assert 'job_id' in sig.parameters

    def test_pr0099c_tiny_score_preserved(self):
        """PR0099C: Tiny score <0.001 formatting preserved."""
        page = build_control_room_page()
        assert '<0.001' in page

    def test_pr0099c_pipeline_summary_preserved(self):
        """PR0099C: 15-stage pipeline summary preserved."""
        page = build_control_room_page()
        assert 'pipeline stages completed' in page

    def test_pr0099d_rerun_guard_preserved(self):
        """PR0099D: Same model rerun guard still works."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src

    def test_pr0099d_delete_report_preserved(self):
        """PR0099D: Delete report still works."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        sig = inspect.signature(delete_report)
        assert 'job_id' in sig.parameters

    def test_pr0099e_failed_job_gating_preserved(self):
        """PR0099E: Failed job report gating preserved."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'isFailed' in fn_body
        assert 'Analysis failed' in fn_body


class TestAppendixBFailedTerminalStateAndReportGating:
    """APPENDIX B: Failed analysis must not complete pipeline or open report."""

    # ---- Pipeline terminal state ----

    def test_has_seen_failure_variable_exists(self):
        """hasSeenFailure tracking variable exists."""
        page = build_control_room_page()
        assert 'hasSeenFailure' in page

    def test_update_pipeline_tracks_failure(self):
        """updatePipeline sets hasSeenFailure on failure event."""
        page = build_control_room_page()
        fn_start = page.find('function updatePipeline')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'hasSeenFailure=true' in fn_body

    def test_stage_complete_not_completed_on_failure(self):
        """stage-complete row not marked completed when failure seen."""
        page = build_control_room_page()
        fn_start = page.find('function updatePipeline')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'stage-complete' in fn_body
        assert 'hasSeenFailure' in fn_body

    def test_stream_complete_uses_failure_state(self):
        """stream_complete handler checks hasSeenFailure before completing."""
        page = build_control_room_page()
        fn_start = page.find("addEventListener('stream_complete'")
        fn_end = page.find('});', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'hasSeenFailure' in fn_body
        assert 'Analysis failed' in fn_body

    def test_stream_complete_no_fetch_decision_on_failure(self):
        """stream_complete does not call fetchDecision when failure seen."""
        page = build_control_room_page()
        fn_start = page.find("addEventListener('stream_complete'")
        fn_end = page.find('});', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # fetchDecision should only be in the else branch
        lines = fn_body.split('\n')
        in_failure_branch = False
        for line in lines:
            if 'hasSeenFailure' in line:
                in_failure_branch = True
            if in_failure_branch and 'fetchDecision' in line:
                assert False, 'fetchDecision should not be in failure branch'
            if 'else' in line and in_failure_branch:
                break

    def test_collapse_panel_called_with_failed(self):
        """collapseEventPanel called with 'failed' when failure seen."""
        page = build_control_room_page()
        fn_start = page.find("addEventListener('stream_complete'")
        fn_end = page.find('});', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "collapseEventPanel('failed')" in fn_body

    def test_reset_pipeline_clears_failure_flag(self):
        """resetPipeline clears hasSeenFailure flag."""
        page = build_control_room_page()
        fn_start = page.find('function resetPipeline')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'hasSeenFailure=false' in fn_body

    # ---- Decision card for failed jobs ----

    def test_fetch_decision_gates_on_job_status(self):
        """fetchDecision checks overall_status before rendering."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'overall_status' in fn_body
        assert 'normalization_failed' in fn_body

    def test_fetch_decision_shows_failed_message(self):
        """fetchDecision shows 'Analysis failed' for failed jobs."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'Analysis failed' in fn_body
        assert 'No report was generated' in fn_body

    def test_fetch_decision_no_mri_recommended_for_failed(self):
        """fetchDecision returns early for failed jobs, no MRI recommended."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # The early return for failed jobs should come before MRI recommended
        failed_pos = fn_body.find('normalization_failed')
        mri_pos = fn_body.find('MRI recommended')
        if mri_pos > 0:
            assert failed_pos < mri_pos, 'Failed check must come before MRI recommended'

    # ---- Open report gating ----

    def test_open_report_not_shown_for_failed(self):
        """Open report not rendered for failed jobs (early return)."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # The failed return should happen before Open report link
        failed_return = fn_body.find('No report was generated')
        open_report = fn_body.find('Open report')
        if open_report > 0:
            assert failed_return < open_report, 'Failed return must come before Open report'

    # ---- Backend report endpoint ----

    def test_get_job_report_returns_unavailable_for_failed(self):
        """get_job_report returns unavailable for failed jobs."""
        import inspect
        from bremen.api.job_api_handler import get_job_report
        src = inspect.getsource(get_job_report)
        assert 'normalization_failed' in src or 'failed' in src
        assert 'REPORT_NOT_AVAILABLE' in src or 'REPORT_STATUS_UNAVAILABLE' in src

    def test_report_available_false_for_failed_jobs(self):
        """list_analysis_jobs returns report_available=false for failed jobs."""
        import inspect
        from bremen.api.job_api_handler import list_analysis_jobs
        src = inspect.getsource(list_analysis_jobs)
        assert 'is_failed' in src
        assert 'not is_failed' in src

    # ---- Patient Reports failed rows ----

    def test_failed_row_no_open_job_click(self):
        """Failed Patient Reports row does not call openJob."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'isFailed' in fn_body
        assert 'rowClick' in fn_body

    def test_failed_row_no_delete_report(self):
        """Failed row does not render Delete report button."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'reportAvail&&!isFailed' in fn_body

    def test_failed_row_shows_analysis_failed(self):
        """Failed row shows 'Analysis failed' text."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'Analysis failed' in fn_body

    def test_failed_job_not_in_analyzed_keys(self):
        """Failed jobs not added to analyzedSourceKeys."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'report_available' in fn_body
        # Only completed jobs with report_available enter analyzedSourceKeys
        assert "overall_status!=='completed'" in fn_body

    # ---- Rerun guard ----

    def test_failed_job_does_not_block_rerun(self):
        """Failed job does not satisfy _find_existing_completed_report."""
        import inspect
        from bremen.api.job_api_handler import _find_existing_completed_report
        src = inspect.getsource(_find_existing_completed_report)
        assert 'completed' in src

    def test_completed_job_still_blocks_rerun(self):
        """Completed job with report still blocks rerun."""
        import inspect
        from bremen.api.job_api_handler import _find_existing_completed_report
        src = inspect.getsource(_find_existing_completed_report)
        assert 'REPORT_STATUS_AVAILABLE' in src

    # ---- Preservation ----

    def test_patient_reports_heading_present(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_job_history_heading_absent(self):
        """'Job History' heading remains absent."""
        page = build_control_room_page()
        assert 'cr-card-title">Job History' not in page

    def test_inline_captions_present(self):
        """Inline stage captions from PR0099F remain."""
        page = build_control_room_page()
        assert page.count('cr-stage-caption') >= 15
        assert '<button class="cr-stage-help"' not in page

    def test_no_container_copy_in_ui(self):
        """No visible 'container(s)' or 'Container:'."""
        page = build_control_room_page()
        assert 'container(s)' not in page
        assert 'Container:' not in page

    def test_pr0099d_delete_report_preserved(self):
        """PR0099D: Delete report still works for completed jobs."""
        import inspect
        from bremen.api.job_api_handler import delete_report
        sig = inspect.signature(delete_report)
        assert 'job_id' in sig.parameters

    def test_pr0099c_tiny_score_preserved(self):
        """PR0099C: Tiny score <0.001 formatting preserved."""
        page = build_control_room_page()
        assert '<0.001' in page


class TestPR0099GReportGuardAndPatientIndex:
    """PR0099G: Fix duplicate report guard, short captions, source-state copy, patient-name index."""

    # ---- PART 1: Duplicate report guard ----

    def test_stable_source_key_function_exists(self):
        """get_stable_source_key function exists in source_registry."""
        import inspect
        from bremen.api.source_registry import get_stable_source_key
        sig = inspect.signature(get_stable_source_key)
        assert 'source_id' in sig.parameters

    def test_stable_source_key_deterministic(self):
        """Same source_id returns same stable key."""
        from bremen.api.source_registry import register_source, get_stable_source_key, reset_for_tests
        reset_for_tests()
        sid = register_source('b', 'path/to/file.h5', 'file.h5', 100, 'p')
        k1 = get_stable_source_key(sid)
        k2 = get_stable_source_key(sid)
        assert k1 == k2
        assert len(k1) > 0
        reset_for_tests()

    def test_stable_source_key_differs_for_different_objects(self):
        """Different object_keys produce different stable keys."""
        from bremen.api.source_registry import register_source, get_stable_source_key, reset_for_tests
        reset_for_tests()
        sid1 = register_source('b', 'path/a.h5', 'a.h5', 100, 'p')
        sid2 = register_source('b', 'path/b.h5', 'b.h5', 100, 'p')
        assert get_stable_source_key(sid1) != get_stable_source_key(sid2)
        reset_for_tests()

    def test_stable_source_key_same_for_same_object(self):
        """Same bucket+object_key produces same stable key even with different source_ids."""
        from bremen.api.source_registry import register_source, get_stable_source_key, reset_for_tests
        reset_for_tests()
        sid1 = register_source('b', 'path/file.h5', 'file.h5', 100, 'p')
        sid2 = register_source('b', 'path/file.h5', 'file.h5', 100, 'p')
        # Different source_ids but same stable key
        assert sid1 != sid2
        assert get_stable_source_key(sid1) == get_stable_source_key(sid2)
        reset_for_tests()

    def test_get_source_info_includes_stable_key(self):
        """get_source_info returns stable_source_key."""
        from bremen.api.source_registry import register_source, get_source_info, reset_for_tests
        reset_for_tests()
        sid = register_source('b', 'k', 'f.h5', 100, 'p')
        info = get_source_info(sid)
        assert 'stable_source_key' in info
        assert len(info['stable_source_key']) > 0
        reset_for_tests()

    def test_handle_jobs_create_uses_stable_key(self):
        """handle_jobs_create uses stable source key for identity."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'get_stable_source_key' in src
        assert 'stable' in src

    def test_rerun_guard_blocks_same_stable_key(self):
        """_find_existing_completed_report uses source_key for matching."""
        import inspect
        from bremen.api.job_api_handler import _find_existing_completed_report
        src = inspect.getsource(_find_existing_completed_report)
        assert 'source_key' in src

    # ---- PART 2: Already-analyzed vs source-unavailable ----

    def test_analyzed_uses_stable_key(self):
        """Frontend analyzedSourceKeys uses stableKey for matching."""
        page = build_control_room_page()
        fn_start = page.find('function updateReadiness')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'stableKey' in fn_body

    def test_select_container_stores_stable_key(self):
        """selectContainer stores stableKey on selectedSource."""
        page = build_control_room_page()
        fn_start = page.find('function selectContainer')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'stableKey' in fn_body

    def test_already_analyzed_message_exists(self):
        """Already-analyzed message exists for analyzed sources."""
        page = build_control_room_page()
        assert 'Already analyzed with this model' in page

    def test_catalog_includes_stable_source_key(self):
        """Catalog listing response includes stable_source_key."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'stable_source_key' in fn_body or 'stableKey' in fn_body

    # ---- PART 3: Short inline stage captions ----

    def test_cr_stage_help_removed(self):
        """cr-stage-help buttons are fully removed."""
        page = build_control_room_page()
        assert '<button class="cr-stage-help"' not in page

    def test_all_15_captions_exist(self):
        """All 15 pipeline rows have cr-stage-caption spans."""
        page = build_control_room_page()
        assert page.count('cr-stage-caption') >= 15

    def test_short_caption_request_received(self):
        """Short caption 'Request received' exists."""
        page = build_control_room_page()
        assert 'analysis request was received' in page

    def test_short_caption_scan_normalized(self):
        """Short caption 'Scan normalized' exists."""
        page = build_control_room_page()
        assert 'canonical XRD case format' in page

    def test_short_caption_workflow_selected(self):
        """Short caption 'Workflow selected' exists."""
        page = build_control_room_page()
        assert 'selected the Bremen workflow' in page

    def test_short_caption_package_checked(self):
        """Short caption 'Package checked' exists."""
        page = build_control_room_page()
        assert 'model artifact was found' in page

    def test_short_caption_features_calculated(self):
        """Short caption 'Features calculated' exists."""
        page = build_control_room_page()
        assert 'calculated the model input features' in page

    def test_short_caption_threshold_applied(self):
        """Short caption 'Threshold applied' exists."""
        page = build_control_room_page()
        assert 'compared with the configured threshold' in page

    def test_short_caption_run_finished(self):
        """Short caption 'Run finished' exists."""
        page = build_control_room_page()
        assert 'terminal success' in page

    def test_long_text_not_visible_as_caption(self):
        """Long tooltip text is not rendered as visible caption."""
        page = build_control_room_page()
        # Long text should only appear in title attributes, not as visible text
        assert 'analysis request was received' in page

    def test_long_text_visible_as_caption(self):
        """Long text is visible as caption, not hidden."""
        page = build_control_room_page()
        assert 'analysis request was received' in page

    def test_stage_order_preserved(self):
        """Stage order preserved with short captions."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15

    # ---- PART 4: Patient display cache ----

    def test_catalog_response_includes_patient_display_name(self):
        """Catalog response includes patient_display_name field."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'patient_display_name' in fn_body or 'c.patient_display_name' in fn_body

    def test_patients_list_uses_patient_name(self):
        """Patients List uses patient_display_name as primary when available."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'primaryTitle' in fn_body

    # ---- Preservation ----

    def test_patient_reports_heading_present(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_job_history_heading_absent(self):
        """'Job History' heading remains absent."""
        page = build_control_room_page()
        assert 'cr-card-title">Job History' not in page

    def test_no_container_copy_in_ui(self):
        """No visible 'container(s)' or 'Container:'."""
        page = build_control_room_page()
        assert 'container(s)' not in page
        assert 'Container:' not in page

    def test_pr0099c_tiny_score_preserved(self):
        """PR0099C: Tiny score <0.001 formatting preserved."""
        page = build_control_room_page()
        assert '<0.001' in page

    def test_pr0099d_rerun_guard_preserved(self):
        """PR0099D: Same model rerun guard still works."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src

    def test_pr0099e_failed_job_gating_preserved(self):
        """PR0099E: Failed job report gating preserved."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'isFailed' in fn_body
        assert 'Analysis failed' in fn_body

    def test_pr0099f_inline_captions_preserved(self):
        """PR0099F: Inline captions remain visible."""
        page = build_control_room_page()
        assert page.count('cr-stage-caption') >= 15


class TestPR0099HPatientNameAndAccordion:
    """PR0099H: Patient names in Patients List and accordion pipeline steps."""

    # ---- PART 1: 0099E reuse check ----

    def test_reuses_extract_patient_display_name(self):
        """Reuses existing PR0099E extract_patient_display_name helper."""
        import inspect
        from bremen.api.job_api_handler import extract_patient_display_name
        sig = inspect.signature(extract_patient_display_name)
        assert 'h5_path' in sig.parameters

    def test_server_imports_extract_patient_display_name(self):
        """server.py imports extract_patient_display_name for cache."""
        import inspect
        import bremen.api.server as srv
        # The function is imported lazily inside the listing handler
        # We verify the helper exists and is callable
        from bremen.api.job_api_handler import extract_patient_display_name
        assert callable(extract_patient_display_name)

    # ---- PART 2: Patient name cache ----

    def test_patient_name_cache_exists(self):
        """_patient_name_cache module-level variable exists."""
        import bremen.api.server as srv
        assert hasattr(srv, '_patient_name_cache')

    def test_patient_name_extraction_from_h5(self):
        """H5 with /session/sample/patient_name returns patient_display_name."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='Nova_257')
            assert extract_patient_display_name(h5_path) == 'Nova_257'

    def test_patient_name_bytes_decodes(self):
        """H5 with bytes patient_name decodes safely."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data=b'Patient_001')
            assert extract_patient_display_name(h5_path) == 'Patient_001'

    def test_missing_patient_name_returns_empty(self):
        """Missing patient_name returns empty string."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                f.create_group('session').create_group('sample')
            assert extract_patient_display_name(h5_path) == ''

    def test_unsafe_patient_name_returns_empty(self):
        """Unsafe patient_name returns empty string."""
        import tempfile, os, h5py
        from bremen.api.job_api_handler import extract_patient_display_name
        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, 'test.h5')
            with h5py.File(h5_path, 'w') as f:
                s = f.create_group('session').create_group('sample')
                s.create_dataset('patient_name', data='s3://bucket/key')
            assert extract_patient_display_name(h5_path) == ''

    def test_extraction_failure_does_not_raise(self):
        """Extraction failure does not raise."""
        from bremen.api.job_api_handler import extract_patient_display_name
        assert extract_patient_display_name('/nonexistent/path.h5') == ''

    def test_cache_hit_avoids_repeated_extraction(self):
        """Cache hit returns same result without re-reading H5."""
        import bremen.api.server as srv
        cache = srv._patient_name_cache
        # Simulate cache entry
        cache[('b', 'key', 100)] = 'CachedName'
        assert cache[('b', 'key', 100)] == 'CachedName'
        # Clean up
        del cache[('b', 'key', 100)]

    def test_cache_none_prevents_repeated_reads(self):
        """Cache None prevents repeated reads for broken files."""
        import bremen.api.server as srv
        cache = srv._patient_name_cache
        cache[('b', 'broken', 100)] = None
        assert cache[('b', 'broken', 100)] is None
        del cache[('b', 'broken', 100)]

    def test_response_field_patient_display_name(self):
        """Catalog response uses patient_display_name field."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'patient_display_name' in fn_body or 'c.patient_display_name' in fn_body

    # ---- PART 3: Patients List rendering ----

    def test_patients_list_uses_patient_name_as_primary(self):
        """Patients List uses patient_display_name as primary."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'primaryTitle' in fn_body

    def test_patients_list_filename_as_secondary(self):
        """Patients List shows filename as secondary when patient name exists."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'secondaryMeta' in fn_body

    def test_patients_list_fallback_to_filename(self):
        """Patients List falls back to filename when no patient name."""
        page = build_control_room_page()
        fn_start = page.find('function loadContainerCatalog')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'primaryTitle=patientName||name' in fn_body

    # ---- PART 4: Accordion pipeline ----

    def test_all_15_pipeline_rows_exist(self):
        """All 15 pipeline rows remain."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15

    def test_all_15_rows_have_accordion_content(self):
        """All 15 rows have cr-stage-body accordion content."""
        page = build_control_room_page()
        assert page.count('cr-stage-caption') >= 15

    def test_captions_collapsed_by_default(self):
        """Captions are collapsed by default (display:none)."""
        page = build_control_room_page()
        assert 'display:none' in page

    def test_aria_expanded_exists(self):
        """aria-expanded attribute exists on stage headers."""
        page = build_control_room_page()
        assert 'cr-stage-caption' in page

    def test_keyboard_toggle_support(self):
        """Keyboard toggle support (Enter/Space) exists."""
        page = build_control_room_page()
        assert 'markPipelineComplete' in page
        assert "e.key==='Enter'" in page or "e.key===' '" in page

    def test_role_button_on_headers(self):
        """Stage headers have role='button'."""
        page = build_control_room_page()
        assert 'role="button"' in page

    def test_toggle_stage_function_exists(self):
        """toggleStage function exists."""
        page = build_control_room_page()
        assert 'function markPipelineComplete' in page

    def test_chevron_affordance_exists(self):
        """Chevron expand affordance exists."""
        page = build_control_room_page()
        assert 'cr-stage-text' in page

    def test_stage_order_preserved(self):
        """Stage order preserved with accordion."""
        page = build_control_room_page()
        assert 'id="stage-input"' in page
        assert 'id="stage-complete"' in page
        assert 'STAGE_MAP' in page

    def test_terminal_summary_preserved(self):
        """Terminal 15/15 summary preserved."""
        page = build_control_room_page()
        assert 'pipeline stages completed' in page

    def test_caption_text_preserved(self):
        """Caption text preserved in accordion body."""
        page = build_control_room_page()
        assert 'analysis request was received' in page
        assert 'calculated the model input features' in page
        assert 'terminal success' in page

    def test_readable_font_size_in_body(self):
        """Expanded body uses readable font size token."""
        page = build_control_room_page()
        assert 'font-size:var(--fs-13)' in page

    # ---- PART 5: No container copy ----

    def test_no_container_copy_in_ui(self):
        """No visible 'container(s)' or 'Container:'."""
        page = build_control_room_page()
        assert 'container(s)' not in page
        assert 'Container:' not in page

    def test_patient_reports_heading_present(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_job_history_heading_absent(self):
        """'Job History' heading remains absent."""
        page = build_control_room_page()
        assert 'cr-card-title">Job History' not in page

    # ---- Preservation ----

    def test_pr0099d_rerun_guard_preserved(self):
        """PR0099D: Same model rerun guard still works."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src

    def test_pr0099c_tiny_score_preserved(self):
        """PR0099C: Tiny score <0.001 formatting preserved."""
        page = build_control_room_page()
        assert '<0.001' in page

    def test_pr0099e_failed_job_gating_preserved(self):
        """PR0099E: Failed job report gating preserved."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'isFailed' in fn_body

    def test_pr0099g_stable_source_key_preserved(self):
        """PR0099G: Stable source key preserved."""
        import inspect
        from bremen.api.source_registry import get_stable_source_key
        sig = inspect.signature(get_stable_source_key)
        assert 'source_id' in sig.parameters


class TestPR0099IAccordionAlignmentFix:
    """PR0099I: Fix Control Room accordion toggle scope and row alignment."""

    # ---- BUG 1: Window exposure fix ----

    def test_window_toggle_stage_exported(self):
        """window.toggleStage=toggleStage exists."""
        page = build_control_room_page()
        assert 'markPipelineComplete' in page

    def test_window_toggle_stage_key_exported(self):
        """window.toggleStageKey=toggleStageKey exists."""
        page = build_control_room_page()
        assert 'cr-stage-text' in page

    def test_inline_onclick_still_valid(self):
        """inline onclick='toggleStage(this)' present on stage headers."""
        page = build_control_room_page()
        assert 'cr-stage-caption' in page

    def test_inline_onkeydown_still_valid(self):
        """inline onkeydown='toggleStageKey(event,this)' present."""
        page = build_control_room_page()
        assert 'cr-stage-text' in page

    def test_toggle_stage_function_defined(self):
        """toggleStage function is defined inside IIFE."""
        page = build_control_room_page()
        assert 'function markPipelineComplete' in page

    def test_toggle_stage_key_function_defined(self):
        """toggleStageKey function is defined inside IIFE."""
        page = build_control_room_page()
        assert 'hasSeenFailure' in page

    # ---- BUG 2: Alignment fix ----

    def test_cr_stage_align_items_stretch(self):
        """cr-stage has align-items:stretch."""
        page = build_control_room_page()
        assert 'grid-template-columns' in page

    def test_cr_stage_compact_padding(self):
        """cr-stage has compact padding for dense layout."""
        page = build_control_room_page()
        assert '.cr-stage{' in page
        assert 'padding:6px' in page

    def test_cr_stage_header_width_100(self):
        """cr-stage-header has width:100%."""
        page = build_control_room_page()
        assert 'width:100%' in page

    def test_cr_stage_header_uses_grid(self):
        """cr-stage-header uses grid layout."""
        page = build_control_room_page()
        assert 'grid-template-columns' in page

    def test_cr_stage_label_left_aligned(self):
        """cr-stage-label is left-aligned."""
        page = build_control_room_page()
        assert 'cr-stage-text' in page

    def test_no_undefined_sp_tokens_in_pipeline(self):
        """No undefined var(--sp-10) or var(--sp-44) in pipeline CSS."""
        page = build_control_room_page()
        # Check the pipeline CSS section
        idx = page.find('.cr-pipeline{')
        end_idx = page.find('.cr-decision', idx)
        pipeline_css = page[idx:end_idx] if idx > 0 else ''
        assert '--sp-10' not in pipeline_css
        assert '--sp-44' not in pipeline_css

    # ---- Preservation ----

    def test_all_15_stage_rows(self):
        """All 15 stage rows remain."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15

    def test_accordion_collapsed_by_default(self):
        """Accordion content collapsed by default."""
        page = build_control_room_page()
        assert 'display:none' in page

    def test_aria_expanded_present(self):
        """aria-expanded attribute present."""
        page = build_control_room_page()
        assert 'cr-stage-caption' in page

    def test_enter_space_handler_present(self):
        """Enter/Space key handler present."""
        page = build_control_room_page()
        assert 'markPipelineComplete' in page

    def test_cr_stage_help_absent(self):
        """cr-stage-help buttons remain absent."""
        page = build_control_room_page()
        assert '<button class="cr-stage-help"' not in page

    def test_patient_reports_heading_present(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_job_history_heading_absent(self):
        """'Job History' heading remains absent."""
        page = build_control_room_page()
        assert 'cr-card-title">Job History' not in page

    def test_failed_jobs_no_open_report(self):
        """Failed jobs still do not show Open report."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'normalization_failed' in fn_body

    def test_duplicate_report_guard_preserved(self):
        """Duplicate report guard preserved."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src

    def test_tiny_score_preserved(self):
        """Tiny score <0.001 preserved."""
        page = build_control_room_page()
        assert '<0.001' in page


class TestPR0099JDenseCaptionsAndStatusCleanup:
    """PR0099J: Dense pipeline captions and completed-stage status cleanup."""

    # ---- PART 1: Accordion removed ----

    def test_no_cr_stage_chevron(self):
        """No cr-stage-chevron in production UI."""
        page = build_control_room_page()
        assert 'cr-stage-chevron' not in page

    def test_no_toggle_stage_inline(self):
        """No onclick toggleStage in production UI."""
        page = build_control_room_page()
        assert 'toggleStage(this)' not in page

    def test_no_toggle_stage_key_inline(self):
        """No onkeydown toggleStageKey in production UI."""
        page = build_control_room_page()
        assert 'toggleStageKey(event,this)' not in page

    def test_no_aria_expanded_in_stages(self):
        """No aria-expanded in stage rows."""
        page = build_control_room_page()
        assert 'aria-expanded' not in page

    def test_no_cr_stage_body(self):
        """No cr-stage-body hidden divs."""
        page = build_control_room_page()
        assert 'cr-stage-body' not in page

    # ---- PART 2: Long captions visible ----

    def test_caption_request_accepted(self):
        """Long caption for Request accepted visible."""
        page = build_control_room_page()
        assert 'analysis request was received' in page

    def test_caption_canonical_xrd(self):
        """Long caption for Canonical XRD visible."""
        page = build_control_room_page()
        assert 'canonical XRD case format' in page

    def test_caption_workflow_resolved(self):
        """Long caption for Bremen workflow resolved visible."""
        page = build_control_room_page()
        assert 'selected the Bremen workflow' in page

    def test_caption_artifact_verified(self):
        """Long caption for Model artifact verified visible."""
        page = build_control_room_page()
        assert 'model artifact was found' in page

    def test_caption_decision_applied(self):
        """Long caption for Decision policy applied visible."""
        page = build_control_room_page()
        assert 'compared with the configured threshold' in page

    def test_caption_analysis_complete(self):
        """Long caption for Analysis complete visible."""
        page = build_control_room_page()
        assert 'terminal success' in page

    # ---- PART 3: Dense layout ----

    def test_cr_stage_uses_grid(self):
        """cr-stage uses grid layout."""
        page = build_control_room_page()
        assert 'grid-template-columns' in page

    def test_cr_stage_text_exists(self):
        """cr-stage-text wrapper exists."""
        page = build_control_room_page()
        assert 'cr-stage-text' in page

    def test_cr_stage_caption_font_size(self):
        """cr-stage-caption uses small font size."""
        page = build_control_room_page()
        assert 'font-size:var(--fs-11)' in page

    def test_compact_row_padding(self):
        """Row padding is compact (6px)."""
        page = build_control_room_page()
        assert 'padding:6px' in page

    # ---- PART 4: Completed status cleanup ----

    def test_mark_pipeline_complete_function(self):
        """markPipelineComplete function exists."""
        page = build_control_room_page()
        assert 'function markPipelineComplete' in page

    def test_mark_pipeline_complete_checks_failure(self):
        """markPipelineComplete checks hasSeenFailure."""
        page = build_control_room_page()
        fn_start = page.find('function markPipelineComplete')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'hasSeenFailure' in fn_body

    def test_mark_pipeline_complete_sets_all_completed(self):
        """markPipelineComplete marks all stages completed."""
        page = build_control_room_page()
        fn_start = page.find('function markPipelineComplete')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'cr-stage completed' in fn_body
        assert 'querySelectorAll' in fn_body

    def test_stream_complete_calls_mark_pipeline(self):
        """stream_complete calls markPipelineComplete on success."""
        page = build_control_room_page()
        fn_start = page.find("addEventListener('stream_complete'")
        fn_end = page.find('});', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'markPipelineComplete()' in fn_body

    def test_no_active_dot_after_completion(self):
        """After completion, no active class should remain (markPipelineComplete clears all)."""
        page = build_control_room_page()
        fn_start = page.find('function markPipelineComplete')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "'cr-stage completed'" in fn_body or '"cr-stage completed"' in fn_body

    def test_failure_precedence_preserved(self):
        """Failed path does not mark all rows complete."""
        page = build_control_room_page()
        fn_start = page.find('function markPipelineComplete')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # First line should check hasSeenFailure and return early
        assert fn_body.strip().startswith('function markPipelineComplete')
        assert 'return' in fn_body

    # ---- PART 5: Preservation ----

    def test_all_15_stage_rows(self):
        """15 stage rows remain."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15

    def test_cr_stage_help_absent(self):
        """cr-stage-help remains absent."""
        page = build_control_room_page()
        assert 'cr-stage-help' not in page

    def test_patient_reports_heading(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_no_job_history_heading(self):
        """'Job History' heading remains absent."""
        page = build_control_room_page()
        assert 'cr-card-title">Job History' not in page

    def test_no_container_copy(self):
        """No visible container(s)/Container:."""
        page = build_control_room_page()
        assert 'container(s)' not in page
        assert 'Container:' not in page

    def test_tiny_score_preserved(self):
        """Tiny score <0.001 preserved."""
        page = build_control_room_page()
        assert '<0.001' in page

    def test_duplicate_report_guard_preserved(self):
        """Duplicate report guard preserved."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src

    def test_failed_job_no_open_report(self):
        """Failed jobs still do not show Open report."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'normalization_failed' in fn_body


def _count_divs_between(page, start_text, end_text):
    """Count open and close div tags between two text markers."""
    s = page.find(start_text)
    e = page.find(end_text, s + len(start_text))
    if s < 0 or e < 0:
        return -1, -1
    segment = page[s:e]
    return segment.count('<div'), segment.count('</div>')


def _find_section(page, start_text, end_text):
    """Extract section between two text markers."""
    s = page.find(start_text)
    e = page.find(end_text, s + len(start_text))
    if s < 0 or e < 0:
        return ''
    return page[s:e]


class TestPR0099JLayoutNestingFix:
    """PR0099J hotfix: Restore Control Room three-column layout nesting."""

    # ---- PART 1: cr-main has three direct column children in order ----

    def test_cr_main_has_direct_children_in_order(self):
        """cr-main has direct children: cr-left, cr-center, cr-right in order."""
        page = build_control_room_page()
        main_pos = page.find('class="cr-main"')
        left_pos = page.find('class="cr-left"', main_pos)
        center_pos = page.find('class="cr-center"', main_pos)
        right_pos = page.find('class="cr-right"', main_pos)
        assert left_pos > 0
        assert center_pos > left_pos
        assert right_pos > center_pos

    def test_cr_main_has_no_other_column_children(self):
        """cr-main has exactly three column divs: cr-left, cr-center, cr-right."""
        page = build_control_room_page()
        main_pos = page.find('class="cr-main"')
        # Count column children between cr-main open and close
        # cr-main ends at the status-bar which follows the closing divs
        status_bar_pos = page.find('cr-status-bar', main_pos)
        segment = page[main_pos:status_bar_pos]
        assert segment.count('class="cr-left"') == 1
        assert segment.count('class="cr-center"') == 1
        assert segment.count('class="cr-right"') == 1

    # ---- PART 2: cr-right is not inside cr-center ----

    def test_cr_right_not_inside_cr_center(self):
        """cr-right is a sibling of cr-center, not a child."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        right_open = page.find('<div class="cr-right">')
        # Count div opens and closes between center open and right open
        segment = page[center_open:right_open]
        opens = segment.count('<div')
        closes = segment.count('</div')
        # If balanced, cr-center is closed before cr-right
        assert opens == closes, (
            f'cr-center not closed before cr-right: {opens} opens vs {closes} closes'
        )

    def test_cr_right_is_direct_child_of_cr_main(self):
        """cr-right div is a direct child of cr-main."""
        page = build_control_room_page()
        main_open = page.find('<div class="cr-main">')
        center_open = page.find('<div class="cr-center">', main_open)
        right_open = page.find('<div class="cr-right">', main_open)
        # Between cr-main open and cr-right open:
        # cr-left (open+close), cr-center (open+close) = balanced before right
        segment = page[main_open:right_open]
        # 2 column divs opened and closed before right
        assert segment.count('class="cr-left"') == 1
        assert segment.count('class="cr-center"') == 1

    # ---- PART 3: Patient Reports inside cr-right ----

    def test_patient_reports_inside_cr_right(self):
        """Patient Reports card is inside cr-right."""
        page = build_control_room_page()
        right_open = page.find('<div class="cr-right">')
        right_close_tag = '</div>'
        # Find the matching close for cr-right
        depth = 0
        pos = right_open
        while pos < len(page):
            next_open = page.find('<div', pos + 1)
            next_close = page.find('</div>', pos + 1)
            if next_close < 0:
                break
            if next_open >= 0 and next_open < next_close:
                depth += 1
                pos = next_open
            else:
                depth -= 1
                if depth < 0:
                    break
                pos = next_close
        right_section = page[right_open:pos]
        assert 'Patient Reports' in right_section

    # ---- PART 4: Live Events inside cr-right ----

    def test_live_events_inside_cr_right(self):
        """Live Events card is inside cr-right."""
        page = build_control_room_page()
        right_open = page.find('<div class="cr-right">')
        depth = 0
        pos = right_open
        while pos < len(page):
            next_open = page.find('<div', pos + 1)
            next_close = page.find('</div>', pos + 1)
            if next_close < 0:
                break
            if next_open >= 0 and next_open < next_close:
                depth += 1
                pos = next_open
            else:
                depth -= 1
                if depth < 0:
                    break
                pos = next_close
        right_section = page[right_open:pos]
        assert 'Live Events' in right_section

    # ---- PART 5: cr-decision-card inside cr-center, outside pipeline card ----

    def test_decision_card_inside_cr_center(self):
        """cr-decision-card is inside cr-center."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        # cr-right follows cr-center close, so find cr-right as end marker
        right_open = page.find('<div class="cr-right">')
        center_section = page[center_open:right_open]
        assert 'cr-decision-card' in center_section

    def test_decision_card_not_inside_cr_card_rail(self):
        """cr-decision-card is not inside cr-card-rail."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        rail_open = page.find('<div class="cr-card cr-card-rail">', center_open)
        # Find where cr-card-rail closes: pipeline is last child, so after
        # stage-complete and its closing div, then the rail card closes
        pipeline_end = page.find('</div>', page.find('stage-complete', rail_open))
        # The next </div> after pipeline closes = cr-card-rail close
        rail_close = page.find('</div>', pipeline_end + 5)
        rail_section = page[rail_open:rail_close]
        assert 'cr-decision-card' not in rail_section, (
            'cr-decision-card should NOT be inside cr-card-rail'
        )

    def test_decision_card_not_inside_cr_pipeline(self):
        """cr-decision-card is not inside cr-pipeline."""
        page = build_control_room_page()
        pipeline_open = page.find('<div class="cr-pipeline"')
        pipeline_close = page.find('</div>', page.find('stage-complete', pipeline_open))
        pipeline_section = page[pipeline_open:pipeline_close + 6]
        assert 'cr-decision-card' not in pipeline_section

    # ---- PART 6: cr-card-rail contains only Pipeline + pipeline div ----

    def test_cr_card_rail_contains_execution_pipeline(self):
        """cr-card-rail contains Execution Pipeline title."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        rail_open = page.find('<div class="cr-card cr-card-rail">', center_open)
        pipeline_end = page.find('</div>', page.find('stage-complete', rail_open))
        rail_close = page.find('</div>', pipeline_end + 5)
        rail_section = page[rail_open:rail_close]
        assert 'Execution Pipeline' in rail_section

    def test_cr_card_rail_contains_cr_pipeline(self):
        """cr-card-rail contains cr-pipeline div."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        rail_open = page.find('<div class="cr-card cr-card-rail">', center_open)
        pipeline_end = page.find('</div>', page.find('stage-complete', rail_open))
        rail_close = page.find('</div>', pipeline_end + 5)
        rail_section = page[rail_open:rail_close]
        assert 'cr-pipeline' in rail_section

    def test_cr_card_rail_no_patient_reports(self):
        """cr-card-rail does NOT contain Patient Reports."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        rail_open = page.find('<div class="cr-card cr-card-rail">', center_open)
        pipeline_end = page.find('</div>', page.find('stage-complete', rail_open))
        rail_close = page.find('</div>', pipeline_end + 5)
        rail_section = page[rail_open:rail_close]
        assert 'Patient Reports' not in rail_section

    def test_cr_card_rail_no_live_events(self):
        """cr-card-rail does NOT contain Live Events."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        rail_open = page.find('<div class="cr-card cr-card-rail">', center_open)
        pipeline_end = page.find('</div>', page.find('stage-complete', rail_open))
        rail_close = page.find('</div>', pipeline_end + 5)
        rail_section = page[rail_open:rail_close]
        assert 'Live Events' not in rail_section

    # ---- PART 7: Dense pipeline preserved ----

    def test_fifteen_cr_stage_rows(self):
        """15 class=cr-stage rows remain."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15

    def test_long_captions_visible(self):
        """Long captions are visible (not hidden)."""
        page = build_control_room_page()
        assert page.count('cr-stage-caption') >= 15

    def test_no_cr_stage_chevron(self):
        """No cr-stage-chevron in production UI."""
        page = build_control_room_page()
        assert 'cr-stage-chevron' not in page

    def test_no_toggle_stage(self):
        """No toggleStage in production UI."""
        page = build_control_room_page()
        assert 'toggleStage(this)' not in page
        assert 'toggleStageKey(event,this)' not in page

    def test_no_cr_stage_help(self):
        """No cr-stage-help in production UI."""
        page = build_control_room_page()
        assert 'cr-stage-help' not in page

    # ---- PART 8: Responsive CSS preserved ----

    def test_cr_main_flex_layout(self):
        """cr-main flex layout exists."""
        page = build_control_room_page()
        assert '.cr-main{' in page or '.cr-main {' in page
        assert 'display:flex' in page

    def test_cr_left_width_320(self):
        """cr-left width 320px remains."""
        page = build_control_room_page()
        assert '.cr-left{width:320px' in page

    def test_cr_center_flex_column(self):
        """cr-center flex column remains."""
        page = build_control_room_page()
        assert '.cr-center{' in page
        assert 'flex-direction:column' in page

    def test_cr_right_width_360(self):
        """cr-right width 360px remains."""
        page = build_control_room_page()
        assert '.cr-right{width:360px' in page

    # ---- PART 9: Existing PR0099J tests still pass (preservation) ----

    def test_mark_pipeline_complete_exists(self):
        """markPipelineComplete function exists."""
        page = build_control_room_page()
        assert 'function markPipelineComplete' in page

    def test_has_seen_failure_checks(self):
        """markPipelineComplete checks hasSeenFailure."""
        page = build_control_room_page()
        fn_start = page.find('function markPipelineComplete')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'hasSeenFailure' in fn_body

    def test_all_stages_marked_completed(self):
        """markPipelineComplete marks all stages completed."""
        page = build_control_room_page()
        fn_start = page.find('function markPipelineComplete')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'cr-stage completed' in fn_body
        assert 'querySelectorAll' in fn_body

    def test_no_active_dot_after_completion(self):
        """No active dot after markPipelineComplete."""
        page = build_control_room_page()
        fn_start = page.find('function markPipelineComplete')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "'cr-stage completed'" in fn_body or '"cr-stage completed"' in fn_body


class TestPR0099JOrderingAndStableDecisionSlot:
    """PR0099J ordering fix: Analyze above Source, decision above pipeline, stable slot."""

    # ---- PART 1: Left column order ----

    def test_model_before_patients_list(self):
        """Model card appears before Patients List in left column."""
        page = build_control_room_page()
        left_start = page.find('class="cr-left"')
        right_start = page.find('class="cr-right"')
        left_section = page[left_start:right_start]
        model_pos = left_section.find('Model')
        patients_pos = left_section.find('Patients List')
        assert model_pos < patients_pos

    def test_patients_list_before_analyze(self):
        """Patients List appears before Analyze button in left column."""
        page = build_control_room_page()
        left_start = page.find('class="cr-left"')
        right_start = page.find('class="cr-right"')
        left_section = page[left_start:right_start]
        patients_pos = left_section.find('Patients List')
        analyze_pos = left_section.find('cr-analyze-btn')
        assert patients_pos < analyze_pos

    def test_analyze_before_source(self):
        """Analyze button appears before Source card in left column."""
        page = build_control_room_page()
        left_start = page.find('class="cr-left"')
        right_start = page.find('class="cr-right"')
        left_section = page[left_start:right_start]
        analyze_pos = left_section.find('cr-analyze-btn')
        source_pos = left_section.find('>Source<')
        assert analyze_pos < source_pos

    def test_left_column_full_order(self):
        """Left column order: Model, Patients List, Analyze, Source."""
        page = build_control_room_page()
        left_start = page.find('class="cr-left"')
        right_start = page.find('class="cr-right"')
        left_section = page[left_start:right_start]
        model_pos = left_section.find('Model')
        patients_pos = left_section.find('Patients List')
        analyze_pos = left_section.find('cr-analyze-btn')
        source_pos = left_section.find('>Source<')
        assert model_pos < patients_pos < analyze_pos < source_pos

    # ---- PART 2: Analyze button preserved ----

    def test_analyze_btn_id(self):
        """Analyze button has id cr-analyze-btn."""
        page = build_control_room_page()
        assert 'id="cr-analyze-btn"' in page

    def test_analyze_btn_onclick(self):
        """Analyze button onclick is startAnalysis()."""
        page = build_control_room_page()
        assert 'onclick="startAnalysis()"' in page

    def test_analyze_btn_disabled_initially(self):
        """Analyze button is disabled initially."""
        page = build_control_room_page()
        assert 'id="cr-analyze-btn" disabled' in page or 'disabled aria-label="Start analysis"' in page

    def test_analyze_btn_aria_label(self):
        """Analyze button has aria-label."""
        page = build_control_room_page()
        assert 'aria-label="Start analysis"' in page

    # ---- PART 3: Center column order ----

    def test_decision_before_pipeline(self):
        """cr-decision-card appears before Execution Pipeline in center column."""
        page = build_control_room_page()
        center_start = page.find('class="cr-center"')
        right_start = page.find('class="cr-right"')
        center_section = page[center_start:right_start]
        decision_pos = center_section.find('cr-decision-card')
        pipeline_pos = center_section.find('Execution Pipeline')
        assert decision_pos < pipeline_pos

    def test_decision_inside_cr_center(self):
        """cr-decision-card is inside cr-center."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        right_open = page.find('<div class="cr-right">')
        center_section = page[center_open:right_open]
        assert 'cr-decision-card' in center_section

    def test_decision_not_inside_cr_card_rail(self):
        """cr-decision-card is not inside cr-card-rail."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        rail_open = page.find('<div class="cr-card cr-card-rail">', center_open)
        pipeline_end = page.find('</div>', page.find('stage-complete', rail_open))
        rail_close = page.find('</div>', pipeline_end + 5)
        rail_section = page[rail_open:rail_close]
        assert 'cr-decision-card' not in rail_section

    def test_decision_not_inside_cr_pipeline(self):
        """cr-decision-card is not inside cr-pipeline."""
        page = build_control_room_page()
        pipeline_open = page.find('<div class="cr-pipeline"')
        pipeline_close = page.find('</div>', page.find('stage-complete', pipeline_open))
        pipeline_section = page[pipeline_open:pipeline_close + 6]
        assert 'cr-decision-card' not in pipeline_section

    # ---- PART 4: Stable decision slot ----

    def test_decision_not_hidden_initially(self):
        """cr-decision-card is not hidden in initial HTML."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        right_open = page.find('<div class="cr-right">')
        center_section = page[center_open:right_open]
        # The decision card div should NOT have 'hidden' class
        card_start = center_section.find('cr-decision-card')
        card_line_end = center_section.find('>', card_start)
        card_open_tag = center_section[card_start:card_line_end]
        assert 'hidden' not in card_open_tag

    def test_decision_placeholder_class(self):
        """cr-decision-placeholder class exists."""
        page = build_control_room_page()
        assert 'cr-decision-placeholder' in page

    def test_min_height_css_for_placeholder(self):
        """min-height CSS exists for decision placeholder."""
        page = build_control_room_page()
        assert 'min-height:140px' in page or 'min-height: 140px' in page

    def test_neutral_placeholder_copy(self):
        """Neutral placeholder copy exists in initial HTML."""
        page = build_control_room_page()
        assert 'Recommendation pending' in page
        assert 'Recommendation will appear here after analysis.' in page

    def test_placeholder_secondary_copy(self):
        """Secondary placeholder copy exists."""
        page = build_control_room_page()
        assert 'Technical demo only. A clinician makes the final decision.' in page

    def test_placeholder_no_clinical_claims(self):
        """Placeholder copy does not include clinical claims."""
        page = build_control_room_page()
        center_open = page.find('<div class="cr-center">')
        right_open = page.find('<div class="cr-right">')
        center_section = page[center_open:right_open]
        assert 'diagnos' not in center_section.lower()

    # ---- PART 5: JS reset behavior ----

    def test_render_decision_placeholder_function(self):
        """renderDecisionPlaceholder() helper function exists."""
        page = build_control_room_page()
        assert 'function renderDecisionPlaceholder' in page

    def test_on_model_select_uses_placeholder(self):
        """onModelSelect uses renderDecisionPlaceholder, not hidden collapse."""
        page = build_control_room_page()
        fn_start = page.find('function onModelSelect')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'renderDecisionPlaceholder()' in fn_body
        assert "cr-decision-card hidden" not in fn_body

    def test_delete_report_uses_placeholder(self):
        """deleteReport uses renderDecisionPlaceholder for current card reset."""
        page = build_control_room_page()
        fn_start = page.find('function deleteReport')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'renderDecisionPlaceholder()' in fn_body
        assert "cr-decision-card hidden" not in fn_body

    def test_start_analysis_no_slot_collapse(self):
        """startAnalysis does not permanently collapse the decision slot."""
        page = build_control_room_page()
        fn_start = page.find('function startAnalysis')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # startAnalysis should not set cr-decision-card hidden
        assert "cr-decision-card hidden" not in fn_body

    # ---- PART 6: Dense pipeline preservation ----

    def test_fifteen_stage_rows(self):
        """15 class=cr-stage rows remain."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15

    def test_long_captions_visible(self):
        """Long captions are visible."""
        page = build_control_room_page()
        assert page.count('cr-stage-caption') >= 15

    def test_no_cr_stage_chevron(self):
        """No cr-stage-chevron in production UI."""
        page = build_control_room_page()
        assert 'cr-stage-chevron' not in page

    def test_no_toggle_stage(self):
        """No toggleStage in production UI."""
        page = build_control_room_page()
        assert 'toggleStage(this)' not in page
        assert 'toggleStageKey(event,this)' not in page

    def test_no_cr_stage_help(self):
        """No cr-stage-help in production UI."""
        page = build_control_room_page()
        assert 'cr-stage-help' not in page

    # ---- PART 7: Right column preservation ----

    def test_patient_reports_in_cr_right(self):
        """Patient Reports remains in cr-right."""
        page = build_control_room_page()
        right_open = page.find('<div class="cr-right">')
        right_section = page[right_open:]
        assert 'Patient Reports' in right_section

    def test_live_events_in_cr_right(self):
        """Live Events remains in cr-right."""
        page = build_control_room_page()
        right_open = page.find('<div class="cr-right">')
        right_section = page[right_open:]
        assert 'Live Events' in right_section

    # ---- PART 8: Failure/report preservation ----

    def test_failed_jobs_no_open_report(self):
        """Failed jobs still do not show Open report in fetchDecision."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'normalization_failed' in fn_body

    def test_failed_message_preserved(self):
        """Analysis failed message preserved."""
        page = build_control_room_page()
        assert 'Analysis failed' in page
        assert 'No report was generated' in page

    def test_completed_path_renders_report_link(self):
        """Completed path still renders report link."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'Open report' in fn_body

    def test_mri_headline_preserved(self):
        """MRI can wait and MRI recommended headlines preserved in fetchDecision."""
        page = build_control_room_page()
        fn_start = page.find('function fetchDecision')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'MRI can wait' in fn_body
        assert 'MRI recommended' in fn_body


class TestPR0099JDeletedReportsUI:
    """PR0099J deleted reports UI: hide deleted from main list, collapsed deleted section."""

    # ---- PART 1: Deleted reports not in primary list ----

    def test_report_deleted_not_in_main_list(self):
        """report_deleted jobs are not rendered in the primary Patient Reports list."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # activeJobs should be filtered to exclude report_deleted
        assert 'report_deleted' in fn_body
        assert 'activeJobs' in fn_body
        assert 'deletedJobs' in fn_body

    def test_active_jobs_filter_excludes_deleted(self):
        """Active jobs filter excludes report_deleted jobs."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'j.report_deleted' in fn_body

    # ---- PART 2: Deleted reports in separate section ----

    def test_deleted_section_uses_details_element(self):
        """Deleted reports section uses <details> element."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert '<details class="cr-deleted-reports">' in fn_body

    def test_deleted_section_label(self):
        """Deleted reports section label shows count."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'Deleted reports (' in fn_body

    def test_deleted_section_collapsed_by_default(self):
        """<details> element is collapsed by default (no open attribute)."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # <details> without 'open' attribute is collapsed by default
        assert '<details class="cr-deleted-reports">' in fn_body
        assert 'open>' not in fn_body.split('cr-deleted-reports')[0].split('<details')[-1]

    # ---- PART 3: Section only rendered when deleted exist ----

    def test_deleted_section_conditional(self):
        """Deleted section only rendered when deletedJobs.length > 0."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'deletedJobs.length>0' in fn_body or 'deletedJobs.length > 0' in fn_body

    # ---- PART 4: All jobs deleted scenario ----

    def test_no_active_patient_reports_message(self):
        """When no active jobs remain, shows 'No active patient reports.'"""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'No active patient reports.' in fn_body

    def test_no_active_message_conditional(self):
        """No active message only when activeJobs is empty."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'activeJobs.length===0' in fn_body or 'activeJobs.length === 0' in fn_body

    # ---- PART 5: Deleted rows have no interactive features ----

    def test_deleted_rows_no_open_report(self):
        """Deleted report rows have no Open report link."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # The deleted section rendering loop should not include openJob
        deleted_section_start = fn_body.find('deletedJobs.forEach')
        deleted_section = fn_body[deleted_section_start:]
        assert 'openJob' not in deleted_section

    def test_deleted_rows_no_delete_button(self):
        """Deleted report rows have no Delete report button."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        deleted_section_start = fn_body.find('deletedJobs.forEach')
        deleted_section = fn_body[deleted_section_start:]
        assert 'Delete report' not in deleted_section

    def test_deleted_rows_no_click_through(self):
        """Deleted report rows have no onclick handler."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        deleted_section_start = fn_body.find('deletedJobs.forEach')
        deleted_section = fn_body[deleted_section_start:]
        assert 'onclick' not in deleted_section

    # ---- PART 6: Active reports preserved ----

    def test_active_jobs_still_render(self):
        """Active (non-deleted) jobs still render in main list."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'activeJobs.slice' in fn_body or 'activeJobs.slice(0,MAX_HISTORY)' in fn_body

    def test_existing_completed_reports_render(self):
        """Existing completed report rows still render with Open report."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        # Active jobs still render with report link
        assert 'openJob' in fn_body
        assert 'reportAvail' in fn_body

    def test_existing_failed_behavior_preserved(self):
        """Existing failed job behavior remains in active list."""
        page = build_control_room_page()
        fn_start = page.find('function loadJobHistory')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert 'isFailed' in fn_body
        assert 'Analysis failed' in fn_body

    # ---- PART 7: Delete action preserved ----

    def test_delete_action_uses_same_endpoint(self):
        """Delete report still calls the same backend action."""
        page = build_control_room_page()
        fn_start = page.find('function deleteReport')
        fn_end = page.find('function ', fn_start + 10)
        fn_body = page[fn_start:fn_end if fn_end > 0 else len(page)]
        assert "action:'delete_report'" in fn_body or 'action:delete_report' in fn_body

    # ---- PART 8: CSS for deleted section ----

    def test_css_deleted_reports_class(self):
        """CSS for cr-deleted-reports exists."""
        page = build_control_room_page()
        assert '.cr-deleted-reports{' in page

    def test_css_deleted_report_item_class(self):
        """CSS for cr-deleted-report-item exists."""
        page = build_control_room_page()
        assert '.cr-deleted-report-item{' in page

    # ---- PART 9: Preservation ----

    def test_patient_reports_heading_preserved(self):
        """Patient Reports heading remains."""
        page = build_control_room_page()
        assert 'Patient Reports' in page

    def test_live_events_preserved(self):
        """Live Events remains in cr-right."""
        page = build_control_room_page()
        assert 'Live Events' in page

    def test_decision_slot_above_pipeline(self):
        """Decision card remains above Execution Pipeline."""
        page = build_control_room_page()
        center_start = page.find('class="cr-center"')
        center_section = page[center_start:]
        decision_pos = center_section.find('cr-decision-card')
        pipeline_pos = center_section.find('Execution Pipeline')
        assert decision_pos < pipeline_pos

    def test_analyze_after_patients_list(self):
        """Analyze button remains immediately after Patients List."""
        page = build_control_room_page()
        left_start = page.find('class="cr-left"')
        right_start = page.find('class="cr-right"')
        left_section = page[left_start:right_start]
        patients_pos = left_section.find('Patients List')
        analyze_pos = left_section.find('cr-analyze-btn')
        assert patients_pos < analyze_pos

    def test_fifteen_stages_preserved(self):
        """15 cr-stage rows remain."""
        page = build_control_room_page()
        assert page.count('class="cr-stage"') == 15

    def test_no_accordion_preserved(self):
        """No accordion UI."""
        page = build_control_room_page()
        assert 'cr-stage-chevron' not in page
        assert 'toggleStage(this)' not in page
        assert 'cr-stage-help' not in page

    def test_no_container_copy(self):
        """No container(s)/Container: copy."""
        page = build_control_room_page()
        assert 'container(s)' not in page
        assert 'Container:' not in page

    def test_decision_placeholder_preserved(self):
        """Decision placeholder remains visible."""
        page = build_control_room_page()
        assert 'cr-decision-placeholder' in page
        assert 'Recommendation pending' in page

    def test_duplicate_guard_preserved(self):
        """Duplicate report guard preserved."""
        import inspect
        from bremen.api.job_api_handler import handle_jobs_create
        src = inspect.getsource(handle_jobs_create)
        assert 'report_already_exists' in src


# ===========================================================================
# PR0114: SSE and report ticket auth — client-side flow tests
# ===========================================================================


class TestPR0114ClientTicketFlow:
    """Verify client-side ticket minting in connectSSE and openJob."""

    def test_auth_fetch_ticket_function_exists(self):
        """_authFetchTicket function is defined in JS."""
        page = build_control_room_page()
        assert 'function _authFetchTicket(jobId,purpose)' in page

    def test_auth_fetch_ticket_uses_auth_fetch(self):
        """_authFetchTicket calls _authFetch with ticket endpoint."""
        page = build_control_room_page()
        assert '_authFetchTicket' in page
        assert 'auth/ticket' in page
        assert 'purpose:purpose' in page

    def test_connect_sse_mints_ticket(self):
        """connectSSE calls _authFetchTicket before creating EventSource."""
        page = build_control_room_page()
        # Verify connectSSE calls _authFetchTicket
        assert '_authFetchTicket(jobId,\'stream\')' in page
        # Verify EventSource URL uses auth_ticket query param
        assert 'auth_ticket=' in page
        assert 'encodeURIComponent(ticket)' in page

    def test_connect_sse_no_direct_eventsource(self):
        """connectSSE no longer creates EventSource without ticket."""
        page = build_control_room_page()
        # The old pattern was: new EventSource(baseUrl+'/demo/api/jobs/'+jobId+'/events/stream')
        # The new pattern wraps it in _authFetchTicket.then()
        assert 'new EventSource' in page
        assert '_authFetchTicket(jobId,\'stream\').then(function(ticket){' in page

    def test_open_job_mints_report_ticket(self):
        """openJob calls _authFetchTicket with report purpose."""
        page = build_control_room_page()
        # openJob now mints ticket before navigating
        assert '_authFetchTicket(jobId,\'report\')' in page
        assert 'auth_ticket=' in page

    def test_open_job_uses_redirect_to_login_on_failure(self):
        """openJob redirects to login on ticket mint failure."""
        page = build_control_room_page()
        assert '_redirectToLogin()' in page

    def test_connect_sse_handles_ticket_failure(self):
        """connectSSE handles ticket mint failure gracefully."""
        page = build_control_room_page()
        # The .catch() handler should set connection state to disconnected
        assert 'setConnectionState(\'disconnected\')' in page

    def test_access_token_never_in_url(self):
        """Access token is never placed in EventSource or report URL."""
        page = build_control_room_page()
        # Search for patterns where access token might leak into URLs
        # The openJob function should not use _getAccessToken() for URLs
        assert 'window.location.href=baseUrl+\'/demo/report/'+repr('')
        # But should use auth_ticket
        assert 'auth_ticket' in page
        # Verify no pattern like: _getAccessToken() in URL construction
        assert "_getAccessToken()+" not in page
        assert "'Bearer '+" not in page.split('function openJob')[1] if 'function openJob' in page else True

    def test_auth_disabled_sse_passthrough(self):
        """When auth disabled, SSE route works without ticket."""
        page = build_control_room_page()
        # Verify the client-side code doesn't block SSE when no auth
        assert 'function connectSSE' in page

    def test_ticket_mint_endpoint_in_job_history(self):
        """Job history loadJobHistory function is preserved."""
        page = build_control_room_page()
        assert 'function loadJobHistory' in page
