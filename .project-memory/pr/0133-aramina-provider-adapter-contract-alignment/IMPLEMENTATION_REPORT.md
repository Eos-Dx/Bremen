# PR 0133 — Implementation Report: Aramina Provider Adapter Contract Alignment

Date: 2026-09-08
Agent: coder
Mode: implementation
Branch: 0133-aramina-provider-adapter-contract-alignment

## Task Completed

Make Bremen's Aramina adapter match the official Aramina /predict API
contract with the smallest safe change.

## Branch / PR

- Task prompt branch: `0133-aramina-provider-adapter-contract-alignment`
- Actual working branch at implementation time: `0133-polish-aramina-provider-boundary-status`
  (HEAD `8a5bebe`). The task-named branch does not exist locally or
  remotely; implementation was applied to the current working tree.
- Note: the working tree carried pre-existing uncommitted changes from a
  different PR (`execution_trace.py`, `job_api_handler.py`, and the
  `TestAraminaJobSummaryConsistency` tests). These were left untouched.

## Files Changed

1. **`src/bremen/api/workflow_aramina.py`** — MODIFIED
   - Added official Aramina /predict contract constants
     (`_ARAMINA_OFFICIAL_REQUEST_FIELDS`, `_ARAMINA_DEFAULT_ANALYSIS_AUTHOR`,
     `_ARAMINA_ALLOWED_TARGET_SIDES`, `_ARAMINA_SENSITIVE_REPORT_KEYS`).
   - Added `_safe_model_id_env_key(model_id)`.
   - Added `_resolve_aramina_provider_url(model_id="")` — per-model env var
     `BREMEN_ARAMINA_PROVIDER_URL__<SAFE_MODEL_ID>` with fallback to
     `BREMEN_ARAMINA_PROVIDER_URL`.
   - Added `_build_aramina_request_json(...)` — builds the official
     request_json containing only analysis_author, prediction_comment,
     patient_id, target_side. Defaults analysis_author to "Bremen Platform".
     Validates target_side left/right and requires patient_id.
   - Added `_sanitize_report_value(value)` and
     `_normalize_aramina_provider_response(response)` — normalize a raw
     provider response into a safe public report (external_report only,
     never internal_report wholesale, sensitive keys stripped).
   - Added `_post_aramina_predict(...)` — the monkeypatchable HTTP boundary.
   - Modified `_call_aramina_provider(...)` to validate the request, build
     the official request_json, call `_post_aramina_predict`, and normalize
     the response into a safe report.
   - Modified `AraminaWorkflowProvider.__init__` to resolve the provider URL
     from the environment (per-model override first, then base fallback)
     when no explicit provider_url is supplied.
   - Modified `AraminaWorkflowProvider.execute` to merge the safe public
     report into the completed payload.

2. **`src/bremen/api/aramina_provider.py`** — MODIFIED
   - Added a `report: dict[str, Any]` field to `AraminaProviderResult` to
     carry the safe public report from the provider call to the workflow
     payload.

3. **`tests/test_aramina_workflow_runtime.py`** — MODIFIED
   - Added imports for the new helper functions/constants.
   - Updated `test_execute_provider_url_configured_returns_completed` to
     pass a valid `aramina_request` with a patient_id (patient_id is now
     required by the official contract).
   - Added `TestAraminaRequestJson` (6 tests).
   - Added `TestAraminaProviderUrlResolution` (6 tests).
   - Added `TestAraminaProviderCallContract` (6 tests).

4. **`.project-memory/pr/0133-aramina-provider-adapter-contract-alignment/IMPLEMENTATION_REPORT.md`** — CREATED
   - This report.

## Implementation Summary

The Aramina workflow adapter now builds the official Aramina /predict
request_json (only analysis_author, prediction_comment, patient_id,
target_side), defaults analysis_author to "Bremen Platform", validates
target_side left/right, and fails safely before any provider call when
patient_id is missing. Provider URL resolution now supports an optional
per-model env var (`BREMEN_ARAMINA_PROVIDER_URL__<SAFE_MODEL_ID>`) while
keeping the existing `BREMEN_ARAMINA_PROVIDER_URL` fallback. The HTTP
boundary is isolated in a small monkeypatchable function
(`_post_aramina_predict`); no real network is required in tests and no
model.joblib is loaded or vendored in Bremen. Provider responses are
normalized so the public payload exposes external_report but never
internal_report wholesale, and never exposes artifact_sha256 /
model_checksum / path / S3 / token / ticket / traceback. No
probability/TRA/decision fields are invented when absent.

## Key Decisions Made During Implementation

- Added a `report` field to `AraminaProviderResult` (in `aramina_provider.py`)
  so the normalized safe report can flow from `_call_aramina_provider` to
  `execute`'s payload. This was the smallest change that avoided changing
  `_call_aramina_provider`'s return type.
- `_post_aramina_predict` returns a safe placeholder response when not
  monkeypatched (no real network call), preserving the prior "returns a
  demo result when provider_url is present" behavior.
- `_call_aramina_provider` checks provider_url first (safe "not configured"
  failure), then builds/validates the request_json (patient_id / target_side
  validation happens before the provider HTTP call).
- The existing test `test_execute_provider_url_configured_returns_completed`
  was updated to supply a patient_id because the official contract now
  requires patient_id; calling execute without one correctly fails.

## Deviations From PLAN.md

No PLAN.md exists for this PR in `.project-memory/pr/`. The task prompt was
treated as the implementation contract. No deviations from the task prompt.

## Warnings / Unresolved Questions

- The working tree carried pre-existing uncommitted changes from a different
  PR (`0133-polish-aramina-provider-boundary-status`): `execution_trace.py`,
  `job_api_handler.py`, and the `TestAraminaJobSummaryConsistency` tests.
  These were left untouched. Two of those tests
  (`test_job_status_matches_overall_status`,
  `test_events_no_workflow_unavailable`) fail for reasons unrelated to this
  PR (a missing `import os` in the test and an H5 layout that does not match
  any recognized container layout). These failures pre-date this PR's
  changes.
- The task-named branch `0133-aramina-provider-adapter-contract-alignment`
  does not exist locally or remotely; implementation was applied to the
  current working tree on `0133-polish-aramina-provider-boundary-status`.

## Validation Commands and Results

All commands run with the project venv (`./venv/bin/python`).

1. `python -m compileall -q src tests` — exit 0 (pass).
2. `pytest -q tests/test_aramina_workflow_runtime.py -k "not TestAraminaJobSummaryConsistency"`
   — 48 passed, 2 deselected (pass). The 2 deselected are the pre-existing
   failing tests from the other PR.
3. `pytest -q tests/test_aramina_provider_contract.py` — 30 passed (pass).
4. `pytest -q` — 3824 passed, 2 failed, 11 skipped. The 2 failures are the
   pre-existing `TestAraminaJobSummaryConsistency` tests from the other PR's
   uncommitted changes (not caused by this PR).

## Safety Checks

- No secrets, credentials, AKIA, SECRET_ACCESS_KEY, dkr.ecr, full s3://,
  raw checksums, Nova_, /Users/, or /home/ patterns introduced.
- No model.joblib loaded or vendored in Bremen.
- No clinical diagnosis wording or claims introduced.
- No probability/TRA/decision fields invented when absent.
- No real network calls required in tests.
- No registry push or secrets introduced.

## Boundaries Preserved

- Bremen workflow behavior unchanged (only the Aramina adapter payload now
  carries the safe external_report).
- Catalog discovery semantics unchanged.
- Auth/ticket behavior unchanged.
- Logging redaction unchanged.
- Real production config unchanged.
- UI unchanged.
- Trace/status polish unchanged (the pre-existing uncommitted changes to
  `execution_trace.py` / `job_api_handler.py` were left untouched).
- No model.joblib loaded/vendored.
- Official request_json fields only (analysis_author, prediction_comment,
  patient_id, target_side).

## Commit Readiness

ready for commit (for the task-named PR scope). The pre-existing uncommitted
changes from the other PR are not part of this PR and were not modified.

## Recommended Next Action

proceed to precommit review for the Aramina provider adapter contract
alignment scope.
