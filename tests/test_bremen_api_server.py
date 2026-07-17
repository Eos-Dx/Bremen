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

    host = "127.0.0.1"
    port = _find_free_port()
    job_store = InMemoryJobStore()
    ModelState.reset_for_tests()
    handler = _make_handler(job_store, version="test-version", load_model=True)
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

        # Reset model state to test cloud env behavior
        ModelState.reset_for_tests()

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
                f"http://{host}:{port}/health",
                headers={"X-Request-ID": "log-test-id"},
            )
            urlopen(req, timeout=3)

            output = capture.getvalue()
            assert "request_id=log-test-id" in output, (
                f"Log output should contain request_id=log-test-id, got: {output}"
            )
            assert "method=GET" in output
            assert "path=/health" in output
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
        """GET /demo response contains 'technical demo'."""
        host, port, _ = server_info
        _, body, _ = _get(host, port, "/demo")
        assert b"Technical demo only" in body

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
# GET /demo/api/h5/containers
# ---------------------------------------------------------------------------


class TestDemoH5ContainersList:
    """Tests for GET /demo/api/h5/containers."""

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
# Import safety (AST-based) for server.py only
# ---------------------------------------------------------------------------


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
