# Implementation Report: PR0104A — FastAPI Phase 1 Foundation

**Branch**: `0104a-fastapi-phase1-foundation`
**Base branch**: `dev`
**PR target**: `dev`
**Date**: 2026-07-29
**Status**: IMPLEMENTATION COMPLETE

---

## Files Changed

### New files (2)
- `src/bremen/api/fastapi_app.py` — Isolated FastAPI app factory with Phase 1 routes
- `tests/test_bremen_fastapi_phase1.py` — 27 tests for FastAPI Phase 1 foundation

### Modified files (15)
- `pyproject.toml` — Added `fastapi>=0.110`, `uvicorn>=0.27` to dependencies; `httpx>=0.27` to dev dependencies
- `requirements.txt` — Added `fastapi>=0.110`, `uvicorn>=0.27`, `httpx>=0.27`
- `tests/test_bremen_api_server.py` — Removed 5 obsolete server-spawning /health and /model/version tests
- `tests/test_bremen_config_governance.py` — Updated FastAPI governance test from "deferred" to "Phase 1 foundation"
- `tests/test_bremen_converter_preprocessing_boundary.py` — Updated `TestFastAPIDeferred` to `TestFastAPIFoundationOrDeferred`
- `tests/test_bremen_preprocessing_source_reconciliation.py` — Updated `TestNoFastAPI` to `TestFastAPIMentioned`
- `tests/test_bremen_product_input_pipeline_contract.py` — Updated `TestFastAPIDeferred` to `TestFastAPIFoundationOrDeferred`
- `docs/adr/0011-config-governance-gates.md` — Updated FastAPI boundary from "deferred" to "Phase 1 foundation on dev"
- `docs/adr/0012-system-of-record-boundary.md` — Updated FastAPI position
- `docs/converter_preprocessing_boundary.md` — Updated FastAPI position and boundary table
- `docs/feature_artifact_ingestion_boundary.md` — Updated FastAPI position
- `docs/feature_artifact_prediction_flow.md` — Updated FastAPI position
- `docs/preprocessing_source_reconciliation.md` — Updated FastAPI position
- `docs/product_input_pipeline_contract.md` — Updated FastAPI position
- `docs/release_readiness_operator_notes.md` — Updated FastAPI non-goals
- `docs/repository_cleanup.md` — Updated FastAPI status

---

## Phase 1 Scope

### FastAPI App Module
- `src/bremen/api/fastapi_app.py` — `create_fastapi_app(version=None)` factory
- Returns FastAPI app with title "Bremen API (FastAPI Phase 1)"
- OpenAPI/docs disabled (no Pydantic schemas yet)
- Global exception handler prevents raw trace leaks

### Routes Implemented
1. `GET /health` — status, service, version, timestamp, model_ready
2. `GET /model/version` — model_configured, model_version, model_checksum, feature_schema_version, threshold_version, threshold_value, qc_criteria_version, model_status

### Business Logic Reused
- Health route reuses `bremen.api.app.handle_health()`
- Model version route reuses `bremen.api.app.handle_model_version()`
- Response shapes match `HealthResponse` and `ModelVersionResponse` from `bremen.api.schemas`
- Tests verify parity: `test_health_multi_model.py` (4 tests) and `test_model_version_multi_model.py` (4 tests) test multi-model business logic directly

---

## Coexistence Strategy

- FastAPI app exists isolated alongside production http.server
- Production http.server routes untouched
- Production Dockerfile unchanged: ENTRYPOINT `["python", "-m", "bremen"]`, CMD `["serve", "--host", "0.0.0.0", "--port", "8080"]`
- No production traffic routed to FastAPI
- FastAPI app used only via TestClient in tests

---

## Dependencies Added

| Package | Version | Location | Purpose |
|---------|---------|----------|---------|
| `fastapi` | `>=0.110` | pyproject.toml, requirements.txt | FastAPI web framework |
| `uvicorn` | `>=0.27` | pyproject.toml, requirements.txt | ASGI server (future use) |
| `httpx` | `>=0.27` | pyproject.toml (dev), requirements.txt | Required by starlette TestClient |

---

## Governance Updated

Changed from "FastAPI is deferred" to "FastAPI Phase 1 foundation started on dev as an isolated side-by-side transport path."

### Tests Updated
| Test File | Old Class | New Class |
|-----------|-----------|-----------|
| test_bremen_config_governance.py | test_adr_0011_mentions_fastapi_deferred | test_adr_0011_mentions_fastapi_foundation |
| test_bremen_converter_preprocessing_boundary.py | TestFastAPIDeferred | TestFastAPIFoundationOrDeferred |
| test_bremen_preprocessing_source_reconciliation.py | TestNoFastAPI | TestFastAPIMentioned |
| test_bremen_product_input_pipeline_contract.py | TestFastAPIDeferred | TestFastAPIFoundationOrDeferred |

### Docs Updated
All governance docs (ADR-0011, ADR-0012, converter boundary, product pipeline contract, preprocessing recon, feature artifact prediction flow, feature artifact ingestion boundary, release readiness operator notes, repository cleanup) now state FastAPI Phase 1 foundation is allowed in the isolated module on dev only.

---

## Server-Spawning Tests Removed or Replaced

### Tests removed from `tests/test_bremen_api_server.py` (5 tests)

| Test | Reason for removal |
|------|-------------------|
| `TestHealth.test_health_returns_200` | Server-spawning; covered by FastAPI TestClient test_health_returns_200 |
| `TestHealth.test_health_content_type` | Server-spawning; covered by FastAPI TestClient test_health_has_expected_fields |
| `TestModelVersion.test_model_version_returns_200` | Server-spawning; covered by FastAPI TestClient test_model_version_returns_200 |
| `TestModelVersion.test_model_version_content_type` | Server-spawning; covered by FastAPI TestClient test_model_version_has_expected_fields |
| `TestModelVersion.test_model_version_default_response_shape` | Server-spawning; covered by FastAPI TestClient test_model_version_has_expected_fields |

### Tests preserved (assertions not lost)
- `TestModelVersion.test_model_version_configured` — direct business logic, no server spawning
- `TestHealthLogSuppression` (3 tests) — tests http.server logging behavior, not /health shape
- `TestQueryStringRouting.test_health_with_query_string` — tests http.server query string handling
- `TestRouteErrors.test_put_on_health_returns_405` — tests http.server method routing
- `TestLegacyCompatibility` in control room tests — tests coexistence during control room operation
- `test_bremen_concurrent_server.py` — tests concurrency behavior
- `test_bremen_production_smoke.py` — tests production smoke checks

### Multi-model business logic tests (NOT removed — already direct tests)
- `test_health_multi_model.py` (4 tests) — uses `handle_health()` directly, no server
- `test_model_version_multi_model.py` (4 tests) — uses `handle_model_version()` directly, no server

---

## Confirmations

- **Production Dockerfile unchanged**: ENTRYPOINT `["python", "-m", "bremen"]`, CMD `["serve", "--host", "0.0.0.0", "--port", "8080"]` — verified
- **Production entrypoint unchanged**: `python -m bremen serve` — verified
- **No catalog routes**: No `GET /demo/api/models` or `GET /demo/api/h5/containers` in FastAPI app
- **No POST routes**: No POST endpoints in FastAPI app
- **No SSE/event streaming**: No `EventSource`, `text/event-stream`, or `UploadFile` in FastAPI app
- **No Pydantic request contracts**: No Pydantic models used in Phase 1 routes
- **No model/training code changes**: Unchanged
- **No private artifacts/H5/model files**: Unchanged
- **No Dockerfile changes**: Unchanged
- **No remaining tests start server solely for /health or /model/version**: Verified
- **Safety assertions preserved**: All removed server-spawning assertions are covered by FastAPI TestClient tests and/or direct business-logic tests

---

## Validation Results

| Command | Result |
|---------|--------|
| pytest tests/test_bremen_fastapi_phase1.py | 27 passed |
| pytest tests/test_bremen_api_server.py | 99 passed (was 104) |
| pytest tests/test_bremen_config_governance.py | 43 passed |
| pytest tests/test_bremen_converter_preprocessing_boundary.py | 40 passed |
| pytest tests/test_bremen_preprocessing_source_reconciliation.py | 36 passed |
| pytest tests/test_bremen_product_input_pipeline_contract.py | 35 passed |
| pytest tests/test_health_multi_model.py | 4 passed |
| pytest tests/test_model_version_multi_model.py | 4 passed |
| pytest (full suite) | 2871 passed, 11 skipped, 30 warnings |
| Dockerfile ENTRYPOINT/CMD check | Unchanged |
| Forbidden file check | Clean |
| Server-spawning check in FastAPI/multi-model tests | Clean |
| Route exclusion check | Clean |
| git diff --check | Clean |

---

## Blockers

None.

## Warnings

- Starlette TestClient deprecation: "install httpx2 instead" — future concern, not Phase 1 blocker.

---

## Next Required Action

PR0104B Phase 2 catalog routes implementation may start only after this PR is merged into dev.
