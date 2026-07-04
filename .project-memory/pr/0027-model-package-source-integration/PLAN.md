# PR 0027 — Plan Model Package Source Integration

Author: plan
Mode: planning only
Branch: 0027-model-package-source-integration

## Objective

Add metadata-only model package source integration for runtime/API surfaces. The runtime derives safe model source metadata from existing cloud config environment variables (`BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, etc.) and exposes configured/unconfigured model package source status through the existing `/model/version` endpoint — without loading, fetching, validating, or deserializing model artifacts.

## Confirmation: PR 0026 is present

```
test -f src/bremen/api/server.py  ->  present (PR 0026 HTTP runner)
python -m bremen serve --help     ->  works (serves subcommand)
```

## Required reads — observed facts

### `src/bremen/config.py` (PR 0020)
- `read_cloud_config()` reads `BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_MANIFEST_KEY`, `BREMEN_SERVICE_ENV`, `BREMEN_AWS_REGION` from environment.
- Returns `CloudConfig(configured=True, model_bucket, model_prefix, model_version, ...)` when bucket is set.
- Returns `CloudConfig(configured=False, ...)` when bucket is absent.
- `CloudConfigError` raised on invalid values (s3:// URI, absolute paths).

### `src/bremen/api/app.py` (PR 0019)
- `handle_model_version()` currently returns `build_not_configured_model_response()` — hardcoded `not_configured`.
- `handle_health()` accepts optional `version` string.
- All handlers are stateless pure functions.

### `src/bremen/api/server.py` (PR 0026)
- `run_server()` accepts optional `version` parameter.
- HTTP `GET /model/version` dispatches to `handle_model_version()` — currently always returns `not_configured`.
- Server already passes shared `job_store` via closure.

### `src/bremen/api/schemas.py` (PR 0019)
- `ModelVersionResponse` has `model_configured`, `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`, `model_status` (all nullable except `model_configured` and `model_status`).
- `MODEL_STATUS_CONFIGURED = "configured"` constant already exists.
- `build_not_configured_model_response()` returns `model_configured=False, model_status="not_configured"`.
- `build_health_response()` handles optional `version` string.

### `src/bremen/__main__.py`
- `serve` command calls `run_server(host=..., port=...)` without passing `version`.
- Lazy import of `run_server`.

### `ROADMAP.md`
- PR 0027 described as: "Model package source integration. Resolve local/cloud model package references and validate manifests/checksums without `joblib.load()`. Uses `read_cloud_config()` and `model_package.validate_model_package()`."

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`src/bremen/api/model_source.py`** — NEW. Metadata-only model source descriptor module.
2. **`src/bremen/api/app.py`** — MODIFY. Wire safe model source metadata into `handle_model_version()`.
3. **`tests/test_bremen_api_model_source.py`** — NEW. Focused tests for model source module and wired behavior.
4. **`tests/test_bremen_api_skeleton.py`** — MODIFY. Update model metadata expectations to reflect configured/unconfigured states.
5. **`tests/test_bremen_api_server.py`** — MODIFY. Add HTTP coverage for `/model/version` configured/unconfigured responses.

Optional only if strongly justified:
6. **`src/bremen/__main__.py`** — MODIFY to pass `version` and/or env-derived model source into the server, if the wiring pattern requires it.
7. **`src/bremen/api/server.py`** — MODIFY only if server wiring changes are needed to pass model source context into handlers.

**Default approach**: Keep wiring in `app.py`. `handle_model_version()` calls `read_cloud_config()` internally and returns either `configured` or `not_configured`. No changes to `server.py` or `__main__.py` unless necessary.

## Forbidden files

- `ROADMAP.md`, `README.md`, `docs/**` (except `docs/api_contract.md` only if contract change is justified)
- `.github/**`, `infra/**`, `Dockerfile`, `.dockerignore`
- `requirements.txt`, `pyproject.toml`, `config/**`, `examples/**`, `agents/**`
- `src/bremen/model_package.py`, `src/bremen/modeling.py`, `src/bremen/pipelines.py`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `.DS_Store`, `__pycache__/**`

## Exact implementation scope

### 1. `src/bremen/api/model_source.py` — Model source descriptor

A small import-safe module. The function receives a `CloudConfig` (or reads env directly) and returns a metadata-only descriptor.

```python
"""Metadata-only model package source descriptor.

Safe to import at any point — no model loading, no network calls,
no H5 reads, no joblib/pickle.
"""

from __future__ import annotations

from ..config import CloudConfig, read_cloud_config


def derive_model_source(
    cloud: CloudConfig | None = None,
) -> dict:
    """Derive safe model package source metadata from cloud config.

    Parameters
    ----------
    cloud : A ``CloudConfig`` instance.  If ``None``, reads from
        environment variables via ``read_cloud_config()``.

    Returns
    -------
    A dict with keys for ``handle_model_version`` response:
    ``model_configured``, ``model_version``, ``model_status``, and
    ``model_checksum``/other fields set to ``None`` where unknown.
    No S3 reads, no model file reads, no validation.
    """
    if cloud is None:
        cloud = read_cloud_config()

    if not cloud.configured:
        return {
            "model_configured": False,
            "model_version": None,
            "model_checksum": None,
            "feature_schema_version": None,
            "threshold_version": None,
            "threshold_value": None,
            "qc_criteria_version": None,
            "model_status": "not_configured",
        }

    return {
        "model_configured": True,
        "model_version": cloud.model_version or None,
        "model_checksum": None,           # unknown until package is fetched
        "feature_schema_version": None,   # unknown until manifest is read
        "threshold_version": None,        # unknown until manifest is read
        "threshold_value": None,          # unknown until manifest is read
        "qc_criteria_version": None,      # unknown until manifest is read
        "model_status": "configured",
    }
```

**Key safety rules**:
- `read_cloud_config()` does not make network calls, import AWS SDK, or read model files.
- When `cloud.configured=True`, the source descriptor reports `model_status="configured"` but all content fields are `None` — no model package has been fetched or validated.
- No `joblib.load()`, no pickle, no S3 reads.
- No exposure of `model_bucket`, `model_prefix`, `model_manifest_key`, or other sensitive env values in public API output.
- The `version` string (if available from `importlib.metadata`) is safe to expose via the health endpoint but not via model source.

### 2. `src/bremen/api/app.py` — Wire into `handle_model_version()`

Change `handle_model_version()` from the hardcoded stub to call `derive_model_source()`:

```python
def handle_model_version(
    cloud: CloudConfig | None = None,
) -> ModelVersionResponse:
    """Return configured model package metadata.

    When environment variables (``BREMEN_MODEL_BUCKET`` etc.) are set,
    reports ``configured`` status.  All content fields remain ``None``
    until a model package is actually fetched and validated.

    Must not import ``joblib`` / ``pickle`` or deserialize artifacts.
    """
    from .model_source import derive_model_source  # noqa: PLC0415

    src = derive_model_source(cloud=cloud)
    return ModelVersionResponse(**src)
```

The `cloud` parameter is optional and defaults to `None` (reads from env). This preserves backward compatibility — all existing callers (server, tests) pass no arguments and get the same behavior, now reflecting actual env config instead of hardcoded `not_configured`.

### 3. `tests/test_bremen_api_model_source.py` — New tests

Test scenarios:

1. **No env vars → not_configured** — `derive_model_source()` with an empty env dict returns `model_configured=False`, `model_status="not_configured"`.
2. **Bucket + prefix set → configured** — `derive_model_source()` with a configured `CloudConfig` returns `model_configured=True`, `model_status="configured"`.
3. **Content fields are None when configured** — All content fields (`model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`) are `None` — no model has been fetched.
4. **`handle_model_version()` reflects env** — Call `handle_model_version()` with a configured cloud config, verify returns `configured`.
5. **`handle_model_version()` without args** — Call without args, verify returns `not_configured` or `configured` based on actual os.environ (safe to run in both states).
6. **Import safety** — Importing `model_source` does not import `joblib`, `pickle`, `boto3`, `h5py`, or make network calls.

### 4. `tests/test_bremen_api_skeleton.py` — Update expectations

The existing `test_model_version_returns_safe_not_configured` may need a small update. The safest approach: test both states explicitly.

- Add `test_model_version_configured_with_cloud_env()` — sets env vars, calls `handle_model_version()`, verifies `configured`.
- Add `test_model_version_not_configured_without_env()` — clears env vars, calls `handle_model_version()`, verifies `not_configured`.
- The existing test `test_model_version_does_not_load_model` can remain unchanged (the test verifies no model loading, which is still true).

### 5. `tests/test_bremen_api_server.py` — Add HTTP coverage

Add HTTP-level tests for the `/model/version` endpoint:

- `test_get_model_version_not_configured()` — Start server with empty env, GET `/model/version`, verify 200 with `model_configured=False`, `model_status="not_configured"`.
- `test_get_model_version_configured()` — Start server with `BREMEN_MODEL_BUCKET` set, verify 200 with `model_configured=True`, `model_status="configured"`.

The server test pattern already uses thread+random port — follow the same pattern from PR 0026's server tests.

### 6. No `docs/api_contract.md` change needed

The existing contract documents `model_configured: false` and `model_status: "not_configured"` as the default. When `configured=true`, the shape is the same — just different values. The contract already says `model_status` values include `configured`. No contract update is required.

## Non-goals

- No S3 reads, no model file reads, no network calls.
- No model package validation (`validate_model_package()` is not called).
- No `joblib.load()` or pickle deserialization.
- No inference or preprocessing.
- No H5/HDF5 reads.
- No Matador integration.
- No checksum fetch or manifest download.
- No Docker/Terraform/CI/dependency changes.
- No clinical claims.
- No AWS account ID, access key, or secret exposure in API output.
- No bucket/prefix/manifest key exposure in public API output.

## Safety boundaries

This PR must ensure:
- No real inference or model prediction.
- No training.
- No model loading or deserialization.
- No `joblib.load()`.
- No pickle.
- No S3/AWS network calls.
- No local model file reads.
- No H5/HDF5 reads.
- No Matador integration.
- No preprocessing bridge.
- No checksum fetch.
- No model package validation at runtime.
- No clinical report generation.
- No claim that Bremen diagnoses disease, replaces MRI, replaces biopsy, replaces a radiologist, or is clinically validated.
- No Docker, Terraform, GitHub Actions, dependency, deployment, or infrastructure changes.
- No bucket/prefix/manifest key or other sensitive env values exposed in public API output.
- Public API metadata is `model_configured`, `model_version` (optional), and `model_status` only — no storage internals.

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_api_model_source.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_cli_entrypoint.py
python -m pytest -q tests/test_bremen_cloud_config.py
python -m pytest -q tests/test_bremen_model_package.py
python -m bremen --help
python -m bremen serve --help
python -m pytest -q
```

### Forbidden-pattern grep checks

```bash
# No joblib/pickle
grep -R "joblib.load\|pickle.load\|import pickle\|import joblib" src/bremen tests || true

# No H5/AWS in API, model source, or server tests
grep -R "boto3\|botocore\|h5py\|\.h5\|\.hdf5" src/bremen/api tests/test_bremen_api_model_source.py tests/test_bremen_api_server.py || true

# No AWS credential exposure
grep -R "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|SECRET_ACCESS_KEY\|aws_secret_access_key" src/bremen/api tests/test_bremen_api_model_source.py tests/test_bremen_api_server.py || true

# No prohibited clinical claims
grep -R "diagnos\|clinical validation\|replace MRI\|replace biopsy" src/bremen/api tests/test_bremen_api_model_source.py tests/test_bremen_api_server.py || true
```

## Platform safety decisions

| Decision | Value |
|----------|-------|
| Public API exposes bucket name? | **No** — bucket/prefix/manifest key are internal env configuration, not public model metadata. |
| Public API exposes model_version from env? | **Yes** — `model_version` is safe metadata. `None` if env var not set. |
| Public API exposes `model_checksum`? | **No** — not known until manifest is read. Reports `None`. |
| Status when bucket configured but model not fetched? | `model_configured=True`, `model_status="configured"` — accurately reflects source configuration without claiming model is loaded. |
| Status when bucket not configured? | `model_configured=False`, `model_status="not_configured"` — same as current behavior. |

## Rollback plan

1. **Revert `src/bremen/api/model_source.py`** — delete.
2. **Revert `src/bremen/api/app.py`** — restore `handle_model_version()` to return `build_not_configured_model_response()`.
3. **Revert test files** — delete or revert `test_bremen_api_model_source.py`, `test_bremen_api_skeleton.py`, `test_bremen_api_server.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only allowed files changed. No forbidden files. |
| **Model source drift** | Metadata-only. No S3 reads, no model validation, no joblib/pickle. No bucket/prefix exposed in public API. |
| **App handler drift** | `handle_model_version()` now returns configured state based on env. Lazy import of `model_source`. No other handler changed. |
| **Safety drift** | No inference, training, model loading, H5 reads, AWS calls, clinical claims. |
| **Test drift** | New module tests, updated skeleton tests, server HTTP tests. Existing tests pass unchanged. |
| **Contract drift** | No `docs/api_contract.md` changes needed — existing contract already specifies `model_configured`, `model_status`, and the `"configured"` status value. |
| **Server/CLI drift** | No server.py or __main__.py changes needed by default. `handle_model_version()` callers (server) unchanged. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- PR 0026 HTTP server is not present on this branch (missing `src/bemmen/api/server.py`).
- Implementation requires dependency changes (pyproject.toml, requirements.txt).
- Implementation requires Docker, Terraform, AWS, GitHub Actions, or deployment changes.
- Implementation requires S3 reads, local model file reads, model package validation, model loading, H5 reads, preprocessing, or inference.
- Safe model source metadata cannot be integrated without exposing sensitive source details (bucket name, prefix, credentials).
- Implementation cannot be completed within the allowed files.
- Implementation claims clinical validation, diagnostic replacement, or production readiness.
- `docs/api_contract.md` would require changes that contradict the existing contract shape.

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0027-model-package-source-integration/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0027-model-package-source-integration/reviews/plan-review.yml` (next step, by plan-review agent)
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Decisions summary

| Decision | Value |
|----------|-------|
| Module location | `src/bremen/api/model_source.py` (inside api package, near handlers) |
| Wiring approach | `handle_model_version()` calls `derive_model_source()` via lazy import. No server.py changes. |
| Cloud config input | `read_cloud_config()` from `config.py` — already reads all 6 env vars. |
| Configured → public API | `model_configured=True`, `model_version` (from env or None), `model_status="configured"` |
| Not configured → public API | `model_configured=False`, all content fields `None`, `model_status="not_configured"` |
| Bucket/prefix exposed? | **No** — not part of public model metadata. |
| docs/api_contract.md change? | **No** — existing contract already accommodates both states. |
| Server/CLI changes? | **No** — wiring is internal to `app.py` and `model_source.py`. |

## Files read

- `ROADMAP.md`
- `.project-memory/project_contract.yml`
- `docs/api_contract.md`
- `src/bremen/config.py`
- `src/bremen/model_package.py`
- `src/bremen/api/app.py`
- `src/bremen/api/jobs.py`
- `src/bremen/api/schemas.py`
- `src/bremen/api/server.py`
- `src/bremen/__main__.py`
- `tests/test_bremen_cloud_config.py`
- `tests/test_bremen_model_package.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_cli_entrypoint.py`

## Files written

- `.project-memory/pr/0027-model-package-source-integration/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR 0026 HTTP server confirmed present on branch: yes
- confirm: no dependency changes planned: yes
- confirm: no S3/AWS/network calls planned: yes
- confirm: no model loading/inference planned: yes
- confirm: no H5/HDF5 reads planned: yes
- confirm: no model package validation/deserialization planned: yes
- confirm: no docs/api_contract.md change required: yes
- confirm: no server.py/__main__.py changes needed by default: yes
- confirm: no bucket/prefix/manifest key exposed in public API: yes
- confirm: no clinical claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
