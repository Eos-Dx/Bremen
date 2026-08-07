# CODER REPORT — PR0118 Fix auth-flow test/code misalignments

## TASK COMPLETE

Yes.

## BRANCH

`0118-fix-auth-flow-test-misalignments` (new branch from current origin/main).

## FILES CHANGED

- `src/bremen/api/fastapi_app.py` — removed leftover duplicated code in
  `demo_report_page` that caused a SyntaxError.
- `tests/test_bremen_fastapi_auth_enforcement.py` — fixed `REPORT_BOOTSTRAP_ROUTES`
  fixture and updated `test_report_route_rejects_no_auth` to expect the bootstrap
  shell.
- `tests/test_bremen_auth_activation_readiness.py` — removed `/demo/report/test`
  from `browser_routes` in `test_browser_nav_routes_redirect_to_login`.
- `.project-memory/pr/0118-fix-auth-flow-test-misalignments/FAILURE_ANALYSIS.md` — created.
- `.project-memory/pr/0118-fix-auth-flow-test-misalignments/CODER_REPORT.md` — created.

## FAILURE ANALYSIS SUMMARY

Initial reproduction found a collection error in `tests/test_bremen_fastapi_auth_enforcement.py`
caused by a `SyntaxError` in `src/bremen/api/fastapi_app.py`. After fixing the
syntax error, three test failures remained, all classified as stale test
expectations or fixture/helper mismatches. No test required weakening auth
protection or making protected data public.

## MISALIGNMENTS FIXED

1. **Code regression (SyntaxError)**: `demo_report_page` in `fastapi_app.py` had
   leftover duplicated code from the PR0116-D edit (old docstring tail and old
   gate logic), creating an unterminated triple-quoted string. Removed the
   leftover code.
2. **Stale redirect expectation**: `test_report_route_rejects_no_auth` expected a
   302 redirect for the bare report URL; the deployed behavior returns a 200
   bootstrap shell. Updated the test.
3. **Stale redirect expectation**: `test_browser_nav_routes_redirect_to_login`
   included `/demo/report/test` expecting a 302 redirect; the report route now
   returns a bootstrap shell. Removed the report route from the redirect list.
4. **Fixture/helper mismatch**: `REPORT_BOOTSTRAP_ROUTES` was corrupted with
   leftover tuples from the old `BROWSER_NAV_ROUTES`. Fixed to contain only the
   report path string.

## CODE CHANGES

- `src/bremen/api/fastapi_app.py`: Removed 7 lines of leftover duplicated code in
  `demo_report_page`. The function now correctly:
  - returns the full report with a valid Bearer or valid report ticket;
  - redirects to login with an invalid ticket;
  - returns a safe bootstrap shell (200 HTML) with no Bearer and no ticket.

## TEST CHANGES

- `tests/test_bremen_fastapi_auth_enforcement.py`:
  - `REPORT_BOOTSTRAP_ROUTES` now contains only `"/demo/report/nonexistent"`.
  - `test_report_route_rejects_no_auth` now asserts 200 bootstrap shell with
    `data-report-bootstrap` marker and no raw JSON auth error.
- `tests/test_bremen_auth_activation_readiness.py`:
  - `test_browser_nav_routes_redirect_to_login` no longer includes
    `/demo/report/test` (covered separately by the bootstrap shell test).

## AUTH CONTRACT PRESERVED

- Bare `/demo/report/{job_id}` returns a safe bootstrap shell (200 HTML), not
  protected report data.
- Ticketed report URL returns full report HTML.
- Wrong report tickets (stream, workspace, other-job) are rejected.
- Workspace ticket issuance accepts `purpose="workspace"`.
- Workspace route opens with a workspace ticket.
- Protected JSON APIs remain Bearer-only (401 without Bearer).
- Log redaction prevents `auth_ticket=eyJ` in repo-controlled logs.
- No access_token or refresh_token in URLs.

## REPORT ROUTE TEST ALIGNMENT

- Bare report URL tests now expect a 200 bootstrap shell with `data-report-bootstrap`
  marker, not a redirect.
- Full ticketed report tests still expect full report HTML.
- Wrong-ticket tests still expect rejection.

## WORKSPACE ROUTE TEST ALIGNMENT

- Workspace ticket issuance accepts `purpose="workspace"`.
- Workspace route opens with a workspace ticket.
- Wrong workspace tickets (stream, report, other-job) are rejected.

## PROTECTED JSON API TEST ALIGNMENT

- Fetch-only JSON APIs remain Bearer-only and return 401 without Bearer.
- No `auth_ticket` fallback added to these APIs.

## LOG REDACTION TEST ALIGNMENT

- Log redaction tests still pass: no `auth_ticket=eyJ`, `access_token=eyJ`, or
  `refresh_token=eyJ` in repo-controlled logs.

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

## WARNINGS

- Copied bare report URLs require an existing browser session to auto-open. In a
  fresh browser context, the bootstrap shell shows a login-required state.
- `auth_ticket` remains required for full server-rendered report content.
- Upstream infrastructure logs (Envoy/App Runner) may still require separate
  query-string redaction outside application code.

## READY FOR PRECOMMIT REVIEW

Yes.
