# PR0116-C Precommit Review — Workspace Ticket and Security Redaction

VERDICT: approved
READY_FOR_COMMIT: true
READY_FOR_PULL_REQUEST: true

## Summary

PR0116-C fixes three issues: (1) workspace ticket issuance now accepts `purpose="workspace"`, (2) workspace page internal fetch/EventSource auth is now handled via the canonical `_authFetch`/`_authFetchTicket` helpers, and (3) sensitive ticket/token query params are redacted from application/access logs. Previous PR0116-A and PR0116-B behavior is preserved.

## Files Reviewed

- src/bremen/api/fastapi_app.py (modified)
- src/bremen/api/fastapi_server.py (modified)
- src/bremen/api/server.py (modified)
- src/bremen/logging_config.py (modified)
- src/bremen/workspace_ui.py (modified)
- tests/test_bremen_fastapi_auth_enforcement.py (modified)
- tests/test_bremen_workspace_ui.py (modified)
- tests/test_bremen_access_logging.py (new)
- .project-memory/pr/0116-hotfix-frontend-report-auth-refresh/CODER_REPORT.md (modified)
- .project-memory/pr/0116-hotfix-frontend-report-auth-refresh/rounds/C-workspace-ticket-security/CODER_REPORT.md (new)

## Confirmed Production Failure Mapping

Confirmed production root cause before this round:
- `POST /demo/api/jobs/{job_id}/auth/ticket` with `purpose="stream"` and `purpose="report"` returned 201.
- `POST /demo/api/jobs/{job_id}/auth/ticket` with `purpose="workspace"` returned 400 `{"error":"Invalid ticket purpose"}`.
- Access logs contained raw `auth_ticket=eyJ...`.

All three are now fixed:
1. Workspace ticket issuance accepts `purpose="workspace"` (verified: 201).
2. Workspace page internal auth handled via `_authFetch`/`_authFetchTicket`.
3. Sensitive query params redacted from application/access logs.

## Workspace Ticket Issuance Review

`POST /demo/api/jobs/{job_id}/auth/ticket` now accepts `purpose="workspace"` with a valid Bearer token (verified: 201). Response includes:
- `purpose="workspace"`
- `token_type="stream_ticket"`
- matching `job_id`
- `expires_in=60`
- non-empty `ticket`

Invalid purpose still returns 400 (verified).

## Ticket Purpose Isolation Review

`_VALID_PURPOSES` includes `{"stream", "report", "workspace"}`. `decode_stream_ticket` validates purpose binding:
- Workspace ticket opens only `/demo/workspace/{job_id}` (verified: 200).
- Workspace ticket rejected on report route (verified: redirect).
- Workspace ticket rejected on SSE stream (verified: 401).
- Stream ticket rejected on workspace (verified: redirect).
- Report ticket rejected on workspace (verified: redirect).
- Other-job workspace ticket rejected (verified: redirect).
- Access/refresh token types remain distinct from stream_ticket.

## Workspace Frontend Navigation Review

`openWorkspace(jobId)` in Control Room:
- Calls `_authFetchTicket(jobId, 'workspace')`.
- Navigates to `/demo/workspace/{job_id}?auth_ticket=<ticket>`.
- Does not put access_token or refresh_token in URL.
- Handles ticket mint failure via `_redirectToLogin()`.

## Workspace Internal AuthFetch Review

`workspace_ui.py` now defines the canonical `_authFetch` helper (same contract as Control Room and Report page). Protected JSON calls now use `_authFetch`:
- `GET /demo/api/jobs` (loadJobList)
- `GET /demo/api/jobs/{job_id}` (selectJob, showcase selectJob, updateShowcaseLive)

`_authFetch` attaches Bearer, refreshes on 401, stores the new token via `_setTokens`, and retries exactly once. Missing/expired session degrades to login-required state. No plain unauthenticated fetch for protected workspace calls.

## Workspace EventSource Review

`connectSSE` and `connectShowcaseSSE` now mint a `purpose="stream"` ticket via `_authFetchTicket(jobId, 'stream')` before opening EventSource, using `/demo/api/jobs/{job_id}/events/stream?auth_ticket=<STREAM_TICKET>`. No access_token or refresh_token is placed in the EventSource URL.

## Protected API Boundary Review

All fetch-only JSON API routes remain Bearer-only and return 401 without a Bearer token:
- `GET /demo/api/jobs/{job_id}`
- `GET /demo/api/jobs/{job_id}/events`
- `GET /demo/api/jobs/{job_id}/reports/bremen`
- `GET /demo/api/reports/{job_id}/external`
- `GET /demo/api/reports/{job_id}/internal`
- `GET /demo/api/h5/containers`

No `auth_ticket` fallback was added to these fetch-only JSON APIs.

## Previous PR0116 Regression Review

- Report page internal JSON calls still use `_authFetch` (verified).
- Report refresh on 401 still retries exactly once (verified).
- `openJob` still mints `purpose="report"` (verified).
- Report URL still uses `auth_ticket` (verified).
- `connectSSE` still mints `purpose="stream"` (verified).
- Report direct route does not return raw JSON Bearer error (verified: redirects to login).
- Bare `/demo/workspace` does not return raw JSON Bearer error (verified: redirects to login).
- Live Events Catalog still renders event/stage list (verified).

## Log Redaction Review

Added `redact_sensitive_query_params` and `SensitiveQueryRedactionFilter` to `logging_config.py`. Sensitive query keys (`auth_ticket`, `access_token`, `refresh_token`, `token`, `ticket`) have their values replaced with `<redacted>`. Verified:
- `auth_ticket=<jwt>` → `auth_ticket=<redacted>`
- `access_token=<jwt>` → `access_token=<redacted>`
- `refresh_token=<jwt>` → `refresh_token=<redacted>`
- `token=...` → `token=<redacted>`
- `ticket=...` → `ticket=<redacted>`
- Non-sensitive params preserved unchanged.
- Paths without query strings unchanged.

The filter is attached to `uvicorn.access` and `uvicorn` loggers in `fastapi_server.py` (production FastAPI path). The legacy `server.py` `log_message` also redacts the logged path. Redaction is logging/output only; request handling is not mutated.

## Scanner Path Review

Representative scanner paths (`/redoc`, `/openapi.json`, `/v1/chat/completions`, `/mcp`, `/gradio_api/*`, `/actuator`, `/.well-known/*`) return 404 via FastAPI default routing (verified). No 500s, no route inventory leakage. No WAF or rate-limiting was added in this round.

## Token Leak Review

- No `auth_ticket=eyJ`, `access_token=eyJ`, or `refresh_token=eyJ` literals.
- No `access_token=.*eyJ`, `refresh_token=.*eyJ`, or `auth_ticket=.*eyJ` patterns.
- No `Authorization: Bearer <JWT literal>` patterns.
- No `BREMEN_AUTH_JWT_SECRET=...` values.
- No `access_token=`/`refresh_token=` URL construction in control_room_ui.py, report_ui.py, workspace_ui.py, or tests.

## Clinical Safety Review

No unsafe clinical wording introduced in changed files. The only match in the changed-file grep is the CODER_REPORT.md describing the safety grep results (not introducing unsafe wording).

## Test Coverage

- `tests/test_bremen_fastapi_auth_enforcement.py`: Added `test_mint_endpoint_workspace_purpose` (workspace ticket issuance) and `test_stream_route_rejects_workspace_ticket` (purpose isolation).
- `tests/test_bremen_workspace_ui.py`: Added `TestWorkspaceInternalAuth` (auth helper presence, refresh-on-401, single retry, no refresh loop, protected calls use `_authFetch`, SSE mints stream ticket, no tokens in URL, showcase auth).
- `tests/test_bremen_access_logging.py` (new): Redaction helper tests (auth_ticket, access_token, refresh_token, token, ticket, multiple params, non-sensitive preserved), logging filter tests, scanner path 404 tests.

## Validation Commands

- `git diff --check`: clean
- `python -m compileall src/bremen tests`: passed
- `pytest tests/test_bremen_auth.py -q`: 64 passed
- `pytest tests/test_bremen_fastapi_auth_enforcement.py -q`: 58 passed
- `pytest tests/test_bremen_control_room.py -q`: 548 passed
- `pytest tests/test_bremen_report_ui.py -q`: 204 passed
- `pytest tests/test_bremen_workspace_ui.py -q`: 34 passed
- `pytest tests/test_bremen_access_logging.py -q`: 15 passed
- `pytest -q` (full suite): 3663 passed, 11 skipped, 0 failed
- `! grep -RInE 'auth_ticket=eyJ|access_token=eyJ|refresh_token=eyJ' src/bremen tests docs README.md`: no matches
- `! grep -RInE 'access_token=.*eyJ|refresh_token=.*eyJ|auth_ticket=.*eyJ' src/bremen tests docs README.md`: no matches
- `! grep -RInE 'Authorization: Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' src/bremen tests docs README.md`: no matches
- `! grep -RIn "BREMEN_AUTH_JWT_SECRET=.*" src/bremen tests docs README.md`: no matches
- `! grep -RInE 'access_token=|refresh_token=' src/bremen/control_room_ui.py src/bremen/report_ui.py src/bremen/workspace_ui.py tests`: no matches
- Clinical safety grep on changed files: no unsafe wording

## Findings

No blocking findings. All confirmed production failures are fixed and all architecture rules are preserved.

## Required Changes

None.

## Warnings

- Upstream Envoy/App Runner logs may still need infrastructure-level query-string redaction outside application code. This round redacts application/uvicorn access logs controlled by this repo; infrastructure-level logs are outside application control.
- Scanner/rate-limit handling is app-level only (default FastAPI 404 for unknown routes). No WAF or rate-limiting was added in this round.

## Final Decision

Approved. This round makes the production smoke pass (stream/report/workspace ticket mint → 201, `GET /demo/workspace/{job_id}?auth_ticket=<workspace_ticket>` → 200 HTML) and ensures repo-controlled logs no longer show `auth_ticket=eyJ...`, while preserving report flow, SSE flow, protected JSON API Bearer boundaries, token secrecy, and Live Events Catalog rendering.
