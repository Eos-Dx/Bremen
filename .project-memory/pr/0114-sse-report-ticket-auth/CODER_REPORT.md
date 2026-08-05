# CODER REPORT — PR0114 SSE and Report Ticket Auth

## CODER COMPLETE

Yes.

## INCIDENT

Native EventSource and `window.location.href` cannot carry custom Authorization headers. PR0102–PR0113 gated protected routes with Bearer access tokens, but the two browser-based flows (SSE stream and report page navigation) were unable to authenticate. This PR adds short-lived, job-bound ticket JWTs for these two flows.

## IMPLEMENTATION SUMMARY

Added a distinct `stream_ticket` JWT type (60-second TTL, job_id-bound, purpose-bound) that is minted via `_authFetch()` immediately before opening EventSource or navigating to the report page. The server validates the ticket on the two designated fallback routes, preserving the existing Bearer access-token path as the primary gate.

## FILES CREATED

None.

## FILES MODIFIED

| File | Change |
|------|--------|
| `src/bremen/auth.py` | +TicketClaims dataclass, +create_stream_ticket(), +decode_stream_ticket(), +_STREAM_TICKET_TTL=60 constant |
| `src/bremen/api/fastapi_app.py` | +_check_auth_gate_with_ticket() helper, +POST /demo/api/jobs/{job_id}/auth/ticket endpoint, updated SSE stream and report page routes |
| `src/bremen/control_room_ui.py` | +_authFetchTicket() JS helper, updated connectSSE() to mint stream ticket, updated openJob() to mint report ticket |
| `tests/test_bremen_auth.py` | +12 ticket tests (create/decode, type isolation, job_id binding, purpose binding, TTL, error safety) |
| `tests/test_bremen_fastapi_auth_enforcement.py` | +22 ticket tests (mint endpoint, SSE fallback, report fallback, cross-job/purpose rejection, auth-disabled passthrough, other routes reject ticket) |
| `tests/test_bremen_control_room.py` | +11 client-side flow tests (ticket function exists, connectSSE mints ticket, openJob mints ticket, access token never in URL) |

## PLAN REVIEW WARNINGS RESOLVED

1. **tests/test_bremen_fastapi_app.py does not exist** → Mapped all planned ticket tests onto existing `tests/test_bremen_fastapi_auth_enforcement.py` (25 existing + 22 new = 47 total).

2. **TokenClaims has no job_id or purpose fields** → Created a distinct `TicketClaims` frozen dataclass with `sub`, `issued_at`, `expires_at`, `token_type`, `jti`, `job_id`, `purpose`, `iss`. `decode_stream_ticket()` returns `TicketClaims`. Existing `TokenClaims` and access/refresh decode behavior are completely unchanged.

3. **Gate ordering preserved** → `_check_auth_gate_with_ticket()` implements: (1) auth disabled → allow, (2) valid Bearer → allow, (3) invalid Bearer → fall through, (4) valid auth_ticket → allow, (5) otherwise → 401. Bearer is always checked first.

## TOKEN TYPE ISOLATION

- `stream_ticket` is distinct from `access` and `refresh`
- `_decode_token()` validates `token_type` against `expected_type` parameter
- Access/refresh code paths never pass `"stream_ticket"` as expected_type
- `decode_stream_ticket()` never accepts access or refresh tokens
- Ticket rejected where access token expected, and vice versa

## TICKET CLAIMS IMPLEMENTATION

New `TicketClaims` frozen dataclass in `src/bremen/auth.py`:
- `sub: str`, `issued_at: float`, `expires_at: float`, `token_type: str`, `jti: str`, `job_id: str`, `purpose: str`, `iss: str | None`
- Distinct from `TokenClaims` — no shared inheritance, no weakening of existing types
- `decode_stream_ticket()` returns `TicketClaims`

## TICKET MINTING ENDPOINT

`POST /demo/api/jobs/{job_id}/auth/ticket` in `src/bremen/api/fastapi_app.py`:
- Protected by `_check_auth_gate` (same Bearer access token gate as all protected routes)
- Validates purpose is "stream" or "report" (400 for invalid)
- Verifies job exists in `_jobs` or `_event_store` (404 if not found)
- Extracts username from access token claims
- Calls `create_stream_ticket()` with job_id, purpose
- Returns 201 with ticket, expires_in=60, token_type, job_id, purpose

## SSE ROUTE FALLBACK

`GET /demo/api/jobs/{job_id}/events/stream` now uses `_check_auth_gate_with_ticket(request, job_id, "stream")`:
- Bearer access token checked first (primary path)
- `auth_ticket` query parameter checked second (EventSource fallback)
- Ticket validated: token_type=stream_ticket, job_id match, purpose=stream
- Invalid/missing/wrong-purpose ticket → 401

## REPORT ROUTE FALLBACK

`GET /demo/report/{job_id}` now uses `_check_auth_gate_with_ticket(request, job_id, "report")`:
- Same gate pattern as SSE
- Ticket validated: token_type=stream_ticket, job_id match, purpose=report
- Stream-purpose ticket rejected on report route (purpose mismatch)

## CLIENT FLOW CHANGES

### `_authFetchTicket(jobId, purpose)` (new helper)
- Calls `_authFetch()` with POST to `/demo/api/jobs/{jobId}/auth/ticket`
- Returns Promise resolving to ticket JWT string
- On failure, `_authFetch` handles refresh-redirect

### `connectSSE(jobId)` (modified)
- Mints stream ticket via `_authFetchTicket(jobId, 'stream')` before opening EventSource
- Creates EventSource with `?auth_ticket=<encoded_ticket>` query parameter
- On mint failure: sets connection state to 'disconnected', state to 'failed'

### `openJob(jobId)` (modified)
- Mints report ticket via `_authFetchTicket(jobId, 'report')` before navigating
- Navigates to `/demo/report/{jobId}?auth_ticket=<encoded_ticket>`
- On mint failure: calls `_redirectToLogin()`

## TESTS ADDED

### Auth tests (tests/test_bremen_auth.py) — 12 new
- create/decode round-trip with job_id and purpose
- job_id binding (cross-job rejection)
- purpose binding (stream on report, report on stream)
- TTL expiry
- access token rejected as stream_ticket
- refresh token rejected as stream_ticket
- stream_ticket rejected as access/refresh token
- issuer validation
- error message safety
- TicketClaims frozen dataclass

### FastAPI enforcement tests (tests/test_bremen_fastapi_auth_enforcement.py) — 22 new
- Mint endpoint: requires Bearer, rejects ticket auth, valid token → 201, report purpose, invalid/missing purpose → 400, auth-disabled passthrough, job not found → 404
- SSE fallback: valid Bearer, valid stream ticket, rejects report ticket, rejects wrong job, rejects no auth, allows when auth disabled
- Report fallback: valid Bearer, valid report ticket, rejects stream ticket, rejects wrong job, rejects no auth, allows when auth disabled
- Other routes reject ticket (jobs list, h5 containers)

### Control room tests (tests/test_bremen_control_room.py) — 11 new
- _authFetchTicket function exists and uses _authFetch
- connectSSE mints ticket and opens EventSource with auth_ticket
- openJob mints report ticket and navigates with auth_ticket
- Access token never placed in URL
- Auth-disabled SSE passthrough preserved

## VALIDATION RESULTS

```
python -m compileall src tests                   → PASS
python -m pytest tests/test_bremen_auth.py       → 64 passed
python -m pytest tests/test_bremen_fastapi_auth_enforcement.py → 47 passed
python -m pytest tests/test_bremen_control_room.py → 533 passed
python -m pytest (full suite)                     → 3589 passed, 11 skipped, 0 failed
```

## REGRESSION RESULTS

Full suite: 3589 passed, 11 skipped, 0 failed. No regressions.

## SECURITY CONFIRMATION

- Ticket (stream_ticket) is a distinct JWT type from access/refresh
- Ticket has 60-second TTL (15x shorter than 900s access token)
- Ticket is job_id-bound (cannot access other jobs)
- Ticket is purpose-bound (stream cannot access report, vice versa)
- Ticket signed with same HS256 secret (no parallel auth system)
- Access/refresh tokens never appear in URLs (only auth_ticket)
- Ticket only accepted on 2 designated routes (SSE stream + report page)
- Other protected routes still require Bearer access token only
- No secrets, hashes, or internal state leaked in error responses

## OUT OF SCOPE CONFIRMATION

- No changes to access token TTL (900s) or refresh token TTL (604800s)
- No changes to access/refresh TokenClaims shape
- No new persistent database or Redis store
- No changes to `/demo/api/evidence`
- No changes to `_authFetch` core refresh logic
- No Aramina work
- No new AuthConfig fields
- No changes to public routes
- No changes to non-SSE/report protected routes
- No new dependencies added

## WARNINGS

None.

## BLOCKERS

None.

## NEXT REQUIRED ACTION

Implementation is complete. Ready for pre-commit review and merge.
