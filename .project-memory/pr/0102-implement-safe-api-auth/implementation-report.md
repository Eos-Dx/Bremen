# Implementation Report — PR0102: Safe API Bearer/JWT Authentication

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/config.py` | Added AuthConfig dataclass and read_auth_config() |
| `src/bremen/auth.py` | New: password verification, JWT issuance/validation, safe errors |
| `src/bremen/login_ui.py` | New: minimal login page |
| `src/bremen/api/server.py` | Added auth endpoints, route protection, login route |
| `src/bremen/control_room_ui.py` | Added _authFetch wrapper for protected POST calls |
| `requirements.txt` | Added PyJWT>=2.0, argon2-cffi>=21.0 |
| `tests/test_bremen_auth.py` | New: 51 auth/config/JWT/safety tests |

## Plan References

- PLAN.md: PR0101 Safe API Bearer/JWT Authentication Implementation Plan
- THREAT_MODEL.md: Detailed threat analysis
- PLAN_REVIEW.yml: Approved with warnings documented

## Dependency Changes

Added to requirements.txt:
- `PyJWT>=2.0` — JWT creation and validation
- `argon2-cffi>=21.0` — Password hashing (argon2id)

No bcrypt added (argon2-cffi preferred per plan).

## Config Implementation

`AuthConfig` dataclass in `src/bremen/config.py`:
- `read_auth_config(env=None)` — never raises, records validation_error
- Injected env dict for testability
- Auth disabled by default
- Fail closed when enabled but incomplete config
- JWT secret minimum 32 characters, distinct from password hash
- TTL bounds: access 60-86400s, refresh 3600-2592000s
- No secret values in validation errors

## Auth Module Implementation

`src/bremen/auth.py`:
- `verify_password()` — argon2id verification, no plaintext compare
- `create_access_token()` / `create_refresh_token()` — HS256 JWT
- `decode_access_token()` / `decode_refresh_token()` — explicit algorithms=["HS256"]
- `authenticate_credentials()` — generic failure, logs safe strings only
- `parse_bearer_header()` / `authenticate_request()` — request middleware
- Exception types: AuthError, AuthenticationFailedError, TokenExpiredError, TokenInvalidError
- Claims: sub, iat, exp, token_type, jti, iss (when configured), aud (when configured)

## Endpoint Implementation

### Token Endpoint: POST /demo/api/auth/token
- Success: 200 with access_token, refresh_token, token_type, expires_in
- Invalid credentials: 401 generic error
- Auth disabled: 503

### Refresh Endpoint: POST /demo/api/auth/refresh
- Success: 200 with new token pair
- Invalid/expired/wrong-type: 401 generic error
- Auth disabled: 503

### Error Response Shape
```json
{"error": "Authentication failed", "token_type": "Bearer", "technical_demo_only": true}
```
No stack traces, config details, or JWT internals in errors.

## Route Protection Implementation

Protected POST endpoints (auth required when enabled):
- POST /demo/api/h5/containers (upload)
- POST /demo/api/stage (stage H5)
- POST /demo/api/h5/analyze (start analysis)
- POST /demo/api/jobs (create job, delete report)

Public endpoints (no auth required):
- All GET routes (control-room, workspace, api-docs, models, jobs, reports, health)
- Auth endpoints (token, refresh)
- Login page

## Frontend Integration

### Login Page
- Route: GET /demo/login
- Username/password form
- sessionStorage for tokens
- Redirects to /demo/control-room on success
- Shows error on failure

### Auth Fetch Wrapper
- `_authFetch()` in Control Room JS
- Attaches Bearer token to protected POST calls
- On 401: attempts refresh, retries once
- On refresh failure: clears sessionStorage, redirects to /demo/login
- Updated protected fetch calls: upload, job create, delete report

## Auth Disabled Behavior

When BREMEN_AUTH_ENABLED is not set or "false":
- All routes remain public
- No auth enforcement
- read_auth_config returns enabled=False

## Auth Enabled Behavior

When BREMEN_AUTH_ENABLED=true with complete config:
- Protected POST endpoints require valid Bearer access token
- Missing/invalid/expired token returns 401
- Incomplete config returns 503
- Valid token allows protected action

## Auth Does Not Expand Visibility

Confirmed: Auth gates actions only, not data. Same handler functions serve authed and unauthed requests. The auth check only gates whether the handler runs at all.

## Safe Error Handling

- Generic "Authentication failed" for all auth errors
- No stack traces in responses
- No config details leaked
- No JWT parse internals exposed
- Safe logging: "auth.login.failed", "auth.token.issued"

## Tests Added

51 tests in `tests/test_bremen_auth.py`:

Config tests (14): disabled default, enabled complete, missing username/hash/secret, short secret, TTL parsing/bounds, injected env, never raises, round-trip, no secret in errors, distinct secret

Password tests (5): valid passes, invalid fails, malformed hash, empty password, no plaintext compare

JWT tests (14): required claims, refresh token_type, expired rejected, wrong type rejected, wrong issuer/audience rejected, explicit algorithm, alg=none rejected, alg=HS512 rejected, valid accepted, malformed rejected, iss/aud in claims

Auth credential tests (4): valid returns pair, wrong password, wrong username, disabled config

Bearer header tests (5): valid, empty, no prefix, bearer no token, case insensitive

Authenticate request tests (5): valid claims, no header, refresh rejected, expired, malformed

Safety tests (4): no secrets in source, no plaintext compare, no token in errors, generic messages

## Validation Results

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_auth.py` | 51 passed |
| `pytest tests/test_bremen_control_room.py` (PR0099J) | 88 passed |
| `pytest tests/test_bremen_api_docs.py` | 77 passed |
| `pytest` (full suite) | 2849 passed, 11 skipped, 0 failed |
| Dependency check | PyJWT, argon2-cffi in requirements.txt |
| `git diff --check` | Clean |

## Warnings

1. **Stateless refresh JWT**: No server-side revocation before natural expiry. Documented in PLAN.md and THREAT_MODEL.md. Acceptable for demo stage.

2. **No rate limiting**: Token endpoint has no rate limiting. Argon2id slows brute force. Deferred per PLAN.md.

3. **sessionStorage**: Tokens stored in sessionStorage. Same-origin JS accessible. Acceptable for demo with no third-party scripts.

## Blockers

None.

## Confirmation Statements

- Auth does not expand visibility: CONFIRMED
- No secrets or default credentials: CONFIRMED (no hardcoded credentials in source)
- No raw/private data exposure after auth: CONFIRMED
- Auth disabled by default: CONFIRMED
- Fail closed behavior: CONFIRMED
- Generic error messages only: CONFIRMED
- Safe logging (no secrets): CONFIRMED

## Next Required Action

Human review and commit.
