# PR 0060 — Plan Production Demo Smoke Path

Author: plan
Mode: planning only
Branch: 0060-production-demo-smoke-path

## Objective

Add a thin, standard-library-only `demo-smoke` CLI command that exercises a running Bremen HTTP service and produces a readable demo/smoke summary. This provides a practical mechanism to demonstrate and smoke-test the Bremen workflow end-to-end through its HTTP API — for local development, CI validation, App Runner/ECS deployed-target verification, and engineering/product demos.

The existing service is already fully operational (PRs 0026–0054, 981 tests passing) with:
- `GET /health` with `model_ready` field
- `GET /model/version` with `model_status: "ready"`
- `POST /predictions` accepting `h5_path` / `h5_uri` with full feature artifact prediction flow
- `GET /predictions/{job_id}` for async result polling
- Structured logging with request_id propagation
- `ModelState` with synthetic model loader for dev/smoke testing

This PR creates the demo/smoke CLI layer. No changes to the HTTP API, inference pipeline, model loading, or deployment infrastructure.

## Required reads — observed facts

### `src/bremen/__main__.py`
- CLI entrypoint with argparse. Commands: `preprocess`, `preflight`, `run`, `report`, `serve`.
- `main()` dispatches by `_cmd_handler` attribute.
- Logging is configured at startup via `logging_config.configure_logging()`.
- Adding a new subcommand follows the existing pattern: define `_add_demo_smoke_subcommand()` and `_handle_demo_smoke()`.

### `src/bremen/api/server.py`
- `_make_handler()` returns a handler bound to `InMemoryJobStore`.
- Server starts with optional `load_model` parameter (loads synthetic model for inference testing).
- All 4 routes exist: `GET /health`, `GET /model/version`, `POST /predictions`, `GET /predictions/{job_id}`.
- Request ID propagation: `X-Request-ID` header accepted and returned.
- Structured logging via `logging.getLogger(__name__)` with `bremen.*` event format.

### `src/bremen/api/app.py`
- `handle_health()` returns `HealthResponse` with `model_ready` field.
- `handle_model_version()` returns full model metadata — `model_status="ready"` when model is loaded.
- `handle_submit_prediction()` runs the full inference pipeline (staging → preflight → preprocessing → inference → decision support report).
- `ModelNotReadyError` raises when model not loaded (HTTP 503).
- Accepts `h5_path` or `h5_uri` in request body.

### `src/bremen/api/schemas.py`
- `PredictionRequest` schema requires `target_scan_ref`, `control_scan_ref`, exactly one of `h5_path` or `h5_uri`.
- Response schemas include `request_id` field.

### `src/bremen/logging_config.py`
- Structured logging with `bremen.*` event format.
- Configured at startup via `configure_logging()`.

### `src/bremen/api/model_state.py`
- `ModelState.get_instance()` — singleton with `is_ready()`, `get_model()`, `load_at_startup()`.
- Synthetic model loaded when `load_model=True` passed to `_make_handler()`.

### `tests/test_bremen_api_server.py`
- 20+ tests for HTTP routes, import safety.

### `tests/test_bremen_feature_artifact_prediction_flow.py`
- 801-line test file for the full prediction flow.

### `tests/test_bremen_predictions.py`
- 630-line test file for prediction job lifecycle.

### `tests/test_bremen_decision_support_output.py`
- 401-line test file for decision support report output contract.

### `ROADMAP.md`
- PR 0060 is the first PR in the next execution block after PR0050–PR0054.
- States: "The next execution block requires a human product/engineering decision."
- The task prompt IS that human decision: build a production/demo smoke path.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_smoke.py`** — NEW. The demo smoke CLI entry point.
2. **`src/bremen/__main__.py`** — MODIFY. Add `demo-smoke` subcommand (very small change: subparser definition + handler call).
3. **`tests/test_bremen_demo_smoke.py`** — NEW. Tests for the demo smoke command.
4. **`tests/test_bremen_api_server.py`** — MODIFY (only if the server needs a startup-mode change to support demo-smoke's inline server launch pattern; default: no change).

**Server note**: The demo smoke command must work against an already-running remote service (deployed App Runner, CI host, or local `python -m bremen serve`). For tests, the demo smoke tests should start an inline test server (same pattern as existing server tests: free port + daemon thread) and run the demo-smoke client against it.

## Forbidden files

- `ROADMAP.md`, `README.md`, `docs/**`
- `.github/**`, `infra/terraform/**`
- `Dockerfile`, `Dockerfile.training`
- `requirements.txt`, `pyproject.toml`
- `frontend/**`, `web/**`, `ui/**`
- `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `node_modules/**`
- `tests/data/**`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `tfstate`, `.terraform`
- `config/training/**`
- `src/bremen/training/**`

A tiny ROADMAP note is allowed if justified by the human decision recording. Default: avoid.

## Exact implementation scope

### 1. `src/bremen/demo_smoke.py` — Demo smoke runner

A small stdlib-only module. No AWS SDK, no third-party HTTP client, no new dependencies.

```python
"""Demo/smoke runner for a running Bremen HTTP service.

Calls the Bremen HTTP API and produces a machine-readable JSON summary
plus pass/fail text suitable for demos, CI smoke tests, and operator
verification.

Standard library only — no third-party dependencies.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from urllib.error import URLError
from urllib.request import Request, urlopen


def run_demo_smoke(
    base_url: str = "http://127.0.0.1:8000",
    timeout: int = 30,
) -> dict:
    """Run the demo smoke checks against a running Bremen service.

    Parameters
    ----------
    base_url : Base URL of the Bremen HTTP service.
    timeout : Request timeout in seconds.

    Returns
    -------
    A dict with keys: ``service_status``, ``model_version_status``,
    ``prediction_status``, ``overall``, ``request_id``, ``warnings``,
    ``technical_demo_only``, and optionally ``result``.
    """
```

**Checks performed (in order)**:

1. **Health check** — `GET {base_url}/health`. Expected: 200, `status: "ok"`, `model_ready: true`.
2. **Model version check** — `GET {base_url}/model/version`. Expected: 200, `model_status: "ready"`, `model_configured: true`.
3. **Prediction smoke** — `POST {base_url}/predictions` with minimal synthetic fixture. Expected: 202 with `job_id`.
   - **Poll** — `GET {base_url}/predictions/{job_id}` until status is `completed` or `failed`.
   - Use a safe synthetic fixture (e.g., inline minimal H5 path or skip prediction if no fixture available).
   - Must not fabricate clinical results, make diagnosis claims, or expose raw patient data.

**Prediction fixture approach**: The demo smoke must work against a remote service that may not have a local H5 file. Therefore:

- First attempt to use a known synthetic H5 fixture path if it exists locally (`tests/data/synthetic_demo.h5` or similar).
- If no local fixture path is configured, **skip** the prediction check with a controlled `"not_available"` status and a human-readable explanation.
- The prediction check must NOT be attempted with a randomly fabricated H5 path or S3 URI.

**Output shape**:

```python
{
    "service_status": {
        "status": "ok",
        "model_ready": True/False,
        "version": "<version or None>",
    },
    "model_version_status": {
        "model_configured": True,
        "model_version": "<version>",
        "model_checksum": "<sha256>",
        "feature_schema_version": "v0.1",
        "model_status": "ready",
    },
    "prediction_status": {
        "status": "completed" | "not_available" | "failed",
        "job_id": "<uuid>",
        "qc_status": "passed",
        # Only when status is "completed":
        "decision_support": {
            "report_schema_version": "v0.1",
            "p_mri_needed": <float>,
            "triage_recommendation": "MRI_RECOMMENDED" | "MRI_RULE_OUT",
        }
        # Only when status is "not_available":
        "reason": "No synthetic H5 fixture available for remote target",
    },
    "overall": "pass" | "partial" | "fail",
    "request_id": "<uuid>",
    "warnings": [],
    "technical_demo_only": True,
    "timestamp": "<ISO-8601 UTC>",
}
```

**Safety rules**:
- `technical_demo_only: true` in every output.
- No diagnosis, no clinical recommendation as validated truth.
- No MRI replacement, biopsy replacement language.
- No patient-specific claims.
- No clinical performance claims.
- No AWS credentials, account IDs, or production URLs hardcoded.

**CLI entry point**:

```python
def main(argv: list[str] | None = None) -> int:
    """Run the demo smoke checks and print the summary.

    Parameters
    ----------
    argv : Command-line args (excluding program name). Default: sys.argv[1:].

    Returns
    -------
    0 if overall is "pass" or "partial", 1 if "fail".
    """
```

CLI flags:
- `--base-url` (default: `http://127.0.0.1:8000`)
- `--timeout` (default: `30`)
- `--skip-prediction` (flag: skip prediction check even if fixture available)

### 2. `src/bremen/__main__.py` — Add `demo-smoke` subcommand

Add a new subcommand:

```
python -m bremen demo-smoke [--base-url URL] [--timeout SECONDS] [--skip-prediction]
```

```python
def _add_demo_smoke_subcommand(subparsers) -> None:
    demo = subparsers.add_parser(
        "demo-smoke",
        help="Run production demo smoke checks against a running Bremen service.",
    )
    demo.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="Base URL of the Bremen HTTP service (default: http://127.0.0.1:8000).",
    )
    demo.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30).",
    )
    demo.add_argument(
        "--skip-prediction",
        action="store_true",
        help="Skip the prediction check even if a fixture is available.",
    )
    demo.set_defaults(_cmd_handler="demo_smoke")
```

Handler:

```python
def _handle_demo_smoke(args) -> int:
    from .demo_smoke import main as demo_main
    return demo_main([f"--base-url={args.base_url}", f"--timeout={args.timeout}"]
                     + (["--skip-prediction"] if args.skip_prediction else []))
```

Update `BUILTIN_COMMANDS` tuple to include `"demo_smoke"`.

### 3. `tests/test_bremen_demo_smoke.py` — Tests

Use the same pattern as existing server tests: start an HTTPServer on a free port in a daemon thread with `_make_handler(job_store, version="test", load_model=True)`, then run `run_demo_smoke()` against it.

**Test scenarios**:

1. **CLI help** — `python -m bremen demo-smoke --help` exits 0.
2. **CLI in main help** — `python -m bremen --help` lists `demo-smoke`.
3. **Health check** — `run_demo_smoke()` against a running test server returns `service_status.status == "ok"`.
4. **Model version check** — Returns `model_version_status.model_status == "ready"`.
5. **Prediction check skipped when no fixture** — Returns `prediction_status.status == "not_available"` with reason.
6. **Overall pass** — When health + model version pass, `overall` is `"pass"`.
7. **Controlled failure when service unavailable** — `run_demo_smoke(base_url="http://127.0.0.1:1")` raises or returns controlled error.
8. **JSON output shape** — Output dict contains all expected keys.
9. **Request ID present** — Output contains `request_id` of correct type.
10. **`technical_demo_only` field** — Present and `true`.
11. **No frontend/package-manager files** — Use the standard forbidden-files checklist.

## Non-goals

- No inference expansion or new inference paths.
- No new HTTP routes or API contract changes.
- No model loading changes.
- No H5 file reads by the demo smoke command itself (it uses the service API, not direct H5 access).
- No H5 file mutation.
- No AWS/S3 calls (stdlib `urllib` to user-supplied `--base-url` is allowed, not AWS SDK).
- No clinical data, real patient data, or fabricated clinical evidence.
- No deployment mutation (Terraform, Docker, CI/CD, App Runner deploy).
- No React/frontend.
- No new dependencies (stdlib only).
- No docs/ROADMAP updates (unless justified minimal human-decision note).

## Safety boundaries

- No runtime training.
- No unsafe model deserialization.
- No new `joblib.load` — the demo smoke calls the existing HTTP API which handles model loading via `ModelState.load_at_startup()` (already approved).
- No pickle loading.
- No H5 reads by demo smoke code — it calls the service API which has its own approved H5 read path.
- No H5 writes ever.
- No preprocessing expansion.
- No AWS/S3 calls except `urllib.request` calls to the user-supplied `--base-url`.
- No Matador resolver implementation.
- No clinical report template.
- No clinical diagnosis claim.
- Output always includes `technical_demo_only: true`.
- No diagnosis, no clinical recommendation as validated truth.
- No MRI/biopsy/replacement language in output.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_feature_artifact_prediction_flow.py
python -m pytest -q tests/test_bremen_predictions.py
python -m pytest -q tests/test_bremen_decision_support_output.py
python -m pytest -q tests/test_bremen_dependency_hygiene.py
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
```

### Forbidden-pattern grep checks

```bash
# No unsafe deserialization in demo smoke code
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" src/bremen/demo_smoke.py tests/test_bremen_demo_smoke.py || true
# Expected: no output

# No H5 reads in demo smoke code
grep -R -I -n "\.h5\|\.hdf5\|h5py" src/bremen/demo_smoke.py tests/test_bremen_demo_smoke.py || true
# Expected: no output unless H5 path reference for prediction check

# No AWS/network client deps (stdlib urllib to supplied base URL is allowed)
grep -R -I -n "boto3\|botocore\|requests\|httpx" src/bremen/demo_smoke.py tests/test_bremen_demo_smoke.py || true
# Expected: no output

# No new web framework
grep -R -I -n "FastAPI\|Flask\|uvicorn\|gunicorn\|starlette\|aiohttp\|django" src tests requirements.txt pyproject.toml || true
# Expected: no output

# Forbidden files unchanged
git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training requirements.txt pyproject.toml config/training frontend web ui package.json package-lock.json yarn.lock pnpm-lock.yaml tests/data

# No model/data artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true

# No .DS_Store
find . -name ".DS_Store" -print
```

## Platform safety decisions

| Decision | Value |
|----------|-------|
| Prediction check for remote targets | **Skip** with `"not_available"` if no local H5 fixture path available. |
| Prediction check for local targets | **Run** if synthetic H5 fixture path can be resolved. |
| Synthetic H5 fixture | Use existing `tests/data/synthetic_demo.h5` if present; do NOT commit one. |
| `technical_demo_only` field | Required in every output. |
| CLI default base URL | `http://127.0.0.1:8000` (matches `serve` default). |
| AWS SDK requirement | **None**. Stdlib `urllib` only. |
| Deployment mutation | **None**. Read-only smoke checks. |
| ROADMAP note | Allowed only as a minimal human-decision record. Default: avoid. |

## Rollback plan

1. **Revert `src/bremen/demo_smoke.py`** — delete.
2. **Revert `src/bremen/__main__.py`** — remove the `demo-smoke` subcommand additions.
3. **Revert `tests/test_bremen_demo_smoke.py`** — delete.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only allowed files changed. No forbidden files. |
| **Demo smoke drift** | Stdlib-only CLI. No AWS SDK, no new dependencies. Calls existing HTTP API; does not bypass it. |
| **Safety drift** | No inference expansion, no model loading, no H5 reads, no clinical claims. `technical_demo_only: true` in output. |
| **Test drift** | New demo smoke tests pass. Existing API/prediction/decision-support tests pass unchanged. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Implementation requires new dependencies.
- Implementation requires Terraform, Docker, GitHub Actions, or deployment changes.
- Implementation adds new HTTP routes or changes the API contract.
- Implementation performs unsafe model deserialization (`joblib.load` / `pickle.load`) outside the approved `ModelState.load_at_startup()` boundary.
- Implementation adds H5 reads outside the approved `h5_inputs.stage_h5_input()` / inference chain.
- Implementation fabricates clinical evidence or makes clinical validation claims.
- Implementation hardcodes secrets, account IDs, registry URLs, or production URLs.
- Implementation cannot be completed within the allowed files.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Module | `src/bremen/demo_smoke.py` — stdlib-only demo/smoke runner. |
| CLI command | `python -m bremen demo-smoke [--base-url URL] [--timeout SECONDS] [--skip-prediction]` |
| HTTP client | stdlib `urllib.request` only. |
| Prediction fixture | Skip with `not_available` if no local synthetic H5. |
| Output shape | JSON dict with `service_status`, `model_version_status`, `prediction_status`, `overall`, `request_id`, `warnings`, `technical_demo_only`, `timestamp`. |
| Exit code | 0 for pass/partial, 1 for fail. |
| AWS/Docker/Terraform | No changes. |
| Dependencies | None new. |
| API contract | No changes. |

## Files read

- `ROADMAP.md`
- `docs/api_contract.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `src/bremen/__main__.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `src/bremen/api/jobs.py`
- `src/bremen/api/schemas.py`
- `src/bremen/api/model_state.py`
- `src/bremen/api/model_source.py`
- `src/bremen/api/feature_artifact_prediction.py`
- `src/bremen/api/decision_support.py`
- `src/bremen/feature_artifacts.py`
- `src/bremen/inference.py`
- `src/bremen/logging_config.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_feature_artifact_prediction_flow.py`
- `tests/test_bremen_predictions.py`
- `tests/test_bremen_decision_support_output.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_dependency_hygiene.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0060-production-demo-smoke-path/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR 0060 planned as production/demo smoke path: yes
- confirm: plan is not docs-only: yes
- confirm: running service smoke/demo target planned: yes
- confirm: health check included: yes
- confirm: model/version check included: yes
- confirm: feature artifact prediction flow considered: yes (prediction smoke via existing API, skip when no fixture)
- confirm: deterministic safe demo payload planned: yes (skip with `not_available`, no fabricated data)
- confirm: request_id/logging behavior preserved: yes (uses existing server request_id propagation)
- confirm: App Runner/deployed URL compatibility planned without AWS SDK: yes (configurable `--base-url`)
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: no React/frontend planned: yes
- confirm: no new dependencies planned: yes
- confirm: no unsafe model loading planned: yes
- confirm: no inference expansion beyond existing approved boundaries planned: yes
- confirm: no H5 mutation planned: yes
- confirm: no real patient data planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
