# Model Package Standard v1

Status: Implemented by PR0156 (framework-independent ownership standard).

Purpose

This document defines a single, framework-independent standard for a
deployable inference-complete model package.  Both Bremen and Aramina conform
to the same semantic ownership boundary.  The standard complements — it does
not replace — Model Runtime Contract v1 (ADR-0016).

The core rule

Bremen Platform orchestrates inference.  Each model package owns its complete
model-specific scientific inference and exposes a Model Runtime Contract v1
runtime entry point.  A future packaging system such as MLflow can wrap any
conforming package without moving scientific logic or teaching the platform how
the model works.

Three distinct layers

Layer                              | Owns                                   | Document
-----------------------------------|----------------------------------------|---------------------------
Bremen Platform                    | auth, sources/containers, storage, jobs, routing, events, public API, reports, frontend | `docs/architecture.md`, ADRs 0001–0015
Model Runtime Contract v1          | callable runtime semantics: requirements / validate / predict (`bremen.model_runtime.ModelRuntime`) | `docs/model_runtime_contract_v1.md`, ADR-0016
Model Package Standard v1 (this)   | deployable ownership boundary: what a conforming package owns and exposes | this document, ADR-0017
Packaging technology (future)      | catalog/registry/distribution around a conforming package (MLflow, …) | `docs/mlflow_model_packaging_spike.md` (PR0155; non-binding until a packaging PR)

Model Runtime Contract v1 defines the *callable* semantics.  Model Package
Standard v1 defines the *deployable ownership* boundary around a runtime.  They
are orthogonal: contract = interface; standard = package.  Neither prescribes a
framework.

Platform responsibilities

- authentication and authorization
- source/container registration
- storage access and artifact staging
- job creation and lifecycle
- routing and model selection
- timeouts, retries and execution orchestration
- audit events and operational diagnostics
- report envelope and links
- public API endpoints
- security, sanitization and redaction
- frontend integration

Model package responsibilities

- model identity
- model-specific input requirements
- scientific input validation
- artifact interpretation (the model's own artifact contract)
- scientific preprocessing
- measurement semantics
- feature generation
- aggregation / statistics
- model-specific normalization
- estimators
- model-owned threshold and postprocessing
- safe model diagnostics
- scientific provenance
- golden contract evidence
- runtime dependency declaration / release metadata

Hard rules

1. WorkflowProvider MUST NOT contain model-specific scientific inference logic.
2. Platform code MUST NOT inspect model coefficients, feature formulas,
   preprocessing internals, thresholds or artifact-specific scientific fields.
3. The Model Package Standard is independent of MLflow, BentoML, KServe,
   FastAPI, HTTP, S3 credentials, job objects, reports and frontend concerns.
   Conforming packages must remain free of these dependencies.

Conformance requirements

Every conforming package must have a clear authoritative source for each of:

1. package/model identity,
2. model requirements (input contract),
3. model input validation,
4. a runtime entry point implementing Model Runtime Contract v1,
5. artifact loading/interpretation where applicable,
6. complete scientific inference (input → structured decision),
7. threshold / postprocessing ownership,
8. safe diagnostics,
9. scientific provenance,
10. direct package-level golden tests,
11. a dependency/import boundary suitable for later standalone packaging.

The standard is structural, not an inheritance hierarchy.  There is no
`ModelPackageBase`; Model Runtime Contract v1 already provides the runtime
interface.  Conformance is asserted by tests (contract satisfaction, manifest
identity/requirements presence, package entry point presence, import-direction
guards, direct-vs-provider prediction equality) rather than by a shared base
class.

Dependency direction

    platform  →  ModelRuntime contract  →  model package public entry  →  package science

Forbidden (reverse) direction:

    package  ↛  workflow provider / job lifecycle / HTTP / FastAPI /
                report providers / auth / S3 credentials / frontend

Remaining narrow bridges (allowed, documented, non-circular):

- Bremen runtime consumes `bremen.api.decision_contract` (platform-owned
  decision *vocabulary*, shared by events/reports/registry; Aramina has its own
  report vocabulary and does not use it).  The numerical threshold comparison
  lives inside the package predictor.  This bridge is classified as
  **platform-specific** and is preserved; a future packaging PR may relocate
  it behind an adapter.
- Both runtimes consume `bremen.canonical_input` — the neutral, stdlib/numpy-
  only home of the canonical XRD measurement vocabulary (re-exported by
  `bremen.api.xrd_normalization` for platform callers).  This bridge is
  classified as **generic cross-model contract** and is the PR0156 answer to
  PR0154's flagged `api.xrd_normalization` coupling for the model-runtime path.
- Aramina inference defaults `_validate_aramina_source` to a lazy lookup of
  `bremen.api.workflow_orchestrator._validate_aramina_source`.  H5 patient/source
  identity binding remains a platform concern; the call lives at the runtime
  boundary for behavior parity with PR0153B and is documented as remaining
  PR0155 work to lift it fully to the platform (see the contract doc).
- Aramina inference loads its staged artifact through the narrow, framework-free
  bridge `bremen.model_packages_bridge.load_staged_artifact` (same error
  contract preserved from `s3_model_discovery._load_staged_artifact`).  The
  package interprets the loaded object; the platform only stages/verifies.

Golden direct-package evidence

A conforming package must be testable without its WorkflowProvider.  Both
reference packages ship direct golden/self tests:

- `tests/test_bremen_v01_package.py` — direct 15-feature + probability parity
  against the PR0151 fixture (atol 1e-10, rtol 0; golden probability
  `0.7388733541967353`) and requirements/validation/gate parity.
- `tests/test_aramina_v0213_package.py` — direct package runtime on synthetic
  artifacts producing the same report fields/decisions as the provider path,
  plus target-side, threshold-flip, taxonomy and leak checks.

Common conformance is asserted by
`tests/test_bremen_model_package_standard_v1.py`, parametrized over both
packages: ModelRuntime satisfaction, requirements/validation/predict
availability, identity/provenance presence, forbidden reverse-import absence,
provider-routes-through-package-runtime.  Structural deduplication is guarded
by `tests/test_bremen_model_package_deduplication.py`.  HTTP-surface freeze is
guarded by `tests/test_bremen_api_freeze_pr0156.py`.

Reference implementations

- Bremen v0.1 — `src/bremen/model_packages/bremen_v01/` (PR0154).
- Aramina v0.2.13 — `src/bremen/model_packages/aramina_v0213/` (PR0156).

The two packages share the *responsibility* set and the *platform-facing
contract*, not internal layout or algorithms.  Aramina keeps its joblib/sklearn
artifact and subprocess preprocessing; Bremen keeps its portable-logreg dict
and sklearn-free math.  The standard normalizes ownership, not artifact format.

Compatibility shims

`bremen.bremen_features`, `bremen.inference`, `bremen.bremen_runtime`,
`bremen.api.aramina_preprocessing`, `bremen.api.aramina_symmetry` and
`bremen.api.aramina_artifact_compat` are re-export-only shims (zero logic) that
preserve import paths for external callers and test seams during the
transition.  `bremen.api.workflow_aramina` retains the platform provider and a
transitional re-export surface.  New code imports package entry points.
Monkeypatch seams were retargeted to the authoritative package modules so the
patched module is the same module the pipeline resolves the attribute on
(PRE-0154 precedent).  Shims are removed after migration in a follow-up.

Framework adoption and packaging

Adopting MLflow (or any equivalent) is a separate, additive decision.  A
packaging PR wraps a *conforming* package's runtime entry point; it must not
move scientific logic back into the platform or introduce a parallel second
runtime contract.  The PR0155 spike documents the recommended approach
(pyyfunc + narrow pyfunc loader + JSON model params + explicit pinned serving
dependencies + Model Registry deferred).

Non-goals

- no requirement to adopt any specific framework;
- no requirement that packages share internals, file layout or artifact format;
- no runtime network serving contract imposed by the standard (that is
  deployment's problem);
- no Model Registry (deferred);
- no public HTTP surface introduced by the standard.

Migration

- PR0152 — dedicated Bremen scientific runtime.
- PR0153B — Model Runtime Contract v1 formalized platform-side.
- PR0154 — Bremen v0.1 packaged as inference-complete.
- PR0155 — MLflow packaging spike (research; no production change).
- PR0156 — Model Package Standard v1 defined; Aramina v0.2.13 packaged to the
  same ownership boundary.
- PR0155+ (next) — MLflow pyfunc wrapper over a conforming package; then Model
  Registry evaluation on proven local packaging.

Acceptance principle

A model release is conforming to Model Package Standard v1 only when Bremen
Platform can invoke the packaged runtime through Model Runtime Contract v1
without importing or reproducing any model-specific scientific logic, and the
package's own golden tests reproduce its scientific decisions when executed
without the platform.
