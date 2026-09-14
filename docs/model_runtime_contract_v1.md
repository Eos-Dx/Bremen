# Model Runtime Contract v1

Status: Accepted platform contract (implemented by PR0153B; see "PR0153B implementation notes" at the end of this document)

Purpose

This document defines the boundary between Bremen Platform and model-specific inference runtimes.

The central rule is:

Bremen Platform orchestrates inference. Model runtimes implement scientific inference.

WorkflowProvider MUST NOT implement model-specific scientific feature engineering.

Background

PR0151 established the authoritative Bremen 3 LEFT + 3 RIGHT training contract.

PR0152 implemented that contract in production and introduced BremenRuntime as the owner of Bremen-specific scientific inference.

This contract generalizes that boundary so Bremen, Aramina, and future models can be integrated without reimplementing their scientific logic inside platform workflow code.

Platform responsibilities

Bremen Platform owns product and infrastructure concerns:

- authentication and authorization
- source and container registration
- storage access and source resolution
- job creation and lifecycle
- model routing and model selection
- timeouts, retries, and execution orchestration
- audit events and operational diagnostics
- persistence of model results
- public API endpoints
- report envelopes and links
- security, sanitization, and redaction
- frontend integration contracts

The platform may determine which model runtime should execute.

The platform must not reproduce the scientific implementation of that model.

Model Runtime responsibilities

A model runtime owns all model-specific scientific inference semantics:

- model-specific input requirements
- scientific input validation
- interpretation of measurements and sides
- model-specific preprocessing
- q-grid handling and interpolation where applicable
- smoothing and normalization where applicable
- measurement aggregation
- replicate statistics
- feature engineering
- imputation and scaling
- estimator execution
- model-owned thresholds
- scientific postprocessing
- model-specific safe technical diagnostics
- model version and inference provenance

A model runtime must be able to reproduce the inference behavior used to validate or train the corresponding model release.

Semantic runtime interface

Model Runtime Contract v1 defines three semantic operations:

requirements()

Describes the input contract required by the model.

Examples include:

- required measurement counts
- required sides
- whether target_side is required
- required measurement metadata
- supported schema or preprocessing versions
- model identity and version information

validate(model_input)

Validates model-specific compatibility before scientific inference.

Examples:

- Bremen v0.1 requires exactly 3 LEFT and 3 RIGHT measurements
- Aramina requires explicit target_side
- a model may reject an unsupported preprocessing or source contract

Platform-level concerns such as authentication, source existence, or job lookup are not model validation responsibilities.

predict(model_input)

Executes the complete model-specific scientific inference pipeline and returns a structured model result.

The result should contain model-owned prediction information, model identity, safe model diagnostics, and technical provenance required by the platform.

The runtime must not own HTTP routing, authentication, public report URLs, job persistence, or frontend behavior.

Model release definition

A deployable model release is not only estimator weights.

A complete model release must contain or reference all behavior required to reproduce validated inference:

- input contract
- scientific preprocessing
- measurement aggregation semantics
- feature construction
- estimator
- model-owned postprocessing and threshold
- dependency/environment contract
- version and provenance information
- golden inference tests or equivalent reproducibility evidence

Delivering only a joblib, coefficient vector, or estimator and expecting Bremen Platform engineers to reconstruct feature generation is not a valid model delivery contract.

WorkflowProvider boundary

WorkflowProvider is a platform adapter and orchestration layer.

It may:

- receive canonical platform input
- resolve the configured model runtime
- invoke requirements, validation, and prediction
- translate safe runtime failures into existing workflow/job semantics
- return structured workflow results to the platform

It must not:

- choose scientific measurements by incidental list position
- implement scientific smoothing or normalization
- implement model-specific aggregation
- implement model-specific feature formulas
- reproduce scaler or estimator mathematics belonging to a model
- independently decide scientific thresholds

Reference implementation: Bremen

BremenRuntime introduced by PR0152 is the first reference implementation of this boundary.

Its scientific runtime owns:

- exact 3 LEFT + 3 RIGHT validation
- authoritative preprocessing
- common q-grid behavior
- side means and replicate standard deviations
- the frozen 15-feature contract
- imputation and scaling
- portable logistic-regression inference
- model threshold behavior

workflow_bremen.py acts as the orchestration adapter.

Reference compatibility target: Aramina

Aramina is the second compatibility target for Model Runtime Contract v1.

Its existing scientific behavior must not be rewritten simply to make Bremen and Aramina implementations structurally identical.

The common contract sits above the model-specific science.

An adapter may be introduced where necessary to expose Aramina through the same semantic runtime operations while preserving existing model behavior.

Failure ownership

Platform failures include concerns such as:

- authorization failure
- source not found
- job not found
- model not found
- storage or routing failure

Model-runtime failures include concerns such as:

- model input invalid
- model input unsupported
- model configuration required
- model preprocessing failure
- model inference failure

This contract defines ownership categories.

It does not require immediate renaming of existing public API error codes.

Backward-compatible adapters should preserve established external contracts.

Security boundary

Model runtimes may return safe technical diagnostics.

They must not expose:

- storage credentials
- tokens
- environment variables
- private filesystem paths
- S3 source keys unless explicitly part of an approved public contract
- raw stack traces
- arbitrary internal artifact paths

The platform remains responsible for final public-response sanitization.

Versioning and reproducibility

A model runtime version must be traceable to the corresponding model release and scientific inference contract.

Scientific changes require a new model/runtime release or other explicit versioned contract change.

Changing scientific preprocessing silently inside the platform while retaining the same model identity is prohibited.

Framework independence

Model Runtime Contract v1 is intentionally independent of MLflow, BentoML, KServe, or another serving framework.

Those tools may later implement packaging, registry, dependency capture, deployment, or serving around this boundary.

The ownership boundary exists regardless of framework choice.

Migration sequence

PR0152 established the first dedicated Bremen scientific runtime.

PR0153/PR0153B formalized and integrated Model Runtime Contract v1 across the platform without changing model science (see implementation notes below).

A later PR (PR0154) may move BremenRuntime into an inference-complete model package outside the platform-owned scientific source tree.

MLflow or an equivalent framework may then be evaluated as a packaging and registry mechanism.

Non-goals for Contract v1

- no model retraining
- no new Bremen scientific formulas
- no Aramina scientific rewrite
- no report redesign
- no frontend redesign
- no requirement to adopt MLflow
- no requirement to deploy model runtimes as independent network services
- no requirement that all model runtimes use identical internal implementations

Acceptance principle

A future model integration is correct only when Bremen Platform can invoke the model without independently reconstructing the scientific logic required to produce that model prediction.

PR0153B implementation notes

Concrete Python shape (as permitted by this document: the ADR defines semantic responsibilities, not a mandatory implementation form):

- The contract is implemented as a structural typing.Protocol, bremen.model_runtime.ModelRuntime (repo precedent: EventSink, RecordResolver). No ABC, no base class, no shared fake behavior is required; implementations satisfy it structurally.
- The three semantic operations map to model_requirements(), validate_model_input(input), and predict_model(input) and return the structured types ModelRequirements, ModelValidation, and RuntimePrediction. The method names carry a model_ prefix to stay unambiguous alongside the workflow-level lifecycle methods already owned by WorkflowProvider (readiness, validate_compatibility, build_features, run_inference, execute); the semantic responsibilities are unchanged.
- Runtime input is the ModelInput carrier (canonical measurements/case plus model-declared request parameters). It uses the existing canonical data model; no canonical model redesign was performed.
- Internal error ownership categories are implemented as ModelRuntimeError plus ModelInputInvalidError, ModelInputUnsupportedError, ModelConfigurationRequiredError, ModelPreprocessingFailedError, and ModelInferenceFailedError. Public error codes were not renamed; adapters preserve established envelopes (Bremen safe reason constants and the full ARAMINA_* code/stage/diagnostic taxonomy propagate unchanged through AraminaRuntime).
- Dependency direction is enforced by tests: bremen/model_runtime.py imports nothing from bremen.api, the Bremen runtime, the Aramina pipeline, or any model-specific scientific module.
- Bremen: BremenRuntime implements the contract directly (no wrapper layer); predict_model delegates to the untouched PR0152 run() sequence. workflow_bremen.py remains a thin adapter: it invokes exactly one predict_model call per execution and translates contract categories into the PR0152 error envelopes byte-for-byte.
- Aramina: AraminaRuntime (in api/workflow_aramina.py, the authoritative Aramina module) is a contract adapter composing the existing pipeline functions. No Aramina scientific logic was duplicated or rewritten; target_side semantics, source resolution behavior, preprocessing release selection and failure classification are externally identical.
- Model Requirements API: where a runtime is reachable, model-specific request fields are derived from the runtime and the response gains an additive container_requirements.model_runtime block (contract_version, input_requirements). With no reachable runtime (display-only or scaffold rows) the response is unchanged. No endpoint paths, fields or types were altered.

Known remaining platform coupling for PR0154:

- ModelInput.container_path: Aramina artifact preprocessing still consumes a platform-staged filesystem path. An inference-complete model package should accept a container abstraction (bytes/source-of-record ref) owned by the platform, removing paths from the runtime input.
- ModelInput.patient_id: the Aramina pipeline still performs patient identity binding internally (via _validate_aramina_source called inside the existing pipeline). This is platform-identity logic living behind the runtime boundary and should move fully to the platform.
- bremen_features.build_bremen_features lazily imports validate_canonical_measurement from bremen.api.xrd_normalization (flagged in the PR0152 review). Decoupling belongs to PR0154 packaging work.
- Bremen model identity constants in bremen_runtime.py mirror the frozen release evidence; PR0154 should source them from the model package manifest itself.

PR0154 resolution (Bremen v0.1 inference-complete package)

PR0154 moved the complete Bremen v0.1 scientific runtime behind a model-package boundary at bremen.model_packages.bremen_v01 (release manifest + feature science + portable predictor + runtime entry point implementing this contract). See docs/bremen_v01_inference_package.md.

- Resolved — the lazy xrd_normalization import was lifted out of the science module: the package feature module contains no platform import; structural canonical-measurement validation now happens at the package runtime boundary (model_packages.bremen_v01.runtime) with the identical fixed safe reason. Numerical behavior unchanged.
- Resolved — Bremen model identity now has one authoritative source: model_packages.bremen_v01.manifest. The duplicate constants in the former top-level bremen_runtime.py are gone; the old bremen_features.py / bremen_runtime.py / inference.py paths are zero-logic re-export shims (documented, deprecated).
- Decision vocabulary stays platform-owned: api.decision_contract remains the single authority for decision codes and is consumed by the package runtime exactly as before; the numerical threshold comparison remains inside the package predictor.
- Remaining for PR0155 — the two Aramina coupling points (ModelInput.container_path and ModelInput.patient_id / _validate_aramina_source) are Aramina-owned and out of PR0154 scope (Bremen only). They should be lifted to the platform when Aramina is packaged, or when a container/bytes abstraction replaces staged paths.
- Remaining for PR0155 — packaging metadata capture (dependencies declared by the package manifest today, model-release provenance, optional migration of the portable dict into a self-contained release directory) and any evaluation of an external packaging/registry mechanism. PR0154 does not introduce MLflow/BentoML/KServe or relocate artifacts.
