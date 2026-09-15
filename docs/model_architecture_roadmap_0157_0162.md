# Model Architecture Roadmap 0157–0162

This roadmap follows Model Package Standard v1.

The immediate priority is to stabilize the contract between model inference and downstream platform integrations before moving further into model packaging, standalone distribution, or Registry work.

## 0157 — Standard Model Result Contract v1

Documentation and ADR only.

Goals:

- freeze the model-independent result envelope
- define field semantics
- define Bremen and Aramina mapping semantics
- define timestamp normalization
- define model metrics ownership
- define the `specific_output` extension point
- preserve all existing platform endpoints and contracts

No production mapper implementation in this PR.

## 0158 — Unified Model Result Mapper v1

Implement one mapping boundary for Bremen and Aramina.

Goals:

- frozen Bremen mapping fixture
- frozen Aramina mapping fixture
- map model-native probability into `risk_probability`
- map authoritative decision into `high` or `low`
- map model-owned threshold into `threshold_value`
- add required Bremen metadata fields
- preserve Aramina-specific output
- preserve all existing endpoint paths, methods, auth, schemas, status codes, model IDs, jobs, events, and reports
- preserve `report.payload.risk_score`
- preserve `report.payload.technical_demo_only`

This is an internal mapping implementation behind the existing API surface.

## 0159 — Model Release Boundary Hardening

Harden both model packages for standalone release.

Goals:

- remove or isolate remaining platform-specific package bridges
- address Aramina source-validation seam
- correct non-runtime provenance metadata inconsistencies
- make Bremen and Aramina independently importable as model packages
- keep ModelRuntime and Model Package Standard v1 unchanged
- no scientific changes
- no endpoint changes

## 0160 — Standard Model Package Release / MLflow

Implement one release-packaging mechanism for all Model Package Standard v1 packages.

Goals:

- same packaging approach for Bremen and Aramina
- explicit input/output signatures
- dependency capture
- provenance
- save → fresh load → prediction parity
- isolated subprocess/environment tests
- no scientific logic inside the packaging adapter
- no endpoint changes

MLflow remains a packaging mechanism, not the model architecture.

## 0161 — Technical Model-native Inference API

Add an optional direct technical inference interface for teams that need model-oriented output.

Goals:

- additive API only
- generic model routing
- authenticated access
- direct ModelRuntime/model-package invocation
- safe model-native result envelope
- no replacement of existing downstream integration endpoints
- no breakage of Alexey team integrations

The existing mapped API remains the compatibility contract.

## 0162 — Model Registry and Release Lifecycle Decision

Evaluate whether MLflow Model Registry or the existing catalog should own release lifecycle.

Evaluate model versions, aliases, promotion, rollback, artifact storage, checksum/provenance, environment metadata, deployment lookup, and operational cost.

Registry adoption is a separate decision from Model Package Standard v1 and Standard Model Result Contract v1.
