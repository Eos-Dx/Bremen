# PR 0034 — Plan Bremen Training Pipeline Implementation

Author: plan
Mode: planning only
Branch: 0034-bremen-training-pipeline-implementation

## Objective

Implement the first complete Bremen training pipeline slice, reaching and improving on reference-level training maturity without weakening Bremen safety boundaries. This PR creates the offline training package, training config, feature computation for all 7 Bremen feature families, Dockerfile.training, CI two-image build, Terraform second ECR repository, and focused tests — all using synthetic data only, no real H5, no model artifacts, no inference integration.

## Catch-up implementation strategy

Bremen is in catch-up mode. The strategy is executable-first, Bremen-specific:
- Implement the training pipeline from ADR-0008 without guessing — the ADR specifies every component, field, and function.
- No real training data accessed in this PR — all tests use synthetic dataframes.
- No model artifacts checked into the repository.
- Runtime/training separation is structurally enforced by directory boundaries and verified by tests.
- CI two-image build is added alongside existing runtime build, preserving existing behavior.
- Terraform training ECR is added alongside existing runtime ECR.

## Required reads — observed facts

### ADR-0008 (PR 0033, present)
- 6 binding decisions: training/runtime separation, two images, artifact dict (21 fields), config YAML, Kubernetes Job trigger, PR 0034 implementation scope (19+ components).
- Feature computation confirmation: Mahalanobis/Wasserstein = per-patient symmetry, NOT population-fitted.
- Repository structure diagram and Implementation Notes table.

### Dependency baseline
- `pyproject.toml` core: numpy, pandas, scikit-learn, joblib, h5py, pyarrow, pyyaml, mlflow.
- `pyproject.toml` dev: pytest, pytest-cov, ruff, marimo.
- `requirements.txt` adds: scipy, lightgbm, pyFAI, fabio, matplotlib, opencv-python-headless, scikit-image, markdown-it-py, fastjsonschema, jsonschema, tqdm, container.
- **scipy is in `requirements.txt` but NOT in `pyproject.toml`**. Dockerfile.training must use `pip install -e . && pip install -r requirements.txt` or similar.
- All training dependencies already exist in either pyproject.toml or requirements.txt. No new external packages needed.

### CI baseline (ecr-publish.yml)
- Single `publish` job building runtime image with `github.sha`, `app-runner`, `latest` tags.
- Auth: static IAM user credentials via secrets.
- Trigger: workflow_dispatch + push to main (no pull_request).
- Workflow test exists at `tests/test_bremen_ecr_publish_workflow.py`.

### Terraform baseline
- Single ECR repository `aws_ecr_repository.bremen` from `var.ecr_repository_name` (default `"bremen"`).
- Variables, outputs, and README documentation all reference one ECR repo.
- App Runner Terraform exists at `infra/terraform/apprunner.tf`.

### ECR workflow test baseline
- `tests/test_bremen_ecr_publish_workflow.py` — 13+ assertions on workflow YAML.
- Tests check for: triggers, permissions, credentials, tags (`:latest`, `:app-runner`, `github.sha`), forbidden patterns (no Terraform, no ECS deploy, no hardcoded keys).
- Must be updated if workflow structure changes significantly.

### Training/runtime separation
- `src/bremen/training/` does not exist yet — must be created.
- `src/bremen/api/` and runtime modules are the existing boundary — must remain training-free.
- `Dockerfile` (runtime) exists — must not be modified.
- `Dockerfile.training` does not exist — must be created.

## Allowed implementation files

The coder may create or modify these files:

### Source
1. `src/bremen/training/__init__.py` — NEW
2. `src/bremen/training/pipeline.py` — NEW (training pipeline with feature computation, artifact assembly, model training)
3. `src/bremen/training/train_classifier.py` — NEW (CLI entrypoint)

### Config
4. `config/training/bremen_v0_1_train.yaml` — NEW (example training config)

### Docker
5. `Dockerfile.training` — NEW (training-only image)

### CI
6. `.github/workflows/ecr-publish.yml` — MODIFY (add training image build/push)

### Terraform
7. `infra/terraform/ecr.tf` — MODIFY (add `bremen-training` ECR repository)
8. `infra/terraform/variables.tf` — MODIFY (add training ECR repository variable)
9. `infra/terraform/outputs.tf` — MODIFY (add training ECR output)

### Tests
10. `tests/test_bremen_training_config.py` — NEW
11. `tests/test_bremen_training_features.py` — NEW
12. `tests/test_bremen_training_artifact.py` — NEW
13. `tests/test_bremen_training_runtime_separation.py` — NEW
14. `tests/test_bremen_ecr_publish_workflow.py` — MODIFY (add training image assertions)

### Review
15. `.project-memory/pr/0034-bremen-training-pipeline-implementation/reviews/precommit-review.yml` (later)

## Forbidden files

- `ROADMAP.md`, `docs/**`, `docs/adr/**`, `.project-memory/project_contract.yml`
- `src/bremen/api/**`, `src/bremen/model_loader.py`, `src/bremen/__main__.py`, `src/bremen/__init__.py`, `src/bremen/config.py`, `src/bremen/model_package.py`
- `Dockerfile` (runtime, unchanged)
- `.github/workflows/quality.yml`, unrelated `.github/**`
- Unrelated `infra/**`
- `examples/**`, `agents/**`, `README.md`
- Any H5/HDF5 files
- Any joblib/pkl/npy/npz artifacts
- Secrets, AWS account IDs, account-specific registry URLs, access keys, secret keys, secret values

## Implementation scope

### 1. `src/bremen/training/__init__.py`

Package init. Empty or contains a version marker. Must not import heavy modules at package level.

### 2. `src/bremen/training/pipeline.py` — Training pipeline

Implement all components specified in ADR-0008 Decision 6. The module must contain:

**Constants**:
- `REQUIRED_TRAINING_ARTIFACT_FIELDS` — tuple/list of field names matching ADR-0008 artifact dict
- `REQUIRED_TRAINING_CONFIG_SECTIONS` — tuple of ['training', 'io', 'model', 'evaluation']
- `REQUIRED_TRAINING_CONFIG_FIELDS` — dict mapping section → required field list (26 fields total)
- `BREMEN_FEATURE_FAMILIES` — tuple of 7 family names: sigma_l1, sigma_l2, Mahalanobis1, Mahalanobis2, wasserstein_distance_full_q2, meanrms2, weightedrms1

**Classes**:
- `PatientModelInputBuilder` — Accept preprocessed dataframe, validate columns match config, enforce MRI-referred cohort filter (via `lr1_row_policy`).
- `BremenPatientTrainingPipeline` — Assemble input builder + trainers + evaluators.
- `PatientModelSetTrainer` — Train M0/M1/M2 models, enforce patient-safe splits.
- `PatientModelSetEvaluator` — Compute metrics, generate split predictions.

**Core functions**:
- `build_patient_training_pipeline(config: dict) -> BremenPatientTrainingPipeline`
- `run_training_from_config(config_path: str | Path) -> dict` — Parse config YAML, run pipeline, assemble artifact
- `train_patient_m0_m1_m2_model_artifact(config_path: str | Path) -> dict` — Called by CLI entrypoint

**Private helpers**:
- `_patient_training_artifact(...)` — Assemble the 21-field artifact dict
- `_validate_training_config(config: dict) -> None` — Validate sections and fields present
- `_patient_feature_table(df, config) -> pd.DataFrame` — Build patient-level feature table
- `_sk_target_contralateral_symmetry_features(df, config) -> pd.DataFrame` — Compute all 7 families
- `_sk_side_mean_metrics(df, config) -> dict` — Aggregate per-side profile means for target/contralateral
- `_mahalanobis_difference(target_profile, contralateral_profile) -> float` — Per-patient symmetry measure
- `_profile_wasserstein(target_profile, contralateral_profile) -> float` — Profile distribution distance
- `_rms_difference(target_profile, contralateral_profile) -> float` — RMS asymmetry (meanrms2)
- `_weighted_rms_difference(target_profile, contralateral_profile) -> float` — Weighted RMS (weightedrms1)
- `_sigma_rms(target_profile, contralateral_profile) -> float` — Sigma RMS (sigma_l1, sigma_l2)
- `_file_sha256(path: str | Path) -> str` — SHA-256 hex digest
- `_config_path(path: str | Path | None) -> Path` — Resolve config path
- `_optional_config_path(path: str | Path | None) -> Path | None` — Resolve optional config reference

**Key implementation rules**:
- Mahalanobis and Wasserstein are per-patient symmetry measures (target vs contralateral breast of same patient).
- They are NOT population-fitted reference statistics.
- `_mahalanobis_difference` computes target-vs-contralateral profile difference normalized by per-patient measurement variance.
- `_profile_wasserstein` computes distance between normalized target and contralateral profile distributions for same patient.
- Patient-safe splits: all measurements from one patient must stay in either train or test (not both).
- `joblib.dump()` is allowed here (offline training).
- No `joblib.load()` from runtime-controlled model packages.
- The module may import sklearn, scipy, pandas, numpy, yaml, joblib, hashlib.

### 3. `src/bremen/training/train_classifier.py` — CLI entrypoint

```python
"""Bremen training pipeline CLI entrypoint.

Usage:
    python -m bremen.training.train_classifier --config <training.yaml>

This module is offline-only. Never imported by runtime API or service code.
"""

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bremen-training")
    parser.add_argument("--config", required=True, type=Path, help="Path to training config YAML")
    args = parser.parse_args(argv)

    from .pipeline import run_training_from_config  # noqa: PLC0415

    try:
        artifact = run_training_from_config(args.config)
    except Exception as exc:
        print(f"Training failed: {exc}", file=sys.stderr)
        return 1

    print(f"Training complete. Artifact kind: {artifact.get('kind')}")
    print(f"Model version: {artifact.get('version')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 4. `config/training/bremen_v0_1_train.yaml` — Example training config

Create with all required sections and fields. Bremen-specific settings:
- `training.clinical_stage: "development"`, `training.intended_use: "Bremen healthy vs disease classification"`
- `model.lr1_row_policy: "mri_referred_only"`
- `evaluation.target_sensitivity: 0.85` (planning target, not clinical claim)
- All section/field structures as defined in ADR-0008 Decision 4.

A comment header must explain: "Bremen training config — Healthy vs disease classification (NORMAL vs BENIGN+CANCER), MRI-referred population."

### 5. `Dockerfile.training` — Training image

```dockerfile
# Bremen Training Image — offline ML model training only.
# NOT part of the runtime inference service.
# See ADR-0008 for the two-image build strategy.

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies required by scipy/numpy/scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml requirements.txt ./

# Install all dependencies (runtime + training)
RUN pip install --no-cache-dir -e ".[dev]" && \
    pip install --no-cache-dir -r requirements.txt

# Copy training package and supporting modules
COPY src/bremen/ src/bremen/

# Copy training config
COPY config/training/ config/training/

# Entrypoint: python -m bremen.training.train_classifier
ENTRYPOINT ["python", "-m", "bremen.training.train_classifier"]
```

**Rules**:
- Installs everything via `pip install -e ".[dev]"` + `-r requirements.txt` (same as CI).
- Copies only what training needs. Runtime configs (`config/preprocessing/`) are not needed.
- Does NOT copy runtime-only assets like `infra/`, `.github/`, `tests/`.
- Does NOT bake model artifacts, H5 data, credentials, or secrets.
- `ENTRYPOINT` is the training CLI — runtime Dockerfile stays separate.
- No `CMD` override needed — `ENTRYPOINT` handles default.

### 6. `.github/workflows/ecr-publish.yml` — CI two-image build

Add a second job `publish-training` that runs after the existing `publish` job (or in parallel):

```yaml
  publish-training:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    needs: publish
    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Log in to Amazon ECR
        id: login-ecr-training
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push training image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr-training.outputs.registry }}
          ECR_REPOSITORY: bremen-training
          IMAGE_TAG: ${{ github.sha }}
        run: |
          IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}"

          docker build \
            -f Dockerfile.training \
            -t "${IMAGE_URI}:${IMAGE_TAG}" \
            -t "${IMAGE_URI}:latest" \
            .

          docker push "${IMAGE_URI}:${IMAGE_TAG}"
          docker push "${IMAGE_URI}:latest"
```

**Design decisions**:
- Uses `-f Dockerfile.training` to specify training Dockerfile (existing `publish` job uses default `Dockerfile`).
- ECR repository name is hardcoded as `bremen-training` in this job (separate from `${{ vars.ECR_REPOSITORY }}`).
- The first job uses build arg for `BREMEN_CI_GITHUB_TOKEN` — training image also needs this if it accesses private deps at build time. The same `BREMEN_CI_GITHUB_TOKEN` secret is available.
- No `app-runner` tag for training image (App Runner is runtime-only).
- Triggered only on `push` to `main` (same as runtime image).

### 7. Terraform — `infra/terraform/ecr.tf`, `variables.tf`, `outputs.tf`

**`infra/terraform/variables.tf`** — add:

```hcl
variable "training_ecr_repository_name" {
  description = "ECR repository name for the Bremen training image."
  type        = string
  default     = "bremen-training"
}
```

**`infra/terraform/ecr.tf`** — add:

```hcl
resource "aws_ecr_repository" "bremen_training" {
  name                 = var.training_ecr_repository_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}
```

**`infra/terraform/outputs.tf`** — add:

```hcl
output "training_ecr_repository_url" {
  description = "URL of the training ECR repository."
  value       = aws_ecr_repository.bremen_training.repository_url
}

output "training_ecr_repository_arn" {
  description = "ARN of the training ECR repository."
  value       = aws_ecr_repository.bremen_training.arn
}
```

**No README update needed** unless the coder finds the existing README would be misleading without it (add a row to the resource summary table).

## Artifact dict plan

The training artifact dict (`_patient_training_artifact`) must assemble all 21 required fields. Key implementation decisions:

| Field | Source |
|-------|--------|
| `kind` | `"bremen_training_artifact"` (constant) |
| `version` | Config `training.version` |
| `created_at` | `datetime.utcnow().isoformat()` |
| `model_type` | `"patient_m0_m1_m2_logistic_set"` |
| `models` | Trained model dict from `PatientModelSetTrainer` |
| `thresholds` | Calibrated thresholds per model |
| `model_descriptions` | Metadata from training config |
| `feature_schema` | Feature names and types from pipeline |
| `warnings` | Warnings collected during training |
| `training_config` | `dict(config)` — full parsed config |
| `training_config_yaml` | Raw YAML string from config file |
| `training_config_text` | Same raw text (compatibility) |
| `training_config_sha256` | `hashlib.sha256(raw_text.encode()).hexdigest()` |
| `input_dataframe_joblib_sha256` | SHA-256 of input dataframe file |
| `dataset_summary` | Patient counts, class distribution, split info |
| `feature_table` | Patient-level feature dataframe (serialized to dict) |
| `metric_summary` | AUC, sensitivity, specificity, balanced accuracy, PPV, NPV per model |
| `split_metrics` | All CV/split results |
| `split_predictions` | Per-split prediction audit table |
| `preprocessing_lineage` | Preprocessing config/artifact provenance |
| `metadata` | `{"bremen_version": ..., "git_sha": ..., "created_at": ..., "branch": ..., "training_role": ...}` |

**Enforcement**: The artifact assembly function must validate that all required fields are present before returning. Missing fields raise a controlled error.

## Training config plan

`config/training/bremen_v0_1_train.yaml` structure:

```yaml
# Bremen training config — Healthy vs disease classification (NORMAL vs BENIGN+CANCER)
# Cohort: MRI-referred population
# See ADR-0008 for full config specification

training:
  name: "bremen_v0_1"
  version: "0.1.0"
  branch: "main"
  clinical_stage: "development"
  intended_use: "Bremen healthy vs disease classification (NORMAL vs BENIGN+CANCER)"
  role: "training"

io:
  input_dataframe_joblib_path: "data/bremen_training_data.joblib"
  output_model_joblib_path: "models/bremen_v0_1.joblib"
  output_json_path: "models/bremen_v0_1_metrics.json"
  output_yaml_path: "models/bremen_v0_1_qc.yaml"

model:
  type: "patient_m0_m1_m2_logistic_set"
  profile_column: "profile"
  label_column: "label"
  group_column: "patient_id"
  specimen_column: "specimen_id"
  side_column: "breast_side"
  q_column: "measurement_q"
  age_column: "age"
  lr1_row_policy: "mri_referred_only"
  selected_models: ["M0", "M1", "M2"]
  logreg_c: 0.1

evaluation:
  mode: "cross_validation"
  n_splits: 5
  test_size: 0.2
  random_state: 42
  target_sensitivity: 0.85
```

## Feature computation plan

All 7 feature families are per-patient symmetry measures computed from target vs contralateral breast side profiles for the same patient.

| Family | Function | Computation |
|--------|----------|-------------|
| `sigma_l1` | `_sigma_rms` | L1-norm sigma RMS of target/contralateral profile difference |
| `sigma_l2` | `_sigma_rms` | L2-norm sigma RMS of target/contralateral profile difference |
| `Mahalanobis1` | `_mahalanobis_difference` | Target-vs-contralateral profile difference normalized by per-patient measurement variance |
| `Mahalanobis2` | `_mahalanobis_difference` | Same as M1 with alternative normalization parameter |
| `wasserstein_distance_full_q2` | `_profile_wasserstein` | Wasserstein-1 distance between normalized target and contralateral profile distributions |
| `meanrms2` | `_rms_difference` | Root-mean-square of target/contralateral profile difference |
| `weightedrms1` | `_weighted_rms_difference` | Weighted RMS of target/contralateral profile difference with profile-intensity weighting |

**Synthetic data design**: Tests create a `pandas.DataFrame` with columns `patient_id`, `breast_side` (`T`/`C`), `label` (`NORMAL`/`BENIGN`), and synthetic profile columns. No H5 files, no real data, no uploaded fixtures.

## Patient-safe split plan

- Patient-safe splits are enforced at the `PatientModelSetTrainer` level.
- `GroupKFold` or `GroupShuffleSplit` from sklearn is used.
- `model.group_column` config value specifies the patient identifier column.
- A direct test verifies that no patient ID appears in both train and test sets for any split.
- Split assignments are deterministic via `evaluation.random_state`.

## Dependency plan

**Decision: No change to `pyproject.toml` or `requirements.txt`** for training dependencies.

Rationale:
- `pyproject.toml` already has: numpy, pandas, scikit-learn, joblib, pyyaml, mlflow.
- `requirements.txt` adds: scipy (needed by scikit-learn and wasserstein distance).
- The training Dockerfile.training installs via `pip install -e ".[dev]" && pip install -r requirements.txt`, which covers all needed packages.
- The runtime Dockerfile uses `pip install -e .` which installs core dependencies only.
- If a training-only dependency is later identified that is NOT in either file, it must be added to `requirements.txt` (not pyproject.toml) with justification. This is not expected for PR 0034.

## Test plan

### `tests/test_bremen_training_config.py`
- `test_config_accepts_example` — Load `config/training/bremen_v0_1_train.yaml`, verify `_validate_training_config` passes.
- `test_config_rejects_missing_section` — Config missing `training` section raises error.
- `test_config_rejects_missing_field` — Config missing `training.name` raises error.
- `test_config_has_bremen_cohort_naming` — `lr1_row_policy` is `"mri_referred_only"`.

### `tests/test_bremen_training_features.py`
- `test_all_7_feature_families_in_table` — Feature table columns include all 7 family names.
- `test_mahalanobis_is_per_patient_symmetry` — Target and contralateral profiles from same patient produce finite Mahalanobis distance.
- `test_wasserstein_is_per_patient_symmetry` — Target and contralateral profiles from same patient produce finite Wasserstein distance.
- `test_missing_contralateral_safe_fallback` — Rows without contralateral side produce safe finite fallback (NaN, 0, or explicit warning, per implementation design).
- `test_features_deterministic` — Same input produces same feature values.
- `test_sigma_l1_l2_produced` — Both sigma_rms variants appear in feature table.

### `tests/test_bremen_training_artifact.py`
- `test_artifact_has_all_21_required_fields` — Artifact dict keys match `REQUIRED_TRAINING_ARTIFACT_FIELDS`.
- `test_artifact_kind_is_bremen_training_artifact` — `artifact["kind"] == "bremen_training_artifact"`.
- `test_artifact_has_required_semantic_fields` — `metadata` contains `bremen_version`, `git_sha`, `created_at`, `branch`, `training_role`.
- `test_artifact_hashes_are_deterministic` — SHA-256 of same config text produces same hash.
- `test_artifact_has_model_version_not_runtime` — `model_version` in artifact is training version, not runtime `bremen.joblib.model_package`.
- `test_artifact_does_not_rename_adr_0007_fields` — `model_version`, `model_checksum`, `feature_schema_version` are present but not renamed.

### `tests/test_bremen_training_runtime_separation.py`
- `test_runtime_does_not_import_training` — Import all runtime modules (`api/`, `model_loader.py`, `config.py`, `model_package.py`, `__main__.py`), verify `bremen.training` is NOT in `sys.modules`.
- `test_runtime_dockerfile_does_not_mention_training` — `Dockerfile` contains no reference to `training/`, `Dockerfile.training`, or `train_classifier`.
- `test_training_cli_help_works` — `python -m bremen.training.train_classifier --help` exits 0.
- `test_runtime_cli_does_not_show_training` — `python -m bremen --help` does NOT show training-related commands.

### `tests/test_bremen_ecr_publish_workflow.py` (MODIFY)
- Add `test_workflow_publishes_training_image` — asserts `publish-training` job exists, uses `Dockerfile.training`, pushes to `bremen-training` repo with `github.sha` and `latest` tags.
- Add `test_training_image_does_not_use_app_runner_tag` — asserts `app-runner` tag is NOT applied to training image.

## Runtime separation enforcement

| Layer | Guard |
|-------|-------|
| Directory boundary | `src/bremen/training/` is a separate package. Runtime module imports from `bremen.training` would need an explicit import path. |
| Import test | `test_bremen_training_runtime_separation.py` verifies no implicit/transitive import. |
| Docker separation | Runtime `Dockerfile` unchanged. `Dockerfile.training` separate. |
| CLI separation | `python -m bremen` shows runtime CLI only. `python -m bremen.training.train_classifier` is the training CLI. |
| CI separation | Two separate workflow jobs, two ECR repositories. |
| Terraform separation | Two separate ECR repository resources. |

## Non-goals

- No real H5/data access.
- No model artifacts checked into repository.
- No inference integration.
- No runtime import of training.
- No change to runtime `Dockerfile`.
- No change to `pyproject.toml` or `requirements.txt` (unless a missing training dependency is identified).
- No change to `.github/workflows/quality.yml`.
- No change to `ROADMAP.md`, `docs/`, `docs/adr/`, `.project-memory/project_contract.yml`.
- No clinical validation or performance claims.
- No claiming training has been run.
- No claiming clinical validation metrics.

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5) Compile check
python -m compileall src tests

# 6-9) Training tests
python -m pytest -q tests/test_bremen_training_config.py
python -m pytest -q tests/test_bremen_training_features.py
python -m pytest -q tests/test_bremen_training_artifact.py
python -m pytest -q tests/test_bremen_training_runtime_separation.py

# 10) Training CLI help works
python -m bremen.training.train_classifier --help

# 11-12) Training source references
grep -R "bremen_training_artifact\|BREMEN_FEATURE_FAMILIES\|PatientModelInputBuilder\|BremenPatientTrainingPipeline\|run_training_from_config" src/bremen/training tests config/training Dockerfile.training

# 13) Feature family references in training code
grep -R "sigma_l1\|sigma_l2\|Mahalanobis1\|Mahalanobis2\|wasserstein_distance_full_q2\|meanrms2\|weightedrms1" src/bremen/training tests config/training

# 14) Runtime does NOT import training
grep -R "bremen.training" src/bremen/api src/bremen/model_loader.py src/bremen/__main__.py || true

# 15) joblib.dump is offline-only (only in training/)
grep -R "joblib.dump" src/bremen tests | grep -v "src/bremen/training" || true

# 16) No secrets/account IDs in changed files
grep -R "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|aws_secret_access_key\|account ID\|registry URL\|[0-9]\{12\}\.dkr\.ecr" .github infra Dockerfile.training src/bremen/training config/training tests || true

# 17) Full test suite
python -m pytest -q
```

## Rollback plan

If the training pipeline implementation causes issues:
1. **Delete `src/bremen/training/`** — remove the entire training package.
2. **Delete `config/training/`** — remove training config directory.
3. **Delete `Dockerfile.training`** — remove training image.
4. **Revert `.github/workflows/ecr-publish.yml`** — remove training image job.
5. **Revert Terraform files** — remove training ECR repository and outputs.
6. **Delete test files** — remove all 4 new test files.
7. **Revert `tests/test_bremen_ecr_publish_workflow.py`** — remove training assertions.

No runtime files affected (runtime `Dockerfile`, `src/bremen/api/`, `model_loader.py`, etc. are untouched).

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only allowed files changed. No forbidden files. |
| **Training package drift** | Contains all 19+ specified functions/classes. No runtime imports. |
| **Artifact dict drift** | All 21 fields present. `kind == "bremen_training_artifact"`. ADR-0007 fields not renamed. |
| **Config drift** | All 4 sections and 26 fields present. Bremen-specific adaptations. |
| **Feature computation drift** | All 7 families implemented as per-patient symmetry measures. No population-fitted statistics. |
| **Patient-safe drift** | Group-level splits. Test verifies no leakage. |
| **Docker drift** | `Dockerfile.training` training-only. `Dockerfile` unchanged. |
| **CI drift** | Training image job added. Runtime image job preserved. |
| **Terraform drift** | Training ECR repo added. Runtime ECR repo preserved. |
| **Dependency drift** | No new packages needed. pyproject.toml and requirements.txt unchanged. |
| **Runtime safety drift** | Import test, Docker separation, CLI separation. |
| **Test drift** | 15+ focused test scenarios across 5 test files. Synthetic data only. |
| **Validation drift** | All validation checks pass. No secrets/account IDs. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- ADR-0008 is missing (PR 0033 not present on main).
- Implementation requires real H5/data access.
- Implementation requires actual training run.
- Implementation requires inference integration.
- Implementation requires runtime to import training.
- Implementation requires model artifacts checked into repo.
- Implementation requires hardcoded secrets/account IDs/registry URLs.
- Implementation requires changing runtime Dockerfile.
- Dependency changes cannot be justified (existing deps cover training needs).
- Artifact dict cannot be produced with exact required 21 fields.
- Patient-safe split cannot be tested with synthetic data.

## Follow-up PR 0035 summary

PR 0035 (tentative) — First controlled training run and model package publication:
- Run training on approved Bremen/Nova study data.
- Publish `bremen_v0_1.joblib` to S3 model store.
- Create/verify manifest with `model_checksum` and `feature_schema_version`.
- Verify `model_package.py` can validate package.
- Update configured `BREMEN_MODEL_VERSION` through approved model release process.

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0034-bremen-training-pipeline-implementation/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0034-bremen-training-pipeline-implementation/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Files read

- `.project-memory/pr/0033-adr-training-pipeline-separation/PLAN.md`
- `.project-memory/pr/0033-adr-training-pipeline-separation/reviews/precommit-review.yml`
- `docs/adr/0008-two-image-build-training-pipeline-separation.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `.project-memory/project_contract.yml`
- `src/bremen/model_package.py`
- `src/bremen/model_loader.py`
- `src/bremen/config.py`
- `src/bremen/__main__.py`
- `requirements.txt`
- `pyproject.toml`
- `.github/workflows/ecr-publish.yml`
- `infra/terraform/ecr.tf`
- `infra/terraform/variables.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/README.md`
- `Dockerfile`
- Existing tests (ecr workflow test, model_loader test, model_package test)

## Files written

- `.project-memory/pr/0034-bremen-training-pipeline-implementation/PLAN.md` (this file)

## Files intentionally ignored

- All runtime source files (not modified).
- All runtime test files (not modified except ecr workflow test).
- All docs, ADR, and roadmap files (not modified).
- Any H5/HDF5 or model artifact files.

## Boundary confirmations

- confirm: branch is `0034-bremen-training-pipeline-implementation`: yes
- confirm: PR 0033 / ADR-0008 present: yes
- confirm: no implementation files edited during planning: yes
- confirm: no real H5/data access planned: yes
- confirm: no model artifacts planned: yes
- confirm: no runtime import of training planned: yes
- confirm: no inference integration planned: yes
- confirm: no clinical claims planned: yes
- confirm: no git mutation commands run: yes
- confirm: runtime Dockerfile not changed: yes
- confirm: pyproject.toml and requirements.txt unchanged: yes
- confirm: all 7 feature families implemented as per-patient symmetry: yes
- confirm: patient-safe split test planned: yes
- confirm: artifact dict has all 21 required fields: yes
