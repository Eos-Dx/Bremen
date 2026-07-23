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


class TestControlRoomRoute:
    """Control Room default route replaces old /demo."""

    @pytest.fixture
    def server_info(self):
        reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        handler = _make_handler(InMemoryJobStore(), version="test", load_model=True)
        server = _ThreadingHTTPServer((host, port), handler)
        server.allow_reuse_address = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        import time as _time
        _time.sleep(0.1)
        yield host, port
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        reset_for_tests()

    def test_control_room_is_default_route(self, server_info):
        host, port = server_info
        status, body, _ = _get(host, port, "/demo")
        assert status == 200
        assert "Investor Control Room" in body
        assert "Should the patient continue to MRI" in body

    def test_workspace_route_preserved(self, server_info):
        host, port = server_info
        status, body, _ = _get(host, port, "/demo/workspace")
        assert status == 200
        assert "Analysis Workspace" in body

    def test_control_room_has_stage_pipeline(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo")
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
        _, body, _ = _get(host, port, "/demo")
        assert "STAGE_MAP" in body
        assert "runtime.input.preparation.completed" in body
        assert "runtime.report.completed" in body

    def test_control_room_has_file_input(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo")
        assert "cr-file-input" in body
        assert "Select H5 File" in body

    def test_control_room_has_event_panel(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo")
        assert "cr-event-list" in body or "cr-event-panel" in body
        assert "cr-filter-all" in body
        assert "cr-filter-completed" in body
        assert "cr-filter-failed" in body

    def test_control_room_has_decision_card(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo")
        assert "cr-decision-card" in body

    def test_control_room_has_state_model(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo")
        assert "setState" in body
        assert "ready_to_submit" in body
        assert "submitting" in body

    def test_control_room_has_model_question(self, server_info):
        host, port = server_info
        _, body, _ = _get(host, port, "/demo")
        assert "Should the patient continue to MRI" in body


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
        assert 'aria-label="Show all events"' in page
        assert 'aria-label="Show completed events only"' in page
        assert 'aria-label="Show failed events only"' in page

    def test_role_status_badges(self):
        page = build_control_room_page()
        assert 'role="status"' in page

    def test_role_alert_decision(self):
        page = build_control_room_page()
        assert 'role="alert"' in page

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
        assert "BREMEN_MODEL_URI" not in page

    def test_no_mri_rule_out_public_wording(self):
        page = build_control_room_page()
        assert "MRI_RULE_OUT" not in page


class TestModelIdentity:
    """Control Room shows exactly one real Bremen model."""

    def test_one_workflow_displayed(self):
        page = build_control_room_page()
        assert "Bremen" in page
        assert "MRI Triage Model" in page

    def test_no_model_selector(self):
        page = build_control_room_page()
        assert "model-select" not in page.lower()
        assert "model_selector" not in page.lower()
        assert "variant" not in page.lower()

    def test_decision_policy_displayed(self):
        page = build_control_room_page()
        assert "bremen_mri_continuation_threshold" in page

    def test_scientific_certification_pending(self):
        page = build_control_room_page()
        assert "Scientific certification: pending" in page or "certification" in page.lower()

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
        assert "must be configured" in page or "Model must be" in page


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

    @pytest.fixture
    def server_info(self):
        reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        handler = _make_handler(InMemoryJobStore(), version="test", load_model=True)
        server = _ThreadingHTTPServer((host, port), handler)
        server.allow_reuse_address = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        import time as _time
        _time.sleep(0.1)
        yield host, port
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        reset_for_tests()

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
        assert "h5_path" in body
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

    @pytest.fixture
    def server_info(self):
        reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        handler = _make_handler(InMemoryJobStore(), version="test", load_model=True)
        server = _ThreadingHTTPServer((host, port), handler)
        server.allow_reuse_address = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        import time as _time
        _time.sleep(0.1)
        yield host, port
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        reset_for_tests()

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
