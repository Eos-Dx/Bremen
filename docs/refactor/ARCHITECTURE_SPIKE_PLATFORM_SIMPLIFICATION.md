# Architecture Spike — Bremen Platform Hard Refactor for Thick Model Packages

Status: proposed execution plan
Date: 2026-09-17
Scope: repository-wide platform/runtime simplification; no scientific formula change in this spike

> **Final-state note (PR0162 Cut 5):** This spike records the pre-refactor
> architecture and measured baseline. The active implementation now follows
> FastAPI routers -> platform services -> generic executor -> `ModelRuntime` ->
> model package -> result/event projection. Historical module names and
> measurements below are intentionally preserved.

## Executive decision

Bremen Platform should stop being a partial model-serving implementation and become a thin product platform around **inference-complete model packages**.

The platform owns HTTP/auth, source registration and integrity, job lifecycle, events, model selection, package execution, persistence, safe error translation and report envelopes.

A model package owns all scientific behaviour from its declared model input to model-native output: preprocessing, measurement selection/aggregation, feature engineering, estimator invocation, threshold/postprocessing, model-owned metadata extraction and golden parity tests.

The repository already moved materially in this direction in ADR-0016/0017 and PR0154–0160. The remaining problem is structural debt: old service-era, platform-science and migration layers remain in the active package and tests.

## Measured repository shape

Static inventory of the supplied `Bremen-main_0160.zip`:

- 111 Python source modules under `src/bremen`
- 37,647 source Python LOC
- 123 `test_*.py` files
- 57,833 test Python LOC
- 4,023 explicit `test_*` functions (the PR0160 report records 4,360 passed + 13 skipped after parametrization)
- 4 internal import cycles
- several deprecated compatibility shims and pre-Model-Package scaffolds remain in the runtime distribution

Largest source modules:

| Module | LOC | Problem |
|---|---:|---|
| `api/server.py` | 1955 | legacy `http.server` transport, yet FastAPI still imports business helpers from it |
| `api/job_api_handler.py` | 1683 | state, upload/source resolution, job service, reporting, HTTP handlers and SSE mixed together |
| `api/fastapi_app.py` | 1603 | one application factory owns almost every route and imports legacy server/app code |
| `report_ui.py` | 1541 | UI rendering monolith |
| `api/h5_layouts.py` | 1428 | old platform normalization/layout ownership |
| `workspace_ui.py` | 1334 | UI rendering monolith |
| `modeling.py` | 1325 | training/research code shipped in runtime package |
| `control_room_ui.py` | 1281 | UI rendering monolith |
| `api/s3_model_discovery.py` | 1165 | discovery, validation, staging and compatibility concerns combined |
| `api/preprocessing_bridge.py` | 944 | legacy platform-owned scientific preprocessing path |

Largest tests are also monolithic: `test_bremen_control_room.py` has 558 test functions / 4477 LOC; `test_aramina_workflow_runtime.py` has 151 tests / 2635 LOC; `test_s3_model_discovery.py` has 110 tests / 2273 LOC.

## Confirmed structural problems

### 1. Root package import is heavy and couples unrelated domains

`bremen/__init__.py` eagerly imports MLflow helpers, training/modeling helpers and preprocessing pipelines. Consequently `import bremen` can require scientific/training dependencies even when a caller only needs auth, API contracts or model registry state. This is an avoidable import-time dependency fan-out and makes isolated testing harder.

### 2. FastAPI is not actually independent of the legacy server

`api/fastapi_app.py` imports `api.server` for:

- auth configuration singleton;
- container listing;
- H5 upload validation/storage;
- auth response shapes / token support.

It also imports `api.app` for health/model-version handlers. Therefore the nominally obsolete `http.server` stack cannot be removed without first extracting reusable application services.

### 3. `job_api_handler.py` is a god module

It combines at least six responsibilities:

1. process-local state/singletons/locks;
2. staged uploads and source resolution;
3. job create/get/list service logic;
4. report provider registration/generation/deletion;
5. HTTP transport adapters;
6. SSE formatting/streaming.

This makes tests patch private globals directly and prevents clean unit boundaries.

### 4. Workflow abstractions still describe the old architecture

`WorkflowProvider` still requires `build_features()` and `run_inference()`, even though ADR-0016 says model packages own feature engineering and inference. Bremen and Aramina now expose `ModelRuntime`, but the workflow provider interface still encodes the platform-science era.

`workflow_orchestrator.py` also contains workflow-specific branches (`if workflow_id == "aramina"`) and constructs concrete Bremen/Aramina providers itself. A new model therefore still risks requiring platform code changes.

### 5. Model packages are thick, but the boundary is not fully clean

Bremen v0.1 can own raw-container preprocessing for relevant artifacts. Aramina owns its preprocessing/scoring/symmetry code, but still receives a platform canonical case and a registry-entry-shaped object. This is a residual coupling: a truly inference-complete package should receive a stable package context + raw input handle, not a platform registry implementation object.

### 6. Obsolete migration/scaffold modules remain

Strong deletion candidates after references are migrated:

- `api/workflow_aramina_scaffold.py`
- `api/report_aramina.py`
- `api/aramina_provider.py` service-era scaffold (retain only the request fields in a neutral execution-request contract)
- `api/aramina_artifact_compat.py` compatibility shim
- `api/aramina_preprocessing.py` compatibility shim
- `api/aramina_symmetry.py` compatibility shim
- `bremen_features.py` compatibility shim
- `bremen_runtime.py` compatibility shim
- `inference.py` compatibility shim
- `api/inference_handler.py` old preflight/bridge/inference wrapper
- `api/feature_artifact_prediction.py` old feature-artifact path

Later deletion candidates once FastAPI and thick-package migration are complete:

- `api/server.py`
- `api/app.py`
- `api/preprocessing_bridge.py`
- `api/symmetry_signals.py`
- significant portions of `api/h5_layouts.py`
- old runtime-plugin/lifecycle feature-stage abstractions

### 7. Training and runtime are physically mixed

`modeling.py`, `pipelines.py`, `mlflow_tracking.py`, `training/` and their heavy dependencies ship in the same package namespace as the production platform. This inflates dependency surface and makes `bremen` mean both product runtime and model-development toolkit.

The long-term target should make training an optional package/extra or separate distribution.

### 8. Test architecture is preserving migrations instead of current behaviour

The suite contains many PR-specific, phase-specific and legacy-path tests. Tests still lock in old scaffolds and compatibility shims. This increases runtime and actively makes deletion difficult.

Tests should be reorganized around current contracts, not historical implementation phases.

## Import cycles to remove

The supplied snapshot has four source-level cycles:

1. `model_packages.aramina_v0213` ↔ `errors` ↔ `runtime`
2. `model_packages.bremen_v01` ↔ `runtime`
3. `api.h5_layouts` ↔ `api.preflight`
4. `api.workflow_aramina` ↔ `api.workflow_orchestrator`

The fourth is especially important: Aramina provider imports `_validate_aramina_source` from the orchestrator, while the orchestrator imports/constructs the Aramina provider. Source validation must become a platform service injected before runtime execution.

## Target architecture

```text
src/bremen/
  contracts/
    model_runtime.py
    execution.py
    errors.py

  platform/
    api/
      app.py
      dependencies.py
      routers/
        auth.py
        models.py
        sources.py
        jobs.py
        reports.py
        events.py
        pages.py

    auth/
      service.py

    jobs/
      models.py
      repository.py
      service.py

    events/
      models.py
      store.py
      service.py

    models/
      catalog.py
      registry.py
      requirements.py
      discovery.py
      staging.py
      loader.py

    sources/
      registry.py
      service.py
      integrity.py

    runtime/
      executor.py
      package_factory.py
      result_projection.py
      tracing.py

    reports/
      models.py
      service.py
      standard_result.py
      mapper.py

  model_packages/
    bremen_v01/
      ... complete model-owned science ...
    aramina_v0213/
      ... complete model-owned science ...

  ui/
    pages/
    components/

  training/
    ... optional / separate distribution target ...

  compat/              # temporary only; empty at end of migration
```

The important boundary is not the exact directory names. The important rule is dependency direction:

```text
platform ---> contracts <--- model_packages

platform ---> model_packages (only via package factory/runtime contract)
model_packages -X-> platform
training -X-> platform runtime internals
```

## New execution model

The active path should become:

```text
HTTP request
  -> JobService
  -> SourceService (resolve + integrity + identity binding)
  -> ModelRegistry (select package descriptor)
  -> ModelPackageFactory
  -> ModelRuntime.predict_model(ModelInput)
  -> generic RuntimePrediction
  -> Standard Result mapper
  -> Job/report persistence
```

There should be no platform call sequence named `build_features -> run_inference` for model-owned science.

Adding a new model should normally require:

1. adding a model package/runtime;
2. registering its package type/factory;
3. publishing its manifest/artifact;
4. adding package contract tests.

It should **not** require a new `workflow_xyz.py`, `xyz_provider.py`, `xyz_preprocessing.py`, or platform feature calculator.

## Public compatibility rule

The refactor may be aggressive internally but must keep the external integration surface stable until an explicit API-version migration says otherwise:

- auth routes;
- model catalog / requirements;
- source/container routes;
- jobs/events;
- `GET /api/jobs/{job_id}/reports/{workflow_id}`;
- `report.standard_result`;
- existing legacy payload fields still consumed by clients.

Internal Python import compatibility is not a reason to retain dead architecture forever. Compatibility shims should have a removal milestone and tests should migrate to canonical imports.

## Test target

Current tests are larger than source code. The target is contract-oriented layering:

```text
tests/unit/          pure platform units; no H5/S3/subprocess/model artifact
tests/contracts/     public API and Model Runtime contract
tests/packages/      package-owned scientific/golden tests
tests/integration/   source + job + package integration
tests/e2e/           minimal deployed surface
```

Target local/PR runtime:

- unit: <= 10 s
- unit + contracts: <= 30 s
- normal PR suite: <= 60 s
- real artifact / subprocess / evidence tests: separate marked stage

Do not solve the problem first with `pytest-xdist`. Reduce duplicate architecture and move scientific regression tests to package scope first.

## Acceptance criteria for the refactor epic

The epic is complete when:

- FastAPI has zero imports from legacy `api.server` / `api.app`;
- production CLI has one server path;
- `job_api_handler.py` no longer exists as a god module;
- `WorkflowProvider.build_features/run_inference` is gone from the active contract;
- the orchestrator has no `if workflow_id == ...` model-specific branches;
- model packages do not import `bremen.platform` or `bremen.api`;
- obsolete Aramina service/scaffold modules are deleted;
- platform preprocessing/feature code is deleted from active runtime paths;
- root `import bremen` is lightweight;
- training dependencies are not required to boot the API;
- public route/JSON compatibility tests pass;
- package parity/golden tests remain model-owned;
- default PR test runtime is below 60 seconds in CI.
