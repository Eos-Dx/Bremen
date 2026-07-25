# PR0088 Implementation Report

## Production Symptom

v0.2.0 model candidate was discovered but shown as unavailable/not_compatible.
Manual S3 artifact checksum verification confirmed expected checksum == actual checksum,
ruling out checksum mismatch as the root cause.

## Checksum Verification Result

Checksum verification is **preserved exactly as-is**. The root cause was NOT
checksum mismatch — it was missing `portable_logreg.threshold` in the v0.2.0
joblib package while the validated manifest already contained `threshold_value`.

## Why Checksum Validation Was Preserved

Checksum validation is a critical security boundary. Removing it would
weaken the entire model loading pipeline. Since the actual checksum matched
the expected checksum, the real issue was package-structure compatibility.

## Manifest Threshold Fallback Behavior

A temporary discovery-only fallback was added: after `adapt_model_package(package)`
runs, if `package["portable_logreg"]["threshold"]` is still missing, the validated
manifest `threshold_value` is copied into `package["portable_logreg"]["threshold"]`.

This happens **before** `_validate_loaded_package()` so the same adapted package
object is validated with the fallback in place and stored in `RegistryModelEntry._package`.

## Precedence Order

1. Existing `portable_logreg.threshold` in the package wins (not overwritten).
2. Existing root-level `threshold` adapted by `adapt_model_package()` wins (not overwritten).
3. Validated manifest `threshold_value` is used only if both package locations are missing.

Only `threshold` is backfilled. No other fields are touched:
- coef, intercept, feature_columns, scaler values, imputer values, classes
- feature_schema_version, workflow_id, model_version, checksum
- Any scientific metric

Packages that still fail `_validate_loaded_package()` after the fallback remain
unavailable/not_compatible. Validation is not weakened.

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/s3_model_discovery.py` | +61 lines: `_apply_manifest_threshold_fallback()` helper + call site |
| `tests/test_s3_model_discovery.py` | +319 lines: PR0088 test class (8 tests), 2 existing test updates |
| `tests/test_catalog_api_multi_model.py` | +82 lines: PR0088 API surface test class (3 tests) |
| `agents/coder.yml` | Model name changed (unrelated config change) |

## Tests Added

11 new tests + 2 existing tests updated for compatibility with the fallback.

### New Tests (test_s3_model_discovery.py — TestPR0088ManifestThresholdFallback)
1. `test_missing_threshold_in_package_becomes_available_via_fallback` — Package with no threshold, manifest has threshold_value → available
2. `test_stored_package_has_threshold_from_fallback` — `_package` contains threshold from manifest
3. `test_existing_nested_threshold_not_overwritten_by_manifest` — Existing `portable_logreg.threshold` preserved
4. `test_root_threshold_not_overwritten_by_manifest` — Root-adapted threshold preserved
5. `test_checksum_mismatch_still_rejects` — Checksum mismatch still rejects
6. `test_missing_other_field_still_rejected` — Missing coef still fails validation
7. `test_v02_like_package_becomes_available_with_fallback` — v0.2-like package becomes available
8. `test_fallback_log_safe_fields_only` — Log includes model_id + event, NOT threshold value/S3 key/checksum

### New Tests (test_catalog_api_multi_model.py — TestPR0088CatalogApi)
9. `test_available_model_catalog_does_not_expose_threshold_value`
10. `test_unavailable_entry_catalog_does_not_expose_threshold_value`
11. `test_mixed_catalog_does_not_expose_threshold_value`

### Updated Tests
- `TestPackageAdapter.test_missing_portable_logreg_threshold_rejected` — Added `threshold_value=0.0` to manifest
- `TestPR0087UnavailableDiscovery.test_bad_package_structure_rejected` — Added `threshold_value=0.0` to manifest

## Focused Tests

```
python -m pytest -q tests/test_s3_model_discovery.py -v  → 85 passed
python -m pytest -q tests/test_catalog_api_multi_model.py -v  → 20 passed
```

## Full Suite

```
python -m pytest -q  → 2010 passed, 11 skipped, 28 warnings
```

## Safety Grep Results

| Check | Result |
|-------|--------|
| `threshold_value` in start_page_ui.py / model_catalog.py | No output (clean) |
| `str(exc)/repr(exc)/exception` in model_catalog.py / start_page_ui.py | No output (clean) |
| `AccessDenied/assumed-role/arn:aws/s3://` in start_page_ui.py / model_catalog.py | No output (clean) |
| `manifest_key/str(exc)/repr(exc)` in s3_model_discovery.py | Only `manifest_key` internal field references (clean) |

## Diff Check

```
git diff --check  → No output (no whitespace errors)
```

## Known Warnings

- `agents/coder.yml` contains an unrelated model name change (`deepseek-v4-flash` → `deepseek-v4-pro`). This is a config change, not part of PR0088.
- Full suite produces 28 DeprecationWarnings from NumPy 2.5/joblib compatibility. These are pre-existing and unrelated to PR0088.

## Rollback Instruction

To roll back this hotfix, revert the changes to:
- `src/bremen/api/s3_model_discovery.py` (remove `_apply_manifest_threshold_fallback` and its call site)
- `tests/test_s3_model_discovery.py` (remove TestPR0088ManifestThresholdFallback, revert 2 test updates)
- `tests/test_catalog_api_multi_model.py` (remove TestPR0088CatalogApi)

## Explicit Affirmations

This hotfix does NOT disable checksum verification.

This hotfix does NOT weaken model validation.

This hotfix only uses validated manifest threshold_value as temporary fallback
for missing portable_logreg.threshold.

Future model exporter should embed threshold into the package so this
fallback can be removed.
