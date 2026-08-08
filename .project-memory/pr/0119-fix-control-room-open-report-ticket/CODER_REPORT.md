# CODER REPORT — PR0119 Fix Control Room Open report button so it mints and appends report auth_ticket

## TASK COMPLETE

Yes.

## BRANCH

`0119-fix-control-room-open-report-ticket` (new branch from current origin/main).

## FILES CHANGED

- `src/bremen/control_room_ui.py`:
  - Wired the "Open report" button in the active result card to `openJob(jobId)`
    via an `onclick` handler (mints a `purpose="report"` ticket before navigation).
  - Updated `openJob`'s ticket-mint failure path to redirect to
    `/demo/login?next=/demo/report/{jobId}` instead of silently falling back to
    the bare report URL.
- `tests/test_bremen_control_room.py`:
  - Added `TestControlRoomOpenReportTicket` class covering the Open report button
    wiring, `openJob` ticket minting, ticketed URL navigation, no bare report
    navigation, no tokens in URL, login-with-next failure path, job_id
    consistency, and history-row wiring.
- `.project-memory/pr/0119-fix-control-room-open-report-ticket/CODER_REPORT.md` — created.

## ROOT CAUSE

The "Open report" button in the active result card was a plain `<a>` link with
`href="'+baseUrl+'/demo/report/'+jobId+'"` and NO `onclick` handler. Clicking it
navigated directly to the bare `/demo/report/{job_id}` URL without minting a
ticket. The bare URL then showed the safe bootstrap shell with "Login required to
open this report".

The `openJob(jobId)` function already correctly minted a `purpose="report"`
ticket and navigated to the ticketed URL, but the "Open report" button was not
wired to it. The patient history rows already used `openJob`, but the active
result card button did not.

## CONTROL ROOM OPEN REPORT FIX

The "Open report" button now uses:
```
onclick="event.preventDefault();openJob('<job_id>')"
```
This calls `openJob(jobId)`, which:
1. Calls `_authFetchTicket(jobId, 'report')`.
2. On success, navigates to `/demo/report/{jobId}?auth_ticket=<ticket>`.
3. On failure, redirects to `/demo/login?next=/demo/report/{jobId}` (does not
   silently fall back to the bare report URL).

## REPORT ENTRYPOINTS AUDITED

All Control Room report entrypoints were audited:
- **Active result card "Open report" button**: now wired to `openJob(jobId)`
  (was a bare href).
- **Patient history rows**: already use `onclick="openJob(...)"` (correct).
- **Open workspace button**: already uses `openWorkspace(jobId)` (correct).

Every protected full-report entrypoint now mints a `purpose="report"` ticket
before navigation.

## JOB_ID WIRING

`openJob(jobId)` uses the same `jobId` variable for both the ticket mint
(`_authFetchTicket(jobId, 'report')`) and the final navigation URL
(`/demo/report/'+jobId+'?auth_ticket='`). No stale selected job, no
patient/container id, no model_id/workflow_id in place of job_id.

## TOKEN SAFETY

- No `access_token` or `refresh_token` in URLs.
- The only URL token allowed is `auth_ticket=<short-lived report ticket>`.
- No raw JWT/token logging.

## REGRESSIONS PRESERVED

- Direct bare `/demo/report/{job_id}` still returns a safe bootstrap shell.
- Ticketed report route still returns full report with a valid report ticket.
- Wrong report tickets (stream, workspace, other-job) remain rejected.
- Workspace Open workspace still mints `purpose="workspace"`.
- SSE still mints `purpose="stream"`.
- Protected JSON APIs remain Bearer-only.
- Log redaction tests still pass.

## TESTS ADDED/UPDATED

Added `TestControlRoomOpenReportTicket` to `tests/test_bremen_control_room.py`:
- `test_open_report_button_wired_to_open_job`
- `test_open_report_button_not_bare_href_only`
- `test_open_job_mints_report_ticket`
- `test_open_job_navigates_to_ticketed_url`
- `test_open_job_no_bare_report_navigation_after_success`
- `test_open_job_no_tokens_in_url`
- `test_open_job_failure_redirects_to_login_with_next`
- `test_open_job_job_id_consistent`
- `test_history_row_uses_open_job`
- `test_open_report_button_uses_job_id`

## VALIDATION RUN

| Command | Exit | Result |
|---|---|---|
| `python -m compileall src/bremen tests` | 0 | Pass |
| `pytest tests/test_bremen_control_room.py -q` | 0 | 558 passed |
| `pytest tests/test_bremen_report_ui.py -q` | 0 | 214 passed |
| `pytest tests/test_bremen_fastapi_auth_enforcement.py -q` | 0 | 59 passed |
| `pytest tests/test_bremen_auth.py -q` | 0 | 64 passed |
| `pytest tests/test_bremen_workspace_ui.py -q` | 0 | 34 passed |
| `pytest tests/test_bremen_access_logging.py -q` | 0 | 15 passed |
| `pytest -q` (full suite) | 0 | 3685 passed, 11 skipped |
| `git diff --check` | 0 | Pass |
| `! grep -RInE 'auth_ticket=eyJ\|access_token=eyJ\|refresh_token=eyJ' src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RInE 'access_token=\|refresh_token=' src/bremen/control_room_ui.py src/bremen/report_ui.py src/bremen/workspace_ui.py tests` | 0 | Pass (no matches) |
| `! grep -RInE 'Authorization: Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' src/bremen tests docs README.md` | 0 | Pass (no matches) |

## PRODUCTION SMOKE EXPECTATION

In a logged-in browser:
1. Open Control Room.
2. Select patient/result card.
3. Click green "Open report".

Expected Network:
- `POST /demo/api/jobs/{job_id}/auth/ticket` with `{"purpose":"report"}` -> 201.

Expected final URL:
- `/demo/report/{job_id}?auth_ticket=<ticket>`.

Expected UI:
- Full report opens.

Not acceptable:
- `/demo/report/{job_id}` with no `auth_ticket`.
- "Login required to open this report" after clicking green Open report from a
  logged-in Control Room.

## WARNINGS

- Copied bare report URLs still require an existing browser session to auto-open.
  In a fresh browser context, the bootstrap shell shows a login-required state.
- `auth_ticket` remains required for full server-rendered report content.
- Upstream infrastructure logs (Envoy/App Runner) may still require separate
  query-string redaction outside application code.

## READY FOR PRECOMMIT REVIEW

Yes.
