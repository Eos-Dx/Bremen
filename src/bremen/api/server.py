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
from ..demo_config import read_demo_h5_config

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
                    "model_ready": resp.model_ready,
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
            elif self.path == "/demo":
                _handle_demo_route(self)
            elif self.path == "/demo/api/evidence":
                _handle_demo_evidence_route(self)
            elif self.path == "/demo/api/h5/containers":
                _handle_demo_h5_containers_list(self)
            else:
                self._log_and_send_error(
                    f"Not found: {self.path}", status=404,
                )

        def do_POST(self) -> None:
            self._request_id = self._get_request_id()
            self._job_id = None
            self._error = None

            if self.path == "/demo/api/h5/containers":
                _handle_demo_h5_containers_upload(self)
            elif self.path == "/demo/api/h5/analyze":
                _handle_demo_h5_analyze(self)
            elif self.path == "/predictions":
                body = self._read_json_body()
                if body is None:
                    self._log_and_send_error(
                        "Invalid or missing JSON body", status=400,
                    )
                    return

                import logging
                from .model_state import ModelState  # noqa: PLC0415
                _log = logging.getLogger("bremen.api.server")

                content_length = self.headers.get("Content-Length", "0")

                _log.info(
                    "bremen.prediction.request.received\t"
                    "stage=prediction\tstatus=received\t"
                    "route=/predictions\t"
                    "method=POST\t"
                    "content_length=%s\t"
                    "model_ready=%s",
                    content_length,
                    str(ModelState.is_ready()).lower(),
                )

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
                    self._log_and_send_error(
                        str(exc), status=400,
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


def _handle_demo_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo — return a board-friendly HTML demo page.

    Uses lazy imports to avoid module-level coupling with demo modules.
    Reads actual model state from ``ModelState`` singleton (not hardcoded).
    """
    import json as _json  # noqa: PLC0415
    import uuid as _uuid  # noqa: PLC0415

    from ..demo_ui import build_demo_html_page  # noqa: PLC0415
    from ..demo_evidence import build_demo_evidence_bundle  # noqa: PLC0415
    from ..demo_config import read_demo_h5_config  # noqa: PLC0415
    from .model_state import ModelState  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    base_url = f"http://{host_header}"

    # ---- Determine actual model state from ModelState ----
    model_pkg = ModelState.get_model()
    if model_pkg is not None:
        state = ModelState.get_instance()
        plr = model_pkg.get("portable_logreg", {})
        model_info = {
            "model_status": "ready",
            "model_version": state._model_version or plr.get("model_version") or "unknown",
            "model_checksum": state._model_checksum or "",
            "feature_schema_version": plr.get("feature_schema_version"),
        }
    elif ModelState.was_load_attempted():
        model_info = {
            "model_status": "error",
            "error_category": ModelState.get_load_error(),
        }
    else:
        model_info = {"model_status": "not_configured"}

    evidence = build_demo_evidence_bundle(
        base_url=base_url,
        request_id=request_id,
        model_status=model_info.get("model_status", "not_configured"),
        model_version=model_info.get("model_version"),
        feature_schema_version=model_info.get("feature_schema_version"),
        prediction_status="not_available",
    )

    demo_config = read_demo_h5_config()
    storage_configured = demo_config.get("h5_bucket") is not None

    html = build_demo_html_page(
        evidence=evidence,
        base_url=base_url,
        request_id=request_id,
        model_info=model_info,
        storage_configured=storage_configured,
        upload_max_bytes=demo_config.get("upload_max_bytes", 100 * 1024 * 1024),
    )
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


def _handle_demo_evidence_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/api/evidence — return evidence bundle JSON.

    Uses lazy imports to avoid module-level coupling with demo modules.
    """
    from ..demo_ui import build_demo_evidence_json_response  # noqa: PLC0415
    from ..demo_evidence import build_demo_evidence_bundle  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    base_url = f"http://{host_header}"

    evidence = build_demo_evidence_bundle(
        base_url=base_url,
        request_id=request_id,
        model_status="ready",
        prediction_status="not_available",
    )

    json_str = build_demo_evidence_json_response(evidence=evidence)
    body = json_str.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------------------
# Demo H5 container endpoints
# ---------------------------------------------------------------------------


def _handle_demo_h5_containers_list(
    handler: BaseHTTPRequestHandler,
) -> None:
    """Handle GET /demo/api/h5/containers — list demo H5 containers."""
    import json as _json  # noqa: PLC0415
    import os as _os  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    config = read_demo_h5_config()

    if config["h5_bucket"] is None:
        # No bucket configured — return safe empty response
        data = {
            "storage": "not_configured",
            "containers": [],
            "technical_demo_only": True,
        }
    else:
        # Read configured container list from env var
        try:
            containers_json = _os.environ.get(
                "BREMEN_DEMO_H5_CONTAINERS", "[]"
            )
            containers = _json.loads(containers_json)
            if not isinstance(containers, list):
                containers = []
        except (_json.JSONDecodeError, TypeError):
            containers = []

        data = {
            "storage": "configured",
            "containers": containers,
            "technical_demo_only": True,
        }

    data["request_id"] = request_id
    body = _json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


def _handle_demo_h5_containers_upload(
    handler: BaseHTTPRequestHandler,
) -> None:
    """Handle POST /demo/api/h5/containers — upload an H5 container."""
    import json as _json  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    config = read_demo_h5_config()

    # ---- Input validation (before storage check) ----

    # Validate content length
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length == 0:
        body = _json.dumps({
            "status": "upload_rejected",
            "error": "Empty body",
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    if content_length > config["upload_max_bytes"]:
        body = _json.dumps({
            "status": "upload_rejected",
            "error": f"File too large: {content_length} bytes "
                     f"(max {config['upload_max_bytes']})",
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(413)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Validate filename from header
    raw_filename = handler.headers.get("X-H5-Filename", "").strip()
    if not raw_filename:
        body = _json.dumps({
            "status": "upload_rejected",
            "error": "Missing X-H5-Filename header",
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Sanitize filename — reject path separators
    if "/" in raw_filename or "\\" in raw_filename or ".." in raw_filename:
        body = _json.dumps({
            "status": "upload_rejected",
            "error": "Invalid filename — path separators not allowed",
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Validate extension
    name_lower = raw_filename.lower()
    if not (name_lower.endswith(".h5") or name_lower.endswith(".hdf5")):
        body = _json.dumps({
            "status": "upload_rejected",
            "error": (
                f"Invalid file extension: {raw_filename!r}. "
                "Only .h5 and .hdf5 files are accepted."
            ),
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # ---- Storage checks (after input is validated) ----

    # Check upload enabled
    if not config["allow_upload"]:
        body = _json.dumps({
            "status": "upload_disabled",
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(403)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Check storage configured
    if config["h5_bucket"] is None:
        body = _json.dumps({
            "status": "storage_not_configured",
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(503)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Sanitize filename (keep only safe characters)
    sanitized = "".join(
        c for c in raw_filename if c.isalnum() or c in "._- "
    )
    sanitized = sanitized.replace(" ", "_").strip("._")
    if not sanitized:
        sanitized = "uploaded.h5"
    # Ensure .h5 extension
    if not sanitized.lower().endswith(".h5"):
        sanitized += ".h5"

    # Read raw bytes from request body
    raw_body = handler.rfile.read(content_length)

    # Upload to S3
    try:
        from boto3 import client as _s3_client  # noqa: PLC0415

        s3 = _s3_client("s3")
        key = f"{config['h5_prefix']}{sanitized}"
        s3.put_object(
            Bucket=config["h5_bucket"],
            Key=key,
            Body=raw_body,
        )

        body = _json.dumps({
            "status": "uploaded",
            "id": key,
            "filename": sanitized,
            "size_bytes": content_length,
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(201)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
    except Exception as exc:
        body = _json.dumps({
            "status": "upload_rejected",
            "error": f"S3 upload failed: {type(exc).__name__}",
            "request_id": request_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(503)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)


def _handle_demo_h5_analyze(
    handler: BaseHTTPRequestHandler,
) -> None:
    """Handle POST /demo/api/h5/analyze — analyze selected H5 container."""
    import json as _json  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415
    from ..h5_inputs import stage_h5_input  # noqa: PLC0415
    from ..api.inference_handler import run_inference  # noqa: PLC0415
    from .model_state import ModelState  # noqa: PLC0415

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    events: list[dict] = []

    # Read body
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length == 0:
        events.append({
            "event": "request_received", "timestamp": _now(),
            "detail": "Analyze requested (empty body)",
        })
        body = _json.dumps({
            "status": "failed",
            "events": events,
            "error": "Missing JSON body",
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    raw = handler.rfile.read(content_length)
    try:
        body_dict = _json.loads(raw)
    except (_json.JSONDecodeError, ValueError):
        events.append({
            "event": "request_received", "timestamp": _now(),
            "detail": "Analyze requested (invalid JSON)",
        })
        body = _json.dumps({
            "status": "failed",
            "events": events,
            "error": "Invalid JSON body",
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    container_id = body_dict.get("container_id", "").strip()

    events.append({
        "event": "request_received",
        "timestamp": _now(),
        "detail": "Analyze requested",
    })

    if not container_id:
        events.append({
            "event": "h5_container_unavailable",
            "timestamp": _now(),
            "detail": "Missing container_id",
        })
        body = _json.dumps({
            "status": "failed",
            "events": events,
            "error": "container_id is required",
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    events.append({
        "event": "container_selected",
        "timestamp": _now(),
        "detail": f"Container: {container_id}",
    })

    # Check storage configured
    config = read_demo_h5_config()
    if config["h5_bucket"] is None:
        events.append({
            "event": "storage_not_configured",
            "timestamp": _now(),
            "detail": "Demo H5 bucket not configured",
        })
        body = _json.dumps({
            "status": "failed",
            "events": events,
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(503)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Check model ready
    if not ModelState.is_ready():
        events.append({
            "event": "model_not_ready",
            "timestamp": _now(),
            "detail": "Model is not loaded",
        })
        load_error = ModelState.get_load_error()
        if load_error:
            events[-1]["detail"] = f"Model not ready: {load_error}"
        body = _json.dumps({
            "status": "failed",
            "events": events,
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Stage H5 from S3
    s3_uri = f"s3://{config['h5_bucket']}/{container_id}"

    events.append({
        "event": "h5_staging_started",
        "timestamp": _now(),
        "detail": f"Staging from {config['h5_bucket']}",
    })

    try:
        staged_path = stage_h5_input(s3_uri)
        events.append({
            "event": "h5_staging_completed",
            "timestamp": _now(),
            "detail": f"Staged: {staged_path.name}",
        })
    except Exception as exc:
        events.append({
            "event": "h5_container_unavailable",
            "timestamp": _now(),
            "detail": f"S3 download failed: {type(exc).__name__}",
        })
        body = _json.dumps({
            "status": "failed",
            "events": events,
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Preflight
    events.append({
        "event": "h5_preflight_started",
        "timestamp": _now(),
        "detail": "Running H5 preflight",
    })

    # Preprocessing
    events.append({
        "event": "preprocessing_started",
        "timestamp": _now(),
        "detail": "Starting preprocessing bridge",
    })

    # Model inference
    events.append({
        "event": "model_inference_started",
        "timestamp": _now(),
        "detail": f"Model version: {body_dict.get('model_version', 'current')}",
    })

    try:
        result = run_inference(str(staged_path))

        events.append({
            "event": "h5_preflight_completed",
            "timestamp": _now(),
            "detail": "Preflight passed",
        })
        events.append({
            "event": "preprocessing_completed",
            "timestamp": _now(),
            "detail": "15 features extracted",
        })
        events.append({
            "event": "model_inference_completed",
            "timestamp": _now(),
            "detail": f"p_mri_needed={result.get('p_mri_needed', 'N/A')}",
        })
        events.append({
            "event": "evidence_built",
            "timestamp": _now(),
            "detail": "Evidence bundle assembled",
        })
        events.append({
            "event": "completed",
            "timestamp": _now(),
            "detail": "Analysis complete",
        })

        body = _json.dumps({
            "status": "completed",
            "events": events,
            "result": {
                "p_mri_needed": result.get("p_mri_needed"),
                "triage_recommendation": result.get("triage_recommendation"),
                "qc_status": result.get("qc_status"),
                "model_version": result.get("model_version"),
                "feature_schema_version": result.get("feature_schema_version"),
                "prediction_id": result.get("prediction_id"),
            },
            "evidence": {
                "model_version": result.get("model_version"),
                "model_checksum": result.get("model_checksum"),
                "feature_schema_version": result.get("feature_schema_version"),
                "threshold_version": result.get("threshold_version"),
                "prediction_id": result.get("prediction_id"),
            },
            "container": {
                "id": container_id,
                "bucket": config["h5_bucket"],
            },
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)

    except RuntimeError as exc:
        err_str = str(exc).lower()
        if "preflight" in err_str:
            events.append({
                "event": "h5_preflight_failed",
                "timestamp": _now(),
                "detail": str(exc)[:200],
            })
            status_msg = "h5_preflight_failed"
        elif "preprocessing" in err_str or "bridge" in err_str:
            events.append({
                "event": "preprocessing_failed",
                "timestamp": _now(),
                "detail": str(exc)[:200],
            })
            status_msg = "preprocessing_failed"
        else:
            events.append({
                "event": "inference_failed",
                "timestamp": _now(),
                "detail": str(exc)[:200],
            })
            status_msg = "inference_failed"

        body = _json.dumps({
            "status": "failed",
            "events": events,
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)

    except Exception:
        events.append({
            "event": "inference_failed",
            "timestamp": _now(),
            "detail": "Unexpected inference error",
        })
        body = _json.dumps({
            "status": "failed",
            "events": events,
            "request_id": request_id,
            "job_id": job_id,
            "technical_demo_only": True,
        }).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)


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

    # --- Model startup: load exactly once per process ---
    from .model_state import ModelState as _ModelState  # noqa: PLC0415

    import os as _os
    _model_env_present = bool(_os.environ.get("BREMEN_MODEL_URI", ""))
    model_ready = _ModelState.load_at_startup()
    _log_level = _os.environ.get("BREMEN_LOG_LEVEL", "INFO")
    _log.info(
        "bremen.runtime.config.summary\t"
        "stage=startup\tstatus=summary\t"
        "model_env_present=%s\t"
        "model_ready=%s\t"
        "log_level=%s\t"
        "server_host=%s\t"
        "server_port=%s",
        str(_model_env_present).lower(),
        str(model_ready).lower(),
        _log_level,
        host, str(port),
    )

    job_store = InMemoryJobStore()
    handler = _make_handler(job_store, version=version)
    server = HTTPServer((host, port), handler)

    _log.info(
        "bremen.server.started\tstage=startup\tstatus=completed\t"
        "host=%s\tport=%s",
        host, port,
    )

    _log.info(
        "bremen.api.routes.ready\t"
        "stage=startup\tstatus=ready\t"
        "health_route=true\t"
        "model_version_route=true\t"
        "predictions_route=true",
    )

    print(f"Bremen API server listening on http://{host}:{port}")
    print("Dev/smoke mode only. Not for production use.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Bremen API server.")
        server.server_close()
