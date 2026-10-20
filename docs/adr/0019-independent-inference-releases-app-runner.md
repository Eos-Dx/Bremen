# ADR 0019: independent inference releases on existing App Runner

Date: 2026-10-20. Status: PROPOSED; acceptance requires repository review/merge.

## Context

The application currently packages platform and model code in one distribution. Bremen discovery can deserialize an artifact into the platform process; Aramina uses its own artifact compatibility behavior. Preprocessing already uses separate Python environments in some paths. These partial boundaries do not constitute standalone, immutable inference releases. Five deployed variants are the business scope, pending inventory verification.

## Decision

Retain App Runner. Keep routing, authorization, source access, job/report orchestration and telemetry in the platform, inside a **Harness**. Put each variant's complete scientific inference behavior—artifact loading, compatibility classes, scientific input validation, preprocessing, feature construction, scaling/imputation, prediction, thresholds and scientific result construction—inside its release, owned by the **ML plugin**. Preserve external projection/error contracts through an explicit adapter. The Harness MUST NOT import ML plugin code; it only installs and invokes a release through the supervised Worker boundary defined below.

Deliver an immutable Model Release: a release manifest, model artifacts, an **ML plugin wheel**, an offline dependency wheelhouse (pinned dependencies), preprocessing configuration, provenance and golden tests, through S3. A release may reference shared immutable blobs, but MUST resolve a complete dependency closure. Each model activation pins a release digest. Shared source or wheel code is allowed only where equivalence is established; five variants still require five separately tracked release descriptors and parity gates.

Responsibilities are split explicitly: the platform owns the Harness, the Model Runner, the common Worker process, supervision and the wire protocol. The ML team owns the plugin, preprocessing and scientific inference/postprocessing inside each release. This boundary is architectural, not just organizational — the Harness never links against or imports plugin source.

Use a separate OS Python process, not a Python thread, for scientific execution. A release-specific virtual environment isolates Python dependencies. Initial design is a supervised one-shot invocation per job, bounded per application instance, with verified installations cached locally. Do not introduce persistent worker pools in this block without a separately reviewed amendment; see "Future directions" below for the non-binding V2/V3 options this restriction defers. Auxiliary preprocessing subprocesses may remain inside a release if needed to preserve the existing dependency split; kill and account for the entire process group.

Use a small framework-neutral file-based protocol between Harness and Worker: the Harness writes `request.json` plus the staged `input.h5` for the job, and the Worker writes `result.json` on completion. Do not send pickle objects between platform and worker, and do not use stdout/stdin as the result channel — stdout/stderr carry diagnostics only. The protocol preserves the existing `requirements`/`validate`/`predict` operations and event semantics (`started`, `features`, `result`/`error` terminal state); see [Architecture and normative contracts](../inference-releases/architecture-and-contract.md) for the exact wire format and the typed error codes (`INPUT_INVALID`, `QC_FAILED`, `MODEL_NOT_READY`, `INFERENCE_FAILED`, `TIMEOUT`, `RESOURCE_EXHAUSTED`, `PROTOCOL_ERROR`). Preserve legacy catalog/API identities. Keep the legacy path available until all five variants pass controlled rollout. An activated release failure is reported as failure; do not silently rerun a different model or legacy path.

A release moves through an explicit lifecycle: **PUBLISHED** (immutable blobs and manifest uploaded) → **VERIFIED** (checksums, ABI and installation smoke-checked) → **READY** (installed and locally cache-admitted) → controlled **ACTIVE** (catalog pointer switched by an authorized operator). Publication alone MUST NOT activate a model; each lifecycle transition is a separately reviewed/recorded step.

Final architectural acceptance for this roadmap block: a new, conforming Model Release can be published and activated without rebuilding the Bremen application image or changing Harness code. Onboarding a sixth (or later) model is an operational/catalog action, not a platform code change.

## Alternatives

Threads do not isolate dependency versions or scientific imports. Shipping only joblib does not carry imported custom classes, transformation code, locked dependencies or provenance. ECS may be reconsidered after this block if measured resource constraints demand it. Mandatory MLflow serving would add another migration and is not required for this extraction.

## Future directions (non-binding)

These are documented as optional future directions, not current implementation tasks for IR-01–IR-07, and each would require its own reviewed amendment before adoption:

- **V2 — persistent workers.** Replace the one-shot supervised invocation with a persistent, pooled worker process per release to reduce cold-start/install overhead. Requires a separately reviewed amendment to the one-shot restriction above, plus concurrency, lifecycle and leak-containment evidence.
- **V3 — OCI-packaged releases.** Package a release as an OCI image instead of (or alongside) an installed virtual environment, for stronger dependency/runtime isolation. Requires its own feasibility and resource review against the existing App Runner hosting decision; it is not an ECS migration proposal.

## Relationship to earlier decisions

Preserve ADR 0016 ModelRuntime semantics, ADR 0017 package ownership and ADR 0018 result semantics. Supersede ADR 0013's earlier restricted Aramina subprocess deployment scope with the release-based execution model for the five inventoried variants. Supersede historical startup-only/in-process joblib-loading prescriptions for migrated variants only. Existing trusted-deserialization checks and scientific invariants remain required. No other historical ADR is blanket-revoked.

## Consequences and acceptance

Cold starts and first-use installation may be slower. Virtual environments share the host Python ABI and OS libraries; they are dependency isolation, not a security sandbox. Local caches are disposable. Resource feasibility is a hard gate before rollout. Wheel-based preprocessing provenance must replace VCS-install metadata checks with verified build provenance, not disable them. Acceptance requires the seven roadmap gates and per-model evidence; this document alone proves none of them.
