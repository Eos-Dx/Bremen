# PR 0042 — Plan: Wire Prediction Job Execution

## 1. Title / Branch / Objective

- **Title**: Wire prediction job execution — fix silent completed/null bug
- **Branch**: `0042-wire-prediction-job-execution`
- **Objective**: Ensure `POST /predictions` actually runs the inference pipeline for every accepted job, never marks a job completed with `result=null, error=null`, and passes the correct H5 path to `run_inference`.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
2f7cb40a6f1bb6cb6e17263c4d9838251767def2

$ git branch --show-current
0042-wire-prediction-job-execution

$ git status --short
(clean — no uncommitted changes)
```

Required source files all present:
- `src/bremen/api/app.py` ✓
- `src/bremen/api/inference_handler.py` ✓
- `src/bremen/api/jobs.py` ✓
- `src/bremen/api/schemas.py` ✓
- `src/bremen/api/server.py` ✓

---

## 3. Production Smoke Evidence

Production App Runner smoke confirmed the bug:

```
POST /predictions with:
  { "h5_path": "/tmp/test.h5", "target_scan_ref": "target", "control_scan_ref": "control" }

→ 202 accepted
→ Polling: { "status": "completed", "result": null, "error": null }
```

Application logs show:
```
request.received
→ job.created
→ job.completed
→ request.accepted
```

**Missing pipeline logs** (proves inference never ran):
- `bremen.prediction.h5.received` — absent
- `bremen.prediction.preflight.start` — absent
- `bremen.prediction.preprocessing.start` — absent
- `bremen.prediction.inference.start` — absent

---

## 4. Root Cause Statement

**File**: `src/bremen/api/app.py` — function `handle_submit_prediction()`

**Bug A — Silent inference skip guard (lines ~58-60):**

```python
if not raw_request.get("target_scan_ref", "").startswith("/"):
    # Non-filesystem reference — accept job but skip inference
    job_store.update_status(record.job_id, STATUS_COMPLETED)
```

This guard treats any `target_scan_ref` that does **not** start with `/` (i.e. every non-filesystem reference such as `"target"`, `"scan:tgt/001"`) as a signal to skip inference entirely and mark the job completed with **no result and no error**. Production sends `"target_scan_ref": "target"`, which does not start with `/`, so the guard triggers silently.

**Bug B — Wrong field passed to `run_inference` (line ~67):**

```python
result_dict = run_inference(
    raw_request.get("target_scan_ref", ""),   # ← BUG: passes "target" instead of H5 path
    patient_id=raw_request.get("patient_id"),
)
```

`run_inference()` expects its first positional argument to be `h5_path` (a filesystem path to an H5 container). But `target_scan_ref` is a scan reference string (e.g. `"target"`, `"scan:tgt/001"`), not a filesystem path. Even if Bug A were removed, inference would fail trying to open a non-existent file named `"target"` or `"scan:tgt/001"`.

**Combined effect**: Production smoke returns `completed/result=null/error=null` because Bug A silently skips inference. Bug B would cause a hard crash if Bug A were removed but `target_scan_ref` were still passed as the H5 path.

---

## 5. Request Schema Findings

**File**: `src/bremen/api/schemas.py`

### `PredictionRequest` dataclass (line ~83):

```python
@dataclass
class PredictionRequest:
    target_scan_ref: str
    control_scan_ref: str
    request_id: str | None = None
```

**Critical finding**: There is **no `h5_path` field**. The schema only captures `target_scan_ref`, `control_scan_ref`, and `request_id`.

### `validate_prediction_request()` (line ~98):

Validates only `target_scan_ref`, `control_scan_ref`, and `request_id`. Does **not** reject unknown fields — `h5_path` passes through silently in `raw_request` but is not surfaced in the validated `PredictionRequest` object.

### Impact on fix:

Since `request.h5_path` does not exist on the validated `PredictionRequest`, the fix **must use `raw_request["h5_path"]`** (with explicit inline validation). The `schemas.py` module needs a separate decision on whether to add `h5_path` to `PredictionRequest` — this PR handles the wiring fix; schema extension is deferred as a non-goal (flagged below as a warning).

### Key validation: `target_scan_ref` is NOT an H5 path

Current schema defines `target_scan_ref` as a **scan reference string** (e.g. `"target"`, `"scan:tgt/001"`, `"urn:scan:xyz"`). It is not, and was never intended to be, a filesystem path to an H5 container. This is confirmed by the production smoke and the `PredictionRequest` field name. **Do not pass `target_scan_ref` to `run_inference` as the H5 path.**

---

## 6. Exact `app.py` Fix

### Changes to `src/bremen/api/app.py` — `handle_submit_prediction()`

**Remove** (delete entirely):
1. The `startswith("/")` guard block (Bug A).
2. The `update_status(record.job_id, STATUS_COMPLETED)` call that skips inference.
3. The `run_inference(raw_request.get("target_scan_ref", ""), ...)` call (Bug B).

**Add**:
1. Extract `h5_path` from `raw_request` and validate it is a non-empty string:
   ```python
   h5_path = raw_request.get("h5_path")
   if not h5_path or not isinstance(h5_path, str):
       raise ValueError("h5_path is required and must be a non-empty string")
   ```
2. Always attempt `run_inference(h5_path=h5_path, ...)` for every accepted job.
3. On success, build `CompletedResult` from the result dict and call `update_status(record.job_id, STATUS_COMPLETED, result=completed_result)`.
4. On failure (exception), call `update_status(record.job_id, "failed", error=str(exc))` — preserving the existing safe-failure logging.

### Pseudocode for the fixed inference block:

```python
# Always attempt inference for every accepted job
try:
    from .inference_handler import run_inference

    h5_path = raw_request.get("h5_path", "")
    if not h5_path or not isinstance(h5_path, str):
        raise ValueError("h5_path is required and must be a non-empty string")

    result_dict = run_inference(
        h5_path=h5_path,
        patient_id=raw_request.get("patient_id"),
    )

    completed_result = CompletedResult(
        prediction_id=result_dict["prediction_id"],
        model_version=result_dict["model_version"],
        model_checksum=result_dict["model_checksum"],
        feature_schema_version=result_dict["feature_schema_version"],
        threshold_version=result_dict["threshold_version"],
        threshold_value=result_dict["threshold_value"],
        qc_status=result_dict["qc_status"],
        qc_flags=result_dict["qc_flags"],
    )

    job_store.update_status(
        record.job_id,
        STATUS_COMPLETED,
        result=completed_result,
    )
except ValueError:
    raise  # Let ValueError propagate to the 400 handler in server.py
except Exception as exc:
    import logging
    _log = logging.getLogger(__name__)
    _log.error(
        "bremen.prediction.failed\t"
        "stage=prediction\tstatus=failed\t"
        "exception_class=%s\t"
        "safe_reason=%s\t"
        "job_id=%s",
        type(exc).__name__,
        str(exc)[:200],
        record.job_id,
    )
    job_store.update_status(
        record.job_id,
        "failed",
        error=str(exc),
    )
```

### Key detail: `ValueError` (missing/invalid h5_path) must propagate

The `h5_path` validation must raise `ValueError` (not caught by `except Exception`) so that `server.py`'s `do_POST` returns HTTP 400 rather than 202-accepted-then-failed. This gives the caller an immediate validation error instead of a silently accepted-then-failed job.

Alternatively, the fix could catch `ValueError` and use the same failure path with `update_status(record.job_id, "failed", error=...)` to keep the job response consistent. **Decision required**: Use immediate HTTP 400 rejection (preferred for API cleanliness) or accept-then-fail (consistent with async pattern). Implementation should prefer HTTP 400 for validation errors.

---

## 7. Job Status Invariant

After this fix, the following invariant MUST hold for all prediction jobs:

| Condition | `status` | `result` | `error` |
|---|---|---|---|
| `h5_path` missing/invalid | `failed` | `None` | Non-empty error message |
| H5 file does not exist | `failed` | `None` | Non-empty error message |
| Preflight/preprocessing/inference fails | `failed` | `None` | Non-empty error message |
| Inference succeeds | `completed` | Non-null dict with all mandatory fields | `None` |

**Invariant to enforce in tests:**
- No job may have `status == "completed"` and `result == None` simultaneously.
- No job may have `status == "failed"` and `error == None` (or `error == ""`) simultaneously.

---

## 8. Test Plan

### Test file: `tests/test_bremen_predictions.py` (new file)

All tests use `handle_submit_prediction` directly or via the HTTP server with synthetic model loaded.

#### 8.1 `test_prediction_job_fails_gracefully_on_missing_h5_path`

- POST `/predictions` with `{ "h5_path": "/tmp/nonexistent-smoke-test.h5", "target_scan_ref": "target", "control_scan_ref": "control" }`
- Poll job until `status != "accepted"`
- Assert: `status == "failed"`, `error` is non-empty, `result is None`
- Assert: logs include `bremen.prediction.h5.received` and failure path

#### 8.2 `test_prediction_job_never_completes_with_null_result`

- Submit prediction that fails early (missing / nonexistent H5)
- Poll job
- Assert: if `status == "completed"`, `result is not None`
- Assert: if `status == "failed"`, `error` is non-empty
- Assert: status is never `"completed"` with `result=None` and `error=None`

#### 8.3 `test_prediction_execution_calls_run_inference_with_h5_path`

- Monkeypatch `run_inference` in app's import path
- Submit `{ "h5_path": "/tmp/test-input.h5", "target_scan_ref": "target", "control_scan_ref": "control" }`
- Assert monkeypatched `run_inference` was called **exactly once** with `h5_path == "/tmp/test-input.h5"`
- Assert it was **not** called with `"target"` or any `target_scan_ref` value

#### 8.4 `test_prediction_job_completes_with_result_when_run_inference_succeeds`

- Monkeypatch `run_inference` to return a valid `result_dict`
- Submit request
- Poll job
- Assert: `status == "completed"`, `result is not None`, `error is None`
- Assert: result contains all `COMPLETED_RESULT_FIELDS`
- Assert: `bremen.job.completed` log event exists

#### 8.5 `test_prediction_job_fails_on_missing_h5_path_field`

- POST `/predictions` with `{ "target_scan_ref": "target", "control_scan_ref": "control" }` (no `h5_path`)
- Assert: HTTP 400 (if using server path) or `ValueError` (if using handler directly)
- Assert: error message mentions `h5_path`

#### 8.6 `test_prediction_job_fails_on_empty_h5_path`

- POST `/predictions` with `{ "h5_path": "", "target_scan_ref": "target", "control_scan_ref": "control" }`
- Assert: HTTP 400 or `ValueError`
- Assert: error message mentions `h5_path`

#### 8.7 `test_prediction_job_with_real_h5_opt_in` (optional)

- Skip unless `BREMEN_REAL_H5_PATH` env var is set
- POST with `h5_path=os.environ["BREMEN_REAL_H5_PATH"]`
- Assert completed only if fixture is compatible
- Skipped by default; no real H5 committed

### Existing test file updates needed

#### `tests/test_bremen_api_skeleton.py`

**Tests that will break** (will expect `status in ("accepted", "completed")` but get `"failed"`):

1. `test_submit_stores_job` (line ~220): `assert job.status in ("accepted", "completed")` → now `"failed"` because no `h5_path` provided
2. `test_get_known_job_returns_status` (line ~248): same assertion → now `"failed"`

**Fix approach**: Either:
  a. Add `h5_path` and create synthetic H5 files via `tmp_path` fixture, or
  b. Monkeypatch `run_inference` in `handle_submit_prediction` to return a valid result, or  
  c. Update assertions to accept `"failed"` as a valid status for requests without `h5_path`

**Recommendation**: Option (b) — mock `run_inference` in the skeleton tests so the job submission flow assertions remain valid without real H5 artifacts. Update `_load_synthetic_model()` tests to include `h5_path` pointing to a synthetic H5 in `tmp_path`.

**Note**: `test_bremen_api_skeleton.py` is not in the explicit allowed-write list but contains tests that will fail. The implementation agent should verify and update these tests under the "tests pass" mandate.

#### `tests/test_bremen_api_server.py` — no changes needed

Tests in `TestSubmitPrediction` only check the POST response (202, has job_id, has poll link). They don't poll for final status. These will continue to pass because `handle_submit_prediction` still returns 202 regardless of inference outcome.

---

## 9. Non-Goals

This PR explicitly does NOT address:

- S3 H5 input ingestion / remote H5 download
- Upload handling
- Async queue / background worker
- Matador integration / result reporting
- Changes to `inference_handler.py` — `run_inference()` signature and behavior are already correct
- Changes to `preflight.py` — preflight logic is fine
- Changes to `preprocessing_bridge.py` — bridge logic is fine
- API response schema changes for `PredictionStatusResponse` — shape remains the same
- Adding `h5_path` to `PredictionRequest` dataclass (deferred; flagged as warning)
- Clinical claim changes
- Model package format changes
- Training pipeline changes

---

## 10. Validation Checklist (implementation phase)

```bash
# Git state
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile check
python -m compileall src tests

# Test runs
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_logging.py
python -m pytest -q tests/test_bremen_inference_integration.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q

# Guard removal verification
grep -n "startswith" src/bremen/api/app.py
# Must return nothing — the old skip guard must be deleted

# Completion verification
grep -n "STATUS_COMPLETED" src/bremen/api/app.py
# Must show completion only in code path that passes result=completed_result

# Field verification
grep -n "run_inference" src/bremen/api/app.py
# Must show run_inference receives h5_path, not target_scan_ref

# Null result check
grep -n "result=None\|result=null" src/bremen/api/app.py
grep -n "result=None\|result=null" tests/test_bremen_predictions.py 2>/dev/null || true

# Forbidden changes check
git diff --name-only -- docs/adr ROADMAP.md docs/architecture.md \
  src/bremen/api/inference_handler.py \
  src/bremen/api/preflight.py \
  src/bremen/api/preprocessing_bridge.py \
  src/bremen/training \
  .github Dockerfile infra requirements.txt pyproject.toml
# Must return nothing
```

---

## 11. Forbidden Changes

The implementation agent MUST NOT:

1. Modify `src/bremen/api/inference_handler.py` — `run_inference()` signature and behavior are correct
2. Modify `src/bremen/api/preflight.py`
3. Modify `src/bremen/api/preprocessing_bridge.py`
4. Modify `src/bremen/training/**` — any training code
5. Modify `docs/adr/`, `ROADMAP.md`, `docs/architecture.md`
6. Modify `.github/`, `Dockerfile`, `infra/`, `requirements.txt`, `pyproject.toml`
7. Commit real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` artifacts
8. Commit secrets, account IDs, or access keys
9. Change `PredictionRequest` schema fields without explicit human approval
10. Change `PredictionStatusResponse` response shape
11. Add S3/upload/async-queue functionality
12. Introduce clinical claim language changes

---

## 12. Rollback Plan

If the fix introduces regressions:

1. **Immediate rollback**: `git revert HEAD` on `0042-wire-prediction-job-execution` branch
2. Verify revert via:
   - `python -m pytest -q tests/test_bremen_api_skeleton.py` — skeleton tests pass
   - `python -m pytest -q tests/test_bremen_api_server.py` — server tests pass
   - `python -m pytest -q tests/test_bremen_logging.py` — logging tests pass
3. Open revert PR with label `revert/0042`
4. Document the failure mode in the revert PR description

---

## 13. Blockers

**None at plan stage.** All required files exist, root cause is identified, fix path is clear.

---

## 14. Warnings

1. **Schema gap detected**: `schemas.py` has no `h5_path` field. This fix uses `raw_request["h5_path"]` with inline validation. A future PR should add `h5_path` to `PredictionRequest` and `validate_prediction_request()`. This is deferred as a non-goal.

2. **Skeleton tests will break**: `test_bremen_api_skeleton.py` has two tests that assert `status in ("accepted", "completed")`. After removing the skip guard, requests without `h5_path` will fail and return `status == "failed"`. The implementation agent must update these tests (add `h5_path` + synthetic H5, or mock `run_inference`).

3. **`ValueError` propagation decision**: The plan recommends raising `ValueError` for missing/invalid `h5_path` to get HTTP 400 from `server.py`. Alternative: catch and mark job as failed. The implementation should confirm this decision with the reviewer.

---

## 15. Files Changed (Plan)

| File | Action |
|---|---|
| `src/bremen/api/app.py` | Modified — remove skip guard, inline h5_path validation, always run inference |
| `tests/test_bremen_predictions.py` | **New** — prediction job execution tests |
| `tests/test_bremen_api_skeleton.py` | Modified — update tests that break due to guard removal |
| `tests/test_bremen_api_server.py` | Modified only if existing prediction server tests need updating (see allowed list) |
| `tests/test_bremen_logging.py` | Modified only if log assertions need updating (see allowed list) |

---

## 16. Plan Summary

| Aspect | Detail |
|---|---|
| **Root cause** | Two bugs in `handle_submit_prediction()`: (1) `startswith("/")` guard skips inference silently, (2) `target_scan_ref` passed instead of `h5_path` to `run_inference` |
| **Request schema findings** | `PredictionRequest` has no `h5_path` field; fix must use validated `raw_request["h5_path"]` |
| **Fix** | Remove guard, add h5_path validation, pass h5_path to run_inference, preserve failure path |
| **Invariant** | `completed` ⇒ `result != None`. `failed` ⇒ `error != None` and non-empty. Never `completed` with both null. |
| **Test coverage** | 7 new tests (5 mandatory + 2 validation + 1 optional), plus updates to 2 existing skeleton tests |
| **Non-goals confirmed** | No inference_handler/preflight/preprocessing changes. No schema changes. No S3/async. No training. |

---

## 17. Implementation Agent Assignment

**Implementation agent**: coder

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. `schemas.py` has no `h5_path` field — fix uses `raw_request["h5_path"]`; schema extension deferred
2. `test_bremen_api_skeleton.py` has 2 tests that will break — must be updated during implementation
3. `ValueError` propagation for missing `h5_path` needs reviewer confirmation (HTTP 400 vs accept-then-fail)

FILES CHANGED:
- `src/bremen/api/app.py` — modified
- `tests/test_bremen_predictions.py` — new
- `tests/test_bremen_api_skeleton.py` — modified (tests need update)
- `tests/test_bremen_api_server.py` — possibly modified if prediction server tests need update
- `tests/test_bremen_logging.py` — possibly modified if log assertions need update

PLAN SUMMARY: Remove the `startswith("/")` guard that silently skips inference. Replace with inline `h5_path` validation from `raw_request`. Always pass `h5_path` (not `target_scan_ref`) to `run_inference`. Ensure every completed job has a non-null result and every failed job has a non-empty error. Add 7 new tests covering missing H5, nonexistent H5, correct field passing, success path, and invariant enforcement.

ROOT CAUSE: Two bugs in `handle_submit_prediction()` — (A) a `startswith("/")` guard on `target_scan_ref` silently marks jobs completed with null result/error when the reference is not a filesystem path; (B) `run_inference` receives `target_scan_ref` instead of the actual H5 path. Combined effect: every production request returns `completed` with `result=null, error=null`.

REQUEST SCHEMA FINDINGS: `PredictionRequest` (schemas.py) has `target_scan_ref`, `control_scan_ref`, `request_id` — no `h5_path` field. `validate_prediction_request()` ignores unknown fields. The fix must extract `h5_path` from `raw_request` with inline validation.

FIX SUMMARY: (1) Delete the `startswith("/")` guard block entirely. (2) Add inline validation: `h5_path` from `raw_request` must be a non-empty string. (3) Always call `run_inference(h5_path=..., patient_id=...)`. (4) On success: build `CompletedResult` and update with result. (5) On failure: update with non-empty error. (6) `ValueError` for missing/invalid `h5_path` propagates as HTTP 400.

JOB STATUS INVARIANT: `completed` ⇒ `result != None` (never null). `failed` ⇒ `error != None` and non-empty. No job may be `completed` with `result=None, error=None`.

TEST PLAN SUMMARY: 7 test cases in `tests/test_bremen_predictions.py` covering missing H5 (HTTP 400), nonexistent H5 (failed), field correctness (monkeypatch), success path (completed with result), invariant enforcement (no completed/null), and optional real-H5 smoke. Plus updates to 2 breaking tests in `test_bremen_api_skeleton.py`.

BOUNDARY CONFIRMATIONS: No changes to inference_handler.py, preflight.py, preprocessing_bridge.py. No schema changes (deferred). No S3/async/upload/training changes. No clinical claim changes.

IMPLEMENTATION AGENT ASSIGNMENT: coder
