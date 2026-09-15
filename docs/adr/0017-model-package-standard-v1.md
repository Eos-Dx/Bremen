# ADR-0017: Model Package Standard v1

Status: Accepted

Context

ADR-0016 established Model Runtime Contract v1: platform orchestration calls a
model runtime through requirements()/validate()/predict() and must not
reimplement model science.  PR0154 packaged Bremen behind this contract.  The
MLflow research spike (PR0155) recommended wrapping an already-correct package
with a framework and explicitly deferred framework adoption.

Aramina already conformed to the *runtime contract* (PR0153B adapter) but its
scientific pipeline was still physically located in the platform/API namespace
(`bremen.api.workflow_aramina`, `bremen.api.aramina_preprocessing`,
`bremen.api.aramina_symmetry`, `bremen.api.aramina_artifact_compat`,
`bremen.api.aramina_preprocess_worker`).  Without a common package standard
each model would keep an ad-hoc notion of "the boundary", which produces
inconsistent ownership, divergent dependency direction and prevents a
framework-agnostic packaging step.

Decision

Bremen Platform adopts a single, framework-independent Model Package Standard
v1 that defines the deployable ownership boundary around the existing Model
Runtime Contract v1 runtime.

Every model package must have one authoritative source for each of:

1. package/model identity,
2. model requirements (input contract),
3. model input validation,
4. runtime entry point implementing `bremen.model_runtime.ModelRuntime`,
5. artifact loading/interpretation where applicable,
6. complete scientific inference (input to structured decision),
7. threshold/postprocessing ownership,
8. safe model diagnostics,
9. scientific provenance,
10. direct package-level golden tests,
11. dependency/import boundary suitable for later standalone packaging.

Conformance is structural, not inheritance-based.  There is no
`ModelPackageBase`: Model Runtime Contract v1 is already the runtime interface;
the standard adds ownership and boundary rules.  Conformance is asserted by
tests, not by a base class.

Bremen and Aramina both conform under the standard:

- Bremen — `bremen.model_packages.bremen_v01` (PR0154).
- Aramina — `bremen.model_packages.aramina_v0213` (PR0156).

The two packages share responsibility semantics, not internal layout or
artifact format: Bremen keeps the portable dict + sklearn-free math; Aramina
keeps the joblib/sklearn artifact and subprocess preprocessing.

Consequences

Positive:

- One ownership rule applies to both reference models and any future model.
- The MLflow/registry step is now well-defined: wrap the runtime entry point of
  a conforming package; do not teach the platform about model science.
- Aramina-specific science moves out of the platform namespace to a package
  namespace; provider becomes pure orchestration.
- Import direction and package entry points are testable and enforced, not
  aspirational.

Costs:

- Transitional compatibility shims remain until all callers are migrated.
- Test seams were retargeted from platform to package module paths (behavior
  identical).
- Two narrow platform bridges remain and are explicitly classified:
  `bremen.canonical_input` (generic cross-model vocabulary) and
  `bremen.api.decision_contract` (Bremen-specific platform vocabulary).
  Aramina additionally reaches the platform via the lazy
  `_validate_aramina_source` default and the narrow
  `bremen.model_packages_bridge.load_staged_artifact` (controlled joblib
  loading).

Alternatives considered

Inherit from a `ModelPackageBase` class.
Rejected.  Would impose artificial shared behavior and force identical internals
across models with genuinely different science and different artifact formats.

Adopt MLflow pyfunc as the package standard.
Rejected as the immediate answer.  Framework adoption does not by itself
correct ownership and would prematurely couple deployment shape to platform
invariants.  A conforming package is a strict prerequisite for a clean
framework wrap.

Leave Aramina in api modules and only rename Bremen.
Rejected.  Produces inconsistent ownership: platform would still own Aramina
science, violating the hard rule that model packages own complete inference.

Compatibility

No public HTTP surface changes.  The HTTP API surface is explicitly frozen
against this refactor and locked by a snapshot regression test
(`tests/test_bremen_api_freeze_pr0156.py`).  The `ARAMINA_*` failure taxonomy,
`target_side` semantics, symmetric-feature outputs, preprocessing contracts,
LR1/final-model behavior, thresholds and report payloads are unchanged; only
their authoritative module location moved.  Public `model_id` values are
unchanged.  Compatibility shims preserve existing import paths for external
callers and tests during the transition and are removed in a follow-up PR.

Framework position

MLflow PyFunc, BentoML, KServe or an equivalent packaging mechanism may later
wrap a conforming package.  The ownership boundary defined here is independent
of framework choice; the framework becomes an adapter over the entry point and
manifest, not a replacement of them.

Migration

- PR0154 — Bremen packaged.
- PR0155 — MLflow packaging spike; no production change; recommended pyfunc
  path over a conforming package; Model Registry deferred.
- PR0156 — Model Package Standard v1 defined and Aramina migrated to conform.
- Future PR — MLflow pyfunc wrap of a conforming package (import/distribution
  isolation, signature, safe JSON params, pinned serving dependencies, local
  save/load golden test).
