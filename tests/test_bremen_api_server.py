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
    host = "127.0.0.1"
    port = _find_free_port()
    job_store = InMemoryJobStore()
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
        # Model was loaded at server startup — it should be configured
        assert data["model_configured"] is True
        assert data["model_status"] == "configured"

    def test_model_version_content_type(self, server_info):
        host, port, _ = server_info
        _, _, headers = _get(host, port, "/model/version")
        assert "application/json" in headers.get("Content-Type", "")

    def test_model_version_configured(self, server_info):
        """Test GET /model/version with env set to configured state."""
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

    def test_submit_returns_503_when_model_not_ready(self, no_model_server_info):
        """POST /predictions returns 503 when model is not loaded."""
        host, port, _ = no_model_server_info
        payload = {
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
        }
        status, body, _ = _post(host, port, "/predictions", payload)
        assert status == 503
        data = json.loads(body)
        assert "not loaded" in data.get("error", "")


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
        """server.py must not import boto3, requests, httpx, urllib."""
        import ast

        src = API_SRC / "server.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        prohibited = {"boto3", "botocore", "requests", "httpx", "urllib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(f"server.py imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(f"server.py imports {module}")

    def test_no_h5_references(self):
        """server.py must not reference .h5, .hdf5, or h5py."""
        src = API_SRC / "server.py"
        content = src.read_text(encoding="utf-8")
        for ref in [".h5", ".hdf5", "h5py"]:
            if ref in content:
                pytest.fail(f"server.py contains H5 reference: {ref}")

    def test_no_joblib_load_string(self):
        """server.py must not contain 'joblib.load(' or 'pickle.load('."""
        src = API_SRC / "server.py"
        content = src.read_text(encoding="utf-8")
        if "joblib.load(" in content:
            pytest.fail("server.py contains 'joblib.load('")
        if "pickle.load(" in content:
            pytest.fail("server.py contains 'pickle.load('")
