# ADR-0009: Config Governance and Audit State

**Status**: Proposed

## Context

- Config is separate from model. Model artifacts have their own lifecycle (ADR-0007, ADR-0008).
- Config values (thresholds, QC criteria, feature parameters, preprocessing settings) can affect decision behavior but have different lifecycle requirements than model artifacts.
- Large YAML/TOML configuration files currently exist under `config/preprocessing/` with `extends:` chaining.
- Future API or UI editing of config may be required for operator workflows.
- Audit requires reproducible historical config states so that any prediction can be traced to the config that was active when it was made.
- G-CFG-1 (build in-house vs. adopt existing config-management product) remains OPEN.

## Decision

1. **Config change classes.** Config changes are classified by risk and deployment mode:

   | Class | Examples | Runtime apply without restart? | Requires redeploy? |
   |-------|----------|-------------------------------|-------------------|
   | A — Operational | Log level, health check interval, max concurrent jobs | Yes | No |
   | B — Decision-adjacent | Thresholds, QC criteria versions, feature parameters | Yes, with validation + audit | No |
   | C — Model-binding | Model version, model bucket, feature schema version | No | Yes — restart/redeploy required |
   | D — Structural | API routes, authentication, network configuration | No | Yes |

2. **Config state requirements.** All config states must be:
   - Versioned — every change produces a new version.
   - Timestamped — every version records when it was applied.
   - Auditable — historical versions are queryable.
   - Reproducible — a given version always produces the same config.

3. **Config identity in prediction outputs.** Prediction/audit records eventually need `config_version` or `config_hash` to identify which config was active at decision time. This is tracked as a future `project_contract.yml` amendment.

4. **Future gates.** The following gates remain OPEN:

   | Gate | Question | Recommended default |
   |------|----------|-------------------|
   | G-CFG-1 (existing) | Build in-house vs. adopt existing config-management product | Not decided |
   | G-CFG-2 (new) | Config state history store: DynamoDB vs. other | DynamoDB |
   | G-CFG-3 (new) | Config validation schema: JSON Schema vs. Pydantic vs. custom | Not decided |

## Non-goals

- No config UI or API implementation in this ADR.
- No config state database or history store implementation.
- No runtime config hot-apply implementation.
- No model-binding hot-swap permitted (Class C changes require redeploy).
- No `project_contract.yml` amendment in this ADR (deferred to the config governance implementation PR).

## Consequences

- A future config governance implementation PR (planned as PR 0039) is required to close gates, define the schema, and build the state history store.
- A future `project_contract.yml` amendment is required to add `config_version`/`config_hash` to the prediction output invariant.
- The config editing surface (originally PR 0024) is reclassified under the config governance track.
