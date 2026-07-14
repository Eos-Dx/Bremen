# PR 0027 — Plan Model Package Source Integration

Author: plan
Mode: planning only
Branch: 0027-model-package-source-integration

## Objective

Add model package source integration for runtime/API surfaces. The runtime:

1. **Cloud metadata source** — derives safe model source status from existing cloud config environment variables (`BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, etc.) and exposes configured/unconfigured model package source status through the existing `/model/version` endpoint — without loading, fetching, validating, or deserializing model artifacts.
2. **Local package source** — resolves a local directory path to a validated model package and surfaces full manifest metadata through `/model/version` — without calling `joblib.load()`, without inference, without S3/network calls.
3. **Source precedence** — uses a deterministic lookup order: explicit local path argument > `BREMEN_MODEL_PACKAGE_DIR` env var > cloud metadata config > `not_configured`.

The PR is strictly metadata/status-only for cloud sources, and validation+metadata for local sources. No model deserialization, no inference, no H5 reads.

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

1. **`src/bremen/model_package_source.py`** — NEW (or RENAME if `src/bremen/api/model_source.py` already exists). Model package source resolver at the bremen package level (not inside api/), to keep source resolution logic separate from HTTP handler concerns.
2. **`src/bremen/api/app.py`** — MODIFY. Wire safe model source metadata into `handle_model_version()`.
3. **`src/bremen/api/server.py`** — MODIFY only if server wiring changes are needed to pass model source context or local package dir into handlers.
4. **`tests/test_bremen_model_package_source.py`** — NEW. Focused tests for model source resolution (local + cloud).
5. **`tests/test_bremen_api_skeleton.py`** — MODIFY. Update model metadata expectations to reflect configured/unconfigured states.
6. **`tests/test_bremen_api_server.py`** — MODIFY. Add HTTP coverage for `/model/version` configured/unconfigured responses.

**Module name resolution note**: If `src/bremen/api/model_source.py` already exists from an earlier partial implementation, the coder should either:
- Move/refactor it to `src/bremen/model_package_source.py` and update imports, OR
- Keep `api/model_source.py` for the cloud metadata path and add `src/bremen/model_package_source.py` for the full source resolution (local + cloud + precedence).

Default preference: keep the existing `src/bremen/api/model_source.py` for the cloud metadata path, add `src/bremen/model_package_source.py` for the full source resolver that wraps both local and cloud resolution with precedence.

## Forbidden files

- `ROADMAP.md`, `README.md`, `docs/**` (except `docs/api_contract.md` only if contract change is justified)
- `.github/**`, `infra/**`, `Dockerfile`, `.dockerignore`
- `requirements.txt`, `pyproject.toml`, `config/**`, `examples/**`, `agents/**`
- `src/bremen/model_package.py`, `src/bremen/modeling.py`, `src/bremen/pipelines.py`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `.DS_Store`, `__pycache__/**`

## Exact implementation scope

### 1. `src/bremen/model_package_source.py` — Model source resolver

A small import-safe module that resolves the active model package source and returns a metadata dict suitable for `/model/version`.

**Core objects**:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ModelPackageSourceError(Exception):
    """Base exception for model package source errors."""


@dataclass(frozen=True)
class ModelPackageSource:
    """Represents a resolved model package source (not loaded)."""
    source_type: str           # "not_configured" | "local" | "cloud"
    model_configured: bool
    model_version: str | None
    model_checksum: str | None
    feature_schema_version: str | None
    threshold_version: str | None
    threshold_value: float | None
    qc_criteria_version: str | None
    model_status: str          # "not_configured" | "configured" | "invalid"
    error: str | None          # validation error message, if any
```

**Functions**:

```python
def resolve_model_package_source(
    explicit_path: str | Path | None = None,
) -> ModelPackageSource:
    """Resolve the active model package source with precedence.

    1. explicit_path argument (local directory)
    2. BREMEN_MODEL_PACKAGE_DIR env var (local directory)
    3. Cloud metadata from read_cloud_config()
    4. not_configured
    """
```

**Precedence and fail-closed behavior**:

1. **Explicit local path** — If provided, resolve and validate as a local package directory. Fail closed if the path is invalid, missing manifest, failing checksum, or path traversal. Reject if not a directory.
2. **`BREMEN_MODEL_PACKAGE_DIR` env var** — If set, same rules as explicit path. Must be a valid package directory. Fail closed with validation error.
3. **Cloud metadata** — Use `read_cloud_config()`. Metadata-only; no S3 reads. If cloud is configured, return `model_status="configured"` with all content fields `None` (unknown until fetched).
4. **not_configured** — Default when nothing is configured.

**Local package source requirements**:

- Use the existing `validate_model_package()` from `src/bremen/model_package.py` for directory/checksum validation.
- Use the existing `summarize_model_package()` for safe metadata after validation.
- Never call `joblib.load()`.
- Never import `joblib` or `pickle`.
- Never run inference.
- Must not leak `BREMEN_MODEL_PACKAGE_DIR` env var value into cloud config context (it's a local dev/runtime path, not a cloud bucket).
- Must not replace existing `BREMEN_CONFIG` discovery behavior.
- Must not require docs/README changes in this PR.

**`BREMEN_MODEL_PACKAGE_DIR` env var validation**:

- Must be a non-empty string after stripping.
- Must be a valid directory path.
- Must not contain local machine path sentinels relative to cloud config (already guarded by separate env var).
- If the directory is missing or not a valid model package, return `model_status="invalid"` with a descriptive error — do not silently fall through to cloud config.

### 1b. `src/bremen/api/model_source.py` — Cloud metadata descriptor (existing, keep as is)

The metadata-only cloud source descriptor using `read_cloud_config()`.

```python
def derive_model_source(
    cloud: CloudConfig | None = None,
) -> dict:
    """Derive safe model package source metadata from cloud config.

    No S3 reads, no model file reads, no validation.
    Returns configured status when BREMEN_MODEL_BUCKET is set.
    """
```

`handle_model_version()` in `app.py` should call `resolve_model_package_source()` (the new full resolver), not the cloud-only path directly. The new resolver wraps both local and cloud resolution with precedence.

### 2. `src/bremen/api/app.py` — Wire into `handle_model_version()`

Change `handle_model_version()` from the hardcoded stub to call `resolve_model_package_source()`:

```python
def handle_model_version(
    explicit_path: str | Path | None = None,
) -> ModelVersionResponse:
    """Return configured model package metadata.

    Resolves via source precedence:
    1. explicit_path (local directory)
    2. BREMEN_MODEL_PACKAGE_DIR env var
    3. Cloud metadata from read_cloud_config()
    4. not_configured

    Must not import ``joblib`` / ``pickle`` or deserialize artifacts.
    """
    from ..model_package_source import resolve_model_package_source  # noqa: PLC0415

    source = resolve_model_package_source(explicit_path=explicit_path)
    return ModelVersionResponse(
        model_configured=source.model_configured,
        model_version=source.model_version,
        model_checksum=source.model_checksum,
        feature_schema_version=source.feature_schema_version,
        threshold_version=source.threshold_version,
        threshold_value=source.threshold_value,
        qc_criteria_version=source.qc_criteria_version,
        model_status=source.model_status,
    )
```

**Backward compatibility**:
- Server.py calls `handle_model_version()` with no args — that's fine, falls through precedence to cloud or not_configured.
- HTTP tests can pass `explicit_path` to test local resolution, or rely on the default env-based precedence.

### 3. `tests/test_bremen_model_package_source.py` — New tests

Test scenarios:

**Source precedence**:

1. **Explicit path wins over all** — Provide an explicit valid package path; verify it returns validated metadata from that path regardless of env vars.
2. **`BREMEN_MODEL_PACKAGE_DIR` env var** — Set the env var to a valid package directory; verify it returns validated metadata.
3. **Cloud metadata fallback** — Clear all local env vars; set `BREMEN_MODEL_BUCKET`; verify returns `configured` with content fields `None`.
4. **not_configured default** — No local path, no env vars for source; verify returns `not_configured`.

**Local package validation**:

5. **Local valid package returns manifest metadata** — Create a valid package dir with `manifest.json` and dummy artifact; verify `model_version`, `feature_schema_version`, `threshold_version`, `model_checksum` are populated from manifest.
6. **Local invalid package fails closed** — Create a package dir with missing manifest or checksum mismatch; verify returns `model_status="invalid"` with error.
7. **Local missing directory** — Non-existent path; verify returns `model_status="invalid"` with error.
8. **Local path traversal rejected** — Invalid model_filename in manifest; verify returns `model_status="invalid"` with error.
9. **Local source does not call joblib.load()** — AST import safety check.

**Cloud metadata-only**:

10. **Cloud configured returns metadata status** — Set `BREMEN_MODEL_BUCKET`; verify `model_configured=True`, `model_status="configured"`, all content fields `None`.
11. **Cloud source does not call S3/AWS/network** — Any env-only; no import of boto3/botocore/requests/httpx.
12. **Manifest key normalization** — If `BREMEN_MODEL_MANIFEST_KEY` is set, it is represented in source metadata (without reading it).

**Integration**:

13. **`handle_model_version()` with explicit path** — Call with a valid local package path; verify metadata populated.
14. **`handle_model_version()` without args** — Works in both configured/unconfigured host env states.
15. **Import safety** — `model_package_source.py` does not import `joblib`, `pickle`, `boto3`, `botocore`, `h5py`, or make network calls.

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

- No S3 reads, no model file reads, no network calls (except local filesystem reads for local package validation).
- No `joblib.load()` or pickle deserialization — local validation reads `manifest.json` only, not the model artifact.
- No inference or preprocessing.
- No H5/HDF5 reads.
- No Matador integration.
- No checksum fetch or manifest download from S3.
- No Docker/Terraform/CI/dependency changes.
- No clinical claims.
- No AWS account ID, access key, or secret exposure in API output.
- No bucket/prefix/manifest key exposure in public API output.
- No model package upload or management API.
- No model activation/reload/restart endpoint.
- No frontend or React.
- No docs/ROADMAP updates.

## Safety boundaries

This PR must ensure:
- No real inference or model prediction.
- No training.
- No model loading or deserialization via `joblib.load()` / `pickle.load()`.
- No pickle deserialization of any kind.
- No S3/AWS network calls.
- **Local validation reads `manifest.json` only** — the model artifact joblib/pkl file is never read by Python code except for SHA-256 checksum computation (pure binary read, no deserialization).
- No H5/HDF5 reads.
- No Matador integration.
- No preprocessing bridge.
- No clinical report generation.
- No claim that Bremen diagnoses disease, replaces MRI, replaces biopsy, replaces a radiologist, or is clinically validated.
- No Docker, Terraform, GitHub Actions, dependency, deployment, or infrastructure changes.
- No bucket/prefix/manifest key or other sensitive env values exposed in public API output.
- No `BREMEN_MODEL_PACKAGE_DIR` leaked into cloud config context — it is a local dev/runtime path only.
- Public API metadata is `model_configured`, `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`, `model_status` only — no storage internals.
- Local package path must not leak into cloud config validation (separate env var, separate validation).

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_model_package_source.py
python -m pytest -q tests/test_bremen_model_package.py
python -m pytest -q tests/test_bremen_cloud_config.py
python -m pytest -q tests/test_bremen_config_loading.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_api_contract.py
python -m pytest -q tests/test_bremen_dependency_hygiene.py
python -m pytest -q tests/test_bremen_cli_entrypoint.py
python -m bremen --help
python -m bremen serve --help
python -m pytest -q
```

### Forbidden-pattern grep checks

```bash
# No joblib/pickle (model_package.py already has it in AST test assertions, which is fine)
grep -R -I -n "joblib\.load\|pickle\.load\|import joblib\|import pickle" src/bremen tests/test_bremen_model_package_source.py || true

# No H5 reads
grep -R -I -n "\.h5\|\.hdf5\|h5py" src/bremen tests/test_bremen_model_package_source.py || true

# No AWS/network clients
grep -R -I -n "boto3\|botocore\|requests\|httpx" src/bremen tests/test_bremen_model_package_source.py || true

# No new web framework
grep -R -I -n "FastAPI\|Flask\|uvicorn\|gunicorn\|starlette\|aiohttp\|django" src tests requirements.txt pyproject.toml || true

# Forbidden files unchanged
git diff --name-only -- .github infra/terraform docs ROADMAP.md README.md Dockerfile requirements.txt pyproject.toml config examples tests/data agents frontend web ui package.json package-lock.json yarn.lock pnpm-lock.yaml

# No model/data artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true

# No .DS_Store
find . -name ".DS_Store" -print
```

### Expected results

- All grep checks return no matches (or only pre-existing safe matches).
- `git diff --name-only` for forbidden paths returns no output.
- `find . -name ".DS_Store" -print` returns no output.

## Platform safety decisions

| Decision | Value |
|----------|-------|
| Public API exposes bucket name? | **No** — bucket/prefix/manifest key are internal env configuration, not public model metadata. |
| Public API exposes model_version from env? | **Yes** — `model_version` is safe metadata. `None` if env var not set. |
| Public API exposes `model_checksum`? | **Yes** when local package is validated (from manifest). **No** for cloud source (not known until fetched). |
| Public API exposes `feature_schema_version`, `threshold_version`, etc.? | **Yes** when local package is validated. **None** for cloud source (not known until fetched). |
| Status when bucket configured but model not fetched? | `model_configured=True`, `model_status="configured"` — accurately reflects source configuration without claiming model is loaded. |
| Status when local package is valid? | `model_configured=True`, `model_status="configured"`, all manifest fields populated. |
| Status when local package is invalid? | `model_configured=False`, `model_status="invalid"`, `error` field describes the failure. |
| Status when nothing configured? | `model_configured=False`, `model_status="not_configured"` — same as current behavior. |
| `BREMEN_MODEL_PACKAGE_DIR` leaked into cloud config? | **No** — separate env var, separate validation path, never merged into CloudConfig. |

## Frontend and Model Ops future boundary

This PR explicitly does **not** include:

- **No React frontend** — No frontend code, no webpack/package.json, no Node toolchain.
- **No model upload endpoint** — No `POST /models` or similar; model package management is PR 0030-ish.
- **No model activation/reload/restart endpoint** — No `POST /models/activate`, `POST /server/reload`.
- **No admin UI** — No admin routes, no admin auth, no admin dashboard.
- **No package manager files** — No `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `node_modules/`.
- **No CORS broadening** — If tests require cross-origin access, that should be avoided.

**Future direction (preserved, not implemented)**:

- PR 0030-ish: Model package management API — upload, validate manifest/checksum/schema, stage, activate/reload.
- PR 0031-ish: React Model Ops Console MVP — consumes JSON APIs and logs/status.
- The `ModelPackageSource` and `resolve_model_package_source()` layer created in this PR provides the source/status foundation for future Model Ops work.

## Rollback plan

1. **Revert `src/bremen/api/model_source.py`** — delete.
2. **Revert `src/bremen/api/app.py`** — restore `handle_model_version()` to return `build_not_configured_model_response()`.
3. **Revert test files** — delete or revert `test_bremen_api_model_source.py`, `test_bremen_api_skeleton.py`, `test_bremen_api_server.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only allowed files changed. No forbidden files. |
| **Model source drift** | Local source reads `manifest.json` only (no joblib/pickle deserialization). Cloud source is metadata-only. No S3 reads. No bucket/prefix exposed in public API. |
| **App handler drift** | `handle_model_version()` now calls `resolve_model_package_source()`. No other handler changed. |
| **Safety drift** | No inference, training, model loading, H5 reads, AWS calls, clinical claims. Local validation reads manifest.json; SHA-256 on artifact binary (no deserialization). |
| **Test drift** | New module tests cover local validation, cloud metadata, source precedence, invalid/fail-closed, no-deserialization. Existing tests pass unchanged. |
| **Contract drift** | No `docs/api_contract.md` changes needed — existing contract already specifies `model_configured`, `model_status`, and the `"configured"`/`"invalid"` status values. |
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
| Source resolver module | `src/bremen/model_package_source.py` (bremen package level) — full resolver with precedence. |
| Cloud descriptor (internal) | `src/bremen/api/model_source.py` — kept for cloud metadata path if already exists. |
| Wiring approach | `handle_model_version()` calls `resolve_model_package_source()`. No server.py changes. |
| Local source validation | Uses `validate_model_package()` / `summarize_model_package()` from existing `model_package.py`. |
| Source precedence | 1. Explicit path arg > 2. `BREMEN_MODEL_PACKAGE_DIR` env > 3. Cloud metadata > 4. not_configured |
| Local package env var | `BREMEN_MODEL_PACKAGE_DIR` — local/dev only, validated separately from cloud config. |
| Cloud config input | `read_cloud_config()` from `config.py` — already reads all 6 env vars. |
| Local valid → public API | `model_configured=True`, all manifest fields populated (`model_version`, `model_checksum`, etc.). |
| Local invalid → public API | `model_configured=False`, `model_status="invalid"`, `error` field with reason. |
| Cloud configured → public API | `model_configured=True`, content fields `None`, `model_status="configured"`. |
| Not configured → public API | `model_configured=False`, all content fields `None`, `model_status="not_configured"`. |
| Bucket/prefix exposed? | **No** — not part of public model metadata. |
| docs/api_contract.md change? | **No** — existing contract already accommodates all states. |
| Server/CLI changes? | **No** — wiring is internal to `app.py` and `model_package_source.py`. |
| Frontend/Model Ops? | **No** — upload, activation, reload, admin UI deferred to PR 0030-ish / PR 0031-ish. |

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
- confirm: PR 0027 planned as model package source integration: yes
- confirm: local model package source planned: yes
- confirm: cloud metadata-only source planned: yes
- confirm: not_configured source status planned: yes
- confirm: source precedence planned: yes
- confirm: fail-closed validation planned: yes
- confirm: `/model/version` metadata-only integration considered/planned: yes
- confirm: future Model Ops direction preserved for later PRs: yes
- confirm: no React/frontend planned: yes
- confirm: no model upload planned: yes
- confirm: no model activation/reload/restart planned: yes
- confirm: no new dependencies planned: yes
- confirm: no joblib/pickle/model loading planned: yes
- confirm: no inference planned: yes
- confirm: no H5/preprocessing planned: yes
- confirm: no AWS/S3/network calls planned: yes
- confirm: no Terraform/GitHub Actions/Docker/docs/ROADMAP changes planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
