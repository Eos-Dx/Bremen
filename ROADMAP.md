# Bremen Roadmap

**Track**: Product Track + Platform Readiness Track (parallel).

No hard calendar dates — use sequence and dependencies.

## Completed foundation PRs

- PR-0001 — Agent workflow foundation
- PR-0002 — Planning/identity cleanup
- PR-0003 — Full Aramis-to-Bremen alignment
- PR-0004 — Roadmap quality/docker/entrypoint planning
- PR-0005 — Docker/CI/Sonar skeleton
- PR-0006 — Coverage/cache
- PR-0007 — GHCR Docker smoke publish
- PR-0008 — Unified Bremen entrypoint
- PR-0009 — Config discovery/loading
- PR-0012 — Model artifact lifecycle ADR + runtime deployment gate closure. ADR-0007 formalizes offline training, controlled package, runtime loading, S3 storage, and security boundaries. G-API-1, G-API-2, G-INFRA-1 closed as DECIDED.
- PR-0019 — API contract + async microservice skeleton. Creates `docs/api_contract.md`, `src/bremen/api/` with route-shaped handlers and in-memory job store.
- PR-0020 — Cloud-aware config sourcing. Extends `src/bremen/config.py` with `read_cloud_config()` and `CloudConfig` dataclass reading `BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_VERSION` from environment.
- PR-0021 — Container dependency hygiene. Removes editable local-path dependencies from `requirements.txt`. Replaces with reproducible git URL pin at `feat/v0_3`. G-DEP-1 remains OPEN.
- PR-0022A — Terraform AWS runtime skeleton. `infra/terraform/` with ECR, S3 versioned bucket, ECS Fargate cluster/service/task definition, CloudWatch, scoped IAM roles. Not yet applied.
- PR-0022B — ECR publish workflow. `.github/workflows/ecr-publish.yml` building and pushing Docker image to ECR on push to main.
- PR-0022C — ECR workflow credentials hotfix / scoped publisher credentials. Uses scoped IAM user credentials via secrets for ECR authentication (interim operational path; OIDC is the planned long-term approach).

## Product Track sequence

Product core before infrastructure wrappers.

1. **Product identity / document separation baseline** — This cascade (0011A/B). ADR-0001 and ADR-0002, architecture baseline, and updated roadmap.
2. **YAML/PDF clinical report template** — Public + internal, per Bremen Assembly plan v1 Phase 1 (currently overdue).
3. **YAML training config template** — Per Bremen Assembly plan v1 Phase 1 (currently overdue).
4. **Bremen feature-family implementation/verification** — For all seven families: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
5. **`train_classifier.py` pipeline + QC criteria document + `bremen_v1.joblib` reproducible model package** — The first controlled model release.
6. **GitHub demo** — Real H5 patients, end-to-end prediction shown.
7. **platform deployment plan document** — Documented deployment architecture.
8. **Safety preflight gates** — H5 metadata validation, target/control consistency, config integrity.
9. **Matador boundary / system-of-record adapter skeleton** — Platform integration contract.
10. **Workflow wrapper / decision-support output** — First end-to-end workflow (preprocess → QC → inference → report).
11. **Model artifact/version reporting** — Artifact management.
12. **Release readiness / operator notes** — Final preparation.

> **Note**: Feature family implementation (`sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`) is covered by PR 0034's Bremen training pipeline, not by a separate unscoped PR.

Items 8–12 must not be silently dropped, but must appear after items 1–7 because there is no model, API surface, or workflow yet for them to gate.

## Platform Readiness Track (parallel to Product Track)

| PR | Description | Depends on |
|----|-------------|------------|
| PR 0019 | **API contract + microservice skeleton** — Delegated from ADR-0003. Creates `docs/api_contract.md` + non-functional stub routes. | Gates G-API-1 and G-API-2 explicitly closed first |
| PR 0020 | **Cloud-aware config sourcing** — Delegated from ADR-0004. Extends `src/bremen/config.py` without breaking PR 0009 tests. | PR 0019 |
| PR 0021 | **Container dependency hygiene** — Delegated from ADR-0005. Fixes `requirements.txt` local-path defect immediately (no dependency). Re-pin itself is separately event-triggered via G-DEP-1. | None |
| PR 0022A | **Terraform AWS runtime skeleton** — Delegated from ADR-0006. ECR, S3 versioned bucket, ECS Fargate, CloudWatch, scoped IAM. Not yet applied. | G-INFRA-1 and G-API-2 closed |
| PR 0022B | **ECR publish workflow** — Docker image build/push to ECR on main push. | Terraform skeleton exists |
| PR 0022C | **ECR workflow credentials** — Scoped IAM user credentials as interim auth path. | PR 0022B |
| PR 0023 | **App Runner proving target** — Near-term CI/CD and deploy path for App Runner proving target. See ADR-0008 for full decision. | Platform access confirmed |
| PR 0024 | **Config editing surface** — BLOCKED on G-CFG-1. Not date-bound. Scheduled only after Product Track's core classifier work (operator-convenience, not product-critical path). | G-CFG-1, Product Track core classifier |

## Decision Gate Register

| Gate ID | Question | Trigger type | Recommended default | Status | Decided value |
|---------|----------|-------------|-------------------|--------|---------------|
| G-API-1 | Sync vs. async request/response | Date-bound (before PR 0019) | Async submit-then-poll | DECIDED | async submit → `job_id` → poll |
| G-API-2 | AWS compute target (ECS Fargate vs. Lambda-container vs. EKS) | Date-bound (before PR 0019, PR 0022) | ECS Fargate | DECIDED | ECS Fargate (primary/long-term), App Runner (near-term proving) |
| G-CFG-1 | Build in-house vs. adopt existing config-management product | Date-bound (before PR 0024) | Not decided | OPEN | — |
| G-CFG-2 | Config state history store: DynamoDB vs. other | Date-bound (before config governance PR) | DynamoDB | OPEN | — |
| G-CFG-3 | Config validation schema: JSON Schema vs. Pydantic vs. custom | Date-bound (before config governance PR) | Not decided | OPEN | — |
| G-DEP-1 | Container repo merges feat/v0_3 to main | Event-bound (external event) | Re-pin within 5 business days; re-verify VERSION_REGISTRY | OPEN | — |
| G-INFRA-1 | Terraform vs. AWS CDK vs. CloudFormation | Date-bound (before PR 0022) | Terraform | DECIDED | Terraform |

Calendar dates in the Product Track may drift and that's expected. What's required is that any slip is recorded with a reason, and no PR silently absorbs scope from an open Decision Gate without that gate first being marked DECIDED.

### Operational hardening

- ECR publish currently uses scoped IAM user credentials via GitHub Secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) as an interim operational path.
- Future hardening should evaluate returning to the planned GitHub OIDC role assumption approach when AWS IAM trust is ready.
- No secrets, account IDs, or registry URLs are recorded in this roadmap.

### Runtime target decision

- **AWS App Runner is the near-term proving/testing target.** App Runner provides faster operational launch for smoke testing, integration validation, and proving the runtime model binding lifecycle end-to-end.
- **ECS Fargate remains the long-term primary production target.** The existing Terraform skeleton (`infra/terraform/ecs.tf`) is retained but not currently prioritized. ECS work moves later in the roadmap sequence.
- This is an operational pivot, not an abandonment of ECS. ADR-0008 records the full rationale.
- **APRANA is retired.** The term "APRANA" was an unverified placeholder from earlier ADR drafts. It is not a synonym for App Runner. It must not be carried forward as a target, alias, shorthand, PR, gate, or option in any future work.

### Model binding lifecycle

The runtime model binding lifecycle is architecturally confirmed:

1. CI/CD builds runtime image — **no model artifacts inside image**.
2. Deployment selects model identity via `BREMEN_MODEL_VERSION` (env var).
3. Container starts → reads cloud config → fetches/stages model package from S3 → validates manifest + checksum → crosses `joblib.load()` boundary exactly once at startup.
4. In-memory model serves all subsequent requests.
5. **No hot-swap. No per-request model loading.**
6. New model version → new deployment → restart/rolling replacement.

### CI/CD image tag policy

- The ECR workflow should keep immutable SHA tags for audit.
- A stable mutable tag named `app-runner` should be added for App Runner auto-deploy (planned PR 0031).
- The `latest` tag may remain as human convenience but should NOT be the App Runner deploy trigger.

### Config governance

- Config is separate from model. Config has its own lifecycle.
- Config states must be versioned, timestamped, auditable, and reproducible.
- Config change classes: runtime-safe operational (class A), decision-adjacent with validation/audit (class B), model-binding requiring redeploy (class C), structural forbidden in runtime UI (class D).
- A config state history store (likely DynamoDB or equivalent) is a future requirement.
- Gates G-CFG-2 and G-CFG-3 are added to the Decision Gate Register (both OPEN).
- G-CFG-1 (build vs. adopt) remains OPEN. See ADR-0009 for details.
- No config UI/API/database implementation in PR 0030.

### Model package composition / DS inventory

The current manifest contract supports a single artifact (`model_filename`). The model loader (`model_loader.py`) is object-level composite-compatible (`model: Any`).

An open question exists: do Mahalanobis and Wasserstein-style features require fitted reference statistics (covariance matrices, reference distributions) as part of the model package?

- If yes, the model package must become composite and atomic (multiple artifacts under one `model_version` / `feature_schema_version`).
- This question must be resolved by a DS/inventory PR (planned PR 0035) before preprocessing/inference PRs.

### Closed gate details

| Gate ID | Decided value | Decided by | Decision date |
|---------|---------------|------------|---------------|
| G-API-1 | async submit → `job_id` → poll | Human product/engineering decision in PR 0012 planning | 2026-07-03 (UTC) |
| G-API-2 | ECS Fargate | Human product/engineering decision in PR 0012 planning | 2026-07-03 (UTC) |
| G-INFRA-1 | Terraform | Human product/engineering decision in PR 0012 planning | 2026-07-03 (UTC) |

**Execution order note**: Runtime/API/IaC/model-artifact foundation is now priority before the patient-facing report template (Product Track item 2). This is execution-order guidance, not a renumbering of existing roadmap items. PRs from the Platform Readiness Track and the Product Track (items 2–12) may be interleaved based on readiness, with the understanding that the API/microservice/IaC/model-artifact foundation precedes downstream work that depends on it.

**Numbering clarification**: Product Track sequence positions (items 1–12) are ordering, not PR-00XX identifiers. The next literal PR number after 0025 will be assigned when the next scheduled sequence item is actually planned. PR 0019–0024 Platform Readiness Track numbers remain unchanged and are not renumbered by this or any subsequent PR. Reprioritization changes execution order only, not existing PR labels.

## Next Execution Sequence (post-platform-foundation)

- **PR 0026** — Runtime HTTP service runner. Expose existing API skeleton (`src/bremen/api/`) as an actual service process suitable for container/ECS smoke testing. No inference, no H5 read, no model loading.
- **PR 0027** — Model package source integration. Resolve local/cloud model package references and validate manifests/checksums without `joblib.load()`. Uses `read_cloud_config()` and `model_package.validate_model_package()`.
- **PR 0028** — Runtime model loading boundary. Controlled `joblib.load()` deserialization boundary, only after checksum/trust rules are in place. Must not load untrusted artifacts.
- **PR 0030** — Roadmap/ADR amendment (this PR). App Runner pivot, APRANA retirement, model lifecycle, config governance, DS inventory note.
- **PR 0031** — ECR workflow: add stable App Runner image tag (`app-runner` tag alongside existing SHA + latest).
- **PR 0032** — Model package fetch/staging from S3. Download model package to local staging directory using `read_cloud_config()`. No joblib.
- **PR 0033** — Startup model loading and readiness probe. Wire fetch + validate + load into server startup. Readiness endpoint returns 503 until model is loaded.
- **PR 0034** — App Runner Terraform skeleton. Add App Runner service Terraform alongside existing ECS skeleton.
- **PR 0035** — DS feature inventory and model package composition decision. Confirm whether Mahalanobis/Wasserstein features require fitted reference statistics. Decide classifier-only vs. composite package.
- **PR 0036** — H5/preflight metadata gate. Target/control consistency and H5 metadata validation.
- **PR 0037** — Preprocessing bridge. Connect approved preprocessing path without training or clinical claims.
- **PR 0038** — Inference pipeline integration. First end-to-end inference.
- **PR 0039** — Config governance ADR and gate decisions. Close G-CFG-1, G-CFG-2, G-CFG-3. Define config validation, history store, and audit architecture.

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
