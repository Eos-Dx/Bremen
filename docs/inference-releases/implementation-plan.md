# Seven-PR implementation plan

Status: planned; none executed by this documentation bundle. These are seven implementation PRs after the documentation adoption PR. Logical IR IDs are stable; actual repository PR numbers are assigned later. Every implementation PR must include its own approved PLAN, independent reviews required by project_contract.yml, evidence and rollback notes. This document is not an approval artifact.

Scope rule: preserve the verified scientific behavior of each of five exact variants. If access, identity, resource feasibility or parity is unresolved, mark the gate blocked rather than guessing. Do not mark a family complete on behalf of all its variants.

## IR-01: Inventory, baseline and feasibility

**Entry:** No runtime changes. Resolve all five deployed identities and freeze their verified behavior.

**Work:** Read active catalog/manifests and deployed image/config through authorized access. Complete every inventory field, fixture matrix and App Runner resource budget. Confirm App Runner/OpenResty topology and existing async polling behavior.

**Gate:** All five identities/artifact hashes resolved; baseline success/failure outputs reproducible; preprocessing mappings explicit; resource/cost limits reviewed. Missing access or unresolved identities block the next gate.

**Rollback:** Documentation/evidence only; no behavior rollback required.

[Detailed PR brief](../../.project-memory/pr/ir-01/PLAN.md).

## IR-02: Release and process contracts

**Entry:** Requires IR-01 accepted inventory. Define contracts before changing runtime execution.

**Work:** Implement versioned release schema (including the `golden_tests` manifest field) and additive catalog reference validation; the file-based Worker protocol v1 (`request.json` + `input.h5` -> `result.json`, diagnostics-only stdout/stderr); exact JSON schemas/codecs for ModelInput, RuntimePrediction, requirements, validation and events; the typed error codes (`INPUT_INVALID`, `QC_FAILED`, `MODEL_NOT_READY`, `INFERENCE_FAILED`, `TIMEOUT`, `RESOURCE_EXHAUSTED`, `PROTOCOL_ERROR`); a neutral import boundary that keeps the Harness free of ML plugin imports; explicit error mapping and size limits.

**Gate:** Legacy manifests and result contract tests pass. Invalid identity/hash/path/protocol payloads fail closed. Round-trip actual representative inputs/results without scientific changes. Review every current field mapping.

**Rollback:** Leave existing runtime selection unchanged; revert additive contracts if needed.

[Detailed PR brief](../../.project-memory/pr/ir-02/PLAN.md).

## IR-03: Standalone inference builds for five variants

**Entry:** Requires stable contracts and frozen baselines. No production activation.

**Work:** Extract complete scientific paths into standalone ML plugin wheels; preserve per-artifact compatibility classes and optional auxiliary environments. Pin observed dependency closures; replace VCS-only provenance guard correctly. Build five immutable descriptors with artifacts/configs, golden tests and offline wheelhouses in CI; avoid full application dependency. Build and publish each Model Release through a release-specific CI/CD pipeline kept separate from the Bremen application's own CI/CD (documentation-level separation in this block; no workflow files are added or changed here).

**Gate:** Each of five runs in a clean environment without application checkout/platform imports or network dependency resolution. Per-stage and public-result parity passes for approved fixtures. Wheel/manifest hashes and provenance reproducible and captured.

**Rollback:** Old image and source runtime remain authoritative; discard unactivated candidates.

[Detailed PR brief](../../.project-memory/pr/ir-03/PLAN.md).

## IR-04: S3 release manager and verified cache

**Entry:** Requires tested release builds. Installation is separate from routing activation.

**Work:** Implement trusted catalog reference resolution, immutable S3 fetch, checksums, ABI checks, offline installation, per-digest locks, READY markers, resource admission and inactive-only eviction. Publish candidate release objects in an authorized test prefix; do not change active catalog pointers.

**Gate:** Corruption/missing object/unsupported ABI/interrupted install/concurrent install/disk pressure tests pass. Cold and warm installs fit budget. Existing immediate-child discovery and duplicate model-ID protections remain intact.

**Rollback:** Disable new loader usage; existing legacy route continues. Remove only unreferenced test/cache objects under approved retention policy.

[Detailed PR brief](../../.project-memory/pr/ir-04/PLAN.md).

## IR-05: Subprocess runtime proxy and supervision

**Entry:** Requires verified installer and protocol. New execution stays opt-in/disabled by default.

**Work:** Implement the Harness's runtime proxy (Model Runner + supervisor) for requirements/validate/predict over the file-based protocol, and event translation from Worker diagnostics. Keep platform source authorization/binding, worker scientific validation, report projection and public errors. Bound scientific concurrency; enforce deadlines, process-group termination and cleanup. Workers load artifacts and plugin code; the Harness process must not import or deserialize plugin/artifact objects in parent discovery.

**Gate:** All five pass local end-to-end proxy parity. Crash, timeout, malformed output, wrong identity, capacity pressure and child-process cleanup tests pass. Legacy defaults and API/report contracts remain unchanged.

**Rollback:** Select legacy route explicitly; no automatic fallback on individual failed predictions.

[Detailed PR brief](../../.project-memory/pr/ir-05/PLAN.md).

## IR-06: App Runner parity and per-model activation

**Entry:** Requires local parity and resource gates. Operator authorization required for deployment/activation.

**Work:** Deploy candidate-capable image in authorized environment, run sequential paired comparisons with legacy authoritative, verify cold/warm/restart/failure behavior and diagnostics, then carry each release through VERIFIED → READY → ACTIVE, activating exact model identities one at a time after review.

**Gate:** Each of five has App Runner parity evidence, resource/cost measurements, reviewed activation and rollback record. No duplicate reports. Existing job/polling behavior documented and tested under actual service topology.

**Rollback:** Restore pinned old catalog configuration and compatible image as needed; retain artifacts and old config. Do not mutate active workers.

[Detailed PR brief](../../.project-memory/pr/ir-06/PLAN.md).

## IR-07: Cleanup after all-five cutover

**Entry:** Requires all five activated and accepted plus rollback rehearsal and agreed observation window.

**Work:** Audit all consumers, remove migrated embedded inference dependencies and obsolete interpreter/model variables, slim runtime image where safe, retain training requirements and independent tools. Update operations and active memory with final release mapping and measured limits.

**Gate:** Fresh image passes all-five parity and service contract checks. Consumer audit shows no broken training/CLI/source/auth paths. Rollback image, manifests, config and artifacts retained and restorable. No ECS resources introduced.

**Rollback:** Redeploy retained previous image and its catalog/config; pointer-only rollback is not sufficient after legacy code removal.

[Detailed PR brief](../../.project-memory/pr/ir-07/PLAN.md).
