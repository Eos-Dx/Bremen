# PR0156 Pre-Commit Review — Model Package Standard v1

## Scope reviewed
Branch `0156-model-package-standard-v1`, HEAD `e361feab04e5f800bf89ebbda8aa62fd60296528`
(verified; `main` == HEAD, so the review diff is the working tree vs main:
12 modified files, 1 deletion, 4 new production modules + 2 doc files + 4 new test
files + PR memory). All changed files read completely. Source-of-truth set read:
`docs/model_runtime_contract_v1.md` (incl. PR0156 update), `docs/adr/0016` (Accepted,
unmodified), `docs/bremen_3x3_training_parity.md` (unmodified), PR0154 package
docs/review evidence, PR0155 `docs/mlflow_model_packaging_spike.md` (note appended
only), new `docs/model_package_standard_v1.md` + `docs/adr/0017-model-package-standard-
v1.md`, PLAN.md, IMPLEMENTATION_REPORT.txt — every claim below independently verified
against the code, not taken from the report.

## Architecture findings
The required chain now exists in production code for both models:

    Bremen Platform (api/*)
      → bremen.model_runtime.ModelRuntime (contract v1, stdlib-only leaf)
        → package public entry points
          bremen.model_packages.bremen_v01          (Bremen v0.1, PR0154)
          bremen.model_packages.aramina_v0213       (Aramina v0.2.13, NEW)
            → model-owned scientific inference

`api/workflow_aramina.py` shrank 1006 → 191 lines and is now the orchestration
provider plus a transitional re-export surface; every scientific symbol resolves to
the package (identity re-exports). `api/aramina_preprocessing.py`,
`api/aramina_symmetry.py`, `api/aramina_artifact_compat.py` are zero-logic shims;
`api/aramina_preprocess_worker.py` was **deleted** (moved into the package; grep
proves no remaining importer; the worker path is resolved via
`Path(__file__).with_name` inside the package). `api/xrd_normalization.py` re-exports
the canonical vocabulary from the new neutral `bremen/canonical_input.py` (verified
`is`-identity for types, validator and error class); the platform-side canonical
surface is unchanged for its ~dozens of existing importers.

## Model Package Standard assessment
`docs/model_package_standard_v1.md` + ADR-0017 define one framework-independent,
**structural** standard (no `ModelPackageBase`, no inheritance framework, no second
runtime interface — `ModelRuntime` remains the only runtime contract). It assigns
single authoritative ownership for: identity, requirements, input validation,
runtime entry point, artifact interpretation, complete inference,
threshold/postprocessing, safe diagnostics, provenance, golden evidence, and a
standalone-packaging dependency boundary — exactly the task's categories. MLflow is
positioned as a future packaging mechanism wrapping a conforming package
(`docs/mlflow_model_packaging_spike.md` note; ADR-0017 "Framework position");
`grep mlflow|bentoml|kserve` in the model packages and all inference paths → none
(the only `mlflow_tracking.py` is pre-existing offline training tooling, untouched).
Conformance is enforced in production code by tests:
`test_bremen_model_package_standard_v1.py` (parametrized over BOTH packages: contract
satisfaction, requirements, validation, prediction, manifest presence, forbidden
import absence, provider-routes-through-package-runtime with exact module-path
assertion), `test_bremen_model_package_deduplication.py` (single authoritative
definitions for 7 scientific symbols + zero-logic shims + reverse-import guards for
both packages), `test_bremen_api_freeze_pr0156.py` (HTTP freeze). This is not
cosmetic renaming: the Aramina science physically moved and its provider no longer
computes anything scientific.

## Bremen ownership assessment
**PASS — unchanged and inference-complete.** Bremen diff vs main is one import
retarget in `model_packages/bremen_v01/runtime.py`
(`api.xrd_normalization` → neutral `bremen.canonical_input`, same object identity)
plus its docstring. `features.py`, `predictor.py`, `manifest.py` untouched.
Exactly one active Bremen production scientific implementation (dedup test +
grep: `build_bremen_features`, `predict_proba_portable`, `validate_bremen_shape`
defined only in the package; `bremen_features.py`/`inference.py`/`bremen_runtime.py`
shims contain zero defs — AST-tested). No scientific logic in `workflow_bremen.py`,
registry, report, or API code (workflow_bremen.py not even modified by this PR).

## Bremen parity evidence
- Direct package golden suite `test_bremen_v01_package.py` → **50 passed**: 15 frozen
  features (atol 1e-10, rtol 0), golden probability **0.7388733541967353**, threshold
  `0.3585907282566089`, decision parity — all without WorkflowProvider.
- PR0151/PR0152/PR0154 parity + workflow + plugin + contract → **207 passed**:
  exact 3 LEFT + 3 RIGHT, all-six participation (frozen mutation vectors),
  q-grid/interpolation behavior, Savitzky–Golay smoothing, p05 normalization,
  **ddof=1** replicate variance (identical-replicate sigma→0 vs reference),
  per-measurement raw peak semantics + gate, LEFT/RIGHT permutation invariance
  (12 cases), portable estimator parity, threshold parity, raw-H5 production-path
  parity, 9 invalid shapes failing closed before science.
- `python -c` identity check confirmed the canonical-vocabulary re-export is
  object-identical, so the retarget cannot alter validation behavior.

## Aramina ownership assessment
**PASS — the critical item.** The authoritative Aramina model package now lives at
`src/bremen/model_packages/aramina_v0213/` and owns ALL current model-specific
scientific execution, mechanically verified as **verbatim moves** (AST structural
diff vs HEAD, docstrings stripped):
- `preprocessing.py`, `symmetry.py`, `artifact_compat.py`,
  `aramina_preprocess_worker.py` — `differing=NONE, added=NONE` vs their HEAD api
  counterparts.
- `inference.py` — artifact load/validate, target-side selection + QC, profile
  matrix, LR1 scoring, logit aggregation, symmetry call, final feature assembly,
  final model execution, model-owned threshold, report payload,
  `_build_aramina_request_json`: identical bodies; the only deltas are
  `RegistryModelEntry` → `Any` annotations (platform type decoupling), import
  retargets to package modules, and the two documented platform seams (below).
- `errors.py` — `AraminaWorkflowError` (init identical), `_SAFE_FAILURES`,
  `FAILURE_STAGES`, `_STAGE_REMEDIATION`, `_STAGE_DETAIL`, trace allowlists: all 15
  constant values verified equal to HEAD (including `_TRACE_LABELS`, which now
  composes `manifest.FINAL_FEATURE_COLUMNS` — value-identical).
- `trace.py` — diagnostics verbatim (only the private logger name reflects the new
  module path; no test or public contract references it).
- `manifest.py` — ARTIFACT_TYPE/ARTIFACT_KIND, allowed preprocessing releases,
  request fields, target-side semantics, final feature columns, notes, dependencies.
- `runtime.py` — `AraminaRuntime` moved; requirements assembled from manifest +
  entry identity (all values verified equal to PR0153B); validation identical;
  `predict_model` composes `inference._run_local_artifact` unchanged and propagates
  `AraminaWorkflowError` unchanged.
`workflow_aramina.py` (provider) performs no preprocessing, feature, aggregation,
scaler/estimator or threshold work — only `ModelInput` construction, delegation to
the package runtime, and the byte-identical `WorkflowResult` envelope translation
(code / failure_stage / preprocessing_diagnostic rules unchanged).

## Aramina parity evidence
- `test_aramina_workflow_runtime.py` → **238 passed** (unchanged count): target_side
  semantics (explicit, lowercase-normalized, never inferred), left/right and
  contralateral processing, symmetry metrics (v0.1 legacy + v0.2 contracts),
  preprocessing release selection/env gates, worker protocol and safe diagnostics,
  LR1 output validation, logit aggregation, final feature ordering, threshold/decision
  boundary, full `ARAMINA_*` failure taxonomy with stage mapping, no-leak guarantees,
  report payloads.
- `test_aramina_provider_contract.py` + `test_bremen_workflow_aramina_scaffold.py` →
  **43 passed**. Aramina total 282, unchanged.
- New direct package suite `test_aramina_v0213_package.py` → **21 passed**: real
  sklearn estimators + real checksum-verified joblib artifacts generated in tmp_path;
  **direct package prediction matches the provider route bit-for-bit**
  (`test_direct_package_prediction_matches_provider_route`); threshold-flip proves
  model-owned threshold ownership; safe-taxonomy leak test with planted sensitive
  text; requirements/validation; import-direction + subprocess isolation.

## Duplicate-science analysis
Explicit searches over production `src/` (dedup test automates 7 of them):
`build_bremen_features`, `predict_proba_portable`, `validate_bremen_shape`,
`symmetry_features`, `preprocess_aramina`, `ensure_compatibility_bridge`,
`load_staged_artifact` — each defined **exactly once** in its authoritative package
module. Additionally `_run_local_artifact`, `_prepare_features`,
`_load_selected_artifact`, `_build_aramina_request_json` → only in
`aramina_v0213/inference.py`. Classification of look-alike results:
- `api/aramina_*` shims + `workflow_aramina` re-exports + PR0154 Bremen shims —
  **compatibility re-exports** (zero defs, AST-enforced, identity-tested).
- `bremen.api.s3_model_discovery._load_staged_artifact` — delegator to the single
  bridge body (no second implementation; no test patches it).
- `tests/reference_0151` — test reference (allowed).
- `bremen/training/pipeline.py`, `api/preprocessing_bridge.py` legacy helpers —
  historical/offline-only, outside both inference paths (documented since PR0152).
- `bremen.mlflow_tracking` — offline training tooling, untouched.
**No actual duplicate production scientific implementation exists.**

## Requirements ownership
Package-owned: `bremen_v01/manifest.py` (3+3, six total, request fields) and
`aramina_v0213/manifest.py` (explicit target_side, request fields, allowed sides,
artifact/preprocessing contract). The platform Model Requirements API (untouched)
still derives from `runtime.model_requirements()` via the provider; the additive
`container_requirements.model_runtime` block flows from the runtimes. Search for
duplicated truth: no Bremen 3+3 literals outside `bremen_v01`; Aramina request-field
constants exist only in the Aramina manifest (runtime + shim re-export the same
objects). Aramina hard-coded requirements defaults in `model_requirements.py` remain
as the pre-existing platform defaults for manifest-less rows — unchanged, and equal
to the package declaration (equivalence covered by requirements suite + conformance
tests).

## Identity/provenance analysis
Public model IDs unchanged (registry/catalog entry-driven; `get_provider_for_model`
and `model_registry.py` untouched). One authoritative identity source per package
(`manifest.py`); the former duplicate Bremen constants were already removed in
PR0154. No model-specific threshold constant exists in platform code (grep:
`0.35859…`, `0.41303…` → none in `api/`; applied thresholds come only from loaded
artifacts inside the packages; platform `threshold_value` references are pass-through
plumbing of runtime-produced values).
**Warning:** `aramina_v0213/manifest.MODEL_ID = "aramina-target-brest-risk"` contains
a spelling variant ("brest") that appears nowhere else in the repository (tests and
catalog usage spell it "breast"). It is **not consumed at runtime** (per-selection
`model_id` is entry-driven; grep confirms `manifest.MODEL_ID` is used only by the
Bremen runtime) and no test asserts its value — a provenance-accuracy defect in
reference metadata, recommended for correction before it misleads PR0155 packaging.

## Artifact ownership
Bremen: unchanged (predictor owns `portable_logreg` interpretation incl. nested
metadata adaptation). Aramina: now package-owned — `_load_selected_artifact` /
`_validate_artifact` (kind, single-model, identity, YAMLs, model_info keys,
predict_proba methods, version gate vs entry) moved verbatim into the package; the
platform continues to locate/stage/checksum via the untouched registry/discovery, and
the shared deserialization body moved to the narrow neutral bridge
`bremen.model_packages_bridge.load_staged_artifact` (byte-identical body and error
vocabulary `ValueError("Artifact integrity failed")` / `RuntimeError("Unsupported
artifact")`; `s3_model_discovery._load_staged_artifact` now delegates). Aramina's
existing joblib/sklearn artifact format is retained (no conversion required, per
task).

## Dependency/import analysis
Allowed edges only: platform → `bremen.model_runtime` + package entry points;
packages → `bremen.model_runtime` (types), `bremen.canonical_input` (neutral,
stdlib/numpy), `bremen.model_packages_bridge` (narrow loader, stdlib-only module),
and two documented narrow platform seams: Aramina's lazy
`_validate_aramina_source` default (H5 patient/source identity binding — platform
concern reached for behavior parity; flagged for PR0155 lift) and Bremen's
`api.decision_contract` (platform decision vocabulary; numerical threshold
comparison stays inside the package predictor — classified platform-specific in
ADR-0017). Forbidden imports (workflow providers, job lifecycle, reports, auth,
FastAPI/HTTP, frontend, S3 credentials, public links): **none** — enforced by three
independent mechanisms (AST import tests over every package file, subprocess
import-isolation tests for both entry points, reverse-import guard tests) and by
grep. `model_packages_bridge.py` imports stdlib only. No circular imports
(compileall + full suite; the two seams are lazy or leaf imports). FastAPI request
objects are not used by either runtime; `ModelInput` remains the plain carrier.

## Public compatibility
**Endpoint freeze independently verified:** `git diff --name-only HEAD` contains no
endpoint-defining module (no fastapi/app/server/route/auth/jobs/report files changed
— `model_requirements.py`, `model_registry.py`, `workflow_orchestrator.py`,
`report_aramina.py`, `aramina_api_errors.py`, `fastapi_app.py` all untouched), and
the live FastAPI route table is 29 routes matching the frozen snapshot
(`test_bremen_api_freeze_pr0156.py` → 3 passed; also asserts no
model-package/MLflow/registry route exists and the requirements v1 schema keys are
intact). No request/response schema, auth, status-code, error-code, model_id,
workflow_id, threshold, report, frontend, PDF, or storage behavior change. Failure
reasons remain the established safe constants (`ARAMINA_*` taxonomy byte-identical;
Bremen envelopes untouched). Existing clients require no modification.

## Security findings
No real patient data, private H5, training-repository copies, ZIPs, joblib/pickle
binaries, AWS credentials, tokens or secret values added (status + diff scans). The
worker retains its pre-existing constant `/opt/aramina-preprocess…` paths (moved
verbatim, unchanged). Diagnostics remain allowlisted; new leak tests plant sensitive
text and assert non-leakage through both the Bremen and Aramina error paths.
Subprocess worker invocation semantics unchanged (`-I` isolated mode, timeout,
fixed-safe failure classification).

## MLflow scope
No production MLflow loading, Registry integration, tracking server, aliases,
deployment routing, BentoML or KServe (grep clean in packages and inference paths);
only the spike doc gained a clarifying note. Production science has zero MLflow
dependency.

## Validation commands/results (all executed during this review)
- `python -m compileall -q src tests` → **exit 0**.
- Standard + Aramina package + freeze + dedup suites → **44 passed**.
- Bremen direct golden (50) + PR0151/0152/0154 parity/workflow/plugin/contract
  suites → **207 passed**.
- Aramina runtime/provider/scaffold → **282 passed**.
- Requirements + inference integration + job handler + catalog multi-model +
  registry + multi-model + training-runtime separation + S3 discovery + model
  registry → **289 passed, 1 skipped**.
- Job/report/decision/HTML-route suites → **107 passed**.
- Full `pytest -q` → **4248 passed, 11 skipped, 0 xfailed** (44.22s, exit 0;
  4248+11 = 4259 = exact collection count).
- `git diff --check` → **exit 0**.
- Ruff on all 25 changed/new Python files → 8 findings, **all pre-existing and
  verified at HEAD** (2 × `s3_model_discovery.py`, 6 × unused
  `AraminaPreprocessingError` imports in `test_aramina_workflow_runtime.py`; counts
  and rules identical at HEAD, lines only shifted). **Zero findings introduced.**

## Test-count comparison with main
main = 4212 collected → worktree **4259** = **+47, 0 removed**. Reconciliation:
16 (standard conformance) + 21 (Aramina direct package) + 3 (API freeze) + 4
(deduplication) = 44 new explicit tests, plus 3 auto-parametrized
`test_no_server_spawning_code` cases for the new test files (105→108). The two
modified test files collect identically to main (238 and 36) — no test deleted,
weakened, or xfailed; the PR0139 env-invariant AST test was **strengthened** (now
enforced across the authoritative package `trace.py` and `inference.py`, plus
provider_url absence across the whole package). Full run reports 0 xfailed.

## Warnings (non-gating)
1. `aramina_v0213/manifest.MODEL_ID = "aramina-target-brest-risk"` — spelling variant
   vs the repo-wide "aramina-target-breast-risk"; runtime-unused (entry-driven
   identity) but should be corrected as provenance metadata before PR0155 packaging.
2. The Aramina runtime still reaches the platform `workflow_orchestrator.
   _validate_aramina_source` via a lazy module-global default (H5 patient/source
   binding inside the pipeline call path). This is behavior-parity-preserving,
   documented in ADR-0017 and the contract doc, and explicitly deferred (with the
   container/bytes abstraction) to the PR0155 packaging work. Same for Bremen's
   `api.decision_contract` vocabulary bridge (platform-specific, classified).
3. Transitional shims (3 Bremen, 3 Aramina + the `workflow_aramina` re-export
   surface) remain by design for import stability; zero logic is AST-enforced and
   object identity is tested; removal tracked as follow-up work.
4. The private Aramina trace logger name changed to
   `bremen.model_packages.aramina_v0213.trace` (private diagnostics only; verified no
   test/contract references the logger name; public events/reports unaffected).
5. The report's stated total collection ("4248") is a typo; the measured values are
   4259 collected / 4248 passed (+47 vs main), matching the report's delta claim.

## Blockers
None.

## Remaining future work
- Correct the Aramina manifest reference `MODEL_ID` spelling (trivial follow-up).
- PR0155 packaging PR: container/bytes abstraction replacing staged-path +
  `_validate_aramina_source` inside the runtime boundary; decision-vocabulary
  adapter if a zero-`bremen.api` Bremen package is desired; dependency/version
  pinning and release-directory metadata; MLflow pyfunc wrap of the conforming
  packages; Model Registry evaluation; shim removal after caller migration.

## FINAL VERDICT

VERDICT: READY FOR COMMIT
