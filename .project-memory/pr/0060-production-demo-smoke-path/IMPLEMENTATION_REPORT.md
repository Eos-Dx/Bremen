# PR 0060 — Implementation Report: Production Demo Smoke Path

**Agent**: coder
**Mode**: implementation
**Branch**: 0060-production-demo-smoke-path
**Date**: 2026-07-15

---

## Files Changed

| File | Status | Notes |
|------|--------|-------|
| `src/bremen/demo_smoke.py` | **New** | Demo/smoke runner module — stdlib-only HTTP client for checking a running Bremen service |
| `src/bremen/__main__.py` | Modified | Added `demo-smoke` CLI subcommand |
| `tests/test_bremen_demo_smoke.py` | **New** | 15 tests covering CLI help, smoke checks, output contract, safety |

---

## Demo Smoke Command Summary

**Command**: `python -m bremen demo-smoke --base-url http://127.0.0.1:8000`

**Options**:
- `--base-url` (default: `http://127.0.0.1:8000`) — URL of running Bremen service
- `--timeout` (default: `30`) — Request timeout in seconds
- `--skip-prediction` (flag) — Skip the prediction check

**Implementation**: Standard-library only (`urllib.request`, `json`, `uuid`, `datetime`, `argparse`). No `requests`, `httpx`, `boto3`, or any third-party dependencies.

**CLI handler**: Uses lazy import of `demo_smoke.main()`, following the same pattern as the existing `serve` and `preprocess` subcommands.

---

## HTTP Checks Summary

Three checks are performed in order:

### 1. GET /health
- Checks service is running with `status: "ok"` and `model_ready` field.
- On success: `checks.health = "pass"`.
- On HTTP/connection error: `checks.health = "fail"` with descriptive warning.

### 2. GET /model/version
- Checks model is configured and reports `model_status`, `model_version`, `model_configured`, etc.
- On success: `checks.model_version = "pass"`.
- On error: `checks.model_version = "fail"` with descriptive warning.

### 3. POST /predictions (optional, skip via `--skip-prediction`)
- Sends a minimal valid prediction request with a synthetic placeholder H5 path.
- The server accepts the job asynchronously (202) and the demo smoke optionally polls once for completion.
- When `--skip-prediction` is set: `prediction.status = "not_available"` with explanation.
- When not skipped: returns `accepted` status with `job_id` and optional poll results.

---

## Feature Artifact / Prediction Check Summary

- The prediction check uses a lightweight synthetic payload:
  ```json
  {
    "target_scan_ref": "demo:target/001",
    "control_scan_ref": "demo:control/001",
    "h5_path": "/tmp/bremen_demo_smoke_placeholder.h5",
    "request_id": "<uuid>"
  }
  ```
- This hits the existing `POST /predictions` endpoint.
- The server accepts the job asynchronously (202) and attempts inference.
- If inference fails due to missing H5 file, the job status becomes `failed`.
- The demo smoke reports the result faithfully without fabricating clinical success.
- When `--skip-prediction` is set, the check is skipped with a clear `not_available` status.

---

## Demo Payload Summary

- No real patient data is used.
- No H5 files are committed or required.
- Placeholder H5 path is synthetic (`/tmp/bremen_demo_smoke_placeholder.h5`).
- No clinical evidence is fabricated.
- No model artifacts are committed.

---

## Output Contract Summary

Every output dict includes:

| Field | Type | Description |
|-------|------|-------------|
| `technical_demo_only` | `bool` | Always `true` |
| `base_url` | `str` | The service URL that was checked |
| `request_id` | `str` | UUID for request correlation |
| `checks` | `dict` | Results per check: `"pass"` or `"fail"` |
| `health` | `dict` | Health endpoint response |
| `model_version` | `dict` | Model version endpoint response |
| `prediction` | `dict` | Prediction check result |
| `warnings` | `list[str]` | Warning messages |
| `status` | `str` | `"pass"` \| `"partial"` \| `"fail"` |
| `timestamp` | `str` | ISO-8601 UTC timestamp |

The output is printed as formatted JSON, followed by a human-readable summary.

**Safety**: 
- No diagnosis, clinical validation, MRI replacement, or biopsy replacement language.
- No patient-specific claims.
- No clinical performance claims.

---

## Observability Summary

- Each demo smoke run generates a UUID `request_id`.
- The `X-Request-ID` header is sent with every HTTP request to the service.
- The returned request ID is included in the output.
- No OpenTelemetry, CloudWatch, Sentry, Datadog, or metrics exporters added.
- Stdlib `logging` not added in demo_smoke.py (output is via `print` to stdout).

---

## Safety Boundary Summary

- ✅ No inference expansion — calls existing HTTP API endpoints only
- ✅ No model loading or deserialization
- ✅ No `joblib.load` or `pickle.load`
- ✅ No H5 reads — synthetic placeholder path is never opened by demo smoke code
- ✅ No H5 mutation or writes
- ✅ No AWS/S3/network clients — stdlib `urllib.request` to user-supplied URL only
- ✅ No Matador integration
- ✅ No real patient data
- ✅ No clinical diagnosis or replacement claims
- ✅ `technical_demo_only: true` in every output
- ✅ No new dependencies (stdlib only)
- ✅ No deployment mutation (read-only smoke checks)
- ✅ No Terraform/GitHub Actions/Docker changes
- ✅ No docs/ROADMAP changes

---

## Tests Run and Results

### Focused tests

| Test File | Result |
|-----------|--------|
| `tests/test_bremen_demo_smoke.py` | **15 passed** ✅ |
| `tests/test_bremen_api_server.py` | 28 passed ✅ |
| `tests/test_bremen_api_skeleton.py` | 51 passed ✅ |
| `tests/test_bremen_feature_artifact_prediction_flow.py` | 61 passed ✅ |
| `tests/test_bremen_predictions.py` | 32 passed ✅ |
| `tests/test_bremen_decision_support_output.py` | 11 passed ✅ |
| `tests/test_bremen_dependency_hygiene.py` | 10 passed ✅ |

### Full test suite

`python -m pytest -q` → **996 passed, 11 skipped** ✅

### CLI help checks

| Command | Exit Code | Result |
|---------|-----------|--------|
| `python -m bremen --help` | 0 | ✅ (lists `demo-smoke`) |
| `python -m bremen serve --help` | 0 | ✅ |
| `python -m bremen demo-smoke --help` | 0 | ✅ (shows `--base-url`, `--timeout`, `--skip-prediction`) |

### Forbidden-pattern grep checks

| Pattern | Result |
|---------|--------|
| `joblib.load\|pickle.load\|import pickle` in demo smoke files | No hits ✅ |
| `.h5\|.hdf5\|h5py` in demo smoke files | Only `h5_path` field name in POST payload (synthetic placeholder path) ✅ |
| `boto3\|botocore\|requests\|httpx` in demo smoke files | No hits ✅ |
| `FastAPI\|Flask\|uvicorn\|gunicorn\|starlette\|aiohttp\|django` | No new hits ✅ |

### Forbidden path checks

| Check | Result |
|-------|--------|
| `.github/ infra/terraform/ Dockerfile Dockerfile.training requirements.txt pyproject.toml config/training frontend web ui package.json ... tests/data` | No changes ✅ |
| `docs/ ROADMAP.md` | No changes ✅ |
| `.h5/.hdf5/.joblib/.pkl/.npy/.npz/.tfstate` | No changes ✅ |
| `.DS_Store` | None found ✅ |

---

## Validation Results

| Command | Exit Code | Status |
|---------|-----------|--------|
| `git rev-parse --verify HEAD` | 0 | ✅ |
| `git branch --show-current` | `0060-production-demo-smoke-path` | ✅ |
| `git status --short` | 3 files changed | ✅ |
| `git diff --name-only` | Only allowed files | ✅ |
| `python -m compileall src tests` | 0 | ✅ |
| `python -m pytest -q tests/test_bremen_demo_smoke.py` | 0 (15 passed) | ✅ |
| `python -m pytest -q tests/test_bremen_api_server.py` | 0 (28 passed) | ✅ |
| `python -m pytest -q tests/test_bremen_api_skeleton.py` | 0 (51 passed) | ✅ |
| `python -m pytest -q tests/test_bremen_feature_artifact_prediction_flow.py` | 0 (61 passed) | ✅ |
| `python -m pytest -q tests/test_bremen_predictions.py` | 0 (32 passed) | ✅ |
| `python -m pytest -q tests/test_bremen_decision_support_output.py` | 0 (11 passed) | ✅ |
| `python -m pytest -q tests/test_bremen_dependency_hygiene.py` | 0 (10 passed) | ✅ |
| `python -m pytest -q` | 0 (996 passed, 11 skipped) | ✅ |
| `python -m bremen --help` | 0 | ✅ |
| `python -m bremen serve --help` | 0 | ✅ |
| `python -m bremen demo-smoke --help` | 0 | ✅ |

---

## Diff Summary

```
src/bremen/__main__.py                |  49 ++++++++++++++++++++++++++++-
src/bremen/demo_smoke.py              | 276 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++
tests/test_bremen_demo_smoke.py       | 276 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++
```

---

## PLAN Compliance

| Requirement | Status |
|-------------|--------|
| `python -m bremen demo-smoke --base-url URL` implemented | ✅ |
| `demo-smoke --help` works | ✅ |
| `--base-url`, `--timeout`, `--skip-prediction` options | ✅ |
| Health check included | ✅ |
| Model/version check included | ✅ |
| Prediction check included or controlled `not_available` | ✅ |
| Stdlib only (urllib.request, json, uuid, datetime, argparse) | ✅ |
| `technical_demo_only: true` in output | ✅ |
| Request ID handling (X-Request-ID header) | ✅ |
| JSON output with pass/fail status | ✅ |
| Unavailable service produces controlled failure | ✅ |
| No clinical diagnosis/replacement claims | ✅ |
| No new dependencies | ✅ |
| No docs/ROADMAP changes | ✅ |
| No Terraform/Docker/GitHub Actions changes | ✅ |
| No frontend/React/package-manager files | ✅ |
| Existing tests pass unchanged | ✅ |

---

## Plan Drift Check

| Drift Category | Check | Result |
|----------------|-------|--------|
| File drift | Only allowed files changed | ✅ |
| Demo smoke drift | Stdlib-only CLI, no AWS SDK, calls existing HTTP API | ✅ |
| Safety drift | No inference expansion, no model loading, no H5 reads, no clinical claims | ✅ |
| Test drift | 15 new tests pass, existing tests unchanged | ✅ |
| Validation drift | All checks pass, forbidden-pattern greps clean | ✅ |

---

## Blockers

None.

---

## Warnings

None.

---

## Boundary Confirmations

- ✅ confirm: production/demo smoke path implemented
- ✅ confirm: implementation is not docs-only
- ✅ confirm: `python -m bremen demo-smoke --base-url ...` implemented
- ✅ confirm: demo-smoke help works
- ✅ confirm: health check included
- ✅ confirm: model/version check included
- ✅ confirm: feature artifact prediction flow included or controlled not_available
- ✅ confirm: deterministic safe demo payload used (synthetic placeholder path)
- ✅ confirm: technical_demo_only output included
- ✅ confirm: request_id/logging behavior preserved
- ✅ confirm: deployed URL compatibility implemented without AWS SDK
- ✅ confirm: no deployment mutation added
- ✅ confirm: no Terraform/GitHub Actions/Docker changes
- ✅ confirm: no React/frontend added
- ✅ confirm: no new dependencies added
- ✅ confirm: no unsafe model loading added
- ✅ confirm: no H5 mutation added
- ✅ confirm: no real patient data added
- ✅ confirm: no clinical diagnosis/replacement claims added
- ✅ confirm: Bremen safety identity preserved
- ✅ confirm: no H5/model/tfstate artifacts
- ✅ confirm: no git mutation commands
