# PR0116 Precommit Review — Frontend Report Auth Refresh Hotfix

VERDICT: approved
READY_FOR_COMMIT: true
READY_FOR_PULL_REQUEST: true

## Summary

PR0116 fixes the observed production failure where `/demo/report/{job_id}?auth_ticket=...` returns 200 but the report page's protected JSON fetches return 401 Bearer auth errors. The report page (`report_ui.py`) previously had no auth helper and used plain `fetch(...)` for all four protected report endpoints. This PR adds the canonical browser auth contract (`_authFetch`) to the report page, replaces all four plain fetches with `_authFetch`, and adds graceful degradation when no stored session exists.

## Files Reviewed

- src/bremen/report_ui.py (modified)
- tests/test_bremen_report_ui.py (modified)
- .project-memory/pr/0116-hotfix-frontend-report-auth-refresh/CODER_REPORT.md (new)

## Production Failure Mapping

The observed failure was: `/demo/report/{job_id}?auth_ticket=...` returns 200, then report page protected JSON fetches return 401 Bearer auth errors.

Root cause confirmed: The report page (`report_ui.py`) had no auth helper at all. All four protected report JSON fetches in `loadReport()` used plain `fetch(...)`:
- `GET /demo/api/jobs/{job_id}`
- `GET /demo/api/jobs/{job_id}/reports/bremen`
- `GET /demo/api/reports/{job_id}/external`
- `GET /demo/api/reports/{job_id}/internal`

No `Authorization: Bearer` header was attached and no refresh flow existed. The Control Room had a working `_authFetch` with refresh+retry, but the report page was a separate document that did not reuse it.

## Frontend Auth Flow Review

The report page now defines the canonical browser auth helpers matching the Control Room's implementation exactly:
- `_getSessionStorage()` — reads from `sessionStorage`
- `_getAccessToken()` — reads `bremen_access_token`
- `_getRefreshToken()` — reads `bremen_refresh_token`
- `_setTokens(data)` — stores access/refresh tokens and expiry to canonical keys
- `_clearTokens()` — clears all token keys
- `_redirectToLogin()` — redirects to `/demo/login`
- `_authFetch(url, opts)` — attaches Bearer, refreshes on 401, retries once

## Report Page Fetch Review

All four protected report endpoints now use `_authFetch`:
- `_authFetch(baseUrl+'/demo/api/jobs/'+jid)`
- `_authFetch(baseUrl+'/demo/api/jobs/'+jid+'/reports/bremen')`
- `_authFetch(baseUrl+'/demo/api/reports/'+jid+'/external')`
- `_authFetch(baseUrl+'/demo/api/reports/'+jid+'/internal')`

No plain `fetch(...)` remains for protected report endpoints. Verified by manual inspection of the generated JS and by tests.

## Refresh Retry Review

- On 401, `_authFetch` reads the refresh token and calls `POST /demo/api/auth/refresh`.
- On success, `_setTokens(result.data)` stores the new access/refresh tokens to canonical storage.
- The in-memory `headers` object is updated with the new Bearer token.
- The original request is retried exactly once (`fetch(url,opts)` count = 2: one initial + one retry).
- No refresh loop: `auth/refresh` appears exactly once in `_authFetch`, no `while` loop.
- On refresh failure or missing refresh token, tokens are cleared and user is redirected to login.

## Ticket Flow Regression Review

- `connectSSE()` in Control Room still mints a `purpose=stream` ticket and uses `auth_ticket` in the EventSource URL.
- `openJob()` in Control Room still mints a `purpose=report` ticket and navigates to `/demo/report/{job_id}?auth_ticket=...`.
- No access_token or refresh_token is placed in URLs.
- The report page ticket navigation flow is unchanged.

## Backend Auth Boundary Review

- Backend auth is not weakened. All protected routes still use `_check_auth_gate` (Bearer) or `_check_auth_gate_with_ticket` (report/SSE ticket fallback).
- Report ticket is not silently accepted as general Bearer replacement.
- Ticket purpose and job_id constraints remain intact.
- No changes to `src/bremen/api/fastapi_app.py` in this PR.

## Token Leak Review

- No `access_token=` or `refresh_token=` URL construction.
- No `auth_ticket=.*eyJ` patterns.
- No real JWT literals in frontend strings.
- No tokens or tickets logged.
- No hard-coded JWTs.

## Test Coverage

Added `TestReportPageAuthFetch` class to `tests/test_bremen_report_ui.py` with 20 tests covering:
- Auth helper presence and canonical storage keys
- Bearer attachment
- Refresh-on-401
- Token storage via `_setTokens`
- Single retry (no refresh loop)
- Token-clear on failure
- All four protected endpoints wrapped with `_authFetch`
- No plain fetch for protected endpoints
- No token-in-URL
- No JWT literals
- Graceful degradation when no session
- Sample-mode bypass

## Validation Commands

- `git diff --check`: clean
- `python -m compileall src/bremen tests`: passed
- `pytest tests/test_bremen_report_ui.py -q`: 204 passed
- `pytest tests/test_bremen_control_room.py -q`: 533 passed
- `pytest tests/test_bremen_fastapi_auth_enforcement.py -q`: 47 passed
- `pytest tests/test_bremen_auth.py -q`: 64 passed
- `pytest -q` (full suite): 3606 passed, 11 skipped, 0 failed
- `! grep -RInE 'access_token=.*eyJ|refresh_token=.*eyJ|auth_ticket=.*eyJ' src/bremen tests docs README.md`: no matches
- `! grep -RInE 'access_token=|refresh_token=' src/bremen/control_room_ui.py tests`: no matches
- `! grep -RIn "Authorization.*auth_ticket\|Bearer.*auth_ticket" src/bremen tests`: no matches
- Clinical safety grep on diff: no unsafe wording

## Findings

No blocking findings. The hotfix correctly addresses the observed production failure.

## Required Changes

None.

## Warnings

- The clinical safety grep (`detects cancer|diagnoses|...`) returns matches in pre-existing unrelated files (`model_playground_page.html`, `demo_evidence.py`, various tests, docs). These are NOT part of this PR. The diff for this PR introduces no forbidden clinical phrases.

## Final Decision

Approved. This PR prevents the observed browser behavior (`/demo/report/{job_id}?auth_ticket=...` → 200, then protected report JSON calls → 401) for a normally logged-in user opening report from the Control Room, including the case where the access token has expired but refresh token is still valid.
