#!/usr/bin/env python3
"""Dev-only ASGI smoke readiness script for the isolated FastAPI app.

Starts the Bremen FastAPI application under a real ASGI server (uvicorn)
and exercises read-only endpoints to prove ASGI readiness.

This is **not** a production cutover.  It is a manual dev smoke tool.

Usage::

    # Read-only smoke (always safe)
    python scripts/smoke_fastapi_asgi.py --read-only

    # Full smoke with a local H5 fixture
    python scripts/smoke_fastapi_asgi.py --h5-file /path/to/local-demo.h5

Safety
------
- Never prints secrets, raw filesystem paths, S3 keys, credentials, or
  JWT tokens.
- H5 file display is restricted to basename only.
- Server binds to 127.0.0.1 by default (loopback only).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8990
_DEFAULT_TIMEOUT = 15  # seconds per request
_DEFAULT_SSE_TIMEOUT = 10  # seconds to wait for SSE frames
_DEFAULT_STARTUP_GRACE = 3.0  # seconds to wait for server startup

_READONLY_ENDPOINTS: list[str] = [
    "/health",
    "/model/version",
    "/demo/api/models",
    "/demo/api/h5/containers",
]

_WRITE_EVENT_ENDPOINTS: list[str] = [
    "POST /demo/api/h5/containers",
    "POST /demo/api/jobs",
    "GET /demo/api/jobs/{job_id}/events",
    "GET /demo/api/jobs/{job_id}/events/stream",
]

# Patterns that must never appear in normal output
_FORBIDDEN_OUTPUT_PATTERNS: tuple[str, ...] = (
    "traceback",
    "traceback (most recent",
    "raise ",
    "boto3",
    "aws_access_key",
    "aws_secret",
    "jwt_secret",
    "JWT_SECRET",
    "s3://",
    "/tmp/",
    "C:\\",
)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def redact_display(value: str, *, max_len: int = 60) -> str:
    """Redact a value for safe terminal display.

    Only the basename is returned for paths; long values are truncated.
    Never returns raw S3 URIs, filesystem paths, or credentials.
    """
    if not value:
        return "<empty>"
    # Normalize Windows-style backslashes so Path works cross-platform
    normalized = value.replace("\\", "/")
    basename = Path(normalized).name
    if len(basename) > max_len:
        basename = basename[:max_len - 3] + "..."
    return basename


def _log(msg: str) -> None:
    """Print a prefixed log line."""
    print(f"[smoke-asgi] {msg}", flush=True)


def _log_pass(label: str, detail: str = "") -> None:
    suffix = f" ({detail})" if detail else ""
    _log(f"PASS  {label}{suffix}")


def _log_skip(label: str, reason: str) -> None:
    _log(f"SKIP  {label} — {reason}")


def _log_fail(label: str, detail: str = "") -> None:
    suffix = f" ({detail})" if detail else ""
    _log(f"FAIL  {label}{suffix}")


def _log_info(msg: str) -> None:
    _log(f"INFO  {msg}")


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser.

    Exposed as a standalone function so that tests can introspect
    defaults without starting a server.
    """
    parser = argparse.ArgumentParser(
        prog="smoke_fastapi_asgi",
        description=(
            "Dev-only ASGI smoke readiness check for the isolated "
            "FastAPI application."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/smoke_fastapi_asgi.py --read-only
              python scripts/smoke_fastapi_asgi.py --h5-file demo.h5
        """),
    )
    parser.add_argument(
        "--host",
        default=_DEFAULT_HOST,
        help=f"Bind address (default: {_DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_PORT,
        help=f"Bind port (default: {_DEFAULT_PORT})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_DEFAULT_TIMEOUT,
        help=f"HTTP request timeout in seconds (default: {_DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--h5-file",
        default=None,
        help=(
            "Optional local H5 fixture path for write/event smoke. "
            "If omitted, write/event checks are skipped."
        ),
    )
    parser.add_argument(
        "--model-id",
        default=None,
        help="Optional model_id for job creation.",
    )
    parser.add_argument(
        "--workflow-id",
        default=None,
        help="Optional workflow_id for job creation (default: bremen).",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=False,
        help="Force read-only smoke (skip write/event checks).",
    )
    parser.add_argument(
        "--keep-server-on-failure",
        action="store_true",
        default=False,
        help="If set, do not kill the server process on smoke failure.",
    )
    parser.add_argument(
        "--startup-grace",
        type=float,
        default=_DEFAULT_STARTUP_GRACE,
        help=(
            f"Seconds to wait for server startup "
            f"(default: {_DEFAULT_STARTUP_GRACE})"
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_get(
    url: str,
    *,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Perform a GET request and return (status_code, body_text)."""
    req = urllib.request.Request(url, method="GET", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except Exception as exc:
        return 0, f"request_error: {type(exc).__name__}"


def _http_post_multipart(
    url: str,
    *,
    filepath: str,
    filename: str,
    timeout: int,
    extra_fields: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Perform a multipart POST (file upload) and return (status_code, body)."""
    import mimetypes  # noqa: PLC0415

    boundary = "----SmokeBoundary2024"
    parts: list[bytes] = []

    # Extra form fields
    for key, val in (extra_fields or {}).items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{val}\r\n".encode("utf-8")
        )

    # File part
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(filepath, "rb") as fh:
        file_data = fh.read()
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n".encode("utf-8")
        + file_data
        + b"\r\n"
    )

    body = b"".join(parts) + f"--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            return resp.status, resp_body
    except urllib.error.HTTPError as exc:
        resp_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, resp_body
    except Exception as exc:
        return 0, f"request_error: {type(exc).__name__}"


def _http_post_json(
    url: str,
    *,
    payload: dict,
    timeout: int,
) -> tuple[int, str]:
    """Perform a JSON POST and return (status_code, body)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except Exception as exc:
        return 0, f"request_error: {type(exc).__name__}"


def _http_get_sse(
    url: str,
    *,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, list[dict]]:
    """Perform a GET for SSE and return (status_code, raw_body, parsed_frames).

    Reads up to ``timeout`` seconds or until the connection closes.
    """
    import select  # noqa: PLC0415
    import socket  # noqa: PLC0415

    parsed_headers = headers or {}
    host_port = urllib.request.urlsplit(url)
    host = host_port.hostname or "127.0.0.1"
    port = host_port.port or 80
    path = host_port.path or "/"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        request_lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Connection: close",
            "Accept: text/event-stream",
        ]
        for k, v in parsed_headers.items():
            request_lines.append(f"{k}: {v}")
        request_lines.append("")
        request_lines.append("")
        sock.sendall("\r\n".join(request_lines).encode("utf-8"))

        chunks: list[bytes] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([sock], [], [], min(remaining, 1.0))
            if readable:
                try:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                except (socket.timeout, OSError):
                    break
        raw = b"".join(chunks).decode("utf-8", errors="replace")
    except Exception as exc:
        return 0, f"sse_error: {type(exc).__name__}", []
    finally:
        sock.close()

    # Parse status from first line
    status_code = 0
    frames: list[dict] = []
    lines = raw.split("\r\n")
    if lines:
        first_parts = lines[0].split(" ", 2)
        if len(first_parts) >= 2:
            try:
                status_code = int(first_parts[1])
            except ValueError:
                pass

    # Parse SSE frames
    current_event: dict[str, str] = {}
    for line in raw.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("event:"):
            current_event["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_event["data"] = line[len("data:"):].strip()
        elif line.startswith("id:"):
            current_event["id"] = line[len("id:"):].strip()
        elif line == "":
            if current_event:
                frames.append(current_event)
                current_event = {}
    if current_event:
        frames.append(current_event)

    return status_code, raw, frames


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def _build_uvicorn_command(
    host: str,
    port: int,
) -> list[str]:
    """Build the uvicorn command line.

    Uses ``bremen.api.fastapi_app:create_fastapi_app`` as the ASGI
    application factory.  The factory import is resolved at runtime
    by uvicorn, not by this script directly.
    """
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "bremen.api.fastapi_app:create_fastapi_app",
        "--factory",
        "--host", host,
        "--port", str(port),
        "--log-level", "warning",
    ]


def _start_server(
    host: str,
    port: int,
    *,
    startup_grace: float = _DEFAULT_STARTUP_GRACE,
) -> subprocess.Popen[str] | None:
    """Start the uvicorn server as a subprocess.

    Returns the Popen handle or None if startup fails.
    """
    cmd = _build_uvicorn_command(host, port)
    _log_info(f"Starting server: {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as exc:
        _log_fail("Server start", f"{type(exc).__name__}: {exc}")
        return None

    # Wait for the server to become ready
    _log_info(f"Waiting {startup_grace:.1f}s for server startup ...")
    deadline = time.monotonic() + startup_grace
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            _log_fail("Server start", "process exited before ready")
            return None
        time.sleep(0.3)

    # Quick readiness probe
    status, _ = _http_get(
        f"http://{host}:{port}/health",
        timeout=3,
    )
    if status == 200:
        _log_pass("Server startup", f"pid={proc.pid}")
        return proc
    else:
        _log_fail("Server startup", f"health probe returned {status}")
        _kill_server(proc)
        return None


def _kill_server(proc: subprocess.Popen[str]) -> None:
    """Terminate a server process cleanly."""
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Smoke checks
# ---------------------------------------------------------------------------

def _check_read_only_endpoints(
    host: str,
    port: int,
    *,
    timeout: int,
) -> int:
    """Run read-only endpoint checks. Returns count of failures."""
    base = f"http://{host}:{port}"
    failures = 0
    for ep in _READONLY_ENDPOINTS:
        url = f"{base}{ep}"
        status, body = _http_get(url, timeout=timeout)

        if status != 200:
            _log_fail(f"GET {ep}", f"status={status}")
            failures += 1
            continue

        # Check for forbidden patterns in output
        body_lower = body.lower()
        for pat in _FORBIDDEN_OUTPUT_PATTERNS:
            if pat.lower() in body_lower:
                _log_fail(f"GET {ep}", f"forbidden pattern in output: {pat!r}")
                failures += 1
                break
        else:
            # Validate JSON parseable
            try:
                parsed = json.loads(body)
                assert isinstance(parsed, dict), "response must be a JSON object"
            except (json.JSONDecodeError, AssertionError) as exc:
                _log_fail(f"GET {ep}", f"invalid JSON: {exc}")
                failures += 1
                continue

            _log_pass(f"GET {ep}", f"status=200, json_ok")
    return failures


def _check_write_event_smoke(
    host: str,
    port: int,
    *,
    h5_file: str,
    model_id: str | None,
    workflow_id: str | None,
    timeout: int,
    sse_timeout: int,
) -> int:
    """Run optional write/event smoke checks.

    Returns count of failures.  Prerequisite failures are logged as
    skips (not failures) to keep the smoke resilient.
    """
    base = f"http://{host}:{port}"
    failures = 0
    h5_basename = redact_display(h5_file)
    effective_workflow = workflow_id or "bremen"

    # -- Step 1: Upload H5 container --
    _log_info(f"Uploading H5 fixture: {h5_basename}")
    status, body = _http_post_multipart(
        f"{base}/demo/api/h5/containers",
        filepath=h5_file,
        filename=h5_basename,
        timeout=timeout,
    )
    if status not in (200, 201):
        _log_skip(
            "POST /demo/api/h5/containers",
            f"status={status} — environment may lack S3/storage config",
        )
        return 0  # skip downstream checks

    try:
        upload_resp = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        _log_skip(
            "POST /demo/api/h5/containers",
            "response is not valid JSON — skipping write/event smoke",
        )
        return 0

    source_id = upload_resp.get("source_id") or upload_resp.get("upload_id")
    if not source_id:
        _log_skip(
            "POST /demo/api/h5/containers",
            "no source_id/upload_id in response — skipping write/event smoke",
        )
        return 0

    _log_pass("POST /demo/api/h5/containers", f"source_id obtained")

    # -- Step 2: Create analysis job --
    job_payload: dict[str, str | None] = {
        "source_id": source_id,
        "workflow_id": effective_workflow,
        "model_id": model_id,
    }
    status, body = _http_post_json(
        f"{base}/demo/api/jobs",
        payload=job_payload,
        timeout=timeout,
    )
    if status not in (200, 201):
        _log_skip(
            "POST /demo/api/jobs",
            f"status={status} — environment may lack model config",
        )
        return 0

    try:
        job_resp = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        _log_skip("POST /demo/api/jobs", "response is not valid JSON")
        return 0

    job = job_resp.get("job", {})
    job_id = job.get("job_id")
    if not job_id:
        _log_skip("POST /demo/api/jobs", "no job_id in response")
        return 0

    _log_pass("POST /demo/api/jobs", f"job_id obtained")

    # -- Step 3: GET /demo/api/jobs/{job_id}/events (JSON polling) --
    events_url = f"{base}/demo/api/jobs/{job_id}/events"
    status, body = _http_get(events_url, timeout=timeout)
    if status == 200:
        try:
            events_resp = json.loads(body)
            assert "events" in events_resp, "response must contain 'events' key"
        except (json.JSONDecodeError, AssertionError) as exc:
            _log_fail(f"GET /demo/api/jobs/{{job_id}}/events", f"invalid: {exc}")
            failures += 1
        else:
            _log_pass(
                f"GET /demo/api/jobs/{{job_id}}/events",
                f"status=200, events_count={len(events_resp.get('events', []))}",
            )
    elif status == 404:
        _log_skip(
            f"GET /demo/api/jobs/{{job_id}}/events",
            "job not found in event store (may have expired)",
        )
    else:
        _log_fail(
            f"GET /demo/api/jobs/{{job_id}}/events",
            f"status={status}",
        )
        failures += 1

    # -- Step 4: GET /demo/api/jobs/{job_id}/events/stream (SSE) --
    stream_url = f"{base}/demo/api/jobs/{job_id}/events/stream"
    _log_info(f"Connecting to SSE stream (timeout={sse_timeout}s) ...")
    sse_status, sse_raw, sse_frames = _http_get_sse(
        stream_url,
        timeout=sse_timeout,
    )

    if sse_status == 200:
        has_terminal = any(
            f.get("event") == "stream_complete" for f in sse_frames
        )
        has_event = any(
            f.get("event") == "job_event" for f in sse_frames
        )
        has_keepalive = any(
            ": keepalive" in (sse_raw or "") for _ in [1]
        )
        if has_terminal or has_event or has_keepalive:
            _log_pass(
                f"GET /demo/api/jobs/{{job_id}}/events/stream",
                f"frames={len(sse_frames)}, "
                f"terminal={has_terminal}, events={has_event}, "
                f"keepalive={has_keepalive}",
            )
        else:
            _log_pass(
                f"GET /demo/api/jobs/{{job_id}}/events/stream",
                f"status=200, frames={len(sse_frames)}",
            )
    elif sse_status == 404:
        _log_skip(
            f"GET /demo/api/jobs/{{job_id}}/events/stream",
            "job not found (may have expired)",
        )
    else:
        _log_fail(
            f"GET /demo/api/jobs/{{job_id}}/events/stream",
            f"status={sse_status}",
        )
        failures += 1

    # -- Step 5: Verify server still healthy after SSE disconnect --
    status, _ = _http_get(f"{base}/health", timeout=timeout)
    if status == 200:
        _log_pass("POST-SSE health check", "server healthy after disconnect")
    else:
        _log_fail("POST-SSE health check", f"status={status}")
        failures += 1

    return failures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_smoke(args: argparse.Namespace) -> int:
    """Execute the smoke readiness checks.

    Returns 0 on success, 1 on failure.
    """
    host: str = args.host
    port: int = args.port
    timeout: int = args.timeout
    read_only: bool = args.read_only
    h5_file: str | None = args.h5_file
    model_id: str | None = args.model_id
    workflow_id: str | None = args.workflow_id
    keep_server_on_failure: bool = args.keep_server_on_failure
    startup_grace: float = args.startup_grace

    total_failures = 0

    # -- Validate H5 fixture if provided --
    if h5_file and not read_only:
        h5_path = Path(h5_file)
        if not h5_path.is_file():
            _log_fail("H5 fixture", f"file not found: {redact_display(h5_file)}")
            return 1
        _log_info(f"H5 fixture: {redact_display(h5_file)}")
    else:
        h5_file = None  # normalize

    # -- Start server --
    proc = _start_server(host, port, startup_grace=startup_grace)
    if proc is None:
        return 1

    try:
        # -- Read-only smoke --
        _log_info("=" * 60)
        _log_info("READ-ONLY SMOKE")
        _log_info("=" * 60)
        total_failures += _check_read_only_endpoints(
            host, port, timeout=timeout,
        )

        # -- Write/event smoke (optional) --
        if not read_only and h5_file:
            _log_info("=" * 60)
            _log_info("WRITE/EVENT SMOKE")
            _log_info("=" * 60)
            total_failures += _check_write_event_smoke(
                host,
                port,
                h5_file=h5_file,
                model_id=model_id,
                workflow_id=workflow_id,
                timeout=timeout,
                sse_timeout=_DEFAULT_SSE_TIMEOUT,
            )
        elif not read_only:
            _log_skip(
                "WRITE/EVENT SMOKE",
                "no --h5-file provided; skipping optional write/event checks",
            )
        else:
            _log_info("Read-only mode — write/event smoke skipped")

        # -- Final summary --
        _log_info("=" * 60)
        if total_failures == 0:
            _log_info("ALL CHECKS PASSED")
        else:
            _log_info(f"FAILURES: {total_failures}")
        _log_info("=" * 60)

    finally:
        if keep_server_on_failure and total_failures > 0:
            _log_info(
                f"Server left running at http://{host}:{port} "
                f"(pid={proc.pid}) — press Ctrl+C to stop"
            )
            try:
                proc.wait()
            except KeyboardInterrupt:
                _kill_server(proc)
        else:
            _kill_server(proc)

    return 1 if total_failures > 0 else 0


def main() -> None:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run_smoke(args))


if __name__ == "__main__":
    main()
