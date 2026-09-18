# Deletion and ownership ledger

Baseline was captured before production edits or test retirement. Audit used `rg -n` across src, tests, scripts and docs; production callers were distinguished from tests and historical prose. Exact file paths and split destinations are in FILE_CHANGES.md. No documented external Python import API required the removed internal shims.

| Original module / capability | Decision | Authoritative replacement; production-reference audit; affected tests; public impact |
|---|---|---|
| api/workflow_provider.py | DELETE interface; MOVE data | contracts/execution.py retains result/readiness envelopes only. No build_features/run_inference/execute ABC. Old provider registry/plugin/scaffold imports removed. Descriptor/runtime contract tests replace test-only fake providers. Public envelopes preserved. |
| api/workflow_registry.py | REPLACE | platform/runtime/registry.py holds descriptors and package factories; no provider operations. Job and requirements callers select a descriptor. Old fake-provider suite retired; duplicate/unknown selection and third-runtime tests retained in PR0162 suite. |
| api/workflow_orchestrator.py | REPLACE | platform/runtime/executor.py invokes validate/predict once. App/server/inference compatibility routes and jobs migrated. Source checksum/patient binding extracted; legacy normalization explicit. Existing public endpoint/parity/event tests retained. |
| api/workflow_bremen.py | DELETE | Package runtime is scientific authority; public result/event projection lives in platform/reports. Production callers now resolve descriptors. Duplicate provider feature/inference tests retired; PR0151/0152 golden vectors, six-measurement participation, gates, PR0160 raw ownership and package error/metadata tests retained. No thresholds/features changed. |
| api/workflow_aramina.py | DELETE | Package runtime/inference/errors own all former reexports. Projection/binding policy replaces execute adapter. HTTP/job/real synthetic-artifact tests retargeted without changing scientific expected values. |
| api/runtime_plugin.py | DELETE ABC; MOVE trace functions | Only execution_trace used ordering/trace projection; no production class implemented the ABC. Trace functions now platform/events_trace.py. Event/context/privacy/trace tests retained; obsolete stage-method reflection tests replaced by real execution-event tests. |
| api/lifecycle_contracts.py: PreparedArtifact, PreparedWorkflowInput, FeatureSet, FeatureValidation, ModelOutput, OutputValidation, DecisionOutput | DELETE | Whole-source audit found definitions only after provider/plugin removal. ExecutionStage and ExecutionTraceSummary remain because report/event projection consumes them. No public output type removed. |
| api/workflow_aramina_scaffold.py | DELETE | No production caller; real Aramina package descriptor was already authoritative. Scaffold-only tests removed; actual route tests assert scaffold absence. No public route removed. |
| api/report_aramina.py | DELETE | No production caller; successful Aramina report generation already used the local numeric report projection, now in reports/service.py. Scaffold assertions retired; legacy risk_score and technical_demo_only tests retained. |
| api/aramina_provider.py | DELETE scaffold helpers; MOVE request | Only request carrier had production callers (job request validation). Neutral contracts/request.py contains AnalysisParameters. Unused scaffold result/error/validator helpers and their contract-only tests removed. Request field types/public validation responses unchanged. |
| api/aramina_artifact_compat.py | DELETE | Pure reexport, no independent behavior. Package artifact_compat is authoritative; imports/fixtures retargeted. Artifact-loading tests retained. |
| api/aramina_preprocessing.py | DELETE | Pure reexport. Package preprocessing is authoritative; tests patch actual package functions. Worker/pin behavior unchanged. |
| api/aramina_symmetry.py | DELETE | Pure reexport. Package symmetry authoritative; mathematical tests retargeted. |
| bremen_features.py | DELETE | Pure reexport. Package features authoritative; training/runtime callers and golden tests use package directly. |
| bremen_runtime.py | DELETE | Pure reexport. Package runtime authoritative; ModelRuntime tests retained. |
| inference.py | DELETE | Pure reexport. Portable package predictor authoritative; server/feature-artifact/inference imports retargeted. Legacy HTTP response adapter remains supported. |
| api/xrd_normalization.py | DELETE | Pure reexport of canonical vocabulary. Callers use contracts/canonical_input.py directly. Validators and tests preserved. |
| model_runtime.py / canonical_input.py | MOVE | Neutral contracts package; no platform/model imports. Contract behavior unchanged. Import architecture tests enforce direction. |
| api/decision_contract.py | MOVE | Bremen package decision vocabulary/processing; API/report callers import package-owned policy. Frozen decision tests retained. |
| api/preprocessing_bridge.py scientific functions | DELETE | Audit found no production caller of run_preprocessing_bridge, build_feature_table, schema validation or profile math. Server imported error categories/constants only; inference adapter imported schema metadata only. Package frozen pipeline is sole scientific replacement. Three bridge-specific test files retired (below). Legacy error classes retained only for safe HTTP translation. |
| api/symmetry_signals.py | MOVE | Existing legacy report callers in decision_support still consume its output. Moved unchanged to Bremen package; no report schema/math changed. Signal tests retargeted. |
| api/h5_layouts.py | MOVE / BLOCKED deletion | platform/sources/legacy_layouts.py retains exact interpretation and QC. Aramina package still checks canonical inputs before artifact-owned raw preprocessing; integrated-profile Bremen artifacts also use it. Legacy input adapter explicitly selected by descriptor; raw Bremen bypass tested. Raw-only scientific parity is required before deletion. |
| api/inference_handler.py | KEEP transport projection | Existing supported legacy result dictionary adapter delegates to new executor; unused bridge/scientific imports removed. No scientific implementation remains here. |
| api/server.py | KEEP | Supported legacy HTTP/CLI transport, safe error mapping and startup/auth state. Jobs/sources delegate to extracted services. Future transport retirement requires explicit approval of public API impact. |
| api/fastapi_app.py | REPLACE by decomposition | One composition root plus system/models/sources/jobs/reports/events/auth/UI route groups and shared HTTP policy. Full baseline path inventory unchanged. |
| api/job_api_handler.py | REPLACE by decomposition | Repository state/locks, job/source/report services, safe value helpers, legacy HTTP translation. Every production import retargeted to its owner. Concurrent/job/source/report/HTTP tests retained. |

## Retired test files

These files exercised deleted internal architecture, not removed public behavior:

- tests/test_aramina_provider_contract.py — unused scaffold helper result/error/validator contracts; live Aramina request/API validation tests retained.
- tests/test_bremen_workflow_aramina_scaffold.py — unavailable scaffold and placeholder report classes; real artifact route tests retained.
- tests/test_bremen_workflow_bremen.py — duplicated provider-era feature/inference entry methods; package/runtime golden and report tests retained.
- tests/test_bremen_workflow_registry.py — fake WorkflowProvider inheritance/registry contracts; new descriptor/third-runtime selection tests replace them.
- tests/test_bremen_preprocessing_bridge.py — unused legacy duplicate preprocessing math; authoritative package feature/gate tests retained.
- tests/test_bremen_calibration_preprocessing.py — unused bridge extraction/math (including two optional integration skips); H5 layout and package-owned real-evidence suites retained.
- tests/test_bremen_v01_schema_rebaseline.py — unused bridge feature-vector class/schema validator; frozen ordered package feature schema and rejection tests retained.

## Retired assertions within retained files

- test_bremen_runtime_plugin.py: TestArtifactStage, TestFeatureStage, TestDecisionStage, TestProviderIsolation tested removed provider stage methods/identifiers. Retained execution context, ordering, trace, event budget and privacy behavior. New PR0162 tests check actual event ordering/fields.
- test_bremen_control_room.py: source-reflection assertions against prepare_artifact/execute (including duplicated inherited assertions) removed; UI and runtime contract tests remain.
- test_bremen_v01_package.py and test_bremen_model_package_deduplication.py: tests requiring compatibility shim files were replaced by explicit removed-module absence assertions.
- Aramina missing-request test no longer invokes deliberately unsupported provider build_features/run_inference methods; it still proves safe invalid-request behavior through the executor.

No expected scientific probability, feature vector, threshold, clinical class, public report field location, HTTP route or auth policy was changed to make the refactor pass.

## Cut 5 final demolition

| Removed test-only subject | Former responsibility | Final owner / retained coverage | Caller audit and public effect |
|---|---|---|---|
| `tests/_legacy_jobs_support.py` | Copied the deleted legacy job/report HTTP adapter for unit tests | Deleted. Public job, report, duplicate/replay, and event behavior is covered through FastAPI routes and direct platform job/report services; Aramina scientific parity tests remain. | No production callers remained. **NO PUBLIC CONTRACT LOSS.** Assertions of deleted handler internals were removed. |
| `tests/_api_app_support.py` | Copied deleted `api.app` prediction, health, and model-version handlers | Deleted. Health and model-version behavior is covered by the system routes; job behavior is covered by current FastAPI/platform boundaries. | No production callers remained. **NO PUBLIC CONTRACT LOSS.** Assertions of deleted facade internals were removed. |

`src/bremen/api/http/system_support.py` was reviewed and deliberately kept. Its
model-version lookup has catalog, explicit-package, loaded-state, failed-state,
and cloud precedence; moving that substantive reusable lookup into a router
would recreate a hidden service boundary. It has one caller (the system router),
contains no scientific logic, and is not an application compatibility facade.
