"""Bremen logging configuration — single point of config.

Idempotent. Safe for testing. No heavy dependencies.
"""

from __future__ import annotations

import logging
import os
import re

_BREMEN_LOG_LEVEL_VAR = "BREMEN_LOG_LEVEL"
_DEFAULT_LOG_LEVEL = "INFO"

# Query parameters whose values must never appear in logs (credential-in-log
# risk). Values are replaced with ``<redacted>``.
_SENSITIVE_QUERY_KEYS = frozenset({
    "auth_ticket",
    "access_token",
    "refresh_token",
    "token",
    "ticket",
})

# Matches ``key=value`` pairs in a query string for the sensitive keys above.
# The value may be URL-encoded or raw; we redact the whole ``key=value`` token.
_SENSITIVE_QUERY_RE = re.compile(
    r"(?P<key>auth_ticket|access_token|refresh_token|token|ticket)"
    r"=[^&\s]*"
)

_REDACTED = "<redacted>"


def redact_sensitive_query_params(text: str) -> str:
    """Redact sensitive query parameter values from a log string.

    Replaces ``key=<value>`` for sensitive keys (auth_ticket, access_token,
    refresh_token, token, ticket) with ``key=<redacted>``. Non-sensitive
    parameters and the rest of the string are preserved unchanged.

    Parameters
    ----------
    text : The raw log message (e.g. a request path with query string).

    Returns
    -------
    The redacted string.
    """
    if not text:
        return text
    return _SENSITIVE_QUERY_RE.sub(
        lambda m: f"{m.group('key')}={_REDACTED}",
        text,
    )


class SensitiveQueryRedactionFilter(logging.Filter):
    """Logging filter that redacts sensitive query params from log records.

    Attach to ``uvicorn.access`` (or any access logger) so that raw short-lived
    JWT tickets and tokens never appear in access logs.  Redaction is
    logging/output only; request handling is not mutated.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Handle uvicorn.access records FIRST — before calling getMessage().
        # uvicorn's AccessFormatter reads record.args[2] directly for the
        # request line.  We must redact args[2] in-place and preserve the
        # 5-tuple arity so AccessFormatter does not raise ValueError.
        if (
            isinstance(record.args, tuple)
            and len(record.args) == 5
            and isinstance(record.args[2], str)
        ):
            redacted_line = redact_sensitive_query_params(record.args[2])
            if redacted_line != record.args[2]:
                record.args = (
                    record.args[0],
                    record.args[1],
                    redacted_line,
                    record.args[3],
                    record.args[4],
                )
            return True

        # Non-uvicorn records: use existing redaction behavior.
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE040
            return True
        if isinstance(msg, str):
            redacted = redact_sensitive_query_params(msg)
            if redacted != msg:
                record.msg = redacted
                record.args = ()
        return True

# Track whether configure_logging has been called for idempotency
_LOGGING_CONFIGURED: bool = False


def configure_logging() -> None:
    """Configure root logger for Bremen runtime.

    - Default level: INFO
    - Override via BREMEN_LOG_LEVEL env var
    - Format: simple tab-separated key=value text
    - Output: stderr (StreamHandler defaults to stderr)
    - Idempotent: safe to call multiple times
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    level_name = os.environ.get(
        _BREMEN_LOG_LEVEL_VAR, _DEFAULT_LOG_LEVEL
    ).upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = "%(levelname)s\t%(name)s\t%(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger already configured for Bremen event format.

    Parameter *name* should be ``__name__`` from the calling module.
    """
    return logging.getLogger(name)


def reset_logging() -> None:
    """Reset the logging configuration flag (for testing only)."""
    global _LOGGING_CONFIGURED
    _LOGGING_CONFIGURED = False
