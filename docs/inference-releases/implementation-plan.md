# Eight-PR implementation plan

Status: planned; none executed by this documentation bundle. These are eight implementation PRs after the documentation adoption PR (amended 2026-10-23 to insert IR-07, External XRD feature-library integration, before the former IR-07 cleanup PR, now renumbered IR-08). Logical IR IDs are stable; actual repository PR numbers are assigned later. Every implementation PR must include its own approved PLAN, independent reviews required by project_contract.yml, evidence and rollback notes. This document is not an approval artifact.

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

**Work:** Cut catalog entries carrying `runtime_release` over to the authoritative release path: manifest-only discovery, lazy `ReleaseCache.install()`, offline wheelhouse/venv installation, supervised `bremen.worker.v1` execution, and existing result projection. Preserve legacy discovery/runtime only for entries without `runtime_release`; verify all five release-backed routes locally before a separately authorized operational rollout.

**Gate:** Each of five executes through the release-backed route without the candidate allowlist, with no legacy artifact load/import in the parent, no automatic fallback, preserved public contracts, and local parity evidence. App Runner parity, resource/cost measurements, activation and rollback remain operational rollout work and are not claimed by this implementation PR.

**Rollback:** Restore the previous compatible catalog configuration and image; do not retry an individual failed request through legacy inference.

[Detailed PR brief](../../.project-memory/pr/ir-06/PLAN.md).

## IR-07: External XRD feature-library integration

**Entry:** Requires IR-06 cutover accepted. Must happen before legacy cleanup (IR-08).

**Work:** Extract all 15 Bremen XRD feature functions (`weightedrms1`, `sigma_l1`, `sigma_r1`, `mahalanobis1`, `weightedrms2`, `sigma_l2`, `sigma_r2`, `mahalanobis2`, `peak14_intensity`, `mean_peak_value_raw`, `wasserstein_distance_muLR`, `cosine_distance_full_q2`, `wasserstein_distance_full_q2`, `meanrms1`, `meanrms2`, in this exact frozen order) into a standalone, independently versioned Python package. Each Model Release binds a pinned feature-library wheel (filename, version and SHA-256 release-bound in the manifest) and installs it into its own release-owned virtual environment; the feature library is never globally installed into the Bremen/App Runner runtime, and different releases may pin different wheel versions or the same SHA. The ML plugin consumes the feature-library package; the Bremen Harness does not import feature/scientific implementation. See [Feature library architecture](architecture-and-contract.md#feature-library-architecture-to-implement-in-ir-07) for the dependency direction, ownership split and preserved scientific contracts. Do not change scientific definitions in this PR.

**Gate:** All 15 feature functions live in the standalone package; Harness has no feature/scientific import; ML plugin consumes the package; every Model Release manifest carries a pinned, release-bound feature-library wheel (filename/version/SHA-256) installed into that release's own venv; B1/B2/B3 exact feature names/order remain frozen; Aramina consumes only its required frozen subset/contract (not forced onto all 15 Bremen features); Bremen v0.1 and v0.2 scientific semantics remain distinct with no silent unification of ROI/normalization/pairing behavior; all five model outputs retain existing parity; adding a future conforming model does not require a Bremen rebuild.

**Rollback:** Releases keep their previously installed feature-library wheel version; no shared/mutable runtime installation to roll back.

[Detailed PR brief](../../.project-memory/pr/ir-07/PLAN.md).

## IR-08: Legacy inference cleanup after all-five cutover

**Entry:** Requires IR-07 accepted (feature library externalized and release-bound) in addition to all five activated and accepted plus rollback rehearsal and agreed observation window.

**Work:** Audit all consumers, remove migrated embedded inference dependencies, feature/scientific code and obsolete interpreter/model variables now that each release owns its ML plugin and feature-library wheel, slim runtime image where safe, retain training requirements and independent tools. Remove legacy artifact loading/discovery when no longer consumed. Update operations and active memory with final release mapping and measured limits.

**Gate:** All five models use release-owned ML plugin and release-owned feature library. Fresh image passes all-five parity and service contract checks. Consumer audit shows no broken training/CLI/source/auth paths. Rollback image, manifests, config and artifacts retained and restorable. No ECS resources introduced.

**Rollback:** Redeploy retained previous image and its catalog/config; pointer-only rollback is not sufficient after legacy code removal.

[Detailed PR brief](../../.project-memory/pr/ir-08/PLAN.md).
