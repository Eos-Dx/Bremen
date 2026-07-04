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
| PR 0023 | **APRANA / App Runner evaluation** — Deferred candidate track. See App Runner/APRANA clarification below. | Platform name/access confirmed |
| PR 0024 | **Config editing surface** — BLOCKED on G-CFG-1. Not date-bound. Scheduled only after Product Track's core classifier work (operator-convenience, not product-critical path). | G-CFG-1, Product Track core classifier |

## Decision Gate Register

| Gate ID | Question | Trigger type | Recommended default | Status | Decided value |
|---------|----------|-------------|-------------------|--------|---------------|
| G-API-1 | Sync vs. async request/response | Date-bound (before PR 0019) | Async submit-then-poll | DECIDED | async submit → `job_id` → poll |
| G-API-2 | AWS compute target (ECS Fargate vs. Lambda-container vs. EKS) | Date-bound (before PR 0019, PR 0022) | ECS Fargate | DECIDED | ECS Fargate |
| G-CFG-1 | Build in-house vs. adopt existing config-management product | Date-bound (before PR 0024) | Not decided | OPEN | — |
| G-DEP-1 | Container repo merges feat/v0_3 to main | Event-bound (external event) | Re-pin within 5 business days; re-verify VERSION_REGISTRY | OPEN | — |
| G-INFRA-1 | Terraform vs. AWS CDK vs. CloudFormation | Date-bound (before PR 0022) | Terraform | DECIDED | Terraform |

Calendar dates in the Product Track may drift and that's expected. What's required is that any slip is recorded with a reason, and no PR silently absorbs scope from an open Decision Gate without that gate first being marked DECIDED.

### Operational hardening

- ECR publish currently uses scoped IAM user credentials via GitHub Secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) as an interim operational path.
- Future hardening should evaluate returning to the planned GitHub OIDC role assumption approach when AWS IAM trust is ready.
- No secrets, account IDs, or registry URLs are recorded in this roadmap.

### App Runner / APRANA clarification

- "APRANA" in earlier ADRs and roadmap entries was a planning shorthand for **AWS App Runner**.
- **ECS Fargate** remains the decided primary AWS runtime target (G-API-2, DECIDED in PR 0012).
- **App Runner** is a deferred candidate track, not current implementation scope. PR 0023 is reserved for future App Runner evaluation or CI/CD planning.
- Before any App Runner work starts, an explicit decision is required on whether App Runner is:
  1. an alternative to ECS Fargate (replacing the current primary target),
  2. a secondary/parallel deployment target, or
  3. abandoned in favor of Fargate alone.
- No App Runner resources, Terraform, GitHub Actions, deployment steps, or runtime changes are introduced by this roadmap rebaseline.

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
- **PR 0029** — H5/preflight metadata gate. Target/control consistency and H5 metadata validation without full inference.
- **PR 0030** — Preprocessing bridge. Connect approved preprocessing path without training or clinical claims.
- **PR 0031** — Inference pipeline integration. First end-to-end inference, only after model package, H5 gate, and preprocessing boundaries are in place.
