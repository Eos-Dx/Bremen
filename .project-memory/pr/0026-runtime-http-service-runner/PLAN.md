# PR 0026 — Plan Runtime HTTP Service Runner

Author: plan
Mode: planning only
Branch: 0026-runtime-http-service-runner

## Objective

Add a minimal standard-library HTTP service runner around the existing Bremen API skeleton so the route-shaped handlers in `src/bremen/api/app.py` can be exercised through HTTP for local, container, and ECS smoke testing.

This is the first PR in the post-platform-foundation execution sequence defined in ROADMAP.md.

## Required reads — observed facts

### `src/bremen/api/app.py`
- Contains 4 route-shaped handler functions: `handle_health()`, `handle_model_version()`, `handle_submit_prediction()`, `handle_get_prediction()`.
- Stateless pure functions (except `job_store` parameter for the two prediction handlers).
- Returns typed dataclass objects from `schemas.py`.
- Already used by `tests/test_bremen_api_skeleton.py`.

### `src/bremen/api/jobs.py`
- `InMemoryJobStore` class with `create_job()`, `get_job()`, `update_status()`, `job_count`.
- Creates UUID-based job IDs.
- No background worker, no persistence.

### `src/bremen/api/schemas.py`
- All request/response dataclasses: `HealthResponse`, `ModelVersionResponse`, `PredictionRequest`, `PredictionResponse`, `PredictionStatusResponse`, `CompletedResult`.
- Status constants (`STATUS_ACCEPTED`, `STATUS_NOT_FOUND`, etc.).
- Validators: `validate_prediction_request()` raises `ValueError` on missing/invalid fields.
- Response builders: `build_health_response()`, `build_not_configured_model_response()`, `build_accepted_response()`, `build_not_found_response()`.
- `PredictionRequest.request_id` field exists but is not used at the HTTP layer.

### `src/bremen/__main__.py`
- CLI entrypoint with argparse.
- Commands: `preprocess` (real, lazy import), `preflight`/`run`/`report` (stubs).
- `main()` dispatches by `_cmd_handler` attribute on `argparse.Namespace`.
- Adding a `serve` command is feasible with the same pattern.

### `docs/api_contract.md`
- Defines the 4 HTTP endpoints with request/response shapes.
- HTTP 202 for `POST /predictions` submit.
- `not_found` status for unknown `job_id`.
- No inference, no H5, no model loading.
- No clinical/diagnostic language.

### `tests/test_bremen_api_skeleton.py`
- Comprehensive tests for the handler functions, job store, and schemas.
- All pass without HTTP.
- Import safety tests use AST inspection.

### `tests/test_bremen_api_server.py` (NEW — already implemented on branch)
- 19 tests covering GET /health, GET /model/version, POST /predictions (valid + invalid), GET /predictions/{job_id} (known + unknown), unknown route 404, unsupported method 405, import safety AST checks.
- Uses `urllib.request` bound to localhost on a free OS-assigned port.
- **Gap**: No tests for request_id header propagation, no structured logging verification.

### `tests/test_bremen_cli_entrypoint.py`
- Tests for the CLI entrypoint (help output, stub commands, serve CLI tests).
- Already contains `test_serve_help_exits_0`, `test_serve_help_contains_host_and_port`, `test_serve_in_main_help`, `test_main_help_shows_serve`.

### `ROADMAP.md`
- PR 0026 described as: "Runtime HTTP service runner. Expose existing API skeleton (`src/bremen/api/`) as an actual service process suitable for container/ECS smoke testing. No inference, no H5 read, no model loading."

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`src/bremen/api/server.py`** — NEW. Standard-library HTTP server adapter.
2. **`tests/test_bremen_api_server.py`** — NEW. Focused tests for HTTP behavior.
3. **`src/bremen/__main__.py`** — MODIFY. Add a `serve` CLI subcommand to start the HTTP server.
4. **`tests/test_bremen_cli_entrypoint.py`** — MODIFY. Add tests for `bremen serve --help` and basic serve invocation.

## Forbidden files

- `ROADMAP.md`, `README.md`, `docs/**`, `.github/**`, `infra/**`
- `Dockerfile`, `.dockerignore`, `requirements.txt`, `pyproject.toml`
- `config/**`, `examples/**`, `agents/**`
- `src/bremen/model_package.py`, `src/bremen/modeling.py`, `src/bremen/pipelines.py`, `src/bremen/config.py`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `.DS_Store`, `__pycache__/**`

## Exact implementation scope

### 1. `src/bremen/api/server.py` — HTTP server adapter

A standard-library-only HTTP server module. No web framework dependency.

**Design options** (choose one):

Option A: `http.server` — Use Python's built-in `http.server` with a custom `BaseHTTPRequestHandler` subclass. Route dispatch by matching `self.path` and `self.command`. JSON serialization via `json.dumps`. This is the simplest approach with zero new dependencies.

Option B: WSGI entry point — Create a WSGI-compatible function (e.g., for `gunicorn` or `waitress`). This requires a WSGI server dependency at runtime, which conflicts with the "no dependency changes" constraint.

**Recommendation**: Option A (`http.server`). The standard library is always available, no new dependencies, and the PR explicitly targets smoke testing, not production serving.

**Required routes**:

| Method | Path | Handler | Status code |
|--------|------|---------|-------------|
| `GET` | `/health` | `handle_health()` | 200 |
| `GET` | `/model/version` | `handle_model_version()` | 200 |
| `POST` | `/predictions` | `handle_submit_prediction()` | 202 (valid) / 400 (invalid) |
| `GET` | `/predictions/<job_id>` | `handle_get_prediction()` | 200 (found) / 404 (not found) |

**Behavior**:
- JSON request body parsing for `POST` requests.
- `POST /predictions` with `target_scan_ref` and `control_scan_ref` returns 202 with `job_id`.
- `POST /predictions` with missing/invalid fields returns 400 with error message.
- `GET /predictions/<uuid>` for known job returns job status.
- `GET /predictions/<uuid>` for unknown job returns 404 with `not_found` status.
- Unknown route returns 404.
- Method not allowed (e.g., `PUT` on known routes) returns 405.
- Runtime uses a single `InMemoryJobStore` instance.

**Exported interface**:
```python
def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the Bremen HTTP server (blocking).
    
    Args:
        host: Host address to bind to.
        port: Port number to listen on.
    """
```

The server is designed for dev/smoke testing only. No production readiness claims.

**Safety rules**:
- No `joblib.load()`.
- No pickle deserialization.
- No model loading.
- No H5/HDF5 reads.
- No AWS/S3/network client calls.
- No Matador integration.
- No clinical report generation.
- Standard library only.

### 1b. Logging baseline

Add basic structured logging using Python's standard `logging` module. No external logging dependencies.

**Log format**: Each request line should emit a structured log record containing:

| Field | Source |
|-------|--------|
| `request_id` | From `X-Request-ID` header or generated UUID |
| `method` | `self.command` |
| `path` | `self.path` |
| `response_status` | The HTTP status code returned |
| `job_id` | Available for `POST /predictions` and `GET /predictions/{job_id}` paths |
| `error` | Error reason for controlled failures (400/404/405 responses) |

**Implementation approach**:
- Configure a `logging.Logger` at module level in `server.py`.
- Do **not** silence `log_message` as a no-op — replace it with structured logging using `logging.Logger`.
- Log after each request completes (after `_send_json` / response is written).
- Use a simple delimited format (e.g., `request_id=<...> method=GET path=/health status=200`).
- Do not add JSON-formatted log output (avoid external dependency for structured logging formatters).

**Request ID behavior**:
- Accept an `X-Request-ID` header from the incoming request.
- If `X-Request-ID` is empty or not provided, generate a UUID request ID (`uuid.uuid4()`).
- Include the request ID in the response as `X-Request-ID` header.
- Also include the request ID in JSON responses where practical (e.g., prediction response, error response).
- This provides traceability for future Model Ops work.

**Non-goals for this PR**:
- No OpenTelemetry, CloudWatch, Sentry, Datadog, or metrics exporters.
- No JSON log output format.
- No log aggregation or streaming.
- No per-route log levels — all requests logged at INFO.

### 2. `src/bremen/__main__.py` — Add `serve` subcommand

Add a new `serve` subcommand to the CLI:

```
python -m bremen serve [--host HOST] [--port PORT]
```

```python
def _add_serve_subcommand(subparsers: argparse._SubParsersAction) -> None:
    serve = subparsers.add_parser(
        "serve",
        help="Start the Bremen HTTP API server (dev/smoke mode).",
    )
    serve.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1).",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number to listen on (default: 8000).",
    )
    serve.set_defaults(_cmd_handler="serve")


def _handle_serve(args: argparse.Namespace) -> int:
    from .api.server import run_server  # noqa: PLC0415 (lazy import)
    print(f"Starting Bremen API server at http://{args.host}:{args.port}")
    print("Dev/smoke mode only. Not for production use.")
    run_server(host=args.host, port=args.port)
    return 0
```

The `serve` handler uses a lazy import (inside the handler function, not at module level) to avoid importing `http.server` or any API code when running other CLI commands.

### 3. `tests/test_bremen_api_server.py` — HTTP server tests

Focused tests for the HTTP adapter. Use `http.server`'s testability or spawn the server on a random port in a thread and make HTTP requests via `urllib.request` (standard library).

**Test scenarios**:

1. `GET /health` returns 200 with status `"ok"`.
2. `GET /model/version` returns 200 with `model_configured: false`.
3. `POST /predictions` with valid body returns 202 with `job_id`.
4. `POST /predictions` with missing `target_scan_ref` returns 400.
5. `POST /predictions` with missing `control_scan_ref` returns 400.
6. `POST /predictions` with malformed JSON body returns 400.
7. `POST /predictions` with empty body returns 400.
8. `GET /predictions/{job_id}` for a known job returns 200 with job status.
9. `GET /predictions/{job_id}` for an unknown job returns 404 with `not_found`.
10. `GET /unknown-route` returns 404.
11. `PUT /health` returns 405 (method not allowed).
12. Server response includes `Content-Type: application/json` header.
13. Request with `X-Request-ID` header returns the same request ID in response `X-Request-ID` header.
14. Request without `X-Request-ID` gets a generated UUID request ID in response `X-Request-ID` header.
15. Request ID is included in JSON error response body.
16. Server logs structured information (verified by injecting a mocked logger or capturing log output).
17. Request ID appears in logged output.

### 4. `tests/test_bremen_cli_entrypoint.py` — Add serve CLI tests

Add test cases for:
- `python -m bremen serve --help` exits 0 and shows help text.
- The `serve` command appears in the main help output.
- No heavy imports triggered by `--help` (import safety preserved).

## Safety boundaries

This PR must not:
- Perform real inference or model prediction.
- Train models.
- Load models via `joblib.load()` or any deserialization.
- Import `joblib` or `pickle`.
- Read H5/HDF5 files.
- Make AWS/S3/network client calls.
- Integrate with Matador.
- Generate clinical reports.
- Claim that Bremen diagnoses disease, replaces MRI, replaces biopsy, or is clinically validated.
- Add any dependency to `requirements.txt` or `pyproject.toml`.
- Modify Docker, Terraform, GitHub Actions, or any infrastructure.
- Modify `config/`, `examples/`, or any data fixtures.
- Add OpenTelemetry, CloudWatch, Sentry, Datadog, or metrics exporters.
- Modify schemas, jobs, app.py, config.py, or model_package.py (all are out of scope).

## Validation checklist for the implementation phase (coder)

```bash
# Compile and test checks
python -m compileall src tests

# New server tests
python -m pytest -q tests/test_bremen_api_server.py

# Existing skeleton tests (regression)
python -m pytest -q tests/test_bremen_api_skeleton.py

# Contract tests (regression)
python -m pytest -q tests/test_bremen_api_contract.py

# CLI entrypoint tests (regression + new serve tests)
python -m pytest -q tests/test_bremen_cli_entrypoint.py

# Full test suite
python -m pytest -q

# CLI help checks
python -m bremen --help
python -m bremen serve --help
```

### Forbidden-pattern grep checks

```bash
# No joblib/pickle
grep -R "joblib.load\|pickle.load\|import pickle\|import joblib" src/bremen/api tests/test_bremen_api_server.py || true

# No H5/AWS/network
grep -R "boto3\|botocore\|h5py\|\.h5\|\.hdf5" src/bremen/api tests/test_bremen_api_server.py || true

# No prohibited clinical claims
grep -R "diagnos\|clinical validation\|replace MRI\|replace biopsy" src/bremen/api tests/test_bremen_api_server.py || true

# No OpenTelemetry/CloudWatch/Sentry/Datadog
grep -R "opentelemetry\|cloudwatch\|sentry_sdk\|datadog" src/bremen/api tests/test_bremen_api_server.py || true
```

## Non-goals

- No production-ready HTTP server (no connection pooling, no TLS, no process management).
- No WSGI/ASGI framework addition.
- No Dockerfile changes (the existing Dockerfile builds the CLI; the `serve` command will be available inside the container without Docker changes).
- No Terraform/IaC changes.
- No GitHub Actions workflow changes.
- No model loading or inference.
- No H5 reading or preprocessing.
- No Matador integration.
- No API contract change (the contract already defines the 4 endpoints).
- No OpenTelemetry, CloudWatch, Sentry, Datadog, or metrics exporters.
- No JSON log output format.
- No log aggregation or streaming.
- No React frontend or Model Ops console (deferred to PR 0030-ish / PR 0031-ish).
- No model upload endpoint (deferred).
- No model activation/reload/restart endpoint (deferred).
- No admin UI (deferred).
- No Node/npm/yarn/pnpm package manager files.
- No CORS configuration.

## Frontend and Model Ops future boundary

This PR explicitly does **not** include:

- **No React frontend** — No frontend code, no webpack/package.json, no Node toolchain.
- **No model upload endpoint** — No `POST /models` or similar; model package management is PR 0030-ish.
- **No model activation/reload/restart endpoint** — No `POST /models/activate`, `POST /server/reload`.
- **No admin UI** — No admin routes, no admin auth, no admin dashboard.
- **No package manager files** — No `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `node_modules/`.
- **No CORS broadening** — If tests require cross-origin access, that should be avoided. CORS can be added in a later PR when a frontend consumer exists.

**Future direction (preserved, not implemented)**:

- PR 0030-ish: Model package management API — upload, validate manifest/checksum/schema, stage, activate/reload.
- PR 0031-ish: React Model Ops Console MVP — consumes JSON APIs and logs/status, does not bypass model package validation.
- The request ID and structured logging foundation laid in this PR will support traceability across the Model Ops workflow.

## Rollback plan

1. **Revert `src/bremen/api/server.py`** — delete.
2. **Revert `tests/test_bremen_api_server.py`** — delete.
3. **Revert `src/bremen/__main__.py`** — remove the `serve` subcommand additions. The other CLI commands remain unchanged.
4. **Revert `tests/test_bremen_cli_entrypoint.py`** — remove the `serve`-related test cases.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only the 4 allowed files changed. |
| **HTTP server drift** | Standard-library only. No new dependencies. Routes match api_contract.md. JSON request/response. Status codes correct. |
| **CLI drift** | `serve` subcommand added with `--host` and `--port` flags. Lazy import inside handler. |
| **Safety drift** | No joblib/pickle/H5/AWS/Matador. No inference/training. No clinical claims. No dependency changes. |
| **Test drift** | 10 HTTP scenarios. `serve --help` check. Existing skeleton/contract/CLI tests pass. |
| **Validation drift** | All validation checks pass. Forbidden-pattern grep checks return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Implementation requires dependency changes (pyproject.toml, requirements.txt).
- Implementation requires Docker, Terraform, AWS, GitHub Actions, or deployment changes.
- Implementation requires model loading, H5 reads, preprocessing, or inference.
- Required HTTP behavior cannot be implemented with Python standard library in the allowed files.
- Plan cannot keep implementation files within the allowed list.
- Implementation claims clinical validation, diagnostic replacement, or production readiness.

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0026-runtime-http-service-runner/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0026-runtime-http-service-runner/reviews/plan-review.yml` (next step, by plan-review agent)
- **Plan.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Decisions summary

| Decision | Value |
|----------|-------|
| HTTP server approach | Standard-library `http.server` (Option A). No WSGI. No new dependencies. |
| CLI exposure | `python -m bremen serve --host 127.0.0.1 --port 8000`. Lazy import. |
| Server shutdown | Blocking `run_server()` for dev/smoke mode. No daemon/background mode in this PR. |
| Server behavior | JSON parsing/response. 202 for valid submit, 400 for invalid, 404 for unknown job/route, 405 for wrong method. |
| Structured logging | Python stdlib `logging` module. Key-value delimited format. No external logging deps. |
| Request ID | From `X-Request-ID` header or generated UUID. Included in response headers and JSON bodies. |
| Host default | `127.0.0.1` (localhost only, safe default). |
| Port default | `8000` (matches Terraform `container_port` variable). |
| Tests | 17 HTTP scenarios + 2 CLI checks + import safety AST checks. |
| Frontend | None. PR 0030-ish and PR 0031-ish reserved for Model Ops. |
| Model upload/activation | None. Deferred. |
| No changes | Docker, Terraform, CI, dependencies, config, examples, model code, API schemas, app.py. |

## Exact human commit instructions

1. Planner writes this file: `.project-memory/pr/0026-runtime-http-service-runner/PLAN.md`
2. Human runs: `git add .project-memory/pr/0026-runtime-http-service-runner/PLAN.md`
3. Human runs: `git commit -m "PR 0026 — Plan runtime HTTP service runner"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the four allowed files.

## Files read

- `ROADMAP.md`
- `.project-memory/project_contract.yml`
- `docs/api_contract.md`
- `src/bremen/api/app.py`
- `src/bremen/api/jobs.py`
- `src/bremen/api/schemas.py`
- `src/bremen/__main__.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_api_contract.py`
- `tests/test_bremen_cli_entrypoint.py`

## Files written

- `.project-memory/pr/0026-runtime-http-service-runner/PLAN.md` (this file)

## Boundary confirmations

- confirm: branch is `0026-runtime-http-service-runner`: yes
- confirm: no dependency changes planned: yes
- confirm: standard-library HTTP server only: yes
- confirm: no Docker/Terraform/CI changes planned: yes
- confirm: no model loading/inference planned: yes
- confirm: no H5/HDF5 reads planned: yes
- confirm: no clinical claims planned: yes
- confirm: no AWS/S3/Matador calls planned: yes
- confirm: `serve` CLI subcommand planned: yes
- confirm: structured logging with stdlib `logging` planned: yes
- confirm: request_id propagation (X-Request-ID header) planned: yes
- confirm: request_id in response headers and JSON planned: yes
- confirm: no OpenTelemetry/CloudWatch/Sentry/Datadog planned: yes
- confirm: no React/frontend planned: yes
- confirm: no model upload endpoint planned: yes
- confirm: no model activation/reload/restart planned: yes
- confirm: future Model Ops direction preserved for later PRs: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
