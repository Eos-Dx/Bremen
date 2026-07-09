# Plan: Roadmap Correction After PR0054

**PR**: roadmap-correction-after-pr0054 (docs-only correction, not PR0055)  
**Role**: plan  
**Mode**: planning  
**Branch**: roadmap-correction-after-pr0054  
**HEAD**: 827b19e8139e7e62d4427eca78cc4467397d2979  
**Audit reference**: .project-memory/audits/roadmap-release-audit-after-pr0054.md (committed but not on this branch; findings reproduced in task CONTEXT)  
**Drift classification**: minor_drift  

---

## 1. ROADMAP.md Correction Plan

### 1.1 Move PR0050–PR0054 from future sequence into completed foundation PRs

In the **Completed foundation PRs** section (currently ending at PR0049 and
"Agent loop guardrails"), append five new entries after the Agent loop
guardrails line. Use the following text:

```markdown
- PR0050 — Model/version readiness endpoint cleanup. Aligns `/model/version`
  `model_status` with actual `model_ready` state. Preserves safe metadata
  only via `ModelState.get_load_error()` safe categories.
- PR0051 — Config governance ADR/gates. Closes G-CFG-1 (DECIDED —
  lightweight in-repo governance), G-CFG-2 (DEFERRED — no DynamoDB/backend
  until Matador boundary), G-CFG-3 (DECIDED — validation gates as repo
  tests/static checks). ADR-0011 records all decisions.
- PR0052 — Matador boundary / system-of-record adapter skeleton. Typed
  boundary with `ExternalRecordRef`, `ResolvedInput`, `RecordResolver`
  protocol, and `UnconfiguredRecordResolver`. Scaffold only — no real
  Matador API calls, credentials, or network adapters. ADR-0012 documents
  the contract.
- PR0053 — Decision-support report/output wrapper. `build_decision_support_report()`
  produces safe structured report around inference results. No diagnosis,
  no clinical validation claim. `report_schema_version: "v0.1"`.
- PR0054 — Release readiness / operator notes. Production checklist,
  rollback, smoke commands, model artifact boundaries, clinical-safety
  disclaimers, and sign-off checklist.
```

### 1.2 Update "Current state through PR0049" to "Current state through PR0054"

Rename the section header from `## Current state through PR0049` to
`## Current state through PR0054`.

Preserve all existing bullet points from the PR0049 state (they are still
accurate). Add the following new bullet points at the end (before the
Product Track sequence section):

```markdown
- Model/version readiness cleanup completed.
- Config governance gates resolved (G-CFG-1 DECIDED, G-CFG-2 DEFERRED,
  G-CFG-3 DECIDED). ADR-0011 records config surface taxonomy and
  lightweight in-repo governance.
- System-of-record boundary skeleton exists (typed scaffold only —
  `ExternalRecordRef`, `ResolvedInput`, `RecordResolver` protocol,
  safe error hierarchy). Real Matador integration is not yet implemented.
- Decision-support report wrapper exists (`decision_support_report` with
  `report_schema_version: "v0.1"`, safety limitations, no diagnosis
  claims).
- Release readiness operator notes exist (16-section checklist covering
  startup, health, smoke, failure modes, logging, rollback, security,
  clinical-safety boundaries).
```

### 1.3 Delete the stale "Next Execution Sequence (post-PR0049)" table

Remove the entire section titled `## Next Execution Sequence (post-PR0049)`
and its 5-row table (PR0050–PR0054).

**Rationale**: The table described future work that is now completed.
Keeping it would confuse readers into thinking PR0050–PR0054 are still
pending. The completed entries are now in the Completed Foundation PRs
list (step 1.1) and the current state section (step 1.2).

### 1.4 Define the next execution block

ROADMAP.md contains reference to remaining Product Track items (items 2, 3,
6, 7 from the original Product Track sequence) and open Decision Gates
(G-CFG-2 is DEFERRED, G-CFG-1 remains OPEN, G-DEP-1 remains OPEN). However,
the audit found that ROADMAP.md does not contain enough explicit evidence
of what the human product/engineering team wants as the *immediate* next
block after PR0054.

**Therefore**: Add a **placeholder section** titled `## Next Execution
Block (post-PR0054)` with the following language:

```markdown
## Next Execution Block (post-PR0054)

The PR0050–PR0054 execution sequence is complete. The next execution block
requires a human product/engineering decision to select and prioritize
the next set of work from the candidates below.

**Remaining Product Track candidates** (from the original Product Track
sequence):

| Position | Description | Status |
|----------|-------------|--------|
| 2 | YAML/PDF clinical report template | Not started |
| 3 | YAML training config template | Not started |
| 6 | GitHub demo — real H5 patients, end-to-end prediction | Not started |
| 7 | Platform deployment plan document | Not started |

**Open Decision Gate candidates** (from the Decision Gate Register):

| Gate | Description | Status |
|------|-------------|--------|
| G-CFG-1 | Build vs. adopt config management product | OPEN |
| G-CFG-2 | Config state history store (DynamoDB or other) | DEFERRED |
| G-DEP-1 | Container repo merges feat/v0_3 to main | OPEN |

**Other roadmap-referenced candidates**:

| Candidate | Reference | Status |
|-----------|-----------|--------|
| Config editing surface (operator UI/API) | PR 0024, ADR-0009 | BLOCKED on G-CFG-1 |
| Matador resolver implementation (real adapter) | ADR-0012 Section "Future Matador Resolver" | Not started |
| FastAPI transport adapter (thin ASGI layer) | ROADMAP.md, ADR-0011 "Boundaries and Non-Goals" | Deferred |
| DynamoDB config state history store | G-CFG-2 | DEFERRED |

**Decision required**: Before PR0055 can be planned, a human
product/engineering decision must define which of these candidates (or
a new candidate not listed here) constitutes the next execution block.

> **Note**: The Product Track sequence positions (1–12) are ordering
> guidance, not chronological commitment. Reprioritisation is expected.
> Items 8–12 from the original Product Track have been completed as
> PR0050–PR0054.
```

### 1.5 Update the "Product Track sequence" note

In the Product Track sequence section, there is a note that says:

> Items 8–12 must not be silently dropped, but must appear after items 1–7
> because there is no model, API surface, or workflow yet for them to gate.

This note is now outdated because items 8–12 have been completed
(PR0050–PR0054). **Update the note** to:

```markdown
> **Note**: Items 8–12 from the original Product Track sequence have been
> completed as part of the PR0050–PR0054 execution sequence. The remaining
> Product Track items (2, 3, 6, 7) and any new candidates require human
> product/engineering prioritisation for the next execution block.
```

Also update the existing note about feature families being covered by
PR0034 — that note is still accurate and should be preserved.

### 1.6 ROADMAP.md summary of changes

| Operation | Location | Description |
|-----------|----------|-------------|
| Append | Completed foundation PRs list | Add PR0050, PR0051, PR0052, PR0053, PR0054 entries |
| Edit | Section header | `Current state through PR0049` → `Current state through PR0054` |
| Append | Current state section | Add 5 new bullet points for PR0050–PR0054 state |
| Delete | Full section | Remove `## Next Execution Sequence (post-PR0049)` and its table |
| Insert | New section | Add `## Next Execution Block (post-PR0054)` with placeholder/decision-required language |
| Edit | Product Track note | Update "Items 8–12 must not be silently dropped" to reflect completion |
| Preserve | All other content | No changes to H5 Layout Strategy, Agent test debugging, Training Pipeline Track, Decision Gate Register, Model binding lifecycle, CI/CD image tag policy, Config governance text |

---

## 2. ADR-0011 Correction Plan

### 2.1 Changes required

ADR-0011 references PR0052 as future work in multiple places. Since PR0052
is now completed, these references should be updated to past or present
tense. No decisions (G-CFG-1, G-CFG-2, G-CFG-3) are changed.

| Line | Current text | Change to |
|------|-------------|-----------|
| 22 | `tracked in PR0052 (Matador boundary / system-of-record adapter skeleton)` | `tracked in PR0052 (now completed — Matador boundary / system-of-record adapter skeleton)` |
| 43 | `Matador/system-of-record boundary work (PR0052) clarifies the ops contract.` | `The Matador/system-of-record boundary (defined in PR0052) clarifies the ops contract.` |
| 51-52 | `Persistence backend decisions are deferred until the Matador/system-of-record boundary is defined (planned PR0052).` | `Persistence backend decisions are deferred until the Matador/system-of-record boundary is further evaluated. PR0052 defined the typed scaffold (ExternalRecordRef, RecordResolver protocol); a real Matador resolver is still future work.` |
| 125-126 | `PR0052 is the Matador boundary PR. PR0051 defers to PR0052.` | `PR0052 (now completed) introduced the Matador boundary scaffold. PR0051 defers Matador integration to that PR — real integration remains future work.` |
| 115 | `PR0052 Matador integration is not implemented by PR0051.` | This line is in a test gate checklist, not a decision statement. It is factually correct and should be **preserved** as-is. |

### 2.2 No changes

The following are **not changed**:

- G-CFG-1: DECIDED — lightweight in-repo governance. No change.
- G-CFG-2: DEFERRED — no DynamoDB/backend implementation. No change.
- G-CFG-3: DECIDED — validation gates as repo tests/static checks. No change.
- Config Surface Taxonomy table. No change.
- Validation Gates list (items 1–16). No change.
- Boundaries and Non-Goals section. No change.
- Consequences sections. No change.
- FastAPI remains deferred. No change.
- Matador real integration remains future work. No change.

---

## 3. ADR-0012 Correction Plan

### 3.1 Status change

**Status**: `Draft (PR0052)` → `Decided (PR0052)`

Rationale: PR0052 is completed and merged. The decisions recorded in
ADR-0012 are no longer draft — they are the accepted architectural
contract for the system-of-record boundary.

### 3.2 Changes required

| Line | Current text | Change to |
|------|-------------|-----------|
| 28 | `PR0052 introduces a typed boundary skeleton for this future integration.` | `PR0052 introduced a typed boundary skeleton for this integration.` |
| 40 | `PR0052 introduces boundary only.` | `PR0052 introduced boundary only.` |
| 44 | `RecordResolver — protocol for future implementations.` | `RecordResolver — protocol for resolver implementations.` |
| 53-54 | `No router change in PR0052.` → `handle_submit_prediction in app.py is not modified.` | `No router change in PR0052.` → `handle_submit_prediction in app.py was not modified.` |

### 3.3 No changes

The following are **not changed**:

- **Matador is the source of record.** Preserved as-is. Real integration
  is still not implemented.
- **Future Matador Resolver** section (lines 110+). Preserved as-is —
  this describes future work that has not yet happened.
- **Safety Rules** section. Preserved as-is — all rules are still
  current and correct.
- **Non-Goals** list. Preserved as-is — all non-goals remain future
  (FastAPI, real Matador adapter, DynamoDB, etc.).
- **Consequences** sections. Preserved as-is — the boundary is still
  not wired into the request path; the Matador resolver is still
  deferred.

### 3.4 Intended result after correction

- Status changes from `Draft (PR0052)` to `Decided (PR0052)`.
- Minor future-tense verb shifts from present/future to past tense
  where PR0052 actions are already completed.
- All substantive architectural decisions, non-goals, and future
  work references remain intact.
- No new scope introduced.

---

## 4. Scope Boundaries

### 4.1 Files to be changed

| File | Type of change | Scope |
|------|---------------|-------|
| `ROADMAP.md` | Correction (sections 1.1–1.6 above) | Docs only |
| `docs/adr/0011-config-governance-gates.md` | Correction (section 2.1 above) | Docs only |
| `docs/adr/0012-system-of-record-boundary.md` | Correction (section 3.1–3.2 above) | Docs only |

### 4.2 Files NOT changed

- `src/` — No source changes.
- `tests/` — No test changes. All existing static doc tests
  (test_bremen_config_governance.py, test_bremen_system_of_record_boundary.py,
  test_bremen_release_readiness_operator_notes.py) assert against ADR and
  ROADMAP.md content. The wording changes must maintain backward
  compatibility with test assertions or the tests must be verified to
  still pass with the new wording.
- `docs/api_contract.md` — No changes. Already up to date.
- `docs/production_e2e_smoke.md` — No changes. Already up to date.
- `docs/release_readiness_operator_notes.md` — No changes. Already up to date.
- `config/`, `Dockerfile*`, `infra/`, `.github/`, `requirements.txt`,
  `pyproject.toml`, `agents/` — No changes.

### 4.3 Implementation constraints

- PR number **PR0055 is NOT consumed** by this PR. The branch name is
  `roadmap-correction-after-pr0054`, not `PR0055`.
- No runtime behavior is changed.
- No clinical validation claim is made.
- No diagnosis claim is made.
- No replacement of MRI, biopsy, radiologist, clinician, or clinical
  judgment is claimed.
- Matador real integration status is preserved as "not yet implemented."
- FastAPI remains deferred.

---

## 5. Validation Plan

### 5.1 Pre-implementation validation commands

```bash
# Verify no unintended files changed
git diff --name-only

# Verify compilation
python -m compileall src tests
```

### 5.2 Post-implementation test suite

```bash
# Static doc tests that assert against ROADMAP.md and ADRs
python -m pytest -q tests/test_bremen_config_governance.py -v
python -m pytest -q tests/test_bremen_system_of_record_boundary.py -v
python -m pytest -q tests/test_bremen_release_readiness_operator_notes.py -v
python -m pytest -q tests/test_bremen_api_contract.py -v
```

### 5.3 Safety validation commands

```bash
# Confirm no source/test/config/agent changes
git diff --name-only -- src tests Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml src/bremen/training agents config

# Confirm no binary artifact changes
git diff --name-only | grep -E '\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$' || true

# FastAPI/starllete/uvicorn: must only appear in deferred/non-goal context
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n ROADMAP.md docs/adr/0011-config-governance-gates.md docs/adr/0012-system-of-record-boundary.md || true

# Matador network libraries: must NOT appear outside ADR non-goals
grep -R "MATADRO_\|Matador.*token\|Matador.*URL\|requests\|httpx\|aiohttp" -n ROADMAP.md docs/adr/0011-config-governance-gates.md docs/adr/0012-system-of-record-boundary.md || true

# Secrets/identifiers: must not be present
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|s3://\|sha256:\|Nova_\|/Users/\|/home/" -n ROADMAP.md docs/adr/0011-config-governance-gates.md docs/adr/0012-system-of-record-boundary.md || true

# Clinical claims: all matches must be negation/disclaimer language only
grep -R "diagnos\|clinical validation\|clinically validated\|replace radiologist\|replace clinician\|replace MRI\|replace biopsy" -n ROADMAP.md docs/adr/0011-config-governance-gates.md docs/adr/0012-system-of-record-boundary.md || true
```

### 5.4 Safety validation expectations

| Check | Expected result |
|-------|----------------|
| FastAPI/uvicorn/starlette | Only in deferred/non-goal context — safe |
| Matador.*token/URL | Not present (ADR-0012 uses only "Matador" as system name) |
| requests/httpx/aiohttp | Not present (no network libraries in docs) |
| AKIA/SECRET_ACCESS_KEY/dkr.ecr | Not present |
| s3:// | Only `${VARIABLE}` placeholder notation or generic examples — safe |
| sha256: | Only in example/placeholder context — safe |
| Nova_ | Not present |
| /Users/ /home/ | Not present |
| diagnosis/clinical validation/replace | Only in negation disclaimer context — safe |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Test fails after ROADMAP.md wording change | Low | Medium | Run config_governance tests and system_of_record_boundary tests before merge. Tests assert on substring presence, not exact wording — wording changes are backward-compatible with assertions. |
| ADR-0011 decision text accidentally changed | Low | High | All G-CFG-1/G-CFG-2/G-CFG-3 decisions are explicitly NO-CHANGE in the plan. Only tense/context lines around them are updated. |
| ADR-0012 status change from Draft to Decided triggers governance test assertion | Low | Medium | The test_bremen_config_governance.py checks ADR-0012 existence and content — it does not check the Status field. The test_bremen_system_of_record_boundary.py checks ADR-0012 content — it also does not assert on the Status header. Safe to change. |
| The "Next Execution Block" placeholder is too prescriptive | Medium | Low | The placeholder lists candidates from existing ROADMAP.md and ADR content — no new work is invented. The final decision is explicitly delegated to human product/engineering. |
| A subsequent PR incorrectly interprets the placeholder as committed work | Low | Medium | The placeholder explicitly states "requires a human product/engineering decision" and "before PR0055 can be planned" — no work is committed. |

---

## 7. Non-Goals

- Not PR0055.
- Not runtime implementation.
- Not FastAPI.
- Not Matador real integration.
- Not clinical validation or diagnosis claims.
- Not replacement of MRI, biopsy, radiologist, clinician, or clinical judgment.
- Not test changes (preferred — verify tests pass as-is).
- Not source changes (`src/`).
- Not dependency changes.
- Not config, Docker, infra, CI, training, or agent changes.
- Not adding new roadmap work that is not already present in ROADMAP.md.

---

## 8. Implementation Order

1. Edit `ROADMAP.md` — all six operations (1.1–1.6)
2. Edit `docs/adr/0011-config-governance-gates.md` — four line changes (2.1)
3. Edit `docs/adr/0012-system-of-record-boundary.md` — status change + four line changes (3.1–3.2)
4. Run validation (section 5)
5. Commit with message: `docs: roadmap correction after PR0054 — move completed PRs from future to completed, update current state, add placeholder for next block, update ADR-0011/0012 minor tense references`

---

## 9. Test Compatibility Verification

Before merging, verify that no test assertion depends on the exact wording
being changed:

- **ADR-0011 tests** (test_bremen_config_governance.py): Assert on
  `G-CFG-1`, `G-CFG-2`, `G-CFG-3`, `in-repo`, `no external config platform`,
  `DynamoDB`, `deferred`, `pytest`, `config surface`, `PR0052`, `FastAPI`,
  `not implemented`, `Matador`, `not implemented` — none of these exact
  anchors are changed by the plan. The plan only changes surrounding
  context sentences, not the keywords the tests assert on.
- **ADR-0012 tests** (test_bremen_system_of_record_boundary.py): Assert on
  `Matador`, `source of record`, `h5_path`, `h5_uri`, `no request schema`,
  `no network`, `no credentials` — none of these are changed.
- **ROADMAP.md tests** (test_bremen_config_governance.py, indirect via
  roadmap tests): The `test_adr_0011_mentions_matador_pr0052` asserts
  `Matador` and `PR0052` are mentioned in ADR-0011 — both are preserved
  in the new wording.

**Verdict**: All existing test assertions remain compatible with the
planned wording changes. No test modifications needed.

---

Implementation role: coder
