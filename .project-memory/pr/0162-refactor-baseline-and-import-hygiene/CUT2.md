# PR0162 Cut 2

## Before

Reviewed Cut 1 baseline: 4248 collected; 4237 passed, 11 skipped. No commit.
The complete scan uses --no-ignore because report directories can be ignored.

```text
src/bremen/platform/events_trace.py:4:from bremen.api.lifecycle_contracts import ExecutionStage, ExecutionTraceSummary
src/bremen/platform/runtime/executor.py:23:from bremen.api.event_schema import JobEvent, EventType
src/bremen/platform/runtime/executor.py:24:from bremen.api.execution_context import WorkflowExecutionContext
src/bremen/model_packages/aramina_v0213/inference.py:46:# ---- moved verbatim from bremen.api.workflow_aramina ----
src/bremen/platform/reports/service.py:7:from bremen.api.job_models import (
src/bremen/platform/reports/service.py:11:from bremen.api.report_provider import (
src/bremen/platform/reports/service.py:17:from bremen.api.model_result_mapper import build_standard_result
src/bremen/platform/reports/service.py:115:    from bremen.api.report_bremen import BremenReportProvider  # noqa: PLC0415
src/bremen/platform/reports/service.py:221:        from bremen.api.report_failures import build_failure_report
src/bremen/platform/sources/binding.py:12:    from bremen.api.preflight import resolve_patient_metadata
src/bremen/platform/runtime/registry.py:143:    from bremen.api.model_registry import get_model_entry
src/bremen/platform/runtime/registry.py:159:    from bremen.api.model_registry import get_registry
src/bremen/platform/runtime/registry.py:160:    from bremen.api.model_state import ModelState
src/bremen/platform/sources/service.py:96:    from bremen.api.source_registry import resolve_source_id as _resolve_source_id
src/bremen/platform/app.py:42:        from bremen.api.model_registry import (  # noqa: PLC0415
src/bremen/platform/app.py:49:            from bremen.api.s3_model_discovery import discover_models  # noqa: PLC0415
src/bremen/platform/app.py:50:            from bremen.api.model_registry import ModelRegistry  # noqa: PLC0415
src/bremen/platform/app.py:66:                from bremen.api.model_state import ModelState  # noqa: PLC0415
src/bremen/platform/jobs/repository.py:3:from bremen.api.job_models import AnalysisJob
src/bremen/platform/jobs/repository.py:6:from bremen.api.event_store import BoundedEventStore
src/bremen/platform/sources/legacy_layouts.py:112:    from bremen.api.preflight import H5ContainerError
src/bremen/platform/sources/legacy_layouts.py:184:        from bremen.api.preflight import H5ContainerError
src/bremen/platform/sources/legacy_layouts.py:248:        from bremen.api.preflight import resolve_patient_metadata
src/bremen/platform/sources/legacy_layouts.py:313:        from bremen.api.preflight import H5ContainerError
src/bremen/platform/sources/legacy_layouts.py:362:        from bremen.api.preflight import H5ContainerError
src/bremen/platform/sources/legacy_layouts.py:454:        from bremen.api.preflight import (
src/bremen/platform/sources/legacy_layouts.py:609:    from bremen.api.preflight import H5MetadataError
src/bremen/platform/sources/legacy_layouts.py:636:    from bremen.api.preflight import H5MetadataError
src/bremen/platform/sources/legacy_layouts.py:715:        from bremen.api.preflight import H5ContainerError
src/bremen/platform/sources/legacy_layouts.py:802:        from bremen.api.preflight import (
src/bremen/platform/sources/legacy_layouts.py:1060:        from bremen.api.preflight import H5ContainerError
src/bremen/platform/sources/legacy_layouts.py:1253:        from bremen.api.preflight import (
src/bremen/platform/jobs/service.py:14:from bremen.api.event_schema import (
src/bremen/platform/jobs/service.py:17:from bremen.api.job_models import (
src/bremen/platform/jobs/service.py:21:from bremen.api.report_provider import (
src/bremen/platform/jobs/service.py:61:    from bremen.api.model_registry import get_model_entry
src/bremen/platform/jobs/service.py:119:        from bremen.api.model_catalog import resolve_model  # noqa: PLC0415
src/bremen/platform/jobs/service.py:143:    from bremen.api.model_registry import get_model_entry
src/bremen/platform/jobs/service.py:212:    from bremen.api.model_registry import get_registry  # noqa: PLC0415
src/bremen/platform/jobs/service.py:290:                from bremen.api.model_registry import get_model_entry  # noqa: PLC0415
src/bremen/platform/jobs/service.py:310:                from bremen.api.aramina_api_errors import unsupported_input_details
src/bremen/platform/jobs/service.py:477:    from bremen.api.source_registry import reset_for_tests as _reset_source_registry  # noqa: PLC0415
src/bremen/platform/api/http_policy.py:102:    from bremen.api.server import _get_auth_config as _gac  # noqa: PLC0415
src/bremen/platform/api/http_policy.py:152:    from bremen.api.server import _get_auth_config as _gac  # noqa: PLC0415
src/bremen/platform/api/routers/system.py:17:        from bremen.api.app import handle_health as _handle_health  # noqa: PLC0415
src/bremen/platform/api/routers/system.py:37:        from bremen.api.app import handle_model_version as _handle_model_version  # noqa: PLC0415
src/bremen/platform/api/routers/events.py:44:        from bremen.api.event_schema import allowed_event_details  # noqa: PLC0415
src/bremen/platform/api/routers/events.py:97:        from bremen.api.event_schema import allowed_event_details  # noqa: PLC0415
src/bremen/platform/api/legacy_jobs.py:10:from bremen.api.execution_trace import build_trace_from_events
src/bremen/platform/api/legacy_jobs.py:100:    from bremen.api.aramina_api_errors import (
src/bremen/platform/api/legacy_jobs.py:157:        from bremen.api.source_registry import get_stable_source_key  # noqa: PLC0415
src/bremen/platform/api/legacy_jobs.py:204:            from bremen.api.source_registry import get_source_info  # noqa: PLC0415
src/bremen/platform/api/routers/auth.py:19:        from bremen.api.server import (  # noqa: PLC0415
src/bremen/platform/api/routers/auth.py:80:        from bremen.api.server import (  # noqa: PLC0415
src/bremen/platform/api/routers/auth.py:156:        from bremen.api.server import _get_auth_config as _gac  # noqa: PLC0415
src/bremen/platform/api/routers/ui.py:120:        from bremen.api_docs_ui import build_api_docs_page  # noqa: PLC0415
src/bremen/platform/api/routers/ui.py:137:        from bremen.api.server import _get_auth_config as _gac  # noqa: PLC0415
src/bremen/platform/api/routers/models.py:20:        from bremen.api.model_catalog import (  # noqa: PLC0415
src/bremen/platform/api/routers/models.py:46:        from bremen.api.model_requirements import (  # noqa: PLC0415
src/bremen/platform/api/routers/models.py:86:        from bremen.api.fastapi_contracts import (  # noqa: PLC0415
src/bremen/platform/api/routers/models.py:89:        from bremen.api.model_requirements import (  # noqa: PLC0415
src/bremen/platform/api/routers/jobs.py:26:        from bremen.api.fastapi_contracts import JobCreateRequest  # noqa: PLC0415
src/bremen/platform/api/routers/jobs.py:28:        from bremen.api.aramina_api_errors import (
src/bremen/platform/api/routers/jobs.py:127:            from bremen.api.source_registry import (  # noqa: PLC0415
src/bremen/platform/api/routers/jobs.py:175:                from bremen.api.source_registry import (  # noqa: PLC0415
src/bremen/platform/api/routers/jobs.py:355:        from bremen.api.execution_trace import build_trace_from_events  # noqa: PLC0415
src/bremen/platform/api/routers/sources.py:24:        from bremen.api.server import (  # noqa: PLC0415
src/bremen/platform/api/routers/sources.py:46:        from bremen.api.server import (  # noqa: PLC0415
```

Classification: job values, event values/storage/context/traces, model catalog/state,
source registry/preflight and report projection are application dependencies owned
under API. Their transitive dependencies move with them. HTTP routers, HTTP policy,
legacy HTTP job adapter and FastAPI composition are outer adapters misplaced under
platform: they move outward. api_docs_ui is a separate package, and the historical
workflow_aramina comment is not an import. No scientific behavior is being changed.

## Changes

`WorkflowRun`, `ReportMetadata`, and `AnalysisJob` are application dataclasses,
not HTTP/Pydantic schemas. All three now have exactly one definition in
`src/bremen/platform/jobs/models.py`. The old API module was deleted; no shim.

Exact module ownership moves (all paths below are Python module names):

| Previous owner | Authoritative owner |
| --- | --- |
| `bremen.api.job_models` | `bremen.platform.jobs.models` |
| `bremen.api.event_schema` | `bremen.contracts.events` |
| `bremen.api.event_store` | `bremen.platform.events.store` |
| `bremen.api.execution_context` | `bremen.platform.events.context` |
| `bremen.api.lifecycle_contracts` | `bremen.contracts.trace` |
| `bremen.api.execution_trace` | `bremen.platform.events.trace` |
| `bremen.api.model_registry` | `bremen.platform.models.registry` |
| `bremen.api.model_catalog` | `bremen.platform.models.catalog` |
| `bremen.api.model_state` | `bremen.platform.models.state` |
| `bremen.api.source_registry` | `bremen.platform.sources.registry` |
| `bremen.api.preflight` | `bremen.platform.sources.preflight` |
| `bremen.api.report_provider` | `bremen.contracts.reports` |
| `bremen.api.model_result_mapper` | `bremen.platform.reports.mapper` |
| `bremen.api.standard_model_result` | `bremen.contracts.results` |
| `bremen.api.report_bremen` | `bremen.platform.reports.bremen` |
| `bremen.api.report_failures` | `bremen.platform.reports.failures` |
| `bremen.api.decision_support` | `bremen.platform.reports.decision_support` |
| `bremen.api.aramina_api_errors` | `bremen.platform.reports.diagnostics` |
| `bremen.platform.app` | `bremen.api.http.app` |
| `bremen.platform.api.http_policy` | `bremen.api.http.http_policy` |
| `bremen.platform.api.__init__` | `bremen.api.http.__init__` |
| `bremen.platform.api.legacy_jobs` | `bremen.api.http.legacy_jobs` |
| `bremen.platform.api.routers.auth` | `bremen.api.http.routers.auth` |
| `bremen.platform.api.routers.system` | `bremen.api.http.routers.system` |
| `bremen.platform.api.routers.models` | `bremen.api.http.routers.models` |
| `bremen.platform.api.routers.ui` | `bremen.api.http.routers.ui` |
| `bremen.platform.api.routers.events` | `bremen.api.http.routers.events` |
| `bremen.platform.api.routers.__init__` | `bremen.api.http.routers.__init__` |
| `bremen.platform.api.routers.jobs` | `bremen.api.http.routers.jobs` |
| `bremen.platform.api.routers.sources` | `bremen.api.http.routers.sources` |
| `bremen.platform.api.routers.reports` | `bremen.api.http.routers.reports` |

The HTTP router tree and composition factory now live in `api/http`; HTTP auth
policy and legacy request translation moved with them. This resolves their
reverse references to `api.server`, `api.app`, request schemas, requirements,
and S3 discovery without pulling those transport responsibilities into platform.

The remaining scan matches were application dependencies: event values and trace
values moved to contracts; event storage/context/projection to platform/events;
model metadata catalog/state to platform/models; opaque source registry and
metadata/structural H5 preflight to platform/sources; report values to contracts
and report/diagnostic projection to platform/reports. Imports from the pre-existing
source, job, runtime, trace and report services were retargeted to these owners.
The Aramina historical comment was reworded to avoid a false import-scan match.
The api_docs_ui match was an unrelated package name, not a reverse dependency.

Required explicit workflow selection in four signatures:

- `contracts.execution.ExecutionRequest.workflow_id`
- `platform.runtime.executor.run_workflow_request(..., workflow_id, ...)`
- `platform.jobs.service.create_analysis_job(..., *, workflow_id, ...)`
- `platform.models.catalog.resolve_model(..., *, workflow_id, ...)`

Production callers already pass the resolved workflow. Direct internal tests now
pass their intended workflow explicitly. No workflow-name dispatch was added.
Imports, monkeypatch targets and source-file inventories in existing callers,
startup scripts and tests were updated. Deleted owners have no re-export shims.

A snapshot of the working Cut 1 tree was taken before editing. Comparing production
ASTs across the ownership map, excluding imports/docstrings and mapping module
reference strings, finds differences only in the four signatures above.
All model package function bodies, H5 layout interpretation, canonical QC,
preprocessing, features, symmetry, thresholds and prediction behavior are unchanged.
Large deferred modules received import retargeting only.

## Dependency boundary after

The required `rg -n 'from bremen.api|import bremen.api'` scan returns no matches
(exit 1), including when repeated with `--no-ignore` to cover report code.
The deterministic AST test now checks platform, contracts and model packages,
resolves relative imports and checks imported members as well as module names.
It forbids platform -> api, contracts -> api/platform/model_packages, and
model_packages -> api/platform; it also preserves the FastAPI boundary checks.

`rg` finds exactly one class definition each for AnalysisJob, WorkflowRun and
ReportMetadata, all in platform/jobs/models.py. An AST assertion enforces this.

The broad workflow regex still finds explicit identities/comparisons in the
Bremen report provider, failure/trace projections, legacy source adapter and
legacy catalog registration. These are existing product registrations/projections,
not argument defaults. AST inspection finds no function argument default equal
to `"bremen"` in platform/contracts. Signature tests enforce explicit selection
for ExecutionRequest, the executor adapter, job creation and catalog resolution.

## inference_handler disposition

**DELETE.** `api/inference_handler.py` had zero production callers; only two
integration tests imported its redundant wrapper. No transport route used it.
The synthetic end-to-end test now executes the supported
`api.app.handle_submit_prediction` / `handle_get_prediction` path, asserting
completion, the actual public result fields and the decision-support report.
It intentionally omits workflow_id and therefore characterizes the retained
outer HTTP default to Bremen. It supplies the required scan references.
The opt-in real-model smoke now calls the authoritative executor with an explicit
Bremen workflow and checks its probability/decision payload.
No public response schema was changed to match the deleted internal wrapper.

## Public contract verification

- Exact baseline equality: 29 method/path pairs, 27 paths.
- Exact Bremen/Aramina public result projection equality against unchanged
  `public_results.json`.
- Existing report parity, auth, event ordering, duplicate/replay, safe failure,
  standard_result, risk_score and technical_demo_only tests pass.
- Legacy request omission remains at outer HTTP boundaries, including
  `api.app`, `api.server`, and `api.http.legacy_jobs`; it is absent from generic
  execution/catalog/job defaults.
- Bremen and Aramina package/runtime regression suites pass. No scientific
  code was moved into generic platform execution. Optional real-artifact tests
  remain skipped unless their external inputs are configured; this run does not
  claim a fresh real-data scientific validation.

## Validation

Final commands and outcomes (repository venv):

```text
./venv/bin/python -m compileall -q src tests
PASS

./venv/bin/python -m pytest -q   tests/test_platform_architecture_pr0162.py   tests/test_bremen_fastapi_jobs_report_parity.py   tests/test_bremen_fastapi_auth_enforcement.py   tests/test_aramina_workflow_runtime.py   tests/test_aramina_v0213_package.py   tests/test_bremen_v01_package.py
402 passed, 867 warnings in 5.63s

./venv/bin/python -m pytest -q   tests/test_bremen_job_api_handler.py   tests/test_bremen_inference_integration.py   tests/test_bremen_model_catalog.py   tests/test_model_registry.py   tests/test_catalog_api_multi_model.py
120 passed, 1 skipped in 1.16s

./venv/bin/python -m pytest --collect-only -q
4248 tests collected in 1.78s (1 warning)

./venv/bin/python -m pytest -q --durations=100
4237 passed, 11 skipped, 1678 warnings in 28.43s
Slowest: 3.88s call
  tests/test_bremen_logging.py::TestS3StagingEvents::test_s3_staging_failure_events

./venv/bin/ruff check . --output-format=json
163 inherited findings; exit 1, same total as reviewed Cut 1.
Zero new findings after normalizing moved module paths in filenames/messages.
Inherited E741 and sklearn warnings were not changed.

./venv/bin/ruff check tests/test_platform_architecture_pr0162.py
All checks passed.

git diff --check
PASS
```

Test count remains 4248: the two prior parameterized import-boundary cases are
now one deterministic scan covering all three boundaries, and a single-owner
job type test was added. Signature checks extend the existing executor test;
the two deleted-wrapper caller tests were replaced in place. No tests were
removed for speed and no test-suite optimization was performed.

Initial validation exposed stale source-file inventories and missing required
scan references in the migrated integration test. Those tests were corrected
without relaxing public/scientific assertions. The final focused and full runs
above pass. Full git diff and git status were inspected; existing Cut 1 changes
and unrelated smoke evidence remain in the working tree. No staging or commit.

## Remaining blockers for Cut 3

No blockers observed for completing this dependency-boundary cut. Existing
architecture debt remains: the legacy HTTP server coexists with FastAPI;
legacy H5 layouts still live in the compatibility source adapter; application
job/report projections retain existing product-specific handling. Those are
explicitly deferred, with no server retirement, scientific redesign, persistence
or async work in this cut. Repository-wide inherited lint debt remains unchanged.

READY FOR 0162 CUT 3
