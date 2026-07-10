# Plan: Process Guardrail For Implementation Reports And Gatekeeper Review

**PR**: process-implementation-report-gatekeeper  
**Role**: plan  
**Mode**: planning  
**Branch**: process-implementation-report-gatekeeper  
**HEAD**: 59a614be38d2d309b84b4b17620161926e1c98ab  
**PR sequence**: Process-only — does not consume the product roadmap PR number sequence  

---

## 1. Process Alignment

1. **This is a process guardrail PR.** It does not modify product/runtime
   behavior, source code, tests, docs, ADRs, config, Docker, infra, CI,
   dependencies, training, or agents.

2. **This does not consume PR0058.** The next product roadmap PR after
   PR0057 is still PR0058. This process PR reserves no PR number.

3. **This does not implement product/runtime changes.** No source files
   are touched. No tests are modified. No runtime behavior is changed.

4. **This does not choose Option A/B/C/D from PR0057.** The preprocessing
   source reconciliation decision is a separate human gate.

5. **This applies to all future PRs after merge** — both product PRs
   (PR0058+) and process PRs. Every implementation/coder task prompt
   must require writing an IMPLEMENTATION_REPORT.md.

---

## 2. Workflow Artifact Standard

Every PR must produce the following four artifacts, in order:

| Order | Artifact | Path | Written by | Purpose |
|-------|----------|------|-----------|---------|
| 1 | PLAN.md | `.project-memory/pr/{branch}/PLAN.md` | planner | Defines what must be done, allowed files, validation plan |
| 2 | plan-review.yml | `.project-memory/pr/{branch}/reviews/plan-review.yml` | plan-review | Verifies PLAN.md is safe, scoped, and implementable |
| 3 | IMPLEMENTATION_REPORT.md | `.project-memory/pr/{branch}/IMPLEMENTATION_REPORT.md` | coder | Reports what was actually done, deviations, validation results |
| 4 | precommit-review.yml | `.project-memory/pr/{branch}/reviews/precommit-review.yml` | precommit-review | Final gatekeeper — reconciles all three prior artifacts against actual diff and validation |

### 2.1 When IMPLEMENTATION_REPORT.md is required

Every implementation task prompt (coder role) must include a HARD RULE
stating: "Before the final action, write `.project-memory/pr/{branch}/IMPLEMENTATION_REPORT.md`
containing the required sections defined in the process guardrail."

For process-only PRs that do not change source/docs/tests (such as this PR
or a future documentation-only process PR), the IMPLEMENTATION_REPORT.md
is still recommended but may be omitted if the PR involves no file changes
other than process documentation under `.project-memory/`.

### 2.2 Relation to existing project_contract.yml

The existing `.project-memory/project_contract.yml` already defines:
- `agent_workflow.four_role_workflow: true`
- `agent_workflow.coder_changes_only: files explicitly approved by PLAN.md`
- `agent_workflow.precommit_review_writes_only: .project-memory/pr/<pr-id>/reviews/precommit-review.yml`

The IMPLEMENTATION_REPORT.md adds a required **self-report** step for the
coder between implementation and precommit-review. It does not change the
four-role workflow — it adds a required output artifact for the coder role.

---

## 3. Implementation Report Required Content

The IMPLEMENTATION_REPORT.md must contain the following sections. "none"
or "not applicable" must be written explicitly where relevant — not
omitted silently.

| # | Section | Required content |
|---|---------|-----------------|
| 1 | **Task Completed** | Exact TASK name from the coder prompt. |
| 2 | **Branch / PR** | Branch name and PR identifier. HEAD commit hash. |
| 3 | **Files Changed** | List of all files created, modified, or deleted. Include file paths relative to repo root. |
| 4 | **Implementation Summary** | Short paragraph describing what was implemented. What files were created and why. What files were modified and how. |
| 5 | **Key Decisions Made During Implementation** | Any decisions that were not specified in PLAN.md or plan-review.yml. Why a certain approach was chosen over alternatives. If no decisions were needed: "No decisions beyond PLAN.md specification." |
| 6 | **Deviations From PLAN.md** | Every difference between what PLAN.md specified and what was actually implemented. If zero deviations: "No deviations from PLAN.md." |
| 7 | **Warnings / Unresolved Questions** | Issues encountered that were not resolved. Any risk flags for the precommit-reviewer. If none: "None." |
| 8 | **Validation Commands and Results** | Every validation command run and its output. Must include compilation, test suite (specific to this PR), and safety checks. If a command had a non-zero exit code, report it — do not hide it. |
| 9 | **Safety Checks** | Specific safety checks run and results: secrets scan, forbidden patterns, boundary confirmations, clinical claims check. Confirmation that no AKIA, SECRET_ACCESS_KEY, dkr.ecr, full s3://, raw checksums, Nova_, /Users/, /home/ patterns were introduced. |
| 10 | **Boundaries Preserved** | Explicit confirmation that PLAN.md-allowed scope was not exceeded. That no source, tests, docs, ADRs, config, Docker, infra, CI, dependencies, training, or agents were changed unless explicitly allowed by PLAN.md. |
| 11 | **Commit Readiness** | Self-assessment: "ready for commit" or "blocked — requires correction." If blocked, list the blockers. |
| 12 | **Recommended Next Action** | Single recommendation: "proceed to precommit review" or description of what must be fixed first. |

---

## 4. Precommit Gatekeeper Standard

### 4.1 Required reads

The precommit-review agent must read the following before forming a verdict:

| # | Source | Purpose |
|---|--------|---------|
| 1 | `.project-memory/pr/{branch}/PLAN.md` | Understand what was planned, allowed scope, validation plan |
| 2 | `.project-memory/pr/{branch}/reviews/plan-review.yml` | Understand what the plan-reviewer approved, any blockers/warnings |
| 3 | `.project-memory/pr/{branch}/IMPLEMENTATION_REPORT.md` | Understand what the coder claims was done, validation results, deviations |
| 4 | `git status --short` | Verify working tree state vs claims |
| 5 | `git diff --name-only` | Verify actual changed files vs allowed scope vs IMPLEMENTATION_REPORT.md |
| 6 | Relevant changed files (read selected sections) | Verify implementation quality and correctness |
| 7 | Relevant unchanged boundary files | Verify that files outside allowed scope were not touched |
| 8 | Validation output | Run or verify validation commands from the plan, compare with coder's results |

### 4.2 Required comparisons

The precommit-review agent must compare and reconcile all of:

| # | Comparison | What to check |
|---|-----------|---------------|
| 1 | PLAN.md vs plan-review.yml | Was the plan approved? Are there any plan-review blockers that were not resolved? |
| 2 | PLAN.md vs IMPLEMENTATION_REPORT.md | Does the coder's work match what was planned? Are there undocumented deviations? |
| 3 | IMPLEMENTATION_REPORT.md vs actual git diff | Does the coder's file list match the actual diff? Are there changed files the coder did not report? |
| 4 | Claimed boundaries vs actual changed files | Did the coder change anything outside the PLAN.md-allowed scope? |
| 5 | Claimed validation vs actual validation | Did the coder run the right commands? Are the reported outputs credible? |
| 6 | Safety claims vs safety grep output | Does the coder's safety self-check match the actual grep results? |

### 4.3 Precommit-review.yml content

The precommit-review.yml artifact must include at least the following fields:

```yaml
# REVIEW ARTIFACT WRITTEN
# VERDICT
# BLOCKERS
# WARNINGS

# Planner summary — what did PLAN.md specify?
planner_summary:
  goal:
  allowed_scope:
  validation_plan:

# Plan-review summary — what did the plan-reviewer approve?
plan_review_summary:
  verdict:
  blockers:
  warnings:

# Implementation report summary — what did the coder claim?
implementation_report_summary:
  files_changed:
  deviations:
  validation_reported:

# Diff summary — what did git diff show?
diff_summary:
  files_changed:
  files_not_in_implementation_report:
  boundaries_violated:

# Validation — what validation was run and was it complete?
validation:
  compilation:
  test_suite:
  safety_checks:

# Safety checks
safety_checks:
  secrets:
  forbidden_patterns:
  clinical_claims:
  boundary_scope:

# Boundary checks
boundary_checks:
  plan_compliance:
  source_files_unchanged:
  docs_unchanged:
  adr_unchanged:
  config_docker_infra_ci_unchanged:
  agents_unchanged:

# Commit readiness — final gatekeeper assessment
commit_readiness:
  assessment:
  rationale:

# Final gatekeeper summary — one paragraph summarizing the full chain
final_gatekeeper_summary:
```

The `verdict` field must be one of: `pass`, `warning`, `block`.

---

## 5. Blocking Conditions

The precommit-review must return verdict `block` if any of the following
conditions are true:

| # | Condition | Rationale |
|---|-----------|-----------|
| 1 | IMPLEMENTATION_REPORT.md is missing for an implementation PR | No coder accountability. Cannot verify what was done. |
| 2 | Implementation report contradicts PLAN.md without documented deviation | Unknown scope creep or implementation drift. |
| 3 | Implementation report contradicts plan-review.yml | Precommit-review cannot reconcile incompatible reviews. |
| 4 | Implementation report claims different files than git diff shows | Fraud or accidental omission. Diff is the source of truth. |
| 5 | Implementation report omits validation results | Cannot verify the implementation works. |
| 6 | Implementation report omits safety checks | Cannot verify safety boundaries were preserved. |
| 7 | Coder claims a boundary was preserved but git diff shows otherwise | Boundary violation — files changed outside allowed scope. |
| 8 | Changed files exceed PLAN.md-allowed scope | Scope creep without plan approval. |
| 9 | Source/runtime files changed when plan prohibited them | Runtime behavior change without planning. |
| 10 | Tests were weakened or deleted to pass | Silent test coverage reduction. |
| 11 | Validation was filtered or hidden (tail/head on pytest output) | Protocol violation (AGENT_TEST_DEBUGGING_RULES.md Rule 4). |
| 12 | Safety claims are unsupported by evidence | Safety cannot be claimed without verification. |
| 13 | Final verdict is block but blockers list is empty | Logical inconsistency in the review artifact. |
| 14 | Blockers exist but verdict is approve/pass | Logical inconsistency — blockers must block. |

---

## 6. Precommit Review YAML Standard

The precommit-review.yml artifact must follow this schema:

```yaml
# Auto-generated by precommit-review agent

REVIEW ARTIFACT WRITTEN: "<ISO-8601 timestamp>"

verdict: pass | warning | block

blockers:
  - "Description of blocking condition"
  - ...

warnings:
  - "Description of non-blocking concern"
  - ...

planner_summary:
  goal: "One-line summary of what PLAN.md specified"
  allowed_scope: "List of allowed file paths or categories"
  validation_plan: "Summary of planned validation commands"

plan_review_summary:
  verdict: "approve | warning | block"
  blockers: "List from plan-review.yml"
  warnings: "List from plan-review.yml"

implementation_report_summary:
  files_changed: "List from coder's report"
  deviations: "List of deviations from PLAN.md, if any"
  validation_reported: "Summary of validation results claimed by coder"

diff_summary:
  files_changed: "List from git diff --name-only"
  files_not_in_implementation_report: "Files in git diff but not mentioned by coder"
  boundaries_violated: "Files outside PLAN.md-allowed scope"

validation:
  compilation: "pass | fail"
  test_suite: "pass | fail | partial — detail"
  safety_checks: "pass | fail | partial — detail"

safety_checks:
  secrets: "pass | fail — detail"
  forbidden_patterns: "pass | fail — detail"
  clinical_claims: "pass | fail — detail"
  boundary_scope: "pass | fail — detail"

boundary_checks:
  plan_compliance: "confirmed | not confirmed"
  source_files_unchanged: "confirmed | not confirmed"
  docs_unchanged: "confirmed | not confirmed — only if plan allowed changes"
  adr_unchanged: "confirmed | not confirmed"
  config_docker_infra_ci_unchanged: "confirmed | not confirmed"
  agents_unchanged: "confirmed | not confirmed"

commit_readiness:
  assessment: "ready for commit | requires correction"
  rationale: "One-paragraph explanation"

final_gatekeeper_summary:
  "One-paragraph summary of the full chain: planner -> plan-reviewer -> coder -> diff -> validation -> safety -> verdict."
```

---

## 7. File Change Plan

### 7.1 Implementation target

Create or update process documentation. The preferred target is a new
standalone process document to avoid bloating the existing
AGENT_TEST_DEBUGGING_RULES.md (which focuses on test debugging) or
TEST_DESIGN_STANDARD.md (which focuses on test design).

**Create**: `.project-memory/IMPLEMENTATION_REPORT_WORKFLOW.md`

This new document should contain:

1. **Purpose** — Formalize implementation reporting and precommit-review
   gatekeeper responsibilities.

2. **Scope** — Applies to all future PRs (product and process) after this
   PR is merged.

3. **Artifact Chain** — PLAN.md → plan-review.yml → IMPLEMENTATION_REPORT.md
   → precommit-review.yml. Each artifact's purpose, author, and timing.

4. **Implementation Report Requirements** — The 12 required sections
   defined in Section 3 of this plan.

5. **Precommit Gatekeeper Requirements** — Required reads, required
   comparisons, blocking conditions defined in Sections 4-5 of this plan.

6. **Precommit Review YAML Schema** — The field structure defined in
   Section 6 of this plan.

7. **Enforcement** — Coder prompts must include a HARD RULE requiring
   IMPLEMENTATION_REPORT.md. Precommit-review must block if it is missing.

### 7.2 Optional cross-references

Add a minimal reference to the new document from:

- `.project-memory/AGENT_TEST_DEBUGGING_RULES.md` — Add a sentence at the
  end: "For implementation reporting and precommit-review gatekeeper
  requirements, see `.project-memory/IMPLEMENTATION_REPORT_WORKFLOW.md`."

- `.project-memory/TEST_DESIGN_STANDARD.md` — Add a sentence at the end:
  "For the implementation report artifact required before precommit review,
  see `.project-memory/IMPLEMENTATION_REPORT_WORKFLOW.md`."

### 7.3 No test changes

No test file changes are needed for this process PR. The existing
`tests/test_bremen_test_policy.py` enforces test-design standards, not
process documentation standards. If a future PR adds a policy-enforcement
test for the IMPLEMENTATION_REPORT_WORKFLOW.md presence, that is a separate
scope.

### 7.4 No source, docs, ADR, config, Docker, infra, CI, dependency, training, or agent changes

Only `.project-memory/` files are modified.

---

## 8. Validation Plan

### 8.1 Pre-implementation validation

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
```

### 8.2 Post-implementation compilation

```bash
python -m compileall src tests
```

### 8.3 Post-implementation test suite

```bash
python -m pytest -q
```

### 8.4 Safety validation

```bash
# Confirm no unintended file changes
git diff --name-only

# Confirm no source/config/infra/doc/ADR changes
git diff --name-only -- src Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml src/bremen/training agents config docs docs/adr ROADMAP.md

# Confirm no binary artifacts
git diff --name-only | grep -E '\.(h5|hdf5|gfrm|GFRM|joblib|pkl|npy|npz|parquet|proto|pb|tfstate|tfstate\.backup)$' || true

# Confirm no secrets/identifiers in .project-memory changes
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|s3://\|sha256:\|Nova_\|/Users/\|/home/" -n .project-memory || true
```

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Implementation prompts for future PRs forget to include the IMPLEMENTATION_REPORT.md HARD RULE | Medium | Medium | The ORCHESTRATOR_STANDARD.txt references .project-memory/AGENT_STANDARD.txt (if it exists). Adding a requirement there is outside this plan's scope, but the new document serves as the authoritative reference. |
| Precommit-review agents in existing scripts do not follow the new workflow standard | Low | Medium | This PR documents the standard. Precommit-review prompts for PR0058+ must reference this standard. |
| The new document adds friction to simple process-only PRs | Low | Low | Section 2.1 allows omitting IMPLEMENTATION_REPORT.md for process-only PRs with no changed files. |

---

## 10. Implementation Order

1. Create `.project-memory/IMPLEMENTATION_REPORT_WORKFLOW.md`
2. (Optional) Add cross-reference to `.project-memory/AGENT_TEST_DEBUGGING_RULES.md`
3. (Optional) Add cross-reference to `.project-memory/TEST_DESIGN_STANDARD.md`
4. Run validation (Section 8)
5. Commit with message: `chore(process): add implementation report and precommit-review gatekeeper standard`

---

## 11. Non-Goals

1. No product/runtime implementation.
2. No PR0058 plan.
3. No Option A/B/C/D decision.
4. No source changes (`src/`).
5. No test changes (`tests/`).
6. No docs changes (`docs/`).
7. No ADR changes (`docs/adr/`).
8. No ROADMAP changes.
9. No config, Docker, infra, CI, dependency, training, or agent changes.
10. No clinical validation or diagnosis claims.
11. No replacement of MRI, biopsy, radiologist, clinician, or clinical judgment.

---

Implementation role: coder
