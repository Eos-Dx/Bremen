"""Tests for FastAPI Phase 1 foundation.

Tests cover:

- ``create_fastapi_app`` exists and returns a FastAPI app.
- ``GET /health`` returns 200 with expected safe shape.
- ``GET /model/version`` returns 200 with expected safe shape.
- No raw exception traces, filesystem paths, S3 bucket/key values,
  credentials, JWT secrets, or env values are exposed.
- Production Dockerfile ENTRYPOINT/CMD unchanged.
- Existing http.server api tests still pass.
- Governance tests now allow isolated FastAPI foundation but
  protect the production http.server path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Conditionally import FastAPI test client
try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None  # type: ignore[assignment,misc]

from bremen.api.fastapi_app import create_fastapi_app

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"


# ===================================================================
# Test if FastAPI is available
# ===================================================================


def test_fastapi_available() -> None:
    """FastAPI must be installed for phase 1 tests."""
    import fastapi  # noqa: F401, PLC0415


def test_uvicorn_available() -> None:
    """Uvicorn must be installed for phase 1."""
    import uvicorn  # noqa: F401, PLC0415


# ===================================================================
# Test create_fastapi_app
# ===================================================================


class TestCreateFastAPIApp:
    def test_create_fastapi_app_exists(self) -> None:
        """create_fastapi_app is callable and returns a FastAPI app."""
        app = create_fastapi_app()
        assert app is not None
        assert "FastAPI" in app.title

    def test_create_fastapi_app_with_version(self) -> None:
        """A version string can be passed through."""
        app = create_fastapi_app(version="1.2.3")
        assert app is not None


# ===================================================================
# Test GET /health via TestClient
# ===================================================================


class TestHealthRoute:
    def test_health_returns_200(self) -> None:
        """GET /health returns 200."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_expected_fields(self) -> None:
        """GET /health returns expected safe fields."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/health")
        body = resp.json()
        assert isinstance(body, dict)
        assert "status" in body
        assert "service" in body
        assert "version" in body
        assert "timestamp" in body
        assert "model_ready" in body
        assert body["status"] == "ok"

    def test_health_no_raw_exception_traces(self) -> None:
        """GET /health does not expose raw exception traces."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/health")
        text = resp.text
        assert "Traceback" not in text
        assert "File \"" not in text
        assert "line" not in text

    def test_health_no_filesystem_paths(self) -> None:
        """GET /health does not expose filesystem paths."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/health")
        text = resp.text
        assert "/Users/" not in text
        assert "/home/" not in text
        assert "/tmp/" not in text

    def test_health_no_s3_bucket_keys(self) -> None:
        """GET /health does not expose raw S3 bucket/key values."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/health")
        text = resp.text
        assert "s3://" not in text

    def test_health_no_credentials(self) -> None:
        """GET /health does not expose credentials or secrets."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/health")
        text = resp.text
        assert "AKIA" not in text
        assert "secret" not in text.lower()
        assert "SECRET_" not in text

    def test_health_model_ready_is_bool(self) -> None:
        """model_ready is a boolean."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/health")
        body = resp.json()
        assert isinstance(body["model_ready"], bool)

    def test_health_timestamp_is_string(self) -> None:
        """timestamp is a string."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/health")
        body = resp.json()
        assert isinstance(body["timestamp"], str)
        assert "T" in body["timestamp"]  # ISO-8601


# ===================================================================
# Test GET /model/version via TestClient
# ===================================================================


class TestModelVersionRoute:
    def test_model_version_returns_200(self) -> None:
        """GET /model/version returns 200."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/model/version")
        assert resp.status_code == 200

    def test_model_version_has_expected_fields(self) -> None:
        """GET /model/version returns expected safe fields."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/model/version")
        body = resp.json()
        assert isinstance(body, dict)
        # All ModelVersionResponse fields
        assert "model_configured" in body
        assert "model_version" in body
        assert "model_checksum" in body
        assert "feature_schema_version" in body
        assert "threshold_version" in body
        assert "threshold_value" in body
        assert "qc_criteria_version" in body
        assert "model_status" in body

    def test_model_version_no_raw_exception_traces(self) -> None:
        """GET /model/version does not expose raw exception traces."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/model/version")
        text = resp.text
        assert "Traceback" not in text
        assert "File \"" not in text
        assert "line" not in text

    def test_model_version_no_filesystem_paths(self) -> None:
        """GET /model/version does not expose filesystem paths."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/model/version")
        text = resp.text
        assert "/Users/" not in text
        assert "/home/" not in text
        assert "/tmp/" not in text

    def test_model_version_no_s3_bucket_keys(self) -> None:
        """GET /model/version does not expose raw S3 bucket/key values."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/model/version")
        text = resp.text
        assert "s3://" not in text

    def test_model_version_no_credentials(self) -> None:
        """GET /model/version does not expose credentials or secrets."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/model/version")
        text = resp.text
        assert "AKIA" not in text
        assert "secret" not in text.lower()
        assert "SECRET_" not in text

    def test_model_status_is_string(self) -> None:
        """model_status is a string."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/model/version")
        body = resp.json()
        assert isinstance(body["model_status"], str)

    def test_model_configured_is_bool(self) -> None:
        """model_configured is a bool."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/model/version")
        body = resp.json()
        assert isinstance(body["model_configured"], bool)


# ===================================================================
# Test coexisting endpoints are unchanged
# ===================================================================


class TestCoexistence:
    def test_health_and_model_version_distinct(self) -> None:
        """GET /health and GET /model/version return distinct responses."""
        app = create_fastapi_app()
        client = TestClient(app)
        health_resp = client.get("/health")
        mv_resp = client.get("/model/version")
        assert health_resp.status_code == 200
        assert mv_resp.status_code == 200
        assert health_resp.json() != mv_resp.json()

    def test_unknown_route_returns_404(self) -> None:
        """An unknown FastAPI route returns 404 (not 500)."""
        app = create_fastapi_app()
        client = TestClient(app)
        resp = client.get("/no/such/route")
        assert resp.status_code == 404


# ===================================================================
# Test production Dockerfile unchanged
# ===================================================================


class TestProductionDockerfileUnchanged:
    """Production Dockerfile ENTRYPOINT and CMD must remain unchanged."""

    def test_dockerfile_entrypoint_unchanged(self) -> None:
        """Production ENTRYPOINT remains python -m bremen."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert 'ENTRYPOINT ["python", "-m", "bremen"]' in content, (
            "Production ENTRYPOINT must remain unchanged"
        )

    def test_dockerfile_cmd_unchanged(self) -> None:
        """Production CMD remains serve --host 0.0.0.0 --port 8080."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert 'CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]' in content, (
            "Production CMD must remain unchanged"
        )

    def test_dockerfile_base_from_unchanged(self) -> None:
        """Base image remains python:3.13-slim."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "FROM python:3.13-slim AS base" in content, (
            "Base image must remain unchanged"
        )


# ===================================================================
# Test that FastAPI app does not import prohibited modules
# ===================================================================


class TestFastAPIModuleSafety:
    """The FastAPI app module stays within safe boundaries."""

    def test_no_boto3_import(self) -> None:
        """FastAPI app module does not import boto3."""
        import ast
        source = Path(__file__).resolve().parents[1] / "src" / "bremen" / "api" / "fastapi_app.py"
        source_text = source.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "boto3" in alias.name.split(".")[0].lower():
                        pytest.fail(f"FastAPI app imports boto3: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "boto3" in module.split(".")[0].lower():
                    pytest.fail(f"FastAPI app imports boto3: {module}")

    def test_no_h5py_import(self) -> None:
        """FastAPI app module does not import h5py."""
        import ast
        source = Path(__file__).resolve().parents[1] / "src" / "bremen" / "api" / "fastapi_app.py"
        source_text = source.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "h5py" in alias.name.split(".")[0].lower():
                        pytest.fail(f"FastAPI app imports h5py: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "h5py" in module.split(".")[0].lower():
                    pytest.fail(f"FastAPI app imports h5py: {module}")
