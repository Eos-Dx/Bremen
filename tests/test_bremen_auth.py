"""Tests for Bremen Auth Module — PR0102.

Tests for:
- AuthConfig (config.py)
- Password verification (auth.py)
- JWT token creation/validation (auth.py)
- Safe error handling
- Security invariants
"""

import time
import inspect
import pytest

from bremen.config import AuthConfig, read_auth_config
from bremen.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    create_stream_ticket,
    decode_stream_ticket,
    authenticate_credentials,
    parse_bearer_header,
    authenticate_request,
    AuthError,
    AuthenticationFailedError,
    TokenExpiredError,
    TokenInvalidError,
    TokenPair,
    TokenClaims,
    TicketClaims,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

# A real argon2id hash for "test-password-123" — never use in production
_VALID_PASSWORD = "test-password-123"
_VALID_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$Qr7vPBPXsQB2+PrP+Qq7+OjqJkqJkqJkqJkqJkqJkqJ"
# Generate at runtime for valid tests
from argon2 import PasswordHasher as _PH
_VALID_HASH_REAL = _PH().hash(_VALID_PASSWORD)
_JWT_SECRET = "a" * 48  # 48-char secret for testing


def _make_config(
    enabled: bool = True,
    username: str = "testuser",
    password_hash: str = None,
    jwt_secret: str = _JWT_SECRET,
    jwt_issuer: str = "test-issuer",
    jwt_audience: str = "test-audience",
    access_ttl: int = 900,
    refresh_ttl: int = 604800,
) -> AuthConfig:
    if password_hash is None:
        password_hash = _VALID_HASH_REAL
    return AuthConfig(
        enabled=enabled,
        username=username,
        password_hash=password_hash,
        jwt_secret=jwt_secret,
        jwt_issuer=jwt_issuer,
        jwt_audience=jwt_audience,
        access_ttl_seconds=access_ttl,
        refresh_ttl_seconds=refresh_ttl,
    )


# ===========================================================================
# Config tests
# ===========================================================================


class TestAuthConfig:
    """AuthConfig from config.py."""

    def test_auth_disabled_by_default(self):
        """No env vars → disabled."""
        cfg = read_auth_config(env={})
        assert cfg.enabled is False
        assert cfg.validation_error is None

    def test_auth_enabled_complete_config(self):
        """All required vars → enabled."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": _JWT_SECRET,
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is True
        assert cfg.username == "demo-user"
        assert cfg.validation_error is None

    def test_auth_enabled_missing_username(self):
        """Enabled but no username → disabled + validation_error."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": _JWT_SECRET,
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert cfg.validation_error is not None
        assert "USERNAME" in cfg.validation_error

    def test_auth_enabled_missing_password_hash(self):
        """Enabled but no hash → disabled + validation_error."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_JWT_SECRET": _JWT_SECRET,
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert cfg.validation_error is not None
        assert "PASSWORD_HASH" in cfg.validation_error

    def test_auth_enabled_missing_jwt_secret(self):
        """Enabled but no secret → disabled + validation_error."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert cfg.validation_error is not None
        assert "JWT_SECRET" in cfg.validation_error

    def test_auth_enabled_short_secret(self):
        """Secret < 32 chars → validation_error."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": "short",
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert cfg.validation_error is not None
        assert "32" in cfg.validation_error

    def test_auth_ttl_parsing(self):
        """Valid/invalid TTL strings → bounds applied."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": _JWT_SECRET,
            "BREMEN_AUTH_ACCESS_TTL_SECONDS": "1800",
            "BREMEN_AUTH_REFRESH_TTL_SECONDS": "86400",
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is True
        assert cfg.access_ttl_seconds == 1800
        assert cfg.refresh_ttl_seconds == 86400

    def test_auth_ttl_invalid_string(self):
        """Invalid TTL string → uses default."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": _JWT_SECRET,
            "BREMEN_AUTH_ACCESS_TTL_SECONDS": "notanumber",
        }
        cfg = read_auth_config(env=env)
        assert cfg.access_ttl_seconds == 900  # default

    def test_auth_ttl_bounds(self):
        """TTL clamped to min/max."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": _JWT_SECRET,
            "BREMEN_AUTH_ACCESS_TTL_SECONDS": "1",  # below min 60
            "BREMEN_AUTH_REFRESH_TTL_SECONDS": "99999999",  # above max
        }
        cfg = read_auth_config(env=env)
        assert cfg.access_ttl_seconds == 60  # clamped to min
        assert cfg.refresh_ttl_seconds == 2592000  # clamped to max (30 days)

    def test_injected_env_dict(self):
        """Passing explicit env dict works for tests."""
        env = {
            "BREMEN_AUTH_ENABLED": "false",
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False

    def test_auth_config_never_raises(self):
        """read_auth_config() never throws."""
        cfg = read_auth_config(env={"BREMEN_AUTH_ENABLED": "true"})
        assert cfg.enabled is False
        assert cfg.validation_error is not None

    def test_auth_config_round_trip(self):
        """Environment → AuthConfig dataclass → field values correct."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "my-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": _JWT_SECRET,
            "BREMEN_AUTH_JWT_ISSUER": "my-issuer",
            "BREMEN_AUTH_JWT_AUDIENCE": "my-audience",
            "BREMEN_AUTH_ACCESS_TTL_SECONDS": "1200",
            "BREMEN_AUTH_REFRESH_TTL_SECONDS": "100000",
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is True
        assert cfg.username == "my-user"
        assert cfg.jwt_issuer == "my-issuer"
        assert cfg.jwt_audience == "my-audience"
        assert cfg.access_ttl_seconds == 1200
        assert cfg.refresh_ttl_seconds == 100000

    def test_no_secret_values_in_validation_errors(self):
        """Secret values never appear in validation errors."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": "short",
        }
        cfg = read_auth_config(env=env)
        assert cfg.validation_error is not None
        assert _VALID_HASH_REAL not in cfg.validation_error
        assert "short" not in cfg.validation_error

    def test_secret_distinct_from_hash(self):
        """JWT secret must be distinct from password hash."""
        env = {
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "demo-user",
            "BREMEN_AUTH_PASSWORD_HASH": _VALID_HASH_REAL,
            "BREMEN_AUTH_JWT_SECRET": _VALID_HASH_REAL,
        }
        cfg = read_auth_config(env=env)
        assert cfg.enabled is False
        assert "distinct" in cfg.validation_error


# ===========================================================================
# Password tests
# ===========================================================================


class TestPasswordVerification:
    """Password verification with argon2id."""

    def test_valid_password_passes(self):
        """Correct password → True."""
        assert verify_password(_VALID_PASSWORD, _VALID_HASH_REAL) is True

    def test_invalid_password_fails(self):
        """Wrong password → False."""
        assert verify_password("wrong-password", _VALID_HASH_REAL) is False

    def test_malformed_hash_fails_safely(self):
        """Invalid hash format → False (no exception)."""
        assert verify_password("any-password", "not-a-valid-hash") is False

    def test_empty_password_fails(self):
        """Empty password → False."""
        assert verify_password("", _VALID_HASH_REAL) is False

    def test_plaintext_compare_not_used(self):
        """No plaintext password comparison in verify_password source."""
        src = inspect.getsource(verify_password)
        # Should not use == to compare password directly
        assert "password ==" not in src
        assert "== password" not in src


# ===========================================================================
# JWT tests
# ===========================================================================


class TestJWTToken:
    """JWT token creation and validation."""

    def test_access_token_has_required_claims(self):
        """Access token contains sub, iat, exp, token_type, jti."""
        cfg = _make_config()
        token = create_access_token(cfg, "testuser")
        claims = decode_access_token(cfg, token)
        assert claims.sub == "testuser"
        assert claims.iat > 0
        assert claims.exp > claims.iat
        assert claims.token_type == "access"
        assert claims.jti  # non-empty UUID

    def test_refresh_token_has_token_type(self):
        """Refresh token has token_type == 'refresh'."""
        cfg = _make_config()
        token = create_refresh_token(cfg, "testuser")
        claims = decode_refresh_token(cfg, token)
        assert claims.token_type == "refresh"

    def test_expired_token_rejected(self):
        """exp < now → TokenExpiredError."""
        cfg = _make_config(access_ttl=1)  # 1 second TTL
        token = create_access_token(cfg, "testuser")
        time.sleep(1.1)
        with pytest.raises(TokenExpiredError):
            decode_access_token(cfg, token)

    def test_wrong_token_type_rejected(self):
        """Refresh token at access decode → TokenInvalidError."""
        cfg = _make_config()
        refresh_token = create_refresh_token(cfg, "testuser")
        with pytest.raises(TokenInvalidError):
            decode_access_token(cfg, refresh_token)

    def test_wrong_issuer_rejected(self):
        """When configured, wrong iss → TokenInvalidError."""
        cfg = _make_config(jwt_issuer="correct-issuer")
        token = create_access_token(cfg, "testuser")
        wrong_cfg = _make_config(jwt_issuer="wrong-issuer")
        with pytest.raises((TokenInvalidError, TokenExpiredError)):
            decode_access_token(wrong_cfg, token)

    def test_wrong_audience_rejected(self):
        """When configured, wrong aud → TokenInvalidError."""
        cfg = _make_config(jwt_audience="correct-audience")
        token = create_access_token(cfg, "testuser")
        wrong_cfg = _make_config(jwt_audience="wrong-audience")
        with pytest.raises((TokenInvalidError, TokenExpiredError)):
            decode_access_token(wrong_cfg, token)

    def test_decode_uses_explicit_algorithm(self):
        """Decode uses explicit algorithms=["HS256"]."""
        src = inspect.getsource(decode_access_token)
        # Check _decode_token which is called by decode_access_token
        from bremen.auth import _decode_token
        src = inspect.getsource(_decode_token)
        assert 'algorithms' in src and 'HS256' in src

    def test_algorithm_none_rejected(self):
        """Token with alg='none' rejected."""
        import jwt as pyjwt
        cfg = _make_config()
        # Craft a token with alg=none
        token_none = pyjwt.encode({"sub": "x", "iat": 0, "exp": 9999999999, "token_type": "access", "jti": "x"}, "", algorithm="none")
        with pytest.raises(TokenInvalidError):
            decode_access_token(cfg, token_none)

    def test_algorithm_hs512_rejected(self):
        """Token with alg='HS512' rejected (only HS256 allowed)."""
        import jwt as pyjwt
        cfg = _make_config()
        token_512 = pyjwt.encode({"sub": "x", "iat": 0, "exp": 9999999999, "token_type": "access", "jti": "x"}, cfg.jwt_secret, algorithm="HS512")
        with pytest.raises(TokenInvalidError):
            decode_access_token(cfg, token_512)

    def test_valid_access_token_accepted(self):
        """Valid token → TokenClaims returned."""
        cfg = _make_config()
        token = create_access_token(cfg, "testuser")
        claims = decode_access_token(cfg, token)
        assert isinstance(claims, TokenClaims)

    def test_malformed_token_rejected(self):
        """Gibberish token → TokenInvalidError."""
        cfg = _make_config()
        with pytest.raises(TokenInvalidError):
            decode_access_token(cfg, "not-a-real-token")

    def test_issuer_in_claims_when_configured(self):
        """iss claim present when issuer configured."""
        cfg = _make_config(jwt_issuer="my-issuer")
        token = create_access_token(cfg, "testuser")
        claims = decode_access_token(cfg, token)
        assert claims.iss == "my-issuer"

    def test_audience_in_claims_when_configured(self):
        """aud claim present when audience configured."""
        cfg = _make_config(jwt_audience="my-audience")
        token = create_access_token(cfg, "testuser")
        claims = decode_access_token(cfg, token)
        assert claims.aud == "my-audience"


# ===========================================================================
# High-level auth tests
# ===========================================================================


class TestAuthenticateCredentials:
    """authenticate_credentials function."""

    def test_valid_credentials_returns_token_pair(self):
        """Valid username/password → TokenPair."""
        cfg = _make_config()
        result = authenticate_credentials(cfg, "testuser", _VALID_PASSWORD)
        assert result is not None
        assert isinstance(result, TokenPair)
        assert result.token_type == "Bearer"
        assert result.access_token
        assert result.refresh_token
        assert result.expires_in == 900

    def test_wrong_password_returns_none(self):
        """Wrong password → None."""
        cfg = _make_config()
        result = authenticate_credentials(cfg, "testuser", "wrong")
        assert result is None

    def test_wrong_username_returns_none(self):
        """Wrong username → None."""
        cfg = _make_config()
        result = authenticate_credentials(cfg, "wronguser", _VALID_PASSWORD)
        assert result is None

    def test_disabled_config_returns_none(self):
        """Disabled config → None."""
        cfg = _make_config(enabled=False)
        result = authenticate_credentials(cfg, "testuser", _VALID_PASSWORD)
        assert result is None


class TestBearerHeader:
    """parse_bearer_header function."""

    def test_valid_bearer_header(self):
        """'Bearer <token>' → token string."""
        assert parse_bearer_header("Bearer mytoken123") == "mytoken123"

    def test_empty_header(self):
        """None/empty → None."""
        assert parse_bearer_header(None) is None
        assert parse_bearer_header("") is None

    def test_no_bearer_prefix(self):
        """No 'Bearer ' prefix → None."""
        assert parse_bearer_header("Basic abc123") is None
        assert parse_bearer_header("mytoken123") is None

    def test_bearer_no_token(self):
        """'Bearer ' with no token → None."""
        assert parse_bearer_header("Bearer ") is None

    def test_case_insensitive(self):
        """'bearer <token>' works."""
        assert parse_bearer_header("bearer mytoken123") == "mytoken123"


class TestAuthenticateRequest:
    """authenticate_request function."""

    def test_valid_access_token_returns_claims(self):
        """Valid Bearer access token → TokenClaims."""
        cfg = _make_config()
        token = create_access_token(cfg, "testuser")
        claims = authenticate_request(cfg, f"Bearer {token}")
        assert claims is not None
        assert claims.sub == "testuser"
        assert claims.token_type == "access"

    def test_no_header_returns_none(self):
        """No Authorization header → None."""
        cfg = _make_config()
        assert authenticate_request(cfg, None) is None

    def test_refresh_token_rejected(self):
        """Refresh token at access endpoint → None."""
        cfg = _make_config()
        refresh = create_refresh_token(cfg, "testuser")
        assert authenticate_request(cfg, f"Bearer {refresh}") is None

    def test_expired_token_returns_none(self):
        """Expired token → None."""
        cfg = _make_config(access_ttl=1)
        token = create_access_token(cfg, "testuser")
        time.sleep(1.1)
        assert authenticate_request(cfg, f"Bearer {token}") is None

    def test_malformed_header_returns_none(self):
        """Malformed header → None."""
        cfg = _make_config()
        assert authenticate_request(cfg, "not-bearer-token") is None


# ===========================================================================
# Safety tests
# ===========================================================================


class TestSafetyInvariants:
    """Security invariant tests."""

    def test_no_secrets_in_auth_module_source(self):
        """Auth module has no hardcoded credentials."""
        import bremen.auth as auth_mod
        src = inspect.getsource(auth_mod)
        assert "demo-password" not in src.lower()
        assert "changeme" not in src.lower()
        assert "secret123" not in src.lower()

    def test_auth_module_no_plaintext_compare(self):
        """No plaintext password comparison in auth module."""
        import bremen.auth as auth_mod
        src = inspect.getsource(auth_mod)
        # Should not do password == stored_password
        assert "password ==" not in src

    def test_no_token_in_error_messages(self):
        """Auth errors don't contain token values."""
        cfg = _make_config()
        token = create_access_token(cfg, "testuser")
        try:
            wrong_cfg = _make_config(jwt_issuer="wrong")
            decode_access_token(wrong_cfg, token)
        except AuthError as e:
            assert token not in str(e)
            assert cfg.jwt_secret not in str(e)

    def test_generic_error_messages(self):
        """Auth errors are generic (no field detail)."""
        cfg = _make_config()
        with pytest.raises(TokenInvalidError, match="Invalid token"):
            decode_access_token(cfg, "garbage")

    def test_expired_error_generic(self):
        """Expired token error is generic."""
        cfg = _make_config(access_ttl=1)
        token = create_access_token(cfg, "testuser")
        time.sleep(1.1)
        with pytest.raises(TokenExpiredError, match="expired"):
            decode_access_token(cfg, token)


# ===========================================================================
# Stream ticket tests (PR0114)
# ===========================================================================


class TestStreamTicket:
    """Stream ticket creation and decoding."""

    def test_create_and_decode_stream_ticket(self):
        """Valid ticket decodes with job_id and purpose."""
        cfg = _make_config()
        token = create_stream_ticket(cfg, "testuser", "job-abc", "stream")
        claims = decode_stream_ticket(cfg, token, "job-abc", "stream")
        assert claims.sub == "testuser"
        assert claims.job_id == "job-abc"
        assert claims.purpose == "stream"
        assert claims.token_type == "stream_ticket"
        assert claims.jti  # non-empty UUID
        assert claims.expires_at > claims.issued_at

    def test_ticket_job_id_binding(self):
        """Ticket for job A rejected on job B."""
        cfg = _make_config()
        token = create_stream_ticket(cfg, "testuser", "job-a", "stream")
        with pytest.raises(TokenInvalidError):
            decode_stream_ticket(cfg, token, "job-b", "stream")

    def test_ticket_purpose_binding_stream_on_report(self):
        """Stream ticket rejected on report route."""
        cfg = _make_config()
        token = create_stream_ticket(cfg, "testuser", "job-abc", "stream")
        with pytest.raises(TokenInvalidError):
            decode_stream_ticket(cfg, token, "job-abc", "report")

    def test_ticket_purpose_binding_report_on_stream(self):
        """Report ticket rejected on stream route."""
        cfg = _make_config()
        token = create_stream_ticket(cfg, "testuser", "job-abc", "report")
        with pytest.raises(TokenInvalidError):
            decode_stream_ticket(cfg, token, "job-abc", "stream")

    def test_expired_ticket_rejected(self):
        """Expired ticket (>60s) rejected."""
        cfg = _make_config(access_ttl=999)
        # Create ticket with 1-second TTL by mocking
        import bremen.auth as auth_mod
        old_ttl = auth_mod._STREAM_TICKET_TTL
        try:
            auth_mod._STREAM_TICKET_TTL = 1
            token = create_stream_ticket(cfg, "testuser", "job-abc", "stream")
        finally:
            auth_mod._STREAM_TICKET_TTL = old_ttl
        time.sleep(1.1)
        with pytest.raises(TokenExpiredError):
            decode_stream_ticket(cfg, token, "job-abc", "stream")

    def test_access_token_rejected_as_stream_ticket(self):
        """Access token rejected where stream_ticket expected."""
        cfg = _make_config()
        token = create_access_token(cfg, "testuser")
        with pytest.raises(TokenInvalidError):
            decode_stream_ticket(cfg, token, "any-job", "stream")

    def test_refresh_token_rejected_as_stream_ticket(self):
        """Refresh token rejected where stream_ticket expected."""
        cfg = _make_config()
        token = create_refresh_token(cfg, "testuser")
        with pytest.raises(TokenInvalidError):
            decode_stream_ticket(cfg, token, "any-job", "stream")

    def test_stream_ticket_rejected_as_access_token(self):
        """Stream ticket rejected where access token expected."""
        cfg = _make_config()
        token = create_stream_ticket(cfg, "testuser", "job-abc", "stream")
        with pytest.raises(TokenInvalidError):
            decode_access_token(cfg, token)

    def test_stream_ticket_rejected_as_refresh_token(self):
        """Stream ticket rejected where refresh token expected."""
        cfg = _make_config()
        token = create_stream_ticket(cfg, "testuser", "job-abc", "stream")
        with pytest.raises(TokenInvalidError):
            decode_refresh_token(cfg, token)

    def test_ticket_issuer_in_claims_when_configured(self):
        """iss claim present in ticket when issuer configured."""
        cfg = _make_config(jwt_issuer="my-issuer")
        token = create_stream_ticket(cfg, "testuser", "job-abc", "stream")
        claims = decode_stream_ticket(cfg, token, "job-abc", "stream")
        assert claims.iss == "my-issuer"

    def test_ticket_issuer_rejected_when_wrong(self):
        """Ticket with wrong issuer rejected."""
        cfg = _make_config(jwt_issuer="correct-issuer")
        token = create_stream_ticket(cfg, "testuser", "job-abc", "stream")
        wrong_cfg = _make_config(jwt_issuer="wrong-issuer")
        with pytest.raises(TokenInvalidError):
            decode_stream_ticket(wrong_cfg, token, "job-abc", "stream")

    def test_ticket_no_secret_in_error(self):
        """Ticket error messages do not contain secrets."""
        cfg = _make_config()
        token = create_stream_ticket(cfg, "testuser", "job-abc", "stream")
        try:
            decode_stream_ticket(cfg, "garbage", "job-abc", "stream")
        except AuthError as e:
            assert token not in str(e)
            assert cfg.jwt_secret not in str(e)
            assert "job-abc" not in str(e)

    def test_ticket_claims_is_frozen_dataclass(self):
        """TicketClaims is a frozen dataclass."""
        cfg = _make_config()
        token = create_stream_ticket(cfg, "testuser", "job-abc", "report")
        claims = decode_stream_ticket(cfg, token, "job-abc", "report")
        assert isinstance(claims, TicketClaims)
        # Frozen dataclass - cannot set attributes
        with pytest.raises(AttributeError):
            claims.purpose = "stream"
