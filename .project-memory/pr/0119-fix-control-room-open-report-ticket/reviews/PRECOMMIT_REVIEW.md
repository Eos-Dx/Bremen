# Precommit Review — Control Room Open Report Ticket Navigation

VERDICT: approved
READY_FOR_COMMIT: true
READY_FOR_PULL_REQUEST: true

## Summary

This branch (`0119-fix-control-room-open-report-ticket`) fixes the production
issue where the Control Room green "Open report" button navigated to the bare
`/demo/report/{job_id}` URL without minting a report ticket, causing the safe
bootstrap shell to show "Login required to open this report".

The root cause was that the "Open report" button in the active result card was a
plain `<a>` link with `href="/demo/report/{job_id}"` and no `onclick` handler.
The `openJob(jobId)` function already correctly minted a `purpose="report"`
ticket and navigated to the ticketed URL, but the button was not wired to it.

The fix wires the "Open report" button to `openJob(jobId)` via
`onclick="event.preventDefault();openJob('<job_id>')"`, and updates `openJob`'s
ticket-mint failure path to redirect to `/demo/login?next=/demo/report/{job_id}`
instead of silently falling back to the bare report URL.

All changed files were read in full. The full test suite passes (3685 passed,
11 skipped). Security greps for token leakage pass. Direct report bootstrap and
ticketed report routes are preserved. Workspace/SSE flows and protected JSON API
boundaries are unchanged. No unsafe clinical/regulatory wording was introduced.

## Branch/Base Review

- Branch: `0119-fix-control-room-open-report-ticket` (exact match required).
- HEAD: `307299de9d14a25675f220d2169086127cf8056e`.
- `git merge-base --is-ancestor origin/main HEAD` returned "based on origin/main".
- Working tree is clean except for the intended changes and the
  `.project-memory/pr/0119-fix-control-room-open-report-ticket/` directory.
- The branch is a new branch from current origin/main; it is not an old
  merged/deleted branch.

## Files Reviewed

- `src/bremen/control_room_ui.py` (changed)
- `tests/test_bremen_control_room.py` (changed)
- `.project-memory/pr/0119-fix-control-room-open-report-ticket/CODER_REPORT.md`
- `src/bremen/report_ui.py` (read for bootstrap/ticketed report regression)
- `src/bremen/api/fastapi_app.py` (read for report route / auth gate regression)

## Production Failure Mapping

The production failure is accurately mapped:

- **Observed**: Clicking "Open report" navigated to `/demo/report/{job_id}` with
  no `auth_ticket`, showing the safe bootstrap shell with "Login required to
  open this report".
- **Root cause**: The "Open report" button in the active result card was a plain
  `<a>` link with `href="/demo/report/{job_id}"` and no `onclick` handler. It
  bypassed the `openJob(jobId)` function that mints a `purpose="report"` ticket.
- **Fix**: Wire the button to `openJob(jobId)` via an `onclick` handler that
  calls `event.preventDefault()` and `openJob('<job_id>')`.

## Control Room Open Report Review

The green "Open report" button is now correctly wired:

- `src/bremen/control_room_ui.py:933`:
  `onclick="event.preventDefault();openJob('<job_id>')"`.
- `openJob(jobId)` (line 735) calls `_authFetchTicket(jobId,'report')` to mint a
  `purpose="report"` ticket.
- On success, navigates to
  `/demo/report/{jobId}?auth_ticket=<ticket>` (line 737).
- Does NOT navigate to bare `/demo/report/{jobId}` after successful ticket mint.
- On ticket-mint failure, redirects to
  `/demo/login?next=/demo/report/{jobId}` (line 741) — does NOT silently fall
  back to the bare report URL.

## Report Entrypoint Audit

All Control Room report entrypoints were audited:

- **Active result card "Open report" button** (line 933): now wired to
  `openJob(jobId)` via `onclick="event.preventDefault();openJob(...)"`. The
  `href` is overridden by `event.preventDefault()`.
- **Patient history rows** (line 691): already use
  `onclick="openJob('<job_id>')"` (correct, unchanged).
- **Open workspace button** (line 934): uses
  `onclick="event.preventDefault();openWorkspace(...)"` (correct, unchanged).

No protected full-report button bypasses report ticket minting. The only
remaining `/demo/report/` references are the `href` attributes (overridden by
`event.preventDefault()`) and the `openJob` function's ticketed URL.

## Job ID Wiring Review

`openJob(jobId)` uses the same `jobId` variable for both the ticket mint
(`_authFetchTicket(jobId,'report')`) and the final navigation URL
(`/demo/report/'+jobId+'?auth_ticket='`). No patient/container/model/workflow id
is substituted for job_id. No stale selected job id is used. The button passes
the specific `job_id` to `openJob`.

## Direct Report Bootstrap Regression Review

The direct report bootstrap route is preserved. `src/bremen/api/fastapi_app.py`
was NOT changed in this PR. The `demo_report_page` function still returns a safe
bootstrap shell (200 HTML) with no Bearer and no auth_ticket, containing no
protected report data. The `data-report-bootstrap` marker and the "Login
required" fallback remain intact.

## Ticketed Report Regression Review

The ticketed report route is preserved. `fastapi_app.py` was NOT changed. The
`demo_report_page` function still returns the full report with a valid Bearer or
valid report ticket, and redirects to login with an invalid ticket. Wrong
tickets (stream, workspace, other-job) remain rejected. The `_check_auth_gate_with_ticket`
logic is unchanged.

## Other Auth Flow Regression Review

- **openWorkspace** (line 746): still mints `purpose="workspace"` and navigates
  to `/demo/workspace/{jobId}?auth_ticket=<ticket>`. Unchanged.
- **Workspace route**: unchanged in `fastapi_app.py`; still accepts a valid
  workspace ticket.
- **SSE** (line 761): still mints `purpose="stream"` and opens EventSource with
  `auth_ticket=<ticket>`. Unchanged.
- **Protected JSON APIs**: unchanged in `fastapi_app.py`; remain Bearer-only via
  `_check_auth_gate`. No `auth_ticket` fallback.
- **Log redaction**: unchanged in `logging_config.py`; still active.

## Token Safety Review

Security greps pass:
- No `auth_ticket=eyJ`, `access_token=eyJ`, or `refresh_token=eyJ` in
  `src/bremen`, `tests`, `docs`, `README.md`.
- No `access_token=` or `refresh_token=` in `control_room_ui.py`,
  `report_ui.py`, `workspace_ui.py`, or `tests`.
- No hardcoded `Authorization: Bearer <jwt>` patterns in source/tests/docs.

The only token allowed in report/SSE/workspace document/EventSource URLs is
`auth_ticket=<short-lived ticket>`. No `access_token` or `refresh_token` appears
in URL construction.

## Test Quality Review

The new `TestControlRoomOpenReportTicket` class in `tests/test_bremen_control_room.py`
would fail on the observed production bug:

- `test_open_report_button_wired_to_open_job` — fails if the button is a bare
  href without `openJob`.
- `test_open_report_button_not_bare_href_only` — fails if the button lacks the
  `onclick="event.preventDefault();openJob(...)"` handler.
- `test_open_job_mints_report_ticket` — fails if `openJob` does not call
  `_authFetchTicket(jobId,'report')`.
- `test_open_job_navigates_to_ticketed_url` — fails if `openJob` does not
  navigate to the ticketed URL.
- `test_open_job_no_bare_report_navigation_after_success` — fails if `openJob`
  navigates to the bare report URL after ticket mint.
- `test_open_job_no_tokens_in_url` — fails if `access_token`/`refresh_token`
  appear in the URL.
- `test_open_job_failure_redirects_to_login_with_next` — fails if ticket mint
  failure silently opens the bare report URL.
- `test_open_job_job_id_consistent` — fails if different job_id is used for
  ticket mint and URL.
- `test_history_row_uses_open_job` — guards the history-row entrypoint.
- `test_open_report_button_uses_job_id` — guards job_id wiring.

These tests directly cover the observed green-button bug and the required
failure modes. No tests were weakened.

## Clinical Safety Review

The UI copy grep for unsafe clinical/regulatory wording
(`detects cancer|diagnoses|diagnosis engine|rules out disease|no MRI needed|
replaces clinician|FDA approved|clinically certified`) returned no matches in
changed files. The changed UI text is limited to the `onclick` handler wiring
and the failure-path comment; no new clinical/regulatory claims were introduced.

## Validation Commands

| Command | Result |
|---|---|
| `git diff --check` | Pass |
| `python -m compileall src/bremen tests` | Pass |
| `pytest tests/test_bremen_control_room.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_report_ui.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_fastapi_auth_enforcement.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_auth.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_workspace_ui.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_access_logging.py -q` | Pass (in combined run) |
| Combined targeted run | 944 passed |
| `pytest -q` (full suite) | 3685 passed, 11 skipped |
| `! grep auth_ticket=eyJ\|access_token=eyJ\|refresh_token=eyJ` | Pass (no matches) |
| `! grep access_token=\|refresh_token=` in UI/tests | Pass (no matches) |
| `! grep Authorization: Bearer <jwt>` | Pass (no matches) |
| UI copy clinical grep | Pass (no matches) |

## Findings

No blocking findings. The production failure is accurately mapped and fixed.
The "Open report" button now mints a `purpose="report"` ticket and navigates to
the ticketed report URL. All report entrypoints are audited. Job id wiring is
correct. Direct report bootstrap and ticketed report routes are preserved.
Workspace/SSE flows and protected JSON API boundaries are unchanged. Token
safety is preserved. Tests cover the observed bug. The full suite passes.

## Required Changes

None.

## Warnings

- Copied bare report URLs still require an existing browser session to
  auto-open; in a fresh browser context, the bootstrap shell shows a
  login-required state. This is expected behavior, not a regression.
- Upstream infrastructure logs (Envoy/App Runner) may require separate
  query-string redaction outside application code; outside the scope of this
  branch.

## Final Decision

**APPROVED.** The production smoke would pass: clicking the green "Open report"
in a logged-in Control Room mints a `purpose="report"` ticket (POST returns
201), navigates to `/demo/report/{job_id}?auth_ticket=<ticket>`, and the full
report opens. The bare `/demo/report/{job_id}` "Login required" path is no
longer reached from the green button. The branch is correct and based on
origin/main. The full suite passes. No token leakage or unsafe clinical wording
was introduced.
