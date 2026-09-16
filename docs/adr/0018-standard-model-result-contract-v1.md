# ADR-0018: Standard Model Result Contract v1

Status: Accepted

## Context

Bremen Platform supports multiple scientific models with different native inference outputs.

Bremen and Aramina have different preprocessing pipelines, model artifacts, probability field names, thresholds, and model-specific result fields.

These differences remain owned by their respective model packages.

At the same time, downstream platform consumers require a stable model-independent result contract.

Existing integrations already depend on the current Bremen Platform HTTP/API surface. Internal model architecture changes must not require those consumers to understand Bremen-specific or Aramina-specific runtime details.

Model Runtime Contract v1 established a common callable runtime boundary.

Model Package Standard v1 established common ownership rules for deployable model packages.

A stable mapped-result boundary is therefore required between model inference and downstream platform integrations.

This approach was agreed by Stanislav Lipin, Alexander Kosyaev, and the Bremen Platform product and architecture owner.

## Decision

Bremen Platform adopts Standard Model Result Contract v1.

Every supported model is mapped into one common top-level result envelope.

The common envelope contains report identity, creation timestamp, analysis metadata, patient and scan metadata, operator and device metadata, model identity and version, model method, model performance metadata, applied threshold, canonical risk probability, canonical target-class risk level, and model-specific safe output.

Model-specific fields are placed under `specific_output`.

The common canonical probability field is `risk_probability`.

The Contract v1 canonical target-class vocabulary is `high` and `low`.

Model-native probability names are translated by a dedicated mapping boundary.

## Model ownership

Scientific model behavior remains model-owned.

The model package remains authoritative for preprocessing, measurement interpretation, feature engineering, estimators, probability, threshold, scientific decision semantics, model-specific diagnostics, identity, provenance, and release metadata where applicable.

The Standard Model Result Mapper translates authoritative outputs. It does not implement model science.

## Threshold rule

The applied threshold remains owned by the model package.

The platform mapper must not define, duplicate, or hardcode an independent threshold for Bremen or Aramina.

If canonical `high` or `low` mapping requires probability and threshold comparison, it must reproduce the authoritative runtime decision exactly using model-owned values.

## Model metrics

Sensitivity and specificity are model-release metadata. They are not patient-level calculations.

They must originate from an authoritative model release source and must not be independently hardcoded across API modules.

## Model-specific extension

`specific_output` is the extension point for model-specific downstream fields.

Aramina currently requires values such as `target_side` and `mammography_suspicious_field`.

Bremen currently uses an empty `specific_output` object.

New model-specific fields do not automatically become new common top-level fields.

## Existing API compatibility

This ADR does not authorize replacement of existing Bremen Platform APIs.

Existing integrations are already implemented against current endpoints.

Adoption of Standard Model Result Contract v1 is initially an internal architecture and mapping change behind the existing API surface.

Existing routes remain backward-compatible unless changed in a separately reviewed and explicitly versioned API decision.

This ADR does not change existing endpoint paths, HTTP methods, authentication requirements, request schemas, response schemas, job lifecycle semantics, event semantics, report endpoint semantics, model identifiers, source/container APIs, or existing report fields.

Existing report payload fields including `report.payload.risk_score` and `report.payload.technical_demo_only` must not be moved or removed.

## Architecture

The intended flow is:

Platform and source metadata

plus

Model Package
→ ModelRuntime result

then

Standard Model Result Mapper
→ Standard Model Result v1
→ existing downstream integrations

This separates model-specific science from integration-specific representation.

## Relationship to Model Runtime Contract v1

Model Runtime Contract v1 defines how the platform calls a model runtime. It does not define the downstream result representation.

## Relationship to Model Package Standard v1

Model Package Standard v1 defines what a deployable model package owns.

Standard Model Result Contract v1 defines how completed inference is mapped into a stable consumer-facing semantic result.

These are separate responsibilities.

## Relationship to MLflow

MLflow is not part of this architecture decision.

MLflow may later package, load, distribute, or register conforming model packages.

It must not own Standard Model Result mapping semantics.

## Future technical inference API

A future technical or model-native inference API may expose a more direct model-oriented response for teams that need it.

Such an API must be additive. It must not replace or break existing integration endpoints.

It is deferred until after the common mapped-result contract is implemented.

## Consequences

Positive consequences:

- downstream integrations gain one stable semantic result
- new models do not require consumers to understand model-specific science
- Bremen and Aramina may evolve independently behind the same mapping boundary
- existing API consumers remain protected
- future model packaging remains independent from result mapping
- model-specific extensions have one controlled location

Costs:

- an explicit mapper layer must be maintained
- authoritative release metadata must be clearly sourced
- Bremen and Aramina require frozen mapping fixtures
- schema versioning becomes an explicit architecture responsibility

## Follow-up

The next implementation PR must implement Unified Model Result Mapper v1.

It must create frozen Bremen and Aramina mapping fixtures, map both models into Standard Model Result Contract v1, preserve existing endpoints, preserve scientific behavior, preserve report compatibility, and prove endpoint/schema compatibility against the existing baseline.
