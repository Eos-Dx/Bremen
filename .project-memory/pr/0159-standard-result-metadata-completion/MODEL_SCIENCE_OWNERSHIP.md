# PR0159 — Model science ownership boundary

PR0159 fixes the ownership boundary for Standard Result metadata and model execution.

## Architectural rule

Bremen Platform is an orchestration and integration layer. It must not reproduce, reinterpret, or partially reimplement scientific logic that belongs to a model package.

The stable execution boundary is:

```text
registered raw source / H5
        |
        v
Bremen Platform
- authentication and authorization
- source registration / source_id resolution
- raw source materialization
- model_id / workflow_id routing
- job lifecycle
- report lifecycle
        |
        v
Model package / ModelRuntime
- model-specific input validation
- supported legacy-container compatibility
- H5 parsing
- artifact-owned preprocessing
- physical / scientific corrections
- profile construction
- feature engineering
- model-specific eligibility gates
- inference
- extraction of model-relevant source metadata
- model metadata and model performance metadata
        |
        v
normalized ModelRuntime result
        |
        v
Standard Result mapper
- canonical field translation only
```

## Platform responsibilities

Generic platform code may own transport and execution concerns:

- authenticate requests;
- resolve `source_id` / registered container identity;
- access or materialize the raw source;
- select the requested model package;
- invoke `ModelRuntime`;
- enforce generic execution limits and timeouts;
- manage jobs, events and reports;
- translate an already-normalized model result into public API contracts.

Generic platform code must not need to understand the scientific meaning of the selected model's input.

## Model package responsibilities

The selected model package owns all logic required to turn its supported raw input into its scientific result.

This includes, when applicable:

- raw H5 structure and model-supported compatibility rules;
- H5 paths and model-specific metadata aliases;
- preprocessing configuration;
- integration;
- geometry handling;
- calibration;
- thickness correction;
- q-range semantics;
- measurement grouping;
- profile aggregation;
- feature construction;
- scientific eligibility gates;
- estimator invocation;
- scientific result semantics;
- extraction of source metadata required by the model/report.

A model package therefore behaves conceptually as:

```text
raw supported input
    -> package-owned scientific processing
    -> structured normalized result
```

The platform must not reproduce these transformations independently.

## Standard Result metadata ownership

Standard Result metadata follows the same boundary.

The intended flow is:

```text
raw H5
    -> model package parsing / preprocessing
    -> package-owned normalized metadata
    -> ModelRuntime result
    -> generic Standard Result mapper
```

The normalized runtime result may expose structures conceptually equivalent to:

```python
source_metadata = {
    "patient_age": ...,
    "scan_date_time": ...,
    "operator_id": ...,
    "hardware_version": ...,
    "eoscan_version": ...,
}

model_metadata = {
    "model_method": ...,
}

model_metrics = {
    "sensitivity": ...,
    "specificity": ...,
}
```

The Standard Result mapper consumes canonical values already produced by the package. It must not open H5 files, inspect model-specific paths, translate model-specific aliases, or reconstruct scientific metadata itself.

If the active package does not yet provide an authoritative value, the corresponding Standard Result field remains null. The platform must not guess it.

## Generic-code invariant

Adding a third model must not require modifying generic platform code to add:

- new H5 paths;
- new scientific metadata aliases;
- new preprocessing rules;
- new feature formulas;
- new q ranges;
- new model-specific thresholds;
- new scientific interpretation logic.

A new model should add or update its own package adapter and return the existing normalized runtime contract.

If onboarding a model requires the generic mapper, workflow provider, API layer or runner to learn that model's scientific internals, the ownership boundary has been violated.

## Requirements ownership

`/models/{model_id}/requirements` is a platform API surface, but the requirements themselves are model-owned.

The platform may expose, cache and safely validate model-declared requirements. It must not independently invent the model's scientific requirements.

Preflight validation must likewise delegate model-specific validation semantics to the selected package or package-declared contract.

## PR0159 guardrail

PR0159 must not introduce a generic API-owned H5 metadata parser as the source of Standard Result metadata.

In particular, any implementation such as:

```text
src/bremen/api/h5_source_metadata.py
```

that opens H5 and knows Bremen- or Aramina-specific paths would create the wrong ownership boundary.

Metadata needed by Standard Result must instead enter through the model/runtime result.

Package-owned metadata that is not yet implemented may remain null until the relevant package supplies it.

## Follow-up implementation

The full removal of existing platform-owned scientific preprocessing is intentionally separated from PR0159.

Follow-up:

```text
0160-model-package-owned-scientific-preprocessing
```

PR0160 will move model-specific preprocessing behind the model-package / ModelRuntime boundary and reduce the generic platform path to source delivery and orchestration.

See also:

`docs/model_package_scientific_ownership.md`
