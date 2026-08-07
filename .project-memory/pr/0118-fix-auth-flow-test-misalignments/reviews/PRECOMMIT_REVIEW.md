# Precommit Review — Auth-Flow Test/Code Misalignment Fixes

VERDICT: approved
READY_FOR_COMMIT: true
READY_FOR_PULL_REQUEST: true

## Summary

This branch (`0118-fix-auth-flow-test-misalignments`) fixes test/code
misalignments that surfaced after the deployed auth-flow changes (PR0116-D).
The primary blocker was a `SyntaxError` in `src/bremen/api/fastapi_app.py`
caused by leftover duplicated code in `demo_report_page` (an unterminated
triple-quoted string). After removing the leftover code, three stale/fixture
test expectations were corrected to match the deployed contract: the bare
`/demo/report/{job_id}` route returns a safe 200 HTML bootstrap shell (not a
302 redirect), and the `REPORT_BOOTSTRAP_ROUTES` fixture was repaired.

All changed files were read in full. The full test suite passes (3675 passed,
11 skipped). Security greps for token leakage pass. No protected JSON API
accepts `auth_ticket`. No access_token/refresh_token appears in URL
construction. Log redaction coverage is intact. No unsafe clinical/regulatory
wording was introduced.

## Branch/Base Review

- Branch: `0118-fix-auth-flow-test-misalignments` (exact match required).
- HEAD: `ce8486cf408659dc93173626f183d41ed7e658c5`.
- `git merge-base --is-ancestor origin/main HEAD` returned "based on origin/main".
- Working tree is clean except for the intended changes and the
  `.project-memory/pr/0118-fix-auth-flow-test-misalignments/` directory.
- The branch is a new branch from current origin/main; it is not an old
  merged/deleted branch.

## Files Reviewed

- `src/bremen/api/fastapi_app.py` (changed)
- `tests/test_bremen_fastapi_auth_enforcement.py` (changed)
- `tests/test_bremen_auth_activation_readiness.py` (changed)
- `.project-memory/pr/0118-fix-auth-flow-test-misalignments/FAILURE_ANALYSIS.md`
- `.project-memory/pr/0118-fix-auth-flow-test-misalignments/CODER_REPORT.md`
- `src/bremen/report_ui.py` (read for bootstrap shell / full report content)
- `src/bremen/control_room_ui.py` (read for frontend auth flow)
- `src/bremen/workspace_ui.py` (read for frontend auth flow)
- `src/bremen/logging_config.py` (read for redaction)
- `tests/test_bremen_report_ui.py` (read for bootstrap/full report assertions)
- `tests/test_bremen_access_logging.py` (read for redaction coverage)
- `tests/test_bremen_workspace_ui.py` (read for frontend auth flow)

## Failure Analysis Review

The `FAILURE_ANALYSIS.md` lists every initially failing test and classifies
each failure:

1. `src/bremen/api/fastapi_app.py` — `SyntaxError` (U+2014) — classified
   `code_regression`. Root cause: leftover duplicated code from the PR0116-D
   edit created an unterminated triple-quoted string.
2. `test_report_bootstrap_route_no_token_returns_shell` — `TypeError` from
   tuple in `REPORT_BOOTSTRAP_ROUTES` — classified `fixture_mismatch`.
3. `test_report_route_rejects_no_auth` — `assert 200 == 302` — classified
   `stale_test` (stale redirect expectation).
4. `test_browser_nav_routes_redirect_to_login` — `assert 200 == 302` for
   `/demo/report/test` — classified `stale_test`.

Each fix maps to the auth-flow contract (bare report URL returns a safe
bootstrap shell). No failure was hidden by skip/xfail/delete without
justification. The classification categories used (code_regression,
fixture_mismatch, stale_test) are a subset of the required taxonomy; no
`duplicate_inconsistent_semantics` case was present. The analysis is complete
and accurate.

## Report Route Test Alignment

The report route tests now distinguish the required cases:

1. **Bare report bootstrap shell** — `test_report_route_rejects_no_auth`
   (auth enforcement) and `test_report_bootstrap_route_no_token_returns_shell`
   assert 200 HTML with `data-report-bootstrap` marker and no raw JSON Bearer
   error. The `TestReportBootstrapShell` class in `test_bremen_report_ui.py`
   additionally asserts the shell contains the job_id, does NOT contain
   protected details (`p_mri_needed`, `decision_code`, `report-document`,
   `assessment-hero`), and mints a `purpose="report"` ticket.
2. **Full ticketed report** — `test_report_route_accepts_valid_report_ticket`
   asserts a valid report ticket is accepted (not 401). Full report HTML
   content is thoroughly verified via `build_report_page` in
   `test_bremen_report_ui.py`.
3. **Wrong-purpose tickets rejected** — `test_report_route_rejects_stream_ticket`
   (302 redirect), `test_report_route_rejects_workspace_ticket` (302 redirect),
   and `test_report_route_rejects_wrong_job_ticket` (302 redirect) all present.

## Workspace Route Test Alignment

- `test_mint_endpoint_workspace_purpose` asserts `purpose="workspace"` ticket
  issuance returns 201 with `token_type == "stream_ticket"` and
  `purpose == "workspace"` — workspace purpose is expected valid.
- `test_workspace_route_accepts_valid_workspace_ticket` asserts 200 HTML.
- `test_workspace_route_rejects_stream_ticket` (302), 
  `test_workspace_route_rejects_report_ticket` (302), and
  `test_workspace_route_rejects_wrong_job_ticket` (302) all present.
- `test_workspace_route_rejects_no_auth` asserts 302 redirect to login.

## Protected JSON API Boundary Review

The `PROTECTED_ROUTES` list includes all required fetch-only JSON APIs:
`/demo/api/h5/containers`, `/demo/api/jobs`, `/demo/api/jobs/{id}`,
`/demo/api/jobs/{id}/events`, `/demo/api/jobs/{id}/reports`,
`/demo/api/jobs/{id}/reports/bremen`, `/demo/api/reports/{id}/external`,
`/demo/api/reports/{id}/internal`. `test_protected_route_no_token_401` asserts
these return 401 without Bearer.

`TestOtherRoutesRejectTicket` verifies `/demo/api/jobs` and
`/demo/api/h5/containers` reject `auth_ticket` (401). The code uses
`_check_auth_gate` (Bearer-only) for all JSON APIs; no `auth_ticket` fallback
was added. The boundary is preserved.

## Frontend Auth Flow Review

Verified in `control_room_ui.py`, `workspace_ui.py`, and `report_ui.py`:

- `openJob` uses `_authFetchTicket(jobId,'report')` — purpose="report".
- `openWorkspace` uses `_authFetchTicket(jobId,'workspace')` — purpose="workspace".
- `bootstrapReportTicket` uses `_authFetchTicket(jobId,'report')` — purpose="report".
- `connectSSE` uses `_authFetchTicket(jobId,'stream')` — purpose="stream".
- No `access_token=` or `refresh_token=` in any URL construction (verified by
  security grep and by `test_bootstrap_shell_no_tokens_in_url`).
- `_authFetch` performs a single refresh retry (one refresh POST, then one
  retry of the original request); no infinite loop. Verified by
  `test_bremen_workspace_ui.py` and `test_bremen_report_ui.py`
  (`_authFetch does not loop on refresh; only one retry per request`).

## Log Redaction Review

`test_bremen_access_logging.py` verifies redaction of `auth_ticket`,
`access_token`, `refresh_token`, `token`, and `ticket` via
`redact_sensitive_query_params` and `SensitiveQueryRedactionFilter`. It also
verifies non-sensitive params (`workflow_id`, `model_id`, `page`) are
preserved, and that the filter always returns True (does not drop records,
i.e., request behavior is not mutated). The security grep confirms no
`auth_ticket=eyJ` in repo-controlled logs.

## Test Quality Review

No tests were weakened in a way that would miss regressions:

- The bare report test now asserts 200 HTML + `data-report-bootstrap` marker +
  no raw JSON error (stronger than the old 302-only check).
- The bootstrap shell content is verified (job_id present, protected data
  absent) in `test_bremen_report_ui.py`.
- Wrong-purpose/wrong-job ticket tests are retained for report, workspace, and
  stream routes.
- Protected JSON API tests remain strict (401 without Bearer).
- No broad skips were added; no meaningful assertions were deleted.
- The `test_report_route_accepts_valid_report_ticket` assertion (`!= 401`) is
  pre-existing and not weakened by this PR; full report content is covered by
  `build_report_page` tests.

## Code Safety Review

The code change in `fastapi_app.py` only removes leftover duplicated code
(old docstring tail and old gate logic) that caused a SyntaxError. The
`demo_report_page` function now correctly:
- returns the full report with a valid Bearer or valid report ticket;
- redirects to login with an invalid ticket (wrong purpose/job);
- returns a safe bootstrap shell (200 HTML) with no Bearer and no ticket.

No code change makes report/workspace routes public with protected data,
allows wrong-purpose/wrong-job tickets, adds `auth_ticket` fallback to JSON
APIs, or removes/bypasses log redaction.

## Token Safety Review

Security greps pass:
- No `auth_ticket=eyJ`, `access_token=eyJ`, or `refresh_token=eyJ` in
  `src/bremen`, `tests`, `docs`, `README.md`.
- No `access_token=` or `refresh_token=` in `control_room_ui.py`,
  `report_ui.py`, `workspace_ui.py`, or `tests`.
- No hardcoded `Authorization: Bearer <jwt>` patterns in source/tests/docs.

## Clinical Safety Review

The UI copy grep for unsafe clinical/regulatory wording
(`detects cancer|diagnoses|diagnosis engine|rules out disease|no MRI needed|
replaces clinician|FDA approved|clinically certified`) returned no matches in
changed files. The bootstrap shell retains the safe disclaimer: "Technical
demo only · Not a diagnosis · Does not replace clinician judgment". No unsafe
clinical/regulatory claims introduced.

## Validation Commands

| Command | Result |
|---|---|
| `git diff --check` | Pass |
| `python -m compileall src/bremen tests` | Pass |
| `pytest tests/test_bremen_report_ui.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_fastapi_auth_enforcement.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_control_room.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_auth.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_workspace_ui.py -q` | Pass (in combined run) |
| `pytest tests/test_bremen_access_logging.py -q` | Pass (in combined run) |
| Combined targeted run | 934 passed |
| `pytest -q` (full suite) | 3675 passed, 11 skipped |
| `! grep auth_ticket=eyJ\|access_token=eyJ\|refresh_token=eyJ` | Pass (no matches) |
| `! grep access_token=\|refresh_token=` in UI/tests | Pass (no matches) |
| `! grep Authorization: Bearer <jwt>` | Pass (no matches) |
| UI copy clinical grep | Pass (no matches) |

## Findings

No blocking findings. The failure analysis is complete and accurate. All
changed files were read. The implementation matches the deployed auth-flow
contract. The full test suite passes. No token leakage or security-boundary
regression was introduced.

## Required Changes

None.

## Warnings

- The `test_report_route_accepts_valid_report_ticket` assertion is limited to
  `resp.status_code != 401`; full report HTML content is covered indirectly via
  `build_report_page` tests in `test_bremen_report_ui.py`. This is pre-existing
  and not a regression introduced by this PR.
- Upstream infrastructure logs (Envoy/App Runner) may require separate
  query-string redaction outside application code; this is outside the scope of
  this branch.

## Final Decision

**APPROVED.** The branch is correct and based on origin/main. The failure
analysis is complete. Tests match the deployed auth-flow contract. Code changes
preserve security boundaries. The full suite passes. No token leakage or unsafe
clinical wording was introduced.
