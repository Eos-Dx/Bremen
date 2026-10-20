# IR-02: Release and process contracts

Status: DRAFT PLAN; not reviewed, not implemented. Assign implementation/review owners and repository PR number at kickoff.

## Entry condition
Requires IR-01 accepted inventory. Define contracts before changing runtime execution.

## Work
Implement versioned release schema and additive catalog reference validation; exact JSON schemas/codecs for ModelInput, RuntimePrediction, requirements, validation and events; neutral import boundary; explicit error mapping and size limits.

## Expected change areas
Paths below are relative to `src/bremen` unless root-level. These are investigation boundaries, not permission to redesign adjacent systems.

platform/models/discovery.py; contracts/model_runtime.py; proposed release/worker contract modules and tests. Preserve old catalog validation and API results.

## Acceptance and evidence
Legacy manifests and result contract tests pass. Invalid identity/hash/path/protocol payloads fail closed. Round-trip actual representative inputs/results without scientific changes. Review every current field mapping.

Record exact commands, environment/image/release hashes, fixture references, outputs and reviewer/date. Run repository-required checks for changed code; do not report historical results as newly passed. No fabricated review records.

## Rollback
Leave existing runtime selection unchanged; revert additive contracts if needed.

## Exclusions
No ECS/IaC migration, new model mathematics, feature unification, threshold changes, retraining, mandatory MLflow serving or unrelated queue redesign. See root ROADMAP and ADR 0019 for authority.
