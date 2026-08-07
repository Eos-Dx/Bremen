# CODER REPORT — PR0116-C Workspace ticket issuance, workspace internal auth, urgent ticket log redaction

## TASK COMPLETE

Yes.

## ROUND

PR0116-C (follow-up round C inside the existing PR0116 hotfix branch).

## FILES CHANGED

- `src/bremen/api/fastapi_app.py` — ticket issuance endpoint now accepts
  `purpose="workspace"`.
- `src/bremen/workspace_ui.py` — added canonical `_authFetch`/`_authFetchTicket`
  helpers; replaced plain `fetch` with `_authFetch` for protected JSON calls;
  `connectSSE`/`connectShowcaseSSE` now mint a `purpose="stream"` ticket before
  opening EventSource.
- `src/bremen/logging_config.py` — added `redact_sensitive_query_params` and
  `SensitiveQueryRedactionFilter`.
- `src/bremen/api/fastapi_server.py` — attached `SensitiveQueryRedactionFilter`
  to uvicorn access loggers.
- `src/bremen/api/server.py` — legacy `log_message` now redacts sensitive query
  params from the logged path.
- `tests/test_bremen_fastapi_auth_enforcement.py` — added workspace ticket
  issuance and purpose-isolation tests.
- `tests/test_bremen_workspace_ui.py` — added `TestWorkspaceInternalAuth`.
- `tests/test_bremen_access_logging.py` — new file for log redaction and scanner
  path tests.

## CONFIRMED PRODUCTION ROOT CAUSE

Production curl confirmed:
- `POST /demo/api/jobs/{job_id}/auth/ticket` with `purpose="stream"` and
  `purpose="report"` returned 201.
- `POST /demo/api/jobs/{job_id}/auth/ticket` with `purpose="workspace"` returned
  400 `{"error":"Invalid ticket purpose"}`.

The ticket issuance endpoint only accepted `("stream", "report")`, so workspace
frontend navigation could not mint a workspace ticket.

## WORKSPACE TICKET ISSUANCE FIX

`POST /demo/api/jobs/{job_id}/auth/ticket` now accepts `purpose="workspace"`
with a valid Bearer token. Response is 201 with `token_type="stream_ticket"`,
`purpose="workspace"`, matching `job_id`, `expires_in=60`, and a non-empty
`ticket`.

## WORKSPACE PURPOSE ISOLATION

`_VALID_PURPOSES` already included `"workspace"` (from PR0116-B).
`decode_stream_ticket` validates purpose binding, so:
- A workspace ticket opens only `GET /demo/workspace/{job_id}`.
- A workspace ticket is rejected on report, SSE stream, and fetch-only JSON APIs.
- A stream ticket cannot open workspace.
- A report ticket cannot open workspace.
- A workspace ticket for another job is rejected.

## WORKSPACE NAVIGATION FIX

`openWorkspace(jobId)` in Control Room mints a `purpose="workspace"` ticket via
`_authFetchTicket(jobId, 'workspace')` and navigates to
`/demo/workspace/{job_id}?auth_ticket=<WORKSPACE_TICKET>`. No access_token or
refresh_token is placed in the URL.

## WORKSPACE INTERNAL AUTHFETCH FIX

`workspace_ui.py` now defines the canonical `_authFetch` helper (same contract as
Control Room and Report page). Protected JSON calls now use `_authFetch`:
- `GET /demo/api/jobs` (loadJobList)
- `GET /demo/api/jobs/{job_id}` (selectJob, showcase selectJob, updateShowcaseLive)

`_authFetch` attaches Bearer, refreshes on 401, stores the new token, and retries
exactly once. Missing/expired session degrades to login-required state.

## WORKSPACE SSE FIX

`connectSSE` and `connectShowcaseSSE` now mint a `purpose="stream"` ticket via
`_authFetchTicket(jobId, 'stream')` before opening EventSource, using
`/demo/api/jobs/{job_id}/events/stream?auth_ticket=<STREAM_TICKET>`. No
access_token or refresh_token is placed in the EventSource URL.

## LOG REDACTION FIX

Added `redact_sensitive_query_params` and `SensitiveQueryRedactionFilter` to
`logging_config.py`. Sensitive query keys (`auth_ticket`, `access_token`,
`refresh_token`, `token`, `ticket`) have their values replaced with
`<redacted>`. The filter is attached to uvicorn access loggers in
`fastapi_server.py`, and the legacy `server.py` `log_message` redacts the logged
path. Redaction is logging/output only; request handling is not mutated.

## SCANNER PATH HANDLING

Representative scanner paths (`/redoc`, `/openapi.json`, `/v1/chat/completions`,
`/mcp`, `/gradio_api/*`, `/actuator`, `/.well-known/*`) return 404 via FastAPI
default routing. No 500s, no route inventory leakage. No WAF or rate-limiting
was added in this round.

## PREVIOUS PR0116 BEHAVIOR PRESERVED

- Report page `_authFetch` and refresh-on-401 preserved.
- Token persistence through `_setTokens` preserved.
- Retry exactly once preserved.
- `openJob` mints `purpose="report"`.
- Report URL uses `auth_ticket`.
- Report direct route does not return raw JSON Bearer error.
- Bare `/demo/workspace` does not return raw JSON Bearer error.
- Live Events Catalog renders event/stage list.
- `connectSSE` mints `purpose="stream"`.
- EventSource URL uses `auth_ticket`.

## TESTS ADDED/UPDATED

- `tests/test_bremen_fastapi_auth_enforcement.py`:
  - `test_mint_endpoint_workspace_purpose` (workspace ticket issuance).
  - `test_stream_route_rejects_workspace_ticket` (purpose isolation).
- `tests/test_bremen_workspace_ui.py`:
  - `TestWorkspaceInternalAuth` (auth helper presence, refresh-on-401, single
    retry, no refresh loop, protected calls use `_authFetch`, SSE mints stream
    ticket, no tokens in URL, showcase auth).
- `tests/test_bremen_access_logging.py` (new):
  - Redaction helper tests (auth_ticket, access_token, refresh_token, token,
    ticket, multiple params, non-sensitive preserved).
  - Logging filter tests.
  - Scanner path 404 tests.

## VALIDATION RUN

| Command | Exit | Result |
|---|---|---|
| `python -m compileall src/bremen tests` | 0 | Pass |
| `pytest tests/test_bremen_auth.py -q` | 0 | 64 passed |
| `pytest tests/test_bremen_fastapi_auth_enforcement.py -q` | 0 | 58 passed |
| `pytest tests/test_bremen_control_room.py -q` | 0 | 548 passed |
| `pytest tests/test_bremen_report_ui.py -q` | 0 | 204 passed |
| `pytest tests/test_bremen_workspace_ui.py -q` | 0 | 34 passed |
| `pytest tests/test_bremen_access_logging.py -q` | 0 | 15 passed |
| `pytest -q` (full suite) | 0 | 3663 passed, 11 skipped |
| `git diff --check` | 0 | Pass |
| `! grep -RInE 'auth_ticket=eyJ\|access_token=eyJ\|refresh_token=eyJ' src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RInE 'access_token=.*eyJ\|refresh_token=.*eyJ\|auth_ticket=.*eyJ' src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RInE 'Authorization: Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RIn "BREMEN_AUTH_JWT_SECRET=.*" src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RInE 'access_token=\|refresh_token=' src/bremen/control_room_ui.py src/bremen/report_ui.py src/bremen/workspace_ui.py tests` | 0 | Pass (no matches) |

## PRODUCTION SMOKE EXPECTATION

After deployment, the smoke loop should return:
- `stream -> 201`
- `report -> 201`
- `workspace -> 201`

And `GET /demo/workspace/{job_id}?auth_ticket=<WORKSPACE_TICKET>` should return
`HTTP/1.1 200 OK` with `content-type: text/html`.

## WARNINGS

- Upstream Envoy/App Runner logs may still need infrastructure-level
  query-string redaction outside application code. This round redacts
  application/uvicorn access logs controlled by this repo; infrastructure-level
  logs are outside application control.
- Scanner/rate-limit handling is app-level only (default FastAPI 404 for unknown
  routes). No WAF or rate-limiting was added in this round.
- The workspace page internal auth is now handled via `_authFetch`/stream
  tickets. No workspace internal behavior remains outside this round.

## READY FOR PRECOMMIT REVIEW

Yes.
