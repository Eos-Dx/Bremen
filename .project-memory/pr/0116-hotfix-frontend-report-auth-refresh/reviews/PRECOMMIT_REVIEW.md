# PR0116 Precommit Review — Page-Route Auth Consistency and Live Events Catalog

VERDICT: approved
READY_FOR_COMMIT: true
READY_FOR_PULL_REQUEST: true

## Summary

This follow-up to PR0116 applies the architect finding for browser page-route auth consistency and fixes the Live Events Catalog rendering gap. Browser-navigation HTML routes (`/demo/report/{job_id}`, `/demo/workspace/{job_id}`, bare `/demo/workspace`) now redirect to login with `next=...` instead of returning raw JSON Bearer errors as the page body. The workspace detail route gains a `purpose="workspace"` ticket fallback. The Live Events Catalog now preserves the chronological event list and derives completed/total counts from actual rendered pipeline stages.

## Files Reviewed

- src/bremen/api/fastapi_app.py (modified)
- src/bremen/auth.py (modified)
- src/bremen/control_room_ui.py (modified)
- tests/test_bremen_auth_activation_readiness.py (modified)
- tests/test_bremen_control_room.py (modified)
- tests/test_bremen_fastapi_auth_enforcement.py (modified)
- .project-memory/pr/0116-hotfix-frontend-report-auth-refresh/CODER_REPORT.md (modified)

## Production Failure Mapping

Confirmed live failures before this fix:
1. `GET /demo/report/{job_id}` without auth returned raw JSON Bearer error.
2. `GET /demo/workspace/{job_id}` without auth returned raw JSON Bearer error.
3. Live Events Catalog rendered only the summary/header, not the event list.

All three are now fixed:
1. `/demo/report/{job_id}` redirects to `/demo/login?next=/demo/report/{job_id}` (302) instead of raw JSON 401.
2. `/demo/workspace/{job_id}` redirects to `/demo/login?next=/demo/workspace/{job_id}` (302) instead of raw JSON 401.
3. Live Events Catalog preserves the chronological event list and prepends the summary as a header row.

## Architecture Rule Review

The architecture rule is correctly applied:
- Fetch-only JSON/API routes use `_check_auth_gate` and remain Bearer-only.
- EventSource routes use `_check_auth_gate_with_ticket` with `purpose="stream"`.
- Job-bound browser-navigation HTML routes use `_check_auth_gate_with_ticket` with route-specific purpose (`report` or `workspace`).
- Browser-navigation HTML routes without job_id (bare `/demo/workspace`) redirect to login with `next=...`.
- No access_token or refresh_token appears in URLs.
- Ticket auth remains purpose-bound and job-id-bound.

## Workspace Detail Route Review

`GET /demo/workspace/{job_id}` now uses `_check_auth_gate_with_ticket(request, job_id, "workspace")`:
- Valid `purpose="workspace"` ticket for same job returns HTML (verified: 200).
- Valid Bearer still works (verified: 200).
- Stream ticket is rejected (redirect to login).
- Report ticket is rejected (redirect to login).
- Workspace ticket for another job is rejected (redirect to login).
- No Bearer and no ticket redirects to login (302), not raw JSON Bearer error.
- Route is not public.

## Report Direct Route Review

`GET /demo/report/{job_id}` uses `_check_auth_gate_with_ticket(request, job_id, "report")`:
- Valid `purpose="report"` ticket for same job returns HTML.
- Valid Bearer still works.
- Stream ticket is rejected (redirect to login).
- Workspace ticket is rejected (redirect to login).
- Report ticket for another job is rejected (redirect to login).
- No Bearer and no ticket redirects to login (302), not raw JSON Bearer error.
- Route is not public.

## Bare Workspace Route Review

`GET /demo/workspace` has no job_id, so the job-bound ticket design does not apply:
- No broad non-job-bound ticket introduced.
- Route is not made public.
- No-auth browser navigation redirects to `/demo/login?next=/demo/workspace` (302), not raw JSON Bearer error.

## Protected JSON API Boundary Review

All fetch-only JSON API routes remain Bearer-only and return 401 without a Bearer token:
- `GET /demo/api/jobs` (verified: 401)
- `POST /demo/api/jobs`
- `GET /demo/api/jobs/{job_id}`
- `GET /demo/api/jobs/{job_id}/events`
- `GET /demo/api/jobs/{job_id}/reports`
- `GET /demo/api/jobs/{job_id}/reports/{workflow_id}`
- `GET /demo/api/reports/{job_id}/external`
- `GET /demo/api/reports/{job_id}/internal`
- `GET /demo/api/h5/containers` (verified: 401)
- `POST /demo/api/h5/containers`

No `auth_ticket` fallback was added to these fetch-only JSON APIs.

## Ticket Purpose Isolation Review

`_VALID_PURPOSES` in `src/bremen/auth.py` now includes `"workspace"` in addition to `"stream"` and `"report"`. `decode_stream_ticket` validates purpose binding:
- Stream ticket works only for stream route.
- Report ticket works only for report route.
- Workspace ticket works only for workspace detail route.
- Wrong purpose rejected (verified: stream/report tickets rejected on workspace, workspace ticket rejected on report).
- Other job rejected (verified: workspace ticket for job-2 rejected on job-1).
- Ticket token_type remains isolated from access/refresh tokens.

## Frontend Navigation Review

- `openWorkspace(jobId)` added — mints `purpose="workspace"` ticket via `_authFetchTicket(jobId, 'workspace')`, navigates to `/demo/workspace/{job_id}?auth_ticket=`, on failure redirects to login.
- "Open workspace" link in decision card now calls `openWorkspace(jobId)` (prevents default href navigation).
- No access_token or refresh_token placed in URL.
- `openJob` still mints `purpose="report"` ticket.
- `connectSSE` still mints `purpose="stream"` ticket.

## Report AuthFetch Regression Review

The report page authFetch behavior from the first PR0116 hotfix remains intact:
- Report page protected JSON calls still use `_authFetch`.
- Refresh on 401 still calls `POST /demo/api/auth/refresh`.
- New access token stored through canonical `_setTokens`.
- In-memory auth state updated.
- Original request retries exactly once.
- Refresh failure clears tokens or redirects safely.
- No infinite retry loop.

## Live Events Catalog Review

- `collapseEventPanel` now preserves the chronological event list and prepends the summary as a header row (`cr-event-summary`) instead of replacing the list.
- Completed/total counts derived from actual rendered pipeline stages (`document.querySelectorAll('.cr-stage.completed')` and `.cr-stage`), not stale hard-coded catalog length or event cache.
- `runtime.report.completed` maps to `stage-report` in STAGE_MAP.
- Unknown event_type renders a fallback label (`ev.event_type`) instead of breaking.
- Empty state is explicit only when truly empty ("Analysis events will appear here").
- If execution_traces has 15 completed stages, UI shows 15 of 15 (DOM-derived).

## Token Leak Review

- No `access_token=.*eyJ`, `refresh_token=.*eyJ`, or `auth_ticket=.*eyJ` patterns.
- No `access_token=`/`refresh_token=` URL construction (the only matches are pre-existing `TokenPair` dataclass field assignments in auth.py, not URL patterns).
- No `Authorization.*auth_ticket` or `Bearer.*auth_ticket` patterns.
- No real JWT literals in source, tests, docs, or logs.

## Clinical Safety Review

No unsafe clinical wording introduced in changed files. The only match in the changed-file grep is the CODER_REPORT.md describing the safety grep results (not introducing unsafe wording).

## Test Coverage

- `tests/test_bremen_fastapi_auth_enforcement.py`: Added `TestWorkspaceRouteTicketFallback` (valid workspace ticket, rejects stream/report tickets, rejects wrong-job ticket, redirects on no auth, accepts when auth disabled). Added report route rejects workspace ticket test. Updated report route rejection tests to expect redirect (302) instead of 401. Added `BROWSER_NAV_ROUTES` and `test_browser_nav_route_no_token_redirects_to_login`. Removed browser-nav HTML routes from `PROTECTED_ROUTES`.
- `tests/test_bremen_control_room.py`: Added `openWorkspace` ticket-mint navigation tests. Added `TestLiveEventsCatalogRendering` (event list preserved, DOM-derived counts, unknown event fallback, report.completed in STAGE_MAP).
- `tests/test_bremen_auth_activation_readiness.py`: Updated `test_protected_routes_require_token` to only cover fetch-only APIs. Added `test_browser_nav_routes_redirect_to_login`.

## Validation Commands

- `git diff --check`: clean
- `python -m compileall src/bremen tests`: passed
- `pytest tests/test_bremen_report_ui.py -q`: 204 passed
- `pytest tests/test_bremen_control_room.py -q`: 548 passed
- `pytest tests/test_bremen_fastapi_auth_enforcement.py -q`: 56 passed
- `pytest tests/test_bremen_auth.py -q`: 64 passed
- `pytest -q` (full suite): 3631 passed, 11 skipped, 0 failed
- `! grep -RInE 'access_token=.*eyJ|refresh_token=.*eyJ|auth_ticket=.*eyJ' src/bremen tests docs README.md`: no matches
- `! grep -RInE 'access_token=|refresh_token=' src/bremen tests`: pre-existing dataclass field matches only (not URL patterns)
- `! grep -RIn "Authorization.*auth_ticket\|Bearer.*auth_ticket" src/bremen tests`: no matches
- Clinical safety grep on changed files: no unsafe wording

## Findings

No blocking findings. All confirmed live failures are fixed and all architecture rules are preserved.

## Required Changes

None.

## Warnings

- The workspace page (`workspace_ui.py`) internal fetches (`/demo/api/jobs`, `/demo/api/jobs/{job_id}`, EventSource) still use plain `fetch`/`EventSource` without Bearer. When the workspace page is opened via a workspace ticket, the page shell loads (200 HTML) but its internal JSON fetches would require a Bearer session. This is outside the scope of this hotfix (which targets page-route auth consistency); the workspace page's internal fetch handling is a separate concern.
- The security grep `access_token=|refresh_token=` returns pre-existing matches in `src/bremen/auth.py` (lines 363-364) which are `TokenPair` dataclass field assignments, not token-in-URL patterns. These are pre-existing and not introduced by this PR.

## Final Decision

Approved. This PR prevents the confirmed live behavior (`GET /demo/report/{job_id}` and `GET /demo/workspace/{job_id}` returning raw JSON Bearer errors) and fixes the Live Events Catalog summary-without-list issue, while preserving protected JSON API Bearer boundaries, stream/report/workspace ticket flows, refresh retry behavior, token secrecy, and clinical safety language.
