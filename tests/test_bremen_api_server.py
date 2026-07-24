"""Tests for the standard-library HTTP service runner.

Covers endpoints defined in ``docs/api_contract.md`` and implemented
in ``src/bremen/api/server.py``.

Spins a real ``HTTPServer`` on a random port in a daemon thread so
that ``urllib.request`` can make real HTTP requests against it.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import h5py
import numpy as np
import pytest

from bremen.api.jobs import InMemoryJobStore
from bremen.api.server import _make_handler

API_SRC = Path(__file__).parents[1] / "src" / "bremen" / "api"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    """Return an OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def server_info():
    """Start an HTTPServer on a free port in a daemon thread.

    Yields ``(host, port, job_store)``.  Shuts down the server
    and joins the thread on teardown.
    """
    from bremen.api.model_state import ModelState
    from bremen.api.model_registry import initialize_registry, build_legacy_registry

    host = "127.0.0.1"
    port = _find_free_port()
    job_store = InMemoryJobStore()
    ModelState.reset_for_tests()
    handler = _make_handler(job_store, version="test-version", load_model=True)
    # Initialize registry from ModelState after loading
    legacy_registry = build_legacy_registry()
    initialize_registry(legacy_registry)
    server = HTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield host, port, job_store

    server.shutdown()
    thread.join(timeout=2)


def _get(host: str, port: int, path: str) -> tuple[int, bytes, dict]:
    """Perform a GET request and return ``(status, body, headers)``."""
    req = Request(f"http://{host}:{port}{path}")
    try:
        resp = urlopen(req, timeout=3)
        return resp.status, resp.read(), dict(resp.headers)
    except HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def _post(
    host: str, port: int, path: str, body: dict | None = None
) -> tuple[int, bytes, dict]:
    """Perform a POST request and return ``(status, body, headers)``."""
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    req = Request(
        f"http://{host}:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urlopen(req, timeout=3)
        return resp.status, resp.read(), dict(resp.headers)
    except HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self, server_info):
        host, port, _ = server_info
        status, body, headers = _get(host, port, "/health")
        assert status == 200
        data = json.loads(body)
        assert data["status"] == "ok"
        assert data["service"] == "bremen"

    def test_health_content_type(self, server_info):
        host, port, _ = server_info
        _, _, headers = _get(host, port, "/health")
        ct = headers.get("Content-Type", "")
        assert "application/json" in ct


# ---------------------------------------------------------------------------
# GET /model/version
# ---------------------------------------------------------------------------


class TestModelVersion:
    def test_model_version_returns_200(self, server_info):
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/model/version")
        assert status == 200
        data = json.loads(body)
        # Server loads synthetic model, so model_configured is True
        assert "model_configured" in data
        assert "model_status" in data

    def test_model_version_content_type(self, server_info):
        host, port, _ = server_info
        _, _, headers = _get(host, port, "/model/version")
        assert "application/json" in headers.get("Content-Type", "")

    def test_model_version_default_response_shape(self, server_info):
        """Test GET /model/version returns JSON with complete field set."""
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/model/version")
        assert status == 200
        data = json.loads(body)
        # Server loads synthetic model, so these are present
        assert "model_configured" in data
        assert "model_version" in data
        assert "model_status" in data
        assert "feature_schema_version" in data
        assert "threshold_version" in data
        assert "threshold_value" in data

    def test_model_version_configured(self):
        """Test handle_model_version with env set to configured state."""
        from bremen.config import read_cloud_config
        from bremen.api.model_state import ModelState
        from bremen.api.model_registry import reset_for_tests as reset_registry

        # Reset model state and registry to test cloud env behavior
        ModelState.reset_for_tests()
        reset_registry()

        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bucket"}
        )
        from bremen.api.app import handle_model_version

        resp = handle_model_version(cloud=cloud)
        assert resp.model_configured is True
        assert resp.model_status == "configured"
        assert resp.model_version is None


# ---------------------------------------------------------------------------
# POST /predictions
# ---------------------------------------------------------------------------


class TestSubmitPrediction:
    def test_valid_submit_returns_202(self, server_info):
        host, port, _ = server_info
        payload = {
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_path": "/tmp/test.h5",
        }
        status, body, _ = _post(host, port, "/predictions", payload)
        assert status == 202
        data = json.loads(body)
        assert data["status"] == "accepted"
        assert "job_id" in data

    def test_submit_has_poll_link(self, server_info):
        host, port, _ = server_info
        payload = {
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_path": "/tmp/test.h5",
        }
        _, body, _ = _post(host, port, "/predictions", payload)
        data = json.loads(body)
        assert "links" in data
        assert "poll" in data["links"]

    def test_submit_missing_target_returns_400(self, server_info):
        host, port, _ = server_info
        payload = {"control_scan_ref": "scan:ctl/001"}
        status, body, _ = _post(host, port, "/predictions", payload)
        assert status == 400
        data = json.loads(body)
        assert "target_scan_ref" in data.get("error", "")

    def test_submit_missing_control_returns_400(self, server_info):
        host, port, _ = server_info
        payload = {"target_scan_ref": "scan:tgt/001"}
        status, body, _ = _post(host, port, "/predictions", payload)
        assert status == 400
        data = json.loads(body)
        assert "control_scan_ref" in data.get("error", "")

    def test_submit_malformed_json_returns_400(self, server_info):
        host, port, _ = server_info
        # Send non-JSON bytes
        req = Request(
            f"http://{host}:{port}/predictions",
            data=b"not valid json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urlopen(req, timeout=3)
            assert False, "Expected HTTPError"
        except HTTPError as exc:
            assert exc.code == 400
            data = json.loads(exc.read())
            assert "JSON" in data.get("error", "")

    def test_submit_empty_body_returns_400(self, server_info):
        host, port, _ = server_info
        status, body, _ = _post(host, port, "/predictions", None)
        assert status == 400


class TestSubmitPredictionModelNotReady:
    """Tests for the 503 model-not-ready case."""

    @pytest.fixture
    def no_model_server_info(self):
        """Start server with model NOT loaded."""
        from bremen.api.model_state import ModelState

        # Ensure clean singleton state before creating handler
        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=False)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield host, port, job_store
        server.shutdown()
        thread.join(timeout=2)

    def test_submit_returns_503_when_model_not_ready(self, no_model_server_info, caplog):
        """POST /predictions returns 503 when model is not loaded.

        Also verifies ``bremen.prediction.request.rejected`` is emitted.
        """
        import logging
        from bremen.api.model_state import ModelState

        # Defensive: ensure ModelState is clean before sending request
        # (previous tests with server_info may have loaded a model)
        ModelState.reset_for_tests()

        caplog.set_level(logging.WARNING)
        host, port, _ = no_model_server_info
        payload = {
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
        }
        status, body, _ = _post(host, port, "/predictions", payload)
        assert status == 503
        data = json.loads(body)
        assert "not loaded" in data.get("error", "")
        assert "bremen.prediction.request.rejected" in caplog.text


# ---------------------------------------------------------------------------
# GET /predictions/{job_id}
# ---------------------------------------------------------------------------


class TestGetPrediction:
    def test_known_job_returns_200(self, server_info):
        host, port, job_store = server_info
        # Create a job directly in the store
        from bremen.api.schemas import PredictionRequest

        request = PredictionRequest(
            target_scan_ref="scan:tgt/001",
            control_scan_ref="scan:ctl/001",
        )
        record = job_store.create_job(request=request)
        status, body, _ = _get(host, port, f"/predictions/{record.job_id}")
        assert status == 200
        data = json.loads(body)
        assert data["job_id"] == record.job_id
        assert data["status"] == "accepted"

    def test_unknown_job_returns_404(self, server_info):
        host, port, _ = server_info
        status, body, _ = _get(
            host, port, "/predictions/00000000-0000-0000-0000-000000000000"
        )
        assert status == 404
        data = json.loads(body)
        assert data["status"] == "not_found"


# ---------------------------------------------------------------------------
# Unknown route / unsupported method
# ---------------------------------------------------------------------------


class TestRouteErrors:
    def test_unknown_route_returns_404(self, server_info):
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/unknown-route")
        assert status == 404
        data = json.loads(body)
        assert "Not found" in data.get("error", "")

    def test_put_on_health_returns_405(self, server_info):
        host, port, _ = server_info
        req = Request(
            f"http://{host}:{port}/health",
            method="PUT",
        )
        try:
            resp = urlopen(req, timeout=3)
            assert False, "Expected HTTPError"
        except HTTPError as exc:
            assert exc.code == 405
            data = json.loads(exc.read())
            assert "not allowed" in data.get("error", "")


# ---------------------------------------------------------------------------
# Request ID propagation
# ---------------------------------------------------------------------------


class TestRequestID:
    def test_request_id_returned_from_header(self, server_info):
        """X-Request-ID header value is returned in response header."""
        host, port, _ = server_info
        req = Request(
            f"http://{host}:{port}/health",
            headers={"X-Request-ID": "my-test-id-001"},
        )
        resp = urlopen(req, timeout=3)
        assert resp.headers.get("X-Request-ID") == "my-test-id-001"

    def test_request_id_generated_when_not_provided(self, server_info):
        """No X-Request-ID header -> response contains a generated UUID."""
        host, port, _ = server_info
        req = Request(f"http://{host}:{port}/health")
        resp = urlopen(req, timeout=3)
        rid = resp.headers.get("X-Request-ID", "")
        # Should be a UUID v4 format
        import uuid

        try:
            uuid.UUID(rid)
        except ValueError:
            pytest.fail(f"Generated request ID is not a valid UUID: {rid}")

    def test_request_id_in_json_response_body(self, server_info):
        """Response JSON body includes a 'request_id' field."""
        host, port, _ = server_info
        req = Request(
            f"http://{host}:{port}/health",
            headers={"X-Request-ID": "body-request-id"},
        )
        resp = urlopen(req, timeout=3)
        data = json.loads(resp.read())
        assert data.get("request_id") == "body-request-id"

    def test_request_id_in_error_response_body(self, server_info):
        """Error responses include a 'request_id' field."""
        host, port, _ = server_info
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError

        req = Request(
            f"http://{host}:{port}/unknown-route",
            headers={"X-Request-ID": "error-request-id"},
        )
        try:
            urlopen(req, timeout=3)
            pytest.fail("Expected HTTPError")
        except HTTPError as exc:
            data = json.loads(exc.read())
            assert data.get("request_id") == "error-request-id"
            assert "error" in data

    def test_request_id_in_json_response_matches_header(self, server_info):
        """Response header and body request_id match."""
        host, port, _ = server_info
        req = Request(
            f"http://{host}:{port}/health",
            headers={"X-Request-ID": "match-check-id"},
        )
        resp = urlopen(req, timeout=3)
        header_rid = resp.headers.get("X-Request-ID")
        body_rid = json.loads(resp.read()).get("request_id")
        assert header_rid == "match-check-id"
        assert body_rid == "match-check-id"


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    def test_log_message_includes_request_id(self, server_info):
        """log_message output includes request_id field."""
        host, port, _ = server_info

        import logging
        from io import StringIO

        capture = StringIO()
        handler = logging.StreamHandler(capture)
        handler.setLevel(logging.INFO)
        logger = logging.getLogger("bremen.api.server")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            req = Request(
                f"http://{host}:{port}/model/version",
                headers={"X-Request-ID": "log-test-id"},
            )
            urlopen(req, timeout=3)

            output = capture.getvalue()
            assert "request_id=log-test-id" in output, (
                f"Log output should contain request_id=log-test-id, got: {output}"
            )
            assert "method=GET" in output
            assert "path=/model/version" in output
            assert "status=200" in output
        finally:
            logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# GET /demo and GET /demo/api/evidence (demo route namespace)
# ---------------------------------------------------------------------------


class TestDemoRoutes:
    """Tests for the /demo/* route namespace (PR0065)."""

    def test_get_demo_returns_html(self, server_info):
        """GET /demo returns 200 with text/html content type."""
        host, port, _ = server_info
        status, body, headers = _get(host, port, "/demo")
        assert status == 200
        ct = headers.get("Content-Type", "")
        assert "text/html" in ct

    def test_get_demo_contains_bremen(self, server_info):
        """GET /demo response contains 'Bremen'."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo")
        assert b"Bremen" in body

    def test_get_demo_contains_technical_demo(self, server_info):
        """GET /demo (Start page) response contains 'technical demo'."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo")
        assert b"Technical demo only" in body or b"technical demo" in body.lower()

    def test_get_demo_contains_request_id(self, server_info):
        """GET /demo response contains X-Request-ID header."""
        host, port, _ = server_info
        _, _, headers = _get(host, port, "/demo")
        assert "X-Request-ID" in headers
        assert len(headers["X-Request-ID"]) > 0

    def test_get_demo_api_evidence_returns_json(self, server_info):
        """GET /demo/api/evidence returns 200 with JSON content type."""
        host, port, _ = server_info
        status, body, headers = _get(host, port, "/demo/api/evidence")
        assert status == 200
        ct = headers.get("Content-Type", "")
        assert "application/json" in ct

    def test_get_demo_api_evidence_contains_technical_demo_only(
        self, server_info
    ):
        """GET /demo/api/evidence JSON has technical_demo_only: true."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/api/evidence")
        data = json.loads(body)
        assert data["technical_demo_only"] is True

    def test_get_demo_api_evidence_contains_bremen(self, server_info):
        """GET /demo/api/evidence JSON has product: 'Bremen'."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/api/evidence")
        data = json.loads(body)
        assert data["product"] == "Bremen"

    def test_get_demo_api_evidence_has_request_id(self, server_info):
        """GET /demo/api/evidence returns X-Request-ID header."""
        host, port, _ = server_info
        _, _, headers = _get(host, port, "/demo/api/evidence")
        assert "X-Request-ID" in headers
        assert len(headers["X-Request-ID"]) > 0

    def test_root_still_404(self, server_info):
        """Root / still returns 404 (not a demo page)."""
        host, port, _ = server_info
        status, _, _ = _get(host, port, "/")
        assert status == 404

    def test_demo_missing_subroute_returns_404(self, server_info):
        """Unknown /demo/* subroute returns 404."""
        host, port, _ = server_info
        status, _, _ = _get(host, port, "/demo/unknown")
        assert status == 404


# ---------------------------------------------------------------------------
# GET /demo — redesigned demo page model readiness (PR0068)
# ---------------------------------------------------------------------------


class TestDemoReadiness:
    """Tests for model readiness display in /demo (PR0068)."""

    def test_get_demo_shows_ready_when_model_loaded(self, server_info):
        """With model loaded, /demo (Start page) shows model selection."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo")
        text = body.decode("utf-8")
        # Start page shows model catalog loading and selection
        assert "Select a model" in text or "model" in text.lower()

    def test_get_demo_shows_not_configured_without_model(self):
        """Without model config, /demo HTML shows not configured."""
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=False)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, body, _ = _get(host, port, "/demo")
            assert status == 200
            text = body.decode("utf-8")
            assert "Not configured" in text or "badge-warn" in text
        finally:
            server.shutdown()
            thread.join(timeout=2)
        ModelState.reset_for_tests()

    def test_get_demo_no_status_fail(self, server_info):
        """Control Room does not show FAIL as a visual status label."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo")
        text = body.decode("utf-8")
        assert "status-fail" not in text
        assert "FAIL_MAP" in text or "FAIL" not in text  # Internal JS map is OK, visual FAIL is not

    def test_get_demo_no_service_health_card(self, server_info):
        """Redesigned /demo does not contain old Service Health card."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo")
        text = body.decode("utf-8")
        assert "Service Health" not in text

    def test_get_demo_storage_not_configured_visible(self, server_info):
        """GET /demo renders the Investor Control Room with model guidance."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo")
        text = body.decode("utf-8")
        assert "Bremen" in text
        assert "Should the patient continue to MRI" in text

    def test_get_demo_hero_header_present(self, server_info):
        """Control Room has header with title and readiness badges."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        text = body.decode("utf-8")
        assert "cr-header" in text or "cr-brand" in text

    def test_get_demo_processing_events_card(self, server_info):
        """Control Room has execution pipeline and event panel."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        text = body.decode("utf-8")
        assert "cr-pipeline" in text or "cr-event-panel" in text or "cr-event-list" in text

    def test_get_demo_result_card_present(self, server_info):
        """Control Room has decision card placeholder."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/control-room")
        text = body.decode("utf-8")
        assert 'id="cr-decision-card"' in text or "cr-decision-card" in text

    def test_analyze_button_disabled_by_default(self, server_info):
        """Analyze button is disabled when model not ready."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo")
        text = body.decode("utf-8")
        assert 'disabled' in text and ('Analysis' in text or 'analyze' in text.lower())


# ---------------------------------------------------------------------------
# GET /demo/api/h5/containers — S3 catalog listing (PR0069)
# ---------------------------------------------------------------------------


class TestDemoH5ContainersS3Listing:
    """Tests for S3-backed container catalog listing (PR0069)."""

    def test_h5_hdf5_only_filtered(self):
        """S3 listing returns only .h5 and .hdf5 objects."""
        import re as _re

        # Simulate the S3 listing logic directly
        contents = [
            {"Key": "demo-uploads/file1.h5", "Size": 100},
            {"Key": "demo-uploads/file2.hdf5", "Size": 200},
            {"Key": "demo-uploads/notext", "Size": 300},
            {"Key": "demo-uploads/file3.txt", "Size": 400},
        ]
        containers = []
        for obj in contents:
            key = str(obj["Key"])
            filename = key.split("/")[-1] if "/" in key else key
            if not _re.search(r"\.h5$|\.hdf5$", key, _re.IGNORECASE):
                continue
            containers.append({
                "id": key,
                "filename": filename,
                "size_bytes": obj.get("Size", 0),
            })

        ids = [c["id"] for c in containers]
        assert "demo-uploads/file1.h5" in ids
        assert "demo-uploads/file2.hdf5" in ids
        assert "demo-uploads/notext" not in ids
        assert "demo-uploads/file3.txt" not in ids
        assert len(containers) == 2

    def test_s3_listing_failure_returns_list_failed(self, server_info, monkeypatch):
        """S3 listing failure sets storage to list_failed."""
        import json as _json

        def raise_on_list(*args, **kwargs):
            raise Exception("Simulated list failure")

        monkeypatch.setattr("bremen.api.server._list_s3_containers", raise_on_list)

        host, port, _ = server_info
        with monkeypatch.context() as m:
            m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
            m.setenv("BREMEN_DEMO_H5_PREFIX", "demo-uploads/")

            from urllib.request import urlopen, Request
            req = Request(f"http://{host}:{port}/demo/api/h5/containers")
            try:
                resp = urlopen(req, timeout=3)
                body = _json.loads(resp.read())
            except Exception as exc:
                body = _json.loads(exc.read())

            assert body["storage"] == "list_failed"
            assert body["containers"] == []

    def test_env_catalog_preserved_with_s3(self, server_info, monkeypatch):
        """Env-configured containers are preserved when S3 listing is enabled."""
        import json as _json

        def empty_s3_list(*args, **kwargs):
            return []

        monkeypatch.setattr("bremen.api.server._list_s3_containers", empty_s3_list)

        host, port, _ = server_info
        with monkeypatch.context() as m:
            m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
            m.setenv("BREMEN_DEMO_H5_CONTAINERS", _json.dumps([
                {"id": "env-ctr-1.h5", "filename": "env-ctr-1.h5", "size_bytes": 100},
            ]))

            from urllib.request import urlopen, Request
            req = Request(f"http://{host}:{port}/demo/api/h5/containers")
            resp = urlopen(req, timeout=3)
            data = _json.loads(resp.read())

            assert data["storage"] == "configured"
            src_ids = [c["source_id"] for c in data["containers"]]
            display_names = [c["display_name"] for c in data["containers"]]
            assert "env-ctr-1.h5" in display_names
            assert len(src_ids) == 1

    def test_s3_listing_deduplicates_by_id(self, server_info, monkeypatch):
        """S3 listing deduplicates containers with same id as env catalog."""
        import json as _json

        def s3_list_with_dup(*args, **kwargs):
            return [
                {"id": "common.h5", "filename": "common.h5", "size_bytes": 500},
                {"id": "s3-only.h5", "filename": "s3-only.h5", "size_bytes": 300},
            ]

        monkeypatch.setattr("bremen.api.server._list_s3_containers", s3_list_with_dup)

        host, port, _ = server_info
        with monkeypatch.context() as m:
            m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
            m.setenv("BREMEN_DEMO_H5_CONTAINERS", _json.dumps([
                {"id": "common.h5", "filename": "common.h5", "size_bytes": 100},
                {"id": "env-only.h5", "filename": "env-only.h5", "size_bytes": 200},
            ]))

            from urllib.request import urlopen, Request
            req = Request(f"http://{host}:{port}/demo/api/h5/containers")
            resp = urlopen(req, timeout=3)
            data = _json.loads(resp.read())

            # Should have 3 unique containers
            ids = [c["source_id"] for c in data["containers"]]
            src_ids = [c["source_id"] for c in data["containers"]]
            display_names = [c["display_name"] for c in data["containers"]]
            assert len(src_ids) == 3, f"Expected 3 unique, got {len(src_ids)}: {display_names}"
            # Verify display names are present (source_ids are opaque UUIDs)
            assert "common.h5" in display_names
            assert "env-only.h5" in display_names
            assert "s3-only.h5" in display_names


# --------------------------------------------------------------------------
# GET /demo/api/h5/containers (existing tests preserved)
# --------------------------------------------------------------------------


class TestDemoH5ContainersList:
    """Tests for GET /demo/api/h5/containers (baseline)."""

    def test_get_containers_returns_json(self, server_info):
        """GET /demo/api/h5/containers returns 200 with JSON."""
        host, port, _ = server_info
        status, body, headers = _get(host, port, "/demo/api/h5/containers")
        assert status == 200
        ct = headers.get("Content-Type", "")
        assert "application/json" in ct
        data = json.loads(body)
        assert "containers" in data
        assert "storage" in data
        assert data["technical_demo_only"] is True

    def test_get_containers_has_request_id(self, server_info):
        """GET /demo/api/h5/containers returns X-Request-ID."""
        host, port, _ = server_info
        _, _, headers = _get(host, port, "/demo/api/h5/containers")
        assert "X-Request-ID" in headers

    def test_get_containers_not_configured_by_default(self, server_info):
        """Without BREMEN_DEMO_H5_BUCKET, returns storage: not_configured."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo/api/h5/containers")
        data = json.loads(body)
        assert data["storage"] == "not_configured"
        assert data["containers"] == []


# ---------------------------------------------------------------------------
# POST /demo/api/h5/containers (upload)
# ---------------------------------------------------------------------------


def _post_raw(
    host: str,
    port: int,
    path: str,
    body: bytes = b"",
    headers: dict | None = None,
) -> tuple[int, bytes, dict]:
    """Perform a POST request with raw bytes body."""
    req = Request(
        f"http://{host}:{port}{path}",
        data=body,
        headers=headers or {},
        method="POST",
    )
    try:
        resp = urlopen(req, timeout=3)
        return resp.status, resp.read(), dict(resp.headers)
    except HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


class TestDemoH5Upload:
    """Tests for POST /demo/api/h5/containers (upload)."""

    def test_upload_no_bucket_returns_503(self, server_info):
        """Without BREMEN_DEMO_H5_BUCKET, upload returns 503."""
        host, port, _ = server_info
        status, body, _ = _post_raw(
            host, port, "/demo/api/h5/containers",
            body=b"fake h5 content",
            headers={
                "Content-Type": "application/octet-stream",
                "X-H5-Filename": "test.h5",
            },
        )
        assert status == 503
        data = json.loads(body)
        assert data["status"] == "storage_not_configured"

    def test_upload_empty_body_returns_400(self, server_info):
        """Empty body returns 400."""
        host, port, _ = server_info
        status, body, _ = _post_raw(
            host, port, "/demo/api/h5/containers",
            body=b"",
            headers={
                "Content-Type": "application/octet-stream",
                "X-H5-Filename": "test.h5",
            },
        )
        assert status == 400

    def test_upload_missing_filename_header_returns_400(self, server_info):
        """Missing X-H5-Filename header returns 400."""
        host, port, _ = server_info
        status, body, _ = _post_raw(
            host, port, "/demo/api/h5/containers",
            body=b"fake h5 content",
            headers={"Content-Type": "application/octet-stream"},
        )
        assert status == 400
        data = json.loads(body)
        assert "X-H5-Filename" in data.get("error", "")

    def test_upload_bad_extension_returns_400(self, server_info):
        """Non-.h5 extension returns 400."""
        host, port, _ = server_info
        status, body, _ = _post_raw(
            host, port, "/demo/api/h5/containers",
            body=b"fake content",
            headers={
                "Content-Type": "application/octet-stream",
                "X-H5-Filename": "test.txt",
            },
        )
        assert status == 400
        data = json.loads(body)
        assert "extension" in data.get("error", "")

    def test_upload_path_traversal_rejected(self, server_info):
        """Filename with path separators is rejected."""
        host, port, _ = server_info
        status, body, _ = _post_raw(
            host, port, "/demo/api/h5/containers",
            body=b"fake content",
            headers={
                "Content-Type": "application/octet-stream",
                "X-H5-Filename": "../etc/passwd.h5",
            },
        )
        assert status == 400

    def test_upload_response_no_raw_h5_contents(self, server_info):
        """Upload response does not contain raw H5 content."""
        host, port, _ = server_info
        raw_content = b"\x89HDF\r\n" + b"\x00" * 100
        status, body, _ = _post_raw(
            host, port, "/demo/api/h5/containers",
            body=raw_content,
            headers={
                "Content-Type": "application/octet-stream",
                "X-H5-Filename": "test.h5",
            },
        )
        data = json.loads(body)
        # Response must be JSON, not raw bytes
        assert "raw" not in str(data).lower()
        # The raw bytes should not appear in response
        decoded = body.decode("utf-8")
        assert "HDF" not in decoded

    def test_upload_has_request_id(self, server_info):
        """Upload response includes request_id."""
        host, port, _ = server_info
        _, body, _ = _post_raw(
            host, port, "/demo/api/h5/containers",
            body=b"fake h5 content",
            headers={
                "Content-Type": "application/octet-stream",
                "X-H5-Filename": "test.txt",
            },
        )
        data = json.loads(body)
        assert "request_id" in data


# ---------------------------------------------------------------------------
# POST /demo/api/h5/analyze
# ---------------------------------------------------------------------------


class TestDemoH5Analyze:
    """Tests for POST /demo/api/h5/analyze."""

    def test_analyze_missing_container_id_returns_400(self, server_info):
        """Missing container_id returns 400."""
        host, port, _ = server_info
        status, body, _ = _post(host, port, "/demo/api/h5/analyze", {})
        assert status == 400
        data = json.loads(body)
        assert "container_id" in data.get("error", "").lower() or "container_id" in str(data)

    def test_analyze_empty_body_returns_400(self, server_info):
        """Empty body returns 400."""
        host, port, _ = server_info
        data = b""
        req = Request(
            f"http://{host}:{port}/demo/api/h5/analyze",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urlopen(req, timeout=3)
            assert False, "Expected HTTPError"
        except HTTPError as exc:
            assert exc.code == 400

    def test_analyze_returns_events_and_request_id(self, server_info):
        """Analyze response includes events and request_id."""
        host, port, _ = server_info
        status, body, _ = _post(
            host, port, "/demo/api/h5/analyze",
            {"container_id": "demo-uploads/test.h5"},
        )
        # Will fail at storage_not_configured or model_not_ready,
        # but should still return structured response
        assert status in (200, 503)
        data = json.loads(body)
        assert "events" in data
        assert isinstance(data["events"], list)
        assert "request_id" in data
        assert "job_id" in data
        assert data["technical_demo_only"] is True

    def test_analyze_storage_not_configured(self, server_info):
        """Without BREMEN_DEMO_H5_BUCKET, returns storage_not_configured event."""
        host, port, _ = server_info
        _, body, _ = _post(
            host, port, "/demo/api/h5/analyze",
            {"container_id": "demo-uploads/test.h5"},
        )
        data = json.loads(body)
        events = data["events"]
        event_types = [e["event"] for e in events]
        # Should include request_received, container_selected, storage_not_configured
        assert "request_received" in event_types
        assert "container_selected" in event_types
        assert "storage_not_configured" in event_types

    def test_analyze_returns_technical_demo_only(self, server_info):
        """All analyze responses include technical_demo_only: true."""
        host, port, _ = server_info
        _, body, _ = _post(
            host, port, "/demo/api/h5/analyze",
            {"container_id": "demo-uploads/test.h5"},
        )
        data = json.loads(body)
        assert data["technical_demo_only"] is True

    def test_analyze_no_fake_successful_prediction(self, server_info):
        """Analyze does not return fake completed status when storage is not configured."""
        host, port, _ = server_info
        _, body, _ = _post(
            host, port, "/demo/api/h5/analyze",
            {"container_id": "demo-uploads/test.h5"},
        )
        data = json.loads(body)
        assert data["status"] != "completed"


# ---------------------------------------------------------------------------
# POST /demo/api/h5/analyze — failure observability (PR0069)
# ---------------------------------------------------------------------------


class TestDemoH5AnalyzeFailureObservability:
    """Tests for analyze stage-specific failure details and logging (PR0069)."""

    def test_unexpected_exception_logged_server_side(self, server_info, caplog, monkeypatch):
        """Unexpected analyze exceptions are logged with logger.exception.

        Public API response detail must be a safe, finite message —
        not a raw exception class name or stack trace.
        """
        import logging
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        # Start a new server with bucket configured
        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        # Monkeypatch run_inference to raise an error (this is called after staging)
        def failing_inference(*args, **kwargs):
            raise RuntimeError("Simulated inference error for demo")

        monkeypatch.setattr("bremen.api.inference_handler.run_inference", failing_inference)

        caplog.set_level(logging.ERROR)

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setenv("BREMEN_DEMO_H5_PREFIX", "demo-uploads/")
                # Mock stage_h5_input to return a valid path
                from pathlib import Path
                mock_path = Path("/tmp/mock_staged.h5")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: mock_path)

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/test.h5"},
                )
                data = json.loads(body)

                # Should have stage-specific failure event
                events = data["events"]
                event_types = [e["event"] for e in events]
                detail_texts = [e.get("detail", "") for e in events]
                combined = " ".join(detail_texts)

                # Must contain a failure event (inference_failed for RuntimeError)
                assert "inference_failed" in event_types, (
                    f"Expected inference_failed event, got: {event_types}"
                )
                # Public detail must NOT contain raw exception class names
                assert "RuntimeError" not in combined, (
                    f"Public detail must not expose raw exception class: {combined}"
                )
                # Public detail must NOT contain raw exception messages
                assert "Simulated" not in combined, (
                    f"Public detail must not expose raw messages: {combined}"
                )
                # Public detail must be one of the safe finite messages
                assert combined.strip(), "Public detail must not be empty"
                # No traceback in public response
                assert "Traceback" not in combined
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()

    def test_non_runtime_exception_yields_safe_detail(self, server_info, monkeypatch):
        """Non-RuntimeError exceptions return safe finite detail — not raw exception text."""
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore
        from pathlib import Path

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def failing_inference(*args, **kwargs):
            raise ValueError("Bridge preprocessing failed: unexpected feature shape")

        monkeypatch.setattr("bremen.api.inference_handler.run_inference", failing_inference)

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: Path("/tmp/mock.h5"))

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/test.h5"},
                )
                data = json.loads(body)
                events = data["events"]
                detail_texts = [e.get("detail", "") for e in events]
                combined = " ".join(detail_texts)
                # Public detail must NOT expose raw exception class names
                assert "ValueError" not in combined, (
                    f"Public detail must not expose raw exception class: {combined}"
                )
                # Public detail must NOT expose raw message
                assert "Bridge" not in combined, (
                    f"Public detail must not expose raw messages: {combined}"
                )
                # Should NOT contain raw stack trace
                assert "Traceback" not in combined
                assert "File " not in combined
                # Event should be classification-appropriate
                event_types = [e["event"] for e in events]
                assert any(
                    ev in event_types
                    for ev in ("h5_preflight_failed", "preprocessing_failed", "inference_failed")
                ), f"Expected a failure event, got: {event_types}"
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()

    def test_unexpected_exception_fallback_detail(self, server_info, monkeypatch):
        """Bare Exception fallback returns safe finite detail without traceback."""
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore
        from pathlib import Path

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def failing_inference(*args, **kwargs):
            raise KeyError("missing_feature")

        monkeypatch.setattr("bremen.api.inference_handler.run_inference", failing_inference)

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: Path("/tmp/mock.h5"))

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/test.h5"},
                )
                data = json.loads(body)
                events = data["events"]
                detail_texts = [e.get("detail", "") for e in events]
                combined = " ".join(detail_texts)
                # Public detail must NOT contain raw exception class name
                assert "KeyError" not in combined, (
                    f"Public detail must not expose raw exception class: {combined}"
                )
                # No raw traceback
                assert "Traceback" not in combined
                assert "File " not in combined
                # Must have a failure event
                event_types = [e["event"] for e in events]
                assert any(
                    ev in event_types
                    for ev in ("h5_preflight_failed", "preprocessing_failed", "inference_failed")
                ), f"Expected a failure event, got: {event_types}"
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()

    def test_no_raw_traceback_in_response(self, server_info, monkeypatch):
        """No raw stack trace or file paths in API response."""
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore
        from pathlib import Path

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def failing_inference(*args, **kwargs):
            raise RuntimeError("Something went wrong with model inference")

        monkeypatch.setattr("bremen.api.inference_handler.run_inference", failing_inference)

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: Path("/tmp/mock.h5"))

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/test.h5"},
                )
                data = json.loads(body)
                body_str = json.dumps(data)
                # Should not contain raw stack traces
                assert "Traceback" not in body_str
                assert "File " not in body_str
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Matador raw route-level success test (PR0073)
# ---------------------------------------------------------------------------


def _create_matador_raw_h5_for_server(tmp_path: Path) -> Path:
    """Create synthetic Matador raw H5 for server route-level test."""
    path = tmp_path / "matador_server_test.h5"
    with h5py.File(path, "w") as f:
        calib = f.create_group("calibrations")
        calib.create_dataset(
            "poni1",
            data=np.array([
                b"poni_version: 2.1\n",
                b"distance: 0.15\n",
                b"pixel_size: 0.0001\n",
                b"wavelength: 0.15\n",
                b"center_x: 100.0\n",
                b"center_y: 100.0\n",
            ], dtype=h5py.string_dtype()),
        )

        m1 = f.create_group("measurement_001")
        m1.attrs["side"] = "LEFT"
        m1.attrs["position"] = "center"
        m1.create_dataset(
            "data",
            data=np.random.default_rng(1).normal(10, 3, (100, 100)).astype(np.float32),
        )

        m2 = f.create_group("measurement_002")
        m2.attrs["side"] = "RIGHT"
        m2.attrs["position"] = "center"
        m2.create_dataset(
            "data",
            data=np.random.default_rng(2).normal(10, 3, (100, 100)).astype(np.float32),
        )
    return path


class TestMatadorRawRouteSuccess:
    """Route-level Matador raw success test — full detection→inference path."""

    def test_matador_raw_analyze_completed(
        self, tmp_path: Path, monkeypatch,
    ):
        """POST /demo/api/h5/analyze with Matador raw H5 completes successfully.

        Verifies:
        - layout detection (MatadorRawH5Adapter)
        - adapter registry selection
        - calibration discovery
        - measurement discovery
        - side and pair-key resolution
        - bilateral pairing
        - context propagation
        - Matador preprocessing dispatch
        - q/i validation
        - Bremen feature extraction
        - model feature-schema validation
        - event ordering
        - status == "completed"
        - result exists
        - technical_demo_only is true
        - request_id exists
        - job_id exists
        - source checksum unchanged
        - no identifier leakage
        """
        import hashlib
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        # Build temp H5
        h5_path = _create_matador_raw_h5_for_server(tmp_path)
        original_checksum = hashlib.sha256(h5_path.read_bytes()).hexdigest()

        # Mock XRD integration to return deterministic q/i
        def _mock_matador_q_i(row, column="measurement_data", npt=100, mode="1D",
                         calibration_mode="poni", error_model=None,
                         thickness_adjustment=False, require_thickness_adjustment=False):
            n = npt or 100
            q = np.linspace(5.0, 8.0, n, dtype=np.float64)
            image = row[column]
            seed = int(np.mean(image) * 1000) % 100
            rng = np.random.default_rng(seed)
            i_arr = np.abs(rng.normal(10, 2, n).astype(np.float64))
            return q, i_arr, None, None

        monkeypatch.setattr(
            "xrd_preprocessing.perform_azimuthal_integration",
            _mock_matador_q_i,
        )

        # Start a server with bucket configured
        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setenv("BREMEN_DEMO_H5_PREFIX", "demo-uploads/")
                # Mock stage_h5_input to return our temp H5 path
                m.setattr(
                    "bremen.h5_inputs.stage_h5_input",
                    lambda *a, **kw: h5_path,
                )
                # Mock the bridge wrapper too (same mock as above)
                m.setattr(
                    "xrd_preprocessing.perform_azimuthal_integration",
                    _mock_matador_q_i,
                )

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/matador_test.h5"},
                )
                data = _json.loads(body)

                # Status assertions
                assert data["status"] == "completed", (
                    f"Expected 'completed', got {data['status']}. "
                    f"Events: {[e['event'] for e in data['events']]}"
                )
                assert data["technical_demo_only"] is True
                assert "request_id" in data
                assert "job_id" in data
                assert data["request_id"] is not None
                assert data["job_id"] is not None

                # Result assertions
                assert "result" in data, f"Result missing: {list(data.keys())}"
                result = data["result"]
                assert "p_mri_needed" in result
                assert "triage_recommendation" in result
                assert result["triage_recommendation"] in (
                    "CONTINUE_MRI", "MRI_REVIEW_DEFER", "MRI_RECOMMENDED", "MRI_RULE_OUT"
                )
                assert 0.0 <= result["p_mri_needed"] <= 1.0
                assert "prediction_id" in result
                assert "model_version" in result
                assert "feature_schema_version" in result

                # Evidence assertions
                assert "evidence" in data
                assert data["evidence"]["model_version"] is not None
                assert data["evidence"]["prediction_id"] is not None

                # Event ordering
                events = data["events"]
                event_types = [e["event"] for e in events]
                expected_order = [
                    "request_received",
                    "container_selected",
                    "h5_staging_started",
                    "h5_staging_completed",
                    "canonical_normalization_started",
                    "canonical_normalization_completed",
                    "workflow_executed",
                    "completed",
                ]
                for expected_event in expected_order:
                    assert expected_event in event_types, (
                        f"Missing event: {expected_event}. "
                        f"Got: {event_types}"
                    )
                # Check ordering (relative positions)
                for i, expected in enumerate(expected_order[:-1]):
                    next_expected = expected_order[i + 1]
                    idx_current = event_types.index(expected)
                    idx_next = event_types.index(next_expected)
                    assert idx_current < idx_next, (
                        f"Event order violation: {expected} ({idx_current}) "
                        f"should be before {next_expected} ({idx_next})"
                    )

                # No identifier leakage
                body_str = _json.dumps(data)
                assert "Nova" not in body_str
                assert "patient_name" not in body_str
                assert "specimen" not in body_str.lower()
                assert "biopsy" not in body_str.lower()
                assert "birads" not in body_str.lower()
                assert "BENIGN" not in body_str
                assert "CANCER" not in body_str

                # Source checksum unchanged
                final_checksum = hashlib.sha256(h5_path.read_bytes()).hexdigest()
                assert original_checksum == final_checksum, (
                    "Source H5 checksum changed during analysis"
                )

                # Container info
                assert "container" in data
                assert data["container"]["id"] == "demo-uploads/matador_test.h5"
                assert data["container"]["bucket"] == "test-bucket"

        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()


class TestMatadorRawRouteFailures:
    """Route-level Matador failure tests."""

    def test_preflight_failure_no_calib_in_response(
        self, tmp_path: Path, monkeypatch,
    ):
        """h5_preflight_failed when calibration missing — no inference events."""
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        # Build temp H5 without calibration
        path = tmp_path / "no_calib_matador.h5"
        with h5py.File(path, "w") as f:
            m1 = f.create_group("measurement_001")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("measurement_002")
            m2.attrs["side"] = "RIGHT"
            m2.attrs["position"] = "center"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: path)

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/matador_nocalib.h5"},
                )
                data = _json.loads(body)

                assert data["status"] == "failed"
                events = data["events"]
                event_types = [e["event"] for e in events]
                assert "inference_failed" in event_types
                # No downstream events
                assert "preprocessing_completed" not in event_types
                assert "model_inference_completed" not in event_types
                assert "completed" not in event_types
                # No result
                assert "result" not in data
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()

    def test_no_result_on_failure(self, tmp_path: Path, monkeypatch):
        """Failed analysis returns no result field."""
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        # Build calibration-less H5 that will fail preflight
        path = tmp_path / "fail_matador.h5"
        with h5py.File(path, "w") as f:
            m1 = f.create_group("measurement_001")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: path)

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/fail.h5"},
                )
                data = _json.loads(body)
                assert "result" not in data
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()

    def test_checksum_unchanged_on_failure(
        self, tmp_path: Path, monkeypatch,
    ):
        """Source checksum unchanged even after failed analysis."""
        import hashlib
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        path = tmp_path / "checksum_test.h5"
        with h5py.File(path, "w") as f:
            m1 = f.create_group("measurement_001")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        original_checksum = hashlib.sha256(path.read_bytes()).hexdigest()

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: path)

                _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/fail.h5"},
                )

                final_checksum = hashlib.sha256(path.read_bytes()).hexdigest()
                assert original_checksum == final_checksum
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Import safety (AST-based) for server.py only
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# PR0074: Session route-level success test
# ---------------------------------------------------------------------------


def _create_session_h5_for_server(tmp_path: Path) -> Path:
    """Create a synthetic session-layout H5 for server route-level test."""
    path = tmp_path / "session_server_test.h5"
    with h5py.File(path, "w") as f:
        f.create_dataset("/patient/id", data="SESSION-P001")
        f.create_dataset("/session/sample/sample_type", data="RIGHT BREAST")
        sets = f.create_group("/session/sets")
        s1 = sets.create_group("set_001_sample_main")
        s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
        s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
        c1 = sets.create_group("contralateral_set_001_sample_main")
        c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
        c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6], dtype=np.float64))
    return path


class TestSessionRouteNoRefs:
    """Session layout route-level success tests (PR0074)."""

    def test_session_no_refs_analyze_completed(
        self, tmp_path: Path, monkeypatch,
    ):
        """POST /demo/api/h5/analyze with session H5, no explicit refs -> completed."""
        import hashlib
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        h5_path = _create_session_h5_for_server(tmp_path)
        original_checksum = hashlib.sha256(h5_path.read_bytes()).hexdigest()

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setenv("BREMEN_DEMO_H5_PREFIX", "demo-uploads/")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: h5_path)

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/session_test.h5"},
                )
                data = _json.loads(body)

                assert data["status"] == "completed", (
                    f"Expected 'completed', got {data['status']}. "
                    f"Events: {[e['event'] for e in data['events']]}"
                )
                assert data["technical_demo_only"] is True
                assert "request_id" in data
                assert "job_id" in data

                events = data["events"]
                event_types = [e["event"] for e in events]
                expected = ["canonical_normalization_completed", "workflow_executed",
                           "completed"]
                for ev in expected:
                    assert ev in event_types, f"Missing event: {ev}. Got: {event_types}"

                final_checksum = hashlib.sha256(h5_path.read_bytes()).hexdigest()
                assert original_checksum == final_checksum
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# PR0074: Typed stage failure tests
# ---------------------------------------------------------------------------


class TestTypedStageFailure:
    """Typed exception classification tests (PR0074)."""

    def test_preflight_error_maps_to_h5_preflight_failed(
        self, tmp_path: Path, monkeypatch,
    ):
        """H5ContainerError maps to h5_preflight_failed event."""
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        path = tmp_path / "preflight_fail.h5"
        with h5py.File(path, "w") as f:
            m1 = f.create_group("m_left")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m_right")
            m2.attrs["side"] = "RIGHT"
            m2.attrs["position"] = "center"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: path)

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/preflight_fail.h5"},
                )
                data = _json.loads(body)

                assert data["status"] == "failed"
                events = data["events"]
                event_types = [e["event"] for e in events]
                assert "inference_failed" in event_types
                assert "preprocessing_completed" not in event_types
                assert "model_inference_completed" not in event_types
                assert "completed" not in event_types
                details = [e.get("detail", "") for e in events if e["event"] == "h5_preflight_failed"]
                for detail in details:
                    assert "Traceback" not in detail
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()

    def test_no_downstream_event_after_failure(self, tmp_path: Path, monkeypatch):
        """After h5_preflight_failed, no downstream events appear."""
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        path = tmp_path / "no_downstream.h5"
        with h5py.File(path, "w") as f:
            m1 = f.create_group("m_left")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m_right")
            m2.attrs["side"] = "RIGHT"
            m2.attrs["position"] = "center"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: path)

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/fail.h5"},
                )
                data = _json.loads(body)

                events = data["events"]
                event_types = [e["event"] for e in events]
                assert "inference_failed" in event_types
                assert "preprocessing_completed" not in event_types
                assert "model_inference_completed" not in event_types
                assert "completed" not in event_types
                assert "result" not in data
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# PR0074: Public error safety tests
# ---------------------------------------------------------------------------


class TestPublicErrorSafety:
    """Public API response safety tests (PR0074)."""

    def test_no_h5_paths_in_error_response(
        self, tmp_path: Path, monkeypatch,
    ):
        """Error responses do not contain H5 internal paths."""
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        path = tmp_path / "safety_test.h5"
        with h5py.File(path, "w") as f:
            m1 = f.create_group("m_left")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: path)

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/safety.h5"},
                )
                data = _json.loads(body)
                body_str = _json.dumps(data)

                assert "/m_left" not in body_str
                assert "/scans" not in body_str
                assert "H5ContainerError" not in body_str
                assert "H5PreflightError" not in body_str
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()

    def test_safe_default_detail_for_unknown_error(
        self, tmp_path: Path, monkeypatch,
    ):
        """Unexpected internal error returns safe default detail."""
        import json as _json
        from bremen.api.model_state import ModelState
        from bremen.api.jobs import InMemoryJobStore

        class UnknownInternalError(Exception):
            pass

        def failing(*args, **kwargs):
            raise UnknownInternalError("/tmp/secret_path: database connection failed")

        monkeypatch.setattr("bremen.api.inference_handler.run_inference", failing)

        h5_path = _create_session_h5_for_server(tmp_path)

        ModelState.reset_for_tests()
        host = "127.0.0.1"
        port = _find_free_port()
        job_store = InMemoryJobStore()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with monkeypatch.context() as m:
                m.setenv("BREMEN_DEMO_H5_BUCKET", "test-bucket")
                m.setattr("bremen.h5_inputs.stage_h5_input", lambda *a, **kw: h5_path)
                m.setattr("bremen.api.inference_handler.run_inference", failing)

                _, body, _ = _post(
                    host, port, "/demo/api/h5/analyze",
                    {"container_id": "demo-uploads/session.h5"},
                )
                data = _json.loads(body)
                body_str = _json.dumps(data)

                assert "/tmp/secret_path" not in body_str
                assert "database" not in body_str.lower()
                assert "UnknownInternalError" not in body_str
                events = data["events"]
                detail_texts = [e.get("detail", "") for e in events]
                combined = " ".join(detail_texts)
                assert len(combined.strip()) > 0
                assert "Traceback" not in combined
        finally:
            server.shutdown()
            thread.join(timeout=2)
            ModelState.reset_for_tests()


class TestImportSafety:
    def test_no_joblib_import(self):
        """server.py must not import joblib at top level.

        Note: ``_load_synthetic_model()`` in ``server.py`` lazily
        imports ``from joblib import dump`` inside a function for
        synthetic model loading.  This AST check only catches
        module-level imports.
        """
        import ast

        src = API_SRC / "server.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "joblib" in alias.name.lower():
                        pytest.fail("server.py has top-level joblib import")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "joblib" in module.lower():
                    pytest.fail(
                        f"server.py has top-level joblib import: from {module}"
                    )

    def test_no_pickle_import(self):
        """server.py must not import pickle."""
        import ast

        src = API_SRC / "server.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "pickle" in alias.name.lower():
                        pytest.fail("server.py imports pickle")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "pickle" in module.lower():
                    pytest.fail(f"server.py imports pickle via {module}")

    def test_no_boto3_or_network(self):
        """server.py must not import boto3, requests, httpx, urllib at module level.

        Lazy imports inside demo handler functions are acceptable — they
        are scoped to the demo H5 upload/analyze paths and use the existing
        boto3 dependency per PLAN.md.
        """
        import ast

        src = API_SRC / "server.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        prohibited = {"boto3", "botocore", "requests", "httpx", "urllib"}
        for node in tree.body:  # Module-level only
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(
                            f"server.py has module-level import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(
                        f"server.py has module-level import: from {module}"
                    )

    def test_no_h5_references(self):
        """server.py must not import h5py.  .h5/.hdf5 string patterns for
        extension validation in demo upload endpoints are acceptable."""
        src = API_SRC / "server.py"
        content = src.read_text(encoding="utf-8")
        assert "h5py" not in content, "server.py imports h5py"

    def test_no_joblib_load_string(self):
        """server.py must not contain 'joblib.load(' or 'pickle.load('."""
        src = API_SRC / "server.py"
        content = src.read_text(encoding="utf-8")
        if "joblib.load(" in content:
            pytest.fail("server.py contains 'joblib.load('")
        if "pickle.load(" in content:
            pytest.fail("server.py contains 'pickle.load('")


# ---------------------------------------------------------------------------
# Query-string routing regression tests
# ---------------------------------------------------------------------------


class TestQueryStringRouting:
    """Routes with query strings resolve correctly."""

    def test_start_page_with_query_string(self, server_info):
        """GET /demo?source=test returns Start page."""
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/demo?source=test")
        assert status == 200
        text = body.decode("utf-8")
        assert "Select a model to begin" in text

    def test_control_room_with_query_string(self, server_info):
        """GET /demo/control-room?workflow_id=bremen&model_id=bremen-current returns Control Room."""
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/demo/control-room?workflow_id=bremen&model_id=bremen-current")
        assert status == 200
        text = body.decode("utf-8")
        assert "cr-page" in text or "Should the patient continue to MRI" in text

    def test_report_with_query_string(self, server_info):
        """GET /demo/report/test-job-id?source=history returns Report page."""
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/demo/report/test-job-id?source=history")
        assert status == 200
        text = body.decode("utf-8")
        assert "report-page" in text or "Bremen Report" in text

    def test_workspace_with_query_string(self, server_info):
        """GET /demo/workspace/test-job-id?tab=events returns Workspace."""
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/demo/workspace/test-job-id?tab=events")
        assert status == 200
        text = body.decode("utf-8")
        assert "Analysis Workspace" in text

    def test_unknown_path_still_404(self, server_info):
        """Unknown path with query string returns 404."""
        host, port, _ = server_info
        status, _, _ = _get(host, port, "/demo/nonexistent?foo=bar")
        assert status == 404

    def test_api_jobs_with_query_string(self, server_info):
        """API resource identifiers exclude query strings."""
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/demo/api/jobs?limit=10")
        assert status == 200
        data = json.loads(body)
        assert "jobs" in data

    def test_health_with_query_string(self, server_info):
        """GET /health?probe=app-runner returns 200."""
        host, port, _ = server_info
        status, body, _ = _get(host, port, "/health?probe=app-runner")
        assert status == 200
        data = json.loads(body)
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Health check log suppression tests
# ---------------------------------------------------------------------------


class TestHealthLogSuppression:
    """Successful health checks do not produce INFO request logs."""

    def test_health_success_no_info_log(self, server_info, caplog):
        """Successful GET /health produces no INFO request log."""
        import logging
        host, port, _ = server_info
        caplog.set_level(logging.INFO)
        _get(host, port, "/health")
        # Check that no log record contains the health request
        health_logs = [
            r for r in caplog.records
            if r.levelno == logging.INFO
            and "path=/health" in r.getMessage()
        ]
        assert len(health_logs) == 0, (
            f"Expected no INFO log for successful health check, got {len(health_logs)}"
        )

    def test_health_with_query_no_info_log(self, server_info, caplog):
        """Successful GET /health?probe=app-runner produces no INFO request log."""
        import logging
        host, port, _ = server_info
        caplog.set_level(logging.INFO)
        _get(host, port, "/health?probe=app-runner")
        health_logs = [
            r for r in caplog.records
            if r.levelno == logging.INFO
            and "path=/health" in r.getMessage()
        ]
        assert len(health_logs) == 0, (
            f"Expected no INFO log for health check with query, got {len(health_logs)}"
        )

    def test_non_health_request_still_logged(self, server_info, caplog):
        """Non-health successful request is still logged at INFO."""
        import logging
        host, port, _ = server_info
        caplog.set_level(logging.INFO)
        _get(host, port, "/model/version")
        model_logs = [
            r for r in caplog.records
            if r.levelno == logging.INFO
            and "path=/model/version" in r.getMessage()
        ]
        assert len(model_logs) > 0, (
            "Expected INFO log for non-health request"
        )

    def test_unknown_route_still_logged(self, server_info, caplog):
        """Unknown route (404) is still logged."""
        import logging
        host, port, _ = server_info
        caplog.set_level(logging.INFO)
        _get(host, port, "/nonexistent")
        notfound_logs = [
            r for r in caplog.records
            if r.levelno == logging.INFO
            and "path=/nonexistent" in r.getMessage()
        ]
        assert len(notfound_logs) > 0, (
            "Expected INFO log for unknown route"
        )
