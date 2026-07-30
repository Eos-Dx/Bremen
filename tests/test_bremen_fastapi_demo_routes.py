"""Tests for FastAPI demo UI route parity.

Verifies that GET /demo and GET /demo/control-room return 200 HTML
via FastAPI TestClient. No real servers, no sockets, no localhost HTTP.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app


@pytest.fixture()
def client() -> TestClient:
    """Create a FastAPI TestClient."""
    return TestClient(create_fastapi_app(), raise_server_exceptions=False)


class TestDemoStartPageRoute:
    """GET /demo must return HTML from build_start_page."""

    def test_demo_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert resp.status_code == 200

    def test_demo_returns_html(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_demo_contains_bremen_title(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert "bremen" in resp.text.lower()

    def test_demo_with_trailing_slash(self, client: TestClient) -> None:
        resp = client.get("/demo/")
        assert resp.status_code == 200

    def test_demo_includes_request_id_header(self, client: TestClient) -> None:
        resp = client.get("/demo", headers={"X-Request-ID": "test-123"})
        assert resp.headers.get("X-Request-ID") == "test-123"

    def test_demo_auto_generates_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0


class TestDemoControlRoomRoute:
    """GET /demo/control-room must return HTML from build_control_room_page."""

    def test_control_room_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert resp.status_code == 200

    def test_control_room_returns_html(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_control_room_contains_control_room_content(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        # The page should contain control room content
        assert "control" in resp.text.lower() or "bremen" in resp.text.lower()

    def test_control_room_includes_request_id_header(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room", headers={"X-Request-ID": "cr-456"})
        assert resp.headers.get("X-Request-ID") == "cr-456"

    def test_control_room_auto_generates_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_control_room_with_query_params(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room?workflow_id=bremen&model_id=test")
        assert resp.status_code == 200


class TestExistingRoutesStillWork:
    """Ensure existing FastAPI routes are not broken by the new additions."""

    def test_health_still_works(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_model_version_still_works(self, client: TestClient) -> None:
        resp = client.get("/model/version")
        assert resp.status_code == 200

    def test_demo_api_models_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200

    def test_unknown_route_returns_404(self, client: TestClient) -> None:
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
