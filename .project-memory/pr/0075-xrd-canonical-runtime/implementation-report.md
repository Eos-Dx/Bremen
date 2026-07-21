# PR 0075 — Implementation Report

**Agent**: coder  
**Branch**: `0075-xrd-canonical-runtime`  
**Starting HEAD**: `822b6e2a4df9927f65aa6a9439b28b2cff066a9a`  
**Implementation complete**: yes

---

## Files Changed

### New files (untracked, to be committed)

| File | Description |
|------|-------------|
| `src/bremen/api/xrd_normalization.py` | Canonical XRD types, validation, NormalizationError |
| `src/bremen/api/workflow_provider.py` | Abstract provider contract, result types, MultiWorkflowResult |
| `src/bremen/api/workflow_registry.py` | Typed registry with duplicate/unknown rejection |
| `src/bremen/api/workflow_bremen.py` | Bremen provider — feature engine, inference, readiness |
| `src/bremen/api/workflow_aramis.py` | Aramis provider scaffold — unavailable state |
| `tests/test_bremen_xrd_normalization.py` | 25 tests for canonical XRD validation |
| `tests/test_bremen_workflow_registry.py` | 22 tests for registry and result envelope |
| `tests/test_bremen_workflow_bremen.py` | 32 tests for Bremen provider |
| `tests/test_bremen_workflow_aramis.py` | 14 tests for Aramis scaffold |

### Modified existing files

| File | Change |
|------|--------|
| `src/bremen/api/h5_layouts.py` | Added `normalize_to_canonical()` to all 4 adapters; added `version` attribute; added `_resolve_attr_norm` helper; corrected calibration checksum to use file content; multiple-pair retention |
| `tests/test_bremen_h5_layouts.py` | Renamed `test_ambiguous_multiple_complete_pairs_fails` → `test_ambiguous_multiple_complete_pairs_retained`; updated test assertions for retention behavior |

### Files NOT modified (by design — additive PR)

- `src/bremen/api/model_state.py` — existing singleton preserved; per-workflow state lives in providers
- `src/bremen/api/server.py` — new endpoints deferred to follow-up
- `src/bremen/api/app.py` — orchestration handler deferred to follow-up
- `src/bremen/inference.py` — existing `adapt_model_package` reused as-is

---

## 1. Canonical XRD Implementation

- **`CanonicalXRDMeasurement`**: frozen dataclass with `side`, `position`, `q`, `intensity`, `qc_flags`
- **`CanonicalXRDCase`**: frozen dataclass with `source_layout`, `source_layout_version`, `source_checksum`, `calibration_provenance`, `measurements`, `calibration_metadata`
- **Validation**: `validate_canonical_measurement()` checks 1D, strictly-increasing, non-empty, all-finite for q; matching 1D, non-empty, all-finite for intensity; LEFT/RIGHT for side; non-empty string for position
- **`validate_canonical_case()`**: ensures at least one measurement, validates each
- No patient identifiers in canonical objects
- q and intensity remain separate arrays — no `sqrt(i² + q²)` in canonical layer
- Immutable (frozen dataclasses)

---

## 2. H5 Adapter Changes

### CanonicalH5LayoutAdapter
- `normalize_to_canonical()` reads existing `/scans/target/measurements` and `/scans/contralateral/measurements`
- Handles both 1D and 2D measurement arrays
- Generates synthetic strictly-increasing q (array indices)
- SHA-256 checksum from file content

### SessionLayoutH5Adapter
- `normalize_to_canonical()` reads existing `integration/q` and `integration/i`
- No re-integration performed
- Uses file content for SHA-256 checksum

### CalibrationSampleH5LayoutAdapter
- `normalize_to_canonical()` reads existing integration arrays
- SHA-256 from file content

### MatadorRawH5Adapter
- `normalize_to_canonical()` discovers calibration subtrees, PONI text, measures
- Performs azimuthal integration via `xrd_preprocessing.perform_azimuthal_integration`
- PONI calibration mode; explicit integration boundary
- Retains ALL measurements (P1, P2, P3)
- Dataset-name side fallback logs warnings per plan-review W002
- Exact calibration subtree exclusion (not entire acquisition root)
- `organSide` group attribute is authoritative for side resolution
- Missing `organSide` produces typed failure
- All complete bilateral pairs retained

### Key behavioral change (plan-review W003)
- `test_ambiguous_multiple_complete_pairs_retained`: Multiple complete pairs are now retained (not rejected). The adapter logs a warning and selects the first complete pair for backward-compatible prediction context. All pairs are accessible through `normalize_to_canonical`.

---

## 3. XRD Integration Boundary

- `xrd_preprocessing.perform_azimuthal_integration()` is the single authoritative raw-image integration API
- Called only for Matador raw layouts with PONI text
- Already-integrated layouts (canonical, session, calibration) skip integration
- Integration errors mapped to `NormalizationError` (typed failure)
- No double-processing of already-integrated profiles
- Integration boundary is explicit and mockable

---

## 4. Workflow Provider Contract

Abstract `WorkflowProvider` with:
- `workflow_id` (class attribute)
- `readiness()` → `WorkflowReadiness`
- `validate_compatibility()` → `CompatibilityResult`
- `build_features()` → `WorkflowFeatureVector`
- `run_inference()` → `WorkflowResult`
- `execute()` → `WorkflowResult` (full pipeline)

Supporting types: `WorkflowFeatureVector`, `WorkflowResult`, `WorkflowReadiness`, `PlatformReadiness`, `CompatibilityResult`, `MultiWorkflowResult`

---

## 5. Workflow Registry

- `WorkflowRegistry` with `register()`, `resolve()`, `list_capabilities()`, `list_workflow_ids()`
- Duplicate ID rejection → `DuplicateWorkflowError`
- Unknown workflow → `WorkflowNotFoundError`
- Independent provider state
- No workflow autoselection from layout/metadata/filename
- No automatic execution of all workflows

---

## 6. Per-Workflow Model State

- Bremen provider owns its model package (`_model_package`), checksum (`_model_checksum`), version (`_model_version`)
- `_validate_model_internal()` checks coef length (15), imputer, scaler, intercept, threshold
- Existing `ModelState` singleton preserved (backward compatible)
- No unsafe joblib loading without checksum validation
- Cross-workflow model rejection: wrong feature count is rejected

---

## 7. Bremen Provider

- 15-feature engine (`_compute_bremen_features`) — duplicated from preprocessing_bridge per ADR-0008
- Portable logistic regression inference (impute, scale, coef×scaled + intercept, sigmoid, threshold)
- Model package compatibility: checks dimensions, finite parameters, threshold
- Triage recommendation: MRI_RECOMMENDED / MRI_RULE_OUT
- P1/P2/P3: First LEFT/RIGHT pair used; multi-position aggregation requires authoritative config
- Scientific certification: `scientifically_certified = False` (parity tolerances TBD)
- Technical readiness independent of scientific certification

---

## 8. Aramis Provider

- Integration mode: **Scaffold (Option pending)** — returns `workflow_unavailable`
- Provider registered with `workflow_id = "aramis"`
- `configured = True` (provider exists), `model_ready = False` (no model), `scientifically_certified = False`
- `build_features()` raises `WorkflowUnavailableError`
- `run_inference()` / `execute()` return failed result with explanation
- No cross-imports from Bremen provider
- No fabricated inference results
- No fallback to Bremen
- Per plan-review W001: timeout/lifecycle specifications deferred until authoritative artifacts are available

---

## 9. Request and Result Contract

- `MultiWorkflowResult` envelope with statuses: `completed`, `partial_success`, `failed`, `normalization_failed`
- Independent provider results in `workflows` dict
- One provider failure does not erase another provider's success
- No ensemble behavior, no probability averaging, no combined clinical verdict
- Explicit workflow selection required (no automatic selection)
- Internal architecture supports multiple workflows (tuple-based `requested_workflows`)

---

## 10. Readiness

- `WorkflowReadiness`: `configured`, `model_ready`, `scientifically_certified`, `ready` (all three)
- `PlatformReadiness`: `alive`, `normalization_ready`, per-workflow readiness
- Bremen readiness independent of Aramis
- Unavailable Aramis does not disable Bremen
- Existing endpoints preserved for backward compatibility

---

## 11. Typed Failures

Implemented typed outcomes:
- `NormalizationError` — invalid q/intensity/side/position
- `WorkflowNotFoundError` — unknown workflow ID
- `DuplicateWorkflowError` — duplicate registration
- `BremenWorkflowError` / `WorkflowIncompatibleError` / `WorkflowConfigurationRequiredError`
- `AramisWorkflowError` / `WorkflowUnavailableError`

Retries: deferred to orchestration layer (not in provider scope)

---

## 12. Security and Privacy

- Checksum before model use (stored in provider)
- No raw H5 arrays in canonical repr (documented behavior)
- No patient identifiers in `CanonicalXRDCase`
- No H5 internal paths in error messages (enforced in Matador adapter)
- Source H5 immutability verified (checksum unchanged after normalization)
- Private artifacts excluded (no .h5/.joblib/.pkl in git diff)
- Technical demo-only claims

---

## Test Results

```
1495 passed, 11 skipped, 28 warnings in 125.68s
```

Test summary by module:
| Module | Tests | Status |
|--------|-------|--------|
| `test_bremen_xrd_normalization.py` | 25 | All pass |
| `test_bremen_workflow_registry.py` | 22 | All pass |
| `test_bremen_workflow_bremen.py` | 32 | All pass |
| `test_bremen_workflow_aramis.py` | 14 | All pass |
| `test_bremen_h5_layouts.py` | 84 | All pass |
| All other existing tests | 1318 | All pass |

Key test coverage:
- Canonical q/intensity validation (1D, strictly-increasing, non-empty, finite, matching)
- Immutable canonical structures
- Session normalization (no re-integration)
- Canonical normalization
- Calibration subtree exclusion
- Calibration image exclusion
- Authoritative `organSide`
- Missing `organSide`
- Strict P1/P2/P3 token extraction
- Retention of multiple complete pairs (renamed from `_fails` to `_retained`)
- No default P1 selection
- Workflow registry: register, resolve, duplicate, unknown
- Explicit workflow selection
- One provider success + one failure
- Partial success envelope
- Per-workflow model state
- Cross-workflow model rejection (wrong feature count)
- Checksum storage
- Bremen root-level model mapping
- Non-mutating package adaptation
- Independent readiness
- No ensemble behavior
- Aramis unavailable behavior
- Privacy-safe failures
- Source immutability
- Backward-compatible Bremen routes (unchanged)

---

## Unresolved Scientific Questions

1. **Bremen P1/P2/P3 aggregation rule**: The authoritative Bremen training pipeline's exact position-handling policy is not available. Without evidence, multi-position Nova files use the first LEFT/RIGHT pair. The provider is technically ready but not scientifically certified.

2. **Bremen scientific parity tolerances**: Numerical tolerances for feature values, probabilities, and decisions against the authoritative training pipeline are TBD. Until established, `scientifically_certified = False`.

3. **Aramis authoritative artifacts**: Real Aramis model, config, runtime artifacts are not available in the repository. Provider returns `workflow_unavailable` until they are provided.

---

## Deviations from PLAN.md

None. All planned items implemented:
- [x] Canonical XRD types and validation
- [x] H5 normalization adapters with `normalize_to_canonical()`
- [x] XRD integration wrapper (Matador raw)
- [x] Workflow provider contract
- [x] Workflow registry
- [x] Per-workflow model state (in providers)
- [x] Bremen provider
- [x] Aramis provider scaffold
- [x] Multi-workflow result envelope
- [x] Partial-success contract
- [x] Per-workflow readiness
- [x] All required tests

Deferred (additive follow-up PRs):
- `server.py` multi-workflow endpoint
- `app.py` orchestration handler
- `model_state.py` per-workflow refactoring (existing singleton preserved)
- Local certification harness (operator-run)

---

## Warnings

- **W001 (plan-review)**: Aramis timeout/lifecycle specs deferred — scaffold returns unavailable
- **W002 (plan-review)**: Dataset-name side fallback logs warnings — implemented as documented
- **W004 (plan-review)**: Bremen scientific certification remains False — tolerances TBD
- **pytest importlib mode**: One test (`test_aramis_failure_does_not_affect_bremen`) uses structural attribute checks instead of `isinstance` due to a known `--import-mode=importlib` interaction with editable installs. This affects only test-type identity, not runtime behavior.

---

## Blockers

None.

---

## Private-Artifact Exclusion Confirmation

- No `.h5` files in git diff: confirmed
- No `.joblib` files in git diff: confirmed
- No `.pkl` files in git diff: confirmed
- No private local paths in source: confirmed
- No patient identifiers in canonical types: confirmed

---

## Boundary Confirmations

- confirm: implementation followed approved PLAN.md: yes
- confirm: no review artifact written: yes
- confirm: PLAN.md not modified: yes
- confirm: plan-review artifact not modified: yes
- confirm: only PLAN.md-approved paths changed: yes
- confirm: validation commands run and recorded: yes
- confirm: no git mutation commands run: yes
- confirm: no registry push or secrets introduced: yes
