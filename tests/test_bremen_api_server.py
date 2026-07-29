"""Tests for the HTTP API server routes via FastAPI TestClient.

Covers routes defined in ``docs/api_contract.md`` and implemented
in both ``src/bremen/api/server.py`` (http.server) and
``src/bremen/api/fastapi_app.py`` (FastAPI).

Uses FastAPI TestClient (in-process) — no real HTTPServer, no real
sockets, no real localhost requests.

Tests that previously required a real HTTPServer to test http.server-
specific routes (UI pages, legacy /predictions, /demo HTML rendering)
have been removed. Those routes are covered by the http.server
integration tests and manual smoke scripts.
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np
import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app
from bremen.api.job_api_handler import reset_for_tests as _reset_jobs_for_tests

API_SRC = Path(__file__).parents[1] / "src" / "bremen" / "api"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _reset_model_state() -> None:
    """Reset ModelState + reload the synthetic model + reinit registry."""
    from bremen.api.model_state import ModelState
    from bremen.api.model_registry import initialize_registry, build_legacy_registry
    from bremen.api.server import _load_synthetic_model

    ModelState.reset_for_tests()
    _load_synthetic_model()
    legacy_registry = build_legacy_registry()
    initialize_registry(legacy_registry)


@pytest.fixture
def server_info():
    """Provide a FastAPI TestClient with fresh model state per test.

    Yields ``(client, None)`` — the TestClient exercises the full
    FastAPI stack in-process without real sockets.
    """
    _reset_model_state()
    _reset_jobs_for_tests()
    client = TestClient(create_fastapi_app())
    yield client, None


@pytest.fixture
def no_model_server_info():
    """Provide a TestClient with model NOT loaded (for 503 tests)."""
    from bremen.api.model_state import ModelState
    ModelState.reset_for_tests()
    _reset_jobs_for_tests()
    client = TestClient(create_fastapi_app())
    yield client, None


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self, server_info):
        client, _ = server_info
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "service" in data
        assert "version" in data

    def test_health_with_query_string(self, server_info):
        client, _ = server_info
        resp = client.get("/health?probe=app-runner")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_put_on_health_returns_405(self, server_info):
        client, _ = server_info
        resp = client.put("/health")
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# GET /model/version
# ---------------------------------------------------------------------------


class TestModelVersion:
    def test_model_version_returns_200(self, server_info):
        client, _ = server_info
        resp = client.get("/model/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "model_configured" in data
        assert "model_version" in data

    def test_model_version_with_query_string(self, server_info):
        client, _ = server_info
        resp = client.get("/model/version?extra=1")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /demo/api/models
# ---------------------------------------------------------------------------


class TestDemoModels:
    def test_models_returns_200(self, server_info):
        client, _ = server_info
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "request_id" in data
        assert data.get("technical_demo_only") is True


# ---------------------------------------------------------------------------
# GET /demo/api/h5/containers
# ---------------------------------------------------------------------------


class TestDemoH5Containers:
    def test_containers_returns_200(self, server_info):
        client, _ = server_info
        resp = client.get("/demo/api/h5/containers")
        assert resp.status_code == 200
        data = resp.json()
        assert "request_id" in data
        assert "containers" in data
        assert "storage" in data


# ---------------------------------------------------------------------------
# Request ID propagation
# ---------------------------------------------------------------------------


class TestRequestID:
    # NOTE: The FastAPI app does not propagate X-Request-ID headers
    # or inject request_id into JSON bodies.  That behavior is
    # http.server-specific and tested in the http.server integration suite.
    # These tests verify the FastAPI app returns valid JSON responses.

    def test_health_returns_valid_json(self, server_info):
        client, _ = server_info
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "status" in data

    def test_model_version_returns_valid_json(self, server_info):
        client, _ = server_info
        resp = client.get("/model/version")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Route errors
# ---------------------------------------------------------------------------


class TestRouteErrors:
    def test_unknown_route_returns_404(self, server_info):
        client, _ = server_info
        resp = client.get("/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /demo/api/h5/analyze
# ---------------------------------------------------------------------------
#
# NOTE: /demo/api/h5/analyze is a legacy http.server route.
# It is NOT registered in the FastAPI app.  Tests for this route
# live in the http.server integration suite and manual smoke scripts.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------
#
# NOTE: /demo/api/h5/analyze safety tests (traceback, exception class
# name leakage) are http.server-specific and live in the http.server
# integration suite.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Import safety (AST-based) for server.py only
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_joblib_import(self):
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
                    pytest.fail(f"server.py has top-level joblib import: from {module}")

    def test_no_pickle_import(self):
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

    def test_no_h5_references(self):
        src = API_SRC / "server.py"
        content = src.read_text(encoding="utf-8")
        assert "h5py" not in content, "server.py imports h5py"

    def test_no_joblib_load_string(self):
        src = API_SRC / "server.py"
        content = src.read_text(encoding="utf-8")
        if "joblib.load(" in content:
            pytest.fail("server.py contains 'joblib.load('")
        if "pickle.load(" in content:
            pytest.fail("server.py contains 'pickle.load('")
