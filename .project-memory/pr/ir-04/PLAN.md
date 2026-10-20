# IR-04: S3 release manager and verified cache

Status: DRAFT PLAN; not reviewed, not implemented. Assign implementation/review owners and repository PR number at kickoff.

## Entry condition
Requires tested release builds. Installation is separate from routing activation.

## Work
Implement trusted catalog reference resolution, immutable S3 fetch, checksums, ABI checks, offline installation, per-digest locks, READY markers, resource admission and inactive-only eviction. Publish candidate release objects in an authorized test prefix; do not change active catalog pointers.

## Expected change areas
Paths below are relative to `src/bremen` unless root-level. These are investigation boundaries, not permission to redesign adjacent systems.

platform release management modules; discovery extension; S3 client boundary; cache configuration and tests.

## Acceptance and evidence
Corruption/missing object/unsupported ABI/interrupted install/concurrent install/disk pressure tests pass. Cold and warm installs fit budget. Existing immediate-child discovery and duplicate model-ID protections remain intact.

Record exact commands, environment/image/release hashes, fixture references, outputs and reviewer/date. Run repository-required checks for changed code; do not report historical results as newly passed. No fabricated review records.

## Rollback
Disable new loader usage; existing legacy route continues. Remove only unreferenced test/cache objects under approved retention policy.

## Exclusions
No ECS/IaC migration, new model mathematics, feature unification, threshold changes, retraining, mandatory MLflow serving or unrelated queue redesign. See root ROADMAP and ADR 0019 for authority.
