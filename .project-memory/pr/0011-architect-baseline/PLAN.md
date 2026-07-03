# PR 0011A — Plan Bremen Architect Baseline Documents

Author: plan
Mode: planning only
Branch: 0011-architect-baseline

## Objective

Create exactly four baseline documents that are prerequisites for the later PR 0011C (Platform Readiness ADR Bundle):

- `docs/adr/0001-bremen-product-identity.md`
- `docs/adr/0002-twin-product-document-separation.md`
- `ROADMAP.md`
- `docs/architecture.md`

None of these files exist yet. This PR does not implement PR 0011C. This PR does not create ADR-0003 through ADR-0006. This PR does not add a Platform Readiness Track or a Decision Gate Register.

## Why this PR is required before PR 0011C

PR 0011C — Platform Readiness ADR Bundle has a strict precondition that these four baseline documents already exist. The ADRs and architecture in 0011C reference ADR-0001 and ADR-0002 for product identity and document separation policy. The roadmap must be current to schedule the Platform Readiness work. The architecture document must exist to be extended. This PR satisfies that precondition.

## 0011A/B/C naming convention

This architecture-correction cascade uses a lettered sub-PR convention, used only for this cascade:

- **PR 0011A** — architect baseline documents (this PR): `docs/adr/0001-bremen-product-identity.md`, `docs/adr/0002-twin-product-document-separation.md`, `ROADMAP.md`, `docs/architecture.md`
- **PR 0011B** — Bremen identity documentation cascade (README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md), if still required after ADR-0001/0002 are merged
- **PR 0011C** — Platform Readiness ADR Bundle

After this cascade completes, sequencing returns to normal one-number-one-PR numbering (PR 0012 onward).

## Exact allowed files

The implementation phase (Agent: architect, Mode: WRITE) may create exactly these files:

1. `docs/adr/0001-bremen-product-identity.md` — NEW. ADR documenting Bremen product identity.
2. `docs/adr/0002-twin-product-document-separation.md` — NEW. ADR documenting permanent separation from Aramis.
3. `ROADMAP.md` — NEW. Root-level roadmap with Product Track only.
4. `docs/architecture.md` — NEW. Architecture baseline document.

These are the ONLY files that may be created or modified. The `docs/adr/` directory will be created if it does not exist.

## Exact forbidden files

- `docs/adr/0003-*.md` through `docs/adr/0006-*.md` — not created here; belong to PR 0011C
- `docs/api_contract.md` — not created here; belongs to a later PR
- `src/**` — no source code changes
- `tests/**` — no test changes
- `config/**` — no config changes
- `examples/**` — no example changes
- `.github/**` — no CI changes
- `Dockerfile` — no Docker changes
- `.dockerignore` — no Docker changes
- `requirements.txt` — no dependency changes
- `pyproject.toml` — no project metadata changes
- `sonar-project.properties` — no SonarCloud changes
- `environment.yml` — no environment changes
- `Makefile` — no build changes
- `docs/roadmap.md` — not modified (existing `docs/roadmap.md` remains as-is for reference; a new root-level `ROADMAP.md` is the authoritative version going forward)
- Any H5/HDF5 files
- Any model/joblib/pkl/npy/npz artifacts
- Terraform/CDK/CloudFormation/IaC files

## Required reads

These documents have been read to establish the evidence base for this PLAN.md:

- `docs/product_development_rules.md` — contains the exact clinical question, label definitions, and product separation rules
- `.project-memory/project_contract.yml` — contains safety invariants and source-of-truth order
- `.project-memory/memory_index.yml` — confirms no existing ADR/architecture documents
- `AGENTS.md` — contains product intent for Bremen and Aramis
- `.project-memory/pr/0001-*/` through `pr/0009-*/` — confirm completed PR scope

## Implementation phase assignment

- **Agent**: architect
- **Mode**: WRITE

**Reason**: The four implementation files are architecture docs and ADRs (`docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`), which only `agents/architect.yml` has write permission for. The coder role must not be assigned this implementation phase.

## ADR-0001 planned content

**File**: `docs/adr/0001-bremen-product-identity.md`
**Status**: Accepted

ADR-0001 must contain:

### Identity statement
- Bremen is the active product identity for this repository.
- "Bremen Assembly plan v1" is the authoritative product identity reference (not the Aramis-inherited text currently in `README.md`, `docs/roadmap.md`, or `docs/machine_learning_concept.md`).

### Clinical question
The exact clinical question, quoted verbatim from `docs/product_development_rules.md`:
> "Should patient continue to MRI?"

### Classification task
- Task: healthy vs. disease (NORMAL vs. BENIGN+CANCER).
- Explicitly stated as distinct from a malignant-vs-benign task.

### Contrast with Aramis
- Explicit statement: This is NOT Aramis's malignant-vs-benign classification (BI-RADS 3/4 → biopsy decision).

### Bremen feature-family anchors
The seven Bremen feature-family anchors, named exactly:
1. `sigma_l1`
2. `sigma_l2`
3. `Mahalanobis1`
4. `Mahalanobis2`
5. `wasserstein_distance_full_q2`
6. `meanrms2`
7. `weightedrms1`

### Contrast with Aramis feature families
Explicit contrast with Aramis's feature families, presented as a paired table tied to the product identity statement:

| Bremen family | Aramis family |
|---|---|
| `sigma_l1`, `sigma_l2` | complete azimuthal integration (components approach) |
| `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1` | cosine asymmetry distance (symmetry approach) |

These families implement Bremen's own healthy-vs-disease symmetry/distance approach and are not interchangeable with Aramis's azimuthal-integration/cosine-asymmetry approach.

### Product description
- Bremen is an XRD-based ML decision-support workflow for patients referred to MRI after suspicious mammography findings (dense breast / low-efficacy mammography).
- Bremen is not a diagnostic replacement.
- Bremen must not claim clinical validation.
- Bremen must not replace MRI, biopsy, radiologists, clinicians, or clinical judgment.

### Architecture constraints
- Runtime Bremen service must not train models.
- Matador is the system of record for measurements and prediction results.
- Platform APIs must not depend on local machine paths.

## ADR-0002 planned content

**File**: `docs/adr/0002-twin-product-document-separation.md`
**Status**: Accepted

ADR-0002 must contain:

### Separation policy
- Bremen and Aramis are permanently separate forks/products/final deliverables.

### Aramis in Bremen
- Aramis may appear in Bremen only as historical/provenance context (fork origin).
- Aramis is not an active dependency, runtime, shared feature set, API, or configuration target for Bremen.

### Shared technical surface
- The only shared technical surface between the two products is the upstream XRD-preprocessing repository.

### Prohibition
- No Aramis-specific architecture, endpoints, or configuration should be added to Bremen as a result of this or any future PR.

## ROADMAP.md planned baseline content

**File**: `ROADMAP.md` (root level)
**Track**: Product Track only

No Platform Readiness Track. No Decision Gate Register. No hard calendar dates — use sequence and dependencies.

### Completed foundation PRs (must record)

- PR-0001 — Agent workflow foundation
- PR-0002 — Planning/identity cleanup
- PR-0003 — Full Aramis-to-Bremen alignment
- PR-0004 — Roadmap quality/docker/entrypoint planning
- PR-0005 — Docker/CI/Sonar skeleton
- PR-0006 — Coverage/cache
- PR-0007 — GHCR Docker smoke publish
- PR-0008 — Unified Bremen entrypoint
- PR-0009 — Config discovery/loading

### Product Track sequence (exact order, product core before infrastructure wrappers)

1. **Product identity / document separation baseline** — This cascade (0011A/B). ADR-0001 and ADR-0002, architecture baseline, and updated roadmap.
2. **YAML/PDF clinical report template** — Public + internal, per Bremen Assembly plan v1 Phase 1 (currently overdue).
3. **YAML training config template** — Per Bremen Assembly plan v1 Phase 1 (currently overdue).
4. **Bremen feature-family implementation/verification** — For all seven families: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
5. **`train_classifier.py` pipeline + QC criteria document + `bremen_v1.joblib` reproducible model package** — The first controlled model release.
6. **GitHub demo** — Real H5 patients, end-to-end prediction shown.
7. **Platform deployment plan document** — Documented deployment architecture.
8. **Safety preflight gates** — H5 metadata validation, target/control consistency, config integrity.
9. **Matador boundary / system-of-record adapter skeleton** — Platform integration contract.
10. **Workflow wrapper / decision-support output** — First end-to-end workflow (preprocess → QC → inference → report).
11. **Model artifact/version reporting** — Artifact management.
12. **Release readiness / operator notes** — Final preparation.

Items 8–12 must not be silently dropped, but must appear after items 1–7 because there is no model, API surface, or workflow yet for them to gate.

## docs/architecture.md planned baseline content

**File**: `docs/architecture.md`

Must contain:

### Product scope
- One paragraph describing Bremen product scope, sourced from ADR-0001 (not restated independently).

### Current CLI/config foundation
- What PR 0008 and PR 0009 actually delivered:
  - CLI entrypoint with `preprocess` command (lazy import), stub commands (`preflight`, `run`, `report`)
  - Config discovery/loading module (`config.py`) with deterministic file lookup

### Intended core chain
Stated exactly:
> Matador → Bremen API → H5 inspect gate → preprocessing/feature extraction → joblib inference → QC → prediction JSON → Matador storage/report layer

### Safety boundaries
Must restate ALL 11 safety invariants from `.project-memory/project_contract.yml` verbatim, 1:1, no paraphrase, no subset:

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

### Current implementation state (honest assessment)
- CLI foundation exists
- Config discovery/loading exists
- Docker/CI/GHCR skeleton exists (image built and published, but not used by runtime)
- Real API, H5 gates, inference workflow, Matador integration, cloud deployment, and product-core classifier artifacts remain future work

### Closing note
- PR 0011C / ADR-C is the next architecture bundle, to be planned only after this baseline is merged.

## Safety boundaries

The four documents created by this PR must:
- Use Bremen-specific product identity content, not generic safety boilerplate.
- Not contain clinical validation claims.
- Not claim FDA clearance, autonomous diagnosis capability, or clinical release.
- Not present Bremen as a replacement for MRI, biopsy, radiologists, or clinicians.
- Not use Aramis as active architecture (only as historical/provenance context in ADR-0002).
- Not introduce runtime training endpoints or claims.
- Not introduce Platform Readiness Track content (belongs to PR 0011C).
- Not introduce Decision Gate Register (belongs to PR 0011C).

## Non-goals

This PR does not:
- Change any source code (`src/**`)
- Change any tests (`tests/**`)
- Change any config files (`config/**`)
- Change any examples (`examples/**`)
- Change any CI/Docker files (`.github/**`, `Dockerfile`, `.dockerignore`)
- Change any project metadata (`pyproject.toml`, `requirements.txt`, `environment.yml`, `Makefile`)
- Change any existing documentation (`README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md` — these may be updated in PR 0011B if needed)
- Create ADR-0003 through ADR-0006 (belong to PR 0011C)
- Create `docs/api_contract.md` (belongs to a later PR)
- Create any H5/HDF5 files or model artifacts
- Add Platform Readiness Track or Decision Gate Register
- Implement PR 0011C

## Validation checklist

The implementation phase (architect) must execute these checks:

### File existence checks
```bash
# 1) Working tree state
git status --short

# 2) Changed files — only allowed files
git diff --name-only

# 3) product_development_rules.md is still readable
test -f docs/product_development_rules.md || exit 1

# 4-7) All four target files exist
test -f docs/adr/0001-bremen-product-identity.md || exit 1
test -f docs/adr/0002-twin-product-document-separation.md || exit 1
test -f ROADMAP.md || exit 1
test -f docs/architecture.md || exit 1
```

### Scope boundary checks
```bash
# 8) ADR-0003..0006 do not exist
test ! -f docs/adr/0003-bremen-microservice-api-architecture.md || exit 1
test ! -f docs/adr/0004-bremen-configuration-management-strategy.md || exit 1
test ! -f docs/adr/0005-container-dependency-stabilization.md || exit 1
test ! -f docs/adr/0006-multi-target-deployment-and-iac.md || exit 1

# 9) docs/api_contract.md does not exist
test ! -f docs/api_contract.md || exit 1

# 10) No source/test/CI/Docker/requirements/config/examples/H5/model/IaC files changed
git diff --name-only | grep -E "^(src/|tests/|config/|examples/|\.github/|Dockerfile|\.dockerignore|requirements\.txt|pyproject\.toml|sonar-project\.properties|environment\.yml|Makefile|\.gitignore)" && exit 1 || echo "OK"
```

### ADR-0001 content checks
```bash
# 11) Contains exact clinical question
grep -q "Should patient continue to MRI?" docs/adr/0001-bremen-product-identity.md || exit 1

# 12) Contains NORMAL
grep -q "NORMAL" docs/adr/0001-bremen-product-identity.md || exit 1

# 13) Contains BENIGN+CANCER
grep -q "BENIGN+CANCER" docs/adr/0001-bremen-product-identity.md || exit 1

# 14-20) Contains all seven Bremen feature-family names
for f in sigma_l1 sigma_l2 Mahalanobis1 Mahalanobis2 wasserstein_distance_full_q2 meanrms2 weightedrms1; do
  grep -q "$f" docs/adr/0001-bremen-product-identity.md || exit 1
done

# 21) Aramis contrast language present and does not make Aramis active architecture
grep -q "NOT Aramis" docs/adr/0001-bremen-product-identity.md || echo "WARNING: contrast language might not be explicit"
```

### ADR-0002 content checks
```bash
# 22) Separation policy stated
grep -q "permanently separate" docs/adr/0002-twin-product-document-separation.md || exit 1
```

### ROADMAP.md content checks
```bash
# 23-28) Product Track items present
grep -q "clinical report template" ROADMAP.md || exit 1
grep -q "training config template" ROADMAP.md || exit 1
grep -q "train_classifier.py" ROADMAP.md || exit 1
grep -q "bremen_v1.joblib" ROADMAP.md || exit 1
grep -q "GitHub demo" ROADMAP.md || exit 1
grep -q "platform deployment plan" ROADMAP.md || exit 1

# 29) Infrastructure items (8-12) are NOT before product-core items (1-7)
# Check that item numbers are in order
FIRST_INFRA=$(grep -n "safety preflight gates\|Matador boundary\|workflow wrapper\|artifact.*version.*reporting\|release readiness" ROADMAP.md | head -1 | cut -d: -f1)
LAST_CORE=$(grep -n "platform deployment plan\|GitHub demo\|bremen_v1.joblib.*reproducible" ROADMAP.md | tail -1 | cut -d: -f1)
test "$FIRST_INFRA" -gt "$LAST_CORE" || exit 1
```

### docs/architecture.md content checks
```bash
# 30-36) Mandatory safety invariants present
grep -q "prediction_id" docs/architecture.md || exit 1
grep -q "model_version" docs/architecture.md || exit 1
grep -q "model_checksum" docs/architecture.md || exit 1
grep -q "feature_schema_version" docs/architecture.md || exit 1
grep -q "qc_status" docs/architecture.md || exit 1
grep -q "qc_flags" docs/architecture.md || exit 1

# 37-38) Target/control requirements present
grep -q "same.patient\|same patient\|same_patient\|samePatient" docs/architecture.md || exit 1
grep -q "opposite.side\|opposite side\|opposite_side\|oppositeSide" docs/architecture.md || exit 1

# 39-40) Joblib checksum and feature schema match requirements present
grep -q "joblib.*checksum\|checksum.*joblib" docs/architecture.md || exit 1
grep -q "feature.schema.*match\|schema.*match" docs/architecture.md || exit 1

# 41) Controlled-ML-product framing (invariant 1)
grep -q "controlled ML decision-support" docs/architecture.md || exit 1

# 42) H5-metadata-validation-required framing (invariant 3)
grep -q "required H5 metadata is present and validated" docs/architecture.md || exit 1

# 43) Supplementary-decision-support-language framing (invariant 11)
grep -q "supplementary decision-support language" docs/architecture.md || exit 1

# 44) Runtime training prohibition
grep -q "must not train\|no runtime training\|not train" docs/architecture.md || exit 1

# 45) Diagnostic replacement prohibition
grep -q "not.*diagnostic.*replace\|not a diagnostic\|no diagnostic claim" docs/architecture.md || exit 1

# 46) No local machine path dependency
grep -q "local machine path\|local path\|machine path\|platform.*path" docs/architecture.md || exit 1
```

### Prohibited content checks
```bash
# 47) No prohibited clinical/diagnostic claims in any new file
for f in docs/adr/0001-bremen-product-identity.md docs/adr/0002-twin-product-document-separation.md ROADMAP.md docs/architecture.md; do
  grep -i -n -E "FDA.?cleared|FDA.?approved|clinically.?validated|replacement.?for.?MRI|autonomous.?diagnos|replace.?radiologist|replace.?clinician|replace.?biopsy" "$f" && exit 1 || true
done

# 48) No runtime training endpoint language
for f in docs/adr/0001-bremen-product-identity.md docs/adr/0002-twin-product-document-separation.md ROADMAP.md docs/architecture.md; do
  grep -i -n -E "train.?endpoint|train.?model.*runtime|runtime.*train|online.?learning" "$f" && exit 1 || true
done
```

### Additional safety checks
```bash
# 49) No H5/model artifacts staged
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) | grep -v "\.git/\|venv/\|\.venv/" && exit 1 || echo "OK"

# 50) .DS_Store not present
find . -name ".DS_Store" -print
```

## Rollback plan

If any of the four baseline documents contains errors:

1. **Revert the specific file(s)** — Each file is independent. A single file can be reverted and corrected.
2. **If all four files are wrong**: `git revert <merge-commit>` or delete the four files:
   - `rm docs/adr/0001-bremen-product-identity.md docs/adr/0002-twin-product-document-separation.md ROADMAP.md docs/architecture.md`
   - `rmdir docs/adr/` if now empty.
3. **No other files are affected** — No source, tests, config, CI, or infrastructure files were changed.

## Follow-up PRs

After PR 0011A merges:

- **PR 0011B** — If still required after ADR-0001/0002 are merged: Update README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md to align with the ADR-0001 product identity. This PR may be skipped if the existing docs are already consistent with ADR-0001.
- **PR 0011C** — Platform Readiness ADR Bundle (ADR-0003 through ADR-0006, Platform Readiness Track, Decision Gate Register). Only planned after PR 0011A (and optionally 0011B) merge.
- **PR 0012 onward** — Normal sequencing resumes: clinical report template, training config template, feature-family implementation, etc.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only the four allowed files created. No other files created or modified. |
| **ADR scope drift** | Only ADR-0001 and ADR-0002 created. No ADR-0003..0006. |
| **ADR-0001 identity drift** | Contains exact clinical question, NORMAL vs BENIGN+CANCER, all 7 feature-family names, Aramis contrast, architecture constraints. |
| **ADR-0002 separation drift** | Declares permanent separation. Only shared surface is XRD-preprocessing. |
| **ROADMAP.md drift** | Product Track only. Product-core items (1-7) before infrastructure/wrappers (8-12). No hard dates. Completed PRs recorded. |
| **Architecture drift** | Core chain stated exactly. ALL applicable project_contract.yml invariants included. Honest implementation state. |
| **Implementation agent drift** | Assigned to Agent: architect, Mode: WRITE. Not assigned to coder. |
| **PR 0011C drift** | 0011C is not implemented. ADR-C work not started. Platform Readiness Track not introduced. |
| **Safety drift** | No clinical claims, no FDA language, no autonomous diagnosis claims, no runtime training claims. |
| **Infrastructure drift** | No CI/Docker/GHCR/SonarCloud changes. No pyproject.toml/environment/Makefile changes. |
| **Validation drift** | All 50 validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Any file outside the four allowed files (`docs/adr/0001-*.md`, `docs/adr/0002-*.md`, `ROADMAP.md`, `docs/architecture.md`) is created or modified.
- ADR-0001 lacks the exact clinical question "Should patient continue to MRI?"
- ADR-0001 lacks NORMAL vs BENIGN+CANCER classification task definition.
- ADR-0001 lacks any of the seven Bremen feature-family names.
- ROADMAP.md puts infrastructure/wrappers (items 8-12) before product-core items (1-7).
- ROADMAP.md introduces Platform Readiness Track or Decision Gate Register.
- ROADMAP.md uses hard calendar dates.
- Implementation phase is assigned to coder instead of architect.
- docs/architecture.md uses only a shortened subset of safety invariants from project_contract.yml.
- ADR-C work (0011C) is started or planned within this PR.
- Any source code, CI, Docker, requirements, config, H5, model, API contract, or IaC file is changed.
- ADR-0003 through ADR-0006 are created.
- `docs/api_contract.md` is created.
- Prohibited clinical/diagnostic claims appear in any new file.

## Decisions summary

### Allowed files
1. `docs/adr/0001-bremen-product-identity.md` — NEW
2. `docs/adr/0002-twin-product-document-separation.md` — NEW
3. `ROADMAP.md` — NEW (root level)
4. `docs/architecture.md` — NEW

### Forbidden files
- ADR-0003 through ADR-0006, docs/api_contract.md
- src/**, tests/**, config/**, examples/**
- .github/**, Dockerfile, .dockerignore, requirements.txt, pyproject.toml, sonar-project.properties, environment.yml, Makefile
- docs/roadmap.md, README.md, AGENTS.md (not modified in this PR)
- H5/HDF5 files, model artifacts, IaC files

### ADR-0001 identity summary
- Bremen is active product identity. Clinical question: "Should patient continue to MRI?"
- Task: NORMAL vs BENIGN+CANCER (healthy vs disease). NOT Aramis malignant-vs-benign.
- Seven feature families mapped to Bremen-specific task: sigma_l1/sigma_l2 (vs Aramis complete azimuthal integration), Mahalanobis1/Mahalanobis2/wasserstein_distance_full_q2/meanrms2/weightedrms1 (vs Aramis cosine asymmetry distance).
- Architecture constraints: no runtime training, Matador is system of record, no local path dependency.

### ADR-0002 separation summary
- Bremen and Aramis are permanently separate. Aramis = historical source material only.
- Shared surface: XRD-preprocessing repository only.
- No Aramis-specific architecture/endpoints/config in Bremen.

### ROADMAP Product Track summary
- 9 completed foundation PRs recorded.
- 12 future items in exact sequence: identity/document baseline → report templates → training config → feature families → train_classifier pipeline → GitHub demo → deployment plan → preflight gates → Matador adapter → workflow wrapper → artifact reporting → release readiness.
- Items 8-12 after items 1-7 (product core before wrappers).

### Architecture invariants summary
All 11 safety invariants from project_contract.yml restated verbatim, 1:1, no subset: controlled ML decision-support product framing; diagnostic system prohibition; H5 metadata validation required before prediction; target/control explicit roles and H5 validation; same-patient opposite-side requirement; feature schema match before inference; joblib checksum verification; mandatory prediction response fields (prediction_id, model_version, model_checksum, feature_schema_version, threshold version/value, qc_status, qc_flags); Matador as system of record; no local machine path dependency; supplementary decision-support language only.

### Implementation agent assignment
- Agent: architect
- Mode: WRITE

### 0011 naming convention
- PR 0011A: architect baseline (this PR)
- PR 0011B: identity documentation cascade (if needed)
- PR 0011C: Platform Readiness ADR Bundle
- After cascade: normal numbering resumes (PR 0012 onward)

### Validation checklist
50 checks: file existence (7), scope boundaries (3), ADR-0001 content (11), ADR-0002 content (1), ROADMAP.md content (7), architecture.md content (17), prohibited content (4), safety checks (2).

### Stop conditions
11 block conditions.

### Rollback plan
- Delete individual files or revert commit. No other files affected.

## Files read

- `docs/product_development_rules.md`
- `.project-memory/project_contract.yml`
- `.project-memory/memory_index.yml`
- `AGENTS.md`
- `docs/roadmap.md` (existing, for reference)
- `.project-memory/pr/0001-bremen-agent-workflow/PLAN.md`
- `.project-memory/pr/0002-aramis-to-bremen-cleanup/PLAN.md`
- `.project-memory/pr/0003-full-aramis-to-bremen-alignment/PLAN.md`
- `.project-memory/pr/0004-roadmap-quality-docker-entrypoint/PLAN.md`
- `.project-memory/pr/0005-docker-ci-sonarcloud-skeleton/PLAN.md`
- `.project-memory/pr/0006-ci-coverage-cache/PLAN.md`
- `.project-memory/pr/0007-ghcr-publish-docker-smoke/PLAN.md`
- `.project-memory/pr/0008-unified-bremen-entrypoint/PLAN.md`
- `.project-memory/pr/0009-config-discovery-loading/PLAN.md`
- `docs/machine_learning_concept.md`

## Files written

- `.project-memory/pr/0011-architect-baseline/PLAN.md` (this file)

## Files intentionally ignored

- All source files (`src/**`)
- All test files (`tests/**`)
- All config files (`config/**`)
- All example files (`examples/**`)
- All infrastructure files (Docker, CI, SonarCloud, etc.)
- `README.md` (may be updated in PR 0011B)
- `docs/roadmap.md` (existing, not replaced by ROADMAP.md)
- `docs/machine_learning_concept.md`, `docs/repository_cleanup.md` (may be updated in PR 0011B)
- Any H5/HDF5 or model artifacts

## Boundary confirmations

- confirm: this PR only plans ADR-0001, ADR-0002, ROADMAP.md, docs/architecture.md: yes
- confirm: ADR-0001 includes exact clinical question, NORMAL vs BENIGN+CANCER, and all 7 Bremen feature families: yes
- confirm: ROADMAP.md Product Track has product-core items before infrastructure wrappers: yes
- confirm: implementation phase assigned to Agent: architect, Mode: WRITE: yes
- confirm: 0011A/B/C naming convention documented: yes
- confirm: docs/architecture.md restates all applicable project_contract.yml invariants, not a shortened subset: yes
- confirm: PR 0011C is not implemented in this PR: yes
- confirm: no ADR-0003..0006 planned: yes
- confirm: no Platform Readiness Track planned: yes
- confirm: no Decision Gate Register planned: yes
- confirm: no source code planned: yes
- confirm: no CI/Docker/requirements/config/H5/model/IaC planned: yes
- confirm: no implementation files modified: yes
- confirm: no git mutation commands run: yes
