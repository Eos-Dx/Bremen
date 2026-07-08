# PR — Roadmap Correction After PR0049

## 1. Title / Branch / Objective

- **Title**: Roadmap Correction After PR0049
- **Branch**: `roadmap-correction-after-pr0049`
- **Objective**: Apply the minimal docs-only ROADMAP.md correction identified by the drift audit. Record PR0047, PR0048, and PR0049 as completed work. Update the "Current state through PR0045" section to "Current state through PR0049". Remove PR0047–PR0049 from the Next Execution Sequence, confirming PR0050 model/version readiness endpoint cleanup as the next code step. Keep process guardrails as process-only work — no roadmap PR number consumed. No source, test, ADR, infra, Docker, or dependency changes.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
ae3655b47cef88563ba063e8fc4ee9a315142298

$ git branch --show-current
roadmap-correction-after-pr0049

$ git status --short
(clean — no uncommitted changes)
```

All required files read. Drift audit (`roadmap-drift-after-pr0049.md`) and its review (`roadmap-drift-after-pr0049-review.yml`) both confirm minor_drift with a single actionable recommendation: docs-only ROADMAP.md correction.

---

## 3. Drift Summary

**Verdict from drift audit**: minor_drift

**Drift items found**:

| # | Severity | Description | Location in ROADMAP.md |
|---|----------|-------------|------------------------|
| 1 | Minor structural | PR0047, PR0048, PR0049 completed but absent from Completed foundation PRs list | Lines 7–44: list stops at PR0045 |
| 2 | Cosmetic | "Current state through PR0045" header is stale | Line 46: `## Current state through PR0045` |
| 3 | Cosmetic | "Calibration sample preprocessing is not yet implemented (scheduled PR0047)" — PR0047 is done | Line 57: stale bullet |
| 4 | Cosmetic | PR0047–PR0049 appear as future work in Next Execution Sequence | Lines 172–174: table entries |
| 5 | Cosmetic | Process guardrails not referenced anywhere in ROADMAP.md | No location — absent entirely |

**Non-drift confirmations (16 items)**: All decision gates, architectural decisions, H5 layout strategy, training pipeline completion, FastAPI deferral, PR0050 next-step accuracy, no duplicate/conflicting PR numbers, no roadmap number consumed by process guardrail work — all correct.

---

## 4. ROADMAP Anchors

The implementation agent must verify these anchors by running `grep -n` before editing, because line numbers may shift after branch updates or intermediate merges.

### Anchor A — Completed foundation PRs insertion point

| Attribute | Value |
|-----------|-------|
| Audit line reference | Lines 7–45 |
| Current state | Lists PR-0001 through PR0045 |
| Insertion anchor | After line 45 (`PR0045 — H5 layout adapter boundary...`) |
| Verify with | `grep -n "PR0045.*layout adapter" ROADMAP.md` |
| Action | Add three new bullets after PR0045: PR0047, PR0048, PR0049 |

### Anchor B — Current state section header

| Attribute | Value |
|-----------|-------|
| Audit line reference | Line 46 |
| Current text | `## Current state through PR0045` |
| Verify with | `grep -n "Current state through" ROADMAP.md` |
| Action | Change to `## Current state through PR0049` |

### Anchor C — Current state calibration preprocessing note

| Attribute | Value |
|-----------|-------|
| Audit line reference | Line 57 |
| Current text | `- Calibration sample preprocessing is not yet implemented (scheduled PR0047).` |
| Verify with | `grep -n "Calibration sample preprocessing\|not yet implemented" ROADMAP.md` |
| Action | Replace with `- Calibration sample preprocessing bridge exists (PR0047).` |

### Anchor D — Current state bullet additions

| Attribute | Value |
|-----------|-------|
| Audit line reference | Lines 46–57 |
| Action | Insert after line 57 (after existing bullet list): |
| | `- Explicit target/control H5 refs are wired through HTTP predictions (PR0048).` |
| | `- Production E2E smoke hardening exists (operator runbook + synthetic automated test) (PR0049).` |
| | `- Agent loop guardrails exist as process-only project hygiene.` |

### Anchor E — Next Execution Sequence PR0047–PR0049 removal

| Attribute | Value |
|-----------|-------|
| Audit line reference | Lines 172–174 |
| Current text | Three table rows for PR0047, PR0048, PR0049 |
| Verify with | `grep -n "| \*\*PR004[789]\*\*" ROADMAP.md` |
| Action | Delete lines 172–174 (the three PR0047–PR0049 rows) |
| | Verify section header remains `## Next Execution Sequence (post-PR0045)` |
| | Verify PR0050–PR0054 rows remain at correct line positions |

### Anchor F — Process guardrails mention (optional)

| Attribute | Value |
|-----------|-------|
| Location | After Completed foundation PRs list, after new PR0049 bullet |
| Action | Optionally add: |
| | `- Process guardrails — AGENT_TEST_DEBUGGING_RULES.md extended, TEST_DESIGN_STANDARD.md added, test_bremen_test_policy.py created. Process-only; no roadmap number consumed.` |

### Anchor G — H5 Layout Strategy stale PR0047 references

| Attribute | Value |
|-----------|-------|
| Audit line reference | Lines 212, 227 |
| Current text | `Preprocessing is PR0047 scope` / `preprocessing in PR0047` |
| Action | No action required — these are cross-references to the PR that *added* the feature, not a claim that it's future work. The context of these lines is the adapter inventory table, which correctly documents that calibration preprocessing was introduced by PR0047. After PR0047 is recorded as completed in the Foundation section, these references are accurate historical notes. |
| Verification | `grep -n "PR0047" ROADMAP.md` — should show references in H5 Layout Strategy section that are legitimate cross-references, not future-work claims |

---

## 5. ROADMAP Correction Plan

### Files to modify

| File | Action | Rationale |
|------|--------|-----------|
| `ROADMAP.md` | **Edit** | Apply all anchor changes from Section 4 |

### Files to NOT modify

| File | Action | Rationale |
|------|--------|-----------|
| `src/**` | Forbidden | No source changes |
| `tests/**` | Forbidden | No test changes |
| `docs/**` | Forbidden | No doc changes |
| `docs/adr/**` | Forbidden | No ADR changes |
| `docs/architecture.md` | Forbidden | No architecture doc changes |
| `Dockerfile` | Forbidden | No Docker changes |
| `Dockerfile.training` | Forbidden | No training Docker changes |
| `infra/**` | Forbidden | No infra changes |
| `.github/**` | Forbidden | No CI/CD changes |
| `requirements.txt` | Forbidden | No dependency changes |
| `pyproject.toml` | Forbidden | No project config changes |
| `src/bremen/training/**` | Forbidden | No training pipeline changes |
| `.project-memory/**` (except review artifact) | Forbidden | No project-memory changes |

---

## 6. Completed Work Update Plan

### 6.1 Add PR0047, PR0048, PR0049 to Completed foundation PRs

Insert after the PR0045 bullet (Anchor A). Use exact descriptions from the Next Execution Sequence table:

```markdown
- PR0047 — Calibration sample preprocessing bridge. Map calibration sample layout into runtime preprocessing without changing inference math. Use explicit target/control sample refs. Read integration i/q arrays safely. Produce the existing 15-feature v0.1 schema. No clinical claims.
- PR0048 — HTTP prediction explicit-ref wiring. Ensure `target_scan_ref` / `control_scan_ref` are carried through HTTP → staging → preflight/layout context → preprocessing/inference. Production smoke with explicit refs.
- PR0049 — Production end-to-end smoke hardening. S3 H5 → explicit sample refs → checksum → layout adapter → preprocessing → inference → completed job/result. Document expected failures and safe errors.
```

### 6.2 Optionally add process guardrails bullet

```markdown
- Process guardrails — AGENT_TEST_DEBUGGING_RULES.md extended, TEST_DESIGN_STANDARD.md added, test_bremen_test_policy.py created. Process-only; no roadmap number consumed.
```

**Decision**: Add this bullet. It is a single line at the end of the Completed foundation PRs list. It prevents future confusion about whether the guardrail work belongs in the numbered roadmap sequence.

### 6.3 Verification after insertion

```bash
grep -n "PR0047\|PR0048\|PR0049\|Process guardrails" ROADMAP.md
```

Expected output:
- PR0047 appears in Completed foundation PRs section AND in H5 Layout Strategy cross-references (2+ occurrences)
- PR0048 appears in Completed foundation PRs section (1+ occurrence)
- PR0049 appears in Completed foundation PRs section (1+ occurrence)
- "Process guardrails" appears once at end of Completed foundation PRs
- PR0047, PR0048, PR0049 do NOT appear in the Next Execution Sequence table

---

## 7. Current State Update Plan

### 7.1 Update section header

Change line 46 from:
```
## Current state through PR0045
```
to:
```
## Current state through PR0049
```

### 7.2 Update stale calibration bullet

Change line 57 from:
```
- Calibration sample preprocessing is not yet implemented (scheduled PR0047).
```
to:
```
- Calibration sample preprocessing bridge exists (PR0047).
```

### 7.3 Add new state bullets

Insert after the modified line 57 (after the existing bullet list ends). The full updated Current State section should read:

```markdown
## Current state through PR0049

- Runtime service exists and is operational on App Runner.
- Runtime model is loaded at startup from a checksum-verified model package (S3 staging + joblib).
- App Runner proving path is operational (S3 staging, inference, prediction jobs).
- S3 model startup staging works (container start → S3 fetch → checksum → joblib.load).
- S3 H5 input staging works (`h5_uri` accepted, downloaded, checksum verified, staged locally).
- Prediction job execution is wired (submit → validate → stage → preflight → bridge → inference → completed/failed).
- H5 metadata fallback is implemented (primary `/patient/id`, fallback sample-level `patient_name` with source tracking).
- H5 layout adapter boundary exists (abstract adapter protocol, detect/resolve, Canonical + CalibrationSample adapters, layout registry).
- Calibration sample preprocessing bridge exists (PR0047).
- Explicit target/control H5 refs are wired through HTTP predictions (PR0048).
- Production E2E smoke hardening exists (operator runbook + synthetic automated test) (PR0049).
- Agent loop guardrails exist as process-only project hygiene.
- FastAPI remains deferred.
```

**Note**: The last two bullets ("Agent loop guardrails exist..." and "FastAPI remains deferred") are new additions not present in the original "through PR0045" section. They accurately reflect current project state.

### 7.4 Verification after changes

```bash
grep -n "Current state through" ROADMAP.md
# Must show "Current state through PR0049"

grep -n "not yet implemented" ROADMAP.md || echo "clean — no stale not-yet-implemented claims"
# Must output "clean — ..."

grep -c "Explicit target/control H5 refs are wired\|Production E2E smoke hardening exists" ROADMAP.md
# Must output >= 1
```

---

## 8. Next Sequence Update Plan

### 8.1 Remove PR0047–PR0049 rows from Next Execution Sequence table

Delete three table rows. The Next Execution Sequence table currently reads (lines 168–179):

```markdown
## Next Execution Sequence (post-PR0045)

| PR | Title | Description |
|----|-------|-------------|
| **PR0047** | Calibration sample preprocessing bridge | ... |        ← DELETE
| **PR0048** | HTTP prediction explicit-ref wiring | ... |             ← DELETE
| **PR0049** | Production end-to-end smoke hardening | ... |            ← DELETE
| **PR0050** | Model/version readiness endpoint cleanup | ... |
| **PR0051** | Config governance ADR/gates | ... |
| **PR0052** | Matador boundary / system-of-record adapter skeleton | ... |
| **PR0053** | Decision-support report/output wrapper | ... |
| **PR0054** | Release readiness / operator notes | ... |
```

After deletion, the table should start directly at PR0050:

```markdown
## Next Execution Sequence (post-PR0049)

| PR | Title | Description |
|----|-------|-------------|
| **PR0050** | Model/version readiness endpoint cleanup | Align `/model/version` `model_status` with actual `model_ready` state. Preserve safe metadata only. |
| **PR0051** | Config governance ADR/gates | Close G-CFG-1/G-CFG-2/G-CFG-3 or explicitly defer with rationale. Config audit/history architecture only, no UI unless separately planned. |
| **PR0052** | Matador boundary / system-of-record adapter skeleton | Contract only, no local path dependency, no raw patient data logging. |
| **PR0053** | Decision-support report/output wrapper | Controlled output around prediction result. No diagnosis, no clinical validation claim. |
| **PR0054** | Release readiness / operator notes | Production checklist, rollback, smoke commands, model artifact notes. |
```

**Important**: Update the section header from `(post-PR0045)` to `(post-PR0049)` to match the new current state anchor.

### 8.2 Verification after deletion

```bash
grep -n "PR0047\|PR0048\|PR0049" ROADMAP.md
# PR0047, PR0048, PR0049 must NOT appear in Next Execution Sequence section
# They SHOULD appear only in Completed foundation PRs and H5 Layout Strategy cross-references

grep -A 8 "Next Execution Sequence" ROADMAP.md | head -10
# First item must be PR0050
```

---

## 9. Preserved Decisions

The following must remain **unchanged** in ROADMAP.md. The implementation agent must not edit them:

| Decision | Location in ROADMAP.md | Status |
|----------|------------------------|--------|
| App Runner near-term proving/testing target | Line 115 | Preserved |
| ECS Fargate long-term primary production target | Line 116 | Preserved |
| APRANA retired | Line 118 | Preserved |
| No model in Docker image | Lines 120–128 | Preserved |
| Startup load only | Lines 120–128 | Preserved |
| Checksum before joblib.load | Lines 120–128 | Preserved |
| No hot-swap | Lines 120–128 | Preserved |
| No per-request model loading | Lines 120–128 | Preserved |
| G-API-1 DECIDED (async submit-poll) | Decision Gate Register | Preserved |
| G-API-2 DECIDED (ECS Fargate/App Runner) | Decision Gate Register | Preserved |
| G-INFRA-1 DECIDED (Terraform) | Decision Gate Register | Preserved |
| G-CFG-1 OPEN (build vs. adopt config) | Decision Gate Register | Preserved |
| G-CFG-2 OPEN (DynamoDB vs. other) | Decision Gate Register | Preserved |
| G-CFG-3 OPEN (validation schema) | Decision Gate Register | Preserved |
| G-DEP-1 OPEN (container dependency pin) | Decision Gate Register | Preserved |
| FastAPI deferred | No explicit line — deferral preserved by not introducing it | Preserved |
| H5 Layout Strategy (adapter protocol, adapter inventory, explicit refs, no auto-selection) | Lines 198–227 | Preserved |

Verify with:
```bash
grep -n "App Runner.*near-term\|ECS Fargate.*long-term\|APRANA\|G-CFG-1.*OPEN\|G-API-1.*DECIDED\|H5 layout" ROADMAP.md
```

---

## 10. Validation Plan

The implementation agent must run these validation commands after editing ROADMAP.md:

```bash
# 1. Verify working tree is clean of unexpected changes
git diff --name-only
# Must show only: ROADMAP.md

# 2. Verify only ROADMAP.md changed
git diff --name-only -- src/ tests/ docs/ docs/adr/ docs/architecture.md \
  Dockerfile Dockerfile.training infra/ .github/ requirements.txt pyproject.toml \
  src/bremen/training/
# Must output nothing (empty)

# 3. Verify PR0047, PR0048, PR0049 appear in Completed foundation PRs
grep -n "PR0047.*Calibration sample preprocessing bridge\|PR0048.*HTTP prediction\|PR0049.*Production end-to-end" ROADMAP.md

# 4. Verify PR0047, PR0048, PR0049 do NOT appear in Next Execution Sequence
SECTION_START=$(grep -n "## Next Execution Sequence" ROADMAP.md | head -1 | cut -d: -f1)
SECTION_END=$(grep -n "## Training Pipeline Track" ROADMAP.md | head -1 | cut -d: -f1)
sed -n "${SECTION_START},${SECTION_END}p" ROADMAP.md | grep "PR004[7-9]"
# If this outputs lines, the deletion in the Next Sequence table failed.

# 5. Verify Current State header is updated
grep -n "## Current state through" ROADMAP.md
# Must show "PR0049", not "PR0045"

# 6. Verify stale "not yet implemented" calibration preprocessing claim is gone
grep -n "not yet implemented" ROADMAP.md || echo "clean"

# 7. Verify current state includes new items
grep -n "Explicit target/control H5 refs\|Production E2E smoke hardening\|Agent loop guardrails\|FastAPI remains deferred" ROADMAP.md

# 8. Verify Next Execution Sequence starts with PR0050
grep -A 5 "Next Execution Sequence.*PR0049" ROADMAP.md | grep "PR0050"
# Must find PR0050 as the first table row

# 9. Verify Next Execution Sequence header is updated
grep -n "Next Execution Sequence.*PR0049" ROADMAP.md
# Must show "post-PR0049"

# 10. Verify preserved decisions are intact
grep -n "App Runner.*near-term\|ECS Fargate.*long-term\|APRANA is retired" ROADMAP.md
# All three must be present

# 11. Verify gates are intact
grep -n "G-API-1\|G-API-2\|G-INFRA-1\|G-CFG-1\|G-CFG-2\|G-CFG-3" ROADMAP.md

# 12. Verify no FastAPI introduced
grep -n -i "FastAPI\|fastapi\|uvicorn\|starlette" ROADMAP.md || echo "clean — no FastAPI"

# 13. Verify process guardrails not given a roadmap PR number
grep -n "PR-005.\|PR 005.\|PR005." ROADMAP.md | grep -i "guardrail\|process\|agent" || echo "clean — no PR number consumed by guardrails"

# 14. Verify no forbidden artifacts committed
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz" || true
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" \
  -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) \
  -not -path "./.git/*" -not -path "./venv/*" -not -path "./.venv/*" -print

# 15. Visual sanity — show the diff
git diff ROADMAP.md
```

---

## 11. Deviations from Plan

This section is populated by the implementation agent after implementation. Before implementation, it is empty.

| # | Deviation | Rationale | Approved? |
|---|-----------|-----------|-----------|
| — | None yet | — | — |

If no deviations occur, mark as "None — plan followed exactly."

---

## 12. Boundary Confirmations

| File/Directory | Changed in this PR? | Rationale |
|---------------|---------------------|-----------|
| `ROADMAP.md` | **YES** | Apply drift correction — completed work, current state, next sequence |
| `src/**` | **NO** | Forbidden |
| `tests/**` | **NO** | Forbidden |
| `docs/**` | **NO** | Forbidden |
| `docs/adr/**` | **NO** | Forbidden |
| `docs/architecture.md` | **NO** | Forbidden |
| `Dockerfile` | **NO** | Forbidden |
| `Dockerfile.training` | **NO** | Forbidden |
| `infra/**` | **NO** | Forbidden |
| `.github/**` | **NO** | Forbidden |
| `requirements.txt` | **NO** | Forbidden |
| `pyproject.toml` | **NO** | Forbidden |
| `src/bremen/training/**` | **NO** | Forbidden |
| `.project-memory/**` (except review artifact) | **NO** | Forbidden |
| `.project-memory/pr/roadmap-correction-after-pr0049/PLAN.md` | **YES** | Planning artifact |
| `.project-memory/pr/roadmap-correction-after-pr0049/reviews/plan-review.yml` | **YES** | Future review artifact |

---

## 13. Implementation Scope

| Item | Included? |
|------|-----------|
| ROADMAP.md — add PR0047/PR0048/PR0049 to Completed foundation PRs | ✓ Yes |
| ROADMAP.md — update Current State header and bullets | ✓ Yes |
| ROADMAP.md — remove PR0047–PR0049 from Next Execution Sequence | ✓ Yes |
| ROADMAP.md — update Next Execution Sequence header to post-PR0049 | ✓ Yes |
| ROADMAP.md — optionally add process guardrails bullet to completed list | ✓ Yes — add it |
| ROADMAP.md — add "Agent loop guardrails" and "FastAPI deferred" to current state | ✓ Yes |
| ROADMAP.md — any other changes | ✗ No — scope-limited |
| Any source, test, ADR, infra, Docker, dependency changes | ✗ No — forbidden |
| Any project-memory changes beyond review artifact | ✗ No — forbidden |

---

## 14. Next Required Action

The implementation agent (`coder`) must:

1. **Read ROADMAP.md** and verify all anchors from Section 4 with `grep -n` commands.
2. **Apply edits in this order** (to avoid line-number drift between edits):
   a. Add PR0047–PR0049 + process guardrails to Completed foundation PRs (Anchor A + F).
   b. Update Current State section header (Anchor B).
   c. Update calibration preprocessing bullet (Anchor C).
   d. Add new current state bullets (Anchor D).
   e. Delete PR0047–PR0049 rows from Next Execution Sequence table (Anchor E).
   f. Update Next Execution Sequence header from `(post-PR0045)` to `(post-PR0049)`.
3. **Verify edits** using the validation commands in Section 10.
4. **Commit** only `ROADMAP.md`.

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. The H5 Layout Strategy section (lines 198–227) contains cross-references to PR0047 (e.g., "Preprocessing is PR0047 scope", "preprocessing in PR0047"). These are legitimate historical references to the PR that introduced the feature, not claims of future work. Do NOT delete or "fix" these references — they are correct after PR0047 is recorded as completed.
2. Line numbers in ROADMAP.md may shift after branch updates. The implementation agent must verify all anchors with `grep -n` before editing, not just at the start.
3. Edit order matters — apply edits in the sequence listed in Section 14 to avoid intermediate line-number conflicts.
4. Do NOT add PR0050–PR0054 descriptions or change their content. The Next Sequence table columns must remain identical except for the deleted rows.

FILES CHANGED:
- `.project-memory/pr/roadmap-correction-after-pr0049/PLAN.md` — written

DRIFT SUMMARY:
Audit found minor_drift: PR0047/PR0048/PR0049 completed but absent from completed list, still in future sequence. Current state header stale at PR0045. Calibration preprocessing still noted as "not yet implemented." Process guardrails not referenced. All gates/decisions/H5 strategy preserved and accurate.

ROADMAP ANCHORS:
7 anchors identified (A–G). See Section 4 for exact line references and edit commands. Verify with `grep -n` before editing.

ROADMAP CORRECTION PLAN:
One file changed (ROADMAP.md). Three categories of edit: completed work additions, current state refresh, next sequence cleanup. No source, test, ADR, docs, infra, or dependency changes.

COMPLETED WORK UPDATE PLAN:
Add 3 product PRs (PR0047–PR0049) + 1 process-only line (guardrails) to Completed foundation PRs. Use exact descriptions from existing sequence table. Guardrails bullet explicitly notes "process-only; no roadmap number consumed."

CURRENT STATE UPDATE PLAN:
Update header from PR0045 to PR0049. Replace one stale bullet. Add three new bullets covering explicit ref wiring, production smoke hardening, process guardrails, and FastAPI deferral.

NEXT SEQUENCE UPDATE PLAN:
Delete three table rows (PR0047–PR0049). Update section header from `(post-PR0045)` to `(post-PR0049)`. PR0050 remains first item. PR0050–PR0054 descriptions unchanged.

PRESERVED DECISIONS:
16 preserved items verified. No architectural, gate, H5 strategy, or lifecycle changes. FastAPI remains deferred.

VALIDATION PLAN:
15 validation commands. Covers: working tree, allowed files, completed work presence, future-work absence, current state header, stale claim removal, new state bullets, sequence order, sequence header, preserved decisions, gates, FastAPI scan, guardrail number consumption, artifact scan, and visual diff.

BOUNDARY CONFIRMATIONS:
21 boundaries confirmed. Only ROADMAP.md changed (plus planning artifacts). All src/tests/docs/adr/infra/Docker/dependency/training files unchanged.

IMPLEMENTATION AGENT ASSIGNMENT: coder

TASK COMPLETE

NEXT REQUIRED ACTION: The implementation agent (coder) must edit ROADMAP.md following the correction plan in Section 5, using the anchors in Section 4, and validate with Section 10.
