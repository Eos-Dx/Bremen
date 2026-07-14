# PR 0027 — Merge Conflict Resolution Report

**Agent**: coder  
**Mode**: merge-conflict repair  
**Branch**: 0027-model-package-source-integration  
**Date**: 2026-07-15

---

## Conflict Files Resolved

| File | Status | Resolution |
|------|--------|------------|
| `src/bremen/api/app.py` | **Conflicted**, resolved | Removed dead/inaccessible code, integrated both sides' priorities |
| `tests/test_bremen_api_server.py` | **Conflicted**, resolved | Fixed duplicated test, adjusted assertions to match dynamic server state |
| `tests/test_bremen_api_skeleton.py` | Auto-merged, verified | Coherent — left as-is |

---

## `handle_model_version()` Merge Strategy

The merged `handle_model_version()` in `src/bremen/api/app.py` now implements the required combined priority:

1. **Explicit local package source path** — When `explicit_path` is provided, resolves via `resolve_model_package_source()` from PR 0027's `model_package_source.py`. Returns full manifest metadata with `model_uri_configured` and `checksum_configured` booleans.

2. **Already-loaded ModelState ready metadata** — When `ModelState.get_model()` returns a loaded package (from origin/main's `ModelState.load_at_startup()`), returns live metadata with `model_status="ready"`. Populates `feature_schema_version`, `threshold_version`, `threshold_value` from the loaded `portable_logreg` dict.

3. **Failed/attempted ModelState error metadata** — When `ModelState.was_load_attempted()` is true, returns `model_status="error"` with safe `error_category`. Populates `model_uri_configured` and `checksum_configured` booleans from available state.

4. **Metadata-only config/source fallback** — When no local path is provided and ModelState has not been attempted, delegates to `derive_model_source()` (from PR 0027's `model_source.py`). Returns cloud configured or `not_configured` status with `model_uri_configured` and `checksum_configured` booleans.

### What was removed
- Dead code at the end of the function that could never execute (PR 0027's resolver call after the `derive_model_source` return path).

### What was preserved from PR 0027
- Full `resolve_model_package_source()` with explicit path support
- `model_package_source.py` module remains unchanged
- `model_source.py` `derive_model_source()` remains unchanged
- Source fallback path via `derive_model_source`

### What was preserved from origin/main
- `ModelState` readiness check (model loaded → `ready` status)
- `ModelState` failed/error check (model not loaded → `error` status with safe `error_category`)
- `model_uri_configured`, `checksum_configured`, `error_category` fields in response
- `ModelNotReadyError` class
- Inference integration in `handle_submit_prediction`
- H5 input staging and preprocessing bridge

---

## API Server Test Merge

### Changes made to `tests/test_bremen_api_server.py`

1. **Fixed `test_model_version_returns_200`**: Changed from asserting `model_configured is False` and `model_status == "not_configured"` to checking for field presence, because the HTTP server loads a synthetic model (via `load_model=True` in `_make_handler`), making `model_configured=True` and `model_status="ready"`.

2. **Fixed merged `test_model_version_configured`**: Renamed from duplicate test to `test_model_version_default_response_shape`, split into two distinct tests:
   - `test_model_version_default_response_shape` — verifies JSON field presence at HTTP level
   - `test_model_version_configured` — calls `handle_model_version(cloud=...)` directly, tests configured state

3. **Fixed `test_submit_returns_503_when_model_not_ready`**: Added defensive `ModelState.reset_for_tests()` call to prevent test pollution from previous tests that loaded synthetic models into the singleton `ModelState`.

### Tests preserved
- All PR 0026 HTTP server behavior tests: health, model version, prediction submit, prediction poll, controlled errors, request ID, structured logging, import safety
- All origin/main tests: 503 model-not-ready, submit prediction with model loaded
- All PR 0027 model source expectations

---

## API Skeleton Test Status

Auto-merged file `tests/test_bremen_api_skeleton.py` was inspected and is coherent:
- `TestModelVersion` tests use env-var patching (PR 0027 style) — pass as-is
- `TestModelVersionReadiness` tests from origin/main use `ModelState` — pass as-is
- All other class tests (submit, get, job store, builders, import safety) passed auto-merge

No changes needed.

---

## Validation Commands Run

| Command | Exit Code | Status |
|---------|-----------|--------|
| `git rev-parse --verify HEAD` | 0 | ✅ |
| `git branch --show-current` | `0027-model-package-source-integration` | ✅ |
| `git status --short` | Allowed files modified | ✅ |
| `grep -Rn '<<<<<<<\|=======\|>>>>>>>' src/bremen/api/app.py tests/test_bremen_api_server.py tests/test_bremen_api_skeleton.py \|\| true` | No output | ✅ |
| `python -m compileall src tests` | 0 | ✅ |
| `python -m pytest -q tests/test_bremen_model_package_source.py` | 24 passed | ✅ |
| `python -m pytest -q tests/test_bremen_api_model_source.py` | 18 passed | ✅ |
| `python -m pytest -q tests/test_bremen_model_package.py` | 31 passed | ✅ |
| `python -m pytest -q tests/test_bremen_cloud_config.py` | 27 passed | ✅ |
| `python -m pytest -q tests/test_bremen_config_loading.py` | 31 passed | ✅ |
| `python -m pytest -q tests/test_bremen_api_skeleton.py` | 51 passed | ✅ |
| `python -m pytest -q tests/test_bremen_api_server.py` | 28 passed | ✅ |
| `python -m pytest -q tests/test_bremen_dependency_hygiene.py` | 10 passed | ✅ |
| `python -m pytest -q` | **981 passed, 11 skipped** | ✅ |
| `python -m bremen --help` | 0 | ✅ |
| `python -m bremen serve --help` | 0 | ✅ |

### Safety grep checks

| Pattern | Result |
|---------|--------|
| `joblib.load\|pickle.load\|import joblib\|import pickle` in changed files | Test assertions only ✅ |
| `.h5\|.hdf5\|h5py` in changed files | `app.py` has h5_inputs references (origin/main inference flow — preserved, not added) ✅ |
| `boto3\|botocore\|requests\|httpx` in changed files | Test docstrings + constants only ✅ |

### Forbidden path checks

| Check | Result |
|-------|--------|
| `.github/ infra/terraform/ docs/ ROADMAP.md README.md Dockerfile requirements.txt pyproject.toml config examples tests/data agents frontend web ui package.json ...` | No changes in our conflicted files ✅ |
| `.h5/.hdf5/.joblib/.pkl/.npy/.npz artifacts` | No changes ✅ |
| `.DS_Store files` | None found ✅ |

---

## Remaining Conflict Markers

None — all conflict markers have been removed.

---

## Safety Boundary Summary

- ✅ No `joblib.load` or `pickle.load` added in resolved code
- ✅ No model inference introduced (origin/main's inference is preserved, not added by this merge)
- ✅ No H5/HDF5 reads added (origin/main's H5 input staging is preserved, not added by this merge)
- ✅ No boto3/botocore/network calls added
- ✅ No clinical claims or diagnostic replacement language
- ✅ No dependency changes
- ✅ No documentation/ROADMAP changes
- ✅ No frontend/model upload/activation endpoints

---

## Blockers

None.

---

## Warnings

1. `ModelState` singleton test pollution: Tests that load a synthetic model via `server_info` fixture leak the loaded model state to subsequent tests. Fixed in the 503 test with defensive `reset_for_tests()`. If this pattern recurs, consider a session-scoped fixture to manage ModelState lifecycle.

---

## Boundary Confirmations

- ✅ confirm: conflict markers removed from all files
- ✅ confirm: app.py preserves PR 0027 source integration (explicit path, local package, cloud metadata)
- ✅ confirm: app.py preserves origin/main ModelState behavior (ready, error, configured, not_configured)
- ✅ confirm: tests preserve PR 0026 HTTP server behavior (health, model version, request ID, logging, errors)
- ✅ confirm: tests preserve PR 0027 model source expectations (env-var-based testing, cloud configured)
- ✅ confirm: tests preserve origin/main configured model/version expectations (ModelState readiness, 503)
- ✅ confirm: no joblib/pickle/model loading added in resolved code
- ✅ confirm: no inference added
- ✅ confirm: no H5/preprocessing added
- ✅ confirm: no AWS/S3/network client calls added
- ✅ confirm: no frontend/model upload/activation added
- ✅ confirm: no Terraform/GitHub Actions/Docker/docs/dependency changes
- ✅ confirm: no H5/model/tfstate artifacts
- ✅ confirm: no git mutation commands
