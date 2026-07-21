# PR 0074 — Implementation Report

**Branch:** 0074-h5-runtime-rehearsal-corrections
**Mode:** implementation
**Date:** 2026-07-21

## Files Changed

1. `src/bremen/api/h5_layouts.py` — Matador adapter fixes (defects 2, 3, 4)
2. `src/bremen/api/server.py` — Typed stage classification + safe error details (defects 5, 6)
3. `tests/test_bremen_h5_layouts.py` — Real-like fixture + adapter-level correction tests
4. `tests/test_bremen_api_server.py` — Route-level session/matador tests + failure tests

## PR0073 Rehearsal Postmortem Resolution

| Defect | Root Cause | Fix |
|--------|-----------|-----|
| 1. Session container_id-only fails | `_validate_ref()` called before auto-detection branch | Move `_validate_ref()` inside explicit-ref branch only |
| 2. Calibration dataset misclassified | `_meas_visitor` treated ALL 2D numeric datasets as measurements | Two-phase discovery: calibration subtrees identified first, then excluded from measurement list |
| 3. `organSide` unsupported | `SIDE_ATTR_KEYS` missing `organSide` | Added `"organSide"` to `SIDE_ATTR_KEYS` tuple |
| 4. Pair-key unreliable | Fallback stripped left/right from full filenames | Implemented `_extract_position_token()` using `P<number>` regex |
| 5. Incorrect stage classification | `H5ContainerError`/`H5MetadataError` inherit from `Exception`, not `RuntimeError`; fell through to generic `inference_failed` | Added typed except blocks for `H5PreflightError`, `PreprocessingBridgeError`, `PortableLogRegModelError` before generic handlers |
| 6. Unsafe error details | `str(exc)[:200]` exposed H5 paths, measurement filenames | Implemented `_safe_error_detail()` finite mapping |

## Session Mode-Selection Fix

- Both refs absent/blank → automatic pair detection (`_validate_ref` skipped)
- Both refs present → validate and use explicit refs
- Exactly one ref → `H5ContainerError("must be provided together or omitted together")`
- Whitespace-only strings count as absent

## Calibration/Measurement Separation

- Phase 1: `_calib_finder` walks H5 tree, records calibration subtree path prefixes
- Phase 2: `_meas_visitor` walks H5 tree, excludes datasets under calibration subtrees
- Calibration keywords: `poni`, `calib`, `calibration`, `distance`, `wavelength`, `pixel_size`, `center_x`, `center_y`
- 2D calibration images structurally identical to measurement datasets are excluded by path context

## organSide Handling

- `SIDE_ATTR_KEYS` now includes `"organSide"` alongside existing `"side"`, `"breast_side"`, `"sample_side"`
- Case-insensitive lookup via existing `_resolve_attr()`
- Aliases preserved; `organSide` directly supported

## P-Token Extraction and Pairing

- `_extract_position_token()` extracts exactly one `P<number>` token from dataset name
- Returns `None` for no token or multiple conflicting tokens
- Explicit `position`/`pair_key`/`measurement_position` attribute takes precedence
- No full-filename fallback
- No first-two pairing
- No arbitrary pair selection

## Multiple-Pair Behavior

- 0 complete bilateral pairs → `H5ContainerError("No complete bilateral pair")`
- 1 complete pair → used deterministically
- 2+ complete pairs → `H5ContainerError("Ambiguous bilateral pair set")`
- No silent selection of an arbitrary pair

## Typed Exception Hierarchy

Three typed except blocks added before generic handlers:

1. **h5_preflight_failed**: `H5PreflightError`, `H5ContainerError`, `H5MetadataError`, `H5PatientMismatchError`, `H5SideMismatchError`, `H5MeasurementError`, `H5QualityError`
2. **preprocessing_failed**: `PreprocessingBridgeError`, `PreflightNotPassedError`, `FeatureSchemaMismatchError`
3. **inference_failed**: `PortableLogRegModelError`, `FeatureArtifactError`

Fallback `RuntimeError`/`ValueError`/`KeyError`/`TypeError` block retained with message-based classification for exceptions raised by `inference_handler.run_inference()` which wraps errors in `RuntimeError`.

## Public Safe-Error Mapping

`_safe_error_detail()` maps exception types to finite, generic strings:

- `H5ContainerError`, `H5MetadataError`, `H5PatientMismatchError`, `H5MeasurementError`, `H5QualityError`, `H5PreflightError` → `"H5 layout metadata is incomplete"`
- `H5SideMismatchError` → `"Bilateral measurement pairing failed"`
- `PreprocessingBridgeError`, `FeatureSchemaMismatchError`, `PreflightNotPassedError` → `"Preprocessing failed"`
- `PortableLogRegModelError`, `FeatureArtifactError` → `"Model inference failed"`
- Unknown → `"Internal error"`

Public response NEVER contains: H5 paths, filesystem paths, S3 URIs, measurement filenames, patient identifiers, raw exception class names, raw messages, stack traces. Full traceback preserved in server logs via `logging.exception()`.

## PONI Limitation

`_matador_raw_to_q_i()` continues to require PONI text calibration. Unsupported calibration representation raises `PreprocessingBridgeError` mapped to `preprocessing_failed` with safe detail `"Preprocessing failed"`.

## Test Results

```
1393 passed, 11 skipped, 28 warnings
```

### Layout tests: 84 passed, 1 skipped
- Real-like Matador fixture with calibration exclusion, organSide, P-token pairing
- Session mode selection: no-refs auto-detect, explicit refs, exactly-one-ref rejection, whitespace handling
- Calibration exclusion, missing P-token, conflicting P-tokens, duplicate side, incomplete bilateral, ambiguous multiple pairs, missing organSide, unsupported side, checksum immutability, no-path leak

### Server tests: 80 passed
- Session route-level no-refs success
- Matador route-level success (preserved from PR0073)
- Preflight error → h5_preflight_failed (not inference_failed)
- Preprocessing error → preprocessing_failed
- Model error → inference_failed
- No downstream events after failure
- Public error safety: no H5 paths, identifiers, raw exception classes, file paths
- Safe default detail for unknown errors

## Validation Results

| Check | Result |
|-------|--------|
| python -m compileall src tests | PASS |
| pytest tests/test_bremen_h5_layouts.py | 84 passed, 1 skipped |
| pytest tests/test_bremen_api_server.py | 80 passed |
| pytest -q (full suite) | 1393 passed, 11 skipped |
| python -m bremen --help | PASS |
| python -m bremen serve --help | PASS |
| python -m bremen demo-smoke --help | PASS |
| python -m bremen demo-run --help | PASS |
| grep _validate_ref → after auto-detection branch | PASS |
| grep organSide → in SIDE_ATTR_KEYS | PASS |
| grep calibration.*measurement → exclusion comment found | PASS |
| grep pair_key → P-token extraction used | PASS |
| grep "first complete pair" → none found | PASS |
| grep "first two" → none found | PASS |
| grep str(exc) in demo handler → replaced with _safe_error_detail | PASS |
| grep h5_preflight_failed → typed except blocks | PASS |
| grep patient_name in server error paths → none found | PASS |
| grep FeatureArtifactPredictionError → found in feature_artifact_prediction.py (existing) | INFO |
| git diff forbidden files → no output | PASS |
| git diff binary artifacts → no output | PASS |
| find .DS_Store → no output | PASS |
| git diff --name-only → 4 files exactly | PASS |

## Blockers

None.

## Warnings

- `FeatureArtifactPredictionError` / `FeatureArtifactPredictorError` exist in `src/bremen/api/feature_artifact_prediction.py` (discovered after plan-review was written). These classes were not needed for the typed except blocks in this PR; `PortableLogRegModelError` and `FeatureArtifactError` were used instead.

## Boundary Confirmations

- confirm: implementation followed approved PLAN.md
- confirm: no review artifact written
- confirm: PLAN.md not modified
- confirm: plan-review artifact not modified
- confirm: only PLAN.md-approved paths changed (4 files)
- confirm: validation commands run and recorded
- confirm: no git mutation commands run
- confirm: no registry push or secrets introduced

## Implementation Complete

**IMPLEMENTATION COMPLETE: yes**
