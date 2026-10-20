# IR-05: Subprocess runtime proxy and supervision

Status: DRAFT PLAN; not reviewed, not implemented. Assign implementation/review owners and repository PR number at kickoff.

## Entry condition
Requires verified installer and protocol. New execution stays opt-in/disabled by default.

## Work
Implement runtime proxy for requirements/validate/predict and event translation. Keep platform source authorization/binding, worker scientific validation, report projection and public errors. Bound scientific concurrency; enforce deadlines, process-group termination and cleanup. Workers load artifacts; new path must not deserialize them in parent discovery.

## Expected change areas
Paths below are relative to `src/bremen` unless root-level. These are investigation boundaries, not permission to redesign adjacent systems.

platform/runtime/registry.py and executor.py; platform/jobs/service.py; discovery conditional loading; new supervisor/proxy modules; protocol and lifecycle tests.

## Acceptance and evidence
All five pass local end-to-end proxy parity. Crash, timeout, malformed output, wrong identity, capacity pressure and child-process cleanup tests pass. Legacy defaults and API/report contracts remain unchanged.

Record exact commands, environment/image/release hashes, fixture references, outputs and reviewer/date. Run repository-required checks for changed code; do not report historical results as newly passed. No fabricated review records.

## Rollback
Select legacy route explicitly; no automatic fallback on individual failed predictions.

## Exclusions
No ECS/IaC migration, new model mathematics, feature unification, threshold changes, retraining, mandatory MLflow serving or unrelated queue redesign. See root ROADMAP and ADR 0019 for authority.
