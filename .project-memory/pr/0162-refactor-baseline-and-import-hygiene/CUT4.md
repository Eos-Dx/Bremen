# PR0162 Cut 4

## Before

The bounded caller inventory was captured with the required search. Production
matches were limited to these direct dependencies:

- `src/bremen/api/http/routers/system.py` imported `handle_health` and
  `handle_model_version` from `bremen.api.app`.
- `src/bremen/api/http/routers/jobs.py`, `reports.py`, `events.py` and
  `legacy_jobs.py` contained the old job/report adapter references and
  compatibility comments.
- `src/bremen/api/http/app.py` used one deprecated `@app.on_event("startup")`
  hook for model registry initialization.
- `src/bremen/api/app.py` contained health, model-version, prediction submit and
  prediction status facades. No production module other than the system router
  imported it after the route migration.

The remaining `legacy_jobs` and `api.app` imports in tests were test callers of
internal facades. Script matches were startup/readiness wording and the local
FastAPI smoke process. Scientific/model package matches were unrelated startup
state or test setup. No production shutdown hook existed.

## legacy_jobs disposition

`src/bremen/api/http/legacy_jobs.py` was deleted. Its functions were classified
as follows:

- job creation/list/detail and duplicate/replay handling: existing
  `platform/jobs/service.py` and direct FastAPI job routes;
- reports and report deletion: existing `platform/reports/service.py` and direct
  FastAPI report routes;
- event/SSE serialization: existing platform event services and direct event
  routes;
- `_send_json`, `_read_json_body`, and handler-specific response writing: HTTP
  translation only, deleted with the obsolete handler adapter;
- no unique production use case remained.

No `legacy_jobs_v2`, facade, manager, or replacement application adapter was
created. Tests that still exercise the former handler shape use a test-only
support module, outside `src/bremen`, and production source has zero imports of
the deleted module.

## api.app disposition

`src/bremen/api/app.py` was deleted. Its production callables were either
already represented by FastAPI routes/platform services or were test-only
facades. The two read-only system queries were moved to the small HTTP boundary
module `api/http/system_support.py`, which is called directly by the system
router; prediction/job behavior remains in the existing platform job/runtime
services and FastAPI routes.

Tests that directly exercised the old pure handler facade were retargeted to a
test-only support copy or to the existing public FastAPI characterization
tests. No production re-export shim exists.

## FastAPI lifecycle

Before, `api/http/app.py` registered `@app.on_event("startup")` and embedded
catalog discovery/model-state initialization in that callback. After, the same
startup responsibilities are owned by one `@asynccontextmanager` `lifespan`
function passed to the single `FastAPI` constructor. It calls the existing
platform registry/discovery/state owners, yields once, and adds no shutdown
behavior. There are no `on_event` or `add_event_handler` registrations in
production FastAPI code.

## Application path after

For a job request the concrete path is:

```text
FastAPI /demo/api/jobs
  -> routers/jobs.py request parsing/auth/status mapping
  -> platform/jobs/service.create_analysis_job
  -> platform/sources service + platform model/runtime registry
  -> platform/runtime/executor
  -> model package
  -> platform report/event services
```

Routers retain HTTP parsing, compatibility defaults and serialization only.
Persistence, source resolution, model selection, execution, events and reports
remain in their existing platform owners.

## Files deleted

- `src/bremen/api/http/legacy_jobs.py`
- `src/bremen/api/app.py`

No scientific, model-package, preprocessing, H5-layout, report-semantic or
deployment files were deleted.

## Tests retired or retargeted

- Direct legacy transport/application-adapter tests were retargeted to
  `tests/_legacy_jobs_support.py` or `tests/_api_app_support.py` only where
  assertions were internal implementation behavior.
- Public HTTP assertions remain in FastAPI route, auth, jobs, reports, events,
  source, UI and snapshot suites.
- No scientific parity tests were removed.
- No test file was removed in Cut 4; the full suite remains above four thousand
  tests. Test-only support is outside production ownership and is not imported
  by `src/bremen`.

## Public contract verification

- `29` method/path pairs and `27` unique paths remain equal to the established
  route baseline.
- `public_results.json` and report projections remain exact, including
  `risk_score`, `technical_demo_only`, and additive `standard_result`.
- Auth token/refresh, protected-route 401 behavior, source listing/upload,
  model catalog/requirements, jobs, duplicate/replay, reports, legacy report
  shapes, events/SSE, tickets and public UI suites pass.
- No `/reports/{workflow_id}/standard-result` endpoint was introduced.

## Validation

```text
./venv/bin/python -m compileall -q src tests
PASS

./venv/bin/python -m pytest -q \
  tests/test_platform_architecture_pr0162.py \
  tests/test_bremen_api_skeleton.py \
  tests/test_bremen_fastapi_jobs_report_parity.py \
  tests/test_bremen_fastapi_auth_enforcement.py \
  tests/test_bremen_inference_integration.py \
  tests/test_aramina_workflow_runtime.py \
  tests/test_bremen_control_room.py \
  tests/test_bremen_model_catalog.py \
  tests/test_s3_model_discovery.py
1074 passed, 1 skipped, 574 warnings in 4.65s

./venv/bin/python -m pytest --collect-only -q
4088 tests collected in 1.83s

./venv/bin/python -m pytest -q --durations=100
4077 passed, 11 skipped, 680 warnings in 34.59s

./venv/bin/ruff check . --output-format=json
162 findings; same inherited count as Cut 3 after normalizing the test-only
support files. No new Ruff regression.

git diff --check
PASS
```

Static checks return zero production matches for
`bremen.api.http.legacy_jobs`, `bremen.api.app`, `on_event(` and
`add_event_handler(`. There is exactly one production `create_app` definition,
in `api/http/app.py`, and exactly one production lifespan owner.

## LOC delta

| File/area | Before | After |
| --- | ---: | ---: |
| `api/http/legacy_jobs.py` | 589 | 0 |
| `api/app.py` | 428 | 0 |
| `api/http/app.py` | 109 | 99 |
| `api/http/routers/jobs.py` | 396 | 396 |
| `api/http/routers/reports.py` | 166 | 166 |
| `api/http/routers/sources.py` | 55 | 55 |
| `api/http/routers/system.py` | 49 | 49 |
| `platform/jobs/service.py` | 479 | 479 |
| `platform/reports/service.py` | 420 | 420 |

Production code decreased by deleting both facades; no equivalent production
facade was introduced. The only copied compatibility logic is test-only support
for internal tests and is outside the shipped package.

## Remaining debt for Cut 5

- Test-only compatibility support still contains historical handler assertions;
  it can be removed after the final test inventory proves no value remains.
- `api/http/system_support.py` is a small HTTP-boundary metadata helper that can
  be folded into the final system-route cleanup if desired.
- Legacy H5 layout compatibility remains under `platform/sources`.
- FastAPI/uvicorn dependency deprecation warnings remain external dependency
  noise.
- Inherited repository Ruff debt remains unchanged.

READY FOR 0162 CUT 5
