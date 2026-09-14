# Model Runtime Contract v1

Status: Proposed platform contract

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

PR0153 will formalize and integrate Model Runtime Contract v1 across the platform without changing model science.

A later PR may move BremenRuntime into an inference-complete model package outside the platform-owned scientific source tree.

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
