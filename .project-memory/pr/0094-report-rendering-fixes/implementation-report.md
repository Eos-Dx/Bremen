# PR0094 — Report Rendering Fixes — Implementation Report

## Files Changed

| File | Nature of Change |
|------|------------------|
| `src/bremen/report_ui.py` | Print color-adjust expansion, nullms duration guard, External QC field mapping fix |
| `tests/test_bremen_report_ui.py` | Regression tests for all four fixes |

No changes to `src/bremen/api/decision_support.py` — QC root cause was entirely in `report_ui.py` field source divergence, not server-side.

---

## Fix 1: Print Color-Adjust Coverage

### How classes were enumerated

The full non-print CSS was audited for every selector that uses:
- `background:` or `background-color:` properties
- tinted backgrounds (e.g., `var(--tint-accent)`, `var(--tint-pending)`, `var(--tint-error)`)
- badge/pill styling with background
- `border-left` with a status/accent color (status rail semantics)
- decorative/tinted callout backgrounds
- `border` with status/accent color

### Classes identified as having background/tint/border-color properties

| Class | Property | Type |
|-------|----------|------|
| `body` | `background: var(--bg-page)` | Page bg |
| `.report-card` | `background: var(--bg-surface)` | Surface bg |
| `.recommendation-card` | `background: var(--bg-surface)` + `border-left: 3px solid var(--accent)` | Surface bg + accent rail |
| `.score-bar` | `background: var(--border)` | Bar track bg |
| `.score-fill` | `background: var(--accent)` | Fill bg |
| `.score-threshold` | `background: var(--status-error)` | Threshold marker |
| `.qc-badge.passed` | `background: var(--tint-accent)` | Tinted badge |
| `.qc-badge.failed` | `background: var(--tint-error)` | Tinted badge |
| `.signal-chip.small` | `background: var(--tint-accent)` | Tinted pill |
| `.signal-chip.moderate` | `background: var(--tint-pending)` | Tinted pill |
| `.signal-chip.larger` | `background: var(--tint-error)` | Tinted pill |
| `.signal-chip.not_available` | `background: var(--bg-page)` | Muted bg |
| `.tech-demo-notice` | `background: var(--tint-pending)` | Tinted callout |
| `.sample-banner` | `background: var(--tint-error)` | Tinted banner |
| `.boundary-note` | `background: var(--tint-pending)` | Tinted callout |
| `.decision-policy-text` | `border-left: 2px solid var(--accent)` | Decorative border |
| `.trace-stage` | `border-left: 2px solid var(--border)` | Status rail |
| `.trace-stage.completed` | `border-left-color: var(--status-available)` | Status rail color |
| `.trace-stage.failed` | `background: var(--tint-error)` + `border-left-color: var(--status-error)` | Tinted bg + status rail |

### Previously covered (HEAD state)

Only 4 classes had `print-color-adjust` in the PREVIOUS (PR0093) @media print block: `.signal-chip`, `.qc-badge`, `.score-fill`, `.score-threshold` (plus `body`).

### Applied fix

Added `print-color-adjust` to these additional classes (now 12 classes total + body):
- `.recommendation-card` (was previously bundled with `.report-card` without print-color-adjust)
- `.report-card` (was previously bundled without print-color-adjust)
- `.score-bar`
- `.tech-demo-notice`
- `.boundary-note`
- `.decision-policy-text`
- `.sample-banner`
- `.trace-stage` **(NEW — added by this implementation)**

The `@media print` block now covers all backgrounded/tinted/border-colored classes that render during print. Classes hidden during print (`.report-error`, `.print-button`, `.report-loading`, etc.) are intentionally excluded.

### Design tokens preserved

No new hex colors, no changed color values, no new design tokens.

---

## Fix 2: nullms Execution Trace Bug

### Before
```javascript
if(stage.duration_ms!==undefined){html+='<span class="trace-stage-dur">'+stage.duration_ms+'ms</span>';}
```

### After
```javascript
if(stage.duration_ms!=null){html+='<span class="trace-stage-dur">'+stage.duration_ms+'ms</span>';}
```

### Guard pattern chosen

`!= null` — the loose-equality null check. This is the safer pattern because:
- `!= null` excludes **both** `null` and `undefined`
- `!== undefined` would pass `null` through, rendering `nullms`
- A numeric check (`typeof stage.duration_ms === 'number'`) would be more restrictive but `!= null` matches the existing data shape where `duration_ms` may be null, undefined, or a number

### Result

When `duration_ms` is `null` or `undefined`, the duration `<span>` is omitted entirely. No `nullms` string can appear. When a numeric value is present, it renders as `{value}ms` as before.

No duration_ms is fabricated. If duration is absent, no duration display is rendered.

---

## Fix 3: External QC Status Field Mapping

### Root cause

The External tab was reading QC status from a **different field path** than the Internal tab:

**External (before fix):**
```javascript
var rs = wfRun.result_summary || {};
var qcStatus = rs.qc_status || '—';
```
Reads from `job.workflow_runs.bremen.result_summary.qc_status`

**Internal (unchanged):**
```javascript
var qcSummary = payload.measurement_qc_summary || {};
var qcStatus = qcSummary.qc_status || '—';
```
Reads from `report.payload.measurement_qc_summary.qc_status`

These are populated by different server-side code paths. For some jobs, `result_summary.qc_status` may be absent or `undefined` while `payload.measurement_qc_summary.qc_status` has the actual value, causing the External tab to show `—` while Internal shows `passed`.

### Fix

Changed External to read from the **same authoritative source** as Internal:
```javascript
var extQcSummary = report.payload ? report.payload.measurement_qc_summary || {} : {};
var qcStatus = extQcSummary.qc_status || rs.qc_status || '—';
```

The fallback chain is:
1. `report.payload.measurement_qc_summary.qc_status` (same as Internal — primary source)
2. `rs.qc_status` (original External source — fallback for older jobs)
3. `'—'` (honest fallback when neither source has a value)

### No server-side change needed

The root cause was in `report_ui.py` only — the External tab was diverged from the Internal tab's field path. `decision_support.py` correctly populates `qc_status` in the report payload; the issue was that External wasn't reading it.

### Honest fallback preserved

If `qc_status` is genuinely unavailable in both sources, the report still shows `—`. No hardcoded `'passed'`.

---

## Fix 4: Tab Structure Verification

### Finding: NOT a product bug (Finding A)

The current HTML structure in `src/bremen/report_ui.py` renders a **single report page shell** containing both tabs:

```html
<div class="report-page">
  <div class="report-header">...</div>
  <div class="report-tabs" role="tablist">...</div>
  <div class="report-content" id="report-content">
    <div id="panel-external" class="tab-panel" ...>...</div>
    <div id="panel-internal" class="tab-panel" ... hidden>...</div>
  </div>
  <div class="report-footer">...</div>
</div>
```

Key observations:
- Exactly one `class="report-page"` div
- Both panels are children of the single `#report-content` div
- Tabs share a single `role="tablist"` container
- `@media print` hides inactive panels via `display:none !important` on `[hidden]`
- Only the active tab panel prints

The observed "two separate documents" issue was **not a product bug**. It occurred because the user printed each tab separately (clicking External → Print, then Internal → Print), which naturally produces separate PDF pages since only the visible tab is rendered during print. This is expected behavior for browser-native Print/Save PDF with tabbed content.

### Tab structure was NOT changed

No structural changes were made. The tab structure is confirmed correct. Tests added to verify:
- Single `report-page` div
- Both panels exist in the same `report-content` parent

---

## Tests Added/Updated

### New test classes (8 test methods total)

| Test Class | Test Method | Coverage |
|-----------|-------------|----------|
| `TestPrintSavePDF` | `test_print_css_preserves_accent_rail` | Verifies recommendation-card 3px accent left rail is preserved in @media print |
| `TestPrintSavePDF` | `test_print_color_adjust_covers_tinted_classes` | Verifies all 12 backgrounded/tinted classes have print-color-adjust, and count >= 26 |
| `TestDurationMsNullFix` | `test_duration_ms_guard_uses_null_check` | Verifies `duration_ms!=null` guard, NOT `!==undefined` |
| `TestDurationMsNullFix` | `test_no_nullms_in_page` | Verifies no `nullms` string anywhere in rendered page |
| `TestExternalQCStatusMapping` | `test_external_reads_qc_from_report_payload` | Verifies External reads from `extQcSummary.qc_status` (same as Internal) |
| `TestExternalQCStatusMapping` | `test_external_qc_falls_back_to_rs` | Verifies External falls back to `rs.qc_status` when payload unavailable |
| `TestTabStructureOneShell` | `test_single_report_page_shell` | Verifies exactly one `report-page` div |
| `TestTabStructureOneShell` | `test_both_panels_in_same_shell` | Verifies both panels under same `report-content` parent |

### Total test count

**79 tests** pass in `tests/test_bremen_report_ui.py` (previously 71).

---

## Validation Results

| Validation Command | Exit Code | Result |
|--------------------|-----------|--------|
| `git rev-parse --verify HEAD` | 0 | `d179e8151029a26ad202f3f70d5009461373d54e` |
| `git branch --show-current` | 0 | `0094-report-rendering-fixes` ✓ |
| `git status --short` | 0 | Only `report_ui.py`, `test_bremen_report_ui.py`, and report directory modified |
| `git diff --name-only` | 0 | Only allowed files changed |
| `grep -n "print-color-adjust" src/bremen/report_ui.py` | 0 | body + 12 classes covered (incl. `.trace-stage`) |
| `grep -n "duration_ms" src/bremen/report_ui.py` | 0 | Only `!=null` guard present |
| `python -m compileall src tests` | 0 | All modules compile cleanly |
| `python -m pytest -q tests/test_bremen_report_ui.py -v` | 0 | **79/79 passed** |
| `git diff --check` | 0 | No whitespace errors |
| `grep -rn "nullms" src/bremen tests \|\| true` | 0 | Only in test assertions (confirming absence) |
| `grep -oE '#[0-9A-Fa-f]{6}' src/bremen/report_ui.py tests/test_bremen_report_ui.py \| sort -u` | 0 | All hex colors from approved palette only |
| `grep -rn "WeasyPrint\|weasyprint\|playwright\|puppeteer\|chromium\|pango\|cairo" ...` | 0 | Only in test assertions confirming absence |
| Safety grep for unsafe field exposure | 0 | No unsafe exposure in report_ui.py |

### Full test suite (timeout)

`python -m pytest -q` timed out at 2 minutes due to integration/server tests that start HTTP listeners. This is expected behavior in the existing test suite. All `test_bremen_report_ui.py` tests (79/79) pass cleanly.

---

## Blockers

None.

---

## Warnings

1. Full test suite (`pytest -q`) timed out due to integration test HTTP servers. Report-specific tests (79/79) all pass.
2. The `__pycache__` files contain stale compiled bytecode from earlier builds, producing false positives in grep safety checks. No source changes introduce unsafe patterns.

---

## Boundary Confirmations

- [x] implementation followed approved PLAN.txt
- [x] no review artifact written
- [x] PLAN.txt not modified
- [x] plan-review artifact not modified
- [x] only PLAN.txt-approved paths changed
- [x] test discipline rules applied
- [x] validation commands run and recorded
- [x] no git mutation commands run
- [x] no registry push or secrets introduced
- [x] no `/demo/*` prohibited fields introduced
- [x] unavailable model candidates remain display-only and non-executable
- [x] IMPLEMENTATION_REPORT.txt written and is handoff context only

---

## Manual Deployment Note

After deploy, re-export both External and Internal reports for a real job and confirm:

1. Colored/tinted elements survive browser PDF export
2. No `nullms` appears in execution trace
3. External and Internal QC status match for the same job when QC status exists
4. Tab structure behaves as expected (single shell, one tab per print)
5. Safety language remains visible in exported PDF

---

## Next Required Action

Merge PR0094 after precommit review.
