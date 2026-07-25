# PR0089A Implementation Report — Model-Scoped Demo Job History

## Observed Bug

When a user selects one Bremen model, runs control data, and gets reports,
then switches to another Bremen model, previous jobs/reports from the first
model remained visible under the second model. Reports are model-specific
outputs and must be scoped to the model that generated them.

## Root Cause

1. `list_analysis_jobs()` in `job_api_handler.py` returned all jobs without
   any `model_id` filtering.
2. `handle_jobs_list()` did not parse query parameters from the request URL.
3. The Control Room JavaScript `loadJobHistory()` fetched `/demo/api/jobs`
   without passing the currently selected `model_id`.
4. `onModelSelect()` did not refresh job history when the model selection changed.

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `src/bremen/api/job_api_handler.py` | Added model_id/workflow_id filtering to `list_analysis_jobs()` and query param parsing to `handle_jobs_list()` | +49/-5 |
| `src/bremen/control_room_ui.py` | JS: `loadJobHistory()` passes model_id/workflow_id query params; `onModelSelect()` refreshes history; `loadModelCatalog()` refreshes history after model resolves | +10/-3 |
| `docs/api_contract.md` | Documented `GET /demo/api/jobs` query parameters (model_id, workflow_id) and safety rules | +48 |
| `tests/test_bremen_api_server.py` | 9 new tests in `TestPR0089AModelScopedJobHistory` | +152 |

## API Behavior

- `GET /demo/api/jobs?model_id=<id>` — returns only jobs with matching model_id
- `GET /demo/api/jobs?workflow_id=bremen&model_id=<id>` — combines filters
- `GET /demo/api/jobs` (no params) — preserves existing unfiltered behavior
- Unknown/invalid `model_id` returns empty list (no 400 error)
- Server-side filtering only (no client-side fallback needed)

## UI Behavior

- Control Room `loadJobHistory()` now passes `selectedModelId` and
  `selectedModelWorkflowId` as query parameters
- `onModelSelect()` triggers `loadJobHistory()` after model change
- `loadModelCatalog()` triggers `loadJobHistory()` after model resolution
- Switching selected model immediately filters job history

## Report Truthfulness

- Report page (`report_ui.py`) already displays `model_id` from
  `job.input_summary.model_id` — shows the job's actual model identity,
  not the currently selected model. No change needed.

## Tests Added (9)

1. `test_jobs_store_model_id` — Jobs store model_id in input_summary
2. `test_filter_by_model_id_a` — filter to model A only
3. `test_filter_by_model_id_b` — filter to model B only
4. `test_combined_filters` — combined workflow_id + model_id filter
5. `test_no_filter_preserves_behavior` — unfiltered returns all
6. `test_unknown_model_id_empty` — unknown model_id returns empty
7. `test_jobs_response_no_prohibited_fields` — no checksum/S3/manifest_key
8. `test_control_room_html_has_model_scoped_js` — JS includes model_id params
9. `test_api_jobs_with_model_id_query` — server accepts query params

## Validation

```
python -m compileall src tests — passed
python -m pytest -q tests/test_bremen_api_server.py -v — 104 passed
python -m pytest -q tests/test_catalog_api_multi_model.py -v — 20 passed
python -m pytest -q tests/test_bremen_demo_ui.py -v — 61 passed
python -m pytest -q — 2019 passed, 11 skipped, 28 warnings
git diff --check — clean
```

## Safety

- No `model_checksum` exposed in UI files
- No `s3://`, `manifest_key`, `AccessDenied` in changed UI files
- No `urllib` import added (query params parsed manually to pass import safety tests)
- All 2019 tests pass including pre-existing test suites

## Non-Goals Confirmed

- No model catalog discovery changes
- No inference changes
- No preprocessing changes
- No model package validation changes
- No thresholds changed
- No decision vocabulary changed
- No scientific report content changed
- No authentication added
- No jobs deleted
- No Aramis work
- No Docker/AWS/private artifacts

## Rollback

Revert changes to `job_api_handler.py`, `control_room_ui.py`, `docs/api_contract.md`,
and remove `TestPR0089AModelScopedJobHistory` from `test_bremen_api_server.py`.
