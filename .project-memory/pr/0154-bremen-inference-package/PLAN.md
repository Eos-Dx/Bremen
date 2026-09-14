# PR0154 — Bremen v0.1 inference-complete model package

## Branch / HEAD

- Branch: `0154-bremen-inference-package`
- HEAD at plan time: `c92f9f0a437efc07b499c833acff69b2879dcb11`
  ("refactor: implement model runtime contract v1", #214). Clean worktree.

## Source-of-truth review

- Model Runtime Contract reviewed: `docs/model_runtime_contract_v1.md`
  (incl. PR0153B implementation notes and PR0154 coupling list) and
  `docs/adr/0016-model-runtime-contract-v1.md` (Accepted).
- PR0151/PR0152 parity evidence reviewed: `docs/bremen_3x3_training_parity.md`
  (Parts 1+2), `.project-memory/pr/0151-*/{PLAN,PRECOMMIT_REVIEW}.md`,
  `.project-memory/pr/0152-*/{PLAN,PRECOMMIT_REVIEW,IMPLEMENTATION_REPORT}.*`,
  `.project-memory/pr/0153b-*/{PLAN,PRECOMMIT_REVIEW,IMPLEMENTATION_REPORT}.*`.
- Current implementations read completely: `src/bremen/model_runtime.py`,
  `src/bremen/bremen_runtime.py`, `src/bremen/bremen_features.py`,
  `src/bremen/inference.py`, `api/workflow_bremen.py`,
  `api/model_requirements.py`, `api/workflow_orchestrator.py`,
  `api/workflow_registry.py`, plus artifact/manifest conventions:
  `model_package.py` (ADR-0007 artifact-directory contract),
  `model_package_source.py`, `api/s3_model_discovery.py`, `model_loader.py`,
  `api/decision_contract.py`, `api/inference_handler.py`,
  `api/feature_artifact_prediction.py`.

## Current Bremen scientific files (assessment)

- `src/bremen/bremen_features.py` — 100% Bremen model science (frozen numerics,
  15-feature builder, 3+3 shape gate, `BremenFeatureError`). Contains one
  platform coupling: lazy import of `validate_canonical_measurement` from
  `api.xrd_normalization` (flagged by PR0152/PR0153B as PR0154 work).
  -> MOVE into the package; lift the canonical-measurement validation up to
  the runtime boundary so the package science core is platform-free.
- `src/bremen/inference.py` — portable-logreg artifact contract
  validator/scorer for the Bremen v0.1 release (validates the exact frozen
  15-column schema, imputation, scaling, sigmoid, threshold). 100% Bremen
  package contract + math. -> MOVE into the package as `predictor.py`.
  NOTE: five platform modules and several tests import `bremen.inference`
  symbols; they keep working through a documented compatibility shim (no
  behavior change).
- `src/bremen/bremen_runtime.py` — Model Runtime Contract v1 reference
  implementation (requirements/validate/predict + PR0152 frozen sequence).
  -> MOVE into the package as the authoritative runtime entry point.
- `api/decision_contract.py` — platform decision-vocabulary authority used by
  six platform modules (events, reports, registry, discovery). NOT Bremen
  math; stays platform-owned. The package runtime consumes it exactly as the
  PR0153B runtime does today (documented runtime-vs-platform seam; the
  numerical threshold comparison already happens inside package predictor
  math; `build_decision` only projects the established vocabulary).
- `bremen/model_runtime.py` — the common contract. Unchanged; platform-owned.

## Chosen package layout

Repository conventions inspected: `bremen/model_package.py` is an artifact-
directory contract (manifest+checksum) — a different concern, reused
conceptually, not duplicated; `src/bremen/training/` proves the subpackage
convention. No existing Python model-package location exists, so the
least-invasive structure consistent with the repo:

    src/bremen/model_packages/
      __init__.py            # package root (no science, no platform imports)
      bremen_v01/
        __init__.py          # single entry point: re-exports runtime surface
        manifest.py          # authoritative model identity/release constants
                             # + inference-completeness contract declaration
        features.py          # MOVED bremen_features (science only; the lazy
                             # api.xrd_normalization import is lifted out)
        predictor.py         # MOVED inference.py (portable_logreg contract)
        runtime.py           # BremenRuntime — Model Runtime Contract v1 entry

The platform consumes only the package entry point
(`bremen.model_packages.bremen_v01`), not individual scientific helpers.

## Authoritative runtime entry point

`bremen.model_packages.bremen_v01.runtime.BremenRuntime` (re-exported by the
package `__init__`) implements `bremen.model_runtime.ModelRuntime`
(`model_requirements` / `validate_model_input` / `predict_model`) with the
PR0152 frozen sequence unchanged. One authoritative active implementation;
the old top-level modules become re-export compatibility shims (documented
below) because many platform/test callers import `bremen.inference` /
`bremen.bremen_runtime` paths today; shims contain zero logic so no duplicate
implementation exists.

## Artifact loading ownership

The portable parameter dict (`portable_logreg`, nested
`feature_schema.feature_columns` / `decision.threshold`) interpretation is
package-owned: `predictor.py` owns `adapt_package_contract`,
`validate_package_contract`, `predict_proba_portable`,
`PortableLogRegModelError` (shim retains the historical
`adapt_model_package` / `validate_portable_logreg_model` names for external
callers). The runtime resolves `model_id` / `model_version` / threshold
provenance from the loaded package through package code (`model_metadata`).
Platform never inspects coefficients, scaler arrays, feature columns or
threshold: routing/discovery continue to pass the opaque loaded package to
the provider, which hands it to the runtime. Physical artifact staging and
integrity (S3, checksums, manifest directories) remain platform
responsibilities (`model_registry` / `s3_model_discovery` / `model_package`
unchanged; no second manifest system is created — the package `manifest.py`
is Python release-contract metadata, not an artifact-directory manifest).

## Requirements ownership

Package-owned: `manifest.py` declares the input contract (3 LEFT + 3 RIGHT,
six total, request fields, feature-schema version);
`runtime.model_requirements()` assembles the `ModelRequirements` view.
Platform `api/model_requirements.py` already derives from
`runtime.model_requirements()` (PR0153B) — no platform-side duplication of
Bremen scientific requirements remains (the last literals lived in
`bremen_runtime.py` and move into the package). Parity tests lock
platform-visible derivation against package declaration.

## Identity ownership

Authoritative package identity: `model_packages/bremen_v01/manifest.py`
— release `model_id=bremen-paper-reference-v0-2-0`,
`name=bremen_paper_reference_symmetry_logreg`,
`version=0.2.0-paper-reference`, feature schema `v0.1`, artifact SHA256
`65866f441a...` provenance, threshold identity `0.3585907282566089`
(PR0151/PR0152 evidence). The runtime compatibility shim no longer defines
these constants (duplication removed). Platform registry/catalog selection
identifiers (`bremen_mri_triage_logreg` provider default, registry
`model_id`s) are unchanged public identifiers; documented as platform routing
identity vs release identity, reconciled through the contract
(`model_requirements().model_id`, `RuntimePrediction.model_id`). No public
identifier changes in this PR.

## Dependency direction

- platform (`api/*`) -> `bremen.model_runtime` (contract) and -> package entry
  `bremen.model_packages.bremen_v01`.
- package runtime -> package science + platform decision-vocabulary module +
  platform canonical-measurement validation (runtime boundary only).
- package science (`features.py`, `predictor.py`, `manifest.py`) ->
  numpy/pandas/scipy/stdlib only.
- contract -> stdlib only.
- Forbidden (tested): the package importing `api.workflow_bremen`, report
  providers, job handlers, FastAPI, auth, frontend, storage/S3 code.
- No cycles (package does not import `bremen_runtime` shim or
  `workflow_bremen`; contract imports nothing platform).

## Input boundary / PR0153 coupling resolution

- lazy `xrd_normalization` import: lifted out of the science module. The
  package runtime validates canonical measurements (side/position/q/intensity
  structure) through the existing platform validator at its boundary and then
  passes plain arrays to pure package science. Numerical behavior identical;
  the same guard still runs on every platform path because it runs on every
  runtime call path (`run`/`build_features` unchanged order).
- `container_path` / `patient_id` coupling: Aramina-owned. Bremen v01 ignores
  them; Aramina untouched; remaining coupling documented for PR0155.
- identity constants: now package-owned (above).

## Compatibility import strategy

Three thin re-export shim modules retained (documented, zero logic,
`__all__` mirrors previous public surface):
`bremen/bremen_features.py`, `bremen/inference.py`,
`bremen/bremen_runtime.py`. Justification: AST search proved five active
platform modules import `bremen.inference` (`feature_artifact_prediction`,
`inference_handler`, `s3_model_discovery`, `server`) and several tests import
the other paths; deleting them would churn unrelated call sites (out of
scope). Shims import from the package — direction stays platform->package
(allowed). Test monkeypatch strings targeting
`bremen.bremen_runtime.build_bremen_features` are updated in place to the
same seam at its authoritative module
(`bremen.model_packages.bremen_v01.runtime.build_bremen_features`) — path
rename only, same behavior. `workflow_bremen.BREMEN_V01_FEATURE_COLUMNS`
retains its name (public constant) sourced from the package runtime class.

## Expected files

Moved/created:
- `src/bremen/model_packages/__init__.py` (NEW)
- `src/bremen/model_packages/bremen_v01/__init__.py` (NEW entry point)
- `src/bremen/model_packages/bremen_v01/manifest.py` (NEW)
- `src/bremen/model_packages/bremen_v01/features.py` (MOVED from
  `bremen_features.py`; canonical-measurement lazy import lifted out)
- `src/bremen/model_packages/bremen_v01/predictor.py` (MOVED from
  `inference.py`)
- `src/bremen/model_packages/bremen_v01/runtime.py` (MOVED from
  `bremen_runtime.py`)
Shimmed (re-export only): `bremen/bremen_features.py`, `bremen/inference.py`,
`bremen/bremen_runtime.py`.
Changed: `src/bremen/api/workflow_bremen.py` (imports the package entry point
only).
Tests: `tests/test_bremen_v01_package.py` (NEW direct golden self-test +
import-direction tests); in-place monkeypatch-path updates in
`tests/test_bremen_3x3_runtime_parity.py` and
`tests/test_bremen_model_runtime_contract_v1.py`.
Docs: `docs/bremen_v01_inference_package.md` (NEW); status/notes clarification
in `docs/model_runtime_contract_v1.md` (PR0154 coupling items resolved).

## Non-goals

No retraining; no science/threshold/formula changes; no artifact replacement;
no new artifact format; no Aramina packaging/moves/behavior changes; no
MLflow/BentoML/KServe; no new network service; no repository split; no API/
report/auth/job/frontend/PDF changes; no registry/S3 discovery redesign; no
changes to `model_runtime.py` contract semantics.

## Test strategy

- Direct package golden self-test WITHOUT WorkflowProvider (new suite):
  15 features + probability + decision/threshold vs PR0151 frozen fixture
  (atol 1e-10, rtol 0); package `model_requirements` contract;
  `validate_model_input` exact 3+3 and invalid shapes; all-six participation;
  LEFT/RIGHT permutation invariance; replicate variance (`ddof=1`) and sigma
  semantics; raw-peak + gate semantics; portable estimator + threshold
  parity; package science modules carry no platform imports.
- Regression: existing PR0151/PR0152 parity suites (raw-H5 job path included,
  unchanged assertions), PR0153B contract suite, workflow/plugin/requirements/
  registry/orchestrator/multi-model/job/report suites, Aramina suites.
- Search checks: exactly one active scientific implementation per concern
  (shims re-export only); no reverse imports (package -> workflow/platform
  handlers).

## Validation commands

- `python -m compileall -q src tests`
- `pytest -q tests/test_bremen_v01_package.py`
- `pytest -q tests/test_bremen_3x3_runtime_parity.py tests/test_bremen_3x3_training_parity.py tests/test_bremen_workflow_bremen.py tests/test_bremen_runtime_plugin.py`
- `pytest -q tests/test_bremen_model_runtime_contract_v1.py`
- `pytest -q tests/test_bremen_model_requirements_api.py tests/test_bremen_inference_integration.py`
- `pytest -q tests/test_aramina_workflow_runtime.py tests/test_aramina_provider_contract.py tests/test_bremen_workflow_aramina_scaffold.py`
- `pytest -q tests/test_bremen_workflow_registry.py tests/test_multi_model_execution.py tests/test_catalog_api_multi_model.py`
- `pytest -q`
- `ruff check` on every changed/new Python file
- `git diff --check`
- duplicate-science + forbidden-import searches (documented in final report)
