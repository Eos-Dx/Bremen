# CODER REPORT — PR0116-D Direct report URL must bootstrap and append report auth_ticket

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
