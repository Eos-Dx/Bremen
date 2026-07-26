# Implementation Report — PR0096A: Measurement reliability report plumbing hotfix

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/app.py` | Removed default=0 for absent counts |
| `src/bremen/api/report_bremen.py` | Added measurement_reliability computation into v0.2 payload |
| `src/bremen/report_ui.py` | Added fallback paths for measurement_reliability |
| `tests/test_bremen_report_ui.py` | Added 6 regression tests |

## Bug Summary

Counts visible in result_summary but not in report JSON. Broken hop: BremenReportProvider._build_report() never read left/right counts from workflow_result. build_external_report_json() only read measurement_reliability from legacy decision_support_report path (empty in v0.2).

## Fix Summary

1. app.py: Remove default=0 — absent counts stay None, no fabricated LOW_TECHNICAL
2. report_bremen.py: Extract counts from workflow_result, compute measurement_reliability, include in v0.2 payload
3. report_ui.py: Add fallback paths (ds -> prediction_legacy -> payload) for measurement_reliability

## Validation

All 2263 tests pass. 6 new regression tests added and passing.
