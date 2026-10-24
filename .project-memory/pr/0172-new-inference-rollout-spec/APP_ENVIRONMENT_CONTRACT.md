# Bremen environment-variable contract (code audit, not a live inspection)

Every classification below comes from reading the merged source — not from inspecting any deployed App Runner service. No AWS was accessed to produce this document.

## REQUIRED

| Variable | Defined in | Default | Notes |
|---|---|---|---|
| `BREMEN_MODEL_CATALOG_URI` | `release_cache.py:ENV_CATALOG_URI`, `api/http/app.py` | none (raises `ReleaseCacheError("invalid_configuration", "catalog_uri")` if unset/empty) | Must be `s3://<bucket>/<prefix>`. Required to resolve any catalog/release reference. **Deployed value is UNKNOWN — this agent did not inspect AWS.** |

## OPTIONAL / RECOMMENDED

| Variable | Defined in | Default | Notes |
|---|---|---|---|
| `BREMEN_RELEASE_CACHE_ROOT` | `release_cache.py:ENV_CACHE_ROOT` | `<tempdir>/bremen-release-cache` (`_default_cache_root()`) | Optional; the code default works, but AWS App Runner's ephemeral/non-durable local storage (noted in `docs/inference-releases/operations.md`) makes an **explicit** value advisable in production so the operator controls exactly which disk/volume holds the cache. Not mandatory for correctness. |
| `BREMEN_RELEASE_CACHE_MAX_BYTES` | `release_cache.py:ENV_CACHE_MAX_BYTES` | `8 * 1024**3` (8 GiB, `DEFAULT_MAX_CACHE_BYTES`) | Optional; must be a positive integer string if set (`_env_int` raises `invalid_configuration` otherwise). Recommended to set explicitly once real per-instance disk budget is measured (IR-01 feasibility gate, still pending live measurement per `operations.md`). |
| `BREMEN_CANDIDATE_INVOCATION_TIMEOUT_SECONDS` | `subprocess_runtime.py:ENV_INVOCATION_TIMEOUT` | `120` (`DEFAULT_INVOCATION_TIMEOUT_SECONDS`) | Still actively consumed (per-Worker-invocation deadline, line 241) — **not** renamed in this PR per instruction. Optional; tune only with measured evidence. |
| `BREMEN_IR03_AUX_ENV_ROOT` | `ml_plugin/release.py:AUX_ENV_ROOT_ENV` | unset -> only `<release>/aux/<tag>/bin/python` is tried | Fallback root for a *materialized* auxiliary preprocessing environment that lives outside any single release (distinct from a release's own bundled `aux/<tag>/` directory, and distinct from the per-Worker-process `BREMEN_FEATURE_LIBRARY_BACKEND` seam below). Legitimate platform-level config if the operator provisions shared preprocessing environments outside release bundles; optional otherwise. |

## LEGACY_COMPATIBILITY

| Variable | Defined in | Notes |
|---|---|---|
| `BREMEN_CANDIDATE_SUBPROCESS_MODELS` | `subprocess_runtime.py:ENV_CANDIDATE_MODELS` | **Confirmed by code read: no longer consulted by the release-backed routing decision.** `registry.py::_candidate_runtime_for` (the actual construction path since IR-06) checks only `entry.get_runtime_release()` truthiness — it never calls `is_candidate_enabled_for`/`candidate_model_ids()`. Those two functions have zero callers anywhere in `src/` outside their own module. Stale/legacy; harmless if still set, but controls nothing in the current route. Candidate for IR-08 removal, not this PR. |
| `BREMEN_PREPROCESS_PYTHON` | `model_packages/bremen_v01/preprocessing.py`; also release-scoped via `ml_plugin/release.py` | Dual-purpose: (a) legacy/global — the non-release in-process Bremen preprocessing path reads this name directly from the process environment; (b) release-owned — `apply_preprocessing_environment` sets this same name transiently inside a release Worker process (`@aux/<tag>` resolved to that release's bundled or `BREMEN_IR03_AUX_ENV_ROOT`-rooted interpreter) before invoking the runtime. `docs/inference-releases/operations.md`: "Retire only after all affected Bremen paths migrate." Do not remove in this PR. |
| `BREMEN_ARAMINA_PREPROCESS_PYTHON` | `model_packages/aramina_v0213/preprocessing.py`; release-scoped via `ml_plugin/release.py` | Same dual-purpose pattern as above, for Aramina's `v0.1.7-beta` preprocessing release. |
| `BREMEN_ARAMINA_PREPROCESS_019_PYTHON` | same | Same pattern, for Aramina's `v0.1.9-beta` preprocessing release (A2). |
| `BREMEN_PREPROCESS_PROVENANCE` | `model_packages/bremen_v01/bremen_preprocess_worker.py`; release-scoped | Points at a provenance JSON record; same dual-purpose pattern. |
| `BREMEN_ARAMINA_PREPROCESS_PROVENANCE` | `model_packages/aramina_v0213/aramina_preprocess_worker.py`; release-scoped | Same pattern, Aramina side. |

## WORKER_OWNED

| Variable | Defined in | Notes |
|---|---|---|
| `BREMEN_FEATURE_LIBRARY_BACKEND` | `ml_plugin/release.py:FEATURE_LIBRARY_BACKEND_ENV` | Set **only** inside a release Worker subprocess, by `apply_feature_library_backend(config)`, and only when that release's own `runtime.json` declares a `feature_library_backend` (every IR-07 release does: value `"xrd_inference_features"`). Read at call time by `bremen_v01/runtime.py::_use_external_feature_backend` and `aramina_v0213/inference.py::_use_external_feature_backend`. No other code path sets or reads it. |

## MUST_NOT_BE_GLOBAL

| Variable | Why |
|---|---|
| `BREMEN_FEATURE_LIBRARY_BACKEND` | Setting this globally (e.g. as a platform-wide App Runner environment variable) would force every process — including the legacy in-process path, which has no `xrd_inference_features` installed — to attempt the external backend, breaking legacy execution. It is deliberately not in `ml_plugin/release.py:ALLOWED_PREPROCESSING_ENV_VARS` or any global config surface; the one and only writer is the per-Worker `apply_feature_library_backend` call, gated on that release's own manifest. **If this variable is ever found set globally on the live service, that is a rollout blocker** — flag and do not proceed; this agent did not check the live environment for it. |

## UNRELATED_APPLICATION_CONFIG (not touched by this migration)

| Variable prefix | Notes |
|---|---|
| `BREMEN_AUTH_*` (`BREMEN_AUTH_ENABLED`, `BREMEN_AUTH_JWT_SECRET`, `BREMEN_AUTH_JWT_AUDIENCE`, `BREMEN_AUTH_JWT_ISSUER`, `BREMEN_AUTH_PASSWORD_HASH`, `BREMEN_AUTH_USERNAME`, `BREMEN_AUTH_ACCESS_TTL_SECONDS`, `BREMEN_AUTH_REFRESH_TTL_SECONDS`) | **UNCHANGED BY NEW INFERENCE WORKFLOW.** Not inspected, not recorded, no values of any kind captured here. |
| `BREMEN_DEMO_H5_*` (`BREMEN_DEMO_H5_ALLOW_UPLOAD`, `BREMEN_DEMO_H5_BUCKET`, `BREMEN_DEMO_H5_CONTAINERS`, `BREMEN_DEMO_H5_MAX_BYTES`, `BREMEN_DEMO_H5_PREFIX`) | **UNCHANGED BY NEW INFERENCE WORKFLOW.** |
| `BREMEN_MODEL_STAGING_DIR` | Legacy artifact-staging path (`model_artifacts.py`, `platform/models/state.py`); orthogonal to release-backed execution. Not evaluated further here. |
| `BREMEN_AWS_REGION`, `BREMEN_LOG_LEVEL`, `BREMEN_SERVICE_ENV`, and the various `BREMEN_DESIGN_SPEC_*`/report-schema/product-copy constants | Application/platform config unrelated to the IR-07 scientific migration. |

## Rules explicitly honored

- `BREMEN_FEATURE_LIBRARY_BACKEND` is never proposed as a global variable (see MUST_NOT_BE_GLOBAL above).
- `BREMEN_CANDIDATE_SUBPROCESS_MODELS` is not required for the new route (confirmed dead for routing purposes, LEGACY_COMPATIBILITY only).
- No legacy variable is proposed for removal in this PR; removal is explicitly deferred to post-cutover cleanup / IR-08 (see `OPERATOR_HANDOFF.md` / `ROLLBACK_SPEC.md`).
- No secret value is recorded anywhere in this document; auth/demo variables are not evaluated beyond "unchanged."
