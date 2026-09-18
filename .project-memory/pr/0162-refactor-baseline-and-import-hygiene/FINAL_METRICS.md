# PR0162 Final Metrics

## Baseline

Original pre-Cut 1 baseline: 37,647 Python source LOC, 58,729 Python test
LOC, 123 test files, and 4,411 collected tests.

## Final

Measured after Cut 5: 32,861 Python source LOC, 51,691 Python test LOC, 128
source files, 118 test files, and 3,964 collected tests. Full pytest completed
with 3,956 passed, 8 skipped, 653 warnings in 30.31 seconds.

## Delta

| Measure | Baseline | Final | Absolute delta | Percent delta |
|---|---:|---:|---:|---:|
| Source LOC | 37,647 | 32,861 | -4,786 | -12.71% |
| Test LOC | 58,729 | 51,691 | -7,038 | -11.96% |
| Source files | not recorded | 128 | — | — |
| Test files | 123 | 118 | -5 | -4.07% |
| Collected tests | 4,411 | 3,964 | -447 | -10.13% |
| Full pytest seconds | not recorded | 30.31 | — | — |

Cut 4's recorded validation was 4,088 collected, 4,077 passed, 11 skipped,
680 warnings, and 34.59 seconds. Cut 5 therefore removed 124 collected tests,
reduced skipped tests by 3, and reduced observed runtime by 4.28 seconds.
Cut 4 did not record aggregate LOC/file totals separately; no unsupported
Cut 4 LOC comparison is inferred here.

## Architecture removed

- The legacy stdlib HTTP server and API server/discovery owners.
- Provider, orchestrator, workflow registry, runtime-plugin, bridge, and API
  scientific re-export modules listed in the deletion ledger.
- `api/app.py` and `api/http/legacy_jobs.py` application facades.
- The two test-only compatibility copies `tests/_legacy_jobs_support.py` and
  `tests/_api_app_support.py`.

## Architecture added

The enduring owners are FastAPI route groups, platform jobs/sources/reports,
platform model discovery and runtime execution, neutral contracts, and thick
model packages. `api/http/system_support.py` remains the single non-trivial
model metadata lookup used by the system router.

## Public contract

The frozen route inventory remains 29 method/path pairs over 27 unique paths;
public route and result snapshots are exact. Auth, catalog, requirements,
source, jobs, duplicate/replay, reports, events/SSE, tickets, and UI routes
remain covered. No `/standard-result` endpoint exists.

## Scientific parity

Cut 5 made no scientific implementation changes. Package-owned preprocessing,
features, symmetry, measurement aggregation, estimators, thresholds, and
frozen parity evidence remain unchanged. Legacy H5 interpretation remains an
explicitly deferred boundary pending independent parity evidence.

## Largest remaining source modules (informational)

| LOC | Module | Final role |
|---:|---|---|
| 1541 | `src/bremen/report_ui.py` | UI/report rendering |
| 1506 | `src/bremen/platform/sources/legacy_layouts.py` | legacy H5 interpretation/QC |
| 1334 | `src/bremen/workspace_ui.py` | workspace UI |
| 1325 | `src/bremen/modeling.py` | training/model comparison |
| 1281 | `src/bremen/control_room_ui.py` | control-room UI |
| 1163 | `src/bremen/platform/models/discovery.py` | platform model discovery |
| 736 | `src/bremen/training/pipeline.py` | training pipeline |
| 687 | `src/bremen/api/model_requirements.py` | requirements projection |
| 588 | `src/bremen/config.py` | configuration |
| 587 | `src/bremen/demo_ui.py` | demo UI |
| 583 | `src/bremen/platform/sources/preflight.py` | source preflight |
| 544 | `src/bremen/model_packages/aramina_v0213/inference.py` | Aramina package science |
| 513 | `src/bremen/pipelines.py` | reusable pipelines |
| 513 | `src/bremen/api_docs_ui.py` | API docs UI |
| 487 | `src/bremen/model_packages/bremen_v01/symmetry_signals.py` | Bremen package science |
| 479 | `src/bremen/platform/jobs/service.py` | platform job service |
| 462 | `src/bremen/model_packages/bremen_v01/features.py` | Bremen package science |
| 454 | `src/bremen/demo_smoke.py` | demo smoke flow |
| 420 | `src/bremen/platform/reports/service.py` | platform report service |
| 415 | `src/bremen/platform/models/state.py` | platform model state |

## Deferred debt

- Legacy H5 layout compatibility remains until independent raw-only scientific
  parity evidence exists.
- The in-memory job/report repositories remain process-local.
- Inherited repository Ruff findings remain; Cut 5 introduced no new findings.
- External FastAPI/httpx and NumPy/sklearn warnings remain dependency noise.
