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
from socketserver import ThreadingMixIn


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Thread-per-request HTTP server with daemon threads.

    Threads are daemon so they do not prevent process exit during
    shutdown.  Each SSE connection lives in its own thread for the
    stream duration (up to 5 minutes).
    """

    daemon_threads = True
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
from .preflight import (
    H5PreflightError,
    H5ContainerError,
    H5MetadataError,
    H5PatientMismatchError,
    H5SideMismatchError,
    H5MeasurementError,
    H5QualityError,
)
from .preprocessing_bridge import (
    PreprocessingBridgeError,
    PreflightNotPassedError,
    FeatureSchemaMismatchError,
)
from ..inference import PortableLogRegModelError
from ..feature_artifacts import FeatureArtifactError

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


# ---------------------------------------------------------------------------
# Auth config singleton and helpers (PR0102)
# ---------------------------------------------------------------------------

_auth_config = None
_AUTH_ERROR_SHAPE = json.dumps({
    "error": "Authentication failed",
    "token_type": "Bearer",
    "technical_demo_only": True,
})
_AUTH_DISABLED_SHAPE = json.dumps({
    "error": "Authentication is not configured",
})


def _get_auth_config():
    """Lazily load auth config singleton."""
    global _auth_config  # noqa: PLW0603
    if _auth_config is None:
        from ..config import read_auth_config  # noqa: PLC0415
        _auth_config = read_auth_config()
    return _auth_config


def _reset_auth_config():
    """Reset auth config (for testing)."""
    global _auth_config  # noqa: PLW0603
    _auth_config = None


def _send_auth_error(handler: BaseHTTPRequestHandler, status: int = 401) -> None:
    """Send a generic auth error response."""
    body = _AUTH_ERROR_SHAPE.encode("utf-8") if status == 401 else _AUTH_DISABLED_SHAPE.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    """Check auth on a request. Returns True if allowed, False if rejected."""
    config = _get_auth_config()
    if not config.enabled:
        return True
    if config.validation_error:
        _send_auth_error(handler, 503)
        return False
    from ..auth import authenticate_request  # noqa: PLC0415
    auth_header = handler.headers.get("Authorization", "")
    claims = authenticate_request(config, auth_header)
    if claims is None:
        _send_auth_error(handler, 401)
        return False
    return True


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
        # Initialize registry from ModelState after loading
        from .model_registry import initialize_registry, build_legacy_registry  # noqa: PLC0415
        legacy_registry = build_legacy_registry()
        initialize_registry(legacy_registry)

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

            Successful GET /health responses (2xx) are suppressed to avoid
            high-volume low-value log noise from App Runner health checks.
            """
            message = format % args
            status = args[1] if len(args) >= 2 else "?"

            # Suppress INFO logging for successful health check requests
            path = getattr(self, "path", "")
            from urllib.parse import urlsplit as _urlsplit
            route_path = _urlsplit(path).path
            try:
                status_int = int(status)
            except (ValueError, TypeError):
                status_int = 0
            if route_path == "/health" and 200 <= status_int < 300:
                return

            # Redact sensitive query params (auth_ticket, access_token, etc.)
            # from the logged path to avoid credential-in-log risk.
            from ..logging_config import redact_sensitive_query_params  # noqa: PLC0415
            safe_path = redact_sensitive_query_params(path)

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
                    "path": safe_path,
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

            from urllib.parse import urlsplit as _urlsplit
            route_path = _urlsplit(self.path).path

            if route_path == "/health":
                resp = handle_health(version=version)
                self._log_and_send({
                    "status": resp.status,
                    "service": resp.service,
                    "version": resp.version,
                    "timestamp": resp.timestamp,
                    "model_ready": resp.model_ready,
                })
            elif route_path == "/model/version":
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
            elif (match := _JOB_ID_PATTERN.match(route_path)) is not None:
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

            elif route_path == "/demo":
                _handle_start_page_route(self)
            elif route_path == "/demo/control-room" or route_path.startswith("/demo/control-room/"):
                _handle_control_room_route(self)
            elif route_path.startswith("/demo/report/"):
                _handle_report_route(self)
            elif route_path == "/demo/workspace" or route_path.startswith("/demo/workspace/"):
                _handle_workspace_route(self)
            elif route_path == "/demo/api-docs":
                _handle_api_docs_route(self)
            elif route_path == "/demo/login":
                _handle_login_route(self)
            elif route_path == "/demo/api/models":
                _handle_demo_models(self)
            elif route_path == "/demo/api/evidence":
                _handle_demo_evidence_route(self)
            elif route_path == "/demo/api/h5/containers":
                _handle_demo_h5_containers_list(self)
            elif route_path == "/demo/api/jobs":
                _handle_demo_jobs_list(self)
            elif route_path.startswith("/demo/api/jobs/"):
                _handle_demo_jobs_route(self)
            elif route_path.startswith("/demo/api/reports/"):
                _handle_demo_reports_route(self)
            else:
                self._log_and_send_error(
                    f"Not found: {self.path}", status=404,
                )

        def do_POST(self) -> None:
            self._request_id = self._get_request_id()
            self._job_id = None
            self._error = None

            # Auth endpoints (no auth required)
            if self.path == "/demo/api/auth/token":
                _handle_auth_token(self)
            elif self.path == "/demo/api/auth/refresh":
                _handle_auth_refresh(self)
            # Protected POST endpoints (auth required when enabled)
            elif self.path == "/demo/api/h5/containers":
                if not _check_auth(self):
                    return
                _handle_demo_h5_containers_upload(self)
            elif self.path == "/demo/api/stage":
                if not _check_auth(self):
                    return
                _handle_demo_stage(self)
            elif self.path == "/demo/api/h5/analyze":
                if not _check_auth(self):
                    return
                _handle_demo_h5_analyze(self)
            elif self.path == "/demo/api/jobs":
                if not _check_auth(self):
                    return
                _handle_demo_jobs_create(self)
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
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
    base_url = f"{forwarded_proto}://{host_header}"

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
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
    base_url = f"{forwarded_proto}://{host_header}"

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


def _list_s3_containers(bucket: str, prefix: str) -> list[dict]:
    """List H5/HDF5 objects under configured S3 prefix.

    Uses the existing boto3 dependency via lazy import.
    Returns a list of container dicts with safe metadata only:
    ``id`` (S3 key), ``filename`` (basename), ``size_bytes``,
    ``last_modified``.

    On S3 errors (AccessDenied, etc.), raises the exception.
    The caller sets ``storage: "list_failed"`` accordingly.
    """
    import re as _re  # noqa: PLC0415
    from boto3 import client as _s3_client  # noqa: PLC0415

    s3 = _s3_client("s3")
    containers: list[dict] = []
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    for page in pages:
        for obj in page.get("Contents", []):
            key = str(obj["Key"])
            filename = key.split("/")[-1] if "/" in key else key
            # Only include H5/HDF5 files
            if not _re.search(r"\.h5$|\.hdf5$", key, _re.IGNORECASE):
                continue
            last_modified = obj.get("LastModified")
            if hasattr(last_modified, "isoformat"):
                last_modified_str = last_modified.isoformat()
            else:
                last_modified_str = str(last_modified or "")
            containers.append({
                "id": key,
                "filename": filename,
                "size_bytes": obj.get("Size", 0),
                "last_modified": last_modified_str,
            })
    return containers


def _handle_demo_models(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/api/models — return the model catalog."""
    import json as _json  # noqa: PLC0415
    from .model_catalog import build_model_catalog  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    catalog = build_model_catalog()
    catalog["request_id"] = request_id
    catalog["technical_demo_only"] = True

    body = _json.dumps(catalog, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------------------
# Demo H5 container endpoints
# ---------------------------------------------------------------------------

# Patient name cache: (bucket, object_key, size_bytes) -> patient_name | None
_patient_name_cache: dict[tuple[str, str, int], str | None] = {}


def _build_containers_response(request_id: str | None = None) -> dict:
    """Build the GET /demo/api/h5/containers response dict.

    This is the transport-independent core extracted from
    ``_handle_demo_h5_containers_list``.  Both the ``http.server``
    handler and the FastAPI route call this helper so that the
    business logic lives in exactly one place.

    Returns
    -------
    A serialisable dict with ``storage``, ``containers``,
    ``upload_max_bytes``, ``technical_demo_only``, and ``request_id``.
    """
    import json as _json  # noqa: PLC0415
    import os as _os  # noqa: PLC0415
    import logging as _logging  # noqa: PLC0415

    if request_id is None:
        request_id = str(uuid.uuid4())

    config = read_demo_h5_config()

    if config["h5_bucket"] is None:
        # No bucket configured — return safe empty response
        return {
            "storage": "not_configured",
            "containers": [],
            "technical_demo_only": True,
            "request_id": request_id,
        }

    # 1. Env-configured catalog
    try:
        containers_json = _os.environ.get(
            "BREMEN_DEMO_H5_CONTAINERS", "[]"
        )
        env_containers = _json.loads(containers_json)
        if not isinstance(env_containers, list):
            env_containers = []
    except (_json.JSONDecodeError, TypeError):
        env_containers = []

    # 2. S3-listed containers
    s3_containers: list[dict] = []
    storage_status = "configured"
    try:
        s3_containers = _list_s3_containers(
            config["h5_bucket"], config["h5_prefix"],
        )
    except Exception:
        _log = _logging.getLogger(__name__)
        _log.exception(
            "bremen.demo.h5.containers.list_failed\t"
            "stage=containers\tstatus=failed\t"
            "bucket=%s\tprefix=%s",
            config["h5_bucket"], config["h5_prefix"],
        )
        storage_status = "list_failed"
        s3_containers = []

    # 3. Merge with deduplication by raw key (server-side only)
    seen_keys: set[str] = set()
    merged_raw: list[dict] = []
    for c in env_containers:
        cid = c.get("id") or c.get("key") or c.get("filename", "")
        if cid not in seen_keys:
            seen_keys.add(cid)
            merged_raw.append(c)
    for c in s3_containers:
        cid = c.get("id", "")
        if cid not in seen_keys:
            seen_keys.add(cid)
            merged_raw.append(c)

    # Filter oversized objects
    max_bytes = config["upload_max_bytes"]
    merged_raw = [c for c in merged_raw if c.get("size_bytes", 0) <= max_bytes]

    # Sort by last_modified descending (newest first)
    merged_raw.sort(key=lambda c: c.get("last_modified", ""), reverse=True)

    # Limit to 100 objects maximum
    merged_raw = merged_raw[:100]

    # Replace raw S3 keys with opaque source_ids from the registry.
    # The browser receives only source_id, display_name, size_bytes,
    # and last_modified — never the S3 key.
    from .source_registry import register_source, get_stable_source_key  # noqa: PLC0415

    bucket = config["h5_bucket"]
    prefix = config["h5_prefix"]
    safe_containers: list[dict] = []
    for item in merged_raw:
        raw_key = item.get("id", "")
        filename = item.get("filename", "unknown.h5")
        size = item.get("size_bytes", 0)
        last_mod = item.get("last_modified", "")
        source_id = register_source(
            bucket=bucket,
            object_key=raw_key,
            filename=filename,
            size_bytes=size,
            prefix=prefix,
        )
        # Determine workflow compatibility
        wf = item.get("workflow_id", "bremen")

        # Patient name from cache or extraction
        cache_key = (bucket, raw_key, size)
        patient_name = ""
        if cache_key in _patient_name_cache:
            cached = _patient_name_cache[cache_key]
            patient_name = cached or ""
        else:
            try:
                from ..h5_inputs import stage_h5_input as _stage  # noqa: PLC0415
                from .job_api_handler import extract_patient_display_name  # noqa: PLC0415
                s3_uri = f"s3://{bucket}/{raw_key}"
                local_path = _stage(s3_uri)
                extracted = extract_patient_display_name(str(local_path))
                if extracted:
                    patient_name = extracted
                    _patient_name_cache[cache_key] = extracted
                else:
                    _patient_name_cache[cache_key] = None
            except Exception:
                _patient_name_cache[cache_key] = None

        display_name = patient_name or filename
        safe_containers.append({
            "source_id": source_id,
            "display_name": display_name,
            "patient_display_name": patient_name,
            "stable_source_key": get_stable_source_key(source_id),
            "size_bytes": size,
            "last_modified": last_mod,
            "workflow_id": wf,
        })

    return {
        "storage": storage_status,
        "containers": safe_containers,
        "upload_max_bytes": max_bytes,
        "technical_demo_only": True,
        "request_id": request_id,
    }


def _handle_demo_h5_containers_list(
    handler: BaseHTTPRequestHandler,
) -> None:
    """Handle GET /demo/api/h5/containers — list demo H5 containers.

    Delegates to :func:`_build_containers_response` for the response
    dict and writes the JSON response over ``http.server``.
    """
    import json as _json  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    data = _build_containers_response(request_id=request_id)

    body = _json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


def _handle_h5_upload_bytes(
    raw_body: bytes,
    raw_filename: str,
    request_id: str,
) -> tuple[int, dict]:
    """Validate and upload H5 bytes to S3. Transport-independent.

    Parameters
    ----------
    raw_body : Raw file bytes.
    raw_filename : Original filename from the client.
    request_id : Request ID for the response.

    Returns
    -------
    A tuple of (http_status_code, response_dict).
    All validation errors return safe public messages only.
    """
    config = read_demo_h5_config()

    # ---- Input validation (before storage check) ----

    # Validate content length
    content_length = len(raw_body)
    if content_length == 0:
        return 400, {
            "status": "upload_rejected",
            "error": "Empty body",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    if content_length > config["upload_max_bytes"]:
        return 413, {
            "status": "upload_rejected",
            "error": f"File too large: {content_length} bytes "
                     f"(max {config['upload_max_bytes']})",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Validate filename
    raw_filename = raw_filename.strip()
    if not raw_filename:
        return 400, {
            "status": "upload_rejected",
            "error": "Missing X-H5-Filename header",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Sanitize filename — reject path separators
    if "/" in raw_filename or "\\" in raw_filename or ".." in raw_filename:
        return 400, {
            "status": "upload_rejected",
            "error": "Invalid filename — path separators not allowed",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Validate extension
    name_lower = raw_filename.lower()
    if not (name_lower.endswith(".h5") or name_lower.endswith(".hdf5")):
        return 400, {
            "status": "upload_rejected",
            "error": (
                f"Invalid file extension: {raw_filename!r}. "
                "Only .h5 and .hdf5 files are accepted."
            ),
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # ---- Storage checks (after input is validated) ----

    # Check upload enabled
    if not config["allow_upload"]:
        return 403, {
            "status": "upload_disabled",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Check storage configured
    if config["h5_bucket"] is None:
        return 503, {
            "status": "storage_not_configured",
            "request_id": request_id,
            "technical_demo_only": True,
        }

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

        return 201, {
            "status": "uploaded",
            "id": key,
            "filename": sanitized,
            "size_bytes": content_length,
            "request_id": request_id,
            "technical_demo_only": True,
        }
    except Exception as exc:
        return 503, {
            "status": "upload_rejected",
            "error": f"S3 upload failed: {type(exc).__name__}",
            "request_id": request_id,
            "technical_demo_only": True,
        }


def _handle_demo_h5_containers_upload(
    handler: BaseHTTPRequestHandler,
) -> None:
    """Handle POST /demo/api/h5/containers — upload an H5 container.

    Delegates to :func:`_handle_h5_upload_bytes` for validation and
    upload logic.
    """
    import json as _json  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    raw_filename = handler.headers.get("X-H5-Filename", "")
    content_length = int(handler.headers.get("Content-Length", 0))
    raw_body = handler.rfile.read(content_length)

    status_code, data = _handle_h5_upload_bytes(
        raw_body, raw_filename, request_id,
    )

    body = _json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)
def _safe_error_detail(exc: Exception) -> str:
    """Map an internal exception to a safe public error detail.

    No internal H5 paths, measurement filenames, S3 URIs,
    patient/sample identifiers, or attribute values are exposed.

    Returns a finite, generic detail string suitable for API
    responses.  The full stack trace is preserved in server logs
    via ``_log.exception()`` for debugging.
    """
    if isinstance(exc, (H5ContainerError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (H5MetadataError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (H5PatientMismatchError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (H5SideMismatchError,)):
        return "Bilateral measurement pairing failed"
    if isinstance(exc, (H5MeasurementError, H5QualityError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (H5PreflightError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (PreprocessingBridgeError, FeatureSchemaMismatchError,
                        PreflightNotPassedError)):
        return "Preprocessing failed"
    if isinstance(exc, (PortableLogRegModelError, FeatureArtifactError)):
        return "Model inference failed"
    # Fallback for unexpected exceptions
    return "Internal error"


def _safe_error_detail_str(error_message: str) -> str:
    """Map a workflow error message to a safe public detail string.

    No internal paths, PONI text, raw arrays, or patient/specimen
    identifiers are exposed.
    """
    msg_lower = error_message.lower()
    if 'configuration_required' in msg_lower:
        return 'Workflow configuration is needed for this input'
    if 'unavailable' in msg_lower:
        return 'Requested workflow is not available'
    if 'not found' in msg_lower or 'not_found' in msg_lower:
        return 'Requested workflow is not available'
    if 'incompatible' in msg_lower:
        return 'Input is not compatible with the requested workflow'
    return 'Internal error'


def _handle_demo_h5_analyze(
    handler: BaseHTTPRequestHandler,
) -> None:
    """Handle POST /demo/api/h5/analyze — analyze selected H5 container."""
    import json as _json  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415
    from ..h5_inputs import stage_h5_input  # noqa: PLC0415
    from .workflow_orchestrator import run_workflow_request  # noqa: PLC0415
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

    source_id = body_dict.get("source_id", "").strip()
    container_id = body_dict.get("container_id", "").strip()
    workflow_id = body_dict.get("workflow_id", "bremen")

    events.append({
        "event": "request_received",
        "timestamp": _now(),
        "detail": f"Analyze requested (workflow={workflow_id})",
    })

    if not source_id and not container_id:
        events.append({
            "event": "h5_container_unavailable",
            "timestamp": _now(),
            "detail": "Missing source_id or container_id",
        })
        body = _json.dumps({
            "status": "failed",
            "events": events,
            "error": "source_id is required",
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
        "detail": f"Source: {source_id or container_id}",
    })

    # --- Resolve source to local h5_path ---
    staged_path = None
    resolved_via = source_id or container_id
    if source_id:
        # New opaque source_id path — resolve via source registry
        from .job_api_handler import resolve_source  # noqa: PLC0415
        try:
            h5_path = resolve_source(source_id=source_id, upload_id=None)
            staged_path = type("", (), {"name": h5_path})()  # lightweight wrapper for .name
            staged_path._h5_path = h5_path
        except ValueError as exc:
            events.append({
                "event": "h5_container_unavailable",
                "timestamp": _now(),
                "detail": str(exc),
            })
            body = _json.dumps({
                "status": "failed",
                "events": events,
                "error": str(exc),
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
    else:
        # Legacy container_id path — resolve via S3 URI
        from ..demo_config import read_demo_h5_config as _read_cfg  # noqa: PLC0415
        _config = _read_cfg()
        if _config["h5_bucket"] is None:
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
        s3_uri = f"s3://{_config['h5_bucket']}/{container_id}"
        events.append({
            "event": "h5_staging_started",
            "timestamp": _now(),
            "detail": f"Staging from {_config['h5_bucket']}",
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

    # Run through the canonical orchestrator
    events.append({
        "event": "canonical_normalization_started",
        "timestamp": _now(),
        "detail": f"Running canonical normalization (workflow={workflow_id})",
    })

    try:
        h5_path_str = (
            staged_path._h5_path
            if hasattr(staged_path, "_h5_path")
            else str(staged_path)
        )
        mw_result = run_workflow_request(
            h5_path=h5_path_str,
            workflow_id=workflow_id,
        )

        wf_result = mw_result.workflows.get(workflow_id)
        wf_status = wf_result.status if wf_result else "not_found"

        if wf_status == "completed":
            payload = wf_result.payload if wf_result else {}
            events.append({
                "event": "canonical_normalization_completed",
                "timestamp": _now(),
                "detail": "Normalization completed",
            })
            events.append({
                "event": "workflow_executed",
                "timestamp": _now(),
                "detail": f"Workflow {workflow_id} completed",
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
                    "p_mri_needed": payload.get("probability"),
                    "triage_recommendation": payload.get("triage_recommendation"),
                    "qc_status": "passed",
                    "model_version": payload.get("model_version"),
                    "feature_schema_version": payload.get("feature_schema_version"),
                    "prediction_id": payload.get("prediction_id"),
                },
                "evidence": {
                    "model_version": payload.get("model_version"),
                    "model_checksum": payload.get("model_checksum"),
                    "feature_schema_version": payload.get("feature_schema_version"),
                    "threshold_version": "v0.1",
                    "prediction_id": payload.get("prediction_id"),
                },
                "container": {
                    "id": resolved_via,
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
        elif wf_status == "failed" and wf_result and (
            "configuration_required" in (wf_result.error or "")
            or "WorkflowConfigurationRequired" in (wf_result.error or "")
        ):
            events.append({
                "event": "workflow_configuration_required",
                "timestamp": _now(),
                "detail": "Workflow configuration required",
            })
            body = _json.dumps({
                "status": "workflow_configuration_required",
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
        elif wf_status == "failed" and wf_result and "unavailable" in (wf_result.error or ""):
            events.append({
                "event": "workflow_unavailable",
                "timestamp": _now(),
                "detail": "Workflow unavailable",
            })
            body = _json.dumps({
                "status": "workflow_unavailable",
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
        else:
            error_msg = wf_result.error if wf_result else "unknown error"
            events.append({
                "event": "inference_failed",
                "timestamp": _now(),
                "detail": _safe_error_detail_str(error_msg),
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

    except Exception as exc:
        import logging as _logging  # noqa: PLC0415
        _log = _logging.getLogger(__name__)
        _log.exception(
            "bremen.demo.analyze.failed\t"
            "stage=analyze\tstatus=failed\t"
            "container_id=%s\tworkflow_id=%s\trequest_id=%s\tjob_id=%s",
            container_id, workflow_id, request_id, job_id,
        )
        safe_detail = _safe_error_detail(exc)
        events.append({
            "event": "inference_failed",
            "timestamp": _now(),
            "detail": safe_detail,
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

    import os as _os

    # --- Determine startup mode: catalog or legacy ---
    catalog_uri = _os.environ.get("BREMEN_MODEL_CATALOG_URI", "").strip()
    legacy_uri = _os.environ.get("BREMEN_MODEL_URI", "").strip()

    if catalog_uri:
        # Catalog mode — run S3 discovery
        if legacy_uri:
            _log.warning(
                "bremen.startup.catalog_mode\t"
                "BREMEN_MODEL_CATALOG_URI is set; "
                "BREMEN_MODEL_URI is ignored"
            )

        _log.info(
            "bremen.startup.catalog.discovering\t"
            "stage=startup\tstatus=started"
        )

        from .s3_model_discovery import discover_models  # noqa: PLC0415
        from .model_registry import initialize_registry, ModelRegistry  # noqa: PLC0415

        discovery_result = discover_models(catalog_uri)

        registry = ModelRegistry(
            entries=tuple(discovery_result.entries),
            unavailable_entries=tuple(discovery_result.unavailable_entries),
            catalog_status=discovery_result.catalog_status,
            candidate_count=discovery_result.candidate_count,
            available_count=discovery_result.available_count,
            rejected_count=discovery_result.rejected_count,
            unavailable_count=discovery_result.unavailable_count,
            last_discovery_at=discovery_result.last_discovery_at,
        )
        initialize_registry(registry)

        _log.info(
            "bremen.startup.catalog.completed\t"
            "stage=startup\tstatus=completed\t"
            "catalog_status=%s\tcandidate_count=%d\t"
            "available_count=%d\trejected_count=%d\t"
            "unavailable_count=%d",
            registry.catalog_status,
            registry.candidate_count,
            registry.available_count,
            registry.rejected_count,
            registry.unavailable_count,
        )
    else:
        # Legacy mode — load ModelState as before
        from .model_state import ModelState as _ModelState  # noqa: PLC0415

        _model_env_present = bool(legacy_uri)
        model_ready = _ModelState.load_at_startup()

        # Build legacy registry from ModelState
        from .model_registry import initialize_registry, build_legacy_registry  # noqa: PLC0415
        legacy_registry = build_legacy_registry()
        initialize_registry(legacy_registry)

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
    server = _ThreadingHTTPServer((host, port), handler)
    server.allow_reuse_address = True

    _log.info(
        "bremen.server.started\tstage=startup\tstatus=completed\t"
        "host=%s\tport=%s\tserver_mode=threaded\tmax_workers=per-request",
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
        _log.info(
            "bremen.server.shutdown\tstage=shutdown\tstatus=started\t"
            "reason=keyboard_interrupt"
        )
        server.shutdown()
        server.server_close()
        _log.info(
            "bremen.server.shutdown\tstage=shutdown\tstatus=completed"
        )

# ---------------------------------------------------------------------------
# Start page route
# ---------------------------------------------------------------------------


def _handle_start_page_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo — Bremen Start page with model selection."""
    import uuid as _uuid  # noqa: PLC0415
    from ..start_page_ui import build_start_page  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
    base_url = f"{forwarded_proto}://{host_header}"
    html = build_start_page(base_url=base_url)
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------------------
# Report page route
# ---------------------------------------------------------------------------


def _handle_report_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/report/{job_id} — product-grade Report page."""
    import uuid as _uuid  # noqa: PLC0415
    from ..report_ui import build_report_page  # noqa: PLC0415
    from urllib.parse import urlsplit as _urlsplit  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
    base_url = f"{forwarded_proto}://{host_header}"
    route_path = _urlsplit(handler.path).path
    job_id = ""
    prefix = "/demo/report/"
    if route_path.startswith(prefix):
        job_id = route_path[len(prefix):].rstrip("/")
    html = build_report_page(base_url=base_url, job_id=job_id)
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------------------
# Demo workspace route
# ---------------------------------------------------------------------------


def _handle_workspace_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/workspace — multi-workflow analysis workspace."""
    import uuid as _uuid  # noqa: PLC0415
    from ..workspace_ui import build_workspace_page  # noqa: PLC0415
    from urllib.parse import urlsplit as _urlsplit  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
    base_url = f"{forwarded_proto}://{host_header}"
    route_path = _urlsplit(handler.path).path
    job_id = None
    prefix = "/demo/workspace/"
    if route_path.startswith(prefix):
        job_id = route_path[len(prefix):].rstrip("/")
    html = build_workspace_page(base_url=base_url, request_id=request_id, job_id=job_id)
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


def _handle_control_room_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo — Bremen Investor Control Room."""
    import uuid as _uuid  # noqa: PLC0415
    from ..control_room_ui import build_control_room_page  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
    base_url = f"{forwarded_proto}://{host_header}"
    html = build_control_room_page(base_url=base_url, request_id=request_id)
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------------------
# API docs route
# ---------------------------------------------------------------------------


def _handle_api_docs_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/api-docs — Bremen API documentation page."""
    import uuid as _uuid  # noqa: PLC0415
    from ..api_docs_ui import build_api_docs_page  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
    base_url = f"{forwarded_proto}://{host_header}"
    html = build_api_docs_page(base_url=base_url, request_id=request_id)
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


def _handle_demo_stage(handler: BaseHTTPRequestHandler) -> None:
    """Handle POST /demo/api/stage — accept a demo H5 file, stage it
    locally, and return an opaque upload_id for job creation.

    The new Control Room contract returns only upload_id, filename,
    and size_bytes — never a local filesystem path. Legacy callers
    that relied on h5_path must use the POST /demo/api/h5/containers
    (S3 upload) endpoint instead.

    The staged file is registered in the uploads registry and evicted
    after a timeout period or after being consumed by a job.
    """
    import json as _json  # noqa: PLC0415
    import os as _os  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    import uuid as _uuid  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415
    from .job_api_handler import register_staged_upload  # noqa: PLC0415

    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length == 0:
        body = _json.dumps({
            "status": "rejected",
            "error": "Empty body",
            "request_id": request_id,
        }).encode("utf-8")
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("X-Request-ID", request_id)
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Read filename from header for display
    raw_filename = handler.headers.get("X-H5-Filename", "").strip() or "uploaded.h5"
    # Sanitize filename (safe display only)
    safe_filename = "".join(c for c in raw_filename if c.isalnum() or c in "._- ").strip()
    if not safe_filename:
        safe_filename = "uploaded.h5"

    raw = handler.rfile.read(content_length)
    suffix = ".h5"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
        tf.write(raw)
        staged_path = tf.name

    upload_id = register_staged_upload(
        h5_path=staged_path,
        filename=safe_filename,
        size_bytes=content_length,
    )

    body = _json.dumps({
        "status": "staged",
        "upload_id": upload_id,
        "filename": safe_filename,
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


# ---------------------------------------------------------------------------
# Demo job API handlers
# ---------------------------------------------------------------------------


def _handle_demo_jobs_list(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/api/jobs."""
    from .job_api_handler import handle_jobs_list  # noqa: PLC0415
    handle_jobs_list(handler)


def _handle_demo_jobs_create(handler: BaseHTTPRequestHandler) -> None:
    """Handle POST /demo/api/jobs."""
    from .job_api_handler import handle_jobs_create  # noqa: PLC0415
    handle_jobs_create(handler)


def _handle_demo_jobs_route(handler: BaseHTTPRequestHandler) -> None:
    """Dispatch /demo/api/jobs/{job_id}/... routes."""
    import re as _re  # noqa: PLC0415
    from urllib.parse import urlsplit as _urlsplit  # noqa: PLC0415
    from .job_api_handler import (  # noqa: PLC0415
        handle_job_get, handle_job_events,
        handle_job_events_stream, handle_job_reports, handle_job_report,
    )
    route_path = _urlsplit(handler.path).path
    m = _re.match(r"^/demo/api/jobs/([^/]+)/events/stream$", route_path)
    if m:
        handle_job_events_stream(handler, m.group(1))
        return
    m = _re.match(r"^/demo/api/jobs/([^/]+)/events$", route_path)
    if m:
        handle_job_events(handler, m.group(1))
        return
    m = _re.match(r"^/demo/api/jobs/([^/]+)/reports/([^/]+)$", route_path)
    if m:
        handle_job_report(handler, m.group(1), m.group(2))
        return
    m = _re.match(r"^/demo/api/jobs/([^/]+)/reports$", route_path)
    if m:
        handle_job_reports(handler, m.group(1))
        return
    m = _re.match(r"^/demo/api/jobs/([^/]+)$", route_path)
    if m:
        handle_job_get(handler, m.group(1))
        return
    handler._log_and_send_error(f"Not found: {handler.path}", status=404)


# ---------------------------------------------------------------------------
# Auth endpoints (PR0102)
# ---------------------------------------------------------------------------


def _handle_auth_token(handler: BaseHTTPRequestHandler) -> None:
    """Handle POST /demo/api/auth/token — authenticate and issue tokens."""
    from ..auth import authenticate_credentials, AuthenticationFailedError  # noqa: PLC0415

    config = _get_auth_config()
    if not config.enabled or config.validation_error:
        _send_auth_error(handler, 503)
        return

    body = handler._read_json_body()
    if body is None:
        _send_auth_error(handler, 401)
        return

    username = body.get("username", "")
    password = body.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        _send_auth_error(handler, 401)
        return

    result = authenticate_credentials(config, username, password)
    if result is None:
        _send_auth_error(handler, 401)
        return

    response = {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "token_type": result.token_type,
        "expires_in": result.expires_in,
        "technical_demo_only": True,
    }
    body_bytes = json.dumps(response).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body_bytes)))
    handler.end_headers()
    handler.wfile.write(body_bytes)


def _handle_auth_refresh(handler: BaseHTTPRequestHandler) -> None:
    """Handle POST /demo/api/auth/refresh — refresh access token."""
    from ..auth import (  # noqa: PLC0415
        decode_refresh_token, create_access_token, create_refresh_token,
        AuthError,
    )

    config = _get_auth_config()
    if not config.enabled or config.validation_error:
        _send_auth_error(handler, 503)
        return

    body = handler._read_json_body()
    if body is None:
        _send_auth_error(handler, 401)
        return

    refresh_token = body.get("refresh_token", "")
    if not isinstance(refresh_token, str) or not refresh_token:
        _send_auth_error(handler, 401)
        return

    try:
        claims = decode_refresh_token(config, refresh_token)
    except AuthError:
        _send_auth_error(handler, 401)
        return

    new_access = create_access_token(config, claims.sub)
    new_refresh = create_refresh_token(config, claims.sub)

    response = {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "Bearer",
        "expires_in": config.access_ttl_seconds,
        "technical_demo_only": True,
    }
    body_bytes = json.dumps(response).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body_bytes)))
    handler.end_headers()
    handler.wfile.write(body_bytes)


def _handle_login_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/login — serve the login page."""
    from ..login_ui import build_login_page  # noqa: PLC0415

    config = _get_auth_config()
    auth_enabled = config.enabled and not config.validation_error
    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
    base_url = f"{forwarded_proto}://{host_header}"
    html = build_login_page(base_url=base_url, auth_enabled=auth_enabled)
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    handler.wfile.write(body)


def _handle_demo_reports_route(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/api/reports/{job_id}/external and /internal."""
    import re as _re  # noqa: PLC0415
    from urllib.parse import urlsplit as _urlsplit  # noqa: PLC0415
    from .job_api_handler import (  # noqa: PLC0415
        handle_external_report, handle_internal_report,
    )
    route_path = _urlsplit(handler.path).path
    m = _re.match(r"^/demo/api/reports/([^/]+)/external$", route_path)
    if m:
        handle_external_report(handler, m.group(1))
        return
    m = _re.match(r"^/demo/api/reports/([^/]+)/internal$", route_path)
    if m:
        handle_internal_report(handler, m.group(1))
        return
    handler._log_and_send_error(f"Not found: {handler.path}", status=404)
