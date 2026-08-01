"""Auth Activation Readiness Tests — PR0112.

Verifies that auth is safe to activate in deployment:
- auth disabled remains default
- auth enabled without required JWT secret/config fails closed safely
- auth enabled with invalid credential hash fails closed safely
- auth enabled with test-only valid hash can issue token
- issued token can access protected route
- missing/invalid token gets safe 401
- public pages remain public

No real credentials, no real tokens, no production secrets.
No real server, socket, localhost HTTP, uvicorn launch.
No external network calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app
from bremen.config import AuthConfig, read_auth_config


# ---------------------------------------------------------------------------
# Test-only constants — never use in production
# ---------------------------------------------------------------------------

_FAKE_USERNAME = "activation-test-user"
_FAKE_PASSWORD = "activation-test-password-999"
_FAKE_JWT_SECRET = "y" * 48  # 48-char fake secret for testing only


def _make_test_hash() -> str:
    """Generate a real argon2id hash for test-only password."""
    from argon2 import PasswordHasher
    return PasswordHasher().hash(_FAKE_PASSWORD)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_auth_singleton():
    """Reset auth config singleton after each test."""
    yield
    from bremen.api.server import _reset_auth_config  # noqa: PLC0415
    _reset_auth_config()


def _inject_auth_config(
    enabled: bool = True,
    username: str = _FAKE_USERNAME,
    password_hash: str | None = None,
    jwt_secret: str = _FAKE_JWT_SECRET,
    issuer: str = "test-readiness-issuer",
    audience: str = "test-readiness-audience",
    access_ttl: int = 900,
    refresh_ttl: int = 604800,
) -> AuthConfig:
    """Inject auth config into the server singleton for testing."""
    from bremen.api import server as _server  # noqa: PLC0415
    from bremen.api.server import _reset_auth_config  # noqa: PLC0415

    _reset_auth_config()

    if password_hash is None:
        password_hash = _make_test_hash()

    cfg = AuthConfig(
        enabled=enabled,
        username=username,
        password_hash=password_hash,
        jwt_secret=jwt_secret,
        jwt_issuer=issuer,
        jwt_audience=audience,
        access_ttl_seconds=access_ttl,
        refresh_ttl_seconds=refresh_ttl,
    )
    _server._auth_config = cfg
    return cfg


def _make_token(config: AuthConfig | None = None) -> str:
    """Generate a valid access token for testing."""
    from bremen.auth import create_access_token  # noqa: PLC0415

    if config is None:
        config = AuthConfig(
            enabled=True,
            username=_FAKE_USERNAME,
            password_hash=_make_test_hash(),
            jwt_secret=_FAKE_JWT_SECRET,
            jwt_issuer="test-readiness-issuer",
            jwt_audience="test-readiness-audience",
            access_ttl_seconds=900,
            refresh_ttl_seconds=604800,
        )
    return create_access_token(config, _FAKE_USERNAME)


# ===========================================================================
# 1. Auth disabled remains default
# ===========================================================================


class TestAuthDisabledByDefault:
    """Auth disabled is the default when no env vars are set."""

    def test_read_auth_config_empty_env(self):
        """read_auth_config({}) returns enabled=False."""
        cfg = read_auth_config(env={})
        assert cfg.enabled is False
        assert cfg.validation_error is None

    def test_read_auth_config_only_enabled_true(self):
        """read_auth_config with only BREMEN_AUTH_ENABLED=true returns disabled."""
        cfg = read_auth_config(env={"BREMEN_AUTH_ENABLED": "true"})
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_read_auth_config_explicitly_disabled(self):
        """read_auth_config with BREMEN_AUTH_ENABLED=false returns disabled."""
        cfg = read_auth_config(env={"BREMEN_AUTH_ENABLED": "false"})
        assert cfg.enabled is False

    def test_auth_disabled_token_returns_none(self):
        """authenticate_credentials returns None when auth disabled."""
        from bremen.auth import authenticate_credentials  # noqa: PLC0415

        cfg = AuthConfig(
            enabled=False, username="", password_hash="",
            jwt_secret="", jwt_issuer="", jwt_audience="",
            access_ttl_seconds=900, refresh_ttl_seconds=604800,
        )
        result = authenticate_credentials(cfg, "anyone", "anything")
        assert result is None


# ===========================================================================
# 2. Auth enabled without required config fails closed safely
# ===========================================================================


class TestFailClosedMissingConfig:
    """Auth enabled with missing/invalid config fails closed."""

    def test_missing_jwt_secret_fails_closed(self):
        """read_auth_config disables auth when JWT secret is missing."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": _make_test_hash(),
            # BREMEN_AUTH_JWT_SECRET intentionally omitted
        })
        assert cfg.enabled is False
        assert cfg.validation_error is not None
        assert "JWT_SECRET" in cfg.validation_error

    def test_short_jwt_secret_fails_closed(self):
        """read_auth_config disables auth when JWT secret is too short."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": _make_test_hash(),
            "BREMEN_AUTH_JWT_SECRET": "short",
        })
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_missing_username_fails_closed(self):
        """read_auth_config disables auth when username is missing."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_PASSWORD_HASH": _make_test_hash(),
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
        })
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_jwt_secret_equals_hash_fails_closed(self):
        """read_auth_config disables auth when JWT secret equals password hash."""
        test_hash = _make_test_hash()
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": test_hash,
            "BREMEN_AUTH_JWT_SECRET": test_hash,
        })
        assert cfg.enabled is False
        assert cfg.validation_error is not None


# ===========================================================================
# 3. Auth enabled with invalid credential hash fails closed safely
# ===========================================================================


class TestFailClosedInvalidHash:
    """Auth enabled with invalid credential hash format fails closed."""

    def test_plaintext_password_hash_rejected(self):
        """read_auth_config rejects plaintext password as hash."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": "not-a-valid-hash",
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
        })
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_sha256_hash_rejected(self):
        """read_auth_config rejects SHA-256 hex as hash."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": "a" * 64,  # looks like SHA-256
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
        })
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_empty_password_hash_rejected(self):
        """read_auth_config rejects empty password hash."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": "",
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
        })
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_valid_argon2id_hash_accepted(self):
        """read_auth_config accepts valid argon2id hash."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": _make_test_hash(),
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
        })
        assert cfg.enabled is True
        assert cfg.validation_error is None

    def test_valid_bcrypt_hash_accepted(self):
        """read_auth_config accepts valid bcrypt hash."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": "$2b$12$LJ3m4ys4g1s1a4e4b4c4d4e4f4g4h4i4j4k4l4m4n4o4p4q4r",
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
        })
        assert cfg.enabled is True
        assert cfg.validation_error is None


# ===========================================================================
# 4. Auth enabled with test-only valid hash can issue token
# ===========================================================================


class TestTokenIssuance:
    """Valid config can issue tokens."""

    def test_authenticate_credentials_returns_token_pair(self):
        """authenticate_credentials returns TokenPair with valid creds."""
        from bremen.auth import authenticate_credentials  # noqa: PLC0415

        test_hash = _make_test_hash()
        cfg = AuthConfig(
            enabled=True, username=_FAKE_USERNAME,
            password_hash=test_hash, jwt_secret=_FAKE_JWT_SECRET,
            jwt_issuer="test-issuer", jwt_audience="test-audience",
            access_ttl_seconds=900, refresh_ttl_seconds=604800,
        )
        result = authenticate_credentials(cfg, _FAKE_USERNAME, _FAKE_PASSWORD)
        assert result is not None
        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "Bearer"

    def test_wrong_password_returns_none(self):
        """authenticate_credentials returns None for wrong password."""
        from bremen.auth import authenticate_credentials  # noqa: PLC0415

        test_hash = _make_test_hash()
        cfg = AuthConfig(
            enabled=True, username=_FAKE_USERNAME,
            password_hash=test_hash, jwt_secret=_FAKE_JWT_SECRET,
            jwt_issuer="test-issuer", jwt_audience="test-audience",
            access_ttl_seconds=900, refresh_ttl_seconds=604800,
        )
        result = authenticate_credentials(cfg, _FAKE_USERNAME, "wrong-password")
        assert result is None

    def test_wrong_username_returns_none(self):
        """authenticate_credentials returns None for wrong username."""
        from bremen.auth import authenticate_credentials  # noqa: PLC0415

        test_hash = _make_test_hash()
        cfg = AuthConfig(
            enabled=True, username=_FAKE_USERNAME,
            password_hash=test_hash, jwt_secret=_FAKE_JWT_SECRET,
            jwt_issuer="test-issuer", jwt_audience="test-audience",
            access_ttl_seconds=900, refresh_ttl_seconds=604800,
        )
        result = authenticate_credentials(cfg, "wrong-user", _FAKE_PASSWORD)
        assert result is None

    def test_token_decode_roundtrip(self):
        """Issued token can be decoded back to valid claims."""
        from bremen.auth import create_access_token, decode_access_token  # noqa: PLC0415

        cfg = AuthConfig(
            enabled=True, username=_FAKE_USERNAME,
            password_hash=_make_test_hash(), jwt_secret=_FAKE_JWT_SECRET,
            jwt_issuer="test-issuer", jwt_audience="test-audience",
            access_ttl_seconds=900, refresh_ttl_seconds=604800,
        )
        token = create_access_token(cfg, _FAKE_USERNAME)
        claims = decode_access_token(cfg, token)
        assert claims.sub == _FAKE_USERNAME
        assert claims.token_type == "access"


# ===========================================================================
# 5. Issued token can access protected route
# ===========================================================================


class TestTokenAccessesProtectedRoute:
    """Valid token grants access to protected routes via FastAPI."""

    def test_token_grants_jobs_list_access(self):
        """Valid token allows access to GET /demo/api/jobs."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        cfg = _inject_auth_config()
        token = _make_token(cfg)
        resp = client.get(
            "/demo/api/jobs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "jobs" in body

    def test_token_grants_h5_containers_access(self):
        """Valid token allows access to GET /demo/api/h5/containers."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        cfg = _inject_auth_config()
        token = _make_token(cfg)
        resp = client.get(
            "/demo/api/h5/containers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_token_grants_workspace_access(self):
        """Valid token allows access to GET /demo/workspace."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        cfg = _inject_auth_config()
        token = _make_token(cfg)
        resp = client.get(
            "/demo/workspace",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_token_grants_report_access(self):
        """Valid token allows access to GET /demo/report/{id}."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        cfg = _inject_auth_config()
        token = _make_token(cfg)
        resp = client.get(
            "/demo/report/test-job",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_token_grants_external_report_access(self):
        """Valid token allows access to GET /demo/api/reports/{id}/external."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        cfg = _inject_auth_config()
        token = _make_token(cfg)
        resp = client.get(
            "/demo/api/reports/test-job/external",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_token_grants_workspace_job_access(self):
        """Valid token allows access to GET /demo/workspace/{id}."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        cfg = _inject_auth_config()
        token = _make_token(cfg)
        resp = client.get(
            "/demo/workspace/test-job",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


# ===========================================================================
# 6. Missing/invalid token gets safe 401
# ===========================================================================


class TestMissingInvalidToken401:
    """Missing or invalid tokens get safe 401."""

    def test_missing_token_401(self):
        """No Authorization header → 401 on protected route."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        assert resp.status_code == 401

    def test_malformed_token_401(self):
        """Malformed Bearer token → 401."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/demo/api/jobs",
            headers={"Authorization": "Bearer garbage"},
        )
        assert resp.status_code == 401

    def test_wrong_secret_token_401(self):
        """Token signed with wrong secret → 401."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        # Create token with different secret
        from bremen.auth import create_access_token  # noqa: PLC0415
        cfg_wrong = AuthConfig(
            enabled=True, username=_FAKE_USERNAME,
            password_hash=_make_test_hash(), jwt_secret="w" * 48,
            jwt_issuer="test-readiness-issuer",
            jwt_audience="test-readiness-audience",
            access_ttl_seconds=900, refresh_ttl_seconds=604800,
        )
        bad_token = create_access_token(cfg_wrong, _FAKE_USERNAME)
        resp = client.get(
            "/demo/api/jobs",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 401

    def test_401_shape_is_safe(self):
        """401 response contains only safe fields."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        body = resp.json()
        assert body.get("error") == "Authentication failed"
        assert body.get("token_type") == "Bearer"
        assert body.get("technical_demo_only") is True
        assert len(body) == 3

    def test_401_no_secrets_in_response(self):
        """401 response does not contain hash, secret, or password."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        text = resp.text
        cfg = _inject_auth_config()
        assert cfg.password_hash not in text
        assert cfg.jwt_secret not in text
        assert _FAKE_PASSWORD not in text

    def test_401_no_traceback(self):
        """401 response contains no traceback."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        assert "Traceback" not in resp.text
        assert ".py" not in resp.text


# ===========================================================================
# 7. Public pages remain public
# ===========================================================================


class TestPublicPagesStillPublic:
    """Public pages remain accessible without auth when auth is enabled."""

    PUBLIC_ROUTES = [
        "/demo",
        "/demo/login",
        "/demo/control-room",
        "/demo/api-docs",
        "/demo/model-guide",
        "/demo/model-playground",
        "/model/version",
        "/health",
        "/demo/api/models",
    ]

    def test_public_routes_no_auth_required(self):
        """All public routes accessible without token when auth enabled."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        for path in self.PUBLIC_ROUTES:
            resp = client.get(path)
            assert resp.status_code != 401, (
                f"{path} should not require auth but returned 401"
            )

    def test_auth_token_endpoint_accessible(self):
        """POST /demo/api/auth/token is accessible without existing token."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/demo/api/auth/token",
            json={"username": _FAKE_USERNAME, "password": _FAKE_PASSWORD},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body

    def test_auth_refresh_endpoint_accessible(self):
        """POST /demo/api/auth/refresh is accessible without existing token."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        # First get a valid refresh token
        resp = client.post(
            "/demo/api/auth/token",
            json={"username": _FAKE_USERNAME, "password": _FAKE_PASSWORD},
        )
        assert resp.status_code == 200
        refresh_token = resp.json()["refresh_token"]
        # Use it on refresh endpoint
        resp2 = client.post(
            "/demo/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert "access_token" in body2

    def test_auth_token_disabled_returns_503(self):
        """POST /demo/api/auth/token returns 503 when auth disabled."""
        _inject_auth_config(enabled=False)
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/demo/api/auth/token",
            json={"username": "any", "password": "any"},
        )
        assert resp.status_code == 503


# ===========================================================================
# 8. TTL configuration works correctly
# ===========================================================================


class TestTTLConfiguration:
    """Access and refresh TTL are configurable."""

    def test_custom_access_ttl(self):
        """Custom access TTL is respected."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": _make_test_hash(),
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
            "BREMEN_AUTH_ACCESS_TTL_SECONDS": "1800",
        })
        assert cfg.enabled is True
        assert cfg.access_ttl_seconds == 1800

    def test_custom_refresh_ttl(self):
        """Custom refresh TTL is respected."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": _make_test_hash(),
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
            "BREMEN_AUTH_REFRESH_TTL_SECONDS": "86400",
        })
        assert cfg.enabled is True
        assert cfg.refresh_ttl_seconds == 86400

    def test_ttl_clamped_to_bounds(self):
        """TTL values are clamped to min/max bounds."""
        cfg = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": _make_test_hash(),
            "BREMEN_AUTH_JWT_SECRET": _FAKE_JWT_SECRET,
            "BREMEN_AUTH_ACCESS_TTL_SECONDS": "10",  # below min (60)
            "BREMEN_AUTH_REFRESH_TTL_SECONDS": "99999999",  # above max
        })
        assert cfg.enabled is True
        assert cfg.access_ttl_seconds >= 60
        assert cfg.refresh_ttl_seconds <= 2592000


# ===========================================================================
# 9. Auth enforcement scope preserved from PR0111
# ===========================================================================


class TestEnforcementScopePreserved:
    """Auth enforcement scope from PR0111 is unchanged."""

    def test_protected_routes_require_token(self):
        """Protected routes require valid token when auth enabled."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        protected = [
            "/demo/api/jobs",
            "/demo/api/h5/containers",
            "/demo/workspace",
            "/demo/report/test",
        ]
        for path in protected:
            resp = client.get(path)
            assert resp.status_code == 401, (
                f"{path} should require auth"
            )

    def test_public_routes_no_token_needed(self):
        """Public routes do not require token when auth enabled."""
        _inject_auth_config()
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        public = ["/demo", "/demo/login", "/health", "/model/version"]
        for path in public:
            resp = client.get(path)
            assert resp.status_code != 401, (
                f"{path} should not require auth"
            )
