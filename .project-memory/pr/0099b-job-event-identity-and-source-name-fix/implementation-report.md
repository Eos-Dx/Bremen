# Implementation Report — PR0099b: Job event identity, source display-name, padding fix

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/workflow_orchestrator.py` | Added optional `job_id` parameter to `run_workflow_request()` |
| `src/bremen/api/job_api_handler.py` | Pass `job_id=job_id` in `create_analysis_job()`; derive safe display name from source_id/upload_id |
| `src/bremen/control_room_ui.py` | Decision card padding: increased left breathing room |
| `tests/test_bremen_control_room.py` | Added 8 PR0099b tests |

## Important Correction

Control Room Analyze uses POST /demo/api/jobs (not /demo/api/h5/analyze). The old handler `_handle_demo_h5_analyze()` was NOT modified.

## Bug 1 — Job ID Mismatch Root Cause

`run_workflow_request()` generated its own internal `job_id` via `str(uuid.uuid4())`, while `create_analysis_job()` generated a different external `job_id`. Control Room polled `/demo/api/jobs/{external_job_id}/events` but runtime events were stored under the internal job_id.

## run_workflow_request Optional Job_id Change

Added `job_id: str | None = None` keyword-only parameter. Changed `job_id = str(uuid.uuid4())` to `job_id = job_id or str(uuid.uuid4())`. When provided, the caller's job_id is used for all event emission. When None, a fresh UUID is generated (backward compatible).

## create_analysis_job Call-site Changes

Both `run_workflow_request()` calls inside `create_analysis_job()` now pass `job_id=job_id`, using the same job_id that the job record was registered under.

## Backward Compatibility

Existing callers of `run_workflow_request()` without `job_id` continue to work unchanged. `app.py`, `inference_handler.py`, and `server.py` call sites were NOT modified — the parameter is optional with default None.

## Source_id/Upload_id Display Name Root Cause

`handle_jobs_create()` parsed `container_id = body.get("container_id", "")` but the UI sends `source_id` or `upload_id`, not `container_id`. So `container_id` was always empty. `list_analysis_jobs()` fell back to "Unknown".

## Effective Source Display Logic

In `handle_jobs_create()`, after parsing source_id/upload_id/container_id:
- `effective_container_id = container_id` (initial default)
- If source_id provided: derive safe basename by splitting on "/" and taking last segment
- If upload_id provided: look up staged upload registry for filename
- Pass `effective_container_id` to `create_analysis_job(container_id=...)`

## Job History Unknown Fix

`list_analysis_jobs()` now receives a non-empty `container_id` (the safe display name) via `effective_container_id`. The existing fallback chain `filename or container_id or "Unknown"` now resolves to the display name.

## Raw Path/S3 Safety

Display name derivation strips path separators and prefixes. No s3://, /tmp/, bucket names, or raw filesystem paths appear in the effective display identifier. Verified by test assertion.

## Decision Card Padding Token

Changed `.cr-decision-card` padding from `var(--sp-16) var(--sp-20)` to `var(--sp-16) var(--sp-20) var(--sp-16) var(--sp-24)` using existing `--sp-24` token for larger left breathing room next to the colored rail.

## Tests Added

8 new tests in TestPR0099bJobIdentityFix:
1. run_workflow_request accepts optional job_id
2. run_workflow_request without job_id still works
3. create_analysis_job passes job_id into run_workflow_request
4. handle_jobs_create derives effective_container_id
5. handle_jobs_create derives from source_id
6. Source display no s3/path exposure
7. Decision card left padding increased
8. Decision card four-value padding

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_control_room.py` | 113 passed |
| `pytest` (full suite) | 2313 passed, 11 skipped, 0 failed |
| job_id parameter in run_workflow_request | CONFIRMED |
| job_id=job_id in both create_analysis_job calls | CONFIRMED |
| effective_container_id logic exists | CONFIRMED |
| No s3:///tmp/ in display derivation | CONFIRMED |
| Decision card padding var(--sp-24) | CONFIRMED |
| No server.py/app.py/inference_handler.py changed | CONFIRMED |
| git diff --check | Clean |

## Blockers

None.

## Warnings

None.

## Next Required Action

Human review and commit.
