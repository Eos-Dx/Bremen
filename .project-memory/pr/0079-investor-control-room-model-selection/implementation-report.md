PR 0079 — Implementation Report (Final)

Agent: coder
Branch: 0079-investor-control-room-model-selection
Starting committed plan HEAD: 08616f7722a669c25f92373198f73f0965e7b10c
Implementation complete: yes
All plan review findings resolved: yes


Findings Resolution

| Finding | Status | Resolution |
|---------|--------|-----------|
| W001 — InMemoryJobStore locking not detailed | Resolved | Added internal threading.Lock. All mutable operations (create_job, get_job, update_status, job_count) acquire the lock. Log writes happen outside the lock. |


Files Changed

New files (1):
  tests/test_bremen_concurrent_server.py — 19 tests covering threaded server class, two-client SSE, singleton initialization, module reload, concurrent job storage, InMemoryJobStore thread safety, event store concurrency, shutdown.

Modified files (3):
  src/bremen/api/server.py — HTTPServer replaced with ThreadingMixIn + HTTPServer (_ThreadingHTTPServer). daemon_threads=True. Clean shutdown with server.shutdown() + server.server_close(). Concurrency-aware startup log (server_mode=threaded).
  src/bremen/api/job_api_handler.py — threading import. Package-level _jobs_lock and _providers_lock. Double-checked locking for _get_or_create_store(), _get_or_create_jobs(), _get_or_create_providers(). Lock-protected _jobs reads/writes. Lock-protected _report_providers init. Lock-guarded _jobs.get() in SSE loop. reset_for_tests() acquires locks during clear.
  src/bremen/api/jobs.py — threading import. Internal _lock added to InMemoryJobStore. All methods (create_job, get_job, update_status, job_count) acquire the lock.

Docs updated:
  docs/workspace_contract.md — PR0079 section: threaded server, concurrent request support, SSE thread-per-connection, lock-protected job storage, InMemoryJobStore thread safety, singleton initialization, module reload behavior, model/provider concurrency audit, resource bounds, demo server limitations, deployed concurrency smoke procedure, multi-model forward strategy.
  ROADMAP.md — Current milestone set to PR0079. Previous milestone PR0078 documented. Next milestone PR0080 (Investor Control Room). Future milestone PR0081 (Provider-Owned Model Variants).

Files NOT modified:
  src/bremen/api/event_store.py — Already thread-safe. No changes needed.
  src/bremen/api/event_schema.py — No schema changes.
  src/bremen/api/job_models.py — No model changes.
  src/bremen/api/workflow_provider.py — No API changes.
  src/bremen/api/workflow_bremen.py — No changes.
  src/bremen/api/workflow_aramis.py — No changes.
  src/bremen/api/workflow_orchestrator.py — No changes.
  All other files — No changes.


Server Implementation

_ThreadingHTTPServer class defined in server.py:
  class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
      daemon_threads = True

This replaces the single-threaded HTTPServer in run_server().
Daemon threads ensure the process can exit during shutdown without
waiting for active SSE connections to time out.  Address reuse is
explicitly enabled.  Clean shutdown calls server.shutdown() then
server.server_close().

Startup log includes server_mode=threaded and max_workers=per-request.
Shutdown log emits reason=keyboard_interrupt with started/completed pairs.


Shared-State Inventory

Object                           | Class              | Thread safety    | Action
---------------------------------|--------------------|------------------|-------
_jobs (dict[str, AnalysisJob])   | dict               | Needs lock       | Lock added (_jobs_lock)
_event_store                     | BoundedEventStore  | Already safe     | Verified only
_report_providers                | dict               | Needs lock       | Lock added (_providers_lock)
ModelState singleton             | ModelState         | Read-only after init | Safe
BremenProvider instances         | BremenProvider     | Per-call, fresh  | Safe
InMemoryJobStore._jobs           | dict               | Needs lock       | Lock added (W001)
job_store (handler closure)      | InMemoryJobStore   | Now thread-safe  | Verified


Jobs Locking

Module-level _jobs_lock = threading.Lock(), stored on bremen package
via _JOBS_LOCK_KEY to survive module reload.

Locking rules implemented:
  create_analysis_job(): acquires lock for _jobs[job_id]=job insertion
    and field mutations after orchestration.  Lock released before
    run_workflow_request() and _generate_job_reports().
  get_analysis_job(): acquires lock for _jobs.get(), releases before return.
  list_analysis_jobs(): acquires lock for _jobs.values() snapshot,
    releases before serialization.
  handle_job_get(): acquires lock for _jobs.get(), releases before
    trace projection and _send_json.
  SSE loop: acquires lock for _jobs.get(job_id) status check,
    releases before wait_for_events.
  get_job_reports(): acquires lock for job read and reports snapshot.
  get_job_report(): acquires lock for job and wf_run reads.
  reset_for_tests(): acquires lock for _jobs.clear().

Lock is never held during:
  run_workflow_request() (model execution, seconds)
  wait_for_events() (blocking on Condition)
  wfile.write() (network I/O)
  json.dumps() (serialization)
  report generation or trace projection


InMemoryJobStore W001 Resolution

Added internal threading.Lock to InMemoryJobStore.  All mutable
operations acquire the lock:

  create_job(): acquires lock for self._jobs[job_id] = record
  get_job(): acquires lock for self._jobs.get(job_id)
  update_status(): acquires lock for record mutations
  job_count: acquires lock for len(self._jobs)

Log writes happen outside the lock.  Lock scope is minimal — only
dict operations, not logging or caller-side processing.


Singleton Initialization

Double-checked locking pattern with a package-stored init lock:

  def _get_package_lock(key):
      lock = getattr(bremen, key, None)
      if lock is None:
          lock = threading.Lock()
          setattr(bremen, key, lock)
      return lock

  def _get_or_create_store():
      s = getattr(bremen, _STORE_KEY, None)
      if s is not None: return s
      with init_lock:
          s = getattr(bremen, _STORE_KEY, None)
          if s is not None: return s
          s = BoundedEventStore()
          setattr(bremen, _STORE_KEY, s)
          return s

Same pattern for _get_or_create_jobs() and _get_or_create_providers().

The init lock (_INIT_LOCK_KEY) is stored on the bremen package.
Jobs lock (_JOBS_LOCK_KEY) and providers lock (_PROVIDERS_LOCK_KEY)
are also package-stored to survive module reload.

Behavioral test: 4 threads concurrently call first-access functions
after clearing package attributes.  Barrier ensures simultaneous
entry.  All threads observe the same object identity (one store,
one dict, one lock).

Module reload test: after bremen.api.* purge and re-import, the
package-level attributes for store, jobs, and lock survive as
authoritative references.


Event Store Audit

BoundedEventStore is internally thread-safe (threading.Lock +
threading.Condition).  All public methods acquire the lock.

Verified under concurrent access:
  Concurrent appends to same job: lock serializes, no duplicates
  Concurrent appends to different jobs: per-job sequence isolation
  wait_for_events on same job: Condition wakes all waiters
  Monotonic sequences: sequence assigned under lock, never duplicated

No changes required to BoundedEventStore for PR0079.


SSE Lifecycle

SSE handler (handle_job_events_stream) runs in a dedicated thread
per connected client.

Lifecycle:
  1. Connect: check _event_store.has_job(job_id), return 404 if unknown
  2. Initial replay: send events since Last-Event-ID cursor
  3. Wait: _event_store.wait_for_events(job_id, cursor, timeout=15.0)
  4. Delivery: send new events as SSE frames, advance cursor
  5. Heartbeat: send keepalive when no events arrive within 15s
  6. Terminal: lock-guarded _jobs.get() status check, drain events,
     send stream_complete
  7. Disconnect: BrokenPipeError/ConnectionResetError on wfile.write()
  8. Deadline: time.monotonic() exceeds start + 300s
  9. Shutdown: daemon thread exits; no additional cleanup needed

Safety properties:
  Independent cursor per client
  One client's slow/disconnected state does not block another
  Both clients receive same events (shared store, independent cursors)
  Client disconnect does not remove events from store
  Job execution independent of browser connections
  No raw tracebacks returned to clients


Two-Client Proof

Real socket-based integration test on ephemeral port:
  1. Create synthetic job via HTTP API
  2. Open SSE client A (raw socket, reads headers+events)
  3. Open SSE client B (raw socket, reads headers+events)
  4. Confirm both clients connect (TCP handshake + 200 response)
  5. Disconnect client A
  6. Verify client B remains alive
  7. Verify health endpoint responds 200 during SSE
  8. Verify job API responds 200 during SSE
  9. Verify workspace HTML responds 200 during SSE
  10. Verify clean shutdown

All tests use bounded timeouts (5s max) and deterministic
synchronization.


Concurrent API Proof

Test class TestTwoClientSSE verifies while SSE streams remain open:
  GET /health responds 200
  GET /demo/api/jobs responds 200 with job list
  GET /demo/api/jobs/{job_id} responds 200 with job data
  GET /demo/workspace responds 200 with HTML


Disconnect Isolation

Test verifies: closing client A's socket does not affect client B.
Health endpoint remains responsive after one client disconnects.
Client B's socket remains readable (timeout confirms alive state,
not connection reset).


Shutdown and Thread Cleanup

Test verifies: server.shutdown() + server.server_close() completes
within 5 seconds.  Server thread joins successfully.  Daemon threads
from active connections do not prevent process exit.


Model and Provider Audit

ModelState: loaded once at startup (load_at_startup).  All subsequent
reads (get_model, is_ready, get_instance) are read-only.  No hot-swap,
no concurrent mutation.  Safe for concurrent inference.

BremenProvider: created fresh per get_default_registry() call.  No
shared provider instances between concurrent HTTP requests.  execute()
reads _model_package (read-only dict reference) and performs pure
computation on local numpy arrays.  Logistic regression is stateless
computation.

No provider-local inference lock is needed.


Resource Bounds

Thread-per-request model.  Thread ~8 MB stack (Linux default).
50 concurrent SSE threads ~400 MB.  Within typical App Runner
instance (2 GB RAM).  Demo usage: 2-5 concurrent SSE clients.

No hard SSE connection cap.  Thread creation bounded by system
resources and the 5-minute stream deadline (threads self-terminate).


Backward Compatibility

All existing routes preserved with no API schema changes:
  GET /health, GET /model/version
  POST /predictions, GET /predictions/{job_id}
  GET /demo, GET /demo/workspace, GET /demo/workspace/{job_id}
  GET /demo/api/evidence
  GET /demo/api/h5/containers, POST /demo/api/h5/containers
  POST /demo/api/h5/analyze
  GET|POST /demo/api/jobs, GET /demo/api/jobs/{job_id}
  GET /demo/api/jobs/{job_id}/events
  GET /demo/api/jobs/{job_id}/events/stream (SSE)
  GET /demo/api/jobs/{job_id}/reports
  GET /demo/api/jobs/{job_id}/reports/{workflow_id}

Response formats unchanged.  SSE protocol unchanged (same event types,
same framing, same Last-Event-ID semantics).  Event schema unchanged.
Job model unchanged.

Full regression: 1644 passed, 0 failed, 11 skipped.
All 1625 pre-existing tests pass unchanged.
All 19 new concurrent tests pass.


Multi-Model Strategy Documentation

Documented in workspace_contract.md and ROADMAP.md:

PR0080 (Bremen Investor Control Room): default route redesign,
central live pipeline, docked log panel, one real Bremen model,
no model selector.  Builds on PR0079's concurrent server.

PR0081 (Provider-Owned Model Variants): model variant catalog,
explicit selection (model_variant_id, model_run_id), multiple
independent runs, per-run events/decisions/reports.  Begins only
when additional real model configurations are available.

Future architecture: WorkflowRegistry -> WorkflowProvider ->
ProviderOwnedModelVariantCatalog -> ModelVariant.  Independence
guarantees: no combined verdict, no score averaging, no silent
fallback, no fabricated variants, Bremen and Aramis separate.


Focused Tests

test_bremen_concurrent_server.py — 19 tests:
  TestThreadedServerClass: 2 tests
    test_threading_server_is_used
    test_server_starts_and_accepts_connections
  TestTwoClientSSE: 8 tests
    test_two_sse_clients_connect
    test_health_during_sse
    test_jobs_api_during_sse
    test_job_get_during_sse
    test_workspace_during_sse
    test_disconnect_isolation
    test_clean_shutdown
  TestSingletonInitialization: 2 tests
    test_singleton_first_access_no_duplicate_creation
    test_module_reload_preserves_singletons
  TestConcurrentJobStorage: 2 tests
    test_concurrent_job_creation
    test_concurrent_list_during_creation
  TestInMemoryJobStoreThreadSafety: 2 tests
    test_concurrent_create_and_read
    test_concurrent_update_and_read
  TestEventStoreConcurrency: 2 tests
    test_concurrent_append_same_job
    test_concurrent_append_different_jobs
    test_monotonic_sequence_under_concurrency
  TestShutdownAndCleanup: 1 test
    test_server_shutdown_completes_quickly


Full Suite

1644 passed, 11 skipped, 0 failures.
All existing tests pass without modification.


Deviations

None.  Implementation follows the approved PLAN.md exactly.


Blockers

None.


Warnings

None.  W001 resolved (InMemoryJobStore locking implemented and tested).


Private-Artifact Exclusion

No private H5 files, model artifacts, patient data, credentials,
or secrets were used during implementation or testing.  All tests
use synthetic data generated at runtime.


PR0080 Boundary

PR0080 (Bremen Investor Control Room) is documented as the next
milestone.  PR0079 provides the concurrent server foundation.
PR0080 will implement:
  Default /demo route redesign
  Central live pipeline
  Docked structured log panel
  One real Bremen model, no selector needed
  Presentation-quality visual hierarchy
  Responsive layout, accessibility, reduced motion


PR0081 Boundary

PR0081 (Provider-Owned Model Variants) is documented as a future
milestone.  It begins only when additional real model configurations
exist.  PR0081 will implement:
  Provider-owned model variant catalogs
  model_variant_id, model_run_id
  Multiple independent model runs
  Per-run events, decisions, reports
  No combined verdict, no score averaging
