# Active roadmap: independent inference releases on App Runner

Rebaseline: 2026-10-20. Status: proposed documentation baseline; implementation gates are NOT completed.

This document becomes the authoritative execution sequence when the documentation PR is merged. Merging it does not authorize production deployment or certify model equivalence. Logical IDs IR-01–IR-08 are not GitHub PR numbers; allocate repository PR numbers when work starts.

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
| IR-06 | Release-runtime cutover and per-model operational rollout | Each of five routes through its immutable release locally; App Runner parity/activation remains separately authorized operational work |
| IR-07 | External XRD feature-library integration | All 15 Bremen XRD feature functions live in a standalone versioned Python wheel, release-bound (not globally installed); Harness does not import feature/scientific implementation; B1/B2/B3 feature names/order frozen; Bremen v0.1/v0.2 and Aramina scientific contracts remain distinct; all five outputs retain existing parity |
| IR-08 | Legacy inference cleanup | All five models use release-owned ML plugin + release-owned feature library; obsolete embedded scientific/feature code and model-specific runtime dependencies/config removed where safe; consumer audit clean; rollback demonstrably available |

Each PR depends on the preceding gate. Stop at failed gates and record evidence; do not silently weaken acceptance criteria. A gate requiring deployment/artifact access stays pending until that evidence exists. Existing project-contract plan-review and precommit-review requirements still apply; this bundle provides no reviewer approvals.

## Contract terminology and final acceptance (2026-10-20 rebaseline)

IR-01 through IR-06 and their order are unchanged by this rebaseline. The architecture is now described using the Harness/Model Runner/common Worker (platform-owned) versus ML plugin (ML-team-owned) terminology in [ADR 0019](docs/adr/0019-independent-inference-releases-app-runner.md) and [architecture-and-contract.md](docs/inference-releases/architecture-and-contract.md); the Worker protocol is file-based (`request.json` + `input.h5` -> `result.json`), not stdin/stdout JSON Lines; and each release carries an explicit PUBLISHED → VERIFIED → READY → ACTIVE lifecycle. Final architectural acceptance for this block: a new conforming Model Release can be published and activated without rebuilding Bremen or changing Harness code. V2 persistent workers and V3 OCI-packaged releases are documented in ADR 0019 as optional future directions, not current implementation tasks.

## Sequence amendment (2026-10-23)

The future sequence after IR-06 is amended: the former IR-07 ("Remove obsolete dependencies/configuration") is renumbered to IR-08 and now follows a new IR-07 ("External XRD feature-library integration"), inserted because feature computation must be separated from Bremen into its own versioned wheel before legacy cleanup proceeds. IR-01 through IR-06 are unchanged by this amendment. See [implementation-plan.md](docs/inference-releases/implementation-plan.md) and [architecture-and-contract.md](docs/inference-releases/architecture-and-contract.md) for the full IR-07/IR-08 definitions and the feature-library architecture.

## Non-goals for all eight PRs

No ECS migration, ECS Terraform/CloudFormation, GPU fleet, queue redesign, new model mathematics, feature standardization, retraining, threshold changes, or mandatory MLflow serving adoption. Existing experiment tracking is preserved. Framework-neutral model contracts and scientific invariants remain binding.

## Supersession

The previous root roadmap is preserved verbatim in [history](docs/roadmap-history/ROADMAP-before-2026-10-20.md). Old ECS scheduling, MLflow-serving sequencing, and in-process/startup-only loading prescriptions do not govern this block. Completed implementation history and numerical contracts are not invalidated. Earlier ADRs remain binding except the execution/deployment boundaries explicitly superseded by ADR 0019. Historical PR numbers must not be reused as new task IDs.

Do not implement an unresolved design by guessing. Record an assumption, its owner, the verification needed, and the gate it blocks. Technical owners are assigned at PR opening; scientific baseline acceptance belongs to the model owner/reviewer, platform acceptance to the service owner, and production activation to the authorized operator.

## Preserved dependency gate

This completed historical gate remains binding. The inference-release
roadmap does not reopen it or change the container dependency pin.

| Gate | Status | Resolution |
|---|---|---|
| G-DEP-1 | CLOSED | feat/v0_3 merged into main; immutable v0.3.0 tag at commit 6af9ab4; Bremen pins v0.3.0; VERSION_REGISTRY maps 0_3 to container.v0_3. |
