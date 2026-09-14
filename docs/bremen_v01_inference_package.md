# Bremen v0.1 Inference-Complete Model Package

Status: Implemented by PR0154 (packaging refactor; no scientific change)

Scope boundary

This document describes the Bremen v0.1 model package: the inference-complete
Bremen scientific runtime relocated behind a model-package boundary at
`src/bremen/model_packages/bremen_v01/`.

PR0154 is a packaging / import-direction refactor. It does not retrain the
model, does not change scientific formulas, thresholds, features, the portable
artifact, the public API, reports, jobs, auth, routing or Aramina. PR0151 and
PR0152 remain the scientific source of truth; PR0153B remains the platform/
model contract boundary (Model Runtime Contract v1).

Research decision support requiring radiologist review. No clinical or release
claim is established by packaging.

Why the package exists

Model Runtime Contract v1 (`docs/model_runtime_contract_v1.md`, ADR-0016)
states: Bremen Platform orchestrates inference; model runtimes implement
scientific inference. Before PR0154 the platform still owned the Bremen
scientific files (`bremen_runtime.py`, `bremen_features.py`, `inference.py`)
and duplicated Bremen model identity. PR0154 moves the complete Bremen v0.1
scientific runtime behind the package boundary so the platform depends only on
the contract and the package entry point.

Package layout

    src/bremen/model_packages/
      __init__.py               # package root; no science, no platform imports
      bremen_v01/
        __init__.py             # single entry point (re-exports runtime surface)
        manifest.py             # authoritative release identity + input contract
                                # + provenance + declared runtime dependencies
        features.py             # frozen 15-feature science (was bremen_features)
        predictor.py            # portable_logreg contract + math (was inference)
        runtime.py              # BremenRuntime — Model Runtime Contract v1 entry

There is exactly ONE active authoritative Bremen v0.1 production scientific
implementation: this package. `bremen_features.py`, `bremen_runtime.py` and
`inference.py` are now zero-logic re-export compatibility shims (see below).

Runtime entry point

`bremen.model_packages.bremen_v01.runtime.BremenRuntime` (also re-exported by
`bremen.model_packages.bremen_v01`) implements `bremen.model_runtime.ModelRuntime`:

- `model_requirements()` -> `ModelRequirements` (3 LEFT + 3 RIGHT, six total,
  request fields, identity, feature schema version — assembled from
  `manifest`).
- `validate_model_input(input)` -> `ModelValidation` (exact 3+3 shape; the
  established `requires_exactly_3_left_3_right` safe reason).
- `predict_model(input, on_features=None)` -> `RuntimePrediction` (the frozen
  PR0152 `run()` sequence: validate -> build features -> score -> decide,
  translated into contract error categories with byte-identical safe reasons).

The package also retains the PR0152 internal methods used by the platform
adapter: `model_ready()`, `build_features()`, `score()`, `run()`,
`model_metadata`, and `validate_measurements()` (see Input boundary).

Scientific ownership

The package owns, unchanged from PR0152: exact 3+3 validation; per-profile ROI
crop, Savitzky–Golay smoothing, p05 normalization (narrow ROI no-op);
overlapping finest-median-step common grid and interpolation; per-side
arithmetic mean and sample std (`ddof=1`); the two bands; original-profile raw
peaks and the `mean_peak_value_raw >= 0.6` gate; the frozen 15-feature order;
imputation and scaler arithmetic; portable logistic-regression inference; the
model-owned threshold and decision projection; safe scientific diagnostics;
and release identity/provenance.

Artifact loading ownership

`predictor.py` owns interpretation and execution of the Bremen portable
artifact contract (`portable_logreg`, with the nested
`feature_schema.feature_columns` / `decision.threshold` adaptation added in
PR0152): `adapt_model_package`, `validate_portable_logreg_model`,
`predict_proba_portable`, `PortableLogRegModelError`. The runtime resolves
`model_id` / `model_version` / threshold provenance from the loaded package in
package code. The platform never inspects coefficients, scaler arrays, feature
columns or the threshold: routing/discovery pass an opaque loaded package dict
to the provider, which hands it to the runtime.

Physical artifact staging, checksum verification and manifest-directory
validation (ADR-0007) remain platform responsibilities
(`bremen.model_package`, `api.s3_model_discovery`, `api.model_registry`),
unchanged. The package `manifest.py` is Python release-contract metadata, not
a second artifact manifest system.

Model identity ownership

`manifest.py` is the single authoritative source for Bremen v0.1 release
identity, from PR0151/PR0152 evidence:

    MODEL_ID              = bremen-paper-reference-v0-2-0
    MODEL_NAME            = bremen_paper_reference_symmetry_logreg
    MODEL_VERSION         = 0.2.0-paper-reference
    FEATURE_SCHEMA_VERSION= v0.1
    THRESHOLD_VALUE       = 0.3585907282566089 (provenance; applied value
                           always comes from the loaded artifact predictor)
    ARTIFACT_SHA256       = 65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0

Platform routing identity (registry/catalog `model_id`s and the
`BremenProvider` default `bremen_mri_triage_logreg`) is unchanged: these are
platform selection identifiers, distinct from the model release identity the
package owns. They reconcile through the contract
(`model_requirements().model_id`, `RuntimePrediction.model_id`). No public
identifier changed in PR0154. This distinction is documented duplication-free:
release identity lives only in `manifest.py`.

Model requirements ownership

Bremen-specific requirements are declared only in the package
(`manifest.py`) and surfaced through the runtime
(`model_requirements()`). The platform Model Requirements API already derives
from the runtime (PR0153B), so no platform module re-declares the 3+3
scientific requirements. The additive `container_requirements.model_runtime`
response block continues to flow from the runtime.

Input boundary and PR0153 coupling

PR0153B documented three Bremen-relevant coupling points; two are resolved
here:

- Resolved — lazy `bremen.api.xrd_normalization` import in the science module.
  Structural canonical-measurement validation (side, 1-D finite strictly
  increasing q matching intensity length) moved to the runtime boundary
  `runtime.validate_measurements()`, which calls the same platform validator
  and preserves the identical fixed safe reason `invalid_scientific_profiles`.
  The pure science module (`features.py`) now imports only numpy/pandas/scipy
  and stdlib. The check still runs on every platform path because the runtime
  `run()`/`build_features()` call order is unchanged.
- Resolved — duplicate identity constants in the former `bremen_runtime.py`
  are gone; identity is sourced from `manifest.py`.
- Remaining (Aramina-owned, out of PR0154 scope) — `ModelInput.container_path`
  and `ModelInput.patient_id` / `_validate_aramina_source` are consumed by the
  Aramina artifact pipeline; PR0154 packages Bremen only. Deferred to PR0155.

The package runtime imports exactly two platform modules and nothing else:
`api.decision_contract` (the platform decision-vocabulary authority shared by
events/reports/registry) and `api.xrd_normalization.validate_canonical_measurement`
(the input-structure contract). The numerical threshold comparison stays inside
the package predictor.

Dependency direction

- platform (`api/*`, `workflow_bremen.py`) -> `bremen.model_runtime` (contract)
  and -> package entry `bremen.model_packages.bremen_v01`.
- package science (`features.py`, `predictor.py`, `manifest.py`) ->
  numpy/pandas/scipy/stdlib only (no `bremen.api`, no workflow/report/job/
  FastAPI/auth/storage imports).
- package runtime -> package science + the two platform modules above +
  `bremen.model_runtime` (types only).
- contract (`bremen.model_runtime`) -> stdlib only.
- The package never imports `workflow_bremen`, report providers, job handlers,
  FastAPI, auth, frontend or storage code; the contract never imports the
  package. No cycles.

Golden self-test (package proves independent inference)

`tests/test_bremen_v01_package.py` invokes the package runtime WITHOUT any
WorkflowProvider and asserts, against the PR0151 frozen fixture (atol 1e-10,
rtol 0): exact 15 features, exact probability (0.7388733541967353),
decision/threshold behavior, exact 3+3 requirements, validation of all invalid
shapes, all-six participation, LEFT/RIGHT permutation invariance, replicate
variance (`ddof=1`), peak semantics, raw-peak gate, portable estimator parity,
and the import-direction guarantees (including a subprocess check that merely
importing the package entry point loads no platform workflow/report/job/FastAPI
module). Platform-level integration still proves `BremenProvider` can invoke
the package (existing PR0151/PR0152/PR0153B suites are unchanged).

Compatibility shims

`bremen/bremen_features.py`, `bremen/inference.py` and
`bremen/bremen_runtime.py` are re-export-only shims (zero logic: no function
or class definitions). Justification: AST search proved several active platform
modules import `bremen.inference` (feature_artifact_prediction,
inference_handler, s3_model_discovery, server) and historical test seams import
the other paths; keeping the import paths resolving avoids unrelated churn.
Shims import from the package (direction stays platform -> package, allowed).
They are documented as deprecated; new code imports the package entry point.

Dependencies

Package runtime scientific dependencies are numpy, pandas and scipy (declared
in `manifest.RUNTIME_DEPENDENCIES`). Global dependency management is unchanged.
Full environment capture, dependency pinning provenance, and any migration of
the portable parameter dict into a self-contained release artifact directory
are PR0155 packaging-metadata work; PR0154 introduces no MLflow/BentoML/KServe
metadata and no new artifact format.

Public API compatibility

No endpoint, field, report, auth, job-lifecycle, model_id or threshold change.
`workflow_bremen.BREMEN_V01_FEATURE_COLUMNS` remains exported (now sourced from
the package runtime class). Provider payload keys are byte-identical to
PR0153B.
