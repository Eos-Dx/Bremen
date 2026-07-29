# PR0104 — FastAPI Migration Phase 2: Catalog Routes

**Status**: Planning Only

---

## 1. Scope

PR0104 implementation will port only two GET routes from the existing `http.server`-based handlers to FastAPI:

| Route | Existing handler | Imported business logic |
|---|---|---|
| `GET /demo/api/models` | `_handle_demo_models()` | `build_model_catalog()` |
| `GET /demo/api/h5/containers` | `_handle_demo_h5_containers_list()` | `_list_s3_containers()`, `read_demo_h5_config()`, `register_source()`, `extract_patient_display_name()`, `_patient_name_cache` |

**Branch**: `0104-fastapi-phase2-catalog-routes`  
**Base branch**: `dev`  
**PR target**: `dev`  
**`main` is not touched.** The production demo (`main` branch) remains fully protected.

**Critical dependency**: PR0103 Phase 1 (FastAPI foundation) must be completed before PR0104 implementation can begin. See [Stop Conditions](#12-stop-conditions).

---

## 2. Current Handler Coupling

### 2.1 `_handle_demo_models()` (server.py:664)

This handler:

1. Receives a raw `BaseHTTPRequestHandler` instance.
2. Calls `build_model_catalog()` from `bremen.api.model_catalog`.
3. Injects `request_id` (from header or generated UUID) and `technical_demo_only: True`.
4. Serializes to JSON with `json.dumps()`.
5. Writes HTTP 200 response manually through `send_response()`, `send_header()`, `end_headers()`, `wfile.write()`.

**Response shape (JSON)**:
```json
{
  "schema_version": "v1",
  "catalog_timestamp": "...",
  "models": [...],
  "default_model_id": "...",
  "status": "available|no_valid_models|not_configured|discovery_failed",
  "request_id": "...",
  "technical_demo_only": true
}
```

**Catalog-mode extras** (when `catalog_status != "not_configured"`):
- `candidate_count`, `available_count`, `rejected_count`, `unavailable_count`
- `last_discovery_at`
- `unavailable_models`

**Key observation**: The data-shaping logic (`build_model_catalog()`) is already transport-independent. Only the HTTP serialization/writing is coupled to `http.server`.

### 2.2 `_handle_demo_h5_containers_list()` (server.py:691)

This handler:

1. Receives a raw `BaseHTTPRequestHandler` instance.
2. Reads config via `read_demo_h5_config()`.
3. Calls `_list_s3_containers()` to get S3-listed containers.
4. Merges env-configured containers, deduplicates, filters oversized objects, sorts by `last_modified`, limits to 100.
5. Replaces raw S3 keys with opaque `source_id` via `register_source()`.
6. Extracts patient display names using `_patient_name_cache` (module-level dict) and `extract_patient_display_name()`.
7. Builds response dict with `storage`, `containers`, `upload_max_bytes`, `request_id`, `technical_demo_only`.
8. Serializes to JSON and writes HTTP response manually.

**Response shape (JSON)**:
```json
{
  "storage": "configured|not_configured|list_failed",
  "containers": [
    {
      "source_id": "...",
      "display_name": "...",
      "patient_display_name": "...",
      "stable_source_key": "...",
      "size_bytes": 12345,
      "last_modified": "...",
      "workflow_id": "bremen"
    }
  ],
  "upload_max_bytes": 524288000,
  "technical_demo_only": true,
  "request_id": "..."
}
```

**Key observation**: The data-shaping logic is deeply intertwined with HTTP response writing. Phase 2 must extract the response-dict construction while preserving all deduplication, caching, filtering, and safety behavior.

---

## 3. FastAPI App Extension Plan

### 3.1 PR0103 Phase 1 Foundation (MISSING — BLOCKER)

**PR0103 Phase 1 does not exist yet.** No FastAPI dependency, no FastAPI app module, no uvicorn runner, and no ASGI entry point exist anywhere in the codebase.

Before Phase 2 can be implemented, PR0103 Phase 1 must establish:

1. **FastAPI dependency** in `pyproject.toml` (`fastapi>=0.115`, `uvicorn[standard]>=0.32`).
2. **FastAPI app module**, recommended as `src/bremen/api/fastapi_app.py` — a single `FastAPI()` instance.
3. **Uvicorn runner integration** — a new command or startup path that boots the FastAPI app via `uvicorn.run()` without modifying the production Dockerfile CMD/ENTRYPOINT.
4. **Mounting or coexistence strategy** — the FastAPI app must be mountable alongside the existing `http.server` (e.g., on a different port, or behind a path prefix) so both can run in parallel during migration.
5. **No production docker change** — the existing production Dockerfile `ENTRYPOINT ["python", "-m", "bremen"]` and `CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]` remain untouched.

**Phase 1 must NOT include any route handlers beyond a health/probe endpoint** (e.g., `GET /__fastapi_health`). Routes are added incrementally in Phase 2+.

### 3.2 Phase 2 Extension

Phase 2 will add routes to the Phase 1 FastAPI app module. Two organizational options are acceptable — Phase 1 must specify which:

**Option A — Companion route module** (preferred):
- `src/bremen/api/fastapi_routes_demo.py` — contains route handlers for the two demo catalog endpoints.
- Imported and included in the Phase 1 `fastapi_app.py` via `app.include_router(router)`.
- Keeps route logic separate from the app definition.

**Option B — Extend app module directly**:
- Add route handler functions directly into `fastapi_app.py`.
- Acceptable only if `fastapi_app.py` is already organized for route growth.

**Forbidden**: Creating a disconnected second FastAPI app instance. The Phase 1 app must be the single source of truth.

---

## 4. GET /demo/api/models Plan

### 4.1 Implementation

```python
# Pseudocode — exact import paths depend on Phase 1 module structure
from fastapi import APIRouter, Request
from ..model_catalog import build_model_catalog

router = APIRouter()

@router.get("/demo/api/models")
async def demo_models(request: Request):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    catalog = build_model_catalog()
    catalog["request_id"] = request_id
    catalog["technical_demo_only"] = True
    return catalog
```

### 4.2 Reuse Confirmation

- `build_model_catalog()` is imported and called directly — no logic duplication.
- No Pydantic request/response models in Phase 2. The response dict is returned as-is (FastAPI serializes to JSON).

### 4.3 Output Shape Matching

The returned dict must produce identical JSON output to the existing `_handle_demo_models()` for the same registry state:

- Same top-level keys: `schema_version`, `catalog_timestamp`, `models`, `default_model_id`, `status`, `request_id`, `technical_demo_only`.
- Same catalog-mode extras when applicable.
- Same model entry shapes (via `RegistryModelEntry.to_safe_dict()`).
- Same `request_id` from X-Request-ID header (or generated if absent).
- `technical_demo_only` always `true`.
- Status codes: always 200.

### 4.4 Error Behavior

- `build_model_catalog()` never raises under normal conditions (it reads from the initialized registry).
- If the registry is not initialized, `get_registry()` returns a default empty registry — the route still returns 200 with `status: "not_configured"`.
- No 4xx/5xx for this route — matching existing behavior.

---

## 5. GET /demo/api/h5/containers Plan

### 5.1 Implementation

This route has more complex logic. The FastAPI handler must reproduce the following sequence exactly:

1. Read config via `read_demo_h5_config()`.
2. If no bucket configured → return `{storage: "not_configured", containers: [], technical_demo_only: true}`.
3. Parse env-configured containers from `BREMEN_DEMO_H5_CONTAINERS`.
4. Call `_list_s3_containers(bucket, prefix)` for S3-listed containers (lazy import boto3).
5. Handle S3 exceptions → set `storage: "list_failed"`.
6. Merge with deduplication by raw S3 key.
7. Filter oversized objects by `upload_max_bytes`.
8. Sort by `last_modified` descending.
9. Limit to 100 objects.
10. For each container:
    - Call `register_source(bucket, object_key, filename, size_bytes, prefix)` → get `source_id`.
    - Get `workflow_id` from item (default `"bremen"`).
    - Check `_patient_name_cache` for `(bucket, raw_key, size)`.
    - If not cached, stage the H5, call `extract_patient_display_name()`, cache result.
    - Build safe container entry with `source_id`, `display_name`, `patient_display_name`, `stable_source_key`, `size_bytes`, `last_modified`, `workflow_id`.
11. Assemble response: `{storage, containers, upload_max_bytes, technical_demo_only, request_id}`.

### 5.2 Key Reuse Points

| Logic | Reused from | Location |
|---|---|---|
| Config reading | `read_demo_h5_config()` | `server.py` (importable from `bremen.api.server` or `bremen.demo_config`) |
| S3 listing | `_list_s3_containers()` | `server.py` (module-level function) |
| Source registry | `register_source()`, `get_stable_source_key()` | `bremen.api.source_registry` |
| Patient name extraction | `extract_patient_display_name()` | `bremen.api.job_api_handler` |
| H5 staging | `stage_h5_input()` | `bremen.h5_inputs` |

### 5.3 Patient Display Name Preservation

- Patient display names must be identical between existing and FastAPI routes for the same input state.
- This includes the fallback chain: cached name → extracted name → filename as `display_name`.
- Empty-string `patient_display_name` when no name is found.

### 5.4 Source ID Opacity

- The raw S3 key must never appear in response.
- `source_id` is generated by `register_source()`.
- The registry is process-local — same as existing implementation.

### 5.5 Error Safety

- If S3 listing fails → `storage: "list_failed"`, empty containers list.
- If H5 staging fails → silently cache `None`, use filename as display_name.
- No raw exception traces in response.
- No raw S3 bucket names, keys, or filesystem paths in response.

---

## 6. Cache Sharing Decision

**Decision**: Import and reuse the exact same `_patient_name_cache` object from `server.py`.

```python
from .server import _patient_name_cache
```

**Justification**:
- The cache is a module-level `dict[tuple[str, str, int], str | None]` at `server.py:688`.
- Creating a separate cache would mean duplicate H5 staging and patient name extraction calls for the same S3 object, wasting S3 bandwidth and latency.
- A second cache would silently diverge — a container could have `patient_display_name` set via one route and empty via the other, breaking frontend consistency.
- The cache is in-memory only, no persistence or serialization concerns.

**Import approach**: Use a direct `from bremen.api.server import _patient_name_cache` import. This is acceptable because:
- The cache is already accessed by multiple callers within `server.py`.
- The import creates no circular dependency (the FastAPI module depends on `server.py`, not vice versa).
- No thread-safety concern — both http.server (threaded) and FastAPI (async) users access the same dict; race conditions on cache writes are acceptable (at worst, duplicate staging).

---

## 7. Response Parity Plan

For each route, implementation tests will verify that the FastAPI route output matches the existing http.server route output for the same input state.

### 7.1 Comparison Method

The implementation PR must include a test that:

1. Initializes the model registry (for `/demo/api/models`) or demo config (for `/demo/api/h5/containers`) to a known state.
2. Calls the existing http.server handler via `server_info` fixture (as existing tests do) and captures the JSON response.
3. Calls the FastAPI route via `TestClient` and captures the JSON response.
4. Deep-compares the two JSON documents using `assert` equality.

### 7.2 Parity Dimensions

| Dimension | `/demo/api/models` | `/demo/api/h5/containers` |
|---|---|---|
| Field names | ✓ | ✓ |
| Field types | ✓ | ✓ |
| `technical_demo_only` | Always `true` | Always `true` |
| Safe identifiers | No raw model paths/checksums | No raw S3 keys/buckets |
| Raw internals absent | No `_package`, `_checksum`, `coef` | No S3 key, bucket, h5 path, PHI |
| Empty state | Zero-model registry | No bucket configured |
| Error state | N/A (always 200) | S3 `list_failed`, bucket None |

### 7.3 Test Scenarios

**For `/demo/api/models`**:
- Empty registry (not_configured)
- One available model
- Multiple models
- Unavailable models present
- Discovery_failed status
- X-Request-ID propagation
- No prohibited fields leak

**For `/demo/api/h5/containers`**:
- No bucket configured (not_configured)
- Bucket configured (via mocked S3)
- Empty S3 listing
- Mixed env-configured + S3 containers
- Patient name cache hit
- Patient name cache miss → extraction
- Oversized object filtering
- Max 100 limit
- S3 error → list_failed
- No raw key/bucket exposure

---

## 8. Safety Boundary

The FastAPI routes must not expose:

- Raw S3 bucket names (`test-bucket`, `prod-bucket`)
- Raw S3 object keys (`demo-uploads/patient_001.h5`)
- Filesystem paths (`/tmp/staged_abc123.h5`)
- Raw H5 internals (dataset names, group paths, attributes)
- PHI / private data (patient names beyond `patient_display_name`, MRNs, study IDs)
- Raw exception traces (stack traces, line numbers, file paths)
- Feature values or model coefficients
- Model checksums (full hashes)
- Credentials, JWT secrets, or env variable values

**Same safety rules as existing handlers**. The FastAPI routes must call the same `_safe_error_detail()` and `_safe_error_detail_str()` functions for exception handling.

---

## 9. Test Plan

The implementation PR must add a new test file (recommended: `tests/test_fastapi_routes_phase2.py`) with FastAPI `TestClient`-based tests.

### 9.1 Required Tests

**`GET /demo/api/models`**:
- `test_models_returns_200` — basic 200 response
- `test_models_parity_with_http_server` — deep JSON equality with existing handler
- `test_models_technical_demo_only` — `technical_demo_only` is `true`
- `test_models_request_id_from_header` — X-Request-ID header propagated
- `test_models_request_id_generated` — X-Request-ID generated when missing
- `test_models_not_configured` — empty registry returns `status: "not_configured"`
- `test_models_no_prohibited_fields` — no `_package`, `_checksum`, `coef`, `s3://`
- `test_models_default_model_id` — single available model is default
- `test_models_unavailable_models` — unavailable_models field present in catalog mode

**`GET /demo/api/h5/containers`**:
- `test_containers_returns_200` — basic 200 response
- `test_containers_parity_with_http_server` — deep JSON equality with existing handler
- `test_containers_technical_demo_only` — `technical_demo_only` is `true`
- `test_containers_request_id_header` — X-Request-ID header propagated
- `test_containers_not_configured` — no bucket returns `storage: "not_configured"`
- `test_containers_no_raw_s3_keys` — response contains no S3 bucket or key values
- `test_containers_no_raw_exceptions` — no traceback/exception in response
- `test_containers_patient_name_cache_shared` — cache entries written by http.server route are visible from FastAPI route and vice versa
- `test_containers_patient_display_name_preserved` — same container returns same name via both routes
- `test_containers_source_id_opaque` — source_id is not a raw S3 key
- `test_containers_stable_source_key` — stable_source_key is present and stable
- `test_containers_oversized_filtered` — containers > upload_max_bytes excluded
- `test_containers_max_100` — at most 100 containers returned
- `test_containers_list_failed` — S3 error returns `storage: "list_failed"`
- `test_containers_empty_response` — empty S3 returns empty containers list
- `test_containers_sort_order` — newest first by last_modified

### 9.2 Existing Test Suite Must Still Pass

```
python -m pytest -q tests/test_bremen_api_server.py -v
python -m pytest -q tests/test_catalog_api_multi_model.py -v
python -m pytest -q tests/ -k "not slow"
```

---

## 10. Validation Plan

### 10.1 Git Validation

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only dev...HEAD
```

### 10.2 Production Docker Integrity

```bash
grep -n "^FROM\|^CMD\|^ENTRYPOINT" Dockerfile
```

Expected unchanged output:
```
22:FROM python:3.13-slim AS base
37:FROM base AS smoke-builder
43:FROM python:3.13-slim AS smoke
57:CMD ["python", "-m", "pytest", "-q", "tests/test_bremen_import_identity.py"]
60:FROM base AS production
96:ENTRYPOINT ["python", "-m", "bremen"]
97:CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]
```

### 10.3 Compile Check

```bash
python -m compileall src tests
```

### 10.4 Test Suite

```bash
python -m pytest -q tests/test_bremen_api_server.py -v
python -m pytest -q tests/test_catalog_api_multi_model.py -v
python -m pytest -q tests/test_fastapi_routes_phase2.py -v   # new file
python -m pytest -q -k "fastapi or api_server or models or containers or h5"
python -m pytest -q
git diff --check
```

### 10.5 Docker Validation (planned, not run during planning)

```bash
docker build --target production -t bremen-prod-unchanged-check .
```

This validates that the production Docker build still succeeds and that the FastAPI dependency does not break the existing build path.

---

## 11. Non-Goals

- ❌ No production Dockerfile/ENTRYPOINT/CMD change.
- ❌ No POST routes (`/demo/api/h5/containers` upload, `/demo/api/h5/analyze`).
- ❌ No SSE or job event streaming (remains Phase 4).
- ❌ No auth redesign.
- ❌ No Pydantic request contracts in Phase 2 (response dicts only).
- ❌ No model/training changes.
- ❌ No duplicated business logic — every reusable function is imported.
- ❌ No second silent patient-name cache — the same `_patient_name_cache` object is imported and shared.
- ❌ No change to `main` branch — all FastAPI work targets `dev`.
- ❌ No removal of existing http.server handlers (they remain until full migration in later phases).

---

## 12. Stop Conditions

Implementation must halt if any of the following are true:

1. **PR0103 Phase 1 FastAPI foundation is missing.** The FastAPI app module must exist and be importable.
2. **Branch is not based on `dev`** (`git merge-base --is-ancestor origin/dev HEAD` fails).
3. **PR would target `main`.** Target must be `dev`.
4. **Production Dockerfile/ENTRYPOINT/CMD would need changes** to support Phase 2 routes.
5. **Business logic would be duplicated** — `build_model_catalog()`, `_list_s3_containers()`, `read_demo_h5_config()`, `register_source()`, `extract_patient_display_name()` must all be imported, not reimplemented.
6. **Patient-name-cache sharing decision cannot be implemented safely** — e.g., if circular imports prevent importing `_patient_name_cache` from `server.py`.
7. **Response parity cannot be tested** — must be able to compare FastAPI `TestClient` output against existing http.server output for the same state.
8. **Safety boundary would weaken** — raw S3 keys, bucket names, filesystem paths, H5 internals, PHI, raw exceptions, feature values, model coefficients, full checksums, credentials, JWT secrets, or env values would be exposed.
9. **Scope expands to POST or SSE routes.**
10. **`main` would be targeted or modified.**

---

## 13. File Changes Summary (Implementation PR)

| File | Action | Reason |
|---|---|---|
| `pyproject.toml` | Add `fastapi`, `uvicorn[standard]` | Phase 1 requirement — new dependency |
| `src/bremen/api/fastapi_app.py` | **Create** | Phase 1 — FastAPI app instance |
| `src/bremen/api/fastapi_routes_demo.py` | **Create** | Phase 2 — two GET route handlers |
| `tests/test_fastapi_routes_phase2.py` | **Create** | Phase 2 — TestClient parity tests |
| `src/bremen/api/server.py` | No change | Existing handlers remain |
| `Dockerfile` | No change | Production target untouched |
| `tests/test_bremen_api_server.py` | No change | Existing tests must still pass |

---

Implementation agent: coder
