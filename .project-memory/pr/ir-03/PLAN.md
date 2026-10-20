# IR-03: Standalone inference builds for five variants

Status: DRAFT PLAN; not reviewed, not implemented. Assign implementation/review owners and repository PR number at kickoff.

## Entry condition
Requires stable contracts and frozen baselines. No production activation.

## Work
Extract complete scientific paths into standalone wheels; preserve per-artifact compatibility classes and optional auxiliary environments. Pin observed dependency closures; replace VCS-only provenance guard correctly. Build five immutable descriptors with artifacts/configs and offline wheelhouses in CI; avoid full application dependency.

## Expected change areas
Paths below are relative to `src/bremen` unless root-level. These are investigation boundaries, not permission to redesign adjacent systems.

model_packages/bremen_v01; model_packages/aramina_v0213; model_packages_bridge; required legacy scientific adapters; pyproject/build configuration; new release build workflow.

## Acceptance and evidence
Each of five runs in a clean environment without application checkout/platform imports or network dependency resolution. Per-stage and public-result parity passes for approved fixtures. Wheel/manifest hashes and provenance reproducible and captured.

Record exact commands, environment/image/release hashes, fixture references, outputs and reviewer/date. Run repository-required checks for changed code; do not report historical results as newly passed. No fabricated review records.

## Rollback
Old image and source runtime remain authoritative; discard unactivated candidates.

## Exclusions
No ECS/IaC migration, new model mathematics, feature unification, threshold changes, retraining, mandatory MLflow serving or unrelated queue redesign. See root ROADMAP and ADR 0019 for authority.
