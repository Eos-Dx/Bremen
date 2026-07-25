# PR0087 — Implementation Report (Corrected)

## Root Cause

Production discovery found two catalog candidates (`candidate_count=2`, `available_count=1`, `rejected_count=1`). v0.1 was accepted. v0.2.0 was rejected during package validation for a `portable_logreg` threshold compatibility failure. The Start page and public model catalog hid the rejected candidate — visible only as `rejected_count` in aggregates.

## Current Log Diagnosis

Before PR0087: `candidate_count=2, available_count=1, rejected_count=1, catalog_status=available`. v0.1 accepted, v0.2.0 rejected silently — no public card, no API entry, no Start page visibility.

After PR0087: v0.2.0 appears as a disabled identified card with `reason_category=not_compatible`. The Start page renders "Not compatible with the current runtime" caption. The API includes it in `unavailable_models`.

## Candidate Inventory Semantics

- `candidate_count`: Unique immediate child package directories under the catalog prefix containing `manifest.json` or `.joblib` objects.
- `available_count`: Executable available models.
- `rejected_count`: Non-executable candidate package directories.
- `unavailable_count`: Public `unavailable_models` cards emitted.
- Discovery uses `_discover_package_directories()` replacing `_list_candidate_manifests()`.
- Directories are detected by grouping all S3 objects by immediate child directory.
- Each directory is a candidate if it contains `manifest.json` or `.joblib` objects.
- Deterministic ordering by directory name.

## Data Model

### `CatalogUnavailableEntry` (in `model_registry.py`)

Frozen dataclass with fields: `kind`, `reason_category`, `candidate_label`, `model_id`, `display_name`, `workflow_id`.

- `kind`: `"identified"` or `"unregistered"`
- `reason_category`: Fixed enum — `not_compatible`, `duplicate_entry`, `unregistered_package`
- `candidate_label`: Generic ordinal (e.g. "Discovered model package 1") for unregistered
- `model_id`/`display_name`/`workflow_id`: Only for identified kind
- `to_safe_dict()`: Returns only safe public fields
- Validation in `__post_init__`: Enforces field requirements per kind

### Extended `ModelRegistry`

New fields: `unavailable_entries`, `unavailable_count`, `last_discovery_at`.

## API Fields Added

`GET /demo/api/models` — new: `unavailable_models`, `unavailable_count`, `last_discovery_at`.

## Start Page Disabled-Card Behavior

- Disabled cards: `aria-disabled="true"`, `role="presentation"`, opacity 0.4
- Status rail: gray (`--status-unconfigured`) with white text
- Reason captions via JS lookup (not_compatible → "Not compatible with the current runtime", etc.)
- Catalog caption below grid

## Changed Files

1. `src/bremen/api/model_registry.py` — `CatalogUnavailableEntry` + extended `ModelRegistry`
2. `src/bremen/api/s3_model_discovery.py` — Major restructure: `PackageDirectoryInfo`, `_discover_package_directories()`, `_generate_candidate_labels()`, phased discovery, unavailable entry creation, sanitized logging, extended `CatalogDiscoveryResult`
3. `src/bremen/api/model_catalog.py` — Extended `build_model_catalog()` with `unavailable_models`, `unavailable_count`, `last_discovery_at`
4. `src/bremen/api/server.py` — Extended `ModelRegistry()` construction with new fields and updated startup log
5. `src/bremen/start_page_ui.py` — CSS: opacity 0.4, status-rail gray, catalog-caption class. JS: render `unavailable_models`, reason captions, catalog caption. HTML: catalog-caption div.
6. `docs/api_contract.md` — Documented new fields and safety rules
7. `tests/test_s3_model_discovery.py` — 13 new PR0087 tests
8. `tests/test_model_registry.py` — 14 new PR0087 tests
9. `tests/test_catalog_api_multi_model.py` — 6 new PR0087 tests
10. `tests/test_bremen_api_server.py` — 4 new PR0087 tests

## Server.Py Scope Justification

`server.py` is changed because it is directly required for registry snapshot construction. The `ModelRegistry()` constructor call must pass `unavailable_entries`, `unavailable_count`, and `last_discovery_at` from the discovery result to the registry. The startup completion log includes `unavailable_count` for observability. These are the minimal required changes — no other server.py logic is modified.

## New PR0087-Specific Regression Tests

### Discovery tests (test_s3_model_discovery.py — 13 new)
- `test_phase3_rejection_creates_identified_not_compatible`
- `test_phase3_rejection_no_raw_technical_detail`
- `test_duplicate_model_id_creates_single_duplicate_entry`
- `test_duplicate_display_name_deterministic`
- `test_joblib_only_creates_unregistered_package`
- `test_joblib_with_invalid_manifest_creates_unregistered`
- `test_joblib_with_manifest_missing_model_id_unregistered`
- `test_manifest_only_no_joblib_aggregate_only`
- `test_available_and_unavailable_coexist`
- `test_candidate_counts_accurate`
- `test_last_discovery_at_is_populated`
- `test_discovery_logs_no_manifest_key_in_warnings`
- `test_unavailable_to_safe_dict_no_raw_detail`

### Registry tests (test_model_registry.py — 14 new)
- `test_identified_entry_creation`
- `test_identified_rejects_missing_model_id`
- `test_unregistered_entry_creation`
- `test_unregistered_rejects_missing_label`
- `test_invalid_reason_category_rejected`
- `test_reason_categories_fixed_enum`
- `test_identified_to_safe_dict`
- `test_unregistered_to_safe_dict`
- `test_unavailable_entry_is_frozen`
- `test_unavailable_entry_not_resolvable`
- `test_available_entry_still_resolvable_with_unavailable_present`
- `test_default_model_id_ignores_unavailable`
- `test_registry_carries_unavailable_entries_and_last_discovery`

### Catalog API tests (test_catalog_api_multi_model.py — 6 new)
- `test_unavailable_models_field_present`
- `test_unavailable_models_empty_when_none`
- `test_default_model_id_uses_only_available`
- `test_default_model_id_null_when_unavailable_only`
- `test_resolve_unavailable_model_id_fails`
- `test_resolve_available_still_works_with_unavailable_present`
- `test_unavailable_models_safe_dict_no_raw_detail`

### Start page tests (test_bremen_api_server.py — 4 new)
- `test_start_page_renders_disabled_cards`
- `test_start_page_has_catalog_caption_div`
- `test_start_page_discovery_failed_no_raw_aws_error`
- `test_start_page_has_reason_captions`

## Focused Test Results

```
test_s3_model_discovery.py:      77 passed (was 64, 13 new PR0087)
test_catalog_api_multi_model.py: 17 passed (was 10,  7 new PR0087)
test_model_registry.py:          34 passed (was 21, 13 new PR0087)
test_bremen_api_server.py:       95 passed (was 91,  4 new PR0087)
```

## Full Suite Result

```
1999 passed, 11 skipped, 28 warnings, 0 failures (181.04s)
```

Up from 1962 passed — 37 new PR0087-specific tests added across all four test files.

## Diff Check

`git diff --check`: clean (exit 0). Only allowed files changed.

## Safety Grep Results

1. `start_page_ui.py`: `feature_schema_version` appears only in pre-existing available-card detail (line 143), not in new unavailable-card code.
2. No raw exception formatting in `model_catalog.py` or `start_page_ui.py`.
3. No AWS references in `start_page_ui.py` or `model_catalog.py`.
4. `manifest_key` in `s3_model_discovery.py` is internal variable (not logged to public). No `str(exc)` or `repr(exc)` in logs.
5. No public/UI reason categories from technical exception classes (technical terms in `model_registry.py` are field definitions, not reason categories).

## PR0087 Coverage Confirmation

125 matches of PR0087-specific terms (`unavailable_models`, `CatalogUnavailable`, `unavailable_entries`, `reason_category`, `candidate_label`, `not_compatible`, `duplicate_entry`, `unregistered_package`) across all four test files.

## Deployment Statement

PR0087 makes non-compliant discovered candidates visible as disabled display-only entries. It does not weaken runtime validation. Disabled candidates are display-only. Unavailable entries are not executable. Public API/UI does not expose raw rejection detail. The second model may still be non-executable; PR0087 makes it visible as a disabled card on the Start page instead of hiding it.

## Rollback Instruction

To revert: restore all changed files from the previous commit. No database migration, schema change, or infrastructure rollback required.
