# PR0093B — Implementation Report

## Branch / HEAD

- **Branch:** `0093b-report-contract-layout-parity`
- **HEAD:** `1d1a92eb1c9b47d8fb67a9e01e3ca306844de4e2`

## Files Changed

| File | Action | Scope |
|------|--------|-------|
| `src/bremen/report_ui.py` | Modified (pre-existing) | Normalized builders, CSS, JS renderers |
| `src/bremen/api/server.py` | Modified (pre-existing) | Report API route dispatch |
| `src/bremen/api/job_api_handler.py` | Modified (pre-existing) | External/Internal report handlers |
| `tests/test_bremen_report_ui.py` | Modified (this PR) | Fixed 4 stale tests, added 38 new tests |

## External JSON Contract

`build_external_report_json()` in `src/bremen/report_ui.py` returns:

**Top-level keys:** `output_type`, `report_schema_version`, `report_id`, `generated_at`, `job_id`, `request_id`, `patient_reference`, `analysis_author`, `intended_use`, `limitations`, `model_metadata`, `input_summary`, `prediction_summary`, `decision_support`, `symmetry_signals`

All keys match `bremen_external_report.yaml` shape. Values come from real job/report data only — no sample values.

## Internal JSON Contract

`build_internal_report_json()` in `src/bremen/report_ui.py` returns:

**Top-level keys:** `output_type`, `report_schema_version`, `report_id`, `generated_at`, `job_identity`, `model_and_plugin`, `decision_policy`, `input_summary`, `execution_trace_summary`, `symmetry_signal_detail`

All keys match `bremen_internal_report.yaml` shape. Checksum is prefix-only (max 8 hex chars).

## Endpoints

| Endpoint | Handler | Behavior |
|----------|---------|----------|
| `GET /demo/api/reports/{job_id}/external` | `handle_external_report()` | Normalized External report JSON |
| `GET /demo/api/reports/{job_id}/internal` | `handle_internal_report()` | Normalized Internal report JSON |
| `GET /demo/report/{job_id}` | `_handle_report_route()` | Full report HTML page |

## External Visual Parity

- Report-document layout with `report-document` class
- Dark recommendation-hero with score, threshold, QC status
- `structural-comparison` section with signal-card-grid
- Level dots for small/moderate/larger/not_available
- `decision-meaning` section
- `model-table-section` with field-table
- `report-footer` with safety disclaimer
- Print/Save PDF via `window.print()`

## Internal Visual Parity

- `internal-technical-report` class with tables/field-rows
- `internal-report-header` with brand, subtitle, pills
- `boundary-note` section
- `signal-breakdown-table` with SIGNAL / FEATURE FAMILY / DIFFERENCE
- `execution-trace-summary` section
- `report-footer` with internal safety disclaimer

## Not Available Rendering

- External: "Calibration pending" for not_available
- Internal: "Reference statistics unavailable" for not_available
- No fabrication of small/moderate/larger when data unavailable
- Forbidden phrase "Asymmetry assessment is not available" is absent

## Print / Save PDF

- `window.print()` only — no server-side PDF
- `@media print` hides tabs, print buttons, navigation
- `print-color-adjust: exact` on all tinted/colored elements
- `page-break-inside: avoid` on signal cards and tables

## Safety Confirmation

- No raw feature values, deltas, percentile cutoffs, or reference-statistic values
- Checksum prefix only (max 8 hex chars)
- No S3 paths, manifest keys, ARNs, H5 paths, PHI, model internals
- Clinical wording: decision-support only, not diagnosis
- No sample values in live reports

## Tests Added or Updated

### Fixed (4 stale tests):
1. `test_reference_artifact_version_not_exposed_internally`
2. `test_execution_trace_uses_field_table`
3. `test_external_reads_qc_from_normalized_prediction`
4. `test_external_qc_rendered_in_hero`

### Added (38 new tests):
- TestExternalReportJSONContract (10)
- TestInternalReportJSONContract (10)
- TestReportHTMLStructure (14)
- TestForbiddenContentAbsence (5)

## Validation Results

- `compileall`: PASS
- `test_bremen_report_ui.py`: 116 passed
- `test_bremen_api_server.py`: 104 passed
- Full suite: 2169 passed, 1 failed (pre-existing), 11 skipped
- Safety greps: all pass

## Warnings

Pre-existing false positive in `test_bremen_control_room.py::test_report_no_bucket_name` — English word "buckets" triggers overly broad substring check.
