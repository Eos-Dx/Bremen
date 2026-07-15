"""One-command Bremen demo runner.

Starts a local Bremen HTTP service, runs the existing demo-smoke/evidence
path against it, and produces the reusable evidence bundle -- all in one
command.

No AWS, Docker, Terraform, external services, H5 files, model artifacts,
or real patient data required.

Standard library only -- no third-party dependencies.

Safety
------
- No model loading or deserialization (reuses existing ``_load_synthetic_model()``).
- No H5 reads or writes.
- No AWS/S3/network clients (stdlib ``urllib.request`` to localhost only).
- No clinical diagnosis or replacement claims.
- ``technical_demo_only: true`` in every output.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import HTTPServer
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_RUN_VERSION = "v0.1"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    """Return an OS-assigned free port bound to localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_local_server(
    host: str = "127.0.0.1",
    port: int | None = None,
    *,
    load_model: bool = True,
) -> tuple[HTTPServer, int, threading.Thread]:
    """Start a Bremen HTTP server on an ephemeral port in a daemon thread.

    Parameters
    ----------
    host : Host address to bind to (default ``127.0.0.1``).
    port : Specific port number, or ``None`` to use a free ephemeral port.
    load_model : If ``True``, load the synthetic model for inference demo.

    Returns
    -------
    A tuple of ``(server, actual_port, thread)``.
    The caller must call ``server.shutdown()`` and ``thread.join()``
    on cleanup.
    """
    if port is None:
        port = _find_free_port()

    from .api.jobs import InMemoryJobStore  # noqa: PLC0415
    from .api.server import _make_handler  # noqa: PLC0415

    job_store = InMemoryJobStore()
    handler = _make_handler(
        job_store, version=DEMO_RUN_VERSION, load_model=load_model
    )
    server = HTTPServer((host, port), handler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server, port, thread


def _wait_for_health(
    base_url: str,
    timeout: int = 30,
    poll_interval: float = 0.5,
) -> bool:
    """Poll the health endpoint until it returns 200 or timeout expires.

    Parameters
    ----------
    base_url : Base URL of the Bremen HTTP service.
    timeout : Maximum time in seconds to wait.
    poll_interval : Time in seconds between poll attempts.

    Returns
    -------
    ``True`` if health check passed (HTTP 200), ``False`` on timeout.
    """
    from urllib.request import Request, urlopen  # noqa: PLC0415

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            remaining = int(deadline - time.monotonic())
            req = Request(f"{base_url}/health")
            resp = urlopen(req, timeout=max(1, remaining))
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_demo(
    base_url: str | None = None,
    timeout: int = 30,
    skip_prediction: bool = False,
) -> dict[str, Any]:
    """Run the one-command demo.

    If *base_url* is provided, assumes the service is already running and
    does NOT start a local server.  If *base_url* is ``None`` (default),
    starts a local Bremen HTTP service on an ephemeral port.

    The demo runs the existing demo-smoke checks against the service
    and returns the result including the PR0061 evidence bundle.

    Parameters
    ----------
    base_url :
        Optional explicit base URL of an already-running service.
        If ``None``, a local server is started automatically.
    timeout :
        Timeout in seconds for server startup and smoke checks.
    skip_prediction :
        If ``True``, skip the prediction check.

    Returns
    -------
    A dict with keys: ``base_url``, ``request_id``, ``checks``,
    ``health``, ``model_version``, ``prediction``, ``warnings``,
    ``status``, ``technical_demo_only``, ``timestamp``, ``evidence``.
    """
    if base_url is not None:
        # Service is already running -- just run smoke
        from .demo_smoke import run_demo_smoke  # noqa: PLC0415

        return run_demo_smoke(
            base_url=base_url,
            timeout=timeout,
            skip_prediction=skip_prediction,
        )

    # Start local server with synthetic model
    server, port, thread = _start_local_server(
        host="127.0.0.1",
        load_model=True,
    )
    local_url = f"http://127.0.0.1:{port}"

    try:
        # Wait for server to become healthy
        healthy = _wait_for_health(local_url, timeout=timeout)
        if not healthy:
            from datetime import datetime, timezone  # noqa: PLC0415

            return {
                "technical_demo_only": True,
                "status": "fail",
                "base_url": local_url,
                "error": (
                    f"Local server did not become healthy "
                    f"within {timeout}s"
                ),
                "checks": {"server_startup": "fail"},
                "warnings": [
                    "Server startup failed or timed out"
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Run demo-smoke against local server
        from .demo_smoke import run_demo_smoke  # noqa: PLC0415

        return run_demo_smoke(
            base_url=local_url,
            timeout=timeout,
            skip_prediction=skip_prediction,
        )
    finally:
        # Clean up server -- guaranteed to run
        server.shutdown()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the one-command demo from the CLI.

    Parameters
    ----------
    argv : Command-line args (excluding program name).

    Returns
    -------
    0 if overall status is ``"pass"`` or ``"partial"``, 1 if ``"fail"``.
    """
    import argparse  # noqa: PLC0415

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
        print(
            "  evidence_version: "
            f"{evidence.get('evidence_version', 'N/A')}"
        )
        print(f"  product: {evidence.get('product', 'N/A')}")

    return 0 if result.get("status") in ("pass", "partial") else 1


if __name__ == "__main__":
    raise SystemExit(main())
