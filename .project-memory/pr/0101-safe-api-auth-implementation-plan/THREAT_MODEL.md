# Threat Model — PR0101/0102 Bremen Safe API Authentication

## Scope

This threat model covers the Bremen demo API authentication implementation planned for PR0102. It assumes a single-instance demo deployment (AWS App Runner or similar), with authentication gating state-changing actions only. Data visibility is unchanged by authentication.

## Assets Protected

| Asset | Sensitivity | Protection Mechanism |
|---|---|---|
| H5 upload/stage operation | Medium | Bearer token required |
| Analysis job creation | Medium | Bearer token required |
| Report deletion | Medium | Bearer token required |
| Access tokens | High | Signed with JWT secret; short TTL |
| Refresh tokens | High | Signed with JWT secret; medium TTL |
| Credentials (username/password) | High | Never stored; verified against hash |
| Password hash | High | Stored in env var, never logged |
| JWT secret | Critical | Stored in env var, never logged |

## Threat: Stolen Access Token

**Description**: An attacker obtains a valid access token (via XSS, network interception, or compromised client).

**Likelihood**: Low (demo deployment over localhost or HTTPS).

**Impact**: Attacker can perform state-changing actions for 15 minutes (default TTL).

**Mitigation**:
- Short TTL (15 min default, max 24h with explicit config).
- Token is not stored in `localStorage` (only `sessionStorage`).
- Token is only sent to the same origin.
- Auth gates actions only — no sensitive data exposed even with valid token.

**Residual risk**: Within the 15-minute window, an attacker with the token can perform any protected action. Acceptable for demo stage.

## Threat: Stolen Refresh Token

**Description**: An attacker obtains a valid refresh token.

**Likelihood**: Low (same access vector as access token).

**Impact**: Attacker can obtain new access tokens for up to 7 days (default refresh TTL). No true server-side revocation.

**Mitigation**:
- Refresh token is stored in `sessionStorage` (cleared on tab close).
- Rotated on each refresh use (new refresh token issued, old one becomes invalid for stateless tokens if `jti` is tracked — but demo stage is stateless, so rotation only helps if the old token is discarded by the client).
- Access token TTL is short — even with a stolen refresh token, the attacker must actively refresh.

**Residual risk**: Without server-side token state, a stolen refresh token cannot be explicitly revoked before expiry. This is the primary trade-off of the stateless design. Acceptable for demo stage. **Future**: Server-side token blacklist in database.

## Threat: Leaked JWT Secret

**Description**: `BREMEN_AUTH_JWT_SECRET` is exposed via env var leak, log, or configuration file.

**Likelihood**: Low (env vars are not logged; config file not in repo).

**Impact**: Critical — attacker can forge arbitrary tokens, including tokens for any username, with any expiry.

**Mitigation**:
- JWT secret is never logged.
- Not in `.env.example` (only placeholder comment).
- Minimum 32-character length enforced.
- Must be distinct from password hash.
- Generated independently per deployment.

**Residual risk**: If the env var is leaked, all tokens are compromised until the secret is rotated. Rotation requires deployment restart. Acceptable for demo stage.

## Threat: Brute Force Login

**Description**: Attacker repeatedly attempts username/password combinations against the token endpoint.

**Likelihood**: Medium (token endpoint is public).

**Impact**: Account compromise if password is weak.

**Mitigation**:
- Generic error response for any failure — no distinction between "user not found" and "wrong password".
- Password hash is verified using argon2id (memory-hard, slow to verify).
- Single credential pair (only one username exists in demo stage) — no user enumeration possible.
- **Not mitigated in demo stage**: No rate limiting. This is a known gap.

**Residual risk**: Without rate limiting, an attacker can attempt many passwords. Argon2id slows this down significantly but does not prevent it. Acceptable for demo stage. **Future**: Rate limiting on token endpoint.

## Threat: Algorithm Confusion (JWT)

**Description**: Attacker crafts a JWT with `alg: "none"` or `alg: "HS256"` but signed with a different key, exploiting decode implementation that trusts the header.

**Likelihood**: Low (prevented by explicit algorithm specification).

**Impact**: Critical — forged token accepted as valid.

**Mitigation**:
- `jwt.decode()` called with `algorithms=["HS256"]` explicitly.
- Implementation never uses `algorithms` parameter from the token header.
- Test verifies that a token with `alg="none"` is rejected.
- Test verifies that a token with `alg="HS512"` is rejected.

**Residual risk**: Eliminated by explicit algorithm enforcement.

## Threat: Replay of Refresh Token

**Description**: Attacker intercepts a refresh token and uses it before the legitimate client.

**Likelihood**: Low (requires network interception).

**Impact**: Attacker obtains a new access token; legitimate user's token may still work.

**Mitigation**: 
- Stateless design means the same refresh token can be used multiple times until expiry.
- Rotation: each refresh returns a new refresh token. The client overwrites the old one. If the attacker uses the old one, it still works (stateless). The legitimate client will get a 401 on its next attempt and re-login.
- **Not mitigated in demo stage**: No server-side tracking of used refresh tokens.

**Residual risk**: A replayed refresh token works until expiry. Acceptable for demo stage.

## Threat: Multi-Instance App Runner — Token Signed on Different Instance

**Description**: With multiple App Runner instances, a token signed by one instance must be verifiable by another.

**Likelihood**: High (App Runner may run multiple instances).

**Impact**: Token rejected by wrong instance.

**Mitigation**: Stateless JWT with shared secret — all instances share `BREMEN_AUTH_JWT_SECRET` via environment variable. No instance-specific state. Works across any number of instances.

**Residual risk**: None — this is a strength of the stateless JWT approach.

## Threat: Logs Leaking Credentials or Tokens

**Description**: Password, password hash, JWT secret, or token values appear in server logs.

**Likelihood**: Medium (if logging is not carefully implemented).

**Impact**: Credential or token compromise via log access.

**Mitigation**:
- Auth module never logs password, hash, token, or secret values.
- Auth logs use safe strings only: `"auth.login.failed\tusername=demo-user"`, `"auth.token.issued"`.
- Token values never appear in log messages.
- Code review enforces no `repr()` or `str()` on secret values in log calls.

**Residual risk**: Eliminated by safe logging rules.

## Threat: Frontend Token Storage (XSS)

**Description**: Cross-site scripting (XSS) attack reads `sessionStorage`.

**Likelihood**: Low (no third-party scripts, minimal JS surface).

**Impact**: Attacker reads tokens from `sessionStorage`.

**Mitigation**:
- `sessionStorage` is same-origin only.
- No third-party JavaScript included in demo pages.
- Token is short-lived (15 min access, 7 day refresh).
- Auth gates actions only — even with a stolen token, no sensitive data is exposed.

**Residual risk**: If an XSS vulnerability exists, token theft is possible. Acceptable for demo stage. **Future**: Consider HTTP-only cookies for token storage (requires different backend design).

## Threat: Accidental Data Exposure After Auth

**Description**: Authenticated routes accidentally return more data than public routes.

**Likelihood**: Low (prevented by architecture invariant and tests).

**Impact**: Sensitive data (raw checksums, H5 internals, feature values) exposed to authenticated users.

**Mitigation**:
- Architecture invariant: auth does not expand visibility.
- Same handler functions serve authed and unauthed requests — the auth check only gates whether the handler runs at all, not which data it returns.
- Safety tests verify that the same report JSON is returned regardless of auth status.
- Any future fuller authenticated view requires a separate PR and safety review.

**Residual risk**: Eliminated by architecture invariant.

## Summary

| Threat | Severity | Mitigated | Residual Risk |
|---|---|---|---|
| Stolen access token | Medium | Yes | 15-min window |
| Stolen refresh token | Medium | Partial | 7-day window; no revocation |
| Leaked JWT secret | Critical | Yes | Secret rotation gap |
| Brute force login | Medium | Partial | No rate limiting |
| Algorithm confusion | Critical | Yes | Eliminated |
| Replay of refresh token | Medium | Partial | Works until expiry |
| Multi-instance signing | Low | Yes | Eliminated |
| Log leakage | High | Yes | Eliminated |
| XSS token theft | Medium | Partial | sessionStorage risk |
| Data exposure after auth | High | Yes | Eliminated |
