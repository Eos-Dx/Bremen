# PR0163 Independent Review — 0163-fix-validation-traces-and-standard-result-contract

Base: `8230700` (main). Working tree: 9 modified production/test files + new
`tests/test_pr0163_orchestration.py` (228 lines, untracked) + 2 new docs
(`production-contracts-2026-09-18.md`, `pre-demo-checklist-2026-09-18.md`).
`git diff HEAD --check` clean. Reviewer modified nothing; no staging/branch changes.

## VERDICT: CHANGES REQUIRED

---

## Blocking findings

### B1. Full test suite fails — retained test invalidated by the trace rewrite

- File: `tests/test_bremen_control_room.py:1217-1224`
  (`TestAppendixAModelReportBinding::test_pr0099c_trace_finalization_preserved`)
- Behavior: asserts `'terminal_event_types' in inspect.getsource(build_trace_from_events)`;
  the PR0163 rewrite of `src/bremen/platform/events/trace.py` removed that token
  (present twice at base). Test fails: `AssertionError`.
- Why it breaks contract: this is a retained characterization test (not deleted or
  updated in the diff); the branch leaves the repository red. Reproduction:
  `./venv/bin/python -m pytest -q` → **1 failed, 3974 passed, 8 skipped**
  (only this test fails; it passes at base).
- Smallest fix: update the test to assert the new terminal-detection behavior
  (e.g. `terminal`/`runtime.workflow.completed` handling and
  `test_aramina_preflight_execution_parity_without_persistence`'s trace status
  assertions), or restore an equivalently meaningful guard. One test edit, no
  production change.

---

## Non-blocking findings

### N1. Concurrent submissions of the same upload/h5_path/container identity race

- Files: `src/bremen/api/http/routers/jobs.py:195-197` (`source_key = source_checksum(h5_path)`
  assigned inside the try block, *after* `resolve_source`/`extract_patient_display_name`) and
  `jobs.py:221` (`patient_id=body_dict.get("patient_id") or patient_display_name`).
- Behavior: if the duplicate arrives while the first request is still staging/extracting, the
  second computes `source_key=''` (upload path — never replaced by checksum because the key is
  pre-set) or `patient_id=''`, so `submit_analysis_job` identity mismatches and both jobs execute.
  Impact window is upload-based submissions and slow first-time extraction; the primary demo flow
  (`source_id` → stable key, registry patient name) is protected because both components are
  computed before submission. Atomic for the guarded path (verified: 16 concurrent maps → 1 job,
  1 executor task).
- Suggested later: resolve+checksum before the reservation section and reuse
  `aramina_request.patient_id`/registry info as single source of identity.

### N2. Reused job carries first-request metadata (by design)

`submit_analysis_job` explicitly excludes author/comment from identity; a replay with a different
`analysis_author`/`prediction_comment` silently keeps the first job's values in `standard_result`.
Documented in the docstring; consider surfacing in the reuse response in a future cut.

### N3. `patient_id` key now present in `job.input_summary`

New key inside `job.to_dict()` responses (additive dict key). Existing suites pass; confirm no
consumer pins the exact input_summary key set outside the repo (Alexey client).

### N4. Source consumption contract change at HTTP boundary

`POST /jobs` now resolves with `consume=False`; a source_id/upload_id can be submitted multiple
times (idempotently). This is required for the replay fix and is coherent, but it removes the
one-shot upload guard; expiry/GC still applies. Note for the ops runbook.

### N5. Executor failure event adds `failure_stage`/`reason_code` to `runtime.workflow.failed` details

Event payloads now carry two extra keys where `descriptor.failure_event_reason` is set; values come
from the safe public error taxonomy only (`ARAMINA_UNSUPPORTED_INPUT`, …), no raw exception text.
`test_failure_event_keeps_registered_safe_reason` (PR0162 suite) still passes.

---

## Scientific-change audit — PASS (no science in diff)

`git diff HEAD --name-only | grep -E "model_packages|features|predictor|preprocess|symmetry|legacy_layouts|contracts/"`
→ zero matches. No thresholds, gates, coefficients, features, preprocessing, artifacts, or
interpretation files touched. Package import/refactor behavior unchanged. Bremen model_name
metadata item: no diff, correctly left to package-owned verification (§13 of the contracts doc
remains open, not fabricated here).

## Idempotency audit — PASS for the documented model, with N1 caveat

Identity = (stable `source_key`, workflow_id, model_id, patient_id, target_side) — not ephemeral
`source_id` (stable key derived from bucket:key:version; distinct `source_id` handles for the same
version share it, a new S3 version changes it — `test_source_identity_stable_across_handles_but_versioned`).
Matrix proven by `test_atomic_identity_and_dimensions`: same request ⇒ same job_id; left vs right ⇒
distinct; different model_id ⇒ distinct; new source version ⇒ distinct; different patient ⇒ distinct.
16 concurrent identical submits under a real ThreadPoolExecutor create exactly one job and one
scheduled task; reservation under `_submission_lock` + `_jobs_lock` (no TOCTOU). Completed replay ⇒
HTTP 200 + `reused_existing=true` + same job_id + report retrievable. Running replay ⇒ 200 + same
job_id, no duplicate executor (`test_http_returns_while_real_background_worker_blocked`). Legacy 409
guard removed; old frontend still recovers job_id from a 409 body (transitional line retained).

## Async audit — PASS (with documented process-local limit)

POST path returns after resolve + identity check + job reservation; `_executor.submit` schedules
execution (`ThreadPoolExecutor(max_workers=2)`), HTTP response asserts `overall_status=="queued"`
before the worker is released (real-worker blocked-thread test). Lifecycle queued→running→
completed/failed verified; submit-scheduling failure and worker crash both terminate as
`failed`/`JOB_EXECUTION_FAILED` without leaking exception text
(`test_scheduling_and_worker_failure_become_terminal`). Docstring and IMPLEMENTATION wording
explicitly state "process-local; no durable queue is claimed" — honest. Sync callers (tests, CLI
`background=False`) retain the old synchronous contract. Report retrieval during queued/running
returns an explicit `WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED`-style unavailable envelope
(pre-existing behavior, no silent race). 201 for new / 200 for reuse matches the task's target
contract. Caveat: in-flight jobs are lost on process restart (consistent with the process-local
repository already documented).

## Frontend patient identity — PASS

Catalog: `display_name` is now the filename and `patient_display_name` a distinct field, seeded
from the S3 item when present, otherwise from H5 extraction (never from filename text; no
`cancer/benign/atypical` parsing and no stable-key→patient table anywhere — grep-verified), and
back-into-registry via `update_source_display_name` so `get_source_info`/stable entries expose it.
UI label: `patient_display_name || display_name || source_id` (`control_room_ui.py:315`). Jobs
route falls back to registry `patient_display_name` when extraction is empty. `Nova_257` +
`atypical_one_patient.h5` renders `Nova_257`.

## Aramina preflight — PASS (contract level)

`run_model_pipeline_dry_run` now runs the identical production path: `get_descriptor_for_model` →
`_single_runtime_registry` → `run_workflow_request` with `patient_id`/`target_side`/parameters,
`consume=False`, no persistence/reports/events (test asserts `jobs._jobs` empty), and failure stage
taken from the real `wf_result.failure_stage` (e.g. `preprocessing_contract`) plus
`failure_reason_code=ARAMINA_UNSUPPORTED_INPUT`. No second preprocessing implementation exists in
platform/API. Parity test parametrizes 0.2.12/0.2.13 × pass/fail; the real patients Nova_257/
Nova_384 classification depends on the package runtime, which production smoke already proved —
same code path is now shared, so the pre-existing 32/32 false negatives (dry-run previously lacked
patient/side and misclassified stage as `model_execution`) are structurally eliminated.

## Trace projection — PASS

Rewritten from event-recorded evidence: no stage is invented without an event; completed Aramina
jobs project `status=completed`, `completed_stage_count>0`, real wall duration (from
`runtime.request.completed`), correct `current_stage=report_completed`; failed jobs project
`status=failed` at the actual failing stage (e.g. `preprocessing_contract`) with safe `reason_code`
and the failed stage marked `failed` (asserted, not fixture-only). Bremen keeps its canonical stage
order plus recorded stages. Resolved-but-failed sibling events no longer masquerade as readiness
traces. Only B1 (stale source-token test) is red.

## Report contract — PASS

`report.standard_result` remains a bare object for both workflows (asserts `'aramina' not in
standard` / `'bremen' not in standard` in `test_http_queued_completed_reuse_and_bare_report`);
`payload.risk_score`/`technical_demo_only` intact for Aramina; Bremen `payload.report_type`/
`score_and_threshold.p_mri_needed` intact; Aramina `specific_output.target_side` preserved; no
`/standard-result` route introduced (route inventory unchanged; full FastAPI parity suites pass).

## Test suite results (run by reviewer on current tree)

- `python -m compileall -q src tests` → OK
- `pytest -q tests/test_pr0163_orchestration.py` → 10 passed (deterministic event/latch sync, real
  concurrency, no sleeps; covers every behavior in objective 9 except the two demo-data preflight
  rows, which require private H5 fixtures and are gated by the same parametrized parity test)
- `pytest -q tests/test_platform_architecture_pr0162.py tests/test_bremen_fastapi_jobs_report_parity.py tests/test_bremen_fastapi_phase3_write_routes.py` → 73 passed
- `pytest -q` (full) → **1 failed**, 3974 passed, 8 skipped, 653 warnings (B1 only)

## Documentation review — PASS

`docs/production-contracts-2026-09-18.md` separates verified production behavior (409 replay
BEFORE) from target behavior (AFTER 200 + `reused_existing`), labels the matrix items not fully
re-executed, and makes no false async-durability claim. The branch implements the AFTER
contract. Minor: checklist item "Bremen model_name verified from package-owned metadata" is
correctly still open — do not close it without package evidence.

## Demo blockers remaining

1. B1 — red test must be fixed/updated before merge (blocks CI gate).
2. Re-run the §17 acceptance gate against live demo data after merging B1 fix, especially the
   Nova_257 preflight PASS rows on the deployed build (unit parity is in place; production
   confirmation is a demo gate, not a code defect).

Everything else in the branch is contract-correct with meaningful, deterministic regression tests.

**VERDICT: CHANGES REQUIRED**
