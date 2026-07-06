# PR 0038 — Plan Preprocessing Bridge

Author: plan
Mode: planning only
Branch: 0038-preprocessing-bridge

## Objective

Implement a preprocessing bridge that converts a validated H5/preflight input into the Bremen 7-feature vector required by the model package contract. This is the third step on the critical path to Bremen's first working prediction — PR 0038 stops at feature table creation and schema validation, without loading models, calling predict, or wiring prediction routes.

## Critical path context

- PR 0036 — v0.1 model package publication infrastructure ✅
- PR 0037 — H5 preflight gate and historical H5 cleanup ✅
- **PR 0038** — Preprocessing bridge (this PR)
- PR 0039 — Inference integration / first working prediction

## Required reads — observed facts

### PR 0037 preflight (`src/bremen/api/preflight.py`)
- `run_h5_preflight()` returns `PreflightResult` with `passed` (bool), `reasons`, `warnings`, `patient_id`, `target_side`, `contralateral_side`, `target_measurement_count`, `contralateral_measurement_count`, `metadata`, `qc_flags`.
- No raw scan data in result.
- Synthetic H5 schema: `/patient/id`, `/scans/target/side|measurements|metadata/snr`, `/scans/contralateral/side|measurements|metadata/snr`.

### Training pipeline (`src/bremen/training/pipeline.py`)
- Contains `BREMEN_FEATURE_FAMILIES` constant (7 feature names).
- Contains complete feature computation functions: `_sigma_rms`, `_mahalanobis_difference`, `_profile_wasserstein`, `_rms_difference`, `_weighted_rms_difference`.
- These are private functions (`_`-prefixed) in the training package.

### Runtime/training separation rule
- Runtime (`src/bremen/api/`) must NOT import from `src/bremen/training/`.
- The preprocessing bridge lives under `src/bremen/api/` — it must not import from training.
- The bridge must have its own copy of the feature computation functions.

### Feature schema
- 7 Bremen feature families per ADR-0001 and ADR-0008: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
- Exact order as defined in `BREMEN_FEATURE_FAMILIES` in training pipeline.

### Existing preprocessing files
- `src/bremen/pipelines.py` — contains `run_preprocessing_from_config()`. This is a research-era module that imports `xrd_preprocessing` and `container`. It is NOT suitable for runtime use (imports private dependencies, uses local config paths with `extends:` chains, couples to local checkout).
- `tests/test_bremen_preprocessing_one_to_one.py` and `one_to_many.py` — test files that depend on the private deps, not suitable for runtime CI.

## Preprocessing bridge design

**File**: `src/bremen/api/preprocessing_bridge.py`

The bridge is a self-contained module that:
1. Accepts a validated H5 path (preflight must pass first) or a synthetic DataFrame for testing.
2. Reads profiles from H5 (target and contralateral sides).
3. Computes the 7 Bremen feature families as per-patient symmetry measures.
4. Returns a structured `PreprocessingBridgeResult` with the feature vector.

**Design decision: No import from training.** The 6 private feature computation functions (`_sigma_rms`, `_mahalanobis_difference`, `_profile_wasserstein`, `_rms_difference`, `_weighted_rms_difference` — plus `_extract_profiles` logic) are duplicated in the bridge module. This is safe, small, and maintains the runtime/training separation boundary.

### Public API

```python
BREMEN_FEATURE_COLUMNS: tuple[str, ...] = (
    "sigma_l1",
    "sigma_l2",
    "Mahalanobis1",
    "Mahalanobis2",
    "wasserstein_distance_full_q2",
    "meanrms2",
    "weightedrms1",
)

FEATURE_SCHEMA_VERSION: str = "v0.1"  # Matches current model package


@dataclass
class BremenFeatureVector:
    """Ordered feature vector with schema metadata."""
    features: list[float]          # Exactly 7 finite float values
    feature_names: list[str]       # Exactly feature order
    feature_schema_version: str    # Schema version string
    patient_id: str | None
    target_side: str | None
    contralateral_side: str | None


@dataclass
class PreprocessingBridgeResult:
    """Result of the preprocessing bridge."""
    passed: bool
    feature_vector: BremenFeatureVector | None
    warnings: list[str]
    qc_flags: list[str]
    preflight_summary: dict
```

### Exceptions

```python
class PreprocessingBridgeError(Exception):
    """Base exception for preprocessing bridge errors."""

class PreflightNotPassedError(PreprocessingBridgeError):
    """Preflight must pass before the bridge can run."""

class FeatureSchemaMismatchError(PreprocessingBridgeError):
    """Feature schema does not match expected columns or order."""
```

### Core functions

```python
def run_preprocessing_bridge(
    h5_path: str | Path,
    *,
    preflight_result: PreflightResult | None = None,
    skip_preflight: bool = False,
) -> PreprocessingBridgeResult:
    """Run the preprocessing bridge on a validated H5 container.

    Requires preflight to have passed (``preflight_result.passed == True``)
    unless ``skip_preflight=True`` (for testing).

    Returns a ``PreprocessingBridgeResult`` with the extracted feature vector.
    Raises ``PreflightNotPassedError`` if preflight was not passed.
    Raises ``PreprocessingBridgeError`` on extraction failure.
    """

def build_feature_table(
    h5_path: str | Path,
) -> dict[str, float]:
    """Extract the 7-feature vector from an H5 container.

    Reads target and contralateral profiles from H5.
    Computes per-patient symmetry measures for all 7 feature families.

    Returns a dict mapping feature names to finite float values.
    """

def validate_feature_schema(
    feature_vector: BremenFeatureVector,
    *,
    expected_version: str | None = "v0.1",
) -> None:
    """Validate feature vector against schema expectations.

    Checks:
    - Feature count matches ``BREMEN_FEATURE_COLUMNS``.
    - Feature names match exact order.
    - Feature schema version matches (if provided).
    - All values are finite (not NaN, not Inf).

    Raises ``FeatureSchemaMismatchError`` on any mismatch.
    """

def validate_feature_values(
    feature_vector: BremenFeatureVector,
) -> list[str]:
    """Validate feature values are finite. Returns warnings list.
    Does NOT raise on non-finite values — returns warnings.
    """
```

### Private helper functions (duplicated from training for runtime separation)

```python
def _extract_profiles(h5_file, base_group: str) -> list[np.ndarray]:
    """Extract profile arrays from an H5 scan group."""

def _mahalanobis_difference(target, contralateral) -> tuple[float, float]:
    """Mahalanobis1 and Mahalanobis2 — per-patient symmetry measure."""

def _profile_wasserstein(target, contralateral) -> float:
    """Wasserstein-1 distance for wasserstein_distance_full_q2."""

def _rms_difference(target, contralateral) -> float:
    """RMS asymmetry for meanrms2."""

def _weighted_rms_difference(target, contralateral) -> float:
    """Weighted RMS asymmetry for weightedrms1."""

def _sigma_rms(target, contralateral) -> tuple[float, float]:
    """Sigma RMS for sigma_l1 and sigma_l2."""

def _compute_file_sha256(path: str | Path) -> str:
    """SHA-256 of input file for provenance tracking."""
```

## Feature schema contract

- **Exact order**: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
- **Count**: Exactly 7.
- **Values**: All finite numeric (float).
- **Version**: `"v0.1"` (constant, matches current model package manifest).
- The bridge output is deterministic — same H5 input always produces the same feature vector.

## Model package schema gate

`validate_feature_schema()` provides the gate:

1. Check feature count matches `BREMEN_FEATURE_COLUMNS` (7).
2. Check feature names match exact order.
3. Check `feature_schema_version` matches expected version.
4. Check all values are finite.

This function does NOT load the model package. In PR 0039, the inference integration will additionally compare against model package manifest `feature_schema_version` and feature columns. For PR 0038, the gate uses the internal constant.

The current ADR-0007 manifest does not include a feature column list — that's deferred. PR 0038 defines the internal schema constant (`BREMEN_FEATURE_COLUMNS`, `FEATURE_SCHEMA_VERSION`). PR 0039 will add the comparison against runtime model package metadata.

## H5/preflight integration

- Bridge requires `preflight_result.passed == True` before extracting features.
- If `preflight_result` is not provided and `skip_preflight=False`, the bridge calls `run_h5_preflight()` first.
- On preflight failure, raises `PreflightNotPassedError`.
- Synthetic H5 tests use `skip_preflight=True` or pass a synthetic `PreflightResult(passed=True, ...)`.

## XRD/preprocessing evidence

Existing preprocessing code (`src/bremen/pipelines.py`, `tests/test_bremen_preprocessing_*.py`) depends on private dependencies (`xrd_preprocessing`, `container`) and local checkout-relative config paths. These are NOT reusable for the runtime bridge.

The bridge uses `h5py` directly to read H5 profiles (no `xrd_preprocessing` dependency). Feature computation logic is duplicated from training pipeline to maintain runtime/training separation.

**No real XRD preprocessing is performed in this PR.** The bridge reads raw measurement profiles from H5 and computes symmetry features. Full XRD preprocessing (azimuthal integration, peak detection, profile reduction) is assumed to be performed before the H5 file reaches the bridge.

## External H5 policy

- External H5 subset remains outside repo.
- Use only via `BREMEN_H5_PREFLIGHT_SMOKE_PATH`.
- CI must not require the external H5.
- No external H5 copied into repo.
- No derived artifacts committed.
- No clinical validation claim.

## Test plan

**File**: `tests/test_bremen_preprocessing_bridge.py`

### Default synthetic tests (always run)

1. `test_valid_preflight_and_synthetic_h5_produces_7_features` — Create synthetic H5 with target/contralateral profiles, pass preflight, verify result has exactly 7 features.
2. `test_feature_order_matches_BREMEN_FEATURE_COLUMNS` — Feature names in output match exact order.
3. `test_all_feature_values_are_finite_numeric` — All 7 values are finite floats.
4. `test_failed_preflight_blocks_bridge` — Pass `preflight_result(passed=False)`, verify `PreflightNotPassedError`.
5. `test_missing_feature_fails_validation` — Manually set feature count to 6, verify `FeatureSchemaMismatchError`.
6. `test_extra_feature_fails_validation` — Add an 8th feature, verify `FeatureSchemaMismatchError`.
7. `test_wrong_feature_order_fails_validation` — Reorder features, verify `FeatureSchemaMismatchError`.
8. `test_feature_schema_version_mismatch_fails` — Set version to `"v0.2"` when expected `"v0.1"`, verify mismatch.
9. `test_result_excludes_raw_arrays` — Result does not contain measurement arrays.
10. `test_no_model_loading_or_inference` — Importing the module does not trigger model loading, training imports, or inference.
11. `test_bridge_import_safe` — No `joblib`, `pickle`, `bremen.training` in module imports.
12. `test_bridge_deterministic` — Same H5 input produces identical feature values across calls.

### Optional real-subset smoke

13. `test_real_subset_bridge_smoke` — Skipped unless `BREMEN_H5_PREFLIGHT_SMOKE_PATH` is set. Runs full bridge (preflight + feature extraction). Verifies 7 features produced. No clinical assertions.

## Runtime/API boundary

- No changes to `POST /predictions`.
- No changes to `GET /predictions/{id}`.
- No inference module created or modified.
- `model_loader.py` unchanged — no model loading in this PR.
- `model_package.py` unchanged.
- Training pipeline unchanged.
- Terraform, Docker, GitHub workflows unchanged.
- ADRs, ROADMAP.md, architecture.md unchanged.

## Allowed implementation files

1. **`src/bremen/api/preprocessing_bridge.py`** — NEW
2. **`tests/test_bremen_preprocessing_bridge.py`** — NEW

Optionally:
3. `tests/test_bremen_import_identity.py` — MODIFY only if module discovery requires it
4. `tests/test_bremen_api_skeleton.py` — MODIFY only if new module should be visible there

## Forbidden files

- Any real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz`
- `src/bremen/api/inference.py`
- Prediction route implementation files
- `src/bremen/model_loader.py`, `model_package.py`
- `src/bremen/training/**`
- `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`, `.project-memory/project_contract.yml`
- Terraform files, `.github/**`, Dockerfiles
- `requirements.txt`, `pyproject.toml`
- `.gitignore`

## Validation checklist

```bash
# 1-3) Baseline
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Compile check
python -m compileall src tests

# 5-7) Bridge, preflight, identity tests
python -m pytest -q tests/test_bremen_preprocessing_bridge.py
python -m pytest -q tests/test_bremen_h5_preflight.py
python -m pytest -q tests/test_bremen_import_identity.py

# 8-9) Feature references in bridge
grep -R "BREMEN_FEATURE_COLUMNS\|BremenFeatureVector\|PreprocessingBridgeResult\|run_preprocessing_bridge\|validate_feature_schema" src/bremen/api tests 2>/dev/null || true
grep -R "sigma_l1\|sigma_l2\|Mahalanobis1\|Mahalanobis2\|wasserstein_distance_full_q2\|meanrms2\|weightedrms1" src/bremen/api tests 2>/dev/null || true

# 10) No inference/training/model loading in bridge
grep -R "predict_proba\|predict(\|model_loader\|load_model\|joblib.load\|bremen.training" src/bremen/api/preprocessing_bridge.py tests/test_bremen_preprocessing_bridge.py 2>/dev/null || true

# 11) Real-subset smoke opt-in
grep -R "BREMEN_H5_PREFLIGHT_SMOKE_PATH\|skipif\|real_subset" tests/test_bremen_preprocessing_bridge.py 2>/dev/null || true

# 12-13) No tracked artifacts
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) -not -path "./.git/*" -not -path "./venv/*" -print

# 14) No forbidden file changes
git diff --name-only -- docs/adr ROADMAP.md docs/architecture.md src/bremen/model_loader.py src/bremen/model_package.py src/bremen/training infra .github Dockerfile Dockerfile.training requirements.txt pyproject.toml

# 15) Full test suite
python -m pytest -q
```

## Rollback plan

1. **Revert `src/bremen/api/preprocessing_bridge.py`** — delete.
2. **Revert `tests/test_bremen_preprocessing_bridge.py`** — delete.
3. No other files affected.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `preprocessing_bridge.py` and its test file changed. |
| **Feature schema drift** | All 7 features in exact order. Feature_schema_version = "v0.1". 7 finite float values only. |
| **Runtime boundary drift** | No import from training. No model loading. No inference. No prediction route changes. |
| **Preflight integration drift** | Requires preflight passed. Fails closed if not. |
| **Test drift** | 12 synthetic + 1 optional real-subset smoke. Deterministic, repeatable. |
| **Validation drift** | All validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Feature schema cannot be made deterministic.
- Bridge requires inference/model loading.
- Bridge requires real H5 in CI.
- Bridge requires committing artifacts.
- Bridge requires training pipeline changes (the 6 private feature functions are duplicated, not imported).
- Bridge requires changing model package/runtime loader.
- Bridge requires changing prediction route behavior.
- Clinical or diagnostic claims are needed.
- Synthetic tests cannot cover the bridge contract.

## Follow-up PR 0039 summary

PR 0039 — Inference Integration / First Working Prediction:
- Wire preprocessing bridge → model loader → predict → post-processing.
- First working prediction using the v0.1 model package from PR 0036.
- No clinical validation claims.

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0038-preprocessing-bridge/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0038-preprocessing-bridge/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after precommit-review.

## Files read

- `.project-memory/project_contract.yml`
- `.project-memory/pr/0037-h5-preflight-gate/PLAN.md`
- `.project-memory/pr/0037-h5-preflight-gate/reviews/precommit-review.yml`
- `.project-memory/pr/0036-model-v01-package-publication/PLAN.md`
- `.project-memory/pr/0036-model-v01-package-publication/reviews/precommit-review.yml`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-two-image-build-training-pipeline-separation.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `src/bremen/api/preflight.py`
- `src/bremen/model_package.py`
- `src/bremen/model_loader.py`
- `src/bremen/config.py`
- `src/bremen/__main__.py`
- `src/bremen/api/` (all files)
- `src/bremen/training/` (all files)
- `src/bremen/pipelines.py`
- `tests/` (existing tests)
- `.gitignore`
- `requirements.txt`
- `pyproject.toml`

## Files written

- `.project-memory/pr/0038-preprocessing-bridge/PLAN.md` (this file)

## Files intentionally ignored

- All runtime source files not in allowed set.
- All training pipeline files (not imported by bridge).
- All docs, ADR, and roadmap files.
- Any H5/HDF5 or model artifact files.

## Boundary confirmations

- confirm: branch is `0038-preprocessing-bridge`: yes
- confirm: feature schema contract with exact order 7 families defined: yes
- confirm: bridge does NOT import from training: yes (feature functions duplicated)
- confirm: preflight integration requires passed status: yes
- confirm: no inference/model loading planned: yes
- confirm: no model package/runtime loader changes planned: yes
- confirm: no prediction route behavior changes planned: yes
- confirm: no clinical claims planned: yes
- confirm: no real H5 required in CI: yes
- confirm: bridge stops at feature table creation: yes
- confirm: no git mutation commands run: yes
