"""FastAPI serve helper — thin wrapper around uvicorn for the CLI.

This module isolates the ``uvicorn.run`` call so that ``__main__.py``
stays lightweight and tests can monkeypatch without side effects.

Safety
------
- Safe error messages — never prints raw exception details.
  credentials, S3 keys, or JWT secrets.
- Uses the existing ``create_fastapi_app`` factory — never creates
  a second FastAPI application.
- Defaults to loopback (127.0.0.1) binding.
"""

from __future__ import annotations

import sys
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FACTORY_TARGET = "bremen.api.fastapi_app:create_fastapi_app"
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8080
_DEFAULT_LOG_LEVEL = "info"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_fastapi_server(
    *,
    host: str = _DEFAULT_HOST,
    port: int = _DEFAULT_PORT,
    reload: bool = False,
    log_level: str = _DEFAULT_LOG_LEVEL,
) -> int:
    """Start the FastAPI app under uvicorn.

    Parameters
    ----------
    host : Bind address (default 127.0.0.1).
    port : Bind port (default 8080).
    reload : Enable auto-reload (dev only).
    log_level : Uvicorn log level.

    Returns
    -------
    Exit code (0 on success, 1 on failure).
    """
    from ..logging_config import get_logger  # noqa: PLC0415

    _log = get_logger(__name__)

    # Validate uvicorn availability before attempting import
    try:
        import uvicorn  # noqa: PLC0415
    except ImportError:
        print(
            "Error: uvicorn is not installed.\n"
            "Install it with:  pip install uvicorn",
            file=sys.stderr,
        )
        return 1

    _log.info(
        "bremen.cli.serve_fastapi.dispatch\t"
        "stage=startup\tstatus=started\t"
        "host=%s\tport=%s\tlog_level=%s\treload=%s",
        host, port, log_level, reload,
    )

    print(f"Starting Bremen FastAPI server at http://{host}:{port}")
    print(f"ASGI mode (uvicorn) — factory: {_FACTORY_TARGET}")
    print("Dev/smoke mode only. Not for production use.")

    # Suppress access-log noise for /health probes and redact sensitive query
    # params (auth_ticket, access_token, refresh_token, token, ticket) from
    # uvicorn access log records. Redaction is logging/output only.
    import logging as _logging  # noqa: PLC0415
    from ..logging_config import SensitiveQueryRedactionFilter  # noqa: PLC0415

    class _HealthAccessFilter(_logging.Filter):
        """Drop uvicorn access log lines for GET /health."""

        def filter(self, record: _logging.LogRecord) -> bool:
            msg = record.getMessage()
            if isinstance(msg, str) and "GET /health" in msg:
                return False
            return True

    for _logger_name in ("uvicorn.access", "uvicorn"):
        _logger = _logging.getLogger(_logger_name)
        _logger.addFilter(_HealthAccessFilter())
        _logger.addFilter(SensitiveQueryRedactionFilter())

    try:
        uvicorn.run(
            _FACTORY_TARGET,
            host=host,
            port=port,
            factory=True,
            log_level=log_level,
            reload=reload,
        )
    except KeyboardInterrupt:
        _log.info("bremen.cli.serve_fastapi.shutdown\tstage=shutdown\tstatus=interrupted")
        print("\nServer stopped.")
    except Exception as exc:
        # Safe error — print type name only, never raw exception details
        _log.exception("bremen.cli.serve_fastapi.error\tstage=runtime\tstatus=failed")
        print(f"Error: server failed to start — {type(exc).__name__}", file=sys.stderr)
        return 1

    return 0
