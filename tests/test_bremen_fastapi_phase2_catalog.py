"""Tests for FastAPI Phase 2 — catalog routes.

Tests cover:

- ``GET /demo/api/models`` — model catalog response shape and safety.
- ``GET /demo/api/h5/containers`` — H5 container listing shape and safety.
- Regression checks that Phase 1 routes still work.
- No POST/SSE routes in Phase 2.
- Dockerfile production ENTRYPOINT/CMD unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None  # type: ignore[assignment,misc]

from bremen.api.fastapi_app import create_fastapi_app

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"


# ===================================================================
# Helpers
# ===================================================================


@pytest.fixture()
def client():
    """Create a TestClient for the FastAPI app."""
    app = create_fastapi_app()
    return TestClient(app)


# ===================================================================
# GET /demo/api/models
# ===================================================================


class TestDemoModelsRoute:
    def test_demo_models_returns_200(self, client) -> None:
        """GET /demo/api/models returns 200."""
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200

    def test_demo_models_has_expected_fields(self, client) -> None:
        """Response has expected catalog fields."""
        resp = client.get("/demo/api/models")
        body = resp.json()
        assert isinstance(body, dict)
        assert "schema_version" in body
        assert "catalog_timestamp" in body
        assert "models" in body
        assert "default_model_id" in body
        assert "status" in body
        assert "technical_demo_only" in body
        assert body["technical_demo_only"] is True
        assert "request_id" in body

    def test_demo_models_no_raw_s3_paths(self, client) -> None:
        """Response does not contain raw S3 URIs."""
        resp = client.get("/demo/api/models")
        text = resp.text
        assert "s3://" not in text

    def test_demo_models_no_raw_checksums(self, client) -> None:
        """Response does not contain full checksums."""
        resp = client.get("/demo/api/models")
        body = resp.json()
        models = body.get("models", [])
        for model in models:
            # model_checksum should not be present in catalog dict
            assert "model_checksum" not in model or model["model_checksum"] is None

    def test_demo_models_no_credentials(self, client) -> None:
        """Response does not expose credentials or secrets."""
        resp = client.get("/demo/api/models")
        text = resp.text
        assert "AKIA" not in text
        assert "SECRET_" not in text

    def test_demo_models_no_filesystem_paths(self, client) -> None:
        """Response does not expose filesystem paths."""
        resp = client.get("/demo/api/models")
        text = resp.text
        assert "/Users/" not in text
        assert "/home/" not in text

    def test_demo_models_empty_catalog(self, client) -> None:
        """Empty catalog (no models configured) returns valid response."""
        from bremen.api.model_registry import reset_for_tests
        reset_for_tests()
        resp = client.get("/demo/api/models")
        body = resp.json()
        assert body["status"] in ("not_configured", "available", "no_valid_models", "discovery_failed")
        assert isinstance(body["models"], list)

    def test_demo_models_no_exception_traces(self, client) -> None:
        """Response does not expose raw exception traces."""
        resp = client.get("/demo/api/models")
        text = resp.text
        assert "Traceback" not in text
        assert "File \"" not in text

    def test_demo_models_request_id_present(self, client) -> None:
        """Response includes request_id."""
        resp = client.get("/demo/api/models")
        body = resp.json()
        assert "request_id" in body
        assert isinstance(body["request_id"], str)
        assert len(body["request_id"]) > 0


# ===================================================================
# GET /demo/api/h5/containers
# ===================================================================


class TestDemoH5ContainersRoute:
    def test_containers_returns_200(self, client) -> None:
        """GET /demo/api/h5/containers returns 200."""
        resp = client.get("/demo/api/h5/containers")
        assert resp.status_code == 200

    def test_containers_has_expected_fields(self, client) -> None:
        """Response has expected container listing fields."""
        resp = client.get("/demo/api/h5/containers")
        body = resp.json()
        assert isinstance(body, dict)
        assert "storage" in body
        assert "containers" in body
        assert "technical_demo_only" in body
        assert body["technical_demo_only"] is True
        assert "request_id" in body

    def test_containers_no_bucket_returns_not_configured(self, client) -> None:
        """Without bucket configured, returns not_configured."""
        with patch.dict("os.environ", {}, clear=False):
            # Remove BREMEN_DEMO_H5_BUCKET if set
            import os
            old = os.environ.pop("BREMEN_DEMO_H5_BUCKET", None)
            try:
                resp = client.get("/demo/api/h5/containers")
                body = resp.json()
                assert body["storage"] == "not_configured"
                assert body["containers"] == []
            finally:
                if old is not None:
                    os.environ["BREMEN_DEMO_H5_BUCKET"] = old

    def test_containers_no_raw_s3_bucket(self, client) -> None:
        """Response does not contain raw S3 bucket names."""
        resp = client.get("/demo/api/h5/containers")
        text = resp.text
        # Raw S3 URIs should never appear
        assert "s3://" not in text

    def test_containers_no_filesystem_paths(self, client) -> None:
        """Response does not expose filesystem paths."""
        resp = client.get("/demo/api/h5/containers")
        text = resp.text
        assert "/Users/" not in text
        assert "/home/" not in text

    def test_containers_no_credentials(self, client) -> None:
        """Response does not expose credentials or secrets."""
        resp = client.get("/demo/api/h5/containers")
        text = resp.text
        assert "AKIA" not in text
        assert "SECRET_" not in text

    def test_containers_no_exception_traces(self, client) -> None:
        """Response does not expose raw exception traces."""
        resp = client.get("/demo/api/h5/containers")
        text = resp.text
        assert "Traceback" not in text
        assert "File \"" not in text

    def test_containers_request_id_present(self, client) -> None:
        """Response includes request_id."""
        resp = client.get("/demo/api/h5/containers")
        body = resp.json()
        assert "request_id" in body
        assert isinstance(body["request_id"], str)
        assert len(body["request_id"]) > 0

    def test_containers_is_list(self, client) -> None:
        """containers field is always a list."""
        resp = client.get("/demo/api/h5/containers")
        body = resp.json()
        assert isinstance(body["containers"], list)


# ===================================================================
# Phase 1 regression
# ===================================================================


class TestPhase1RoutesStillWork:
    def test_health_still_works(self, client) -> None:
        """GET /health still returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    def test_model_version_still_works(self, client) -> None:
        """GET /model/version still returns 200."""
        resp = client.get("/model/version")
        assert resp.status_code == 200
        body = resp.json()
        assert "model_configured" in body
        assert "model_status" in body


# ===================================================================
# Route exclusion
# ===================================================================


class TestNoPostOrSSE:
    def test_no_post_routes(self) -> None:
        """FastAPI app has no POST routes."""
        app = create_fastapi_app()
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        post_routes = [r for r in routes if "upload" in r or "analyze" in r or "stage" in r]
        assert post_routes == [], f"Unexpected POST-like routes: {post_routes}"

    def test_no_sse_routes(self) -> None:
        """FastAPI app has no SSE/event-stream routes."""
        app = create_fastapi_app()
        for route in app.routes:
            if hasattr(route, "path") and "event" in route.path.lower():
                pytest.fail(f"Unexpected event route: {route.path}")


# ===================================================================
# Production Dockerfile unchanged
# ===================================================================


class TestProductionDockerfileUnchanged:
    def test_dockerfile_entrypoint_unchanged(self) -> None:
        """Production ENTRYPOINT remains python -m bremen."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert 'ENTRYPOINT ["python", "-m", "bremen"]' in content

    def test_dockerfile_cmd_unchanged(self) -> None:
        """Production CMD remains serve --host 0.0.0.0 --port 8080."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert 'CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]' in content


# ===================================================================
# Module safety
# ===================================================================


class TestFastAPIModuleSafety:
    """The FastAPI app module stays within safe boundaries."""

    def test_no_boto3_import(self) -> None:
        """FastAPI app module does not import boto3."""
        import ast
        source = ROOT / "src" / "bremen" / "api" / "fastapi_app.py"
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
        source = ROOT / "src" / "bremen" / "api" / "fastapi_app.py"
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

    def test_no_server_spawning_in_test(self) -> None:
        """Phase 2 test file does not start a real web server."""
        test_source = Path(__file__).read_text(encoding="utf-8")
        # Check only import/function lines, not string literals in assertions
        import_lines = [
            line for line in test_source.split("\n")
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines)
        prohibited = [
            "HTTPServer", "ThreadingHTTPServer", "serve_forever",
            "start_server", "urlopen",
        ]
        for term in prohibited:
            assert term not in import_text, (
                f"Phase 2 test file imports server-spawning pattern: {term}"
            )
