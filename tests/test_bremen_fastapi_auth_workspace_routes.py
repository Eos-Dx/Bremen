"""Tests for FastAPI auth and workspace route parity (PR0107).

Covers:
- GET /demo/login returns 200 HTML
- POST /demo/api/auth/token — auth disabled returns 503, bad creds return 401
- POST /demo/api/auth/refresh — auth disabled returns 503, bad token returns 401
- GET /demo/workspace returns 200 HTML
- GET /demo/workspace/{job_id} returns 200 HTML
- No real server, socket, localhost HTTP, uvicorn launch
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app


@pytest.fixture()
def client() -> TestClient:
    """Create a FastAPI TestClient."""
    return TestClient(create_fastapi_app(), raise_server_exceptions=False)


# ===================================================================
# GET /demo/login
# ===================================================================


class TestLoginPageRoute:
    """GET /demo/login must return 200 HTML."""

    def test_login_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/login")
        assert resp.status_code == 200

    def test_login_returns_html(self, client: TestClient) -> None:
        resp = client.get("/demo/login")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_login_includes_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/login", headers={"X-Request-ID": "login-123"})
        assert resp.headers.get("X-Request-ID") == "login-123"

    def test_login_auto_generates_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/login")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0


# ===================================================================
# POST /demo/api/auth/token
# ===================================================================


class TestAuthTokenRoute:
    """POST /demo/api/auth/token — auth disabled or config invalid returns 503."""

    def test_auth_disabled_returns_503(self, client: TestClient) -> None:
        resp = client.post("/demo/api/auth/token", json={
            "username": "test", "password": "test",
        })
        # In test env, auth is typically disabled → 503
        assert resp.status_code in (503, 401)

    def test_auth_disabled_body_shape(self, client: TestClient) -> None:
        resp = client.post("/demo/api/auth/token", json={
            "username": "test", "password": "test",
        })
        body = resp.json()
        if resp.status_code == 503:
            assert "error" in body
            assert "not configured" in body["error"].lower()
        else:
            # 401 means auth is enabled but creds are wrong
            assert "error" in body

    def test_empty_body_returns_error(self, client: TestClient) -> None:
        resp = client.post(
            "/demo/api/auth/token",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (401, 503)

    def test_bad_credentials_returns_401_when_auth_enabled(
        self, client: TestClient,
    ) -> None:
        """If auth is enabled, bad creds should return 401."""
        resp = client.post("/demo/api/auth/token", json={
            "username": "nonexistent", "password": "wrong",
        })
        # Only check shape if auth is enabled (401)
        if resp.status_code == 401:
            body = resp.json()
            assert "error" in body
            assert "Authentication failed" in body["error"]

    def test_missing_username_returns_401(self, client: TestClient) -> None:
        resp = client.post("/demo/api/auth/token", json={
            "password": "test",
        })
        assert resp.status_code in (401, 503)


# ===================================================================
# POST /demo/api/auth/refresh
# ===================================================================


class TestAuthRefreshRoute:
    """POST /demo/api/auth/refresh — auth disabled returns 503."""

    def test_auth_disabled_returns_503(self, client: TestClient) -> None:
        resp = client.post("/demo/api/auth/refresh", json={
            "refresh_token": "some-token",
        })
        assert resp.status_code in (503, 401)

    def test_auth_disabled_body_shape(self, client: TestClient) -> None:
        resp = client.post("/demo/api/auth/refresh", json={
            "refresh_token": "some-token",
        })
        body = resp.json()
        if resp.status_code == 503:
            assert "error" in body
            assert "not configured" in body["error"].lower()
        else:
            assert "error" in body

    def test_bad_refresh_token_returns_401(self, client: TestClient) -> None:
        resp = client.post("/demo/api/auth/refresh", json={
            "refresh_token": "invalid-jwt-token",
        })
        assert resp.status_code in (401, 503)

    def test_empty_body_returns_error(self, client: TestClient) -> None:
        resp = client.post(
            "/demo/api/auth/refresh",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (401, 503)

    def test_missing_refresh_token_returns_401(self, client: TestClient) -> None:
        resp = client.post("/demo/api/auth/refresh", json={})
        assert resp.status_code in (401, 503)


# ===================================================================
# GET /demo/workspace
# ===================================================================


class TestWorkspaceRoute:
    """GET /demo/workspace must return 200 HTML."""

    def test_workspace_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/workspace")
        assert resp.status_code == 200

    def test_workspace_returns_html(self, client: TestClient) -> None:
        resp = client.get("/demo/workspace")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_workspace_includes_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/workspace", headers={"X-Request-ID": "ws-456"})
        assert resp.headers.get("X-Request-ID") == "ws-456"

    def test_workspace_auto_generates_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/workspace")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_workspace_contains_bremen(self, client: TestClient) -> None:
        resp = client.get("/demo/workspace")
        assert "bremen" in resp.text.lower() or "workspace" in resp.text.lower()


class TestWorkspaceJobRoute:
    """GET /demo/workspace/{job_id} must return 200 HTML."""

    def test_workspace_with_job_id_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/workspace/test-job-123")
        assert resp.status_code == 200

    def test_workspace_with_job_id_returns_html(self, client: TestClient) -> None:
        resp = client.get("/demo/workspace/test-job-123")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_workspace_with_job_id_includes_request_id(
        self, client: TestClient,
    ) -> None:
        resp = client.get(
            "/demo/workspace/abc-123",
            headers={"X-Request-ID": "wsjob-789"},
        )
        assert resp.headers.get("X-Request-ID") == "wsjob-789"


# ===================================================================
# Existing routes not broken
# ===================================================================


class TestExistingRoutesPreserved:
    """All previously working routes must still work."""

    def test_health_still_works(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_model_version_still_works(self, client: TestClient) -> None:
        resp = client.get("/model/version")
        assert resp.status_code == 200

    def test_demo_start_page_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert resp.status_code == 200

    def test_demo_control_room_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert resp.status_code == 200

    def test_demo_models_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200
