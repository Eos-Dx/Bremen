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
