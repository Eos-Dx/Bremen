# Bremen Roadmap

**Track**: Product Track + Platform Readiness Track (parallel).

No hard calendar dates — use sequence and dependencies.

## Current milestone (PR0077)

Multi-Workflow Analysis Workspace:
- Structured job events and bounded ephemeral event store
- SSE live event stream with reconnect
- Job status API, report metadata API
- Workflow cards with independent status per workflow
- Bremen report v0.2 (extended from PR0053 decision_support_report)
- Aramis report provider boundary (unavailable, typed reason code)
- Analysis Workspace frontend (timeline, process panel, report/audit tabs)
- Privacy/redaction controls
- Audit metadata display

**Status**: Implemented (PR0077)

---

## Next milestone

- Authoritative Aramis runtime integration
- Aramis report parity
- Persistent job/event history (database backend)
- Report access controls
- PDF/report artifact storage
- Bremen scientific parity evidence
- Bremen P1/P2/P3 policy

---

## Later milestone

- Additional workflow providers
- Long-term audit retention
- Operational dashboards
- Cross-version report comparison
- Certification evidence bundles
- Role-based report access

---

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
- PR0026 — Runtime HTTP service runner. Exposes `src/bremen/api/server.py` as a service process.
- PR0027 — Model package source integration. `read_cloud_config()` + `model_package.validate_model_package()`.
- PR0028 — Runtime model loading boundary. Controlled `joblib.load()` deserialization with checksum/trust rules.
- PR0029 — Runtime model config roadmap rebaseline.
- PR0030 — App Runner pivot docs. ADR-0008 + APRANA retirement + model lifecycle.
- PR0031 — App Runner image tag. `app-runner` stable tag in ECR workflow.
- PR0032 — Model package fetch/staging from S3.
- PR0033 — Startup model loading + readiness probe.
- PR0034 — Bremen training pipeline. `Dockerfile.training`, `src/bremen/training/`, feature computation.
- PR0035 — Model package publication path. v0.1 model published to S3, manifest validation.
- PR0036 — H5 preflight gate. `run_h5_preflight()` with target/control validation.
- PR0037 — Preprocessing bridge. `run_preprocessing_bridge()` with 15-feature extraction.
- PR0038 — Inference pipeline integration. `run_inference()` end-to-end.
- PR0039 — v0.1 schema rebaseline + inference integration. ADR-0010, 15-column schema, portable logistic regression.
- PR0040 — S3 model startup staging. Model fetch from S3 at container startup.
- PR0041 — Runtime observability logging. `bremen.*` structured log events.
- PR0042 — Prediction job execution wiring. `handle_submit_prediction()` → job → `run_inference()`.
- PR0043 — S3 H5 input staging. `src/bremen/h5_inputs.py`, `stage_h5_input()`.
- PR0044 — H5 sample metadata fallback. `resolve_patient_metadata()`, `patient_name_fallback`.
- PR0045 — H5 layout adapter boundary. `src/bremen/api/h5_layouts.py`, adapter protocol, canonical + calibration adapters.
- PR0047 — Calibration sample preprocessing bridge. Map calibration sample layout into runtime preprocessing without changing inference math. Explicit target/control sample refs. Integration i/q arrays. 15-feature v0.1 schema.
- PR0048 — HTTP explicit-ref wiring. `target_scan_ref` / `control_scan_ref` carried through HTTP → staging → preflight/layout context → preprocessing/inference.
- PR0049 — Production E2E smoke hardening. In-process handler-call smoke test with synthetic H5, monkeypatched S3 staging, explicit refs, calibration layout, log leakage checks, and operator runbook.
- Agent loop guardrails — Process-only project hygiene (no numbered PR). Enforced by `AGENT_TEST_DEBUGGING_RULES.md` and `TEST_DESIGN_STANDARD.md.
- PR0050 — Model/version readiness endpoint cleanup. Aligns `/model/version`
  `model_status` with actual `model_ready` state. Preserves safe metadata
  only via `ModelState.get_load_error()` safe categories.
- PR0051 — Config governance ADR/gates. Closes G-CFG-1 (DECIDED —
  lightweight in-repo governance), G-CFG-2 (DEFERRED — no DynamoDB/backend
  until Matador boundary), G-CFG-3 (DECIDED — validation gates as repo
  tests/static checks). ADR-0011 records all decisions.
- PR0052 — Matador boundary / system-of-record adapter skeleton. Typed
  boundary with `ExternalRecordRef`, `ResolvedInput`, `RecordResolver`
  protocol, and `UnconfiguredRecordResolver`. Scaffold only — no real
  Matador API calls, credentials, or network adapters. ADR-0012 documents
  the contract.
- PR0053 — Decision-support report/output wrapper. `build_decision_support_report()`
  produces safe structured report around inference results. No diagnosis,
  no clinical validation claim. `report_schema_version: "v0.1"`.
- PR0054 — Release readiness / operator notes. Production checklist,
  rollback, smoke commands, model artifact boundaries, clinical-safety
  disclaimers, and sign-off checklist.

## Current state through PR0054

- Runtime service exists and is operational on App Runner.
- Runtime model is loaded at startup from a checksum-verified model package (S3 staging + joblib).
- App Runner proving path is operational (S3 staging, inference, prediction jobs).
- S3 model startup staging works (container start → S3 fetch → checksum → joblib.load).
- S3 H5 input staging works (`h5_uri` accepted, downloaded, checksum verified, staged locally).
- Prediction job execution is wired (submit → validate → stage → preflight → bridge → inference → completed/failed).
- H5 metadata fallback is implemented (primary `/patient/id`, fallback sample-level `patient_name` with source tracking).
- H5 layout adapter boundary exists (abstract adapter protocol, detect/resolve, Canonical + CalibrationSample adapters, layout registry).
- Calibration sample preprocessing bridge exists (PR0047 — integration i/q read, 15-feature v0.1 schema, explicit refs).
- Explicit target/control refs are wired through predictions (PR0048 — HTTP → staging → preflight/layout context → bridge → inference).
- Production E2E smoke hardening exists (PR0049 — in-process handler-call smoke test with synthetic H5, monkeypatched S3 staging, log leakage checks, operator runbook).
- Agent loop guardrails exist as process-only project hygiene (no numbered PR).
- Model/version readiness cleanup completed.
- Config governance gates resolved (G-CFG-1 DECIDED, G-CFG-2 DEFERRED,
  G-CFG-3 DECIDED). ADR-0011 records config surface taxonomy and
  lightweight in-repo governance.
- System-of-record boundary skeleton exists (typed scaffold only —
  `ExternalRecordRef`, `ResolvedInput`, `RecordResolver` protocol,
  safe error hierarchy). Real Matador integration is not yet implemented.
- Decision-support report wrapper exists (`decision_support_report` with
  `report_schema_version: "v0.1"`, safety limitations, no diagnosis
  claims).
- Release readiness operator notes exist (16-section checklist covering
  startup, health, smoke, failure modes, logging, rollback, security,
  clinical-safety boundaries).

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

> **Note**: Items 8–12 from the original Product Track sequence have been
> completed as part of the PR0050–PR0054 execution sequence. The remaining
> Product Track items (2, 3, 6, 7) and any new candidates require human
> product/engineering prioritisation for the next execution block.

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

## Next Execution Block (post-PR0054)

The PR0050–PR0054 execution sequence is complete. The next execution block
requires a human product/engineering decision to select and prioritize
the next set of work from the candidates below.

**Remaining Product Track candidates** (from the original Product Track
sequence):

| Position | Description | Status |
|----------|-------------|--------|
| 2 | YAML/PDF clinical report template | Not started |
| 3 | YAML training config template | Not started |
| 6 | GitHub demo — real H5 patients, end-to-end prediction | Not started |
| 7 | Platform deployment plan document | Not started |

**Open Decision Gate candidates** (from the Decision Gate Register):

| Gate | Description | Status |
|------|-------------|--------|
| G-CFG-1 | Build vs. adopt config management product | OPEN |
| G-CFG-2 | Config state history store (DynamoDB or other) | DEFERRED |
| G-DEP-1 | Container repo merges feat/v0_3 to main | OPEN |

**Other roadmap-referenced candidates**:

| Candidate | Reference | Status |
|-----------|-----------|--------|
| Config editing surface (operator UI/API) | PR 0024, ADR-0009 | BLOCKED on G-CFG-1 |
| Matador resolver implementation (real adapter) | ADR-0012 Section "Future Matador Resolver" | Not started |
| FastAPI transport adapter (thin ASGI layer) | ROADMAP.md, ADR-0011 "Boundaries and Non-Goals" | Deferred |
| DynamoDB config state history store | G-CFG-2 | DEFERRED |

**Decision required**: Before PR0055 can be planned, a human
product/engineering decision must define which of these candidates (or
a new candidate not listed here) constitutes the next execution block.

> **Note**: The Product Track sequence positions (1–12) are ordering
> guidance, not chronological commitment. Reprioritisation is expected.
> Items 8–12 from the original Product Track have been completed as
> PR0050–PR0054.

## Training Pipeline Track (completed)

This track ran in parallel with the runtime track. All items are completed:

- **PR0034** — Bremen training pipeline implementation:
  - `Dockerfile.training`
  - `src/bremen/training/`
  - CI extension for runtime and training images
  - Second ECR repository for training image
  - `config/training/*.yaml`
  - Bremen training joblib artifact assembly
  - Feature computation for 7 Bremen feature families (sigma_l1, sigma_l2, Mahalanobis1, Mahalanobis2, wasserstein_distance_full_q2, meanrms2, weightedrms1)
  - Tests for training artifact shape and patient-safe splits
- **PR0035** — First controlled training run and model package publication:
  - Run training on approved Bremen/Nova study data
  - Publish `bremen_v0_1.joblib` to S3 model store
  - Create/verify manifest with `model_checksum` and `feature_schema_version`
  - Verify `model_package.py` can validate package
  - Update configured `BREMEN_MODEL_VERSION` through approved model release process

## H5 Layout Strategy

### Core principles

- H5 layouts are adapter/plugin based (`H5LayoutAdapter` protocol). New H5 layouts
  must add an adapter + tests, not hardcoded conditionals in preflight.
- The canonical layout (single patient, `/patient/id`, `/scans/target/`,
  `/scans/contralateral/`) remains fully supported with zero regression.
- The calibration sample layout (multiple patients under `/calib_*/sample_*/`,
  `sample/patient_name`, `sample/sample_type`, `sets/set_*/integration/i/q`)
  is supported through the `CalibrationSampleH5LayoutAdapter` at the
  metadata/context/preflight level. Preprocessing is PR0047 scope.
- Multi-patient H5 containers require explicit `target_scan_ref` /
  `control_scan_ref` to select which samples to process.
- No automatic first-patient or first-sample selection is permitted under any
  adapter.
- Raw patient identifiers (`patient_name`, `patient_id`) must not be logged.
  Raw scan arrays must not be logged.
- Future H5 layouts must add adapters and passing tests. Adapters must include
  `detect()` and `resolve_prediction_context()` methods.

### Current adapter inventory

| Adapter | Detection trigger | Status |
|---------|------------------|--------|
| `CanonicalH5LayoutAdapter` | `/scans/target/measurements` exists | Production — supported |
| `CalibrationSampleH5LayoutAdapter` | `/calib_*` groups with `sample/patient_name` + `sample/sample_type`, no `/scans/target/measurements` | Preflight metadata/context only — preprocessing in PR0047 |

## Agent test debugging

Agent test debugging rules are defined in
`.project-memory/AGENT_TEST_DEBUGGING_RULES.md`.
