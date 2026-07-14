# Bremen Architecture Baseline

## Product scope

Bremen is an XRD-based ML decision-support workflow for patients referred to MRI after suspicious mammography findings (dense breast / low-efficacy mammography). Bremen processes target/control HDF5 scan containers, validates metadata, runs preprocessing/feature extraction, loads a controlled joblib model package, and returns prediction/QC/model metadata. Bremen is not a diagnostic replacement and must not claim clinical validation. See ADR-0001 for the full product identity definition.

## Current CLI/config foundation

PR 0008 and PR 0009 delivered the current CLI and config foundation:

- CLI entrypoint with `preprocess` command (lazy import), stub commands (`preflight`, `run`, `report`).
- Config discovery/loading module (`config.py`) with deterministic file lookup (explicit path → `BREMEN_CONFIG` env var → `bremen.yml` → `bremen.yaml` → `bremen.toml`).

## Intended core chain

> Matador → Bremen API → H5 inspect gate → preprocessing/feature extraction → joblib inference → QC → prediction JSON → Matador storage/report layer

## Project Contract Invariant Inventory

1. "Bremen is a controlled ML decision-support product, not just a joblib file."
2. "Bremen must never be described or marketed as a standalone diagnostic system."
3. "No prediction made unless required H5 metadata is present and validated."
4. "Target/control scan roles must be explicit and validated against H5 metadata before any downstream action."
5. "Target and control scans must belong to the same patient/study and be opposite anatomical sides."
6. "Feature schema must be explicit and must match the model package schema before inference."
7. "Joblib model packages are controlled artifacts; joblib must be loaded only from checksum-verified model packages."
8. "Every prediction result MUST include: prediction_id, model_version, model_checksum, feature_schema_version, threshold version/value, qc_status, qc_flags."
9. "Matador remains the system of record for measurements and prediction results."
10. "Platform API MUST NOT depend on local machine paths; all platform paths must be abstracted in project_contract.yml."
11. "Clinical/report wording must remain supplementary decision-support language only."

## Current implementation state

- CLI foundation exists.
- Config discovery/loading exists.
- Docker/CI/GHCR skeleton exists (image built and published, but not used by runtime).
- Real API, H5 gates, inference workflow, Matador integration, cloud deployment, and product-core classifier artifacts remain future work.

## Closing note

PR 0011C / ADR-C is the next architecture bundle, to be planned only after this baseline is merged.

## Deployment Topology

- **GHCR (existing)** — `ghcr.io/eos-dx/bremen`, `latest` and `sha` tags on push to main (PR 0007).
- **AWS ECR (planned, PR 0022)** — Second registry target, same CI safety rules as GHCR: human-provided secrets only, no destructive changes without review, publish gated to merge-to-main/release tag.
- **APRANA (planned, name UNVERIFIED)** — Interim/EOL fallback, deprioritized relative to ECR. The platform name, EOL timeline, and access model must be confirmed before any implementation PR touches APRANA.
- **AWS** is the primary long-term compute target.

## API Surface (Draft)

DRAFT — not a binding contract until PR 0019 is merged.

Minimum endpoint skeleton (from ADR-0003):

- `POST /predictions` — Submit target/control H5 references.
- `GET /predictions/{id}` — Retrieve prediction result by ID.
- `GET /health` — Health check endpoint.
- `GET /model/version` — Current model version metadata.

Every prediction response must carry these fields (from the Project Contract Invariant Inventory):

- `prediction_id`
- `model_version`
- `model_checksum`
- `feature_schema_version`
- threshold version/value
- `qc_status`
- `qc_flags`

The full API contract is delegated to PR 0019.

## Configuration Management

- **Current state**: Static local YAML discovery via `src/bremen/config.py` (PR 0009), relative local paths (`io.output_joblib_path: ../../examples/outputs/...`), `extends:` chaining.
- **Target state**: Cloud-aware sourcing (PR 0020), environment-aware config without breaking the PR 0009 discovery order (explicit path → `BREMEN_CONFIG` env → `bremen.yml` → `bremen.yaml` → `bremen.toml`).
- **Deferred state**: Config editing surface (PR 0024), gated on G-CFG-1.

## External Dependency Risk

- The `container` dependency is pinned to `feat/v0_3-eoscan-session-container` (a feature branch, not main).
- **Why it exists**: `VERSION_REGISTRY "0_3"` support is not yet on `main`.
- **Event-triggered response plan** (G-DEP-1): Re-pin to `main` within 5 business days of `feat/v0_3` → `main` merge; re-verify the `VERSION_REGISTRY` assertion.
- The `requirements.txt` local-path defect (`-e /Users/sad/dev/container`) is part of the same hygiene work (PR 0021).

## Offline Model Artifact Lifecycle

- Training pipeline creates controlled model package.
- Model package stored separately from app image.
- S3 versioned bucket as first implementation target.
- Checksum computed at training-pipeline trust boundary; not derived post-hoc by runtime.
- Checksum manifest write access restricted separately from model artifact read access.

## Online Prediction Runtime Workflow

> Matador/platform submits target/control H5 references
> → Bremen async job is created
> → H5 inspect gate
> → target/control metadata validation
> → preprocessing/feature extraction
> → feature schema validation
> → checksum-verified model package loading
> → joblib inference
> → QC gates
> → prediction JSON
> → Matador storage/report layer

The async job creation is a consequence of the closed G-API-1 decision (async submit → `job_id` → poll, DECIDED in PR 0012).

## AWS Runtime/Deployment Default Decisions

- **Async API**: submit → `job_id` → poll (G-API-1, DECIDED).
- **Compute**: ECS Fargate (G-API-2, DECIDED).
- **IaC tool**: Terraform (G-INFRA-1, DECIDED).
- **Service image path**: ECR (planned, PR 0022).
- **Model package path**: S3 versioned bucket (planned, PR 0013+).
- No automatic deploy or destructive infra mutation in this PR.

## Safety

- Runtime service does not train models.
- Model package load must be checksum-verified.
- Feature schema must match model expectations.
- Prediction result must include required model/version/checksum/QC fields.
- Platform API must not depend on local machine paths.

## Training Pipeline Architecture

- **Offline only**; never part of runtime service.
- **Input**: approved training data + training config YAML.
- **Pipeline**: preprocessing → feature extraction for 7 Bremen feature families → LR1 → M0/M1/M2 training → threshold calibration → artifact assembly.
- **Output**: joblib dict training artifact, QC summary YAML, metrics JSON.
- **Artifact publication**: S3 model store, manifest, checksum.
- **Trigger**: Kubernetes Job. Lambda container image may be supported later for simple cases.
- Runtime (`src/bremen/api/`) never imports from training (`src/bremen/training/`).

## Bremen Feature Computation Confirmation

- Mahalanobis and Wasserstein features are **per-patient symmetry measures**: target breast vs contralateral breast of the same patient.
- They are NOT population-fitted reference statistics.
- `_mahalanobis_difference` computes target-vs-contralateral profile difference normalized by per-patient target/contralateral measurement variance.
- `_profile_wasserstein` computes a distance between normalized target and contralateral profile distributions for the same patient.
- No separate fitted feature-extractor artifact is needed for these features.
- A single joblib training artifact is sufficient for this design.
- ADR-0007 runtime model package manifest remains the checksum and runtime trust boundary.
- A composite artifact may be needed only if future feature computation adds fitted reference statistics.
