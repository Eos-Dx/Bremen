# ADR-0008: Two-Image Build Strategy and Bremen Training Pipeline Separation

**Status**: Accepted

## Context

- Bremen currently has runtime foundation, model package validation, and research-era modeling helpers, but does not yet have a production-shaped offline training pipeline.
- ADR-0007 establishes that the runtime service must not train, retrain, mutate, or overwrite model artifacts.
- Training is an offline-only activity that produces controlled, checksum-verified model packages consumed by the runtime.
- The existing repository structure has research-era scripts (`modeling.py`, `mlflow_tracking.py`) that are not a production training boundary.

## Decision 1 — Training pipeline is separate from the runtime service

**Decision**: Training lives in `src/bremen/training/` as a new offline-only package. Runtime lives in `src/bremen/api/` and related runtime modules. Runtime NEVER imports from `src/bremen/training/`. Runtime never trains, retrains, mutates, or overwrites model artifacts.

**Repository consequences**:
- A new `src/bremen/training/` package is created containing the training pipeline.
- Runtime modules (`api/`, `model_package.py`, `model_loader.py`, `config.py`) must never import from `training/`.
- linting or import-checking rules should enforce this separation.

**Rationale**: This structurally enforces ADR-0007: runtime must not train. Research-era modules such as `modeling.py` or `mlflow_tracking.py` are not the runtime training boundary. A clean directory boundary prevents accidental runtime imports of training code and keeps the runtime image lightweight.

## Decision 2 — Two Docker images, two ECR repositories

**Decision**: Two separate Docker images are built and pushed to two separate ECR repositories.

### Bremen Runtime image
- Uses the existing `Dockerfile`.
- Lightweight inference-only service image.
- Contains: runtime HTTP/API code, `model_package`, `model_loader`, `config`, runtime API/service code.
- Does NOT contain: offline training entrypoints, training config readers, MLflow training flow, heavy training-only dependencies, or training orchestration.

### Bremen Training image
- Uses a new `Dockerfile.training` (to be created in PR 0034, not this PR).
- Training-only image.
- Contains: training pipeline code, training entrypoint, sklearn training stack, MLflow if needed for training, scipy/pandas and other offline dependencies required by training.
- Entry point: `python -m bremen.training.train_classifier`.

### ECR repositories
- Two separate ECR repositories:
  - `bremen-runtime`
  - `bremen-training`
- Both images are built in CI as part of the implementation PR (PR 0034), not this PR.
- Each image must have an immutable `github.sha` tag for audit.
- Mutable tags may exist for operator convenience but must not weaken artifact traceability.

**Rationale**: Separate images keep the runtime image small and minimize the runtime attack surface. Training-only dependencies (scipy, pandas, MLflow) are not needed at runtime. Separate ECR repositories provide separate access control, audit trails, and tag namespaces.

## Decision 3 — Bremen training joblib artifact structure

The training joblib artifact is a Python `dict` and is the offline training audit payload. The joblib file must preserve enough information to reconstruct what data, config, preprocessing lineage, feature schema, metrics, and code produced the trained model.

### Complete field list

| Field | Type / example | Description |
|-------|---------------|-------------|
| `kind` | `"bremen_training_artifact"` | Artifact type identifier |
| `version` | `string` | Artifact schema version |
| `created_at` | ISO-8601 UTC timestamp | When the artifact was assembled |
| `model_type` | `"patient_m0_m1_m2_logistic_set"` | String identifying the model architecture |
| `models` | `dict` | Fitted model entries, e.g. `M0`, `M1`, optionally `M2` |
| `thresholds` | `dict` | Per-model threshold entries for configured sensitivity target |
| `model_descriptions` | `dict` | Describing each model entry when available |
| `feature_schema` | `dict` | Feature names, feature columns, and types |
| `warnings` | `list` | Training/audit warnings that remain attached to the artifact |
| `training_config` | `dict` | Full parsed training config dict embedded for audit |
| `training_config_yaml` | `str` | Raw YAML string embedded for audit |
| `training_config_text` | `str` | Same raw training config text if retained for compatibility |
| `training_config_sha256` | `str` | SHA-256 hex digest of training config text |
| `input_dataframe_joblib_sha256` | `str` | SHA-256 of input dataframe artifact |
| `dataset_summary` | `dict` | Patient counts, class distribution, split info |
| `feature_table` | `dict` | Patient-level feature table or equivalent audit payload |
| `metric_summary` | `dict` | AUC, sensitivity, specificity, balanced accuracy, PPV, NPV and related metrics per model |
| `split_metrics` | `dict` | All CV/split results |
| `split_predictions` | `dict` | Per-split prediction audit table when available |
| `preprocessing_lineage` | `dict` | Preprocessing config/artifact provenance needed to trace the training dataframe |
| `metadata` | `dict` | Bremen-specific metadata: `bremen_version`, `git_sha`, `created_at`, branch/training role |

### Relationship to ADR-0007 runtime model package manifest

This training artifact dict is **separate** from the ADR-0007 runtime model package manifest. The ADR-0007 runtime manifest fields remain unchanged:

- `artifact_type` — must remain `"bremen.joblib.model_package"`
- `model_version`
- `model_checksum`
- `model_filename`
- `feature_schema_version`
- `threshold_version`
- `threshold_value`
- `qc_criteria_version`

The training artifact dict may have more fields than the runtime package manifest, but must not rename or conflict with ADR-0007 concepts: `model_version`, `model_checksum`, `feature_schema_version`.

The `EXPECTED_ARTIFACT_TYPE` constant in `model_package.py` remains `"bremen.joblib.model_package"`.

## Decision 4 — Bremen training config YAML structure

Bremen training config uses a YAML structure with the following sections and fields:

### `training` section
- `training.name` — Name of the training run
- `training.version` — Config version
- `training.branch` — Config branch identifier
- `training.clinical_stage` — Clinical stage label
- `training.intended_use` — Intended use description
- `training.role` — Training role label

### `io` section
- `io.input_dataframe_joblib_path` — Path to input dataframe joblib artifact
- `io.output_model_joblib_path` — Path for output model joblib artifact
- `io.output_json_path` — Path for output metrics JSON
- `io.output_yaml_path` — Path for output QC YAML
- Optional preprocessing/prediction lineage config paths if needed

### `model` section
- `model.type` — Model type string
- `model.profile_column` — Column containing XRD profile data
- `model.label_column` — Column containing the label
- `model.group_column` — Column for patient/group grouping
- `model.specimen_column` — Column for specimen identifiers
- `model.side_column` — Column for breast side (target/contralateral)
- `model.q_column` — Column for quality/measurement flags
- `model.age_column` — Column for age
- `model.lr1_row_policy` — Row filtering policy name, e.g. `mri_referred_only`
- `model.selected_models` — Which models to train (e.g., M0, M1, M2)
- `model.logreg_c` — Logistic regression regularization parameter

### `evaluation` section
- `evaluation.mode` — Evaluation mode (e.g., `cross_validation`, `holdout`)
- `evaluation.n_splits` — Number of cross-validation splits
- `evaluation.test_size` — Test set proportion
- `evaluation.random_state` — Random state for reproducibility
- `evaluation.target_sensitivity` — Target sensitivity for threshold calibration (training/QC configuration, not achieved clinical validation)

### Bremen adaptation
- **Classification task**: Healthy vs disease — NORMAL vs BENIGN + CANCER.
- **Cohort context**: MRI-referred population.
- **Feature families**: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
- **`lr1_row_policy`**: Should use Bremen naming such as `mri_referred_only` when filtering to the MRI-referred training cohort.
- **`target_sensitivity`**: A planning/optimization target for threshold calibration. Must not be reported as achieved clinical validation.

## Decision 5 — Training trigger

- The Bremen Training image is designed to run as an offline batch job.
- **Primary target**: Kubernetes Job.
- Entry example for implementation planning: `docker run bremen-training:<sha> CONFIG_URI=s3://...`
- AWS Lambda container image may be supported later for simpler cases.
- ECS and App Runner are **runtime targets only**, not training targets.
- Operator or Argo Workflow may be added later, but is not designed in this PR.
- **No training job is run in PR 0033.**

## Decision 6 — PR 0034 Bremen training implementation scope

The next implementation PR (PR 0034) must build these Bremen training components. They are stated as Bremen-owned implementation targets, not as external product dependencies.

### Implementation targets

| Target | Location | Description |
|--------|----------|-------------|
| `PatientModelInputBuilder` | `src/bremen/training/pipeline.py` | Accept preprocessed dataframe, validate columns match config, enforce MRI-referred cohort filter |
| `BremenPatientTrainingPipeline` | `src/bremen/training/pipeline.py` | Assemble input builder + trainers + evaluators |
| `PatientModelSetTrainer` | `src/bremen/training/pipeline.py` | Train M0/M1/M2 models, enforce patient-safe splits |
| `PatientModelSetEvaluator` | `src/bremen/training/pipeline.py` | Compute metrics, generate split predictions |
| `build_patient_training_pipeline` | `src/bremen/training/pipeline.py` | Build the pipeline from config |
| `run_training_from_config` | `src/bremen/training/pipeline.py` | Parse config YAML, run pipeline, assemble artifact |
| `train_patient_m0_m1_m2_model_artifact` | `src/bremen/training/train_classifier.py` | CLI entrypoint caller |
| `_patient_training_artifact` | `src/bremen/training/pipeline.py` | Assemble the training artifact dict with all audit fields |
| `_sk_target_contralateral_symmetry_features` | `src/bremen/training/pipeline.py` | Compute all 7 feature families per patient target-vs-contralateral |
| `_sk_side_mean_metrics` | `src/bremen/training/pipeline.py` | Aggregate per-side profile means for target/contralateral |
| `_mahalanobis_difference` | `src/bremen/training/pipeline.py` | Mahalanobis1 and Mahalanobis2 — per-patient symmetry measure |
| `_profile_wasserstein` | `src/bremen/training/pipeline.py` | `wasserstein_distance_full_q2` — profile distribution distance |
| `_rms_difference` | `src/bremen/training/pipeline.py` | `meanrms2` — RMS asymmetry |
| `_weighted_rms_difference` | `src/bremen/training/pipeline.py` | `weightedrms1` — weighted RMS asymmetry |
| `_sigma_rms` | `src/bremen/training/pipeline.py` | `sigma_l1`, `sigma_l2` — sigma RMS measures |
| `_file_sha256` | `src/bremen/training/pipeline.py` | Compute SHA-256 of input data files |
| `_config_path` | `src/bremen/training/pipeline.py` | Resolve config file path |
| `_optional_config_path` | `src/bremen/training/pipeline.py` | Resolve optional config reference path |

### CLI entrypoint

```
python -m bremen.training.train_classifier --config <training.yaml>
```

### Required Bremen adaptations

- Use Bremen names in `kind`/`version`/`metadata`.
- Use Bremen target labels: NORMAL vs BENIGN + CANCER. Healthy vs disease.
- Use Bremen cohort naming: MRI-referred population. `mri_referred_only` policy where applicable.
- Use exact Bremen feature column names: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
- Keep patient-safe split logic: measurements from one patient must not appear in both train and test.
- Keep M0/M1/M2 model structure if appropriate for Bremen.
- Keep `target_sensitivity` as training/QC configuration, not a clinical claim.
- Keep feature computation logic as per-patient target vs contralateral symmetry features.
- Add Bremen-specific metadata fields.

## Repository Structure After PR 0034

```text
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

## Bremen Training Implementation Notes

See Decision 6 for the complete implementation target table with locations and descriptions. All implementation targets are listed there with function-level detail and required Bremen adaptation.

## Feature computation confirmation

- Mahalanobis and Wasserstein features are **per-patient symmetry measures**: target breast vs contralateral breast of the same patient.
- They are NOT population-fitted reference statistics.
- `_mahalanobis_difference` computes target-vs-contralateral profile difference normalized by per-patient target/contralateral measurement variance.
- `_profile_wasserstein` computes a distance between normalized target and contralateral profile distributions for the same patient.
- No separate fitted feature-extractor artifact is needed for this feature design.
- A single joblib training artifact is sufficient for this feature computation design.
- ADR-0007 runtime model package manifest remains the checksum and runtime trust boundary.
- A composite artifact may be needed only if future feature computation adds fitted reference statistics.

## Consequences

- PR 0034 must implement all training components listed in Decision 6.
- The training pipeline is offline-only. Runtime must never import from `src/bremen/training/`.
- Two Docker images and two ECR repositories will be created.
- The training artifact dict (Decision 3) and training config YAML (Decision 4) provide the contract for PR 0034.
- ADR-0007 runtime manifest fields remain unchanged.

## Non-goals

- No clinical validation.
- No achieved performance metrics.
- No claim that inference is implemented.
- No claim that training has been run.
- No claim that Bremen diagnoses disease.
- No claim that Bremen replaces MRI, biopsy, radiologist, or clinician.
