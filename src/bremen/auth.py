"""Safe Bearer/JWT authentication module for Bremen demo API.

PR0102 — Safe API Bearer/JWT authentication.
Planning basis: PR0101.

This module provides:
- AuthConfig consumption
- Password verification (argon2id)
- JWT access token issuance and validation
- JWT refresh token issuance and validation
- No raw secrets, credentials, or internals exposed
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import jwt

if TYPE_CHECKING:
    from .config import AuthConfig

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------


class AuthError(Exception):
    """Base auth exception — safe message only, no internals."""


class AuthenticationFailedError(AuthError):
    """Generic auth failure — no detail about which field was wrong."""


class TokenExpiredError(AuthError):
    """Token is expired."""


class TokenInvalidError(AuthError):
    """Token is invalid (bad signature, wrong type, malformed)."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenPair:
    """A pair of access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900


@dataclass(frozen=True)
class TokenClaims:
    """Decoded JWT claims."""

    sub: str
    iat: float
    exp: float
    token_type: str  # "access" or "refresh"
    jti: str
    iss: str | None = None
    aud: str | None = None


@dataclass(frozen=True)
class TicketClaims:
    """Decoded ticket JWT claims (distinct from TokenClaims)."""

    sub: str
    issued_at: float
    expires_at: float
    token_type: str  # always "stream_ticket"
    jti: str
    job_id: str
    purpose: str  # "stream" or "report"
    iss: str | None = None


# ---------------------------------------------------------------------------
# Password verification
# ---------------------------------------------------------------------------

# Lazy import to avoid import error if argon2-cffi not installed
_argon2_hasher = None


def _get_hasher():
    """Get or create argon2 PasswordHasher (lazy import)."""
    global _argon2_hasher  # noqa: PLW0603
    if _argon2_hasher is None:
        from argon2 import PasswordHasher
        _argon2_hasher = PasswordHasher()
    return _argon2_hasher


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against the stored hash (argon2id).

    Returns True if password matches, False otherwise.
    Never reveals which part of the credential was wrong.
    """
    try:
        hasher = _get_hasher()
        return hasher.verify(password_hash, password)
    except Exception:  # noqa: BLE001
        # argon2 raises various exceptions for invalid hash format
        # or wrong password — we treat all as "not verified"
        return False


# ---------------------------------------------------------------------------
# JWT token creation
# ---------------------------------------------------------------------------


def create_access_token(config: AuthConfig, username: str) -> str:
    """Create a short-lived JWT access token.

    Claims:
    - sub: username
    - iat: now
    - exp: now + access_ttl_seconds
    - token_type: "access"
    - jti: random UUID
    - iss: config.jwt_issuer (if non-empty)
    - aud: config.jwt_audience (if non-empty)

    Algorithm: HS256.
    """
    now = time.time()
    claims: dict = {
        "sub": username,
        "iat": now,
        "exp": now + config.access_ttl_seconds,
        "token_type": "access",
        "jti": str(uuid.uuid4()),
    }
    if config.jwt_issuer:
        claims["iss"] = config.jwt_issuer
    if config.jwt_audience:
        claims["aud"] = config.jwt_audience
    return jwt.encode(claims, config.jwt_secret, algorithm="HS256")


def create_refresh_token(config: AuthConfig, username: str) -> str:
    """Create a longer-lived JWT refresh token.

    Claims: same as access token except:
    - token_type: "refresh"
    - exp: now + refresh_ttl_seconds
    """
    now = time.time()
    claims: dict = {
        "sub": username,
        "iat": now,
        "exp": now + config.refresh_ttl_seconds,
        "token_type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    if config.jwt_issuer:
        claims["iss"] = config.jwt_issuer
    if config.jwt_audience:
        claims["aud"] = config.jwt_audience
    return jwt.encode(claims, config.jwt_secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# JWT token decoding
# ---------------------------------------------------------------------------


def _decode_token(config: AuthConfig, token: str, expected_type: str) -> TokenClaims:
    """Decode and validate a JWT token.

    Validates:
    - Signature matches config.jwt_secret
    - Algorithm is HS256 (explicit, not from header)
    - token_type matches expected_type
    - exp is not expired
    - iss matches config.jwt_issuer if configured
    - aud matches config.jwt_audience if configured

    Raises: TokenExpiredError, TokenInvalidError, AuthenticationFailedError.
    Never returns raw JWT internals or config values in error messages.
    """
    try:
        kwargs: dict = {
            "algorithms": ["HS256"],
            "options": {"require": ["sub", "iat", "exp", "token_type", "jti"]},
        }
        if config.jwt_issuer:
            kwargs["issuer"] = config.jwt_issuer
        if config.jwt_audience:
            kwargs["audience"] = config.jwt_audience

        payload = jwt.decode(token, config.jwt_secret, **kwargs)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired") from None
    except jwt.InvalidTokenError as exc:
        # Catch-all for malformed, bad signature, wrong issuer/aud, etc.
        raise TokenInvalidError("Invalid token") from exc

    # Validate token_type
    if payload.get("token_type") != expected_type:
        raise TokenInvalidError("Invalid token")

    return TokenClaims(
        sub=payload["sub"],
        iat=float(payload["iat"]),
        exp=float(payload["exp"]),
        token_type=payload["token_type"],
        jti=payload["jti"],
        iss=payload.get("iss"),
        aud=payload.get("aud"),
    )


# ---------------------------------------------------------------------------
# Stream/report ticket tokens (PR0114)
# ---------------------------------------------------------------------------

_STREAM_TICKET_TTL = 60  # seconds
_STREAM_TICKET_TYPE = "stream_ticket"
_VALID_PURPOSES = frozenset({"stream", "report", "workspace"})


def create_stream_ticket(
    config: AuthConfig,
    username: str,
    job_id: str,
    purpose: str,
) -> str:
    """Create a short-lived, job-bound ticket for SSE/report-page auth.

    The ticket is a distinct JWT token type (stream_ticket) that cannot
    be used as an access or refresh token.
    """
    now = time.time()
    claims: dict = {
        "sub": username,
        "iat": now,
        "exp": now + _STREAM_TICKET_TTL,
        "token_type": _STREAM_TICKET_TYPE,
        "jti": str(uuid.uuid4()),
        "job_id": job_id,
        "purpose": purpose,
    }
    if config.jwt_issuer:
        claims["iss"] = config.jwt_issuer
    return jwt.encode(claims, config.jwt_secret, algorithm="HS256")


def decode_stream_ticket(
    config: AuthConfig,
    token: str,
    expected_job_id: str,
    expected_purpose: str,
) -> TicketClaims:
    """Decode and validate a stream/report ticket.

    Validates:
    - Signature matches config.jwt_secret
    - Algorithm is HS256
    - token_type == "stream_ticket"
    - exp is not expired
    - job_id matches expected_job_id
    - purpose matches expected_purpose
    """
    if expected_purpose not in _VALID_PURPOSES:
        raise TokenInvalidError("Invalid token")

    try:
        kwargs: dict = {
            "algorithms": ["HS256"],
            "options": {"require": ["sub", "iat", "exp", "token_type", "jti", "job_id", "purpose"]},
        }
        if config.jwt_issuer:
            kwargs["issuer"] = config.jwt_issuer
        payload = jwt.decode(token, config.jwt_secret, **kwargs)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired") from None
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError("Invalid token") from exc

    # Validate token_type
    if payload.get("token_type") != _STREAM_TICKET_TYPE:
        raise TokenInvalidError("Invalid token")

    # Validate job_id binding
    if payload.get("job_id") != expected_job_id:
        raise TokenInvalidError("Invalid token")

    # Validate purpose binding
    if payload.get("purpose") != expected_purpose:
        raise TokenInvalidError("Invalid token")

    return TicketClaims(
        sub=payload["sub"],
        issued_at=float(payload["iat"]),
        expires_at=float(payload["exp"]),
        token_type=payload["token_type"],
        jti=payload["jti"],
        job_id=payload["job_id"],
        purpose=payload["purpose"],
        iss=payload.get("iss"),
    )


def decode_access_token(config: AuthConfig, token: str) -> TokenClaims:
    """Decode and validate an access token."""
    return _decode_token(config, token, "access")


def decode_refresh_token(config: AuthConfig, token: str) -> TokenClaims:
    """Decode and validate a refresh token."""
    return _decode_token(config, token, "refresh")


# ---------------------------------------------------------------------------
# High-level auth functions
# ---------------------------------------------------------------------------


def authenticate_credentials(
    config: AuthConfig,
    username: str,
    password: str,
) -> TokenPair | None:
    """Verify username and password, return token pair if valid.

    Returns None for any failure (wrong username, wrong password,
    config disabled). Never reveals which field was wrong.
    """
    if not config.enabled:
        return None

    if username != config.username:
        _log.warning("auth.login.failed\tusername=%s", username)
        return None

    if not verify_password(password, config.password_hash):
        _log.warning("auth.login.failed\tusername=%s", username)
        return None

    _log.info("auth.token.issued")
    access = create_access_token(config, username)
    refresh = create_refresh_token(config, username)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        token_type="Bearer",
        expires_in=config.access_ttl_seconds,
    )


def parse_bearer_header(header: str | None) -> str | None:
    """Extract token from 'Bearer <token>' header.

    Returns the token string, or None if header is missing/malformed.
    """
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    return token


def authenticate_request(
    config: AuthConfig,
    authorization_header: str | None,
) -> TokenClaims | None:
    """Extract and validate Bearer token from Authorization header.

    Returns TokenClaims on success, None on any failure.
    Safe for use as request middleware.
    """
    if not config.enabled:
        return None

    token = parse_bearer_header(authorization_header)
    if not token:
        return None

    try:
        return decode_access_token(config, token)
    except AuthError:
        return None
