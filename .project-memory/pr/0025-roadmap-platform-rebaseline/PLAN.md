# PR 0025 — Plan ROADMAP Rebaseline After Platform Foundation

Author: plan
Mode: planning only
Branch: 0025-roadmap-platform-rebaseline

## Objective

Rebaseline ROADMAP.md to reflect the completed and merged platform foundation work (PR 0019–0022C), preserve open gates, document the operational debt item (interim IAM credentials for ECR), clarify APRANA/App Runner status, and define the next execution sequence for the product/runtime track (PR 0026 onward).

This is a concrete, execution-oriented roadmap update, not narrative filler.

## Context

The Platform Readiness Track has delivered the following merged work:

- **PR 0019** — API contract + async microservice skeleton (`docs/api_contract.md`, `src/bremen/api/`, route-shaped handlers, in-memory job store)
- **PR 0020** — Cloud-aware config sourcing (`read_cloud_config()` in `src/bremen/config.py`, `CloudConfig` dataclass, environment variable contract matching Terraform/ECS)
- **PR 0021** — Container dependency hygiene (`requirements.txt` local-path defect fixed, reproducible git URL pin for `container` at `feat/v0_3`)
- **PR 0022A** — Terraform AWS runtime skeleton (`infra/terraform/`: main.tf, variables.tf, outputs.tf, ecr.tf, s3.tf, ecs.tf, iam.tf, README.md)
- **PR 0022B** — ECR publish workflow (`.github/workflows/ecr-publish.yml`, initial version)
- **PR 0022C** — ECR workflow credentials hotfix / scoped publisher credentials (workflow updated to use scoped IAM user credentials via secrets as an interim path)

G-CFG-1 and G-DEP-1 remain OPEN (no new evidence to close them).

## Allowed implementation files

The architect may modify exactly these files:

1. **`ROADMAP.md`** — MODIFY. Rebaseline to reflect completed platform work, update gate/debt register, add APRANA/App Runner clarification, define next execution sequence.

Optional only if strongly justified:

2. **`docs/architecture.md`** — MODIFY only if ROADMAP.md cannot be made internally consistent without it. Default: do not modify.

This PLAN.md recommends modifying only ROADMAP.md. docs/architecture.md already has a correct "API Surface (Draft)" section that mentions PR 0019; updating it is not strictly necessary for roadmap consistency.

## Forbidden files

- `src/**`, `tests/**`, `.github/**`, `infra/terraform/**`
- `docs/adr/**`, `docs/api_contract.md`, `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`
- `Dockerfile`, `requirements.txt`, `pyproject.toml`, `config/**`, `examples/**`, `tests/data/**`
- `agents/**`
- Any H5/HDF5, joblib/pkl/npy/npz artifacts
- Any `*.tfstate`, `.terraform/`

## Required reads (completed for this PLAN.md)

- `ROADMAP.md` — current state
- `docs/architecture.md` — current architecture baseline with platform sections
- `docs/adr/0003-bremen-microservice-api-architecture.md` — API architecture (G-API-1, G-API-2)
- `docs/adr/0004-bremen-configuration-management-strategy.md` — config management (G-CFG-1)
- `docs/adr/0005-container-dependency-stabilization.md` — container dependency (G-DEP-1)
- `docs/adr/0006-multi-target-deployment-and-iac.md` — multi-target deployment (G-INFRA-1)
- `docs/adr/0007-model-artifact-lifecycle.md` — model artifact lifecycle
- `docs/api_contract.md` — PR 0019 output
- `infra/terraform/README.md` — Terraform skeleton
- `infra/terraform/outputs.tf` — ECR, S3, ECS outputs
- `.github/workflows/ecr-publish.yml` — current ECR workflow (scoped IAM user creds)
- `src/bremen/config.py` — PR 0020 output (cloud config function exists)
- `.project-memory/project_contract.yml` — safety invariants
- `AGENTS.md` — agent role definitions

## Implementation phase assignment

- **Agent**: architect
- **Mode**: roadmap update

**Reason**: ROADMAP.md is an architect-reserved path per `agents/architect.yml`.

## ROADMAP.md update requirements

### 1. Platform Readiness status

Update `## Completed foundation PRs` to add:

```
- PR-0019 — API contract + async microservice skeleton. Creates docs/api_contract.md, src/bremen/api/ with route-shaped handlers and in-memory job store.
- PR-0020 — Cloud-aware config sourcing. Extends src/bremen/config.py with read_cloud_config() and CloudConfig dataclass reading BREMEN_MODEL_BUCKET, BREMEN_MODEL_PREFIX, BREMEN_MODEL_VERSION from environment.
- PR-0021 — Container dependency hygiene. Removes editable local-path dependencies from requirements.txt. Replaces with reproducible git URL pin at feat/v0_3. G-DEP-1 remains OPEN.
- PR-0022A — Terraform AWS runtime skeleton. infra/terraform/ with ECR, S3 versioned bucket, ECS Fargate cluster/service/task definition, CloudWatch, scoped IAM roles. Not yet applied.
- PR-0022B — ECR publish workflow. .github/workflows/ecr-publish.yml building and pushing Docker image to ECR on push to main.
- PR-0022C — ECR workflow credentials hotfix / scoped publisher credentials. Uses scoped IAM user credentials via secrets for ECR authentication (interim operational path; OIDC is the planned long-term approach).
```

Update `## Platform Readiness Track (parallel to Product Track)` to reflect completion for PR 0019, PR 0020, PR 0021, and PR 0022A/0022B/0022C. The PR 0022 entry should be clarified as:

| PR | Description | Depends on |
|----|-------------|------------|
| PR 0022A | **Terraform AWS runtime skeleton** — Delegated from ADR-0006. ECR, S3 versioned bucket, ECS Fargate, CloudWatch, scoped IAM. Not yet applied. | G-INFRA-1 and G-API-2 closed |
| PR 0022B | **ECR publish workflow** — Docker image build/push to ECR on main push. | Terraform skeleton exists |
| PR 0022C | **ECR workflow credentials** — Scoped IAM user credentials as interim auth path. | PR 0022B |
| PR 0023 | **APRANA / App Runner evaluation** — Deferred candidate track. See note below. | Platform name/access confirmed |
| PR 0024 | **Config editing surface** — BLOCKED on G-CFG-1. Not date-bound. Scheduled only after Product Track's core classifier work (operator-convenience, not product-critical path). | G-CFG-1, Product Track core classifier |

### 2. Gate and debt register

**Keep OPEN** (no evidence to close):
- **G-CFG-1** — Config management tool choice not yet decided. Maintain OPEN status.
- **G-DEP-1** — External container repo `feat/v0_3` → `main` merge not yet confirmed. Maintain OPEN status.

**Add operational hardening item**:
```
### Operational hardening
- ECR publish currently uses scoped IAM user credentials via GitHub Secrets (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) as an interim operational path.
- Future hardening should evaluate returning to the originally planned GitHub OIDC role assumption approach when AWS IAM trust is ready.
- No secrets, account IDs, or registry URLs are recorded in this roadmap.
```

### 3. Next execution sequence

Add a new section `## Next Execution Sequence (post-platform-foundation)` with the following PRs:

- **PR 0026** — Runtime HTTP service runner. Expose existing API skeleton (`src/bremen/api/`) as an actual service process suitable for container/ECS smoke testing. No inference, no H5 read, no model loading.
- **PR 0027** — Model package source integration. Resolve local/cloud model package references and validate manifests/checksums without `joblib.load()`. Uses `read_cloud_config()` and `model_package.validate_model_package()`.
- **PR 0028** — Runtime model loading boundary. Controlled `joblib.load()` deserialization boundary, only after checksum/trust rules are in place. Must not load untrusted artifacts.
- **PR 0029** — H5/preflight metadata gate. Target/control consistency and H5 metadata validation without full inference.
- **PR 0030** — Preprocessing bridge. Connect approved preprocessing path without training or clinical claims.
- **PR 0031** — Inference pipeline integration. First end-to-end inference, only after model package, H5 gate, and preprocessing boundaries are in place.

These entries do NOT use PR 0023 or PR 0024 (both are reserved/deferred).

### 4. App Runner / APRANA clarification

Add a subsection explaining APRANA:

```
### App Runner / APRANA clarification

- "APRANA" in earlier ADRs and roadmap entries was a planning shorthand for **AWS App Runner**.
- **ECS Fargate** remains the decided primary AWS runtime target (G-API-2, DECIDED in PR 0012).
- **App Runner** is a deferred candidate track, not current implementation scope. PR 0023 is reserved for future App Runner evaluation or CI/CD planning.
- Before any App Runner work starts, an explicit decision is required on whether App Runner is:
  1. an alternative to ECS Fargate (replacing the current primary target),
  2. a secondary/parallel deployment target, or
  3. abandoned in favor of Fargate alone.
- No App Runner resources, Terraform, GitHub Actions, deployment steps, or runtime changes are introduced by this roadmap rebaseline.
```

### 5. Product/safety language

Ensure ROADMAP.md preserves Bremen identity language throughout:
- Clinical question: "Should patient continue to MRI?"
- Classification: healthy vs. disease (NORMAL vs. BENIGN+CANCER).
- Controlled ML decision-support workflow.
- No diagnosis claim.
- No replacement for MRI, biopsy, radiologist, or clinician.
- Runtime service must not train models.
- H5 metadata validation and target/control consistency remain safety gates.
- Matador is system of record.
- Platform APIs must not depend on local paths.

## Validation checklist

The implementation phase (architect) must execute these checks:

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5) File exists
test -f ROADMAP.md || exit 1

# 6-11) Completed PR references present
grep -n "PR 0019" ROADMAP.md || exit 1
grep -n "PR 0020" ROADMAP.md || exit 1
grep -n "PR 0021" ROADMAP.md || exit 1
grep -n "0022A\|0022B\|0022C" ROADMAP.md || exit 1

# 12-13) OPEN gates still present
grep -n "G-CFG-1" ROADMAP.md || exit 1
grep -n "G-DEP-1" ROADMAP.md || exit 1
grep -n "OPEN" ROADMAP.md || exit 1

# 14) APRANA/App Runner clarification present
grep -n "App Runner\|APRANA\|ECS Fargate" ROADMAP.md || exit 1

# 15) Next execution sequence present
grep -n "runtime HTTP service runner\|model package source integration\|H5/preflight" ROADMAP.md || exit 1

# 16) No secrets/account IDs/registry URLs in ROADMAP
grep -R -I -n "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|AKIA\|SecretAccessKey\|851725451903\|dkr.ecr" ROADMAP.md || true

# 17) No unsafe production/clinical claims
grep -R -I -n "production-ready\|deployed production API\|diagnos\|cancer detected" ROADMAP.md || true

# 18) No forbidden file changes
git diff --name-only -- src tests .github infra/terraform docs/adr docs/api_contract.md README.md Dockerfile requirements.txt pyproject.toml config examples tests/data agents
# Must return nothing

# 19) No terraform/H5/model artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true

# 20) .DS_Store check
find . -name ".DS_Store" -print
```

## Non-goals

- No source changes.
- No test changes.
- No GitHub Actions changes.
- No Terraform changes.
- No Docker/dependency changes.
- No ADR rewrite.
- No API contract rewrite.
- No secrets/account IDs/registry URLs in docs.
- No production deployment claim.
- No clinical validation claim.
- No runtime inference.
- No model loading.
- No H5 reads.
- No App Runner implementation.
- No closing of G-CFG-1 or G-DEP-1 without evidence.
- No reuse of PR 0023 or PR 0024.

## Rollback plan

1. **Revert ROADMAP.md** — restore the pre-PR-0025 version. All roadmap information is text — no runtime effects.
2. No other files affected.

## Follow-up PRs

- **PR 0026** — Runtime HTTP service runner (next execution PR after this rebaseline).
- **PR 0027** — Model package source integration.
- **PR 0028** — Runtime model loading boundary.
- **PR 0029** — H5/preflight metadata gate.
- **PR 0030** — Preprocessing bridge.
- **PR 0031** — Inference pipeline integration.

PR 0023 remains reserved for App Runner evaluation. PR 0024 remains reserved for config editing surface.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only ROADMAP.md changed (optionally docs/architecture.md with justification). |
| **Platform PR status drift** | PR 0019–0022C marked as completed with accurate descriptions. |
| **Gate drift** | G-CFG-1 and G-DEP-1 remain OPEN. Operational hardening item documented. |
| **APRANA drift** | Clarified as App Runner shorthand. Deferred. Not implemented. ECS Fargate remains primary. |
| **Next sequence drift** | PR 0026–0031 defined. Does not reuse PR 0023 or PR 0024. |
| **Safety drift** | Bremen identity preserved. No clinical/diagnostic claims. No production-ready claims. |
| **Secrets drift** | No AWS keys, account IDs, or registry URLs in ROADMAP.md. |
| **Infrastructure drift** | No source/Terraform/CI/Docker changes. |
| **Validation drift** | All 20 validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan is vague or narrative-only (fails to update completed PR statuses concretely).
- Plan claims Terraform apply/deployment without committed evidence.
- Plan puts AWS keys, account IDs, secrets, or registry URLs into docs.
- Plan closes G-CFG-1 or G-DEP-1 without evidence.
- Plan reuses reserved PR 0023 or PR 0024.
- Plan treats APRANA as unknown (must clarify as App Runner shorthand per the task).
- Plan selects or implements App Runner in PR 0025.
- Plan changes source/tests/GitHub Actions/Terraform.
- Implementation phase is not Agent: architect / Mode: roadmap update.

## Decisions summary

### Allowed files
1. `ROADMAP.md` — MODIFY (rebaseline)
2. `docs/architecture.md` — MODIFY (optional, only if strongly justified; default = no change)

### Forbidden files
- All source, test, CI, Terraform, Docker, dependency, docs, ADR, and agent files.

### Completed platform work summary
| PR | Status | Description |
|----|--------|-------------|
| PR 0019 | ✅ Completed | API contract + async microservice skeleton |
| PR 0020 | ✅ Completed | Cloud-aware config sourcing |
| PR 0021 | ✅ Completed | Container dependency hygiene |
| PR 0022A | ✅ Completed | Terraform AWS runtime skeleton (not yet applied) |
| PR 0022B | ✅ Completed | ECR publish workflow |
| PR 0022C | ✅ Completed | ECR workflow credentials hotfix / scoped publisher credentials |

### Open gates / debt summary
| Gate | Status | Notes |
|------|--------|-------|
| G-CFG-1 | OPEN | Config management tool choice not decided |
| G-DEP-1 | OPEN | Container feat/v0_3 → main merge not confirmed |
| ECR auth | Operational debt | Interim IAM user credentials; OIDC planned for future |

### App Runner / APRANA summary
- APRANA = App Runner planning shorthand.
- ECS Fargate remains decided primary runtime target.
- App Runner is deferred candidate track, not current scope.
- PR 0023 reserved for future App Runner evaluation.
- Explicit decision required before any App Runner work.

### Next execution sequence
- PR 0026 — Runtime HTTP service runner
- PR 0027 — Model package source integration
- PR 0028 — Runtime model loading boundary
- PR 0029 — H5/preflight metadata gate
- PR 0030 — Preprocessing bridge
- PR 0031 — Inference pipeline integration

### Validation checklist
20 checks: git state, completed PR references, OPEN gates, APRANA clarification, next sequence, secrets absence, safety claims, forbidden files, artifact scan, .DS_Store.

### Stop conditions
9 block conditions.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0025-roadmap-platform-rebaseline/PLAN.md`
2. Human runs: `git add .project-memory/pr/0025-roadmap-platform-rebaseline/PLAN.md`
3. Human runs: `git commit -m "PR 0025 — Plan ROADMAP rebaseline after platform foundation"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the architect implements ROADMAP.md.

## Files read

- `ROADMAP.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0004-bremen-configuration-management-strategy.md`
- `docs/adr/0005-container-dependency-stabilization.md`
- `docs/adr/0006-multi-target-deployment-and-iac.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/api_contract.md`
- `infra/terraform/README.md`
- `infra/terraform/outputs.tf`
- `.github/workflows/ecr-publish.yml`
- `src/bremen/config.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0025-roadmap-platform-rebaseline/PLAN.md` (this file)

## Files intentionally ignored

- All source, test, CI, Terraform, Docker, and dependency files.
- All docs files not in required reads.
- Any H5/HDF5 or model artifact files.

## Boundary confirmations

- confirm: ROADMAP.md update planned: yes
- confirm: default scope is ROADMAP.md only: yes
- confirm: platform completed PRs will be reflected: yes
- confirm: no Terraform apply/deployment claim planned: yes
- confirm: no secrets/account IDs/registry URLs planned: yes
- confirm: G-CFG-1 and G-DEP-1 remain OPEN unless evidence proves otherwise: yes
- confirm: APRANA clarified as App Runner shorthand: yes
- confirm: App Runner remains deferred candidate, not current implementation scope: yes
- confirm: ECS Fargate remains current decided primary runtime target: yes
- confirm: PR 0023 reserved/deferred for App Runner / APRANA evaluation or CI/CD planning: yes
- confirm: PR 0024 reserved/deferred for config editing surface: yes
- confirm: next product/runtime PR sequence planned (PR 0026–0031): yes
- confirm: no source/test/GitHub Actions/Terraform changes planned: yes
- confirm: implementation assigned to Agent: architect / Mode: roadmap update: yes
- confirm: no git mutation commands run: yes
