# PR 0012 — Plan Model Artifact Lifecycle and Runtime Deployment Gate Closure

Author: plan
Mode: planning only
Branch: 0012-model-artifact-lifecycle-gates

## Objective

Formalize Bremen's model artifact lifecycle (offline training, controlled package, runtime loading, artifact storage, security boundaries) and record the human decision to close G-API-1, G-API-2, and G-INFRA-1. This is a docs-only architect PR that creates ADR-0007 and extends ROADMAP.md and docs/architecture.md.

The 0011A/B/C lettered cascade is closed. Normal one-number-one-PR numbering resumes at PR 0012.

## Human decisions being recorded

The following human product/engineering decisions are recorded in this PR:

1. **G-API-1** = DECIDED. Value: asynchronous prediction API (submit → `job_id` → poll).
2. **G-API-2** = DECIDED. Value: ECS Fargate.
3. **G-INFRA-1** = DECIDED. Value: Terraform.
4. **Model artifact strategy** = DECIDED. Separate controlled checksum-verified model package artifact.
5. **Joblib is built offline only** — not during runtime service execution and not by the Docker image CI/CD pipeline.
6. **Runtime service loads an already-trained model package from artifact storage** — no training in the runtime.
7. **Initial model artifact store** = S3 versioned bucket.
8. **Model publication flow** is delegated to a future implementation PR — not defined here.

G-CFG-1 and G-DEP-1 remain OPEN.

## Exact allowed implementation files

The implementation phase (Agent: architect, Mode: WRITE) may create or modify exactly these files:

1. `docs/adr/0007-model-artifact-lifecycle.md` — NEW
2. `ROADMAP.md` — EDIT (add ADR-0007/PR 0012 entry, close G-API-1/G-API-2/G-INFRA-1, add execution-order guidance, add numbering clarification)
3. `docs/architecture.md` — EDIT (add Offline model artifact lifecycle, Online prediction runtime workflow, AWS runtime/deployment default decisions, Safety sections)

## Exact forbidden files

- `src/**`, `tests/**`, `config/**`, `examples/**`
- `.github/**`, `Dockerfile`, `.dockerignore`, `requirements.txt`, `pyproject.toml`, `sonar-project.properties`, `environment.yml`, `Makefile`
- `docs/api_contract.md`
- `docs/adr/0001-*.md` through `docs/adr/0006-*.md` (already merged, read-only)
- `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`
- `AGENTS.md`, `agents/**`
- Any H5/HDF5 files
- Any model/joblib/pkl/npy/npz artifacts
- Terraform/CDK/CloudFormation/IaC files

## Required reads (completed for this PLAN.md)

- `ROADMAP.md` — current state with Platform Readiness Track and Decision Gate Register
- `docs/architecture.md` — current state with all extensions from PR 0011C
- `docs/adr/0003-bremen-microservice-api-architecture.md` — G-API-1/G-API-2 definitions
- `docs/adr/0004-bremen-configuration-management-strategy.md` — G-CFG-1 definition
- `docs/adr/0005-container-dependency-stabilization.md` — G-DEP-1 definition
- `docs/adr/0006-multi-target-deployment-and-iac.md` — G-INFRA-1 definition
- `.project-memory/project_contract.yml` — safety invariants, mandatory response fields
- `.project-memory/memory_index.yml` — PR/artifact index
- `AGENTS.md` — agent role definition

## Implementation phase assignment

- **Agent**: architect
- **Mode**: WRITE

**Reason**: All three implementation files are architect-reserved paths per `agents/architect.yml`: `docs/adr/**` (ADR-0007), `ROADMAP.md` (edit), and `docs/architecture.md` (edit).

## ADR-0007 planned content: docs/adr/0007-model-artifact-lifecycle.md

**Status**: Accepted

### 1. Offline model training pipeline

- `train_classifier.py` or future training pipeline creates the model package.
- This pipeline runs rarely, only when releasing a new model version.
- It is not part of the runtime prediction API.
- It is not part of the normal application Docker image CI/CD pipeline.
- Runtime Bremen service must not train models.

### 2. Model package contents

A controlled model package must include at minimum:

- joblib model artifact
- `model_version`
- `model_checksum`
- `feature_schema_version`
- threshold version/value
- QC criteria metadata
- training/config provenance reference
- creation timestamp
- checksum manifest
- Enough metadata for every prediction response to include the required `project_contract.yml` fields

### 3. Runtime loading

- Runtime service receives or resolves a configured `model_version` / model package reference.
- Runtime service loads only checksum-verified model packages.
- Runtime service verifies feature schema compatibility before inference.
- Runtime service does not build, retrain, mutate, or overwrite model artifacts.
- Runtime service fails closed if checksum, schema, metadata, or package validation fails.

### 4. Artifact storage

- Initial implementation target: S3 versioned bucket.
- Model package storage is separate from Docker image registry.
- Docker image contains application code and inference wrapper logic, not a freshly-built model artifact.
- GHCR/ECR image pipeline and model package release pipeline are independent release cycles.

### 5. Security note for `joblib.load()`

`joblib.load()` uses pickle deserialization and can execute arbitrary code. The following rules apply:

- Checksum verification is a security boundary **only if** the checksum is computed at the training-pipeline trust boundary.
- Checksum must not be derived post-hoc from the stored artifact by the runtime.
- Checksum manifest write access must be restricted separately from model artifact read access.
- Model artifact read access alone must not allow checksum manifest modification.
- Runtime must load only from trusted, checksum-verified, approved model packages.

### 6. Publication flow

- A future implementation PR must define the exact publication flow.
- Publishing a new model package must be explicit and auditable.
- A model package should be promoted only after validation/QC evidence exists.
- This PR does not implement the publication pipeline.

### 7. Relationship to CI/CD

- Application CI/CD builds/tests/publishes service image.
- Model package release pipeline builds/tests/publishes model artifact.
- Updating a model must not require rebuilding application image unless application code changes are also required.
- Updating application image must not silently change `model_version`.

### 8. Relationship to prediction API

Every prediction response must include the `project_contract.yml`-required fields:

- `prediction_id`
- `model_version`
- `model_checksum`
- `feature_schema_version`
- threshold version/value
- `qc_status`
- `qc_flags`

## ROADMAP.md planned changes

Edit ROADMAP.md to make the following changes. Prefer append-only or minimal targeted edit.

### 1. Add ADR-0007 / PR 0012 to Completed foundation PRs

Add a new entry to the `## Completed foundation PRs` list:

```
- PR-0012 — Model artifact lifecycle ADR + runtime deployment gate closure. ADR-0007 formalizes offline training, controlled package, runtime loading, S3 storage, and security boundaries. G-API-1, G-API-2, G-INFRA-1 closed as DECIDED.
```

### 2. Close Decision Gates

In the `## Decision Gate Register` table, update three gates:

| Gate | Before | After |
|------|--------|-------|
| G-API-1 | Status: OPEN, Decided value: — | Status: DECIDED, Decided value: async submit → `job_id` → poll |
| G-API-2 | Status: OPEN, Decided value: — | Status: DECIDED, Decided value: ECS Fargate |
| G-INFRA-1 | Status: OPEN, Decided value: — | Status: DECIDED, Decided value: Terraform |

For each closed gate, add a `Decided by` row or column entry:

```
Decided by: human product/engineering decision in PR 0012 planning
Decision date: 2026-07-03 (UTC)
```

The exact representation may be an additional column or a footnote, as long as the decision authority and date are traceable.

### 3. Do NOT close

- G-CFG-1 — remains OPEN
- G-DEP-1 — remains OPEN

### 4. Add execution-order guidance

Add a new paragraph after the Decision Gate Register:

> **Execution order note**: Runtime/API/IaC/model-artifact foundation is now priority before the patient-facing report template (Product Track item 2). This is execution-order guidance, not a renumbering of existing roadmap items. PRs from the Platform Readiness Track (PR 0019–0024) and the Product Track (items 2–12) may be interleaved based on readiness, with the understanding that the API/microservice/IaC/model-artifact foundation precedes downstream work that depends on it.

### 5. Add numbering clarification

Add a new paragraph:

> **Numbering clarification**: Product Track sequence positions (items 1–12) are ordering, not PR-00XX identifiers. The next literal PR number after 0012 will be assigned when the next scheduled sequence item is actually planned. PR 0019–0024 Platform Readiness Track numbers remain unchanged and are not renumbered by this or any subsequent PR. Reprioritization changes execution order only, not existing PR labels.

## docs/architecture.md planned changes

Extend docs/architecture.md with clearly delimited new subsections after the existing `## External Dependency Risk` section (or as a new top-level section). Do not remove or rewrite existing PR 0011A or PR 0011C content.

### `## Offline Model Artifact Lifecycle`

- Training pipeline creates controlled model package.
- Model package stored separately from app image.
- S3 versioned bucket as first implementation target.
- Checksum/security trust boundary (restated from ADR-0007 security note).

### `## Online Prediction Runtime Workflow`

Describe the workflow:

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

Label the async job creation as a consequence of the closed G-API-1 decision.

### `## AWS Runtime/Deployment Default Decisions`

Record the now-closed gate decisions:

- **Async API**: submit → `job_id` → poll (G-API-1, DECIDED)
- **Compute**: ECS Fargate (G-API-2, DECIDED)
- **IaC tool**: Terraform (G-INFRA-1, DECIDED)
- **Service image path**: ECR (planned, PR 0022)
- **Model package path**: S3 versioned bucket (planned, PR 0013+)
- No automatic deploy or destructive infra mutation in this PR.

### `## Safety`

Restate key safety invariants relevant to the runtime deployment:

- Runtime service does not train models.
- Model package load must be checksum-verified.
- Feature schema must match model expectations.
- Prediction result must include required model/version/checksum/QC fields.
- Platform API must not depend on local machine paths.

## Non-goals

- No source code, no tests, no CI YAML, no Dockerfile change.
- No ECR publish implementation, no Terraform or IaC file.
- No API contract file, no service skeleton.
- No model/joblib artifact, no training pipeline implementation.
- No H5 reading/mutation, no config/preprocessing changes.
- No APRANA implementation (remains unverified).
- No closing G-CFG-1 or G-DEP-1 (both remain OPEN).
- No product identity relitigation, no Aramis active architecture.
- No renumbering of PR 0019–0024.

## Validation checklist

The implementation phase (architect) must execute these commands and report results:

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4-5) Changed files
git diff --name-only
git diff --stat

# 6-8) Allowed files exist
test -f docs/adr/0007-model-artifact-lifecycle.md || exit 1
test -f ROADMAP.md || exit 1
test -f docs/architecture.md || exit 1
```

### ADR-0007 content checks

```bash
# 9) joblib.load() security note present
grep -n "joblib.load()" docs/adr/0007-model-artifact-lifecycle.md || exit 1

# 10) Checksum manifest write access
grep -n "checksum manifest write access" docs/adr/0007-model-artifact-lifecycle.md || exit 1

# 11) Training-pipeline trust boundary security note
grep -n "training-pipeline trust boundary" docs/adr/0007-model-artifact-lifecycle.md || exit 1

# 12) S3 versioned bucket as first artifact store
grep -n "S3 versioned bucket" docs/adr/0007-model-artifact-lifecycle.md || exit 1

# 13) Not part of normal Docker image CI/CD
grep -n "not part of the normal application Docker image CI/CD pipeline" docs/adr/0007-model-artifact-lifecycle.md || exit 1
```

### ROADMAP.md gate closure checks

```bash
# 14-16) G-API-1 present and marked DECIDED
grep -n "G-API-1" ROADMAP.md || exit 1
grep -n "DECIDED" ROADMAP.md || exit 1
grep -n "async submit" ROADMAP.md || exit 1

# 17-18) G-API-2 present and reference to ECS Fargate
grep -n "G-API-2" ROADMAP.md || exit 1
grep -n "ECS Fargate" ROADMAP.md || exit 1

# 19-20) G-INFRA-1 present and reference to Terraform
grep -n "G-INFRA-1" ROADMAP.md || exit 1
grep -n "Terraform" ROADMAP.md || exit 1

# 21-22) Decided by / Decision date pattern
grep -n "Decided by" ROADMAP.md || exit 1
grep -n "Decision date" ROADMAP.md || exit 1
```

### ROADMAP.md numbering/execution checks

```bash
# 23) Product Track sequence positions are ordering, not PR numbers
grep -n "Product Track sequence positions are ordering" ROADMAP.md || exit 1

# 24) PR 0019-0024 not renumbered
grep -n "does not renumber PR 0019" ROADMAP.md || exit 1
```

### docs/architecture.md content checks

```bash
# 25-27) Three new sections
grep -n "Offline model artifact lifecycle" docs/architecture.md || exit 1
grep -n "Online prediction runtime workflow" docs/architecture.md || exit 1
grep -n "AWS Runtime/Deployment Default Decisions" docs/architecture.md || exit 1

# 28) Checksum-verified model package
grep -n "checksum-verified model package" docs/architecture.md || exit 1

# 29) ECS Fargate
grep -n "ECS Fargate" docs/architecture.md || exit 1

# 30) S3 versioned bucket
grep -n "S3 versioned bucket" docs/architecture.md || exit 1

# 31) Terraform
grep -n "Terraform" docs/architecture.md || exit 1
```

### Forbidden path checks

```bash
# 32) No forbidden files changed
git diff --name-only -- src tests config examples .github Dockerfile .dockerignore requirements.txt pyproject.toml sonar-project.properties environment.yml Makefile docs/api_contract.md
# Must return nothing
```

### Safety checks

```bash
# 33) No H5/HDF5 files
find . -path "./.git" -prune -o -path "./venv" -prune -o -path "./.venv" -type f \( -name "*.h5" -o -name "*.hdf5" \) -print

# 34) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

If the ADR or roadmap/architecture extensions contain errors:

1. **ADR-0007** — Delete `docs/adr/0007-model-artifact-lifecycle.md`. No other files affected.
2. **ROADMAP.md** — Revert the gate closures (change DECIDED back to OPEN, remove Decided by/date). Revert the added paragraphs. Remove the PR 0012 completed entry. The existing Platform Readiness Track and Decision Gate Register structure is preserved.
3. **docs/architecture.md** — Revert the four new subsections. The existing PR 0011A and PR 0011C content is preserved.

Each file is independent and revertible individually.

## Follow-up PRs

After PR 0012 merges:

- **PR 0013** — Model package contract and local validation helpers (delegated from ADR-0007)
- **PR 0014** — API contract + async microservice skeleton (uses G-API-1/G-API-2 decisions)
- **PR 0015** — Terraform/ECR/ECS/S3 IaC skeleton (uses G-INFRA-1/G-API-2 decisions)
- **Later** — Cloud-aware config sourcing, container dependency hygiene, product-core model training

The literal PR number after 0012 will be assigned when the next scheduled sequence item is actually planned.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 3 allowed files changed: ADR-0007, ROADMAP.md, docs/architecture.md. |
| **Gate closure drift** | G-API-1, G-API-2, G-INFRA-1 marked DECIDED with Decided by/date. G-CFG-1, G-DEP-1 remain OPEN. |
| **ADR-0007 drift** | Contains all 8 required sections: offline training, package contents, runtime loading, artifact storage, joblib.load security note, publication flow deferral, CI/CD relationship, prediction API relationship. |
| **Security note drift** | joblib.load() pickle risk stated. Checksum trust boundary defined. Checksum manifest write access restricted. |
| **ROADMAP.md drift** | PR 0012 added to completed. 3 gates closed. Execution order note added. Numbering clarification added. PR 0019-0024 not renumbered. |
| **Architecture drift** | 4 new subsections. Existing content not removed or rewritten. |
| **No-implementation drift** | No source/CI/Docker/Terraform/API/model artifact changes. |
| **Validation drift** | All 34 validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan writes source code, CI YAML, Dockerfile, Terraform, API contract, or model artifacts.
- Plan closes G-CFG-1 or G-DEP-1.
- Plan omits the `joblib.load()` security note from ADR-0007.
- Plan omits the Decided by/date pattern for gate closures.
- Plan renumbers PR 0019–0024.
- Plan treats Product Track sequence positions as literal PR identifiers.
- Plan invents APRANA technical details (must remain unverified).
- Plan makes Aramis active architecture.
- Any implementation file outside the three allowed files is planned.

## Decisions summary

### Allowed files
1. `docs/adr/0007-model-artifact-lifecycle.md` — NEW
2. `ROADMAP.md` — EDIT (add ADR-0007 entry, close 3 gates, add execution/numbering notes)
3. `docs/architecture.md` — EDIT (add 4 new subsections)

### Human decisions recorded
| Decision | Value |
|----------|-------|
| G-API-1 | DECIDED: async submit → job_id → poll |
| G-API-2 | DECIDED: ECS Fargate |
| G-INFRA-1 | DECIDED: Terraform |
| Model artifact | Separate controlled checksum-verified package |
| joblib build | Offline only, not in runtime or Docker CI/CD |
| Runtime loading | Loads already-trained model from artifact storage |
| Initial artifact store | S3 versioned bucket |
| Publication flow | Delegated to future PR |

### ADR-0007 summary
8 sections covering: offline training, package contents (10 minimum fields), runtime loading (fail closed), S3 artifact storage, joblib.load() security (checksum trust boundary, manifest access separation), publication flow deferral, CI/CD independence, prediction API mandatory response fields.

### ROADMAP change summary
- PR 0012 added to Completed foundation PRs.
- G-API-1/G-API-2/G-INFRA-1 closed as DECIDED with Decided by/date.
- Execution order note added (API/IaC/model-artifact foundation before report template).
- Numbering clarification added (Product Track items are ordering, not PR numbers; PR 0019–0024 not renumbered).
- G-CFG-1/G-DEP-1 remain OPEN.

### Architecture change summary
4 new subsections: ## Offline Model Artifact Lifecycle, ## Online Prediction Runtime Workflow, ## AWS Runtime/Deployment Default Decisions, ## Safety. Existing content from PR 0011A and PR 0011C untouched.

### Security note summary
- joblib.load() uses pickle deserialization → arbitrary code execution risk.
- Checksum verified at training-pipeline trust boundary, not post-hoc by runtime.
- Checksum manifest write access separate from artifact read access.
- Runtime loads only from trusted, checksum-verified, approved packages.

### Gate closure pattern
Each closed gate updated with: Status = DECIDED, Decided value = [specific value], Decided by = human product/engineering decision in PR 0012 planning, Decision date = 2026-07-03 (UTC).

### Numbering / execution order clarification
- Product Track items 1–12 are order positions, not PR identifiers.
- Next literal PR number after 0012 assigned when the next item is actually planned.
- PR 0019–0024 remain unchanged and are not renumbered.
- Reprioritization changes execution order only, not PR labels.

### Validation checklist
34 checks: git state, file existence, ADR-0007 content (5 checks), ROADMAP.md gate closure (11 checks), ROADMAP.md numbering (2 checks), architecture.md content (7 checks), forbidden paths (1 check), safety checks (2 checks).

### Stop conditions
8 block conditions.

### Rollback plan
Each of the 3 files independently revertible.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0012-model-artifact-lifecycle-gates/PLAN.md`
2. Human runs: `git add .project-memory/pr/0012-model-artifact-lifecycle-gates/PLAN.md`
3. Human runs: `git commit -m "PR 0012 — Plan model artifact lifecycle and runtime deployment gate closure"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the architect implements the three allowed files.

## Files read

- `ROADMAP.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0004-bremen-configuration-management-strategy.md`
- `docs/adr/0005-container-dependency-stabilization.md`
- `docs/adr/0006-multi-target-deployment-and-iac.md`
- `.project-memory/project_contract.yml`
- `.project-memory/memory_index.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0012-model-artifact-lifecycle-gates/PLAN.md` (this file)

## Files intentionally ignored

- All source, test, config, example files
- All infrastructure files (Docker, CI, SonarCloud, pyproject, env)
- All ADRs 0001–0006 (read-only references)
- README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md
- AGENTS.md, agents/**
- Any H5/HDF5 or model artifacts
- Terraform/CDK/CloudFormation/IaC files

## Boundary confirmations

- confirm: PR 0012 is docs-only architect planning: yes
- confirm: ADR-0007 planned: yes
- confirm: G-API-1/G-API-2/G-INFRA-1 planned as DECIDED: yes
- confirm: G-CFG-1/G-DEP-1 remain OPEN: yes
- confirm: joblib is offline-only model package artifact, not Docker image CI/CD build output: yes
- confirm: S3 versioned bucket planned as first model artifact store: yes
- confirm: joblib.load security note planned: yes
- confirm: Decided by/date planned for gate closure: yes
- confirm: Product Track sequence positions are not literal PR numbers: yes
- confirm: PR 0019–0024 are not renumbered: yes
- confirm: no source/CI/Docker/Terraform/API/model artifact changes planned: yes
- confirm: no implementation files modified: yes
- confirm: no git mutation commands run: yes
