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
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from .app import (
    handle_health,
    handle_model_version,
    handle_submit_prediction,
    handle_get_prediction,
)
from .jobs import InMemoryJobStore

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

        # Silence per-request log output
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

        # ---- Route dispatch ----

        def _send_json(
            self, data: Any, status: int = 200
        ) -> None:
            """Serialize *data* as JSON and write the response."""
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
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

        def do_GET(self) -> None:
            if self.path == "/health":
                resp = handle_health(version=version)
                self._send_json({
                    "status": resp.status,
                    "service": resp.service,
                    "version": resp.version,
                    "timestamp": resp.timestamp,
                })
            elif self.path == "/model/version":
                resp = handle_model_version()
                self._send_json({
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
                resp = handle_get_prediction(job_id, job_store)
                if resp.status == "not_found":
                    self._send_json({
                        "job_id": resp.job_id,
                        "status": resp.status,
                        "submitted_at": resp.submitted_at,
                        "updated_at": resp.updated_at,
                    }, status=404)
                else:
                    self._send_json({
                        "job_id": resp.job_id,
                        "status": resp.status,
                        "submitted_at": resp.submitted_at,
                        "updated_at": resp.updated_at,
                        "result": resp.result,
                        "error": resp.error,
                    })
            else:
                self._send_json(
                    {"error": f"Not found: {self.path}"},
                    status=404,
                )

        def do_POST(self) -> None:
            if self.path == "/predictions":
                body = self._read_json_body()
                if body is None:
                    self._send_json(
                        {"error": "Invalid or missing JSON body"},
                        status=400,
                    )
                    return

                try:
                    resp = handle_submit_prediction(body, job_store)
                except ValueError as exc:
                    self._send_json(
                        {"error": str(exc)},
                        status=400,
                    )
                    return

                self._send_json({
                    "job_id": resp.job_id,
                    "status": resp.status,
                    "submitted_at": resp.submitted_at,
                    "links": resp.links,
                }, status=202)
            else:
                self._send_json(
                    {"error": f"Not found: {self.path}"},
                    status=404,
                )

        def do_PUT(self) -> None:
            self._send_json(
                {"error": "Method not allowed"},
                status=405,
            )

        def do_DELETE(self) -> None:
            self._send_json(
                {"error": "Method not allowed"},
                status=405,
            )

        def do_PATCH(self) -> None:
            self._send_json(
                {"error": "Method not allowed"},
                status=405,
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
