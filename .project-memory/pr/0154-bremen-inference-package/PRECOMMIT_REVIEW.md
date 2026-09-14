# PR0154 Pre-Commit Review — Bremen v0.1 Inference-Complete Model Package

## Branch
`0154-bremen-inference-package` (verified via `git branch --show-current`)

## HEAD
`c92f9f0a437efc07b499c833acff69b2879dcb11` (verified via `git rev-parse --verify HEAD`;
base commit "refactor: implement model runtime contract v1", #214. No commit created by
this review; worktree at review time 2026-09-14T22:42:32Z)

## PLAN reviewed
`.project-memory/pr/0154-bremen-inference-package/PLAN.md` — read in full (package
layout, shim strategy, identity/requirements/artifact ownership, dependency direction,
PR0153-coupling resolution, non-goals, test strategy). `IMPLEMENTATION_REPORT.txt`
present and read.

## Prior source-of-truth artifacts reviewed
`docs/model_runtime_contract_v1.md` (incl. PR0153B notes + PR0154 resolution diff),
`docs/adr/0016-model-runtime-contract-v1.md` (Accepted; unmodified),
`docs/bremen_3x3_training_parity.md` (Parts 1+2; unmodified), PR0151
PLAN+PRECOMMIT_REVIEW, PR0152 PLAN+PRECOMMIT_REVIEW, PR0153B PLAN+PRECOMMIT_REVIEW
(all unchanged in git status; contents in evidence from the prior three reviews).

## Changed files (all read completely)
`git diff --name-status`: 8 modified; untracked: `src/bremen/model_packages/` (5 new
modules), `tests/test_bremen_v01_package.py`, `docs/bremen_v01_inference_package.md`,
`.project-memory/pr/0154…/{PLAN.md,IMPLEMENTATION_REPORT.txt}`.

| File | Status |
| --- | --- |
| `src/bremen/model_packages/__init__.py` | NEW (package root; no science, no platform imports) |
| `src/bremen/model_packages/bremen_v01/__init__.py` | NEW (single entry point) |
| `src/bremen/model_packages/bremen_v01/manifest.py` | NEW (authoritative identity + input contract) |
| `src/bremen/model_packages/bremen_v01/features.py` | NEW (moved science; canonical import lifted) |
| `src/bremen/model_packages/bremen_v01/predictor.py` | NEW (moved portable predictor) |
| `src/bremen/model_packages/bremen_v01/runtime.py` | NEW (moved contract runtime) |
| `src/bremen/bremen_features.py` | M → zero-logic re-export shim |
| `src/bremen/inference.py` | M → zero-logic re-export shim |
| `src/bremen/bremen_runtime.py` | M → zero-logic re-export shim (old identity constants removed) |
| `src/bremen/api/workflow_bremen.py` | M (imports package entry point only) |
| `docs/model_runtime_contract_v1.md` | M (PR0154 resolution notes appended) |
| `docs/bremen_v01_inference_package.md` | NEW (package contract doc) |
| `tests/test_bremen_v01_package.py` | NEW (50 direct package tests) |
| `tests/test_bremen_3x3_runtime_parity.py` | M (2 monkeypatch seams retargeted to package runtime) |
| `tests/test_bremen_model_runtime_contract_v1.py` | M (1 monkeypatch seam retargeted) |
| `tests/test_bremen_inference_integration.py` | M (sklearn scan covers shim + package predictor) |

No ZIP, real H5, joblib, pickle, training repository, binary model, large binary fixture
or private data added (status + `find src/bremen/model_packages` → only `.py`).

## Package layout
`src/bremen/model_packages/bremen_v01/` with `__init__.py` (entry point re-exporting the
runtime surface + `manifest`), `manifest.py`, `features.py`, `predictor.py`,
`runtime.py`. Root `model_packages/__init__.py` carries no science and no platform
imports.

## Authoritative runtime entry point
`bremen.model_packages.bremen_v01.runtime.BremenRuntime` (re-exported by
`bremen.model_packages.bremen_v01`), implementing `bremen.model_runtime.ModelRuntime`
(`model_requirements` / `validate_model_input` / `predict_model`) over the frozen
PR0152 `run()` sequence. `workflow_bremen.py` imports exactly this entry point
(`from bremen.model_packages.bremen_v01 import BremenRuntime`); the provider's
`runtime`/`model_runtime()` handles expose it to the platform; requirements routing
(PR0153B) reaches the same object through the provider.

## Package completeness assessment
**PASS — inference-complete, not a wrapper.** The package owns every listed
responsibility, each mechanically verified as the moved authoritative code:
- Bremen-specific requirements: `manifest.MEASUREMENT_SIDES=(("LEFT",3),("RIGHT",3))`,
  `TOTAL_MEASUREMENTS=6`, `REQUIRES_TARGET_SIDE=False`, request fields — assembled by
  `runtime.model_requirements()` (values verified equal to the PR0153B literals).
- Exact 3+3 validation: `features.validate_bremen_shape` (AST-identical to HEAD).
- Preprocessing / q-grid / smoothing / normalization / aggregation / replicate
  variation / 15 features: `features.py` — every primitive AST-identical to HEAD
  `bremen_features.py` (and to the frozen `tests/reference_0151` reference), except
  `build_bremen_features` itself, whose only change is the removal of the lazy
  `bremen.api.xrd_normalization` import (guard lifted, see below).
- Imputation/scaling/portable estimator/threshold: `predictor.py` — **100% AST-identical**
  to HEAD `inference.py` (`validate_portable_logreg_model`, `predict_proba_portable`,
  `adapt_model_package`, `_validate_field`, `_first_mismatch`, error class).
- Model-specific safe diagnostics: `BremenFeatureError` constants +
  `_runtime_error_for` mapping (docstring-stripped AST-identical to HEAD).
- Model identity/provenance: `manifest.py` (single source).

## Platform boundary assessment
**PASS.** `workflow_bremen.py` changes are import/projection-hygiene only: it now
imports the package entry point (no scientific helper imports), drops the
package-internal `BremenModelResult` type annotation (attribute-access translation
only), and keeps payload keys byte-identical. `BREMEN_V01_FEATURE_COLUMNS` remains
exported, sourced from the package runtime class. Platform modules do not compute
Bremen features, inspect scaler values, coefficients, aggregation, or threshold
logic: `grep` for release-identity literals (`bremen-paper-reference-v0-2-0`,
`0.2.0-paper-reference`, `bremen_paper_reference_symmetry_logreg`) and the threshold
literal (`0.3585907282566089`) in `src/` outside the package → **none**. Platform
consumers of the predictor (`feature_artifact_prediction`, `inference_handler`,
`s3_model_discovery`, `server`) call the package-owned functions through the shim —
they hand opaque data to package code, they do not reimplement or inspect scientific
internals. Model Requirements API continues to derive Bremen requirements from the
runtime (PR0153B); the platform does not re-declare the 3+3 contract anywhere.

## Direct package golden parity
**PASS.** `tests/test_bremen_v01_package.py` (50 tests) executes the package runtime
**without WorkflowProvider**:
- `test_package_golden_features_and_probability_no_provider`: 15 feature names/values
  == frozen fixture (atol 1e-10, rtol 0); `run()` probability ==
  `0.7388733541967353`; threshold == `0.3585907282566089`; prediction 1; decision
  positive.
- `test_package_predict_model_contract_no_provider`: contract `predict_model` returns
  `RuntimePrediction` with golden probability, `CONTINUE_MRI`, manifest model_id.
- Plus: requirements/manifest identity vs PR0151 evidence; all 9 invalid shapes;
  all-six participation (frozen mutation vectors + changed_features); LEFT/RIGHT
  permutation invariance (12 cases); replicate variance ddof=1 vs the PR0151
  reference (sigma → 0 on identical replicates); original-profile peak semantics;
  raw-peak gate; portable estimator + threshold parity vs the reference scorer;
  feature-column single source. This proves inference-completeness: the package alone
  reproduces the validated release behavior.

## Scientific parity (freeze)
**PASS — no numerical change.** Move verified mechanically:
- `predictor.py`: 100% identical to HEAD `inference.py`.
- `features.py`: all primitives identical to HEAD and to the frozen PR0151 reference;
  sole delta is the lifted lazy platform import (see Input boundary).
- `runtime.py`: `run`, `score`, `model_ready`, `validate_model_input`,
  `_bremen_result_mapping`, dataclasses identical; `model_requirements`/`model_metadata`/
  `predict_model`/`_runtime_error_for` differ only by manifest-sourced constants
  (each value verified equal) and a hoisted local; `build_features` adds the lifted
  structural guard.
- Regression suites green: PR0151/PR0152 parity + workflow + plugin → **151 passed**
  (golden features, golden probability, exact 3+3, all-six participation, LEFT and
  RIGHT permutation invariance, replicate variance, peak semantics, q-grid behavior,
  scaler parity, raw-H5 parity, invalid-shape behavior — all unchanged assertions).

## Raw-H5 parity
**PASS — unchanged.** `test_synthetic_h5_production_job_path`, calibration-layout,
canonical physical-q and H5-enumeration permutation tests pass inside the 151-suite
run; loading/canonicalization remain platform-owned (`workflow_orchestrator`,
`h5_layouts` untouched in this PR); the synthetic fixture is still test-generated in
`tmp_path`; no H5 committed.

## Model identity ownership
**PASS.** `manifest.py` is the single authoritative release-identity source:
`MODEL_ID=bremen-paper-reference-v0-2-0`, `MODEL_NAME=bremen_paper_reference_symmetry_
logreg`, `MODEL_VERSION=0.2.0-paper-reference`, `FEATURE_SCHEMA_VERSION=v0.1`,
`THRESHOLD_VALUE=0.3585907282566089` (provenance; applied value always from the
loaded artifact predictor), `ARTIFACT_SHA256=65866f44…df3b0` (PR0151/PR0152 evidence).
The duplicate constants in the former `bremen_runtime.py` are **removed**; grep proves
no identity/threshold literal remains in platform `src/`. `test_manifest_identity_
matches_pr0151_evidence` and `test_package_requirements_exact_three_plus_three` lock
the values against divergence. Platform routing identifiers (registry/catalog
`model_id`s, provider default `bremen_mri_triage_logreg`) are unchanged public
identifiers, documented as platform selection identity distinct from release
identity, reconciled through the contract (`model_requirements().model_id`,
`RuntimePrediction.model_id`). No public identifier changed.

## Requirements ownership
**PASS — package-owned.** The declared 3 LEFT + 3 RIGHT input contract lives only in
`manifest.py`, surfaced via `runtime.model_requirements()`; the platform
Model Requirements API derives from the runtime (PR0153B path unchanged, suites
green: 82 passed incl. requirements API + inference integration). No multiple
divergent active truths: the old runtime constants are gone; the requirements API
hard-coded Aramina defaults are Aramina-owned (out of scope) and unchanged.

## Artifact ownership
**PASS.** `predictor.py` owns interpretation and execution of the `portable_logreg`
artifact contract, including the PR0152 nested `feature_schema.feature_columns` /
`decision.threshold` adaptation (AST-identical move). `runtime.model_metadata`
resolves identity from the loaded package in package code. The platform selects,
stages, and checksum-verifies artifacts (`model_registry`, `s3_model_discovery`,
ADR-0007 `model_package`) — unchanged — and hands the opaque loaded dict to the
runtime; it never executes scientific internals. `manifest.py` is Python
release-contract metadata, explicitly not a second artifact-manifest system. No
artifact binary was added, moved, or duplicated.

## Dependency direction
**PASS.**
- platform (`api/*`, `workflow_bremen.py`) → `bremen.model_runtime` (contract) and →
  package entry point. Platform modules import no package-internal science helpers
  (grep: only `workflow_bremen.py` + the three shims reference the package).
- package science (`features.py`, `predictor.py`, `manifest.py`) → numpy/pandas/
  scipy/stdlib only (AST-tested: no `bremen.api`, no workflow/fastapi).
- package runtime → package science + exactly two platform bridges:
  `api.decision_contract` (platform decision-vocabulary authority; the numerical
  threshold comparison stays inside the package predictor) and
  `api.xrd_normalization.validate_canonical_measurement` (input-structure contract).
- contract → stdlib only. No cycles (`decision_contract` references `workflow_bremen`
  only in a comment; compileall and the full suite pass; the subprocess test proves
  importing the package entry point loads no workflow/job/report/FastAPI module).

## Forbidden import search
**PASS.** Package imports of `workflow_bremen` / `workflow_aramina` / report
providers / `job_api_handler` / FastAPI / auth / frontend / `s3_model_discovery` /
`source_registry`: **none** (AST test over all five package modules + runtime
subprocess isolation test). Package science importing `bremen.api`: **none**.

## Duplicate science search
**PASS.** `grep "^def …"` for `build_bremen_features`, `validate_bremen_shape`,
`predict_proba_portable`, `validate_portable_logreg_model`, `adapt_model_package`
across `src/`: each defined **exactly once**, in the package. Historical grep hits of
`bremen_features.py` are the shim re-exporting the same objects (zero definitions —
AST-verified and asserted by `test_shims_have_no_scientific_logic` and
`test_shims_reexport_authoritative_objects` object-identity checks). Test-only
PR0151 reference and historical docs do not count; pre-existing dormant
`preprocessing_bridge`/`training` helpers are unchanged and outside the Bremen v0.1
inference path (documented since PR0152).

## Compatibility shim review
**PASS.** Three shims (`bremen/bremen_features.py`, `bremen/inference.py`,
`bremen/bremen_runtime.py`) contain only imports and `__all__` — zero function/class
definitions (AST test enforces this permanently). Justification documented: four
active platform modules import `bremen.inference` symbols and historical test seams
import the other paths; shims keep those resolving without churn while the import
direction stays platform→package. `test_shims_reexport_authoritative_objects` asserts
object identity with the package implementations, so no second implementation can
hide there. The removed `BREMEN_WORKFLOW_ID`/`BREMEN_MODEL_ID`/etc. constants have no
remaining importers (grep-verified). Deprecation is documented in each shim
docstring; removal is listed as PR0155 cleanup.

## Input boundary (PR0153 coupling resolution)
**PASS.** The lazy `xrd_normalization` import was lifted out of the science module:
`runtime.validate_measurements()` now performs the same structural canonical
validation (side/1-D finite strictly-increasing q matching intensity length) through
the same platform validator at the runtime boundary, mapping any violation to the
identical fixed safe reason `invalid_scientific_profiles`. It runs on every path —
`build_features()` and therefore `run()`/`predict_model()` — in the same position
(after shape validation, before science) as the PR0152 in-module guard.
`test_package_raw_canonical_validation_fail_closed` (reversed q → fail closed) and
the retargeted PR0152 regression test prove identical behavior. Science modules are
now platform-import-free.

## Aramina regression
**PASS — unchanged.** No Aramina file is modified in this PR. `test_aramina_workflow_
runtime.py` + `test_aramina_provider_contract.py` + `test_bremen_workflow_aramina_
scaffold.py` → **282 passed**. The two remaining Aramina coupling points
(`ModelInput.container_path`, `patient_id` binding) are explicitly deferred to
PR0155 in the contract doc and PLAN.

## Public API compatibility
**PASS.** No endpoint, report field, auth, job-lifecycle, `model_id`, threshold,
frontend or PDF change. Provider payload keys byte-identical to PR0153B;
`BREMEN_V01_FEATURE_COLUMNS` retained; failed Bremen behavior identical (`Incompatible:
requires_exactly_3_left_3_right`, `Feature construction failed:
invalid_scientific_profiles`, `Model execution failed` — proven by the retargeted
regression tests). Contract doc changes are additive implementation notes; ADR-0016
and the accepted contract rules are untouched.

## Security/privacy
**PASS.** Package diagnostics remain fixed safe constants
(`test_package_scientific_failure_is_safe` asserts a planted sensitive exception
produces only `invalid_scientific_profiles` with no substring leakage);
`to_input_requirements` and the manifest contain only static model-declared values;
no filesystem paths, S3 keys, artifact private paths, tracebacks, tokens, environment
variables or patient-identifying data in the new modules; no real H5 or patient data
committed; no binaries added.

## Binary/artifact check
**PASS.** Untracked/new content is source, tests and Markdown only. No training
repository, ZIP, real H5, unapproved joblib/pickle, binary model copy or private
data. No artifact relocation occurred, so no byte-identity check was required; the
artifact provenance constant in `manifest.py` matches the PR0151/PR0152-verified
SHA256 of the existing training-repository artifact.

## PR0155 readiness
**PASS — suitable for MLflow PyFunc-style packaging without moving science again.**
The runtime is a self-contained class implementing the common contract with declared
dependencies (`manifest.RUNTIME_DEPENDENCIES = ("numpy","pandas","scipy")`); a future
framework wrapper can call `BremenRuntime.predict_model`/`run` directly. Remaining
coupling, explicitly identified and documented: (1) the two platform bridges above
(decision vocabulary + canonical validator) — acceptable documented seams; (2) the
portable parameter dict is still loaded by platform staging rather than packaged
inside the release directory (PR0155 metadata work); (3) exact dependency pinning and
release-directory packaging deferred to PR0155; (4) shim removal after caller
migration; (5) Aramina coupling points are Aramina-owned.

## Targeted tests (executed during this review)
- `python -m compileall -q src tests` → **exit 0**.
- `pytest -q tests/test_bremen_v01_package.py` → **50 passed**.
- `pytest -q tests/test_bremen_3x3_runtime_parity.py tests/test_bremen_3x3_training_
  parity.py tests/test_bremen_workflow_bremen.py tests/test_bremen_runtime_plugin.py`
  → **151 passed**.
- `pytest -q tests/test_bremen_model_runtime_contract_v1.py
  tests/test_bremen_model_requirements_api.py tests/test_bremen_inference_integration.py`
  → **82 passed, 1 skipped**.
- Aramina suites → **282 passed**.
- Registry/multi-model/catalog/training-runtime-separation/job/report/decision suites
  → **166 passed**.

## Full pytest
`pytest -q` → **4201 passed, 11 skipped, 0 xfailed** (43.21s, exit 0). Collection
reconciliation verified with `git stash -u`: base 4161 collected → worktree 4212
(+51 = 50 new package tests + 1 auto-parametrized guard over the new test file);
**0 tests removed or weakened** (test diffs are seam renames and scan extensions only).

## Changed-file Ruff
All 14 changed/new Python files → **All checks passed!** (includes the previously
pre-existing-F401 file `workflow_provider.py`, which this PR does not modify).
Repository-wide `ruff check .` → 355 findings, identical pre-existing baseline to the
PR0153B review; zero findings introduced by this PR.

## git diff --check
**exit 0** (no whitespace errors).

## Legacy and import search results
- Old-path implementations vs re-exports: `bremen_features.py` / `inference.py` /
  `bremen_runtime.py` contain **zero definitions** (AST + grep `^def|^class` → 0);
  they are identity re-exports of the package objects (tested).
- Forbidden imports in the package: **none** (see Forbidden import search).
- Platform provider scientific math: **none** (`workflow_bremen.py` scientific-pattern
  grep → none; only event-diagnostic counting).
- Duplicate model artifacts: **none** (no binary added or copied; single provenance
  constant referencing the existing verified artifact).

## Risks / non-gating notes
1. Three re-export shims remain by design (four active platform importers + test
   seams); they are zero-logic, identity-tested, deprecated, and their removal is
   PR0155 cleanup. Any future monkeypatch of shim attributes would not affect
   package-internal globals — verified no such caller remains (seams retargeted).
2. The package runtime imports two platform modules by documented decision
   (`api.decision_contract` for the platform-owned decision vocabulary — the numerical
   threshold comparison itself stays in the package predictor — and
   `api.xrd_normalization.validate_canonical_measurement` for the platform canonical
   input-structure contract). This is an accepted V1 boundary; zero-`bremen.api`
   packaging is listed as optional PR0155 work.
3. `manifest.THRESHOLD_VALUE` and `ARTIFACT_SHA256` are provenance/reconciliation
   constants; the applied threshold always comes from the loaded artifact predictor
   (unchanged behavior, grep-verified no platform threshold literal).
4. Live deployment identity verification (PR0152 post-deploy smoke) remains an
   operator step; unaffected by this packaging refactor.
5. The provider's `_validate_model_internal` treats a runtime without `model_ready`
   as ready (fake-runtime seam from PR0153B) — unchanged; production
   `BremenRuntime` always provides it.
6. The subprocess isolation test pins the entry point's import surface; it is
   environment-dependent only in that it runs the repo's own interpreter.

## FINAL VERDICT

**READY FOR COMMIT**

All required conditions hold: the Bremen v0.1 package is inference-complete and owns
the full scientific implementation (requirements, 3+3 validation, preprocessing,
q-grid, smoothing, normalization, aggregation, replicate variation, 15 features,
imputation/scaling, portable estimator, threshold, diagnostics, identity); the moves
are mechanically proven semantics-preserving (predictor 100% identical, science
identical except the lifted lazy import with identical guard behavior at the runtime
boundary); `WorkflowProvider` remains orchestration-only; direct package golden
inference passes without the provider; PR0151/PR0152 parity remains exact (151
regression tests green); exactly one active production Bremen scientific
implementation exists (shims are zero-logic identity re-exports); no forbidden
reverse platform dependencies and no cycles; requirements and artifact interpretation
are runtime/package-owned with no divergent platform truths; public API, Aramina,
routing, auth, job lifecycle, model_id and threshold are unchanged; no private or
binary additions; full pytest (4201 passed, 11 skipped), changed-file Ruff (all
pass) and `git diff --check` (exit 0) all pass.

Do not commit (review-only task).
