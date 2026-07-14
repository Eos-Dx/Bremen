# PR 0030 — Plan Roadmap and ADR Amendment: App Runner Pivot, APRANA Retirement, Model Lifecycle, Config Governance

Author: plan
Mode: planning only
Branch: 0030-roadmap-adr-apprunner-pivot

## Objective

Record the runtime/model/config rebaseline into source-of-truth project docs before any more runtime code. This is a docs/ADR/roadmap amendment PR — no source code, no CI/CD, no Terraform, no Dockerfile, no dependencies.

The rebaseline artifact at `.project-memory/architecture/runtime-model-config-roadmap-rebaseline.md` details all findings. This PLAN.md implements its recommendations as formal PR 0030 scope.

## Required reads — observed facts

### Rebaseline artifact
- `.project-memory/architecture/runtime-model-config-roadmap-rebaseline.md` — present. Full architectural assessment.

### ROADMAP.md
- Current state reflects PR 0025 rebaseline with completed PRs 0019–0028.
- Contains an "App Runner / APRANA clarification" section that conflates APRANA with App Runner.
- Contains PR 0023 as "APRANA / App Runner evaluation — Deferred candidate track."
- G-API-2 is DECIDED: "ECS Fargate" only — does not mention App Runner.
- Next execution sequence has PR 0029 (H5 gate) → PR 0030 (preprocessing) → PR 0031 (inference) but does NOT have model fetch/staging or App Runner deploy PRs.
- No config governance gates (G-CFG-2, G-CFG-3) exist.
- No model binding lifecycle confirmation exists.

### ADR-0003
- G-API-2 recorded as OPEN → later DECIDED: ECS Fargate. No App Runner mention.
- Mandatory prediction response fields do NOT include `config_version` or `config_hash`.

### ADR-0006
- Contains "APRANA (UNVERIFIED)" section. APRANA must be retired.
- No mention of App Runner as near-term proving target.

### ADR-0007
- Model artifact lifecycle correctly specified. No changes needed.

### ADR index
- No `docs/adr/README.md` exists. New ADRs (0008, 0009) will be standalone files.

### ADR numbering
- Next available numbers: 0008 (after 0007). ADR-0008 and ADR-0009 are available.

### `.project-memory/project_contract.yml`
- Prediction output invariant does NOT include `config_version` or `config_hash`.
- No config governance safety invariant.
- **Decision**: Do NOT modify `project_contract.yml` in PR 0030. The config governance prediction output field addition and config change-class invariant are important but belong in a dedicated config governance ADR/roadmap PR (PR 0039 per rebaseline proposal), not in the App Runner pivot PR. PR 0030 is already carrying enough scope (ROADMAP + 3 ADRs). Adding the contract amendment would increase review burden without blocking the App Runner pivot.

## Implementation agent

- **Agent**: architect
- **Mode**: docs/ADR/roadmap write

## Allowed implementation files

The architect may create or modify exactly these files:

1. **`ROADMAP.md`** — MODIFY. Amend for App Runner pivot, APRANA retirement, model binding lifecycle, config governance gates, revised PR sequence.
2. **`docs/adr/0006-multi-target-deployment-and-iac.md`** — MODIFY. Remove APRANA section entirely. Add reference to ADR-0008 for App Runner.
3. **`docs/adr/0008-runtime-target-apprunner-proving.md`** — NEW. Record App Runner as near-term proving target.
4. **`docs/adr/0009-config-governance.md`** — NEW. Record config governance skeleton (change classes, future gates, classification rules).

No other files may be created or modified.

## Forbidden files

- `src/**`, `tests/**`, `.github/**`, `infra/**`
- `Dockerfile`, `.dockerignore`, `requirements.txt`, `pyproject.toml`
- `config/**`, `examples/**`, `agents/**`
- `docs/adr/0001.md` through `docs/adr/0005.md`, `docs/adr/0007.md` — read-only
- `docs/api_contract.md`, `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `.project-memory/project_contract.yml` — excluded by default decision

## Exact implementation scope

### 1. ROADMAP.md amendments

#### a. Remove "App Runner / APRANA clarification" section entirely

Replace with a short "Runtime target decision" section:

```
### Runtime target decision

- **AWS App Runner is the near-term proving/testing target.** App Runner provides faster operational launch for smoke testing, integration validation, and proving the runtime model binding lifecycle end-to-end.
- **ECS Fargate remains the long-term primary production target.** The existing Terraform skeleton (`infra/terraform/ecs.tf`) is retained but not currently prioritized. ECS work moves later in the roadmap sequence.
- This is an operational pivot, not an abandonment of ECS. ADR-0008 records the full rationale.
```

#### b. Amend PR 0023

Change from:
```
PR 0023 | **APRANA / App Runner evaluation** — Deferred candidate track. See App Runner/APRANA clarification below.
```
to:
```
PR 0023 | **App Runner proving target** — Near-term CI/CD and deploy path for App Runner proving target. See ADR-0008 for full decision.
```

#### c. Amend G-API-2

Change decided value from `"ECS Fargate"` to `"ECS Fargate (primary/long-term), App Runner (near-term proving)"`.

Record this as a gate amendment with PR 0030 as the amendment source, maintaining the original PR 0012 closure.

#### d. Add new gates to Decision Gate Register

| Gate ID | Question | Trigger type | Recommended default | Status | Decided value |
|---------|----------|-------------|-------------------|--------|---------------|
| G-CFG-2 | Config state history store: DynamoDB vs. other | Date-bound (before config governance PR) | DynamoDB | OPEN | — |
| G-CFG-3 | Config validation schema: JSON Schema vs. Pydantic vs. custom | Date-bound (before config governance PR) | Not decided | OPEN | — |

#### e. Add model binding lifecycle confirmation

Add a new subsection:

```
### Model binding lifecycle

The runtime model binding lifecycle is architecturally confirmed:

1. CI/CD builds runtime image — **no model artifacts inside image**.
2. Deployment selects model identity via `BREMEN_MODEL_VERSION`.
3. Container starts → reads cloud config → fetches/stages model package → validates manifest + checksum → calls `joblib.load()` exactly once at startup.
4. In-memory model serves all subsequent requests.
5. No hot-swap. No per-request loading.
6. New model version → new deployment → restart/rolling replacement.

See ADR-0007 and the controlled `model_loader.py` implementation for details.
```

#### f. Update Next Execution Sequence

Replace the current PR 0029–0031 block with the revised sequence:

```
- **PR 0030** — Roadmap/ADR amendment (this PR). App Runner pivot, APRANA retirement, model binding lifecycle, config governance gates.
- **PR 0031** — ECR workflow: add stable App Runner image tag (`app-runner` tag alongside existing SHA + latest).
- **PR 0032** — Model package fetch/staging from S3. Download model package to local staging directory using `read_cloud_config()`. No joblib.
- **PR 0033** — Startup model loading and readiness probe. Wire fetch + validate + load into server startup. Readiness endpoint returns 503 until model is loaded.
- **PR 0034** — App Runner Terraform skeleton. Add App Runner service Terraform alongside existing ECS skeleton.
- **PR 0035** — DS feature inventory and model package composition decision. Confirm whether Mahalanobis/Wasserstein features require fitted reference statistics. Decide classifier-only vs composite package.
- **PR 0036** — H5/preflight metadata gate. Target/control consistency and H5 metadata validation.
- **PR 0037** — Preprocessing bridge. Connect approved preprocessing path without training or clinical claims.
- **PR 0038** — Inference pipeline integration. First end-to-end inference.
- **PR 0039** — Config governance ADR and gate decisions. Close G-CFG-1, G-CFG-2, G-CFG-3. Define config validation, history store, and audit architecture.
```

Do not remove the completed PRs 0026, 0027, 0028 from the sequence (they remain listed as completed foundation PRs).

### 2. ADR-0006 amendment

- Remove the entire "APRANA (UNVERIFIED)" subsection and all APRANA references.
- Replace with: "App Runner is the near-term proving target. See ADR-0008 for the full decision. ECS Fargate remains the long-term primary production target."
- Update the G-INFRA-1 gate to note it now applies to both Terraform-managed targets (ECS / App Runner).

### 3. ADR-0008: Runtime Target Pivot — App Runner Proving Target (NEW)

**Status**: Accepted

Content:

- **Decision**: AWS App Runner is the near-term proving/testing target.
- **Rationale**: Faster operational launch — source-to-code or image-based deployment, auto-scaling, built-in load balancer, no VPC/subnet management.
- **Relationship to ECS**: ECS Fargate remains the long-term primary production target. The existing Terraform skeleton is retained but not currently prioritized.
- **Deployment model**: App Runner uses ECR image source. The `app-runner` mutable tag (added in PR 0031) triggers auto-deployment.
- **Health check**: `/health` endpoint serves as App Runner health check. Readiness endpoint (PR 0033) serves as readiness gate.
- **Relationship to G-API-2**: This is an operational addition to the G-API-2 decision, not a replacement. G-API-2 now reads: "ECS Fargate (primary/long-term), App Runner (near-term proving)."
- **Non-goals**: No abandonment of ECS. No App Runner Terraform in this ADR (deferred to PR 0034). No APRANA (retired entirely).

### 4. ADR-0009: Config Governance (NEW)

**Status**: Accepted

Content:

- **Core principle**: Config is not model. Config has its own lifecycle, separate from model artifacts.
- **Config change classes**:

| Class | Examples | Runtime apply without restart? | Requires redeploy? |
|-------|----------|-------------------------------|-------------------|
| A — Operational | Log level, health check interval, max concurrent jobs | Yes | No |
| B — Decision-adjacent | Thresholds, QC criteria versions | Yes, with validation + audit | No |
| C — Model-binding | Model version, model bucket, feature schema | No | Yes — restart/redeploy required |
| D — Structural | API routes, auth, network | No | Yes |

- **Config state requirements**: Versioned, timestamped, auditable, reproducible.
- **Future gates**:

| Gate | Question | Status |
|------|----------|--------|
| G-CFG-1 (existing) | Build in-house vs. adopt existing config-management product | OPEN |
| G-CFG-2 (new) | Config state history store: DynamoDB vs. other | OPEN |
| G-CFG-3 (new) | Config validation schema: JSON Schema vs. Pydantic vs. custom | OPEN |

- **Prediction output amendment**: `config_version` / `config_hash` must be added to prediction output invariant once config governance is implemented. (The `project_contract.yml` amendment is deferred to the config governance PR.)
- **Non-goals**: No config editing UI in this ADR. No runtime config apply implementation. No config state database creation. G-CFG-1, G-CFG-2, G-CFG-3 remain OPEN.

## APRANA retirement rules

1. **Every occurrence of "APRANA" in ROADMAP.md and ADR-0006 must be removed or replaced** with explicit "AWS App Runner" language.
2. **APRANA must not be carried forward** into any future PR, gate, target name, or documentation.
3. **The term "APRANA" in ADR-0006 was an unverified placeholder; App Runner is a real AWS service.** These are not the same thing.
4. **Do not use "APRANA" as a synonym for App Runner anywhere in the new content.**

## App Runner / ECS wording rules

1. App Runner is the **near-term proving/testing target**.
2. ECS Fargate is the **long-term primary production target**.
3. App Runner does NOT replace ECS. The existing Terraform ECS skeleton is retained.
4. G-API-2 is amended to record both targets, not replaced.
5. Do not claim App Runner is production-ready for Bremen at this stage.
6. Do not claim ECS is abandoned.

## Model binding lifecycle wording rules

1. "Runtime image must not contain model artifacts."
2. "Deployment config/env selects model identity."
3. "Startup fetches/stages/validates/loads the selected model package."
4. "`joblib.load()` remains behind controlled post-validation boundary."
5. "Runtime serves requests from the in-memory loaded model."
6. "Model updates require redeploy/restart/rolling replacement."
7. "No hot-swap and no per-request model loading."

## Config governance wording rules

1. "Config is separate from model."
2. "Config may require validated runtime editing/apply later."
3. "Config states must be versioned, timestamped, auditable, and reproducible."
4. "Prediction/audit records eventually need config identity (`config_version` or `config_hash`)."
5. Define config change classes (A/B/C/D) as specified above.
6. Add gates G-CFG-2 and G-CFG-3.
7. Do NOT implement config UI/API/database in PR 0030.

## `.project-memory/project_contract.yml` decision

**Decision: NOT modified in PR 0030.**

Rationale: The config governance prediction output field addition (`config_version`, `config_hash`) and the config change-class safety invariant are important but belong in a dedicated config governance PR (PR 0039), not in the App Runner pivot PR. PR 0030 already carries ROADMAP + 3 ADRs. Adding the contract amendment would increase review burden without blocking the App Runner pivot. The ADR-0009 already records the intent to amend the prediction output once config governance is implemented.

## DS / model package composition follow-up

The rebaseline artifact identifies an open question: whether Mahalanobis/Wasserstein-style features require fitted reference statistics. PR 0030 does NOT answer this question. PR 0035 (DS feature inventory) is reserved for this purpose. The current `model_loader.py` `model: Any` type is already composite-compatible at the loader level. The manifest schema constraint (single `model_filename`) is documented as a current limitation that must be resolved before preprocessing/inference.

## Non-goals

- No source code changes.
- No test changes.
- No CI/CD workflow changes.
- No Terraform changes.
- No Dockerfile or dependency changes.
- No `project_contract.yml` changes (deferred to config governance PR).
- No config editing implementation.
- No App Runner implementation (CI/CD, Terraform, deploy path).
- No model package format changes.
- No H5/preflight implementation.
- No preprocessing or inference implementation.
- No clinical claims.

## Validation checklist

The implementation phase (architect) must execute these checks:

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5-8) File existence
test -f ROADMAP.md || exit 1
test -f docs/adr/0006-multi-target-deployment-and-iac.md || exit 1
test -f docs/adr/0008-runtime-target-apprunner-proving.md || exit 1
test -f docs/adr/0009-config-governance.md || exit 1
```

### APRANA retirement checks

```bash
# 9) No APRANA in ROADMAP.md except retirement statements
grep -n "APRANA" ROADMAP.md || true

# 10) No APRANA in ADR-0006
grep -n "APRANA" docs/adr/0006-multi-target-deployment-and-iac.md || true
```

### App Runner / ECS checks

```bash
# 11) App Runner mentioned as proving target, not replacement
grep -n "App Runner" ROADMAP.md docs/adr/0008-runtime-target-apprunner-proving.md || exit 1

# 12) ECS Fargate still present as primary target
grep -n "ECS Fargate" ROADMAP.md docs/adr/0008-runtime-target-apprunner-proving.md || exit 1
```

### Model lifecycle checks

```bash
# 13) Model lifecycle section present in ROADMAP.md
grep -n "Model binding lifecycle" ROADMAP.md || exit 1

# 14) Contains "no model artifacts inside image"
grep -q "no model artifacts inside image" ROADMAP.md || exit 1

# 15) Contains "No hot-swap"
grep -q "No hot-swap" ROADMAP.md || exit 1
```

### Config governance checks

```bash
# 16) ADR-0009 exists
test -f docs/adr/0009-config-governance.md || exit 1

# 17) Contains config change classes
grep -q "Class A\|class A\|Operational parameters" docs/adr/0009-config-governance.md || exit 1

# 18) Contains G-CFG-2 and G-CFG-3
grep -q "G-CFG-2" docs/adr/0009-config-governance.md || exit 1
grep -q "G-CFG-3" docs/adr/0009-config-governance.md || exit 1
```

### Forbidden path checks

```bash
# 19) No source/test/CI/Terraform/Docker changes
git diff --name-only -- src tests .github infra Dockerfile .dockerignore requirements.txt pyproject.toml config examples || true
# Must return nothing
```

### Security checks

```bash
# 20) No secrets/account IDs in changed files
grep -R -n "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|AKIA\|SecretAccessKey" ROADMAP.md docs/adr/0006*.md docs/adr/0008*.md docs/adr/0009*.md || true

# 21) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

1. **Revert ROADMAP.md** — restore pre-PR-0030 version.
2. **Revert ADR-0006** — restore pre-PR-0030 version (with APRANA section).
3. **Delete ADR-0008** — `docs/adr/0008-runtime-target-apprunner-proving.md`.
4. **Delete ADR-0009** — `docs/adr/0009-config-governance.md`.

No runtime, infrastructure, or dependency rollback needed.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only the 4 allowed files changed (ROADMAP.md, ADR-0006, ADR-0008, ADR-0009). |
| **APRANA drift** | APRANA removed from ROADMAP.md and ADR-0006. No remaining APRANA-forward language. |
| **App Runner drift** | Described as near-term proving target, not ECS replacement. ECS Fargate remains primary/long-term. |
| **Model lifecycle drift** | Confirmed: no model-in-image, no hot-swap, startup-time load, request-time serve only. |
| **Config governance drift** | ADR-0009 defines change classes, gates G-CFG-2/G-CFG-3, defers implementation. Project_contract.yml not modified. |
| **PR sequence drift** | Updated to include model fetch/staging, App Runner deploy, DS inventory, config governance. Does not reuse PR numbers. |
| **Validation drift** | All 21 validation checks pass. No secrets/account IDs in changed files. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Rebaseline artifact (`.project-memory/architecture/runtime-model-config-roadmap-rebaseline.md`) is missing.
- ADR numbering conflicts with existing ADR files (0008 and 0009 are available after 0007).
- ROADMAP cannot be updated without changing runtime code.
- App Runner wording replaces ECS instead of adding a near-term proving target.
- APRANA remains as a future target (must be removed entirely).
- Model lifecycle text implies hot-swap or per-request loading.
- Config governance text implies runtime model-binding changes are allowed.
- The plan requires workflow/Terraform/source changes.
- The plan cannot stay docs/ADR/roadmap-only.

## Decisions summary

| Decision | Value |
|----------|-------|
| Allowed files | ROADMAP.md, ADR-0006, ADR-0008 (NEW), ADR-0009 (NEW) |
| Implementation agent | Agent: architect, Mode: docs/ADR/roadmap write |
| APRANA | Retired entirely. Removed from ROADMAP.md and ADR-0006. Not carried forward. |
| App Runner | Near-term proving target. ECS Fargate remains primary/long-term. |
| G-API-2 amendment | "ECS Fargate (primary/long-term), App Runner (near-term proving)" |
| PR 0023 | Changed from "APRANA / App Runner evaluation" to "App Runner proving target" |
| Model lifecycle | Confirmed. Documented in ROADMAP.md. No model-in-image, no hot-swap. |
| Config governance | ADR-0009 created. Change classes A/B/C/D defined. G-CFG-2, G-CFG-3 added. |
| project_contract.yml | NOT modified in PR 0030. Config governance prediction fields deferred to PR 0039. |
| Revised PR sequence | PR 0030 (this) → 0031 (App Runner tag) → 0032 (fetch/staging) → 0033 (startup load) → 0034 (App Runner Terraform) → 0035 (DS inventory) → 0036 (H5 gate) → 0037 (preprocessing) → 0038 (inference) → 0039 (config governance) |

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0030-roadmap-adr-apprunner-pivot/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0030-roadmap-adr-apprunner-pivot/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Files read

- `.project-memory/architecture/runtime-model-config-roadmap-rebaseline.md`
- `.project-memory/project_contract.yml`
- `ROADMAP.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0006-multi-target-deployment-and-iac.md`
- `docs/adr/0007-model-artifact-lifecycle.md`

## Files written

- `.project-memory/pr/0030-roadmap-adr-apprunner-pivot/PLAN.md` (this file)

## Files intentionally ignored

- All source, test, CI, Terraform, Docker, and dependency files.
- All ADRs not in the allowed set (0001–0005, 0007 are read-only).
- `.project-memory/project_contract.yml` (not modified per decision).

## Boundary confirmations

- confirm: branch is `0030-roadmap-adr-apprunner-pivot`: yes
- confirm: only docs/ADR/roadmap files planned: yes
- confirm: no source/test/CI/Terraform/Docker changes planned: yes
- confirm: APRANA retired from ROADMAP and ADR-0006: yes
- confirm: App Runner is near-term proving target, not ECS replacement: yes
- confirm: ECS Fargate remains primary/long-term target: yes
- confirm: G-API-2 amended but not replaced: yes
- confirm: model lifecycle confirmed (no model-in-image, no hot-swap): yes
- confirm: config governance ADR created (change classes, gates, deferred implementation): yes
- confirm: `project_contract.yml` not modified in this PR: yes
- confirm: implementation assigned to Agent: architect / Mode: docs/ADR/roadmap write: yes
- confirm: no git mutation commands run: yes
