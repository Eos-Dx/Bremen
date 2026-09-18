# PR0162 Cut 5

## Before

Test-support and stale-reference inventory.

The two test-only compatibility copies of the deleted application facades were
already absent from the working tree and enforced absent by the architecture
suite:

- `tests/_legacy_jobs_support.py` — absent.
- `tests/_api_app_support.py` — absent.

`rg -n '_legacy_jobs_support|_api_app_support' tests src scripts` finds only
the architecture-suite assertions that the files do not exist. No production or
test file imports either module.

Stale-reference scan over current production source for
`legacy_jobs`, `bremen.api.app`, `handle_submit_prediction`,
`handle_get_prediction`, `WorkflowProvider`, `WorkflowRuntimePlugin`,
`run_server`, `bremen.api.server`, `s3_model_discovery`,
`inference_handler`, `on_event(`, `add_event_handler(`:
zero production matches. Exactly one `create_app` definition exists
(`src/bremen/api/http/app.py:42`), and exactly one lifespan owner.

## Test compatibility demolition

The two test-only compatibility copies were deleted; no replacement helper
exists under any filename. Affected assertions were classified and handled:

- PUBLIC_HTTP_CONTRACT — retained in the existing FastAPI public-route
  characterization suites (auth, jobs, reports, events/SSE, source, UI,
  model catalog, result parity).
- APPLICATION_SERVICE_CONTRACT — retargeted to the authoritative platform
  services (`platform/jobs/service.py`, `platform/reports/service.py`,
  `platform/runtime/*`).
- SCIENTIFIC_PARITY — unchanged; the frozen PR0151/0152/0160 golden
  evidence (3x3 fixtures, Nova_378 mean-peak, paper-reference parity) remains
  intact and passing.
- DELETED_INTERNAL_BEHAVIOR — assertions whose sole subject was the deleted
  legacy handler/facade implementation were deleted with their subjects.

The architecture suite now proves absence:

```python
assert not (tests_root / "_legacy_jobs_support.py").exists()
assert not (tests_root / "_api_app_support.py").exists()
```

## system_support disposition

**KEEP** — `src/bremen/api/http/system_support.py` (189 LOC).

`handle_model_version` is not trivial transport formatting: it performs
substantive model-metadata resolution across catalog mode (zero/one/many),
explicit local package path, loaded `ModelState`, failed-load error metadata,
and cloud-derived fallback. Part 5's rule explicitly forbids moving substantive
model/version lookup logic into a router ("Do NOT move substantive model/version
lookup logic into a router"). The module is transport-adjacent (read-only
model-metadata query used only by the system router), has no reusable
application responsibility beyond the HTTP boundary, and no other production
caller. Inlining would push ~150 lines of model-resolution logic into
`routers/system.py`, which Part 5 prohibits. The two router functions
(`/health`, `/model/version`) remain thin (read response fields, serialize).

`src/bremen/api/http/system_support.py` is the single surviving HTTP-boundary
metadata helper introduced in Cut 4 and is retained unchanged in Cut 5.

## Stale reference cleanup

Current-runtime references removed earlier and verified absent now:

- `api/app.py` deleted; `bremen.api.app` has zero production imports.
- `api/http/legacy_jobs.py` deleted; `bremen.api.http.legacy_jobs` has zero
  production imports.
- `api/server.py` deleted; no `from http.server` / `BaseHTTPRequestHandler`.
- `api/s3_model_discovery.py` deleted; model discovery owned by
  `platform/models/discovery.py`.
- No deprecated FastAPI `on_event` / `add_event_handler` registration remains;
  the single lifespan owner is `api/http/app.py:lifespan`.
- No `WorkflowProvider` / `WorkflowRuntimePlugin` / provider-registry /
  orchestrator / scaffold / bridge / API scientific re-export modules remain in
  production source.
- `docs/refactor/module_inventory.csv` reflects the final tree (deleted entries
  marked DELETE with final owner; platform tree marked ADDED PR0162;
  `api.http.system_support` listed ADDED PR0162 with its role).

## Final architecture

```text
bremen serve
  -> api.fastapi_server (uvicorn launcher)
  -> api/http/app.py create_app + lifespan
  -> api/http/routers/* (HTTP parsing, auth gate, status mapping, serialization)
  -> platform/{jobs,sources,reports} services
  -> platform/runtime/executor + registry
  -> ModelRuntime contract (contracts/model_runtime)
  -> model package (bremen_v01 / aramina_v0213)
  -> RuntimePrediction
  -> platform/reports/mapper -> public report/standard_result
```

One `create_app` owner (`api/http/app.py`). One lifespan owner. One serving
path. No legacy application facade. Platform/contracts/model-packages never
import `bremen.api`; model packages never import platform or API. Generic
executor is model-agnostic.

## Public contract verification

- Routes: **29 method/path pairs, 27 unique paths** — matches
  `public_routes.json` (verified live against `create_app()`).
- Result projection: exact equality against `public_results.json` for Bremen
  and Aramina standard results.
- Preserved: `report.payload.risk_score`, `report.payload.technical_demo_only`,
  `report.standard_result`; auth token/refresh, model catalog, requirements,
  source listing/upload, job submit/list/detail, duplicate/replay, reports,
  legacy external/internal reports, events, auth ticket, SSE authorization,
  public UI routes.
- No `/reports/{workflow_id}/standard-result` endpoint added.

## Scientific parity

Cut 5 made no scientific implementation changes. Package-owned preprocessing,
Bremen/Aramina features, symmetry, H5 scientific interpretation,
`platform/sources/legacy_layouts.py`, canonical QC, estimators, thresholds,
artifact formats and result mapping are unchanged by Cut 5. Parity evidence
retained and green: frozen 3x3 golden (`0.7388733541967353`), Nova_378
authoritative `mean_peak_value_raw ≈ 0.46283992131551105` and unchanged 0.6
gate, Nova_227 paper-reference probability `≈ 0.772694032994381` (abs 1e-10).

## Final validation

```text
./venv/bin/python -m compileall -q src tests
PASS

./venv/bin/python -m pytest tests/test_platform_architecture_pr0162.py -q
13 passed

./venv/bin/python -m pytest \
  tests/test_platform_architecture_pr0162.py \
  tests/test_bremen_fastapi_jobs_report_parity.py \
  tests/test_bremen_fastapi_auth_enforcement.py \
  tests/test_bremen_standard_model_result_v1.py \
  tests/test_bremen_standard_result_hardening_pr0158a.py \
  tests/test_bremen_3x3_runtime_parity.py \
  tests/test_bremen_v01_package.py \
  tests/test_aramina_v0213_package.py
268 passed

./venv/bin/python -m pytest --collect-only -q
3964 tests collected

./venv/bin/python -m pytest -q --durations=100
3956 passed, 8 skipped, 653 warnings in ~21-31s (observed 21.08s / 21.66s /
22.81s / 30.31s across runs; timing varies, non-blocking)

git diff --check
PASS

Ruff: same inherited-findings methodology as Cuts 2-4; Cut 5 introduced no
new findings (documented in FINAL_METRICS.md line 91).
```

## Final metrics

Baseline (pre-Cut 1) vs final (post-Cut 5):

| Measure | Baseline | Final | Absolute | Percent |
|---|---:|---:|---:|---:|
| Source LOC | 37,647 | 32,861 | -4,786 | -12.71% |
| Test LOC | 58,729 | 51,691 | -7,038 | -11.98% |
| Source files | — | 128 | — | — |
| Test files | 123 | 118 | -5 | -4.07% |
| Collected tests | 4,411 | 3,964 | -447 | -10.13% |
| Full pytest seconds | — | 21-31 | — | — |

Cut 4 reference: 4,088 collected / 4,077 passed / 11 skipped / 680 warnings /
34.59 s. Cut 5 removed 124 collected tests (deleted internal-architecture test
subjects), reduced skipped by 3, and reduced observed runtime by ~4-13 s.
Every reduction is attributable to deleted internal-architecture test subjects;
no meaningful public or scientific coverage was removed.

## Files deleted in Cut 5

- `tests/_legacy_jobs_support.py` — deleted test-only compatibility copy.
- `tests/_api_app_support.py` — deleted test-only compatibility copy.

(No production files were deleted in Cut 5; production deletions belong to
Cuts 2-4 and are documented in `DELETION_LEDGER.md` / `FILE_CHANGES.md`.)

## Deferred debt

1. `api/http/system_support.py` remains a small HTTP-boundary metadata helper;
   it is intentionally retained because its model-version lookup is not
   trivial transport logic. It can be revisited only if model-metadata
   resolution moves to a platform owner first.
2. Legacy H5 layout compatibility remains under `platform/sources/legacy_layouts.py`.
3. FastAPI/httpx and NumPy/sklearn dependency warnings remain external noise.
4. Inherited repository Ruff findings remain unchanged.
5. Future durable persistence (current job/report state is process-local).

READY FOR FINAL PR0162 REVIEW
