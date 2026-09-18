# PR0162 Precommit Review

## Verdict

READY FOR NEXT 0162 CUT

## Scope reviewed

Verification review against the declared architecture, public-contract freeze and
deletion evidence. Inputs read: PR0162 PLAN.md, BASELINE.md,
ARCHITECTURE_DECISIONS.md, DELETION_LEDGER.md, METRICS.md, FILE_CHANGES.md,
IMPLEMENTATION_REPORT.md. Diff vs BASE `dc6e99d` (= merge-base with main;
120 tracked files: 89 M + 31 D) plus 41 untracked new source/test files. Files
inspected directly: platform/runtime/{executor,registry}.py,
platform/sources/{binding,legacy_input}.py (full), platform/jobs/{values,service}
, platform/reports/{service,runtime_projection}, platform/app+routers
(inventory), api/{server,inference_handler,report_bremen,job_models,lifecycle_contracts}.py,
contracts/{model_runtime,canonical_input,execution,request,legacy_errors},
moved package files, bremen_v01/{runtime,features} diffs, and
tests/test_platform_architecture_pr0162.py. Untracked
`results/`, `alexey-smoke-pack-0157/` excluded per instructions.

## Contract verification

PASS:
- routes — live `create_app()` inventory = 29 method/path pairs, 27 unique paths,
  byte-equal to `public_routes.json` baseline (reviewer script +
  `test_all_public_routes_equal_baseline`); no `/reports/{workflow_id}/standard-result`
  exists anywhere in src/scripts/tests.
- auth — auth/token/refresh/ticket/SSE suites pass
  (`test_bremen_fastapi_auth_enforcement.py` 100s of cases in focused run;
  auth_activation_readiness passes in full run); no auth-boundary file changed semantics.
- jobs — POST/GET jobs + duplicate/replay/concurrency characterization retained
  (full suite green); legacy http.server delegates jobs to the same services
  (`api/server.py:1783-1801,1941-1942` imports from `platform.api.legacy_jobs`).
- reports — report characterization suites pass; success envelopes verified against
  baseline `public_results.json` (exact-match test) and golden suites (85 passed).
- standard_result — additive field only, in its existing location;
  `report.payload.risk_score`/`technical_demo_only` retained
  (`platform/reports/service.py:73,101`); no field removed/renamed/moved/type-changed.
- events/SSE — `test_bremen_event_stream.py` + phase4 streaming suites pass;
  event ordering/fields asserted against real execution
  (`test_bremen_event_fields_and_order_survive_provider_removal`).
- safe failures — PR0161 failure-projection suite, auth no-traceback/no-secret
  suites, and `test_failure_event_keeps_registered_safe_reason` pass; adversarial
  path/token strings asserted absent from events and reports.

## Architecture verification

PASS:
- generic executor — `platform/runtime/executor.py` has zero
  bremen/aramina comparisons (AST test + reviewer grep: the only `"bremen"` at
  :216 is the `run_workflow_request` default workflow argument, no
  `build_features(`/`run_inference(`); flow = descriptor → source_checksum →
  validate_model_input → predict_model → descriptor.project; binding and
  legacy-input are descriptor policies, not executor branches.
- ModelRuntime boundary — `contracts/model_runtime.py` is neutral (import-
  direction test forbids api/platform/model_packages/fastapi in contracts).
- no WorkflowProvider execution — symbols exist only in one docstring
  (`contracts/model_runtime.py:235`); ABC file deleted.
- no WorkflowRuntimePlugin execution — same; only `platform/events_trace.py`
  functions retained; obsolete stage-class tests retired per ledger.
- model-package dependency direction — grep `from bremen.(api|platform)` in
  model_packages → only a historical comment (`aramina_v0213/inference.py:46`);
  `test_import_direction` AST-enforces it continuously.
- source binding ownership — `platform/sources/binding.py` owns checksum +
  patient identity (same checks as PR0160's `_validate_aramina_source`,
  invoked via `descriptor.bind_patient=True` before package execution); no
  silent removal.
- legacy canonical path isolation — `sources/legacy_input.py` +
  `legacy_layouts.py` (moved h5_layouts) isolate Aramina/integrated-profile QC
  exactly as the accepted decision states; raw-capable Bremen bypasses it
  (`legacy_input=not runtime.requires_raw_container`), tested.

## Scientific parity

PASS:
- Bremen — package feature/runtime diffs are import-path/docstring-only
  (`decision_contract`→package `decision`, `bremen.model_runtime`→
  `contracts.model_runtime`); moved `model_runtime.py`/`canonical_input.py`/
  `decision.py` are content-identical to baseline except one docstring line
  and blank lines (diffed). Parity suites: `test_bremen_3x3_runtime_parity`,
  `test_bremen_model_package_deduplication`, `test_bremen_v01_package`,
  PR0160 raw-ownership suite all pass (focused 443 passed overall).
- Aramina — `test_aramina_v0213_package` + `test_aramina_workflow_runtime`
  pass unchanged expectations; deleted `api/preprocessing_bridge` math had no
  production computation caller (only constants/error categories, retained in
  `contracts/legacy_errors.py`; verified by grep + green suites). No
  validation/QC step bypassed: Aramina canonical QC preserved via the
  documented legacy adapter.

## Deletion verification

Checked disposition (all: no live src/scripts import — repo-wide grep returned
only a comment and retained-file `api/job_models.py` which was never deleted):
workflow_provider, workflow_registry, workflow_orchestrator, workflow_bremen,
workflow_aramina, workflow_aramina_scaffold, aramina_provider,
aramina_artifact_compat, aramina_preprocessing, aramina_symmetry,
report_aramina, runtime_plugin, preprocessing_bridge, fastapi_app,
job_api_handler, decision_contract (moved), h5_layouts (moved),
symmetry_signals (moved), xrd_normalization, model_runtime (moved),
canonical_input (moved), bremen_features, bremen_runtime, inference.
Removed lifecycle dataclasses (PreparedArtifact/PreparedWorkflowInput/FeatureSet/
FeatureValidation/ModelOutput/OutputValidation/DecisionOutput): zero code
references anywhere in src/scripts (docstring mention only);
`ExecutionStage`/`ExecutionTraceSummary` retained and consumed. Retired test
files all target deleted internal abstractions with retained-file replacements
named in FILE_CHANGES/ledger (third-runtime selection, PR0162 event tests).
No external behavior disappeared: route/result snapshots match baseline.

## Validation

```
git status --short                    → 129 lines; staging empty (git diff --cached: 0 files)
BASE=dc6e99d (=merge-base HEAD main); git diff --check "$BASE" → exit 0
git diff --name-status "$BASE"        → 120 files (89 M + 31 D) — exact match vs
                                         FILE_CHANGES Modified (89) and Deleted+Moved
git ls-files -o (filtered)            → 41 new src/test files = FILE_CHANGES Created
                                         minus 5 move destinations (listed under Moved)
python -m compileall -q src tests     → exit 0
pytest -q tests/test_platform_architecture_pr0162.py → 10 passed
focused suite (8 files, step 8)       → 443 passed, 867 warnings, 4.45s
pytest --collect-only -q              → 4248 collected  (matches reported 4248)
pytest -q --durations=100             → 4237 passed, 11 skipped, 1678 warnings, 22.23s
                                         (matches reported 4237/11; faster than the
                                         report's 34.76s — timing variance allowed)
ruff check <all new platform/contracts/test files> → All checks passed
ruff <moved package modules>          → 2×E741 only (pre-existing in baseline
                                         api/symmetry_signals.py:174,177; move also
                                         deleted 2 unused imports → F401 count reduced)
route inventory live check            → 29 pairs / 27 paths == public_routes.json
11 skips enumerated: all opt-in private-evidence/smoke env-var skips (identical
families to baseline's 13 minus 2 retired bridge-test skips).
```

Git hygiene: nothing staged; HEAD == BASE (no commit made by coder);
`results/`, `alexey-smoke-pack-0157/` untouched and untracked; `.gitignore`
change is the documented `src/bremen/platform/reports/` un-ignore (source code,
not generated output); no binary/private artifacts in the diff.

## Blocking findings

None.

## Follow-up, non-blocking

1. `src/bremen/platform/jobs/{service,repository}.py` and
   `platform/reports/service.py` import `bremen.api.job_models`
   (service.py:17, repository.py:3, reports/service.py:7) — data models still
   live under `api/` while services live under `platform/`; move in a later cut.
2. Post-change full-suite warning count is 1678 vs baseline 1676; the two
   additions are sklearn "X has feature names" UserWarnings from existing
   synthetic-package paths (observed in focused run), not contract drift.
3. `api/inference_handler.py` retains the `workflow_id="bremen"` default in the
   legacy transport translation signature — harmless carryover now that the
   executor is generic.
4. Moved `bremen_v01/symmetry_signals.py` keeps 2 inherited E741 (`l`) names
   (baseline debt, documented in METRICS.md).

## Final conclusion

The branch is safe to continue: the declared BEFORE/AFTER execution chain is
materially real — provider/plugin execution interfaces are gone with zero live
references, one descriptor-driven executor performs no model-specific science
(AST-enforced, plus a third-runtime proof), model packages import neither api
nor platform, source integrity/patient binding and the intentionally isolated
Aramina canonical QC are preserved, every deletion has an audited replacement,
the complete public route/report/event/auth contract matches the frozen
baselines byte-for-byte, scientific parity suites pass, lint regressed only by
reduction, and full validation (4248 collected, 4237 passed, 11 documented
opt-in skips) is reproduced independently. Only cosmetic, explicitly-scoped
follow-ups remain for later 0162 cuts.

READY FOR NEXT 0162 CUT
