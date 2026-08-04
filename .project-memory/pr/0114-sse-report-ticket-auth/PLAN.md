# PR0114 — Short-lived ticket-based auth for SSE and report-page navigation

## TASK COMPLETE

Planning for PR0114 is complete. This document specifies the design for a
short-lived, single-purpose ticket mechanism that allows SSE and report-page
navigation to prove authentication without custom Authorization headers,
while preserving the existing access/refresh token security model.

Branch: `0114-sse-report-ticket-auth`
Head: `64bbd6bd8e778ec5e68dea2a8ee3e1778ba35afd`

---

## BLOCKERS

None.

---

## WARNINGS

1. **In-memory ticket state**: This is a single-process demo server. No
   multi-worker or Redis-backed ticket store is needed now. If the server
   migrates to multiple uvicorn workers behind a load balancer, ticket
   validation will still work (stateless JWT), but any future single-use
   tracking would need a shared store. This is acceptable for PR0114 scope.

2. **EventSource reconnect window**: EventSource auto-reconnects with
   `Last-Event-ID`. The 60-second ticket TTL means a reconnect more than
   60 seconds after the initial mint will fail. This is acceptable: the
   SSE stream itself has a 5-minute deadline, and reconnection within a
   single stream session will always be within the ticket TTL. If the
   connection is lost for >60 seconds, the page should refresh and
   re-mint a ticket.

---

## NEW TOKEN TYPE SPECIFICATION

### token_type value

```
stream_ticket
```

This is distinct from the existing `"access"` and `"refresh"` token types.
The `_decode_token` function validates `token_type` against an
`expected_type` parameter, so a stream_ticket cannot be accepted where
an access or refresh token is expected, and vice versa.

### Ticket claims

```python
{
    "sub": "<username>",         # inherited from the access token's sub
    "iat": <issued_at_float>,    # time.time() at mint
    "exp": <expires_at_float>,   # iat + 60
    "token_type": "stream_ticket",
    "jti": "<uuid4>",            # unique ticket ID
    "iss": "<jwt_issuer>",       # config.jwt_issuer (if configured)
    "job_id": "<job_id>",        # bound to a specific analysis job
    "purpose": "<purpose>",      # "stream" or "report"
}
```

### Purpose claim values

| Purpose   | Grants access to                           |
|-----------|--------------------------------------------|
| `stream`  | `GET /demo/api/jobs/{job_id}/events/stream` |
| `report`  | `GET /demo/report/{job_id}`                 |

A ticket minted with `purpose=stream` must be rejected for the report
route, and vice versa. This prevents a ticket obtained for SSE from being
used to navigate to an arbitrary report page or vice versa.

### TTL: 60 seconds

**Justification**:

- The ticket is minted via `_authFetch()` immediately before opening
  EventSource or navigating to the report page. The typical round-trip
  is <2 seconds.
- 60 seconds provides generous margin for slow networks, browser tab
  preloading, and EventSource auto-reconnect attempts within an active
  SSE session.
- 60 seconds is 15x shorter than the 900-second access token TTL,
  limiting the exposure window of a token that appears in URLs.
- The SSE stream itself has a 300-second (5-minute) deadline. Within
  that window, the EventSource reconnection uses `Last-Event-ID` and
  the server still holds the connection open — the ticket is only
  needed for the initial connection handshake. If the browser fully
  disconnects and needs to re-establish, it must re-mint.
- Falls within the required 30–120 second range.

### How ticket type isolation is enforced

`_decode_token(config, token, expected_type)` already validates that
`token_type` in the JWT payload matches `expected_type`. The new
functions will call `_decode_token(config, token, "stream_ticket")`.
Since no access-token or refresh-token code path ever passes
`"stream_ticket"` as `expected_type`, the types are fully isolated.

---

## TICKET-MINTING ENDPOINT SPECIFICATION

### Route

```
POST /demo/api/jobs/{job_id}/auth/ticket
```

### Authentication

Requires a valid Bearer access token in the `Authorization` header,
verified through the existing `_check_auth_gate` dependency.

This is the same gate used by all other protected routes. No weakening.

### Request

```
POST /demo/api/jobs/{job_id}/auth/ticket
Content-Type: application/json
Authorization: Bearer <access_token>

{
    "purpose": "stream"    // or "report"
}
```

Request body fields:

| Field     | Type   | Required | Values                |
|-----------|--------|----------|-----------------------|
| `purpose` | string | yes      | `"stream"` or `"report"` |

Validation:
- `purpose` must be exactly `"stream"` or `"report"`.
- `job_id` must be a non-empty string (already enforced by FastAPI path
  parameter).
- The job must exist in `_jobs` or `_event_store` (same check as other
  job routes). Returns 404 if not found.

### Response — 201 Created

```json
{
    "ticket": "<jwt_string>",
    "expires_in": 60,
    "token_type": "stream_ticket",
    "job_id": "abc-123",
    "purpose": "stream",
    "technical_demo_only": true
}
```

Response fields:

| Field          | Type   | Description                              |
|----------------|--------|------------------------------------------|
| `ticket`       | string | Signed JWT string                        |
| `expires_in`   | int    | 60 (seconds)                             |
| `token_type`   | string | `"stream_ticket"`                        |
| `job_id`       | string | The job ID the ticket is bound to        |
| `purpose`      | string | `"stream"` or `"report"`                 |

### Error responses

| Status | Condition                              | Body                                         |
|--------|----------------------------------------|----------------------------------------------|
| 401    | No Bearer token / invalid access token | `{"error": "Authentication failed", ...}`    |
| 404    | Job not found                          | `{"error": "Job not found", "job_id": ...}`  |
| 400    | Invalid or missing `purpose` field     | `{"error": "Invalid ticket purpose"}`        |
| 503    | Auth disabled                          | `{"error": "Auth disabled", ...}`            |

### Implementation location

New endpoint in `src/bremen/api/fastapi_app.py`, placed immediately
before the SSE route definitions (Phase 4 section).

---

## SSE ROUTE FALLBACK SPECIFICATION

### Current behavior

```
GET /demo/api/jobs/{job_id}/events/stream
```

Currently calls `_check_auth_gate(request)` which requires a valid
Bearer access token. Native EventSource cannot attach headers.

### New behavior

The SSE route will use a new gate function
`_check_auth_gate_with_ticket(request, job_id, purpose)`:

```
1. If auth disabled → pass (unchanged)
2. If Authorization header present:
   a. Try Bearer access token via existing _check_auth_gate logic
   b. If valid → pass
   c. If invalid → fall through to step 3
3. If query parameter `auth_ticket` present:
   a. Decode as token_type "stream_ticket"
   b. Validate job_id claim matches path parameter {job_id}
   c. Validate purpose claim == "stream"
   d. If all valid → pass
   e. If any invalid → 401
4. Otherwise → 401
```

**Critical**: Step 2 is the existing `_check_auth_gate` behavior. It is
not weakened. If a Bearer token is present, it is validated first. The
ticket path is only reached when:
- No Authorization header is present (EventSource case), OR
- Authorization header is present but the access token is invalid/expired
  (rare edge case — `_authFetch` should have refreshed, but defensive)

### Query parameter

| Parameter    | Type   | Description                              |
|--------------|--------|------------------------------------------|
| `auth_ticket`| string | JWT string with token_type=stream_ticket |

### Ticket validation checklist

When `auth_ticket` query parameter is found:

1. Decode JWT with `_decode_token(config, ticket, "stream_ticket")`
2. Check `claims.job_id == job_id` (path parameter)
3. Check `claims.purpose == "stream"`
4. If all pass → continue to SSE handler
5. If any fail → return 401 with safe error shape

### Implementation location

New helper function `_check_auth_gate_with_ticket()` in
`src/bremen/api/fastapi_app.py`. The SSE route handler replaces its
call from `_check_auth_gate(request)` to
`_check_auth_gate_with_ticket(request, job_id, "stream")`.

---

## REPORT ROUTE FALLBACK SPECIFICATION

### Current behavior

```
GET /demo/report/{job_id}
```

Currently calls `_check_auth_gate(request)`. Browser navigation cannot
attach headers.

### New behavior

Same gate function as SSE: `_check_auth_gate_with_ticket(request, job_id, "report")`

```
1. If auth disabled → pass (unchanged)
2. If Authorization header present:
   a. Try Bearer access token
   b. If valid → pass
   c. If invalid → fall through to step 3
3. If query parameter `auth_ticket` present:
   a. Decode as token_type "stream_ticket"
   b. Validate job_id claim matches path parameter {job_id}
   c. Validate purpose claim == "report"
   d. If all valid → pass
   e. If any invalid → 401
4. Otherwise → 401
```

### Query parameter

Same: `auth_ticket`

### Ticket validation checklist

Same as SSE but with `purpose == "report"`.

### Implementation location

The report route handler replaces its call from
`_check_auth_gate(request)` to
`_check_auth_gate_with_ticket(request, job_id, "report")`.

---

## SINGLE-USE DECISION

### Chosen: Short-lived reusable ticket within TTL

### Rationale

1. **SSE reconnection**: EventSource auto-reconnects on network errors.
   During reconnection, the browser may need to re-establish the
   connection. A single-use ticket would make the connection fragile —
   the first transient network error would permanently kill the SSE
   stream. The ticket is the only way to authenticate the reconnection
   since EventSource cannot carry headers.

2. **Browser report page reload**: Users may reload the report page
   (F5/Cmd+R). A single-use ticket would force a new ticket-minting
   round-trip on every reload.

3. **Minimal risk**: The ticket is:
   - Bound to a specific job_id (cannot access other jobs)
   - Bound to a specific purpose (stream cannot access report, and vice
     versa)
   - Valid for only 60 seconds
   - Signed with the same HS256 JWT secret as access/refresh tokens
   - Not usable as an access token (token_type mismatch)
   - Only accepted on two specific routes (SSE and report)

4. **No in-memory tracking complexity**: Single-use tracking requires a
   `set()` of used JTIs, cleanup logic, and concerns about multi-worker
   consistency. For a 60-second demo-server token, this adds fragility
   without meaningful security improvement.

### Security properties preserved

- Ticket cannot be used on any protected route other than the two
  designated fallback routes (token_type check blocks it)
- Ticket cannot access other jobs (job_id claim check)
- Ticket cannot cross purpose boundaries (purpose claim check)
- Ticket expires in 60 seconds (exp claim check)
- Ticket is signed with the same JWT infrastructure (no parallel auth
  system)

---

## CLIENT-SIDE FLOW CHANGES

### Files modified

`src/bremen/control_room_ui.py` — embedded JavaScript in the
`_JS` string constant.

### New helper: `_authFetchTicket(jobId, purpose)`

Add a new JavaScript function that mints a ticket via `_authFetch()`:

```javascript
function _authFetchTicket(jobId, purpose) {
  return _authFetch(baseUrl + '/demo/api/jobs/' + jobId + '/auth/ticket', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({purpose: purpose})
  }).then(function(r) {
    return r.json().then(function(data) {
      if (!r.ok || !data.ticket) {
        throw new Error('ticket_mint_failed');
      }
      return data.ticket;
    });
  });
}
```

Key properties:
- Uses `_authFetch()` which carries the Bearer access token and handles
  refresh-redirect automatically
- Returns a Promise that resolves to the ticket JWT string
- On failure (expired session, network error), `_authFetch` handles
  refresh or redirect to login

### Modified: `connectSSE(jobId)`

**Current** (line 744):
```javascript
function connectSSE(jobId){
  if(eventSource){eventSource.close()}
  eventSource=new EventSource(baseUrl+'/demo/api/jobs/'+jobId+'/events/stream');
  ...
}
```

**New**:
```javascript
function connectSSE(jobId){
  if(eventSource){eventSource.close()}
  _authFetchTicket(jobId, 'stream').then(function(ticket){
    eventSource=new EventSource(
      baseUrl+'/demo/api/jobs/'+jobId+'/events/stream?auth_ticket='+encodeURIComponent(ticket)
    );
    setConnectionState('connecting');
    eventSource.addEventListener('job_event',function(e){
      try{var ev=JSON.parse(e.data);setState('running');processEvent(ev)}catch(ex){}
    });
    eventSource.addEventListener('stream_complete',function(){
      ...  // unchanged
    });
    eventSource.onopen=function(){setConnectionState('live');setState('running')};
    eventSource.onerror=function(){
      ...  // unchanged
    };
  }).catch(function(){
    setConnectionState('disconnected');
    setState('failed');
  });
}
```

Flow:
1. `_authFetchTicket(jobId, 'stream')` — POST with Bearer token
2. Receive ticket JWT string
3. Create `EventSource` with `?auth_ticket=<ticket>` query parameter
4. If ticket minting fails (session expired), `_authFetch` handles
   refresh → redirect to login

### Modified: `openJob(jobId)`

**Current** (line 732):
```javascript
function openJob(jobId){
  window.location.href=baseUrl+'/demo/report/'+jobId;
}
```

**New**:
```javascript
function openJob(jobId){
  _authFetchTicket(jobId, 'report').then(function(ticket){
    window.location.href=baseUrl+'/demo/report/'+jobId+'?auth_ticket='+encodeURIComponent(ticket);
  }).catch(function(){
    // Ticket minting failed — session expired, redirect to login
    _redirectToLogin();
  });
}
```

Flow:
1. `_authFetchTicket(jobId, 'report')` — POST with Bearer token
2. Receive ticket JWT string
3. Navigate to report page with `?auth_ticket=<ticket>` query parameter
4. If ticket minting fails, redirect to login

### Access/refresh token URL safety

Access tokens and refresh tokens are stored in `sessionStorage` and
only transmitted via the `Authorization` header through `_authFetch()`.
They are **never** placed in URLs. The `auth_ticket` query parameter
is the **only** token that appears in a URL, and it is a distinct,
short-lived, purpose-scoped token type.

---

## EVIDENCE-ROUTE SCOPE CONFIRMATION

`/demo/api/evidence` is **explicitly out of scope** for PR0114.

It is a separate compatibility/smoke-test issue. No changes to its
auth behavior are planned or permitted in this PR.

---

## VALIDATION PLAN

### Automated checks (future implementation)

```
git rev-parse --verify HEAD
git branch --show-current
git status --short
python -m compileall src tests
python -m pytest -q tests/test_bremen_auth.py -v
python -m pytest -q tests/test_bremen_fastapi_app.py -v
python -m pytest -q tests/test_bremen_control_room.py -v
python -m pytest -q tests/test_bremen_fastapi_auth_enforcement.py -v
python -m pytest -q
```

### Manual / documented test cases

| # | Test case                                              | Expected |
|---|--------------------------------------------------------|----------|
| 1 | Ticket minted for job A, used on job A SSE route       | 200      |
| 2 | Ticket minted for job A, used on job B SSE route       | 401      |
| 3 | Ticket minted for job A, used on job A report route    | 401 (purpose mismatch: stream ≠ report) |
| 4 | Report ticket used on SSE route                         | 401 (purpose mismatch) |
| 5 | Expired ticket (>60s) used on SSE route                | 401      |
| 6 | Access token used in auth_ticket query param on SSE    | 401 (token_type mismatch) |
| 7 | Refresh token used in auth_ticket query param on SSE   | 401 (token_type mismatch) |
| 8 | stream_ticket used on a non-SSE/report protected route | 401      |
| 9 | Access token via Authorization header on SSE route     | 200 (existing path) |
| 10 | No auth on SSE route (auth enabled)                    | 401      |
| 11 | No auth on report route (auth enabled)                 | 401      |
| 12 | No auth on other protected routes (auth enabled)       | 401 (unchanged) |
| 13 | Auth disabled: SSE route without ticket                | 200      |
| 14 | Auth disabled: report route without ticket             | 200      |
| 15 | connectSSE mints ticket and opens EventSource          | SSE connects |
| 16 | openJob mints ticket and navigates to report           | Page loads |
| 17 | Ticket mint fails (expired session) → redirect login   | Redirect to /demo/login |

---

## NON-GOALS CONFIRMED

The following are explicitly excluded from PR0114:

- No implementation in this planning PR (planning only)
- No change to access token TTL (900s) or refresh token TTL (604800s)
- No change to claims for access or refresh tokens
- No new persistent database or Redis store
- No fix for `/demo/api/evidence`
- No change to `_authFetch` core refresh logic
- No Aramina work
- No backend route broadening beyond the two ticket fallback routes
  (SSE and report)
- No new AuthConfig fields (ticket TTL is hardcoded as a constant
  `_STREAM_TICKET_TTL = 60` in auth.py)
- No changes to public routes (/demo, /demo/login, /health, etc.)
- No changes to non-SSE/report protected routes

---

## STOP CONDITIONS CONFIRMED

All stop conditions have been checked:

| Condition                                         | Status |
|---------------------------------------------------|--------|
| Ticket cannot be confused with access/refresh      | ✅ PASS — token_type="stream_ticket", _decode_token enforces expected_type |
| Ticket is job_id-bound                             | ✅ PASS — job_id claim, validated against path parameter |
| TTL is short and justified                         | ✅ PASS — 60 seconds, justified above |
| Access/refresh tokens never appear in URLs         | ✅ PASS — only auth_ticket in query string |
| Single-use vs reusable resolved                    | ✅ PASS — reusable within 60s TTL |
| Existing protected routes not weakened             | ✅ PASS — _check_auth_gate unchanged; ticket is additive fallback |

---

## NEXT REQUIRED ACTION

Implementation agent: **coder**

### Implementation order

1. **src/bremen/auth.py** — Add `create_stream_ticket(config, claims_sub, job_id, purpose)` and `decode_stream_ticket(config, token, expected_job_id, expected_purpose)` functions. Add `_STREAM_TICKET_TTL = 60` constant. Reuse `_decode_token` with `expected_type="stream_ticket"`.

2. **src/bremen/api/fastapi_app.py** — Add `_check_auth_gate_with_ticket(request, job_id, purpose)` helper. Add `POST /demo/api/jobs/{job_id}/auth/ticket` endpoint. Update `job_events_stream_route` and `demo_report_page` to use the new gate.

3. **src/bremen/control_room_ui.py** — Add `_authFetchTicket()` JS helper. Modify `connectSSE()` and `openJob()` to mint tickets before connection/navigation.

4. **tests/test_bremen_auth.py** — Add tests for `create_stream_ticket`, `decode_stream_ticket`, type isolation, job_id binding, purpose binding, TTL expiry.

5. **tests/test_bremen_fastapi_app.py** — Add tests for the ticket minting endpoint, SSE fallback, report fallback, cross-job rejection, cross-purpose rejection, auth-disabled passthrough.

6. **tests/test_bremen_fastapi_auth_enforcement.py** — Verify existing 25 tests still pass (no regression). Add tests confirming access/refresh tokens rejected where ticket expected, and ticket rejected where access expected.

7. Run full validation suite.

Implementation agent: coder
