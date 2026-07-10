# Bremen Implementation Report And Precommit-Review Gatekeeper Workflow

**Process guardrail PR** — Does not consume the product roadmap PR
number sequence. Applies to all future implementation PRs after merge.

---

## 1. Purpose

This document formalizes the implementation report and precommit-review
gatekeeper workflow. It prevents loss of coder findings and makes
precommit-review the final gatekeeper by comparing planner intent,
plan-reviewer approval, coder implementation report, actual git diff,
validation output, and safety checks.

The precommit-review agent reconciles all of these sources before
issuing a commit-readiness verdict.

---

## 2. Scope

1. Applies to future implementation PRs after merge.
2. Applies to both product and process PRs when implementation changes
   are made.
3. Does not consume product PR numbering.
4. Does not change runtime/product behavior.
5. Does not choose PR0057 Option A/B/C/D.

---

## 3. Per-PR Artifact Chain

Every implementation PR must produce the following four artifacts, in
order:

| Order | Artifact | Path | Written by | Purpose |
|-------|----------|------|-----------|---------|
| 1 | PLAN.md | `.project-memory/pr/{branch}/PLAN.md` | planner | Defines what must be done, allowed files, validation plan |
| 2 | plan-review.yml | `.project-memory/pr/{branch}/reviews/plan-review.yml` | plan-review | Verifies PLAN.md is safe, scoped, and implementable |
| 3 | IMPLEMENTATION_REPORT.md | `.project-memory/pr/{branch}/IMPLEMENTATION_REPORT.md` | coder | Reports what was actually done, deviations, validation results |
| 4 | precommit-review.yml | `.project-memory/pr/{branch}/reviews/precommit-review.yml` | precommit-review | Final gatekeeper — reconciles all three prior artifacts against actual diff and validation |

IMPLEMENTATION_REPORT.md must be created by the coder before
precommit-review starts.

---

## 4. Implementation Report Requirement

Every coder implementation task prompt must include a HARD RULE
requiring the coder to write `.project-memory/pr/{branch}/IMPLEMENTATION_REPORT.md`
before completing the task.

For process-only PRs that do not change source, docs, or tests (such
as a documentation-only process PR), the implementation report is
still recommended but may be omitted if the PR involves no file changes
other than process documentation under `.project-memory/`.

### 4.1 When required

| PR type | IMPLEMENTATION_REPORT.md required? |
|---------|-----------------------------------|
| Product PR with implementation changes | **Yes — mandatory** |
| Process PR with implementation changes | **Yes — mandatory** |
| Process PR with no file changes outside `.project-memory/` | Recommended; may be omitted |

---

## 5. Implementation Report Required Fields

IMPLEMENTATION_REPORT.md must include the following sections. "none"
or "not applicable" must be written explicitly where relevant. Silent
omission is not allowed.

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

## 6. Precommit-Review Gatekeeper Responsibility

Precommit-review is the final commit gatekeeper. It is the last review
before a PR is committed.

### 6.1 Required reads

The precommit-review agent must read all of:

| # | Source | Purpose |
|---|--------|---------|
| 1 | `.project-memory/pr/{branch}/PLAN.md` | Understand planned scope and allowed files |
| 2 | `.project-memory/pr/{branch}/reviews/plan-review.yml` | Understand plan-review approval, blockers, warnings |
| 3 | `.project-memory/pr/{branch}/IMPLEMENTATION_REPORT.md` | Understand coder's claimed work and validation |
| 4 | `git status --short` | Verify working tree state |
| 5 | `git diff --name-only` | Verify actual changed files |
| 6 | Relevant changed files (selected sections) | Verify implementation quality |
| 7 | Relevant unchanged boundary files | Verify files outside scope were not touched |
| 8 | Validation output | Run or verify validation, compare with coder results |

### 6.2 Required comparisons

The precommit-review agent must compare and reconcile all of:

| # | Comparison | What to check |
|---|-----------|---------------|
| 1 | PLAN.md vs plan-review.yml | Was the plan approved? Are there unresolved blockers? |
| 2 | PLAN.md vs IMPLEMENTATION_REPORT.md | Does the coder's work match the plan? Undocumented deviations? |
| 3 | plan-review.yml vs IMPLEMENTATION_REPORT.md | Does the report address plan-review concerns? |
| 4 | IMPLEMENTATION_REPORT.md vs actual git diff | Does the coder's file list match the diff? Unreported changed files? |
| 5 | Claimed changed files vs actual changed files | Are all changes accounted for? |
| 6 | Claimed preserved boundaries vs actual changed files | Did the coder touch anything outside allowed scope? |
| 7 | Claimed validation vs actual validation | Right commands? Credible output? |
| 8 | Claimed safety checks vs safety grep output | Do grep results match coder claims? |

---

## 7. Required Precommit-Review Reads

As specified in Section 6.1, the precommit-review agent must read the
full artifact chain (PLAN.md, plan-review.yml, IMPLEMENTATION_REPORT.md)
plus git status, diff, changed files, and validation output.

The agent must not skip any of these reads. If a read is impossible
(e.g., IMPLEMENTATION_REPORT.md is missing), the agent must report a
blocker.

---

## 8. Required Reconciliation Checks

As specified in Section 6.2, the precommit-review agent must reconcile
the planner's intent, the plan-reviewer's approval, the coder's report,
the actual git diff, and the validation results.

The coder's claim of "no deviations" must be verified against the
actual diff. If the diff shows files outside the plan's allowed scope,
that is a blocker.

The coder's claim of "validation passed" must be verified. If commands
were filtered or hidden, that is a blocker per AGENT_TEST_DEBUGGING_RULES.md
Rule 4.

---

## 9. Blocking Conditions

Precommit-review must return verdict `block` if any of the following
are true:

| # | Condition | Rationale |
|---|-----------|-----------|
| 1 | IMPLEMENTATION_REPORT.md is missing for an implementation PR | No coder accountability. Cannot verify what was done. |
| 2 | Implementation report contradicts PLAN.md without documented deviation | Unknown scope creep or implementation drift. |
| 3 | Implementation report contradicts plan-review.yml | Precommit-review cannot reconcile incompatible reviews. |
| 4 | Implementation report contradicts actual git diff | Fraud or accidental omission. Diff is the source of truth. |
| 5 | Implementation report omits validation results | Cannot verify the implementation works. |
| 6 | Implementation report omits safety checks | Cannot verify safety boundaries were preserved. |
| 7 | Implementation report omits changed files | Cannot reconcile with git diff. |
| 8 | Implementation report omits deviations/warnings or fails to say "none" | Silent omission hides potential issues. |
| 9 | Coder claims a boundary was preserved but git diff shows otherwise | Boundary violation — files changed outside allowed scope. |
| 10 | Changed files exceed PLAN.md-allowed scope | Scope creep without plan approval. |
| 11 | Source/runtime files changed when plan prohibited them | Runtime behavior change without planning. |
| 12 | Tests were weakened, deleted, or assertions removed to pass | Silent test coverage reduction. |
| 13 | Validation output was hidden, filtered, or selectively summarized when full output was required | Protocol violation (AGENT_TEST_DEBUGGING_RULES.md Rule 4). |
| 14 | Final verdict/blocker consistency is invalid, including: verdict is block but blockers are empty; blockers exist but verdict is approve/pass | Logical inconsistency in the review artifact. |

---

## 10. precommit-review.yml Required Schema

The precommit-review.yml artifact must include at least the following
fields:

| Field | Required? | Description |
|-------|-----------|-------------|
| `verdict` | Yes | `pass`, `warning`, or `block` |
| `blockers` | Yes | List of blocking conditions; empty list if verdict is not block |
| `warnings` | Yes | List of non-blocking concerns |
| `planner_summary` | Yes | Summary of what PLAN.md specified (goal, allowed scope, validation plan) |
| `plan_review_summary` | Yes | Summary of plan-review approval (verdict, blockers, warnings) |
| `implementation_report_summary` | Yes | Summary of coder's report (files, deviations, validation) |
| `diff_summary` | Yes | Summary of actual git diff (files, unreported files, boundary violations) |
| `validation` | Yes | Compilation, test suite, and safety check results |
| `safety_checks` | Yes | Secrets, forbidden patterns, clinical claims, boundary scope results |
| `boundary_checks` | Yes | Confirmation that each boundary category (source, docs, ADRs, etc.) was preserved |
| `commit_readiness` | Yes | Final assessment and rationale |
| `final_gatekeeper_summary` | Yes | One paragraph describing the full chain: planner → plan-reviewer → coder implementation report → actual diff → validation → final verdict |

The `final_gatekeeper_summary` field must describe the complete chain:

> Planner defined the scope. Plan-reviewer approved it. Coder's
> implementation report described the work. Git diff confirmed the
> reported changes. Validation confirmed correctness. Safety checks
> confirmed boundaries. Final verdict: [pass/warning/block].

---

## 11. Validation and Safety Expectations

### 11.1 Implementation report validation

Implementation reports must include exact commands run and results.
Commands that failed must be reported — not hidden.

### 11.2 Precommit-review validation

Precommit-review should run required validation independently when the
prompt requires it. The agent must compare its own results against the
coder's reported results.

### 11.3 Filtered validation prohibition

Filtered validation (tail, head, grep on pytest output) is not allowed
when full/unfiltered validation was required.

### 11.4 Static negative assertions

Static negative assertions (e.g., tests that confirm forbidden patterns
are NOT present) and known historical references in prohibition context
may be classified as safe when appropriate.

---

## 12. How This Applies to PR0058+

1. PR0058 remains blocked until human Option A/B/C/D decision after
   PR0057. This workflow does not unblock PR0058.
2. Once PR0058 begins, its coder prompt must include a HARD RULE
   requiring IMPLEMENTATION_REPORT.md.
3. Its precommit-review prompt must read and compare the implementation
   report before issuing a commit-readiness verdict.
4. All subsequent PRs (PR0059, PR0060, etc.) must follow the same
   artifact chain.

---

## 13. Non-Goals

1. No product/runtime implementation.
2. No PR0058 plan.
3. No Option A/B/C/D decision from PR0057.
4. No source changes (`src/`).
5. No runtime request schema changes.
6. No tests weakening or deletion.
7. No docs/product contract changes.
8. No ADR changes.
9. No ROADMAP changes.
10. No dependency changes.
11. No agent template changes.
12. No real data artifacts.
13. No clinical validation or diagnosis claims.
14. No replacement of MRI, biopsy, radiologist, clinician, or clinical
    judgment.
