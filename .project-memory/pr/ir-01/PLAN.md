# IR-01: Inventory, baseline and feasibility

Status: DRAFT PLAN; not reviewed, not implemented. Assign implementation/review owners and repository PR number at kickoff.

## Entry condition
No runtime changes. Resolve all five deployed identities and freeze their verified behavior.

## Work
Read active catalog/manifests and deployed image/config through authorized access. Complete every inventory field, fixture matrix and App Runner resource budget. Confirm App Runner/OpenResty topology and existing async polling behavior.

## Expected change areas
Paths below are relative to `src/bremen` unless root-level. These are investigation boundaries, not permission to redesign adjacent systems.

Discovery/manifests; model runtime paths; Dockerfile; deployment configuration; inventory and evidence documents.

## Acceptance and evidence
All five identities/artifact hashes resolved; baseline success/failure outputs reproducible; preprocessing mappings explicit; resource/cost limits reviewed. Missing access or unresolved identities block the next gate.

Record exact commands, environment/image/release hashes, fixture references, outputs and reviewer/date. Run repository-required checks for changed code; do not report historical results as newly passed. No fabricated review records.

## Rollback
Documentation/evidence only; no behavior rollback required.

## Exclusions
No ECS/IaC migration, new model mathematics, feature unification, threshold changes, retraining, mandatory MLflow serving or unrelated queue redesign. See root ROADMAP and ADR 0019 for authority.
