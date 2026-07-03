# PR 0011B — Plan Bremen Identity Documentation Cascade

Author: plan
Mode: planning only
Branch: 0011b-bremen-identity-doc-cascade

## Objective

Rewrite the identity-facing sections of four documentation files (README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md) to match ADR-0001 (Bremen product identity) and ADR-0002 (permanent separation from Aramis). These files currently violate Bremen's actual product identity because they were derived by mechanically replacing "Aramis" with "Bremen" in text that still describes Aramis's product (malignant vs. benign, patients referred to biopsy, azimuthal-integration/cosine-asymmetry features).

## Precondition verification

The four PR 0011A baseline files must exist before this PR can proceed:

```bash
test -f docs/adr/0001-bremen-product-identity.md
test -f docs/adr/0002-twin-product-document-separation.md
test -f ROADMAP.md
test -f docs/architecture.md
```

All four are confirmed present. This PLAN.md is written against that base.

## Why this PR is required

ADR-0002 records, as explicit Consequences, that four files in the repository currently violate Bremen's actual product identity:

1. **README.md** — Describes Bremen's product as "for patients referred to biopsy" with a "malignant vs benign" classification task, using Aramis's clinical framing under Bremen's name.
2. **docs/roadmap.md** — Contains stale PR descriptions (PR 0005/0006/0007 described with their original planned content, not what actually shipped) and an outdated test policy table.
3. **docs/machine_learning_concept.md** — Title is "Aramis Machine Learning Concept," uses "malignant vs benign" language, refers to biopsy rather than MRI continuation, and lists Aramis feature families instead of Bremen's.
4. **docs/repository_cleanup.md** — Contains a stale "Future PR Sequencing" table with incorrect PR descriptions and a now-orphaned second roadmap.

This PR rewrites exactly these four files to carry forward the identity anchors from ADR-0001 and the separation policy from ADR-0002.

## 0011A/B/C cascade context

This is the 0011B step of the previously agreed 0011A/B/C lettered cascade convention:

- **PR 0011A** — Architect baseline documents (ADR-0001, ADR-0002, ROADMAP.md, docs/architecture.md) — merged.
- **PR 0011B** — This PR: identity documentation cascade for README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md.
- **PR 0011C** — Platform Readiness ADR Bundle (already branched as 0011-adr-platform-readiness, unblocked once this merges).

After this cascade completes, sequencing returns to normal one-number-one-PR numbering (PR 0012 onward).

## Exact allowed implementation files

The coder may modify exactly these four files:

1. **README.md** — MODIFY. Rewrite product description and development roadmap sections to match ADR-0001 identity anchors.
2. **docs/roadmap.md** — MODIFY. Replace with a stub saying this file is superseded by root ROADMAP.md.
3. **docs/machine_learning_concept.md** — MODIFY. Rewrite title, clinical workflow concept, modeling goal, and feature-family references to match ADR-0001.
4. **docs/repository_cleanup.md** — MODIFY. Add PR 0011A/0011B completion row. Replace stale "Future PR Sequencing" table with pointer to root ROADMAP.md.

## Exact forbidden files

- `docs/adr/0001-bremen-product-identity.md` — read-only reference
- `docs/adr/0002-twin-product-document-separation.md` — read-only reference
- `ROADMAP.md` — read-only reference (root-level; already correct)
- `docs/architecture.md` — read-only reference (already correct)
- `docs/product_development_rules.md` — already correct, do not touch
- `docs/data_preprocessing.md`, `docs/agbh_quality_exclusions.md`, `docs/mlflow.md`, `docs/eosproduct_environment.md` — out of scope
- `src/**`, `tests/**`, `config/**`, `examples/**` — no source/test/config/example changes
- `.github/**`, `Dockerfile`, `.dockerignore`, `sonar-project.properties` — no infrastructure changes
- `requirements.txt`, `pyproject.toml`, `environment.yml`, `Makefile` — no metadata changes
- `AGENTS.md`, `agents/**` — out of scope for product PRs
- `.project-memory/**` other than this PR's own PLAN.md and reviews
- Any H5/HDF5, joblib/pkl/npy/npz artifacts

## Required reads (completed for this PLAN.md)

- `docs/adr/0001-bremen-product-identity.md` — identity anchors: clinical question, NORMAL vs BENIGN+CANCER, 7 feature families, Aramis contrast table
- `docs/adr/0002-twin-product-document-separation.md` — separation policy: permanently separate, provenance only, XRD-preprocessing as shared surface
- `ROADMAP.md` — authoritative roadmap (root-level)
- `docs/architecture.md` — architecture baseline
- `docs/product_development_rules.md` — independent confirmation source for identifier structure and product separation
- `README.md` (current) — to identify Aramis-identity sections
- `docs/roadmap.md` (current) — to be replaced with stub
- `docs/machine_learning_concept.md` (current) — titled "Aramis Machine Learning Concept"
- `docs/repository_cleanup.md` (current) — stale "Future PR Sequencing" table

## Implementation phase assignment

- **Agent**: coder
- **Mode**: implementation

**Reason**: These four files are ordinary product documentation, not architect-reserved paths. Architect-reserved paths are `docs/adr/**`, `ROADMAP.md`, and `docs/architecture.md` per `agents/architect.yml` permissions. The four files planned here are not in that reserved set.

## README.md planned content

### Product Description section (rewrite)

The product description section will be rewritten to state:

- **Clinical question**, verbatim: "Should patient continue to MRI?"
- **Classification task**: healthy vs. disease (NORMAL vs. BENIGN+CANCER), not malignant vs. benign.
- **Target population**: patients referred to MRI after suspicious mammography findings (dense breast / low-efficacy mammography), not patients referred to biopsy.
- **The seven Bremen feature families**, named exactly: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1` — replacing any mention of "complete azimuthal integration" or "cosine asymmetry distance" as Bremen's own features.
- **The existing "derived from Aramis" provenance sentence** is KEPT. ADR-0002 explicitly permits provenance mentions as historical context.
- **No new clinical validation or diagnostic-replacement claims** introduced.

### Development Roadmap section (update)

The "## Development Roadmap" section will be updated to:
- Point to the root `ROADMAP.md` as the authoritative development roadmap (replace the current link to `docs/roadmap.md`).
- Replace the outdated PR description list (which still describes PR 0005/0006/0007 with their originally planned content) with a brief pointer to `ROADMAP.md` for the most up-to-date sequencing.
- Remove the stale PR 0005/0006/0007 descriptions that no longer match what those PRs actually delivered.

### Other sections

Non-identity sections (CLI usage, Repository Split, config file listings, syntax examples) may be preserved or updated for consistency but must not introduce identity drift. No section that currently describes Bremen's product identity may continue to use Aramis's clinical framing (biopsy, malignant vs. benign) as Bremen's own.

## docs/roadmap.md planned content (stub)

Replace the entire file with a short stub (not deleted, to avoid breaking inbound links from other documentation):

```markdown
# Bremen Roadmap

This file is superseded by [ROADMAP.md](../ROADMAP.md) (repository root). See that file for the authoritative Bremen development roadmap.
```

No re-statement of roadmap content. No product identity content. Just the redirect.

## docs/machine_learning_concept.md planned content

### Title

Change from "Aramis Machine Learning Concept" to **"Bremen Machine Learning Concept"**.

### "## Clinical Workflow Concept" section

Rewrite to MRI-continuation / healthy-vs-disease framing, matching ADR-0001 exactly:

- **Clinical question**: "Should patient continue to MRI?" (not "Does the suspicious breast side likely need biopsy?").
- **Target population**: Patients referred to MRI after suspicious mammography findings (not patients referred to biopsy).
- **Clinical workflow**: Suspicious mammography finding → XRD measurement of both breasts → comparison → decision support for MRI continuation (not biopsy decision).

### "## Modeling Goal" section

Rewrite to healthy-vs-disease framing:

- **Output**: `p_disease` / `suggested class: NORMAL or DISEASE` (replacing `p_cancer` / `BENIGN or CANCER`).
- **Classification goal**: separate healthy (NORMAL) from disease (BENIGN+CANCER), not malignant vs. benign.
- **Label grouping**: NORMAL as the healthy/control group; BENIGN, CANCER, ATYPICAL, PRE_CANCEROUS as the disease group.

### Feature-family references

Replace all mentions of Aramis feature families (complete azimuthal integration / components approach, cosine asymmetry distance / symmetry approach) as Bremen's own features with the seven Bremen feature families: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.

If Aramis feature families are mentioned for historical/provenance context (e.g., to explain how Bremen's approach was derived or differs), they must be clearly labeled as Aramis's approach and contrasted with Bremen's approach — not presented as Bremen's own features.

### Identifier structure

The patient/breast/measurement identifier structure (`patientId`, `specimenId`, breast side, measurement position P1/P2/P3, `measurementId`) is genuinely product-agnostic, as confirmed by `docs/product_development_rules.md`. It may be kept without modification.

The one-to-one (contralateral comparison) and one-to-many (population comparison) structure is symmetric between products and may be kept. Its purpose description must be updated to MRI-continuation framing (not biopsy decision).

### Sections that may be preserved with minimal changes

- "### Patient Measurement Unit" — identifier structure kept.
- "### Model Components" subsections — the one-to-many / one-to-one / fusion structure is symmetric; descriptions updated to MRI/healthy-vs-disease framing.
- "### Draft Pipeline" — preserved, with name updated.
- "### Training And Validation Rules" — product-agnostic; preserved.
- "### Data Quality And Monochromaticity" — product-agnostic; preserved.
- "### Current Decisions" — product-agnostic; preserved.
- "### Open Questions" — product-agnostic; preserved.

## docs/repository_cleanup.md planned content

### Add PR 0011A + PR 0011B completed-item row

Add new rows to the "Completed" sections (or a new "Completed (PR 0011A/B — Identity Architecture)" section):

| Item | Status | Details |
|------|--------|---------|
| ADR-0001 (Bremen product identity) | ✅ Done | PR 0011A. Product identity ADR with clinical question, classification task, 7 feature families, Aramis contrast. |
| ADR-0002 (Twin product separation) | ✅ Done | PR 0011A. Permanent separation from Aramis; XRD-preprocessing as only shared surface. |
| ROADMAP.md (root-level) | ✅ Done | PR 0011A. Product Track roadmap with 12 sequenced items. |
| docs/architecture.md | ✅ Done | PR 0011A. Architecture baseline with core chain and 11 safety invariants. |
| Identity documentation cascade | ✅ Done | PR 0011B. README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md aligned with ADR-0001/ADR-0002. |

### Replace the stale "Future PR Sequencing" table

The existing table at the bottom of `docs/repository_cleanup.md` has a "Future PR Sequencing" table that still describes PR 0005/0006/0007 with their originally planned content from before those PR numbers were repurposed. Replace this table with a single sentence pointing to the root `ROADMAP.md`:

```markdown
## Future PR Sequencing

The authoritative Bremen development roadmap is now maintained in [ROADMAP.md](../ROADMAP.md) (repository root). This file retains only the completed cleanup items above.
```

## Non-goals

- No changes to `docs/adr/0001-bremen-product-identity.md`, `docs/adr/0002-twin-product-document-separation.md`, `ROADMAP.md`, or `docs/architecture.md` (already correct, merged — read-only reference).
- No changes to `docs/product_development_rules.md` (already correct).
- No source code, test, CI, Docker, requirements, config, or example changes.
- No changes to `agents/**` tooling.
- No new clinical validation or diagnostic-replacement claims.
- No re-litigating ADR-0001/ADR-0002 content — implement what they already decided, do not re-derive it.
- No changes to docs listed as historical/source-material in ADR-0002's Consequences (config audit files, packaging, etc.).

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1) Working tree state
git status --short

# 2) Changed files — only the 4 allowed files
git diff --name-only

# 3) Precondition: PR 0011A files still present
test -f docs/adr/0001-bremen-product-identity.md || exit 1
test -f docs/adr/0002-twin-product-document-separation.md || exit 1
test -f ROADMAP.md || exit 1
test -f docs/architecture.md || exit 1
```

### ADR-0001 identity anchors in README.md and docs/machine_learning_concept.md

```bash
# 4) Clinical question present in both
grep -q "Should patient continue to MRI?" README.md || exit 1
grep -q "Should patient continue to MRI?" docs/machine_learning_concept.md || exit 1

# 5) NORMAL present in both
grep -q "NORMAL" README.md || exit 1
grep -q "NORMAL" docs/machine_learning_concept.md || exit 1

# 6) BENIGN+CANCER present in both
grep -q "BENIGN+CANCER" README.md || exit 1
grep -q "BENIGN+CANCER" docs/machine_learning_concept.md || exit 1

# 7-13) All 7 Bremen feature-family names present in README.md and docs/machine_learning_concept.md
for f in sigma_l1 sigma_l2 Mahalanobis1 Mahalanobis2 wasserstein_distance_full_q2 meanrms2 weightedrms1; do
  grep -q "$f" README.md || exit 1
  grep -q "$f" docs/machine_learning_concept.md || exit 1
done
```

### Prohibited Aramis-identity framing

```bash
# 14) No "referred to biopsy" or "malignant vs. benign" as Bremen's OWN framing
# (Historical Aramis-provenance mentions, clearly labeled, are acceptable)
grep -i -n -E "referred to biopsy|malignant vs\.? benign" README.md docs/machine_learning_concept.md && \
  echo "WARNING: Check context — these may be acceptable provenance mentions" || \
  echo "OK"

# 15) No "azimuthal integration" or "cosine asymmetry" as Bremen's OWN feature list
# (Aramis feature mentions in provenance context are acceptable)
grep -i -n -E "azimuthal integration.*components|cosine asymmetry" README.md && \
  echo "WARNING: Check context — may need to be labeled as Aramis" || echo "OK"
```

### Target file content checks

```bash
# 16) docs/machine_learning_concept.md title updated
grep -q "Bremen Machine Learning Concept" docs/machine_learning_concept.md || exit 1

# 17) ROADMAP.md referenced in README.md, docs/roadmap.md, and docs/repository_cleanup.md
grep -q "ROADMAP.md" README.md || exit 1
grep -q "ROADMAP.md" docs/roadmap.md || exit 1
grep -q "ROADMAP.md" docs/repository_cleanup.md || exit 1

# 18) docs/roadmap.md is a stub (no product identity content)
grep -q "superseded by\|redirect\|See.*ROADMAP.md\|authoritative" docs/roadmap.md || exit 1
```

### Prohibited clinical/diagnostic claims

```bash
# 19) No prohibited claims in any of the 4 files
for f in README.md docs/roadmap.md docs/machine_learning_concept.md docs/repository_cleanup.md; do
  grep -i -n -E "FDA.?cleared|FDA.?approved|clinically.?validated|replacement.?for.?MRI|autonomous.?diagnos|replace.?radiologist|replace.?clinician|replace.?biopsy" "$f" && exit 1 || true
done
```

### Forbidden file changes check

```bash
# 20) No changes to architect-reserved or infrastructure files
git diff --name-only -- docs/adr src tests config examples .github Dockerfile .dockerignore requirements.txt pyproject.toml sonar-project.properties environment.yml Makefile AGENTS.md agents/ docs/architecture.md ROADMAP.md
# Must return nothing
```

### Additional safety checks

```bash
# 21) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

If any of the four documentation files contain errors after rewrite:

1. **README.md** — Revert to the pre-PR-0011B version. The previous version was functionally correct (if identity-misaligned); rollback preserves access to CLI usage and product-development content.
2. **docs/roadmap.md** — Revert to the pre-PR-0011B version. The previous version had detailed PR descriptions; rollback unbreaks inbound links.
3. **docs/machine_learning_concept.md** — Revert to the pre-PR-0011B version. The previous version had complete technical content (if identity-misaligned).
4. **docs/repository_cleanup.md** — Revert to the pre-PR-0011B version. Remove the new PR 0011A/B rows and restore the stale Future PR Sequencing table (it was incorrect but functional as a historical artifact).

Each file is independent and can be reverted individually.

## Follow-up PRs

- **PR 0011C** — Platform Readiness ADR Bundle (ADR-0003 through ADR-0006, Platform Readiness Track, Decision Gate Register). Already branched as `0011-adr-platform-readiness`. Unblocked once PR 0011B merges.
- **PR 0012 onward** — Normal sequencing resumes: clinical report template, training config template, feature-family implementation, etc.

## Plan Drift Gate

Precommit-review must check each of these drift categories. Any drift blocks merge until resolved.

| Drift category | Check |
|----------------|-------|
| **File drift** | Only the 4 allowed files (README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md) changed. |
| **Identity drift** | README.md and docs/machine_learning_concept.md carry ADR-0001 identity anchors verbatim (clinical question, NORMAL vs BENIGN+CANCER, all 7 feature families). No "referred to biopsy" or "malignant vs benign" as Bremen's own framing. |
| **Roadmap stub drift** | docs/roadmap.md is a short stub redirecting to root ROADMAP.md. No roadmap content. No identity content. |
| **ML concept drift** | Title changed to "Bremen Machine Learning Concept." Clinical workflow and modeling goal rewritten to MRI/healthy-vs-disease framing. Feature families replaced with Bremen's 7. |
| **Cleanup doc drift** | PR 0011A/B rows added. Stale Future PR Sequencing table replaced with pointer to root ROADMAP.md. |
| **Architect boundary drift** | No changes to docs/adr/**, ROADMAP.md, or docs/architecture.md. |
| **Infrastructure drift** | No changes to CI/Docker/SonarCloud/pyproject/config/source/tests/agents. |
| **Validation drift** | All validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Any file outside the four allowed files is planned or modified.
- ADR-0001 identity anchors (clinical question, NORMAL vs BENIGN+CANCER, all 7 feature families) are missing from README.md or docs/machine_learning_concept.md planned content.
- docs/roadmap.md plan does anything other than stub-and-redirect (no roadmap content, no identity content).
- docs/repository_cleanup.md plan does not fix the stale PR-sequencing table.
- Implementation phase is assigned to architect instead of coder.
- Changes are planned to `docs/adr/`, `ROADMAP.md`, or `docs/architecture.md`.
- Prohibited clinical/diagnostic claims are added.
- The identifier structure check from `docs/product_development_rules.md` has not been performed as a named step.

## Decisions summary

### Allowed files
1. `README.md` — MODIFY (rewrite product description and development roadmap)
2. `docs/roadmap.md` — MODIFY (replace with stub)
3. `docs/machine_learning_concept.md` — MODIFY (rewrite title, workflow, goals, feature references)
4. `docs/repository_cleanup.md` — MODIFY (add PR 0011A/B rows, fix stale table)

### Forbidden files
- `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md` — architect-owned, read-only
- `docs/product_development_rules.md` — already correct
- `src/**`, `tests/**`, `config/**`, `examples/**`, `.github/**`, `Dockerfile`, `.dockerignore`
- `requirements.txt`, `pyproject.toml`, `environment.yml`, `Makefile`, `AGENTS.md`, `agents/**`
- Any H5/HDF5, joblib/pkl/npy/npz artifacts

### README.md identity summary
- Clinical question: "Should patient continue to MRI?" (verbatim)
- Classification task: NORMAL vs BENIGN+CANCER (healthy vs disease), not malignant vs benign
- Target population: patients referred to MRI after suspicious mammography (not biopsy)
- All 7 Bremen feature families replace Aramis features as Bremen's own
- "Derived from Aramis" provenance sentence preserved
- Development roadmap points to root ROADMAP.md
- No new clinical/diagnostic claims

### docs/roadmap.md stub summary
- Short redirect to root `ROADMAP.md`
- No product identity content, no roadmap content, no PR descriptions

### docs/machine_learning_concept.md rewrite summary
- Title: "Bremen Machine Learning Concept" (not "Aramis ML Concept")
- Clinical workflow: MRI-continuation framing, healthy vs disease
- Modeling goal: separate healthy (NORMAL) from disease (BENIGN+CANCER)
- Feature families: all 7 Bremen families as own features; Aramis families only as labeled provenance
- Identifier structure: kept (product-agnostic per product_development_rules.md)
- Technical sections (training, quality, decisions, open questions): preserved with minimal changes

### docs/repository_cleanup.md summary
- New rows: PR 0011A (ADR-0001, ADR-0002, ROADMAP.md, architecture.md) + PR 0011B (this cascade)
- Stale Future PR Sequencing table replaced with pointer to root ROADMAP.md

### Implementation agent assignment
- Agent: coder
- Mode: implementation

### Validation checklist
21 checks: working tree state, changed files, precondition verification, ADR-0001 identity anchors in README.md and docs/machine_learning_concept.md (11 checks), prohibited Aramis framing (2 checks), target file content (3 checks), prohibited clinical claims (1 check), forbidden file changes (1 check), .DS_Store (1 check).

### Stop conditions
8 block conditions: file drift, missing identity anchors, non-stub roadmap, stale table not fixed, wrong agent assignment, architect file changes, prohibited claims, missing identifier check.

### Rollback plan
Each of the four files can be reverted independently.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0011b-bremen-identity-doc-cascade/PLAN.md`
2. Human runs: `git add .project-memory/pr/0011b-bremen-identity-doc-cascade/PLAN.md`
3. Human runs: `git commit -m "PR 0011B — Plan Bremen identity documentation cascade"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the four allowed files.

## Files read

- `docs/adr/0001-bremen-product-identity.md`
- `docs/adr/0002-twin-product-document-separation.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `docs/product_development_rules.md`
- `README.md` (current)
- `docs/roadmap.md` (current)
- `docs/machine_learning_concept.md` (current)
- `docs/repository_cleanup.md` (current)

## Files written

- `.project-memory/pr/0011b-bremen-identity-doc-cascade/PLAN.md` (this file)

## Files intentionally ignored

- All architect-reserved files (docs/adr/**, ROADMAP.md, docs/architecture.md)
- All source, test, config, example files
- All infrastructure files (Docker, CI, SonarCloud, etc.)
- `docs/product_development_rules.md` (already correct)
- `docs/data_preprocessing.md`, `docs/agbh_quality_exclusions.md`, `docs/mlflow.md`, `docs/eosproduct_environment.md`
- `AGENTS.md`, `agents/**`
- Any H5/HDF5 or model artifacts

## Boundary confirmations

- confirm: precondition files (PR 0011A outputs) verified present: yes
- confirm: this PR only plans README.md, docs/roadmap.md, docs/machine_learning_concept.md, docs/repository_cleanup.md: yes
- confirm: no docs/adr/**, ROADMAP.md, or docs/architecture.md changes planned: yes
- confirm: ADR-0001 identity anchors carried forward verbatim, not re-derived: yes
- confirm: implementation phase assigned to Agent: coder: yes
- confirm: no source/test/CI/Docker/requirements/config/H5/model/agents changes planned: yes
- confirm: no git mutation commands run: yes
- confirm: identifier structure check from product_development_rules.md named as required step: yes
- confirm: docs/machine_learning_concept.md identifier structure confirmed product-agnostic: yes
