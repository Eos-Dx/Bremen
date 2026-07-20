# PR 0071 — Implementation Report: Demo Legacy/Synthetic H5 Layout Adapter

Implementation Agent: coder
Mode: implementation
Branch: 0071-demo-legacy-h5-layout-adapter
Date: 2026-07-20

## FILES CHANGED

| File | Change | Lines |
|------|--------|-------|
| `src/bremen/api/h5_layouts.py` | MODIFIED | Added `SessionLayoutH5Adapter` + `import numpy` + registration as 3rd built-in adapter |
| `src/bremen/api/preprocessing_bridge.py` | MODIFIED | Added `"session_layout"` branch in `build_feature_table()` + `_extract_session_profiles()` helper |
| `tests/test_bremen_h5_layouts.py` | MODIFIED | Added 12 new tests (detection, context resolution, preflight, clinical-label safety) |
| `.project-memory/pr/0071-demo-legacy-h5-layout-adapter/IMPLEMENTATION_REPORT.md` | NEW | This file |

Total: 3 files modified, +494/-1 lines.

## SESSION LAYOUT ADAPTER SUMMARY

Added `SessionLayoutH5Adapter` implementing the `H5LayoutAdapter` protocol:

**Detection** (`detect()`):
- Returns `False` if `/scans/target/measurements` exists (canonical layout)
- Returns `False` if `/session/sets` doesn't exist
- Returns `True` if at least one `set_NNN_sample_main` + `contralateral_set_NNN_sample_main` pair exists

**Context resolution** (`resolve_prediction_context()`):
- Uses explicit `target_scan_ref`/`control_scan_ref` if provided, otherwise finds first pair by sort order
- Validates `integration/q` and `integration/i` arrays exist at resolved paths
- Validates q-axis length match and `np.max(np.abs(diff)) <= 0.01` compatibility
- Resolves patient metadata via `resolve_patient_metadata()` (reads `/patient/id` or `/session/sample/patient_name`)
- Resolves side metadata from `/session/sample/sample_type` → breast type → side (LEFT/RIGHT)
- No biopsy/birads/BENIGN/CANCER labels used as prediction targets
- Registered as 3rd built-in adapter via `register_adapter(SessionLayoutH5Adapter())`

## PREPROCESSING BRIDGE COMPATIBILITY SUMMARY

Added a `"session_layout"` branch in `build_feature_table()` alongside the existing `"calibration_sample"` branch:
- Reads `integration/i` and `integration/q` from resolved group paths
- Computes magnitude `sqrt(i^2 + q^2)` using new `_extract_session_profiles()` helper
- Returns a list with a single 1D profile array (matching the non-calibration pipeline expectation)

## TESTS SUMMARY

All 1334 tests pass (11 skipped), including:

| Test File | Count | Result |
|-----------|-------|--------|
| `tests/test_bremen_h5_layouts.py` | 45 + 1 skipped | All passed |
| `tests/test_bremen_h5_preflight.py` | 19 + 1 skipped | All passed |
| `tests/test_bremen_preprocessing_bridge.py` | 14 + 0 skipped | All passed |
| `tests/test_bremen_h5_sample_metadata.py` | 19 + 1 skipped | All passed |
| `tests/test_bremen_api_server.py` | 71 | All passed |
| `tests/test_bremen_demo_ui.py` | 61 | All passed |
| `tests/test_bremen_demo_smoke.py` | 43 | All passed |
| `tests/test_bremen_demo_run.py` | 41 | All passed |
| `tests/test_bremen_demo_capture.py` | 37 | All passed |
| `tests/test_bremen_api_skeleton.py` | 51 | All passed |
| `tests/test_bremen_dependency_hygiene.py` | 10 | All passed |
| Full suite | 1334 passed, 11 skipped | ✅ |

**New tests (12)**:

| Test | What it verifies |
|------|-----------------|
| `test_detects_session_layout` | Session adapter detects valid session H5 with paired sets |
| `test_detect_false_for_canonical` | Session adapter returns False for canonical layout |
| `test_detect_false_for_missing_session_sets` | Session adapter returns False without /session/sets |
| `test_detect_false_for_missing_contralateral_pair` | Session adapter returns False without matching contralateral |
| `test_detect_false_for_calibration_layout` | Session adapter returns False for calibration layout |
| `test_resolves_first_pair_by_default` | Resolves first valid pair with explicit refs |
| `test_includes_patient_identifier` | Context includes patient identifier metadata |
| `test_raises_on_missing_integration` | Missing integration array raises H5ContainerError |
| `test_raises_on_q_axis_mismatch` | Mismatched q-axis lengths raise H5ContainerError |
| `test_preflight_passes_with_session_layout` | Full run_h5_preflight with session layout passes |
| `test_no_biopsy_or_birads_in_adapter` | No biopsy/birads used as prediction targets (AST-safe check) |
| `test_no_benign_vs_cancer_as_target` | No BENIGN/CANCER classification used as prediction targets |

## SAFETY BOUNDARY SUMMARY

- No Aramis product dependency
- No biopsy/birads/BENIGN/CANCER labels used as Bremen prediction targets
- Side metadata from sample_type → breast type → side (not hardcoded clinical labels)
- Patient metadata resolved through existing safe `resolve_patient_metadata()` path
- No raw patient names exposed in API/log/UI
- H5 files read-only — no mutation
- No committed H5 fixtures
- `technical_demo_only: true` preserved
- No new dependencies

## PRESERVED BEHAVIOR SUMMARY

- Canonical layout `/scans/target` — unchanged
- Calibration layout `/calib_*` — unchanged
- All existing adapters still registered and functional
- `detect_layout()` tries adapters in registration order
- Preflight via `run_h5_preflight()` unchanged
- `run_preprocessing_bridge()` backward compatible — only adds new branch for `"session_layout"`
- No changes to analyze endpoint, demo UI, or CLI

## IMPLEMENTATION REPORT WRITTEN: yes

## VALIDATION RESULTS

All commands passed (git, compileall, all test suites, CLI help, safety greps, forbidden file checks).

## PLAN COMPLIANCE

All PLAN.md requirements implemented:
- [x] `SessionLayoutH5Adapter` class implementing `H5LayoutAdapter` protocol
- [x] Detection of `/session/sets` with paired `set_NNN_sample_main` + `contralateral_set_NNN_sample_main`
- [x] Integration q/i array validation
- [x] Q-axis length + compatibility check
- [x] Patient metadata via `resolve_patient_metadata()`
- [x] Side metadata from sample_type (not clinical labels)
- [x] No biopsy/birads/BENIGN/CANCER as prediction targets
- [x] Registered as 3rd built-in adapter
- [x] Preprocessing bridge `"session_layout"` branch added
- [x] `_extract_session_profiles()` helper
- [x] 12 new tests covering detection, context resolution, preflight, safety

## BLOCKERS

None.

## WARNINGS

None.

## BOUNDARY CONFIRMATIONS

- confirm: PR0071 implemented as legacy/synthetic H5 ingestion-boundary adapter: yes
- confirm: no Aramis product dependency: yes
- confirm: legacy session/sets layout detection implemented: yes
- confirm: set/contralateral pairing implemented: yes
- confirm: integration q/i normalization implemented: yes
- confirm: `/scans/target` preserved for Bremen-native path: yes
- confirm: `/scans/target` not required for legacy session layout: yes
- confirm: side/problem metadata not used as Bremen target: yes
- confirm: biopsy/birads/status labels not used as Bremen target: yes
- confirm: raw patient metadata not exposed: yes
- confirm: H5 files not mutated: yes
- confirm: no committed H5/HDF5 files: yes
- confirm: preflight failures stop before preprocessing/model events: yes
- confirm: no fake success: yes
- confirm: PR0068/0069/0070 UI preserved: yes
- confirm: no React added: yes
- confirm: no package manager files added: yes
- confirm: no new dependencies added: yes
- confirm: no new startup command: yes
- confirm: no --ui flag: yes
- confirm: no root / demo page: yes
- confirm: no deployment mutation: yes
- confirm: no Terraform/GitHub Actions/Docker changes: yes
- confirm: no unsafe model loading added: yes
- confirm: no clinical diagnosis/replacement claims added: yes
- confirm: no H5/model/tfstate artifacts: yes
- confirm: no git mutation commands: yes
