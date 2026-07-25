# PR0090 — ADR Exception for Process-Isolated Aramis Runtime and Source-Access Gate

**Governance PR only — no runtime, Docker, source, or test changes.**

---

## 1. BLOCKERS

| Blocker | Status |
|---------|--------|
| Branch mismatch | ✅ Resolved — `0090-aramis-subprocess-governance-gate` |
| ADR-0002 text readable | ✅ Read |
| No Docker implementation planned | ✅ Confirmed |
| No source/test/runtime changes planned | ✅ Confirmed |
| No in-process import permitted | ✅ Designed out |
| No shared site-packages permitted | ✅ Designed out |
| No immediate product exposure | ✅ Designed out |
| No decision vocabulary mapping | ✅ Designed out |
| Public demo safety not weakened | ✅ Designed out |
| Real Aramis source/bundle still required before Docker work | ✅ Gate preserved |
| Existing no-aramis tests not silently ignored | ✅ Migration plan included |

No remaining blockers.

---

## 2. WARNINGS

1. This PR is **documentation/governance only**. A future PR (PR0091 or later) must still provide the actual Aramis runtime source/bundle before any Docker work.
2. Existing `test_no_aramis_*` tests will continue to pass because this PR does not touch `src/`, `tests/`, or product-facing output. No test weakening occurs.
3. The `requirements.txt` comment referencing ADR-0002 is NOT updated in this PR. A future implementation PR may update the comment to reference the new ADR exception instead. See section 7.
4. ROADMAP.md update is optional. Project conventions do not require gate registration in ROADMAP.md, but adding a brief entry for PR0090's governance completion is recommended for roadmap traceability.

---

## 3. FILES CHANGED

Only the following file will be created/updated by this PR:

| File | Action | Justification |
|------|--------|---------------|
| `docs/adr/0013-aramis-process-isolated-runtime-exception.md` | **CREATE** | New ADR superseding ADR-0002's prohibition for the specific case of process-isolated subprocess integration with phased gates |
| `ROADMAP.md` | **MAY UPDATE** | Optional — add brief entry for PR0090 governance completion if project convention requires roadmap gate registration (not required by existing ADR conventions) |

**Explicitly not changed:**
- `src/` — no source code
- `tests/` — no test code
- `Dockerfile`, `Dockerfile.training` — no Docker changes
- `requirements.txt` — no dependency changes
- `.github/` — no CI changes
- `infra/` — no infrastructure changes
- `AGENTS.md` — not changed (historical context already acknowledges Aramis derivation)
- `.project-memory/project_contract.yml` — not changed

---

## 4. ADR STRATEGY

### Option chosen: Option A

**Create new ADR `docs/adr/0013-aramis-process-isolated-runtime-exception.md`** (next available number).

### Why Option A over Option B

| Criteria | Option A (New ADR) | Option B (Amend ADR-0002) |
|----------|-------------------|--------------------------|
| Audit trail clarity | ✅ Clear: original prohibition preserved, exception layered on top | ❌ Original prohibition text must be altered |
| Rollback semantics | ✅ Remove one file to restore prohibition | ❌ Must re-edit ADR-0002 |
| Test/policy references | ✅ New exception is self-contained; ADR-0002 references remain valid for product-facing code | ❌ ADR-0002 must be re-read to understand which parts still apply |
| Precedent in repo | ✅ ADR-0012 already exists as independent decision; no existing ADR has been amended | ❌ No existing ADR amendment precedent |
| Supersedes relationship | ✅ New ADR explicitly declares it supersedes ADR-0002 for this specific case | ❌ Unclear scope of amendment |

### Relationship to ADR-0002

ADR-0013 will:

- **Acknowledge** ADR-0002 as the governing separation policy for product-facing concerns.
- **Declare a narrow exception** for Docker-level, process-isolated Aramis runtime bundling for smoke/integration purposes only.
- **State that ADR-0002 remains in full force** for all product-facing surfaces (public API, UI, reports, model catalog, demo routes, decision vocabulary).

### ADR file name

`docs/adr/0013-aramis-process-isolated-runtime-exception.md`

---

## 5. ADR-0002 CURRENT PROHIBITION

**ADR-0002 verbatim text:**

> **Separation policy**: Bremen and Aramis are permanently separate forks/products/final deliverables.
>
> **Aramis in Bremen**: Aramis may appear in Bremen only as historical/provenance context (fork origin). Aramis is not an active dependency, runtime, shared feature set, API, or configuration target for Bremen.
>
> **Shared technical surface**: The only shared technical surface between the two products is the upstream XRD-preprocessing repository.
>
> **Prohibition**: No Aramis-specific architecture, endpoints, or configuration should be added to Bremen as a result of this or any future PR.

**Impact**: This flatly prohibits the planned Phase 1 Docker-level Aramis runtime bundling. ADR-0013 must create a carve-out.

### Where ADR-0002 remains in full force

Even after ADR-0013, ADR-0002 continues to apply to:

- In-process imports of Aramis Python modules into the Bremen Python process
- Shared Python site-packages between Bremen and Aramis
- Public `/demo` routes exposing Aramis content
- Bremen model catalog allowlisting Aramis workflow IDs
- Bremen decision vocabulary (`CONTINUE_MRI`, `MRI_REVIEW_DEFER`, `p_mri_needed`) mapping from Aramis outputs
- Raw Aramis clinical report wording in Bremen product surfaces
- Bremen product API returning Aramis-specific fields
- Clinical-equivalence claims between Aramis and Bremen outputs

---

## 6. PROPOSED EXCEPTION BOUNDARY

### New ADR-0013 content specification

```
Title:    Process-Isolated Aramis Runtime Exception
Status:   Accepted (supersedes ADR-0002 for this specific case)
```

### Context section

- ADR-0002 currently prohibits Aramis as active dependency, runtime, API, or configuration target.
- `AramisProvider` exists as an inert scaffold in `src/bremen/api/workflow_aramis.py`.
- Product owner wants a second workflow path (`workflow_id: "aramis"`) for parallel decision support.
- Integration must be strictly process-isolated (subprocess), never in-process import.
- Integration must proceed in explicit phases, each gated by the previous phase's completion.

### Decision section

Permit Aramis runtime only as:
- **Process-isolated subprocess integration** under explicit phased gates.
- **Docker-level bundling** in isolated virtual environment (e.g., `/opt/aramis-venv`).
- **One-shot subprocess per job** — no persistent process, pool, or IPC server.
- **No network service** — subprocess within the same container only.

Explicitly **not permitted** by this exception:
- In-process imports (`import aramis`) into Bremen Python process.
- Shared Python site-packages (`pip install aramis` into Bremen's environment).
- Shared feature sets between Bremen and Aramis.
- Shared decision vocabulary or clinical-equivalence mapping.
- Public `/demo` exposure in the Docker smoke phase.
- Raw Aramis directive clinical report wording in Bremen `/demo` or product surfaces.
- Model catalog allowlist changes (deferred to Phase 4).
- Persistent process, process pool, IPC server, or network service.
- Real patient data in Phase 1 or Phase 2.
- Guessing Aramis dependencies, CLI contract, or output schema.

### Boundary conditions table

| Concern | Permitted | Not Permitted |
|---------|-----------|---------------|
| Python environment | Separate venv (`/opt/aramis-venv`) | Bremen's own site-packages |
| Process model | One-shot subprocess per job | Persistent daemon, pool, IPC server |
| Network | Same-container subprocess only | TCP/UDP service, HTTP server, RPC |
| Vocabulary | Aramis keeps native output | Mapping into Bremen decision codes |
| Product exposure | Internal Docker smoke only | Public UI, API, /demo routes |
| Report wording | Aramis native output files only | Copying directive language into Bremen reports |
| Patient data | Synthetic/approved fixtures only | Real patient H5 files |
| Source guessing | Must use official bundle/contract | Fabricating dependencies or CLI syntax |

### Source access gate

Docker work (Phase 1) cannot begin until **at least one** of the following is provided as a verifiable artifact in the repository:

1. Official Aramis runtime source tree (e.g., cloned from `https://github.com/Eos-Dx/Aramis.git` at a tagged release).
2. Official Aramis Docker/runtime bundle (e.g., `aramis_docker_training_bundle_*`).
3. Official `requirements.txt`, `environment.yml`, or `pyproject.toml` from the Aramis runtime.
4. Official `predict.sh`, `run_prediction_docker.sh`, or equivalent CLI entrypoint from the Aramis team.
5. Written subprocess/CLI contract from the Aramis team specifying: invocation syntax, required input paths, expected output files, exit codes, and environment variables.

**Every future implementation plan must cite the exact source/bundle used.** No plan may guess, reverse-engineer, or fabricate Aramis behavior.

### Phased sequence

| Phase | Title | Description | Depends on |
|-------|-------|-------------|------------|
| **1** | Docker-level smoke proof | Install Aramis into isolated venv in Docker image. Smoke command runs Aramis subprocess, exits 0, produces expected output. No product code wiring. | ADR-0013 + Aramis source/bundle |
| **2** | Provider subprocess invocation | Wire `AramisProvider.execute()` to spawn Aramis subprocess. Parse exit code and output file existence. No clinical parsing. | Phase 1 + confirmed Aramis CLI contract |
| **3** | Checksummed artifact/manifest | Load Aramis via checksum-verified manifest (parallel to Bremen's model package). | Phase 2 |
| **4** | Workflow allowlist | Add `aramis` to `_ALLOWED_WORKFLOW_IDS` or equivalent allowlist for public workflow selection. | Phase 3 + safety review |
| **5** | Safe native-result presentation | Display Aramis's native output in controlled UI surface with appropriate disclaimers. No Bremen vocabulary mapping. | Phase 4 + presentation safety review |

### Non-goals (ADR text)

- No clinical-equivalence mapping between Aramis and Bremen.
- No `p_cancer → p_mri_needed` mapping.
- No `CANCER/NON-CANCER → CONTINUE_MRI/MRI_REVIEW_DEFER` mapping.
- No Aramis report language copied into Bremen `/demo`.
- No immediate runtime activation after ADR-0013 alone.

### Rollback

- Removing `docs/adr/0013-aramis-process-isolated-runtime-exception.md` restores ADR-0002 prohibition to full force for all concerns including process-isolated bundling.
- No code changes are required for rollback of this governance PR itself (it creates no runtime behavior).
- For future phases, rollback of Docker/implementation changes would be separate PRs.

---

## 7. TEST AND POLICY MIGRATION PLAN

### Existing `no_aramis` test inventory

The following tests assert "aramis" must not appear in product-facing surfaces. These tests **remain valid and unchanged** after ADR-0013:

| Test file | Test method | Scope | Status after ADR-0013 |
|-----------|-------------|-------|----------------------|
| `test_bremen_api_contract.py` | `test_no_aramis_identity` | API contract document | ✅ Unchanged — product API must not contain "aramis" |
| `test_bremen_cli_entrypoint.py` | `test_help_no_aramis` | CLI help output | ✅ Unchanged — product CLI must not contain "aramis" |
| `test_bremen_config_loading.py` | `test_no_aramis_in_docstring` | Config module docstring | ✅ Unchanged — product source must not contain "aramis" |
| `test_bremen_config_loading.py` | `test_no_aramis_in_error_messages` | Config error messages | ✅ Unchanged — product errors must not contain "aramis" |
| `test_bremen_decision_vocabulary.py` | `test_no_aramis_decision_code_in_bremen` | Decision policy IDs | ✅ Unchanged — decision vocabulary must not contain "aramis" |
| `test_bremen_demo_capture.py` | `test_no_aramis_in_capture_files` | Demo capture output | ✅ Unchanged — demo capture must not contain "aramis" |
| `test_bremen_demo_capture.py` | `test_no_aramis_in_module_source` | Demo capture source | ✅ Unchanged — product source must not contain "aramis" |
| `test_bremen_demo_evidence.py` | `test_no_aramis_in_evidence_bundle` | Demo evidence output | ✅ Unchanged — demo evidence must not contain "aramis" |
| `test_bremen_demo_evidence.py` | `test_no_aramis_in_build_function` | Evidence build function | ✅ Unchanged — product source must not contain "aramis" |
| `test_bremen_demo_evidence.py` | `test_rejects_bundle_with_aramis_in_optional_field` | Evidence validation | ✅ Unchanged — evidence must reject "aramis" |
| `test_bremen_demo_presentation.py` | `test_no_aramis_in_pretty_output` | Demo presentation output | ✅ Unchanged — demo output must not contain "aramis" |
| `test_bremen_demo_presentation.py` | `test_no_aramis_in_module_source` | Demo presentation source | ✅ Unchanged — product source must not contain "aramis" |
| `test_bremen_demo_ui.py` | `test_no_aramis_in_html` | Demo HTML output | ✅ Unchanged — demo UI must not contain "aramis" |
| `test_bremen_demo_ui.py` | `test_no_aramis_in_json` | Demo JSON output | ✅ Unchanged — demo API must not contain "aramis" |
| `test_bremen_demo_ui.py` | `test_no_aramis_in_module_source` | Demo UI source | ✅ Unchanged — product source must not contain "aramis" |
| `test_bremen_import_identity.py` | `test_bremen_pipelines_no_aramis_class_names` | Pipeline class names | ✅ Unchanged — no Aramis class names in product |
| `test_bremen_import_identity.py` | `test_no_aramis_class_names_in_src` | Source class names | ✅ Unchanged — no Aramis class names in `src/` |
| `test_bremen_model_package.py` | `test_no_aramis_references` | Model package content | ✅ Unchanged — model packages must not contain "aramis" |
| `test_bremen_execution_showcase.py` | (inline assertions) | Orchestrator source | ✅ Unchanged — no hardcoded `workflow_id == "aramis"` |

### Future test distinction

A future Phase 1 implementation will need to distinguish between:

1. **Product-facing output** (help text, HTML, JSON, evidence bundles, API responses) — these must still pass the existing `test_no_aramis_*` tests.
2. **Internal Docker smoke artifacts** (e.g., `/opt/aramis-venv/`, `tests/smoke/aramis-output/`) — these are not shipped to end users and may contain "aramis" strings.

The ADR-0013 text will include a note that future implementation tests for Docker smoke artifacts should be scoped to avoid the same check paths as the existing product-facing tests.

### No test changes in this PR

This PR (governance only) does not modify any test files. The above migration analysis is for future implementation awareness only.

---

## 8. REQUIREMENTS COMMENT UPDATE

### Current state

`requirements.txt` contains the following comment:

```
#
# Aramis is not an active Bremen dependency (ADR-0002) — the
# stale local-path editable line has been removed.
```

### Plan

**Do not update `requirements.txt` in this governance PR.** The comment is factually correct about ADR-0002's current prohibition and the removal of the stale editable line.

**Future implementation plan**: When Phase 1 (Docker-level smoke) is planned, the comment may be updated to:

```
# Aramis is not an active Bremen dependency — it runs in an isolated
# venv (/opt/aramis-venv) via subprocess. See ADR-0013 for the
# process-isolated runtime exception. Do not add Aramis to
# Bremen's site-packages or pyproject.toml dependencies.
```

This update would happen in the Phase 1 implementation PR, not in this governance PR. The current PR preserves the status quo.

---

## 9. VALIDATION PLAN

### Pre-implementation validation

```bash
# Git state
git rev-parse --verify HEAD
git branch --show-current        # Must be 0090-aramis-subprocess-governance-gate
git status --short               # Must be clean (no uncommitted changes)
git diff --name-only             # Only docs/adr/0013-*.md (and optionally ROADMAP.md)
```

### Content validation

```bash
# Verify the new ADR exists and contains required sections
test -f docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "ADR exists" || echo "MISSING ADR"

# Verify mandatory section headers
grep -q "## Status" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Status section found" || echo "MISSING Status"
grep -q "## Context" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Context section found" || echo "MISSING Context"
grep -q "## Decision" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Decision section found" || echo "MISSING Decision"
grep -q "## Boundary conditions" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Boundary conditions found" || echo "MISSING Boundary conditions"
grep -q "## Source access gate" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Source access gate found" || echo "MISSING Source access gate"
grep -q "## Phased sequence" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Phased sequence found" || echo "MISSING Phased sequence"
grep -q "## Non-goals" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Non-goals found" || echo "MISSING Non-goals"
grep -q "## Rollback" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Rollback found" || echo "MISSING Rollback"

# Verify process-isolated language
grep -q "process-isolated\|subprocess" docs/adr/0013-aramis-process-isolated-runtime-exception.md && \
  echo "Process-isolation language present" || echo "MISSING process-isolation language"
```

### Safety greps — no clinical-equivalence mapping

```bash
grep -rn "p_mri_needed\|CONTINUE_MRI\|MRI_REVIEW_DEFER\|decision_policy" docs/adr/ ROADMAP.md || true
# Expected: no matches, OR matches only in explicit prohibited-example context
```

### Safety greps — no source changes

```bash
grep -rn "workflow_aramis\|_ALLOWED_WORKFLOW_IDS\|s3_model_discovery" src tests || true
# Expected: only pre-existing references in workflow_aramis.py, report_aramis.py,
#            workflow_orchestrator.py, and their tests — no new references from this PR
```

### Docs lint

No dedicated docs linter was found in the repository. Run basic markdown validation:

```bash
# Check for basic markdown formatting issues
python -c "
import re
with open('docs/adr/0013-aramis-process-isolated-runtime-exception.md') as f:
    content = f.read()
# Check for common issues
lines = content.split('\n')
if any(l.strip().startswith('```') for l in lines):
    print('Code blocks present — OK')
if content.count('|') > 0:
    print('Tables present — OK')
print(f'Total lines: {len(lines)}')
print(f'Total chars: {len(content)}')
" || echo "No docs lint runner available — manual review required"
```

### Also run

```bash
# General diff hygiene
git diff --check

# Confirm no src/ changes
git diff --name-only | grep -q "^src/" && echo "ERROR: src changes detected" || echo "No src changes — OK"

# Confirm no tests/ changes  
git diff --name-only | grep -q "^tests/" && echo "ERROR: tests changes detected" || echo "No tests changes — OK"

# Confirm no Docker changes
git diff --name-only | grep -q "^Dockerfile" && echo "ERROR: Docker changes detected" || echo "No Docker changes — OK"
```

---

## 10. NON-GOALS CONFIRMED

| Non-goal | Status |
|----------|--------|
| No AramisProvider implementation | ✅ Excluded — Phases 2+ |
| No model catalog workflow allowlist change | ✅ Excluded — Phase 4 |
| No public UI or API change | ✅ Excluded — governance PR only |
| No report change | ✅ Excluded — governance PR only |
| No report wording | ✅ Excluded — ADR-0013 explicitly forbids |
| No Aramis result parsing into Bremen types | ✅ Excluded — requires Phase 2+ contract |
| No clinical-equivalence mapping | ✅ ADR-0013 explicitly forbids |
| No persistent process | ✅ Boundary conditions forbid |
| No network service | ✅ Boundary conditions forbid |
| No real patient data | ✅ Source access gate forbids |
| No Phase 2 contract work | ✅ Phased sequence documents deferral |
| No Phase 3 model artifact work | ✅ Phased sequence documents deferral |
| No Phase 4 allowlist work | ✅ Phased sequence documents deferral |
| No Phase 5 presentation work | ✅ Phased sequence documents deferral |
| No Docker implementation in this PR | ✅ Governance-only scope |
| No Phase 1 smoke implementation in this PR | ✅ Governance-only scope |
| No source/test/runtime changes | ✅ Verified by validation plan |

---

## 11. STOP CONDITIONS CONFIRMED

| Condition | Status |
|-----------|--------|
| Branch mismatch | ✅ Matches: `0090-aramis-subprocess-governance-gate` |
| ADR-0002 text cannot be read | ✅ Read and cited |
| Plan attempts Docker implementation | ✅ Not attempted |
| Plan attempts source/test/runtime changes | ✅ Not attempted |
| Plan permits in-process import | ✅ Boundary conditions forbid |
| Plan permits shared site-packages | ✅ Boundary conditions forbid |
| Plan permits immediate product exposure | ✅ Phased sequence defers |
| Plan maps Aramis output to Bremen decision vocabulary | ✅ ADR-0013 non-goals forbid |
| Plan weakens public demo safety | ✅ Test migration preserves all existing tests |
| Plan removes need for real Aramis source/bundle | ✅ Source access gate preserved |
| Plan silently ignores existing no-aramis tests | ✅ Section 7 documents all 19 tests |

---

## 12. IMPLEMENTATION SEQUENCE FOR CODER

### Step 1: Create ADR-0013

Create `docs/adr/0013-aramis-process-isolated-runtime-exception.md` with the following structure:

```
# ADR-0013: Process-Isolated Aramis Runtime Exception

**Status**: Accepted

**Supersedes**: ADR-0002 for the specific case of process-isolated,
  Docker-level Aramis runtime bundling for smoke/integration purposes.
  ADR-0002 remains in full force for all product-facing surfaces
  (public API, UI, reports, model catalog, demo routes, decision
  vocabulary).

## Context

ADR-0002 currently prohibits Aramis as an active dependency, runtime,
shared feature set, API, or configuration target for Bremen.

An inert AramisProvider scaffold exists at
src/bremen/api/workflow_aramis.py, registered in
src/bremen/api/workflow_orchestrator.py, returning
workflow_unavailable.

Product owner now wants a second workflow path
(workflow_id: "aramis") for parallel decision support, with strict
process isolation and phased gates.

## Decision

Permit Aramis runtime only as process-isolated subprocess integration
under the explicit phased sequence defined below.

The following are permitted:
- Docker-level bundling in an isolated Python virtual environment
  (separate from Bremen's site-packages).
- One-shot subprocess invocation per job.
- Subprocess within the same container (no network service).

The following remain prohibited by ADR-0002 and this exception does
not alter that:
- In-process imports of Aramis Python modules into the Bremen Python
  process.
- Shared Python site-packages between Bremen and Aramis.
- Shared feature sets, label mappings, or preprocessing configurations.
- Shared decision vocabulary or clinical-equivalence mapping.
- Public /demo routes exposing Aramis content.
- Bremen model catalog allowlisting Aramis workflow IDs.
- Raw Aramis directive clinical report wording in Bremen product
  surfaces.
- Bremen product API returning Aramis-specific fields.
- Clinical-equivalence claims between Aramis and Bremen outputs.

## Boundary conditions

[TABLE from section 6]

## Source access gate

[Verbatim text from section 6]

## Phased sequence

[Table from section 6]

## Non-goals

[List from section 6]

## Test and policy migration

Existing "no aramis in public output" tests (19 tests across
test_bremen_demo_ui.py, test_bremen_demo_presentation.py,
test_bremen_demo_evidence.py, test_bremen_demo_capture.py,
test_bremen_cli_entrypoint.py, test_bremen_api_contract.py,
test_bremen_import_identity.py, test_bremen_config_loading.py,
test_bremen_decision_vocabulary.py, test_bremen_model_package.py,
test_bremen_execution_showcase.py) remain valid for product-facing
surfaces.  No existing test is weakened by this ADR.

Future implementation PRs must scope new tests to avoid the same
check paths as product-facing tests — Docker smoke artifacts are
internal only and not shipped to end users.

## Requirements.txt implications

ADR-0002's comment in requirements.txt remains accurate for the
current state.  When Phase 1 implementation begins, the comment
may be updated to reference ADR-0013 instead.  Aramis dependencies
must never be added to pyproject.toml or Bremen's site-packages.

## Rollback

Removing this ADR restores ADR-0002 prohibition to full force
for all concerns including process-isolated bundling.
```

### Step 2: Optionally update ROADMAP.md

If project convention requires roadmap gate registration, add a brief entry:

```
### PR0090 — ADR-0013 Aramis process-isolated runtime exception (governance)

Docks-only governance PR creating ADR-0013 to permit Docker-level,
process-isolated Aramis runtime bundling under strict boundary
conditions and a source-access gate. No runtime, source, or test
changes.

**Status**: Completed
```

### Step 3: Validate

Run all validation commands from section 9. Confirm:
- `docs/adr/0013-aramis-process-isolated-runtime-exception.md` exists with all required sections.
- No `src/`, `tests/`, Dockerfile, or `requirements.txt` files were modified.
- Safety greps show no unexpected matches.

### Step 4: Write implementation report

Create `.project-memory/pr/0090-aramis-subprocess-governance-gate/implementation-report.md` documenting:
- Files created/modified
- Validation results
- Final ADR content checksum

---

## 13. NEXT REQUIRED ACTION

Implementation agent (coder) should:

1. Create `docs/adr/0013-aramis-process-isolated-runtime-exception.md` with the structure specified above.
2. Optionally update `ROADMAP.md` with a brief PR0090 entry.
3. Run all validation commands from section 9.
4. Confirm no `src/`, `tests/`, Dockerfile, or `requirements.txt` changes.
5. Write `.project-memory/pr/0090-aramis-subprocess-governance-gate/implementation-report.md`.

**After this PR merges**, the next step is:
- Provide Aramis runtime source/bundle (official source tree, bundle, requirements, or CLI contract).
- Plan PR0091 (Phase 1 — Docker-level smoke proof) using the real Aramis evidence.

---

Implementation agent: coder
