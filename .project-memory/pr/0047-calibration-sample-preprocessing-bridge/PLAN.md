# PR 0047 — Plan: Calibration Sample Preprocessing Bridge

## 1. Title / Branch / Objective

- **Title**: Calibration Sample Preprocessing Bridge
- **Branch**: `0047-calibration-sample-preprocessing-bridge`
- **Objective**: Extend the preprocessing bridge so that calibration sample H5 layout (with explicit target/control sample refs, `sets/set_*/integration/i` and `integration/q` arrays) produces the existing v0.1 15-feature schema. Existing canonical preprocessing remains unchanged. Inference math, model package, threshold behavior, and feature schema order are unchanged. No FastAPI. No clinical claims.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
7236b7813a760219558ce71d67cb72cb229464c1

$ git branch --show-current
0047-calibration-sample-preprocessing-bridge

$ git status --short
(clean — no uncommitted changes)
```

Required files all present and read:

- `ROADMAP.md` ✓
- `.project-memory/AGENT_TEST_DEBUGGING_RULES.md` ✓
- `src/bremen/api/h5_layouts.py` ✓
- `src/bremen/api/preflight.py` ✓
- `src/bremen/api/preprocessing_bridge.py` ✓
- `src/bremen/api/inference_handler.py` ✓
- `src/bremen/api/app.py` ✓
- `src/bremen/api/schemas.py` ✓
- `tests/test_bremen_h5_layouts.py` ✓
- `tests/test_bremen_h5_preflight.py` ✓
- `tests/test_bremen_preprocessing_bridge.py` ✓
- `tests/test_bremen_inference_integration.py` ✓
- `tests/test_bremen_predictions.py` ✓
- `.project-memory/pr/0045-h5-layout-adapter-boundary/PLAN.md` ✓
- `.project-memory/pr/0045-h5-layout-adapter-boundary/reviews/precommit-review.yml` ✓

PR0045 confirmed merged. Calibration sample layout supported at preflight/context level. Preprocessing is the gap.

---

## 3. Current State After PR0045

### What works
- S3 H5 input staging (PR0043)
- H5 patient metadata fallback — `/patient/id` primary, sample `patient_name` fallback (PR0044)
- H5 layout adapter boundary — `CanonicalH5LayoutAdapter` + `CalibrationSampleH5LayoutAdapter` (PR0045)
- Preflight passes with explicit calibration sample refs: `run_h5_preflight(h5_path, target_scan_ref="...", control_scan_ref="...")`
- `H5PredictionContext` provides resolved `target_group_path`, `control_group_path`, sides, measurement counts, patient identifier
- Existing canonical preflight/preprocessing unchanged

### What does NOT work
- `run_preprocessing_bridge()` still reads from `/scans/target/measurements` and `/scans/contralateral/measurements`
- Calibration layout has no `/scans/` structure — preprocessing always fails with `H5ContainerError` or `PreprocessingBridgeError`
- No code reads `sets/set_*/integration/i` or `/q` arrays

### The bridge gap
The calibration adapter `resolve_prediction_context()` returns `target_group_path` (e.g., `/calib_20260128_132622/sample_01_20260128_Nova_376_Right`) and `control_group_path`. These paths are on the `H5PredictionContext` but **preprocessing_bridge.py never receives them**. The bridge only gets `h5_path` and an optional `PreflightResult`.

---

## 4. FastAPI Deferral Note

FastAPI is **not** part of this PR. FastAPI must be deferred until the end-to-end domain path is proven through:
- PR0047 — calibration sample preprocessing bridge (this PR)
- PR0048 — HTTP explicit-ref wiring
- PR0049 — production end-to-end smoke hardening

FastAPI must eventually be a thin transport adapter only. It must not change preprocessing, inference math, model loading, H5 staging, or model lifecycle.

---

## 5. Real Calibration Sample H5 Structure

Each selected sample group:

```
/calib_20260128_132622/sample_01_20260128_Nova_376_Right/
  sample/
    name           = "Nova_376_Right"
    patient_name   = "Nova_376"
    sample_type    = "RIGHT BREAST"
  sets/
    set_001_sample_main/
      integration/
        i   — 1D array (in-phase component)
        q   — 1D array (quadrature component)
      measurements/
        det_1_ash512x768/data  (NOT read in this PR)
      raw/
        data                   (NOT read in this PR)
    set_002_sample_main/     (same structure)
    set_003_sample_main/     (same structure)
```

### Measurement data source
- **Primary**: `sets/*/integration/i` and `sets/*/integration/q` — both are 1D arrays
- **Not used**: `measurements/det_1_ash512x768/data` and `raw/data` — raw detector images excluded

### Multiple sets
- 3 sets per sample in the current H5: `set_001`, `set_002`, `set_003`
- Each set has identical structure with `integration/i` and `integration/q`
- Sets represent repeated measurements of the same physical sample

---

## 6. Existing Preprocessing Behavior Summary

### `build_feature_table(h5_path)` — canonical only
1. Opens H5 file
2. Calls `_extract_profiles(f, "target")` → reads `/scans/target/measurements` → returns list of 1D profile arrays
3. Calls `_extract_profiles(f, "contralateral")` → reads `/scans/contralateral/measurements`
4. Computes mean target profile and mean contralateral profile (1D arrays, length ~100)
5. Passes both mean profiles to 15 pure-numpy feature computation functions
6. Returns `{"weightedrms1": ..., ..., "meanrms2": ...}`

### Feature computation functions
All 15 helper functions (`_sigma_rms`, `_mahalanobis_difference`, etc.) take two 1D numpy arrays (`target_mean_profile`, `control_mean_profile`) and return floats. These functions are **layout-agnostic** — they work on any two 1D arrays of the same length. They do not read H5 files.

### Bridge flow
```
run_preprocessing_bridge(h5_path, preflight_result=None)
  → run_h5_preflight(h5_path) → PreflightResult (gate)
  → build_feature_table(h5_path)
    → _extract_profiles(f, "target")
    → _extract_profiles(f, "contralateral")
    → _sigma_rms(t_mean, c_mean), etc.
  → BremenFeatureVector
  → PreprocessingBridgeResult
```

### Key architectural insight
The feature computation helpers (`_sigma_rms` through `_mean_peak_value_raw`) are **pure numpy** — they take two np.ndarrays and return floats. The **only** layout-dependent code is `_extract_profiles()` which reads from fixed H5 paths.

---

## 7. Proposed Calibration Preprocessing Contract

### Chosen option: Option A — extend preprocessing_bridge.py

**Option A** is preferred over Option B (new module `calibration_preprocessing.py`) because:
1. The feature computation helpers are already in `preprocessing_bridge.py` and are layout-agnostic
2. Adding a second module would require duplicating or importing helpers — introducing either duplication or circular dependency risk
3. The bridge already has a `preflight_result` parameter — adding an `H5PredictionContext` parameter is a natural extension
4. File growth is acceptable — the addition is one new function and a conditional branch

### Changes to `build_feature_table()`

Add a new optional parameter:

```python
def build_feature_table(
    h5_path: str | Path,
    *,
    layout_context: H5PredictionContext | None = None,
) -> dict[str, float]:
```

When `layout_context` is provided and `layout_context.layout_name == "calibration_sample"`:
- Use `layout_context.target_group_path` and `layout_context.control_group_path` to read integration i/q arrays
- Compute mean profiles from each sample's sets
- Apply the same 15 feature computation functions

When `layout_context` is `None` or `layout_name == "canonical"`:
- Use existing canonical path (backward compatible)

### New function: `_extract_calibration_profiles()`

```python
def _extract_calibration_profiles(
    h5_file: h5py.File,
    sample_group_path: str,
) -> list[np.ndarray]:
```

Reads `{sample_group_path}/sets/set_*/integration/i` and `integration/q` for each set, combines them into a profile.

**I/Q combination strategy**: For each set, compute `magnitude = sqrt(i^2 + q^2)` — the standard I/Q demodulation output. This produces a 1D profile per set. Multiple sets produce multiple 1D profiles, matching the existing interface of `_extract_profiles()` which returns `list[np.ndarray]`.

**Set handling**: All sets under the sample's `sets/` group are processed. Each set yields one profile. This preserves the existing semantics where multiple measurements produce multiple profile arrays that are averaged downstream.

**Deterministic ordering**: Sets are sorted by group name (e.g., `set_001_sample_main` < `set_002_sample_main`).

### Changes to `run_preprocessing_bridge()`

Add an optional parameter:

```python
def run_preprocessing_bridge(
    h5_path: str | Path,
    *,
    preflight_result: PreflightResult | None = None,
    layout_context: H5PredictionContext | None = None,
    skip_preflight: bool = False,
) -> PreprocessingBridgeResult:
```

The `layout_context` is passed through to `build_feature_table()`.

### Inference handler bridge wiring

`inference_handler.py` remains **unchanged** in this PR. The `run_inference()` function already receives `preflight_result` and passes it to `run_preprocessing_bridge()`. However, the adapter context is currently **not available** inside `run_inference()` — it is computed inside `run_h5_preflight()` but not returned.

To bridge this gap, the `PreflightResult` already contains all fields needed to reconstruct the layout context indirectly (`patient_identifier_source`, `metadata_fallback_used`, `target_side`, `contralateral_side`, `target_measurement_count`, `contralateral_measurement_count`). For the actual group paths needed by `_extract_calibration_profiles()`, there are two options:

**Option i**: Add `target_group_path` and `control_group_path` to `PreflightResult.metadata`. These are safe H5 paths (not patient data, not S3 URIs).

**Option ii**: Add a small `target_group_path` / `control_group_path` field to `PreflightResult`. This requires a dataclass change but makes the paths explicitly typed.

**Plan recommendation: Option i** — add to `PreflightResult.metadata["target_group_path"]` and `metadata["control_group_path"]`. The metadata dict is already typed as `dict[str, Any]` and is populated by `run_h5_preflight()`. This requires a tiny change to `preflight.py` (where adapter context is already available inside `run_h5_preflight()`) but **no** change to the `PreflightResult` dataclass.

### Data flow for calibration

```
run_inference(h5_path)
  → run_h5_preflight(h5_path, target_scan_ref="...", control_scan_ref="...")
    → adapter.resolve_prediction_context(...) → H5PredictionContext
    → builds PreflightResult with metadata["target_group_path"] and metadata["control_group_path"]
    → returns PreflightResult
  → run_preprocessing_bridge(h5_path, preflight_result=preflight)
    → build_feature_table(h5_path, layout_context=...)
      → _extract_calibration_profiles(f, target_group_path)  # reads integration i/q
      → _extract_calibration_profiles(f, control_group_path)
      → _sigma_rms(t_mean, c_mean), ... (same 15 functions)
    → BremenFeatureVector
  → model validation → inference → prediction JSON
```

---

## 8. Feature Schema Preservation

The v0.1 15-feature schema must be produced in **exact order**:

```
weightedrms1
sigma_l1
sigma_r1
mahalanobis1    (lowercase)
weightedrms2
sigma_l2
sigma_r2
mahalanobis2    (lowercase)
peak14_intensity
mean_peak_value_raw
wasserstein_distance_muLR
cosine_distance_full_q2
wasserstein_distance_full_q2
meanrms1
meanrms2
```

The schema constants (`BREMEN_V01_FEATURE_COLUMNS`, `FEATURE_SCHEMA_VERSION`) in `preprocessing_bridge.py` are **not changed**. The same 15 feature computation functions are reused. Only the profile extraction path changes.

**Verification**: Existing tests `test_feature_order_matches_v01`, `test_all_15_feature_values_are_finite`, `test_mahalanobis_is_lowercase` continue to pass for canonical layout. New tests verify the same properties for calibration layout.

---

## 9. Set Handling Decision

### Decision: Process all sets, combine via magnitude

For each `set_NNN_sample_main` under the sample's `sets/` group:
1. Read `integration/i` — 1D numpy array
2. Read `integration/q` — 1D numpy array
3. Compute `magnitude = sqrt(i^2 + q^2)` — 1D profile
4. Append to list of profiles

**Why magnitude?** The canonical layout stores processed profiles directly. The calibration layout stores raw I/Q demodulated data. The magnitude profile `sqrt(i^2 + q^2)` is the standard way to convert I/Q to the signal envelope that the feature computation functions expect.

**Why all sets?** Multiple sets represent repeated measurements of the same sample. This matches the canonical layout where `/scans/target/measurements` contains multiple profile rows. The downstream code already handles multiple profiles by taking the mean.

**Deterministic ordering**: Sets are sorted alphabetically by their H5 group key. `sorted(sets_group.keys())` gives a stable order (`set_001_sample_main`, `set_002_sample_main`, ...).

**No arbitrary selection**: All sets are processed. No "first set only" selection. No average of a subset. This avoids the ambiguity of choosing which measurements to use.

**Rejection rules**:
- If a sample has no `sets/` group: raise `PreprocessingBridgeError`
- If a sample has no `sets/set_*` groups: raise `PreprocessingBridgeError`
- If any selected set group is missing `integration/i` or `integration/q`: raise `PreprocessingBridgeError`
- If `integration/i` and `integration/q` have different lengths: raise `PreprocessingBridgeError`
- If target and control profiles have incompatible lengths (feature functions will naturally fail): raise `PreprocessingBridgeError`

---

## 10. Safety and Privacy Rules

1. **No raw patient_name in logs**: The calibration preprocessing must not log `patient_name` values
2. **No raw feature values in logs**: Feature values are technical but still must not be logged at INFO level
3. **No raw scan arrays in logs**: Integration i/q arrays must not be logged
4. **No full S3 URI in logs**: Pre-existing invariant
5. **No raw detector image arrays**: PR0047 must not read `measurements/det_1_ash512x768/data` or `raw/data` — only `integration/i` and `integration/q`
6. **No weakening of existing checks**: All canonical preprocessing validation remains
7. **No auto-selection**: All sets are processed — no arbitrary subset selection
8. **No inference model changes**: Feature computation functions are reused, not modified
9. **No clinical claims**: Preprocessing produces technical features only

---

## 11. Implementation Files and Scope

### Allowed implementation files

| File | Action | Rationale |
|---|---|---|
| `src/bremen/api/preprocessing_bridge.py` | **Modified** — add `_extract_calibration_profiles()`, add `layout_context` param to `build_feature_table()` and `run_preprocessing_bridge()`, add conditional branch for calibration extraction | Core preprocessing extension |
| `src/bremen/api/preflight.py` | **Modified** — add `target_group_path` and `control_group_path` to `PreflightResult.metadata` in the adapter path | Required for bridge to know resolved group paths |
| `tests/test_bremen_calibration_preprocessing.py` | **New** — tests for calibration sample preprocessing (Tests A–I) | Isolated coverage |
| `tests/test_bremen_preprocessing_bridge.py` | **Modified only if needed** — existing canonical tests must pass unchanged | Per allowed list |
| `tests/test_bremen_inference_integration.py` | **Modified only if needed** — narrow integration assertion updates | Per allowed list |
| `tests/test_bremen_predictions.py` | **Modified only if needed** — narrow expectation updates | Per allowed list |

### Not modified (read-only unless plan proves otherwise)

- `src/bremen/api/inference_handler.py` — no change needed; bridge changes are backward compatible
- `src/bremen/api/app.py` — no change needed
- `src/bremen/api/schemas.py` — no change needed
- `src/bremen/api/h5_layouts.py` — narrow change only if context needs a new field (e.g., `raw_iq_paths`); not expected
- `src/bremen/h5_inputs.py` — no change
- `src/bremen/api/model_state.py` — no change

---

## 12. Test Plan

All calibration-specific tests in `tests/test_bremen_calibration_preprocessing.py` (new file).

### A. `test_canonical_preprocessing_still_passes`

- Create synthetic canonical H5 (existing helper)
- Call `run_preprocessing_bridge(h5_path)` without layout_context
- Assert: passes, 15 features, same as current behavior
- Assert: no regression in feature order or values

### B. `test_calibration_sample_reads_integration_iq_arrays`

- Create synthetic calibration H5 with explicit target/control refs (reuse `_create_calibration_h5` from `test_bremen_h5_layouts.py`)
- Run preflight to get `PreflightResult` with metadata paths
- Call `run_preprocessing_bridge(h5_path, preflight_result=result)`
- Assert: bridge passes, 15 features, finite values
- Assert: uses `integration/i` and `integration/q` — not raw/data paths

### C. `test_calibration_sample_multiple_sets_are_handled_deterministically`

- Create calibration H5 with 5 sets per sample
- Run bridge twice
- Assert: feature values identical between runs (deterministic)
- Assert: all 5 sets are processed (measurement count matches)

### D. `test_calibration_sample_missing_integration_i_fails_safely`

- Create calibration H5 with a set group missing `integration/i`
- Assert: `PreprocessingBridgeError` raised
- Error message must not contain raw path values

### E. `test_calibration_sample_missing_integration_q_fails_safely`

- Same pattern for missing `integration/q`

### F. `test_calibration_sample_mismatched_iq_lengths_fails_safely`

- Create calibration H5 where `integration/i` and `integration/q` have different lengths
- Assert: `PreprocessingBridgeError` raised

### G. `test_calibration_sample_outputs_v01_feature_schema_order`

- Run bridge on calibration H5
- Assert: feature names match `BREMEN_V01_FEATURE_COLUMNS` exact order
- Assert: schema version is `"v0.1"`

### H. `test_calibration_sample_does_not_log_raw_patient_name_or_feature_values`

- caplog at INFO level
- Assert: no raw `Nova_376`, no raw feature values, no raw i/q arrays in log

### I. `test_calibration_sample_does_not_read_raw_image_arrays`

- Use monkeypatch to track H5 reads
- Assert: `integration/i` and `integration/q` are accessed
- Assert: `measurements/det_1_ash512x768/data` and `raw/data` are NOT accessed
- This verifies the no-raw-detector-image-array safety rule

### J. Optional real H5 smoke (skipped by default)

```python
@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="Set BREMEN_H5_PREFLIGHT_SMOKE_PATH to enable",
)
def test_calibration_preprocessing_real_h5_smoke():
    """
    Assert calibration preprocessing moves past bridge on real H5.
    
    Explicit refs:
      target_scan_ref = "calib_20260128_132622/sample_01_20260128_Nova_376_Right"
      control_scan_ref = "calib_20260128_132622/sample_02_20260128_Nova_376_Left"
    
    NOTE: Full prediction may still fail at later stages (inference wiring).
    This test only asserts the bridge no longer fails.
    """
```

---

## 13. Validation Checklist

```bash
# Follow AGENT_TEST_DEBUGGING_RULES.md — no tail/head on failing pytest

# Compile
python -m compileall src tests

# Test runs
python -m pytest -q tests/test_bremen_preprocessing_bridge.py -v
python -m pytest -q tests/test_bremen_calibration_preprocessing.py -v
python -m pytest -q tests/test_bremen_h5_layouts.py -v
python -m pytest -q tests/test_bremen_h5_preflight.py -v
python -m pytest -q tests/test_bremen_inference_integration.py -v
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_logging.py
python -m pytest -q

# Code coverage — calibration preprocessing
grep -n "integration/i\|integration/q\|calibration_sample\|_extract_calibration_profiles\|layout_context" \
  src/bremen tests

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

# Feature schema unchanged
grep -n "BREMEN_V01_FEATURE_COLUMNS\|FEATURE_SCHEMA_VERSION" \
  src/bremen/api/preprocessing_bridge.py | head -5
```

---

## 14. Forbidden Changes

The implementation agent MUST NOT:

1. Add FastAPI, uvicorn, starlette, or any web framework dependency
2. Modify `requirements.txt` or `pyproject.toml`
3. Modify Dockerfile or Dockerfile.training
4. Modify `infra/**` or `.github/**`
5. Modify `src/bremen/training/**`
6. Modify model loading, model package validation, S3 model staging
7. Modify S3 H5 staging (`src/bremen/h5_inputs.py`)
8. Modify `docs/adr/**` or `ROADMAP.md`
9. Modify `inference_handler.py` unless proven necessary (plan says no)
10. Modify `app.py` unless proven necessary (plan says no)
11. Modify `h5_layouts.py` unless proven necessary (plan says only narrow metadata field)
12. Change inference math or threshold behavior
13. Change feature schema order or version
14. Log raw patient identifiers, raw feature values, or raw scan arrays
15. Read raw detector image arrays (`measurements/data`, `raw/data`) as primary source
16. Auto-select first patient or sample
17. Commit real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` artifacts
18. Commit secrets, account IDs, access keys, registry URLs

---

## 15. Non-Goals

- No FastAPI or HTTP transport change
- No App Runner redeploy or production smoke
- No model retraining or model package change
- No config governance
- No Matador integration
- No decision report wrapper
- No clinical claims
- No changes to inference math or feature computation formulas
- No changes to profile averaging strategy (mean of all measurements remains)
- No calibration of I/Q to physical units — magnitude computation only

---

## 16. Rollback Plan

1. **Immediate rollback**: `git revert HEAD` on `0047-calibration-sample-preprocessing-bridge` branch
2. Verify revert:
   - `python -m pytest -q tests/test_bremen_preprocessing_bridge.py -v`
   - `python -m pytest -q tests/test_bremen_h5_layouts.py -v`
   - `python -m pytest -q tests/test_bremen_h5_preflight.py -v`
   - `python -m pytest -q tests/test_bremen_inference_integration.py -v`
   - `python -m pytest -q tests/test_bremen_predictions.py -v`
   - `python -m pytest -q`
3. Open revert PR with label `revert/0047`

### Partial rollback (calibration bridge only)

If the calibration-specific code causes issues but canonical bridge is stable, revert only the calibration changes in `preprocessing_bridge.py` and `preflight.py`. The `_extract_calibration_profiles()` function can remain in a follow-up PR.

---

## 17. Implementation Agent Assignment

**Implementation agent**: coder

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. The `preflight.py` change (adding `target_group_path` + `control_group_path` to `PreflightResult.metadata`) is a tiny, safe addition — but the implementation agent must ensure it only happens in the adapter path, not in the legacy canonical path. When `target_scan_ref` is `None` (legacy path), these metadata keys should not be set.
2. The I/Q magnitude computation (`sqrt(i^2 + q^2)`) is a reasonable default for converting I/Q to signal envelope. If the actual v0.1 model was trained on a different profile representation (e.g., phase, complex, or raw profiles), this might produce systematically different features. This is an empirical question that will be resolved by end-to-end smoke testing (PR0049).
3. The `run_preprocessing_bridge()` API change (adding `layout_context` param) is backward compatible — existing callers without it use the canonical path. But `run_inference()` does not yet pass `layout_context`. The bridge relies on `PreflightResult.metadata["target_group_path"]` instead. This works but is fragile — PR0048 should formalise the context flow.

FILES CHANGED:
- `.project-memory/pr/0047-calibration-sample-preprocessing-bridge/PLAN.md` — written

FASTAPI DEFERRAL SUMMARY:
FastAPI must be deferred until PR0047–PR0049 prove the end-to-end domain path. FastAPI must be a thin transport adapter only — no preprocessing, inference, model loading, or staging changes.

CURRENT STATE SUMMARY:
S3 staging ✓, metadata fallback ✓, layout adapter ✓, preflight with calibration refs ✓. Preprocessing bridge only supports canonical layout. Calibration sample preprocessing is the gap.

CALIBRATION H5 STRUCTURE SUMMARY:
/calib_*/sample_*/sets/set_*/integration/i (1D I component) and /integration/q (1D Q component). 3 sets per sample typical. Raw detector images not read.

PREPROCESSING CONTRACT SUMMARY:
Option A — extend preprocessing_bridge.py. Add `_extract_calibration_profiles()` that reads i/q → magnitude per set → list of profiles. Add `layout_context` param to `build_feature_table()` and `run_preprocessing_bridge()`. Add `target_group_path` + `control_group_path` to `PreflightResult.metadata` (in adapter path). Reuse existing 15 feature computation functions unchanged.

FEATURE SCHEMA SUMMARY:
Unchanged. `BREMEN_V01_FEATURE_COLUMNS` and `FEATURE_SCHEMA_VERSION` remain identical. Calibration preprocessing produces the same schema order through the same computation functions.

SET HANDLING DECISION:
All sets processed via sorted group key order. `magnitude = sqrt(i^2 + q^2)` per set → 1 profile per set → list of profiles → mean → same 15 feature functions.

SAFETY/PRIVACY SUMMARY:
No raw patient_name, raw feature values, raw scan arrays, or raw S3 URIs in logs. Only `integration/i` and `integration/q` read — no raw detector images. No weakening of canonical checks. No auto-selection.

TEST PLAN SUMMARY:
10 tests (A–J): canonical preserved, calibration i/q reading, multiple sets deterministic, missing i/q fails, mismatched I/Q lengths fails, schema order, no raw identifiers logged, no raw detector arrays read, optional real H5 smoke.

VALIDATION PLAN:
Follow AGENT_TEST_DEBUGGING_RULES.md. Compile all. Run 7 test suites. Verify no FastAPI deps. Verify only allowed files changed. Verify no forbidden changes. Verify feature schema unchanged.

BOUNDARY CONFIRMATIONS:
| Module | Changed? | Rationale |
|---|---|---|
| `preprocessing_bridge.py` | YES | Add `_extract_calibration_profiles()`, `layout_context` param, conditional branch |
| `preflight.py` | YES | Add `target_group_path`/`control_group_path` to metadata in adapter path |
| `h5_layouts.py` | No | Context already sufficient |
| `inference_handler.py` | No | Bridge APIs backward compatible |
| `app.py` | No | No wiring change needed |
| `schemas.py` | No | No schema change |
| All other files | No | Forbidden list |

IMPLEMENTATION AGENT ASSIGNMENT: coder
