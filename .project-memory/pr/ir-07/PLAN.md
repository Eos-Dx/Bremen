# IR-07: External XRD feature-library integration

Status: implementation in progress (branch `0171-ir-07-xrd-feature-library`). This file is the logical-ID plan brief referenced from `ROADMAP.md` / `docs/inference-releases/implementation-plan.md`; it is rewritten here (2026-10-24) because it previously described the unrelated post-cutover cleanup task. That cleanup task is **IR-08** now — see the detailed PR brief for this concrete branch at `.project-memory/pr/0171-ir-07-xrd-feature-library/PLAN.md`.

## Entry condition

Requires IR-06 (release-runtime cutover) merged. Must complete, and be accepted, before IR-08 (legacy inference cleanup) proceeds — the roadmap explicitly orders feature-library externalization before any embedded-code removal.

## Work

Extract the Bremen 15-feature contract and the Aramina CORE4 symmetry contracts (v0.1 and v0.2) out of `src/bremen/model_packages/**` into a standalone, independently versioned Python distribution (`xrd-inference-features`, import package `xrd_inference_features`) living at `packages/xrd-inference-features/`. The library is release-bound, never a Bremen/App Runner application dependency: each Model Release manifest additively declares a `feature_library` block (distribution, version, contract, wheel filename, SHA-256), the release build independently constructs and binds the exact wheel, and `ReleaseCache` installs it into that release's own venv the same way it installs the plugin wheel. The release-backed Worker computes features through the external library; the legacy in-process path keeps the embedded implementation unchanged until IR-08. Selection is explicit and release-scoped (`BREMEN_FEATURE_LIBRARY_BACKEND`, set only inside a release Worker process), not import-presence duck typing, so the external package being importable in some other process/test never changes legacy behavior.

## Expected change areas

`packages/xrd-inference-features/**` (new); `src/bremen/contracts/inference_release.py` (additive `feature_library` manifest block); `src/bremen/release_build/feature_wheel.py` (new, deterministic builder); `src/bremen/release_build/assemble.py` (builds/binds the wheel, derives `feature_order_hash` from the library); `src/bremen/platform/models/release_cache.py` (installs the optional `feature_library_wheel` role); `src/bremen/ml_plugin/release.py` (`apply_feature_library_backend`); `src/bremen/model_packages/bremen_v01/runtime.py` and `src/bremen/model_packages/aramina_v0213/inference.py` (backend-selection seam); `tests/**`.

## Acceptance and evidence

See `.project-memory/pr/0171-ir-07-xrd-feature-library/IMPLEMENTATION_REPORT.md`, `FEATURE_CONTRACTS.md`, `WHEEL_EVIDENCE.md`, and `FIVE_RELEASE_PARITY.md` for the concrete evidence for this branch: differential parity (embedded vs. library, exact equality), manifest schema tests, deterministic wheel hashes, the five rebuilt release manifests, and real `ReleaseCache.install()` runs proving every golden case passes through the real Worker subprocess with the external backend active.

## Rollback

No shared/global install to roll back. Releases built before IR-07 (no `feature_library` block) remain valid and unaffected; the legacy in-process path never changes. A release can be rebuilt without the `feature_library` block only by reverting to a pre-IR-07 `assemble_release`; this documentation does not perform that rollback.

## Exclusions

No scientific behavior change (ROI, normalization, pairing, peak windows, thresholds, feature names/order are byte-identical extractions). No AWS/App Runner/S3 publication/activation. No IR-08 cleanup (legacy embedded code, discovery, and config are untouched). No dependency version changes (scikit-learn stays pinned at 1.9.0; the exact wheel was located from existing local `/tmp/ir04/wheelhouse-all` build evidence, not upgraded). See root `ROADMAP.md` and ADR 0019 for authority.
