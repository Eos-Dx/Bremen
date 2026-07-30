# PR0104D — FastAPI Phase 4 Event Streaming / Job Events Migration (PLAN ONLY)

**Status**: Planning Only — Do Not Implement

---

## 1. Scope

PR0104D is a **plan-only** PR. It plans the migration of job event streaming / live events from the http.server path to the isolated FastAPI app.

The future implementation will be a separate PR, likely:

> **0104e-fastapi-phase4-event-streaming**

**Branch**: `0104d-plan-fastapi-phase4-event-streaming`  
**Base branch**: `dev`  
**PR target**: `dev`  
**`main` is not touched.** The production demo (`main` branch) and production http.server path remain fully protected.

---

## 2. Current Route Inventory

### 2.1 Event Routes Identified

The http.server dispatcher in `server.py:_handle_demo_jobs_route()` (server.py:1791) delegates to handlers in `job_api_handler.py` for the following sub-routes:

| # | Path | Method | Handler in job_api_handler.py | Content-Type | Type |
|---|---|---|---|---|---|
| 1 | `/demo/api/jobs/{job_id}/events` | GET | `handle_job_events()` (line 1088) | `application/json` | **JSON polling** |
| 2 | `/demo/api/jobs/{job_id}/events/stream` | GET | `handle_job_events_stream()` (line 1104) | `text/event-stream` | **SSE streaming** |

### 2.2 Route Detail: `GET /demo/api/jobs/{job_id}/events`

**Path pattern**: `/demo/api/jobs/{job_id}/events`  
**Method**: GET  
**Content-Type**: `application/json`  
**Response shape** (200):
```json
{
  "events": [ ... ],
  "cursor": 42,
  "job_id": "uuid-...",
  "request_id": "uuid-...",
  "technical_demo_only": true
}
```

**Behavior**:
- Checks `_event_store.has_job(job_id)` — returns 404 `{"error": "Job not found", "job_id": job_id}` if unknown.
- Reads `X-Event-Cursor` header for `since_sequence` (default 0).
- Calls `get_job_events(job_id, since_sequence)` → `_event_store.get_events(job_id, since_sequence)`.
- Returns events list, current cursor, and job_id.
- Error safety: no raw exceptions exposed; 404 is the only error case (canonical).

### 2.3 Route Detail: `GET /demo/api/jobs/{job_id}/events/stream`

**Path pattern**: `/demo/api/jobs/{job_id}/events/stream`  
**Method**: GET  
**Content-Type**: `text/event-stream`  
**Cache-Control**: `no-cache`  
**Connection**: `keep-alive`  

**SSE protocol**:
- **Event type**: `job_event` — contains JSON event data
- **Event type**: `stream_complete` — signals end of stream
- **Event ID**: sequence number (for `Last-Event-ID` reconnect)
- **Heartbeat**: `: keepalive\n\n` (comment frame) every 15 seconds if idle
- **Deadline**: 300 seconds (5 minutes max stream duration)

**Behavior**:
1. Check `_event_store.has_job(job_id)` — return 404 if unknown
2. Read `Last-Event-ID` header for initial cursor
3. Set response headers: 200, `text/event-stream`, `no-cache`, `keep-alive`
4. Send any buffered events since cursor
5. Loop:
   - Check job terminal status under `_jobs_lock`:
     - If `completed`, `failed`, `partial_success`, or `workflow_configuration_required`: drain remaining events, send `stream_complete`, break
   - Call `_event_store.wait_for_events(job_id, cursor, timeout=15.0)` — blocks on `threading.Condition`
   - If events returned: send them as SSE frames, advance cursor
   - If timeout: send `: keepalive\n\n` heartbeat
   - If write error (BrokenPipeError, ConnectionResetError): break
6. Max duration: 300 seconds (deadline check each loop iteration)

**Error safety**:
- 404 for unknown job_id (JSON body, not SSE)
- Stream silently ends on client disconnect (catch BrokenPipeError/ConnectionResetError)
- No raw exceptions in SSE data
- No raw S3, filesystem paths, or model internals in event data (governed by `event_schema.py` prohibited key list)

### 2.4 How job_id Is Parsed

In `_handle_demo_jobs_route()` (server.py:1792):
```python
route_path = _urlsplit(handler.path).path
m = _re.match(r"^/demo/api/jobs/([^/]+)/events/stream$", route_path)
```
The job_id is captured as `m.group(1)` — the first path segment after `/demo/api/jobs/`.

### 2.5 Missing/Unknown job_id Behavior

- `handle_job_events`: returns HTTP 404 JSON `{"error": "Job not found", "job_id": job_id}`
- `handle_job_events_stream`: returns HTTP 404 JSON `{"error": "Job not found"}`

Both check `_event_store.has_job(job_id)` which returns `True` only if events were explicitly stored for that job_id via `_event_store.append()`.

### 2.6 Terminal States

Terminal states checked in the SSE loop (server.py:1104 `handle_job_events_stream`):
- `"completed"`
- `"failed"`
- `"partial_success"`
- `"workflow_configuration_required"`

When terminal: remaining events are drained and `event: stream_complete` is sent.

### 2.7 Error Safety

- 404 JSON body (not SSE) for unknown job
- Stream silently closes on write errors (client disconnect)
- Event details are governed by `_PROHIBITED_DETAIL_KEYS` in `event_schema.py` — fail-fast on append
- No tracebacks, paths, PHI, credentials, model internals, or full checksums

---

## 3. Event Source of Truth

### 3.1 Event Store

**Module**: `src/bremen/api/event_store.py`  
**Class**: `BoundedEventStore`  
**Identity**: Singleton stored on the `bremen` package via `_get_or_create_store()` in `job_api_handler.py`  
**Key**: `bremen._bremen_workspace_event_store`  
**Module-level reference**: `job_api_handler._event_store`

### 3.2 Event Schema

**Module**: `src/bremen/api/event_schema.py`  
**Class**: `JobEvent` (frozen dataclass)  
**Fields**: `schema_version`, `event_id`, `sequence`, `timestamp`, `job_id`, `request_id`, `workflow_id`, `stage`, `event_type`, `status`, `duration_ms`, `details`  
**Serialization**: `to_dict()` method  
**Validation**: `validate_event_details()` rejects prohibited keys (PHI, paths, coefficients, raw data, etc.)

### 3.3 Event Lifecycle

**Append path**: Events are appended by `create_analysis_job()` and the workflow orchestrator (`run_workflow_request`) which calls `_event_store.append(job_id, event)`.

**Read path**: `handle_job_events()` and `handle_job_events_stream()` both call `_event_store.get_events(job_id, since_sequence=0)`.

**How events are appended**: 
1. `create_analysis_job()` in `job_api_handler.py` creates the job, then calls `run_workflow_request()` with `event_store=_event_store`.
2. The orchestrator emits structured `JobEvent` objects at each lifecycle stage (artifact verification, model loading, feature extraction, inference, decision, report).
3. After orchestrator returns, `create_analysis_job()` may emit additional events (e.g., `runtime.report.completed`).

**How ordering is preserved**: Each event gets a monotonic `sequence` number via `_JobBucket.append()` using an auto-incrementing counter. Events are stored in insertion order in a `list[JobEvent]`.

**How terminal events are identified**: The SSE handler checks `_jobs.get(job_id).overall_status` which is set to `"completed"`, `"failed"`, `"partial_success"`, or `"workflow_configuration_required"` by `create_analysis_job()`.

### 3.4 Job Store Integration

**Module**: `job_api_handler._jobs` — singleton dict stored under `bremen._bremen_workspace_jobs`  
**Key**: `job_id` (UUID string) → `AnalysisJob` object  
**Lock**: `job_api_handler._jobs_lock` — protects concurrent reads/writes

The `_event_store` (BoundedEventStore) and `_jobs` dict are separate. Events are in the event store; job status (including terminal state) is in the `_jobs` dict. The SSE handler reads both: events from `_event_store`, terminal status from `_jobs`.

### 3.5 Execution Trace Integration

`execution_trace.py` provides `build_trace_from_events(store, job_id, workflow_id)` which reads events from the event store and projects an `ExecutionTraceSummary`. This is a read-only projection — it does not store state.

### 3.6 Module-Reload Safety

All shared state (`_event_store`, `_jobs`, `_report_providers`, `_staged_uploads`, locks) is stored on the `bremen` package (not module-level) via `_get_or_create_store()`, `_get_or_create_jobs()`, etc. This ensures state survives `bremen.api.*` module reload.

---

## 4. job_id Reconciliation Plan

### 4.1 Current Flow

1. **job_id generation**: `create_analysis_job()` generates `job_id = str(uuid.uuid4())`
2. **job_id returned to client**: Via `POST /demo/api/jobs` response → `{"job": {"job_id": "uuid-..."}, "storage_mode": "ephemeral"}`
3. **job_id used by event route**: Same UUID used as path parameter in `GET /demo/api/jobs/{job_id}/events` and `GET /demo/api/jobs/{job_id}/events/stream`
4. **job_id displayed in Control Room**: From `list_analysis_jobs()` → `summary["job_id"]` → rendered as secondary metadata (first 8 chars)
5. **job_id in reports**: Stored in `job.job_id` and accessible from `get_job_report()` response

### 4.2 Phase 4 Consistency

The FastAPI `POST /demo/api/jobs` (Phase 3) already calls the same `create_analysis_job()` function which writes to the same singleton `_event_store` and `_jobs` dict. This means:

- **Same event_store**: FastAPI-created jobs write events to the same `_event_store` that the http.server SSE handler reads from.
- **Same _jobs dict**: FastAPI-created jobs are stored in the same `_jobs` dict.
- **Same job_id**: Both routes use the same UUID generation from `create_analysis_job()`.

**Implication for Phase 4**: The FastAPI event routes can directly read from the existing `_event_store` and `_jobs` singletons. **No reconciliation gap exists.** The job_id created via FastAPI POST is immediately visible to both http.server SSE and future FastAPI SSE routes.

### 4.3 Behavior Matrix

| Scenario | FastAPI GET /jobs/{id}/events | http.server GET /jobs/{id}/events |
|---|---|---|
| Known job_id | Returns events | Returns events |
| Unknown job_id | 404 "Job not found" | 404 "Job not found" |
| Stale job_id (evicted from event_store) | 404 | 404 |
| Completed job | Returns all events + terminal state from _jobs | Returns all events + terminal state |
| Failed job | Returns events up to failure | Returns events up to failure |
| Deleted report | Job still exists, events available | Job still exists, events available |

**Blocker condition**: Implementation must stop if the same `_event_store` and `_jobs` singletons cannot be imported and shared. See stop conditions.

---

## 5. Status Vocabulary Plan

### 5.1 Job Status Strings

| Status | Set by | Terminal? | Notes |
|---|---|---|---|
| `"running"` | `create_analysis_job()` | No | Initial state when job is created |
| `"completed"` | `create_analysis_job()` | Yes | All workflow stages completed successfully |
| `"failed"` | `create_analysis_job()` | Yes | Workflow execution failed |
| `"partial_success"` | (referenced in SSE handler) | Yes | Defined but not explicitly set in job creation |
| `"workflow_configuration_required"` | (referenced in SSE handler) | Yes | Workflow could not execute due to configuration gap |
| `"normalization_failed"` | `create_analysis_job()` | Yes | Normalization step failed before workflow execution |

### 5.2 Event Type Strings

From `event_schema.py` `EventType` enum (28 event types):

**Request lifecycle**:
- `runtime.request.accepted`
- `runtime.input.staging.started` / `.completed`
- `runtime.normalization.started` / `.completed` / `.failed`
- `runtime.workflow.resolved` / `.started` / `.not_found`
- `runtime.workflow.completed` / `.failed`
- `runtime.request.completed`

**Model/artifact lifecycle**:
- `runtime.model.load.started` / `.completed`
- `runtime.model.validation.started` / `.completed` / `.failed`
- `runtime.artifact.verification.started` / `.completed` / `.failed`
- `runtime.artifact.load.started` / `.completed` / `.failed`
- `runtime.artifact.adaptation.started` / `.completed` / `.failed`

**Feature lifecycle**:
- `runtime.features.started` / `.completed` / `.failed`
- `runtime.input.preparation.started` / `.completed` / `.failed`
- `runtime.features.validation.started` / `.completed` / `.failed`

**Inference/decision lifecycle**:
- `runtime.inference.started` / `.completed` / `.failed`
- `runtime.decision.started` / `.completed` / `.failed`
- `runtime.output.validation.started` / `.completed` / `.failed`

**Report lifecycle**:
- `runtime.report.started` / `.completed` / `.failed`
- `runtime.report.unavailable`

**Other**:
- `runtime.stage.skipped`

### 5.3 Mapping from Internal to Public SSE Output

**The mapping is already 1:1**. The SSE stream emits `JobEvent.to_dict()` directly as the `data:` field of each SSE event. No additional transformation is needed:

```
event: job_event
id: 5
data: {"schema_version": "1", "event_id": "...", "sequence": 5, ...}
```

**No new status strings should be invented.** The existing status vocabulary (EventType enum + overall_status strings) is exhaustive and tested by 15-stage Control Room pipeline tests.

---

## 6. Stage Completeness Plan

### 6.1 15-Stage Control Room Pipeline

The Control Room UI and execution trace (`execution_trace.py`) define 11 canonical Bremen stages in `BREMEN_STAGE_ORDER` (from `runtime_plugin.py`):

1. `artifact_verification`
2. `artifact_loaded`
3. `artifact_adapted`
4. `model_validated`
5. `input_prepared`
6. `features_produced`
7. `features_validated`
8. `inference_completed`
9. `output_validated`
10. `decision_completed`
11. `report_completed`

Plus 4 additional Control Room display stages (pre/staging and post/completion), making 15 total.

### 6.2 Event Ordering

Events are stored in insertion order in `_event_store` with monotonic `sequence` numbers. Both the SSE stream and the JSON polling endpoint return events in sequence order. The "execution trace" projection (`build_trace_from_events`) reorders events by `_STAGE_EVENT_MAP` against `BREMEN_STAGE_ORDER`.

**Phase 4 must preserve**: 
- Events returned in sequence order (already guaranteed by `_event_store.get_events()`)
- Trace projection reads from same event store (no change needed)

### 6.3 Missing Stage Handling

`build_trace_from_events()` handles missing events gracefully — any stage without a corresponding completion event shows as `"not_started"`.

### 6.4 Duplicate Event Handling

The event store does not deduplicate — duplicate calls to `_event_store.append()` create multiple entries with sequential sequence numbers. The SSE handler sends all events since cursor.

### 6.5 Terminal Success Behavior

When job.overall_status == `"completed"`:
1. All remaining events are drained from the event store
2. `event: stream_complete` is sent
3. SSE handler breaks out of the loop

### 6.6 Terminal Failure Behavior

When job.overall_status == `"failed"` or `"normalization_failed"`:
1. Remaining events up to failure point are drained
2. `event: stream_complete` is sent
3. No false `runtime.workflow.completed` or `runtime.request.completed` events are emitted

### 6.7 Failure Precedence

Failure is terminal and takes precedence over any subsequent events. The SSE handler checks `_jobs.get(job_id).overall_status` before waiting for new events.

### 6.8 Live Event Completeness

The SSE stream delivers all events from the event store. The `wait_for_events()` mechanism with `threading.Condition` ensures sub-second delivery of new events (verified by existing `test_new_event_notified_quickly`).

---

## 7. Streaming Design Options

### Option A: FastAPI StreamingResponse SSE (RECOMMENDED)

**How**: Use `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"` backed by the existing `_event_store`.

**Implementation approach**:

```python
from fastapi.responses import StreamingResponse
from bremen.api.job_api_handler import _event_store, _jobs, _jobs_lock

@app.get("/demo/api/jobs/{job_id}/events/stream")
async def job_events_stream(job_id: str, request: Request):
    if not _event_store.has_job(job_id):
        return JSONResponse(content={"error": "Job not found"}, status_code=404)

    async def event_generator():
        cursor = int(request.headers.get("last-event-id", "0"))
        deadline = time.monotonic() + 300
        heartbeat_interval = 15.0

        # Send buffered events
        yield from _format_sse_events(_event_store, job_id, cursor)
        cursor = _event_store.get_job_cursor(job_id)

        while time.monotonic() < deadline:
            # Check terminal
            with _jobs_lock:
                job = _jobs.get(job_id)
            if job and job.overall_status in TERMINAL_STATUSES:
                yield from _format_sse_events(_event_store, job_id, cursor)
                yield f"event: stream_complete\ndata: {json.dumps({'cursor': cursor})}\n\n"
                return

            # Block on store (use run_in_executor to avoid blocking event loop)
            loop = asyncio.get_event_loop()
            new_events = await loop.run_in_executor(
                None, _event_store.wait_for_events, job_id, cursor, heartbeat_interval
            )

            if new_events:
                yield from _format_sse_events_from_list(new_events)
                cursor = _event_store.get_job_cursor(job_id)
            else:
                yield ": keepalive\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Request-ID": ...})
```

**Benefits**:
- True SSE with EventSource-compatible protocol
- Reuses existing `_event_store` singleton directly
- Reuses existing terminal-status check pattern from http.server handler
- Backward compatible with existing Control Room EventSource frontend code
- Testable via `TestClient` (with streaming support) or direct unit tests on the generator

**Risks**:
- `_event_store.wait_for_events()` is synchronous (blocks on `threading.Condition`) — must use `run_in_executor` to avoid blocking the FastAPI async event loop
- ASGI `StreamingResponse` cancellation on disconnect is less reliable than http.server's write-error detection
- SSE timeout/deadline management must be explicit (the generator must end)
- `run_in_executor` standard thread pool may be exhausted by many concurrent SSE connections
- Cannot use `TestClient` for true SSE streaming in starlette (TestClient blocks on response)

**Event_store compatibility**: 100% — same singleton, same `wait_for_events()`, same `get_events()`, same `get_job_cursor()`.

**Testability**: Good for unit tests (direct generator iteration), limited for integration tests (need real server for SSE streaming).

**Client disconnect behavior**: FastAPI detects disconnect as `await request.is_disconnected()` or by catching `RuntimeError` on generator `yield` after disconnect.

**Effect on future Control Room cutover**: No change needed — Control Room already uses EventSource-compatible SSE. Same protocol, same endpoint path.

### Option B: FastAPI JSON Polling Endpoint

**How**: Implement a FastAPI JSON endpoint matching the existing `/demo/api/jobs/{job_id}/events` but with long-polling semantics.

**Benefits**:
- Simple request/response — no streaming complexity
- Fully testable with TestClient (no real server needed)
- No `run_in_executor` requirement
- No ASGI disconnect handling complexity

**Risks**:
- Does not replace SSE — Control Room would still connect to http.server SSE endpoint
- Long-polling has different latency characteristics
- Would not enable eventual http.server SSE decommission
- Increases test burden (need to maintain both polling and SSE paths)

**Event_store compatibility**: 100%

**Testability**: Excellent — TestClient works directly.

**Client disconnect behavior**: Standard — client disconnects before response returns.

**Effect on future Control Room cutover**: Delays cutover — Control Room would remain on http.server SSE.

### Decision: Option A — FastAPI StreamingResponse SSE

**Rationale**:
1. The existing production path is **true SSE** (`text/event-stream`), not polling. A streaming migration must deliver SSE.
2. The `BoundedEventStore` is designed for SSE with `wait_for_events()` and `threading.Condition`.
3. The `run_in_executor` risk is manageable — SSE connections in demo use (2–5 concurrent) are well within standard thread pool limits.
4. Full SSE parity enables eventual http.server event route decommission.
5. The FastAPI `POST /demo/api/jobs` (Phase 3) already writes to the same `_event_store`, so FastAPI SSE will immediately receive events from FastAPI-created jobs.

---

## 8. Client Disconnect / Heartbeat Plan

### 8.1 Client Disconnect

In the `async def event_generator()`:
- Use `try/except` around `yield` to catch `RuntimeError` on client disconnect (ASGI send to closed connection).
- Optionally check `await request.is_disconnected()` periodically.
- On disconnect: clean up (break from loop, close any resources), generator ends.

### 8.2 Generator Cancellation

- The generator should use a `try/finally` block for cleanup.
- No background tasks leak — the generator is the only resource holder.

### 8.3 Heartbeat

- Same as http.server: send `: keepalive\n\n` after `wait_for_events` timeout (15 seconds).
- No need for separate heartbeat timer — the timeout parameter of `wait_for_events` serves double duty as heartbeat interval.

### 8.4 Timeout

- Same as http.server: 300-second deadline from first connection.
- Track `deadline = time.monotonic() + 300` at generator start.
- Check each loop iteration before `wait_for_events`.

### 8.5 Terminal Stream Close

- When `_jobs[job_id].overall_status` is terminal: drain remaining events, send `event: stream_complete`, end generator.
- Client receives `stream_complete` event and can close EventSource.

### 8.6 Background Task Leak Prevention

- The SSE generator is the only task created per connection.
- No `BackgroundTasks` or separate asyncio tasks.
- On disconnect or completion, the generator ends and ASGI cleans up.
- `run_in_executor` thread returns when `wait_for_events` returns — no persistent thread.

---

## 9. Safety Boundary

Event streaming must preserve the same safety invariants as the existing http.server path:

- **No raw S3 bucket names** in event details
- **No raw S3 object keys** in event details
- **No filesystem paths** (`/tmp/...`, `/app/...`) in event details
- **No H5 internals** (dataset paths, group names, attributes)
- **No feature values** or model coefficients
- **No full checksums** (partial/safe display only)
- **No package internals** (`_package`, `_checksum`, `_model`)
- **No credentials** (AWS keys, JWT tokens)
- **No JWT secrets or env values**
- **No raw exception traces** (stack frames, file paths, line numbers)
- **No PHI/private data** beyond existing safe display names (`patient_display_name`, `source_id`, `display_name`)

**Enforcement**: The existing `event_schema.py` `_PROHIBITED_DETAIL_KEYS` set and `validate_event_details()` function already enforce this at event append time. The same `JobEvent` objects flow through the FastAPI route unchanged.

---

## 10. Auth Boundary

### 10.1 Current State

The existing http.server SSE route (`GET /demo/api/jobs/{job_id}/events/stream`) does **not** apply auth gates. It is a demo-only endpoint accessible without authentication.

The existing http.server event polling route (`GET /demo/api/jobs/{job_id}/events`) also does **not** apply auth gates.

Auth is only applied to `POST /demo/api/auth/token` and `POST /demo/api/auth/refresh`.

### 10.2 Phase 4 Decision

**No auth gates on event routes in Phase 4.** The Phase 4 SSE and event routes will maintain the same access model as the existing http.server event routes — no authentication required.

**Rationale**:
- Auth redesign is explicitly a non-goal for all FastAPI migration phases.
- Adding auth to event routes would change behavior vs the existing http.server path.
- Auth integration is a future standalone PR (after all migration phases are complete).
- Do not expand or contract visibility in this phase.

---

## 11. Test Strategy

### 11.1 Test File

New file: `tests/test_bremen_fastapi_phase4_event_stream.py`

### 11.2 FastAPI TestClient Tests (Unit-Level)

These tests verify route existence, response shapes, error states, and safety — without spawning a real server:

| Test | Purpose |
|------|---------|
| `test_events_route_exists` | `GET /demo/api/jobs/{id}/events` returns 200 or 404 |
| `test_events_unknown_job_id` | Unknown job_id returns 404 JSON body |
| `test_events_known_job_id` | Job with events returns events list |
| `test_events_empty_job` | Job with no events returns empty events list |
| `test_events_cursor_header` | X-Event-Cursor filters events |
| `test_events_ordered` | Events returned in sequence order |
| `test_events_safe_output` | No prohibited fields in event data |

### 11.3 Generator Unit Tests (SSE)

These tests directly iterate the SSE event generator (without TestClient):

| Test | Purpose |
|------|---------|
| `test_sse_generator_yields_events` | Generator yields event frames for known job |
| `test_sse_generator_empty` | Generator yields no events for empty job |
| `test_sse_generator_heartbeat` | Generator yields heartbeat on idle timeout |
| `test_sse_generator_stream_complete` | Generator yields `stream_complete` on terminal |
| `test_sse_generator_disconnect` | Generator stops cleanly on simulated disconnect |
| `test_sse_generator_deadline` | Generator stops after deadline |
| `test_sse_event_format` | SSE frames match `event: job_event\ndata: {...}\n\n` format |
| `test_sse_no_raw_internals` | No prohibited fields in SSE data content |

### 11.4 Event Store Parity Tests

| Test | Purpose |
|------|---------|
| `test_event_store_shared_singleton` | Same `_event_store` object used by both http.server and FastAPI |
| `test_events_from_fastapi_job_visible_to_http` | Events from FastAPI-created job visible to http.server event route |
| `test_events_survive_module_reload` | Events survive module reload (uses package-level store) |

### 11.5 Termination / Stage Completeness Tests

| Test | Purpose |
|------|---------|
| `test_terminal_completed` | Completed job returns stream_complete |
| `test_terminal_failed` | Failed job returns stream_complete |
| `test_terminal_unknown_status` | Unknown terminal status behavior |
| `test_failure_precedence` | Failure prevents false completion events |
| `test_duplicate_events_handling` | Duplicate events both appear in order |

### 11.6 Existing Tests Must Still Pass

```bash
python -m pytest -q tests/test_bremen_fastapi_phase1.py -v
python -m pytest -q tests/test_bremen_fastapi_phase2_catalog.py -v
python -m pytest -q tests/test_bremen_fastapi_phase3_write_routes.py -v
python -m pytest -q tests/test_bremen_api_server.py -v
python -m pytest -q tests/test_bremen_concurrent_server.py -v
```

### 11.7 No Server-Spawning Tests

All Phase 4 event streaming tests must be:
- FastAPI TestClient (for route existence, error states, JSON responses)
- Direct generator iteration (for SSE content, heartbeats, disconnect, terminal)
- Direct function calls (for event store sharing, singleton identity)

No test may start a real TCP/HTTP server.

---

## 12. Production Path Protection

- **No Dockerfile changes.** The production Dockerfile (`FROM`, `ENTRYPOINT`, `CMD`) remains untouched.
- **No production ENTRYPOINT/CMD change.** The existing `ENTRYPOINT ["python", "-m", "bremen"]` and `CMD ["serve", ...]` are unchanged.
- **Existing http.server path remains active.** Phase 4 migration does NOT remove or replace the http.server event routes. Both paths coexist.
- **No main branch merge.** All FastAPI work remains on `dev`.
- **No Control Room UI changes in this planning PR.** The Control Room continues to use http.server SSE until a future explicit cutover plan.
- **Future implementation remains isolated** until a later explicit cutover plan.

---

## 13. Non-Goals

- ❌ No implementation in this PR (planning only).
- ❌ No Control Room UI changes.
- ❌ No production cutover (http.server SSE remains active).
- ❌ No Dockerfile changes.
- ❌ No auth redesign (event routes remain unauthenticated).
- ❌ No model/training changes.
- ❌ No report route migration.
- ❌ No POST /demo/api/stage migration.
- ❌ No POST /demo/api/h5/analyze migration.
- ❌ No main branch target.
- ❌ No server-spawning tests.
- ❌ No new status strings or event types.
- ❌ No change to event schema.
- ❌ No change to event store implementation.
- ❌ No change to execution trace projection.
- ❌ No change to terminal state semantics.

---

## 14. Stop Conditions

Implementation must halt if any of the following are true:

1. **Phase 1/2/3 are missing from dev.** The FastAPI app must have routes for health, model version, catalog, containers, upload, and job creation.
2. **Exact current event route cannot be identified.** The SSE handler in `job_api_handler.py::handle_job_events_stream()` must be the target route.
3. **Event_store source of truth is ambiguous.** Must import and reuse the same `_event_store` singleton from `job_api_handler`.
4. **job_id reconciliation is ambiguous.** FastAPI-created job_ids must be visible to the http.server event route without additional wiring.
5. **Terminal status vocabulary is ambiguous.** The set of terminal `overall_status` values must be enumerable and unchanged.
6. **Implementation would require Control Room UI change.** Phase 4 must not modify `control_room_ui.py`.
7. **Implementation would require production Dockerfile/entrypoint change.**
8. **Implementation would expose raw internals** (S3 keys/buckets, filesystem paths, H5 internals, feature values, model coefficients, full checksums, credentials, JWT secrets, env values, PHI, raw exception traces).
9. **Event ordering cannot be tested.** Must be able to verify event sequence order in tests.
10. **Failure precedence cannot be preserved.** Must be able to verify that terminal failure prevents false completion events.
11. **Generator disconnect behavior cannot be bounded.** Must be able to verify that client disconnect stops the generator.
12. **Tests would need real server spawning.** All tests must use TestClient or direct function/generator iteration.
13. **No shared `_event_store`** — if `_event_store` cannot be imported from `job_api_handler` without side effects or circular imports.

---

## 15. Validation Plan

### 15.1 Planning Validation (run on this PR)

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only dev...HEAD
```

### 15.2 Future Implementation Validation

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only dev...HEAD

# Verify event store and SSE are reused/shared, not reimplemented
grep -R "event_store\|EventSource\|text/event-stream\|StreamingResponse\|job.*events\|live events\|job_id" -n src tests

# Verify Dockerfile unchanged
grep -n "^FROM\|^CMD\|^ENTRYPOINT" Dockerfile

# Compile check
python -m compileall src tests

# Phase-specific tests
python -m pytest -q tests/test_bremen_fastapi_phase1.py -v
python -m pytest -q tests/test_bremen_fastapi_phase2_catalog.py -v
python -m pytest -q tests/test_bremen_fastapi_phase3_write_routes.py -v
python -m pytest -q tests/test_bremen_fastapi_phase4_event_stream.py -v

# Broad test runs
python -m pytest -q -k "fastapi or phase4 or event or events or stream or job_id or terminal or control_room"
python -m pytest -q

# Whitespace check
git diff --check
```

### 15.3 Docker Validation (planned, not run during planning)

```bash
docker build --target production -t bremen-prod-unchanged-check .
```

---

## 16. File Changes Summary (Future Implementation PR)

| File | Action | Reason |
|---|---|---|
| `src/bremen/api/fastapi_app.py` | **Modify** | Add `GET /demo/api/jobs/{job_id}/events` and `GET /demo/api/jobs/{job_id}/events/stream` |
| `tests/test_bremen_fastapi_phase4_event_stream.py` | **Create** | TestClient + generator unit tests for Phase 4 |
| `src/bremen/api/server.py` | No change | Existing http.server handlers remain |
| `src/bremen/api/job_api_handler.py` | No change | Already stores state on package; reusable as-is |
| `src/bremen/api/event_store.py` | No change | Already thread-safe and SSE-capable |
| `src/bremen/api/event_schema.py` | No change | Already defines all event types and validation |
| `Dockerfile` | No change | Production target untouched |
| `pyproject.toml` | No change | Dependencies already include fastapi/uvicorn |
| `tests/test_bremen_api_server.py` | No change | Existing http.server tests must still pass |
| `tests/test_bremen_concurrent_server.py` | No change | Existing SSE concurrency tests must still pass |

---

Implementation agent: coder
