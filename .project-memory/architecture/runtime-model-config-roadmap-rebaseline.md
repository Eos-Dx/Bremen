# Bremen Runtime / Model / Config Roadmap Rebaseline

**Date**: 2026-07-05 (UTC)
**Author**: Chief Architect
**Branch**: `0029-runtime-model-config-roadmap-rebaseline`
**HEAD**: `f95737316ff39ed907c73382d626b2c6b7303171`
**Working tree**: clean (`git status --short` — no output)

---

## Verdict

**REBASELINE_BEFORE_MORE_RUNTIME_CODE**

The runtime/model/config/infra architecture is structurally sound at the component level (model package contract, controlled loader, HTTP server, cloud config reader, ECR workflow, Terraform skeleton all exist and are reviewed), but the roadmap, ADRs, and gate register are out of alignment with the human directive to pivot App Runner to the near-term proving target, retire APRANA, defer ECS, and establish config governance as a first-class concern. No implementation PR should proceed until the roadmap/ADR amendments are recorded.

---

## Executive Decision

1. **App Runner is the near-term proving/testing target.** ECS Fargate remains the long-term primary production target. ECS work moves later in the sequence. This is an acceptable operational pivot, not a blocker, but it requires ADR and ROADMAP amendment before any App Runner implementation PR.

2. **APRANA is retired entirely.** It must not be carried forward. The term "APRANA" in ADR-0006 and ROADMAP.md must be replaced with explicit "AWS App Runner" language or removed. APRANA is not App Runner — it was an unverified placeholder name. A dedicated cleanup PR is required.

3. **Model binding lifecycle is confirmed correct** as specified in the human directive: deploy-time identity, startup-time fetch/validate/load, request-time serve-only, no hot-swap. The existing `model_loader.py` and `model_package.py` already implement the controlled boundary correctly. The missing piece is the fetch/staging step between cloud config and local validation.

4. **Model package composition is an open DS/inventory question.** The repo contains feature-family names (Mahalanobis, Wasserstein) that may require fitted reference statistics, but no source code or training pipeline evidence confirms whether these are pre-computed at training time or required at inference time. This must be resolved before preprocessing/inference PRs. It does not block the roadmap/ADR amendment PR.

5. **Config governance requires a new ADR and gate.** Config is not model. Config needs validated editing, versioned state history, audit, and runtime-vs-restart classification. This is a new architectural concern not covered by existing ADRs.

6. **CI/CD image tag policy needs a follow-up PR** to add a stable mutable App Runner tag alongside the existing immutable SHA tag. The current `latest` tag is acceptable for GHCR/ECR but should not be the App Runner deploy trigger.

7. **The immediate next PR must be a roadmap/ADR amendment**, not runtime code. The amendment records the App Runner pivot, APRANA retirement, model binding lifecycle, config governance gate, and revised PR sequence.

---

## Evidence Read

### Files read

| File | Purpose |
|------|---------|
| `ROADMAP.md` | Current roadmap, gate register, PR sequence, APRANA clarification |
| `.project-memory/project_contract.yml` | Safety invariants, source-of-truth order, prediction output requirements |
| `.project-memory/pr/0012-model-artifact-lifecycle-gates/reviews/precommit-review.yml` | ADR-0007 creation, gate closures G-API-1/G-API-2/G-INFRA-1 |
| `.project-memory/pr/0013-model-package-contract/reviews/precommit-review.yml` | model_package.py creation, manifest contract, checksum validation |
| `.project-memory/pr/0022a-terraform-skeleton/reviews/precommit-review.yml` | Terraform skeleton: ECR, S3, ECS Fargate, IAM |
| `.project-memory/pr/0022b-ecr-publish-workflow/reviews/precommit-review.yml` | ECR publish workflow, github.sha + latest tags |
| `.project-memory/pr/0022c-ecr-credentials-hotfix/reviews/precommit-review.yml` | Not found at expected path (see Warnings) |
| `.project-memory/pr/0026-runtime-http-service-runner/reviews/precommit-review.yml` | HTTP server creation, stdlib only, no inference |
| `.project-memory/pr/0027-model-package-source-integration/reviews/precommit-review.yml` | model_source.py, metadata-only, read_cloud_config reuse |
| `.project-memory/pr/0028-controlled-model-loading-boundary/reviews/precommit-review.yml` | model_loader.py, validation-before-deserialization, joblib boundary |
| `src/bremen/model_package.py` | Manifest validation, SHA-256, path traversal prevention |
| `src/bremen/model_loader.py` | Controlled joblib.load boundary, validation-first |
| `src/bremen/api/model_source.py` | Metadata-only model source descriptor |
| `src/bremen/api/server.py` | Stdlib HTTP server, 4 routes, in-memory job store |
| `src/bremen/config.py` | Config discovery (YAML/TOML) + cloud config (env vars) |
| `.github/workflows/ecr-publish.yml` | ECR build/push, github.sha + latest tags |
| `Dockerfile` | CI smoke image, no model/H5/data, python:3.13-slim |
| `requirements.txt` | joblib>=1.4, h5py, scikit-learn, etc. |
| `pyproject.toml` | Package metadata, joblib>=1.4 dependency |
| `infra/terraform/README.md` | Terraform skeleton documentation |
| `infra/terraform/*.tf` (7 files) | ECR, S3, ECS Fargate, IAM, CloudWatch |
| `docs/adr/0007-model-artifact-lifecycle.md` | Model artifact lifecycle ADR |
| `docs/adr/0006-multi-target-deployment-and-iac.md` | Multi-target deployment ADR (contains APRANA) |
| `docs/adr/0001-bremen-product-identity.md` | Feature family definitions |

### Commands run

```
git rev-parse --verify HEAD          → f95737316ff39ed907c73382d626b2c6b7303171
git branch --show-current            → 0029-runtime-model-config-roadmap-rebaseline
git status --short                   → (clean)

grep -n "joblib" requirements.txt pyproject.toml
  → requirements.txt:6:joblib>=1.4
  → pyproject.toml:16:"joblib>=1.4",

grep -R "joblib.load|import joblib|pickle.load|import pickle" src/bremen
  → src/bremen/model_loader.py: lazy import inside load_model_package()
  → src/bremen/modeling.py:9: import joblib (pre-existing research code)
  → src/bremen/modeling.py:81: joblib.load (pre-existing, loads DataFrames not models)
  → src/bremen/mlflow_tracking.py: import joblib (pre-existing)

grep -R "BREMEN_MODEL_|BREMEN_AWS_REGION|BREMEN_SERVICE_ENV" src/bremen
  → src/bremen/config.py: 6 env vars defined (BUCKET, PREFIX, VERSION, MANIFEST_KEY, SERVICE_ENV, AWS_REGION)
  → src/bremen/api/app.py: references BREMEN_MODEL_BUCKET

grep -R "ECR_REPOSITORY|latest|github.sha|tags:" .github/workflows
  → ecr-publish.yml: IMAGE_TAG=${{ github.sha }}, tags: sha + latest
  → quality.yml: ghcr.io tags: latest + github.sha

grep -R "App Runner|apprunner|APRANA|ECS|Fargate" ROADMAP.md infra/terraform
  → ROADMAP.md: APRANA referenced as App Runner shorthand, ECS Fargate is DECIDED primary
  → infra/terraform: ECS Fargate cluster/service/task definition

grep -R "Mahalanobis|wasserstein|reference_stat|fitted|covariance" src/bremen --include="*.py"
  → (no results — no feature implementation in source code)

grep -R "sigma_l1|sigma_l2|Mahalanobis|wasserstein|meanrms|weightedrms" config/ docs/
  → docs/adr/0001-bremen-product-identity.md: 7 feature families listed
  → docs/machine_learning_concept.md: feature families referenced

grep -R "config_version|config_hash|config.*audit|config.*history" src/bremen .project-memory/project_contract.yml
  → (no results — no config versioning exists)
```

---

## Current Inventory

### Present capabilities

| Capability | Evidence | Status |
|-----------|----------|--------|
| HTTP runtime server | `src/bremen/api/server.py` — stdlib `http.server`, 4 routes (`/health`, `/model/version`, `/predictions`, `/predictions/{job_id}`), in-memory job store | ✅ Present (PR 0026) |
| Model source metadata | `src/bremen/api/model_source.py` — `derive_model_source()` reads `CloudConfig`, returns metadata-only dict, no network calls | ✅ Present (PR 0027) |
| Model package validation | `src/bremen/model_package.py` — manifest validation, SHA-256 checksum, path traversal prevention, fail-closed | ✅ Present (PR 0013) |
| Controlled model loader | `src/bremen/model_loader.py` — `load_model_package()`, validation-before-deserialization, lazy joblib import, injectable deserializer | ✅ Present (PR 0028) |
| Cloud config reader | `src/bremen/config.py` — `read_cloud_config()` reads 6 env vars, `CloudConfig` dataclass, no network/AWS SDK | ✅ Present (PR 0020) |
| Local config discovery | `src/bremen/config.py` — `discover_config()` / `load_config()`, YAML/TOML, deterministic order | ✅ Present (PR 0009) |
| ECR publish workflow | `.github/workflows/ecr-publish.yml` — build/push on main, `github.sha` + `latest` tags, scoped IAM credentials | ✅ Present (PR 0022B/C) |
| Dockerfile | `Dockerfile` — python:3.13-slim, no model/H5/data, smoke test only | ✅ Present (PR 0005) |
| Terraform/ECS skeleton | `infra/terraform/*.tf` (7 files) — ECR, S3 versioned, ECS Fargate, IAM, CloudWatch, `desired_count=0` | ✅ Present (PR 0022A) |
| Model artifact lifecycle ADR | `docs/adr/0007-model-artifact-lifecycle.md` — offline training, checksum-verified package, runtime loading rules, prediction output requirements | ✅ Present (PR 0012) |
| API contract | `docs/api_contract.md` — async submit/poll, route definitions | ✅ Present (PR 0019) |
| Prediction output invariant | `.project-memory/project_contract.yml` — requires prediction_id, model_version, model_checksum, feature_schema_version, threshold version/value, qc_status, qc_flags | ✅ Present |

### Missing capabilities

| Capability | Evidence of absence | Priority |
|-----------|-------------------|----------|
| Model package fetch/staging | No S3 download code in `src/bremen/`. `model_source.py` is metadata-only. `model_loader.py` expects local `package_dir`. | High — blocks startup load |
| Startup load / readiness integration | `model_loader.py` exists but is not wired into `server.py` or `app.py`. No startup-time load path. No readiness probe. | High — blocks serving |
| App Runner service config/deploy path | No App Runner Terraform, no App Runner GitHub Action, no `apprunner.tf` | High — blocks proving target |
| Stable App Runner image tag | ECR workflow tags `github.sha` + `latest` only. No `app-runner` or `runtime-latest` mutable tag. | Medium — blocks App Runner auto-deploy |
| H5/preflight metadata gate | No H5 validation code in `src/bremen/api/`. ROADMAP PR 0029 planned but not implemented. | High — blocks inference |
| Preprocessing bridge | No preprocessing integration in API layer. ROADMAP PR 0030 planned but not implemented. | High — blocks inference |
| Inference integration | No `.predict()` call in API layer. ROADMAP PR 0031 planned but not implemented. | High — blocks end-to-end |
| Training/package publishing flow | No training pipeline that produces `bremen.joblib.model_package` artifacts. `src/bremen/modeling.py` is research code, not a release pipeline. | High — blocks first real model |
| DS confirmation of feature reference statistics | No source code implements Mahalanobis/Wasserstein features. No training artifact evidence. | Open question — blocks composite package decision |
| Config validation/edit/apply/history/audit store | No config versioning, no config state history, no config audit. `config.py` is read-only discovery. | Medium — blocks config governance |
| Config version/hash in prediction outputs | No `config_version` or `config_hash` field in prediction output invariant or API schemas. | Medium — blocks audit completeness |

---

## Model Binding Decision

### Confirmed lifecycle architecture

The human-specified lifecycle is **correct architecture**. No blocker found.

```
CI/CD builds runtime image (no model inside)
  → Deployment specifies model identity (BREMEN_MODEL_VERSION)
    → Container starts
      → Runtime reads deployment env/config (read_cloud_config)
        → Runtime fetches/stages model package from S3 [MISSING — future PR]
          → Runtime validates manifest + checksum (model_package.validate_model_package)
            → Runtime crosses joblib.load() boundary once (model_loader.load_model_package)
              → Runtime serves many requests using in-memory model
                → Runtime does NOT reload or hot-swap per request
                  → New model version requires new deployment/restart/rolling replacement
```

**Evidence of correctness:**
- `model_package.py` validates manifest fields, SHA-256 checksum, and path traversal before any artifact access.
- `model_loader.py` calls `validate_model_package()` BEFORE `deserializer()`. Tests prove deserializer is never invoked on validation failure (PR 0028 precommit-review).
- `model_loader.py` joblib import is lazy (inside function body, not module top-level).
- `model_source.py` is metadata-only — no fetch, no load, no network.
- `server.py` does not import `model_loader` — no request-time loading.
- ADR-0007 states: "Runtime never builds, retrains, mutates, or overwrites model artifacts."
- `project_contract.yml` states: "Joblib model packages are controlled artifacts; joblib must be loaded only from checksum-verified model packages."

**Missing piece:** The fetch/staging step between `read_cloud_config()` (which knows bucket/prefix/version) and `validate_model_package()` (which expects a local directory) does not exist yet. This is the primary runtime gap.

### Authoritative model selector

**Decision: Combination of `BREMEN_MODEL_VERSION` + immutable checksum.**

| Selector | Role | Authority |
|----------|------|-----------|
| `BREMEN_MODEL_VERSION` | Deployment-time identity — human/operator selects which model version to deploy | Primary selector (env var, set at deployment) |
| `model_checksum` (SHA-256) | Immutable trust anchor — computed at training-pipeline boundary, verified at runtime | Trust verification (manifest field, verified by `validate_model_package`) |
| `feature_schema_version` | Compatibility gate — must match between package and runtime | Compatibility check (manifest field) |
| Stable deployment tag | Operational convenience — maps a human-readable name to a version | Optional alias (not authoritative) |

**Rationale:** `BREMEN_MODEL_VERSION` alone is not sufficient because it is a mutable label — a version string could be reused. The checksum is the immutable ground truth. The runtime must verify that the fetched package's checksum matches the manifest's declared checksum, and the manifest's checksum must have been computed at the training-pipeline trust boundary (per ADR-0007). `BREMEN_MODEL_VERSION` selects *which* package to fetch; the checksum verifies *that* the fetched package is authentic.

### Audit fields required in prediction outputs

Per `project_contract.yml` and ADR-0007, every prediction result MUST include:

| Field | Source | Already required? |
|-------|--------|-------------------|
| `prediction_id` | Runtime-generated UUID | ✅ Yes (contract) |
| `model_version` | Model package manifest | ✅ Yes (contract + ADR-0007) |
| `model_checksum` | Model package manifest (SHA-256) | ✅ Yes (contract + ADR-0007) |
| `feature_schema_version` | Model package manifest | ✅ Yes (contract + ADR-0007) |
| `threshold_version` | Model package manifest | ✅ Yes (contract + ADR-0007) |
| `threshold_value` | Model package manifest | ✅ Yes (contract + ADR-0007) |
| `qc_status` | Runtime QC gate | ✅ Yes (contract + ADR-0007) |
| `qc_flags` | Runtime QC gate | ✅ Yes (contract + ADR-0007) |
| `model_package_identity` | Composite of model_version + checksum | **NEW — recommended addition** |
| `config_version` / `config_hash` | Config state at decision time | **NEW — required if config affects decision behavior** |

**Decision:** `model_package_identity` should be a composite field (`model_version` + `:` + `model_checksum`[:12]) for human-readable audit. `config_version`/`config_hash` must be added to the prediction output invariant once config governance is implemented, because config (thresholds, QC criteria, feature parameters) affects decision behavior. This requires a `project_contract.yml` amendment and ADR update.

---

## Joblib Boundary Decision

### Where `joblib.load()` belongs

**Decision: `joblib.load()` belongs in exactly one place: `src/bremen/model_loader.py::load_model_package()`, inside the default-deserializer fallback branch.**

**Evidence:**
- `model_loader.py` line 88: `from joblib import load as _joblib_load` — lazy import inside function body.
- `model_loader.py` is the ONLY module in `src/bremen/api/` or `src/bremen/model_loader.py` that imports joblib.
- `src/bremen/modeling.py` imports joblib (line 9) and calls `joblib.load` (line 81), but this is **pre-existing research code** that loads preprocessing DataFrames, not model artifacts. It is not in the API/runtime path.
- `src/bremen/mlflow_tracking.py` imports joblib — pre-existing research code, not in runtime path.
- `src/bremen/model_package.py` has NO joblib import — it validates without deserializing.
- `src/bremen/api/server.py` has NO joblib import.
- `src/bremen/api/model_source.py` has NO joblib import.

### When it runs

**Decision: `joblib.load()` runs exactly once during startup/readiness, never per-request.**

The lifecycle:
1. Container starts.
2. Runtime reads `BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_VERSION` from env.
3. Runtime fetches model package from S3 to local staging directory. [MISSING — future PR]
4. Runtime calls `validate_model_package(staging_dir)` — manifest + checksum + path safety. [EXISTS]
5. Runtime calls `load_model_package(staging_dir)` — validation passes, then `joblib.load()` executes once. [EXISTS]
6. Runtime holds `LoadedModelPackage` in memory.
7. Runtime serves requests using the in-memory model object.
8. Runtime does NOT call `joblib.load()` again for any request.
9. New model version → new deployment → new container → steps 1-6 repeat.

### Why it is not request-time

1. **Security:** `joblib.load()` uses pickle deserialization, which can execute arbitrary code. ADR-0007 explicitly states this. Loading per-request would multiply the attack surface.
2. **Performance:** Model deserialization is expensive (seconds). Per-request loading would make the API unusable.
3. **Auditability:** A model loaded once at startup has a single, verifiable identity. Per-request loading would make it impossible to guarantee which model produced which prediction.
4. **Operational safety:** Hot-swapping models in-process risks serving predictions from a partially-loaded or inconsistent model state. Rolling replacement (new container) is the safe update mechanism.

### What must validate before `joblib.load()`

Per `model_loader.py` and `model_package.py`, the following must pass BEFORE deserialization:

1. **Package directory exists** — `ModelPackageNotFoundError` if missing.
2. **Manifest exists and is valid JSON** — `ModelPackageManifestError` if invalid.
3. **Manifest is a dict** — `ModelPackageManifestError` if not.
4. **All required manifest fields present and correctly typed** — `ModelPackageManifestError` if missing/wrong type.
5. **`artifact_type` equals `bremen.joblib.model_package`** — `ModelPackageManifestError` if mismatch.
6. **`model_checksum` is a valid 64-char hex string** — `ModelPackageManifestError` if invalid format.
7. **`model_filename` is not absolute** — `ModelPackageSecurityError` if absolute.
8. **`model_filename` does not escape package directory** — `ModelPackageSecurityError` if traversal detected.
9. **Model artifact file exists** — `ModelPackageNotFoundError` if missing.
10. **Computed SHA-256 matches manifest `model_checksum`** — `ModelPackageChecksumError` if mismatch.

Only after all 10 checks pass does `deserializer(str(summary.model_path))` execute.

---

## Model Package Composition / Training Inventory

### Does current repo evidence prove classifier-only package is sufficient?

**No.** The repo does not contain evidence that proves classifier-only is sufficient.

**Evidence:**
- `model_package.py` manifest schema requires: `artifact_type`, `model_version`, `model_checksum`, `model_filename`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`. This is a single-artifact contract — one `model_filename`, one `model_checksum`.
- `model_loader.py` `LoadedModelPackage.model` is typed `Any`, which is composite-compatible. The PR 0028 precommit-review explicitly notes: "Composite package compatibility preserved: LoadedModelPackage.model: Any (not classifier, not Pipeline, not sklearn type)."
- `modeling.py` uses `sklearn.pipeline.Pipeline` with `StandardScaler` + `LogisticRegression`. A Pipeline bundles preprocessing (scaling) into the model artifact, but this is research code, not the controlled release pipeline.
- No `bremen_v1.joblib` model package exists in the repo. No training pipeline produces one.

### Does current repo evidence show fitted reference-statistics artifact is required?

**Cannot determine from repo evidence. This is an open DS/inventory question.**

**Evidence:**
- `docs/adr/0001-bremen-product-identity.md` lists 7 feature families: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
- `docs/machine_learning_concept.md` references Mahalanobis and Wasserstein features but does not describe their computation pipeline or whether fitted reference statistics (covariance matrices, reference distributions) are required.
- No source code in `src/bremen/` implements any of these feature families (`grep` returned no results).
- No training config or feature extraction code exists in the runtime path.
- Mahalanobis distance requires a fitted covariance matrix and mean vector from reference data. Wasserstein distance may require a reference distribution. These are typically fitted at training time and required at inference time. **But the repo does not confirm this.**

### Decision

**If fitted reference statistics are required (to be confirmed by DS):**

The model package must become composite and atomic:
- Classifier artifact (joblib)
- Feature extractor / reference-statistics artifact (joblib or separate format)
- Shared `model_version`
- Shared `feature_schema_version`
- One manifest with checksums for all artifacts
- One trust boundary (manifest validation covers all artifacts)

The current `model_package.py` manifest schema supports only one `model_filename` / `model_checksum` pair. A composite package would require manifest schema evolution to support multiple artifacts (e.g., `artifacts: [{name, filename, checksum, role}]`).

**If not required (to be confirmed by DS):**

Classifier-only package may remain sufficient. The current single-artifact contract is adequate.

### Required follow-up

- **DS confirmation required** before preprocessing/inference PRs (ROADMAP PR 0030/0031).
- **New ADR required** if composite package is needed — this is a model package contract change, not a runtime change.
- **ROADMAP amendment required** to add a DS/inventory PR before preprocessing.
- The `model_loader.py` `LoadedModelPackage.model: Any` type already accommodates composite packages at the loader level. The constraint is in `model_package.py`'s manifest schema.

---

## Runtime Target Decision

### Classification: Acceptable operational pivot, requires ADR/roadmap amendment

The human directive to use App Runner as a near-term proving target and defer ECS Fargate is an **acceptable operational pivot**. It is not a blocker, but it requires formal ADR and ROADMAP amendment before any App Runner implementation.

### App Runner proving target

**Decision: App Runner is the near-term proving/testing target.**

- App Runner provides faster operational launch (source-to-code or image-based deployment, auto-scaling, built-in load balancer, no VPC/subnet management).
- Suitable for smoke testing, integration validation, and proving the runtime model binding lifecycle end-to-end.
- Does not replace ECS Fargate as the primary production target.

### ECS Fargate remains later/primary

**Decision: ECS Fargate remains the long-term primary production-grade target.**

- The existing Terraform skeleton (`infra/terraform/ecs.tf`) is retained but not prioritized.
- ECS work moves later in the roadmap sequence.
- No evidence found that ECS should be abandoned. The Terraform skeleton is valid scaffolding.
- `G-API-2` (DECIDED: ECS Fargate) remains the primary production target decision. App Runner is an additional near-term target, not a replacement.

### APRANA retirement

**Decision: APRANA is retired entirely. APRANA is not App Runner.**

- ADR-0006 refers to "APRANA" as an "UNVERIFIED" placeholder. The ROADMAP.md "App Runner / APRANA clarification" section states "APRANA was a planning shorthand for AWS App Runner." This conflation is incorrect and must be corrected.
- APRANA must not be carried forward in any form. The term must be removed from ADR-0006 and ROADMAP.md.
- App Runner is a real AWS service. APRANA was an unverified name that should never have been used as a synonym.
- **Which PR should retire APRANA:** The immediate roadmap/ADR amendment PR (proposed PR 0030, see below).

### Where to record App Runner as short-term proving target

1. **ROADMAP.md** — Add App Runner as near-term proving target in the Platform Readiness Track. Move ECS Fargate to later sequence. Remove APRANA references.
2. **New ADR** — ADR-0008 (or next available number): "Runtime Target Pivot: App Runner Proving Target" — records the decision, rationale, and relationship to ECS Fargate.
3. **ADR-0006** — Amend or supersede the APRANA section. Remove "APRANA" language entirely.
4. **Gate register** — Add a new gate `G-DEPLOY-1` (or similar) for "App Runner vs ECS Fargate deployment path" if needed, or record App Runner as an operational sub-decision under `G-API-2`.

### Which ADR/gate/roadmap entries must change

| Entry | Current state | Required change |
|-------|--------------|-----------------|
| ROADMAP.md "App Runner / APRANA clarification" | Conflates APRANA with App Runner | Remove APRANA. Record App Runner as near-term proving target. Record ECS Fargate as later/primary. |
| ROADMAP.md PR 0023 | "APRANA / App Runner evaluation — Deferred candidate track" | Replace with "App Runner proving target — near-term CI/CD and deploy path" |
| ROADMAP.md Platform Readiness Track | ECS Fargate is the only runtime target | Add App Runner as near-term, move ECS later |
| ADR-0006 | Contains "APRANA (UNVERIFIED)" section | Remove APRANA section entirely. Add App Runner as near-term target. |
| G-API-2 | DECIDED: ECS Fargate | Amend to: "ECS Fargate (primary/long-term), App Runner (near-term proving)" |
| New ADR-0008 | Does not exist | Create: "Runtime Target Pivot: App Runner Proving Target" |

### Whether next PR should be App Runner CI/CD or roadmap/ADR amendment first

**Decision: Roadmap/ADR amendment first.**

The roadmap and ADRs are the source of truth. Implementation must follow architecture decisions, not precede them. The amendment PR is lightweight (docs only), fast, and unblocks all subsequent App Runner work.

---

## CI/CD Image Tag Decision

### Current image tagging behavior

**Evidence from `.github/workflows/ecr-publish.yml`:**

```yaml
IMAGE_TAG: ${{ github.sha }}
# Tags:
#   ${IMAGE_URI}:${IMAGE_TAG}   (immutable SHA tag)
#   ${IMAGE_URI}:latest          (mutable convenience tag)
```

- **Immutable SHA tag:** `github.sha` — ✅ Present, correct for audit.
- **Mutable `latest` tag:** Present — used for human convenience, not deploy trigger.
- **No stable App Runner-specific tag:** Missing.

**Evidence from `.github/workflows/quality.yml` (GHCR):**
- Same pattern: `ghcr.io/eos-dx/bremen:latest` + `ghcr.io/eos-dx/bremen:${{ github.sha }}`.

### Desired image policy

| Tag | Mutability | Purpose | Deploy trigger? |
|-----|-----------|---------|-----------------|
| `github.sha` (full SHA) | Immutable | Audit, rollback, traceability | No (reference only) |
| `app-runner` | Mutable | App Runner auto-deploy source | **Yes** — App Runner watches this tag |
| `latest` | Mutable | Human convenience, local dev | No |

**Decision:**
- **Add a stable mutable tag `app-runner`** to the ECR workflow. App Runner's auto-deploy feature watches a specific image tag. When a new image is pushed with that tag, App Runner triggers a new deployment. This provides controlled, predictable deploys.
- **Keep the immutable SHA tag** `github.sha` for audit and rollback. Every deployed image can be traced to an exact commit.
- **`latest` should be preserved** for human convenience and local development but should NOT be the App Runner deploy trigger. `latest` is ambiguous in a multi-target environment.
- **ECR workflow needs a follow-up PR** to add the `app-runner` tag. This is a CI/CD change, not a runtime change.

### Tag push sequence (future PR)

```
docker build \
  -t "${IMAGE_URI}:${IMAGE_TAG}" \     # immutable SHA
  -t "${IMAGE_URI}:app-runner" \       # mutable, App Runner deploy trigger
  -t "${IMAGE_URI}:latest" \           # mutable, human convenience
  .

docker push "${IMAGE_URI}:${IMAGE_TAG}"
docker push "${IMAGE_URI}:app-runner"
docker push "${IMAGE_URI}:latest"
```

**No AWS account IDs, registry URLs, access keys, or secrets are recorded here.**

---

## Config Governance Decision

### Problem statement

Config is not model. Config (thresholds, QC criteria, feature parameters, preprocessing settings) affects decision behavior but has different lifecycle requirements than model artifacts:
- Config may need runtime editing/apply without restart.
- Config changes must be versioned, timestamped, auditable, and reproducible.
- Historical config states must be queryable for audit.
- Prediction records must identify which config version was active.

### Current state

- `src/bremen/config.py` provides read-only discovery (`discover_config`, `load_config`) and cloud config reading (`read_cloud_config`).
- No config validation beyond syntax (YAML/TOML parsing).
- No config versioning, no state history, no audit store.
- No config editing API.
- `G-CFG-1` (build in-house vs. adopt existing config-management product) is OPEN.
- ROADMAP PR 0024 (Config editing surface) is BLOCKED on `G-CFG-1`.

### Future config architecture (gates and placement, not full design)

**Decision: Config governance requires a new ADR and gate before implementation.**

#### Config change classification

| Config change class | Runtime apply without restart? | Requires redeploy? | Forbidden in runtime UI? |
|---------------------|-------------------------------|-------------------|-------------------------|
| **Class A: Operational parameters** (log level, health check interval, max concurrent jobs) | Yes | No | No |
| **Class B: Decision-adjacent parameters** (thresholds, QC criteria versions) | Yes, with validation | No, but requires audit record | Editable with approval workflow |
| **Class C: Model-binding parameters** (model version, model bucket, feature schema) | No | Yes — requires restart/rolling replacement | Yes — must be deployment-time only |
| **Class D: Structural parameters** (API routes, auth, network) | No | Yes | Yes |

**Rationale:**
- Class A changes are safe to apply at runtime because they do not affect decision behavior.
- Class B changes affect decision behavior but can be applied safely if validated and audited. The in-memory model is not affected; only the decision threshold/criteria changes.
- Class C changes affect which model is loaded. These must not be changed at runtime because the model is loaded once at startup. Changing `BREMEN_MODEL_VERSION` at runtime without restart would create a mismatch between the declared version and the loaded model.
- Class D changes are structural and must not be editable at runtime.

#### Config state history / audit store

**Decision: A database (DynamoDB or equivalent) is likely needed for config state history.**

- Every applied config state must be versioned, timestamped, and auditable.
- Historical states must be queryable: "what config was active when prediction X was made?"
- Prediction/audit records must include `config_version` or `config_hash`.
- DynamoDB is a natural fit for AWS-native, low-latency, event-driven config state storage.
- This is a future architecture decision — do not design the full system now.

#### Required gates before implementation

| Gate | Question | Must be decided before |
|------|----------|----------------------|
| `G-CFG-1` (existing, OPEN) | Build in-house vs. adopt existing config-management product | Config editing surface PR |
| `G-CFG-2` (new, proposed) | Config state history store: DynamoDB vs. other | Config history/audit PR |
| `G-CFG-3` (new, proposed) | Config validation schema: JSON Schema vs. Pydantic vs. custom | Config validation PR |

#### Roadmap placement

**Decision: Config governance belongs AFTER inference integration, not before.**

- Inference integration (PR 0031 in current roadmap) is the critical path to a working product.
- Config governance is important for audit and operational maturity but is not on the critical path to first prediction.
- However, `config_version`/`config_hash` in prediction outputs should be designed now (as a placeholder field) and populated later when config governance is implemented.
- Config governance PRs should be sequenced after inference integration and before production readiness.

---

## Roadmap Drift Assessment

| Prior decision | Current pressure | Drift classification | Required action |
|---------------|-----------------|---------------------|-----------------|
| G-API-2 DECIDED: ECS Fargate as primary target | Human directive: App Runner as near-term proving target | **Acceptable operational pivot** — requires ADR/roadmap amendment | Amend G-API-2 to record App Runner as near-term, ECS as long-term. Create ADR-0008. |
| ROADMAP PR 0023: "APRANA / App Runner evaluation — Deferred" | Human directive: App Runner is near-term proving target, APRANA retired | **Drift — APRANA must be removed** | Replace PR 0023 with App Runner proving target. Remove all APRANA language from ROADMAP and ADR-0006. |
| ADR-0006: "APRANA (UNVERIFIED)" section | Human directive: APRANA retired entirely | **Drift — APRANA must be removed** | Amend ADR-0006 to remove APRANA section. |
| ROADMAP next sequence: PR 0029 (H5 gate) → PR 0030 (preprocessing) → PR 0031 (inference) | Missing: model fetch/staging, startup load, App Runner deploy path | **Drift — sequence gaps** | Insert model fetch/staging PR and App Runner deploy PR before H5 gate. |
| Model package contract: single artifact (one `model_filename`) | Open question: composite package may be needed for reference statistics | **Potential drift — pending DS confirmation** | Add DS/inventory PR before preprocessing. Amend model package contract if composite needed. |
| Config governance: G-CFG-1 OPEN, PR 0024 BLOCKED | Human directive: config needs validated editing, history, audit | **Drift — config governance under-scoped** | Add new gates G-CFG-2, G-CFG-3. Add config governance ADR. Sequence after inference. |
| Prediction output invariant: no `config_version`/`config_hash` | Config affects decision behavior | **Drift — audit incomplete** | Amend prediction output invariant to include `config_version`/`config_hash` (placeholder until config governance implemented). |
| ECR workflow: `github.sha` + `latest` tags only | App Runner needs stable mutable deploy tag | **Drift — missing App Runner tag** | Add `app-runner` tag to ECR workflow in follow-up CI/CD PR. |
| Terraform skeleton: ECS Fargate only | App Runner needs separate Terraform or service config | **Acceptable — ECS skeleton retained for later** | Add App Runner Terraform in future infra PR. Do not remove ECS skeleton. |

---

## Proposed Next 8-10 PRs

| PR | Branch | Title | Objective | Key architectural decision | Likely files | Non-goals | Type | Blocks inference? |
|----|--------|-------|-----------|---------------------------|-------------|-----------|------|-------------------|
| 0030 | `0030-roadmap-adr-apprunner-pivot` | Roadmap and ADR amendment: App Runner proving target, APRANA retirement, model binding lifecycle, config governance gates | Record all architectural decisions from this rebaseline as formal ADR/ROADMAP amendments before any implementation | App Runner near-term, ECS later/primary, APRANA retired, model binding lifecycle confirmed, config governance gates added | `ROADMAP.md`, `docs/adr/0006-multi-target-deployment-and-iac.md` (amend), `docs/adr/0008-runtime-target-apprunner-proving.md` (new), `docs/adr/0009-config-governance.md` (new) | No source code, no CI/CD, no Terraform, no Dockerfile changes | Architecture/docs | No |
| 0031 | `0031-ecr-apprunner-image-tag` | ECR workflow: add stable App Runner image tag | Add `app-runner` mutable tag alongside existing SHA + latest tags | Stable mutable tag for App Runner auto-deploy, immutable SHA for audit | `.github/workflows/ecr-publish.yml`, `tests/test_bremen_ecr_publish_workflow.py` | No Terraform, no App Runner service creation, no runtime code | CI/CD | No |
| 0032 | `0032-model-package-fetch-staging` | Model package fetch and staging from S3 | Implement S3 download of model package to local staging directory using CloudConfig | Fetch is separate from validation and loading; staging directory is ephemeral; no joblib in this PR | `src/bremen/model_fetcher.py` (new), `tests/test_bremen_model_fetcher.py` (new) | No joblib.load, no inference, no H5 reads, no App Runner config | Runtime code | Yes (prerequisite) |
| 0033 | `0033-startup-model-load-readiness` | Startup model loading and readiness probe | Wire model_fetcher + model_loader into server startup; add readiness endpoint that returns 503 until model is loaded | Model loads once at startup; readiness gate prevents traffic to unready containers; no per-request loading | `src/bremen/api/server.py`, `src/bremen/api/app.py`, `src/bremen/api/schemas.py`, `tests/test_bremen_api_server.py` | No inference, no H5 reads, no hot-swap | Runtime code | Yes (prerequisite) |
| 0034 | `0034-apprunner-terraform-skeleton` | App Runner Terraform skeleton | Add App Runner service Terraform alongside existing ECS skeleton | App Runner uses ECR image source, auto-deploy on `app-runner` tag, health check endpoint | `infra/terraform/apprunner.tf` (new), `infra/terraform/variables.tf` (modify), `infra/terraform/outputs.tf` (modify), `infra/terraform/README.md` (modify) | No ECS changes, no apply, no runtime code | Infra skeleton | No |
| 0035 | `0035-ds-feature-inventory` | DS feature family inventory and model package composition decision | DS confirms whether Mahalanobis/Wasserstein features require fitted reference statistics; decide classifier-only vs composite package | If composite: amend model_package.py manifest schema; if classifier-only: confirm current contract | `docs/adr/0010-model-package-composition.md` (new, if composite), `docs/feature_inventory.md` (new), possibly `src/bremen/model_package.py` (if manifest schema evolves) | No inference, no training pipeline, no H5 reads | Model/training inventory | Yes (prerequisite for preprocessing) |
| 0036 | `0036-h5-preflight-metadata-gate` | H5/preflight metadata gate | Validate H5 metadata, target/control consistency before any downstream action | H5 validation is a hard gate; no prediction without valid metadata | `src/bremen/api/preflight.py` (new), `src/bremen/api/app.py`, `tests/test_bremen_api_preflight.py` (new) | No inference, no model loading, no preprocessing | Runtime code | Yes (prerequisite) |
| 0037 | `0037-preprocessing-bridge` | Preprocessing bridge | Connect approved preprocessing path to API without training or clinical claims | Preprocessing produces feature vectors matching `feature_schema_version` | `src/bremen/api/preprocessing.py` (new), `src/bremen/api/app.py`, `tests/test_bremen_api_preprocessing.py` (new) | No inference, no training, no clinical claims | Runtime code | Yes (prerequisite) |
| 0038 | `0038-inference-integration` | Inference pipeline integration | First end-to-end inference: model load + preprocessing + predict + audit fields | Inference uses in-memory model; output includes all audit fields; no hot-swap | `src/bremen/api/inference.py` (new), `src/bremen/api/app.py`, `src/bremen/api/schemas.py`, `tests/test_bremen_api_inference.py` (new) | No training, no clinical claims, no model reloading | Runtime code | No (this IS inference) |
| 0039 | `0039-config-governance-adr-and-gates` | Config governance ADR and gate decisions | Close G-CFG-1, G-CFG-2, G-CFG-3; define config validation, history store, and audit architecture | Config is versioned; DynamoDB or equivalent for state history; config_version in prediction outputs | `docs/adr/0009-config-governance.md` (or amend), `ROADMAP.md`, `.project-memory/project_contract.yml` (amend prediction invariant) | No config editing UI, no runtime config apply implementation | Architecture/docs | No |

---

## Required ADR / Roadmap Amendments

### 1. New ADR-0008: Runtime Target Pivot — App Runner Proving Target

**Status**: Proposed (to be created in PR 0030)
**Content**:
- App Runner is the near-term proving/testing target.
- ECS Fargate remains the long-term primary production target.
- ECS Terraform skeleton is retained but deprioritized.
- App Runner uses ECR image source with `app-runner` tag for auto-deploy.
- Health check endpoint (`/health`) serves as App Runner health check.
- Readiness endpoint (new, from PR 0033) serves as App Runner readiness gate.

### 2. Amend ADR-0006: Remove APRANA

**Action**: Remove the "APRANA (UNVERIFIED)" section entirely. Replace with reference to ADR-0008 for App Runner decision. Remove all "APRANA" language.

### 3. New ADR-0009: Config Governance

**Status**: Proposed (to be created in PR 0030, detailed in PR 0039)
**Content**:
- Config is not model. Config has its own lifecycle.
- Config change classes (A/B/C/D) as defined above.
- Config state must be versioned, timestamped, auditable, reproducible.
- Config state history store (DynamoDB or equivalent) — gate G-CFG-2.
- Config validation schema (JSON Schema / Pydantic / custom) — gate G-CFG-3.
- `config_version` / `config_hash` must be included in prediction outputs.

### 4. Amend ROADMAP.md

- Remove "App Runner / APRANA clarification" section. Replace with "Runtime target decision" section referencing ADR-0008.
- Amend PR 0023 from "APRANA / App Runner evaluation" to "App Runner proving target — CI/CD and deploy path".
- Amend G-API-2 to: "ECS Fargate (primary/long-term), App Runner (near-term proving)".
- Add new gates: G-CFG-2 (config state history store), G-CFG-3 (config validation schema).
- Update "Next Execution Sequence" to reflect proposed PRs 0030-0039.
- Add model binding lifecycle confirmation (reference this rebaseline artifact).
- Add config governance to prediction output invariant (placeholder `config_version`/`config_hash`).

### 5. Amend `.project-memory/project_contract.yml` (in PR 0030 or 0039)

- Add `config_version` and `config_hash` to the prediction output invariant:
  "Every prediction result MUST include: prediction_id, model_version, model_checksum, feature_schema_version, threshold version/value, qc_status, qc_flags, config_version, config_hash."
- Add config governance safety invariant:
  "Config changes that affect model binding (Class C) must not be applied at runtime; they require restart/redeployment."

### 6. New ADR-0010 (conditional): Model Package Composition

**Status**: Proposed (to be created in PR 0035, only if DS confirms composite package is needed)
**Content**: Composite model package contract with multiple artifacts, shared version/schema, single trust boundary.

---

## Immediate Next PR Recommendation

**One PR only: PR 0030 — `0030-roadmap-adr-apprunner-pivot`**

**Branch**: `0030-roadmap-adr-apprunner-pivot`

**Why**: The roadmap and ADRs are the source of truth for all subsequent implementation. They are currently out of alignment with the human directive on three critical points: (1) App Runner is not recorded as the near-term proving target, (2) APRANA has not been retired, and (3) config governance is not scoped. No implementation PR should proceed until these architectural decisions are formally recorded. This PR is docs-only (ROADMAP.md, ADRs), carries zero runtime risk, and unblocks all subsequent work.

**Scope**: ROADMAP.md amendment, ADR-0006 amendment (remove APRANA), new ADR-0008 (App Runner proving target), new ADR-0009 (config governance skeleton). No source code, no CI/CD, no Terraform, no Dockerfile, no dependencies.

---

## Blockers

None.

All hard questions have been answered with direct evidence:
- App Runner proving target vs ECS primary/later: **Classified** — acceptable operational pivot, requires ADR/roadmap amendment.
- Current image tagging behavior: **Determined** — `github.sha` + `latest` in `ecr-publish.yml`; no App Runner-specific tag.
- Model package contract classifier-only vs composite-compatible: **Determined** — current contract is single-artifact; `model_loader.py` is composite-compatible at the loader level; manifest schema is the constraint. Composite need is an open DS question, not a blocker for the amendment PR.
- Config governance ADR/roadmap amendment: **Determined** — required, new ADR-0009 and gates G-CFG-2/G-CFG-3 proposed.

---

## Warnings

1. **PR 0022C precommit-review not found at expected path.** The file `.project-memory/pr/0022c-ecr-credentials-hotfix/reviews/precommit-review.yml` was listed as a required read but returned "not found." The ROADMAP.md confirms PR 0022C was completed ("ECR workflow credentials hotfix / scoped publisher credentials"). The ECR workflow file confirms scoped IAM credentials are in use (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from secrets). This does not block the rebaseline but the missing review artifact should be investigated.

2. **Pre-existing joblib usage in `src/bremen/modeling.py` and `src/bremen/mlflow_tracking.py`.** These modules import joblib and call `joblib.load()` outside the controlled `model_loader.py` boundary. This is pre-existing research code, not in the API/runtime path. However, if these modules are ever imported by the runtime server, the controlled boundary would be bypassed. A future hardening PR should ensure the runtime server never imports `modeling.py` or `mlflow_tracking.py`.

3. **`src/bremen/modeling.py` loads DataFrames via `joblib.load()`.** While this loads preprocessing DataFrames (not model artifacts), it still uses pickle deserialization. If preprocessing DataFrames are ever loaded at runtime, they should go through a controlled boundary similar to `model_loader.py`.

4. **Dockerfile does not install private dependencies.** The Dockerfile comment states "Private dependencies (xrd-preprocessing, container) are installed by the CI workflow." The ECR workflow passes `BREMEN_CI_GITHUB_TOKEN` as a build arg. This means the ECR-published image may differ from a locally-built image. This is acceptable for CI smoke testing but must be verified before production deployment.

5. **Terraform `container_image_tag` defaults to `latest`.** The ECS task definition uses `var.container_image_tag` which defaults to `"latest"`. If ECS is ever activated, this should be changed to an immutable SHA tag for production. This is acceptable for the skeleton (desired_count=0) but is a production-readiness concern.

6. **No `config_version` or `config_hash` exists anywhere in the codebase.** The prediction output invariant in `project_contract.yml` does not include config versioning. This is an audit gap that must be addressed before production readiness, but does not block the immediate amendment PR.

---

## Boundary Confirmations

- No source code was modified.
- No tests were modified.
- No ROADMAP.md was modified.
- No ADRs were modified.
- No GitHub workflows were created or modified.
- No Terraform was modified.
- No Dockerfile was modified.
- No dependencies were installed.
- No `git add`, `git commit`, `git push`, or `gh pr create` was executed.
- No Docker, Terraform, or AWS commands were executed.
- No AWS account IDs, registry URLs, access keys, or secrets are recorded in this artifact.
- No clinical validation is claimed.
- No inference implementation is claimed.
- No DS/training facts were guessed. Open questions are explicitly marked.
- The only file written is `.project-memory/architecture/runtime-model-config-roadmap-rebaseline.md`.
- The only directory created is `.project-memory/architecture/`.
