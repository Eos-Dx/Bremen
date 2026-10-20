# IR-06: App Runner parity and per-model activation

Status: DRAFT PLAN; not reviewed, not implemented. Assign implementation/review owners and repository PR number at kickoff.

## Entry condition
Requires local parity and resource gates. Operator authorization required for deployment/activation.

## Work
Deploy candidate-capable image in authorized environment, run sequential paired comparisons with legacy authoritative, verify cold/warm/restart/failure behavior and diagnostics, then activate exact model identities one at a time after review.

## Expected change areas
Paths below are relative to `src/bremen` unless root-level. These are investigation boundaries, not permission to redesign adjacent systems.

Deployment runbook; catalog references; release evidence matrix; configuration. No scientific algorithm changes.

## Acceptance and evidence
Each of five has App Runner parity evidence, resource/cost measurements, reviewed activation and rollback record. No duplicate reports. Existing job/polling behavior documented and tested under actual service topology.

Record exact commands, environment/image/release hashes, fixture references, outputs and reviewer/date. Run repository-required checks for changed code; do not report historical results as newly passed. No fabricated review records.

## Rollback
Restore pinned old catalog configuration and compatible image as needed; retain artifacts and old config. Do not mutate active workers.

## Exclusions
No ECS/IaC migration, new model mathematics, feature unification, threshold changes, retraining, mandatory MLflow serving or unrelated queue redesign. See root ROADMAP and ADR 0019 for authority.
