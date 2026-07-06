# PR 0039 — v0.1 Feature Schema Rebaseline and Inference Integration

Author: plan
Mode: planning only
Branch: 0039-inference-integration

## Objective

Deliver the first working Bremen prediction from H5 input to prediction JSON. Rebaseline the runtime preprocessing bridge from the old 7-feature assumption to the delivered v0.1 model's 15-column concrete schema. Add portable-logreg inference, startup model state, and API wiring. Transparently record the schema rebaseline in ROADMAP and a new ADR.

## Precondition verification

| Check | Result |
|-------|--------|
| `src/bremen/api/preflight.py` | Present ✅ |
| `src/bremen/api/preprocessing_bridge.py` | Present ✅ |
| `src/bremen/model_loader.py` | Present ✅ |
| `src/bremen/model_package.py` | Present ✅ |
| `src/bremen/api/app.py` | Present ✅ |
| `src/bremen/api/jobs.py` | Present ✅ |
| `src/bremen/inference.py` | NOT present — will be created |

## Delivered model facts

| Field | Value |
|-------|-------|
| Filename | `bremen_mri_triage_logreg_v0_1_model_package.joblib` |
| model_version | `bremen_mri_triage_logreg_v0_1` |
| SHA-256 | `sha256:8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` |
| Size | ~4 KB |
| S3 URI | `s3://matur-misc-uk/bremen/models/bremen-xrd-classifier/v0.1/bremen_mri_triage_logreg_v0_1_model_package.joblib` |
| Threshold | `0.3640352477169748` |
| threshold_version | `v0.1` |
| Internal format | `portable_logreg` — plain Python dict/list/float/string payload. No sklearn objects. |
| Train-all AUC | 0.646 |
| OOF AUC | 0.443 |
| Sensitivity at threshold | 0.966 |
| Specificity at threshold | 0.024 |

**Required statement**: This is a runnable research baseline for proving the end-to-end pipeline, not a clinically validated product model. The OOF AUC is weak and deployment goal is pipeline proof, not clinical validation.

## v0.1 schema rebaseline record

- **PR 0038** used a 7-feature bridge assumption (sigma_l1, sigma_l2, Mahalanobis1, Mahalanobis2, wasserstein_distance_full_q2, meanrms2, weightedrms1).
- **Delivered v0.1 model** uses 15 concrete feature columns in this exact order:
  1. `weightedrms1`
  2. `sigma_l1`
  3. `sigma_r1`
  4. `mahalanobis1`
  5. `weightedrms2`
  6. `sigma_l2`
  7. `sigma_r2`
  8. `mahalanobis2`
  9. `peak14_intensity`
  10. `mean_peak_value_raw`
  11. `wasserstein_distance_muLR`
  12. `cosine_distance_full_q2`
  13. `wasserstein_distance_full_q2`
  14. `meanrms1`
  15. `meanrms2`
- The delivered model package schema is the source of truth for runtime v0.1.
- PR 0039 must update preprocessing bridge to 15 columns before inference.
- Old 7-feature assumption is superseded for v0.1 runtime.
- This is a transparent schema rebaseline, not silent drift.
- Lowercase `mahalanobis1` and `mahalanobis2` (not capital-M as in earlier ADRs).

## Documentation plan

### `docs/adr/0010-v01-feature-schema-rebaseline.md`

**Status**: Accepted

Content:
- Delivered v0.1 model schema has 15 concrete columns (listed explicitly).
- Earlier ADRs and roadmap captured Bremen feature families and a 7-feature runtime assumption.
- Runtime v0.1 follows model package schema, not a pre-declared feature list.
- Model is a runnable research baseline, not clinically validated.
- OOF AUC 0.443 is weak and is NOT performance evidence.
- First deployment goal is end-to-end pipeline proof.
- Future model versions may have different feature schemas — the runtime shall follow the model package contract.
- This ADR does not change existing ADRs or roadmap identity anchors (ADR-0001 feature families remain Bremen's product identity; ADR-0010 records the v0.1 runtime implementation schema).

### `ROADMAP.md`

Add PR 0039 to Completed foundation PRs section:
```
- PR-0039 — v0.1 feature schema rebaseline + inference integration. ADR-0010 records the 7→15 schema rebaseline. First working prediction from H5 input. Portable logistic regression inference with 15-column schema. Weak AUC disclosed (OOF 0.443) — pipeline proof, not clinical validation.
```

## Feature schema contract

```python
BREMEN_V01_FEATURE_COLUMNS: tuple[str, ...] = (
    "weightedrms1",
    "sigma_l1",
    "sigma_r1",
    "mahalanobis1",
    "weightedrms2",
    "sigma_l2",
    "sigma_r2",
    "mahalanobis2",
    "peak14_intensity",
    "mean_peak_value_raw",
    "wasserstein_distance_muLR",
    "cosine_distance_full_q2",
    "wasserstein_distance_full_q2",
    "meanrms1",
    "meanrms2",
)
```

- Exact order, exact casing, lowercase `mahalanobis1/2`.
- `feature_schema_version = "v0.1"`.
- Output: 15 finite numeric float values.
- Fail closed on count mismatch, name mismatch, order mismatch, non-finite values.
- No raw arrays in output.

## Preprocessing bridge update

**File**: `src/bremen/api/preprocessing_bridge.py`

Replace `BREMEN_FEATURE_COLUMNS` (7 entries) with `BREMEN_V01_FEATURE_COLUMNS` (15 entries). Or keep the old constant and add the new one as `BREMEN_V01_FEATURE_COLUMNS` with a note that the old 7-feature assumption is superseded.

Update:
- The constant tuple.
- The internal feature extraction functions to compute all 15 columns.
- `validate_feature_schema()` to check against the new 15-column list.
- All tests referencing the old 7 features.

Some of the 15 columns were not in the original 7 families (e.g., `sigma_r1`, `sigma_r2`, `peak14_intensity`, `mean_peak_value_raw`, `wasserstein_distance_muLR`, `cosine_distance_full_q2`, `meanrms1`). The bridge must compute these new features from the same H5 profile data. Implementation details:
- `sigma_l2`, `meanrms2`, `weightedrms1`, `sigma_l1`, `wasserstein_distance_full_q2` — already have computation functions from PR 0038.
- `sigma_r1`/`sigma_r2` — sigma RMS with different normalisation (r instead of l).
- `mahalanobis1`/`mahalanobis2` — lowercase version of the existing Mahalanobis computation.
- `weightedrms2` — additional weighted RMS variant.
- `meanrms1` — additional mean RMS variant.
- `peak14_intensity` — intensity at a specific peak index (q=14 or equivalent index in the profile array).
- `mean_peak_value_raw` — mean of peak values in the raw profile.
- `wasserstein_distance_muLR` — muLR variant of Wasserstein distance.
- `cosine_distance_full_q2` — cosine distance between target/contralateral profiles.

**Important**: No runtime import of `bremen.training`. Feature computation functions remain duplicated in the bridge module.

## Portable inference plan

**File**: `src/bremen/inference.py` (NEW)

### Exception

```python
class PortableLogRegModelError(Exception):
    """Portable logistic regression model validation or inference error."""
```

### Validation function

```python
def validate_portable_logreg_model(package: dict) -> dict:
    """Validate the portable_logreg model package structure.
    
    Checks:
    - `portable_logreg` key present.
    - 15 `feature_columns` list matching BREMEN_V01_FEATURE_COLUMNS.
    - Numeric `imputer_statistics` (15 floats).
    - Numeric `scaler_mean` (15 floats).
    - Numeric `scaler_scale` (15 floats).
    - Numeric `coef` (15 floats).
    - Numeric `intercept` (float).
    - Numeric `threshold` (float).
    
    Returns validated package dict.
    Raises PortableLogRegModelError on any failure.
    """
```

### Prediction function

```python
def predict_proba_portable(
    package: dict,
    feature_vector: list[float],
) -> dict:
    """Run portable logistic regression inference.
    
    Steps:
    1. Validate package if not already validated.
    2. Impute NaN values using package['imputer_statistics'].
    3. Scale using (x - scaler_mean) / scaler_scale.
    4. Compute logit = dot(coef, scaled_features) + intercept.
    5. Compute sigmoid probability.
    6. Apply threshold.
    
    Returns a dict with:
    - probability: float in [0.0, 1.0]
    - prediction: int (0 or 1)
    - threshold_applied: float
    """
```

**No sklearn import.** Pure numpy/standard-library math only.

## Model loading / model state plan

**File**: `src/bremen/api/model_state.py` (NEW)

```python
class ModelState:
    """Startup model loading and state management.
    Loads model exactly once at startup. No per-request loading.
    """
    
    _instance: ModelState | None = None
    
    def __init__(self):
        self._model_package: dict | None = None
        self._model_version: str | None = None
        self._model_checksum: str | None = None
        self._loaded: bool = False
    
    @classmethod
    def load_at_startup(
        cls,
        model_uri: str | None = None,
        model_version: str | None = None,
        model_checksum: str | None = None,
    ) -> bool:
        """Load model package at startup.
        
        Reads BREMEN_MODEL_URI, BREMEN_MODEL_VERSION, BREMEN_MODEL_CHECKSUM
        from os.environ if not explicitly provided.
        
        For local/testing: supports file:// URI and plain filesystem paths.
        For S3: detects s3:// URI — a follow-up PR will implement S3 download.
        In this PR, S3 URIs will be recorded as a load failure with a clear
        message that local model file must be downloaded manually.
        
        Checksum verified before joblib.load().
        """
    
    @classmethod
    def get_model(cls) -> dict | None:
        """Get the loaded model package. Returns None if not loaded."""
    
    @classmethod
    def is_ready(cls) -> bool:
        """Returns True if model is loaded and ready for inference."""
    
    @classmethod
    def reset_for_tests(cls) -> None:
        """Reset singleton for isolated test execution."""
```

**S3 behavior decision for PR 0039**: S3 download is NOT implemented in this PR. The model URI is added to Terraform config, and when the service starts, if `BREMEN_MODEL_URI` starts with `s3://`, it logs a clear message and marks model not ready. A follow-up PR will add S3 download logic. Local testing uses `file://` URI or plain filesystem path.

## Inference handler plan

**File**: `src/bremen/api/inference_handler.py` (NEW)

```python
def run_inference(h5_path: str, patient_id: str) -> dict:
    """Run full inference pipeline from H5 path to prediction JSON.
    
    1. Call run_h5_preflight(h5_path).
    2. Require preflight passed.
    3. Call run_preprocessing_bridge(h5_path, skip_preflight=True).
    4. Validate bridge feature_schema_version matches model.
    5. Validate feature names match model feature_columns.
    6. Call predict_proba_portable(model, bridge.feature_vector.features).
    7. Assemble prediction JSON with all mandatory fields.
    """
```

**Mandatory prediction response fields:**

```python
{
    "prediction_id": str,
    "model_version": str,
    "model_checksum": str,
    "feature_schema_version": str,
    "threshold_version": str,
    "threshold_value": float,
    "qc_status": str,
    "qc_flags": list[str],
    "patient_id": str,
    "p_mri_needed": float,
    "triage_recommendation": str,  # "MRI_RECOMMENDED" or "MRI_RULE_OUT"
    "created_at_utc": str,
}
```

**Triage decision logic:**
- `p_mri_needed >= threshold → "MRI_RECOMMENDED"`
- `p_mri_needed < threshold → "MRI_RULE_OUT"`

## API app/jobs plan

**Files**: `src/bremen/api/app.py`, `src/bremen/api/jobs.py`

### App changes

- Call `ModelState.load_at_startup()` on module import (or in a startup function called by the server).
- `handle_health()` — add `"model_ready"` field to the response dict.
- `handle_model_version()` — return configured model version/checksum when model is loaded.
- `handle_submit_prediction()` — check `ModelState.is_ready()`. If not ready, return dict compatible with 503 behavior.
- `handle_get_prediction()` — return job status with result when complete.

### Job store changes

The existing `InMemoryJobStore` in `jobs.py` is suitable. No changes needed. For v0.1, synchronous job execution is acceptable — submit creates a job, immediately executes inference, updates status to completed, returns the job.

## Terraform/runtime value plan

**Files**: `infra/terraform/variables.tf` (optionally `outputs.tf`, `README.md`)

Update the existing variables' default values from empty strings to the real v0.1 values:

```hcl
variable "model_version" {
  default = "bremen_mri_triage_logreg_v0_1"
}

variable "model_uri" {
  default = "s3://matur-misc-uk/bremen/models/bremen-xrd-classifier/v0.1/bremen_mri_triage_logreg_v0_1_model_package.joblib"
}

variable "model_checksum" {
  default = "sha256:8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e"
}
```

Do NOT add secrets, AWS account IDs, registry URLs, or Terraform backend changes. The S3 URI is a public-accessible S3 path, not a secret.

## Test plan

### `tests/test_bremen_v01_schema_rebaseline.py`

1. `test_exact_15_feature_names_and_order` — `BREMEN_V01_FEATURE_COLUMNS` matches the exact delivered list.
2. `test_mahalanobis_is_lowercase` — Entries 4 and 8 are `mahalanobis1`, `mahalanobis2` (not `Mahalanobis`).
3. `test_old_7_feature_schema_rejected` — Old 7-column list fails validation.
4. `test_feature_schema_version_is_v0_1` — Version is `"v0.1"`.

### `tests/test_bremen_preprocessing_bridge.py` (updated)

- All existing tests updated to use 15-column schema.
- New test: bridge output has exactly 15 finite numeric values.
- New test: `sigma_r1`, `sigma_r2`, `peak14_intensity` etc. are present.

### `tests/test_bremen_inference_integration.py`

1. `test_synthetic_portable_logreg_returns_probability_in_range` — Create synthetic `portable_logreg` dict, run `predict_proba_portable()`, verify probability is `[0, 1]`.
2. `test_missing_portable_logreg_fails_closed` — Dict without `portable_logreg` key raises `PortableLogRegModelError`.
3. `test_wrong_feature_order_fails_closed` — Feature vector with wrong order raises error.
4. `test_no_sklearn_import` — Inference module does not import `sklearn`.
5. `test_end_to_end_synthetic_inference` — Create synthetic H5 + synthetic model, run `run_inference()`, verify all mandatory prediction fields.
6. `test_post_predictions_returns_job_id` — HTTP test (using `test_bremen_api_server.py` pattern), verify 202 with `job_id`.
7. `test_get_prediction_returns_result` — Submit then poll, verify result has all mandatory fields.
8. `test_503_when_model_not_loaded` — Submit prediction when model not ready, verify 503.
9. `test_health_reports_model_ready` — `/health` includes `model_ready: bool`.
10. `test_local_file_model_loading_works` — Create synthetic model joblib + manifest, verify `ModelState.load_at_startup()` loads it.
11. `test_no_aws_credentials_required` — Verify inference tests pass without real AWS credentials.
12. `test_real_model_smoke_opt_in` — Skipped unless `BREMEN_V01_JOBLIB_PATH` is set. Runs inference with real model on synthetic H5.

## Allowed implementation files

1. `ROADMAP.md` — MODIFY
2. `docs/adr/0010-v01-feature-schema-rebaseline.md` — NEW
3. `src/bremen/api/preprocessing_bridge.py` — MODIFY (update to 15 columns)
4. `src/bremen/inference.py` — NEW (portable logreg inference)
5. `src/bremen/api/model_state.py` — NEW (startup model loading)
6. `src/bremen/api/inference_handler.py` — NEW (wires preflight + bridge + inference)
7. `src/bremen/api/app.py` — MODIFY (wire model readiness, prediction submission)
8. `tests/test_bremen_v01_schema_rebaseline.py` — NEW
9. `tests/test_bremen_inference_integration.py` — NEW
10. `tests/test_bremen_preprocessing_bridge.py` — MODIFY (update for 15 columns)
11. `tests/test_bremen_api_skeleton.py` — MODIFY (model_state integration)
12. `infra/terraform/variables.tf` — MODIFY (real v0.1 model values)

## Forbidden files

- Any real `*.joblib`, `*.pkl`, `*.npy`, `*.npz`, `*.h5`, `*.hdf5`
- `src/bremen/training/**`
- Existing ADR files 0001–0009 (read-only)
- `docs/architecture.md` unless explicitly justified (not needed for this PR)
- `.project-memory/project_contract.yml`
- `.github/**`, Dockerfiles
- `requirements.txt`, `pyproject.toml`
- `.gitignore`
- Secrets, account IDs, access keys, registry URLs

## Safety/claims

- No diagnosis claim.
- No clinical validation claim.
- No claim that model replaces MRI, biopsy, radiologist, or clinician.
- Weak OOF AUC (0.443) is disclosed and deployment goal is pipeline proof, not clinical validation.
- The triage recommendation output (`MRI_RECOMMENDED` / `MRI_RULE_OUT`) is a decision-support label, not a clinical order.
- Passing preflight means structural H5 acceptance only, not clinical suitability.

## Validation checklist

```bash
# 1-3) Baseline
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Compile check
python -m compileall src tests

# 5-11) Test suites
python -m pytest -q tests/test_bremen_v01_schema_rebaseline.py
python -m pytest -q tests/test_bremen_preprocessing_bridge.py
python -m pytest -q tests/test_bremen_inference_integration.py
python -m pytest -q tests/test_bremen_h5_preflight.py
python -m pytest -q tests/test_bremen_import_identity.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q

# 12) 15-column feature references in source
grep -R "weightedrms1\|sigma_l1\|sigma_r1\|mahalanobis1\|weightedrms2\|sigma_l2\|sigma_r2\|mahalanobis2\|peak14_intensity\|mean_peak_value_raw\|wasserstein_distance_muLR\|cosine_distance_full_q2\|wasserstein_distance_full_q2\|meanrms1\|meanrms2" src/bremen tests docs/adr ROADMAP.md 2>/dev/null || true

# 13) Mandatory prediction response fields
grep -R "prediction_id\|model_version\|model_checksum\|feature_schema_version\|threshold_version\|threshold_value\|qc_status\|qc_flags\|patient_id\|p_mri_needed\|triage_recommendation\|created_at_utc" src/bremen/api tests 2>/dev/null || true

# 14) Terraform model values
grep -R "BREMEN_MODEL_VERSION\|BREMEN_MODEL_URI\|BREMEN_MODEL_CHECKSUM\|bremen_mri_triage_logreg_v0_1\|8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e" infra src tests docs 2>/dev/null || true

# 15) No sklearn in inference
grep -R "from sklearn\|import sklearn\|fit(\|fit_transform\|bremen.training" src/bremen/api src/bremen/inference.py tests/test_bremen_inference_integration.py 2>/dev/null || true

# 16) No local paths or secrets
grep -R "/Users/\|AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|aws_secret_access_key\|[0-9]\{12\}\.dkr\.ecr" src tests docs infra .github 2>/dev/null || true

# 17-18) No tracked artifacts
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) -not -path "./.git/*" -not -path "./venv/*" -print

# 19) No forbidden file changes
git diff --name-only -- src/bremen/training .github Dockerfile Dockerfile.training requirements.txt pyproject.toml .project-memory/project_contract.yml
```

## Rollback plan

1. **Revert the PR 0039 commit** — service returns to PR 0038 state (preflight + preprocessing bridge only).
2. No model artifacts removed from S3 by code.
3. Terraform real model values can be reverted to previous empty-string placeholders if needed.

## Follow-up PRs

- **S3 download implementation** — Wire real S3 download for `s3://` URIs in model loading.
- **Matador integration** — Record results in Matador as system of record.
- **Clinical/report contract** — Decision-support report formatting.
- **Async job queue** — Separate queue for long-running inference if needed.
- **Shared feature module extraction** — After full pipeline works, consider extracting runtime-safe shared feature functions.
- **Model v1.0 retraining** — Stronger validation, improved AUC.

## Implementation agent assignment

- **Agent**: coder
- **Mode**: implementation

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0039-inference-integration/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0039-inference-integration/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after precommit-review.

## Files read

- `.project-memory/project_contract.yml`
- `.project-memory/pr/0036-model-v01-package-publication/PLAN.md`
- `.project-memory/pr/0036-model-v01-package-publication/reviews/precommit-review.yml`
- `.project-memory/pr/0037-h5-preflight-gate/PLAN.md`
- `.project-memory/pr/0037-h5-preflight-gate/reviews/precommit-review.yml`
- `.project-memory/pr/0038-preprocessing-bridge/PLAN.md`
- `.project-memory/pr/0038-preprocessing-bridge/reviews/precommit-review.yml`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-two-image-build-training-pipeline-separation.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `src/bremen/api/app.py`
- `src/bremen/api/preflight.py`
- `src/bremen/api/preprocessing_bridge.py`
- `src/bremen/api/jobs.py`
- `src/bremen/model_loader.py`
- `src/bremen/model_package.py`
- `src/bremen/config.py`
- `src/bremen/api/` (all files)
- `infra/terraform/variables.tf`
- `infra/terraform/ecs.tf`
- `infra/terraform/apprunner.tf`
- `infra/terraform/outputs.tf`
- `.gitignore`
- `requirements.txt`
- `pyproject.toml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0039-inference-integration/PLAN.md` (this file)

## Files intentionally ignored

- All training pipeline files (not imported by runtime).
- All ADRs 0001–0009 (read-only, not modified).
- Architecture docs (not modified by default).
- Any real H5 or model artifact files.

## Boundary confirmations

- confirm: branch confirmed as `0039-inference-integration`: yes
- confirm: 7→15 schema rebaseline transparently documented: yes
- confirm: preprocessing bridge updated to 15 columns: yes
- confirm: portable-logreg inference (no sklearn, no training): yes
- confirm: model startup loading with checksum verification: yes
- confirm: S3 download NOT implemented in this PR (requires follow-up): yes
- confirm: mandatory prediction response fields all listed: yes
- confirm: triage recommendation logic defined: yes
- confirm: 503 model-not-ready behavior planned: yes
- confirm: Terraform values updated to real v0.1 values: yes
- confirm: weak AUC disclosed, no clinical validation claims: yes
- confirm: no real model artifact committed: yes
- confirm: no git mutation commands run: yes
