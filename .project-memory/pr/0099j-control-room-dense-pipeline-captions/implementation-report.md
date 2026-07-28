# Implementation Report — PR0099J: Dense pipeline captions and completed-stage status cleanup

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/control_room_ui.py` | Replaced accordion with dense grid layout; restored long captions; added markPipelineComplete(); updated tests for new layout |
| `tests/test_bremen_control_room.py` | Updated 31 existing tests for new layout; added 29 new PR0099J tests |

## Root Causes

### 1. Accordion created excessive vertical gaps
PR0099H/0099I accordion rows with hidden bodies, chevrons, and click-to-expand created too much vertical spacing. The pipeline card was visually sparse and required interaction to read explanations.

### 2. Active dot persisted after terminal completion
After a completed analysis, "Bremen workflow resolved" remained in `active` state with a dot instead of being marked completed. The `updatePipeline` function processed events individually but didn't cascade completion to all prior stages on terminal success.

## Dense Pipeline Caption Layout

### Structure
```html
<div class="cr-stage" id="stage-input">
  <span class="cr-stage-icon pending">●</span>
  <span class="cr-stage-text">
    <span class="cr-stage-label">Request accepted</span>
    <span class="cr-stage-caption">The analysis request was received and assigned to a Control Room job.</span>
  </span>
  <span class="cr-stage-dur"></span>
</div>
```

### CSS
```css
.cr-stage{display:grid;grid-template-columns:16px minmax(0,1fr) auto;align-items:start;
  column-gap:var(--sp-12);padding:6px var(--sp-16);border-left:3px solid var(--border);...}
.cr-stage-text{min-width:0;display:flex;flex-direction:column;gap:1px}
.cr-stage-label{color:var(--text-primary);line-height:1.25}
.cr-stage-caption{display:block;font-size:var(--fs-11);color:var(--text-secondary);line-height:1.25}
.cr-stage-dur{align-self:center;font-size:var(--fs-11);...}
```

### Key design decisions
- Grid layout: icon (16px) | label+caption (flexible) | duration (auto)
- Compact padding: `6px var(--sp-16)` — much denser than accordion
- Caption always visible — no click-to-expand needed
- `align-items:start` — icon aligns to top of multi-line row
- Existing tokens only — no undefined `--sp-10` or `--sp-44`

## Long Caption Text Restored

All 15 stages use the full explanatory text from PR0099H title attributes as visible captions:

1. "The analysis request was received and assigned to a Control Room job."
2. "The H5 measurements were converted into the canonical XRD case format used by Bremen."
3. "The system selected the Bremen workflow for the current model and source."
4. "The selected model artifact was found and its safe metadata/integrity checks passed."
5. "The verified model package was loaded into the runtime for analysis."
6. "The model package was adapted to the runtime interface when required."
7. "The loaded model was checked against the expected schema, metadata, and readiness contract."
8. "The accepted measurements were arranged into the Bremen model input structure."
9. "The runtime calculated the model input features from the prepared measurements."
10. "Feature count, order, names, and finite values were checked before inference."
11. "The model produced the probability score and raw prediction output."
12. "The model output was checked for expected fields and valid finite values."
13. "The score was compared with the configured threshold to produce the public recommendation."
14. "A safe demo report payload was created from the completed workflow result."
15. "The analysis reached terminal success and the Control Room is ready to show the result."

Short captions (PR0099G) no longer used as production visible text.

## Accordion UI Removed

Removed:
- `cr-stage-chevron` elements
- `onclick="toggleStage(this)"` inline handlers
- `onkeydown="toggleStageKey(event,this)"` inline handlers
- `aria-expanded` attributes
- `cr-stage-body` hidden divs
- `toggleStage()` function
- `toggleStageKey()` function
- `window.toggleStage` / `window.toggleStageKey` exports
- Accordion CSS rules

## Completed Status Cleanup

### markPipelineComplete()
```javascript
function markPipelineComplete(){
  if(hasSeenFailure)return;
  document.querySelectorAll('.cr-stage').forEach(function(s){
    s.className='cr-stage completed';
    var icon=s.querySelector('.cr-stage-icon');
    if(icon){icon.textContent='\u2713';icon.className='cr-stage-icon completed'}
  });
}
```

### Called from stream_complete success path
```javascript
if(hasSeenFailure){
  setState('failed');
  collapseEventPanel('failed');
  // show failed message
}else{
  markPipelineComplete();  // ← NEW: marks all 15 rows completed
  fetchDecision(jobId);
  setState('completed');
  collapseEventPanel('completed');
}
```

### Active dot bug fix
After `markPipelineComplete()`, all 15 stages are marked `cr-stage completed` with checkmarks. No stage remains in `active` state. The "Bremen workflow resolved" stage no longer keeps its active dot after terminal completion.

## Failure Precedence

- `markPipelineComplete()` checks `hasSeenFailure` first — returns early if any failure observed
- Failed path: `setState('failed')`, `collapseEventPanel('failed')`, shows "Analysis failed" message
- Failed path does NOT call `markPipelineComplete()`
- Individual stage failures from `updatePipeline()` still work — failed stages keep failed styling

## Tests Updated

31 existing tests updated for new layout (accordion assertions replaced with dense layout assertions).

## Tests Added

29 new tests in `TestPR0099JDenseCaptionsAndStatusCleanup`:

Accordion removed (5):
1-5. No chevron, no toggleStage inline, no toggleStageKey inline, no aria-expanded, no cr-stage-body

Long captions visible (6):
6-11. Six representative long captions verified visible

Dense layout (4):
12-15. Grid layout, cr-stage-text, font size, compact padding

Completed status cleanup (7):
16-22. markPipelineComplete exists, checks failure, sets all completed, called from stream_complete, no active dot, failure precedence

Preservation (7):
23-29. 15 rows, cr-stage-help absent, Patient Reports, no container copy, tiny score, duplicate guard, failed gating

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest` (full suite) | 2636 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| cr-stage-chevron count | 0 |
| toggleStage references | 0 |
| aria-expanded in stages | 0 |
| cr-stage-body count | 0 |
| Long captions (6 unique) | CONFIRMED |
| Grid layout | CONFIRMED |
| markPipelineComplete | CONFIRMED |
| 15 stage rows | CONFIRMED |
| cr-stage-help = 0 | CONFIRMED |
| No backend files changed | CONFIRMED |

## Blockers

None.

## Warnings

None.

## Next Required Action

Human review and commit.

---

## POST-REVIEW LAYOUT NESTING FIX

### Root Cause

Two HTML nesting defects in `build_control_room_page()`:

1. **cr-card-rail not closed before cr-decision-card**: The `</div>` that closes `cr-card-rail` was missing after the `cr-pipeline` div. The decision card was therefore nested inside the pipeline card instead of being a sibling under `cr-center`.

2. **cr-center not closed before cr-right**: With the missing `</div>`, `cr-center` remained open when `cr-right` was emitted. The browser rendered `cr-right` as a child of `cr-center`, not as a sibling. This caused Patient Reports and Live Events to appear below the pipeline instead of in the right column.

### Exact HTML Nesting Fix

Added one `</div>` to close `cr-card-rail` after the pipeline div, and re-indented the decision card:

```diff
         </div>
+      </div>

-            <div class="cr-decision-card hidden" id="cr-decision-card"></div>
+      <div class="cr-decision-card hidden" id="cr-decision-card"></div>
     </div>
```

### Confirmation: cr-main has direct cr-left/cr-center/cr-right children

Verified: `cr-main` contains exactly three direct column children in order: `cr-left`, `cr-center`, `cr-right`. The div count between `cr-center` open and `cr-right` open is balanced (20 opens, 20 closes).

### Confirmation: Patient Reports and Live Events inside cr-right

Verified: Both `Patient Reports` and `Live Events` appear within the `cr-right` div section.

### Confirmation: Decision card is sibling under cr-center, outside pipeline card

Verified: `cr-decision-card` appears between `cr-card-rail` close and `cr-center` close (position 21915, after rail close at 21876, before center close). It is NOT inside `cr-card-rail` or `cr-pipeline`.

### Tests Added

26 new tests in `TestPR0099JLayoutNestingFix`:

1. cr-main direct children in order (2 tests)
2. cr-right not inside cr-center (1 test)
3. cr-right is direct child of cr-main (1 test)
4. Patient Reports inside cr-right (1 test)
5. Live Events inside cr-right (1 test)
6. cr-decision-card inside cr-center (1 test)
7. cr-decision-card not inside cr-card-rail (1 test)
8. cr-decision-card not inside cr-pipeline (1 test)
9. cr-card-rail contains Execution Pipeline (1 test)
10. cr-card-rail contains cr-pipeline (1 test)
11. cr-card-rail no Patient Reports (1 test)
12. cr-card-rail no Live Events (1 test)
13. Dense pipeline preserved: 15 rows, captions, no chevron, no toggleStage, no cr-stage-help (5 tests)
14. Responsive CSS preserved: flex layout, 320px left, flex center, 360px right (4 tests)
15. PR0099J active-dot cleanup preserved (4 tests)

### Validation Results

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest -k PR0099JLayoutNestingFix` | 26 passed |
| `pytest -k PR0099JDenseCaptionsAndStatusCleanup` | 29 passed (existing tests) |
| `pytest -k control_room or pipeline or layout or stage or failed or report or patient or duplicate` | 950 passed, 2 skipped |
| `pytest` (full suite) | 2662 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| cr-stage count | 15 |
| cr-stage-chevron | 0 (production) |
| toggleStage | 0 (production) |
| cr-stage-help | 0 (production) |

### Blockers

None.

### Warnings

None.

---

## POST-REVIEW DELETED REPORTS UI FIX

### Root Cause

Deleted reports (report_deleted === true) remained visible in the primary Patient Reports list as "Report deleted" rows. This was visually confusing because deleted reports appeared alongside active reports with no separation.

### Active/Deleted Partition Behavior

In `loadJobHistory()`, jobs are now partitioned into two arrays:
- `activeJobs`: jobs where `report_deleted` is falsy
- `deletedJobs`: jobs where `report_deleted` is truthy

The main Patient Reports list renders only `activeJobs`. If no active jobs remain, it shows "No active patient reports."

### Deleted Reports Collapsed Section

Deleted reports render in a `<details class="cr-deleted-reports">` element that is collapsed by default. The summary label shows "Deleted reports (N)" with the count. Each deleted row shows patient name, model (truncated), and timestamp — no interactive features.

### Audit-Friendly Soft Delete Rationale

Deleted reports are soft-deleted only. The backend `delete_report` endpoint sets `report_deleted: true` but does not remove the job from storage. The UI hides deleted reports from the primary list but keeps them accessible in the collapsed section for audit purposes.

### Confirmation: No Hard Delete Added

No new delete endpoint, no permanent removal, no data erasure. The existing `deleteReport()` function still calls the same `action:'delete_report'` backend endpoint.

### Confirmation: Backend Unchanged

Scope check: `git diff --name-only | grep -E "^src/bremen/api/|^scripts/"` returns no output.

### Confirmation: No Open/Delete/Click-Through for Deleted Rows

The deleted reports section rendering loop does not include:
- `openJob` calls
- `Delete report` buttons
- `onclick` handlers

### Confirmation: Existing Layout Preserved

- Decision placeholder above Execution Pipeline
- Analyze button immediately after Patients List
- Source card below Analyze
- Patient Reports and Live Events in cr-right
- 15 cr-stage rows, dense pipeline, no accordion

### Tests Added

26 new tests in `TestPR0099JDeletedReportsUI`:

Deleted not in main list (2): report_deleted filter, activeJobs/deletedJobs partition
Deleted section (4): details element, label with count, collapsed by default, conditional rendering
All deleted scenario (2): no active message, conditional on activeJobs empty
No interactive features (3): no Open report, no Delete button, no onclick
Active reports preserved (3): activeJobs render, completed reports with Open, failed behavior
Delete action preserved (1): same backend endpoint
CSS (2): cr-deleted-reports, cr-deleted-report-item
Preservation (9): Patient Reports heading, Live Events, decision slot, Analyze order, 15 stages, no accordion, no container copy, decision placeholder, duplicate guard

### Validation Results

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest -k PR0099JDeletedReportsUI` | 26 passed |
| `pytest -k control_room or patient or report or deleted or duplicate or layout or pipeline or decision` | 1061 passed, 2 skipped |
| `pytest` (full suite) | 2721 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| cr-stage count | 15 |
| Backend/scripts in diff | 0 |

### Blockers

None.

### Warnings

None.


---

## POST-REVIEW ORDERING FIX

### Left Column Order Change

Moved Analyze button from below Source card to immediately after Patients List card.

Before: Model → Patients List → Source → Analyze
After:  Model → Patients List → Analyze → Source

Rationale: Analyze is the primary action and should be adjacent to the patient selection. Source/upload is secondary.

### Center Column Order Change

Moved decision card from below the pipeline card to above it.

Before: Execution Pipeline → Decision card (hidden)
After:  Decision placeholder → Execution Pipeline

Rationale: The answer card is the primary result and should appear above the pipeline.

### Decision Slot Stability Approach

Replaced the hidden empty decision card with a visible placeholder that reserves stable vertical space:

- Removed `hidden` class from initial HTML
- Added `cr-decision-placeholder` class with `min-height:140px`
- Added neutral placeholder content: “Recommendation pending” headline, “Recommendation will appear here after analysis.” copy, “Technical demo only. A clinician makes the final decision.” copy
- Added CSS: `.cr-decision-placeholder` (min-height, border-left-color), `.cr-decision-placeholder .cr-decision-headline` (secondary color), `.cr-decision-placeholder-copy` (font-size, color)

This prevents layout jump when a real result arrives.

### JS Placeholder Reset Behavior

Added `renderDecisionPlaceholder()` helper function that sets the decision card back to placeholder state with neutral content and `cr-decision-card cr-decision-placeholder` class.

Updated reset sites:
- `onModelSelect()`: replaced `card.innerHTML=''; card.className='cr-decision-card hidden'` with `renderDecisionPlaceholder()`
- `deleteReport()`: replaced same pattern with `renderDecisionPlaceholder()` when current job deleted
- Failed job paths (stream_complete failure, fetchDecision failure) remain unchanged — they show “Analysis failed. No report was generated.” message

### Confirmation: Dense Pipeline Preserved

- 15 `cr-stage` rows remain
- Long captions visible by default
- No `cr-stage-chevron` in production
- No `toggleStage`/`toggleStageKey` in production
- No `cr-stage-help` in production

### Confirmation: Right Column Preserved

- Patient Reports remains in `cr-right`
- Live Events remains in `cr-right`

### Confirmation: No Backend/Scripts Changes

Scope check: `git diff --name-only | grep -E "^src/bremen/api/|^scripts/"` returns no output.

### Tests Added/Updated

33 new tests in `TestPR0099JOrderingAndStableDecisionSlot`:

Left column order (4): Model before Patients List, Patients List before Analyze, Analyze before Source, full order
Analyze button preserved (4): id, onclick, disabled initially, aria-label
Center column order (4): decision before pipeline, decision inside cr-center, decision not inside cr-card-rail, decision not inside cr-pipeline
Stable decision slot (6): not hidden initially, placeholder class, min-height CSS, neutral copy, secondary copy, no clinical claims
JS reset behavior (4): renderDecisionPlaceholder exists, onModelSelect uses placeholder, deleteReport uses placeholder, startAnalysis no slot collapse
Dense pipeline preservation (5): 15 rows, captions, no chevron, no toggleStage, no cr-stage-help
Right column preservation (2): Patient Reports in cr-right, Live Events in cr-right
Failure/report preservation (4): failed jobs no Open report, failed message preserved, completed renders report link, MRI headlines preserved

2 existing tests updated:
- `test_on_model_select_resets_decision_card`: asserts `renderDecisionPlaceholder()` instead of `cr-decision-card hidden`
- `test_delete_report_clears_decision_card`: asserts `renderDecisionPlaceholder()` instead of `cr-decision-card`

### Validation Results

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest -k PR0099JOrderingAndStableDecisionSlot` | 33 passed |
| `pytest -k PR0099JLayoutNestingFix` | 26 passed |
| `pytest -k PR0099JDenseCaptionsAndStatusCleanup` | 29 passed |
| `pytest -k control_room or pipeline or layout or stage or failed or report or patient or duplicate or decision` | 1073 passed, 2 skipped |
| `pytest` (full suite) | 2695 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| cr-stage count | 15 |
| cr-stage-chevron | 0 (production) |
| toggleStage | 0 (production) |
| cr-stage-help | 0 (production) |
| Backend/scripts in diff | 0 |

### Blockers

None.

### Warnings

None.
