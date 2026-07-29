# Implementation Report: PR0104B — FastAPI Phase 2 Catalog Routes

**Branch**: `0104b-fastapi-phase2-catalog-routes`
**Base branch**: `dev`
**PR target**: `dev`
**Date**: 2026-07-29
**Status**: IMPLEMENTATION COMPLETE

---

## Files Changed

### New files (1)
- `tests/test_bremen_fastapi_phase2_catalog.py` — 27 Phase 2 tests

### Modified files (3)
- `src/bremen/api/fastapi_app.py` — Added GET /demo/api/models and GET /demo/api/h5/containers routes
- `src/bremen/api/server.py` — Extracted `_build_containers_response()` transport-independent helper; refactored `_handle_demo_h5_containers_list` to use it
- `tests/test_bremen_fastapi_phase1.py` — Updated app title assertion for Phase 1→2 evolution

### Not changed
- `pyproject.toml` — No new dependencies (fastapi/uvicorn/httpx already added in PR0104A)
- `requirements.txt` — No changes
- `Dockerfile` — Unchanged
- `src/bremen/model_catalog.py` — No changes (reused as-is)
- `src/bremen/api/source_registry.py` — No changes (reused as-is)
- `src/bremen/auth.py` — Unchanged
- `src/bremen/config.py` — Unchanged

---

## Phase 2 Scope

### Routes Added
1. **GET /demo/api/models** — Model catalog via `build_model_catalog()` from `bremen.api.model_catalog`
2. **GET /demo/api/h5/containers** — H5 container listing via `_build_containers_response()` from `bremen.api.server`

### FastAPI Foundation Reused
- Existing `create_fastapi_app()` factory extended with two new routes
- Same app instance serves Phase 1 and Phase 2 routes
- No disconnected second FastAPI app

### build_model_catalog Reuse
- `GET /demo/api/models` calls `bremen.api.model_catalog.build_model_catalog()` directly
- Adds `request_id` and `technical_demo_only: True` to match existing http.server response shape
- No catalog logic duplicated

### _list_s3_containers Reuse
- `_build_containers_response()` calls `bremen.api.server._list_s3_containers()` for S3 listing
- Same function used by the refactored http.server handler

---

## Cache Sharing Decision

**Decision**: Reuse the same `_patient_name_cache` from `src/bremen/api/server.py`.

**Result**: The `_build_containers_response()` helper function is defined in `server.py` and shares the module-level `_patient_name_cache` dict. Both the http.server handler and the FastAPI route call this same helper, so there is exactly one cache instance. No duplicate cache was created.

---

## Transport Extraction

**Extracted**: `_build_containers_response(request_id)` in `src/bremen/api/server.py`

This is a transport-independent function that:
- Reads demo H5 config
- Handles empty bucket case (returns safe not_configured response)
- Merges env-configured and S3-listed containers
- Deduplicates, filters oversized, sorts, limits to 100
- Assigns opaque source_ids via source_registry
- Extracts patient display names using the shared _patient_name_cache
- Returns a response dict (no HTTP transport code)

**Used by both**:
1. `_handle_demo_h5_containers_list()` (http.server handler) — calls helper, then writes JSON via BaseHTTPRequestHandler
2. `demo_h5_containers_route()` (FastAPI route) — calls helper, returns JSONResponse

---

## Server-Spawning Tests

**Not added**: No new tests start a real web server for /demo/api/models or /demo/api/h5/containers.

**Not removed**: No existing server-spawning tests were removed in this PR (Phase 2 routes are new, not replacements for existing tests).

**Existing tests preserved**: All existing http.server tests for these routes continue to pass.

---

## Confirmations

- **Production Dockerfile unchanged**: ENTRYPOINT `["python", "-m", "bremen"]`, CMD `["serve", "--host", "0.0.0.0", "--port", "8080"]` — verified
- **Production entrypoint unchanged**: `python -m bremen serve` — verified
- **No POST/SSE routes**: No POST upload/analyze/stage, no EventSource/text/event-stream in FastAPI app
- **Auth unchanged**: No auth middleware or token routes added
- **Pydantic not implemented**: No Pydantic request contracts
- **No model/training changes**: Unchanged
- **No private artifacts/H5/model files touched**: Unchanged
- **No Control Room UI changes**: Unchanged
- **No server-spawning tests added**: Verified
- **_patient_name_cache shared**: Single cache instance in server.py used by both handlers
- **Business logic not duplicated**: build_model_catalog() and _list_s3_containers() reused directly

---

## Safety Boundary

- No raw S3 bucket names or object keys in response output
- No raw filesystem paths exposed
- No raw H5 internals exposed
- No raw exception traces exposed (global exception handler)
- No credentials, JWT secrets, or env values exposed
- No model coefficients or full checksums exposed
- No PHI beyond existing patient_display_name behavior
- source_id is opaque — raw S3 key never reaches the browser

---

## Validation Results

| Command | Result |
|---------|--------|
| pytest tests/test_bremen_fastapi_phase1.py | 27 passed |
| pytest tests/test_bremen_fastapi_phase2_catalog.py | 27 passed |
| pytest tests/test_bremen_api_server.py | 99 passed |
| pytest (full suite) | 2898 passed, 11 skipped, 30 warnings |
| Dockerfile ENTRYPOINT/CMD check | Unchanged |
| Forbidden file check | Clean |
| Route exclusion check (POST/SSE) | Clean |
| git diff --check | Clean |
| Server-spawning check in Phase 2 tests | Clean |

---

## Blockers

None.

## Warnings

- Starlette TestClient deprecation: "install httpx2 instead" — future concern, not Phase 2 blocker.

---

## Next Required Action

PR0104C (if needed) for additional route migration, auth integration, or Pydantic contracts may start after this PR is merged into dev.
