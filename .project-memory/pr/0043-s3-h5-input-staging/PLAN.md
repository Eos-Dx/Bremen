# PR 0043 — Plan: S3 H5 Input Staging for Predictions

## 1. Title / Branch / Objective

- **Title**: S3 H5 input staging for predictions
- **Branch**: `0043-s3-h5-input-staging`
- **Objective**: Add production-style S3 H5 input staging so the prediction API can accept `h5_uri` (s3://) in addition to the existing `h5_path` (filesystem). Staging downloads the H5 to a local path, verifies checksum if provided, then passes the local path to the existing `run_inference()` pipeline.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
fbf64850876b2fe09d356764d304a3d213f618ec

$ git branch --show-current
0043-s3-h5-input-staging

$ git status --short
(clean — no uncommitted changes)
```

Required source files all present:
- `src/bremen/api/app.py` ✓
- `src/bremen/api/inference_handler.py` ✓
- `src/bremen/api/jobs.py` ✓
- `src/bremen/api/schemas.py` ✓
- `src/bremen/model_artifacts.py` ✓
- `tests/test_bremen_predictions.py` ✓

PR0042 is confirmed merged. Production behavior verified:
- `/predictions` with nonexistent `h5_path` returns 202, polling yields `status=failed` with non-empty error
- Inference pipeline logs are visible (`bremen.prediction.h5.received`, `bremen.prediction.failed`, `bremen.job.failed`)

---

## 3. Production Evidence from PR0042

Confirmed working in production App Runner after PR0042:
- `POST /predictions` with valid `h5_path` executes inference end-to-end
- `POST /predictions` with nonexistent `h5_path` → 202 accepted, then `status=failed` with non-empty error
- `POST /predictions` without `h5_path` → HTTP 400 (ValueError propagated)
- Job invariant holds: no job is completed with `result=None, error=None`

**Current limitation**: App Runner can only run prediction if the H5 file already exists inside the container filesystem. This is not production-realistic for a service that receives H5 files referenced by S3 URI.

---

## 4. Smoke H5 S3 Object Details

The smoke H5 object is already in place:

| Property | Value |
|---|---|
| **S3 URI** | `s3://matur-misc-uk/bremen/prediction-inputs/smoke/v0.1/aramis_real_h5_subset_20260128_5_patients.h5` |
| **SHA-256** | `0bda036f08b057d992b329f6bd6834b3bb52cb74b1f3fca3efb08dda5edf655a` |
| **ContentLength** | 40324488 |
| **ContentType** | `application/x-hdf5` |
| **ServerSideEncryption** | AES256 |
| **sha256 metadata** | `0bda036f08b057d992b329f6bd6834b3bb52cb74b1f3fca3efb08dda5edf655a` |
| **artifact_type** | `h5_smoke_input` |
| **purpose** | `bremen_prediction_smoke` |

IAM policy `BremenReadSmokeH5InputsFromS3` is already attached to role `matador-ingest-app-role-prod`, allowing `s3:GetObject` on `arn:aws:s3:::matur-misc-uk/bremen/prediction-inputs/smoke/v0.1/*`.

---

## 5. Request Contract

### Supported input modes

**A. Existing filesystem mode** (unchanged):

```json
{
  "h5_path": "/tmp/input.h5",
  "target_scan_ref": "...",
  "control_scan_ref": "...",
  "patient_id": "optional"
}
```

**B. New S3 mode**:

```json
{
  "h5_uri": "s3://bucket/key.h5",
  "h5_checksum": "sha256:<64-hex>",
  "target_scan_ref": "...",
  "control_scan_ref": "...",
  "patient_id": "optional"
}
```

### Validation rules (to be enforced in `validate_prediction_request`)

| Rule | Error |
|---|---|
| `target_scan_ref` must be present, non-empty string | `ValueError` (HTTP 400) |
| `control_scan_ref` must be present, non-empty string | `ValueError` (HTTP 400) |
| Exactly one of `h5_path` or `h5_uri` must be present | `ValueError` (HTTP 400) |
| `h5_path` and `h5_uri` must not both be present | `ValueError` (HTTP 400) |
| If `h5_uri` present: must start with `s3://` | `ValueError` (HTTP 400) |
| If `h5_checksum` present: must match `sha256:<64-hex>` pattern | `ValueError` (HTTP 400) |

### Schema changes (`src/bremen/api/schemas.py`)

Extend `PredictionRequest` dataclass:

```python
@dataclass
class PredictionRequest:
    target_scan_ref: str
    control_scan_ref: str
    h5_path: str | None = None
    h5_uri: str | None = None
    h5_checksum: str | None = None
    request_id: str | None = None
```

Update `validate_prediction_request()` to enforce all rules in the table above. The validator must check mutual exclusivity AND format before any fields are used by the application layer.

### Why schema change is needed

PR0042 left `h5_path` as an unvalidated raw field because the schema had no slot for it. With the addition of `h5_uri` and `h5_checksum`, the request contract now has structured input-source fields that require mutual-exclusivity validation. Adding them to `PredictionRequest` is the correct architectural choice — it makes the schema the source of truth for valid request shapes and simplifies `app.py`.

---

## 6. Staging Design

### New module: `src/bremen/h5_inputs.py`

A narrow, focused module for H5 input staging. Single public function.

### `stage_h5_input()` signature

```python
def stage_h5_input(
    h5_uri: str,
    staging_dir: str | Path = "/tmp/bremen-inputs",
    expected_checksum: str | None = None,
    *,
    s3_client: Any = None,
) -> Path:
    """Stage an H5 file from S3 to a local staging directory.

    Parameters
    ----------
    h5_uri : ``s3://bucket/key`` URI.
    staging_dir : Local staging directory. Defaults to ``/tmp/bremen-inputs``.
    expected_checksum : Optional ``sha256:<hex>`` or bare hex checksum.
        If provided, file is verified after download. Deletes on mismatch.
    s3_client : Injectable S3 client for testing.

    Returns
    -------
    ``Path`` to the staged file (checksum verified if expected_checksum given).

    Raises
    ------
    ValueError
        On non-s3 URI, download failure, or checksum mismatch.
    """
```

### Implementation details

1. **URI parsing**: Reuse `parse_s3_uri()` from `bremen.model_artifacts` — it validates `s3://` prefix, extracts bucket/key.
2. **Staging directory**: Create if missing. Use safe basename from S3 key (just the filename part). Reject paths with `..` or `/` in the basename component to prevent path traversal.
3. **Download**: Download to a temp file (`tempfile.mkstemp` under staging_dir). Use `boto3.client("s3")` lazily.
4. **Checksum verification**: Call `verify_file_sha256()` from `bremen.model_artifacts` if `expected_checksum` is provided. This function already deletes the file on mismatch.
5. **Finalize**: Atomic rename (via `shutil.move`) from temp to final path under staging_dir.
6. **Return**: The staged `Path`.

### Reuse of `model_artifacts.py`

The module already provides:
- `parse_s3_uri(uri)` — validates and parses `s3://bucket/key`
- `verify_file_sha256(path, expected)` — verifies checksum, deletes on mismatch, supports `sha256:` prefix

`stage_h5_input()` will import both. This avoids duplicating S3 parsing and checksum logic.

### Security / safety

- Never expose the full S3 URI in logs
- Reject non-s3 URIs early
- Download to temp file first, move to final path only after checksum passes
- Use `tempfile.mkstemp(dir=staging_dir)` to prevent path traversal
- Delete temp file on download failure or checksum mismatch

---

## 7. App Integration Plan

### Changes to `src/bremen/api/app.py` — `handle_submit_prediction()`

**New validation ordering** (fixes PR0042 concern about job creation before validation):

```
1. Validate request (schema validation including h5_path XOR h5_uri)
   → ValueError → HTTP 400 — NO JOB CREATED
2. Create job record (status = accepted)
3. Resolve input:
   a. If h5_uri: call stage_h5_input() → staged local path
   b. If h5_path: use h5_path directly
4. Call run_inference(h5_path=resolved_path, patient_id=...)
5. On success: completed with result
6. On failure: failed with non-empty error
```

**Specific code changes in `handle_submit_prediction()`:**

Replace the current `h5_path` validation block:

```python
# Current (PR0042):
h5_path = raw_request.get("h5_path", "")
if not h5_path or not isinstance(h5_path, str):
    raise ValueError("h5_path is required and must be a non-empty string")
```

With:

```python
# New (PR0043):
resolved_h5_path = None

if request.h5_uri:
    from ..h5_inputs import stage_h5_input  # noqa: PLC0415
    staged = stage_h5_input(
        request.h5_uri,
        expected_checksum=request.h5_checksum,
    )
    resolved_h5_path = str(staged)
else:
    # h5_path (guaranteed non-None by schema validation)
    resolved_h5_path = request.h5_path  # type: ignore[union-attr]
```

The `request` object (validated `PredictionRequest`) becomes the source of truth for all input fields. No more `raw_request.get("...")` for core fields.

**Important**: The `request` object returned by `validate_prediction_request()` now contains `h5_path`, `h5_uri`, and `h5_checksum` fields. The inference block uses `request.h5_path` or the staged local path, never `raw_request`.

### Job creation timing

After the schema change, `validate_prediction_request()` validates all input fields including h5_path/h5_uri mutual exclusivity. If validation fails, `ValueError` propagates to `server.py` → HTTP 400 **before any job is created**. The `job_store.create_job()` call now happens after validation and is guaranteed to have a valid request.

### Error handling

- **S3 staging failure** (network, permissions, checksum mismatch): Caught by `except Exception` → job marked `failed` with non-empty error. Same pattern as run_inference failure.
- **Checksum mismatch**: `verify_file_sha256()` raises `ValueError`, caught by `except Exception` → job marked `failed`.
- **Non-existent h5_path**: `run_inference()` raises `RuntimeError` (through preflight) → job marked `failed`. (Same as PR0042 behavior.)

---

## 8. Logging Plan

### New log events (in `src/bremen/h5_inputs.py`)

| Event | Level | Fields | When |
|---|---|---|---|
| `bremen.h5_input.stage.start` | INFO | `uri_scheme=s3`, `h5_basename=<basename>`, `checksum_present=<bool>` | Before S3 download |
| `bremen.h5_input.stage.success` | INFO | `size_bytes=<int>` | After download + checksum verify |
| `bremen.h5_input.stage.failure` | ERROR | `reason=<safe_reason>` | On download or checksum failure |
| `bremen.h5_input.checksum.verify.success` | INFO | `checksum_algorithm=sha256` | On successful checksum match |
| `bremen.h5_input.checksum.verify.failure` | ERROR | `reason=checksum_mismatch` | On checksum mismatch |

### Prohibited in logs

- Full S3 URI (log only `h5_basename`)
- `patient_id`
- Raw request body
- Secrets / AWS account IDs
- Local `/Users/` paths
- Raw checksum hex value (log only `checksum_present` boolean and `checksum_algorithm`)
- Raw feature values or scan arrays

### No duplicate events

The `h5_inputs` module emits its own `bremen.h5_input.*` events. The `model_artifacts` module already emits `bremen.model.*` events — these are separate namespaces. No duplication.

---

## 9. Job Status Invariant

Same invariant from PR0042, extended for S3 staging:

| Condition | `status` | `result` | `error` |
|---|---|---|---|
| Missing/invalid h5_path/h5_uri | No job created (HTTP 400) | N/A | N/A |
| Both h5_path and h5_uri | No job created (HTTP 400) | N/A | N/A |
| Invalid h5_uri (not s3://) | No job created (HTTP 400) | N/A | N/A |
| S3 download fails (`stage_h5_input` exception) | `failed` | `None` | Non-empty |
| Checksum mismatch | `failed` | `None` | Non-empty |
| h5_path file does not exist | `failed` | `None` | Non-empty |
| Preflight/preprocessing/inference fails | `failed` | `None` | Non-empty |
| Inference succeeds | `completed` | Non-null dict with all mandatory fields | `None` |

**Key invariant**: No validation error may create a job. No job may be completed with both `result=None` and `error=None`.

---

## 10. Test Plan

### New test file: `tests/test_bremen_h5_input_staging.py`

Tests the isolated `stage_h5_input()` function with monkeypatched boto3.

#### E. `test_h5_input_staging_downloads_s3_object`

- Monkeypatch `boto3.client("s3").download_file` to write fake content
- Call `stage_h5_input("s3://bucket/test.h5", staging_dir=tmp_path)`
- Assert: correct bucket/key passed to download
- Assert: staged path under tmp_path
- Assert: file exists and contains expected content
- Assert: no path traversal

#### F. `test_h5_input_staging_verifies_checksum_success`

- Create fake downloaded file via monkeypatch
- Call `stage_h5_input(...)` with matching `expected_checksum`
- Assert: function returns `Path` and file exists

#### G. `test_h5_input_staging_rejects_checksum_mismatch`

- Create fake downloaded file via monkeypatch
- Call `stage_h5_input(...)` with non-matching `expected_checksum`
- Assert: `ValueError` raised
- Assert: staged file is deleted (not left on disk)

#### H. `test_h5_input_staging_logs_safe_metadata` (caplog)

- Use caplog at INFO level
- Monkeypatch S3 download to succeed
- Call `stage_h5_input(...)` with checksum
- Assert: `bremen.h5_input.stage.start` present with `uri_scheme=s3`, `h5_basename`, `checksum_present=true`
- Assert: `bremen.h5_input.stage.success` present with `size_bytes`
- Assert: `bremen.h5_input.checksum.verify.success` present
- Assert: NO full S3 URI in logs
- Assert: NO patient_id in logs
- Assert: NO `/Users/` in logs

#### I. `test_h5_input_staging_rejects_non_s3_uri`

- Call `stage_h5_input("https://example.com/input.h5", staging_dir=tmp_path)`
- Assert: `ValueError` with message about s3://

### Extended existing file: `tests/test_bremen_predictions.py`

#### A. `test_prediction_accepts_s3_h5_uri_and_stages_before_inference`

- Monkeypatch `bremen.h5_inputs.stage_h5_input` to return `/tmp/staged-input.h5`
- Monkeypatch `bremen.api.inference_handler.run_inference` to return valid result
- Submit `{ "h5_uri": "s3://bucket/test.h5", "target_scan_ref": "target", "control_scan_ref": "control" }`
- Assert: `run_inference` was called with `/tmp/staged-input.h5` (the staged local path), **not** with `s3://bucket/test.h5`
- Assert: job completed with non-None result

#### B. `test_prediction_rejects_both_h5_path_and_h5_uri`

- Submit `{ "h5_path": "/tmp/a.h5", "h5_uri": "s3://bucket/b.h5", "target_scan_ref": "...", "control_scan_ref": "..." }`
- Assert: `ValueError` raised
- Assert: no job created (check `store.job_count == 0`)

#### C. `test_prediction_rejects_missing_h5_input_before_job_creation`

- Submit `{ "target_scan_ref": "...", "control_scan_ref": "..." }` (no h5_path, no h5_uri)
- Assert: `ValueError` raised
- Assert: no job created

#### D. `test_prediction_rejects_non_s3_h5_uri`

- Submit `h5_uri="https://example.com/file.h5"`
- Assert: `ValueError` raised (or HTTP 400 through server)
- Assert: no job created

#### I (opt-in). `test_prediction_with_real_s3_h5_opt_in`

- Skip unless `BREMEN_SMOKE_H5_URI` and `BREMEN_SMOKE_H5_SHA` are set
- Submit with the real S3 URI and checksum
- Poll and assert completed or failed (whichever is appropriate for the smoke H5)
- Skipped by default; no real S3 in unit tests

#### Validation ordering test

- Add assertion to `test_prediction_rejects_missing_h5_input_before_job_creation` that verifies `store.job_count == 0` — confirming no job was created for validation errors.

### Existing test compatibility

- `test_bremen_predictions.py` tests that submit with `h5_path` and `target_scan_ref`/`control_scan_ref` will continue to work unchanged, since `h5_path` is now a validated field of `PredictionRequest`.
- `test_bremen_api_server.py` tests that don't include `h5_path` will now correctly fail with HTTP 400 (ValueError), which is the correct behavior.
- No changes needed to `test_bremen_inference_integration.py`.
- `test_bremen_api_skeleton.py` tests that use `handle_submit_prediction` with only `target_scan_ref`/`control_scan_ref` will now raise `ValueError` — these tests must be updated to include `h5_path` (or mock `run_inference`). Same as PR0042 warning.

---

## 11. Non-Goals

This PR explicitly does NOT address:

- Matador integration / prediction result reporting to Matador
- Browser or file upload endpoints
- Presigned URL upload flow
- Async queue / background worker (prediction remains synchronous within POST handler)
- Changes to `inference_handler.py` — `run_inference()` receives `h5_path` as before
- Changes to `preflight.py` — preflight logic unchanged
- Changes to `preprocessing_bridge.py` — bridge logic unchanged
- Changes to `model_artifacts.py` — reused via import, not modified
- Model package changes
- Training pipeline changes
- Clinical claim changes
- Terraform/IAM changes — policy already exists
- Documentation/ADR/roadmap changes (unless explicitly requested later)
- Non-s3 URI support (e.g., HTTPS, GCS) — deferred to future PR

---

## 12. Validation Checklist (implementation phase)

```bash
# Git state
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile check
python -m compileall src tests

# Test runs
python -m pytest -q tests/test_bremen_h5_input_staging.py -v
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_logging.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_inference_integration.py
python -m pytest -q

# New code coverage
grep -n "h5_uri" src/bremen/h5_inputs.py  # must show parse, log, download
grep -n "bremen.h5_input" src/bremen/h5_inputs.py  # all 5 events present
grep -n "bremen.h5_input" tests/test_bremen_h5_input_staging.py  # log assertions

# H5 URI in app.py
grep -n "h5_uri" src/bremen/api/app.py  # must show stage_h5_input call, not passed to run_inference
grep -n "run_inference" src/bremen/api/app.py  # must show resolved_h5_path, not raw h5_uri

# No artifact leaks
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" \
  -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) \
  -not -path "./.git/*" -not -path "./venv/*" -print

# Forbidden changes
git diff --name-only -- docs/adr ROADMAP.md docs/architecture.md \
  src/bremen/api/inference_handler.py \
  src/bremen/api/preflight.py \
  src/bremen/api/preprocessing_bridge.py \
  src/bremen/training \
  .github Dockerfile infra requirements.txt pyproject.toml

# Null result check
grep -n "result=None\|result=null" src/bremen/api/app.py tests 2>/dev/null || true
```

---

## 13. Forbidden Changes

The implementation agent MUST NOT:

1. Modify `src/bremen/api/inference_handler.py` — `run_inference()` must receive `h5_path` as before
2. Modify `src/bremen/api/preflight.py`
3. Modify `src/bremen/api/preprocessing_bridge.py`
4. Modify `src/bremen/api/model_state.py`
5. Modify `src/bremen/model_artifacts.py` (import only; no changes)
6. Modify `src/bremen/api/jobs.py`
7. Modify `src/bremen/training/**`
8. Modify `docs/adr/`, `ROADMAP.md`, `docs/architecture.md`
9. Modify `.github/`, `Dockerfile`, `infra/`, `requirements.txt`, `pyproject.toml`
10. Commit real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` artifacts
11. Commit secrets, account IDs, or access keys
12. Pass `h5_uri` directly to `run_inference()` — must always stage to local path first
13. Add Matador / upload / async-queue functionality
14. Introduce clinical claim language changes
15. Require real S3 access for default unit tests

---

## 14. Rollback Plan

If the fix introduces regressions:

1. **Immediate rollback**: `git revert HEAD` on `0043-s3-h5-input-staging` branch
2. Verify revert via:
   - `python -m pytest -q tests/test_bremen_predictions.py` — PR0042 tests pass
   - `python -m pytest -q tests/test_bremen_api_server.py` — server tests pass
   - `python -m pytest -q tests/test_bremen_logging.py` — logging tests pass
   - `python -m pytest -q tests/test_bremen_inference_integration.py` — inference tests pass
3. Open revert PR with label `revert/0043`
4. Document the failure mode

### Partial rollback (schema only)

If only the S3 staging has issues, keep the schema changes (h5_path/h5_uri/h5_checksum in `PredictionRequest`) and revert only the staging integration. The schema changes are backwards-compatible — they formalise `h5_path` in the validated request object without breaking existing clients.

---

## 15. Files Changed (Plan)

| File | Action | Rationale |
|---|---|---|
| `src/bremen/api/schemas.py` | **Modified** — add `h5_path`, `h5_uri`, `h5_checksum` to `PredictionRequest`; update `validate_prediction_request()` with mutual-exclusivity rules | Required to represent the new input contract |
| `src/bremen/h5_inputs.py` | **New** — `stage_h5_input()` function for S3 H5 download + checksum verification | Narrow module; keeps S3 staging separate from model staging and API logic |
| `src/bremen/api/app.py` | **Modified** — use validated `PredictionRequest.h5_path` / `PredictionRequest.h5_uri`; call `stage_h5_input()` before `run_inference()`; move input validation before job creation | Wire S3 staging into prediction pipeline |
| `tests/test_bremen_h5_input_staging.py` | **New** — unit tests for `stage_h5_input()` (download, checksum, logging, non-s3 rejection) | Isolated coverage of staging module |
| `tests/test_bremen_predictions.py` | **Modified** — add tests for S3 URI acceptance, mutual exclusivity, validation ordering, non-s3 rejection, plus opt-in real S3 smoke | Coverage of new app.py integration paths |
| `tests/test_bremen_logging.py` | **Modified only if log assertions need update** | Per allowed list |
| `tests/test_bremen_api_server.py` | **Modified only if existing server tests need update** | Per allowed list |

---

## 16. Plan Summary

| Aspect | Detail |
|---|---|
| **Problem** | App Runner can only use filesystem H5 paths; S3 H5 URIs are not supported |
| **Solution** | Add `h5_uri`/`h5_checksum` to request schema, add `stage_h5_input()` in new module, wire into `handle_submit_prediction()` |
| **Schema** | `PredictionRequest` gains `h5_path`, `h5_uri`, `h5_checksum`; validator enforces mutual exclusivity and format |
| **Staging** | `src/bremen/h5_inputs.py` — `stage_h5_input(s3://, staging_dir, checksum?) → Path` |
| **Validation ordering** | Schema validation before job creation — no job for HTTP 400 errors |
| **Invariant** | No completed/null jobs; validation errors never create jobs |
| **Logging** | 5 new `bremen.h5_input.*` events; no S3 URI/patient_id/checksum hex in logs |
| **Test coverage** | 8 new tests across 2 files, plus updates to existing prediction tests |
| **Non-goals confirmed** | No inference/preflight/preprocessing changes; no Matador/upload/async; no model/staging changes |

---

## 17. Implementation Agent Assignment

**Implementation agent**: coder

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. `test_bremen_api_skeleton.py` has tests that submit without `h5_path` — they will now get `ValueError` for missing input. The implementation agent should update these tests (same pattern as PR0042).
2. The `server.py` test helper `_make_handler(load_model=True)` creates POST tests without `h5_path`. These server tests (`test_valid_submit_returns_202`, etc.) will now get HTTP 400 instead of 202. The implementation agent must add `h5_path` to test payloads or update assertions.
3. `h5_checksum` validation regex should accept uppercase and lowercase hex (the actual smoke checksum uses lowercase hex).

FILES CHANGED:
- `src/bremen/api/schemas.py` — modified (extend PredictionRequest, update validator)
- `src/bremen/h5_inputs.py` — new (stage_h5_input function)
- `src/bremen/api/app.py` — modified (S3 staging integration, validation ordering)
- `tests/test_bremen_h5_input_staging.py` — new (5 tests)
- `tests/test_bremen_predictions.py` — modified (4 new tests + opt-in smoke)
- `tests/test_bremen_logging.py` — possibly modified
- `tests/test_bremen_api_server.py` — possibly modified

PLAN SUMMARY: Add `h5_uri`/`h5_checksum` to the prediction request schema with mutual-exclusivity validation against existing `h5_path`. Create `src/bremen/h5_inputs.py` with a `stage_h5_input()` function that downloads from S3, verifies optional checksum, and stages locally. Wire this into `handle_submit_prediction()` before `run_inference()`. Move all request-level validation before job creation so HTTP 400 errors never create a job. Add 5 new `bremen.h5_input.*` log events with safe metadata only. Add 8 new tests across 2 test files.

REQUEST CONTRACT: Two mutually exclusive modes — (A) `h5_path` (local filesystem) and (B) `h5_uri` (S3 object) + optional `h5_checksum`. Both require `target_scan_ref` + `control_scan_ref`. Exactly one of `h5_path` or `h5_uri` must be provided; providing both raises HTTP 400. `h5_uri` must start with `s3://`. `h5_checksum` must match `sha256:<64hex>` pattern.

STAGING DESIGN: `stage_h5_input()` in new module `src/bremen/h5_inputs.py` — parses `s3://bucket/key` via `parse_s3_uri()` from `model_artifacts.py`, downloads to temp file with boto3 (lazy import), verifies checksum via `verify_file_sha256()`, moves to final path under `/tmp/bremen-inputs`. Returns `Path` to staged file. Deletes temp file on failure or mismatch.

APP INTEGRATION SUMMARY: In `handle_submit_prediction()`, validate all input fields via updated `validate_prediction_request()` before any job creation. After job creation, resolve input: if `h5_uri` → call `stage_h5_input()` → pass staged local path to `run_inference()`; if `h5_path` → pass directly. All failures in staging or inference mark job as `failed` with non-empty error. No job created for validation errors.

LOGGING SUMMARY: 5 new events under `bremen.h5_input.*` namespace — `stage.start`, `stage.success`, `stage.failure`, `checksum.verify.success`, `checksum.verify.failure`. Safe fields only: `uri_scheme`, `h5_basename`, `size_bytes`, `checksum_present`, `checksum_algorithm`. No full S3 URI, no patient_id, no raw checksum hex, no request body, no secrets.

TEST PLAN SUMMARY: 8 tests — 5 in new `tests/test_bremen_h5_input_staging.py` (download, checksum success, checksum failure, safe logging, non-s3 rejection), 4 in existing `tests/test_bremen_predictions.py` (S3 URI acceptance with monkeypatch, both rejected, missing rejected, non-s3 rejected), plus 1 opt-in real S3 smoke test.

JOB STATUS INVARIANT: Validation errors (missing/both/invalid format) → no job created (HTTP 400). S3 staging failures → job `failed` with non-empty error, null result. Checksum mismatch → job `failed`. Runtime failures → job `failed`. Success → job `completed` with non-null result, null error. Never completed with both null.

BOUNDARY CONFIRMATIONS: No changes to inference_handler.py, preflight.py, preprocessing_bridge.py, model_artifacts.py (import only), model_state.py, jobs.py. No training, CI/CD, Docker, infra, or ADR changes. No real H5/model artifacts committed. No S3 dependency in default tests.

IMPLEMENTATION AGENT ASSIGNMENT: coder
