# Roadmap Drift Audit — After PR0049 and Process Guardrail Merge

**Date**: 2026-07-08
**Branch**: `roadmap-drift-audit-after-pr0049`
**HEAD**: `0c2b5881c7558e6adf6e626fdb44418422be8aba`

**Recent merges (in order)**:
1. `078a74c` — PR0048: HTTP explicit-ref wiring
2. `9f99969` — PR0049 Plan: production E2E smoke hardening
3. `a940f5d` — PR0049 Implementation: smoke test + runbook
4. `7663450` — Merge PR0049 into main
5. `f3e9d4e` — Process agent loop guardrails (AGENT_TEST_DEBUGGING_RULES.md, TEST_DESIGN_STANDARD.md, test_bremen_test_policy.py)
6. `0c2b588` — Merge process guardrails into main

---

## ROADMAP DRIFT VERDICT: minor_drift

ROADMAP.md is largely correct after PR0049 and the process guardrail merge. The roadmap structure, next sequence (PR0050–PR0054), H5 layout strategy, architectural decisions, and decision gates are all preserved and accurate. However, three completed PRs (PR0047, PR0048, PR0049) are still presented as future work instead of completed work. This is a cosmetic/naming drift, not a structural one — the next actionable step (PR0050) remains correct.

---

## CURRENT STATE CHECK

### Question 1: Does ROADMAP.md record completed work through PR0049?

**Answer**: Partially. Completed foundation PRs lists PR-0001 through PR0045. PR0047, PR0048, PR0049 are **absent** from the completed list. They appear only in the Next Execution Sequence as future work.

- `Completed foundation PRs` section (lines 7–45): Stops at `PR0045 — H5 layout adapter boundary`
- `Current state through PR0045` section (lines 46–57): Section header literally anchors at PR0045, states "Calibration sample preprocessing is not yet implemented (scheduled PR0047)"
- `Next Execution Sequence (post-PR0045)` section (lines 168–179): PR0047, PR0048, PR0049 listed as future entries

**Evidence**:
```
# ROADMAP.md line 46:
## Current state through PR0045

# ROADMAP.md line 57:
Calibration sample preprocessing is not yet implemented (scheduled PR0047).

# ROADMAP.md lines 172-174:
| **PR0047** | Calibration sample preprocessing bridge | ...
| **PR0048** | HTTP prediction explicit-ref wiring | ...
| **PR0049** | Production end-to-end smoke hardening | ...
```

### Question 2: Does ROADMAP.md record that production E2E smoke hardening is completed?

**Answer**: No. PR0049 is listed in the Next Execution Sequence as future work (line 174). It is not mentioned in the completed section.

### Question 3: Does ROADMAP.md avoid presenting PR0049 as future work?

**Answer**: No. It presents PR0049 as a future task.

### Questions 4–9: Next execution sequence (PR0050–PR0054)

| Question | Answer |
|----------|--------|
| 4. Preserves next execution sequence starting with PR0050? | **Yes** — PR0050 is the next uncompleted entry in the sequence |
| 5. Still lists PR0050 as model/version readiness endpoint cleanup? | **Yes** — line 175 |
| 6. Still lists PR0051 as config governance ADR/gates? | **Yes** — line 176 |
| 7. Still lists PR0052 as Matador boundary? | **Yes** — line 177 |
| 8. Still lists PR0053 as decision-support report? | **Yes** — line 178 |
| 9. Still lists PR0054 as release readiness? | **Yes** — line 179 |

### Question 10: Mentions/preserves H5 layout strategy?

**Answer**: Yes. The full H5 Layout Strategy section exists at lines 198–227 with adapter inventory and core principles.

### Question 11: Mentions production smoke hardening or needs update?

**Answer**: Mentions it as future work (line 174). Needs update to record it as completed.

### Question 12: Incorrectly consumes a roadmap number for process loop guard work?

**Answer**: No. The process guardrail merge (`f3e9d4e`) changed only `.project-memory/AGENT_TEST_DEBUGGING_RULES.md`, `.project-memory/TEST_DESIGN_STANDARD.md`, and `tests/test_bremen_test_policy.py`. It did NOT touch ROADMAP.md and did NOT consume a PR number. The commit message says "chore(project): add agent loop guardrails" — not a product or platform readiness PR.

---

## NEXT SEQUENCE CHECK

The next uncompleted roadmap entry after PR0049 is **PR0050 — Model/version readiness endpoint cleanup** (line 175). Its description: "Align `/model/version` `model_status` with actual `model_ready` state. Preserve safe metadata only."

PR0050 is the correct next step. No sequence reordering is needed.

---

## FASTAPI DEFERRAL CHECK

**Passed**. FastAPI is not mentioned anywhere in ROADMAP.md. No FastAPI, uvicorn, starlette, or ASGI references appear in the roadmap, the next execution sequence, or any architectural section. FastAPI deferral is preserved both in the roadmap and in all merged PRs.

---

## PROCESS GUARDRAIL CHECK

### What was merged

The process-only guardrail branch (`process-agent-loop-guard`) added three files:

| File | Purpose |
|------|---------|
| `.project-memory/AGENT_TEST_DEBUGGING_RULES.md` (extended) | Added 3 new rules: Rule 6 (no regex mass rewrites), Rule 7 (no sleep/retry loops), Rule 8 (no deleting assertions) — plus elevated protocol-violation stop-and-report to its own section |
| `.project-memory/TEST_DESIGN_STANDARD.md` | 7 rules governing test design: in-process smoke tests, dedicated server tests only for server patterns, prefer direct handler calls, prefer monkeypatch over server fixtures, one file one pattern, synthetic model loading in smoke, policy enforcement in test_bremen_test_policy.py |
| `tests/test_bremen_test_policy.py` | Policy enforcement tests: AST-based checks that `test_bremen_production_smoke.py` does not import or use server/network patterns (HTTPServer, threading, socket, etc.), checks docstring declares in-process pattern, verifies TEST_DESIGN_STANDARD.md and AGENT_TEST_DEBUGGING_RULES.md have required sections |

### Impact on roadmap

**None**. These are process-only artifacts. They do not consume a roadmap number, do not appear in the Next Execution Sequence, and do not affect the product or platform readiness tracks. ROADMAP.md correctly does not reference them — process guardrails are project-memory governance, not roadmap items.

### The production smoke test design deviation

The implemented `test_bremen_production_smoke.py` uses **in-process** handler calls (calling `handle_submit_prediction` and `handle_get_prediction` directly) instead of the HTTP server pattern originally planned in PR0049 PLAN.md. This is correct per `TEST_DESIGN_STANDARD.md` Rule 1 ("Production-like smoke tests must be in-process"). The test also monkeypatches `run_inference` to avoid `ModelState` global state sensitivity — an implementation adjustment documented implicitly in the test code.

This deviation is not a roadmap concern. The test exists and works. No roadmap update is needed for this.

---

## DECISION AND GATE CHECK

| Gate | Status in ROADMAP.md | Actual status | Match? |
|------|---------------------|---------------|--------|
| G-API-1 (async submit-poll) | DECIDED | DECIDED | ✓ |
| G-API-2 (ECS Fargate / App Runner) | DECIDED | DECIDED | ✓ |
| G-INFRA-1 (Terraform) | DECIDED | DECIDED | ✓ |
| G-CFG-1 (build vs. adopt) | OPEN | OPEN | ✓ |
| G-CFG-2 (state history store) | OPEN | OPEN | ✓ |
| G-CFG-3 (validation schema) | OPEN | OPEN | ✓ |
| G-DEP-1 (container dependency pin) | OPEN | OPEN | ✓ |

| Architecture | Status in ROADMAP.md | Actual | Match? |
|-------------|---------------------|--------|--------|
| App Runner near-term proving target | Preserved (line 115) | Active | ✓ |
| ECS Fargate long-term primary target | Preserved (line 116) | Planned | ✓ |
| APRANA retired | Preserved (line 118) | Retired | ✓ |
| Model binding lifecycle (startup load, no hot-swap) | Preserved (lines 120–128) | Active | ✓ |

All gates and decisions match current reality.

---

## DRIFT ITEMS

### Drift 1 (minor): Completed PRs in future section

**Location**: ROADMAP.md lines 168–174 (Next Execution Sequence)
**Problem**: PR0047, PR0048, PR0049 are completed but appear in the "Next Execution Sequence (post-PR0045)" section as future work.
**Impact**: An agent or developer reading the roadmap may believe PR0047–PR0049 still need implementation. This could cause duplicate work or confusion about current capability.
**Fix needed**: Move PR0047–PR0049 to the "Completed foundation PRs" section and update the "Current state through PR0045" section header and content.

### Drift 2 (cosmetic): "Current state through PR0045" header is stale

**Location**: ROADMAP.md line 46
**Problem**: The section header literally says "Current state through PR0045", implying the roadmap has not been updated since PR0045.
**Fix needed**: Change header to "Current state through PR0049" and update the bullet list to reflect:
- Calibration sample preprocessing is implemented (PR0047)
- Explicit target/control refs are wired through HTTP predictions (PR0048)
- Production E2E smoke hardening exists (runbook + synthetic test) (PR0049)

### Drift 3 (cosmetic): Stale note about calibration preprocessing

**Location**: ROADMAP.md line 57
**Problem**: States "Calibration sample preprocessing is not yet implemented (scheduled PR0047)." PR0047 is complete.
**Fix needed**: Remove or update this line as part of the current state refresh.

### Drift 4 (cosmetic): Process guardrails not mentioned

**Location**: ROADMAP.md — no reference to agent loop guardrails or test design standards
**Problem**: The AGENT_TEST_DEBUGGING_RULES.md was significantly extended, TEST_DESIGN_STANDARD.md was created, and test_bremen_test_policy.py was added. An operator or agent onboarding via ROADMAP.md would not know these process constraints exist.
**Fix needed**: Optionally add a brief mention in the "Completed foundation PRs" section or in a new "Process guardrails" section. This is not a numeric PR — it's process-only work. Minimal fix: a single bullet at the end of Completed foundation PRs like "Process guardrails — AGENT_TEST_DEBUGGING_RULES.md extended, TEST_DESIGN_STANDARD.md added, test policy tests created. Process-only; no product/PR number."

### Non-drift confirmations

The following are **not** drift — they are correctly preserved and accurate:
- All decision gates (G-API-1/2, G-INFRA-1, G-CFG-1/2/3, G-DEP-1)
- All architectural decisions (App Runner, ECS Fargate, APRANA retired, model lifecycle)
- H5 layout strategy (adapter protocol, adapter inventory, explicit ref requirement, no auto-selection)
- Training Pipeline Track (completed)
- FastAPI deferral
- No duplicate or conflicting PR numbers
- No roadmap number consumed by process guardrail work

---

## RECOMMENDED NEXT ACTION

**Recommended next action**: Correct the minor roadmap drift before starting PR0050.

The smallest correct action is a **docs-only ROADMAP.md update** that:

1. **Add PR0047, PR0048, PR0049 to the Completed foundation PRs section** with their descriptions:
   - `PR0047 — Calibration sample preprocessing bridge`
   - `PR0048 — HTTP prediction explicit-ref wiring`
   - `PR0049 — Production end-to-end smoke hardening`

2. **Update "Current state through PR0045" to "Current state through PR0049"** and refresh the bullet list:
   - Add: "Calibration sample preprocessing is implemented (PR0047)"
   - Add: "Explicit target/control refs are wired through HTTP predictions (PR0048)"
   - Add: "Production end-to-end smoke hardening exists — operator runbook (`docs/production_e2e_smoke.md`) and synthetic production-like test (`tests/test_bremen_production_smoke.py`) (PR0049)"
   - Remove or update: "Calibration sample preprocessing is not yet implemented (scheduled PR0047)"

3. **Optionally add a single line** to Completed foundation PRs noting the process guardrail work:
   - `Process guardrails — Extended AGENT_TEST_DEBUGGING_RULES.md, added TEST_DESIGN_STANDARD.md, added test_bremen_test_policy.py. Process-only; no roadmap number consumed.`

4. **Do NOT change** the Next Execution Sequence section — leave PR0050–PR0054 as-is. The sequence is correct; PR0050 is the next step.

### If the drift correction is made first:

**Next PR**: `PR0050 — Model/version readiness endpoint cleanup`
**PR number**: 0050 (available — no conflict)
**Implementation scope**: Align `/model/version` `model_status` with actual `model_ready` state. Preserve safe metadata only. No inference, preprocessing, staging, or schema changes.

### If the drift correction is skipped and PR0050 is started immediately:

The next agent would likely work on the correct code (PR0050) because the Next Execution Sequence clearly shows PR0050 next. However, the agent might also:
- Get confused about whether PR0047–PR0049 are actually done
- Try to re-implement something already completed
- Miss the fact that production smoke hardening exists

**Risk without correction**: Low to medium. The Next Execution Sequence section clearly labels PR0050 as the next uncompleted item. But the "Current state through PR0045" header is misleading and could cause confusion.

**Recommendation**:
1. **Correct the roadmap** (this is a 5-minute docs-only task) as the next action.
2. **Then start PR0050** model/version readiness endpoint cleanup.

This ensures the roadmap is truth before the next code PR, which prevents agent confusion and duplicate work.

---

## VALIDATION RUN

```bash
# 1. Working tree — must show only the audit artifact
git diff --name-only

# 2. Evidence: roadmap tokens
grep -n "PR0049\|PR0050\|FastAPI\|App Runner\|ECS Fargate\|APRANA\|G-CFG" ROADMAP.md

# 3. Evidence: production smoke and readiness tokens
grep -n "production E2E smoke\|production smoke\|model/version\|readiness" ROADMAP.md

# 4. Evidence: recent merge sequence
git log --oneline -10

# 5. No pytest required — this is a documentation audit only
```

---

## BOUNDARY CONFIRMATIONS

| File/Directory | Changed in this audit? | Rationale |
|---------------|----------------------|-----------|
| `.project-memory/audits/roadmap-drift-after-pr0049.md` | **YES** — new | Audit artifact |
| `ROADMAP.md` | **NO** | Read-only — audit forbids editing |
| `src/**` | **NO** | Forbidden |
| `tests/**` | **NO** | Forbidden — read-only for evidence |
| `docs/**` | **NO** | Forbidden — read-only for evidence |
| `docs/adr/**` | **NO** | Forbidden |
| `docs/architecture.md` | **NO** | Forbidden |
| `.project-memory/**` (except audit artifact) | **NO** | Read-only |
| Any other file | **NO** | Forbidden |

---

## SUMMARY

| Metric | Value |
|--------|-------|
| Drift classification | minor_drift |
| Drift items found | 4 (2 minor structural, 2 cosmetic) |
| Non-drift confirmations | 16 (all correct) |
| Roadmap next step accuracy | Correct — PR0050 is next |
| FastAPI deferral | Preserved |
| Process guardrails roadmap impact | None — process-only, no number consumed |
| Recommended action | Correct roadmap drift (docs-only), then start PR0050 |

TASK COMPLETE

BLOCKERS: none

WARNINGS:
1. The "Current state through PR0045" section header is misleading — it implies no progress since PR0045 even though PR0047, PR0048, and PR0049 are all merged.
2. The production smoke test (test_bremen_production_smoke.py) uses in-process handler calls with monkeypatched run_inference, which differs from the original PR0049 PLAN.md that described HTTP server round-trips. This deviation was caused by TEST_DESIGN_STANDARD.md Rule 1 (smoke tests must be in-process) and is correct, but a future reader comparing PLAN.md to implementation may be confused.
3. Process guardrail files (TEST_DESIGN_STANDARD.md, test_bremen_test_policy.py) are not referenced in ROADMAP.md. Consider adding a single notification bullet to Completed foundation PRs.

FILES CHANGED:
- `.project-memory/audits/roadmap-drift-after-pr0049.md` — written

ROADMAP DRIFT VERDICT: minor_drift

CURRENT STATE CHECK: Partially — 16 of 20 audit questions pass. PR0047/PR0048/PR0049 absent from completed list, present only as future work.

NEXT SEQUENCE CHECK: Correct — PR0050 (model/version readiness endpoint cleanup) is the next step.

FASTAPI DEFERRAL CHECK: Passed — no FastAPI references in ROADMAP.md.

PROCESS GUARDRAIL CHECK: Process guardrails merged without consuming a roadmap number. No roadmap impact.

DECISION AND GATE CHECK: All 7 gates and 4 architectural decisions match current reality.

DRIFT ITEMS: 4 items — 1 minor (completed PRs in future section), 3 cosmetic (stale header, stale calibration note, process guardrails unmentioned).

RECOMMENDED NEXT ACTION: Correct minor roadmap drift (docs-only), then start PR0050 model/version readiness endpoint cleanup.

VALIDATION RUN: See Section above.

BOUNDARY CONFIRMATIONS: Only audit artifact changed. All other files read-only.

Recommended next action: Correct minor roadmap drift (add PR0047–PR0049 to completed, update current state section) as a docs-only PR, then proceed with PR0050 model/version readiness endpoint cleanup.
