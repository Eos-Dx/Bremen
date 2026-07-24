# PR0085 Implementation Report — Startup S3 Model Discovery and Per-Job Model Selection

## Summary

Implemented the complete S3 model catalog discovery pipeline with an immutable process-local model registry. Two mutually exclusive startup modes: catalog mode (BREMEN_MODEL_CATALOG_URI) and legacy mode (BREMEN_MODEL_URI). After bootstrap, all catalog, health, model-version, job, workflow, report, history, and UI behavior reads from one finalized registry.

## Architecture

- **Catalog mode**: BREMEN_MODEL_CATALOG_URI triggers S3 discovery at startup. Legacy BREMEN_MODEL_URI is ignored with a warning.
- **Legacy mode**: When catalog URI is absent, ModelState loads as before and a single-entry registry is built.
- **Registry**: Immutable after startup. Request handlers receive read-only access. No S3 calls after startup.

## Configuration Precedence

1. BREMEN_MODEL_CATALOG_URI (catalog mode, takes precedence)
2. BREMEN_MODEL_URI (legacy mode, only when catalog URI absent)

## Discovery Algorithm

- Parse catalog URI into bucket and prefix
- ListObjectsV2 without Delimiter
- Filter for keys matching `{prefix}{package_dir}/manifest.json` (exactly one level below prefix)
- Sort lexicographically
- Enforce 50 candidate maximum
- Enforce 65536 manifest byte maximum

## Manifest Validation

- Size check before parse
- JSON parse
- Base manifest fields validated via `model_package.validate_model_manifest()` (threshold_version, threshold_value, qc_criteria_version, feature_schema_version, artifact_type, model_checksum, model_filename, model_version)
- Discovery fields (model_id, display_name, workflow_id) — NOT added to legacy _REQUIRED_MANIFEST_FIELDS
- model_id pattern: `^[a-z0-9][a-z0-9._-]{0,63}$`
- display_name: non-empty, max 80 chars
- workflow_id: must be "bremen"

## Duplicate Handling — Two-Phase Rejection

Phase 1: Download, parse, base-validate, and discovery-validate all candidate manifests.

Phase 2: Count model_id occurrences among otherwise valid manifests. Reject every candidate whose model_id occurs more than once. Only unique model_ids proceed to artifact staging, checksum verification, deserialization, package validation, and registry insertion.

All occurrences of a duplicated model_id are rejected. The first occurrence is NOT accepted. Unrelated unique models remain available.

## Registry Lifecycle

- Created during startup bootstrap (single-threaded)
- Protected by threading.Lock with double-checked pattern
- Stored on bremen package for reload safety
- Immutable after initialize_registry() returns
- Reads from request handler threads are safe without locks

## Legacy Behavior

- BREMEN_MODEL_URI mode unchanged
- ModelState.load_at_startup() still called
- build_legacy_registry() converts ModelState to a single-entry registry
- model_id = "bremen-current"

## Catalog API

- GET /demo/api/models reads from registry snapshot
- Deterministic model_id ordering
- default_model_id: null for zero, model_id for exactly one, null for multiple
- Safe aggregate counts: candidate_count, available_count, rejected_count
- Status values: available, not_configured, no_valid_models, discovery_failed

## Start-Page Behavior

- One model: auto-selected (unchanged)
- Multiple models: requires explicit selection (unchanged)
- Zero models: disables progression (unchanged)

## Job Binding

- POST /demo/api/jobs binds one immutable model_id before execution
- In catalog mode, get_provider_for_model(model_id) reads the registry and constructs a fresh BremenProvider with the specific package
- Unknown model_id: rejected with typed error
- No model_id with 2+ models: rejected ambiguous
- Provider is fresh per job — no shared mutable state

## Execution Binding

- get_provider_for_model() in workflow_orchestrator.py
- Reads registry entry's private package, checksum, version
- Constructs BremenProvider with model_package, model_checksum, model_version, model_id
- model_id parameter added to BremenProvider.__init__ (default None for backward compatibility)

## Health

- Legacy mode: model_ready = ModelState.is_ready() (unchanged)
- Catalog mode: model_ready = (registry.available_count > 0)
- HTTP 200 with model_ready=false when discovery empty or failed
- Successful health log suppression intact

## Model Version

- Zero models: not_configured
- One model: that model's safe metadata
- Multiple models: selection_required with null singular fields
- No arbitrary first/lexicographic/timestamp selection

## Privacy

- No BREMEN_MODEL_CATALOG_URI, bucket, prefix, manifest key, artifact key, S3 URI, filename, staging path, checksum, package content, coefficients, intercepts, scaler values, imputer values, reference distributions, or environment values in public responses
- Safe structured logs: catalog_status, candidate_count, available_count, rejected_count, model_id, error_category

## Thread Safety

- Registry written exactly once during startup (single-threaded)
- After that, immutable and read-only
- Reads from request handler threads are safe without locks
- Initialization function protected by threading.Lock with double-checked pattern
- Registry reference stored on bremen package

## Files Added

- **`src/bremen/api/model_registry.py`** — RegistryModelEntry dataclass, ModelRegistry dataclass, initialize_registry(), get_registry(), get_model_entry(), get_model_package(), get_model_checksum(), build_legacy_registry()
- **`src/bremen/api/s3_model_discovery.py`** — discover_models(), URI validation, S3 listing, manifest validation, artifact staging and loading, package validation. Two-phase duplicate rejection.
- **`tests/test_s3_model_discovery.py`** — 56 tests: catalog URI validation, S3 listing, manifest validation, discovery field validation, artifact resolution, package validation, full discovery pipeline, base manifest rejection pipeline (qc_criteria_version, artifact_type, model_version), duplicate model_id handling, no post-startup S3 work.
- **`tests/test_model_registry.py`** — 21 tests: registry creation, immutability, singleton access, get_model_entry, get_model_package, deterministic ordering, safe serialization, workflow incompatibility, ambiguous selection, legacy compatibility.
- **`tests/test_multi_model_execution.py`** — 8 tests: two-model output proof, model_id in result payload, ModelState isolation, concurrent execution with two models, no cross-job mutation, deterministic repeated execution.
- **`tests/test_catalog_api_multi_model.py`** — 10 tests: zero-model response, one-model response, multiple-model response, deterministic ordering, no private fields, only technically valid models, rejected duplicates, safe aggregate counts, catalog status values.
- **`tests/test_health_multi_model.py`** — 4 tests: zero models HTTP 200 model_ready false, discovery failure HTTP 200 model_ready false, one model model_ready true, multiple models model_ready true.
- **`tests/test_model_version_multi_model.py`** — 4 tests: zero models not_configured, one model singular metadata, multiple models selection_required with null fields, no arbitrary model selected.

## Files Modified

- **`src/bremen/api/model_catalog.py`** — Reads from registry instead of ModelState. Re-exports RegistryModelEntry as ModelEntry for backward compatibility.
- **`src/bremen/api/app.py`** — handle_health() checks registry first. handle_model_version() checks registry for catalog mode (zero/one/multiple model behavior).
- **`src/bremen/api/server.py`** — run_server() startup bootstrap with catalog/legacy mode selection.
- **`src/bremen/api/workflow_bremen.py`** — Added model_id parameter to BremenProvider.__init__ (default None).
- **`src/bremen/api/workflow_orchestrator.py`** — Added get_provider_for_model() function.
- **`src/bremen/api/job_api_handler.py`** — create_analysis_job() uses get_provider_for_model() in catalog mode.
- **`src/bremen/api/s3_model_discovery.py`** — Removed dead _process_single_candidate function (buggy single-pass duplicate handling).
- **`tests/test_bremen_api_server.py`** — Updated server_info fixture to initialize registry. Updated test_model_version_configured to reset registry.
- **`tests/test_bremen_api_skeleton.py`** — Updated health and model-version tests to reset registry. Added s3_model_discovery.py to import safety allowlists.
- **`tests/test_bremen_model_catalog.py`** — Updated fixtures to initialize registry. Updated ModelEntry tests to include _package field.

## Base Manifest Validation Correction

The discovery pipeline calls `model_package.validate_model_manifest(data)` before `_validate_discovery_fields(data)`. This validates all authoritative base fields including threshold_version, threshold_value, qc_criteria_version, feature_schema_version, artifact_type, model_checksum, model_filename, and model_version. Pipeline-level rejection tests are added for invalid qc_criteria_version (empty string), invalid artifact_type (wrong value), and invalid model_version (empty string). Each test proves: the bad manifest is rejected, the artifact is NOT inserted into the registry, available_count stays at 1, rejected_count increments to 1, and no private storage or exception data appears in the result.

## Two-Phase Duplicate Rejection

Phase 1 downloads and validates all manifests, collecting (key, data) pairs. Phase 2 counts model_id occurrences and identifies duplicates. All candidates with duplicated model_ids are rejected, including the first occurrence. Only unique model_ids proceed to artifact staging, checksum verification, deserialization, and registry insertion. Tests cover: two duplicates no unique, two duplicates plus one unique, three occurrences of one duplicate, deterministic rejected_count and available_count.

## Two-Model Output Proof

test_multi_model_execution.py constructs two synthetic packages with different coefficients (PACKAGE_A_COEF=[0.01]*15, PACKAGE_A_INTERCEPT=-5.0 vs PACKAGE_B_COEF=[0.9]*15). The same controlled canonical XRD input produces probability < 0.5 for model-a and probability > 0.5 for model-b. The test uses the real registry-to-provider-to-execution path via get_provider_for_model().

## Concurrent Isolation Proof

Two concurrent jobs using threading.Barrier and ThreadPoolExecutor execute model-a and model-b simultaneously. Each job uses its own provider with its own package. Outputs match the correct package with no cross-bleed. Provider isolation is verified: provider_a._model_package is not provider_b._model_package. Repeated execution is deterministic.

## Health Discovery-Failure Proof

test_health_multi_model.py verifies: catalog_status="discovery_failed" returns HTTP 200 with model_ready=False. Zero available models returns HTTP 200 with model_ready=False. Multiple models returns model_ready=True.

## Validation Results

### Focused Tests
- **Command**: `python -m pytest -q tests/test_s3_model_discovery.py tests/test_model_registry.py tests/test_multi_model_execution.py tests/test_catalog_api_multi_model.py tests/test_health_multi_model.py tests/test_model_version_multi_model.py`
- **test_s3_model_discovery.py**: 56 passed
- **test_model_registry.py**: 21 passed
- **test_multi_model_execution.py**: 8 passed
- **test_catalog_api_multi_model.py**: 10 passed
- **test_health_multi_model.py**: 4 passed
- **test_model_version_multi_model.py**: 4 passed
- **Focused passed**: 103
- **Focused skipped**: 0
- **Focused failed**: 0

### Full Suite
- **Collected**: 1965
- **Command**: `python -m pytest -q` (unfiltered, no arguments)
- **Passed**: 1954
- **Skipped**: 11
- **Failed**: 0
- **Warnings**: 28 (pre-existing numpy deprecation warnings)
- **Duration**: 184.88s (0:03:04)

### Compileall
- **Command**: `python -m compileall src tests`
- **Result**: PASS

### Diff Check
- **Command**: `git diff --check`
- **Result**: PASS (no whitespace errors)

## Collection Difference Analysis

- 1965 tests collected in the current PR0085 branch.
- 75 test_*.py files exist under tests/.
- `git diff -- pyproject.toml pytest.ini setup.cfg tox.ini` returns empty — no pytest configuration changes.
- `git diff --name-status origin/main...HEAD -- tests` returns empty — no test files were deleted or renamed.
- The 1965 collected = 1954 passed + 11 skipped. All tests participate.
- No tests were removed, renamed out of discovery, skipped globally, or excluded by configuration.

## Blockers

None.

## Warnings

- 28 pre-existing numpy deprecation warnings in joblib numpy_pickle.py (NumPy 2.5 shape assignment). Not related to PR0085.
- The `_process_single_candidate` function (dead code with buggy single-pass duplicate handling) has been removed. The main `discover_models()` function uses the correct two-phase approach.
