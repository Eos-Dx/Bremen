"""Bremen logging configuration — single point of config.

Idempotent. Safe for testing. No heavy dependencies.
"""

from __future__ import annotations

import logging
import os

_BREMEN_LOG_LEVEL_VAR = "BREMEN_LOG_LEVEL"
_DEFAULT_LOG_LEVEL = "INFO"

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
