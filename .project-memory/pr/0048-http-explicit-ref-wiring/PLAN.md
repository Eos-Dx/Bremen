# PR 0048 — Plan: HTTP Explicit-Ref Wiring

## 1. Title / Branch / Objective

- **Title**: HTTP Explicit-Ref Wiring
- **Branch**: `0048-http-explicit-ref-wiring`
- **Objective**: Wire explicit `target_scan_ref` and `control_scan_ref` through the entire HTTP prediction path — from request schema through `handle_submit_prediction()` → `run_inference()` → `run_h5_preflight()` → preprocessing bridge → inference result/job completion. A prediction request with a calibration-sample H5 and explicit refs should execute the domain path instead of failing due to unwired layout context. No FastAPI. No inference math changes.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
4fcbec042ca08b7fd4087001acc464a1b454fc72

$ git branch --show-current
0048-http-explicit-ref-wiring

$ git status --short
(clean — no uncommitted changes)
```

Required files all present and read. PR0047 confirmed merged (precommit-review.yml: 544 tests pass, calibration preprocessing implemented, no preflight.py changes needed because PR0045 already populated `target_group_path`/`control_group_path` in `PreflightResult.metadata`).

---

## 3. Current State After PR0047

### What works
- S3 H5 input staging (PR0043)
- H5 metadata fallback (PR0044)
- H5 layout adapter boundary — canonical + calibration adapters (PR0045)
- Preflight with explicit calibration refs: `run_h5_preflight(h5_path, target_scan_ref="...", control_scan_ref="...")` (PR0045)
- `PreflightResult.metadata` contains `layout_name`, `target_group_path`, `control_group_path` (PR0045)
- Calibration sample preprocessing bridge: `run_preprocessing_bridge()` reconstructs `H5PredictionContext` from `PreflightResult.metadata` when `layout_context` is not provided (PR0047)
- `_extract_calibration_profiles()` reads `sets/set_*/integration/i` and `/q` (PR0047)

### What is broken / unwired
- `run_inference()` does **not** accept `target_scan_ref`/`control_scan_ref` — signature is `run_inference(h5_path, patient_id=None)`
- `run_inference()` calls `run_h5_preflight(h5_path)` **without refs** — refs are dropped at this boundary
- `handle_submit_prediction()` in `app.py` does **not** pass refs to `run_inference()` — `request` object has `target_scan_ref` and `control_scan_ref` but they are never forwarded
- A calibration H5 prediction request will fail because preflight is called without refs and detects a multi-patient H5 → `Ambiguous sample patient_name metadata`
- The `request` object (`PredictionRequest`) already validates refs as non-empty strings — but no layout-aware validation occurs

### The wiring gap

```
HTTP /predictions
  → validate_prediction_request(body) → PredictionRequest
    target_scan_ref = "calib_.../sample_01_..._Right"  ✓ validated
    control_scan_ref = "calib_.../sample_02_..._Left"   ✓ validated
  → handle_submit_prediction()
    → request.target_scan_ref  ✓ available
    → request.control_scan_ref ✓ available
    → run_inference(h5_path=resolved_h5_path, patient_id=...)  ✗ refs DROPPED
      → run_h5_preflight(h5_path)  ✗ refs DROPPED — preflight detects multi-patient, fails
```

---

## 4. FastAPI Deferral Note

FastAPI is **not** part of this PR. FastAPI must remain deferred until after:
- PR0048 — HTTP explicit-ref wiring (this PR)
- PR0049 — production end-to-end smoke hardening

FastAPI must eventually be a thin transport adapter only. It must not change inference, preprocessing, model loading, H5 staging, or model lifecycle.

---

## 5. Existing HTTP Prediction Path Analysis

### Current data flow

```
POST /predictions (server.py)
  → _read_json_body() → body dict
  → handle_submit_prediction(body, job_store)  # app.py
    → validate_prediction_request(body) → PredictionRequest
    → job_store.create_job(request)
    → resolve h5 input (stage or use filesystem path)
    → run_inference(h5_path=resolved_h5_path, patient_id=raw_request.get("patient_id"))
      → run_h5_preflight(h5_path)  # NO REFS
      → run_preprocessing_bridge(h5_path, preflight_result=preflight)  # preflight metadata used
      → validate + inference → result dict
    → build CompletedResult → store completed
    → return accepted response
```

### Where refs are available

| Layer | Variable | Available |
|---|---|---|
| `server.py` | `body["target_scan_ref"]` | raw dict |
| `app.py` `handle_submit_prediction()` | `request.target_scan_ref` | `PredictionRequest` object |
| `inference_handler.py` `run_inference()` | **not available** | signature has no ref params |
| `preflight.py` `run_h5_preflight()` | **available** | accepts `target_scan_ref`/`control_scan_ref` |
| `preprocessing_bridge.py` | **available** | reconstructs context from preflight metadata |

### Validation status (schemas.py)

`target_scan_ref` and `control_scan_ref` are **already** validated as non-empty strings. No change needed at schema level for basic validation.

However, no **layout-aware ref validation** exists at the HTTP layer. For example:
- Leading `/` in a ref would be caught by the adapter later, but not by schema validation
- `..` path traversal is caught by adapter validation
- Identical target/control refs are caught by adapter validation (`Target and control refs must be distinct`)

The adapter validation in `h5_layouts.py` (`_validate_ref()`) already handles all these cases. The question is whether to duplicate or rely on the adapter. **Decision**: rely on the adapter — the adapter is the single source of truth for ref validation. Schema validation ensures non-empty strings; adapter validation ensures structural correctness.

---

## 6. Request/Schema Contract Decision

### Decision: No change to schemas.py

`PredictionRequest` already has:
```python
target_scan_ref: str
control_scan_ref: str
```

`validate_prediction_request()` already validates them as non-empty strings. No new validation is needed in `schemas.py` — the adapter layer validates ref structure (no leading `/`, no `..`, distinct, existing groups).

### For calibration layout, both refs are required
This is already enforced by schema non-empty validation. No additional "calibration requires" enforcement at schema level — the adapter will fail with a clear error if refs don't resolve.

### For canonical layout, refs are validated but not used for path discovery
The `CanonicalH5LayoutAdapter` accepts `"target"` and `"contralateral"` as canonical ref values. Existing tests use these values. No change needed.

### Decision summary
- **Schema**: unchanged — `PredictionRequest` and `validate_prediction_request()` already sufficient
- **Calibration refs**: must be non-empty and valid H5 group paths (validated by adapter)
- **Canonical refs**: must be `"target"` and `"contralateral"` (validated by adapter)
- **Ref path safety**: enforced by adapter (`_validate_ref()`), not duplicated at schema layer

---

## 7. Inference Handler Signature Decision

### Decision: Add `target_scan_ref` and `control_scan_ref` parameters

```python
def run_inference(
    h5_path: str,
    patient_id: str | None = None,
    target_scan_ref: str | None = None,
    control_scan_ref: str | None = None,
) -> dict[str, Any]:
```

### Why
- `run_inference()` is the single point where `h5_path` is resolved and the inference pipeline starts
- The refs must be forwarded from here to `run_h5_preflight()`
- Adding optional params with `None` defaults preserves backward compatibility — existing callers without refs use canonical path

### Internal changes in `run_inference()`

**Before:**
```python
preflight = run_h5_preflight(h5_path)
```

**After:**
```python
preflight = run_h5_preflight(
    h5_path,
    target_scan_ref=target_scan_ref,
    control_scan_ref=control_scan_ref,
)
```

**No other changes needed** inside `run_inference()` — the preflight result metadata already contains `target_group_path` and `control_group_path` when refs are provided, and the preprocessing bridge reconstructs the layout context from preflight metadata (PR0047).

### Logging note
Add a safe log event when refs are present (without logging raw ref values):

```python
_log.info(
    "bremen.prediction.preflight.start\t"
    "stage=preflight\tstatus=started\t"
    "explicit_refs=%s",
    str(target_scan_ref is not None).lower(),
)
```

---

## 8. Preflight/Layout/Preprocessing Wiring Plan

### The wire path

```
run_inference(h5_path, target_scan_ref, control_scan_ref)
  │
  ├──→ run_h5_preflight(h5_path, target_scan_ref, control_scan_ref)
  │     → adapter.detect() → CalibrationSampleH5LayoutAdapter
  │     → adapter.resolve_prediction_context(h5_file, refs)
  │     → returns PreflightResult
  │       .patient_id = "Nova_376"
  │       .target_side = "RIGHT"
  │       .contralateral_side = "LEFT"
  │       .metadata["layout_name"] = "calibration_sample"
  │       .metadata["target_group_path"] = "/calib_.../sample_01_..._Right"
  │       .metadata["control_group_path"] = "/calib_.../sample_02_..._Left"
  │         [✓ already populated by PR0045]
  │
  ├──→ run_preprocessing_bridge(h5_path, preflight_result=preflight)
  │     → PR0047 reconstructs H5PredictionContext from metadata
  │       when layout_context is None
  │     → build_feature_table(h5_path, layout_context=resolved_context)
  │       → _extract_calibration_profiles(f, target_group_path)  [✓ exists]
  │       → _extract_calibration_profiles(f, control_group_path) [✓ exists]
  │       → σ_l1, σ_r1, ... mahalanobis1, ... etc. [✓ unchanged]
  │     → returns BremenFeatureVector [✓ works]
  │
  ├──→ validate → inference → prediction JSON [✓ unchanged]
```

### What this PR wires
The **only** change needed is in `run_inference()` — to forward refs to `run_h5_preflight()`. Everything downstream already works because:
- `PreflightResult.metadata` already contains layout paths (PR0045)
- `run_preprocessing_bridge()` already reconstructs `H5PredictionContext` from metadata (PR0047)

### What does NOT change
- `h5_layouts.py` — already correct
- `preflight.py` — already accepts refs and populates metadata
- `preprocessing_bridge.py` — already handles context reconstruction

---

## 9. App Route/Job Execution Plan

### Changes to `app.py` `handle_submit_prediction()`

**Before:**
```python
result_dict = run_inference(
    h5_path=resolved_h5_path,
    patient_id=raw_request.get("patient_id"),
)
```

**After:**
```python
result_dict = run_inference(
    h5_path=resolved_h5_path,
    patient_id=raw_request.get("patient_id"),
    target_scan_ref=request.target_scan_ref,
    control_scan_ref=request.control_scan_ref,
)
```

The `request` object is already available and has `target_scan_ref` / `control_scan_ref`. This is a simple pass-through.

### Error handling
No changes needed. The existing error handling in `handle_submit_prediction()` catches:
- `ValueError` → propagates for HTTP 400 (validation errors before job)
- `Exception` → job marked `failed` with safe error message

Adapter validation errors (`H5ContainerError`, `H5MetadataError`, `H5PatientMismatchError`, `H5SideMismatchError`) are subclasses of `Exception` and will be caught by the existing `except Exception` clause, marking the job as `failed` with a safe error message. This is correct behavior.

### Job status invariant
No change needed. The invariant remains:
- Validation errors (schema) → no job created (HTTP 400)
- Runtime failures → job `failed` with non-empty error, `result=None`
- Success → job `completed` with non-null `result`, `error=None`

---

## 10. Server Route Parity Plan

### Changes to `server.py`

The `server.py` `_make_handler()` routes POST to `handle_submit_prediction(body, job_store)`. The handler passes the raw body dict to `handle_submit_prediction()`. No change needed in `server.py` — the app layer handles the refs from the validated `PredictionRequest`.

### Verification
- Existing server tests pass without modification
- The `do_POST` handler already calls `handle_submit_prediction()` with the body — refs flow through automatically

---

## 11. Logging/Privacy Rules

### Enforced
- No raw patient names (e.g., `Nova_376`) in any log
- No full S3 URI in logs (pre-existing invariant)
- No patient_id in logs
- No raw feature values or raw scan arrays in logs
- No secrets, account IDs, or access keys

### Allowed in logs
- `explicit_refs=true` boolean — safe, does not expose ref values
- `layout_name` — safe, standard layout identifier
- Stage/status transitions — safe
- Safe error class and truncated message (without patient identifiers)
- Job ID — safe

### New log events
Adding one new safe log field in `run_inference()` — `explicit_refs=` boolean — does not contain the ref strings themselves.

---

## 12. Backward Compatibility Plan

| Feature | Preserved? | How |
|---------|-----------|-----|
| canonical `h5_path` prediction | ✓ | `request.h5_path` still resolved and passed |
| `h5_uri` staging (PR0043) | ✓ | `stage_h5_input()` unchanged |
| model readiness check | ✓ | `ModelState.is_ready()` unchanged |
| model loading from S3 at startup | ✓ | No change |
| job status semantics | ✓ | No change to job store |
| response schemas | ✓ | `CompletedResult`, `PredictionResponse` unchanged |
| v0.1 feature schema order | ✓ | No change to bridge or schema constants |
| `run_inference()` without refs | ✓ | Default params preserve existing callers |
| `handle_submit_prediction()` API | ✓ | Same signature, backward compatible |
| server.py handler | ✓ | No server.py changes |

---

## 13. Implementation Files and Scope

### Allowed implementation files

| File | Action | Rationale |
|---|---|---|
| `src/bremen/api/inference_handler.py` | **Modified** — add `target_scan_ref` and `control_scan_ref` params to `run_inference()`; forward to `run_h5_preflight()`; add safe `explicit_refs` log field | Core wiring: refs → preflight |
| `src/bremen/api/app.py` | **Modified** — pass `request.target_scan_ref` and `request.control_scan_ref` to `run_inference()` | Refs from request → inference handler |
| `tests/test_bremen_inference_integration.py` | **Modified** — add tests for ref forwarding; update existing tests that call `run_inference()` to use new signature if needed | Test coverage |
| `tests/test_bremen_predictions.py` | **Modified** — add tests for explicit refs through submit path; verify calibration H5 with refs completes; verify generic refs on calibration H5 fail safely | Test coverage |
| `tests/test_bremen_api_skeleton.py` | **Modified only if needed** — narrow updates | Per allowed list |
| `tests/test_bremen_api_server.py` | **Modified only if needed** — narrow updates | Per allowed list |
| `tests/test_bremen_logging.py` | **Modified only if needed** — narrow assertions for new log events | Per allowed list |

### Not modified (read-only unless plan proves otherwise)

- `src/bremen/api/preflight.py` — already accepts refs
- `src/bremen/api/h5_layouts.py` — already correct
- `src/bremen/api/preprocessing_bridge.py` — already handles layout context from metadata
- `src/bremen/api/schemas.py` — already validates refs as non-empty
- `src/bremen/api/jobs.py` — no change needed
- `src/bremen/api/server.py` — no change needed; refs flow through body → app layer
- `src/bremen/h5_inputs.py` — S3 staging unchanged
- `src/bremen/api/model_state.py` — no change
- `src/bremen/model_artifacts.py` — no change
- `src/bremen/model_loader.py` — no change

---

## 14. Test Plan

All tests use synthetic H5 data. No real H5 by default.

### A. `test_run_inference_passes_explicit_refs_to_preflight`

- Monkeypatch `run_h5_preflight` to capture arguments
- Call `run_inference(h5_path="/tmp/test.h5", target_scan_ref="calib_test/sample_01", control_scan_ref="calib_test/sample_02")`
- Assert `run_h5_preflight` was called with exactly those refs

### B. `test_run_inference_passes_preflight_context_to_preprocessing`

- Monkeypatch `build_feature_table` to capture `layout_context`
- Call `run_inference()` with explicit refs on a synthetic calibration H5
- Assert `build_feature_table` is called with a non-None `layout_context`
- Assert the context has `layout_name == "calibration_sample"`

### C. `test_predictions_h5_path_with_explicit_refs_completes`

- Create synthetic calibration H5 (reuse `_create_calibration_h5` from test_bremen_h5_layouts)
- Load synthetic model
- Submit prediction with `h5_path` + explicit refs
- Assert job transitions to `completed` with non-null result
- Assert mandatory result fields present

### D. `test_predictions_h5_uri_with_explicit_refs_stages_then_runs`

- Monkeypatch `stage_h5_input` to return a path to a synthetic calibration H5
- Submit with `h5_uri` + `h5_checksum` + explicit refs
- Assert `stage_h5_input` was called
- Assert job completes with non-null result

### E. `test_predictions_generic_refs_on_calibration_sample_fails_safely`

- Create synthetic calibration H5 (multi-patient)
- Submit with generic refs `"target"` / `"contralateral"`
- Assert job fails with safe error
- Assert no auto-selection of first patient

### F. `test_predictions_missing_required_ref_for_calibration_fails_safely`

- Create synthetic calibration H5 (multi-patient)
- Submit with `target_scan_ref` for one patient but missing/invalid control ref
- Assert job fails with safe `H5ContainerError` or `H5PreflightError` message
- No raw patient identifiers in error

### G. `test_canonical_prediction_without_calibration_refs_preserved`

- Create synthetic canonical H5
- Submit with `h5_path`, `target_scan_ref="target"`, `control_scan_ref="contralateral"`
- Assert job completes with non-null result
- Assert feature schema order preserved

### H. `test_run_inference_without_refs_still_works`

- Create synthetic canonical H5
- Call `run_inference(h5_path=...)` without ref params
- Assert result dict has all mandatory fields
- Assert backward compatibility

### I. `test_logging_no_patient_or_raw_refs`

- Use caplog around inference path with calibration refs
- Assert no `Nova_376`, no `patient_id`, no full S3 URI, no raw feature values
- Assert `explicit_refs=true` logged safely

### J. Optional real H5 smoke (skipped by default)

```python
@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="Set BREMEN_H5_PREFLIGHT_SMOKE_PATH to enable",
)
def test_prediction_with_explicit_refs_on_real_h5():
    """Submit with real H5 and explicit refs.
    
    Explicit refs:
      target_scan_ref = "calib_20260128_132622/sample_01_20260128_Nova_376_Right"
      control_scan_ref = "calib_20260128_132622/sample_02_20260128_Nova_376_Left"
    
    NOTE: Real H5 may fail at later stages (model compatibility).
    Only assert no "Ambiguous sample patient_name metadata" error.
    """
```

---

## 15. Validation Checklist

```bash
# Follow AGENT_TEST_DEBUGGING_RULES.md — no tail/head on failing pytest

# Compile
python -m compileall src tests

# Test runs (in order)
python -m pytest -q tests/test_bremen_inference_integration.py -v
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_api_skeleton.py -v
python -m pytest -q tests/test_bremen_api_server.py -v
python -m pytest -q tests/test_bremen_calibration_preprocessing.py -v
python -m pytest -q tests/test_bremen_h5_layouts.py -v
python -m pytest -q tests/test_bremen_h5_preflight.py -v
python -m pytest -q tests/test_bremen_logging.py -v
python -m pytest -q

# Verify ref wiring through the layers
grep -n "target_scan_ref\|control_scan_ref\|run_inference\|run_h5_preflight" \
  src/bremen/api/inference_handler.py src/bremen/api/app.py

# No FastAPI dependency
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n \
  src/bremen tests requirements.txt pyproject.toml || true

# No forbidden changes
git diff --name-only -- requirements.txt pyproject.toml Dockerfile \
  Dockerfile.training infra .github src/bremen/training docs/adr ROADMAP.md

# No artifact leaks
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" \
  -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) \
  -not -path "./.git/*" -not -path "./venv/*" -print

# Confidence check: verify the wire path
grep -n "target_scan_ref=request\.\|control_scan_ref=request\." src/bremen/api/app.py
grep -n "target_scan_ref=target_scan_ref\|control_scan_ref=control_scan_ref" \
  src/bremen/api/inference_handler.py
```

---

## 16. Forbidden Changes

The implementation agent MUST NOT:

1. Add FastAPI, uvicorn, starlette, or any web framework dependency
2. Modify `requirements.txt` or `pyproject.toml`
3. Modify `Dockerfile` or `Dockerfile.training`
4. Modify `infra/**` or `.github/**`
5. Modify `src/bremen/training/**`
6. Modify `src/bremen/api/preflight.py` — already accepts refs
7. Modify `src/bremen/api/h5_layouts.py` — no change needed
8. Modify `src/bremen/api/preprocessing_bridge.py` — no change needed; PR0047 handles context
9. Modify `src/bremen/api/schemas.py` — no change needed; refs already validated as non-empty
10. Modify `src/bremen/api/jobs.py` — no change needed
11. Modify `src/bremen/api/server.py` — no change needed; refs flow through body
12. Modify `src/bremen/h5_inputs.py` — S3 staging unchanged
13. Modify `src/bremen/api/model_state.py` — no change
14. Modify `docs/adr/**` or `ROADMAP.md`
15. Commit real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` artifacts
16. Commit secrets, account IDs, access keys, registry URLs
17. Change inference math or feature schema order
18. Change model loading or S3 staging implementation
19. Log raw patient identifiers, raw feature values, or raw scan arrays
20. Introduce clinical claims

---

## 17. Non-Goals

- No FastAPI or HTTP transport migration
- No App Runner redeploy or production smoke
- No model retraining or model package change
- No config governance
- No Matador integration
- No decision report wrapper
- No clinical claims
- No changes to preflight.py (already accepts refs)
- No changes to h5_layouts.py (already correct)
- No changes to preprocessing_bridge.py (already handles context)
- No changes to schemas.py (refs already validated)
- No changes to server.py (refs flow through body layer)
- No schema ref validation beyond non-empty (adapter validates structure)

---

## 18. Rollback Plan

1. **Immediate rollback**: `git revert HEAD` on `0048-http-explicit-ref-wiring` branch
2. Verify revert:
   - `python -m pytest -q tests/test_bremen_inference_integration.py -v`
   - `python -m pytest -q tests/test_bremen_predictions.py -v`
   - `python -m pytest -q tests/test_bremen_api_skeleton.py -v`
   - `python -m pytest -q tests/test_bremen_api_server.py -v`
   - `python -m pytest -q`
3. Open revert PR with label `revert/0048`

### Partial rollback (app.py only)

If the `app.py` changes cause issues, revert only `app.py` and `inference_handler.py` separately. The test additions can remain for future wiring attempts.

---

## 19. Implementation Agent Assignment

**Implementation agent**: coder

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. The implementation is minimal — only two source files need changes (`inference_handler.py` and `app.py`) plus tests. This is by design: PR0045 and PR0047 already laid the groundwork.
2. The `run_inference()` signature change adds two optional params — all existing callers without refs continue to use canonical path. Zero regression risk.
3. No schema, preflight, h5_layouts, or preprocessing_bridge changes needed — verify this before implementation to avoid unnecessary work.
4. Test J (real H5 smoke) must be skipped by default — the real H5 may still fail at model compatibility, which is expected and addressed by PR0049.

FILES CHANGED:
- `.project-memory/pr/0048-http-explicit-ref-wiring/PLAN.md` — written

FASTAPI DEFERRAL SUMMARY:
FastAPI deferred until after PR0048 and PR0049. Must be thin transport adapter only — no inference, preprocessing, model, or lifecycle changes.

CURRENT STATE SUMMARY:
S3 staging ✓, metadata fallback ✓, layout adapter ✓, preflight with refs ✓, calibration preprocessing ✓. Gap: refs are validated at HTTP layer but dropped before reaching `run_inference()` / `run_h5_preflight()`. Calibration H5 requests fail at preflight due to missing refs.

HTTP PATH ANALYSIS:
`POST /predictions` → `handle_submit_prediction()` → `PredictionRequest` (refs validated) → `run_inference(h5_path, patient_id)` → refs DROPPED → `run_h5_preflight(h5_path)` → fails. Fix: forward `request.target_scan_ref` and `request.control_scan_ref` through `run_inference()` to `run_h5_preflight()`.

REQUEST CONTRACT DECISION:
No schema changes. `target_scan_ref` and `control_scan_ref` already validated as non-empty strings in schemas.py. Ref structure validation (no leading `/`, no `..`, distinct, existing groups) is handled by adapter layer — not duplicated at HTTP layer.

INFERENCE HANDLER DECISION:
Add `target_scan_ref: str | None = None` and `control_scan_ref: str | None = None` to `run_inference()`. Forward to `run_h5_preflight()`. Add safe `explicit_refs` boolean log field.

PREFLIGHT/PREPROCESSING WIRING SUMMARY:
Minimal change. `run_inference()` forwards refs to `run_h5_preflight()`. PR0045 already populates `PreflightResult.metadata` with `layout_name`, `target_group_path`, `control_group_path`. PR0047 already reconstructs `H5PredictionContext` from metadata in `run_preprocessing_bridge()`. The entire pipeline works once refs reach preflight.

APP/JOB EXECUTION SUMMARY:
One line change in `app.py`: pass `request.target_scan_ref` and `request.control_scan_ref` to `run_inference()`. Error handling unchanged — adapter exceptions become failed jobs with safe messages.

SERVER PARITY SUMMARY:
No changes to `server.py`. The `do_POST` handler passes body to `handle_submit_prediction()` — refs flow through automatically.

LOGGING/PRIVACY SUMMARY:
Safe `explicit_refs=true/false` boolean in preflight log event. No raw ref values, patient identifiers, or S3 URIs in logs. No new log events — only existing events extended with safe field.

BACKWARD COMPATIBILITY SUMMARY:
All features preserved: canonical h5_path, h5_uri staging, model readiness, model loading, job semantics, response schemas, feature schema order. Default param values ensure existing callers unchanged.

TEST PLAN SUMMARY:
10 tests: A (ref forwarding to preflight), B (context reaches preprocessing), C (h5_path + refs completes), D (h5_uri + refs stages + runs), E (generic refs on calibration fail safely), F (missing refs fail safely), G (canonical preserved), H (no-refs backward compat), I (logging safety), J (opt-in real H5 smoke).

VALIDATION PLAN:
Follow AGENT_TEST_DEBUGGING_RULES.md. Compile all. Run 8 test suites. Verify ref wiring at app layer and inference handler. No FastAPI deps. No forbidden changes.

BOUNDARY CONFIRMATIONS:
| Module | Changed? | Rationale |
|---|---|---|
| `inference_handler.py` | YES | Add ref params, forward to preflight |
| `app.py` | YES | Pass refs from request to run_inference |
| `preflight.py` | No | Already accepts refs |
| `h5_layouts.py` | No | Already correct |
| `preprocessing_bridge.py` | No | Already handles context from metadata |
| `schemas.py` | No | Refs already validated |
| `jobs.py` | No | No change |
| `server.py` | No | Body → app layer, refs flow through |
| `h5_inputs.py` | No | S3 staging unchanged |
| All other files | No | Forbidden list |

IMPLEMENTATION AGENT ASSIGNMENT: coder
