# Implementation Report — PR0099a: Job History enrichment, decision card spacing, status-rail

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/control_room_ui.py` | Job History: source_display_name, size swap, status-rail; Decision card: spacing fix + status-rail; CSS updates |
| `tests/test_bremen_control_room.py` | Added 13 PR0099a tests |

## PART A — source_display_name Rendering Confirmed

`loadJobHistory()` now reads `j.source_display_name` from the API response and renders it via `cr-history-source` class, positioned prominently between the header row and the decision text.

## PART A — Size Swap Confirmed (Job History expands, Live Events bounded)

- Job History card: `flex:1;display:flex;flex-direction:column;min-height:0` (expanding)
- Live Events card: `max-height:320px;display:flex;flex-direction:column;min-height:0` (bounded)
- `.cr-history-list`: `max-height:none;overflow-y:auto;flex:1;min-height:0` (scrollable, expands)

## PART A — Status Rail on Job History Entries Confirmed

CSS rules added:
- `.cr-history-item.defer{border-left-color:var(--status-available)}` (soft green for MRI_REVIEW_DEFER)
- `.cr-history-item.continue{border-left-color:var(--status-pending)}` (soft amber for CONTINUE_MRI)
- `.cr-history-item.failed{border-left-color:var(--status-error)}` (existing, for failed jobs)
- Default: `border-left:3px solid var(--border)` (neutral)

`loadJobHistory()` applies rail class based on `j.decision_code`: MRI_REVIEW_DEFER → defer, CONTINUE_MRI → continue, other → no rail class.

## PART B — Decision Card Spacing Fix

Changed `.cr-decision-card` padding from `var(--sp-20) var(--sp-24)` to `var(--sp-16) var(--sp-20)` to match other card conventions.

## PART C — Status Rail on Decision Card Confirmed

CSS rules added:
- `.cr-decision-card.defer{border-left-color:var(--status-available)}` (soft green)
- `.cr-decision-card.continue{border-left-color:var(--status-pending)}` (soft amber)

`fetchDecision()` applies class: MRI_REVIEW_DEFER → defer, CONTINUE_MRI → continue.

Tokens used: `--status-available` (soft green) for DEFER, `--status-pending` (soft amber) for CONTINUE. `--status-error` is NOT used for either decision outcome.

## Tests Added

13 new tests in TestPR0099aQAFix:
1. source_display_name in job history
2. cr-history-source class
3. Job History expands (flex:1)
4. Live Events bounded (max-height)
5. Defer CSS rail class
6. Continue CSS rail class
7. No status-error for decision rail
8. History rail class from decision_code
9. Decision card rail class from code
10. Live Events retains filter buttons
11. Live Events retains empty state
12. Live Events retains event list
13. Decision card padding matches cards

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_control_room.py` | 105 passed |
| `pytest` (full suite) | 2305 passed, 11 skipped, 0 failed |
| source_display_name in loadJobHistory | CONFIRMED |
| status-available/pending for decision rail | CONFIRMED |
| status-error NOT used for decision outcomes | CONFIRMED |
| PR0098 Patients List preserved | CONFIRMED |
| git diff --check | Clean |

## Blockers

None.

## Warnings

None.

## Next Required Action

Human review and commit.
