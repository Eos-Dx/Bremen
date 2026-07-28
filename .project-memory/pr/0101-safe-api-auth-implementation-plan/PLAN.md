# PR0101 — Safe API Bearer/JWT Authentication Implementation Plan

## PLAN COMPLETE

## SCOPE

### What PR0102 will implement

1. **Auth configuration** — new env-var-based auth config reader in an `auth_config.py` module (or `config.py` extension), following the existing `read_cloud_config()` pattern with injected env dict for testability.
2. **Auth module** — `src/bremen/auth.py` containing:
   - Password verification against a stored hash (argon2).
   - JWT access token issuance and validation (PyJWT, HS256, explicit algorithm enforcement).
   - JWT refresh token issuance and validation (stateless, token_type claim differentiation).
   - Safe error types (generic auth failure, no leakage of internals).
3. **Token endpoint** — `POST /api/auth/token` at `/demo/api/auth/token` under the demo namespace.
4. **Refresh endpoint** — `POST /api/auth/refresh` at `/demo/api/auth/refresh`.
5. **Route protection decorator/middleware** — lightweight auth gate that checks the `Authorization: Bearer <token>` header for protected actions.
6. **Protected actions** — the specific state-changing endpoints listed in §Route Protection Design below.
7. **Auth-disabled mode** — when `BREMEN_AUTH_ENABLED` is not set or `false`, all routes remain public as today.
8. **Login form UI** — minimal login page/modal for the demo UI (auth page served at `/demo/login`).
9. **Client-side token handling** — fetch wrapper that attaches Bearer token and handles refresh.
10. **Safe error handling** — all auth errors return generic messages; no stack traces, config details, or JWT internals leaked.

### What PR0102 will NOT implement

- Database-backed user management (future PR).
- Per-user roles/scopes (future PR).
- Token revocation/blacklisting (requires server-side state; future PR).
- Auth audit event logging (future PR).
- Secret manager integration (future PR).
- JWT signing secret rotation (future PR).
- Rate limiting on token endpoint (future PR).
- HTTPS enforcement (deployment-level concern).
- CORS policy for public API (future PR).
- Logout endpoint with true server-side revocation (stateless refresh JWT trade-off; logout endpoint with client-side token discard may be added but is documented as not true revocation).
- Any change to demo page visibility — auth gates actions only, not data.

## SECURITY INVARIANTS

1. **Auth gates actions only** — authentication determines WHO can perform state-changing operations, not WHAT data they see.
2. **Auth does not expand data visibility** — authenticated users receive the same safe payloads as public demo users.
3. **No raw/private/internal fields unlocked by login** — specifically prohibited from unlocking: raw feature values, full checksums, raw H5 internals, raw S3 refs, model coefficients, PHI, model package internals, raw exception traces.
4. **Fail closed** — when `BREMEN_AUTH_ENABLED=true` and required env vars (`BREMEN_AUTH_USERNAME`, `BREMEN_AUTH_PASSWORD_HASH`, `BREMEN_AUTH_JWT_SECRET`) are missing, the server MUST start but auth endpoints MUST return 503/error. The server must not start in a degraded partial-auth state.
5. **No secrets in frontend** — credentials and JWT secrets never appear in JavaScript source, HTML, or client-side code.
6. **No secrets in logs** — password verification attempts, token values, and env var values are never logged. Auth logs are safe strings only ("login attempt", "token issued", "auth error").
7. **No default credentials in repository** — no username/password defaults in code, config files, or documentation. The `example.env` or `.env.example` uses placeholder values.
8. **No credentials in frontend code** — the login form posts credentials to the token endpoint. Credentials are never embedded in HTML/JS.

## DEPENDENCY DECISION

### Required new dependency: PyJWT

- **Purpose**: JWT creation (`jwt.encode()`) and validation (`jwt.decode()`).
- **Algorithm**: HS256 only.
- **Safety**: `jwt.decode()` must be called with `algorithms=["HS256"]` explicitly, never relying on the token header algorithm.
- **Version**: Latest stable release (no pinning needed for demo, but pyproject.toml should specify `>=2.0`).
- **Alternatives considered**: stdlib-only approach rejected (no built-in JWT support); `python-jose` rejected (heavier, less maintained).

### Required new dependency: argon2-cffi

- **Purpose**: Password hashing and verification.
- **Justification**: Argon2id is the modern recommended password hashing algorithm (OWASP, NIST). It is memory-hard and resistant to GPU/ASIC attacks. It is the preferred choice over bcrypt for new implementations.
- **Alternatives considered**:
  - `bcrypt`: Mature, widely used, but less resistant to hardware-accelerated attacks. Acceptable but not preferred.
  - `hashlib`/`pbkdf2`: Stdlib-available but weaker than Argon2id. Rejected.
- **Recommendation**: argon2-cffi. If bcrypt is preferred for simplicity (pure Python dependency, smaller install), it is an acceptable alternative. The plan documents both but recommends argon2-cffi.
- **Implementation note**: `argon2.PasswordHasher` is the recommended API. Verify against the stored hash using `hasher.verify(hash, password)`.

### Dependency installation

The actual `requirements.txt` and `pyproject.toml` changes belong in PR0102 (implementation PR), not this planning PR. No dependency changes are made in PR0101.

## CONFIG DESIGN

### Module location

New config values should be added to the existing `src/bremen/config.py` as a new dataclass `AuthConfig` with a factory function `read_auth_config(env=None)`, following the exact same pattern as `read_cloud_config()` and `CloudConfig`.

### Env vars

| Variable | Required (when enabled) | Default | Validation |
|---|---|---|---|
| `BREMEN_AUTH_ENABLED` | No | `"false"` | Must be `"true"` (case-insensitive) to enable. Any other value → disabled. |
| `BREMEN_AUTH_USERNAME` | Yes, if enabled | — | Non-empty string. |
| `BREMEN_AUTH_PASSWORD_HASH` | Yes, if enabled | — | Non-empty string. Must start with `$argon2id$` prefix (argon2) or `$2b$`/`$2a$` (bcrypt). |
| `BREMEN_AUTH_JWT_SECRET` | Yes, if enabled | — | Non-empty string. Minimum 32 characters. Must be distinct from password hash. |
| `BREMEN_AUTH_JWT_ISSUER` | No | `"bremen-demo"` | Optional. When set, JWT `iss` claim is validated on decode. |
| `BREMEN_AUTH_JWT_AUDIENCE` | No | `"bremen-api"` | Optional. When set, JWT `aud` claim is validated on decode. |
| `BREMEN_AUTH_ACCESS_TTL_SECONDS` | No | `"900"` (15 min) | Integer. Clamped to minimum 60, maximum 86400 (24h). |
| `BREMEN_AUTH_REFRESH_TTL_SECONDS` | No | `"604800"` (7 days) | Integer. Clamped to minimum 3600 (1h), maximum 2592000 (30d). |

### Validation rules

```python
@dataclass(frozen=True)
class AuthConfig:
    enabled: bool
    username: str  # empty if disabled
    password_hash: str  # empty if disabled
    jwt_secret: str  # empty if disabled
    jwt_issuer: str
    jwt_audience: str
    access_ttl_seconds: int
    refresh_ttl_seconds: int
```

- If `enabled=False`: all other fields except `jwt_issuer`/`jwt_audience`/ttls are empty/zero. No auth enforcement.
- If `enabled=True`:
  - `username` must be non-empty → raise `CloudConfigError`.
  - `password_hash` must be non-empty and start with a recognized hash prefix → raise `CloudConfigError`.
  - `jwt_secret` must be ≥32 characters and not equal to `password_hash` → raise `CloudConfigError`.
  - `access_ttl_seconds` and `refresh_ttl_seconds` parsed as int, clamped to safe bounds.
- `read_auth_config()` must never raise. Validation errors result in a config with `enabled=False` and a `validation_error` field (string or None). The caller checks `validation_error` at startup.

### Issuer/audience decision

`issuer` and `audience` are **optional** for demo stage. When provided, they are enforced on decode. When absent, JWT decode omits `iss`/`aud` validation. This allows simple local deployment without requiring specific issuer/audience values. Production deployment should set both.

## AUTH MODULE DESIGN

### File: `src/bremen/auth.py`

```python
"""
Safe Bearer/JWT authentication module for Bremen demo API.

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
from dataclasses import dataclass
from typing import Any
import time
import uuid
import logging

_log = logging.getLogger(__name__)


class AuthError(Exception):
    """Base auth exception — safe message only, no internals."""


class AuthenticationFailedError(AuthError):
    """Generic auth failure — no detail about which field was wrong."""


class TokenExpiredError(AuthError):
    """Token is expired."""


class TokenInvalidError(AuthError):
    """Token is invalid (bad signature, wrong type, malformed)."""


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    iat: float
    exp: float
    token_type: str  # "access" or "refresh"
    jti: str
    iss: str | None = None
    aud: str | None = None


# --- Public API ---

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against the stored hash (argon2id).

    Returns True if password matches, False otherwise.
    Never reveals which part of the credential was wrong.
    No timing-safe concerns at demo stage (generic error returned either way).
    """


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


def create_refresh_token(config: AuthConfig, username: str) -> str:
    """Create a longer-lived JWT refresh token.

    Claims: same as access token except:
    - token_type: "refresh"
    - exp: now + refresh_ttl_seconds

    Decode must NOT accept a refresh token at an access-token-only endpoint.
    """


def decode_access_token(config: AuthConfig, token: str) -> TokenClaims:
    """Decode and validate an access token.

    Validates:
    - Signature matches config.jwt_secret
    - Algorithm is HS256 (explicit, not from header)
    - token_type == "access"
    - exp is not expired
    - iss matches config.jwt_issuer if configured
    - aud matches config.jwt_audience if configured

    Raises: TokenExpiredError, TokenInvalidError, AuthenticationFailedError.
    Never returns raw JWT internals or config values in error messages.
    """


def decode_refresh_token(config: AuthConfig, token: str) -> TokenClaims:
    """Decode and validate a refresh token.

    Same as decode_access_token but validates token_type == "refresh".
    """


def authenticate_credentials(
    config: AuthConfig, username: str, password: str
) -> TokenPair | None:
    """Verify username and password, return token pair if valid.

    Returns None for any failure (wrong username, wrong password,
    config disabled). Never reveals which field was wrong.
    """


# --- Request authentication ---

def authenticate_request(
    config: AuthConfig,
    authorization_header: str | None,
) -> TokenClaims | None:
    """Extract and validate Bearer token from Authorization header.

    Returns TokenClaims on success, None on any failure.
    Safe for use as request middleware.
    """
```

## ENDPOINT DESIGN

### Token endpoint: `POST /demo/api/auth/token`

**Request**:
```json
{
  "username": "<username>",
  "password": "<password>"
}
```

**Success response (200)**:
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**Error response (401)**:
```json
{
  "error": "Authentication failed",
  "token_type": "Bearer"
}
```

- Generic error for any credential failure. No "user not found" vs "wrong password" distinction.
- If auth is disabled, returns 503 with `{"error": "Authentication is not configured"}`.
- No rate limiting in demo stage.

### Refresh endpoint: `POST /demo/api/auth/refresh`

**Request**:
```json
{
  "refresh_token": "<refresh-jwt>"
}
```

**Success response (200)**:
```json
{
  "access_token": "<new-jwt>",
  "refresh_token": "<rotated-jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**Error responses**:
- 401 for invalid/expired refresh token: `{"error": "Authentication failed", "token_type": "Bearer"}`
- 401 if an access token is submitted to the refresh endpoint (wrong token_type): `{"error": "Authentication failed", "token_type": "Bearer"}`
- If auth is disabled, returns 503.

### Error response shape

All auth errors follow:
```json
{
  "error": "Authentication failed",
  "token_type": "Bearer",
  "technical_demo_only": true
}
```

No `detail`, no `reason`, no stack trace, no config reference.

## ROUTE PROTECTION DESIGN

### Protected actions (require valid access token)

These endpoints change state and MUST be protected when auth is enabled:

| Method | Route | Reason |
|---|---|---|
| POST | `/demo/api/h5/containers` | Upload H5 file — state-changing |
| POST | `/demo/api/stage` | Stage an H5 file — state-changing |
| POST | `/demo/api/h5/analyze` | Start analysis — state-changing |
| POST | `/demo/api/jobs` | Create analysis job — state-changing |
| POST | `/demo/api/jobs/*/events` | (If any POST exists for events) |
| Any | `/demo/api/reports/*` DELETE or state-changing report operation | Report deletion |

### Public endpoints (no auth required — remain open)

| Method | Route | Reason |
|---|---|---|
| GET | `/demo` | Start page — read-only |
| GET | `/demo/control-room` | Read-only UI |
| GET | `/demo/workspace` | Read-only UI |
| GET | `/demo/report/*` | Read-only report view |
| GET | `/demo/api-docs` | Documentation |
| GET | `/demo/api/models` | Model catalog — read-only |
| GET | `/demo/api/evidence` | Evidence bundle — read-only |
| GET | `/demo/api/h5/containers` | List containers — read-only |
| GET | `/demo/api/jobs` | List jobs — read-only |
| GET | `/demo/api/jobs/*` | Get job detail — read-only |
| GET | `/demo/api/jobs/*/events` | Get job events — read-only |
| GET | `/demo/api/reports/*` | Get report — read-only |
| GET | `/health` | Health check — must remain open |
| GET | `/model/version` | Model info — read-only |
| GET | `/predictions/*` | Prediction status (legacy) — read-only |

### Protection mechanism

Two approaches considered:

**Approach A (preferred for demo stage)**: A lightweight `@check_auth` decorator or wrapper function in `server.py` that wraps the handler functions for protected routes. Pattern:

```python
def _require_auth(handler_func):
    """Wrap a handler to require valid Bearer token when auth is enabled."""
    def wrapper(handler, *args, **kwargs):
        config = get_auth_config()  # lazily loaded singleton
        if not config.enabled:
            return handler_func(handler, *args, **kwargs)
        auth_header = handler.headers.get("Authorization", "")
        claims = authenticate_request(config, auth_header)
        if claims is None:
            _send_auth_error(handler)
            return
        return handler_func(handler, *args, **kwargs)
    return wrapper
```

**Approach B**: Centralized dispatch check in `do_POST()` and relevant `do_GET()` branches. Simpler but less reusable.

**Recommendation**: Approach A — it follows the existing pattern of wrapper functions already used in server.py (e.g., `_handle_*` functions are called from dispatch) and is the most maintainable for the demo stage.

### No protection on read-only safe pages

The Control Room, Workspace, Start page, Report page, and API docs page remain public. This preserves the demo experience while protecting state-changing actions.

## FRONTEND INTEGRATION PLAN

### Login page

A minimal login page at `/demo/login` (or a login modal within the Control Room page). The plan recommends a **separate minimal login page** to avoid cluttering the Control Room layout.

**Content**: Username field, password field, submit button. "Technical demo only. Not clinically validated." disclaimer at bottom. Link back to Start.

### Token storage

**Decision**: `sessionStorage`.

**Justification**: 
- `sessionStorage` is cleared when the tab closes — no persistent token across sessions.
- Does not survive browser restart (unlike `localStorage`).
- Safer than `localStorage` for demo tokens.
- Memory-only storage would lose tokens on page navigation/refresh, breaking the demo UX.

**Trade-off acknowledged**: `sessionStorage` is still accessible by any JavaScript on the same origin. For the demo stage where the threat model assumes same-origin JavaScript is trusted (no third-party scripts), this is acceptable.

### Fetch wrapper

A thin JavaScript fetch wrapper (`_authFetch()`) that:
1. Reads `access_token` from `sessionStorage`.
2. Attaches `Authorization: Bearer <token>` header.
3. If the response is 401, attempts a refresh using `refresh_token` from `sessionStorage`.
4. If refresh succeeds, retries the original request with the new access token.
5. If refresh fails, clears `sessionStorage`, redirects to `/demo/login`.

### Login flow

1. User clicks "Submit analysis" on a protected action.
2. If no token in `sessionStorage`, frontend shows login modal or redirects to `/demo/login`.
3. User enters credentials, frontend calls `POST /demo/api/auth/token`.
4. On success, tokens stored in `sessionStorage`, original action proceeds.
5. On failure, generic error message shown ("Authentication failed").

### Token refresh flow

1. Before each API call, check if access token is close to expiry.
2. If expired (API returns 401), call `POST /demo/api/auth/refresh`.
3. On success, store new tokens, retry original request.
4. On failure, clear sessionStorage, redirect to login.

### No credentials in frontend code

The login page never hardcodes credentials. The fetch wrapper never stores credentials. Environment variables are never accessible to frontend JavaScript.

## SAFE ERROR HANDLING

| Scenario | HTTP Status | Response | Logged |
|---|---|---|---|
| Invalid credentials | 401 | `{"error":"Authentication failed","token_type":"Bearer"}` | `auth.login.failed\tusername=<safe>` |
| Missing auth header | 401 | `{"error":"Authentication failed","token_type":"Bearer"}` | `auth.missing_header` |
| Expired token | 401 | `{"error":"Authentication failed","token_type":"Bearer"}` | `auth.token_expired` |
| Invalid token | 401 | `{"error":"Authentication failed","token_type":"Bearer"}` | `auth.token_invalid` |
| Auth disabled | 503 | `{"error":"Authentication is not configured"}` | — |
| Config validation error | 503 | `{"error":"Authentication is not configured"}` | `auth.config_invalid\t<safe_reason>` |

- No stack traces in responses.
- No config details (which field is missing, what the TTL bounds are).
- No JWT parse internals (signature invalid, wrong algorithm, etc.).
- No timing-sensitive verbose differences between "user not found" and "wrong password".
- Auth logs are safe strings only — no token values, no password values, no hash values.
- Log at INFO level for successful auth, WARNING for failed attempts.

## TEST PLAN

### Config tests (`tests/test_bremen_auth.py`)

| Test | Description |
|---|---|
| `test_auth_disabled_by_default` | No env vars → disabled |
| `test_auth_enabled_complete_config` | All required vars → enabled |
| `test_auth_enabled_missing_username` | Enabled but no username → disabled + validation_error |
| `test_auth_enabled_missing_password_hash` | Enabled but no hash → disabled + validation_error |
| `test_auth_enabled_missing_jwt_secret` | Enabled but no secret → disabled + validation_error |
| `test_auth_enabled_short_secret` | Secret < 32 chars → validation_error |
| `test_auth_ttl_parsing` | Valid/invalid TTL strings → bounds applied |
| `test_auth_ttl_bounds` | TTL clamped to min/max |
| `test_injected_env_dict` | Passing explicit env dict works for tests |
| `test_auth_config_never_raises` | `read_auth_config()` never throws |
| `test_auth_config_round_trip` | Environment → AuthConfig dataclass → field values correct |

### Password tests (`tests/test_bremen_auth.py`)

| Test | Description |
|---|---|
| `test_valid_password_passes` | Correct password → True |
| `test_invalid_password_fails` | Wrong password → False |
| `test_wrong_username_returns_none` | authenticate_credentials with wrong user → None |
| `test_plaintext_compare_not_used` | Verify no `==` comparison with stored hash in source |
| `test_hash_format_validation` | Invalid hash format detected at config time |

### JWT tests (`tests/test_bremen_auth.py`)

| Test | Description |
|---|---|
| `test_access_token_has_required_claims` | sub, iat, exp, token_type, jti present |
| `test_refresh_token_has_token_type` | token_type == "refresh" |
| `test_expired_token_rejected` | exp < now → TokenExpiredError |
| `test_wrong_token_type_rejected` | Refresh token at access decode → TokenInvalidError |
| `test_wrong_issuer_rejected` | When configured, wrong iss → TokenInvalidError |
| `test_wrong_audience_rejected` | When configured, wrong aud → TokenInvalidError |
| `test_decode_uses_explicit_algorithm` | Decode called with `algorithms=["HS256"]` |
| `test_algorithm_header_confusion_rejected` | Token with alg="none" rejected |
| `test_algorithm_header_confusion_hs512` | Token with alg="HS512" rejected (only HS256 allowed) |
| `test_valid_access_token_accepted` | Valid token → TokenClaims returned |
| `test_token_string_not_in_logs` | Token values never appear in log output |

### Endpoint tests (`tests/test_bremen_auth.py` or `tests/test_bremen_server.py`)

| Test | Description |
|---|---|
| `test_token_endpoint_success` | Valid credentials → 200 with token pair |
| `test_token_endpoint_invalid_credentials` | Invalid → 401 generic error |
| `test_token_endpoint_disabled` | Auth disabled → 503 |
| `test_refresh_endpoint_success` | Valid refresh token → 200 with new pair |
| `test_refresh_endpoint_rejects_access_token` | Access token at refresh → 401 |
| `test_refresh_endpoint_invalid_token` | Gibberish → 401 |
| `test_protected_action_without_token` | No Auth header → 401 |
| `test_protected_action_with_valid_token` | Valid token → request proceeds |
| `test_protected_action_with_expired_token` | Expired token → 401 |
| `test_protected_action_malformed_header` | "Bearer not-a-real-token" → 401 |
| `test_public_page_no_auth_required` | GET /demo/control-room → 200 without auth |
| `test_health_route_no_auth` | GET /health → 200 without auth |

### Safety tests (`tests/test_bremen_auth.py`)

| Test | Description |
|---|---|
| `test_auth_does_not_expand_report_payload` | Same report JSON returned authed vs unauthed |
| `test_no_full_checksums_after_auth` | No checksum beyond prefix exposed after auth |
| `test_no_raw_features_after_auth` | No feature values in authed response |
| `test_no_secrets_in_repo` | grep for hardcoded credentials returns nothing |
| `test_no_credentials_in_frontend_js` | JS source contains no credential strings |

### Regression tests

| Test | Description |
|---|---|
| `test_existing_control_room_tests_pass` | All existing control room tests pass |
| `test_existing_report_tests_pass` | Report/delete/duplicate tests pass |
| `test_existing_api_docs_tests_pass` | PR0100 docs tests pass |
| `test_full_suite_passes` | `python -m pytest -q` returns 0 failures |

## THREAT MODEL

See `THREAT_MODEL.md` for detailed threat analysis.

Summary of mitigated threats:
1. **Stolen access token** (15-min window) — mitigated by short TTL.
2. **Stolen refresh token** (7-day window) — mitigated by stateless design; risk acknowledged.
3. **Leaked env secret** — mitigated by independent secret generation, no repo defaults, no logs.
4. **Brute force login** — partially mitigated by generic error responses (no user enumeration); full rate limiting deferred.
5. **Algorithm confusion** — mitigated by explicit `algorithms=["HS256"]` in decode.
6. **Replay of refresh token** — accepted trade-off with stateless design.
7. **Multi-instance App Runner** — supported (stateless JWT, no server-side session).
8. **Logs leaking credentials/tokens** — mitigated by safe logging rules.
9. **Frontend token storage** — mitigated by `sessionStorage`, acknowledged risk.
10. **Accidental data exposure after auth** — mitigated by invariant: auth does not expand visibility.

## ROLLOUT PLAN

### Auth disabled by default

`BREMEN_AUTH_ENABLED` defaults to `false`. The server starts with no auth enforcement. All routes remain public. This is the **explicit default** — no silent security posture change.

### Local env example (`.env.example`)

```
# --- Authentication (optional, disabled by default) ---
# Set to "true" to enable Bearer/JWT authentication.
# BREMEN_AUTH_ENABLED=false
# BREMEN_AUTH_USERNAME=demo-user
# BREMEN_AUTH_PASSWORD_HASH=<generate with: python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('your-password'))">
# BREMEN_AUTH_JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
# BREMEN_AUTH_JWT_ISSUER=bremen-demo
# BREMEN_AUTH_JWT_AUDIENCE=bremen-api
# BREMEN_AUTH_ACCESS_TTL_SECONDS=900
# BREMEN_AUTH_REFRESH_TTL_SECONDS=604800
```

### Deployment env requirements

When deploying with auth enabled:
1. Generate a strong JWT secret: `python -c "import secrets; print(secrets.token_hex(32))"` (64 hex chars).
2. Generate a password hash: `python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('chosen-password'))"`.
3. Set all env vars in the deployment environment (App Runner, ECS, etc.).
4. Verify auth is enforced by hitting a protected route without a token → 401.
5. Verify public routes still work without auth → 200.

### Manual QA checklist

1. Start server with no auth env vars → all routes public.
2. Start server with `BREMEN_AUTH_ENABLED=true` but missing required vars → server starts, auth endpoints return 503.
3. Start server with complete auth config → token endpoint works.
4. POST valid credentials → 200 + access_token + refresh_token.
5. POST invalid credentials → 401 generic error.
6. Use access token on protected POST → 200 (or whatever the endpoint normally returns).
7. Use expired access token → 401.
8. Use refresh token to get new token pair → 200.
9. Use access token on refresh endpoint → 401.
10. Verify public GET routes (control-room, workspace, report, api-docs) → 200 without auth.
11. Verify no credentials/plaintext in logs.
12. Run full test suite → all pass.

## STOP CONDITIONS

The implementation PR (PR0102) must stop and escalate if:

1. **Auth would require exposing raw data** — if any protected endpoint needs raw feature values, full checksums, H5 internals, S3 refs, or model internals to function, stop. This indicates the protection boundary is wrong.

2. **Backend needs persistent user store now** — if the auth implementation requires a database, user registration flow, or persistent session store beyond what is planned for PR0102, stop. Database-backed users are a future PR.

3. **Route list cannot be protected safely** — if a state-changing endpoint cannot be reliably distinguished from a read-only endpoint in the dispatch logic, stop. This indicates a routing refactoring is needed first.

4. **Dependency choice cannot be resolved** — if PyJWT or argon2-cffi/bcrypt causes version conflicts, import failures, or platform incompatibilities, stop and document the resolution.

5. **Token storage cannot be made safe enough for demo** — if the recommended `sessionStorage` approach has a demonstrated vulnerability in the demo deployment context that cannot be mitigated, stop and escalate.

6. **Tests cannot cover security invariants** — if any invariant in §Security Invariants cannot be tested automatically (e.g., "auth does not expand visibility"), stop and document the gap.

7. **Existing tests fail and cannot be fixed within scope** — if the implementation breaks existing control room, report, or API docs tests and the fix requires changes outside the approved file list, stop.

8. **Auth enforcement changes demo page content** — if enabling auth causes different data to appear on demo pages (more or less data), stop. Auth gates actions only, not data.

## FILES WRITTEN

- `.project-memory/pr/0101-safe-api-auth-implementation-plan/PLAN.md`
- `.project-memory/pr/0101-safe-api-auth-implementation-plan/THREAT_MODEL.md` (optional, see separate file)

## BLOCKERS

None.

## WARNINGS

1. **Stateless refresh JWT trade-off**: No true server-side revocation before natural expiry. This is a known limitation of the demo-stage stateless approach. Logout endpoint, if added, can only discard the client-side token. True revocation requires server-side token state (database), which is planned for a future PR.

2. **No rate limiting in demo stage**: Brute force protection on the token endpoint is deferred. For demo/local deployment this is acceptable; for any exposed deployment, rate limiting (or at minimum fail2ban-style monitoring) should be added before production use.

3. **Auth configuration validation at startup**: The server starts even when auth config validation fails (fail closed = auth endpoints return 503, but the rest of the server works). This prevents a silent misconfiguration from locking out the entire server, but means the operator must actively check auth status.

4. **Frontend token storage in sessionStorage**: sessionStorage is accessible to any JavaScript on the same origin. For the demo stage where the threat model assumes no third-party scripts, this is acceptable. For any deployment serving third-party content, this must be re-evaluated.

## NEXT REQUIRED ACTION

Implementation PR (PR0102) with the following ordered steps:

1. Add `PyJWT` and `argon2-cffi` to `requirements.txt` / `pyproject.toml`.
2. Implement `read_auth_config()` in `config.py` (or new `auth_config.py`).
3. Implement `src/bremen/auth.py` with password verification, JWT creation/validation.
4. Add `POST /demo/api/auth/token` route handler in `server.py`.
5. Add `POST /demo/api/auth/refresh` route handler in `server.py`.
6. Implement `_require_auth()` wrapper and apply to protected routes.
7. Add login page (`src/bremen/login_ui.py`) and serve at `/demo/login`.
8. Add frontend JS fetch wrapper for token handling in Control Room / Workspace.
9. Write comprehensive tests (see §Test Plan above).
10. Manual QA (see §Rollout Plan above).
11. Verify full test suite passes.
12. Update `.env.example` with auth config comments.

Implementation agent: coder
