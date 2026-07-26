# Implementation Report — PR0096: Per-side measurement reliability tier

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/lifecycle_contracts.py` | Added `left_measurement_count: int = 0`, `right_measurement_count: int = 0` to `PreparedWorkflowInput` |
| `src/bremen/api/workflow_bremen.py` | Added per-side count computation in `prepare_input()` and `execute()` |
| `src/bremen/api/decision_support.py` | Added `_compute_measurement_reliability()` helper; wired into `build_decision_support_report()` |
| `src/bremen/api/app.py` | Added `left_measurement_count` and `right_measurement_count` to `result_dict` from payload |
| `src/bremen/report_ui.py` | Added `measurement_reliability` passthrough in Python External/Internal builders and JS builders/renderer |
| `tests/test_bremen_decision_support.py` | NEW — 24 tests for tier logic, wiring, naming guard |
| `tests/test_bremen_workflow_bremen.py` | Added 4 tests for per-side count computation in execute() |
| `tests/test_bremen_report_ui.py` | Added 12 tests for report JSON wiring and naming guard |

## Count Computation

**Location**: `workflow_bremen.py` → `prepare_input()` and `execute()`.

**Method**: Direct computation from `canonical.measurements` using `getattr(m, "side", None) == "LEFT"` / `"RIGHT"`.

**Dual computation**: `prepare_input()` computes counts for event emission and `PreparedWorkflowInput` storage. `execute()` computes counts directly from `canonical.measurements` and injects into `result.payload` after successful inference.

## Storage

**Object**: `PreparedWorkflowInput` dataclass in `lifecycle_contracts.py`.

**Fields**: `left_measurement_count: int = 0`, `right_measurement_count: int = 0` — placed after non-default fields.

## Plumbing Path

1. `workflow_bremen.py` `execute()` → computes counts → injects into `result.payload`
2. `app.py` → reads from `payload` → puts into `result_dict`
3. `decision_support.py` → extracts counts → calls `_compute_measurement_reliability()` → emits into `prediction_summary["measurement_reliability"]`
4. Other call sites omit counts → reliability field absent (correct fallback)

## Decision Support Report Wiring

**Helper**: `_compute_measurement_reliability(left, right)` in `decision_support.py`.

**Logic**: Verbatim from bremen-training-pipeline:
- left >= 3 AND right >= 3 → HIGH_TECHNICAL
- left >= 2 AND right >= 2 → ACCEPTABLE_TECHNICAL
- else → LOW_TECHNICAL

## JSON Contract Placement

`prediction_summary.measurement_reliability` with shape: `{"tier", "reason", "left_measurement_count", "right_measurement_count"}`

## Internal Report Wiring

- Python `build_internal_report_json()`: carried via `_get_path()` into `decision_policy.measurement_reliability`
- JS `buildInternalReport()`: carried from `external.prediction_summary.measurement_reliability`
- JS `renderInternalReport()`: "Measurement Reliability" section after Decision Policy, before Boundary Note

## External Display

Deferred to follow-up PR (as approved). JSON-only emission.

## Naming Guard Confirmation

- No top-level `reliability` or `reliability_reason` anywhere
- Only reliability-bearing key: `prediction_summary.measurement_reliability`
- Function named `_compute_measurement_reliability`
- No clinical/diagnostic/model/scientific reliability wording

## Safety Confirmation

- No raw measurement values — only aggregate int counts
- No PHI, no patient identifiers, no clinical claims
- POST /predictions schema unchanged
- No Aramis code touched, no PR0092 touched

## Validation Results

| Command | Result |
|---------|--------|
| `git rev-parse --verify HEAD` | `9c8be584` |
| `git branch --show-current` | `0096-measurement-reliability-tier` |
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_workflow_bremen.py` | 36 passed |
| `pytest tests/test_bremen_decision_support.py` | 24 passed |
| `pytest tests/test_bremen_report_ui.py` | 181 passed |
| `pytest` (full suite) | 2263 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |

## Blockers

None.

## Next Required Action

Human review and commit.
