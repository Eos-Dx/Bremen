# PR 0079 — Concurrent Demo Server and Multi-Client SSE Safety

## Product Correction

The original PR0079 proposal combined server concurrency, investor control room, pop-out live window, model variant catalog, multiple model runs, model selector, and per-model event correlation. That scope is too large under deadline pressure and builds live UI on an unsafe server foundation.

**This PR is revised to:** Concurrent Demo Server and Multi-Client SSE Safety

The existing branch name `0079-investor-control-room-model-selection` is retained for workflow continuity, but the corrected implementation scope is documented here.

## Verified Current Blocker

The current server uses:

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
server = HTTPServer((host, port), handler)
```

`HTTPServer` is single-threaded and single-request. Each request blocks the server until the handler returns. The SSE endpoint (`GET /demo/api/jobs/{job_id}/events/stream`) keeps a blocking request open for up to 5 minutes, waiting on the event store with heartbeat intervals.

**With a single-threaded HTTPServer, one SSE connection blocks all other requests:**
- A second SSE connection cannot connect
- `/health` is unresponsive
- Job API requests are queued
- Report API requests are queued
- Normal workspace page requests are queued
- Polling requests for job status are queued

This is a verified runtime blocker, not a theoretical performance concern.

## Objective

Make the current demo server safely handle concurrent HTTP and SSE requests before further live-interface development.

The corrected PR must prove:

```
SSE client A remains connected
+ SSE client B connects independently
+ health and job API remain responsive
+ both clients receive the same authoritative new event
+ disconnecting either client does not stop the other
```

## Corrected Scope

**In scope (PR0079):**
- Threaded HTTP server (ThreadingHTTPServer)
- Thread-safe shared-state audit and locking (_jobs, singletons)
- SSE handler concurrency audit
- Concurrent two-client SSE proof
- Concurrent API responsiveness tests
- Safe operational concurrency logging
- Backward compatibility (no API schema changes)
- Documentation update (workspace_contract, ROADMAP)
- Multi-model forward architecture documented for roadmap alignment

**Deferred to PR0080 (Bremen Investor Control Room):**
- Default visible redesign
- Central live pipeline
- Docked structured log panel
- Presentation-quality visual hierarchy
- No model selector required

**Deferred to PR0081 (Provider-Owned Model Variants):**
- Real model catalog
- Explicit model selection
- model_variant_id, model_run_id
- Multiple model runs
- Independent events, decisions, and reports

## Non-Goals

PR0079 does **not** implement:
- Investor UI redesign
- Docked/pop-out log UI
- Presentation/Operator/Technical modes
- Model selector
- Model variant catalog API
- Multiple model runs
- New Bremen model variant
- Aramis model integration
- Training or evaluation
- Persistent job/event storage
- Async framework migration
- Deployment infrastructure redesign
- Any API schema changes

## Current Server Architecture

```
HTTPServer (single-threaded)
  → BaseHTTPRequestHandler
    → do_GET / do_POST dispatch
    → SSE handler: blocking loop up to 5 minutes
```

The handler class is created via `_make_handler(job_store, version)` which returns a nested class with the `InMemoryJobStore` from closure. The handler is stateless per request — all shared state lives in module-level singletons.

### Current shared state:
- `job_store` (InMemoryJobStore) — passed via closure to handler, only used by `/predictions` endpoints
- `_event_store` (BoundedEventStore) — module-level singleton in `job_api_handler.py`
- `_jobs` (dict[str, AnalysisJob]) — module-level singleton in `job_api_handler.py`
- `_report_providers` (dict[str, ReportProvider]) — module-level singleton in `job_api_handler.py`
- `ModelState` — module-level singleton with loaded model
- `WorkflowRegistry` — built fresh per call, reads current ModelState
- `BremenProvider` — created fresh per registry build

## Target Server Architecture

```
ThreadingHTTPServer (thread-per-request)
  → BaseHTTPRequestHandler (same handler class)
    → per-request thread
    → SSE handler: blocking loop, one thread per SSE client
    → lock-protected _jobs access
    → event_store already internally thread-safe
```

### Key properties:
- `daemon_threads = True` — threads don't prevent shutdown
- Address reuse already handled by `HTTPServer.allow_reuse_address = True`
- Clean `server_close()` on shutdown — no leak
- Broken client connections caught by existing write exception handlers
- Compatible with App Runner (standard HTTP, no async dependency)
- Python 3.7+ standard library, no new dependencies

### Thread lifetime:
- Each request thread serves one HTTP request-response cycle
- SSE threads live up to 5 minutes (configurable deadline)
- SSE thread exits on: stream_complete, client disconnect, deadline
- Shutdown: `daemon_threads` + explicit `server.shutdown()` + `server.server_close()`
- No thread pool — `ThreadingHTTPServer` creates/destroys per request

## Request Concurrency Boundary

| Scope | Thread safety | Action required |
|-------|---------------|-----------------|
| request handler instance | Per-request (fresh instance each call) | Safe |
| handler method locals | Per-thread stack | Safe |
| `job_store` (InMemoryJobStore) | Not internally thread-safe (plain dict) | Refactor or lock |
| `_event_store` (BoundedEventStore) | Internally thread-safe | Verify only |
| `_jobs` dict | Not thread-safe (plain dict) | Add lock |
| `_report_providers` dict | Write-once, read-many after init | Add lock |
| `ModelState` singleton | Read-only during inference | Safe |
| `BremenProvider` instance | Read-only after init, local per execute() | Safe |
| `BoundedEventStore` events | Internally thread-safe | No change needed |
| SSE handler blocking loop | Per-thread, reads shared _jobs | Add lock guard for job read |

## Shared-State Inventory

### 1. `_jobs` — dict[str, AnalysisJob]

**Classification: Requires external lock**

Current accesses:
- `create_analysis_job()`: writes `_jobs[job_id] = job`, mutates `job.overall_status`, `job.workflow_runs`, `job.completed_at`, call `_generate_job_reports` which mutates `job.reports`
- `get_analysis_job()`: reads `_jobs.get(job_id)`
- `list_analysis_jobs()`: iterates `_jobs.values()`
- `handle_job_get()`: reads job, builds traces from event store
- `handle_job_events_stream()`: reads `_jobs.get(job_id)` each loop iteration to check terminal status

**Risk**: During `create_analysis_job()`, the orchestrator runs synchronously. While model execution doesn't need the lock, the dict insertion and job field mutations do. An SSE thread reading `_jobs.get()` while a create thread is mid-mutation could see a partially initialized job. Iteration in `list_analysis_jobs()` during mutation risks `RuntimeError: dictionary changed size during iteration`.

### 2. `_event_store` — BoundedEventStore

**Classification: Thread-safe internally**

Already uses `threading.Lock` and `threading.Condition`. All public methods (`append`, `get_events`, `wait_for_events`, `has_job`, `get_job_cursor`) acquire the internal lock. No external synchronization needed.

### 3. `_report_providers` — dict[str, ReportProvider]

**Classification: Requires external lock**

Write-once during `_register_default_providers()` (called on first job creation). Read-only after that. However, concurrent first-job creation could race on the `"bremen" not in _report_providers` check. A `threading.Lock` is needed for the write path; reads can use a snapshot.

### 4. `ModelState` singleton (bremen.api.model_state)

**Classification: Immutable after initialization / internally protected**

Model is loaded once at startup. `get_model()`, `get_instance()`, `is_ready()` are read-only. The `_model_package` reference is read-only after startup. No concurrent mutation. Already safe.

### 5. `WorkflowRegistry` and `BremenProvider`

**Classification: Per-call, read-only configuration**

`get_default_registry()` builds a fresh registry each call by reading current `ModelState`. Providers are created fresh. No shared mutable state between calls.

### 6. `InMemoryJobStore` (legacy /predictions path)

**Classification: Requires external lock**

Used by `handle_submit_prediction()` path. Plain dict with no internal locking. While this path runs synchronously and completes quickly, concurrent POST requests could race. A lock guard should be added.

## Jobs Locking Strategy

Add a module-level `threading.Lock` for `_jobs`:

```python
_jobs_lock = threading.Lock()
```

### Locking rules:
1. **Acquire on write**: `create_analysis_job()` acquires `_jobs_lock` for the `_jobs[job_id] = job` insertion and any field mutations on `job` that happen after orchestration completes.
2. **Acquire on read-iteration**: `list_analysis_jobs()` acquires `_jobs_lock` for the `.values()` iteration, takes a snapshot dict copy under the lock, then releases.
3. **Acquire on single read**: `get_analysis_job()` acquires `_jobs_lock` for the `.get()` call, takes a deep-copied snapshot, then releases.
4. **Do NOT hold during orchestration**: The lock is released before `run_workflow_request()` (which may take seconds). Event store writes during orchestration are independent and already thread-safe.
5. **Do NOT hold during SSE loop**: The SSE handler's `_jobs.get()` check reads the job dict briefly under the lock. The lock is never held during `wait_for_events()`.
6. **Do NOT hold during network writes**: Lock is released before `_send_json()` or `wfile.write()`.

### Job snapshot strategy:
For read paths, capture a shallow copy of the relevant fields under the lock. This avoids holding the lock during JSON serialization or trace projection. The snapshot reflects a consistent point-in-time view.

### `_report_providers` lock:
Add `_providers_lock = threading.Lock()`. Acquire on write (`register_report_provider`). Reads use a lock-free snapshot pattern: copy the dict under the lock, use the copy.

## Singleton Initialization

### Current pattern (PR0077):
```python
_STORE_KEY = "_bremen_workspace_event_store"
def _get_or_create_store():
    s = getattr(bremen, _STORE_KEY, None)
    if s is None:
        s = BoundedEventStore()
        setattr(bremen, _STORE_KEY, s)
    return s
```

**First-access race**: Two concurrent request threads could both observe `getattr(bremen, _STORE_KEY, None) is None` and both create new stores, with only the last `setattr` surviving.

### Fix:
Use `threading.Lock` for first-access:

```python
_init_lock = threading.Lock()

def _get_or_create_store():
    s = getattr(bremen, _STORE_KEY, None)
    if s is not None:
        return s
    with _init_lock:
        # Double-check after acquiring lock
        s = getattr(bremen, _STORE_KEY, None)
        if s is not None:
            return s
        s = BoundedEventStore()
        setattr(bremen, _STORE_KEY, s)
        return s
```

Same pattern for `_get_or_create_jobs()` and `_get_or_create_providers()`.

### Module reload safety:
The current approach of storing on the `bremen` package is preserved. After `bremen.api.*` module purge and re-import, the package-level attributes survive. The lock itself is stored on the `bremen` package to survive reload:

```python
_LOCK_KEY = "_bremen_workspace_init_lock"
def _get_init_lock():
    lock = getattr(bremen, _LOCK_KEY, None)
    if lock is None:
        lock = threading.Lock()
        setattr(bremen, _LOCK_KEY, lock)
    return lock
```

## Event Store Audit

The `BoundedEventStore` already uses:
- `threading.Lock` for all mutations (`_lock`)
- `threading.Condition` for SSE wait/notify (`_condition`)
- Internal sequence counter per job
- OrderedDict for LRU eviction

### Verified safe under concurrent access:
- Concurrent appends to same job: lock protects sequence + append + LRU touch
- Concurrent appends to different jobs: lock serializes, no cross-job interference
- Concurrent `get_events` and append: lock provides consistent snapshot
- Two `wait_for_events` on same job: Condition wakes all waiters, each re-scans
- `wait_for_events` on different jobs: separate cursor checks, independent delivery
- Sequence monotonicity: sequence is assigned under the lock, never duplicated
- Event loss: append stores event in list before releasing lock; get_events re-scans after Condition wake

### No changes required to BoundedEventStore for PR0079.

## SSE Lifecycle

The SSE handler runs in a dedicated thread (one per connected client).

### Lifecycle:
1. **Connect**: Handler checks `_event_store.has_job(job_id)`, returns 404 if unknown
2. **Initial replay**: Sends events since `Last-Event-ID` cursor (or 0)
3. **Wait**: Calls `_event_store.wait_for_events(job_id, cursor, timeout=15.0)` — blocks on Condition
4. **New-event delivery**: When new events arrive, they are sent as SSE frames; cursor advances
5. **Idle heartbeat**: If `wait_for_events` times out (no events in 15s), sends `: keepalive`
6. **Terminal job**: Reads `_jobs.get(job_id)` under lock; if terminal status, drains remaining events and sends `event: stream_complete`
7. **Client disconnect**: `BrokenPipeError` / `ConnectionResetError` on `wfile.write()` breaks the loop
8. **Deadline expiry**: `time.monotonic()` exceeds start + 300s, loop exits
9. **Server shutdown**: Server calls `shutdown()` which stops accepting; SSE threads eventually hit deadline and exit (daemon threads)

### Safety properties:
- Independent cursor per client
- One slow/disconnected client does not block another
- Both clients receive the same events (shared store, independent cursors)
- Client disconnect does not remove events from store
- Broken pipe handled silently (debug log only)
- Heartbeat only while idle (no events arrive within timeout)
- `Last-Event-ID` semantics: cursor = int(last_event_id), send events with sequence > cursor

### One change required: The SSE loop currently reads `_jobs.get(job_id)` without lock protection. This must use the lock-guarded read (brief lock, snapshot, release before wait_for_events).

## Two-Client SSE Proof

Integration test using real socket/HTTP clients and a locally bound server on an ephemeral port:

```
1. start ThreadingHTTPServer on ephemeral port
2. create synthetic job via POST /demo/api/jobs
3. connect SSE client A (EventSource-like socket)
4. connect SSE client B (EventSource-like socket)
5. confirm both streams are open (connack or first keepalive)
6. request /health concurrently
7. append one event to job (via internal API, not HTTP — avoids dispatch race)
8. confirm client A receives event
9. confirm client B receives event
10. disconnect client A
11. append another event
12. confirm client B receives second event
13. request GET /demo/api/jobs/{job_id} concurrently
14. shutdown server cleanly
15. verify no leaked threads
```

The test uses `http.client` (or `urllib.request`) for regular requests and raw sockets for SSE to avoid external dependencies.

## Concurrent API Responsiveness

Integration test proving that while one or two SSE streams remain open:

```
1. start ThreadingHTTPServer on ephemeral port
2. create synthetic job
3. open SSE client A
4. open SSE client B
5. with both clients connected:
   a. GET /health responds 200
   b. GET /demo/api/jobs responds 200 with jobs list
   c. GET /demo/api/jobs/{job_id} responds 200 with job data
   d. GET /demo/api/jobs/{job_id}/events responds 200
6. verify timeout failures are absent
```

Each concurrent request must complete within a short timeout (e.g., 5 seconds). Sequential handler calls are not sufficient — only real concurrent HTTP requests prove the fix.

## Job Transition Safety

Under concurrent access:

| Transition | Atomicity | Risk | Fix |
|------------|-----------|------|-----|
| `_jobs[job_id] = job` | Writes dict entry | Partial execution visible to readers | Lock |
| `job.status = "completed"` | Field mutation | Reader sees stale status | Snapshot under lock |
| `job.workflow_runs[wid] = wr` | Dict mutation | Reader sees partial runs | Snapshot under lock |
| `job.reports[wid] = rm` | Dict mutation | Reader sees partial reports | Snapshot under lock |

**Terminal state rule**: `overall_status` is set once and never overwritten. The job is inserted as `"running"` before orchestration. After orchestration, status is set to `"completed"` or `"failed"`. No late non-terminal update can overwrite a terminal state because terminal assignment happens exactly once per job after orchestration completes. No concurrent writer exists for the same job — each job is created by exactly one request thread.

**Cross-workflow protection**: `workflow_runs` dict is per-job. Multiple workflow runs within the same job are not yet supported (that's PR0081). With single-workflow-per-job, there is exactly one workflow run writer per job. Future multi-workflow support (PR0081) will require per-run locking or atomic dict update.

## Model State and Provider Audit

### ModelState:
- `load_at_startup()` — called once at server start, never concurrently
- `get_model()` — returns reference to read-only dict; safe for concurrent reads
- `is_ready()` — reads boolean flag; safe for concurrent reads
- `get_instance()` — returns singleton reference; safe
- **No concurrent mutation**: model is not hot-swapped, reloaded, or updated during server lifetime

### BremenProvider:
- Created fresh per registry build (`get_default_registry()`)
- `__init__` receives `model_package` reference (read-only)
- `execute()` reads `_model_package` (read-only) and `_validate_model_internal()` (read-only check)
- Feature computation uses local numpy arrays (thread-local)
- Logistic regression inference is pure computation on local variables
- **No shared mutable state during inference**

### Inference concurrency:
Multiple simultaneous `execute()` calls read the same `_model_package` but do not mutate it. This is safe — numpy array reads from distinct threads operating on the same array are safe (no writer). The model coefficients, scaler means, etc. are never modified during inference.

**No provider-local inference lock is needed.**

### WorkflowRegistry:
Built fresh per call. `resolve()` returns a newly-created provider instance. No shared provider instances between concurrent calls.

## Resource Bounds

| Resource | Bound | Rationale |
|----------|-------|-----------|
| Max concurrent SSE clients | No hard cap initially | ThreadingHTTPServer creates one thread per request. Thread creation is bounded by system resources. |
| SSE stream duration | 300 seconds (5 min) | Existing deadline. Prevents abandoned connections. |
| Heartbeat interval | 15 seconds | Existing. Keeps connection alive. |
| Idle thread cleanup | Via deadline | SSE threads exit when deadline expires. |
| Thread stack | ~8 MB per thread default | Linux default. 50 concurrent SSE threads = ~400 MB. Acceptable for demo. |
| App Runner instance | 1 vCPU, 2 GB RAM typical | ~250 concurrent SSE threads feasible. Demo usage: 2–5. |

**No SSE connection cap is needed for the demo server.** If resource constraints appear, future PRs can add a configurable cap with typed rejection.

## Operational Logging

Add safe concurrency-aware log events:

```
bremen.server.starting  server_mode=threaded  max_workers=per-request
bremen.sse.connected    job_id=...  cursor=...  request_id=...
bremen.sse.disconnected  job_id=...  reason=client_disconnect|deadline|stream_complete
bremen.server.shutdown  reason=keyboard_interrupt|signal
```

No patient identifiers, raw H5 data, model inputs, feature values, private paths, or tracebacks returned to clients in logs.

## Backward Compatibility

All existing paths are preserved with no API schema changes:
- GET /health
- GET /model/version
- POST /predictions
- GET /predictions/{job_id}
- GET /demo
- GET /demo/workspace
- GET /demo/workspace/{job_id}
- GET /demo/api/evidence
- GET /demo/api/h5/containers
- POST /demo/api/h5/containers
- POST /demo/api/h5/analyze
- GET /demo/api/jobs
- POST /demo/api/jobs
- GET /demo/api/jobs/{job_id}
- GET /demo/api/jobs/{job_id}/events
- GET /demo/api/jobs/{job_id}/events/stream (SSE)
- GET /demo/api/jobs/{job_id}/reports
- GET /demo/api/jobs/{job_id}/reports/{workflow_id}

Response formats are unchanged. SSE protocol is unchanged. Event schema is unchanged. Job model is unchanged.

## Documentation

Update `docs/workspace_contract.md`:
- Document threaded demo server (ThreadingHTTPServer)
- Document concurrent-request support
- Document SSE thread-per-connection behavior
- Document stream deadline and heartbeat
- Document lock-protected job storage
- Document module-reload singleton behavior
- Document limitations of the built-in demo HTTP server (not production-grade)

Update `ROADMAP.md`:
- Set current milestone to PR0079: Concurrent Demo Server and Multi-Client SSE Safety
- List PR0080: Bremen Investor Control Room (next)
- List PR0081: Provider-Owned Model Variants and Independent Model Runs (future)

## Multi-Model Forward Architecture

Although PR0079 does not implement model selection, the following architecture is documented for roadmap alignment and future compatibility:

```
WorkflowRegistry
→ WorkflowProvider
    → provider-owned ModelVariantCatalog
        → ModelVariant
        → provider-owned artifact/configuration
        → provider-owned lifecycle
```

Future variants (only when real configurations exist):
```
Bremen
  Bremen current
  Bremen version 2
  future Bremen variants

Aramis
  Aramis current
  Aramis version 2
  future Aramis variants
```

Future selection identity:
```
workflow_id, model_variant_id, model_run_id
```

Future event correlation:
```
job_id, request_id, workflow_id, model_variant_id, model_run_id
event_id, sequence, stage, status
```

Future guarantees:
- Multiple variants of the same workflow run independently
- Results attached to model_run_id
- Reports attached to model_run_id
- One variant cannot overwrite another
- No combined verdict, no score averaging, no automatic promotion
- Unavailable variants do not silently fall back
- Bremen and Aramis remain separate providers

This architecture is documented for compatibility only. No fields are added to runtime APIs in PR0079.

## PR0080 Strategy

**Bremen Investor Control Room** (next PR after PR0079):

- Default `/demo` route redesigned with investor layout
- One real Bremen model (current, no selector needed)
- Central live pipeline visualization (per-job, single workflow)
- Docked structured log panel (right panel, SSE-fed)
- Presentation-quality visual hierarchy
- Responsive: 3-column on large screens, single-column on mobile
- Keyboard accessibility, prefers-reduced-motion
- No model selector — single workflow, single model mode
- Model provenance metadata displayed from existing trace/report data

PR0080 builds on PR0079's concurrent server foundation.

## PR0081 Strategy

**Provider-Owned Model Variants and Independent Model Runs** (future PR):

- `WorkflowProvider.list_model_variants()` and ModelVariantInfo
- `GET /demo/api/models` endpoint
- `POST /demo/api/jobs` accepts `workflow_runs: [{workflow_id, model_variant_id}]`
- `ModelRun` dataclass with `model_run_id`
- Multiple independent runs of the same workflow_id
- Per-run event correlation, results, and reports
- Independent result cards with comparison layout
- "No combined verdict" statement
- Candidate model marking (`evaluation_only`)

PR0081 begins only when additional real model configurations are available.

## Testing Strategy

### Backend tests (new file: `tests/test_bremen_concurrent_server.py`):

1. **Threaded server class**: Verify `ThreadingHTTPServer` is used, daemon threads enabled, address reuse allowed
2. **Two simultaneous SSE clients**: Real socket-based SSE clients on ephemeral port, both connected concurrently
3. **Health during SSE**: GET /health responds while SSE streams are open
4. **Job API during SSE**: GET /demo/api/jobs and GET /demo/api/jobs/{job_id} respond while SSE streams are open
5. **Both clients receive same event**: Same event emitted, both clients receive it
6. **Independent cursors**: Each SSE client has independent cursor, one client's ack does not affect the other
7. **Client disconnect isolation**: Disconnect client A, client B remains live and receives subsequent events
8. **Terminal stream**: After job completes, both clients receive stream_complete
9. **Deadline expiry**: SSE stream ends after deadline without events
10. **Broken pipe handling**: Abrupt socket close does not raise unhandled exception
11. **Clean shutdown**: server.shutdown() + server_close() do not hang
12. **No leaked threads**: After test, no request-handler threads remain

### Job storage thread-safety tests (extend `tests/test_bremen_event_stream.py`):

13. **Concurrent job creation**: Multiple threads create jobs simultaneously, all jobs visible in list
14. **Concurrent job read/write**: One thread creates/updates job, another reads concurrently, consistent snapshot
15. **Singleton first-access race**: Initialize with multiple concurrent threads, verify single store/jobs instance
16. **Module reload safety**: After module purge/reload, store, jobs, and lock survive as authoritative references
17. **Event sequence monotonicity**: Under concurrent appends to the same job from different threads, no duplicate sequence values

### Existing regression: All existing tests pass without modification.

## Deployment Smoke

After merge, verify on deployed App Runner instance:

1. Open SSE client A in browser tab 1 (workspace page)
2. Open SSE client B in browser tab 2 (workspace page, same job)
3. Keep both connected
4. Request /health via curl — responds 200
5. Request /demo/api/jobs via curl — responds 200
6. Start or inspect a demo analysis
7. Observe same new event in both clients
8. Close client A (close tab)
9. Verify client B remains live and continues to receive events
10. Open workspace in another tab, verify responsiveness
11. No tracebacks or unhandled errors in App Runner logs

Do not expose private artifacts during smoke testing.

## Expected Files to Change

### Modified files:
- `src/bremen/api/server.py` — Replace `HTTPServer` with `ThreadingHTTPServer`, add concurrency logging
- `src/bremen/api/job_api_handler.py` — Add `_jobs_lock`, `_providers_lock`, `_init_lock`, guarded singleton init, lock-protected job read/write, SSE loop lock guard
- `docs/workspace_contract.md` — Document threaded server, concurrent SSE, locking, limitations
- `ROADMAP.md` — Update current milestone to PR0079 concurrent server, add PR0080 and PR0081

### New files:
- `tests/test_bremen_concurrent_server.py` — Real concurrent HTTP/SSE integration tests

### Files NOT modified:
- `src/bremen/api/event_store.py` — Already thread-safe, no changes needed
- `src/bremen/api/event_schema.py` — No schema changes
- `src/bremen/api/job_models.py` — No model changes
- `src/bremen/api/workflow_provider.py` — No API changes
- `src/bremen/api/workflow_bremen.py` — No changes
- `src/bremen/api/workflow_aramis.py` — No changes
- `src/bremen/api/workflow_orchestrator.py` — No changes
- `src/bremen/api/runtime_plugin.py` — No changes
- `src/bremen/api/execution_context.py` — No changes
- `src/bremen/api/lifecycle_contracts.py` — No changes
- `src/bremen/api/execution_trace.py` — No changes
- `src/bremen/api/report_provider.py` — No changes
- `src/bremen/api/report_bremen.py` — No changes
- `src/bremen/api/report_aramis.py` — No changes
- `src/bremen/api/decision_support.py` — No changes
- `src/bremen/api/app.py` — No changes
- `src/bremen/api/schemas.py` — No changes
- `src/bremen/api/jobs.py` — No changes
- `src/bremen/api/h5_layouts.py` — No changes
- `src/bremen/api/preflight.py` — No changes
- `src/bremen/api/preprocessing_bridge.py` — No changes
- `src/bremen/api/model_state.py` — No changes
- `src/bremen/api/model_source.py` — No changes
- `src/bremen/workspace_ui.py` — No changes
- `src/bremen/demo_ui.py` — No changes
- `src/bremen/demo_presentation.py` — No changes
- All other frontend/src files — No changes
- Docker files — No changes
- CI/CD workflows — No changes
- Terraform — No changes

## Risks

| Risk | Mitigation |
|------|------------|
| ThreadingHTTPServer not available in Python version | Python 3.7+ standard library. We're on 3.13. No compatibility concern. |
| Thread-per-request exhausts App Runner memory | Demo usage: 2–5 SSE clients. Each thread ~8 MB. Total well within 2 GB. |
| Broken SSE thread leaks | Daemon threads + deadline (5 min) + explicit break on write error + server.shutdown() cleanup |
| Lock contention during job creation | Lock held only for brief dict/field mutations, not during model execution (seconds). |
| Lock held during SSE wait loop | Only a brief `_jobs.get()` snapshot under lock, then release before `wait_for_events` (blocking). |
| Module reload creates duplicate singletons | Lock stored on `bremen` package with double-checked locking pattern. Survives reload. |
| Existing tests need no updates | All public APIs unchanged. No schema changes. No behavior changes for non-concurrent access. |
| Lock not used in all read paths | Audit each read path. Use snapshot pattern. Tests verify concurrent safety. |

## Stop Conditions

Stop with a blocker if:
- The server cannot be made concurrent without changing deployment architecture
- Shared job state cannot be protected with bounded changes
- Model inference is proven unsafe for concurrent calls and no provider-local guard is feasible
- SSE integration tests cannot be made deterministic
- Module reload creates multiple authoritative stores or locks
- Concurrent clients cause event loss or duplicate sequence assignment
- Implementation would require PR0080 or PR0081 scope
- Private artifacts would be required

## Acceptance Criteria

### Gate 1: Threaded server pass
- `ThreadingHTTPServer` replaces `HTTPServer` in `run_server()`
- `daemon_threads = True` configured
- Server starts, accepts connections, shuts down cleanly
- Address reuse allowed
- No new dependencies

### Gate 2: Two simultaneous SSE clients pass
- Two SSE clients connect concurrently via real sockets
- Both streams receive initial events
- Both streams receive same new event
- Independent cursors maintained

### Gate 3: Health during SSE pass
- GET /health responds 200 while one or two SSE streams are open
- Response time < 5 seconds

### Gate 4: Job API during SSE pass
- GET /demo/api/jobs responds 200 during SSE
- GET /demo/api/jobs/{job_id} responds 200 during SSE
- GET /demo/api/jobs/{job_id}/events responds 200 during SSE

### Gate 5: Workspace during SSE pass
- GET /demo/workspace HTML loads during concurrent SSE streams

### Gate 6: Same event reaches both clients pass
- Both SSE clients receive the same event (same sequence, same data)

### Gate 7: Disconnect isolation pass
- Disconnecting client A does not disconnect client B
- Client B continues to receive subsequent events
- No tracebacks on disconnect

### Gate 8: Clean shutdown pass
- `server.shutdown()` + `server_close()` complete without hang
- No leaked threads after shutdown
- No unhandled exceptions

### Gate 9: Jobs thread safety pass
- Concurrent job creation from multiple threads: all jobs created and visible
- Concurrent read/write: consistent snapshots, no partial state
- `list_analysis_jobs()` iteration is safe during concurrent mutation
- Lock is not held during model execution or network writes

### Gate 10: Singleton race safety pass
- Multiple concurrent first-access calls produce a single store, single jobs dict, single lock
- Double-checked locking prevents duplicate initialization

### Gate 11: Module reload safety pass
- After `bremen.api.*` purge and re-import, store and jobs dict retain authoritative references
- Lock survives reload and is used by re-imported modules

### Gate 12: Event sequence safety pass
- Concurrent appends to same job produce no duplicate sequence numbers
- Sequence values are monotonic and gap-free

### Gate 13: Bounded resources pass
- SSE threads exit after 5-minute deadline
- Heartbeat interval documented
- No unbounded thread creation without documentation

### Gate 14: Backward compatibility pass
- All existing routes work identically
- No API schema changes
- No SSE protocol changes
- No event schema changes
- All existing tests pass unchanged

### Gate 15: Multi-model strategy documented pass
- ROADMAP.md includes PR0080 and PR0081 as documented follow-ups
- Forward architecture for model variants, model runs, event correlation is documented

### Gate 16: Full regression pass
- All existing tests pass
- New concurrent server tests pass
- No regressions in event storage, job API, SSE, reports

### Gate 17: Deployed concurrency smoke pass
- Two SSE streams open simultaneously on App Runner
- Health and job API responsive
- Both clients receive events
- Client disconnect does not affect remaining client
- No errors in App Runner logs

---

**PLAN REVISION COMPLETE: yes**

PLAN FILE: `.project-memory/pr/0079-investor-control-room-model-selection/PLAN.md`
HEAD: `18ae60374c2f22bdc086bd9666369264ea3e1f8e`
BRANCH: `0079-investor-control-room-model-selection` (retained for workflow continuity)
PRODUCT CORRECTION: Original scope was too large. Revised to pure concurrency foundation. Investor control room deferred to PR0080. Model variants deferred to PR0081.
VERIFIED BLOCKER: HTTPServer is single-threaded. One SSE connection blocks all other requests for up to 5 minutes.
CORRECTED SCOPE: Threaded server, shared-state locking, singleton race safety, concurrent SSE proof, API responsiveness tests, concurrency logging, documentation, roadmap.
TARGET SERVER: ThreadingHTTPServer with daemon_threads. No new dependencies. Python 3.7+ standard library.
SHARED STATE INVENTORY: _jobs (needs lock), _event_store (already thread-safe), _report_providers (needs lock for init), ModelState (read-only safe), providers (per-call).
JOBS LOCKING: Module-level threading.Lock. Acquire on write/create. Snapshot on read. Never held during model execution or SSE wait. Never held during network writes.
SINGLETON INITIALIZATION: Double-checked locking pattern. Lock stored on bremen package to survive module reload.
EVENT STORE: Already thread-safe (threading.Lock + Condition). Verified under concurrent append/read/wait scenarios. No changes needed.
SSE LIFECYCLE: Independent cursor per client. Lock-guarded _jobs read. wait_for_events without lock. Both clients receive same events. Independent disconnect.
TWO-CLIENT PROOF: Real sockets on ephemeral port. Connect both, send events, verify both receive, disconnect one, verify other survives. Bounded timeouts.
CONCURRENT API PROOF: Real concurrent HTTP requests during SSE streams. /health, /jobs, /jobs/{id}, /events all responsive.
MODEL STATE AUDIT: Read-only during inference. No provider-local lock needed. Model coefficients are never modified.
RESOURCE BOUNDS: No hard cap. Thread ~8 MB. 50 SSE threads ~400 MB. Within App Runner 2 GB. Deadline = 5 min.
BACKWARD COMPATIBILITY: No API schema changes. No SSE protocol changes. No event schema changes. All existing routes preserved. All existing tests pass.
MULTI-MODEL STRATEGY: Documented forward architecture. PR0080 (Control Room) next. PR0081 (Model Variants) future when configurations exist.
PR0080 STRATEGY: Investor Control Room with one model, central pipeline, docked log. No model selector. Default route redesign.
PR0081 STRATEGY: Model catalog, selection contract, model_run_id, multiple independent runs, per-run results and reports.
TESTING: test_bremen_concurrent_server.py with real socket-based SSE clients. Concurrent API test. Lock/singleton race tests. No sequential mock workaround.
DEPLOYMENT SMOKE: Two SSE tabs open simultaneously. Health responsive. Same events both clients. Disconnect isolation. No App Runner errors.
EXPECTED FILES: 1 new test file, 3 modified files (server.py, job_api_handler.py, workspace_contract.md, ROADMAP.md).
BLOCKERS: None
WARNINGS: None — all stop conditions checked and clear
