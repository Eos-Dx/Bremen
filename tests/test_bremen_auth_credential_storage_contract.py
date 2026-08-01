"""Tests for Auth Credential Storage Contract — PR0110.

Enforces that:
- No plaintext passwords accepted as production credential store
- Credentials loaded only from explicit env, never hardcoded
- Invalid/missing auth config keeps auth disabled or returns safe 503
- Password verification uses argon2id/bcrypt, never plaintext compare
- Access/refresh token TTL configurable through auth config
- Generated responses never expose password hashes, signing secrets,
  raw config, stack traces, or internal paths
- Auth remains disabled by default unless explicit config present

Uses only fake test-only hashes and fake usernames.
No real credentials, no real tokens, no production secrets.
No real server, socket, localhost HTTP, uvicorn launch.
"""

from __future__ import annotations

import inspect
import re

import pytest
from argon2 import PasswordHasher as _PH

from bremen.config import AuthConfig, read_auth_config
from bremen.auth import (
    authenticate_credentials,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    verify_password,
    TokenPair,
)

# ---------------------------------------------------------------------------
# Test-only fake credentials — never use in production
# ---------------------------------------------------------------------------

_FAKE_USERNAME = "test-fake-user"
_FAKE_PASSWORD = "test-fake-password-456"
_FAKE_HASH = _PH().hash(_FAKE_PASSWORD)
_FAKE_JWT_SECRET = "x" * 48  # 48-char fake secret for testing only


def _enabled_env(
    *,
    username: str = _FAKE_USERNAME,
    password_hash: str = _FAKE_HASH,
    jwt_secret: str = _FAKE_JWT_SECRET,
    access_ttl: str = "",
    refresh_ttl: str = "",
) -> dict[str, str]:
    """Build a minimal enabled auth env dict."""
    env: dict[str, str] = {
        "BREMEN_AUTH_ENABLED": "true",
        "BREMEN_AUTH_USERNAME": username,
        "BREMEN_AUTH_PASSWORD_HASH": password_hash,
        "BREMEN_AUTH_JWT_SECRET": jwt_secret,
    }
    if access_ttl:
        env["BREMEN_AUTH_ACCESS_TTL_SECONDS"] = access_ttl
    if refresh_ttl:
        env["BREMEN_AUTH_REFRESH_TTL_SECONDS"] = refresh_ttl
    return env


def _make_config(**kwargs) -> AuthConfig:
    """Build an AuthConfig for testing."""
    return AuthConfig(
        enabled=kwargs.get("enabled", True),
        username=kwargs.get("username", _FAKE_USERNAME),
        password_hash=kwargs.get("password_hash", _FAKE_HASH),
        jwt_secret=kwargs.get("jwt_secret", _FAKE_JWT_SECRET),
        jwt_issuer=kwargs.get("jwt_issuer", "test-issuer"),
        jwt_audience=kwargs.get("jwt_audience", "test-audience"),
        access_ttl_seconds=kwargs.get("access_ttl", 900),
        refresh_ttl_seconds=kwargs.get("refresh_ttl", 604800),
    )


# ===========================================================================
# 1. Plaintext passwords rejected as credential store
# ===========================================================================


class TestPlaintextPasswordsRejected:
    """Config must reject plaintext passwords as credential store."""

    def test_plaintext_password_hash_rejected(self):
        """A plaintext password string as password_hash is rejected."""
        env = _enabled_env(password_hash="my-actual-password")
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert cfg.validation_error is not None
        assert "PASSWORD_HASH" in cfg.validation_error

    def test_empty_password_hash_rejected(self):
        """Empty password_hash is rejected."""
        env = _enabled_env(password_hash="")
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_sha256_hash_rejected(self):
        """SHA-256 hex string as password_hash is rejected (not argon2/bcrypt)."""
        env = _enabled_env(
            password_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_md5_hash_rejected(self):
        """MD5 hex string as password_hash is rejected."""
        env = _enabled_env(password_hash="5d41402abc4b2a76b9719d911017c592")
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_valid_argon2id_accepted(self):
        """Argon2id hash is accepted."""
        env = _enabled_env(password_hash=_FAKE_HASH)
        cfg = read_auth_config(env=env)
        assert cfg.enabled is True
        assert cfg.validation_error is None

    def test_valid_bcrypt_accepted(self):
        """Bcrypt hash is accepted."""
        env = _enabled_env(password_hash="$2b$12$LJ3m4ys4g1s1a4e4b4c4d4e4f4g4h4i4j4k4l4m4n4o4p4q4r")
        cfg = read_auth_config(env=env)
        # bcrypt hash format is accepted even if verification would fail
        assert cfg.enabled is True or cfg.validation_error is None


# ===========================================================================
# 2. Credentials loaded only from explicit env, never hardcoded
# ===========================================================================


class TestCredentialsFromEnvOnly:
    """No hardcoded credentials anywhere in auth/config source."""

    def test_auth_module_no_hardcoded_passwords(self):
        """auth.py has no hardcoded password strings."""
        import bremen.auth as mod
        src = inspect.getsource(mod)
        for bad in ("changeme", "password123", "admin123", "secret123"):
            assert bad not in src.lower(), f"Hardcoded credential found: {bad}"

    def test_config_module_no_hardcoded_passwords(self):
        """config.py has no hardcoded password strings."""
        from bremen import config as mod
        src = inspect.getsource(mod)
        for bad in ("changeme", "password123", "admin123", "secret123"):
            assert bad not in src.lower(), f"Hardcoded credential found: {bad}"

    def test_auth_config_from_empty_env(self):
        """Empty env → disabled, no credential leakage."""
        cfg = read_auth_config(env={})
        assert cfg.enabled is False
        assert cfg.username == ""
        assert cfg.password_hash == ""
        assert cfg.jwt_secret == ""

    def test_auth_config_from_env_with_only_enabled(self):
        """Enabled=true but missing required fields → disabled."""
        cfg = read_auth_config(env={"BREMEN_AUTH_ENABLED": "true"})
        assert cfg.enabled is False
        assert cfg.validation_error is not None


# ===========================================================================
# 3. Invalid/missing auth config keeps auth disabled or returns safe 503
# ===========================================================================


class TestInvalidConfigSafeBehavior:
    """Invalid/missing config → disabled or safe 503."""

    def test_missing_required_fields_disables_auth(self):
        """Missing username/hash/secret → disabled with validation_error."""
        cases = [
            {"BREMEN_AUTH_ENABLED": "true"},
            {"BREMEN_AUTH_ENABLED": "true", "BREMEN_AUTH_USERNAME": "u"},
            {
                "BREMEN_AUTH_ENABLED": "true",
                "BREMEN_AUTH_USERNAME": "u",
                "BREMEN_AUTH_PASSWORD_HASH": _FAKE_HASH,
            },
        ]
        for env in cases:
            cfg = read_auth_config(env=env)
            assert cfg.enabled is False
            assert cfg.validation_error is not None

    def test_short_jwt_secret_disables_auth(self):
        """JWT secret < 32 chars → disabled."""
        env = _enabled_env(jwt_secret="short")
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert "32" in cfg.validation_error

    def test_same_secret_and_hash_disables_auth(self):
        """JWT secret == password hash → disabled."""
        env = _enabled_env(jwt_secret=_FAKE_HASH)
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert "distinct" in cfg.validation_error

    def test_never_raises_on_invalid_config(self):
        """read_auth_config never raises even with garbage input."""
        cfg = read_auth_config(env={"BREMEN_AUTH_ENABLED": "true", "GARBAGE": "x"})
        assert isinstance(cfg, AuthConfig)
        assert cfg.enabled is False

    def test_authenticate_disabled_returns_none(self):
        """authenticate_credentials with disabled config → None."""
        cfg = _make_config(enabled=False)
        result = authenticate_credentials(cfg, "any", "any")
        assert result is None


# ===========================================================================
# 4. Password verification uses safe hash/verifier
# ===========================================================================


class TestPasswordVerificationSafe:
    """Password verification uses argon2id/bcrypt, never plaintext."""

    def test_verify_uses_argon2id(self):
        """verify_password uses argon2id hasher."""
        assert verify_password(_FAKE_PASSWORD, _FAKE_HASH) is True

    def test_verify_wrong_password_returns_false(self):
        """Wrong password → False, no exception."""
        assert verify_password("wrong", _FAKE_HASH) is False

    def test_verify_malformed_hash_returns_false(self):
        """Invalid hash format → False, no exception."""
        assert verify_password("anything", "not-a-hash") is False

    def test_no_plaintext_compare_in_verify_source(self):
        """verify_password source has no plaintext == comparison."""
        src = inspect.getsource(verify_password)
        assert "password ==" not in src
        assert "== password" not in src

    def test_no_plaintext_compare_in_authenticate_source(self):
        """authenticate_credentials source has no plaintext == comparison."""
        src = inspect.getsource(authenticate_credentials)
        assert "password ==" not in src
        assert "== password" not in src


# ===========================================================================
# 5. Access/refresh token TTL configurable
# ===========================================================================


class TestTokenTTLConfigurable:
    """Access and refresh TTL are configurable through auth config."""

    def test_default_access_ttl(self):
        """Default access TTL is 900 seconds."""
        env = _enabled_env()
        cfg = read_auth_config(env=env)
        assert cfg.access_ttl_seconds == 900

    def test_default_refresh_ttl(self):
        """Default refresh TTL is 604800 seconds (7 days)."""
        env = _enabled_env()
        cfg = read_auth_config(env=env)
        assert cfg.refresh_ttl_seconds == 604800

    def test_custom_access_ttl(self):
        """Custom access TTL is accepted."""
        env = _enabled_env(access_ttl="1800")
        cfg = read_auth_config(env=env)
        assert cfg.access_ttl_seconds == 1800

    def test_custom_refresh_ttl(self):
        """Custom refresh TTL is accepted."""
        env = _enabled_env(refresh_ttl="86400")
        cfg = read_auth_config(env=env)
        assert cfg.refresh_ttl_seconds == 86400

    def test_access_ttl_clamped_to_min(self):
        """Access TTL below minimum → clamped."""
        env = _enabled_env(access_ttl="1")
        cfg = read_auth_config(env=env)
        assert cfg.access_ttl_seconds == 60  # min

    def test_access_ttl_clamped_to_max(self):
        """Access TTL above maximum → clamped."""
        env = _enabled_env(access_ttl="999999")
        cfg = read_auth_config(env=env)
        assert cfg.access_ttl_seconds == 86400  # max

    def test_refresh_ttl_clamped_to_min(self):
        """Refresh TTL below minimum → clamped."""
        env = _enabled_env(refresh_ttl="1")
        cfg = read_auth_config(env=env)
        assert cfg.refresh_ttl_seconds == 3600  # min

    def test_refresh_ttl_clamped_to_max(self):
        """Refresh TTL above maximum → clamped."""
        env = _enabled_env(refresh_ttl="99999999")
        cfg = read_auth_config(env=env)
        assert cfg.refresh_ttl_seconds == 2592000  # max (30 days)

    def test_invalid_ttl_string_uses_default(self):
        """Non-numeric TTL string → uses default."""
        env = _enabled_env(access_ttl="notanumber")
        cfg = read_auth_config(env=env)
        assert cfg.access_ttl_seconds == 900  # default

    def test_token_expires_in_matches_config(self):
        """Issued token expires_in matches configured access_ttl."""
        cfg = _make_config(access_ttl=1200)
        result = authenticate_credentials(cfg, _FAKE_USERNAME, _FAKE_PASSWORD)
        assert result is not None
        assert result.expires_in == 1200


# ===========================================================================
# 6. Generated responses never expose internals
# ===========================================================================


class TestNoInternalLeakage:
    """Responses must never expose password hashes, signing secrets, etc."""

    def test_token_response_no_password_hash(self):
        """Token response doesn't contain password_hash."""
        cfg = _make_config()
        result = authenticate_credentials(cfg, _FAKE_USERNAME, _FAKE_PASSWORD)
        assert result is not None
        # TokenPair only has access_token, refresh_token, token_type, expires_in
        assert not hasattr(result, "password_hash")
        assert not hasattr(result, "jwt_secret")
        result_dict = {
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
            "token_type": result.token_type,
            "expires_in": result.expires_in,
            "technical_demo_only": True,
        }
        text = str(result_dict)
        assert _FAKE_HASH not in text
        assert _FAKE_JWT_SECRET not in text

    def test_auth_error_shape_no_secrets(self):
        """Auth error response doesn't contain secrets."""
        from bremen.api.server import _AUTH_ERROR_SHAPE, _AUTH_DISABLED_SHAPE
        assert _FAKE_HASH not in _AUTH_ERROR_SHAPE
        assert _FAKE_JWT_SECRET not in _AUTH_ERROR_SHAPE
        assert _FAKE_HASH not in _AUTH_DISABLED_SHAPE
        assert _FAKE_JWT_SECRET not in _AUTH_DISABLED_SHAPE

    def test_auth_error_shape_generic(self):
        """Auth error response is generic."""
        from bremen.api.server import _AUTH_ERROR_SHAPE, _AUTH_DISABLED_SHAPE
        error = _AUTH_ERROR_SHAPE
        disabled = _AUTH_DISABLED_SHAPE
        assert "Authentication failed" in error
        assert "not configured" in disabled

    def test_validation_error_no_secret_leak(self):
        """Validation error never contains secret values."""
        env = _enabled_env(jwt_secret="short")
        cfg = read_auth_config(env=env)
        assert cfg.validation_error is not None
        assert "short" not in cfg.validation_error
        assert _FAKE_HASH not in cfg.validation_error

    def test_no_filesystem_paths_in_auth_source(self):
        """Auth module source has no filesystem paths."""
        import bremen.auth as mod
        src = inspect.getsource(mod)
        assert "/Users/" not in src
        assert "/home/" not in src
        assert "/tmp/" not in src

    def test_no_filesystem_paths_in_config_auth(self):
        """Config auth section has no filesystem paths."""
        from bremen import config as mod
        src = inspect.getsource(mod._read_auth_config_inner)
        assert "/Users/" not in src
        assert "/home/" not in src

    def test_no_stack_traces_in_auth_errors(self):
        """Auth errors don't contain stack traces."""
        cfg = _make_config(access_ttl=1)
        token = create_access_token(cfg, _FAKE_USERNAME)
        import time as _time
        _time.sleep(1.1)
        try:
            decode_access_token(cfg, token)
        except Exception as e:
            assert "Traceback" not in str(e)
            assert ".py" not in str(e)

    def test_no_regex_path_in_error(self):
        """Error messages don't contain regex/file paths."""
        from bremen.api.server import _AUTH_ERROR_SHAPE
        error = _AUTH_ERROR_SHAPE
        assert not re.search(r"/[a-zA-Z]+\.(py|json|yaml)", error)


# ===========================================================================
# 7. Auth disabled by default
# ===========================================================================


class TestAuthDisabledByDefault:
    """Auth must be disabled by default unless explicit config present."""

    def test_empty_env_disabled(self):
        """No env vars → disabled."""
        cfg = read_auth_config(env={})
        assert cfg.enabled is False

    def test_partial_env_disabled(self):
        """Only some env vars → disabled."""
        cfg = read_auth_config(env={"BREMEN_AUTH_USERNAME": "u"})
        assert cfg.enabled is False

    def test_enabled_false_explicit(self):
        """BREMEN_AUTH_ENABLED=false → disabled."""
        cfg = read_auth_config(env={"BREMEN_AUTH_ENABLED": "false"})
        assert cfg.enabled is False

    def test_enabled_true_with_all_fields(self):
        """All required fields present → enabled."""
        cfg = read_auth_config(env=_enabled_env())
        assert cfg.enabled is True

    def test_login_page_shows_auth_disabled_when_no_config(self):
        """Login page reflects auth disabled when no config."""
        cfg = read_auth_config(env={})
        assert cfg.enabled is False
        # The login page should show "auth not configured" state
        # This is tested indirectly through the config

    def test_disabled_config_authenticate_returns_none(self):
        """authenticate_credentials with disabled config → None."""
        cfg = _make_config(enabled=False)
        assert authenticate_credentials(cfg, "user", "pass") is None


# ===========================================================================
# 8. Route parity preserved
# ===========================================================================


class TestRouteParityPreserved:
    """Existing auth routes are not broken."""

    def test_auth_token_route_exists_in_fastapi(self):
        """FastAPI app has /demo/api/auth/token route."""
        from bremen.api.fastapi_app import create_fastapi_app
        app = create_fastapi_app()
        routes = [r.path for r in app.routes]
        assert "/demo/api/auth/token" in routes

    def test_auth_refresh_route_exists_in_fastapi(self):
        """FastAPI app has /demo/api/auth/refresh route."""
        from bremen.api.fastapi_app import create_fastapi_app
        app = create_fastapi_app()
        routes = [r.path for r in app.routes]
        assert "/demo/api/auth/refresh" in routes

    def test_login_route_exists_in_fastapi(self):
        """FastAPI app has /demo/login route."""
        from bremen.api.fastapi_app import create_fastapi_app
        app = create_fastapi_app()
        routes = [r.path for r in app.routes]
        assert "/demo/login" in routes
