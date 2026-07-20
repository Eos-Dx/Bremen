# PR 0073 — Plan Matador Raw Runtime Completion

Author: plan
Mode: planning only
Branch: 0073-matador-raw-runtime-completion

## Objective

Complete the Matador raw H5 path from structural detection through real 2D diffraction integration, Bremen feature extraction, and model inference. PR0072 remains in place — this is a corrective follow-up, not a revert.

## PR0072 Postmortem

1. **A registered structural adapter is not proof of a working raw normalization pipeline.** PR0072 registered `MatadorRawH5Adapter` with a keyword-based detection heuristic (`"calib"` or `"calibration"` and `"measurement"`) that did not match the real Nova H5 layout. The adapter's `detect()` returned `False`, causing `detect_layout()` to raise `H5ContainerError: Unrecognised H5 container layout`.

2. **A green full pytest run is not sufficient when the required route-level acceptance test does not exist.** PR0072 passed 1334 tests but had no controlled HTTP test for the Matador raw path. The only Matador-specific test was for a simplified synthetic fixture, not the real layout contract.

3. **Structural detection must be validated against the real input layout contract, not only a simplified temporary fixture.** The synthetic fixture used in PR0072 testing had top-level groups named "calibration_001" and "measurement_001" which triggered the keyword-based detection. The real Nova container uses different naming.

4. **Future-work deferral cannot satisfy a current PR acceptance criterion.** The PR0072 implementation report explicitly deferred the XRD integration call to a future PR. True path completion requires both detection AND integration.

5. **Precommit review must compare implementation claims against the approved PLAN and deployed acceptance target.** The PR0072 precommit review accepted the Matador adapter as "structural only" without verifying that the deployed container would actually be detected and processed end-to-end.

6. **A Matador raw success claim requires actual evidence through detection, calibration discovery, pairing, integration, feature extraction, and inference.** PR0072 satisfied only the structural detection (for a simplified fixture), not the full pipeline.

## Confirmed current state

| Component | State | Detail |
|-----------|-------|--------|
| `MatadorRawH5Adapter.detect()` | ✗ Fails for real Nova | Keyword-based heuristic doesn't match real layout |
| `MatadorRawH5Adapter.resolve_prediction_context()` | ✗ Unreachable for real Nova | Can't reach this if detect() fails |
| Preprocessing bridge `matador_raw` branch | ✗ Not reached | No branch tested for real layout |
| XRD integration call | ✗ Not implemented | `perform_azimuthal_integration` wrapper not called |
| Route-level success test | ✗ Not existing | No Matador raw HTTP test |
| Failure tests for real layout | ✗ Not existing | No tests for real structural contract |
| `list_h5_measurement_sets` usage | ✗ Not implemented | Available but not used |
| Session layout path | ✓ Working | Confirmed deployed |
| Canonical native path | ✓ Working | Confirmed |
| Event lifecycle | ✓ Working | PR0072 fix in place |

## Real-layout structural contract

**Required: structure-only manifest from a human**.

The `MatadorRawH5Adapter.detect()` currently uses keyword matching on top-level group names (`"calib"`, `"calibration"`, `"measurement"`). The real Nova H5 has a different naming convention that does not trigger these keywords.

A human must run the following structure-export script against a real Nova H5 and provide the output. The script exports only paths, shapes, dtypes, and attribute names — no dataset values or attribute values.

```python
"""Export H5 structure for planning — paths, shapes, dtypes, attr names only.
No dataset values, no attribute values, no patient identifiers.

Usage: python export_h5_structure.py /path/to/Nova_103_.h5
"""
import sys, h5py

def export_structure(h5_path):
    with h5py.File(h5_path, "r") as f:
        def visitor(name, obj):
            if isinstance(obj, h5py.Dataset):
                attrs = list(obj.attrs.keys())
                print(f"DATASET  {name}  shape={obj.shape}  dtype={obj.dtype}  attrs={attrs}")
            elif isinstance(obj, h5py.Group):
                attrs = list(obj.attrs.keys())
                print(f"GROUP    {name}  attrs={attrs}")
        f.visititems(visitor)

if __name__ == "__main__":
    export_structure(sys.argv[1])
```

The output must be manually reviewed and redacted if any identifier values are visible in attribute names or group names. After review, the output guides adapter detection changes.

**Until the manifest is provided, the implementation must use the following known-available structure evidence**:

From the deployed failure evidence and `docs/product_input_pipeline_contract.md`, the Nova container is an XRD acquisition format with:
- Acquisition/session root groups
- Calibration data (PONI/geometry) at known paths used by `xrd_preprocessing`
- Raw 2D diffraction measurement datasets
- Side/position metadata attached to measurement groups
- The `xrd_preprocessing` library has `list_h5_measurement_sets()` and `list_h5_sessions()` that can structurally analyze the container

**Implementation approach given manifest unavailability**:
1. Use `list_h5_sessions()` and `list_h5_measurement_sets()` from `xrd_preprocessing` for structural detection instead of keyword matching
2. These functions can read the H5 structure without loading raw arrays and return DataFrame metadata
3. If they return non-empty results for session + measurement sets, the container is a valid Matador raw acquisition
4. This avoids hardcoded group name patterns while using the already-installed trusted library

## Structure-only manifest workflow (for real-layout verification)

1. Human runs `export_h5_structure.py` against `Nova_103_.h5`
2. Human reviews output for identifiers, redacts if needed
3. Human provides the structure manifest as a code comment or in the PR description
4. If path/group names contain identifiers, the manifest is redacted before use
5. The manifest defines the exact structural predicates for `detect()`

If the manifest above reveals that `list_h5_sessions()` / `list_h5_measurement_sets()` return empty results for the real Nova, alternative detection using `visititems` structural search must be used.

## MatadorRawH5Adapter correction

**Detection strategy** (tiered, first match wins):

1. **Native `list_h5_sessions` + `list_h5_measurement_sets`**: Call these from `xrd_preprocessing`. If they return non-empty DataFrames with valid session and measurement metadata, the H5 is a Matador raw acquisition. This is the most reliable detection method because it uses the same library that performs the integration.

2. **Structural fallback** (if session listing returns empty but structure is recognisable): Use `h5py.File.visititems()` to find groups containing 2D numeric datasets with dimensions > 1, and calibration/PONI-related datasets.

**Detection must NOT use**:
- Filename patterns (`Nova`, `Matador`)
- Top-level group name keyword matching (`calib`, `measurement`)
- Patient/sample/specimen identifiers

**Adapter changes**:

```python
class MatadorRawH5Adapter(H5LayoutAdapter):
    name = "matador_raw"

    def detect(self, h5_file: h5py.File) -> bool:
        # Must not claim canonical or session layouts
        if "/scans/target/measurements" in h5_file:
            return False
        if "/session/sets" in h5_file:
            return False

        # Method 1: Use xrd_preprocessing session listing
        try:
            from xrd_preprocessing import list_h5_sessions
            sessions = list_h5_sessions(str(h5_file.filename))
            if sessions is not None and len(sessions) > 0:
                from xrd_preprocessing import list_h5_measurement_sets
                measurements = list_h5_measurement_sets(str(h5_file.filename))
                if measurements is not None and len(measurements) > 0:
                    return True
        except Exception:
            pass

        # Method 2: Structural fallback
        # Look for 2D numeric datasets and calibration/PONI datasets
        # using visititems structural search
        found_2d = False
        found_poni = False
        def _visitor(name, obj):
            nonlocal found_2d, found_poni
            if isinstance(obj, h5py.Dataset):
                if len(obj.shape) >= 2 and obj.dtype.kind in ('f', 'i', 'u'):
                    found_2d = True
                if 'poni' in name.lower() or ('calib' in name.lower() and obj.dtype.kind in ('f', 'i', 'u')):
                    found_poni = True
        h5_file.visititems(_visitor)
        return found_2d and found_poni
```

**`resolve_prediction_context()` changes**:

Use `list_h5_measurement_sets()` to discover measurement rows, their side metadata, and 2D array column names deterministically. Pair by side/position metadata rather than "first two measurements".

```python
def resolve_prediction_context(self, h5_file, target_scan_ref, control_scan_ref):
    from xrd_preprocessing import list_h5_measurement_sets, list_h5_sessions

    # Discover sessions and measurement sets
    sessions_df = list_h5_sessions(str(h5_file.filename))
    ms_df = list_h5_measurement_sets(str(h5_file.filename))

    if ms_df is None or len(ms_df) == 0:
        raise H5ContainerError("No measurement sets found")

    # -- Pair bilateral measurements by side --
    # The measurement_sets DataFrame contains side/position columns.
    # Group by position, find target/control pairs.
    # This is deterministic, not "first two measurements".

    # ... pairing logic based on actual columns in ms_df ...

    return H5PredictionContext(
        layout_name=self.name,
        # ... populated from paired measurements ...
        adapter_metadata={
            "layout_name": self.name,
            "session_count": len(sessions_df) if sessions_df is not None else 0,
            "measurement_count": len(ms_df),
        },
    )
```

**Important**: The exact column names in the DataFrame from `list_h5_measurement_sets` determine the pairing logic. These must be inspected from the real H5 output or from the library's documentation/docstrings. The implementation must handle this generically.

## Trusted XRD API verification

Confirmed available:

| Function | Purpose | Signature |
|----------|---------|-----------|
| `list_h5_measurement_sets(file_path)` | List measurement-set metadata as DataFrame | `(file_path, ...)` |
| `list_h5_sessions(file_path)` | List session metadata as DataFrame | `(file_path, ...)` |
| `perform_azimuthal_integration(row, column='measurement_data', npt=100, ...)` | Integrate one detector image | `(pd.Series, ...)` |
| `AzimuthalIntegration` (class) | Pipeline-compatible integration transformer | `(column, npt, ...)` |

`perform_azimuthal_integration` takes a pandas Series (one row from the measurement DataFrame) and returns an integrated profile. It reads the 2D array from `row[column]`, calibrates using PONI metadata from the row, and returns a 1D profile.

## Integration wrapper plan

Create a thin wrapper in `src/bremen/api/preprocessing_bridge.py` (or a small helper) that:

1. Receives `H5PredictionContext` with `layout_name == "matador_raw"`
2. Opens the H5 file
3. Reads the 2D array from the resolved measurement group path
4. Calls `perform_azimuthal_integration` on the array with the PONI calibration
5. Returns validated q/i profiles
6. Passes q/i to the existing feature extraction logic

```python
def _matador_raw_to_q_i(h5_path: str, context: H5PredictionContext) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Read Matador raw measurement, integrate, return target/control q/i."""
```

This wrapper is called from the preprocessing bridge when `layout_name == "matador_raw"`, replacing the direct integration/q array reading used for other layouts.

## Preflight vs preprocessing responsibilities

**Preflight** (`run_h5_preflight` → adapter):
- Layout detection passes (or fails with `h5_preflight_failed`)
- Calibration data is present and readable
- Raw 2D measurement groups exist with valid shapes/dtypes
- Side/position metadata exists for deterministic pairing
- Bilateral pairs are complete
- No integration performed — only structural validation

**Preprocessing** (`run_preprocessing_bridge`):
- Load validated raw 2D images
- Call `perform_azimuthal_integration` (trusted external API)
- Validate resulting q/i profiles (finite, matching lengths, compatible q ranges)
- Align paired q ranges
- Compute Bremen feature inputs
- Run existing feature extraction
- Integration error → `preprocessing_failed`, not `inference_failed`

## Canonical context plan

The existing `H5PredictionContext` carries `layout_name="matador_raw"`, `target_group_path`, `control_group_path`, and `adapter_metadata`. The preprocessing bridge uses `layout_context` to detect matador raw and dispatch to the integration wrapper. No architectural changes needed beyond what PR0072 established.

## Route event plan

Truthful event sequence preserved from PR0072. No premature events. The preprocessing bridge emits `preprocessing_started` before calling the integration wrapper, and `preprocessing_completed` after successful feature extraction. If integration fails, `preprocessing_failed` is raised and caught by `run_inference()`.

## Controlled success test plan

Create temp HDF5 with Matador-like structure (2D arrays + PONI attrs on a calibration group):

1. H5 with a session group, a calibration dataset, and a measurement group containing a 2D float array
2. Mock `perform_azimuthal_integration` at the wrapper boundary to return deterministic q/i
3. POST `/demo/api/h5/analyze` via the test server
4. Assert: `status == "completed"`, result present, correct event order, `technical_demo_only`, request_id, job_id, source checksum unchanged

## Failure test plan

- Unknown layout → `h5_preflight_failed`
- Missing 2D arrays → `h5_preflight_failed`
- Integration exception → `preprocessing_failed`
- Invalid q/i from integration mock → `preprocessing_failed`
- No patient identifiers in responses
- No clinical labels as targets

## Regression plan

Verify:
- Canonical `/scans/target` runtime still works
- Session layout `/session/sets` still works
- Event lifecycle still correct (no premature events)
- H5 catalog/upload still works
- demo UI unchanged
- All existing 1334+ tests pass

## Deployed rehearsal plan

After merge/deploy, human verifies:
- `cancer_one_patient.h5` still completes (session layout)
- `Nova_103_.h5` progresses through `h5_preflight_completed` → `preprocessing_completed` → `model_inference_completed` → `completed`

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Implementation scope

| File | Change |
|------|--------|
| `src/bremen/api/h5_layouts.py` | Fix `MatadorRawH5Adapter.detect()` to use `list_h5_sessions`/`list_h5_measurement_sets`; fix pairing to use side/position metadata |
| `src/bremen/api/preprocessing_bridge.py` | Add matador_raw branch that calls integration wrapper |
| `tests/test_bremen_h5_layouts.py` | Add real-structure detection tests + failure tests |
| `tests/test_bremen_preprocessing_bridge.py` | Add matador_raw branch tests |
| `tests/test_bremen_api_server.py` | Add controlled HTTP success test + failure tests |

No new files unless a separate integration wrapper module is justified.

## Validation checks

All git, compile, test suite, CLI help, and grep checks as specified in the task prompt.

## Boundary confirmations

- one focused corrective PR: yes
- PR0072 retained: yes
- postmortem included: yes (above)
- structural adapter is not treated as runtime completion: yes
- real layout contract required: yes (via `list_h5_measurement_sets` or structural manifest)
- no direct agent inspection of real H5: yes
- structure-only redacted evidence required: yes
- no filename-based detection: yes
- trusted integration API must be verified: yes (`perform_azimuthal_integration` confirmed)
- no approximate integration: yes
- no fabricated calibration or pairing: yes
- external integration is the only Matador mock boundary: yes
- route-level success required: yes
- native and session paths preserved: yes
- source H5 immutable: yes
- no physical repacking or derived cache: yes
- no committed H5/model/data artifacts: yes
- no product labels used as Bremen target: yes
- no identifiers exposed: yes
- no new dependency/frontend/startup/infra/docs work: yes
- implementation assigned to coder: yes
- no git mutation commands run: yes
