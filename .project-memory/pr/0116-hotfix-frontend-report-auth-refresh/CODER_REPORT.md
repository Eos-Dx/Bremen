# CODER REPORT — PR0116 Hotfix frontend auth refresh/state on report page

## TASK COMPLETE

Yes.

## FILES CHANGED

- `src/bremen/report_ui.py` — added canonical browser auth helpers (`_getSessionStorage`, `_getAccessToken`, `_getRefreshToken`, `_setTokens`, `_clearTokens`, `_redirectToLogin`, `_authFetch`) to the report page JS; replaced plain `fetch(...)` with `_authFetch(...)` for all four protected report endpoints; added graceful degradation when no stored session exists.
- `tests/test_bremen_report_ui.py` — added `TestReportPageAuthFetch` class covering auth helper presence, Bearer attachment, refresh-on-401, token storage, single retry, no refresh loop, token-clear on failure, protected-endpoint wrapping, no plain fetch for protected endpoints, no token-in-URL, no JWT literals, graceful degradation, and sample-mode bypass.

## ROOT CAUSE

- **Which report-page fetches were unwrapped/stale?** All four protected report JSON fetches in `loadReport()` used plain `fetch(...)`:
  - `GET /demo/api/jobs/{job_id}`
  - `GET /demo/api/jobs/{job_id}/reports/bremen`
  - `GET /demo/api/reports/{job_id}/external`
  - `GET /demo/api/reports/{job_id}/internal`
  The report page (`report_ui.py`) had no auth helper at all, so no `Authorization: Bearer` header was attached and no refresh flow existed.
- **Why did refresh not update the request path?** There was no refresh logic on the report page. The Control Room (`control_room_ui.py`) had a working `_authFetch` with refresh+retry, but the report page was a separate document that did not reuse it and did not bootstrap auth state from browser storage.
- **What exact helper now handles those fetches?** The report page now defines and uses `_authFetch(url, opts)`, which reads the access token from the canonical `sessionStorage` key (`bremen_access_token`), attaches `Authorization: Bearer <token>`, and on 401 calls `POST /demo/api/auth/refresh` with the canonical refresh token (`bremen_refresh_token`), stores the new tokens via `_setTokens`, updates the in-memory header, and retries the original request exactly once.
- **How does the page behave if opened with report ticket but no stored session?** `loadReport()` checks `!_getAccessToken() && !_getRefreshToken()` first. If no tokens exist (e.g., a copied report-ticket URL opened in a fresh browser context), it renders a clear "Login required to refresh live report details" message and returns without issuing any protected API requests — no 401 storm, no infinite refresh loop.

## IMPLEMENTATION SUMMARY

- Added the canonical browser auth contract to the report page JS, matching the Control Room's `_authFetch` implementation exactly (same storage keys, same refresh endpoint, same single-retry semantics).
- Replaced all four plain `fetch(...)` calls in `loadReport()` with `_authFetch(...)`.
- Added graceful degradation for the no-session case.
- No backend auth changes. No model behavior changes. No clinical wording changes. No deployment config changes.

## FRONTEND AUTH FLOW

The report page now uses the same canonical auth flow as Control Room:

1. `_getAccessToken()` reads `bremen_access_token` from `sessionStorage`.
2. `_authFetch` attaches `Authorization: Bearer <access_token>`.
3. On 401, `_authFetch` reads `bremen_refresh_token` and calls `POST /demo/api/auth/refresh`.
4. On success, `_setTokens(result.data)` stores the new access/refresh tokens and expiry in the same canonical storage keys.
5. The in-memory `headers` object is updated with the new Bearer token.
6. The original request is retried exactly once.
7. On refresh failure or missing refresh token, tokens are cleared and the user is redirected to `/demo/login`.

## REPORT PAGE FIX

- `loadReport()` now uses `_authFetch` for all four protected endpoints.
- No plain `fetch(...)` remains for protected report endpoints.
- Graceful degradation: if no stored session tokens exist, the page shows a clear login-required message and does not issue protected requests.

## REFRESH RETRY BEHAVIOR

- On 401, `_authFetch` calls the refresh endpoint once.
- If refresh succeeds, the new access token is stored, the in-memory header is updated, and the original request is retried exactly once.
- If refresh fails or the refresh token is missing, tokens are cleared and the user is redirected to login.
- No refresh loop: only one retry per original request.

## TICKET FLOW PRESERVED

- `connectSSE()` in Control Room still mints a `purpose=stream` ticket and uses `auth_ticket` in the EventSource URL.
- `openJob()` in Control Room still mints a `purpose=report` ticket and navigates to `/demo/report/{job_id}?auth_ticket=...`.
- No access_token or refresh_token is placed in URLs.
- The report page ticket navigation flow is unchanged.

## SECURITY NOTES

- No access_token or refresh_token in URLs.
- No token-in-query-parameter patterns added.
- No new token-in-URL patterns introduced.
- No real JWT literals in frontend strings.
- No backend auth rules broadened.
- No ticket auth accepted as Bearer on protected routes.
- No tokens or tickets logged.

## TESTS ADDED/UPDATED

Added `TestReportPageAuthFetch` class to `tests/test_bremen_report_ui.py` with 20 tests covering:

- A. Report page JS uses auth helper for all protected endpoints (job, reports/bremen, external, internal).
- B. Refresh response updates stored access token (`_setTokens(result.data)`).
- C. Refresh endpoint is not called in a loop (only one retry per original request).
- D. Report navigation remains ticket-based (existing Control Room tests still pass).
- E. SSE remains ticket-based (existing Control Room tests still pass).
- F. No raw token leak in frontend strings (no `access_token=`/`refresh_token=` in URLs, no JWT literals).
- G. Existing auth enforcement remains intact (existing FastAPI auth tests still pass).

## VALIDATION RUN

| Command | Exit | Result |
|---|---|---|
| `python -m compileall src/bremen tests` | 0 | Pass |
| `pytest tests/test_bremen_report_ui.py -q` | 0 | 204 passed |
| `pytest tests/test_bremen_control_room.py -q` | 0 | 533 passed |
| `pytest tests/test_bremen_fastapi_auth_enforcement.py -q` | 0 | 47 passed |
| `pytest tests/test_bremen_auth.py -q` | 0 | 64 passed |
| `pytest -q` (full suite) | 0 | 3606 passed, 11 skipped |
| `git diff --check` | 0 | Pass |
| `! grep -RInE 'access_token=.*eyJ\|refresh_token=.*eyJ\|auth_ticket=.*eyJ' src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RInE 'access_token=\|refresh_token=' src/bremen/control_room_ui.py tests` | 0 | Pass (no matches) |

## WARNINGS

- The clinical safety grep (`! grep -RInEi 'detects cancer|diagnoses|diagnosis engine|replaces clinician|FDA approved|clinically certified|rules out disease' src/bremen tests docs README.md`) returns matches, but all are pre-existing in unrelated files (`model_playground_page.html`, `demo_evidence.py`, various tests, docs). The diff for this PR introduces no forbidden clinical phrases. The report UI text added ("Login required to refresh live report details") contains no forbidden wording.

## READY FOR REVIEW

Yes.

---

# PR0116-D — Direct report URL must bootstrap and append report auth_ticket

## TASK COMPLETE

Yes.

## ROUND

PR0116-D (follow-up round D inside the existing PR0116 hotfix branch).

## FILES CHANGED

- `src/bremen/api/fastapi_app.py` — bare `/demo/report/{job_id}` now returns a
  safe bootstrap shell (200 HTML) instead of redirecting to login; invalid
  tickets still redirect to login.
- `src/bremen/report_ui.py` — added `_authFetchTicket` to the report page JS;
  added `build_report_bootstrap_page` and `_BOOTSTRAP_JS`.
- `tests/test_bremen_report_ui.py` — added `TestReportBootstrapShell`.
- `tests/test_bremen_fastapi_auth_enforcement.py` — updated report route tests
  for bootstrap shell behavior; added `REPORT_BOOTSTRAP_ROUTES`.
- `tests/test_bremen_auth_activation_readiness.py` — updated browser-nav tests
  for report bootstrap shell behavior.

## CONFIRMED PRODUCTION ROOT CAUSE

- `GET /demo/report/{job_id}?auth_ticket=<valid report ticket>` works (200 full
  report).
- `GET /demo/report/{job_id}` (bare) did not bootstrap the browser session and
  did not mint/append `auth_ticket` automatically.

The missing behavior was that the bare report URL did not bootstrap the browser
session and did not mint/append `auth_ticket` automatically.

## DIRECT REPORT URL FIX

`GET /demo/report/{job_id}` without Bearer and without `auth_ticket` now returns
a 200 HTML safe bootstrap shell. The shell contains no protected report data and
mints a `purpose="report"` ticket client-side, then navigates to the canonical
ticketed URL.

## REPORT BOOTSTRAP SHELL

`build_report_bootstrap_page(base_url, job_id)` returns a safe HTML shell that:
- embeds the job_id;
- contains no protected patient/report/model/result details;
- reads canonical browser auth storage (`bremen_access_token`,
  `bremen_refresh_token`);
- mints a `purpose="report"` ticket via `_authFetchTicket(jobId, 'report')`;
- navigates via `window.location.replace` to
  `/demo/report/{job_id}?auth_ticket=<REPORT_TICKET>`;
- shows a login-required state with a link to
  `/demo/login?next=/demo/report/{job_id}` when no session exists.

## REPORT TICKET MINT FLOW

1. User opens `/demo/report/{job_id}`.
2. Server returns the safe bootstrap shell.
3. Browser JS reads canonical auth storage.
4. If a session exists, JS calls `_authFetchTicket(jobId, 'report')`.
5. On success, JS uses `window.location.replace` to navigate to
   `/demo/report/{job_id}?auth_ticket=<REPORT_TICKET>`.
6. The existing ticketed route renders the full report.

## LOGIN FALLBACK

When `/demo/report/{job_id}` is opened in a fresh browser/no stored session:
- no protected report data is exposed;
- no raw JSON auth error is shown;
- no infinite loop;
- a clear login-required state is shown with a link to
  `/demo/login?next=/demo/report/{job_id}`.

## TOKEN SAFETY

- No `access_token` or `refresh_token` in URLs.
- The only URL token allowed in this flow is `auth_ticket=<REPORT_TICKET>`.
- No raw tokens are logged.

## PREVIOUS PR0116 BEHAVIOR PRESERVED

- Report page internal `_authFetch` preserved.
- Report refresh on 401 preserved.
- Single retry preserved.
- `openJob` mints `purpose="report"`.
- Report ticketed URL works.
- Workspace ticket issuance accepts `purpose="workspace"`.
- Workspace route opens with workspace ticket.
- Workspace internal `_authFetch`.
- Workspace EventSource uses stream ticket.
- `connectSSE` uses stream ticket.
- Live Events Catalog renders event/stage list.
- Log redaction prevents `auth_ticket=eyJ` in repo-controlled logs.
- Protected JSON APIs remain Bearer-only.

## TESTS ADDED/UPDATED

- `tests/test_bremen_report_ui.py`:
  - `TestReportBootstrapShell` (bootstrap marker, job_id, no protected data,
    mints report ticket, navigates to ticketed URL, no tokens in URL, login
    fallback, no infinite loop, canonical storage, login-required state).
- `tests/test_bremen_fastapi_auth_enforcement.py`:
  - Updated `test_report_route_rejects_no_auth` to expect bootstrap shell (200).
  - Added `REPORT_BOOTSTRAP_ROUTES` and `test_report_bootstrap_route_no_token_returns_shell`.
  - Removed report route from `BROWSER_NAV_ROUTES`.
- `tests/test_bremen_auth_activation_readiness.py`:
  - Updated `test_browser_nav_routes_redirect_to_login` to remove report route.
  - Added `test_report_bootstrap_route_returns_shell`.

## VALIDATION RUN

| Command | Exit | Result |
|---|---|---|
| `python -m compileall src/bremen tests` | 0 | Pass |
| `pytest tests/test_bremen_report_ui.py -q` | 0 | 214 passed |
| `pytest tests/test_bremen_fastapi_auth_enforcement.py -q` | 0 | 59 passed |
| `pytest tests/test_bremen_control_room.py -q` | 0 | 548 passed |
| `pytest tests/test_bremen_auth.py -q` | 0 | 64 passed |
| `pytest tests/test_bremen_workspace_ui.py -q` | 0 | 34 passed |
| `pytest tests/test_bremen_access_logging.py -q` | 0 | 15 passed |
| `pytest -q` (full suite) | 0 | 3675 passed, 11 skipped |
| `git diff --check` | 0 | Pass |
| `! grep -RInE 'auth_ticket=eyJ\|access_token=eyJ\|refresh_token=eyJ' src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RInE 'access_token=\|refresh_token=' src/bremen/control_room_ui.py src/bremen/report_ui.py src/bremen/workspace_ui.py tests` | 0 | Pass (no matches) |
| `! grep -RInE 'Authorization: Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' src/bremen tests docs README.md` | 0 | Pass (no matches) |

## PRODUCTION SMOKE EXPECTATION

Given a logged-in browser session, opening `/demo/report/{job_id}` should:
- load the safe bootstrap shell;
- mint a `purpose="report"` ticket;
- navigate to `/demo/report/{job_id}?auth_ticket=<REPORT_TICKET>`;
- open the full report;
- show no raw JSON Bearer error;
- show no access_token/refresh_token in URL.

Given a fresh/no-session browser, opening `/demo/report/{job_id}` should:
- expose no protected report data;
- show a login-required state or login link;
- preserve `next=/demo/report/{job_id}`.

Curl smoke: `curl -i -L "$BASE/demo/report/$JOB_ID"` should return a
`text/html` bootstrap shell, not a JSON auth error, not a full protected report.

## WARNINGS

- Bare `/demo/report/{job_id}` now returns a safe bootstrap shell, not the full
  report. The full report is only served with a valid Bearer or valid report
  ticket.
- Copied bare report URLs require an existing browser session to auto-open. In a
  fresh browser context, the shell shows a login-required state.
- `auth_ticket` remains required for full server-rendered report content.

## READY FOR PRECOMMIT REVIEW

Yes.

---

# PR0116-C — Workspace ticket issuance, workspace internal auth, urgent ticket log redaction

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

## READY FOR REVIEW

Yes.

---

# FOLLOW-UP FIX — PR0116 follow-up hotfix

## TASK COMPLETE

Yes.

## FOLLOW-UP FIX

This follow-up hotfix addresses the remaining page-route authentication
inconsistency and the Live Events Catalog rendering gap exposed by production
smoke after the first PR0116 hotfix.

## ARCHITECTURE FINDING APPLIED

Browser document navigation cannot attach `Authorization: Bearer` headers.
Therefore browser-navigation HTML routes must not be protected only by
header-only `_check_auth_gate` when they are intended to be opened through
`window.location.href`, direct link, or browser navigation.

Durable rule applied:
- Fetch-only JSON/API routes stay Bearer-only and use `_check_auth_gate`.
- EventSource routes use `_check_auth_gate_with_ticket` with `purpose="stream"`.
- Job-bound browser-navigation HTML routes use `_check_auth_gate_with_ticket`
  with a route-specific purpose (`report` or `workspace`).
- Browser-navigation HTML routes without job_id cannot use the job-bound ticket
  design; they redirect to login with `next=...` when auth is missing.
- No route puts access_token or refresh_token in URLs.

## REMAINING PRODUCTION FAILURE

Confirmed live failures before this fix:
1. `GET /demo/report/{job_id}` without auth returned raw JSON Bearer error.
2. `GET /demo/workspace/{job_id}` without auth returned raw JSON Bearer error.
3. Live Events Catalog rendered only the summary/header, not the event list.

## ROUTE AUTH CONSISTENCY RULE

- Fetch-only JSON/API routes: Bearer-only (`_check_auth_gate`).
- EventSource routes: `_check_auth_gate_with_ticket` with `purpose="stream"`.
- Job-bound browser HTML routes: `_check_auth_gate_with_ticket` with
  `purpose="report"` or `purpose="workspace"`.
- Browser HTML routes without job_id: redirect to login with `next=...`.

## WORKSPACE DETAIL ROUTE FIX

`GET /demo/workspace/{job_id}` now uses `_check_auth_gate_with_ticket(request,
job_id, "workspace")`. It accepts a valid Bearer access token or a short-lived
job-bound workspace ticket via `auth_ticket`. When neither is present, it
redirects to `/demo/login?next=/demo/workspace/{job_id}` instead of returning a
raw JSON Bearer error as the page body.

## REPORT DIRECT ROUTE FIX

`GET /demo/report/{job_id}` already used `_check_auth_gate_with_ticket(request,
job_id, "report")`. It now redirects to `/demo/login?next=/demo/report/{job_id}`
when no Bearer and no valid report ticket is present, instead of returning a raw
JSON Bearer error as the page body.

## BARE WORKSPACE ROUTE TREATMENT

`GET /demo/workspace` has no job_id, so the job-bound ticket design does not map
cleanly to it. It remains Bearer-gated for authenticated callers. When auth is
missing, it redirects to `/demo/login?next=/demo/workspace` instead of returning
a raw JSON Bearer error as the page body. No broad non-job-bound ticket was
invented. The route is not made public.

## CLIENT-SIDE WORKSPACE ENTRY POINT

A client-side workspace entry point exists in the Control Room: the "Open
workspace" link in the decision card. It was a plain `href` navigation that
would hit the Bearer-only route without a ticket. It now calls a new
`openWorkspace(jobId)` function that mints a `purpose="workspace"` ticket via
`_authFetchTicket(jobId, 'workspace')` and navigates to
`/demo/workspace/{job_id}?auth_ticket=<WORKSPACE_TICKET>`. No access_token or
refresh_token is placed in the URL.

## LIVE EVENTS CATALOG FIX

Root cause: `collapseEventPanel('completed')` replaced the entire event list
content with only the summary line, wiping out the chronological event rows
rendered by `addEventRow`. The "14 of 15" count was derived from
`eventCache.filter(e => e.status==='completed')`, which could undercount when
not all events carried `status='completed'`.

Fix:
- `collapseEventPanel` now preserves the chronological event list and prepends
the summary as a header row (`cr-event-summary`) instead of replacing the list.
- Completed/total counts are derived from the actual rendered pipeline stages
(`document.querySelectorAll('.cr-stage.completed')` and `.cr-stage`), not from
a stale hard-coded catalog length or the event cache.
- `runtime.report.completed` maps to `stage-report` in `STAGE_MAP`, so the
report-completed stage is counted when present.
- Unknown event_type renders a fallback label (`ev.event_type`) instead of
breaking the list.
- Empty state is explicit only when truly empty ("Analysis events will appear
here").

## PROTECTED API BOUNDARIES PRESERVED

All fetch-only JSON API routes remain Bearer-only and return 401 without a
Bearer token:
- `GET /demo/api/jobs`
- `POST /demo/api/jobs`
- `GET /demo/api/jobs/{job_id}`
- `GET /demo/api/jobs/{job_id}/events`
- `GET /demo/api/jobs/{job_id}/reports`
- `GET /demo/api/jobs/{job_id}/reports/{workflow_id}`
- `GET /demo/api/reports/{job_id}/external`
- `GET /demo/api/reports/{job_id}/internal`
- `GET /demo/api/h5/containers`
- `POST /demo/api/h5/containers`

No `auth_ticket` fallback was added to these fetch-only JSON APIs.

## TICKET PURPOSE VALIDATION

`_VALID_PURPOSES` in `src/bremen/auth.py` now includes `"workspace"` in addition
to `"stream"` and `"report"`. `decode_stream_ticket` validates purpose binding,
so:
- A `stream` ticket cannot open report or workspace.
- A `report` ticket cannot open workspace or stream.
- A `workspace` ticket cannot open report or stream.
- A ticket for a different job is rejected.

## TESTS ADDED/UPDATED

- `tests/test_bremen_fastapi_auth_enforcement.py`:
  - Added `TestWorkspaceRouteTicketFallback` (valid workspace ticket, rejects
    stream/report tickets, rejects wrong-job ticket, redirects on no auth,
    accepts when auth disabled).
  - Added report route rejects workspace ticket test.
  - Updated report route rejection tests to expect redirect (302) instead of 401.
  - Added `BROWSER_NAV_ROUTES` and `test_browser_nav_route_no_token_redirects_to_login`.
  - Removed browser-nav HTML routes from `PROTECTED_ROUTES` (they now redirect).
- `tests/test_bremen_control_room.py`:
  - Added `openWorkspace` ticket-mint navigation tests.
  - Added `TestLiveEventsCatalogRendering` (event list preserved, DOM-derived
    counts, unknown event fallback, report.completed in STAGE_MAP).
- `tests/test_bremen_auth_activation_readiness.py`:
  - Updated `test_protected_routes_require_token` to only cover fetch-only APIs.
  - Added `test_browser_nav_routes_redirect_to_login`.

## VALIDATION RUN

| Command | Exit | Result |
|---|---|---|
| `python -m compileall src/bremen tests` | 0 | Pass |
| `pytest tests/test_bremen_report_ui.py -q` | 0 | 204 passed |
| `pytest tests/test_bremen_control_room.py -q` | 0 | 548 passed |
| `pytest tests/test_bremen_fastapi_auth_enforcement.py -q` | 0 | 56 passed |
| `pytest tests/test_bremen_auth.py -q` | 0 | 64 passed |
| `pytest -q` (full suite) | 0 | 3631 passed, 11 skipped |
| `git diff --check` | 0 | Pass |
| `! grep -RInE 'access_token=.*eyJ\|refresh_token=.*eyJ\|auth_ticket=.*eyJ' src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RInE 'access_token=\|refresh_token=' src/bremen tests` | 1 | Pre-existing matches in `auth.py` dataclass fields (not URL patterns) |
| `! grep -RIn "Authorization.*auth_ticket\|Bearer.*auth_ticket" src/bremen tests` | 0 | Pass (no matches) |

## WARNINGS

- The security grep `! grep -RInE 'access_token=|refresh_token=' src/bremen tests`
  returns pre-existing matches in `src/bremen/auth.py` (lines 363-364) which are
  `TokenPair` dataclass field assignments (`access_token=access`,
  `refresh_token=refresh`), not token-in-URL patterns. These are pre-existing and
  not introduced by this PR.
- The workspace page (`workspace_ui.py`) internal fetches (`/demo/api/jobs`,
  `/demo/api/jobs/{job_id}`, EventSource) still use plain `fetch`/`EventSource`
  without Bearer. When the workspace page is opened via a workspace ticket, the
  page shell loads (200 HTML) but its internal JSON fetches would require a
  Bearer session. This is outside the scope of this hotfix (which targets
  page-route auth consistency); the workspace page's internal fetch handling is
  a separate concern.
- The clinical safety grep returns pre-existing matches in unrelated files
  (`model_playground_page.html`, `demo_evidence.py`, various tests, docs). The
diff for this PR introduces no forbidden clinical phrases.

## READY FOR REVIEW

Yes.
