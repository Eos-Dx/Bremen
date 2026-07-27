# Implementation Report — PR0099c: Control Room runtime stage completeness, trace finalization, source display, and tiny-score UX

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/workflow_bremen.py` | Emit 4 missing completed stage events in `prepare_artifact()` and `execute()` |
| `src/bremen/api/execution_trace.py` | Trace finalization: status=completed when terminal workflow events present, even if some stage events are missing |
| `src/bremen/api/job_api_handler.py` | Source registry lookup for display filename; fallback "Patient" instead of "Unknown" |
| `src/bremen/control_room_ui.py` | STAGE_MAP keys corrected; tiny-score UX; pipeline summary uses 15-row denominator; Score/Threshold — for null |
| `tests/test_bremen_control_room.py` | Added 22 tests in TestPR0099CRuntimeStageCompleteness class |

## Real Deployed Evidence Summary

Job `6a3c0bc0-8324-47f5-84c3-e3b88eef44b3` showed:

- `overall_status = completed`
- `execution_traces.bremen.status = running`
- `completed_stage_count = 7`
- `total_applicable_stage_count = 11`
- Event stream missing: `runtime.artifact.load.completed`, `runtime.artifact.adaptation.completed`, `runtime.model.validation.completed`, `runtime.features.completed`
- `probability = 3.000407207061041E-8` rendered as "0.000" (bad UX)
- `container_id = 7ad5bb2a-2ab1-44af-b46a-780d657aeba0` (opaque UUID in Job History)

## PR0099/0099B Context

PR0099 established the 15-row pipeline with STAGE_MAP entries for all events. PR0099B fixed job_id mismatch in `run_workflow_request()` and added source display derivation from source_id/upload_id. This PR0099C completes the remaining gaps.

## Missing Event Types Fixed

Four event types were missing from the event stream:

1. `runtime.artifact.load.completed`
2. `runtime.artifact.adaptation.completed`
3. `runtime.model.validation.completed`
4. `runtime.features.completed`

## Exact Event Emission/Materialization Points

### In `BremenProvider.prepare_artifact()` (workflow_bremen.py):

- **`runtime.artifact.load.completed`** — emitted after `runtime.artifact.verification.completed`, with safe details: model_id, model_version, checksum_status
- **`runtime.artifact.adaptation.completed`** — emitted after load event, with safe details: model_id, adaptation_applied
- **`runtime.model.validation.completed`** — emitted when `validation_status == "completed"`, with safe details: model_id, model_version, model_schema_version, checksum_status

### In `BremenProvider.execute()` (workflow_bremen.py):

- **`runtime.features.completed`** — emitted after successful `build_features()` call and before `validate_features()`, with safe details: feature_schema_version, produced_count

### Chronological Order Preserved

The four new events follow the correct 15-row pipeline order:
1. ... artifact.verification.completed
2. artifact.load.completed ← NEW
3. artifact.adaptation.completed ← NEW
4. model.validation.completed ← NEW
5. ... input.preparation.completed
6. features.completed ← NEW
7. features.validation.completed
8. ... inference → output → decision → report → complete

### Safety

All event details are safe: no file paths, S3 keys, feature values, model coefficients, H5 internals, tokens, or PHI.

## Execution Trace Finalization

### Root Cause

`build_trace_from_events()` in `execution_trace.py` set `status = "completed"` only when `completed_count == len(stage_order)` (11 of 11). With 4 missing events, `completed_count` was 7, so status remained `"running"` even though the job was fully completed.

### Fix

Added terminal event detection. After building stages from event data, the function now checks for terminal workflow completion events (`runtime.workflow.completed`, `runtime.request.completed`). If a terminal completed event exists and at least one stage completed, trace status is set to `"completed"`. If a terminal failed event (`runtime.workflow.failed`) exists, status is `"failed"`.

### Logic (in priority order):

1. All 11 stages have events → `"completed"` (standard path)
2. Terminal failure event exists → `"failed"`
3. Terminal completion event exists + at least 1 completed stage → `"completed"` (legacy/missing events path)
4. Some stages completed, no terminal event → `"running"`
5. No stages completed → `"not_started"`

### Completed/Failed Trace Behavior

- Completed job trace status: `"completed"` (not `"running"`)
- Failed job trace status: `"failed"` (not faked as completed)
- Completed stage count reflects actual canonical stages with events
- Total applicable stage count remains 11
- The 4 newly emitted events cause artifact_loaded, artifact_adapted, model_validated, and features_produced to become completed stages

## Control Room Terminal Summary Fix

### Root Cause

`collapseEventPanel()` used `eventCache.length` (live event count) as the pipeline denominator.

### Fix

Changed denominator from `eventCache.length` to `Object.keys(STAGE_MAP).length` (always 15). Terminal completed summary now reads:

> Analysis complete · X of 15 pipeline stages completed · HH:MM:SS

Where X is the count of completed events in the cache, and 15 is the static pipeline row count.

- No more "1 of 1 events" or "10 of 14" or "9 of 9"
- Failed summary unchanged ("Analysis stopped · timestamp")
- Running state remains expanded (collapse only on completed/failed)

## Tiny-Score UX Fix

### Root Cause

`fetchDecision()` used `prob.toFixed(3)` and `thresh.toFixed(3)`, which rendered `3.000407207061041E-8` as `"0.000"`.

### Fix

Three-branch formatting in `fetchDecision()`:

1. `prob === null || prob === undefined || !isFinite(prob)` → `"Score —"`
2. `prob === 0` → `"Score 0.000"`
3. `prob < 0.001` → `"Score <0.001"`
4. Otherwise → `prob.toFixed(3)`

Same logic applied to threshold.

Missing score now shows "Score —", not "Score 0.000".
Score bar is preserved (may be visually tiny for tiny scores).
Threshold "—" shown for null/undefined threshold.

## Source Display / Patient Name Fix

### Root Cause

PR0099B fixed the "Unknown" fallback but deployed job still showed opaque UUID `7ad5bb2a-...` because `source_id` was treated as a raw string without registry lookup.

### Fix

In `handle_jobs_create()`:
- For `source_id`: first look up `get_source_info(source_id)` from the source registry. If a `filename` field exists, use it as the display name. Otherwise fall back to the safe basename derivation.
- For `upload_id`: look up staged upload record for its `filename`. Fall back to `"Patient"`.
- Fallback chain: `filename > source_registry_filename > basename_from_source_id > "Patient"`

In `list_analysis_jobs()`:
- `source_display_name` fallback changed from `"Unknown"` to `"Patient"`

No S3 keys, bucket names, S3 prefixes, s3:// URIs, filesystem paths, /tmp paths, upload temp paths, or PHI are exposed in user-facing display.

## Raw Path/S3 Safety Confirmed

- `resolve_source()` (unmodified) internally constructs `s3://` URIs for S3 download but this is internal and not exposed to user-facing output
- Display name derivation: `source_id.split("/")[-1]` takes only the last segment (safe basename)
- Source registry lookup returns only `filename` (no raw keys)
- Upload registry returns `filename` (no file path)
- Confirmed by test assertions

## PR0098/0099/0099B Preservation Confirmed

- PR0098: Patients List heading and Refresh Patients button preserved; upload endpoint /demo/api/h5/containers unchanged
- PR0099: 15 visible pipeline rows remain; decision card safety wording remains; Live Events terminal collapse remains
- PR0099B: `run_workflow_request(job_id: str | None = None)` remains optional; `create_analysis_job` continues passing `job_id=job_id`; app.py/inference_handler.py/server.py call sites unchanged

## Tests Added

21 new tests in `TestPR0099CRuntimeStageCompleteness` class:

1. `test_stage_map_uses_correct_event_type_names` — STAGE_MAP keys use correct event types
2. `test_stage_map_no_wrong_event_type_names` — STAGE_MAP does not use wrong event types
3. `test_prepare_artifact_emits_four_events` — prepare_artifact emits 4 events
4. `test_execute_emits_features_completed` — execute emits runtime.features.completed
5. `test_prepare_artifact_emits_validated_model_event_only_when_valid` — conditional emission
6. `test_trace_status_completed_with_all_11_stages` — all 11 stages → completed
7. `test_trace_status_running_with_partial_stages` — partial stages → running
8. `test_completed_summary_contains_15_of_15` — "15 of 15 pipeline stages completed"
9. `test_completed_summary_no_one_of_one_events` — not "1 of 1 events"
10. `test_completed_summary_no_10_of_14` — not "10 of 14"
11. `test_completed_summary_no_9_of_9` — not "9 of 9"
12. `test_collapse_uses_pipeline_total_not_event_cache` — pipelineTotal not eventCache.length
13. `test_tiny_positive_score_renders_less_than_0_001` — "<0.001" for tiny scores
14. `test_null_score_renders_em_dash` — "Score —" for null
15. `test_exact_zero_renders_0_000` — "Score 0.000" for zero
16. `test_threshold_renders_normally` — threshold formatting preserved
17. `test_null_threshold_renders_em_dash` — "Threshold —" for null
18. `test_source_registry_lookup_for_uuid_source_id` — get_source_info lookup
19. `test_list_analysis_jobs_fallback_is_patient_not_unknown` — "Patient" not "Unknown"
20. `test_source_display_no_s3_or_path_exposure` — no S3/path in display derivation
21. `test_fallback_without_metadata_is_patient` — fallback is "Patient"

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_control_room.py -v` | 134 passed (21 PR0099C-specific) |
| `pytest` (full suite) | 2334 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| Four missing event types in source | CONFIRMED — all 4 emitted in workflow_bremen.py |
| Event types in STAGE_MAP | CONFIRMED — correct keys in control_room_ui.py |
| Event types in execution_trace.py _STAGE_EVENT_MAP | CONFIRMED — all 4 mapped |
| Trace finalization: completed with terminal events | CONFIRMED |
| Trace finalization: running with partial, no terminal | CONFIRMED |
| Pipeline summary uses 15 rows | CONFIRMED — Object.keys(STAGE_MAP).length |
| Tiny-score: <0.001 for tiny positive | CONFIRMED |
| Tiny-score: — for null | CONFIRMED |
| Source display: "Patient" not "Unknown" | CONFIRMED |
| Source display: registry lookup for UUID | CONFIRMED |
| No S3/path exposure | CONFIRMED |
| PR0098/0099/0099B preserved | CONFIRMED |
| No forbidden files changed | CONFIRMED |

## Blockers

None.

## Warnings

None.

## Next Required Action

Human review and commit.

---

## APPENDIX A — MODEL/REPORT BINDING

### Root Cause

When `onModelSelect()` fires (user switches model in dropdown), the function updated `selectedModelId` and reloaded job history, but did NOT reset:
- The decision card (stale from previous model)
- Pipeline stage completion indicators
- Event panel contents
- `currentJobId`
- `jobState`

This meant stale model A results (decision card, pipeline, events) remained visible when the user switched to model B. The job history correctly filtered by new model_id, but the active analysis UI showed the old model's results, creating the appearance of report reuse.

### Backend Identity (Already Correct)

The backend was already model-safe:
- `create_analysis_job()` creates a unique `job_id` per call (UUID-based, no dedup)
- `input_summary` stores `model_id` on each job
- `list_analysis_jobs()` returns `model_id` and filters by it
- Reports are stored per-job in `job.reports` (not source-level)
- `handle_jobs_create()` passes `model_id` from request body to `create_analysis_job()`
- No source-level report caching or dedup exists

### Fix Applied

`onModelSelect()` in `control_room_ui.py` now resets all stale state:

```javascript
function onModelSelect(sel){
  selectedModelId=sel.value;
  var opt=sel.options[sel.selectedIndex];
  selectedModelWorkflowId=opt.getAttribute('data-workflow')||'bremen';
  currentJobId=null;          // ← NEW: clear stale job reference
  resetPipeline();            // ← NEW: reset all 15 stage indicators
  resetEventPanel();          // ← NEW: clear event cache and DOM
  var card=document.getElementById('cr-decision-card');
  if(card){card.innerHTML='';card.className='cr-decision-card hidden'} // ← NEW: hide decision card
  setState('idle');            // ← NEW: reset state machine
  loadJobHistory();           // reload with new model_id filter
  updateReadiness();
}
```

### Identity Model Confirmation

| Concern | Status |
|---------|--------|
| Frontend sends `model_id` in POST body | ✓ `body.model_id=selectedModelId` |
| Backend stores `model_id` on job | ✓ `input_summary["model_id"]` |
| Job History filters by `model_id` | ✓ Server-side filter + `model_id` query param |
| Job History displays `model_id` | ✓ `Model: <model_id>` in each row |
| Open report uses job-specific URL | ✓ `/demo/report/{job_id}` |
| Decision card uses specific job | ✓ `fetchDecision(jobId)` |
| No source-level report caching | ✓ Each call creates new job |
| Model switch resets stale UI | ✓ Decision card, pipeline, events, state all reset |
| Same source + different models → separate jobs | ✓ Unique UUID per creation |

### Tests Added (21 in `TestAppendixAModelReportBinding`)

1. `test_create_analysis_job_stores_model_id_in_input_summary` — backend stores model_id
2. `test_list_analysis_jobs_returns_model_id` — list returns model_id
3. `test_list_analysis_jobs_filters_by_model_id` — list filters by model_id
4. `test_handle_jobs_create_passes_model_id` — request model_id flows to job
5. `test_job_id_unique_per_creation` — UUID per job, no dedup
6. `test_no_source_level_report_caching` — no existing_job/cached_report/reuse_report
7. `test_start_analysis_sends_model_id` — frontend sends model_id in POST
8. `test_load_job_history_sends_model_id_filter` — history filtered by model_id
9. `test_job_history_displays_model_id` — model_id shown in history rows
10. `test_open_job_navigates_to_specific_job_report` — openJob uses job_id
11. `test_decision_card_report_link_uses_job_id` — report link is job-specific
12. `test_on_model_select_resets_decision_card` — decision card hidden on model switch
13. `test_on_model_select_resets_pipeline` — pipeline reset on model switch
14. `test_on_model_select_resets_event_panel` — events cleared on model switch
15. `test_on_model_select_clears_current_job` — currentJobId cleared
16. `test_on_model_select_sets_state_idle` — state reset to idle
17. `test_no_s3_or_path_in_model_display` — no S3/path in model display
18. `test_fetch_decision_no_model_internals` — no coefficients/intercept in decision
19. `test_pr0099b_job_id_identity_preserved` — PR0099B job_id optional arg intact
20. `test_pr0099c_stage_events_preserved` — PR0099C 4 stage events still emitted
21. `test_pr0099c_trace_finalization_preserved` — PR0099C terminal detection intact

### Raw Path/S3 Safety

No S3 keys, bucket names, S3 prefixes, s3:// URIs, filesystem paths, /tmp paths, H5 internals, feature values, coefficients, PHI, raw exceptions, or stack traces exposed in model display or job identity.

### Aramis

Not implemented. Only future-safe identity contract fixed. Aramis will inherit the model-scoped identity model when implemented.
