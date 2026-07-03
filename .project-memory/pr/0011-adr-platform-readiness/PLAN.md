# PR 0011C — Plan Platform Readiness ADR Bundle (Microservice/API, Config Management, Dependency Stabilization, Multi-Target Deployment)

Author: plan
Mode: planning only
Branch: 0011-adr-platform-readiness

## Objective

Create four new ADRs (0003–0006) and extend ROADMAP.md and docs/architecture.md with platform-readiness architecture decisions. This is the third and final step of the 0011A/B/C lettered cascade. It adds platform-readiness ADRs on top of the now-settled identity foundation from PR 0011A and PR 0011B.

This PR extends ROADMAP.md and docs/architecture.md — it appends new sections without removing or rewriting existing PR 0011A content. It does not write implementation code, CI YAML, Terraform/CDK, or docs/api_contract.md content — those are delegated to future numbered PRs.

## Precondition verification

All four PR 0011A baseline files must exist:
```bash
test -f docs/adr/0001-bremen-product-identity.md
test -f docs/adr/0002-twin-product-document-separation.md
test -f ROADMAP.md
test -f docs/architecture.md
```

Both PR 0011B identity anchors must be present:
```bash
grep -q "Should patient continue to MRI?" README.md
grep -q "Bremen Machine Learning Concept" docs/machine_learning_concept.md
```

All preconditions are confirmed satisfied on the current HEAD.

## Why this PR is required

Four engineering facts require platform-readiness architecture decisions now:

1. **Static local-path config coupling**: Bremen's preprocessing/training configuration is static YAML under `config/preprocessing/`, chained via `extends:`, with relative local paths (e.g., `io.output_joblib_path: ../../examples/outputs/...` — confirmed in `config/preprocessing/bremen_one_to_one_minimal_v0_1.yaml`). This couples Bremen's operating mode to a local checkout — a problem once Bremen runs as a cloud microservice.

2. **Private container dependency pinned to feature branch**: `.github/workflows/quality.yml` installs `"git+https://github.com/Eos-Dx/container.git@feat/v0_3-eoscan-session-container"` — a feature branch, not main. `requirements.txt` separately contains a personal-machine local path (`-e /Users/sad/dev/container`). Both must be stabilized.

3. **Undocumented target architecture**: Bremen is intended to run as a containerized AWS microservice with API endpoints called repeatedly by the platform. This has not been formally decided anywhere except in prose.

4. **Multiple registry targets required**: Bremen currently publishes only to GHCR (PR 0007). AWS ECR and a platform referred to as "APRANA" (name UNVERIFIED — treat as placeholder) are required additional targets.

This PR captures formal architecture decisions for these facts. Implementation of each decision is delegated to specific future numbered PRs.

## 0011A/B/C cascade context

This is the final step of the agreed lettered cascade:

- **PR 0011A** — Architect baseline documents (ADR-0001, ADR-0002, ROADMAP.md, docs/architecture.md) — merged.
- **PR 0011B** — Identity documentation cascade (README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md) — merged.
- **PR 0011C** — This PR: Platform Readiness ADR Bundle (ADR-0003 through ADR-0006, ROADMAP.md extension, docs/architecture.md extension).

After this cascade, sequencing returns to normal one-number-one-PR numbering (PR 0012 onward) and the Platform Readiness Track defined here runs parallel to the Product Track.

## Exact allowed implementation files

The implementation phase (Agent: architect, Mode: WRITE) may create or modify exactly these files:

1. `docs/adr/0003-bremen-microservice-api-architecture.md` — NEW
2. `docs/adr/0004-bremen-configuration-management-strategy.md` — NEW
3. `docs/adr/0005-container-dependency-stabilization.md` — NEW
4. `docs/adr/0006-multi-target-deployment-and-iac.md` — NEW
5. `ROADMAP.md` — EDIT (append only — do not remove PR 0011A content)
6. `docs/architecture.md` — EDIT (append only — do not remove PR 0011A content)

## Exact forbidden files

- `docs/adr/0001-*.md`, `docs/adr/0002-*.md` (already merged, read-only)
- `docs/api_contract.md` (delegated to future PR — not created here)
- `src/bremen/config.py`, `config/**`, `requirements.txt`, `.github/workflows/quality.yml`, `Dockerfile` (read as evidence only — fixes delegated to future PRs)
- `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`, `docs/product_development_rules.md`, `AGENTS.md`
- `src/**`, `tests/**`, `examples/**`
- `.dockerignore`, `sonar-project.properties`, `pyproject.toml`, `environment.yml`, `Makefile`
- `agents/**`
- Any H5/HDF5, joblib/pkl/npy/npz artifact
- Terraform/CDK/CloudFormation/IaC files
- `.project-memory/**` other than this PR's own PLAN.md/reviews

## Required reads (completed for this PLAN.md)

- `docs/adr/0001-bremen-product-identity.md` — product identity anchors
- `docs/adr/0002-twin-product-document-separation.md` — separation policy
- `ROADMAP.md` (current) — exact insertion point for Platform Readiness Track and Decision Gate Register
- `docs/architecture.md` (current) — exact insertion point after closing note; existing Project Contract Invariant Inventory heading
- `.project-memory/project_contract.yml` — full 11 safety invariants; new content must not contradict them
- `src/bremen/config.py` — current discovery contract from PR 0009
- `tests/test_bremen_config_loading.py` — current config loading test suite
- `config/preprocessing/bremen_one_to_one_minimal_v0_1.yaml` — confirms relative local paths
- `.github/workflows/quality.yml` — confirms feat/v0_3 branch pin for container package
- `Dockerfile` — current GHCR-only build
- `requirements.txt` — confirms `-e /Users/sad/dev/container` local-path defect
- `agents/architect.yml` — confirms write permissions for `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`

## Implementation phase assignment

- **Agent**: architect
- **Mode**: WRITE

**Reason**: All six implementation files are architect-reserved paths per `agents/architect.yml`: `docs/adr/**` (four new ADRs), `ROADMAP.md` (append), and `docs/architecture.md` (append). The coder role lacks write permission for these paths.

## ADR-0003 planned content: docs/adr/0003-bremen-microservice-api-architecture.md

**Status**: Accepted

### Decisions

- Bremen runtime is a containerized AWS microservice with API endpoints, extending (not replacing) the core chain already in docs/architecture.md:
  > Matador → Bremen API → H5 inspect gate → preprocessing/feature extraction → joblib inference → QC → prediction JSON → Matador storage/report layer
- Minimum endpoint skeleton (sketch only, not a final contract):
  - `POST /predictions` — Submit target/control H5 references. Returns `job_id` or full result depending on Gate G-API-1 resolution.
  - `GET /predictions/{id}` — Retrieve prediction result by ID.
  - `GET /health` — Health check endpoint.
  - `GET /model/version` — Current model version metadata.
- Every prediction response must carry the mandatory fields (restated verbatim from `project_contract.yml`):
  - `prediction_id`, `model_version`, `model_checksum`, `feature_schema_version`, threshold version/value, `qc_status`, `qc_flags`
- Runtime must not train models (restated as an API-level constraint).
- This ADR does NOT create `docs/api_contract.md` — that is delegated to PR 0019.

### OPEN Decision Gates (explicitly revisable, not final)

- **G-API-1**: Sync request/response vs. async submit-then-poll. Recommended default: async, because latency is uncharacterized.
- **G-API-2**: AWS compute target (ECS Fargate vs. Lambda-container vs. EKS). Recommended default: ECS Fargate, reuses existing Dockerfile.

## ADR-0004 planned content: docs/adr/0004-bremen-configuration-management-strategy.md

**Status**: Accepted

### Context (cited from evidence)

- Current config is static YAML under `config/preprocessing/`, chained via `extends:` (confirmed in `bremen_one_to_one_minimal_v0_1.yaml`).
- Config files use relative local paths (e.g., `io.output_joblib_path: ../../examples/outputs/...`), coupling Bremen's operating mode to a local checkout.
- Config discovery is implemented in `src/bremen/config.py` with deterministic order: explicit path → `BREMEN_CONFIG` env → `bremen.yml` → `bremen.yaml` → `bremen.toml` → `ConfigNotFoundError`.
- Config loading tests exist in `tests/test_bremen_config_loading.py` (PR 0009).

### Decisions

- **Config versioning discipline**: Every semantically meaningful config change bumps a version marker; no silent overwrite.
- **Config sourcing must become environment-aware for cloud deployment**: The PR 0009 discovery order must not be broken. A future PR extends it to support a remote/mounted source (e.g., S3-backed or environment-injected) without changing existing local-discovery semantics.
- **Config editing surface**: EXPLICITLY DEFERRED (not designed here). Non-negotiable guardrails for when it is built:
  - Must reuse the existing config-validation contract.
  - Must disable unsafe YAML features (no arbitrary Python execution).
  - Must never hot-write to a production-serving config without review/approval.
  - Every write must be versioned and attributable.

### OPEN Decision Gate

- **G-CFG-1**: Build in-house vs. adopt an existing config-management/feature-flag product. Not decided here.

## ADR-0005 planned content: docs/adr/0005-container-dependency-stabilization.md

**Status**: Accepted

### Context (cited from evidence)

- `.github/workflows/quality.yml` installs `"git+https://github.com/Eos-Dx/container.git@feat/v0_3-eoscan-session-container"` — pinned to a feature branch, not main.
- `requirements.txt` contains a separate local-path defect: `-e /Users/sad/dev/container`.
- The current safety net is the `VERSION_REGISTRY "0_3"` assertion in the CI workflow (`from container.registry import VERSION_REGISTRY; assert "0_3" in VERSION_REGISTRY`).

### Decisions

- The container repo merging `feat/v0_3` to `main` is an EXTERNAL EVENT, not a schedulable date. Registered as event-triggered Decision Gate **G-DEP-1** in ROADMAP.md, not a calendar date.
- Required response once that event happens: re-pin within a fixed window (recommended default: 5 business days, marked revisable). Re-verify the `VERSION_REGISTRY` assertion against the new main — do not assume it still holds.
- The `requirements.txt` local-path defect (`-e /Users/sad/dev/container`) is fixed in the same delegated PR as the re-pin work, since both are "container dependency hygiene."

## ADR-0006 planned content: docs/adr/0006-multi-target-deployment-and-iac.md

**Status**: Accepted

### Context (cited from evidence)

- GHCR publish exists and works (PR 0007): `ghcr.io/eos-dx/bremen` with `latest` and `sha` tags on push to main.
- No AWS ECR target exists.
- No Infrastructure-as-Code exists.
- No target referred to as "APRANA" exists or is configured.

### Decisions

- **AWS ECR**: Add as a second registry target, with the same non-negotiable CI safety rules as GHCR:
  - Human-provided secrets only; no baked credentials.
  - No destructive infra changes without human review.
  - Publish gated to merge-to-main/release tag.
- **APRANA**: EXPLICITLY UNVERIFIED. Before any implementation PR touches it, a human must confirm the exact platform name, EOL timeline, and access model. This ADR records intent only and does not invent technical specifics. APRANA is explicitly deprioritized relative to AWS/ECR.
- **IaC**: Required for whichever AWS resources ADR-0003 and ADR-0006 imply. Not written here.

### OPEN Decision Gate

- **G-INFRA-1**: Terraform vs. AWS CDK vs. CloudFormation. Recommended default: Terraform, marked revisable.

## ROADMAP.md extension

Append two new top-level sections after the existing content (after the "Items 8–12 must not be silently dropped..." paragraph, before any final line). Do not remove or renumber the existing Product Track sequence.

### `## Platform Readiness Track (parallel to Product Track)`

| PR | Description | Depends on |
|----|-------------|------------|
| PR 0019 | **API contract + microservice skeleton** — Delegated from ADR-0003. Creates `docs/api_contract.md` + non-functional stub routes. | Gates G-API-1 and G-API-2 explicitly closed first |
| PR 0020 | **Cloud-aware config sourcing** — Delegated from ADR-0004. Extends `src/bremen/config.py` without breaking PR 0009 tests. | PR 0019 |
| PR 0021 | **Container dependency hygiene** — Delegated from ADR-0005. Fixes `requirements.txt` local-path defect immediately (no dependency). Re-pin itself is separately event-triggered via G-DEP-1. | None |
| PR 0022 | **IaC skeleton + ECR publish job** — Delegated from ADR-0006. | G-INFRA-1 and G-API-2 closed |
| PR 0023 | **APRANA CI/CD publish job** — Delegated from ADR-0006. BLOCKED until platform name/access confirmed. No date until unblocked. | Platform name/access confirmed |
| PR 0024 | **Config editing surface** — Delegated from ADR-0004. BLOCKED on G-CFG-1. Not date-bound. Scheduled only after Product Track's core classifier work (operator-convenience, not product-critical path). | G-CFG-1, Product Track core classifier |

### `## Decision Gate Register`

| Gate ID | Question | Trigger type | Recommended default | Status | Decided value |
|---------|----------|-------------|-------------------|--------|---------------|
| G-API-1 | Sync vs. async request/response | Date-bound (before PR 0019) | Async submit-then-poll | OPEN | — |
| G-API-2 | AWS compute target (ECS Fargate vs. Lambda-container vs. EKS) | Date-bound (before PR 0019, PR 0022) | ECS Fargate | OPEN | — |
| G-CFG-1 | Build in-house vs. adopt existing config-management product | Date-bound (before PR 0024) | Not decided | OPEN | — |
| G-DEP-1 | Container repo merges feat/v0_3 to main | Event-bound (external event) | Re-pin within 5 business days; re-verify VERSION_REGISTRY | OPEN | — |
| G-INFRA-1 | Terraform vs. AWS CDK vs. CloudFormation | Date-bound (before PR 0022) | Terraform | OPEN | — |

Plus one explicit paragraph:

> Calendar dates in the Product Track may drift and that's expected. What's required is that any slip is recorded with a reason, and no PR silently absorbs scope from an open Decision Gate without that gate first being marked DECIDED.

## docs/architecture.md extension

Append four new sections after the existing "## Closing note" section. Do not remove or rewrite the existing "## Project Contract Invariant Inventory" or any other PR 0011A content.

### `## Deployment Topology`

Describe:
- GHCR (existing) — `ghcr.io/eos-dx/bremen`, `latest` and `sha` tags on push to main.
- AWS ECR (planned, PR 0022) — second registry target, same CI safety rules.
- APRANA (planned, name unverified) — interim/EOL fallback, deprioritized relative to ECR.
- AWS as primary long-term target.

### `## API Surface (Draft)`

Restate the ADR-0003 endpoint sketch, labeled draft pending `docs/api_contract.md` (PR 0019):
- `POST /predictions`, `GET /predictions/{id}`, `GET /health`, `GET /model/version`.
- Restate the mandatory prediction response field list from the Project Contract Invariant Inventory.
- Label as "DRAFT — not a binding contract until PR 0019 is merged."

### `## Configuration Management`

Describe:
- Current state: static local YAML discovery via `src/bremen/config.py`, relative local paths, `extends:` chaining.
- Target state: cloud-aware sourcing (PR 0020), environment-aware config without breaking PR 0009 discovery order.
- Deferred state: config editing surface (PR 0024), gated on G-CFG-1.

### `## External Dependency Risk`

Describe:
- The `container` dependency pinned to `feat/v0_3` feature branch.
- Why it exists: `VERSION_REGISTRY "0_3"` support is not yet on main.
- Event-triggered response plan: G-DEP-1; re-pin to main within 5 business days; re-verify VERSION_REGISTRY assertion.
- The `requirements.txt` local-path defect (`-e /Users/sad/dev/container`) is part of the same hygiene work (PR 0021).

## Non-goals

- No code, no CI YAML, no Terraform/CDK/CloudFormation files.
- No `docs/api_contract.md` content (delegated to PR 0019).
- No `src/bremen/config.py` changes (delegated to PR 0020).
- No `requirements.txt` or `quality.yml` edits (delegated to PR 0021).
- No guessing APRANA's real technical details beyond the name as given (explicitly labelled unverified).
- No closing any Decision Gate — this PR proposes defaults, does not decide.
- No removal or rewrite of existing ROADMAP.md or docs/architecture.md content from PR 0011A.
- No changes to `docs/adr/0001-*.md` or `docs/adr/0002-*.md` (already merged, read-only).

## Validation checklist

The implementation phase (architect) must execute these checks:

```bash
# 1) Working tree state
git status --short

# 2) Changed files — only the 6 allowed files
git diff --name-only

# 3) Precondition: ADR-0001 still present
test -f docs/adr/0001-bremen-product-identity.md || exit 1

# 4) ROADMAP.md heading count sanity
echo "PRE-CHANGE: 2 sections (## Completed foundation PRs, ## Product Track sequence)"
echo "POST-CHANGE: should be 4 sections (add ## Platform Readiness Track, ## Decision Gate Register)"
PRE=$(grep -c "^## " ROADMAP.md)
echo "Current heading count: $PRE"
echo "Expected after extension: $(($PRE + 2))"

# 5) APRANA marked as unverified
grep -q "UNVERIFIED\|unverified\|EXPLICITLY UNVERIFIED\|placeholder" docs/adr/0006-multi-target-deployment-and-iac.md || exit 1

# 6) Platform Readiness Track present in ROADMAP.md, absent in docs/architecture.md
grep -q "Platform Readiness Track" ROADMAP.md || exit 1
grep -c "Platform Readiness Track" docs/architecture.md | xargs test 0 -eq || exit 1

# 7) Decision Gate Register present
grep -q "Decision Gate Register" ROADMAP.md || exit 1

# 8) All 5 Decision Gates present in ROADMAP.md
for g in G-API-1 G-API-2 G-CFG-1 G-DEP-1 G-INFRA-1; do
  grep -q "$g" ROADMAP.md || exit 1
done

# 9) Project Contract Invariant Inventory still present (not overwritten)
grep -q "Project Contract Invariant Inventory" docs/architecture.md || exit 1

# 10) No forbidden file changes
git diff --name-only -- README.md docs/roadmap.md docs/machine_learning_concept.md docs/repository_cleanup.md docs/product_development_rules.md src tests config examples .github Dockerfile requirements.txt pyproject.toml environment.yml Makefile AGENTS.md agents/ docs/api_contract.md
# Must return nothing

# 11) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

If any of the four new ADRs or the two extended files contain errors:

1. **ADR-0003, ADR-0004, ADR-0005, ADR-0006** — Delete the individual ADR file. No other files are affected.
2. **ROADMAP.md** — Revert the append-only change (remove the Platform Readiness Track and Decision Gate Register sections). The existing Product Track content is preserved.
3. **docs/architecture.md** — Revert the append-only change (remove the four new extension sections). The existing PR 0011A content is preserved.

Each file is independent and can be reverted individually. The existing PR 0011A content in ROADMAP.md and docs/architecture.md is never removed or rewritten — only appended to.

## Follow-up PRs

After PR 0011C merges:

- **PR 0019** — API contract + microservice skeleton (delegated from ADR-0003)
- **PR 0020** — Cloud-aware config sourcing (delegated from ADR-0004)
- **PR 0021** — Container dependency hygiene (delegated from ADR-0005)
- **PR 0022** — IaC skeleton + ECR publish job (delegated from ADR-0006)
- **PR 0023** — APRANA CI/CD publish job (delegated from ADR-0006; blocked)
- **PR 0024** — Config editing surface (delegated from ADR-0004; gated)
- **PR 0012 onward** — Normal sequencing resumes for Product Track items not covered by this cascade.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 4 new ADRs + ROADMAP.md + docs/architecture.md changed. No other files. |
| **ADR-0003 drift** | AWS microservice, minimum endpoint skeleton, mandatory response fields, no runtime training, G-API-1/G-API-2 OPEN. No docs/api_contract.md created. |
| **ADR-0004 drift** | Context cites actual evidence (extends chains, relative paths, PR 0009 contract). Config versioning. Environment-aware sourcing deferred. Config editing surface deferred with guardrails. G-CFG-1 OPEN. |
| **ADR-0005 drift** | Context cites feat/v0_3 pin, VERSION_REGISTRY assertion, local-path defect. G-DEP-1 event-triggered. Re-pin window documented. |
| **ADR-0006 drift** | Context: GHCR exists, ECR/APRANA/IaC don't. ECR with same safety rules as GHCR. APRANA explicitly unverified. G-INFRA-1 OPEN. |
| **ROADMAP.md drift** | Appended only. Product Track content not removed. Platform Readiness Track has 6 PRs. Decision Gate Register has 5 gates, all OPEN. |
| **Architecture drift** | Appended only. Project Contract Invariant Inventory preserved. 4 new sections: Deployment Topology, API Surface (Draft), Configuration Management, External Dependency Risk. |
| **Implementation agent drift** | Assigned to Agent: architect, Mode: WRITE. Not assigned to coder. |
| **Safety invariant drift** | New API/config/deployment content does not contradict any of the 11 project_contract.yml invariants. |
| **Delegation drift** | No implementation content written in this PR (no CI YAML, no IaC, no config.py changes, no api_contract.md). Everything delegated to numbered future PRs. |
| **Validation drift** | All validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Any ADR proposes a technical decision as final when this PLAN.md requires it be marked as an OPEN Decision Gate.
- APRANA is stated as a confirmed platform name/technical detail (must be marked unverified).
- PLAN.md instructs removal or rewrite of existing PR 0011A ROADMAP.md or docs/architecture.md content.
- PLAN.md includes `docs/api_contract.md`, `src/bremen/config.py`, CI, IaC, or any other delegated-implementation content directly.
- Implementation phase is assigned to coder instead of architect.
- Any safety invariant from `project_contract.yml` is contradicted or weakened by planned API/config/deployment content.
- Any file outside the six allowed implementation files is planned.

## Decisions summary

### Allowed files
1. `docs/adr/0003-bremen-microservice-api-architecture.md` — NEW
2. `docs/adr/0004-bremen-configuration-management-strategy.md` — NEW
3. `docs/adr/0005-container-dependency-stabilization.md` — NEW
4. `docs/adr/0006-multi-target-deployment-and-iac.md` — NEW
5. `ROADMAP.md` — EDIT (append only)
6. `docs/architecture.md` — EDIT (append only)

### Forbidden files
- All ADR 0001-0002, docs/api_contract.md, src/**, tests/**, config/**, examples/**
- All infrastructure files (Docker, CI, SonarCloud, pyproject, env, Makefile)
- README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md, docs/product_development_rules.md, AGENTS.md
- agents/**
- Terraform/CDK/CloudFormation/IaC files
- H5/HDF5, model artifacts

### ADR-0003 summary
- Containerized AWS microservice with API endpoints. Minimum skeleton: POST /predictions, GET /predictions/{id}, GET /health, GET /model/version. Mandatory response fields from project_contract.yml. No runtime training. G-API-1 (sync vs async), G-API-2 (compute target) OPEN.

### ADR-0004 summary
- Static YAML with extends chains and relative local paths. Config versioning required. Environment-aware sourcing deferred (must not break PR 0009 discovery order). Config editing surface deferred with guardrails. G-CFG-1 (build vs adopt) OPEN.

### ADR-0005 summary
- container pinned to feat/v0_3 feature branch. VERSION_REGISTRY assertion as safety net. requirements.txt local-path defect. G-DEP-1 event-triggered. Re-pin within 5 business days of feat/v0_3 → main.

### ADR-0006 summary
- GHCR exists. Add ECR with same safety rules. APRANA unverified/deprioritized. IaC required. G-INFRA-1 (Terraform vs CDK vs CF) OPEN.

### ROADMAP extension summary
- Platform Readiness Track: 6 PRs (0019-0024), 3 with dependencies/gates.
- Decision Gate Register: 5 gates (G-API-1, G-API-2, G-CFG-1, G-DEP-1, G-INFRA-1), all OPEN.

### Architecture extension summary
- 4 new sections: ## Deployment Topology, ## API Surface (Draft), ## Configuration Management, ## External Dependency Risk.

### Implementation agent assignment
- Agent: architect
- Mode: WRITE

### Validation checklist
11 checks: git state, changed files, precondition, heading count, APRANA unverified marker, Platform Readiness Track presence/absence, Decision Gate Register, all 5 gate IDs, Project Contract Invariant Inventory preservation, forbidden file changes, .DS_Store.

### Stop conditions
7 block conditions.

### Rollback plan
Each ADR independently deleteable. ROADMAP.md and docs/architecture.md edits are append-only — revert by removing the appended sections.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0011-adr-platform-readiness/PLAN.md`
2. Human runs: `git add .project-memory/pr/0011-adr-platform-readiness/PLAN.md`
3. Human runs: `git commit -m "PR 0011C — Plan Platform Readiness ADR bundle"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the architect implements the six allowed files.

## Files read

- `docs/adr/0001-bremen-product-identity.md`
- `docs/adr/0002-twin-product-document-separation.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `.project-memory/project_contract.yml`
- `src/bremen/config.py`
- `tests/test_bremen_config_loading.py`
- `config/preprocessing/bremen_one_to_one_minimal_v0_1.yaml`
- `.github/workflows/quality.yml`
- `Dockerfile`
- `requirements.txt`
- `agents/architect.yml`

## Files written

- `.project-memory/pr/0011-adr-platform-readiness/PLAN.md` (this file)

## Files intentionally ignored

- All source, test, config, example files
- All infrastructure files (Docker, CI, SonarCloud, pyproject, env)
- ADR-0001, ADR-0002 (read-only references)
- README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md, AGENTS.md
- agents/**
- Any H5/HDF5 or model artifacts
- Terraform/CDK/CloudFormation/IaC files

## Boundary confirmations

- confirm: precondition files (PR 0011A+0011B outputs) verified present: yes
- confirm: this PR only plans 4 new ADRs + ROADMAP.md/docs/architecture.md extensions, appended not replacing existing content: yes
- confirm: no docs/api_contract.md, config.py, CI, IaC content planned directly — all delegated: yes
- confirm: APRANA marked unverified throughout: yes
- confirm: all 5 Decision Gates marked OPEN, not decided: yes
- confirm: implementation phase assigned to Agent: architect, Mode: WRITE: yes
- confirm: no git mutation commands run: yes
