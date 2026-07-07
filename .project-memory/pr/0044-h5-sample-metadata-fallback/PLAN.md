# PR 0044 — Plan: H5 Sample Metadata Fallback

## 1. Title / Branch / Objective

- **Title**: H5 Sample Metadata Fallback
- **Branch**: `0044-h5-sample-metadata-fallback`
- **Objective**: Add a controlled fallback in the H5 preflight gate so that when `/patient/id` is absent from an H5 container, a patient identifier can be resolved from sample-level `patient_name` fields under calibration groups. The fallback must be explicitly tracked via source metadata (`patient_identifier_source`, `metadata_fallback_used`). No silent equivalence between `patient_name` and `patient_id`. No raw patient identifiers in logs.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
9ca03d88252a5384c91f525851902f7c11b406ae

$ git branch --show-current
0044-h5-sample-metadata-fallback

$ git status --short
(clean — no uncommitted changes)
```

Required files all present:

- `src/bremen/api/preflight.py` ✓
- `src/bremen/api/preprocessing_bridge.py` ✓
- `src/bremen/api/inference_handler.py` ✓
- `tests/test_bremen_h5_preflight.py` ✓
- `tests/test_bremen_inference_integration.py` ✓

PR0043 is confirmed merged and deployed. Production App Runner smoke confirmed:
- `/predictions` accepts `h5_uri`
- S3 H5 staging starts and succeeds
- checksum verification succeeds
- staged local H5 reaches `inference_handler`
- logs show `bremen.prediction.h5.received`

---

## 3. Production Evidence from PR0043

Confirmed working in production App Runner after PR0043:
- `POST /predictions` with `h5_uri` + `h5_checksum` → 202 accepted, S3 download → staging → inference
- S3 staging logs present: `bremen.h5_input.stage.start` → `bremen.h5_input.checksum.verify.success` → `bremen.h5_input.stage.success`
- Staged H5 reaches `inference_handler`: `bremen.prediction.h5.received`

**Current failure** (smoke H5):

```
bremen.h5_input.stage.start
bremen.h5_input.checksum.verify.success
bremen.h5_input.stage.success
bremen.prediction.h5.received
bremen.prediction.failed exception_class=H5MetadataError safe_reason=Missing /patient/id
bremen.job.failed safe_reason=Missing /patient/id
```

The uploaded smoke H5 has no `/patient/id`. Preflight raises `H5MetadataError` immediately.

---

## 4. Real H5 Metadata Findings

Inspection of the production smoke H5 via `h5py` shows:

**Top-level structure:**
- `/calib_20260128_132622` (single calibration group)

**Sample groups under calibration:**

| Path | Value |
|---|---|
| `/calib_20260128_132622/sample_01_20260128_Nova_376_Right/sample/name` | `Nova_376_Right` |
| `/calib_20260128_132622/sample_01_20260128_Nova_376_Right/sample/patient_name` | `Nova_376` |
| `/calib_20260128_132622/sample_01_20260128_Nova_376_Right/sample/sample_type` | `RIGHT BREAST` |
| `/calib_20260128_132622/sample_02_20260128_Nova_376_Left/sample/name` | `Nova_376_Left` |
| `/calib_20260128_132622/sample_02_20260128_Nova_376_Left/sample/patient_name` | `Nova_376` |
| `/calib_20260128_132622/sample_02_20260128_Nova_376_Left/sample/sample_type` | `LEFT BREAST` |

Additional pairs present: Nova_378 (R/L), Nova_379 (R/L), Nova_383 (R/L), Nova_384 (R/L).

**Key structural differences from expected layout:**
- No `/patient/id` path
- No `/scans/target/...` or `/scans/contralateral/...` paths
- No `/patient/` group at all
- Data is organised by calibration group → sample groups, not by target/control scan labels
- `patient_name` is at the sample level, not the patient level

---

## 5. Current Preflight Metadata Behavior

The preflight pipeline in `src/bremen/api/preflight.py` currently:

1. Requires `/patient/id` to exist — `_get_patient_id()` raises `H5MetadataError("Missing /patient/id")` if absent
2. Validates `/scans/target/side`, `/scans/target/measurements`, `/scans/contralateral/side`, `/scans/contralateral/measurements` via `validate_required_metadata()`
3. Stores the patient ID as `PreflightResult.patient_id` and in `PreflightResult.metadata["patient_id"]`
4. Does NOT check for sample-level `patient_name`
5. Does NOT have any fallback mechanism

The current `PreflightResult` dataclass:
```python
@dataclass
class PreflightResult:
    status: str
    passed: bool
    reasons: list[PreflightReason]
    warnings: list[str]
    patient_id: str | None
    target_side: str | None
    contralateral_side: str | None
    target_measurement_count: int | None
    contralateral_measurement_count: int | None
    metadata: dict[str, Any]
    qc_flags: list[str]
```

No `patient_identifier_source`, `metadata_fallback_used`, or `patient_metadata_path` fields exist.

---

## 6. Proposed Fallback Contract

### `PatientMetadata` result class

Introduce a new helper class (in `preflight.py` or a narrow new module) that encapsulates the resolved patient metadata:

```python
@dataclass
class PatientMetadata:
    """Resolved patient identifier with source tracking."""
    patient_identifier: str
    patient_identifier_source: str  # "patient_id" or "patient_name_fallback"
    patient_metadata_path: str | None  # e.g., "/patient/id" or 
                                       # "/calib_.../sample_.../sample/patient_name"
    fallback_used: bool
```

### Resolution logic in `resolve_patient_metadata()`

```python
def resolve_patient_metadata(h5_file: h5py.File) -> PatientMetadata:
    """Resolve patient identifier from an H5 container.

    Primary: /patient/id
    Fallback: sample-level patient_name under calibration groups.

    Returns PatientMetadata with source tracking.
    Raises H5MetadataError if neither source yields a valid identifier.
    """
```

#### Step 1: Primary path
If `/patient/id` exists and is non-empty:
- `patient_identifier` = value from `/patient/id`
- `patient_identifier_source` = `"patient_id"`
- `patient_metadata_path` = `"/patient/id"`
- `fallback_used` = `False`
- Return immediately

#### Step 2: Fallback scan
If `/patient/id` is missing or empty:
1. Walk all `/calib_*/` groups
2. For each calibration group, walk `/calib_*/sample_*/sample/patient_name`
3. Collect all non-empty `patient_name` values found
4. Apply **ambiguity rejection rules** (see section 8)
5. If acceptable: `patient_identifier` = the resolved value, `patient_identifier_source` = `"patient_name_fallback"`, `patient_metadata_path` = first discovered path, `fallback_used` = `True`

### Changes to `PreflightResult`

Add two new fields:

```python
@dataclass
class PreflightResult:
    # ... existing fields ...
    patient_identifier_source: str = "patient_id"  # "patient_id" or "patient_name_fallback"
    metadata_fallback_used: bool = False
```

The existing `patient_id` field remains and will hold the resolved identifier string (from either path). These two new fields disambiguate the source. This preserves backward compatibility — any code reading `patient_id` continues to work, while new code can check the source.

### Changes to `_get_patient_id()` in preflight.py

Refactor `_get_patient_id()` to call `resolve_patient_metadata()` internally or split into two functions:
- A private `_get_patient_id_primary()` that tries `/patient/id` directly (current behavior, raises if missing)
- A public `_resolve_patient_identifier()` that wraps the primary + fallback

The top-level `run_h5_preflight()` will:
1. Call the resolver instead of `_get_patient_id()`
2. Record `patient_identifier_source` and `metadata_fallback_used` on the result
3. Include these in `PreflightResult.metadata`

### Not changing `validate_required_metadata()`

The `validate_required_metadata()` check still requires `/patient/id` for the **primary layout**. When the fallback is used, this check will fail — because `/patient/id`, `/scans/target/side`, `/scans/target/measurements`, `/scans/contralateral/side`, `/scans/contralateral/measurements` are all absent.

**This PR does NOT modify `validate_required_metadata()` or `_get_scan_side_and_measurements()`**. The fallback only affects patient identifier resolution. The container structure layout fallback (calibration groups → scan paths) is deferred to a future PR.

This means that even after PR0044, preflight on the real H5 will still fail — but **not** at "Missing /patient/id". It will fail at `Missing required metadata paths: ['/patient/id', '/scans/target/side', '/scans/target/measurements', '/scans/contralateral/side', '/scans/contralateral/measurements']`. This is the correct boundary for this PR.

---

## 7. Safety and Privacy Rules

1. **No raw patient_name in logs**: The `patient_name` value must never appear in log output. The resolver must not log the identifier value at any level.
2. **No raw patient_id in logs**: Same constraint — already enforced in the codebase, verified via caplog tests.
3. **No weakening of target/control consistency**: The fallback only affects patient identifier resolution. It does not change any scan-side, measurement, or structural checks.
4. **No silent fallback**: If fallback is used, `metadata_fallback_used` must be `True` and `patient_identifier_source` must be `"patient_name_fallback"`. Downstream consumers can check these fields.
5. **No inference or preprocessing changes**: The resolver is purely a metadata operation inside `preflight.py`.
6. **No model loading changes**: Absolutely none.
7. **No S3 staging changes**: Absolutely none.
8. **Empty value rejection**: Empty string `patient_name` values are rejected the same way as missing.

---

## 8. Ambiguity Handling

### Rules (conservative)

1. **Collect all sample/patient_name values** across all calibration groups and all sample groups.
2. **Reject if none found**: Raise `H5MetadataError` with message indicating no patient identifier could be resolved.
3. **Reject if any value is empty**: Raise `H5MetadataError` if a `patient_name` dataset exists but contains an empty string.
4. **Reject if multiple distinct patient_name values exist**: If the set of unique non-empty `patient_name` values has cardinality > 1, raise `H5MetadataError` — do not silently choose one.

### Why "reject if > 1 distinct value"?

Because the current `run_h5_preflight()` has **no target/control scan selection logic**. There is no mechanism to determine which sample is the "target" and which is the "control". Without that context, choosing one patient name from several distinct values would be non-deterministic. A future PR that adds calibration-group scan selection can relax this rule by restricting the search to only the selected target/control samples.

### Example scenarios

| H5 contents | Distinct patient_name values | Verdict |
|---|---|---|
| `/patient/id = "P001"` | N/A (primary used) | Pass — primary |
| `{/calib_*/sample_*/sample/patient_name: "Nova_376"}` (×2 samples, same value) | 1 | Pass — fallback with source tracking |
| `{/calib_*/sample_*/sample/patient_name: ""}` | 0 (empty) | Reject — H5MetadataError |
| `{/calib_*/sample_*/sample/patient_name: "Nova_376"}` and `{...patient_name: "Nova_378"}` | 2 | Reject — ambiguous without scan selection context |
| No `/patient/id`, no `/calib_*/.../patient_name` | 0 | Reject — H5MetadataError |

---

## 9. App / Inference Impact

### `app.py` — No changes
`handle_submit_prediction()` calls `run_inference()` which calls `run_h5_preflight()`. The fallback is transparent to `app.py`.

### `inference_handler.py` — No changes
`run_inference()` already handles `preflight.patient_id` being `None` (it falls back to "unknown"). With the fallback, `preflight.patient_id` will be populated from `patient_name`. No logic change needed.

However, the new `patient_identifier_source` and `metadata_fallback_used` fields on `PreflightResult` will be available for future use in prediction metadata. This PR does not require `inference_handler.py` to read them, but they will be accessible.

### `preprocessing_bridge.py` — No changes
The bridge uses `preflight_result.patient_id` to populate `BremenFeatureVector.patient_id`. Since `patient_id` still contains the resolved identifier, the bridge works unchanged.

### PreflightResult consumer compatibility
- `PreflightResult.patient_id` remains a valid identifier string (from either source)
- New fields `patient_identifier_source` and `metadata_fallback_used` are optional (defaults preserve backward compat)
- `PreflightResult.metadata` gains `"patient_identifier_source"` and `"metadata_fallback_used"` keys

---

## 10. Test Plan

All tests in `tests/test_bremen_h5_sample_metadata.py` (new file) unless otherwise noted.

### A. `test_preflight_uses_patient_id_when_present`

Goal: Verify current behavior is preserved when `/patient/id` exists.

- Create synthetic H5 with `/patient/id = "P001"`, valid `/scans/target/` and `/scans/contralateral/`
- Assert: `run_h5_preflight()` passes, `patient_id == "P001"`
- Assert: `patient_identifier_source == "patient_id"`
- Assert: `metadata_fallback_used is False`

### B. `test_preflight_falls_back_to_sample_patient_name_when_patient_id_missing`

Goal: Verify fallback works for real-layout-like H5 with no `/patient/id`.

- Create synthetic H5 with:
  - `/calib_20260128_132622/sample_01_Right/sample/patient_name = "Nova_376"`
  - `/calib_20260128_132622/sample_02_Left/sample/patient_name = "Nova_376"`
  - Both values identical
- Also create `/scans/target/...` and `/scans/contralateral/...` (to avoid secondary structure failures)
- Assert: `run_h5_preflight()` does NOT raise `H5MetadataError("Missing /patient/id")`
- Assert: `patient_id == "Nova_376"`
- Assert: `patient_identifier_source == "patient_name_fallback"`
- Assert: `metadata_fallback_used is True`

### C. `test_preflight_rejects_missing_patient_id_and_missing_patient_name`

Goal: Verify strict rejection when neither source is available.

- Create synthetic H5 with no `/patient/id` and no sample `patient_name` paths
- Also create `/scans/target/...` and `/scans/contralateral/...`
- Assert: `H5MetadataError` raised

### D. `test_preflight_rejects_empty_sample_patient_name`

Goal: Verify empty `patient_name` values are rejected.

- Create synthetic H5 with:
  - `/calib_*/sample_01/sample/patient_name = ""` (empty string)
  - No `/patient/id`
- Assert: `H5MetadataError` raised

### E. `test_preflight_rejects_ambiguous_sample_patient_names`

Goal: Verify multiple distinct `patient_name` values are rejected conservatively.

- Create synthetic H5 with:
  - `/calib_*/sample_01/sample/patient_name = "Nova_376"`
  - `/calib_*/sample_02/sample/patient_name = "Nova_378"`
  - No `/patient/id`
- Assert: `H5MetadataError` raised (ambiguous, no selection context)

### F. `test_preflight_does_not_log_raw_patient_name`

Goal: Privacy — no raw patient identifier in logs.

- Use `caplog`
- Run preflight with fallback path (`patient_name = "Nova_376"`)
- Assert: log text does not contain `"Nova_376"`, `"patient_name"` or similar identifier strings
- The log may contain safe metadata like `patient_identifier_source` or `fallback_used` but never the raw value

### G. `test_resolve_patient_metadata_primary_path`

Goal: Unit test the resolver directly when `/patient/id` exists.

- Call `resolve_patient_metadata()` (or equivalent) on an H5 with `/patient/id`
- Assert: returns `PatientMetadata(fallback_used=False, patient_identifier_source="patient_id")`

### H. `test_resolve_patient_metadata_fallback_path`

Goal: Unit test the resolver directly with sample-level `patient_name`.

- Call `resolve_patient_metadata()` on H5 with fallback structure
- Assert: returns `PatientMetadata(fallback_used=True, patient_identifier_source="patient_name_fallback")`

### I. Optional real H5 smoke (skipped by default)

Add to `tests/test_bremen_h5_preflight.py` (modify existing opt-in `test_real_subset_schema_inspection`):

```python
@pytest.mark.skipif(
    "BREMEN_SMOKE_H5_PATH" not in os.environ,
    reason="Set BREMEN_SMOKE_H5_PATH to run real H5 smoke",
)
def test_preflight_no_longer_fails_at_missing_patient_id():
    """Assert preflight no longer fails specifically at Missing /patient/id.
    
    NOTE: Preflight may still fail due to missing /scans/ layout paths.
    This test only asserts the specific /patient/id error is gone.
    """
    h5_path = os.environ["BREMEN_SMOKE_H5_PATH"]
    try:
        result = run_h5_preflight(h5_path)
        # If preflight passes, verify source tracking
        if result.passed:
            assert hasattr(result, "patient_identifier_source")
            assert result.metadata_fallback_used == \
                (result.patient_identifier_source == "patient_name_fallback")
    except H5MetadataError as e:
        # Must not fail on "Missing /patient/id"
        assert "Missing /patient/id" not in str(e), \
            f"Still failing on missing /patient/id: {e}"
        # Other metadata errors (e.g., missing /scans/) are expected
```

---

## 11. Non-Goals

This PR explicitly does NOT address:

- Container structure fallback (calibration groups → `/scans/target/` / `/scans/contralateral/`)
- Target/control scan selection from calibration samples
- Side resolution from `sample_type` (LEFT BREAST / RIGHT BREAST)
- Measurement extraction from calibration groups
- Matador integration / prediction result reporting
- S3 staging changes
- Model loading changes
- Inference math or preprocessing feature formula changes
- Broad H5 layout migration
- Automatic patient identity mapping beyond controlled fallback
- Clinical claims
- ADR, ROADMAP, or docs/architecture.md changes
- CI/CD, Docker, infra, or dependency changes

---

## 12. Validation Checklist

```bash
# Git state
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile check
python -m compileall src tests

# Test runs
python -m pytest -q tests/test_bremen_h5_preflight.py -v
python -m pytest -q tests/test_bremen_h5_sample_metadata.py -v
python -m pytest -q tests/test_bremen_inference_integration.py -v
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_logging.py
python -m pytest -q

# Code coverage — new fallback code
grep -n "resolve_patient_metadata\|patient_identifier_source\|metadata_fallback_used\|patient_name_fallback\|patient_metadata_path" \
  src/bremen/api/preflight.py tests/test_bremen_h5_sample_metadata.py

# Privacy — no raw identifiers in logs
grep -R "patient_name" -n src/bremen tests/
# Allowed: in test assertions, in resolver logic, in dataclass fields
# Forbidden: in log format strings, in log event extra data

# No forbidden fields logged
grep -R "patient_identifier_source\|metadata_fallback_used" -n src/bremen tests/
# These are safe metadata fields — verify they appear only in intended locations

# No artifact leaks
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" \
  -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) \
  -not -path "./.git/*" -not -path "./venv/*" -print

# Forbidden changes check
git diff --name-only -- docs/adr ROADMAP.md docs/architecture.md \
  src/bremen/training \
  .github Dockerfile infra requirements.txt pyproject.toml \
  src/bremen/model_artifacts.py \
  src/bremen/model_loader.py \
  src/bremen/api/model_state.py \
  src/bremen/h5_inputs.py
```

---

## 13. Forbidden Changes

The implementation agent MUST NOT:

1. Modify `src/bremen/api/app.py`
2. Modify `src/bremen/api/inference_handler.py`
3. Modify `src/bremen/api/preprocessing_bridge.py`
4. Modify `src/bremen/api/model_state.py`
5. Modify `src/bremen/model_artifacts.py`
6. Modify `src/bremen/h5_inputs.py` (S3 staging)
7. Modify `src/bremen/training/**`
8. Modify `docs/adr/`, `ROADMAP.md`, `docs/architecture.md`
9. Modify `.github/`, `Dockerfile`, `infra/`, `requirements.txt`, `pyproject.toml`
10. Commit real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` artifacts
11. Commit secrets, account IDs, or access keys
12. Weaken target/control consistency checks (side mismatch, missing scans)
13. Change inference math or preprocessing feature formulas
14. Change model loading
15. Log raw `patient_name` or `patient_id` values
16. Treat `patient_name` as `patient_id` without recording `patient_identifier_source`
17. Accept ambiguous multiple patient names without rejection (see section 8)
18. Require real H5 access for default unit tests
19. Modify `docs/adr/`, `ROADMAP.md`, or `docs/architecture.md`

---

## 14. Rollback Plan

If the fallback introduces regressions:

1. **Immediate rollback**: `git revert HEAD` on `0044-h5-sample-metadata-fallback` branch
2. Verify revert via:
   - `python -m pytest -q tests/test_bremen_h5_preflight.py -v`
   - `python -m pytest -q tests/test_bremen_inference_integration.py -v`
   - `python -m pytest -q tests/test_bremen_predictions.py -v`
   - `python -m pytest -q`
3. Open revert PR with label `revert/0044`
4. Document the failure mode

### Partial rollback (resolver only)

If only the `PreflightResult` field additions cause issues, revert those and keep the resolver as a standalone helper function without wiring it into `run_h5_preflight()`. The resolver can be called externally by test code or future PRs.

---

## 15. Implementation Agent Assignment

**Implementation agent**: coder

---

## 16. Files Changed (Plan)

| File | Action | Rationale |
|---|---|---|
| `src/bremen/api/preflight.py` | **Modified** — add `resolve_patient_metadata()`, `PatientMetadata` dataclass; add `patient_identifier_source` and `metadata_fallback_used` fields to `PreflightResult`; modify `_get_patient_id()` call in `run_h5_preflight()` to use resolver; update `run_h5_preflight()` to populate new result fields | Core fallback implementation |
| `tests/test_bremen_h5_sample_metadata.py` | **New** — 8+ tests covering primary path, fallback, rejection cases, ambiguity, logging safety, real H5 smoke | Isolated coverage of the fallback logic |
| `tests/test_bremen_h5_preflight.py` | **Modified** — update existing opt-in smoke test to assert no longer fails on `Missing /patient/id`; update any assertions on `PreflightResult` that may be affected by new fields | Ensure existing tests remain compatible |
| `tests/test_bremen_predictions.py` | **Modified only if needed** — narrow updates to existing smoke error expectations | Per allowed list |
| `tests/test_bremen_inference_integration.py` | **Modified only if needed** — narrow updates to existing integration assertions | Per allowed list |

---

## 17. Plan Summary

| Aspect | Detail |
|---|---|
| **Problem** | Preflight requires `/patient/id`; real production H5 containers store patient info as sample-level `patient_name` under calibration groups |
| **Solution** | Add `resolve_patient_metadata()` in `preflight.py` that tries `/patient/id` first, then falls back to sample `patient_name` with explicit source tracking |
| **Safety** | `patient_identifier_source` distinguishes `"patient_id"` from `"patient_name_fallback"`; `metadata_fallback_used` is `True` when fallback is active; no raw identifiers in logs |
| **Ambiguity** | Reject >1 distinct patient_name values (no selection context yet); reject empty values; reject missing |
| **Scope** | Patient identifier resolution only — no container structure fallback, no scan selection, no preprocessing changes, no inference changes, no S3 changes |
| **Boundary** | Even with this PR, preflight on the real H5 will still fail on missing `/scans/target/` structure — that is expected and deferred |
| **Test coverage** | 8+ new tests in new file, plus modifications to existing tests |

---

## 18. REAL H5 METADATA FINDINGS

| Observation | Detail |
|---|---|
| Top-level structure | Single calibration group `/calib_20260128_132622` — no `/patient/` group |
| Patient metadata | Sample-level `patient_name` like `Nova_376` under `/calib_*/sample_*/sample/patient_name` |
| Multiple patients | 5 patients present: Nova_376, Nova_378, Nova_379, Nova_383, Nova_384 |
| Side info | `sample_type` values `RIGHT BREAST` / `LEFT BREAST` at same sample path |
| No `/patient/id` | Confirmed absent |
| No `/scans/` structure | Confirmed absent — no `/scans/target/` or `/scans/contralateral/` groups |
| Container structure | Significantly different from expected layout — calibration-group organised |

## 19. CURRENT PREFLIGHT BEHAVIOR

| Check | Location | Current behavior |
|---|---|---|
| Patient ID | `_get_patient_id()` in `preflight.py:391` | Requires `/patient/id`; raises `H5MetadataError("Missing /patient/id")` if absent |
| Required metadata | `validate_required_metadata()` in `preflight.py:287` | Requires `/patient/id`, `/scans/target/side`, `/scans/target/measurements`, `/scans/contralateral/side`, `/scans/contralateral/measurements` |
| Side validation | `validate_opposite_sides()` in `preflight.py:257` | Requires L/R or LEFT/RIGHT opposite pair |
| Measurement count | `validate_measurement_counts()` in `preflight.py:319` | Requires >= 1 measurement per scan |
| Target/control selection | `_get_scan_side_and_measurements()` in `preflight.py:409` | Uses static paths `/scans/target/` and `/scans/contralateral/` — no dynamic selection |
| Result fields | `PreflightResult` | Has `patient_id`, no source tracking fields |

## 20. FALLBACK CONTRACT

```
resolve_patient_metadata(h5_file) -> PatientMetadata
                                   or -> raises H5MetadataError

Primary path (unchanged):
  /patient/id exists and non-empty:
    patient_identifier = value
    patient_identifier_source = "patient_id"
    fallback_used = False

Fallback path (new):
  /patient/id missing or empty:
    scan all /calib_*/sample_*/sample/patient_name paths
    collect unique non-empty values
    if 0 values: raise H5MetadataError("No patient identifier found")
    if >1 distinct values: raise H5MetadataError("Ambiguous patient names")
    if 1 distinct value:
      patient_identifier = that value
      patient_identifier_source = "patient_name_fallback"
      fallback_used = True

PreflightResult additions:
  patient_identifier_source: str = "patient_id"
  metadata_fallback_used: bool = False
  metadata["patient_identifier_source"] = source
  metadata["metadata_fallback_used"] = fallback_used
```

## 21. AMBIGUITY HANDLING

| Scenario | Result |
|---|---|
| 0 distinct patient_name values | Reject — H5MetadataError |
| 1 distinct patient_name value | Accept — fallback used |
| 2+ distinct patient_name values | Reject — no selection context |
| Empty string patient_name | Treated as missing |
| Mixed empty + non-empty | Only non-empty considered for distinct count |
| `/patient/id` exists alongside patient_name | Primary used; patient_name ignored |

Future PRs with scan selection can relax the ambiguity rule by restricting the search to only the selected target/control samples.

## 22. SAFETY/PRIVACY SUMMARY

| Rule | Enforcement |
|---|---|
| No raw patient_name in logs | Caplog test F; resolver must not log the value |
| No raw patient_id in logs | Existing invariant; caplog test extends to new paths |
| Source tracking mandatory | `patient_identifier_source` must be set correctly |
| No silent fallback | `metadata_fallback_used` must be `True` when fallback active |
| Target/control checks unchanged | No modification to side validation, measurement count, or scan path checks |
| Inference/preprocessing/model unchanged | Forbidden files list |
| No real H5 in tests | All tests use synthetic H5; smoke is opt-in with env guard |

## 23. TEST PLAN SUMMARY

| Test | File | What it verifies |
|---|---|---|
| A. Primary path preserved | `test_bremen_h5_sample_metadata.py` | `/patient/id` works; source=`"patient_id"`; fallback_used=`False` |
| B. Fallback to patient_name | `test_bremen_h5_sample_metadata.py` | No `/patient/id`; patient_name resolves; source=`"patient_name_fallback"` |
| C. Reject missing both | `test_bremen_h5_sample_metadata.py` | No `/patient/id`, no patient_name → H5MetadataError |
| D. Reject empty patient_name | `test_bremen_h5_sample_metadata.py` | Empty patient_name → H5MetadataError |
| E. Reject ambiguous names | `test_bremen_h5_sample_metadata.py` | Multiple distinct patient_name → H5MetadataError |
| F. No raw name in logs | `test_bremen_h5_sample_metadata.py` | caplog: no raw identifier value in logs |
| G. Resolver unit: primary | `test_bremen_h5_sample_metadata.py` | Direct resolver call, primary path |
| H. Resolver unit: fallback | `test_bremen_h5_sample_metadata.py` | Direct resolver call, fallback path |
| I. Real H5 smoke (opt-in) | `test_bremen_h5_preflight.py` (modified) | No longer fails on "Missing /patient/id" |

## 24. BOUNDARY CONFIRMATIONS

| Module | Changed? | Rationale |
|---|---|---|
| `src/bremen/api/preflight.py` | **YES** | Patient metadata resolver + PreflightResult fields |
| `src/bremen/api/preprocessing_bridge.py` | No | Bridge unchanged — patient_id still populated |
| `src/bremen/api/inference_handler.py` | No | No logic change needed |
| `src/bremen/api/app.py` | No | Transparent to handler |
| `src/bremen/api/schemas.py` | No | No schema change needed |
| `src/bremen/api/jobs.py` | No | No job logic change |
| `src/bremen/h5_inputs.py` | No | S3 staging unchanged |
| `src/bremen/model_artifacts.py` | No | Not modified |
| `src/bremen/api/model_state.py` | No | Not modified |
| `src/bremen/training/**` | No | Forbidden |
| `docs/adr/`, `ROADMAP.md` | No | Forbidden |
| `.github/`, `Dockerfile`, `infra/` | No | Forbidden |
| `requirements.txt`, `pyproject.toml` | No | Forbidden |

## 25. IMPLEMENTATION AGENT ASSIGNMENT

Implementation agent: coder

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. Even after this PR, the real smoke H5 will still fail preflight due to missing `/scans/target/` and `/scans/contralateral/` structure — that is expected and acknowledged as a future PR scope.
2. The `validate_required_metadata()` function still requires `/patient/id` in its required paths list. The implementation should consider whether to conditionally exclude `/patient/id` from required paths when fallback is active, or leave it as a pre-existing metadata error. **Recommendation**: Leave it as is — the resolver handles the patient identifier, but the metadata check still validates the structural contract. If fallback is used and `/patient/id` is absent, `validate_required_metadata()` will report it missing, which is correct for the primary layout contract.
3. The existing opt-in smoke test `test_real_subset_schema_inspection` in `test_bremen_h5_preflight.py` asserts `result.patient_id is not None`. With the fallback in place for a real H5, this assertion may now pass even if the broader preflight fails — but the test currently wraps `run_h5_preflight()` directly. If preflight raises H5MetadataError (from `validate_required_metadata()`), the test will catch the exception, not reach the assertion. The plan modifies this test to catch the specific error and verify it's not about `/patient/id`.
4. Test assertions that check `len(result.reasons) >= 6` may need updating since the reasons list may include additional fallback-related reasons.

FILES CHANGED:
- `src/bremen/api/preflight.py` — modified (add resolver + PreflightResult fields)
- `tests/test_bremen_h5_sample_metadata.py` — new (8+ tests)
- `tests/test_bremen_h5_preflight.py` — modified (update opt-in smoke test)
- `tests/test_bremen_predictions.py` — possibly modified (narrow updates only)
- `tests/test_bremen_inference_integration.py` — possibly modified (narrow updates only)

PLAN SUMMARY: Add a controlled H5 patient metadata fallback in `preflight.py` so that when `/patient/id` is absent, a patient identifier is resolved from sample-level `patient_name` under calibration groups. The fallback is conservative — rejects empty values, rejects ambiguous (>1 distinct) values, and always records the source via `patient_identifier_source` and `metadata_fallback_used` fields on `PreflightResult`. No raw identifiers in logs. No changes to inference, preprocessing, model loading, S3 staging, or container structure validation. Container structure fallback (calibration groups → scan paths) is explicitly deferred. 8+ new tests in a dedicated test file.

REAL H5 METADATA FINDINGS: Production smoke H5 has no `/patient/id`, no `/scans/` structure. Instead it uses `/calib_20260128_132622/sample_*/sample/patient_name` for patient identity and `sample_type` for side. Multiple patients (5) present.

CURRENT PREFLIGHT BEHAVIOR: `_get_patient_id()` requires `/patient/id` and raises `H5MetadataError("Missing /patient/id")`. No fallback mechanism. `PreflightResult` has `patient_id` but no source tracking.

FALLBACK CONTRACT: `resolve_patient_metadata(h5_file)` → `PatientMetadata` with `patient_identifier`, `patient_identifier_source` (`"patient_id"` or `"patient_name_fallback"`), `patient_metadata_path`, `fallback_used`. Wired into `_get_patient_id()` so `run_h5_preflight()` uses it transparently.

AMBIGUITY HANDLING: Reject if 0 values, reject if >1 distinct values (no selection context), reject if empty. Only 1 distinct non-empty value is accepted.

SAFETY/PRIVACY SUMMARY: No raw identifiers in logs, source tracking mandatory, target/control checks unchanged, inference/preprocessing/model unchanged, no real H5 in default tests.

TEST PLAN SUMMARY: 8 tests — primary path preserved, fallback works, missing rejected, empty rejected, ambiguous rejected, no raw name in logs, resolver unit tests (primary + fallback), plus opt-in real H5 smoke test.

BOUNDARY CONFIRMATIONS: Only `preflight.py` and test files modified. All other modules explicitly unchanged. Container structure fallback deferred. Target/control selection deferred.

IMPLEMENTATION AGENT ASSIGNMENT: coder
