# PR 0045 — Plan: H5 Layout Adapter Boundary

## 1. Title / Branch / Objective

- **Title**: H5 Layout Adapter Boundary
- **Branch**: `0045-h5-layout-adapter-boundary`
- **Objective**: Introduce an H5 layout adapter/plugin boundary in preflight so that Bremen can support multiple H5 container layouts without hardcoding every future H5 shape. Add a `CalibrationSampleH5LayoutAdapter` that resolves explicit `target_scan_ref` and `control_scan_ref` paths for the real calibration-sample H5 layout. The canonical layout remains as the default with zero regression. Preprocessing feature extraction is **not** changed — that is PR0046.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
af447e65592d32946ce6d7672d7f9f79cd0e513f

$ git branch --show-current
0045-h5-layout-adapter-boundary

$ git status --short
(clean — no uncommitted changes)
```

Required files all present:
- `src/bremen/api/preflight.py`
- `src/bremen/api/preprocessing_bridge.py`
- `src/bremen/api/inference_handler.py`
- `tests/test_bremen_h5_preflight.py`
- `tests/test_bremen_h5_sample_metadata.py`
- `tests/test_bremen_inference_integration.py`
- `tests/test_bremen_predictions.py`

PR0043 and PR0044 are confirmed merged and deployed.

---

## 3. Production Evidence from PR0043 and PR0044

Confirmed working in production App Runner after PR0043:
- `POST /predictions` with `h5_uri` + `h5_checksum` -> 202 accepted, S3 download -> staging -> inference
- S3 staging logs: `bremen.h5_input.stage.start` -> `bremen.h5_input.checksum.verify.success` -> `bremen.h5_input.stage.success`

Confirmed working in production App Runner after PR0044:
- Missing `/patient/id` no longer raises H5MetadataError — fallback activates
- Sample `patient_name` values are resolved when all samples share the same patient
- Multi-patient H5 safely fails with `Ambiguous sample patient_name metadata`
- Raw `Nova_*` values do not appear in logs

**Current production smoke failure:**
```json
{
  "h5_uri": "s3://matur-misc-uk/bremen/prediction-inputs/smoke/v0.1/aramis_real_h5_subset_20260128_5_patients.h5",
  "h5_checksum": "sha256:0bda036f08b057d992b329f6bd6834b3bb52cb74b1f3fca3efb08dda5edf655a",
  "target_scan_ref": "target",
  "control_scan_ref": "control",
  "patient_id": "smoke_test"
}
```
Returns: `Ambiguous sample patient_name metadata` — correct because the H5 contains 5 patients and no explicit sample refs were provided. With the adapter approach and explicit refs, preflight can resolve a specific patient pair.

---

## 3. Real Calibration Sample H5 Layout Findings

### Top-level structure
```
/calib_20260128_132622
```

### Sample groups under calibration
```
/calib_20260128_132622/sample_01_20260128_Nova_376_Right/
  sample/
    name           = "Nova_376_Right"
    patient_name   = "Nova_376"
    sample_type    = "RIGHT BREAST"
  sets/
    set_001_sample_main/
      integration/
        i   (dataset, 1D)
        q   (dataset, 1D)
      measurements/
        det_1_ash512x768/
          data  (dataset)
      raw/
        data  (dataset)
    set_002_sample_main/  (same structure)
    set_003_sample_main/  (same structure)

/calib_20260128_132622/sample_02_20260128_Nova_376_Left/
  sample/
    name           = "Nova_376_Left"
    patient_name   = "Nova_376"
    sample_type    = "LEFT BREAST"
  sets/...   (same layout)

... (additional patients: Nova_378 R/L, Nova_379 R/L, Nova_383 R/L, Nova_384 R/L)
```

### Key differences from canonical layout

| Aspect | Canonical (current) | Calibration Sample (real) |
|---|---|---|
| Patient ID | `/patient/id` | `sample/patient_name` under each sample group |
| Scan paths | `/scans/target/`, `/scans/contralateral/` | Dynamic sample groups per patient |
| Side | `side` dataset (L/R/LEFT/RIGHT) | `sample/sample_type` (`RIGHT BREAST`/`LEFT BREAST`) |
| Measurements | `/scans/{label}/measurements` (2D array) | `sets/set_*/integration/i`, `sets/set_*/integration/q` (per-set) |
| Multiple patients | One patient per container | Multiple patients per container |
| Target/control selection | Fixed logical paths | Explicit `target_scan_ref`/`control_scan_ref` required |

---

## 4. Current Canonical Assumptions

The current `preflight.py` encodes the canonical layout directly:

1. `_get_scan_side_and_measurements(f, "target")` hardcodes `/scans/target/side` and `/scans/target/measurements`
2. `validate_required_metadata()` lists `/scans/target/side`, `/scans/target/measurements`, `/scans/contralateral/side`, `/scans/contralateral/measurements` as required
3. `validate_opposite_sides()` expects L/R/LEFT/RIGHT values
4. `_get_patient_id()` now delegates to `resolve_patient_metadata()` (PR0044)
5. `run_h5_preflight()` accepts only `h5_path` — no `target_scan_ref` or `control_scan_ref` parameters

The current `preprocessing_bridge.py` also hardcodes:
1. `_extract_profiles(f, "target")` reads `/scans/target/measurements`
2. `build_feature_table()` hardcodes `"target"` and `"contralateral"` scan labels

**Key insight**: `target_scan_ref` and `control_scan_ref` are **validated and stored in `PredictionRequest`** (in `schemas.py`) but are **never passed to `run_inference()`** or `run_h5_preflight()`. They exist as unused metadata.

---

## 5. Proposed Adapter/Plugin Boundary

### New module: `src/bremen/api/h5_layouts.py`

A narrow module defining the adapter protocol and built-in adapters.

### Core types

```python
@dataclass
class H5PredictionContext:
    """Resolved prediction context from an H5 layout adapter."""
    layout_name: str                          # "canonical" or "calibration_sample"
    target_scan_ref: str                       # Original ref from request
    control_scan_ref: str                      # Original ref from request
    target_group_path: str                     # Resolved absolute H5 group path
    control_group_path: str                    # Resolved absolute H5 group path
    target_side: str | None                    # Normalised side (L/R/LEFT/RIGHT)
    control_side: str | None                   # Normalised side (L/R/LEFT/RIGHT)
    patient_identifier: str                    # Resolved patient identifier
    patient_identifier_source: str             # "patient_id" or "patient_name_fallback"
    metadata_fallback_used: bool               # True if fallback was needed
    target_measurement_count: int | None       # Preflight measurement count
    control_measurement_count: int | None      # Preflight measurement count
    adapter_metadata: dict[str, Any]           # Adapter-specific data

class H5LayoutAdapter(ABC):
    """Abstract base for H5 layout adapters."""
    name: str
    
    @abstractmethod
    def detect(self, h5_file: h5py.File) -> bool:
        """Return True if this adapter can handle the H5 layout."""
    
    @abstractmethod
    def resolve_prediction_context(
        self,
        h5_file: h5py.File,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> H5PredictionContext:
        """Resolve target/control refs to a prediction context.
        
        Raises H5MetadataError, H5ContainerError, H5SideMismatchError
        on validation failure.
        """
```

### Adapter registry

```python
_BUILTIN_ADAPTERS: list[H5LayoutAdapter] = [
    CanonicalH5LayoutAdapter(),
    CalibrationSampleH5LayoutAdapter(),
]

def detect_layout(h5_file: h5py.File) -> H5LayoutAdapter:
    """Detect the H5 layout by trying registered adapters in order.
    
    Returns the first adapter whose detect() returns True.
    Raises H5ContainerError if no adapter matches.
    """
    for adapter in _BUILTIN_ADAPTERS:
        if adapter.detect(h5_file):
            return adapter
    raise H5ContainerError("Unrecognised H5 container layout")
```

---

## 6. Adapter Contract

### Detection rules

**CanonicalH5LayoutAdapter.detect()**:
- Returns `True` if `/scans/target/measurements` exists in the H5 file
- This is a simple, reliable detection: all canonical H5 files have this path

**CalibrationSampleH5LayoutAdapter.detect()**:
- Returns `True` if:
  - At least one top-level group key starts with `calib_`
  - At least one descendant has a `sample/patient_name` dataset
  - At least one descendant has a `sample/sample_type` dataset
  - There is **no** `/scans/target/measurements` path (mutually exclusive with canonical)
- This prevents the calibration adapter from falsely claiming a canonical layout H5

### Resolution rules (both adapters)

Both adapters accept `target_scan_ref` and `control_scan_ref` as strings.
- For the **canonical adapter**: refs are validated but **not used for path resolution** — data is at fixed `/scans/target/` and `/scans/contralateral/`
- For the **calibration adapter**: refs are resolved as relative H5 group paths under root (no leading `/`)

### Ref path handling

Adapters normalise refs consistently:
- Reject refs containing `..` (path traversal)
- Reject refs beginning with `/` (absolute paths not allowed in refs)
- Reject empty or whitespace-only refs
- Reject refs that don't correspond to existing groups in the H5 file

---

## 7. Canonical Adapter Plan

### `CanonicalH5LayoutAdapter`

```python
class CanonicalH5LayoutAdapter(H5LayoutAdapter):
    name = "canonical"
    
    def detect(self, h5_file):
        return "/scans/target/measurements" in h5_file
    
    def resolve_prediction_context(self, h5_file, target_scan_ref, control_scan_ref):
        # Validate refs exist (but don't use for path resolution)
        if not target_scan_ref or target_scan_ref.strip() != "target":
            raise H5MetadataError("target_scan_ref for canonical layout must be 'target'")
        if not control_scan_ref or control_scan_ref.strip() != "contralateral":
            raise H5MetadataError("control_scan_ref for canonical layout must be 'contralateral'")
        
        # Use existing resolve_patient_metadata for patient ID
        patient_meta = resolve_patient_metadata(h5_file)
        
        # Read sides
        target_side = _read_side(h5_file, "/scans/target/side")
        control_side = _read_side(h5_file, "/scans/contralateral/side")
        
        # Read measurements for counting
        target_measurements = h5_file["/scans/target/measurements"][:]
        control_measurements = h5_file["/scans/contralateral/measurements"][:]
        target_count = len(target_measurements) if target_measurements.size > 0 else 0
        control_count = len(control_measurements) if control_measurements.size > 0 else 0
        
        return H5PredictionContext(
            layout_name="canonical",
            target_scan_ref=target_scan_ref,
            control_scan_ref=control_scan_ref,
            target_group_path="/scans/target",
            control_group_path="/scans/contralateral",
            target_side=target_side,
            control_side=control_side,
            patient_identifier=patient_meta.patient_identifier,
            patient_identifier_source=patient_meta.patient_identifier_source,
            metadata_fallback_used=patient_meta.fallback_used,
            target_measurement_count=target_count,
            control_measurement_count=control_count,
            adapter_metadata={},
        )
```

### Backward compatibility

- Existing callers of `run_h5_preflight(h5_path)` without refs: the canonical adapter is used (detection based on `/scans/target/measurements` presence)
- Existing callers that pass `target_scan_ref="target"` / `control_scan_ref="contralateral"`: works identically
- All existing tests pass without modification

---

## 8. Calibration Sample Adapter Plan

### `CalibrationSampleH5LayoutAdapter`

```python
class CalibrationSampleH5LayoutAdapter(H5LayoutAdapter):
    name = "calibration_sample"
    
    def detect(self, h5_file):
        # Must NOT claim canonical layouts
        if "/scans/target/measurements" in h5_file:
            return False
        # Look for calibration group with sample metadata
        for key in h5_file.keys():
            if key.startswith("calib_"):
                if _has_sample_metadata(h5_file[key]):
                    return True
        return False
    
    def resolve_prediction_context(self, h5_file, target_scan_ref, control_scan_ref):
        # Validate refs
        _validate_ref(target_scan_ref)
        _validate_ref(control_scan_ref)
        
        # Build absolute paths
        target_path = f"/{target_scan_ref}"
        control_path = f"/{control_scan_ref}"
        
        # Verify groups exist
        if target_path not in h5_file:
            raise H5ContainerError(f"Target scan group not found")
        if control_path not in h5_file:
            raise H5ContainerError(f"Control scan group not found")
        
        # Verify patient_name consistency
        target_pn = _read_sample_metadata(h5_file, target_path, "patient_name")
        control_pn = _read_sample_metadata(h5_file, control_path, "patient_name")
        if target_pn != control_pn:
            raise H5PatientMismatchError("Target and control patient names do not match")
        if not target_pn or not target_pn.strip():
            raise H5MetadataError("Missing patient identifier metadata")
        
        # Verify sample_type indicates opposite sides
        target_type = _read_sample_metadata(h5_file, target_path, "sample_type")
        control_type = _read_sample_metadata(h5_file, control_path, "sample_type")
        _validate_opposite_breast_types(target_type, control_type)
        
        # Resolve sides from sample_type
        target_side = _breast_type_to_side(target_type)
        control_side = _breast_type_to_side(control_type)
        
        # Count measurement sets
        target_count = _count_sets(h5_file, target_path)
        control_count = _count_sets(h5_file, control_path)
        
        return H5PredictionContext(
            layout_name="calibration_sample",
            target_scan_ref=target_scan_ref,
            control_scan_ref=control_scan_ref,
            target_group_path=target_path,
            control_group_path=control_path,
            target_side=target_side,
            control_side=control_side,
            patient_identifier=target_pn,
            patient_identifier_source="patient_name_fallback",
            metadata_fallback_used=True,
            target_measurement_count=target_count,
            control_measurement_count=control_count,
            adapter_metadata={
                "calibration_group": _find_calibration_group(h5_file),
            },
        )
```

### Side resolution for calibration layout

```python
_BREAST_TYPE_SIDE_MAP = {
    "RIGHT BREAST": "RIGHT",
    "LEFT BREAST": "LEFT",
    "right breast": "RIGHT",
    "left breast": "LEFT",
    "BREAST RIGHT": "RIGHT",   # defensive variants
    "BREAST LEFT": "LEFT",
}

def _breast_type_to_side(sample_type: str) -> str:
    """Convert a sample_type string to a normalised side value (LEFT/RIGHT)."""
    normalised = sample_type.strip().upper()
    for pattern, side in _BREAST_TYPE_SIDE_MAP.items():
        if pattern == normalised or normalised in (pattern, pattern.replace(" ", "_")):
            return side
    raise H5MetadataError("Cannot determine breast side from sample_type")

def _validate_opposite_breast_types(target_type: str | None, control_type: str | None):
    if not target_type or not control_type:
        raise H5MetadataError("Missing breast side metadata")
    target_side = _breast_type_to_side(target_type)
    control_side = _breast_type_to_side(control_type)
    if target_side == control_side:
        raise H5SideMismatchError(
            "Target and control samples are the same breast side"
        )
```

### Set counting for calibration layout

```python
def _count_sets(h5_file, sample_path: str) -> int:
    """Count the number of measurement set groups under a sample."""
    sets_path = f"{sample_path}/sets"
    if sets_path not in h5_file:
        return 0
    sets_group = h5_file[sets_path]
    count = sum(1 for key in sets_group.keys() if key.startswith("set_"))
    return count
```

---

## 8. Explicit Target/Control Ref Contract

### Request shape (future production)

```json
{
  "h5_uri": "s3://matur-misc-uk/bremen/prediction-inputs/smoke/v0.1/aramis_real_h5_subset_20260128_5_patients.h5",
  "h5_checksum": "sha256:0bda036f08b057d992b329f6bd6834b3bb52cb74b1f3fca3efb08dda5edf655a",
  "target_scan_ref": "calib_20260128_132622/sample_01_20260128_Nova_376_Right",
  "control_scan_ref": "calib_20260128_132622/sample_02_20260128_Nova_376_Left",
  "patient_id": "smoke_test"
}
```

### Ref format rules

| Rule | Enforcement |
|---|---|
| Must be non-empty string | Already validated in `schemas.py` |
| Must not start with `/` | Reject absolute paths — refs are relative |
| Must not contain `..` | Prevent path traversal |
| Must correspond to existing H5 group | Verified by adapter |
| Canonical layout only accepts `"target"` / `"contralateral"` | Canonical adapter enforces |

### Canonical ref values

For backward compatibility, the canonical adapter accepts:
- `target_scan_ref = "target"` — standard value
- `control_scan_ref = "contralateral"` — standard value

These are validated to be non-empty but not used for path discovery.

### Calibration ref values

For the calibration adapter, refs are relative H5 group paths:
- `target_scan_ref = "calib_20260128_132622/sample_01_20260128_Nova_376_Right"`
- `control_scan_ref = "calib_20260128_132622/sample_02_20260128_Nova_376_Left"`

Resolved to absolute paths: `/{ref}`

### Rejection rules

| Condition | Error | Exception |
|---|---|---|
| Empty or missing ref | `target_scan_ref required` | ValueError (HTTP 400, before job) |
| Ref with `..` | `Invalid scan ref path` | ValueError (HTTP 400, before job) |
| Ref with leading `/` | `Scan ref must not start with /` | ValueError (HTTP 400, before job) |
| Ref not matching any group | `Target scan group not found` | H5ContainerError (preflight) |
| Target/control same H5 group | `Must be distinct groups` | H5ContainerError (preflight) |

---

## 9. Ambiguity Handling

### No automatic selection

The calibration adapter **never** auto-selects a patient or sample. If `target_scan_ref` and `control_scan_ref` are not valid sample group paths, the adapter raises an appropriate error. This is enforced by requiring explicit group paths.

### Multi-patient H5 without explicit refs

If a calibration-layout H5 contains multiple patients and neither `target_scan_ref` nor `control_scan_ref` can be resolved, the adapter raises `H5ContainerError("Target scan group not found")`. This is safe.

The existing `resolve_patient_metadata()` fallback (PR0044) will still reject multi-patient H5s with `Ambiguous sample patient_name metadata` when no refs are provided. Once refs are provided, the ambiguity is resolved by the explicit group selection.

### Ref mismatch handling

| Condition | Action |
|---|---|
| target and control belong to different patients | Reject — H5PatientMismatchError |
| target and control are same breast side | Reject — H5SideMismatchError |
| target/control patient_name missing | Reject — H5MetadataError |
| target/control sample_type missing | Reject — H5MetadataError |
| target/control have no measurement sets | Reject — H5MeasurementError |

---

## 10. Safety and Privacy Rules

1. **No raw patient_name in logs**: Adapter must not log patient_name values. Exception messages must use safe generic language.
2. **No raw patient_id in logs**: Same constraint.
3. **No full S3 URI in logs**: Pre-existing invariant.
4. **No weakening of existing checks**: All existing canonical checks remain.
5. **No auto-selection**: Adapter must not select first patient/sample.
6. **No inference or preprocessing changes**: PR0045 strictly ends at preflight context resolution.
7. **No model loading changes**: Absolutely none.
8. **No S3 staging changes**: Absolutely none.
9. **No calibration measurement data in exception messages**: Raw measurement values must not appear in errors.

---

## 11. Preflight Integration Plan (Option A)

**Chosen option: Option A (preflight only)**. Option B is not viable because `preprocessing_bridge.py` hardcodes `/scans/{label}/measurements` paths that don't exist in the calibration layout.

### Changes to `run_h5_preflight()`

```python
def run_h5_preflight(
    h5_path: str | Path,
    *,
    target_scan_ref: str | None = None,
    control_scan_ref: str | None = None,
) -> PreflightResult:
```

New optional parameters `target_scan_ref` and `control_scan_ref`. When provided, preflight uses the adapter system. When absent, preflight preserves current behavior (canonical layout assumed).

### Flow

```
1. Open H5 file
2. If target_scan_ref is None:
     - Use canonical layout directly (legacy path, unchanged)
     - Call existing _get_scan_side_and_measurements()
     - Call existing validate_required_metadata()
     - Return existing-style PreflightResult
3. If target_scan_ref is provided:
     a. Detect layout via adapter registry
     b. Call adapter.resolve_prediction_context(h5_file, target_scan_ref, control_scan_ref)
     c. Validate opposite sides from context
     d. Validate measurement counts from context
     e. Build PreflightResult from context (no _get_scan_side_and_measurements needed)
```

### What the context provides

The `H5PredictionContext` gives preflight everything it needs:
- `patient_identifier` -> `PreflightResult.patient_id`
- `patient_identifier_source` + `metadata_fallback_used` -> `PreflightResult.patient_identifier_source` + `.metadata_fallback_used`
- `target_side` / `control_side` -> `PreflightResult.target_side` / `.contralateral_side`
- `target_measurement_count` / `control_measurement_count` -> measurement counts
- `layout_name` -> can be recorded in `PreflightResult.metadata["layout_name"]`

### What the context does NOT provide

- Raw measurement/profile arrays for preprocessing
- Feature extraction paths
- Model input data

These are all PR0046.

### Integration with existing metadata

When adapter is used, `resolve_patient_metadata()` is **not called separately** — the adapter already resolves patient identity. The `patient_identifier_source` and `metadata_fallback_used` from the context are used directly.

### Calling inference_handler / app.py

Neither `inference_handler.py` nor `app.py` is changed by this PR. The `target_scan_ref` and `control_scan_ref` from `PredictionRequest` are not yet wired to `run_inference()` or `run_h5_preflight()`. This PR introduces the adapter boundary, but the actual wiring of refs through the API layer is deferred to a follow-up PR (or could be a narrow addition after PR0045 is merged).

**Rationale for deferring the wiring**: Wiring refs would require changes to `app.py` (to pass refs to `run_inference()`) and `inference_handler.py` (to pass refs to `run_h5_preflight()`). These are currently read-only files. Keeping the adapter boundary as a standalone module that can be called from tests validates the architecture without touching the critical request path.

**Alternative**: If the implementation agent can make a narrow, safe change to `preflight.py`'s `run_h5_preflight()` signature (adding optional ref params) without touching `app.py` or `inference_handler.py`, that is acceptable. The refs can be piped through a future PR.

---

## 12. Preprocessing Impact and PR0046 Boundary

### PR0045 stops here

PR0045 builds the adapter boundary and integrates it into preflight. The `PreflightResult` from adapter-based preflight will succeed for the calibration layout (patient identity, sides, measurement counts all validated).

### What PR0045 does NOT do

- Does **not** change `preprocessing_bridge.py` — `_extract_profiles()` still hardcodes `/scans/target/measurements`
- Does **not** change `build_feature_table()` — still expects canonical layout
- Does **not** extract profiles from `sets/set_*/integration/i` and `/q`
- Does **not** compute 15-feature vectors from calibration layout data

### PR0046 scope (preview, not committed)

PR0046 will likely need to:

1. Add a calibration-sample feature extractor that reads `integration/i` and `integration/q` from set groups
2. Either extend the adapter to provide a measurement extraction method or add a separate bridge for calibration layout
3. Wire the context `target_group_path` / `control_group_path` into the extraction logic

**Status of preprocessing bridge with calibration context**:
- `_extract_profiles()` currently reads `/scans/{label}/measurements` — a single 2D dataset
- The calibration layout has multiple `sets/set_*/integration/i` and `/q` — these are 1D arrays
- The feature formulas work on mean profiles (target_mean vs contralateral_mean)
- The I/Q data will need to be combined into profiles before feature computation
- This is a non-trivial change reserved for PR0046

---

## 13. Test Plan

All tests in `tests/test_bremen_h5_layouts.py` (new file) unless otherwise noted.

### A. `test_detects_canonical_layout`

- Create synthetic H5 with `/scans/target/measurements`
- Assert `CanonicalH5LayoutAdapter.detect()` returns `True`
- Assert `CalibrationSampleH5LayoutAdapter.detect()` returns `False`

### B. `test_detects_calibration_sample_layout`

- Create synthetic calibration-style H5:
  - `/calib_test/sample_01/sample/patient_name = "P001"`
  - `/calib_test/sample_01/sample/sample_type = "RIGHT BREAST"`
- Assert `CalibrationSampleH5LayoutAdapter.detect()` returns `True`
- Assert `CanonicalH5LayoutAdapter.detect()` returns `False`

### C. `test_resolves_explicit_calibration_target_control_context`

- Create synthetic H5 with target (RIGHT BREAST) and control (LEFT BREAST) samples for same patient
- Call `adapter.resolve_prediction_context()` with explicit paths
- Assert:
  - `layout_name == "calibration_sample"`
  - `target_group_path` and `control_group_path` match refs
  - `patient_identifier_source == "patient_name_fallback"`
  - `metadata_fallback_used is True`
  - `target_side` and `control_side` are opposite
  - `target_measurement_count` and `control_measurement_count` are >= 0

### D. `test_rejects_missing_target_or_control_ref`

- Call adapter with nonexistent ref path
- Assert `H5ContainerError` or `H5MetadataError`

### E. `test_rejects_mismatched_patient_names`

- Target and control sample have different `patient_name` values
- Assert `H5PatientMismatchError`
- Exception message must not contain raw patient_name values

### F. `test_rejects_same_side_samples`

- Both samples have `sample_type = "RIGHT BREAST"`
- Assert `H5SideMismatchError`

### G. `test_rejects_missing_sample_type`

- Sample without `sample/sample_type`
- Assert `H5MetadataError`

### H. `test_rejects_missing_patient_name`

- Sample without `sample/patient_name`
- Assert `H5MetadataError`

### I. `test_does_not_auto_select_first_patient_in_multi_patient_h5`

- Create multi-patient calibration H5 (Nova_376, Nova_378)
- Call `detect_layout()` — returns calibration adapter
- Call `resolve_prediction_context()` without matching ref — raises error
- Assert no auto-selection of first patient

### J. `test_preflight_with_explicit_calibration_refs`

- Create synthetic calibration-layout H5 with valid target/control
- Call `run_h5_preflight(h5_path, target_scan_ref="...", control_scan_ref="...")`
- Assert preflight returns `passed` with correct metadata
- Assert `patient_identifier_source == "patient_name_fallback"`

### K. `test_preflight_canonical_without_refs_preserved`

- Create synthetic canonical H5
- Call `run_h5_preflight(h5_path)` without refs (legacy path)
- Assert preflight passes identically to current behavior
- Assert `patient_identifier_source == "patient_id"`

### L. `test_no_raw_patient_name_in_logs_or_errors`

- caplog assertions + exception message assertions
- No raw patient_name in logs
- No raw patient_name in exception messages

### M. Optional real H5 smoke (skipped by default)

```python
@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="Set BREMEN_H5_PREFLIGHT_SMOKE_PATH to enable",
)
def test_preflight_with_explicit_calibration_refs_on_real_h5():
    """Assert preflight no longer fails with explicit refs.
    
    Set BREMEN_H5_PREFLIGHT_SMOKE_PATH and use explicit refs:
    target_scan_ref = "calib_20260128_132622/sample_01_20260128_Nova_376_Right"
    control_scan_ref = "calib_20260128_132622/sample_02_20260128_Nova_376_Left"
    
    NOTE: Preflight may pass but preprocessing bridge will still fail.
    That is expected and documented as PR0046 scope.
    """
```

---

## 14. Non-Goals

This PR explicitly does NOT address:

- Preprocessing feature extraction for calibration layout (PR0046)
- Wire `target_scan_ref` / `control_scan_ref` through `app.py` or `inference_handler.py` (follow-up)
- Changes to `preprocessing_bridge.py`
- Changes to `inference_handler.py`
- Changes to `app.py`
- Changes to `schemas.py`
- Changes to `model_artifacts.py`
- Model loading changes
- S3 staging changes
- Training changes
- Matador integration
- Broad H5 layout migration
- Clinical claims
- ADR, ROADMAP, or docs/architecture.md changes
- CI/CD, Docker, infra, or dependency changes

---

## 15. Validation Checklist

```bash
# Git state
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile check
python -m compileall src tests

# Test runs
python -m pytest -q tests/test_bremen_h5_layouts.py -v
python -m pytest -q tests/test_bremen_h5_preflight.py -v
python -m pytest -q tests/test_bremen_h5_sample_metadata.py -v
python -m pytest -q tests/test_bremen_inference_integration.py -v
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_logging.py
python -m pytest -q

# Adapter code coverage
grep -n "H5LayoutAdapter\|H5PredictionContext\|calibration_sample\|CanonicalH5LayoutAdapter\|CalibrationSampleH5LayoutAdapter" \
  src/bremen tests -r

# Privacy audit
grep -n "Nova_376\|Nova_378\|Nova_379\|Nova_383\|Nova_384" src/bremen tests || true
# Should only appear in test assertions, never in log/error messages

# No artifact leaks
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" \
  -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) \
  -not -path "./.git/*" -not -path "./venv/*" -print

# Forbidden changes
git diff --name-only -- docs/adr ROADMAP.md docs/architecture.md \
  src/bremen/training \
  .github Dockerfile infra requirements.txt pyproject.toml \
  src/bremen/model_artifacts.py \
  src/bremen/model_loader.py \
  src/bremen/api/model_state.py \
  src/bremen/h5_inputs.py
```

---

## 16. Forbidden Changes

The implementation agent MUST NOT:

1. Modify `src/bremen/api/preprocessing_bridge.py`
2. Modify `src/bremen/api/inference_handler.py`
3. Modify `src/bremen/api/app.py`
4. Modify `src/bremen/api/schemas.py`
5. Modify `src/bremen/api/model_state.py`
6. Modify `src/bremen/model_artifacts.py`
7. Modify `src/bremen/h5_inputs.py` (S3 staging)
8. Modify `src/bremen/training/**`
9. Modify `docs/adr/`, `ROADMAP.md`, `docs/architecture.md`
10. Modify `.github/`, `Dockerfile`, `infra/`, `requirements.txt`, `pyproject.toml`
11. Commit real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` artifacts
12. Commit secrets, account IDs, or access keys
13. Change inference math or preprocessing feature formulas
14. Change model loading
15. Log raw `patient_name` or `patient_id` values
16. Include raw patient_name values in exception messages
17. Auto-select first patient/sample in multi-patient H5
18. Weaken target/control consistency checks
19. Require real H5 for default unit tests

---

## 17. Rollback Plan

1. **Immediate rollback**: `git revert HEAD` on `0045-h5-layout-adapter-boundary` branch
2. Verify revert:
   - `python -m pytest -q tests/test_bremen_h5_preflight.py -v`
   - `python -m pytest -q tests/test_bremen_h5_sample_metadata.py -v`
   - `python -m pytest -q tests/test_bremen_inference_integration.py -v`
   - `python -m pytest -q tests/test_bremen_predictions.py -v`
   - `python -m pytest -q`
3. Open revert PR with label `revert/0045`

### Partial rollback (adapter module only)

If the adapter integration causes preflight regressions, revert the `preflight.py` changes but keep the `h5_layouts.py` module. The adapters can be used in isolation via test code.

---

## 18. Implementation Agent Assignment

**Implementation agent**: coder

