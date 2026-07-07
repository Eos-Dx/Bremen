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

def _load_synthetic_model() -> None:
    """Load a minimal synthetic model for dev/smoke testing."""
    import tempfile
    from pathlib import Path
    from joblib import dump
    from .model_state import ModelState
    from .preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS

    tmp_path = Path(tempfile.mkdtemp())
    n_features = 15
    package = {
        "portable_logreg": {
            "feature_columns": list(BREMEN_V01_FEATURE_COLUMNS),
            "imputer_statistics": [0.0] * n_features,
            "scaler_mean": [0.0] * n_features,
            "scaler_scale": [1.0] * n_features,
            "coef": [0.1] * n_features,
            "intercept": 0.0,
            "threshold": 0.5,
        }
    }
    model_path = tmp_path / "synth_model.joblib"
    dump(package, model_path)
    import hashlib
    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    ModelState.load_at_startup(
        model_uri=str(model_path),
        model_version="smoke-v0.1",
        model_checksum=checksum,
    )


from .app import (
    ModelNotReadyError,
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
    *,
    load_model: bool = False,
) -> type[BaseHTTPRequestHandler]:
    """Return a ``BaseHTTPRequestHandler`` subclass bound to *job_store*.

    Parameters
    ----------
    job_store : An ``InMemoryJobStore`` instance shared across requests.
    version : Optional version string for health response.
    load_model : If ``True``, load a synthetic model for inference testing.

    Returns
    -------
    A handler class suitable for ``HTTPServer``.
    """
    if load_model:
        _load_synthetic_model()

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
                    "model_ready": resp.model_ready,
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

                import logging
                _log = logging.getLogger("bremen.api.server")

                try:
                    resp = handle_submit_prediction(body, job_store)
                except ModelNotReadyError:
                    _log.warning(
                        "bremen.prediction.request.rejected\t"
                        "stage=prediction\tstatus=rejected\t"
                        "reason=model_not_ready"
                    )
                    self._send_json(
                        {"error": "Model is not loaded. "
                                  "Prediction cannot be submitted."},
                        status=503,
                    )
                    return
                except ValueError as exc:
                    self._send_json(
                        {"error": str(exc)},
                        status=400,
                    )
                    return
                except RuntimeError as exc:
                    err_str = str(exc)
                    if "not loaded" in err_str:
                        self._send_json(
                            {"error": str(exc)},
                            status=503,
                        )
                    else:
                        self._send_json(
                            {"error": str(exc)},
                            status=500,
                        )
                    return

                _log.info(
                    "bremen.prediction.request.accepted\t"
                    "stage=prediction\tstatus=accepted\t"
                    "job_id=%s",
                    resp.job_id,
                )

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
    import logging

    _log = logging.getLogger(__name__)
    _log.info(
        "bremen.server.starting\tstage=startup\tstatus=started\t"
        "host=%s\tport=%s",
        host, port,
    )

    job_store = InMemoryJobStore()
    handler = _make_handler(job_store, version=version)
    server = HTTPServer((host, port), handler)

    _log.info(
        "bremen.server.started\tstage=startup\tstatus=completed\t"
        "host=%s\tport=%s",
        host, port,
    )
    print(f"Bremen API server listening on http://{host}:{port}")
    print("Dev/smoke mode only. Not for production use.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Bremen API server.")
        server.server_close()
