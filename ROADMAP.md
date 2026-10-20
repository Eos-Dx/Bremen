# Active roadmap: independent inference releases on App Runner

Rebaseline: 2026-10-20. Status: proposed documentation baseline; implementation gates are NOT completed.

This document becomes the authoritative execution sequence when the documentation PR is merged. Merging it does not authorize production deployment or certify model equivalence. Logical IDs IR-01–IR-07 are not GitHub PR numbers; allocate repository PR numbers when work starts.

## Objective and scope

Keep the current AWS App Runner service. Extract the full inference chain for two Aramina and three Bremen deployed variants into independently versioned releases, stored in S3, installed from pinned wheels and invoked in separate Python processes. Preserve each variant's verified behavior and the public service contract. S3 stores code and artifacts; computation remains on App Runner.

The user reported five deployed variants. Repository evidence confirms historical IDs for two Aramina variants, but does not establish the exact current three Bremen identities. IR-01 MUST resolve all five from the active catalog and deployment. Two runtime families are not five verified releases.

The latest mention of “OpenResty” is interpreted as referring to the existing App Runner deployment, based on preceding instructions and repository deployment code. This is an explicit assumption, not evidence that OpenResty is absent. IR-01 must confirm the hosting topology; any actual OpenResty layer is retained and documented.

## Required reading

1. [ADR 0019](docs/adr/0019-independent-inference-releases-app-runner.md)
2. [Architecture and execution contract](docs/inference-releases/architecture-and-contract.md)
3. [Five-model inventory](docs/inference-releases/five-model-inventory.md)
4. [Seven-PR implementation plan](docs/inference-releases/implementation-plan.md)
5. [Parity and rollout gates](docs/inference-releases/parity-and-rollout.md)
6. [Operations and configuration](docs/inference-releases/operations.md)
7. [Source audit](docs/inference-releases/source-audit.md)

## Execution sequence

| ID | Deliverable | Completion gate |
|---|---|---|
| IR-01 | Exact five-model inventory, baseline outputs, resource feasibility | Five resolved identities and immutable baselines; App Runner resource budget feasible |
| IR-02 | Release schema, neutral contracts, subprocess protocol | Schema and wire-contract tests; legacy contract unchanged |
| IR-03 | Standalone inference wheels and reproducible release builds | All five run outside the Bremen application with offline dependencies and parity evidence |
| IR-04 | S3 release installation and bounded local cache | Verified, race-safe installation; legacy discovery still works; no activation |
| IR-05 | Supervised subprocess runtime integration | Candidate route disabled by default; lifecycle/error/concurrency tests pass |
| IR-06 | Per-model App Runner verification and controlled activation | Each of five has environment-specific parity and reviewed activation evidence |
| IR-07 | Remove obsolete dependencies/configuration | All five cut over; consumer audit clean; rollback demonstrably available |

Each PR depends on the preceding gate. Stop at failed gates and record evidence; do not silently weaken acceptance criteria. A gate requiring deployment/artifact access stays pending until that evidence exists. Existing project-contract plan-review and precommit-review requirements still apply; this bundle provides no reviewer approvals.

## Non-goals for all seven PRs

No ECS migration, ECS Terraform/CloudFormation, GPU fleet, queue redesign, new model mathematics, feature standardization, retraining, threshold changes, or mandatory MLflow serving adoption. Existing experiment tracking is preserved. Framework-neutral model contracts and scientific invariants remain binding.

## Supersession

The previous root roadmap is preserved verbatim in [history](docs/roadmap-history/ROADMAP-before-2026-10-20.md). Old ECS scheduling, MLflow-serving sequencing, and in-process/startup-only loading prescriptions do not govern this block. Completed implementation history and numerical contracts are not invalidated. Earlier ADRs remain binding except the execution/deployment boundaries explicitly superseded by ADR 0019. Historical PR numbers must not be reused as new task IDs.

Do not implement an unresolved design by guessing. Record an assumption, its owner, the verification needed, and the gate it blocks. Technical owners are assigned at PR opening; scientific baseline acceptance belongs to the model owner/reviewer, platform acceptance to the service owner, and production activation to the authorized operator.
