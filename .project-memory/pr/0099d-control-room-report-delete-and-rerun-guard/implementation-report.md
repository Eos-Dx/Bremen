# Implementation Report — PR0099D: Control Room model-specific report deletion and rerun guard

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/job_api_handler.py` | Rerun guard, report deletion, source_key tracking, report_deleted field |
| `src/bremen/control_room_ui.py` | Analyzed row state, delete report button, model switch recomputation, Patient copy |
| `tests/test_bremen_control_room.py` | 40 new tests in TestPR0099DReportDeleteAndRerunGuard |
| `tests/test_bremen_launch_flow.js` | Updated assertion from "Container:" to "Patient:" |

## Root Cause

PR0099C fixed model/report binding identity, but Control Room still allowed re-analysis of the same patient/source with the same model. There was no:
- Backend rerun guard for same source + workflow + model
- Frontend indication that a source was already analyzed for the current model
- User action to delete/remove a report and unlock re-analysis

## Model-Specific Report Lock Behavior

The lock is keyed by: `source_key + workflow_id + model_id`

- `source_key` is the stable identity (source_id, upload_id, or container_id) stored in `input_summary`
- Not keyed by display filename alone (filenames can collide)
- Not keyed by source alone (different models remain selectable)
- Model switch recomputes disabled state

## Delete Report Endpoint/Action

Since `server.py` is FORBIDDEN (do_DELETE returns 405 for all routes), report deletion uses:

```
POST /demo/api/jobs
{
  "action": "delete_report",
  "job_id": "...",
  "workflow_id": "bremen"
}
```

Action routing added at top of `handle_jobs_create()` — checks for `action` field before normal job creation flow.

Response:
```json
{
  "status": "deleted",
  "job_id": "...",
  "workflow_id": "bremen",
  "model_id": "...",
  "report_deleted": true,
  "technical_demo_only": true
}
```

## Backend Duplicate Guard

`_find_existing_completed_report(source_key, workflow_id, model_id)` scans all jobs for:
- Same `source_key` in input_summary
- Same `workflow_id` in requested_workflows
- Same `model_id` in input_summary
- Job status == "completed"
- Report status == REPORT_STATUS_AVAILABLE

If found, returns 409 with `report_already_exists` error.

`handle_jobs_create` computes `source_key = source_id or upload_id or container_id or ""` and checks rerun guard before proceeding.

After report deletion (soft-delete to UNAVAILABLE), the same source + model becomes available for re-analysis.

## Frontend Disabled Patient Rows

- `analyzedSourceKeys` global variable: `{source_key: {model_id: job_id}}`
- Populated by `loadJobHistory()` from completed jobs with available reports
- `loadContainerCatalog()` renders `.cr-container-item.analyzed` class for matching sources
- CSS: `opacity: 0.5; cursor: not-allowed; pointer-events: none`
- `selectContainer()` returns early if row has `.analyzed` class
- `aria-disabled="true"` and `title="Already analyzed with this model"` for accessibility

## Model Switch Recomputation

`onModelSelect()` calls `loadJobHistory()` which:
1. Rebuilds `analyzedSourceKeys` from fresh job data (filtered by new model_id)
2. Calls `loadContainerCatalog()` to re-render patient rows with new analyzed state
3. Different model_id → different analyzed set → previously blocked rows become selectable

## Delete Report UX

- "Delete report" button appears in Job History for each job with available report
- Confirmation dialog: "Delete this generated report? The patient file will remain available. You can run this model again after deletion."
- On success: clears decision card (if current job), refreshes Job History (which re-renders Patients List)
- Report deleted status shown in Job History: "Report deleted"
- `window.deleteReport` exported for onclick binding

## Job History / Report Availability After Deletion

- `report_available` field: `false` after soft-delete
- `report_deleted` field: derived as `not has_available and overall_status == "completed" and len(reports) > 0`
- "Report deleted" shown instead of "Open report" link
- Job row remains visible (not removed)

## Safety/Audit Behavior

- Soft-delete only: report status set to UNAVAILABLE, no data destroyed
- Source files NOT deleted
- Catalog entries NOT deleted
- Other model reports NOT deleted (keyed by model_id)
- No raw paths, S3 keys, bucket names, prefixes, or internals exposed
- No raw exceptions or stack traces in responses

## Raw Path/S3 Safety Confirmed

- `delete_report()`: no s3://, /tmp/, h5_path references
- Frontend delete logic: no path or S3 references
- `source_key` stored as opaque identifier, not raw path
- Response contains only safe metadata (status, job_id, workflow_id, model_id, report_deleted)

## PR0098/0099/0099B/0099C Preservation Confirmed

- PR0098: Patients List, Refresh Patients, /demo/api/h5/containers preserved
- PR0099: 15 pipeline rows, decision safety wording, terminal collapse preserved
- PR0099B: `run_workflow_request(job_id=...)` optional arg preserved, create_analysis_job passes job_id
- PR0099C: Missing stage events emitted, trace finalization, tiny score <0.001, model/report binding

## Tests Added

40 new tests in `TestPR0099DReportDeleteAndRerunGuard`:

Backend (13):
1. `test_find_existing_completed_report_function_exists`
2. `test_rerun_guard_blocks_same_source_workflow_model`
3. `test_rerun_guard_uses_source_key_identity`
4. `test_create_analysis_job_accepts_source_key`
5. `test_input_summary_stores_source_key`
6. `test_list_analysis_jobs_returns_source_key`
7. `test_delete_report_function_exists`
8. `test_delete_report_soft_deletes`
9. `test_delete_report_returns_safe_response`
10. `test_delete_report_does_not_delete_source`
11. `test_handle_report_delete_function_exists`
12. `test_handle_jobs_create_routes_delete_report_action`
13. `test_list_analysis_jobs_has_report_deleted_field`

Frontend (20):
14. `test_analyzed_source_keys_variable_exists`
15. `test_load_job_history_populates_analyzed_source_keys`
16. `test_container_item_has_analyzed_class`
17. `test_analyzed_row_cannot_be_selected`
18. `test_analyzed_css_class_exists`
19. `test_update_readiness_checks_analyzed_state`
20. `test_update_readiness_shows_analyzed_message`
21. `test_start_analysis_checks_analyzed_state`
22. `test_on_model_select_resets_analyzed_state`
23. `test_load_job_history_calls_load_container_catalog`
24. `test_delete_report_button_in_job_history`
25. `test_delete_report_confirmation_text`
26. `test_delete_report_function_exists_in_page`
27. `test_delete_report_posts_action`
28. `test_delete_report_clears_decision_card`
29. `test_delete_report_refreshes_job_history`
30. `test_report_deleted_status_in_history`
31. `test_delete_report_window_export`
32. `test_no_visible_container_s`
33. `test_no_visible_container_colon`
34. `test_patient_label_used`
35. `test_no_s3_or_path_in_delete_logic`
36. `test_no_container_copy_in_analyzed_message`

Preservation (4):
37. `test_pr0099b_job_id_identity_preserved`
38. `test_pr0099c_stage_events_preserved`
39. `test_pr0099c_tiny_score_preserved`
40. `test_pr0099c_pipeline_summary_preserved`

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_control_room.py -v` | 195 passed |
| `pytest` (full suite) | 2395 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| `container(s)` in UI | CONFIRMED ABSENT |
| `Container:` in UI | CONFIRMED ABSENT |
| `s3://` in user-facing output | CONFIRMED ABSENT |
| PR0099B job_id preserved | CONFIRMED |
| PR0099C stage events preserved | CONFIRMED |
| PR0099C tiny score preserved | CONFIRMED |
| PR0099C pipeline summary preserved | CONFIRMED |
| No forbidden files changed | CONFIRMED |

## Blockers

None.

## Warnings

- Report deletion uses POST action routing because `server.py` is FORBIDDEN and `do_DELETE` returns 405. A future PR could add proper DELETE routes if server.py becomes modifiable.
- `analyzedSourceKeys` is populated from job history (last 20 jobs). If a very old job's report exists beyond the history window, the frontend won't know about it. The backend rerun guard still catches this and returns 409.

## Next Required Action

Human review and commit.
