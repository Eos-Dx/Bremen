# PR 0050 — Plan: Model Version Readiness Cleanup

## 1. Title / Branch / Objective

- **Title**: Model Version Readiness Cleanup
- **Branch**: `0050-model-version-readiness-cleanup`
- **Objective**: Clean up the `/model/version` endpoint so that `model_status` reflects actual runtime model state (unconfigured / configured / ready / error) and is consistent with `/health` `model_ready`. Operator semantics become unambiguous: when the model is loaded and validated, both endpoints agree it is ready. Narrow scope — no model loading lifecycle, preprocessing, inference, S3 staging, H5 staging, FastAPI, Docker, Terraform, or training changes.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
37699cbc5f8198f279aff9c571a8875c7f96d3fe

$ git branch --show-current
0050-model-version-readiness-cleanup

$ git status --short
(clean — no uncommitted changes)
```

Branch matches. Working tree clean.

---

## 3. Current State After PR0049

### The ambiguity problem

PR0049 (production E2E smoke hardening) delivered the operator runbook and synthetic production-like smoke test. During production smoke, the following contradictory behavior was observed:

| Endpoint | Returns | Interpretation |
|----------|---------|---------------|
| `GET /health` | `model_ready: true` | Model is loaded and usable |
| `GET /model/version` | `model_status: "configured"` | Model package env is set but NOT yet loaded |

The operator cannot tell whether the model is **ready** or merely **configured** from `/model/version` alone. The smoke test in `docs/production_e2e_smoke.md` documents `model_status: "configured"` as the expected response even when the model is fully loaded.

### Root cause in `handle_model_version()` (`src/bremen/api/app.py`, line ~96)

When `ModelState.get_model()` returns a non-None package (model loaded and validated), the handler returns:

```python
ModelVersionResponse(
    ...
    model_status="configured",  # BUG: should be "ready"
)
```

This is the only place the status string is set for the loaded-case branch. The status string `"configured"` was written before the runtime was mature enough to distinguish "config exists" from "model is actually loaded and validated." Now the runtime has a working `ModelState.is_ready()` check and a fully wired model loading pipeline, so the distinction is actionable.

### Additional problem: error state is invisible

If `ModelState.load_at_startup()` fails (checksum mismatch, corrupt joblib, missing local file, S3 staging failure), the state after failure is:

- `_loaded = False`
- `_model_package = None`

These are the same values as "load never called." When `handle_model_version()` sees `get_model() is None`, it falls through to `derive_model_source()` which reads the environment config. If env vars are set, `derive_model_source()` returns `model_status="configured"` — even though loading failed. The operator sees `model_status: "configured"` and `model_ready: false` simultaneously, which is contradictory and misleading.

---

## 4. Current State Matrix

| Condition | `ModelState._loaded` | `ModelState._model_package` | `/health` `model_ready` | `/model/version` `model_status` (current) | `/model/version` `model_status` (desired) |
|---|---|---|---|---|---|
| No env vars set | False | None | false | `not_configured` | `unconfigured` |
| Env vars set, load not attempted | False | None | false | `configured` | `configured` |
| Env vars set, load succeeded | True | dict | true | `configured` (WRONG) | `ready` |
| Env vars set, load failed | False | None | false | `configured` (WRONG) | `error` |

---

## 5. Required Status Semantics

### 5.1 `unconfigured`
- Required model configuration (env vars) is absent.
- `model_ready` is `false`.
- Prediction requests return HTTP 503 with `ModelNotReadyError`.
- `/model/version` returns `model_status: "not_configured"` (existing constant preserved; rename considered but would break compatibility; keep `not_configured` as the string value).

### 5.2 `configured`
- Required model configuration (env vars) exists.
- Model has NOT completed successful load/validation yet (or loading has not been attempted).
- `model_ready` is `false`.
- Prediction requests return HTTP 503 with `ModelNotReadyError`.

### 5.3 `ready`
- Model artifact has been staged or local file resolved.
- Checksum has been verified before `joblib.load()`.
- Model package has been loaded and validation passed.
- `model_ready` is `true`.
- Prediction requests proceed normally.
- `/model/version` returns live metadata from the loaded package.

### 5.4 `error`
- Model configuration exists.
- Staging, checksum verification, loading, or validation failed.
- `model_ready` is `false`.
- `/model/version` returns `model_status: "error"` with a safe error category (not raw exception details, stack traces, or full S3 URIs).
- Prediction requests return HTTP 503 with safe error message.

---

## 6. Endpoint Contract Plan

### 6.1 `GET /model/version` new response shape

```json
{
    "model_configured": true,
    "model_version": "<version>",
    "model_checksum": "<sha256-hex>",
    "feature_schema_version": "v0.1",
    "threshold_version": "<version>",
    "threshold_value": 0.5,
    "qc_criteria_version": null,
    "model_status": "ready",
    "model_uri_configured": true,
    "checksum_configured": true,
    "error_category": null
}
```

Fields to add:
- `model_uri_configured` (bool): whether `BREMEN_MODEL_URI` was provided (safe boolean, not raw URI).
- `checksum_configured` (bool): whether `BREMEN_MODEL_CHECKSUM` was provided (safe boolean, not raw checksum).
- `error_category` (str or null): safe error category when `model_status` is `"error"`, null otherwise.

**Backward compatibility note**: Existing fields (`model_configured`, `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`, `model_status`) are preserved. Three new fields are added. Existing clients that ignore unknown fields will not break.

### 6.2 `model_status` allowed values

Expand `ALL_MODEL_STATUSES` in `schemas.py`:

```
not_configured, configured, ready, error
```

The old `invalid` and `unavailable` constants were unused in practice. They may be deprecated (kept in the set for compatibility) or replaced. The plan recommends keeping them as historical constants but not using them in current runtime logic.

### 6.3 Safe response content rules

- `model_uri_configured` must be `bool` only — no raw full S3 URI, no bucket/key parts.
- `checksum_configured` must be `bool` only — no raw checksum hex string.
- `error_category` must contain only safe enum-style strings (e.g., `"checksum_mismatch"`, `"s3_staging_failure"`, `"local_file_not_found"`, `"joblib_load_failure"`, `"package_validation_failure"`), not raw exception messages, stack traces, or S3 URIs.
- `model_checksum` in the response is the full checksum string — this is already exposed today for model identity verification. No change.

---

## 7. Health Contract Plan

### 7.1 Current behavior
`/health` returns:
```json
{
    "status": "ok",
    "service": "bremen",
    "model_ready": true,
    "timestamp": "<ISO-8601 UTC>"
}
```

`model_ready` is derived from `ModelState.is_ready()`, which returns `self._loaded`.

### 7.2 Verification plan
1. `/health` `model_ready` must match `model_status == "ready"` (i.e., `model_ready` is `true` iff `model_status` is `"ready"`).
2. `/health` must NOT leak model URI, checksum, error internals, or any metadata beyond what it currently exposes.
3. `/health` must remain lightweight — no model package inspection, no network calls.
4. App Runner health check compatibility: `/health` returns HTTP 200 regardless of `model_ready` value (App Runner health checks accept 200/302; if `model_ready` is false, the service is alive but not usable — this is the correct App Runner health behavior for an alive-but-not-ready service).

### 7.3 No changes required to `/health`
`/health` already works correctly. Only the `/model/version` endpoint needs changes. The smoke doc's `/health` section remains correct as-is.

---

## 8. ModelState Changes

### 8.1 New state fields

Add two fields to `ModelState.__init__()`:

```python
self._load_attempted: bool = False   # True once load_at_startup has run
self._load_error: str | None = None  # Safe error category if loading failed
```

### 8.2 `load_at_startup()` changes

1. Set `self._load_attempted = True` as the first action.
2. At each failure return point (`return False`), set `self._load_error` to a safe category string:
   - `"model_uri_not_set"` — empty URI
   - `"s3_staging_failure"` — S3 download/access failure
   - `"local_file_not_found"` — file URI resolves to nonexistent path
   - `"checksum_mismatch"` — SHA-256 verification failed
   - `"joblib_load_failure"` — `joblib.load()` raised an exception
   - `"package_validation_failure"` — loaded package is not a dict or lacks required keys
3. On success, set `self._load_error = None`.
4. On `reset_for_tests()`, reset both new fields.

### 8.3 New accessor methods

```python
@classmethod
def get_load_error(cls) -> str | None:
    """Return safe error category, or None if no error or model is ready."""

@classmethod
def was_load_attempted(cls) -> bool:
    """Return True if load_at_startup has been called at least once."""
```

### 8.4 Non-goals of this change
- No change to when `load_at_startup()` is called.
- No change to checksum-before-deserialization boundary.
- No change to S3 staging logic.
- No change to local file resolution.
- No change to `joblib.load()` invocation.
- No change to package validation logic.
- No change to the singleton pattern.

This adds observability to the loading lifecycle output without altering the lifecycle itself.

---

## 9. `handle_model_version()` Changes (`src/bremen/api/app.py`)

### 9.1 Decision logic

```
if ModelState.get_model() is not None:
    # Model is loaded and validated — return live metadata
    model_status = "ready"
    error_category = None
    ...
elif ModelState.was_load_attempted():
    # Loading was attempted but failed — error state
    model_status = "error"
    error_category = ModelState.get_load_error()
    ...
else:
    # Loading not yet attempted — delegate to derive_model_source
    src = derive_model_source(cloud=cloud)
    # src already returns not_configured or configured
    # No change to this branch
```

### 9.2 New fields in the loaded branch

When `model_pkg is not None`, populate:
- `model_uri_configured = True` (inference from model being loaded)
- `checksum_configured = True` (inference from model being loaded)
- `error_category = None`

### 9.3 New fields in the error branch

When loading failed:
- Read `model_uri_configured` / `checksum_configured` from `derive_model_source()` or directly from `CloudConfig`
- `model_status = "error"`
- `error_category = ModelState.get_load_error()`
- Content fields (`model_version`, `model_checksum`, etc.) set from whatever was available at config time
- `model_configured = True` (because env vars are set, just loading failed)

### 9.4 New fields in the not-configured branch

When `model_status == "not_configured"`:
- `model_uri_configured = False`
- `checksum_configured = False`
- `error_category = None`

### 9.5 `build_not_configured_model_response()` changes

Update to include the three new fields with safe defaults (`False`, `False`, `None`).

---

## 10. Test Plan

### 10.1 New tests

#### A. `test_model_version_ready_after_load` (`test_bremen_api_skeleton.py`)
- Load synthetic model via `_load_synthetic_model()`.
- Call `handle_model_version(cloud=None)`.
- Assert `model_status == "ready"`.
- Assert `model_configured is True`.
- Assert `error_category is None`.
- Assert `model_uri_configured is True`.
- Assert `checksum_configured is True`.
- Assert `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value` are populated.

#### B. `test_model_version_error_after_failed_load` (`test_bremen_api_skeleton.py`)
- Create a corrupt or mismatched model file.
- Call `ModelState.load_at_startup()` with a mismatched checksum or invalid path.
- Assert return value is `False`.
- Call `handle_model_version()`.
- Assert `model_status == "error"`.
- Assert `error_category` is a non-empty string (one of the safe categories).
- Assert `model_configured is True`.
- Assert `model_ready` from health is `False`.
- Assert `model_uri_configured` and `checksum_configured` reflect the env/args provided.

#### C. `test_model_version_configured_not_loaded` (`test_bremen_api_skeleton.py`)
- Set cloud config with env vars but do NOT call `load_at_startup()`.
- Call `handle_model_version(cloud=configured_cloud)`.
- Assert `model_status == "configured"`.
- Assert `model_configured is True`.
- Assert `error_category is None`.
- Assert `model_ready` from health is `False`.

#### D. `test_model_version_not_configured` (`test_bremen_api_skeleton.py`)
- No env vars set, no load attempted.
- Assert `model_status == "not_configured"`.
- Assert `model_configured is False`.
- Assert `error_category is None`.
- Assert `model_uri_configured is False`.
- Assert `checksum_configured is False`.

#### E. `test_health_model_ready_consistency` (`test_bremen_api_skeleton.py`)
- After load: `handle_health().model_ready` is `True`, `handle_model_version().model_status` is `"ready"`.
- After load failure: `handle_health().model_ready` is `False`, `handle_model_version().model_status` is `"error"`.
- Not configured: `handle_health().model_ready` is `False`, `handle_model_version().model_status` is `"not_configured"`.

#### F. `test_no_raw_uri_or_checksum_leakage_in_model_version_error` (`test_bremen_api_skeleton.py`)
- After failed load, inspect `handle_model_version()` response.
- `model_uri_configured` is a `bool`, not a string.
- `checksum_configured` is a `bool`, not a string.
- `error_category` is a safe enum string, not a raw exception message or traceback.
- Assert no raw S3 URI pattern in response JSON.

#### G. `test_prediction_rejected_on_error_state` (`test_bremen_api_skeleton.py`)
- After failed load, `handle_submit_prediction()` raises `ModelNotReadyError` or returns HTTP 503.
- No change to existing behavior — just verify the gate still works after the model status refactor.

#### H. `test_model_source_unchanged` (`test_bremen_api_model_source.py`)
- Verify `derive_model_source()` still returns only `not_configured` / `configured` statuses (it deals with config-level, not runtime). This is a safety regression check.

### 10.2 Test modifications required

#### `tests/test_bremen_api_skeleton.py`
- Line ~173: Change `assert response.model_status == "configured"` to `assert response.model_status == "ready"` in the test that loads a synthetic model and calls `handle_model_version()`.
- The `test_model_version_does_not_load_model` test at line 161 remains unchanged (it tests the cloud-config path, not the loaded path).

#### `tests/test_bremen_api_server.py`
- Line ~126 (`test_model_version_returns_200`): Change `assert data["model_status"] == "configured"` to `assert data["model_status"] == "ready"` since server starts with `load_model=True`.

#### `tests/test_bremen_model_startup_staging.py`
- Review for any assertions that depend on `model_status == "configured"`. Add `ready`/`error` checks as needed.

#### `tests/test_bremen_inference_integration.py`
- Review for any assertions about model status after synthetic model load. Adjust if needed.

#### `tests/test_bremen_predictions.py`
- Review for any `model_status` assertions. These tests use `_load_synthetic_model` which results in ready state.

#### `tests/test_bremen_logging.py`
- No changes expected — logging events already distinguish `model_ready=true/false`. The status string is a reporting concern, not a logging concern.
- But verify: the `test_detected_model_config_logs_safe_fields` test and `test_successful_model_load_logs_ready` test should still pass.

### 10.3 Test design rules

All tests must:
- Be synthetic/mocked only. No AWS, Docker, Terraform, App Runner, network, real H5, or real model artifact.
- Follow `TEST_DESIGN_STANDARD.md` (prefer direct handler calls, no HTTP server for non-server tests).
- Follow `AGENT_TEST_DEBUGGING_RULES.md` (no `tail`/`head` on failing pytest output, no regex mass rewrites).

---

## 11. File Change Plan

### 11.1 Source files (implementation agent)

| File | Change type | Scope |
|---|---|---|
| `src/bremen/api/model_state.py` | Modify | Add `_load_attempted`, `_load_error` fields, `get_load_error()`, `was_load_attempted()` accessors, set error category at failure points in `load_at_startup()` |
| `src/bremen/api/schemas.py` | Modify | Add `MODEL_STATUS_READY = "ready"`, `MODEL_STATUS_ERROR = "error"` constants, update `ALL_MODEL_STATUSES`, add `model_uri_configured`, `checksum_configured`, `error_category` fields to `ModelVersionResponse`, update `build_not_configured_model_response()` |
| `src/bremen/api/app.py` | Modify | Update `handle_model_version()` to return correct status based on loaded/error/configured state, add new fields to response |
| `src/bremen/api/model_source.py` | No change | `derive_model_source()` remains config-only; no runtime state needed |

### 11.2 Test files (implementation agent)

| File | Change type | Scope |
|---|---|---|
| `tests/test_bremen_api_skeleton.py` | Modify + add tests | Update existing `model_status == "configured"` assertions to `"ready"` after load; add tests A–H (see section 10.1) |
| `tests/test_bremen_api_server.py` | Modify | Update server-based assertions for `model_status == "ready"` after `load_model=True` startup |
| `tests/test_bremen_model_startup_staging.py` | Review only | Verify tests still pass; no change expected |
| `tests/test_bremen_inference_integration.py` | Review only | Verify tests still pass; no change expected |
| `tests/test_bremen_predictions.py` | Review only | Verify tests still pass; no change expected |
| `tests/test_bremen_logging.py` | Review only | Verify tests still pass; no change expected |

### 11.3 Documentation files (implementation agent)

| File | Change type | Scope |
|---|---|---|
| `docs/production_e2e_smoke.md` | Modify | Update expected `model_status` from `"configured"` to `"ready"` in the model version check section; update expected response JSON to include new fields |
| `docs/api_contract.md` | Modify | Document `ready` and `error` as valid `model_status` values; document new response fields |

---

## 12. Preserved Boundaries

1. No model in image — unchanged.
2. No hot-swap — unchanged.
3. No per-request model loading — unchanged.
4. Checksum before `joblib.load()` — unchanged.
5. S3 model staging remains startup path — unchanged.
6. Runtime must not train — unchanged.
7. Training code remains offline-only — unchanged.
8. H5 staging remains separate from model staging — unchanged.
9. Matador remains system of record — unchanged.
10. FastAPI remains deferred — unchanged.
11. Preprocessing math — unchanged.
12. Inference math — unchanged.
13. Job semantics — unchanged.
14. Prediction response shape — unchanged (only `/model/version` response shape changes with additions).
15. No new dependencies — unchanged.

---

## 13. Validation Plan

### 13.1 Implementation validation

```bash
python -m compileall src tests

python -m pytest -q tests/test_bremen_api_skeleton.py -v
python -m pytest -q tests/test_bremen_api_server.py -v
python -m pytest -q tests/test_bremen_model_startup_staging.py -v
python -m pytest -q tests/test_bremen_inference_integration.py -v
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_logging.py -v
python -m pytest -q tests/test_bremen_api_model_source.py -v

python -m pytest -q
```

### 13.2 Safety validation

```bash
git diff --name-only -- Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml src/bremen/training

git diff --name-only | grep -E '\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$' || true

grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n src tests requirements.txt pyproject.toml || true

grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|Nova_\|s3://" -n src/bremen/api || true
```

### 13.3 Contract stability check

```bash
# Verify /model/version still returns all required fields
python -c "
import json
# Verify expected shape: all old fields present, new fields optional
# This is a manual verification step during implementation
"
```

### 13.4 Runbook update check

```bash
# Verify smoke doc expected response has model_status: ready
grep -c '"model_status": "ready"' docs/production_e2e_smoke.md
```

---

## 14. Non-Goals

1. No FastAPI.
2. No new deployment target.
3. No Docker changes.
4. No Terraform changes.
5. No dependency changes.
6. No training changes.
7. No model artifact changes.
8. No H5 layout changes.
9. No preprocessing changes.
10. No inference math changes.
11. No production smoke execution.
12. No clinical validation claims.
13. No Matador integration yet.
14. No config governance ADR yet.
15. No model loading lifecycle changes (load timing, retry logic, hot-swap, restart behavior).
16. No changes to `/health` response shape.
17. No changes to prediction flow (validation, job creation, poll, result shape).
18. No changes to logging events or log format.
19. No changes to `derive_model_source()` — it remains a config-only descriptor.

---

## 15. Implementation Agent Assignment

**Agent**: coder

**Ordered task list**:
1. Read this PLAN.md and the required source/docs/test artifacts listed in the task prompt (sections 1–16 of the task, already all read by the plan agent).
2. Create directory if needed: `.project-memory/pr/0050-model-version-readiness-cleanup/reviews/`
3. Implement source changes:
   a. `src/bremen/api/model_state.py` — add state fields + accessors + error assignment
   b. `src/bremen/api/schemas.py` — add constants + response fields + update builder
   c. `src/bremen/api/app.py` — update `handle_model_version()` logic
4. Update test files:
   a. `tests/test_bremen_api_skeleton.py` — update + add tests
   b. `tests/test_bremen_api_server.py` — update assertion
5. Review-only test files: verify no changes needed
6. Update docs:
   a. `docs/production_e2e_smoke.md` — update expected `model_status`
   b. `docs/api_contract.md` — document new status values and fields
7. Run validation checklist (section 13)
8. Fix any failures — follow `AGENT_TEST_DEBUGGING_RULES.md` (no `tail`/`head` on pytest output, anti-loop escalation after 3 attempts or 20 minutes)
9. Commit all changes in a single clean commit

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. The `error` state detection requires adding `_load_attempted` and `_load_error` fields to `ModelState`. This is adding observability to the loading lifecycle output — it is NOT changing the lifecycle itself. The plan agent considers this compliant with the hard rule "do not change model loading lifecycle," but the implementation agent should verify this interpretation.
2. `docs/api_contract.md` documents `invalid` and `unavailable` as `model_status` values that are not used in practice. The plan keeps them for backward compatibility but does not use them. The implementation agent may choose to deprecate them explicitly in the docstring.
3. The three new fields (`model_uri_configured`, `checksum_configured`, `error_category`) are additive. Existing clients that parse `model_status` from the known set and ignore unknown fields will not break. However, any client that asserts exact JSON field equality will need updating.
4. `test_bremen_api_server.py` line 126 asserts `data["model_status"] == "configured"` — this must change to `"ready"` since the `server_info` fixture uses `load_model=True`.
5. `test_bremen_api_skeleton.py` line 173 (`test_model_version_does_not_load_model`) tests the cloud-config path where model is NOT loaded — this test correctly expects `"configured"` and must NOT be changed. Only the test at line ~165 (which loads a synthetic model and then calls `handle_model_version()`) is affected.

FILES CHANGED:
- `.project-memory/pr/0050-model-version-readiness-cleanup/PLAN.md` — written
- `.project-memory/pr/0050-model-version-readiness-cleanup/reviews/plan-review.yml` — future artifact

CURRENT STATE SUMMARY:
PR0049 merged. The roadmap step PR0050 is verified as the next priority. Runtime model loading works, S3 staging works, checksum verification works, prediction execution works, production E2E smoke test exists. The remaining gap is that `/model/version` reports `model_status="configured"` when the model is actually loaded and ready, and has no `error` state at all. This PR cleans up readiness reporting with minimal changes to `ModelState` (two new fields for observability), `schemas.py` (new constants and response fields), and `app.py` (updated decision logic in `handle_model_version`). Seven source lines of actual logic change plus supporting accessors. All other layers are untouched.

STATUS SEMANTICS:
- unconfigured: no env vars → `not_configured`, `model_ready=false`
- configured: env vars set, no load attempt yet → `configured`, `model_ready=false`
- ready: loaded+validated → `ready`, `model_ready=true`
- error: env vars set, load failed → `error`, `model_ready=false`, safe `error_category`

ENDPOINT CONTRACT PLAN:
`/model/version` gets three new fields (`model_uri_configured` bool, `checksum_configured` bool, `error_category` str|null). Existing fields preserved. `model_status` gets two new values (`ready`, `error`). `not_configured` and `configured` constants preserved. All response content remains safe — no raw full S3 URI, no raw checksum, no secrets, no patient data.

HEALTH CONTRACT PLAN:
No changes to `/health`. `model_ready` already correctly reflects `ModelState.is_ready()`. Verification test added for consistency between `/health` `model_ready` and `/model/version` `model_status`.

TEST PLAN:
8 new test cases (A–H) covering all four status states, health consistency, safe leakage, prediction rejection in error state, and model_source regression. 2 existing test assertions updated (skeleton + server). 4 existing test files reviewed-only (no changes expected). All tests synthetic/mocked.

FILE CHANGE PLAN:
3 source files modified (model_state.py, schemas.py, app.py). 2 test files modified (test_bremen_api_skeleton.py with additions, test_bremen_api_server.py with one assertion). 4 test files reviewed-only. 2 doc files updated (production_e2e_smoke.md, api_contract.md). No infra, CI/CD, Docker, training, or dependency changes.

PRESERVED BOUNDARIES:
All 19 boundaries preserved. The only "close call" is adding `_load_attempted`/`_load_error` to ModelState — but this is layer-7 observability on the lifecycle output, not a lifecycle change. No change to timing, retry, hot-swap, checksum boundary, S3 path, H5 path, job semantics, or prediction math.

VALIDATION PLAN:
Compileall + 7 test suites + full suite + safety scans (diff checks for forbidden paths, FastAPI/grep scans, artifact scans) + runbook content check. All commands specified.

NON-GOALS:
19 non-goal categories listed. Key: no lifecycle changes, no preprocessing/inference changes, no prediction flow changes, no logging changes, no derive_model_source changes.

---

Implementation agent: coder
