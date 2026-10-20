# IR-07: Cleanup after all-five cutover

Status: DRAFT PLAN; not reviewed, not implemented. Assign implementation/review owners and repository PR number at kickoff.

## Entry condition
Requires all five activated and accepted plus rollback rehearsal and agreed observation window.

## Work
Audit all consumers, remove migrated embedded inference dependencies and obsolete interpreter/model variables, slim runtime image where safe, retain training requirements and independent tools. Update operations and active memory with final release mapping and measured limits.

## Expected change areas
Paths below are relative to `src/bremen` unless root-level. These are investigation boundaries, not permission to redesign adjacent systems.

Dockerfile; pyproject/runtime dependencies; config; legacy branches; CI; docs and project memory. Remove only paths proven unused by nonmigrated tools/models.

## Acceptance and evidence
Fresh image passes all-five parity and service contract checks. Consumer audit shows no broken training/CLI/source/auth paths. Rollback image, manifests, config and artifacts retained and restorable. No ECS resources introduced.

Record exact commands, environment/image/release hashes, fixture references, outputs and reviewer/date. Run repository-required checks for changed code; do not report historical results as newly passed. No fabricated review records.

## Rollback
Redeploy retained previous image and its catalog/config; pointer-only rollback is not sufficient after legacy code removal.

## Exclusions
No ECS/IaC migration, new model mathematics, feature unification, threshold changes, retraining, mandatory MLflow serving or unrelated queue redesign. See root ROADMAP and ADR 0019 for authority.
