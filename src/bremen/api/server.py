"""Standard-library HTTP service runner for the Bremen API.

Uses Python's built-in ``http.server`` module.  No web framework
dependency.  Designed for local dev/smoke testing and container
smoke validation only — not production serving.

Routes
------
- ``GET /health`` — Service health.
- ``GET /model/version`` — Model metadata (not_configured).
- ``POST /predictions`` — Submit async prediction job.
- ``GET /predictions/{job_id}`` — Poll job status.

Safety
------
- No model loading / inference.
- No H5/HDF5 reads.
- No AWS/S3/network client calls.
- No ``joblib`` / ``pickle`` imports.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from .app import (
    handle_health,
    handle_model_version,
    handle_submit_prediction,
    handle_get_prediction,
)
from .jobs import InMemoryJobStore

logger = logging.getLogger(__name__)

_JOB_ID_PATTERN = re.compile(
    r"^/predictions/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})$"
)

_STATUS_CODES = {
    "ok": 200,
    "created": 201,
    "accepted": 202,
    "bad_request": 400,
    "not_found": 404,
    "method_not_allowed": 405,
    "server_error": 500,
}


def _make_handler(
    job_store: InMemoryJobStore,
    version: str | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Return a ``BaseHTTPRequestHandler`` subclass bound to *job_store*.

    Parameters
    ----------
    job_store : An ``InMemoryJobStore`` instance shared across requests.
    version : Optional version string for health response.

    Returns
    -------
    A handler class suitable for ``HTTPServer``.
    """

    class _BremenHandler(BaseHTTPRequestHandler):
        """Single-request HTTP handler.  Shared *job_store* from closure."""

        # ---- Request ID ----

        def _get_request_id(self) -> str:
            """Return the request ID from X-Request-ID header or generate one."""
            return self.headers.get("X-Request-ID") or str(uuid.uuid4())

        # ---- Structured logging ----

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Override default log_message to use structured logging.

            This replaces the default ``BaseHTTPRequestHandler.log_message``
            behaviour with structured key=value logging through ``logger``.
            Each log line includes request_id, method, path, status, and
            available contextual fields (job_id, error).
            """
            # Format the default status-line message (
            #   e.g. '"GET /health HTTP/1.1" 200 -'
            # )
            message = format % args
            # Extract status from args[1] (the code passed by log_request)
            status = args[1] if len(args) >= 2 else "?"
            extra_parts = []
            job_id = getattr(self, "_job_id", None)
            error = getattr(self, "_error", None)
            if job_id:
                extra_parts.append(f"job_id={job_id}")
            if error:
                extra_parts.append(f"error={error}")
            extra_str = " ".join(extra_parts)
            logger.info(
                "request_id=%(request_id)s method=%(method)s "
                "path=%(path)s status=%(status)s %(extra)s",
                {
                    "request_id": getattr(self, "_request_id", "?"),
                    "method": getattr(self, "command", "?"),
                    "path": getattr(self, "path", "?"),
                    "status": status,
                    "extra": extra_str,
                },
            )

        # ---- Route dispatch ----

        def _send_json(
            self, data: Any, status: int = 200
        ) -> None:
            """Serialize *data* as JSON and write the response."""
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            request_id = self._get_request_id()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Request-ID", request_id)
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict[str, Any] | None:
            """Read and parse the request body as JSON.

            Returns ``None`` if the body is empty or not valid JSON.
            """
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return None
            raw = self.rfile.read(content_length)
            try:
                return dict(json.loads(raw))
            except (json.JSONDecodeError, ValueError):
                return None

        # ---- Request handler ----

        def _log_and_send(
            self, data: Any, status: int = 200,
            job_id: str | None = None, error: str | None = None,
        ) -> None:
            """Send JSON response and log the request summary.

            Parameters
            ----------
            data : Response body dict.
            status : HTTP status code.
            job_id : Optional job ID for request correlation.
            error : Optional error reason for controlled failures.
            """
            request_id = self._get_request_id()
            data["request_id"] = request_id
            self._request_id = request_id
            self._job_id = job_id
            self._error = error
            self._send_json(data, status=status)

        def _log_and_send_error(
            self, message: str, status: int = 400,
            job_id: str | None = None,
        ) -> None:
            """Send an error JSON response with request_id."""
            self._log_and_send(
                {"error": message},
                status=status, job_id=job_id, error=message,
            )

        def do_GET(self) -> None:
            self._request_id = self._get_request_id()
            self._job_id = None
            self._error = None

            if self.path == "/health":
                resp = handle_health(version=version)
                self._log_and_send({
                    "status": resp.status,
                    "service": resp.service,
                    "version": resp.version,
                    "timestamp": resp.timestamp,
                })
            elif self.path == "/model/version":
                resp = handle_model_version()
                self._log_and_send({
                    "model_configured": resp.model_configured,
                    "model_version": resp.model_version,
                    "model_checksum": resp.model_checksum,
                    "feature_schema_version": resp.feature_schema_version,
                    "threshold_version": resp.threshold_version,
                    "threshold_value": resp.threshold_value,
                    "qc_criteria_version": resp.qc_criteria_version,
                    "model_status": resp.model_status,
                })
            elif (match := _JOB_ID_PATTERN.match(self.path)) is not None:
                job_id = match.group(1)
                self._job_id = job_id
                resp = handle_get_prediction(job_id, job_store)
                if resp.status == "not_found":
                    self._log_and_send({
                        "job_id": resp.job_id,
                        "status": resp.status,
                        "submitted_at": resp.submitted_at,
                        "updated_at": resp.updated_at,
                    }, status=404, job_id=job_id, error="Job not found")
                else:
                    self._log_and_send({
                        "job_id": resp.job_id,
                        "status": resp.status,
                        "submitted_at": resp.submitted_at,
                        "updated_at": resp.updated_at,
                        "result": resp.result,
                        "error": resp.error,
                    }, job_id=job_id)
            else:
                self._log_and_send_error(
                    f"Not found: {self.path}", status=404,
                )

        def do_POST(self) -> None:
            self._request_id = self._get_request_id()
            self._job_id = None
            self._error = None

            if self.path == "/predictions":
                body = self._read_json_body()
                if body is None:
                    self._log_and_send_error(
                        "Invalid or missing JSON body", status=400,
                    )
                    return

                try:
                    resp = handle_submit_prediction(body, job_store)
                except ValueError as exc:
                    self._log_and_send_error(
                        str(exc), status=400,
                    )
                    return

                self._job_id = resp.job_id
                self._log_and_send({
                    "job_id": resp.job_id,
                    "status": resp.status,
                    "submitted_at": resp.submitted_at,
                    "links": resp.links,
                }, status=202, job_id=resp.job_id)
            else:
                self._log_and_send_error(
                    f"Not found: {self.path}", status=404,
                )

        def do_PUT(self) -> None:
            self._request_id = self._get_request_id()
            self._job_id = None
            self._error = None
            self._log_and_send_error(
                "Method not allowed", status=405,
            )

        def do_DELETE(self) -> None:
            self._request_id = self._get_request_id()
            self._job_id = None
            self._error = None
            self._log_and_send_error(
                "Method not allowed", status=405,
            )

        def do_PATCH(self) -> None:
            self._request_id = self._get_request_id()
            self._job_id = None
            self._error = None
            self._log_and_send_error(
                "Method not allowed", status=405,
            )

    return _BremenHandler


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    version: str | None = None,
) -> None:
    """Start the Bremen HTTP API server (blocking).

    Parameters
    ----------
    host : Host address to bind to (default ``127.0.0.1``).
    port : Port number to listen on (default ``8000``).
    version : Optional version string for health endpoint.
    """
    job_store = InMemoryJobStore()
    handler = _make_handler(job_store, version=version)
    server = HTTPServer((host, port), handler)

    print(f"Bremen API server listening on http://{host}:{port}")
    print("Dev/smoke mode only. Not for production use.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Bremen API server.")
        server.server_close()
