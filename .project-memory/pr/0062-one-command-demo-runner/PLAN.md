# PR 0062 — Plan One-command Bremen Demo Runner

Author: plan
Mode: planning only
Branch: 0062-one-command-demo-runner

## Objective

Add a `python -m bremen demo-run` command that starts a local Bremen HTTP service, runs the existing demo-smoke/evidence path against it, emits the reusable evidence bundle, and cleanly stops the server — all in one command.

This completes the demo trilogy:
- **PR0060** (`demo-smoke`) — Check a running service
- **PR0061** (`demo_evidence.py`) — Evidence bundle contract
- **PR0062** (`demo-run`) — One-command local demo

No AWS, Docker, Terraform, external services, H5 files, model artifacts, or real patient data required.

## Required reads — observed facts

### `src/bremen/demo_smoke.py` (PR0060 + PR0061)
- `run_demo_smoke(base_url, timeout, skip_prediction)` — calls HTTP service and returns structured result.
- Already includes evidence bundle via `build_demo_evidence_bundle()` at the end.
- Already has `technical_demo_only: True`, `request_id`, `checks`, `health`, `model_version`, `prediction`, `warnings`, `status`, `timestamp`, `evidence`.

### `src/bremen/demo_evidence.py` (PR0061)
- `build_demo_evidence_bundle(...)` — evidence bundle factory.
- `build_demo_feature_artifact_payload()` — synthetic 15-feature artifact.
- `validate_demo_evidence_bundle()` — bundle invariant validator.

### `src/bremen/api/server.py`
- `run_server(host, port, version)` — blocking HTTP server.
- `_make_handler(job_store, version, *, load_model=False)` — handler factory with optional synthetic model loading.
- `_load_synthetic_model()` — loads a minimal `portable_logreg` model with `coef=[0.1]*15`, `intercept=0.0`, `threshold=0.5`.
- `run_server()` calls `ModelState.load_at_startup()` which requires env vars. The synthetic model path is in `_load_synthetic_model()` called via `_make_handler(load_model=True)`.

### `src/bremen/api/app.py`
- `handle_submit_prediction()` — checks `ModelState.is_ready()` before accepting jobs.
- Prediction endpoint requires model to be loaded (HTTP 503 if not).

### `src/bremen/__main__.py`
- CLI pattern: `_add_X_subcommand()`, `_handle_X(args)`, `BUILTIN_COMMANDS` tuple.
- Lazy imports inside handlers.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_run.py`** — NEW. One-command demo runner module.
2. **`src/bremen/__main__.py`** — MODIFY. Add `demo-run` subcommand (small: subparser + handler).
3. **`tests/test_bremen_demo_run.py`** — NEW. Tests for the one-command demo runner.
4. **`tests/test_bremen_demo_smoke.py`** — No change needed (existing tests pass).
5. **`tests/test_bremen_demo_evidence.py`** — No change needed (existing tests pass).
6. **`tests/test_bremen_cli_entrypoint.py`** — MODIFY. Add CLI help tests for `demo-run`.

## Forbidden files

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
- `docs/**`, `ROADMAP.md`

## Exact implementation scope

### 1. `src/bremen/demo_run.py` — One-command demo runner

A stdlib-only module. No new dependencies. Starts a local server, runs demo-smoke, returns evidence bundle.

```python
"""One-command Bremen demo runner.

Starts a local Bremen HTTP service, runs the existing demo-smoke/evidence
path against it, and produces the reusable evidence bundle — all in one
command.

No AWS, Docker, Terraform, external services, H5 files, model artifacts,
or real patient data required.

Standard library only — no third-party dependencies.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import HTTPServer
from typing import Any
```

**Architecture**:

The module creates a tiny server lifecycle wrapper. It does NOT modify or duplicate the existing `run_server()` or `_make_handler()` — it reuses them directly.

**`_find_free_port()`** — same pattern as existing test fixtures:

```python
def _find_free_port() -> int:
    """Return an OS-assigned free port bound to localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
```

**`_start_local_server(host, port, load_model)`** — starts server in a daemon thread:

```python
def _start_local_server(
    host: str = "127.0.0.1",
    port: int | None = None,
    *,
    load_model: bool = True,
) -> tuple[HTTPServer, int, threading.Thread]:
    """Start a Bremen HTTP server on an ephemeral port in a daemon thread.

    Returns
    -------
    A tuple of (server, actual_port, thread).
    The caller should call ``server.shutdown()`` and ``thread.join()``
    on cleanup.
    """
    if port is None:
        port = _find_free_port()

    from .api.jobs import InMemoryJobStore  # noqa: PLC0415
    from .api.server import _make_handler  # noqa: PLC0415

    job_store = InMemoryJobStore()
    handler = _make_handler(job_store, version=DEMO_RUN_VERSION, load_model=load_model)
    server = HTTPServer((host, port), handler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server, port, thread
```

Note: This approach bypasses `run_server()` (which is blocking and calls `ModelState.load_at_startup()` with env-var-based model loading). Instead, it calls `_make_handler(load_model=True)` which calls `_load_synthetic_model()` — the synthetic model path that works without env vars. This is the same pattern used by existing tests in `test_bremen_api_server.py`.

**`_wait_for_health(base_url, timeout, poll_interval)`** — bounded polling for /health:

```python
def _wait_for_health(
    base_url: str,
    timeout: int = 30,
    poll_interval: float = 0.5,
) -> bool:
    """Poll the health endpoint until it returns 200 or timeout expires.

    Returns True if health check passed, False on timeout.
    """
    from urllib.request import Request, urlopen

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = Request(f"{base_url}/health")
            resp = urlopen(req, timeout=max(1, int(deadline - time.monotonic())))
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False
```

**`run_demo(base_url=None, timeout=30, skip_prediction=False)`** — main function:

```python
DEMO_RUN_VERSION = "v0.1"


def run_demo(
    base_url: str | None = None,
    timeout: int = 30,
    skip_prediction: bool = False,
) -> dict[str, Any]:
    """Run the one-command demo: start local server, run smoke, emit bundle.

    Parameters
    ----------
    base_url : Optional explicit base URL. If provided, assumes the
        service is already running and does NOT start a local server.
        If ``None`` (default), starts a local server on an ephemeral port.
    timeout : Timeout in seconds for server startup and smoke checks.
    skip_prediction : If ``True``, skip the prediction check.

    Returns
    -------
    The demo-smoke result dict including the ``evidence`` bundle.
    """
    if base_url is not None:
        # Service is already running — just run smoke
        from .demo_smoke import run_demo_smoke
        return run_demo_smoke(
            base_url=base_url,
            timeout=timeout,
            skip_prediction=skip_prediction,
        )

    # Start local server
    server, port, thread = _start_local_server(
        host="127.0.0.1",
        load_model=True,
    )
    local_url = f"http://127.0.0.1:{port}"

    try:
        # Wait for server to become ready
        healthy = _wait_for_health(local_url, timeout=timeout)
        if not healthy:
            return {
                "technical_demo_only": True,
                "status": "fail",
                "error": (
                    f"Local server did not become healthy "
                    f"within {timeout}s"
                ),
                "timestamp": __import__(
                    "datetime", fromlist=["datetime"]
                ).datetime.now(
                    __import__("datetime", fromlist=["timezone"]
                ).timezone.utc).isoformat(),
            }

        # Run demo-smoke against local server
        from .demo_smoke import run_demo_smoke

        return run_demo_smoke(
            base_url=local_url,
            timeout=timeout,
            skip_prediction=skip_prediction,
        )
    finally:
        # Clean up server
        server.shutdown()
        thread.join(timeout=5)
```

**CLI entry point**:

```python
def main(argv: list[str] | None = None) -> int:
    """Run the one-command demo.

    Parameters
    ----------
    argv : Command-line args (excluding program name).

    Returns
    -------
    0 if overall status is "pass" or "partial", 1 if "fail".
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="bremen demo-run",
        description=(
            "Start a local Bremen HTTP service and run demo smoke checks "
            "against it. No AWS, Docker, Terraform, or external services "
            "required."
        ),
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help=(
            "Base URL of an already-running Bremen service. "
            "If provided, does not start a local server."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--skip-prediction",
        action="store_true",
        help="Skip the prediction check.",
    )

    args = parser.parse_args(argv)
    result = run_demo(
        base_url=args.base_url,
        timeout=args.timeout,
        skip_prediction=args.skip_prediction,
    )

    # Print JSON output
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Print human-readable summary
    status_str = result.get("status", "fail").upper()
    print(f"\nDemo Run Result: {status_str}")
    checks = result.get("checks", {})
    for key, value in checks.items():
        print(f"  {key}: {value}")
    warnings = result.get("warnings", [])
    if warnings:
        print("  Warnings:")
        for w in warnings:
            print(f"    - {w}")
    print(f"  request_id: {result.get('request_id', 'N/A')}")
    evidence = result.get("evidence", {})
    if evidence:
        print(f"  evidence_version: {evidence.get('evidence_version', 'N/A')}")
        print(f"  product: {evidence.get('product', 'N/A')}")

    return 0 if result.get("status") in ("pass", "partial") else 1
```

### 2. `src/bremen/__main__.py` — Add `demo-run` subcommand

Add a new subcommand following the existing pattern:

```python
BUILTIN_COMMANDS = ("preprocess", "serve", "demo_smoke")  # add "demo_run"
```

```python
def _add_demo_run_subcommand(subparsers) -> None:
    demo_run = subparsers.add_parser(
        "demo-run",
        help=(
            "One-command demo: start local server, run smoke checks, "
            "produce evidence bundle."
        ),
    )
    demo_run.add_argument(
        "--base-url",
        type=str,
        default=None,
        help=(
            "Base URL of an already-running Bremen service. "
            "If not provided, starts a local server."
        ),
    )
    demo_run.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds (default: 30).",
    )
    demo_run.add_argument(
        "--skip-prediction",
        action="store_true",
        help="Skip the prediction check.",
    )
    demo_run.set_defaults(_cmd_handler="demo_run")


def _handle_demo_run(args) -> int:
    from .demo_run import main as demo_run_main
    cli_args = [f"--timeout={args.timeout}"]
    if args.base_url:
        cli_args.append(f"--base-url={args.base_url}")
    if args.skip_prediction:
        cli_args.append("--skip-prediction")
    return demo_run_main(cli_args)
```

Call `_add_demo_run_subcommand(subparsers)` in `build_parser()` and add `"demo_run"` handler branch in `main()`.

### 3. `tests/test_bremen_demo_run.py` — Tests

Follow the same pattern as existing server tests: use `_make_handler()` with `load_model=True`, start on port 0, call `run_demo()` with the explicit `--base-url`.

**Test scenarios**:

1. **CLI help** — `python -m bremen demo-run --help` exits 0.
2. **CLI in main help** — `python -m bremen --help` lists `demo-run`.
3. **`run_demo()` with explicit base URL** — Start a test server, call `run_demo(base_url=...)`; verify health/model checks pass.
4. **`run_demo()` without base URL starts local server** — Call `run_demo()` without args; verify it returns a result with `status` field.
5. **Evidence bundle present** — Result dict contains `evidence` key with `technical_demo_only: True`.
6. **`technical_demo_only` field** — Present and `True`.
7. **Request ID present** — `request_id` field of correct type.
8. **Server startup failure** — With short timeout on unavailable port (simulate by providing a non-existent base URL).
9. **`--skip-prediction`** — Pass through to demo-smoke; prediction check skipped.
10. **Server cleanup** — After `run_demo()` returns, no lingering server process/thread.
11. **JSON serializable** — `json.dumps(result)` succeeds.
12. **No fixed port conflict** — Two sequential calls use different ports.
13. **`demo-run` CLI runs end-to-end** — Full subprocess test: `python -m bremen demo-run --skip-prediction`.

### 4. `tests/test_bremen_cli_entrypoint.py` — Add CLI help tests

Add test cases:
- `test_demo_run_help_exits_0` — `python -m bremen demo-run --help` exits 0.
- `test_demo_run_in_main_help` — `python -m bremen --help` lists `demo-run`.

## Non-goals

- No new HTTP routes or API contract changes.
- No model loading changes — uses existing `_load_synthetic_model()`.
- No inference expansion — uses existing synthetic model.
- No H5 reads or writes — prediction check works via existing synthetic model path.
- No AWS/S3 calls.
- No Matador resolver implementation.
- No clinical report template.
- No deployment mutation (Terraform, Docker, CI/CD).
- No React/frontend.
- No new dependencies.
- No docs/ROADMAP updates.
- No real patient data.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization — uses existing `_load_synthetic_model()` which is already approved in the codebase.
- No new `joblib.load()` or `pickle.load()` — no new deserialization added.
- No H5 reads — the demo-run does not read H5 files; the synthetic model path uses feature-artifact-style inference which is number-based.
- No H5 writes.
- No preprocessing expansion.
- No AWS/S3 network calls — only stdlib `urllib.request` to localhost.
- No Matador resolver implementation.
- No clinical report template addition.
- No clinical diagnosis claims.
- `technical_demo_only: True` in every output.
- No real patient data.
- No Aramis references.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_demo_evidence.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_api_skeleton.py
if test -f tests/test_bremen_dependency_hygiene.py; then \
  python -m pytest -q tests/test_bremen_dependency_hygiene.py; \
else echo "SKIP missing tests/test_bremen_dependency_hygiene.py"; fi
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
```

### Forbidden-pattern grep checks

```bash
# No Aramis dependency or product labels
grep -R -I -n "Aramis\|aramis\|M2Q\|BENIGN vs CANCER" \
  src/bremen/demo_run.py src/bremen/demo_smoke.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_run.py tests/test_bremen_demo_smoke.py tests/test_bremen_demo_evidence.py || true
# Expected: no output

# No clinical/replacement claims
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen/demo_run.py src/bremen/demo_smoke.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_run.py tests/test_bremen_demo_smoke.py tests/test_bremen_demo_evidence.py || true
# Expected: no output (negative-test assertion strings in tests allowed with justification)

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen/demo_run.py src/bremen/demo_smoke.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_run.py tests/test_bremen_demo_smoke.py tests/test_bremen_demo_evidence.py || true
# Expected: no output (pre-existing joblib in modeling.py/mlflow_tracking.py not in scope)

# No H5 dependency in demo-run/evidence
grep -R -I -n "\.h5\|\.hdf5\|h5py" \
  src/bremen/demo_run.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_run.py tests/test_bremen_demo_evidence.py || true
# Expected: no output

# No AWS/network client deps (stdlib urllib localhost is allowed)
grep -R -I -n "boto3\|botocore\|requests\|httpx" \
  src/bremen/demo_run.py src/bremen/demo_smoke.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_run.py tests/test_bremen_demo_smoke.py tests/test_bremen_demo_evidence.py || true
# Expected: no output

# No new web framework
grep -R -I -n "FastAPI\|Flask\|uvicorn\|gunicorn\|starlette\|aiohttp\|django" \
  src tests requirements.txt pyproject.toml || true
# Expected: no output

# Forbidden files unchanged
git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training \
  requirements.txt pyproject.toml config/training frontend web ui \
  package.json package-lock.json yarn.lock pnpm-lock.yaml tests/data

# Docs/ROADMAP unchanged
git diff --name-only -- docs ROADMAP.md
# Expected: no output

# No model/data artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true
# Expected: no output

# No .DS_Store
find . -name ".DS_Store" -print
```

## Platform safety decisions

| Decision | Value |
|----------|-------|
| Server startup | Reuses `_make_handler(load_model=True)` — same pattern as existing tests. |
| Model loading | Uses existing `_load_synthetic_model()` — approved, creates temp file + `joblib.dump()` + `ModelState.load_at_startup()`. |
| Port binding | `port=0` (ephemeral) — no fixed-port conflicts. |
| Server lifecycle | Daemon thread with `server.shutdown()` + `thread.join()` in `finally` block. |
| Health wait | Bounded polling with configurable timeout and poll interval. |
| Base URL override | `--base-url` flag allows using an already-running service (skips local server). |
| Evidence bundle | Included automatically via existing `demo_smoke.py` call to `build_demo_evidence_bundle()`. |
| Output | JSON to stdout with human-readable summary. |
| Exit code | 0 for pass/partial, 1 for fail. |

## Rollback plan

1. **Revert `src/bremen/demo_run.py`** — delete.
2. **Revert `src/bremen/__main__.py`** — remove `demo-run` subcommand additions.
3. **Revert `tests/test_bremen_demo_run.py`** — delete.
4. **Revert `tests/test_bremen_cli_entrypoint.py`** — remove `demo-run` CLI test cases.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 4 allowed files changed. No forbidden files. |
| **Demo-run drift** | Stdlib-only. Reuses `_make_handler()` / `_load_synthetic_model()` — no new server logic. |
| **Server lifecycle drift** | Uses existing `HTTPServer` + daemon thread pattern from existing tests. No blocking `run_server()` call. |
| **Safety drift** | No unsafe deserialization, no H5, no AWS, no clinical claims. |
| **Test drift** | 13 new demo-run tests + 2 CLI tests. Existing tests pass unchanged. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Implementation requires new dependencies.
- Implementation requires Terraform, Docker, GitHub Actions, or deployment changes.
- Implementation adds new HTTP routes or changes the API contract.
- Implementation introduces unsafe model deserialization.
- Implementation reads H5 files.
- Implementation hardcodes secrets, account IDs, or production URLs.
- Implementation cannot be completed within the allowed files.
- Implementation becomes docs-only.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Module | `src/bremen/demo_run.py` — stdlib-only one-command runner. |
| CLI command | `python -m bremen demo-run [--base-url URL] [--timeout SECONDS] [--skip-prediction]` |
| Server startup | `_make_handler(load_model=True)` — reuses existing synthetic model path. |
| Port binding | `port=0` (ephemeral, OS-assigned) — no conflict. |
| Health wait | Bounded polling (`_wait_for_health`) with configurable timeout + 0.5s interval. |
| Smoke integration | Calls `run_demo_smoke()` from `demo_smoke.py` — no duplicated logic. |
| Evidence bundle | Included automatically via existing `demo_smoke.py` → `build_demo_evidence_bundle()`. |
| Base URL override | `--base-url` for already-running service. |
| Output | JSON + human-readable summary. |
| Exit code | 0 for pass/partial, 1 for fail. |
| Dependencies | None new. |

## Files read

- `ROADMAP.md`
- `docs/api_contract.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `docs/adr/0012-system-of-record-boundary.md`
- `src/bremen/__main__.py`
- `src/bremen/demo_smoke.py`
- `src/bremen/demo_evidence.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `src/bremen/api/jobs.py`
- `src/bremen/api/schemas.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_demo_evidence.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_dependency_hygiene.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0062-one-command-demo-runner/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0062 planned as one-command Bremen demo runner: yes
- confirm: demo-run starts local service: yes
- confirm: demo-run uses existing demo-smoke/evidence path: yes
- confirm: demo evidence is not disposable: yes (builds on versioned evidence bundle)
- confirm: product-owner demo value planned: yes
- confirm: technical_demo_only preserved: yes
- confirm: request_id/logging behavior preserved: yes (via demo-smoke)
- confirm: localhost/ephemeral-port lifecycle planned: yes
- confirm: deployed URL compatibility remains in demo-smoke: yes (via `--base-url` override)
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: no React/frontend planned: yes
- confirm: no new dependencies planned: yes
- confirm: no unsafe model loading planned: yes (reuses existing approved `_load_synthetic_model()`)
- confirm: no H5 mutation planned: yes
- confirm: no real patient data planned: yes
- confirm: no Aramis dependency planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
