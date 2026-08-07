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
