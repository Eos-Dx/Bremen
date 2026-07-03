# Bremen Roadmap

**Track**: Product Track only.

No Platform Readiness Track. No Decision Gate Register. No hard calendar dates — use sequence and dependencies.

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
| PR 0022 | **IaC skeleton + ECR publish job** — Delegated from ADR-0006. | G-INFRA-1 and G-API-2 closed |
| PR 0023 | **APRANA CI/CD publish job** — Delegated from ADR-0006. BLOCKED until platform name/access confirmed. No date until unblocked. | Platform name/access confirmed |
| PR 0024 | **Config editing surface** — Delegated from ADR-0004. BLOCKED on G-CFG-1. Not date-bound. Scheduled only after Product Track's core classifier work (operator-convenience, not product-critical path). | G-CFG-1, Product Track core classifier |

## Decision Gate Register

| Gate ID | Question | Trigger type | Recommended default | Status | Decided value |
|---------|----------|-------------|-------------------|--------|---------------|
| G-API-1 | Sync vs. async request/response | Date-bound (before PR 0019) | Async submit-then-poll | OPEN | — |
| G-API-2 | AWS compute target (ECS Fargate vs. Lambda-container vs. EKS) | Date-bound (before PR 0019, PR 0022) | ECS Fargate | OPEN | — |
| G-CFG-1 | Build in-house vs. adopt existing config-management product | Date-bound (before PR 0024) | Not decided | OPEN | — |
| G-DEP-1 | Container repo merges feat/v0_3 to main | Event-bound (external event) | Re-pin within 5 business days; re-verify VERSION_REGISTRY | OPEN | — |
| G-INFRA-1 | Terraform vs. AWS CDK vs. CloudFormation | Date-bound (before PR 0022) | Terraform | OPEN | — |

Calendar dates in the Product Track may drift and that's expected. What's required is that any slip is recorded with a reason, and no PR silently absorbs scope from an open Decision Gate without that gate first being marked DECIDED.
