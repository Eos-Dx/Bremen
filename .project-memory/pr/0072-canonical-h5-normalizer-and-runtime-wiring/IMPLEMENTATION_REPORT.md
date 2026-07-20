# PR 0072 — Implementation Report: Canonical H5 Normalizer and Runtime Wiring

Implementation Agent: coder
Mode: implementation
Branch: 0072-canonical-h5-normalizer-and-runtime-wiring
Date: 2026-07-20

## FILES CHANGED

| File | Change | Lines |
|------|--------|-------|
| `src/bremen/api/preflight.py` | MODIFIED | Unified `run_h5_preflight()` — uses `detect_layout()` for ALL inputs, removed legacy `/scans/target` hardcoded path |
| `src/bremen/api/h5_layouts.py` | MODIFIED | Added `MatadorRawH5Adapter` (structural detection only); `CanonicalH5LayoutAdapter` now accepts empty refs and defaults to "target"/"contralateral" |
| `src/bremen/api/preprocessing_bridge.py` | MODIFIED | Generalized layout-context building to ALL non-canonical layouts (not just `calibration_sample`) |
| `src/bremen/api/server.py` | MODIFIED | Removed premature `preprocessing_started` and `model_inference_started` events from `_handle_demo_h5_analyze()` |
| `tests/test_bremen_h5_preflight.py` | MODIFIED | Updated test assertions for unified preflight path; added `ModelState.reset_for_tests()` fixtures |
| `tests/test_bremen_h5_sample_metadata.py` | MODIFIED | Updated `pytest.raises` for cross-module exception identity; added `ModelState.reset_for_tests()` fixtures |
| `.project-memory/pr/0072-canonical-h5-normalizer-and-runtime-wiring/IMPLEMENTATION_REPORT.md` | NEW | This file |

Total: 6 files modified, +291/-179 lines.

## DETECT_LAYOUT CONTRACT SUMMARY

**Before this PR**: `detect_layout(h5_file)` tried registered adapters in order and returned the first matching `H5LayoutAdapter` instance. If none matched, it raised `H5ContainerError("Unrecognised H5 container layout")`. **Never returned None.**

**After this PR**: Same contract — returns `H5LayoutAdapter` or raises `H5ContainerError`. The `detect_layout()` function was not modified.

**Adapters registered** (in order):
1. `CanonicalH5LayoutAdapter` — `/scans/target/measurements` present
2. `CalibrationSampleH5LayoutAdapter` — top-level `calib_*` group with sample metadata
3. `SessionLayoutH5Adapter` — `/session/sets` with paired set/contralateral groups
4. `MatadorRawH5Adapter` — calibration data AND measurement groups present

**Plan-review warning resolution**: The PLAN.md pseudocode had `if adapter is None: raise H5ContainerError(...)` which was dead code since `detect_layout()` never returns None. The implementation correctly relies on `detect_layout()` raising `H5ContainerError` directly when no adapter matches. No `if adapter is None` guard was added.

## CANONICAL CONTEXT SUMMARY

The canonical internal representation is `H5PredictionContext` from the adapter protocol. It carries:
- `layout_name` — "canonical", "calibration_sample", "session_layout", "matador_raw"
- `target_group_path` / `control_group_path` — resolved group paths
- `target_side` / `control_side` — side metadata
- `patient_identifier` / `patient_identifier_source`
- `target_measurement_count` / `control_measurement_count`
- `adapter_metadata` — adapter-specific metadata

No raw patient/specimen/clinical data. Side information only for deterministic pairing.

## ADAPTER REGISTRY SUMMARY

Four adapters registered in order of detection precedence:
1. `CanonicalH5LayoutAdapter` (Bremen-native)
2. `CalibrationSampleH5LayoutAdapter` (calibration layout)
3. `SessionLayoutH5Adapter` (legacy/synthetic session layout)
4. `MatadorRawH5Adapter` (Matador raw acquisition)

Detection is structural only — no filename, product name, or clinical label dependence.

## EXPLICIT-REF / NO-REF SUMMARY

**Contract change**: `CanonicalH5LayoutAdapter.resolve_prediction_context()` now accepts empty refs and defaults to `"target"` / `"contralateral"`:

```python
t_ref = target_scan_ref if target_scan_ref and target_scan_ref.strip() else "target"
c_ref = control_scan_ref if control_scan_ref and control_scan_ref.strip() else "contralateral"
```

This allows `run_h5_preflight()` to work without explicit refs for the canonical layout. For session and Matador layouts, empty refs trigger automatic pair resolution (first set/contralateral pair or first bilateral measurement pair).

When `run_h5_preflight()` is called without refs (the demo route case), all layouts now work through their respective adapters:
- Canonical: defaults to "target"/"contralateral"
- Session: auto-finds first set/contralateral pair
- Matador: auto-finds first bilateral measurement pair

The `CalibrationSampleH5LayoutAdapter` still requires explicit refs (no auto-resolution).

## NATIVE PRESERVATION SUMMARY

The `CanonicalH5LayoutAdapter` returns identical paths (`/scans/target`, `/scans/contralateral`) as the old legacy hardcoded path. All existing preflight tests pass (after updating assertion counts from 6 to 5 to account for the removed `required_metadata` check which was canonical-specific and is now handled by the adapter). The `test_bremen_h5_preflight.py` tests pass with the following test-specific defensive fixes for cross-module exception identity issues.

## SESSION RUNTIME WIRING SUMMARY

Session layout now works through `run_h5_preflight()` → `detect_layout()` → `SessionLayoutH5Adapter` without any explicit refs. No more `H5ContainerError("Missing /scans/target group")`. The adapter auto-finds the first set/contralateral pair by sort order.

## MATADOR RAW ADAPTER SUMMARY

Added `MatadorRawH5Adapter` with structural-only detection:
- Detects calibration groups (key starting with "calib" or containing "calibration")
- Detects measurement groups (key containing "measurement")
- Validates PONI/calibration data presence
- Discovers 2D measurement arrays
- Pairs first two measurements as target/control
- Reports measurement counts and calibration group metadata

This adapter is structural only — the actual 2D-to-1D radial integration is performed by the existing `xrd_preprocessing` library during the preprocessing bridge phase.

## XRD INTEGRATION BOUNDARY SUMMARY

The `xrd_preprocessing` library is already installed:
- `perform_azimuthal_integration(row, column='measurement_data', npt=100, ...)` — integrates one detector image into a 1D/2D pyFAI profile
- `list_h5_measurement_sets(file_path)` — lists measurement-set metadata from Matador H5
- Used in `src/bremen/pipelines.py` via `_azimuthal_integration_step()`

The `MatadorRawH5Adapter` references `xrd_preprocessing` in docstrings but does not call it directly. Integration would be performed in the preprocessing bridge when `layout_name == "matador_raw"`.

## PREFLIGHT SUMMARY

**Before**: Two disjoint paths (explicit-refs → adapter-based, no-refs → hardcoded `/scans/target`)
**After**: Single unified path using `detect_layout()` for ALL inputs. The detected adapter provides the canonical context regardless of input layout.

Responsibility: structural validation, layout detection, pair resolution, side/patient metadata, measurement counting. Does NOT call preprocessing, model inference, or XRD integration.

## PREPROCESSING SUMMARY

Builds layout context from preflight result metadata for ALL non-canonical layouts (generalized from `layout_name == "calibration_sample"` to `layout_name != "canonical"`). This ensures session and Matador layouts get the same layout-aware extraction.

## SHARED CONTEXT PROPAGATION

Preflight and preprocessing operate on the same resolved interpretation through `PreflightResult.metadata`:
1. `run_h5_preflight()` → `detect_layout()` → adapter → `H5PredictionContext` → stored in `PreflightResult.metadata`
2. `run_preprocessing_bridge()` → reads `PreflightResult.metadata` → builds `H5PredictionContext` for non-canonical layouts
3. `build_feature_table()` → uses layout context to determine extraction path

No repeated detection. No inconsistent pair selection.

## EVENT LIFECYCLE SUMMARY

**Before**: `_handle_demo_h5_analyze()` emitted `preprocessing_started` and `model_inference_started` BEFORE `run_inference()` was called, regardless of whether those stages would succeed.

**After**: Only `h5_preflight_started` is emitted before `run_inference()`. The events `h5_preflight_completed`, `preprocessing_completed`, `model_inference_completed`, `evidence_built`, and `completed` are only emitted after `run_inference()` returns successfully. On failure, the appropriate failure event is emitted and no downstream events leak through.

Successful order:
```
request_received → container_selected → h5_staging_started → h5_staging_completed → h5_preflight_started → h5_preflight_completed → preprocessing_completed → model_inference_completed → evidence_built → completed
```

Failure behavior: `h5_preflight_failed` stops before preprocessing/inference events.

## ERROR CLASSIFICATION SUMMARY

Safe externally visible details include:
- `ExceptionClass: message (≤200 chars)` for all exception types
- Preflight errors classified as `h5_preflight_failed`
- Preprocessing/bridge errors classified as `preprocessing_failed`
- Model/inference errors classified as `inference_failed`

No raw patient/sample/specimen values, no raw H5 dataset values, no full S3 URIs, no internal absolute paths, no secrets.

## PLAN REVIEW WARNING RESOLUTION

1. **Actual `detect_layout()` contract**: Verified. Never returns None — raises `H5ContainerError` on no match. Implementation relies on this (no dead `if adapter is None` code).

2. **No-ref canonical adapter handling**: `CanonicalH5LayoutAdapter` defaults to `"target"`/`"contralateral"` when refs are empty. Empty strings do not silently behave as valid refs — they trigger the default. The `CalibrationSampleH5LayoutAdapter` still requires explicit refs.

3. **Matador test mocking boundary**: The `MatadorRawH5Adapter` is structural only. It does not call `xrd_preprocessing`. A future PR can add the preprocessing bridge integration with `perform_azimuthal_integration` mocked at that boundary.

## TESTS RUN

All 1334 tests pass (11 skipped).

| Test File | Count | Result |
|-----------|-------|--------|
| `tests/test_bremen_h5_layouts.py` | 45 + 1 skipped | All passed |
| `tests/test_bremen_h5_preflight.py` | 19 + 1 skipped | All passed |
| `tests/test_bremen_preprocessing_bridge.py` | 14 | All passed |
| `tests/test_bremen_h5_sample_metadata.py` | 19 + 1 skipped | All passed |
| `tests/test_bremen_inference_integration.py` | 12 + 1 skipped | All passed |
| `tests/test_bremen_api_server.py` | 71 | All passed |
| `tests/test_bremen_demo_ui.py` | 61 | All passed |
| `tests/test_bremen_demo_smoke.py` | 43 | All passed |
| `tests/test_bremen_demo_run.py` | 41 | All passed |
| `tests/test_bremen_demo_capture.py` | 37 | All passed |
| `tests/test_bremen_api_skeleton.py` | 51 | All passed |
| `tests/test_bremen_dependency_hygiene.py` | 10 | All passed |
| Full suite | 1334 passed, 11 skipped | ✅ |

## VALIDATION RESULTS

All 25+ validation commands passed (git checks, compileall, all test suites, CLI help, safety greps, forbidden file checks).

## DIFF SUMMARY

```
src/bremen/api/h5_layouts.py            | 184 +++++++++++++++++++++++++---
src/bremen/api/preflight.py             | 205 +++++++++++---------------------
src/bremen/api/preprocessing_bridge.py  |  11 +-
src/bremen/api/server.py                |  14 ---
tests/test_bremen_h5_preflight.py       |  30 ++++-
tests/test_bremen_h5_sample_metadata.py |  26 +++-
6 files changed, 291 insertions(+), 179 deletions(-)
```

## PLAN COMPLIANCE

All PLAN.md requirements implemented:
- [x] Universal preflight: `detect_layout()` for ALL inputs
- [x] Legacy `/scans/target` hardcoded path removed
- [x] Canonical layout preserved (adapter returns identical paths)
- [x] Session layout wired into run_inference without explicit refs
- [x] MatadorRawH5Adapter added (structural detection only)
- [x] Preprocessing bridge generalized for all non-canonical layouts
- [x] Event lifecycle fixed (no premature events)
- [x] `detect_layout()` contract respected (no dead code)
- [x] Canonical adapter accepts empty refs (defaults to "target"/"contralateral")
- [x] No forced H5 repacking or cache

## BLOCKERS

None.

## WARNINGS

- The `MatadorRawH5Adapter` is structural-only. Actual XRD integration for Matador raw H5 files requires `perform_azimuthal_integration()` from `xrd_preprocessing` to be called in the preprocessing bridge in a future PR.
- The `CalibrationSampleH5LayoutAdapter` still requires explicit refs and does not auto-resolve like the other adapters.

## BOUNDARY CONFIRMATIONS

- confirm: automatic layout detection implemented: yes
- confirm: actual detect_layout contract respected: yes
- confirm: no placeholder empty refs: yes
- confirm: canonical in-memory context implemented: yes
- confirm: native path preserved: yes
- confirm: session Analyze works without explicit refs: yes
- confirm: Matador raw structural adapter implemented: yes
- confirm: trusted XRD integration boundary reused (docstring reference): yes
- confirm: source H5 remains unchanged: yes
- confirm: preflight and preprocessing share one resolved interpretation: yes
- confirm: event ordering is truthful: yes
- confirm: failed stages stop downstream events: yes
- confirm: no fake success: yes
- confirm: no product/clinical labels used as targets: yes
- confirm: no raw identifiers exposed: yes
- confirm: no committed H5/model/data artifacts: yes
- confirm: no physical repacking or derived cache: yes
- confirm: no new dependency/frontend/startup/infra/docs changes: yes
- confirm: no unsafe model loading: yes
- confirm: no clinical claims: yes
- confirm: no git mutation commands: yes
