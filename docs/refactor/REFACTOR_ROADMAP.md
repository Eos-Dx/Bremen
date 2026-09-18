# Bremen Hard Refactor Roadmap

This roadmap implements `ARCHITECTURE_SPIKE_PLATFORM_SIMPLIFICATION.md` as a sequence of deliberately destructive internal changes while freezing the public HTTP/report contracts.

> **Final-state note (PR0162 Cut 5):** This document is the historical
> execution roadmap. The completed tree uses FastAPI routers, platform
> jobs/sources/reports and model discovery/runtime services, one generic
> executor, neutral contracts, and thick model packages. Deleted `api/server.py`,
> `api/app.py`, provider modules, and other paths named below are retained here
> as historical checkpoints; see `module_inventory.csv` for final ownership.

## R0 — Baseline and guardrails

Purpose: make deletion measurable before moving code.

Deliverables:

- commit `docs/refactor/module_inventory.csv` generated from the supplied snapshot;
- capture route inventory (method + path + auth + status semantics);
- capture `pytest --durations=100` in the real project venv/CI;
- capture import graph and four known cycles;
- freeze one Bremen and one Aramina successful report fixture plus one safe-failure fixture each;
- freeze `report.standard_result` fixtures.

No production code change beyond import hygiene.

## R1 — Lightweight package root + clean shared contracts

- make `bremen/__init__.py` lazy; importing the package must not import MLflow, sklearn, pandas or xrd-preprocessing;
- create `bremen/contracts/` and move Model Runtime data/protocol types there;
- keep a temporary root import shim only if external Python consumers require it;
- introduce a neutral `ExecutionRequest` contract instead of the service-era `AraminaProviderRequest` scaffold.

Exit: API/auth/catalog modules import without scientific/training dependencies.

## R2 — Delete the old Aramina service/scaffold era

Delete after references/tests move:

- `api/workflow_aramina_scaffold.py`
- `api/report_aramina.py`
- `api/aramina_provider.py`
- deprecated `api/aramina_*` compatibility shims
- associated scaffold/service tests

Move any still-required request normalization into either the package manifest/runtime or the neutral execution request contract.

Exit: no `aramina_service` vocabulary or fake unavailable-provider path remains in active source.

## R3 — FastAPI-only product transport

Extract transport-independent services from `api/server.py` / `api/app.py`:

- auth config/token service;
- health/model-version service;
- source/container list/upload service.

Update FastAPI to import these services directly.

Then delete:

- legacy `http.server` routing;
- `--backend http` CLI mode;
- duplicate route tests for the old server;
- server-specific helper tests.

Exit: exactly one production HTTP stack (FastAPI/uvicorn).

## R4 — Split FastAPI into routers

Replace the 1600-line factory with router modules:

- `routers/auth.py`
- `routers/models.py`
- `routers/sources.py`
- `routers/jobs.py`
- `routers/reports.py`
- `routers/events.py`
- `routers/pages.py`

`create_fastapi_app()` should become ~100–200 lines and only compose dependencies/routers/middleware.

Exit: route modules have no model science and no process-global job state.

## R5 — Replace `job_api_handler.py` with services/repositories

Introduce explicit process state object instead of storing mutable state as attributes on the `bremen` package.

Split:

- `jobs/repository.py` — job persistence only;
- `jobs/service.py` — create/get/list/idempotency;
- `reports/service.py` — report lifecycle;
- `sources/service.py` — staged upload/source resolution;
- `events/service.py` — event retrieval/wait;
- FastAPI router code — JSON/SSE only.

Delete private-global monkeypatch tests and replace with constructor-injected repositories.

Exit: no module owns jobs + reports + HTTP + SSE simultaneously.

## R6 — Generic model package executor

Replace workflow-specific provider construction with a package factory keyed by package/artifact type.

New core shape:

```python
runtime = package_factory.create(model_descriptor)
validation = runtime.validate_model_input(model_input)
prediction = runtime.predict_model(model_input)
```

Platform source binding happens before that call and is injected, never imported back from the package.

Delete active dependency on:

- `WorkflowProvider.build_features()`;
- `WorkflowProvider.run_inference()`;
- feature-stage plugin abstractions that exist only because platform used to own science.

Exit: orchestrator contains zero Bremen/Aramina branches.

## R7 — Finish thick-package ownership

Bremen:

- raw-container path becomes the only supported scientific runtime for released packages;
- integrated-profile compatibility path is kept only in package tests if historically required.

Aramina:

- package stops requiring a platform-normalized `CanonicalXRDCase` if the artifact preprocessing can establish all required scientific input from the raw container;
- registry entry is converted by platform to a stable package descriptor before package construction;
- source/patient integrity remains platform-owned and injected as verified context.

Only after golden parity is proven, delete active platform science:

- `api/preprocessing_bridge.py`
- `api/symmetry_signals.py`
- scientific portions of `api/h5_layouts.py`
- old root inference/feature/runtime shims.

Exit: platform contains no Bremen/Aramina feature formula.

## R8 — Report simplification

Make Standard Model Result the canonical model-independent projection.

- model packages return model-native result + normalized metadata;
- one platform mapper produces `report.standard_result`;
- workflow-specific report modules contain only compatibility projections needed by existing clients;
- remove unused/unavailable report scaffolds;
- legacy `/external`/`/internal` handlers are removed only after consumer audit.

Exit: adding a model does not add a report mapper module unless it has genuine `specific_output` semantics.

## R9 — Training/runtime package separation

Move training/research code out of the production import surface.

At minimum:

- `bremen` runtime dependencies no longer include MLflow/pyarrow/training pipeline dependencies unless the deployed runtime actually imports them;
- training becomes an optional extra or separate distribution;
- root `bremen` imports remain lightweight.

Exit: API container boots without the training toolchain.

## R10 — Test demolition and rebuild

Delete historical implementation tests together with deleted code.

Collapse PR/phase tests into current contract suites.

Examples:

- old FastAPI phase1/2/3/4 files -> one route-contract suite + focused router unit tests;
- legacy server tests -> delete after R3;
- Aramina provider scaffold tests -> delete after R2;
- runtime plugin/showcase tests -> delete after R6;
- platform scientific tests -> move to `tests/packages/` or delete when superseded by package golden tests;
- large UI assertion grids -> use smaller component/snapshot contract tests.

Markers:

- `unit`
- `contract`
- `integration`
- `model_evidence`
- `e2e`

Default PR excludes `model_evidence`/external evidence and runs them in a separate CI job.

## Suggested PR sequence

1. `0162-refactor-baseline-and-import-hygiene`
2. `0163-delete-aramina-service-scaffolds`
3. `0164-fastapi-only-runtime`
4. `0165-split-fastapi-routers`
5. `0166-split-job-services`
6. `0167-generic-model-package-executor`
7. `0168-aramina-raw-package-boundary`
8. `0169-delete-platform-science-legacy`
9. `0170-report-service-simplification`
10. `0171-training-runtime-separation`
11. `0172-test-suite-rebaseline`

Do not combine R3, R5 and R6 in one PR. They are each large enough to review independently and each changes a different failure surface.
