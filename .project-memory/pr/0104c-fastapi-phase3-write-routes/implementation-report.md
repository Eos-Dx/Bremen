# Implementation Report: PR0104C — FastAPI Phase 3 Write Routes

**Branch**: `0104c-fastapi-phase3-write-routes`
**Base branch**: `dev`
**PR target**: `dev`
**Date**: 2026-07-29
**Status**: IMPLEMENTATION COMPLETE

---

## Files Changed

### New files (2)
- `src/bremen/api/fastapi_contracts.py` — Pydantic request model for job creation
- `tests/test_bremen_fastapi_phase3_write_routes.py` — 36 Phase 3 tests

### Modified files (3)
- `src/bremen/api/fastapi_app.py` — Added POST /demo/api/h5/containers and POST /demo/api/jobs routes
- `src/bremen/api/server.py` — Extracted `_handle_h5_upload_bytes()` transport-independent helper; refactored `_handle_demo_h5_containers_upload` to use it
- `tests/test_bremen_api_skeleton.py` — Added fastapi_app.py to H5 reference whitelist (upload route legitimately references .h5 extension)

### Not changed
- `pyproject.toml` — No new dependencies (pydantic already available)
- `Dockerfile` — Unchanged
- `src/bremen/auth.py` — Unchanged
- `src/bremen/control_room_ui.py` — Unchanged

---

## Phase 3 Scope

### Routes Added
1. **POST /demo/api/h5/containers** — H5 file upload via UploadFile with validation
2. **POST /demo/api/jobs** — Analysis job creation with typed Pydantic request

### FastAPI Foundation Reused
- Existing `create_fastapi_app()` factory extended with two new POST routes
- Same app instance serves Phase 1, 2, and 3 routes
- No disconnected second FastAPI app

---

## Pydantic Request Models

**Module**: `src/bremen/api/fastapi_contracts.py`

**JobCreateRequest** — Pydantic BaseModel with fields:
- `workflow_id` (str, default "bremen")
- `model_id` (Optional[str], default None)
- `source_id` (Optional[str], default None)
- `upload_id` (Optional[str], default None)
- `h5_path` (str, default "")
- `container_id` (str, default "")
- `action` (str, default "")

Framework-independent — can be used outside FastAPI for validation in tests or other transports.

---

## Job Creation Logic Reused

- `POST /demo/api/jobs` reuses `bremen.api.job_api_handler.create_analysis_job()` directly
- `POST /demo/api/jobs` reuses `bremen.api.job_api_handler.resolve_source()` for source resolution
- `POST /demo/api/jobs` reuses `bremen.api.job_api_handler.extract_patient_display_name()` for patient display name
- `POST /demo/api/jobs` reuses `bremen.api.job_api_handler._find_existing_completed_report()` for rerun guard
- `POST /demo/api/jobs` reuses `bremen.api.job_api_handler._cleanup_expired_uploads()` for cleanup
- `POST /demo/api/jobs` reuses `bremen.api.source_registry.get_stable_source_key()` and `get_source_info()` for source resolution
- No job creation business logic duplicated

---

## Upload Logic Reused/Extracted

**Extracted**: `_handle_h5_upload_bytes(raw_body, raw_filename, request_id)` in `src/bremen/api/server.py`

Transport-independent function that:
- Validates content length (empty body rejection)
- Validates filename presence
- Validates path traversal (/, \, ..)
- Validates extension (.h5/.hdf5 only)
- Checks upload enabled
- Checks storage configured
- Sanitizes filename
- Uploads to S3
- Returns (http_status_code, response_dict)

**Used by both**:
1. `_handle_demo_h5_containers_upload()` (http.server handler) — calls helper, writes JSON via BaseHTTPRequestHandler
2. `demo_h5_upload_route()` (FastAPI route) — calls helper, returns JSONResponse

---

## Upload Validation Checks Preserved

Every existing validation check from `_handle_demo_h5_containers_upload` is preserved:

1. **Empty body rejection** — content_length == 0 returns 400 "Empty body"
2. **Maximum upload size enforcement** — content_length > config["upload_max_bytes"] returns 413
3. **Missing filename rejection** — empty X-H5-Filename returns 400 "Missing X-H5-Filename header"
4. **Path traversal rejection** — /, \, .. in filename returns 400 "Invalid filename"
5. **Extension rejection** — non-.h5/.hdf5 returns 400 "Invalid file extension"
6. **Upload disabled check** — config["allow_upload"] == False returns 403 "upload_disabled"
7. **Storage not configured check** — config["h5_bucket"] == None returns 503 "storage_not_configured"
8. **Filename sanitization** — safe characters only, spaces to underscores, ensure .h5 extension
9. **S3 upload** — put_object with sanitized key
10. **S3 failure handling** — returns 503 with safe error type name only

All checks verified by 13 upload-specific tests.

---

## Job Validation Preserved

Job creation validation from `handle_jobs_create` is preserved:

1. **Empty body rejection** — returns 400 "Invalid JSON body"
2. **Invalid JSON rejection** — returns 400
3. **Pydantic validation** — type-safe request contract
4. **Both source_id and upload_id rejection** — returns 400 AMBIGUOUS_SOURCE
5. **Missing source rejection** — no source_id/upload_id/h5_path/container_id returns 400 MISSING_SOURCE
6. **Rerun guard** — duplicate source+workflow+model returns 409 report_already_exists
7. **Invalid source rejection** — ValueError from resolve_source returns 400 SOURCE_ERROR
8. **delete_report action** — not migrated in Phase 3, returns 400

---

## Server-Spawning Tests

**Not added**: No new tests start a real web server for these routes.

**Not removed**: No existing server-spawning tests removed in this PR.

**Existing tests preserved**: All existing http.server upload and job tests continue to pass.

---

## Confirmations

- **Production Dockerfile unchanged**: ENTRYPOINT `["python", "-m", "bremen"]`, CMD `["serve", "--host", "0.0.0.0", "--port", "8080"]` — verified
- **Production entrypoint unchanged**: `python -m bremen serve` — verified
- **No SSE/event streaming**: No EventSource, text/event-stream, or StreamingResponse in FastAPI app
- **Auth unchanged**: No auth middleware or token routes added
- **Control Room UI unchanged**: No changes to control_room_ui.py
- **No model/training changes**: Unchanged
- **No private artifacts/H5/model files touched**: Unchanged
- **No server-spawning tests added**: Verified
- **Business logic not duplicated**: create_analysis_job() and resolve_source() reused directly
- **Upload validation checks all preserved**: 10 checks enumerated and tested

---

## Safety Boundary

- No raw S3 bucket names or object keys in response output
- No raw filesystem paths exposed
- No raw H5 internals exposed
- No raw exception traces exposed (global exception handler + typed safe errors)
- No credentials, JWT secrets, or env values exposed
- No model coefficients or full checksums exposed
- source_id is opaque — raw S3 key never reaches the browser
- Upload error messages use safe type names only (not raw exceptions)

---

## Validation Results

| Command | Result |
|---------|--------|
| pytest tests/test_bremen_fastapi_phase1.py | 27 passed |
| pytest tests/test_bremen_fastapi_phase2_catalog.py | 27 passed |
| pytest tests/test_bremen_fastapi_phase3_write_routes.py | 36 passed |
| pytest tests/test_bremen_api_server.py | 99 passed |
| pytest (full suite) | 2934 passed, 11 skipped, 30 warnings |
| Dockerfile ENTRYPOINT/CMD check | Unchanged |
| Forbidden file check | Clean |
| SSE exclusion check | Clean |
| git diff --check | Clean |

---

## Blockers

None.

## Warnings

- Starlette TestClient deprecation: "install httpx2 instead" — future concern, not Phase 3 blocker.

---

## Next Required Action

PR0104D (if needed) for SSE/event streaming, analyze/stage migration, auth integration, or additional route migration may start after this PR is merged into dev.
