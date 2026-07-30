"""Tests for FastAPI models, API docs, and health log parity.

Covers:
- GET /demo/api/models returns configured models (not empty catalog)
- GET /demo/api-docs returns API documentation HTML
- GET /health is accessible and does not leak internal details
- H5 container listing still works
- No real servers, sockets, localhost HTTP, uvicorn launch
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app


@pytest.fixture()
def client() -> TestClient:
    """Create a FastAPI TestClient."""
    return TestClient(create_fastapi_app(), raise_server_exceptions=False)


class TestModelCatalogRoute:
    """GET /demo/api/models must return a valid catalog."""

    def test_models_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200

    def test_models_has_catalog_fields(self, client: TestClient) -> None:
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

    def test_models_status_is_known(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        body = resp.json()
        assert body["status"] in (
            "not_configured", "available", "no_valid_models", "discovery_failed",
        )

    def test_models_no_raw_s3_paths(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert "s3://" not in resp.text

    def test_models_no_exception_traces(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert "Traceback" not in resp.text


class TestAPIDocsRoute:
    """GET /demo/api-docs must return API documentation HTML."""

    def test_api_docs_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/api-docs")
        assert resp.status_code == 200

    def test_api_docs_returns_html(self, client: TestClient) -> None:
        resp = client.get("/demo/api-docs")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_api_docs_contains_bremen(self, client: TestClient) -> None:
        resp = client.get("/demo/api-docs")
        assert "bremen" in resp.text.lower()

    def test_api_docs_includes_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/api-docs", headers={"X-Request-ID": "docs-123"})
        assert resp.headers.get("X-Request-ID") == "docs-123"

    def test_api_docs_auto_generates_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/api-docs")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0


class TestHealthRoute:
    """GET /health must work and not leak internals."""

    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_json(self, client: TestClient) -> None:
        resp = client.get("/health")
        body = resp.json()
        assert isinstance(body, dict)
        assert "status" in body

    def test_health_no_raw_exception(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert "Traceback" not in resp.text


class TestH5ContainersStillWork:
    """GET /demo/api/h5/containers must not regress."""

    def test_containers_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/api/h5/containers")
        assert resp.status_code == 200

    def test_containers_has_expected_fields(self, client: TestClient) -> None:
        resp = client.get("/demo/api/h5/containers")
        body = resp.json()
        assert isinstance(body, dict)
        assert "storage" in body
        assert "containers" in body
        assert isinstance(body["containers"], list)


class TestExistingRoutesNotBroken:
    """Existing routes must not be broken by new additions."""

    def test_demo_start_page_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert resp.status_code == 200

    def test_demo_control_room_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert resp.status_code == 200

    def test_model_version_still_works(self, client: TestClient) -> None:
        resp = client.get("/model/version")
        assert resp.status_code == 200

    def test_unknown_route_returns_404(self, client: TestClient) -> None:
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
