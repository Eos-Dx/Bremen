# PR0086 — Implementation Report

## Root Cause

Production startup discovery found two real Bremen manifests but rejected both loaded packages with:

```
portable_logreg missing required fields: {'threshold'}
```

The real Bremen packages store `threshold` and `feature_columns` at the top-level dict, not inside `portable_logreg`. The discovery path (`_validate_loaded_package`) validates the raw loaded package directly, which lacks `portable_logreg.threshold`.

The existing `adapt_model_package` function in `src/bremen/inference.py` already provides the compatibility bridge — copying root-level `threshold` and `feature_columns` into `portable_logreg` when those nested fields are absent. The fix wires this adapter into the discovery pipeline.

## Import Added

```python
from ..inference import adapt_model_package  # noqa: PLC0415
```

Line 22 of `src/bremen/api/s3_model_discovery.py`.

## Adapter Call Location

Line 539 of `src/bremen/api/s3_model_discovery.py`, immediately after `_stage_and_load_artifact` returns and before `_validate_loaded_package` is called:

```python
package = adapt_model_package(package)
```

## Proof That Validation Receives the Adapted Package

The adapter call (`package = adapt_model_package(package)`) reassigns the local `package` variable. The next statement calls `_validate_loaded_package(package, entry_builder)`, which receives the adapted package. The raw unadapted package reference is discarded.

## Proof That RegistryModelEntry Stores the Adapted Package

The `RegistryModelEntry` constructor on line 558 receives `_package=package`, where `package` is the adapted value. No second unadapted reference is retained.

## Regression Tests Added

All in `tests/test_s3_model_discovery.py`, class `TestPackageAdapter`:

| # | Test | What It Proves |
|---|------|----------------|
| 1 | `test_root_threshold_passes_discovery` | Root threshold adapted → discovery passes |
| 2 | `test_root_feature_columns_passes_discovery` | Root feature_columns adapted → discovery passes |
| 3 | `test_registry_stores_adapted_package` | Registry entry stores the adapted view |
| 4 | `test_adapted_threshold_copied_from_root` | `portable_logreg.threshold` matches root value |
| 5 | `test_adapted_feature_columns_copied_from_root` | `portable_logreg.feature_columns` matches root list |
| 6 | `test_existing_nested_threshold_not_overwritten` | Nested threshold (0.33) takes precedence over root (0.99) |
| 7 | `test_missing_threshold_everywhere_rejected` | Package with no threshold anywhere is rejected |
| 8 | `test_missing_feature_columns_everywhere_still_passes_if_validator_ignores` | Discovery validator does not gate on feature_columns; no rule weakened |

All tests use fake S3 clients and synthetic packages. No AWS, private artifacts, or real models.

## Focused Test Result

```
64 passed in 1.64s
```

## Full Suite Result

```
1962 passed, 11 skipped, 28 warnings in 181.27s
```

Zero failures. The `ConnectionResetError` messages in stdout are harmless HTTP server thread noise from concurrent test client teardown.

## Diff Check

```
git diff --check → (no output — clean)
git diff --name-only:
  src/bremen/api/s3_model_discovery.py
  tests/test_s3_model_discovery.py
```

Only allowed files changed. No forbidden files modified.

## Changed Files

- `src/bremen/api/s3_model_discovery.py` — 1 import added, 3 lines added (adapter call + comment)
- `tests/test_s3_model_discovery.py` — `_make_root_level_package` helper + `TestPackageAdapter` class (8 tests)

## Blockers

None.

## Warnings

None. The adapter function `adapt_model_package` was confirmed present, compatible (`dict → dict`), importable without circular dependency, and requires no modification.

## Deployment Expectation

The previous `portable_logreg_missing_required_field_threshold` rejection must no longer occur for packages whose root `threshold` can be adapted. A package may still be rejected by another independent validation gate (e.g., checksum mismatch, missing `coef`, missing `intercept`, unsupported feature schema version).

## Boundary Confirmations

- `_validate_loaded_package` not changed
- `required_plr` not changed (`{'coef', 'intercept', 'threshold'}`)
- Manifest validation not changed
- Checksum validation not changed
- Artifact staging not changed
- Portable-logreg structural requirements not changed
- Workflow compatibility not changed
- Feature-schema compatibility not changed
- Threshold compatibility not changed
- Duplicate handling not changed
- Failure policy not changed
- Registry publication behavior not changed
- No inline threshold or feature_columns normalization added to `s3_model_discovery.py`
- `adapt_model_package` called exactly once per loaded candidate
- `adapt_model_package` not modified
- No review artifacts written
- PLAN.md not modified (not created)
- No git mutation commands run
- No registry push or secrets introduced
