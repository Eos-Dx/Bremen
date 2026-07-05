# PR 0033 — Plan ADR-0008: Two-Image Build Strategy and Bremen Training Pipeline Separation

Author: plan
Mode: planning only
Branch: 0033-adr-training-pipeline-separation

## Objective

Create ADR-0008 recording the human-decided architecture for separating Bremen's offline training pipeline from the runtime service, and append training-pipeline sections to ROADMAP.md and docs/architecture.md. This is architect-only docs work — no source code, Dockerfiles, CI, Terraform, configs, model artifacts, or training runs.

## Precondition verification

```
git rev-parse --verify HEAD  -> 23236bfcd58d55f98078d88418cb56589dbcf647
git branch --show-current    -> 0033-adr-training-pipeline-separation
git status --short           -> clean (aside from PR directory)

test -f docs/adr/0007-model-artifact-lifecycle.md  ->  present ✓
grep "must not train" docs/adr/0007-*.md           ->  "Runtime service must not train models." ✓
grep "EXPECTED_ARTIFACT_TYPE" src/bremen/model_package.py  ->  "bremen.joblib.model_package" ✓
grep "model_version\|model_checksum\|feature_schema_version" src/bremen/model_package.py  ->  all present ✓
src/bremen/model_package.py exists  ->  present ✓
```

## Branch name note

The task prompt referenced branch `0031-adr-training-pipeline-separation` but the actual branch is `0033-adr-training-pipeline-separation` (PR 0033, following the ROADMAP.md Next Execution Sequence where PR 0030 was the roadmap/ADR amendment, 0031 was ECR tag, 0032 was model fetch/staging, and this training pipeline ADR is a newly inserted item at PR 0033). The task content — ADR-0008 for two-image training pipeline separation — is identical regardless of PR number.

## Explicit statement

**This PR is architect-only docs work.** It creates ADR-0008 and appends new sections to ROADMAP.md and docs/architecture.md. It does not implement source code, Dockerfiles, CI, Terraform, configs, model artifacts, or training runs.

## Allowed implementation files

The architect may create or modify exactly these files:

1. **`docs/adr/0008-two-image-build-training-pipeline-separation.md`** — NEW
2. **`ROADMAP.md`** — MODIFY (append new `## Training Pipeline Track` section)
3. **`docs/architecture.md`** — MODIFY (append `## Training Pipeline Architecture` and `## Bremen Feature Computation Confirmation` sections)

## Forbidden files

- `src/**`, `tests/**`
- `Dockerfile`, `Dockerfile.training`, `.github/**`, `infra/**`
- `requirements.txt`, `pyproject.toml`, `environment.yml`, `Makefile`
- `config/**`, `agents/**`
- `docs/adr/0001-*.md` through `docs/adr/0007-*.md` (read-only)
- `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`, `docs/product_development_rules.md`, `AGENTS.md`
- Any H5/HDF5, joblib/pkl/npy/npz artifact
- `.project-memory/**` other than this PR's own PLAN.md and reviews

## Required reads (completed for this PLAN.md)

- `docs/adr/0007-model-artifact-lifecycle.md` — existing runtime model lifecycle (must not train, checksum boundary)
- `docs/adr/0003-bremen-microservice-api-architecture.md` — API architecture context
- `ROADMAP.md` — current roadmap with Product Track, Platform Readiness Track, Next Execution Sequence
- `docs/architecture.md` — current architecture with Offline Model Artifact Lifecycle section
- `.project-memory/project_contract.yml` — safety invariants, prediction output requirements
- `src/bremen/model_package.py` — EXPECTED_ARTIFACT_TYPE, manifest fields
- `AGENTS.md` — agent role definitions
- `agents/architect.yml` — architect write permissions for docs/adr/**, ROADMAP.md, docs/architecture.md

## Implementation phase assignment

- **Agent**: architect
- **Mode**: WRITE

**Reason**: All three implementation files are architect-reserved paths per `agents/architect.yml`: `docs/adr/**` (ADR-0008), `ROADMAP.md` (append), `docs/architecture.md` (append). The coder role lacks write permission for these paths.

## ADR-0008 planned content: `docs/adr/0008-two-image-build-training-pipeline-separation.md`

**Status**: Accepted

**Title**: Two-Image Build Strategy and Bremen Training Pipeline Separation

### Decision 1 — Training pipeline is separate from the runtime service

- Training lives in `src/bremen/training/` as a new offline-only package.
- Runtime lives in `src/bremen/api/` and related runtime modules.
- Runtime NEVER imports from `src/bremen/training/`.
- Runtime never trains, retrains, mutates, or overwrites model artifacts.
- This structurally enforces ADR-0007: runtime must not train.
- Research-era modules such as `modeling.py` or `mlflow_tracking.py` are not the runtime training boundary.

### Decision 2 — Two Docker images, two ECR repositories

- **Image 1: Bremen Runtime image**
  - Existing runtime Dockerfile.
  - Lightweight inference-only service image.
  - Contains runtime HTTP/API code, `model_package`, `model_loader`, `config`, runtime API/service code.
  - Does NOT contain offline training entrypoints, training config readers, MLflow training flow, heavy training-only dependencies, or training orchestration.

- **Image 2: Bremen Training image**
  - New `Dockerfile.training` in the implementation PR, not this PR.
  - Training-only image.
  - Contains training pipeline code, training entrypoint, sklearn training stack, MLflow if needed for training, scipy/pandas and other offline dependencies required by training.
  - Entry point: `python -m bremen.training.train_classifier`

- Two separate ECR repositories:
  - `bremen-runtime`
  - `bremen-training`

- Both images are built in CI for implementation PR scope, not this PR.
- Each image must have immutable `github.sha` tag for audit.
- Mutable tags may exist for operator convenience but must not weaken artifact traceability.

### Decision 3 — Bremen training joblib artifact structure

The training joblib artifact is a Python `dict` and is the offline training audit payload. The joblib file must preserve enough information to reconstruct what data, config, preprocessing lineage, feature schema, metrics, and code produced the trained model.

Fields:

```
kind: "bremen_training_artifact"
version: string
created_at: ISO-8601 UTC timestamp
model_type: string, for example "patient_m0_m1_m2_logistic_set"
models: dict of fitted model entries, for example M0, M1, optionally M2
thresholds: dict or per-model threshold entries for configured sensitivity target
model_descriptions: dict describing each model entry when available
feature_schema: dict describing feature names, feature columns, and types
warnings: list of training/audit warnings that must remain attached to artifact
training_config: full parsed training config dict embedded for audit
training_config_yaml: raw YAML string embedded for audit
training_config_text: same raw training config text if retained for compatibility
training_config_sha256: SHA-256 of training config text
input_dataframe_joblib_sha256: SHA-256 of input dataframe artifact
dataset_summary: patient counts, class distribution, split info
feature_table: patient-level feature table or equivalent audit payload
metric_summary: AUC, sensitivity, specificity, balanced accuracy, PPV, NPV
  and related metrics per model
split_metrics: all CV/split results
split_predictions: per-split prediction audit table when available
preprocessing_lineage: preprocessing config/artifact provenance needed to
  trace the training dataframe
metadata: dict with bremen_version, git_sha, created_at, branch/training role
```

This artifact dict is separate from the ADR-0007 runtime model package manifest. ADR-0007 manifest fields remain:

- `artifact_type` (must remain `"bremen.joblib.model_package"`)
- `model_version`
- `model_checksum`
- `model_filename`
- `feature_schema_version`
- `threshold_version`
- `threshold_value`
- `qc_criteria_version`

The training artifact dict may have more fields than the runtime package manifest, but must not rename or conflict with ADR-0007 concepts: `model_version`, `model_checksum`, `feature_schema_version`.

### Decision 4 — Bremen training config YAML structure

Bremen training config uses a YAML structure with these sections:

```yaml
training:
  name
  version
  branch
  clinical_stage
  intended_use
  role

io:
  input_dataframe_joblib_path
  output_model_joblib_path
  output_json_path
  output_yaml_path
  optional preprocessing/prediction lineage config paths if needed

model:
  type
  profile_column
  label_column
  group_column
  specimen_column
  side_column
  q_column
  age_column
  mri_referred_column or cohort/filter policy field if needed
  lr1_row_policy
  selected_models
  logreg_c

evaluation:
  mode
  n_splits
  test_size
  random_state
  target_sensitivity
```

Bremen adaptation:
- Classification task is Healthy vs disease: NORMAL vs BENIGN + CANCER.
- Cohort context is MRI-referred population.
- Feature families must match Bremen product identity: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
- `lr1_row_policy` must use Bremen naming such as `mri_referred_only` when filtering to the MRI-referred training cohort.
- `target_sensitivity` may be a planning/optimization target but must not be reported as achieved clinical validation.

### Decision 5 — Training trigger

- Bremen Training image is designed to run as an offline batch job.
- Primary target: Kubernetes Job.
- Entry example for implementation planning: `docker run bremen-training:<sha> CONFIG_URI=s3://...`
- AWS Lambda container image may be supported later for simpler cases.
- ECS/App Runner are runtime targets only, not training targets.
- Operator or Argo Workflow may be added later, but is not designed in this PR.
- No training job is run in PR 0033.

### Decision 6 — PR 0034 Bremen training implementation scope

The next implementation PR (PR 0034) must build these Bremen training components. They must be stated as Bremen-owned implementation targets, not as external product dependencies:

- `PatientModelInputBuilder`
- `BremenPatientTrainingPipeline`
- `PatientModelSetTrainer`
- `PatientModelSetEvaluator`
- `build_patient_training_pipeline`
- `run_training_from_config`
- `train_patient_m0_m1_m2_model_artifact`
- `_patient_training_artifact`
- `_sk_target_contralateral_symmetry_features` for the 7 Bremen feature families
- `_sk_side_mean_metrics` for target/contralateral profile aggregation
- `_mahalanobis_difference` for Mahalanobis1 and Mahalanobis2
- `_profile_wasserstein` for `wasserstein_distance_full_q2`
- `_rms_difference` / `_weighted_rms_difference` / `_sigma_rms` as needed for: `sigma_l1`, `sigma_l2`, `meanrms2`, `weightedrms1`
- `_file_sha256`
- `_config_path` / `_optional_config_path` helpers
- training config YAML under `config/training/`
- CLI entrypoint: `python -m bremen.training.train_classifier --config <training.yaml>`

Required Bremen adaptation notes for PR 0034:
- Use Bremen names in kind/version/metadata.
- Use Bremen target labels: NORMAL vs BENIGN + CANCER. Healthy vs disease.
- Use Bremen cohort naming: MRI-referred population. `mri_referred_only` policy where applicable.
- Use Bremen feature column names exactly: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
- Keep patient-safe split logic: measurements from one patient must not appear in both train and test.
- Keep M0/M1/M2 model structure if appropriate for Bremen.
- Keep `target_sensitivity` as training/QC configuration, not clinical claim.
- Keep feature computation logic as per-patient target vs contralateral symmetry features.
- Add Bremen-specific metadata fields.

### Repository Structure After PR 0034

```
src/bremen/
  api/          existing runtime package
  training/     new offline training package only
    __init__.py
    train_classifier.py
    pipeline.py
model_package.py
model_loader.py
config.py
config/
  training/
    bremen_v0_1_train.yaml
Dockerfile
Dockerfile.training
```

### Bremen Training Implementation Notes

Each implementation target, target Bremen location, and required Bremen adaptation:

| Target | Location (src/bremen/training/) | Adaptation |
|--------|--------------------------------|------------|
| `PatientModelInputBuilder` | `pipeline.py` | Accept preprocessed dataframe, validate columns match config, enforce MRI-referred cohort filter |
| `BremenPatientTrainingPipeline` | `pipeline.py` | Assemble input builder + trainers + evaluators |
| `PatientModelSetTrainer` | `pipeline.py` | Train M0/M1/M2 models, enforce patient-safe splits |
| `PatientModelSetEvaluator` | `pipeline.py` | Compute metrics, generate split predictions |
| `build_patient_training_pipeline` | `pipeline.py` | Build the pipeline from config |
| `run_training_from_config` | `pipeline.py` | Parse config YAML, run pipeline, assemble artifact |
| `train_patient_m0_m1_m2_model_artifact` | `train_classifier.py` | CLI entrypoint caller |
| `_patient_training_artifact` | `pipeline.py` | Assemble the training artifact dict with all audit fields |
| `_sk_target_contralateral_symmetry_features` | `pipeline.py` | Compute all 7 feature families per patient target-vs-contralateral |
| `_sk_side_mean_metrics` | `pipeline.py` | Aggregate per-side profile means for target/contralateral |
| `_mahalanobis_difference` | `pipeline.py` | Mahalanobis1 and Mahalanobis2 — per-patient symmetry measure |
| `_profile_wasserstein` | `pipeline.py` | wasserstein_distance_full_q2 — profile distribution distance |
| `_rms_difference` | `pipeline.py` | meanrms2 — RMS asymmetry |
| `_weighted_rms_difference` | `pipeline.py` | weightedrms1 — weighted RMS asymmetry |
| `_sigma_rms` | `pipeline.py` | sigma_l1, sigma_l2 — sigma RMS measures |
| `_file_sha256` | `pipeline.py` | Compute SHA-256 of input data files |
| `_config_path` | `pipeline.py` | Resolve config file path |
| `_optional_config_path` | `pipeline.py` | Resolve optional config reference path |

### What ADR-0008 must NOT claim

- No clinical validation.
- No achieved performance metrics.
- No claim that inference is implemented.
- No claim that training has been run.
- No claim that Bremen diagnoses disease.
- No claim that Bremen replaces MRI, biopsy, radiologist, or clinician.

## ROADMAP.md extension

Append a new `## Training Pipeline Track` section **after** the existing `## Next Execution Sequence (post-platform-foundation)` content. Do not remove or rewrite existing content.

```markdown
## Training Pipeline Track

- **PR 0033** — ADR-0008: two-image build strategy and training/runtime separation (this PR).
- **PR 0034** — Bremen training pipeline implementation:
  - `Dockerfile.training`
  - `src/bremen/training/`
  - CI extension for runtime and training images
  - Second ECR repository for training image
  - `config/training/*.yaml`
  - Bremen training joblib artifact assembly
  - Feature computation for 7 Bremen feature families (sigma_l1, sigma_l2, Mahalanobis1, Mahalanobis2, wasserstein_distance_full_q2, meanrms2, weightedrms1)
  - Tests for training artifact shape and patient-safe splits
- **PR 0035 (tentative)** — First controlled training run and model package publication:
  - Run training on approved Bremen/Nova study data
  - Publish `bremen_v0_1.joblib` to S3 model store
  - Create/verify manifest with `model_checksum` and `feature_schema_version`
  - Verify `model_package.py` can validate package
  - Update configured `BREMEN_MODEL_VERSION` through approved model release process
```

Also update the existing Product Track item 4 ("Bremen feature-family implementation/verification") with an additive note:

> **Note**: Feature family implementation (sigma_l1, sigma_l2, Mahalanobis1, Mahalanobis2, wasserstein_distance_full_q2, meanrms2, weightedrms1) is covered by PR 0034's Bremen training pipeline, not by a separate unscoped PR.

## docs/architecture.md extension

Append two new sections **after** the existing `## Safety` section. Do not remove or rewrite existing content.

### `## Training Pipeline Architecture`

- **Offline only**; never part of runtime service.
- **Input**: approved training data + training config YAML.
- **Pipeline**: preprocessing → feature extraction for 7 Bremen feature families → LR1 → M0/M1/M2 training → threshold calibration → artifact assembly.
- **Output**: joblib dict training artifact, QC summary YAML, metrics JSON.
- **Artifact publication**: S3 model store, manifest, checksum.
- **Trigger**: Kubernetes Job. Lambda container image may be supported later for simple cases.
- Runtime (`src/bremen/api/`) never imports from training (`src/bremen/training/`).

### `## Bremen Feature Computation Confirmation`

- Mahalanobis and Wasserstein features are **per-patient symmetry measures**: target breast vs contralateral breast of the same patient.
- They are NOT population-fitted reference statistics.
- `_mahalanobis_difference` computes target-vs-contralateral profile difference normalized by per-patient measurement variance.
- `_profile_wasserstein` computes a distance between normalized target and contralateral profile distributions for the same patient.
- No separate fitted feature-extractor artifact is needed for these features.
- Single joblib training artifact is sufficient for this design.
- ADR-0007 runtime model package manifest remains the checksum and runtime trust boundary.

## Non-goals

- No source code.
- No `Dockerfile.training`.
- No CI changes.
- No ECR second repository Terraform.
- No actual training run.
- No inference integration.
- No H5 reads.
- No model package publication.
- No dependency changes.
- No runtime import of training code.

## Validation checklist

The implementation phase (architect) must execute these checks:

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5-7) File existence
test -f docs/adr/0008-two-image-build-training-pipeline-separation.md || exit 1

# 8-10) ADR-0008 content checks
grep -q "bremen_training_artifact" docs/adr/0008-*.md || exit 1
grep -q "Dockerfile.training" docs/adr/0008-*.md || exit 1
grep -q "Bremen Training Implementation Notes" docs/adr/0008-*.md || exit 1

# 11-12) Architecture extension checks
grep -q "per-patient symmetry" docs/architecture.md || exit 1
grep -q "Project Contract Invariant Inventory" docs/architecture.md || exit 1

# 13) ROADMAP extension check
grep -q "Training Pipeline Track" ROADMAP.md || exit 1

# 14) No forbidden file changes
git diff --name-only -- src tests config .github Dockerfile Dockerfile.training infra requirements.txt pyproject.toml environment.yml Makefile agents/ README.md docs/adr/0001-*.md docs/adr/0007-*.md
# Must return nothing

# 15) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

1. **Revert `docs/adr/0008-two-image-build-training-pipeline-separation.md`** — delete.
2. **Revert `ROADMAP.md`** — remove the appended `## Training Pipeline Track` section and the additive note on Product Track item 4.
3. **Revert `docs/architecture.md`** — remove the appended `## Training Pipeline Architecture` and `## Bremen Feature Computation Confirmation` sections.

No other files affected.

## Follow-up PR summary

- **PR 0034** — Bremen training pipeline implementation. Builds all components listed in Decision 6 and the Implementation Notes. Creates `src/bremen/training/`, `Dockerfile.training`, `config/training/*.yaml`, CI extensions, second ECR repository.
- **PR 0035 (tentative)** — First controlled training run and model package publication on approved data.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only ADR-0008, ROADMAP.md, docs/architecture.md changed. |
| **ADR-0008 drift** | Contains 6 numbered decisions, Repository Structure section, Bremen Training Implementation Notes with function-level detail, complete artifact dict structure. No clinical claims. |
| **ROADMAP.md drift** | Training Pipeline Track appended after Next Execution Sequence. Product Track item 4 additively updated. Existing content not removed or rewritten. |
| **Architecture drift** | Training Pipeline Architecture and Bremen Feature Computation Confirmation sections appended after existing content. Project Contract Invariant Inventory preserved. |
| **Feature computation drift** | Confirms per-patient symmetry measures. No population-fitted reference statistics. All 7 families listed with function-level mapping. |
| **Safety drift** | No clinical validation, inference claims, or training run claims. ADR-0007 manifest names preserved (artifact_type, model_version, model_checksum, feature_schema_version). |
| **Implementation agent drift** | Assigned to Agent: architect, Mode: WRITE. |
| **Validation drift** | All validation checks pass. No forbidden file changes. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- ADR-0007 is missing.
- `model_package.py` is missing.
- ADR-0008 planned content is missing function-level Bremen implementation notes.
- ADR-0008 planned content is missing complete artifact dict structure.
- ADR-0008 planned content conflicts with ADR-0007 manifest names (must preserve `artifact_type`, `model_version`, `model_checksum`, `feature_schema_version`).
- Feature computation confirmation is missing.
- ADR-0008 planned content claims clinical validation or implemented inference.
- ROADMAP.md plan removes or renumbers existing content.
- `docs/architecture.md` plan removes or rewrites existing content.
- Implementation phase is assigned to coder instead of architect.
- Any source code, Dockerfile, CI, Terraform, config, or dependency change is planned.

## Decisions summary

### Allowed files
1. `docs/adr/0008-two-image-build-training-pipeline-separation.md` — NEW
2. `ROADMAP.md` — MODIFY (append Training Pipeline Track, update Product Track item 4)
3. `docs/architecture.md` — MODIFY (append Training Pipeline Architecture + Feature Computation Confirmation)

### ADR-0008 summary
Status: Accepted. 6 binding decisions: (1) training/runtime separation, (2) two Docker images/repos, (3) training artifact dict structure with 19+ fields, (4) training config YAML structure, (5) Kubernetes Job as training trigger, (6) PR 0034 implementation scope with 19+ component list. Repository structure diagram. Implementation notes table.

### Training implementation notes summary
All 7 feature families listed with function-level implementation target:
- `sigma_l1`, `sigma_l2` → `_sigma_rms`
- `Mahalanobis1`, `Mahalanobis2` → `_mahalanobis_difference`
- `wasserstein_distance_full_q2` → `_profile_wasserstein`
- `meanrms2` → `_rms_difference`
- `weightedrms1` → `_weighted_rms_difference`

### Artifact dict summary
19+ fields: `kind`, `version`, `created_at`, `model_type`, `models`, `thresholds`, `model_descriptions`, `feature_schema`, `warnings`, `training_config`, `training_config_yaml`, `training_config_text`, `training_config_sha256`, `input_dataframe_joblib_sha256`, `dataset_summary`, `feature_table`, `metric_summary`, `split_metrics`, `split_predictions`, `preprocessing_lineage`, `metadata`.

### ROADMAP extension summary
New `## Training Pipeline Track` section with PR 0033 (this ADR), PR 0034 (training implementation), PR 0035 (first training run + publication). Product Track item 4 additively updated.

### Architecture extension summary
`## Training Pipeline Architecture` — offline-only, never runtime, feature extraction for 7 families, artifact assembly, Kubernetes Job trigger. `## Bremen Feature Computation Confirmation` — Mahalanobis/Wasserstein are per-patient symmetry measures, NOT population-fitted reference statistics.

### Implementation agent assignment
- Agent: architect
- Mode: WRITE

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0033-adr-training-pipeline-separation/PLAN.md`
2. Human runs: `git add .project-memory/pr/0033-adr-training-pipeline-separation/PLAN.md`
3. Human runs: `git commit -m "PR 0033 — Plan ADR-0008: two-image build strategy and training pipeline separation"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the architect implements the three allowed files.

## Files read

- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `.project-memory/project_contract.yml`
- `src/bremen/model_package.py`
- `AGENTS.md`
- `agents/architect.yml`

## Files written

- `.project-memory/pr/0033-adr-training-pipeline-separation/PLAN.md` (this file)

## Files intentionally ignored

- All source, test, config, and example files
- All infrastructure files (CI, Docker, Terraform, pyproject)
- All docs not in allowed set
- Any H5/HDF5 or model artifact files

## Boundary confirmations

- confirm: precondition files verified present: yes
- confirm: this PR only plans `docs/adr/0008-*.md`, `ROADMAP.md`, `docs/architecture.md`: yes
- confirm: Bremen training implementation notes included with function-level detail: yes
- confirm: artifact dict structure specified completely (19+ fields): yes
- confirm: feature computation confirmation included: yes
- confirm: no source code, Dockerfile, CI, Terraform, config, or dependency change planned: yes
- confirm: implementation phase assigned to Agent: architect, Mode: WRITE: yes
- confirm: no git mutation commands run: yes
