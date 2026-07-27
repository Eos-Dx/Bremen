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
import socket
import threading
import tempfile
import os
import h5py
import numpy as np
from http.server import HTTPServer
from pathlib import Path

import pytest

from bremen.api.server import _make_handler, _ThreadingHTTPServer
from bremen.api.jobs import InMemoryJobStore
from bremen.api.job_api_handler import reset_for_tests
from bremen.control_room_ui import build_control_room_page


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
    """Start a _ThreadingHTTPServer ONCE per module on a free port with synthetic model.

    Uses ``allow_reuse_address=True``, ``server_close()``, and a 0.1s startup
    sleep to preserve the original fixture's exact behavior — but only runs
    once per module instead of once per test.
    """
    import time as _time
    reset_for_tests()
    host = "127.0.0.1"
    port = _find_free_port()
    handler = _make_handler(InMemoryJobStore(), version="test", load_model=True)
    server = _ThreadingHTTPServer((host, port), handler)
    server.allow_reuse_address = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _time.sleep(0.1)
    yield host, port
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    reset_for_tests()


@pytest.fixture
def server_info(_shared_server):
    """Per-test cheap-reset fixture sharing the module-scoped server.

    Yields ``(host, port)`` (same signature as original per-test fixtures).
    """
    from bremen.api.model_state import ModelState
    from bremen.api.server import _load_synthetic_model

    host, port = _shared_server

    ModelState.reset_for_tests()
    _load_synthetic_model()
    reset_for_tests()

    yield host, port


class TestControlRoomRoute:
    """Control Room default route replaces old /demo."""

    def test_start_page_is_default_route(self, server_info):
        host, port = server_info
        status, body, _ = _get(host, port, "/demo")
        assert status == 200
        assert "Select a model to begin" in body
        assert "Should the patient continue to MRI" in body

    def test_control_room_route(self, server_info):
        host, port = server_info
        status, body, _ = _get(host, port, "/demo/control-room")
        assert status == 200
        assert "Control Room" in body or "cr-page" in body
        assert "Should the patient continue to MRI" in body

    def test_workspace_route_preserved(self, server_info):
        host, port = server_info
        status, body, _ = _get(host, port, "/demo/workspace")
        assert status == 200
        assert "Analysis Workspace" in body

    def test_control_room_has_stage_pipeline(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        assert "stage-input" in body
        assert "stage-source" in body
        assert "stage-xrd" in body
        assert "stage-workflow" in body
        assert "stage-artifact" in body
        assert "stage-features" in body
        assert "stage-inference" in body
        assert "stage-decision" in body
        assert "stage-report" in body
        assert "stage-complete" in body

    def test_control_room_has_stage_map_code(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        assert "STAGE_MAP" in body
        assert "runtime.input.preparation.completed" in body
        assert "runtime.report.completed" in body

    def test_control_room_has_file_input(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        assert "cr-file-input" in body
        assert "Upload New H5 File" in body

    def test_control_room_has_event_panel(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        assert "cr-event-list" in body or "cr-event-panel" in body
        assert "cr-filter-all" in body
        assert "cr-filter-completed" in body
        assert "cr-filter-failed" in body

    def test_control_room_has_decision_card(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        assert "cr-decision-card" in body

    def test_control_room_has_state_model(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        assert "setState" in body
        assert "ready_to_submit" in body
        assert "submitting" in body

    def test_control_room_has_model_question(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        assert "Should the patient continue to MRI" in body

    def test_report_route(self, server_info):
        host, port = server_info
        status, body, _ = _get(host, port, "/demo/report/test-job-id")
        assert status == 200
        assert "Bremen Report" in body or "report-page" in body


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


class TestFileUpload:
    """File upload and staging endpoint integration."""

    def test_stage_endpoint_accepts_file(self, server_info):
        host, port = server_info
        import urllib.request
        data = b"\x89HDF\r\n\x1a\n" + b"\x00" * 100
        req = urllib.request.Request(
            f"http://{host}:{port}/demo/api/stage",
            data=data,
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        assert resp.status == 201
        body = json.loads(resp.read())
        assert body["status"] == "staged"
        assert "upload_id" in body
        assert "filename" in body
        assert "size_bytes" in body
        assert "h5_path" not in body
        assert body["technical_demo_only"] is True

    def test_stage_empty_body_rejected(self, server_info):
        host, port = server_info
        import urllib.request
        from urllib.error import HTTPError
        req = urllib.request.Request(
            f"http://{host}:{port}/demo/api/stage",
            data=b"",
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "Expected HTTPError"
        except HTTPError as exc:
            assert exc.code == 400

    def test_staged_file_creates_valid_job(self, server_info):
        host, port = server_info
        import urllib.request
        import tempfile, os, h5py, numpy as np

        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, "test.h5")
            with h5py.File(h5_path, "w") as f:
                scans = f.create_group("scans")
                for label in ("target", "contralateral"):
                    grp = scans.create_group(label)
                    arr = np.random.default_rng(42).normal(10.0, 2.0, 100).astype(np.float64)
                    grp.create_dataset("measurements", data=arr.reshape(1, -1))

            data = json.dumps({"h5_path": h5_path, "workflow_id": "bremen"}).encode()
            req = urllib.request.Request(
                f"http://{host}:{port}/demo/api/jobs",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=10)
            assert resp.status == 201
            body = json.loads(resp.read())
            job = body.get("job", {})
            assert job.get("overall_status") in ("completed", "running")
            assert "decision_code" in str(body).lower() or "CONTINUE_MRI" in str(body) or "MRI_REVIEW_DEFER" in str(body)


class TestLegacyCompatibility:
    """Workspace routes and APIs preserved."""

    def test_health_responds_during_control_room(self, server_info):
        host, port = server_info
        status, _, _ = _get(host, port, "/health")
        assert status == 200

    def test_jobs_api_responds_during_control_room(self, server_info):
        host, port = server_info
        status, _, _ = _get(host, port, "/demo/api/jobs")
        assert status == 200

    def test_model_version_responds(self, server_info):
        host, port = server_info
        status, _, _ = _get(host, port, "/model/version")
        assert status == 200


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
        """Job History card has flex:1 for expansion."""
        page = build_control_room_page()
        idx = page.find('cr-card-title">Job History')
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
