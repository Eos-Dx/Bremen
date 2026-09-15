# PR0156 — Model Package Standard v1 + Aramina conformance

## Branch / HEAD
- Branch: `0156-model-package-standard-v1`
- HEAD at plan time: `e361feab04e5f800bf89ebbda8aa62fd60296528`
  ("docs: record MLflow model packaging spike", #216). Clean worktree.
- No commit will be created.

## Source-of-truth review
- ADRs: docs/adr/0001..0016 inspected; **next ADR number = 0017**.
- ADR-0016 (Model Runtime Contract v1), docs/model_runtime_contract_v1.md
  (incl. PR0153B + PR0154 notes and the PR0155/PR0154 coupling list).
- docs/bremen_3x3_training_parity.md (PR0151/0152 scientific source of truth).
- PR evidence: .project-memory/pr/0154-bremen-inference-package/{PLAN,
  PRECOMMIT_REVIEW,IMPLEMENTATION_REPORT}.*, docs/bremen_v01_inference_package.md.
- docs/mlflow_model_packaging_spike.md (PR0155). Note: this is an unmerged
  research-spike doc — it proposed a *different* "0156-mlflow-pyfunc" scope.
  The **authoritative task instruction for this PR is PR0156 = Model Package
  Standard v1 + Aramina conformance**. The MLflow spike's useful conclusion
  ("wrap an already-correct package; do not teach the platform model science")
  is respected; actual MLflow packaging is a NON-GOAL here.
- Implementations read completely: src/bremen/model_runtime.py,
  model_packages/bremen_v01/*, api/workflow_bremen.py, api/workflow_aramina.py,
  api/aramina_{provider,preprocessing,preprocess_worker,artifact_compat,
  symmetry,api_errors}.py, api/report_aramina.py, api/workflow_aramina_scaffold.py,
  api/model_requirements.py, api/workflow_orchestrator.py, api/workflow_registry.py,
  api/workflow_provider.py, api/model_registry.py, api/decision_contract.py,
  api/xrd_normalization.py, api/model_state.py, api/s3_model_discovery.py,
  api/preflight.py.
- Baseline (pre-change) targeted run of the suites this PR touches:
  **485 passed, 1 skipped** (aramina_runtime + contract_v1 + catalog_multi_model +
  aramina_scaffold + v01_package + 3x3_runtime_parity + inference_integration +
  server_helpers). Must remain equal-or-higher after (new tests only add).

## Current-state ownership map — Bremen (already package-owned; PR0154)
| Concern | Location | Owner |
| --- | --- | --- |
| requirements/validation/predict entry | model_packages/bremen_v01/runtime.py `BremenRuntime` | package (contract v1) |
| 15-feature science | model_packages/bremen_v01/features.py | package (numpy/pandas/scipy only) |
| portable logreg contract | model_packages/bremen_v01/predictor.py | package |
| identity/provenance/deps | model_packages/bremen_v01/manifest.py | package (authoritative) |
| package entry surface | model_packages/bremen_v01/__init__.py | package |
| orchestration adapter | api/workflow_bremen.py | platform (thin) |
| legacy import paths | bremen_features.py / inference.py / bremen_runtime.py | platform **shims** (zero logic) |
| **remaining bridges** | runtime.py imports api.decision_contract + api.xrd_normalization.validate_canonical_measurement | classification below |

## Current-state ownership map — Aramina (partly platform-owned today)
| Concern | Current location | Nature |
| --- | --- | --- |
| ModelRuntime adapter (`AraminaRuntime`) | api/workflow_aramina.py | logic (stays platform; delegates) |
| `AraminaWorkflowProvider` (orchestration, payload/`ARAMINA_*` envelope) | api/workflow_aramina.py | **platform** |
| `AraminaWorkflowError` + `FAILURE_STAGES` + `_SAFE_FAILURES` + `entry_contract` check | api/workflow_aramina.py | cross-cutting failure vocabulary |
| public per-stage remediation/detail copy | api/workflow_aramina.py (`_STAGE_REMEDIATION`/`_STAGE_DETAIL`) | **platform** (consumed by api/aramina_api_errors.py) |
| artifact load `_load_selected_artifact` (joblib via s3 `_load_staged_artifact`, version gate vs entry) | api/workflow_aramina.py | model artifact interpretation |
| artifact contract validate `_validate_artifact` | api/workflow_aramina.py | model artifact interpretation |
| pickle-stub bridge `aramina_artifact_compat` (`GatedSymmetryLogistic`) | api/aramina_artifact_compat.py | model-specific |
| raw-H5 preprocessing `aramina_preprocessing` (`preprocess_aramina`, release env selection, allowlisted worker diagnostics) | api/aramina_preprocessing.py | model-specific |
| preprocessing worker `aramina_preprocess_worker.py` (invoked by absolute `__file__` path) | api/aramina_preprocess_worker.py | model-specific; no bremen/aramina imports |
| LR1 score / logit aggregation / final df / final model / threshold | api/workflow_aramina.py `_run_local_artifact` | model science |
| symmetry features | api/aramina_symmetry.py | model science |
| profile matrix / target-side selection | api/workflow_aramina.py `_prepare_features`, `_build_profile_matrix`, `_select_measurements` | model science |
| model requirements (request fields, target_side) | api/workflow_aramina.py `ARAMINA_*` constants | model identity/requirements |
| `_validate_aramina_source` (H5 checksum/patient binding, opens H5) | api/workflow_orchestrator.py | **platform** source concern (called from science) |
| report payload build | api/workflow_aramina.py `_run_local_artifact` step 8 | model-owned safe result |

## Proposed common Model Package Standard v1
Framework-independent, structural standard defining the **deployable ownership
boundary around Model Runtime Contract v1** (contract = *how* the platform calls
a runtime; standard = *what a conforming package owns/exposes*). Implemented as
documentation + ADR-0017 + a neutral contract type + a test-side conformance
helper (NO `ModelPackageBase` class — the runtime protocol already is the
interface; no shared scientific behavior exists between Bremen and Aramina).

Each conforming package must have one authoritative source for the 11 task
categories (identity, requirements, validation, runtime entry implementing
ModelRuntime, artifact interpretation, complete inference, threshold/post-
processing, safe diagnostics, provenance, golden evidence, dependency/import
boundary). Layout/algorithm may differ (Bremen: portable dict + sklearn-free
math; Aramina: joblib sklearn artifact + subprocess preprocessing).

## Dependency-direction analysis
Required: platform → ModelRuntime contract → package public entry → package
science. Forbidden: package → workflow/job/fastapi/report/auth/S3/frontend.

Classification of the two Bremen bridges (per task "classify, do not force-
remove"):
- `api.xrd_normalization.validate_canonical_measurement` — operates on the
  canonical XRD measurement, which is a **generic cross-model scientific input
  type** shared by both models' model-runtimes. → classify as generic
  model/runtime vocabulary. **Additive neutralization**: create
  `bremen/canonical_input.py` as the authoritative neutral home (stdlib/numpy
  only, no `bremen.api`), re-export it from `api/xrd_normalization.py` so
  `xrd_normalization` remains the full canonical home (normalizers,
  `NormalizationError`), and repoint model-runtime references. No
  duplicate-implementation risk (one definition). Platform modules keep using
  `api.xrd_normalization`. Aramina will consume the same neutral module.
- `api.decision_contract` — Bremen-specific decision vocabulary (MRI
  continuation), referenced in 6+ platform modules; Aramina uses its own report
  vocabulary and does not consume it. → classify as platform-specific. Keep as
  a documented single narrow platform bridge for the Bremen runtime (PR0154
  decision unchanged). **Not** moved (moving would churn unrelated platform
  modules; a neutral home is not justified because it is not generic).

Cycles: none — `bremen.canonical_input` (neutral) and `bremen.model_runtime`
are leaves; `model_packages.aramina_v*` imports only neutral leaves + stdlib
scipy numpy pandas yaml; `api.model_packages_bridge` (joblib loader, lazy) and
`api.workflow_orchestrator._validate_aramina_source` (injected callable) are
the only package→platform edges and neither imports the package.

## Scientific parity strategy
No algorithm edits. Aramina pipeline functions (`_prepare_features`,
`_run_local_artifact`, symmetry, preprocessing, artifact load/validate, debug
trace) move **verbatim** (import lines retargeted to the neutral home /
package-local modules). Behavior-preserving changes ONLY:
1. Artifact deserialization: `_load_selected_artifact` currently does a lazy
   `from .s3_model_discovery import _load_staged_artifact`. The package cannot
   import the platform module (import-literal test). Provide an **identical**
   controlled loader `api.model_packages_bridge.load_staged_artifact` (same
   body: sha256-integrity→joblib.load→ValueError("Artifact integrity
   failed")/RuntimeError("Unsupported artifact")). `_load_staged_artifact`
   becomes a re-export of it (it is only used by Aramina; verified). This keeps
   the error mapping identical.
2. `_validate_aramina_source` stays a platform function but is injected into
   `AraminaRuntime` (default lazy-imports it); the pipeline calls the injected
   callable with the same args → same exceptions → same `ARAMINA_UNSUPPORTED_
   INPUT`/`h5_patient_contract`.
3. Debug trace `_debug_checkpoint`: the module name in the log line becomes the
   package module (private diagnostic only; log-name change asserted safe by
   grep of tests). `BREMEN_ARAMINA_DEBUG_TRACE` env gate unchanged.

Bremen: only `bremen.api.xrd_normalization`→`bremen.canonical_input` import
retargets in runtime.py + features.py docstring; no code path change.

Golden parity retained: PR0151 fixture (probability 0.7388733541967353,
atol 1e-10 rtol 0) and all PR0151/0152/0154 parity tests must pass.

## Public compatibility strategy
- `api/workflow_aramina.py` keeps the EXACT external surface (re-exports from
  package/neutral/bridge + its own `AraminaRuntime`/`AraminaWorkflowProvider`):
  `ARTIFACT_TYPE`, `_ARTIFACT_KIND`, `_DEFAULT_AUTHOR`, `_FINAL_FEATURE_COLUMNS`,
  `_SAFE_FAILURES`, `FAILURE_STAGES`, `_STAGE_REMEDIATION`, `_STAGE_DETAIL`,
  `_ALLOWED_PREPROCESSING_RELEASES`, `_TRACE_LABELS`, `_TRACE_STAGES`,
  `AraminaWorkflowError`, `_safe_stage`, `_safe_release_tag`,
  `_build_aramina_request_json`, `_load_selected_artifact`, `_reject_artifact`,
  `_validate_artifact`, `_select_measurements`, `_build_profile_matrix`,
  `_prepare_features`, `_run_local_artifact`, plus
  `ARAMINA_WORKFLOW_ID/REQUEST_FIELDS/OPTIONAL_REQUEST_FIELDS/
  ALLOWED_TARGET_SIDES`. (Verified the existing AST source-text test at
  test_aramina_workflow_runtime.py:211-217 still passes: `os.environ.get`
  appears once, with only "BREMEN_ARAMINA_DEBUG_TRACE", and
  `BREMEN_ARAMINA_PROVIDER_URL`/`provider_url`/`_post_aramina_predict` absent.)
- `api/aramina_preprocessing.py`, `api/aramina_symmetry.py`,
  `api/aramina_artifact_compat.py`, `api/aramina_preprocess_worker.py` become
  re-export shims (same public names) so the many test monkeypatch seams keep
  resolving. Shims: zero scientific logic, transitional, re-export authoritative
  object.
- No public API endpoint/field/report envelope/model_id/routing/auth/job/PDF/
  frontend/threshold change. `ARAMINA_*` codes, target_side, symmetry,
  preprocessing contracts, report semantics, model IDs all unchanged.
- Report layer (`api/report_aramina.py`) untouched (consumes result payload).

## Aramina package layout (name chosen after inspecting conventions)
`bremen/model_packages/<model>_<release>` is the PR0154 convention
(`bremen_v01`). Aramina release is `0.2.13-beta` (production model; artifact
`model_identity.version`; `_ARAMINA_RELEASES`/`_DEFAULT_ARAMINA_MODEL_ID`
confirm). → **`src/bremen/model_packages/aramina_v0213/`** with:
```
__init__.py            # entry point (re-exports AraminaRuntime + manifest +
                       # the science seam surface for the transitional shim)
manifest.py            # authoritative STATIC contract: workflow_id, artifact
                       # kind/type, allowed preprocessing releases, request
                       # fields, allowed target sides, notes, and reference
                       # release identity (id/name/version) + provenance.
                       # Per-selection identity stays entry-driven (public
                       # model_id/routing unchanged); requirements merge
                       # static contract (package) + entry identity.
trace.py               # _debug_checkpoint/_debug_stage/_TRACE_* (moved from
                       # workflow_aramina; log name becomes bremen.model_packages
                       # .aramina_v0213.trace — private, no test asserts logger)
errors.py              # AraminaWorkflowError + _SAFE_FAILURES + FAILURE_STAGES
                       # + _STAGE_REMEDIATION/_STAGE_DETAIL + _safe_stage
                       # (+ _safe_release_tag, _ARTIFACT_KIND, _ALLOWED_* )
artifact_compat.py     # moved pickle bridge (GatedSymmetryLogistic)
preprocess_worker.py   # moved worker (co-located; __file__ resolves)
preprocessing.py       # moved preprocess_aramina + worker allowlists
symmetry.py            # moved symmetry features
inference.py           # moved artifact load/validate + profile matrix +
                       # LR1/logit/symmetry/final/threshold pipeline +
                       # report payload build + _build_aramina_request_json;
                       # package-only globals
                       # (_load_staged_artifact_impl, _validate_aramina_source_impl)
                       # default to api.model_packages_bridge /
                       # api.workflow_orchestrator lazy lookups, monkeypatchable
                       # in tests
runtime.py             # AraminaRuntime (moved here): model_requirements from
                       # manifest + entry identity; validate_model_input;
                       # predict_model calls inference.run_local_artifact and
                       # PROPAGATES AraminaWorkflowError unchanged (the platform
                       # provider keeps the exact code/stage/preprocessing_
                       # diagnostic → WorkflowResult envelope translation it
                       # performs today). on_features is a documented no-op.
```
`api/workflow_aramina.py` retains ONLY the platform provider
(`AraminaWorkflowProvider`) and a transitional zero-logic re-export surface
(the ~20 names external code/tests import). The provider builds `ModelInput`,
delegates `self._runtime.predict_model(...)`, and keeps the SAME
`except AraminaWorkflowError`/`except Exception` → `WorkflowResult` translation
it performs today (byte-identical public envelope). The runtime lives in the
package and propagates `AraminaWorkflowError` exactly as the current
in-platform runtime does, so contract-level behavior is unchanged.

Chosen for lowest behavioral risk (mirrors PR0154 precedent): Aramina runtime
moves into the package; provider stays in api as a thin adapter; provider does
NOT import scientific helpers directly (only the runtime entry +
AraminaWorkflowError for the sentinel `build_features`). Package import test
forbids `workflow_aramina`/orchestration; provider→package and
package→platform-bridge (lazy) are the only allowed edges.

## Monkeypatch seam handling (verified counts)
Because Aramina runtime+science move to the package and `workflow_aramina`
becomes a transitional re-export shim, monkeypatching the shim's attribute does
NOT affect the package's global lookup. Therefore seams are RETARGETED to the
authoritative package module (pure path change; identical object; behavior
unchanged — exactly the PR0154 `build_bremen_features` precedent):
- `bremen.api.workflow_aramina._load_selected_artifact` — 7 test sites →
  `bremen.model_packages.aramina_v0213.inference._load_selected_artifact`.
- `bremen.api.aramina_preprocessing.preprocess_aramina` — 10 test sites →
  `bremen.model_packages.aramina_v0213.preprocessing.preprocess_aramina`.
- `bremen.api.aramina_symmetry.symmetry_features` — 1 test site →
  `bremen.model_packages.aramina_v0213.symmetry.symmetry_features`.
- `runpy.run_path("src/bremen/api/aramina_preprocess_worker.py")` — 1 test site
  → package worker path.
- `_prepare_features`-injected `_validate_aramina_source` / loader: package
  inference exposes module globals `_validate_aramina_source` and
  `_load_staged_artifact` initialized to the platform impls (lazy import);
  seams patch the package-inference attributes.
Also `tests/test_aramina_workflow_runtime.py:211` AST test asserts the ONLY
`os.environ.get` in `workflow_aramina.py` is the debug-trace flag; after the
move that call site lives in `trace.py`, so the shim has none → the test is
updated to read the authoritative moved source (still asserting the env flag is
the only one, and provider_url/BREMEN_ARAMINA_PROVIDER_URL/_post_aramina_predict
absent). This is a test-side source-path retarget, not a behavior change.
No assertion is weakened. The `workflow_aramina` re-export surface is retained
for import compatibility only.


## Compatibility shims retained + why
- api/aramina_{preprocessing,symmetry,artifact_compat,preprocess_worker}.py →
  re-export shims (test seams + `test_no_external_dependency` AST test uses
  only `path.split('.')[0]=='aramina'` which cannot match a package submodule,
  so no breakage).
- api/workflow_aramina.py keeps full re-export surface (see above) — required by
  external imports/tests and job/fastapi/api_errors/registry consumers.
- bremen/api/model_packages_bridge.py — new platform-neutral controlled loader
  (not a shim; a bridge the package may import).
- bremen/canonical_input.py — new neutral home; api/xrd_normalization re-exports.
No two active scientific implementations (shims re-export only).

## Files expected to move / be created / change
Moved (into aramina_v0213 package, verbatim):
- api/aramina_preprocessing.py → package/preprocessing.py
- api/aramina_preprocess_worker.py → package/preprocess_worker.py
- api/aramina_symmetry.py → package/symmetry.py
- api/aramina_artifact_compat.py → package/artifact_compat.py
- the science section of api/workflow_aramina.py (artifact load/validate,
  profile matrix, LR1/logit/symmetry/final/threshold, report payload,
  `_build_aramina_request_json`, errors, debug trace) → package/errors.py,
  debug_trace.py, inference.py
Created:
- model_packages/aramina_v0213/{__init__,manifest,runtime,errors,debug_trace,
  artifact_compat,preprocessing,preprocess_worker,symmetry,inference}.py
- src/bremen/canonical_input.py (neutral canonical validation/type)
- src/bremen/api/model_packages_bridge.py (controlled artifact loader)
- tests/test_bremen_model_package_standard_v1.py (conformance matrix)
- tests/test_aramina_v0213_package.py (direct package golden/parity)
- docs/model_package_standard_v1.md
- docs/adr/0017-model-package-standard-v1.md
Changed:
- api/workflow_aramina.py (provider + AraminaRuntime keep; science removed →
  re-export; requirements from package manifest)
- api/workflow_bremen.py, model_packages/bremen_v01/runtime.py + features.py
  (xrd_normalization→canonical_input retarget only)
- api/s3_model_discovery.py (`_load_staged_artifact` re-export of bridge)
- api/aramina_api_errors.py (import FAILURE_STAGES/_STAGE_* from shim path —
  unchanged since shim re-exports; verify)
- model_runtime.py, docs/model_runtime_contract_v1.md (clarification:
  contract vs standard vs packaging; PR0155-coupling now resolved by PR0156)
- tests: add new; minimal path/`__file__`-literal retargets where a test
  imports a moved symbol from a now-shimmed module (should be zero due to
  shims; only `runpy.run_path("src/bremen/api/aramina_preprocess_worker.py")`
  is a path literal to update).

## Test matrix
- Standard conformance (per package): exposes ModelRuntime entry; requirements
  available + correct (Bremen 3+3; Aramina target_side/explicit); validation
  callable; prediction callable; identity/provenance present; package does NOT
  import forbidden orchestration modules (AST); provider routes through
  package runtime; direct package prediction == provider-level prediction.
- Bremen direct golden parity (test_bremen_v01_package.py) unchanged + must pass.
- Aramina direct package execution on existing fixtures reproduces current
  provider/runtime scientific outputs (report payload parity: risk_probability,
  target_class_risk_level, thresholds, model_name/version, reliability).
- Regression: full PR0151/0152/0154 Bremen parity suites; PR0153B contract
  suite; Aramina preprocessing/runtime/provider tests; registry/orchestrator/
  model-requirements; job/report integration affected by movement; fastapi
  route plumbing; catalog multi-model.
- Search tests/commands: duplicate Bremen science; duplicate Aramina science;
  forbidden reverse imports; artifact/private-data scan.

## Validation commands
- python -m compileall -q src tests
- pytest -q tests/test_bremen_model_package_standard_v1.py tests/test_aramina_v0213_package.py
- pytest -q tests/test_bremen_v01_package.py tests/test_bremen_3x3_runtime_parity.py tests/test_bremen_3x3_training_parity.py tests/test_bremen_workflow_bremen.py
- pytest -q tests/test_bremen_model_runtime_contract_v1.py
- pytest -q tests/test_aramina_workflow_runtime.py tests/test_aramina_provider_contract.py tests/test_bremen_workflow_aramina_scaffold.py
- pytest -q tests/test_bremen_model_requirements_api.py tests/test_bremen_inference_integration.py tests/test_bremen_job_api_handler.py tests/test_catalog_api_multi_model.py
- pytest -q  (full)
- ruff check on every changed/new .py
- git diff --check
- grep/AST searches (duplicate science, forbidden reverse imports, artifact scan)

## Rollback risks
- Import cycle if package imports any platform module beyond the two
  documented edges (mitigated: bridge + injected validator + neutral leaf;
  AST import test + compileall).
- Monkeypatch seam divergence (patching a shim symbol that science calls via
  its own module global). Mitigated by verbatim move (package science keeps
  calling `preprocess_aramina`/`symmetry_features`/`_load_staged_artifact`/
  `run_local_artifact` exactly where they are defined; those definitions live
  in the package, and the shim re-exports the SAME object) — but a patch on the
  SHIM module attribute would NOT affect the package's own global lookup.
  Resolution: for the seams tests actually use, point the package's calls at
  the module whose attribute tests patch, OR (preferred) update the affected
  test seams to patch the package path. Chosen: update the small set of Aramina
  test seams to the authoritative package module (behavior-preserving path
  change) — the PR0154 precedent did exactly this for build_bremen_features.
- Loader error-mapping drift (bridge must byte-match `_load_staged_artifact`).
- Subprocess worker path (moved file; update the runpy test path).
- Report payload field parity (must remain byte-identical).

## Explicit non-goals
No retraining; no scientific/threshold/formula changes; no artifact-format
change or new model versions; no MLflow/BentoML/KServe integration, loaders,
registry, tracking server, aliases, deployment; no service split; no separate
git repo; no storage/S3 redesign; no API/report/frontend/PDF redesign; no Model
Registry; no Aramina retraining; no broad unrelated cleanup; do not move
`_validate_aramina_source` into the package (platform source concern; injected).

## HTTP API FREEZE (hard constraint)
All existing HTTP endpoints are frozen. This PR is an internal refactor behind
the provider/runtime boundary ONLY. It must not add/remove/rename/move/version
any public endpoint, change HTTP methods, request/response schemas, auth
requirements, status-code behavior, externally consumed error codes/reason
fields, model_id semantics, or workflow_id semantics. Model Package Standard v1
is NOT exposed through any new HTTP endpoint; MLflow is not exposed publicly.
Route inventory at HEAD (29 routes in api/fastapi_app.py) is locked by a new
snapshot regression test (`tests/test_bremen_api_freeze_pr0156.py`) comparing
the live FastAPI route table (method+path) against the frozen list; it must
pass unchanged after the refactor. No endpoint module is modified. If any
architectural improvement would require an endpoint change, it is deferred and
documented as future work instead of implemented.
