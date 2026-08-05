"""Tests for Auth Enforcement Scope — PR0111.

Covers:
- auth disabled: protected routes still behave as before (no 401)
- auth enabled + missing Authorization: protected routes return safe 401
- auth enabled + malformed/invalid Bearer token: protected routes return safe 401
- auth enabled + valid access token: representative protected routes work
- public pages remain reachable without auth
- token/refresh endpoints remain reachable without existing token
- no global auth enforcement
- safe 401 shape verified (no secrets, no internals)

Uses fake test-only config and generated test tokens.
No real credentials, no real tokens, no production secrets.
No real server, socket, localhost HTTP, uvicorn launch.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

from argon2 import PasswordHasher as _PH

_FAKE_USERNAME = "test-enforcement-user"
_FAKE_PASSWORD = "test-enforcement-password-789"
_FAKE_HASH = _PH().hash(_FAKE_PASSWORD)
_FAKE_JWT_SECRET = "z" * 48  # 48-char fake secret for testing only


@pytest.fixture(autouse=True)
def _reset_auth_after_test():
    """Ensure auth config singleton is reset after every test."""
    yield
    from bremen.api.server import _reset_auth_config  # noqa: PLC0415
    from bremen.api.job_api_handler import _jobs, _jobs_lock  # noqa: PLC0415
    from bremen.api.job_api_handler import _event_store  # noqa: PLC0415
    _reset_auth_config()
    with _jobs_lock:
        _jobs.clear()
    _event_store.reset_for_tests()


def _make_app(auth_enabled: bool = False):
    """Create a FastAPI app with optional auth config."""
    from bremen.api.server import _reset_auth_config  # noqa: PLC0415
    from bremen.config import AuthConfig as _AuthConfig  # noqa: PLC0415

    _reset_auth_config()

    if auth_enabled:
        # Inject auth config into the server singleton
        from bremen.api import server as _server  # noqa: PLC0415
        cfg = _AuthConfig(
            enabled=True,
            username=_FAKE_USERNAME,
            password_hash=_FAKE_HASH,
            jwt_secret=_FAKE_JWT_SECRET,
            jwt_issuer="test-enforcement-issuer",
            jwt_audience="test-enforcement-audience",
            access_ttl_seconds=900,
            refresh_ttl_seconds=604800,
        )
        _server._auth_config = cfg
    else:
        from bremen.api import server as _server  # noqa: PLC0415
        _server._auth_config = None

    return create_fastapi_app()


def _make_token():
    """Generate a valid access token for testing."""
    from bremen.auth import create_access_token  # noqa: PLC0415
    from bremen.config import AuthConfig  # noqa: PLC0415

    cfg = AuthConfig(
        enabled=True,
        username=_FAKE_USERNAME,
        password_hash=_FAKE_HASH,
        jwt_secret=_FAKE_JWT_SECRET,
        jwt_issuer="test-enforcement-issuer",
        jwt_audience="test-enforcement-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    return create_access_token(cfg, _FAKE_USERNAME)


def _auth_headers(token: str = "") -> dict:
    """Build Authorization header."""
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _make_stream_ticket(job_id: str = "test-job-123", purpose: str = "stream"):
    """Generate a valid stream ticket for testing."""
    from bremen.auth import create_stream_ticket  # noqa: PLC0415
    from bremen.config import AuthConfig  # noqa: PLC0415

    cfg = AuthConfig(
        enabled=True,
        username=_FAKE_USERNAME,
        password_hash=_FAKE_HASH,
        jwt_secret=_FAKE_JWT_SECRET,
        jwt_issuer="test-enforcement-issuer",
        jwt_audience="test-enforcement-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    return create_stream_ticket(cfg, _FAKE_USERNAME, job_id, purpose)


# ---------------------------------------------------------------------------
# Protected routes list
# ---------------------------------------------------------------------------

PROTECTED_ROUTES = [
    ("GET", "/demo/api/h5/containers"),
    ("GET", "/demo/api/jobs"),
    ("GET", "/demo/api/jobs/nonexistent"),
    ("GET", "/demo/api/jobs/nonexistent/events"),
    ("GET", "/demo/api/jobs/nonexistent/reports"),
    ("GET", "/demo/api/jobs/nonexistent/reports/bremen"),
    ("GET", "/demo/report/nonexistent"),
    ("GET", "/demo/api/reports/nonexistent/external"),
    ("GET", "/demo/api/reports/nonexistent/internal"),
    ("GET", "/demo/workspace"),
    ("GET", "/demo/workspace/nonexistent"),
]

PUBLIC_ROUTES = [
    ("GET", "/demo"),
    ("GET", "/demo/login"),
    ("GET", "/demo/control-room"),
    ("GET", "/demo/api-docs"),
    ("GET", "/demo/model-guide"),
    ("GET", "/demo/model-playground"),
    ("GET", "/model/version"),
    ("GET", "/health"),
    ("GET", "/demo/api/models"),
]

AUTH_ROUTES = [
    ("POST", "/demo/api/auth/token"),
    ("POST", "/demo/api/auth/refresh"),
]


# ===========================================================================
# 1. Auth disabled — protected routes behave as before
# ===========================================================================


class TestAuthDisabledBehavior:
    """When auth is disabled, all routes work without tokens."""

    def test_protected_route_no_token_200(self):
        """Protected routes return 200 (not 401) when auth disabled."""
        app = _make_app(auth_enabled=False)
        client = TestClient(app, raise_server_exceptions=False)
        for method, path in PROTECTED_ROUTES:
            resp = client.get(path) if method == "GET" else client.post(path)
            assert resp.status_code != 401, (
                f"{method} {path} returned 401 with auth disabled"
            )

    def test_protected_route_no_token_not_503(self):
        """Protected routes do not return 503 when auth disabled."""
        app = _make_app(auth_enabled=False)
        client = TestClient(app, raise_server_exceptions=False)
        for method, path in PROTECTED_ROUTES:
            resp = client.get(path) if method == "GET" else client.post(path)
            assert resp.status_code != 503, (
                f"{method} {path} returned 503 with auth disabled"
            )


# ===========================================================================
# 2. Auth enabled — missing/invalid token → safe 401
# ===========================================================================


class TestAuthEnabledMissingToken:
    """When auth is enabled, missing token → safe 401."""

    def test_protected_route_no_token_401(self):
        """Protected routes return 401 without Authorization header."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        for method, path in PROTECTED_ROUTES:
            resp = client.get(path) if method == "GET" else client.post(path)
            assert resp.status_code == 401, (
                f"{method} {path} should return 401 without token"
            )

    def test_401_shape_is_safe(self):
        """401 response contains only safe fields."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        body = resp.json()
        assert body.get("error") == "Authentication failed"
        assert body.get("token_type") == "Bearer"
        assert body.get("technical_demo_only") is True
        # No extra fields that could leak internals
        assert len(body) == 3

    def test_401_no_password_hash(self):
        """401 response does not contain password hash."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        text = resp.text
        assert _FAKE_HASH not in text
        assert _FAKE_JWT_SECRET not in text


class TestAuthEnabledInvalidToken:
    """When auth is enabled, invalid token → safe 401."""

    def test_malformed_token_401(self):
        """Malformed Bearer token → 401."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/demo/api/jobs",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401

    def test_empty_bearer_401(self):
        """Bearer with no token → 401."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/demo/api/jobs",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    def test_wrong_auth_scheme_401(self):
        """Non-Bearer Authorization → 401."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/demo/api/jobs",
            headers={"Authorization": "Basic abc123"},
        )
        assert resp.status_code == 401

    def test_refresh_token_rejected_401(self):
        """Refresh token at access endpoint → 401."""
        from bremen.auth import create_refresh_token  # noqa: PLC0415
        from bremen.config import AuthConfig  # noqa: PLC0415

        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)

        cfg = AuthConfig(
            enabled=True,
            username=_FAKE_USERNAME,
            password_hash=_FAKE_HASH,
            jwt_secret=_FAKE_JWT_SECRET,
            jwt_issuer="test-enforcement-issuer",
            jwt_audience="test-enforcement-audience",
            access_ttl_seconds=900,
            refresh_ttl_seconds=604800,
        )
        refresh = create_refresh_token(cfg, _FAKE_USERNAME)
        resp = client.get(
            "/demo/api/jobs",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert resp.status_code == 401


# ===========================================================================
# 3. Auth enabled + valid token → routes work
# ===========================================================================


class TestAuthEnabledValidToken:
    """When auth is enabled with valid token, protected routes work."""

    def test_jobs_list_with_valid_token(self):
        """GET /demo/api/jobs with valid token → 200."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/api/jobs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "jobs" in body

    def test_job_detail_with_valid_token(self):
        """GET /demo/api/jobs/{id} with valid token → 200 or 404."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/api/jobs/nonexistent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 404)

    def test_h5_containers_with_valid_token(self):
        """GET /demo/api/h5/containers with valid token → 200."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/api/h5/containers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_workspace_with_valid_token(self):
        """GET /demo/workspace with valid token → 200 HTML."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/workspace",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_report_page_with_valid_token(self):
        """GET /demo/report/{id} with valid token → 200 HTML."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/report/test-job-123",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_external_report_with_valid_token(self):
        """GET /demo/api/reports/{id}/external with valid token → 200."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/api/reports/nonexistent/external",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_workspace_job_with_valid_token(self):
        """GET /demo/workspace/{id} with valid token → 200 HTML."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/workspace/test-job-456",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


# ===========================================================================
# 4. Public pages remain reachable without auth
# ===========================================================================


class TestPublicRoutesAlwaysReachable:
    """Public pages are never gated by auth."""

    def test_public_routes_no_auth(self):
        """All public routes accessible without token when auth enabled."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        for method, path in PUBLIC_ROUTES:
            resp = client.get(path) if method == "GET" else client.post(path)
            assert resp.status_code != 401, (
                f"{method} {path} should not require auth"
            )

    def test_auth_routes_no_existing_token(self):
        """Auth token/refresh endpoints accessible without existing token."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        # POST /demo/api/auth/token with valid creds should work
        resp = client.post(
            "/demo/api/auth/token",
            json={"username": _FAKE_USERNAME, "password": _FAKE_PASSWORD},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_auth_token_disabled_returns_503(self):
        """POST /demo/api/auth/token returns 503 when auth disabled."""
        app = _make_app(auth_enabled=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/demo/api/auth/token",
            json={"username": "any", "password": "any"},
        )
        assert resp.status_code == 503


# ===========================================================================
# 5. No global auth enforcement
# ===========================================================================


class TestNoGlobalAuth:
    """Auth is NOT enforced globally — only on protected routes."""

    def test_models_catalog_no_auth(self):
        """GET /demo/api/models never requires auth."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200

    def test_health_no_auth(self):
        """GET /health never requires auth."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_model_version_no_auth(self):
        """GET /model/version never requires auth."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/model/version")
        assert resp.status_code == 200


# ===========================================================================
# 6. Safe 401 shape verification
# ===========================================================================


class TestSafe401Shape:
    """401 responses are safe and consistent."""

    def test_401_shape_consistent_across_routes(self):
        """All protected routes return the same 401 shape."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        for method, path in PROTECTED_ROUTES[:5]:  # sample subset
            resp = client.get(path) if method == "GET" else client.post(path)
            if resp.status_code == 401:
                body = resp.json()
                assert body.get("error") == "Authentication failed"
                assert body.get("token_type") == "Bearer"
                assert body.get("technical_demo_only") is True

    def test_401_no_traceback(self):
        """401 response contains no traceback."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        assert "Traceback" not in resp.text
        assert ".py" not in resp.text

    def test_401_no_secrets(self):
        """401 response contains no secret values."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        text = resp.text
        assert _FAKE_HASH not in text
        assert _FAKE_JWT_SECRET not in text
        assert _FAKE_PASSWORD not in text


# ===========================================================================
# 7. Ticket minting endpoint
# ===========================================================================


class TestTicketMintingEndpoint:
    """POST /demo/api/jobs/{job_id}/auth/ticket endpoint."""

    def _inject_job(self, client, job_id: str = "test-job") -> None:
        """Inject a test job so the mint endpoint can find it."""
        from bremen.api.job_api_handler import _jobs, _jobs_lock  # noqa: PLC0415
        from bremen.api.job_api_handler import _event_store  # noqa: PLC0415
        from bremen.api.job_models import AnalysisJob  # noqa: PLC0415
        import time as _time

        now = datetime.now(timezone.utc).isoformat()
        job = AnalysisJob(
            job_id=job_id,
            request_id="test",
            created_at=now,
            overall_status="running",
            requested_workflows=("bremen",),
        )
        with _jobs_lock:
            _jobs[job_id] = job
        # Also emit a minimal event so _event_store knows about the job
        from bremen.api.event_schema import JobEvent  # noqa: PLC0415
        _event_store.append(job_id, JobEvent(
            job_id=job_id,
            request_id="test",
            sequence=1,
            event_type="test",
            status="started",
        ))

    def test_mint_endpoint_requires_bearer(self):
        """Mint endpoint requires valid Bearer access token."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        self._inject_job(client, "test-job")
        resp = client.post(
            "/demo/api/jobs/test-job/auth/ticket",
            json={"purpose": "stream"},
        )
        assert resp.status_code == 401

    def test_mint_endpoint_rejects_ticket_auth(self):
        """Mint endpoint rejects ticket (not access token) as auth."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        self._inject_job(client, "test-job")
        ticket = _make_stream_ticket("test-job", "stream")
        resp = client.post(
            "/demo/api/jobs/test-job/auth/ticket",
            json={"purpose": "stream"},
            headers={"Authorization": f"Bearer {ticket}"},
        )
        assert resp.status_code == 401

    def test_mint_endpoint_valid_token(self):
        """Mint endpoint returns 201 with valid access token."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        self._inject_job(client, "test-job")
        token = _make_token()
        resp = client.post(
            "/demo/api/jobs/test-job/auth/ticket",
            json={"purpose": "stream"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "ticket" in body
        assert body["expires_in"] == 60
        assert body["token_type"] == "stream_ticket"
        assert body["job_id"] == "test-job"
        assert body["purpose"] == "stream"
        assert body["technical_demo_only"] is True

    def test_mint_endpoint_report_purpose(self):
        """Mint endpoint works for report purpose."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        self._inject_job(client, "test-job")
        token = _make_token()
        resp = client.post(
            "/demo/api/jobs/test-job/auth/ticket",
            json={"purpose": "report"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["purpose"] == "report"

    def test_mint_endpoint_invalid_purpose_400(self):
        """Mint endpoint rejects invalid purpose."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        self._inject_job(client, "test-job")
        token = _make_token()
        resp = client.post(
            "/demo/api/jobs/test-job/auth/ticket",
            json={"purpose": "invalid"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_mint_endpoint_missing_purpose_400(self):
        """Mint endpoint rejects missing purpose."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        self._inject_job(client, "test-job")
        token = _make_token()
        resp = client.post(
            "/demo/api/jobs/test-job/auth/ticket",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_mint_endpoint_auth_disabled_allows_through(self):
        """Mint endpoint allows through when auth disabled (same as _check_auth_gate)."""
        app = _make_app(auth_enabled=False)
        client = TestClient(app, raise_server_exceptions=False)
        # Auth disabled → gate returns None → endpoint proceeds to decode_access_token
        # which will fail because config has no secret → 500 (server error)
        resp = client.post(
            "/demo/api/jobs/test-job/auth/ticket",
            json={"purpose": "stream"},
        )
        # When auth is disabled, the gate passes, but decode_access_token
        # will fail because the config is not set up for token creation.
        # The key assertion: NOT 401 (auth gate allows through)
        assert resp.status_code != 401

    def test_mint_endpoint_job_not_found_404(self):
        """Mint endpoint returns 404 when job does not exist."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.post(
            "/demo/api/jobs/nonexistent-job/auth/ticket",
            json={"purpose": "stream"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# ===========================================================================
# 8. SSE route ticket fallback
# ===========================================================================


class TestSSERouteTicketFallback:
    """GET /demo/api/jobs/{job_id}/events/stream ticket fallback."""

    def test_stream_route_accepts_valid_bearer(self):
        """Stream route accepts valid Bearer token."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/api/jobs/test-job/events/stream",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Should not be 401 — may be 200 or other non-auth error
        assert resp.status_code != 401

    def test_stream_route_accepts_valid_stream_ticket(self):
        """Stream route accepts valid stream ticket via query param."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        ticket = _make_stream_ticket("test-job", "stream")
        resp = client.get(
            "/demo/api/jobs/test-job/events/stream",
            params={"auth_ticket": ticket},
        )
        assert resp.status_code != 401

    def test_stream_route_rejects_report_ticket(self):
        """Stream route rejects report-purpose ticket."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        ticket = _make_stream_ticket("test-job", "report")
        resp = client.get(
            "/demo/api/jobs/test-job/events/stream",
            params={"auth_ticket": ticket},
        )
        assert resp.status_code == 401

    def test_stream_route_rejects_wrong_job_ticket(self):
        """Stream route rejects ticket for different job."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        ticket = _make_stream_ticket("other-job", "stream")
        resp = client.get(
            "/demo/api/jobs/test-job/events/stream",
            params={"auth_ticket": ticket},
        )
        assert resp.status_code == 401

    def test_stream_route_rejects_no_auth(self):
        """Stream route rejects request with no auth."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs/test-job/events/stream")
        assert resp.status_code == 401

    def test_stream_route_accepts_ticket_when_auth_disabled(self):
        """Stream route allows access when auth disabled."""
        app = _make_app(auth_enabled=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs/test-job/events/stream")
        assert resp.status_code != 401


# ===========================================================================
# 9. Report route ticket fallback
# ===========================================================================


class TestReportRouteTicketFallback:
    """GET /demo/report/{job_id} ticket fallback."""

    def test_report_route_accepts_valid_bearer(self):
        """Report route accepts valid Bearer token."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_token()
        resp = client.get(
            "/demo/report/test-job-123",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code != 401

    def test_report_route_accepts_valid_report_ticket(self):
        """Report route accepts valid report ticket via query param."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        ticket = _make_stream_ticket("test-job-123", "report")
        resp = client.get(
            "/demo/report/test-job-123",
            params={"auth_ticket": ticket},
        )
        assert resp.status_code != 401

    def test_report_route_rejects_stream_ticket(self):
        """Report route rejects stream-purpose ticket."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        ticket = _make_stream_ticket("test-job-123", "stream")
        resp = client.get(
            "/demo/report/test-job-123",
            params={"auth_ticket": ticket},
        )
        assert resp.status_code == 401

    def test_report_route_rejects_wrong_job_ticket(self):
        """Report route rejects ticket for different job."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        ticket = _make_stream_ticket("other-job", "report")
        resp = client.get(
            "/demo/report/test-job-123",
            params={"auth_ticket": ticket},
        )
        assert resp.status_code == 401

    def test_report_route_rejects_no_auth(self):
        """Report route rejects request with no auth."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/report/test-job-123")
        assert resp.status_code == 401

    def test_report_route_accepts_ticket_when_auth_disabled(self):
        """Report route allows access when auth disabled."""
        app = _make_app(auth_enabled=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/report/test-job-123")
        assert resp.status_code != 401


# ===========================================================================
# 10. Other protected routes do NOT accept tickets
# ===========================================================================


class TestOtherRoutesRejectTicket:
    """Non-SSE/report protected routes do not accept auth_ticket."""

    def test_jobs_list_rejects_ticket(self):
        """GET /demo/api/jobs does not accept stream_ticket in URL."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        ticket = _make_stream_ticket("any-job", "stream")
        resp = client.get(
            "/demo/api/jobs",
            params={"auth_ticket": ticket},
        )
        assert resp.status_code == 401

    def test_h5_containers_rejects_ticket(self):
        """GET /demo/api/h5/containers does not accept ticket."""
        app = _make_app(auth_enabled=True)
        client = TestClient(app, raise_server_exceptions=False)
        ticket = _make_stream_ticket("any-job", "stream")
        resp = client.get(
            "/demo/api/h5/containers",
            params={"auth_ticket": ticket},
        )
        assert resp.status_code == 401
