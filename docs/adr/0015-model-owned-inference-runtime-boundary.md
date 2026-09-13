# ADR-0015: Model-Owned Inference Runtime Boundary

**Status**: Proposed  
**Date**: 2026-09-12

**Related spike**: [Architecture Spike: Six-Measurement Bremen Inference and Model-Owned Runtime](../architecture_spike_six_measurement_and_model_owned_inference.md)  
**Related review**: [Architecture Review Reconciliation: Model Boundary and Technical Debt](../architecture_review_model_boundary_and_technical_debt.md)

## Context

Bremen Platform currently contains model-specific scientific/inference logic in addition to platform orchestration. Examples include measurement selection, feature construction, scaling/imputation, estimator invocation, and workflow-specific preprocessing logic.

This creates a training-serving skew risk: changing platform code can change the effective model behavior while the published model artifact remains unchanged.

The repository already separates training and runtime lifecycles (ADR-0007 / ADR-0008), and prior reconciliation work identifies duplicated feature computation as a risk. The remaining boundary should be strengthened so model-specific inference behavior is versioned with the model release.

An architecture review independently concluded that a framework rewrite does not solve this ownership problem. The higher-leverage decision is a firm boundary rule. Registry/versioning modernization may be pursued separately.

## Proposed decision

Bremen Platform SHOULD evolve toward a **model-owned, inference-complete runtime contract**.

Bremen Platform owns:

- authentication and public API;
- source/container registration and resolution;
- job lifecycle, idempotency and async orchestration;
- model catalog/selection;
- audit/events/observability;
- storage and public report envelope;
- security/redaction and safe platform errors.

A model release owns:

- model-specific input validation;
- measurement aggregation/selection;
- q-grid/model preprocessing;
- feature engineering;
- estimator and model-specific threshold/postprocessing;
- model dependencies;
- model signature/schema;
- training/preprocessing provenance;
- golden reference inference fixtures.

This corresponds to the architecture review's preferred **boundary-rule / Option C** direction.

The preferred first implementation is an inference-complete package loaded by Bremen Platform. MLflow PyFunc is a suitable candidate because the project already uses MLflow for lineage, but the architectural requirement is framework-neutral.

MLflow Model Registry or an equivalent registry MAY be adopted independently to improve catalog/versioning/signatures/environment capture. It is not a prerequisite for enforcing the boundary.

Separate serving frameworks/services such as BentoML or KServe MAY be introduced later when independent scaling, dependency isolation, or deployment ownership requires them. They are not required for the first migration step.

## Migration principle

This is an incremental migration, not a greenfield rewrite.

Existing Bremen platform contracts and infrastructure should be retained while model-specific inference logic is moved behind a stable Model Runtime Contract v1 one model at a time.

## Required gates before acceptance

- Model Runtime Contract v1 proposal and examples.
- Bremen six-measurement golden parity proof.
- Security review for executable model packages/serialization.
- Dependency isolation strategy.
- Model release/version/checksum provenance contract.
- Shadow/parity cutover plan preserving external API compatibility.
- Ownership agreement with ML/model teams for scientific inference code and golden fixtures.

## Non-goals

This proposed ADR does not:

- mandate Kubernetes;
- mandate MLflow, KServe, or BentoML;
- require a Bremen Platform rewrite;
- authorize immediate removal of existing runtime paths;
- change public API/report contracts;
- merge Bremen and Aramina scientific logic;
- transfer platform security/operations responsibilities to ML engineers;
- treat historical/snapshot-specific Aramina findings as current defects without provenance.

## Consequences if accepted

- ML/model engineers become explicit owners of scientific inference semantics and reproducibility.
- Bremen Platform becomes thinner at the model boundary and less likely to duplicate training feature code.
- Model releases become larger/more complete than a standalone estimator file.
- Model acceptance must include golden training-serving parity, not only artifact checksum/schema checks.
- Operational complexity may increase for dependency isolation, but scientific ownership and reproducibility improve.
- Registry/framework adoption can be evaluated on its own merits instead of being used as a proxy for the boundary decision.
