# ADR 0019: independent inference releases on existing App Runner

Date: 2026-10-20. Status: PROPOSED; acceptance requires repository review/merge.

## Context

The application currently packages platform and model code in one distribution. Bremen discovery can deserialize an artifact into the platform process; Aramina uses its own artifact compatibility behavior. Preprocessing already uses separate Python environments in some paths. These partial boundaries do not constitute standalone, immutable inference releases. Five deployed variants are the business scope, pending inventory verification.

## Decision

Retain App Runner. Keep routing, authorization, source access, job/report orchestration and telemetry in the platform. Put each variant's complete scientific inference behavior—artifact loading, compatibility classes, scientific input validation, preprocessing, feature construction, scaling/imputation, prediction, thresholds and scientific result construction—inside its release. Preserve external projection/error contracts through an explicit adapter.

Deliver an immutable release manifest, inference wheel, offline dependency wheelhouse, model artifacts, preprocessing configuration and provenance through S3. A release may reference shared immutable blobs, but MUST resolve a complete dependency closure. Each model activation pins a release digest. Shared source or wheel code is allowed only where equivalence is established; five variants still require five separately tracked release descriptors and parity gates.

Use a separate OS Python process, not a Python thread, for scientific execution. A release-specific virtual environment isolates Python dependencies. Initial design is a supervised one-shot invocation per job, bounded per application instance, with verified installations cached locally. Do not introduce persistent worker pools in this block without a separately reviewed amendment. Auxiliary preprocessing subprocesses may remain inside a release if needed to preserve the existing dependency split; kill and account for the entire process group.

Use a small framework-neutral JSON protocol. Do not send pickle objects between platform and worker. Preserve legacy catalog/API identities. Keep the legacy path available until all five variants pass controlled rollout. An activated release failure is reported as failure; do not silently rerun a different model or legacy path.

## Alternatives

Threads do not isolate dependency versions or scientific imports. Shipping only joblib does not carry imported custom classes, transformation code, locked dependencies or provenance. ECS may be reconsidered after this block if measured resource constraints demand it. Mandatory MLflow serving would add another migration and is not required for this extraction.

## Relationship to earlier decisions

Preserve ADR 0016 ModelRuntime semantics, ADR 0017 package ownership and ADR 0018 result semantics. Supersede ADR 0013's earlier restricted Aramina subprocess deployment scope with the release-based execution model for the five inventoried variants. Supersede historical startup-only/in-process joblib-loading prescriptions for migrated variants only. Existing trusted-deserialization checks and scientific invariants remain required. No other historical ADR is blanket-revoked.

## Consequences and acceptance

Cold starts and first-use installation may be slower. Virtual environments share the host Python ABI and OS libraries; they are dependency isolation, not a security sandbox. Local caches are disposable. Resource feasibility is a hard gate before rollout. Wheel-based preprocessing provenance must replace VCS-install metadata checks with verified build provenance, not disable them. Acceptance requires the seven roadmap gates and per-model evidence; this document alone proves none of them.
