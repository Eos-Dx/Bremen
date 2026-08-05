# PRECOMMIT REVIEW — PR0114 SSE and Report Ticket Auth

## PRECOMMIT REVIEW COMPLETE

## VERDICT
approved

## READY FOR COMMIT
true

## READY FOR PULL REQUEST
true

## BLOCKERS
None

## WARNINGS
- `on_event('startup')` is deprecated in favor of lifespan event handlers. Non-blocking — existing tests pass.
- The ticket JWT (token_type=stream_ticket) appears in URL query strings (`?auth_ticket=...`). Replay risk is bounded by the 60s TTL, job_id binding, purpose binding, and token_type isolation. Acceptable for the demo scope (documented in PLAN.md).

## CHANGED FILE SCOPE
All changed files are within the allowed scope:
- src/bremen/auth.py
- src/bremen/api/fastapi_app.py
- src/bremen/control_room_ui.py
- tests/test_bremen_auth.py
- tests/test_bremen_control_room.py
- tests/test_bremen_fastapi_auth_enforcement.py
- .project-memory/pr/0114-sse-report-ticket-auth/CODER_REPORT.md (untracked)

No unrelated files changed. No docs/deployment/config changed.

## PLAN REVIEW WARNINGS REVIEW
1. **tests/test_bremen_fastapi_app.py does not exist** → RESOLVED. Coder mapped all planned ticket tests onto the existing `tests/test_bremen_fastapi_auth_enforcement.py` (25 existing + 22 new = 47 total). Verified: file does not exist, but all planned ticket tests are present in auth_enforcement.py.
2. **TokenClaims job_id/purpose issue** → RESOLVED. Coder created a distinct `TicketClaims` frozen dataclass with `sub`, `issued_at`, `expires_at`, `token_type`, `jti`, `job_id`, `purpose`, `iss`. `decode_stream_ticket()` returns `TicketClaims`. Existing `TokenClaims` and access/refresh decode behavior are completely unchanged.
3. **Gate ordering** → PRESERVED. `_check_auth_gate_with_ticket()` implements: (1) auth disabled → allow, (2) valid Bearer → allow, (3) invalid Bearer → fall through, (4) valid auth_ticket → allow, (5) otherwise → 401. Bearer is always checked first.

## TOKEN TYPE REVIEW
- `stream_ticket` is distinct from `access` and `refresh` (verified in auth.py `_STREAM_TICKET_TYPE = "stream_ticket"`).
- `_decode_token()` validates `token_type` against `expected_type` parameter.
- Access token cannot be decoded as stream ticket (tested: `test_access_token_rejected_as_stream_ticket`).
- Refresh token cannot be decoded as stream ticket (tested: `test_refresh_token_rejected_as_stream_ticket`).
- Stream ticket cannot be decoded as access token (tested: `test_stream_ticket_rejected_as_access_token`).
- Stream ticket cannot be decoded as refresh token (tested: `test_stream_ticket_rejected_as_refresh_token`).
- Ticket cannot mint another ticket (mint endpoint requires valid Bearer access token via `_check_auth_gate`; ticket rejected as auth — tested: `test_mint_endpoint_rejects_ticket_auth`).

## TICKET CLAIMS REVIEW
Ticket claims include: `sub`, `iat`, `exp`, `token_type`, `jti`, `job_id`, `purpose`, `iss` (if configured). Verified in `create_stream_ticket()`.
- TTL is 60 seconds (`_STREAM_TICKET_TTL = 60`).
- Purpose is controlled to `stream` or `report` (`_VALID_PURPOSES = frozenset({"stream", "report"})`).
- job_id and purpose are enforced server-side in `decode_stream_ticket()` (validates `payload.get("job_id") == expected_job_id` and `payload.get("purpose") == expected_purpose`).

## TICKET MINTING ENDPOINT REVIEW
`POST /demo/api/jobs/{job_id}/auth/ticket`:
- Requires valid real Bearer access token via `_check_auth_gate` (tested: `test_mint_endpoint_requires_bearer`).
- Rejects missing/invalid/ticket auth (tested: `test_mint_endpoint_rejects_ticket_auth`).
- Mints ticket only for requested job_id and purpose (validates purpose is "stream" or "report", verifies job exists → 404 if not found).
- Returns no access/refresh token (response contains only ticket, expires_in, token_type, job_id, purpose, technical_demo_only).
- Returns ticket, expires_in=60, token_type=stream_ticket, job_id, purpose (tested: `test_mint_endpoint_valid_token`).

## SSE FALLBACK REVIEW
`GET /demo/api/jobs/{job_id}/events/stream` uses `_check_auth_gate_with_ticket(request, job_id, "stream")`:
- Accepts valid Bearer access token (tested: `test_stream_route_accepts_valid_bearer`).
- Accepts valid auth_ticket with purpose=stream and matching job_id (tested: `test_stream_route_accepts_valid_stream_ticket`).
- Rejects missing auth (tested: `test_stream_route_rejects_no_auth`).
- Rejects expired ticket (tested in auth.py: `test_expired_ticket_rejected`).
- Rejects wrong job_id (tested: `test_stream_route_rejects_wrong_job_ticket`).
- Rejects wrong purpose (tested: `test_stream_route_rejects_report_ticket`).
- Rejects access/refresh token in auth_ticket (tested in auth.py: `test_access_token_rejected_as_stream_ticket`, `test_refresh_token_rejected_as_stream_ticket`).

## REPORT FALLBACK REVIEW
`GET /demo/report/{job_id}` uses `_check_auth_gate_with_ticket(request, job_id, "report")`:
- Accepts valid Bearer access token (tested: `test_report_route_accepts_valid_bearer`).
- Accepts valid auth_ticket with purpose=report and matching job_id (tested: `test_report_route_accepts_valid_report_ticket`).
- Rejects missing auth (tested: `test_report_route_rejects_no_auth`).
- Rejects expired ticket (tested in auth.py).
- Rejects wrong job_id (tested: `test_report_route_rejects_wrong_job_ticket`).
- Rejects wrong purpose (tested: `test_report_route_rejects_stream_ticket`).
- Rejects stream ticket for report (tested: `test_report_route_rejects_stream_ticket`).

## OTHER ROUTE REGRESSION REVIEW
Other protected routes do NOT accept auth_ticket as substitute for Bearer access token. Verified:
- All other protected routes still use `_check_auth_gate(request)` (Bearer only).
- Tested: `test_jobs_list_rejects_ticket`, `test_h5_containers_rejects_ticket` (both return 401 with auth_ticket).

## CLIENT REVIEW
- `connectSSE()`: mints stream ticket through `_authFetchTicket(jobId, 'stream')` (which uses `_authFetch()`), uses EventSource URL with `?auth_ticket=`, does not place access/refresh token in URL. On mint failure, sets connection state to 'disconnected' and state to 'failed'.
- `openJob()`: mints report ticket through `_authFetchTicket(jobId, 'report')`, navigates with `?auth_ticket=` only, does not place access/refresh token in URL. On mint failure, calls `_redirectToLogin()`.
- `_authFetchTicket()` uses `_authFetch()` which carries the Bearer access token and handles refresh-redirect automatically.
- Access/refresh tokens never appear in URLs (only `auth_ticket`).

## SECURITY REVIEW
- Access/refresh tokens stored in sessionStorage, transmitted only via Authorization header through `_authFetch()`, never in URLs.
- Only `auth_ticket` (stream_ticket JWT) appears in query strings.
- No hardcoded secrets.
- No unsafe DOM changes.
- No broadening of unauthenticated access (only 2 designated routes gain ticket fallback).
- `/demo/api/evidence` is out of scope and unchanged.

## VALIDATION RESULTS
- compileall: passed
- tests/test_bremen_auth.py: 64 passed
- tests/test_bremen_fastapi_auth_enforcement.py: 47 passed
- tests/test_bremen_control_room.py: 533 passed
- Full suite: 3589 passed, 11 skipped, 0 failed
- git diff --check: clean

## REGRESSION RESULTS
Full suite: 3589 passed, 11 skipped, 0 failed. No regressions.

## REQUIRED CORRECTIONS
None

## FINAL SUMMARY
PR0114 safely implements short-lived ticket auth for native EventSource and report-page navigation. The `stream_ticket` JWT type is distinct from access/refresh, has a 60-second TTL, is job_id-bound and purpose-bound, and is only accepted on the two designated fallback routes (SSE stream and report page). The mint endpoint requires a valid Bearer access token. Access/refresh tokens never appear in URLs. All planned tests and regressions pass. Approved.
