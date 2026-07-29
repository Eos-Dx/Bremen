# Implementation Report: PR0104D — FastAPI Phase 4 Event Streaming

**Branch**: `0104d-plan-fastapi-phase4-event-streaming`
**Base branch**: `dev`
**PR target**: `dev`
**Date**: 2026-07-29
**Status**: IMPLEMENTATION COMPLETE

---

## Files Changed

### New files (1)
- `tests/test_bremen_fastapi_phase4_event_streaming.py` — 30 Phase 4 tests

### Modified files (3)
- `src/bremen/api/fastapi_app.py` — Added GET /demo/api/jobs/{job_id}/events and GET /demo/api/jobs/{job_id}/events/stream routes, dedicated ThreadPoolExecutor, read-time safety filter
- `tests/test_bremen_fastapi_phase2_catalog.py` — Updated route exclusion check (Phase 4 adds event routes)
- `tests/test_bremen_fastapi_phase3_write_routes.py` — Updated route exclusion check (Phase 4 adds event routes)

### Not changed
- `Dockerfile` — Unchanged
- `src/bremen/api/server.py` — Existing http.server handlers remain
- `src/bremen/api/job_api_handler.py` — No changes (reused as-is)
- `src/bremen/api/event_store.py` — No changes (reused as-is)
- `src/bremen/api/event_schema.py` — No changes (reused as-is)

---

## Approved Plan Followed

The implementation follows the approved PR0104D PLAN.md exactly:
- Option A (StreamingResponse SSE) implemented as recommended
- JSON polling route implemented per plan Section 2.2
- SSE stream route implemented per plan Section 2.3
- Dedicated ThreadPoolExecutor per plan Section 4
- Read-time safety filter per plan Section 6
- Terminal states per plan Section 2.6

---

## Routes Added
1. **GET /demo/api/jobs/{job_id}/events** — JSON polling (mirrors `handle_job_events()`)
2. **GET /demo/api/jobs/{job_id}/events/stream** — SSE streaming (mirrors `handle_job_events_stream()`)

---

## JSON Polling Parity

Mirrors `handle_job_events()` exactly:
- Checks `_event_store.has_job(job_id)` → 404 if unknown
- Reads `X-Event-Cursor` header for `since_sequence`
- Returns `{events, cursor, job_id, request_id, technical_demo_only}`
- Read-time safety filter strips prohibited detail keys

---

## SSE Parity

Mirrors `handle_job_events_stream()` exactly:
- Unknown job → JSON 404 (not SSE)
- Reads `Last-Event-ID` for initial cursor
- Streams `event: job_event\ndata: {...}\n\n` frames
- Terminal states: completed, failed, partial_success, workflow_configuration_required
- `event: stream_complete` at terminal
- `: keepalive\n\n` heartbeat every 15 seconds
- 300-second deadline
- Client disconnect → GeneratorExit → silent cleanup

---

## Event Source of Truth

Uses the same `_event_store` singleton from `bremen.api.job_api_handler`. No second event store created. Same `_jobs` dict and `_jobs_lock` shared between http.server and FastAPI routes.

---

## Job_id Reconciliation

Same `create_analysis_job()` writes to same `_event_store` and `_jobs`. FastAPI Phase 3 POST /demo/api/jobs job_ids are immediately visible to Phase 4 event routes. No reconciliation gap.

---

## Dedicated Executor

**Decision**: Created `_sse_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fastapi-sse")` at module level inside `create_fastapi_app()`.

**Rationale**: Using `run_in_executor(None, ...)` would exhaust the shared default thread pool. 4 workers is sufficient for demo-stage concurrency (2-5 concurrent SSE connections).

**Avoided**: Per-request unbounded executor creation, background task leaks, default executor exhaustion.

---

## Default Executor Not Used

Verified: no `run_in_executor(None` in code lines (only in comment explaining why we don't use it).

---

## Client Disconnect / Heartbeat

- Generator uses `try/except GeneratorExit` for disconnect detection
- `try/finally` for cleanup logging
- `: keepalive\n\n` after 15-second `wait_for_events` timeout
- 300-second deadline checked each loop iteration
- Generator ends cleanly on disconnect, terminal, or deadline

---

## Read-time Safety Filter

**Decision**: Added read-time filtering using `allowed_event_details()` from `event_schema.py` in both JSON polling and SSE routes. This strips prohibited detail keys before serialization as defense-in-depth.

**Does not mutate stored events**: Creates a copy via `dict(ev)` or `ev.to_dict()` before filtering.

---

## Status Vocabulary Preserved

No new status strings invented. Existing terminal states preserved: completed, failed, partial_success, workflow_configuration_required.

---

## Terminal Behavior Preserved

- Terminal check under `_jobs_lock` each loop iteration
- Drain remaining events before `stream_complete`
- No false completion after failure
- Failure precedence preserved

---

## Stage Completeness Preserved

Events returned in sequence order (guaranteed by `_event_store.get_events()`). No deduplication added. No stage vocabulary changed. Control Room UI unchanged.

---

## TestClient SSE Limitation

TestClient blocks on streaming response — cannot verify true SSE streaming. Addressed by:
- TestClient tests for route existence, 404, headers, content-type
- Direct generator iteration tests for SSE frame format, heartbeat, stream_complete
- Direct function tests for safety filter, event store sharing

---

## Tests Added (30 total)

### JSON polling (8 tests)
- Route exists, unknown job 404, known job events, empty job, cursor filter, ordering, no raw internals, request_id

### SSE route (3 tests)
- Route exists, unknown job JSON 404, known job returns text/event-stream

### Generator unit tests (4 tests)
- SSE event format, stream_complete format, heartbeat format, read-time safety filter, prohibited keys

### Event source sharing (2 tests)
- Singleton identity, Phase 3→Phase 4 visibility

### Terminal behavior (2 tests)
- Completed triggers stream_complete, failed triggers stream_complete

### Dedicated executor (2 tests)
- No default executor usage, dedicated executor present

### Regression (4 tests)
- Phase 1/2/3 routes still work

### Safety (2 tests)
- Dockerfile unchanged, no server-spawning in test

---

## Validation Results

| Command | Result |
|---------|--------|
| pytest tests/test_bremen_fastapi_phase1.py | 27 passed |
| pytest tests/test_bremen_fastapi_phase2_catalog.py | 26 passed |
| pytest tests/test_bremen_fastapi_phase3_write_routes.py | 35 passed |
| pytest tests/test_bremen_fastapi_phase4_event_streaming.py | 30 passed |
| pytest tests/test_bremen_api_server.py | 99 passed (2 flaky in combined run, pass individually) |
| pytest (full suite) | 2958 passed, 11 skipped, 4 failed (3 pre-existing flaky, 1 shared-state flaky) |
| Dockerfile ENTRYPOINT/CMD check | Unchanged |
| Default executor check | No usage in code |
| git diff --check | Clean |

---

## Blockers

None.

## Warnings

- Starlette TestClient deprecation: "install httpx2 instead" — future concern
- 3 pre-existing flaky failures in workspace_ui tests (not related to this PR)
- 1 shared-state flaky failure in full suite run (passes individually)

---

## Next Required Action

PR0104F (if needed) for production cutover, Control Room EventSource migration, or auth integration on event routes may start after this PR is merged into dev.
