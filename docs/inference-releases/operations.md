# Operations, configuration and resource budget

## Keep hosting stable

AWS App Runner remains the execution host for IR-01–IR-07. No ECS or GPU infrastructure is provisioned. The HTTP request must use the existing asynchronous job pattern rather than wait for a long scientific run. The current job repository is process-local/in-memory; this roadmap does not promise durable jobs across restarts or cross-instance routing. IR-01 documents existing polling/routing behavior and IR-06 verifies it under the actual deployment topology. Do not silently introduce a distributed queue.

AWS documents a 120-second total HTTP request timeout, a five-minute startup health window and 3 GB of ephemeral storage that also accommodates image storage. Local file persistence is not guaranteed. Verify these constraints against the actual deployment and current documentation at implementation time. Reference: https://docs.aws.amazon.com/apprunner/latest/dg/develop.html (reviewed 2026-10-20).

## Feasibility gate

IR-01 measures current image footprint, baseline RSS/peak process-tree memory, CPU/native thread use, temporary H5 copies, artifact and wheel sizes, installed main/auxiliary environments, installation time and inference duration. Budget compressed/downloaded objects and expanded installations separately. Include platform overhead, simultaneous installation/execution, cleanup reserve and temporary copies. Measure cold and warm runs for each variant; do not assume five environments fit at once.

Propose explicit limits for active processes, install concurrency, cache bytes, input/temp bytes, minimum free disk, worker memory budget, deadlines and native numerical threads. Initial active scientific process target is one per instance, pending measurements. Cache admission must reject work cleanly before disk exhaustion; no active environment eviction. If the budget fails, stop rollout and review alternatives within App Runner or propose a separate scope decision. Do not silently migrate to ECS.

Idle App Runner, storage and observability may still cost money. Record current service sizing/scaling, measured usage and an owner-approved cost ceiling; do not claim zero idle costs or savings without billing evidence. Add bounded logs and usage telemetry without patient data or unbounded labels.

## CI/CD separation (documentation only)

Model Release CI/CD (building and publishing an ML plugin wheel, offline wheelhouse, artifacts, provenance and golden tests for one of the five variants) is documented here as a pipeline distinct from the existing Bremen application CI/CD (`.github/workflows/ecr-publish.yml` and related application build/test workflows). This block makes no workflow-file changes; it only records the intended separation so that IR-03's "new release build workflow" is scoped as a release-only pipeline when it is implemented, not as a change to the application's own CI/CD.

## Configuration ownership

| Configuration | Treatment |
|---|---|
| Existing catalog URI, AWS region and source/storage access | Preserve unless a consumer audit proves replacement |
| Authentication, secrets and external source configuration | Preserve; never put secret values in release manifests |
| Per-model artifact identity, preprocessing version/config, feature metadata | Move into immutable release metadata after parity |
| `BREMEN_PREPROCESS_PYTHON` | Retire only after all affected Bremen paths migrate |
| `BREMEN_ARAMINA_PREPROCESS_PYTHON`, `BREMEN_ARAMINA_PREPROCESS_019_PYTHON` | Retire only after both Aramina dependency paths are release-owned |
| Legacy model bucket/prefix/version/manifest settings | Audit every discovery/CLI/training/rollback consumer before removing |
| Release cache, deadlines, process/install limits | A small validated platform-level configuration surface; names finalized in IR-02 |

Do not replace many model-specific variables with another set of per-model variables. Keep the existing catalog as the routing authority, with pinned release references. Separate deployment-level resource policies from scientific model parameters. During transition, retain both paths explicitly; missing optional release metadata means legacy behavior, not a guessed release.

## Reproducible installation and provenance

Build against the observed Python ABI and Linux architecture. Current Dockerfile uses Python 3.13; verify actual deployed image. A venv cannot supply a different interpreter or absent OS libraries. Native dependencies must be covered by the base image/release compatibility contract. Use an offline wheelhouse, exact hash-locked requirements, `--no-index`, `--only-binary=:all:` and `--require-hashes`; no live Git checkout, runtime compiler or GitHub token.

The current preprocessing worker checks version `0.1.7b0` plus VCS commit `45d5568248e9774b7938a36e028d80e72b130b19` through direct_url.json. Wheel installation has different provenance metadata. Replace that assumption with trusted CI provenance binding original source commit, built wheel SHA-256 and installed distribution identity; validate this before executing scientific code. Do not fabricate VCS metadata or simply remove the guard.

References: https://packaging.python.org/en/latest/specifications/direct-url-data-structure/ and https://pip.pypa.io/en/latest/topics/secure-installs/ (reviewed 2026-10-20).

## Required diagnostics

Record request correlation ID, model ID, release digest, image identity, lifecycle phase (PUBLISHED/VERIFIED/READY/ACTIVE), install/cache outcome, queue wait, execution time, exit/error category (including the typed worker error code), peak process-tree memory and free/used disk. Preserve existing feature telemetry semantics without logging sensitive feature values by default. S3 IAM grants runtime read access only to needed release/source prefixes; publication credentials stay outside runtime. Checksums do not make untrusted pickle safe.
