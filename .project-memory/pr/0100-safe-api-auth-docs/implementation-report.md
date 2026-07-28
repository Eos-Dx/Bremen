# Implementation Report — PR0100: Safe API Authentication Documentation

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api_docs_ui.py` | New module: API documentation page builder |
| `src/bremen/api/server.py` | Added `/demo/api-docs` route and handler |
| `src/bremen/control_room_ui.py` | Added "API docs" nav link in header |
| `tests/test_bremen_api_docs.py` | New: 58 tests for API docs page |

## Route Added

`GET /demo/api-docs` — serves the API documentation HTML page.

Handler: `_handle_api_docs_route()` in `server.py`, following the same pattern as `_handle_workspace_route()` and `_handle_control_room_route()`.

## Nav Link Added

"API docs" link added to Control Room header, next to "Change model":

```html
<a href="/demo/api-docs" class="cr-model-link">API docs</a>
```

## Auth Documentation Summary

The API docs page documents the following planned authentication model:

- **Bearer Token Authentication**: Short-lived JWT access tokens delivered via Bearer auth
- **Token Endpoint**: `POST /api/auth/token` (planned)
- **Refresh Endpoint**: `POST /api/auth/refresh` (planned)
- **Access Token TTL**: 15 minutes (900 seconds)
- **Refresh Token TTL**: 7 days (604800 seconds)
- **Authorization Header**: `Authorization: Bearer <access_token>`

All auth items are clearly labeled as "Planned" with badge indicators.

## Env Credential Documentation

The following environment variables are documented:

| Variable | Purpose |
|----------|---------|
| `BREMEN_AUTH_ENABLED` | Enable/disable auth enforcement |
| `BREMEN_AUTH_USERNAME` | Allowed username for demo/local deployment |
| `BREMEN_AUTH_PASSWORD_HASH` | Bcrypt or argon2 password hash |
| `BREMEN_AUTH_JWT_SECRET` | JWT signing secret (must be distinct from password hash) |
| `BREMEN_AUTH_JWT_ISSUER` | JWT issuer claim |
| `BREMEN_AUTH_JWT_AUDIENCE` | JWT audience claim |
| `BREMEN_AUTH_ACCESS_TTL_SECONDS` | Access token TTL |
| `BREMEN_AUTH_REFRESH_TTL_SECONDS` | Refresh token TTL |

Password handling recommendations:
- Store password hash, not plaintext
- No default credentials in repository
- No credentials in frontend JavaScript
- No credentials in logs
- Auth fails closed if required env vars missing

## Safe API Surface Documented

Endpoint groups documented:

- **A. Auth**: `/api/auth/token`, `/api/auth/refresh`, `/api/auth/logout` (planned)
- **B. Models**: `GET /api/models`, `GET /api/models/{model_id}`
- **C. Patients/Sources**: `GET /api/patients`, `GET /api/patients/{source_id}`
- **D. Jobs**: `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{job_id}`, `GET /api/jobs/{job_id}/events`
- **E. Reports**: `GET /api/reports/{job_id}`, `POST /api/reports/{job_id}/delete`

## Forbidden Exposures Documented

The page explicitly lists items the API must NOT expose:
- Raw S3 bucket names
- Raw S3 object keys
- Filesystem paths
- Raw H5 internals
- PHI
- Patient identifiers beyond display-safe demo labels
- Raw exception traces
- Model coefficients
- Feature values
- Full checksums
- Model package internals
- Credentials
- JWT secrets
- Environment variable values

## Allowed Safe Fields Documented

The page lists items the API may safely expose:
- Opaque source IDs
- Safe patient display names
- Safe filenames
- `stable_source_key`
- `model_id`, model display name
- `workflow_id`
- `job_id`
- Status, safe decision code
- Score/threshold (if accepted for public demo)
- Report availability status
- Event status labels

## Planned vs Implemented Clarity

- Every planned item labeled with "Planned" badge
- Explicit note: "Authentication documentation is planning guidance. Enforcement will be implemented in a follow-up PR."
- Page does not claim auth is active or enforced
- No implementation of actual auth enforcement

## No Auth Enforcement Implemented

Confirmed: No authentication enforcement, token validation, or JWT processing added. This PR is documentation/UI only.

## No Dependencies Added

`api_docs_ui.py` has no external library imports. No changes to `requirements.txt` or `pyproject.toml`.

## No Secrets or Default Credentials

- No real credentials in page content
- No default passwords (demo-password, changeme, secret123, etc.)
- All credential references are env var names or placeholder syntax
- Test explicitly verifies absence of common default credential patterns

## Tests Added

77 tests in `tests/test_bremen_api_docs.py`:

- Route/page basics (3): page builds, title, nav links
- Auth model (5): Bearer, JWT, refresh token, short TTL, long TTL
- Env credentials (12): all 8 env vars, password hash, no defaults, no frontend creds, no logs, fails closed
- Endpoint groups (6): token, refresh, models, patients, jobs, reports
- Forbidden exposures (10): S3, H5, PHI, exception traces, model coefficients, feature values, credentials, JWT secrets
- Allowed safe fields (5): job_id, model_id, workflow_id, opaque source ids, stable_source_key
- Planned vs implemented (3): marked planned, follow-up note, no "active" claims
- Safety disclaimer (4): technical demo only, not clinically validated, not diagnosis, clinical judgment
- No secrets (2): no real credentials, no real JWT secret
- Future hardening (4): database users, roles, revocation, secret rotation
- Control Room nav (2): link exists, link in header
- No dependencies (2): no external imports

## Validation Results

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest -k api_docs` | 58 passed |
| `pytest -k api_docs or demo or control_room or auth or jwt or bearer` | 929 passed |
| `pytest` (full suite) | 2798 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| `grep -R demo-password/changeme/etc.` | No matches in source (only in test assertions) |
| Scope check (forbidden files) | No violations |

## Architecture Decisions Reflected

The API docs page includes a new section "9. Authentication Architecture Decisions" covering:

1. **Confirmed current state**: `/demo/*` routes are unauthenticated, no JWT/password hashing dependency present, adding auth deps is a future decision, current safety boundary assumes no authenticated fuller-view surface.

2. **Open Decision 1 (Auth Scope)**: Auth gates actions only. Authenticated users receive same safe payloads. No raw features/checksums/H5/S3/PHI/exceptions unlocked by login.

3. **Open Decision 2 (Credential Source)**: Single demo username/password from env. Password stored as hash. JWT secret must be independently generated and distinct from password hash. All BREMEN_AUTH_* env vars documented.

4. **Open Decision 3 (Refresh Storage)**: Three options (in-memory, stateless JWT, persistent). Recommended default: stateless refresh JWT with explicit no-server-side-revocation trade-off.

5. **JWT Mechanics**: PyJWT, HS256, claims (sub/iat/exp/iss/aud/token_type), optional jti. Decode must not trust token header algorithm.

6. **Safety Invariant**: Auth does not expand data visibility. Fuller view requires separate PR + safety review.

7. **Planning Status**: Every auth endpoint is planned/follow-up. Auth is not active in PR0100.

Tests verify all 7 architecture decisions are present in the page content.

## Blockers

None.

## Warnings

None.

## Next Required Action

Human review and commit.
