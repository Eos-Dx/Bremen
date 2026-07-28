# Implementation Report — PR0099I: Fix Control Room accordion toggle scope and row alignment

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/control_room_ui.py` | Added window.toggleStage/toggleStageKey exports; fixed CSS alignment with grid layout |
| `tests/test_bremen_control_room.py` | 22 new tests in TestPR0099IAccordionAlignmentFix |

## BUG 1 — WINDOW EXPOSURE FIX

### Root Cause

`toggleStage()` and `toggleStageKey()` were defined inside the IIFE (lines 909, 918) but NOT exported to `window`. The inline HTML handlers `onclick="toggleStage(this)"` and `onkeydown="toggleStageKey(event,this)"` cannot see IIFE-private functions, causing `ReferenceError: toggleStage is not defined`.

### Exact Fix

Added two lines to the existing window-exposure block:

```javascript
window.toggleStage=toggleStage;
window.toggleStageKey=toggleStageKey;
```

Placed adjacent to existing `window.deleteReport=deleteReport;` export.

### No Other Changes

- `toggleStage()` body unchanged
- `toggleStageKey()` body unchanged
- All existing window exports preserved

## BUG 2 — SOURCE INVESTIGATION

### Source Confirmed

```css
/* Line 104: original rule */
.cr-stage{display:flex;align-items:center;gap:var(--sp-12);padding:var(--sp-10) var(--sp-16);...}

/* Line 113: PR0099H override */
.cr-stage{flex-direction:column}
```

The second rule adds `flex-direction:column` but does NOT reset `align-items:center` from the first rule. Result: `.cr-stage-header` child is centered horizontally instead of stretching full width.

Also confirmed:
- `.cr-stage-header` had `display:flex` but no `width:100%`
- `.cr-stage-body` used undefined `var(--sp-44)` token
- `.cr-stage-header` used `var(--sp-10)` in first rule

## BUG 2 — CSS FIX

Replaced the problematic CSS block with properly aligned grid layout:

```css
.cr-stage{flex-direction:column;align-items:stretch;padding:0}
.cr-stage-header{width:100%;display:grid;grid-template-columns:16px minmax(0,1fr) auto auto;align-items:center;column-gap:var(--sp-12);padding:var(--sp-8) var(--sp-16);cursor:pointer;user-select:none}
.cr-stage-label{min-width:0;color:var(--text-primary);text-align:left}
.cr-stage-chevron{font-size:var(--fs-11);color:var(--text-secondary);margin-left:0}
.cr-stage-body{padding:0 var(--sp-16) var(--sp-12) calc(var(--sp-16) + 16px + var(--sp-12));font-size:var(--fs-13);color:var(--text-secondary);line-height:1.5}
```

Key changes:
- `align-items:stretch` on `.cr-stage` — header stretches full width
- `padding:0` on `.cr-stage` — header controls row spacing
- `width:100%` on `.cr-stage-header` — full width
- `grid-template-columns:16px minmax(0,1fr) auto auto` — icon | label | chevron | duration
- `text-align:left` on `.cr-stage-label` — left-aligned
- `margin-left:0` on `.cr-stage-chevron` — no auto margin centering
- Body padding uses `calc()` with existing tokens only
- Replaced `var(--sp-10)` with `var(--sp-8)` and `var(--sp-44)` with `calc()`

## MOUSE/KEYBOARD BEHAVIOR

- Mouse click on header: toggles row expansion ✓
- Enter/Space on header: toggles row expansion ✓
- `aria-expanded` updates on toggle ✓
- Multiple rows may be expanded independently ✓
- `resetPipeline()` collapses all rows ✓

## 15 STAGE ROWS PRESERVED

`grep -c 'class="cr-stage"' → 15` ✓

## CR-STAGE-HELP ABSENT

`grep -c "cr-stage-help" → 0` ✓

## BACKEND UNCHANGED

Only `src/bremen/control_room_ui.py` and `tests/test_bremen_control_room.py` changed. No backend files touched.

## PR0099H/G/F PRESERVATION

- PR0099H: Patient name cache, accordion structure preserved
- PR0099G: stable_source_key, already-analyzed copy, short captions preserved
- PR0099F: failed terminal state, hasSeenFailure, no Open report for failed preserved
- Patient Reports heading remains
- No container(s)/Container: copy

## Tests Added

22 new tests in `TestPR0099IAccordionAlignmentFix`:

Bug 1 — Window exposure (6):
1. `test_window_toggle_stage_exported`
2. `test_window_toggle_stage_key_exported`
3. `test_inline_onclick_still_valid`
4. `test_inline_onkeydown_still_valid`
5. `test_toggle_stage_function_defined`
6. `test_toggle_stage_key_function_defined`

Bug 2 — Alignment (6):
7. `test_cr_stage_align_items_stretch`
8. `test_cr_stage_padding_zero`
9. `test_cr_stage_header_width_100`
10. `test_cr_stage_header_uses_grid`
11. `test_cr_stage_label_left_aligned`
12. `test_no_undefined_sp_tokens_in_pipeline`

Preservation (10):
13. `test_all_15_stage_rows`
14. `test_accordion_collapsed_by_default`
15. `test_aria_expanded_present`
16. `test_enter_space_handler_present`
17. `test_cr_stage_help_absent`
18. `test_patient_reports_heading_present`
19. `test_job_history_heading_absent`
20. `test_failed_jobs_no_open_report`
21. `test_duplicate_report_guard_preserved`
22. `test_tiny_score_preserved`

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest` (full suite) | 2607 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| window.toggleStage exported | CONFIRMED |
| window.toggleStageKey exported | CONFIRMED |
| align-items:stretch | CONFIRMED |
| width:100% on header | CONFIRMED |
| grid-template-columns | CONFIRMED |
| text-align:left on label | CONFIRMED |
| No --sp-10 or --sp-44 in pipeline CSS | CONFIRMED |
| 15 stage rows | CONFIRMED |
| cr-stage-help = 0 | CONFIRMED |
| No backend files changed | CONFIRMED |

## Blockers

None.

## Warnings

None.

## Next Required Action

Human review and commit.
