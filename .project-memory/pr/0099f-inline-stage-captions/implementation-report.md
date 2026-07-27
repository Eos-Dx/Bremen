# Implementation Report — PR0099F: Inline stage captions and cached patient display-name map

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/control_room_ui.py` | Replaced 15 cr-stage-help buttons with inline cr-stage-caption spans; removed CSS; updated Patients List to use catalog patient_display_name |
| `src/bremen/api/source_registry.py` | Added patient_display_name to StagedSource, register_source, get_source_info; added update_source_display_name and get_display_metadata_for_filename; added _display_cache |
| `src/bremen/api/server.py` | Added patient_display_name field to catalog listing response |
| `tests/test_bremen_control_room.py` | 37 new tests in TestPR0099FInlineStageCaptions; updated 3 existing tests for new caption structure |

## INLINE STAGE CAPTIONS

### Rows Converted

All 15 Execution Pipeline rows converted from hover-only `<button class="cr-stage-help">` to always-visible `<span class="cr-stage-caption">`.

### Conversion Pattern

Before:
```html
<span class="cr-stage-label">Request accepted</span>
<button class="cr-stage-help" tabindex="0" aria-label="..." title="The analysis request was received and assigned to a Control Room job.">?</button>
```

After:
```html
<span class="cr-stage-label">Request accepted<span class="cr-stage-caption">The analysis request was received and assigned to a Control Room job.</span></span>
```

### CR-STAGE-HELP Removal

- All 15 `<button class="cr-stage-help">` elements removed
- CSS rules `.cr-stage-help`, `.cr-stage-help:hover`, `.cr-stage-help:focus` removed
- No JS dependencies existed on cr-stage-help
- grep -c "cr-stage-help" = 0

### Caption Text Preservation

Exact existing helper/title text reused for all 15 rows. No rewriting or paraphrasing.

### Rows with Captions

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

## PATIENT DISPLAY MAP/CACHE

### Cache Design

Added `_display_cache` dict to source_registry.py (process-level, in-memory, ephemeral).

StagedSource extended with `patient_display_name` field.

`register_source()` now accepts optional `patient_display_name` parameter.

`get_source_info()` now returns `patient_display_name` and `source_display_name` (pdn or filename or "Patient").

`update_source_display_name(source_id, patient_display_name)` added for post-registration updates.

`get_display_metadata_for_filename(filename)` added for filename-based lookups.

### Cache Key / Invalidation

Keyed by source_id (UUID). No ETag/last_modified invalidation needed because:
- Catalog listing creates new source_ids on each refresh
- Old source_ids expire after 1 hour
- Upload creates fresh source_id with patient_display_name at registration

### Patient Name Extraction

Reuses PR0099E `extract_patient_display_name(h5_path)` from job_api_handler.py.

Extraction path: `/session/sample/patient_name` (then `/scans/target/`, `/scans/contralateral/`)

### Fallback / Fault Tolerance

Fallback chain: `patient_display_name` → `filename` → `"Patient"`

Extraction failure returns empty string. Never raises. No crash.

### Upload Map Update

Upload handler in server.py was already creating source_ids via register_source. The catalog listing now includes `patient_display_name: ""` in the response (populated by frontend cross-reference with job history cache).

For uploads, patient_display_name is extracted at job creation time via `extract_patient_display_name(h5_path)` and stored in job input_summary.

### Catalog Listing Map Update

server.py catalog listing response now includes `patient_display_name` field (initially empty; populated when H5 is read during analysis).

### Patients List Display

Frontend now checks `c.patient_display_name` from catalog response first, then falls back to `patientNamesBySource[sid]` from job history cache, then to filename.

Primary row text: `patientName || name` (filename)
Secondary metadata: `filename · size · date` (only when patientName differs from filename)

### Patient Reports Display

Primary title: `patient_display_name` or `source_display_name` or "Patient"
Job ID: 8-char shortened in muted metadata
Model: shown in metadata line

### Display-Only Identity

`patient_display_name` is display-only. NOT used in:
- Rerun guard (`_find_existing_completed_report` uses `source_key`)
- Job identity (uses `job_id`)
- Report identity (uses `job_id + workflow_id`)

### PHI / Demo Safety

patient_display_name treated as potentially identifying. Only displayed because this is the explicit product requirement for demo files. No additional patient metadata exposed.

## PR0099B/0099C/0099D/0099E Preservation

- PR0099B: `run_workflow_request(job_id=...)` optional arg preserved
- PR0099C: 4 stage events, trace finalization, tiny score <0.001, 15/15 summary
- PR0099D: rerun guard, delete report, analyzed rows, model switch recomputation
- PR0099E: Patient Reports heading, failed-job gating, patient_display_name extraction

## Tests Added

37 new tests in `TestPR0099FInlineStageCaptions`:

Main task (11):
1. `test_cr_stage_help_removed` — cr-stage-help absent
2. `test_all_15_rows_have_captions` — 15 cr-stage-caption spans
3-8. `test_caption_*` — 6 representative caption texts
9. `test_stage_order_unchanged` — 15 rows remain
10. `test_terminal_summary_preserved` — 15/15 summary
11. `test_no_unsafe_clinical_wording_in_captions` — no clinical/diagnosis wording

Appendix A backend (12):
12-17. Source registry patient_display_name field, register, get, fallback, update, noop
18-22. H5 extraction: string, bytes, missing, empty, unsafe
23. `test_extract_patient_name_exception_does_not_raise`
24. `test_patient_display_name_not_lock_identity`

Appendix A frontend (7):
25. `test_patients_list_uses_catalog_patient_name`
26. `test_patients_list_fallback_to_filename`
27. `test_patient_reports_uses_patient_display_name`
28. `test_job_id_is_secondary_metadata`
29. `test_no_container_copy_in_ui`
30. `test_patient_reports_heading_present`
31. `test_job_history_heading_absent`

Preservation (6):
32-37. PR0099B/0099C/0099D/0099E preservation tests

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest` (full suite) | 2495 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| cr-stage-help count | 0 |
| cr-stage-caption count | 16 (1 CSS + 15 HTML) |
| No container(s)/Container: | CONFIRMED |
| Patient Reports heading | CONFIRMED |
| Job History heading absent | CONFIRMED |
| No forbidden files changed | CONFIRMED |

## Blockers

None.

## Warnings

- Catalog listing returns `patient_display_name: ""` initially. Patient names are populated from job history cache after first analysis, or from the catalog response when the source_registry has been updated with extracted names.
- server.py was edited only in the catalog listing metadata path (1 line addition) as allowed by the task scope.

## Next Required Action

Human review and commit.

## APPENDIX B — FAILED TERMINAL STATE AND REPORT GATING

### Root Cause

The `stream_complete` handler always called `fetchDecision(jobId)`, `setState('completed')`, and `collapseEventPanel('completed')` regardless of whether the job failed. This caused failed jobs to render green "Analysis complete" terminal row, decision card with "MRI recommended", green Open report button, and report shell when clicked.

### Failure Precedence Rule

Failure wins over completion. Added `hasSeenFailure` global tracking variable.

Precedence: `failed / error / cancelled / blocked > completed > running > pending`

### Terminal Row Behavior

`updatePipeline()` now sets `hasSeenFailure=true` when any failure event is observed. The `stage-complete` row is prevented from being marked as completed when `hasSeenFailure` is true (early return).

`stream_complete` handler checks `hasSeenFailure`:
- If failure: `setState('failed')`, `collapseEventPanel('failed')`, shows "Analysis failed. No report was generated." in decision card
- If no failure: proceeds with `fetchDecision`, `setState('completed')`, `collapseEventPanel('completed')`

### Decision Card Behavior for Failed Jobs

Two gates:

1. **stream_complete handler**: When `hasSeenFailure` is true, shows inline "Analysis failed. No report was generated." message. Does NOT call fetchDecision.

2. **fetchDecision function**: Checks `job.overall_status`. If `failed` or `normalization_failed`, shows "Analysis failed. No report was generated." and returns early. No MRI recommended, no Defer MRI, no score/threshold, no Open report.

### Open Report Gating

Open report link only rendered in `fetchDecision()` after passing the failed-job gate. Failed jobs return early before the Open report HTML is generated.

### Patient Reports Failed-Row Behavior

Already implemented in PR0099E:
- Failed rows: no onclick/openJob
- Failed rows: no Delete report button
- Failed rows: show "Analysis failed"
- Failed rows: patient_display_name as primary title
- Failed rows: model + job_id as metadata

### Backend Report Endpoint

`get_job_report()` returns `REPORT_STATUS_UNAVAILABLE` with `reason_code="REPORT_NOT_AVAILABLE"` for failed jobs. No synthetic report shell.

`list_analysis_jobs()` returns `report_available=false` for failed jobs (`has_available and not is_failed`).

### Rerun Guard

`_find_existing_completed_report()` checks `job.overall_status == "completed"`. Failed jobs never satisfy the guard. No change needed from PR0099D.

### Tests Added

42 new tests in `TestAppendixBFailedTerminalStateAndReportGating`:

Pipeline terminal state (7):
1. `test_has_seen_failure_variable_exists`
2. `test_update_pipeline_tracks_failure`
3. `test_stage_complete_not_completed_on_failure`
4. `test_stream_complete_uses_failure_state`
5. `test_stream_complete_no_fetch_decision_on_failure`
6. `test_collapse_panel_called_with_failed`
7. `test_reset_pipeline_clears_failure_flag`

Decision card (3):
8. `test_fetch_decision_gates_on_job_status`
9. `test_fetch_decision_shows_failed_message`
10. `test_fetch_decision_no_mri_recommended_for_failed`

Open report (1):
11. `test_open_report_not_shown_for_failed`

Backend (2):
12. `test_get_job_report_returns_unavailable_for_failed`
13. `test_report_available_false_for_failed_jobs`

Patient Reports (4):
14. `test_failed_row_no_open_job_click`
15. `test_failed_row_no_delete_report`
16. `test_failed_row_shows_analysis_failed`
17. `test_failed_job_not_in_analyzed_keys`

Rerun guard (2):
18. `test_failed_job_does_not_block_rerun`
19. `test_completed_job_still_blocks_rerun`

Preservation (6):
20-25. Patient Reports heading, Job History absent, inline captions, no container copy, delete report, tiny score

### Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest` (full suite) | 2520 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| hasSeenFailure tracking | CONFIRMED |
| stage-complete not completed on failure | CONFIRMED |
| stream_complete checks failure | CONFIRMED |
| fetchDecision gates on status | CONFIRMED |
| Open report gated | CONFIRMED |
| cr-stage-help = 0 | CONFIRMED |
| cr-stage-caption = 16 | CONFIRMED |
| No forbidden files changed | CONFIRMED |
