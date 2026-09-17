# Hard Refactor Execution Plan

## Operating principle

Freeze public HTTP/report behaviour, then aggressively simplify internal architecture around self-contained thick model packages.

## Before implementation

1. Commit the spike/evidence pack as documentation only.
2. Capture a fresh baseline from the real project environment:
   - route inventory;
   - full test count and `pytest --durations=100`;
   - import graph/cycles;
   - successful Bremen + Aramina report fixtures;
   - safe-failure fixtures;
   - `report.standard_result` fixtures.
3. Turn `module_inventory.csv` into a signed-off disposition matrix: KEEP / REFACTOR / MOVE / DELETE / UNKNOWN.

## Migration sequence

1. Import hygiene and shared contracts.
2. Delete Aramina service/scaffold era.
3. Extract reusable services and remove legacy HTTP server.
4. Split FastAPI into routers.
5. Split job/report/source/event responsibilities out of the god module.
6. Introduce one generic model package executor.
7. Move all scientific preprocessing/feature engineering into thick model packages.
8. Delete platform-science compatibility layers after parity evidence passes.
9. Simplify report projection around `report.standard_result`.
10. Separate training/research dependencies from production runtime.
11. Demolish historical tests and rebuild fast unit/contract suites around current behaviour.

## Review rule

Do not combine transport removal, job-service extraction and model-executor replacement in one PR. Each is a separate failure surface.

Every deletion PR must show:

- no remaining production imports/references;
- public route/report compatibility preserved;
- relevant golden fixtures unchanged unless an explicitly approved contract change exists;
- targeted tests pass;
- full suite status recorded;
- test-duration delta recorded.

## Desired end state

Adding a model should primarily mean adding/registering a model package and manifest. It should not require new platform-side workflow, preprocessing, feature or provider modules.
