# PR0155 Research Spike — MLflow Packaging for Bremen v0.1

Status: research result; no production change

> PR0156 update: MLflow packaging, if adopted, applies to **any** package
> conforming to Model Package Standard v1 (see
> `docs/model_package_standard_v1.md` / ADR-0017), not only Bremen. Both Bremen
> (`bremen.model_packages.bremen_v01`) and Aramina
> (`bremen.model_packages.aramina_v0213`) now sit behind that standard, so a
> framework wrapper targets each package's ModelRuntime entry point without
> moving scientific logic. This document remains a non-binding spike; no MLflow
> production integration was implemented in PR0156.

## Verdict

RECOMMEND MLflow PyFunc-compatible packaging for Bremen v0.1, but defer MLflow Model Registry adoption.

Before the first production MLflow model release, close one packaging-isolation gap: the Bremen inference package is scientifically self-contained, but its Python import path still sits inside the platform distribution and importing `bremen.*` executes the eager top-level `bremen/__init__.py`. A release should not require research/training-only imports merely to load the inference package.

The recommended sequence is:

1. Isolate the Bremen v0.1 inference distribution/release boundary.
2. Package the existing runtime through MLflow pyfunc without changing science.
3. Use a nested structured model signature representing the real six-measurement input.
4. Package portable model parameters as safe structured data (prefer JSON) rather than making joblib the serving contract.
5. Pin the tested serving dependencies explicitly.
6. Keep the existing Bremen catalog/registry initially.
7. Re-evaluate MLflow Model Registry separately after local/S3 pyfunc packaging is proven in production.

## Snapshot reviewed

Fresh Bremen snapshot supplied after PR0154.

Relevant implemented boundaries:

- `src/bremen/model_runtime.py` — Model Runtime Contract v1.
- `src/bremen/model_packages/bremen_v01/` — inference-complete Bremen v0.1 package.
- `src/bremen/model_packages/bremen_v01/runtime.py` — runtime entry point.
- `src/bremen/model_packages/bremen_v01/features.py` — frozen 15-feature science.
- `src/bremen/model_packages/bremen_v01/predictor.py` — portable logistic-regression inference.
- `src/bremen/model_packages/bremen_v01/manifest.py` — release identity/input contract.
- `src/bremen/api/s3_model_discovery.py` — current custom S3 catalog/model discovery and staging.
- `src/bremen/api/model_registry.py` — current process-local registry.
- `src/bremen/model_package.py` — current manifest/checksum package validation.

## What MLflow would solve well

MLflow pyfunc is a good fit for the boundary already established by PR0153/PR0154. It can wrap the model-owned runtime instead of moving scientific logic back into the platform.

Useful capabilities for Bremen:

- standard model directory format;
- one generic `predict` interface;
- model signature / input example;
- code and artifact packaging;
- dependency/environment metadata;
- load/save semantics independent of Bremen job orchestration;
- optional later registration/versioning/aliases through Model Registry.

MLflow must not replace:

- Bremen authentication;
- source/container registry;
- job lifecycle;
- report generation;
- public API;
- audit/event logic;
- model-specific scientific code.

## Structured input PoC

A framework-neutral adapter was executed against the actual PR0154 BremenRuntime using a nested Pydantic-compatible input shape.

Conceptual batch input:

    list[BremenCaseInput]

Each case contains:

    measurements: exactly six objects

Each measurement contains:

    side: LEFT | RIGHT
    position: string
    q: list[float]
    intensity: list[float]

The adapter reconstructed canonical measurement objects and called the package runtime through Model Runtime Contract semantics.

Observed result against PR0151 golden fixture:

- batch size tested: 2 cases;
- expected probability: 0.7388733541967353;
- adapter probability: 0.7388733541967349;
- probability absolute difference: 3.33e-16;
- max 15-feature absolute difference: 7.11e-15;
- serialized one-case input size: approximately 60.7 KB JSON;
- serialized selected output size: approximately 0.8 KB JSON.

Conclusion: MLflow does not require Bremen Platform to prepare the 15 features. The pyfunc boundary can accept the real six-measurement scientific input.

A nested Pydantic input model is the preferred signature shape because recent MLflow releases support nested Pydantic model type hints, arrays and object schemas.

## Proposed pyfunc boundary

The MLflow-facing adapter should be deliberately thin.

Conceptually:

    MLflow adapter
      deserialize validated structured input
      -> package-local measurement objects
      -> Bremen model runtime
      -> structured prediction output

The adapter must not contain smoothing, normalization, feature formulas, scaler arithmetic or threshold logic.

Recommended external model input is integrated canonical measurement profiles, not H5/S3 paths. Storage and H5 layout normalization remain platform concerns; the model release begins at the validated six-profile scientific boundary established by PR0152/PR0154.

## Model parameter artifact

The current Bremen predictor does not need sklearn at serving time. It consumes a plain dictionary containing:

- imputer statistics;
- scaler mean/scale;
- coefficients;
- intercept;
- classes;
- exact feature columns;
- threshold.

The frozen PR0151 fixture already represents this as a small JSON document.

Recommendation: the MLflow release should prefer a safe structured `model.json` (plus release metadata) generated from the trusted, checksum-verified source artifact during release build. The resulting model must be golden-parity checked against the original authoritative artifact before publication.

This avoids making joblib deserialization the long-term MLflow serving contract. Retain the original artifact checksum as provenance.

## Packaging blocker found

The scientific package is inference-complete, but the Python distribution boundary is not fully isolated yet.

Normal Python import of:

    bremen.model_packages.bremen_v01

first executes:

    bremen/__init__.py

The top-level package eagerly imports research/training modules, including `bremen.pipelines`, which imports the external `xrd_preprocessing` package.

In an environment containing numpy/pandas/scipy but not `xrd_preprocessing`, direct package import therefore fails before the model package entry point is reached.

This is undesirable for an independently loadable MLflow model release.

PR0154 also intentionally retains two runtime bridges:

- `bremen.api.decision_contract`;
- `bremen.api.xrd_normalization.validate_canonical_measurement`.

They are small and deterministic, but they show that the release is still physically nested inside the platform distribution.

Recommended fix before or as part of the MLflow implementation PR:

- create a genuinely isolated model distribution/release bundle, OR
- make the root Bremen package lazy/minimal and explicitly package only the inference code and narrow shared contract modules.

Long-term preference: a model-release distribution that can be installed/loaded without importing Bremen training/research/platform modules.

## MLflow serialization strategy

Do not choose a serialization path merely because it is the shortest.

Current MLflow documentation recommends Models From Code for custom Python models and highlights its pickle-free benefits, but the feature remains marked experimental.

For the first Bremen production package, a conservative option is the established pyfunc loader-module/data-path workflow:

- stable pyfunc model format;
- a small loader module;
- release data directory containing safe model parameter JSON and release metadata;
- isolated installable inference package or explicitly packaged code dependency;
- explicit input signature and input example;
- explicit pinned serving dependencies.

This avoids cloudpickle of a live PythonModel object and avoids making an experimental feature mandatory for the first production migration.

Models From Code can be re-evaluated after the basic release path is stable.

## Dependency capture

The repository currently declares broad ranges such as:

    mlflow>=2.20
    numpy>=1.26,<3
    pandas>=2.2
    scipy>=1.13

That is acceptable for development but insufficient as release-level inference reproducibility.

The model release should record exact tested versions or a lock produced by the release build.

MLflow now has uv lockfile support, but current MLflow documentation marks uv-specific model dependency parameters as experimental and this repository has no `uv.lock`.

Initial recommendation:

- pass explicit pinned `pip_requirements` for the release;
- record Python version;
- record original model checksum;
- record Bremen model package version/commit;
- run a fresh-environment load/predict golden smoke test.

A later dependency-lock PR may adopt uv once the team chooses it project-wide.

## MLflow version

As of the research date, MLflow 3.16.0 is the current release line. The project only specifies `mlflow>=2.20`, which permits uncontrolled major/minor drift.

Do not publish a production model against an open-ended MLflow range.

Select one MLflow version in CI, test the model save/load path, and pin that tested version in the model release environment. The spike does not select an exact production pin because MLflow could not be installed in the isolated research container for execution testing.

## Model Registry assessment

Recommendation: DEFER REGISTRY.

Registry functionality is attractive:

- centralized model versions;
- tags;
- lineage;
- model aliases such as candidate/champion;
- standard model URIs;
- UI/API model lifecycle management.

However, using a self-hosted MLflow Model Registry adds an operational service and database-backed backend store. Bremen already has a working model catalog/registry and S3 artifact flow.

The current custom code is substantial (`s3_model_discovery.py` ~1169 lines, `model_registry.py` ~304 lines, `model_package.py` ~397 lines), so Registry may eventually remove meaningful custom infrastructure. But it will not replace container requirements, source registry, job routing, reports or model-specific runtime requirements without adapters/tags.

Adopt packaging first. Measure real benefits and deployment behavior. Then decide whether replacing the catalog with MLflow Registry justifies the additional service and migration risk.

If Registry is later adopted, preserve the existing public `model_id` as model metadata/API identity. Do not blindly expose MLflow's integer model-version IDs as Bremen model versions. Use aliases/tags for deployment state rather than deprecated stage-style workflows.

## Current custom S3/catalog code versus MLflow

Likely replaceable later:

- manual model version/catalog discovery;
- model artifact version organization;
- some manifest metadata;
- model lifecycle aliasing;
- model URI resolution;
- some dependency/signature metadata.

Still Bremen-owned:

- workflow identity;
- model-specific requirements projection;
- source/container compatibility;
- public catalog response contract;
- auth/access policy integration;
- job orchestration;
- report contracts;
- platform safety metadata.

## Aramina implications

Do not use Bremen's successful pyfunc packaging as proof that Aramina can be migrated identically.

Aramina currently has a materially different execution contract, including artifact-owned raw-H5 preprocessing and isolated preprocessing Python environments/releases. Model Runtime Contract v1 provides the common semantic boundary, but Aramina packaging needs its own spike after Bremen.

MLflow Registry could store Aramina release metadata even before its runtime becomes a direct pyfunc, but that is not a reason to migrate the shared registry immediately.

## Spike environment limitation

A real `mlflow.pyfunc.save_model()` / `load_model()` execution could not be performed in this research container because MLflow was not preinstalled and outbound package installation was unavailable.

This limitation does not affect the repository analysis or structured input/runtime parity PoC, but it means the first implementation PR must include the real MLflow local save/load golden test before any production decision.

## Recommended decision

RECOMMEND MLflow PyFunc-compatible Bremen packaging.

DEFER Model Registry.

Do not start by replacing the Bremen platform catalog.

The next implementation should prove one narrow path:

    frozen six-measurement input
    -> saved MLflow model directory
    -> fresh load
    -> exact 15 features
    -> exact probability
    -> exact decision

with no workflow provider and no platform scientific code.

## Proposed next PR

Suggested name:

    0156-bremen-mlflow-pyfunc-package

Scope:

- close import/distribution isolation required for standalone loading;
- introduce MLflow-facing structured input/output types;
- create thin pyfunc/loader adapter;
- package safe model parameters + release metadata;
- explicit model signature and input example;
- explicit pinned serving requirements;
- local save/load golden parity test;
- subprocess/fresh-environment smoke test;
- no Model Registry server;
- no public API changes;
- no scientific changes;
- no Aramina migration.

Only after this passes should a separate Registry PR be considered.
