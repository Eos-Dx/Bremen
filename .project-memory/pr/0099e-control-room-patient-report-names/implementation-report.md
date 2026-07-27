# Implementation Report — PR0099E: Control Room patient display names and Patient Reports UX

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/job_api_handler.py` | `extract_patient_display_name()` helper, `patient_display_name` in input_summary and list_analysis_jobs |
| `src/bremen/control_room_ui.py` | "Patient Reports" heading, patient name as primary title, stage help buttons with tooltips |
| `tests/test_bremen_control_room.py` | 41 new tests in TestPR0099EPatientDisplayNames |

## Root Cause

1. H5 files contain patient display labels at `/session/sample/patient_name` but this was never extracted for UI display
2. Job History showed opaque UUIDs/source_ids as primary row titles
3. "Job History" heading was unclear for demo users
4. Pipeline stages had no explanatory text for demo presenters

## Observed H5 Patient Name Path

Primary: `/session/sample/patient_name`
Fallback: `/scans/target/patient_name`, `/scans/contralateral/patient_name`

## Extraction Strategy

`extract_patient_display_name(h5_path)` in `job_api_handler.py`:
- Opens H5 read-only with h5py
- Tries `/session/sample/patient_name` first, then `/scans/target/patient_name`, then `/scans/contralateral/patient_name`
- Reads scalar string or bytes dataset
- Returns first safe unambiguous value found
- Never raises — catches all exceptions and returns empty string

## Fallback / Fault Tolerance

Fallback chain in `list_analysis_jobs()`:
1. `patient_display_name` (from H5 extraction)
2. `filename` (from input_summary)
3. `container_id` (from input_summary)
4. `"Patient"` (ultimate fallback)

If H5 extraction fails: returns empty string, falls through to filename.
If catalog listing fails: unaffected (extraction happens at job creation time, not catalog time).
If job creation fails: unaffected (extraction is non-blocking).

## Ambiguity/Failure Behavior

- Empty/whitespace-only values → rejected (returns empty)
- Values > 80 chars → rejected
- Values containing `s3://`, `/tmp/`, `/`, `\\`, `traceback`, `exception`, `bucket` → rejected
- Multiple scan paths → first safe value wins (no ambiguity detection needed since paths are tried in fixed order)
- Binary garbage → caught by exception handler → returns empty

## Where Patient Display Name is Cached/Propagated

1. `handle_jobs_create()` calls `extract_patient_display_name(h5_path)` after source resolution
2. Passed to `create_analysis_job(patient_display_name=...)`
3. Stored in `input_summary["patient_display_name"]`
4. Returned by `list_analysis_jobs()` as `summary["patient_display_name"]`
5. `list_analysis_jobs()` uses `pdn` as first choice in `source_display_name` fallback chain
6. Frontend `loadJobHistory()` populates `patientNamesBySource[source_key]` cache
7. Frontend `loadContainerCatalog()` uses `patientNamesBySource[sid]` for Patients List display

## Patient Reports Rename

"Job History" → "Patient Reports" in the HTML card title.

## Report Row Title Behavior

Patient Reports row structure:
- Primary title: `patient_display_name` or `source_display_name` or "Patient"
- Secondary metadata: filename (if patient_display_name differs from filename)
- Decision/status line: preserved from PR0099D
- Model + short job_id: in muted metadata line

## Patients List Display Behavior

Patients List row structure:
- Primary: `patientNamesBySource[sid]` or `display_name` (filename)
- Secondary: filename + size + date (when patient name differs from filename)
- Analyzed badge: preserved from PR0099D

## UUID/Job/Source Metadata Behavior

- UUID/job_id: appears as 8-char shortened metadata in `cr-history-meta`, not as primary title
- source_id: used only for internal identity (analyzedSourceKeys, rerun guard)
- No raw source_id or UUID in primary visible text

## Display-Only Identity Confirmation

`patient_display_name` is display-only. NOT used in:
- Rerun guard (`_find_existing_completed_report` uses `source_key`)
- Job identity (uses `job_id`)
- Report identity (uses `job_id + workflow_id`)

## Raw Path/S3 Safety Confirmed

- `extract_patient_display_name()`: checks for `s3://`, `/tmp/`, `/` in values and rejects them
- H5 internal paths (`/session/sample/...`) never exposed in output
- No raw file paths in user-facing display
- `source_key` stored as opaque identifier

## APPENDIX A — PIPELINE STAGE EXPLAINERS

### UI Pattern Chosen

Inline help button (`<button class="cr-stage-help">`) per pipeline row:
- Small circular "?" button, keyboard-focusable
- `tabindex="0"` for keyboard access
- `aria-label` with full accessible text (stage name + explanation)
- Native `title` attribute for tooltip on hover/focus
- CSS: 16px circle, border style, hover accent color, focus outline

### Accessibility Behavior

- Each button has `tabindex="0"` for keyboard navigation
- Each button has `aria-label` with "Stage name: explanation" format
- `title` attribute provides tooltip on hover and focus
- Focus style: 2px solid accent outline

### Stage Helper Copy (All 15 Rows)

1. Request accepted — "The analysis request was received and assigned to a Control Room job."
2. Canonical XRD created — "The H5 measurements were converted into the canonical XRD case format used by Bremen."
3. Bremen workflow resolved — "The system selected the Bremen workflow for the current model and source."
4. Model artifact verified — "The selected model artifact was found and its safe metadata/integrity checks passed."
5. Model artifact loaded — "The verified model package was loaded into the runtime for analysis."
6. Model artifact adapted — "The model package was adapted to the runtime interface when required."
7. Model validated — "The loaded model was checked against the expected schema, metadata, and readiness contract."
8. Input prepared — "The accepted measurements were arranged into the Bremen model input structure."
9. Features produced — "The runtime calculated the model input features from the prepared measurements."
10. Feature contract validated — "Feature count, order, names, and finite values were checked before inference."
11. Inference completed — "The model produced the probability score and raw prediction output."
12. Output validated — "The model output was checked for expected fields and valid finite values."
13. Decision policy applied — "The score was compared with the configured threshold to produce the public recommendation."
14. Report generated — "A safe demo report payload was created from the completed workflow result."
15. Analysis complete — "The analysis reached terminal success and the Control Room is ready to show the result."

### No Backend Changes

Stage explainers are frontend-only. No backend event names, stage ids, or workflow logic changed.

### Safety Copy Confirmation

- No diagnosis/clinical decision/treatment wording in any helper
- Uses technical-demo framing: "score", "threshold", "recommendation", "workflow", "model artifact", "report payload"
- Existing "This is not a diagnosis" in decision card preserved

## PR0099B/0099C/0099D Preservation Confirmed

- PR0099B: `run_workflow_request(job_id=...)` optional arg preserved
- PR0099C: 4 stage events emitted, trace finalization, tiny score <0.001, 15/15 summary
- PR0099D: rerun guard (`report_already_exists`), delete report, analyzed rows, model switch recomputation

## Tests Added

41 new tests in `TestPR0099EPatientDisplayNames`:

Backend (15):
1. `test_extract_patient_display_name_function_exists`
2. `test_extract_patient_name_from_h5_scalar_string`
3. `test_extract_patient_name_from_h5_bytes`
4. `test_extract_patient_name_missing_returns_empty`
5. `test_extract_patient_name_empty_returns_empty`
6. `test_extract_patient_name_unsafe_path_returns_empty`
7. `test_extract_patient_name_unsafe_tmp_returns_empty`
8. `test_extract_patient_name_too_long_returns_empty`
9. `test_extract_patient_name_failure_does_not_raise`
10. `test_extract_patient_name_from_scans_target`
11. `test_create_analysis_job_accepts_patient_display_name`
12. `test_input_summary_stores_patient_display_name`
13. `test_list_analysis_jobs_returns_patient_display_name`
14. `test_list_analysis_jobs_prefers_patient_display_name`
15. `test_patient_display_name_not_used_as_lock_identity`

Frontend (19):
16. `test_patient_reports_heading_present`
17. `test_job_history_heading_absent`
18. `test_report_row_uses_patient_display_name`
19. `test_report_row_job_id_as_metadata`
20. `test_report_row_fallback_to_source_display_name`
21. `test_patients_list_uses_patient_name_from_cache`
22. `test_patients_list_patient_name_as_primary`
23. `test_patients_list_filename_as_secondary`
24. `test_patients_list_fallback_to_filename`
25. `test_all_15_pipeline_rows_have_help_buttons`
26. `test_stage_help_buttons_are_keyboard_accessible`
27. `test_stage_help_request_accepted_tooltip`
28. `test_stage_help_model_verified_tooltip`
29. `test_stage_help_features_produced_tooltip`
30. `test_stage_help_decision_applied_tooltip`
31. `test_stage_help_report_generated_tooltip`
32. `test_stage_help_analysis_complete_tooltip`
33. `test_no_unsafe_clinical_wording_in_stage_helpers`
34. `test_no_container_s_in_ui`
35. `test_no_container_colon_in_ui`

Safety/Preservation (6):
36. `test_no_h5_path_exposed_in_output`
37. `test_pr0099d_rerun_guard_preserved`
38. `test_pr0099d_delete_report_preserved`
39. `test_pr0099c_stage_events_preserved`
40. `test_pr0099c_tiny_score_preserved`
41. `test_pr0099b_job_id_wiring_preserved`

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_control_room.py -v` | 236 passed |
| `pytest` (full suite) | 2436 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| `patient_display_name` in source | CONFIRMED |
| `Patient Reports` heading | CONFIRMED |
| `Job History` heading absent | CONFIRMED |
| `container(s)` in UI | CONFIRMED ABSENT |
| `Container:` in UI | CONFIRMED ABSENT |
| Stage help buttons (15) | CONFIRMED |
| No unsafe clinical wording | CONFIRMED |
| PR0099B/0099C/0099D preserved | CONFIRMED |
| No forbidden files changed | CONFIRMED |

## Blockers

None.

## Warnings

- Patient name extraction reads H5 at job creation time. For catalog listing, patient names are only available after at least one job has been created for that source. The frontend cross-references with job history to populate the Patients List cache.
- The `container(s)` status text in loadContainerCatalog was already fixed in PR0099D to "patient(s) available".

## Next Required Action

Human review and commit.

## PRECOMMIT WARNING FIXES

### Warning 1 — Duplicate Analysis Complete Label Fixed

The `stage-complete` row had a duplicate `<span class="cr-stage-label">Analysis complete</span>` after the help button. Removed the duplicate so the label renders exactly once.

Before:
```html
<span class="cr-stage-label">Analysis complete</span>
<button class="cr-stage-help" ...>?</button>
<span class="cr-stage-label">Analysis complete</span>  ← DUPLICATE
<span class="cr-stage-dur"></span>
```

After:
```html
<span class="cr-stage-label">Analysis complete</span>
<button class="cr-stage-help" ...>?</button>
<span class="cr-stage-dur"></span>
```

Added test: `test_analysis_complete_label_appears_once_in_stage_row`

### Warning 3 — Patient Reports Loading Copy Fixed

Changed `Loading job history...` to `Loading patient reports...` for consistency with the "Patient Reports" heading.

Added test: `test_loading_patient_reports_text`

### Warning 2 — Patient Name Catalog-Scan (Accepted Non-Blocking)

Patient name extraction reads H5 at job creation time, so Patients List cache only populates after first job for a source. This is accepted as non-blocking because:
- Catalog-wide H5 scanning would require touching server.py (FORBIDDEN)
- The fallback to filename is safe and functional
- After first analysis, patient names appear in both Patients List and Patient Reports

### Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest` (full suite) | 2441 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| Analysis complete label: 1 per row | CONFIRMED |
| Loading text: "patient reports" | CONFIRMED |
| Job History absent | CONFIRMED |
| Patient Reports present | CONFIRMED |

## APPENDIX B — FAILED JOB REPORT GATING

### Root Cause

Failed analysis jobs could be clicked/opened in the Patient Reports panel, navigating to a report page that would render with empty/missing values (no score, threshold, QC status, decision code). The UI did not distinguish failed jobs from completed jobs in terms of click behavior or report availability.

### Backend Report Availability for Failed Jobs

`list_analysis_jobs()`: Added `is_failed = j.overall_status in ("failed", "normalization_failed")`. Changed `report_available` to `has_available and not is_failed`. Failed jobs always have `report_available=false`.

`get_job_report()`: Added early return for failed jobs returning `REPORT_STATUS_UNAVAILABLE` with `reason_code="REPORT_NOT_AVAILABLE"` instead of generating a synthetic report with empty values.

### Rerun Guard Behavior

`_find_existing_completed_report()` already checks `job.overall_status == "completed"`, so failed jobs never satisfy the rerun guard. No change needed.

Failed jobs do not block same source + workflow + model rerun.

### Frontend Failed-Row Behavior

Added `isFailed` check in `loadJobHistory()`:
- `isFailed = status==='failed'||status==='normalization_failed'`
- Failed rows: `statusText='Analysis failed'`
- Failed rows: no onclick handler (no openJob)
- Failed rows: no Delete report button (`reportAvail&&!isFailed`)
- Failed rows: no Open report link
- Failed rows: still show patient_display_name as primary title
- Failed rows: still show model + job_id as metadata

### Patient Display Name Preservation

patient_display_name still appears as primary title for failed rows when available.

### Safety / No Internal Details

Failed report responses contain only `status`, `reason_code`, `job_id`, `workflow_id`. No raw exceptions, stack traces, paths, S3 keys, H5 internals, feature values, or model internals.

### Tests Added

17 new tests in `TestAppendixBFailedJobReportGating`:

Backend (4):
1. `test_list_jobs_failed_has_report_available_false`
2. `test_get_job_report_returns_unavailable_for_failed`
3. `test_failed_job_does_not_block_rerun_guard`
4. `test_completed_job_still_blocks_rerun`

Frontend (8):
5. `test_failed_row_no_open_report`
6. `test_failed_row_no_delete_report_button`
7. `test_failed_row_shows_analysis_failed`
8. `test_failed_source_not_in_analyzed_keys`
9. `test_patient_reports_heading_still_present`
10. `test_job_history_heading_absent`
11. `test_patient_display_name_shown_for_failed`
12. `test_job_id_remains_secondary_metadata`

Preservation (5):
13. `test_pr0099d_rerun_guard_preserved`
14. `test_pr0099d_delete_report_preserved`
15. `test_pr0099c_tiny_score_preserved`
16. `test_pr0099c_pipeline_summary_preserved`
17. `test_no_container_copy_in_ui`

### Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest` (full suite) | 2458 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| Failed job report_available=false | CONFIRMED |
| Failed job no openJob onclick | CONFIRMED |
| Failed job no Delete report | CONFIRMED |
| Failed job shows "Analysis failed" | CONFIRMED |
| Failed job does not block rerun | CONFIRMED |
| Patient Reports heading | CONFIRMED |
| Job History heading absent | CONFIRMED |
| No container(s)/Container: copy | CONFIRMED |
