# PR0116-D Precommit Review — Direct Report URL Bootstrap

VERDICT: approved
READY_FOR_COMMIT: true
READY_FOR_PULL_REQUEST: true

## Summary

PR0116-D fixes the final direct report URL gap. Bare `GET /demo/report/{job_id}` (no Bearer, no auth_ticket) now returns a safe HTML bootstrap shell (200) that mints a `purpose="report"` ticket client-side and navigates to the canonical ticketed URL. The full report is only served with a valid Bearer or valid report ticket. Previous PR0116-A/B/C behavior is preserved.

## Files Reviewed

- src/bremen/api/fastapi_app.py (modified)
- src/bremen/report_ui.py (modified)
- tests/test_bremen_auth_activation_readiness.py (modified)
- tests/test_bremen_fastapi_auth_enforcement.py (modified)
- tests/test_bremen_report_ui.py (modified)
- .project-memory/pr/0116-hotfix-frontend-report-auth-refresh/CODER_REPORT.md (modified)
- .project-memory/pr/0116-hotfix-frontend-report-auth-refresh/rounds/D-report-direct-url-bootstrap/CODER_REPORT.md (new)

## Confirmed Production Failure Mapping

Confirmed production behavior before this round:
- `GET /demo/report/{job_id}?auth_ticket=<valid purpose=report ticket>` → 200 full report HTML (works).
- `GET /demo/report/{job_id}` (bare) → no report / auth required / no auth_ticket appended (does not work).

The report route and report ticket validation were already correct. The missing behavior was the browser bootstrap: bare report URL should mint a `purpose="report"` ticket from the stored browser session and navigate to the ticketed URL.

## Bare Report Route Review

`GET /demo/report/{job_id}` without Bearer and without auth_ticket now returns a safe HTML bootstrap shell (verified: 200, text/html):
- Contains the `data-report-bootstrap` marker.
- Contains the job_id.
- Contains no protected patient/report/model/result details (no `p_mri_needed`, no `decision_code`, no `assessment-hero`, no `report-document`).
- Does not return raw JSON Bearer error.
- Does not expose full protected report content.

## Bootstrap Shell Review

`build_report_bootstrap_page(base_url, job_id)` returns a safe HTML shell that:
- Reads canonical browser auth storage (`bremen_access_token`, `bremen_refresh_token`).
- Mints a `purpose="report"` ticket via `_authFetchTicket(jobId, 'report')`.
- Handles expired access token through the existing refresh path (via `_authFetch`).
- Navigates via `window.location.replace` to `/demo/report/{job_id}?auth_ticket=<ticket>`.
- Does not create `access_token=` or `refresh_token=` URLs.
- Shows a login-required state with a link to `/demo/login?next=/demo/report/{job_id}` when no session exists.
- No infinite reload/redirect loop (uses `location.replace`, not a plain reload of the bare URL).

## Ticketed Report Regression Review

`GET /demo/report/{job_id}?auth_ticket=<valid report ticket>` → 200 full report (verified).

Negative cases:
- Stream ticket rejected on report route (verified: redirect to login).
- Workspace ticket rejected on report route (verified: redirect to login).
- Other-job report ticket rejected (verified: redirect to login).

## Protected API Boundary Review

All fetch-only JSON API routes remain Bearer-only and return 401 without a Bearer token:
- `GET /demo/api/jobs/{job_id}`
- `GET /demo/api/jobs/{job_id}/reports/bremen`
- `GET /demo/api/reports/{job_id}/external`
- `GET /demo/api/reports/{job_id}/internal`

No `auth_ticket` fallback was added to these fetch-only JSON APIs.

## Previous PR0116 Regression Review

- Report page internal JSON calls still use `_authFetch` (verified).
- Report refresh on 401 still retries exactly once (verified).
- `openJob` still mints `purpose="report"` (verified).
- Workspace ticket issuance still accepts `purpose="workspace"` (verified).
- Workspace route still opens with workspace ticket (verified).
- Workspace internal `_authFetch` still intact (verified).
- Workspace SSE still uses stream ticket (verified).
- `connectSSE` still uses stream ticket (verified).
- Live Events Catalog still renders list (verified).
- Log redaction still prevents `auth_ticket=eyJ` in repo-controlled logs (verified).

## Token Safety Review

- No `auth_ticket=eyJ`, `access_token=eyJ`, or `refresh_token=eyJ` literals.
- No `access_token=`/`refresh_token=` URL construction in control_room_ui.py, report_ui.py, workspace_ui.py, or tests.
- No `Authorization: Bearer <JWT literal>` patterns.
- Only short-lived `auth_ticket` may appear in browser URL.

## Clinical Safety Review

No unsafe clinical wording introduced in changed files. The only match in the changed-file grep is the CODER_REPORT.md describing the safety grep results (not introducing unsafe wording).

## Test Coverage

- `tests/test_bremen_report_ui.py`: Added `TestReportBootstrapShell` (bootstrap marker, job_id, no protected data, mints report ticket, navigates to ticketed URL, no tokens in URL, login fallback, no infinite loop, canonical storage, login-required state).
- `tests/test_bremen_fastapi_auth_enforcement.py`: Updated `test_report_route_rejects_no_auth` to expect bootstrap shell (200). Added `REPORT_BOOTSTRAP_ROUTES` and `test_report_bootstrap_route_no_token_returns_shell`. Removed report route from `BROWSER_NAV_ROUTES`.
- `tests/test_bremen_auth_activation_readiness.py`: Updated `test_browser_nav_routes_redirect_to_login` to remove report route. Added `test_report_bootstrap_route_returns_shell`.

## Validation Commands

- `git diff --check`: clean
- `python -m compileall src/bremen tests`: passed
- `pytest tests/test_bremen_report_ui.py -q`: 214 passed
- `pytest tests/test_bremen_fastapi_auth_enforcement.py -q`: 59 passed
- `pytest tests/test_bremen_control_room.py -q`: 548 passed
- `pytest tests/test_bremen_auth.py -q`: 64 passed
- `pytest tests/test_bremen_workspace_ui.py -q`: 34 passed
- `pytest tests/test_bremen_access_logging.py -q`: 15 passed
- `pytest -q` (full suite): 3675 passed, 11 skipped, 0 failed
- `! grep -RInE 'auth_ticket=eyJ|access_token=eyJ|refresh_token=eyJ' src/bremen tests docs README.md`: no matches
- `! grep -RInE 'access_token=|refresh_token=' src/bremen/control_room_ui.py src/bremen/report_ui.py src/bremen/workspace_ui.py tests`: no matches
- `! grep -RInE 'Authorization: Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' src/bremen tests docs README.md`: no matches
- Clinical safety grep on changed files: no unsafe wording

## Findings

No blocking findings. All confirmed production failures are fixed and all architecture rules are preserved.

## Required Changes

None.

## Warnings

- Bare `/demo/report/{job_id}` now returns a safe bootstrap shell, not the full report. The full report is only served with a valid Bearer or valid report ticket.
- Copied bare report URLs require an existing browser session to auto-open. In a fresh browser context, the shell shows a login-required state.
- `auth_ticket` remains required for full server-rendered report content.

## Final Decision

Approved. This round makes the smoke pass: a logged-in browser opening `/demo/report/{job_id}` loads the safe bootstrap shell, mints a `purpose="report"` ticket, navigates to `/demo/report/{job_id}?auth_ticket=<ticket>`, and opens the full report. A fresh/no-session browser shows a clear login-required state with no protected data exposed. A ticketed URL opens the full report. Previous PR0116 behavior is preserved.
