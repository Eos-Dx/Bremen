# PR0153B — Model Runtime Contract v1 implementation

## Branch / HEAD / authority

- Branch: `0153b-model-runtime-contract-v1`
- HEAD at plan time: `a2fabd74737dc4133273f19e4b5ecee5da6d3995` (docs: define
  model runtime contract v1, #213). Clean worktree.
- Accepted ADR reviewed: `docs/adr/0016-model-runtime-contract-v1.md` (Accepted)
  and `docs/model_runtime_contract_v1.md`.
- Context read: `docs/bremen_3x3_training_parity.md` (Parts 1+2),
  `.project-memory/pr/0152-bremen-3x3-runtime-parity/{PLAN.md,PRECOMMIT_REVIEW.md}`.
- Implementation files inspected completely before design:
  `src/bremen/bremen_runtime.py`, `src/bremen/bremen_features.py`,
  `src/bremen/api/workflow_bremen.py`, `src/bremen/api/workflow_aramina.py`,
  `src/bremen/api/workflow_orchestrator.py`, `src/bremen/api/workflow_registry.py`,
  `src/bremen/api/model_requirements.py`.

## Existing abstractions inspected (no duplicate created)

- `WorkflowProvider` (ABC, `api/workflow_provider.py`): platform/job-layer
  lifecycle (readiness, compatibility, build_features, run_inference, execute,
  MultiWorkflowResult). It owns workflow/job semantics, not the model-science
  semantic boundary; extending it with scientific `requirements()/validate()/
  predict()` would violate the documented boundary (WorkflowProvider is an
  adapter, not a runtime). Therefore NOT extended with scientific methods.
- `WorkflowRuntimePlugin` (ABC, `api/runtime_plugin.py`): event-lifecycle
  tracing stage machine owned by providers; explicitly not a runtime
  abstraction for science; untouched.
- Protocol precedents: `EventSink` (api/execution_context.py),
  `RecordResolver` (system_of_record.py). Repository style supports
  `typing.Protocol` for narrow semantic interfaces.
- No generic model-runtime abstraction exists (`grep` for ModelRuntime/
  runtime contract in src/tests: none).

## Chosen runtime interface form

Structural `typing.Protocol` (`runtime_checkable=True`), single new small
module `src/bremen/model_runtime.py`, defining:

- `ModelRuntime` protocol with exactly three semantic members:
  - `model_requirements() -> ModelRequirements`
  - `validate_model_input(input: ModelInput) -> ModelValidation`
  - `predict_model(input: ModelInput) -> RuntimePrediction`
- Support types: `ModelInput` (canonical measurements + optional request
  parameters), `ModelRequirements` (model-declared input contract as a typed
  view incl. `to_input_requirements()` payload), `ModelValidation`,
  `RuntimePrediction` (structured internal result with `result` mapping;
  provider translates to existing workflow result), `CONTRACT_VERSION = "v1"`.
- Internal error categories (all safe constant messages): `ModelRuntimeError`
  base plus `ModelInputInvalidError`, `ModelInputUnsupportedError`,
  `ModelConfigurationRequiredError`, `ModelPreprocessingFailedError`,
  `ModelInferenceFailedError`.

Protocol chosen over ABC: structural (works for existing classes without
forced re-parenting), precedent in repo, no shared fake behavior required,
least invasive. Dependency direction: `model_runtime.py` imports nothing from
`bremen.api.*` and nothing Bremen/Aramina-specific (innermost layer).

## Model runtime contract (concrete)

- `ModelInput`: `workflow_id`, `measurements` (existing canonical measurements,
  reused not redesigned), `patient_id`, `target_side`, `h5_path`
  (platform-staged container path — documented remaining coupling for PR0154).
- `ModelRequirements.request_fields` / `optional_request_fields` express the
  public request-field contract so the Model Requirements API can derive from
  the runtime (no second requirements system).
- `RuntimePrediction.result`: model-owned safe mapping (probability/
  prediction/threshold/decision or external_report etc.); providers copy into
  existing payload shapes — no new public API fields.

## Bremen adaptation strategy

`BremenRuntime` implements the contract directly (no wrapper layers):

- `model_requirements()`: workflow/model identity, feature schema version,
  exactly 3 LEFT + 3 RIGHT (six total) encoded via `measurement_sides` +
  `total_measurements`, `request_fields=("container_id","source_id")` (matches
  current public behavior), supported model version `0.2.0-paper-reference`.
- `validate_model_input()`: wraps `validate_bremen_shape` into
  `ModelValidation`; missing measurements -> `ModelInputInvalidError`.
- `predict_model()`: runs the frozen PR0152 sequence
  (`validate_input` -> `build_features` -> `score`) unchanged, notifies
  optional `on_features` callback once, returns `RuntimePrediction` with the
  existing `BremenModelResult` as `result` mapping.
- Error mapping keeps `safe_reason` constants byte-identical to PR0152:
  `requires_exactly_3_left_3_right` -> `ModelInputInvalidError`;
  `raw_peak_gate_failed` / `invalid_scientific_profiles` ->
  `ModelPreprocessingFailedError`; `model_not_ready` ->
  `ModelConfigurationRequiredError`; `model_execution_failed` ->
  `ModelInferenceFailedError`.
- `BremenProvider` remains a thin adapter: `execute()` delegates to one
  `runtime.predict_model()` call; error translation preserved
  (`ModelInputInvalidError` -> `Incompatible: <reason>`; configuration ->
  `Workflow configuration required...`; inference -> `Model execution
  failed`; other runtime errors -> `Feature construction failed: <safe_reason>`
  exactly as PR0152). Compatibility gate still uses the runtime. No science
  returns to `workflow_bremen.py`.

## Aramina adaptation strategy

Adapter in place (no rewrite, no science duplication):

- New `AraminaRuntime` class inside `src/bremen/api/workflow_aramina.py`
  (same authoritative module that already owns Aramina inference) composing the
  existing functions unchanged: `_build_aramina_request_json`,
  `_load_selected_artifact`, `_prepare_features`, `_run_local_artifact`.
- `model_requirements()`: `requires_target_side=True`,
  `allowed_target_sides=("left","right")`, `request_fields=
  ("container_id","source_id","patient_id","target_side")`,
  optional `("analysis_author","prediction_comment")` — equal to the existing
  public requirements defaults; model identity from registry entry.
- `validate_model_input()`: explicit target_side via the existing request
  validator (`ARAMINA_INVALID_REQUEST` -> `ModelInputInvalidError`); case
  validation stays inside predict (`validate_canonical_case` unchanged).
- `predict_model()`: executes the existing artifact pipeline;
  `AraminaWorkflowError` propagates unchanged (its public code/stage/diagnostic
  taxonomy already equals the ownership categories; external behavior
  identical).
- `AraminaWorkflowProvider` keeps constructing its `entry`, delegates
  `execute()` to `self._runtime.predict_model(...)` and keeps the identical
  payload/WorkflowResult projection and failure translation
  (`_safe_stage`, preprocessing_diagnostic rules unchanged).
- Public request requirements, target_side semantics, source resolution,
  preprocessing release selection, failure classification: unchanged.

## WorkflowProvider wiring (minimal, backward compatible)

- Non-abstract convenience accessor `WorkflowProvider.model_runtime()`
  returning `None` by default; Bremen and Aramina providers return their
  contract runtime. Purely additive; existing subclasses unaffected.
- Model Requirements API resolves `entry -> provider -> runtime ->
  runtime.model_requirements()` (registry/orchestrator routing reused, not
  redesigned).

## Requirements integration strategy

`model_requirements._build_declared_requirements_response` (additive, behavior
preserving):

- When no runtime available (legacy/test registries, display-only rows):
  output byte-identical to PR0124 behavior.
- When a runtime exists: `required_fields`/`optional_fields` fall back to the
  runtime-declared fields only when the manifest does not declare them; the
  container contract is annotated with an additive
  `container_requirements["model_runtime"] = {"contract_version": "v1",
  "input_requirements": {...runtime payload...}}`. Endpoint paths, existing
  field names and types unchanged; runtime payload is static model-declared
  strings (no paths/secrets).

## Validation boundary

- Model runtime: scientific input contract (Bremen 3+3 shape + measurement
  validation inside frozen feature path; Aramina explicit target_side +
  artifact-owned preprocessing checks through existing stage taxonomy).
- Platform (orchestrator/job handler): source existence, authorization,
  routing, job identity, H5 patient binding through `_validate_aramina_source`
  as invoked by the existing runtime pipeline — position unchanged (documented
  remaining coupling).
- Invalid input still fails before any scientific work or scoring (preserved
  PR0152 guarantee, asserted by regression + new contract tests).

## Prediction boundary

- One authoritative scientific implementation per model, unchanged:
  Bremen = `BremenRuntime`/`bremen_features` (PR0152 frozen);
  Aramina = `workflow_aramina` pipeline + `aramina_preprocessing` +
  `aramina_symmetry` (existing).
- Providers translate `RuntimePrediction` into the existing `WorkflowResult`
  payloads; no provider performs preprocessing, feature formulas, aggregation,
  scaler/estimator math, or threshold application themselves.

## Error compatibility strategy

- No public error codes renamed. `ARAMINA_*` codes, Bremen fixed reason
  constants (`requires_exactly_3_left_3_right`, `invalid_scientific_profiles`,
  `raw_peak_gate_failed`), `Incompatible:` envelope, job API mapping all
  preserved; runtime error categories carry the same `safe_reason` values.
- No source paths, S3 keys, artifact paths, tracebacks, tokens, env vars or
  package internals in runtime errors (constant messages only).

## Expected files

Changed:
- `src/bremen/model_runtime.py` (NEW — common contract + types + error categories)
- `src/bremen/bremen_runtime.py` (contract methods; error hierarchy links)
- `src/bremen/bremen_features.py` (import-safe error base only; no science change)
- `src/bremen/api/workflow_bremen.py` (delegate execute via contract; runtime handle)
- `src/bremen/api/workflow_aramina.py` (AraminaRuntime adapter; provider delegates; runtime handle)
- `src/bremen/api/workflow_provider.py` (additive `model_runtime()` accessor)
- `src/bremen/api/model_requirements.py` (runtime-derived requirements, additive)
- `tests/test_bremen_model_runtime_contract_v1.py` (NEW — contract tests)
- `tests/test_bremen_3x3_runtime_parity.py` (extend contract wiring assertions)
- `docs/model_runtime_contract_v1.md` (focused implementation notes + PR0154 coupling)

Non-goals: no retraining; no Bremen/Aramina scientific changes; no threshold/
feature changes; no new public API fields; no report/frontend/PDF changes; no
S3 registry redesign; no idempotency work; no MLflow/BentoML/KServe; no new
network model service; no model package relocation (PR0154); no commit.

## Test strategy

Contract suite (`tests/test_bremen_model_runtime_contract_v1.py`):
- structural protocol satisfaction: `isinstance(..., ModelRuntime)` for both
  `BremenRuntime` and `AraminaRuntime`.
- requirements behavior: Bremen 3+3/six-total/side counts vs Aramina
  explicit target_side + left/right; model-specific requirements differ behind
  the same contract type.
- validation routing: Bremen invalid shape (3+2) -> `ModelInputInvalidError`,
  valid -> compatible; Aramina missing/invalid target_side ->
  `ModelInputInvalidError`; platform concerns not owned by runtimes.
- predict routing + provider delegation: monkeypatched fake runtime injected
  into `BremenProvider` proves execute/predict routing without touching
  provider scientific logic; error-category translation preserves strings.
- model requirements API derives from runtime (additive block + fallback
  equality with legacy defaults).
- minimal fake runtime satisfies the protocol and drives a synthetic provider
  end-to-end (unit-testability requirement).
- dependency direction: `model_runtime.py` imports no `bremen.api`,
  `bremen_runtime`, or `workflow_*` modules; error category set exact.

Regression (run, not rewritten): PR0151/PR0152 parity suites (golden features,
golden probability, all-six participation, permutation invariance, raw-H5
parity, invalid shapes), Aramina runtime/provider/preprocessing/report suites,
requirements API suite, registry/orchestrator/multi-model suites.

## Validation commands

- `python -m compileall -q src tests`
- `pytest -q tests/test_bremen_model_runtime_contract_v1.py`
- `pytest -q tests/test_bremen_3x3_runtime_parity.py tests/test_bremen_3x3_training_parity.py tests/test_bremen_workflow_bremen.py tests/test_bremen_runtime_plugin.py`
- `pytest -q tests/test_aramina_workflow_runtime.py tests/test_aramina_provider_contract.py tests/test_bremen_workflow_aramina_scaffold.py` (plus aramina preprocessing/report suites)
- `pytest -q tests/test_bremen_model_requirements_api.py`
- `pytest -q tests/test_bremen_workflow_registry.py tests/test_multi_model_execution.py tests/test_catalog_api_multi_model.py tests/test_bremen_training_runtime_separation.py`
- `pytest -q`
- `ruff check` on every changed Python file
- `git diff --check`
