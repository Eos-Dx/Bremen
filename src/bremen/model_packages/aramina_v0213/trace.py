"""Aramina private diagnostics — opt-in checkpoints and failure-stage trace.

Moved verbatim from ``bremen.api.workflow_aramina`` by PR0156.  This is
private runtime diagnostics only: nothing here is attached to public events,
reports or API responses.  The single environment switch
(``BREMEN_ARAMINA_DEBUG_TRACE``) and the allowlisted label/stage redaction are
unchanged.  The log record name reflects this module's location
(``bremen.model_packages.aramina_v0213.trace``); it is not part of any public
contract.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import Any

from bremen.model_packages.aramina_v0213.errors import (
    AraminaWorkflowError,
    _TRACE_LABELS,
    _TRACE_STAGES,
)


def _debug_checkpoint(stage: str, *, _failure: bool = False, **fields: Any) -> None:  # noqa: D401
    """Private diagnostics: opt-in checkpoints and always-on failure stages.

    Only fixed metadata labels and numeric shapes/counts survive. Unknown
    artifact keys, columns, class names, and sides are redacted. Nothing is
    attached to public events, reports, or API responses.
    """
    if stage not in _TRACE_STAGES:
        return
    if not _failure and os.environ.get("BREMEN_ARAMINA_DEBUG_TRACE") != "1":
        return
    try:
        safe = {}
        for key, value in fields.items():
            if value is None or type(value) in (bool, int):
                safe[key] = value
            elif isinstance(value, str):
                safe[key] = value if value in _TRACE_LABELS | _TRACE_STAGES else "redacted"
            elif isinstance(value, (list, tuple)):
                safe[key] = [
                    item if type(item) is int or (
                        isinstance(item, str) and item in _TRACE_LABELS
                    ) else "redacted" for item in value
                ]
        logging.getLogger(__name__).warning(
            "%s %s", "aramina.runtime.rejected" if _failure else "aramina.debug_trace",
            json.dumps({"stage": stage, **safe}),
        )
    except Exception:  # noqa: BLE001, S110 -- logging failures must not affect inference
        # Diagnostics must never change inference or public failure behavior.
        pass


@contextmanager
def _debug_stage(stage: str, group: str = "execution"):
    """Record the original exception class before public error translation.

    PR0141: an inner boundary may already have translated the failure into an
    ``AraminaWorkflowError``. In that case the original exception class is
    carried on the error so the private trace still names the real cause
    instead of the translation wrapper.
    """
    try:
        yield
    except Exception as exc:
        name = type(exc).__name__
        if isinstance(exc, AraminaWorkflowError):
            # Prefer the original cause. When the cause class is unknown or
            # unsafe, report a fixed label rather than the translation
            # wrapper name, which would misattribute the failure.
            name = exc.original_exception_class or "redacted"
        if name not in _TRACE_LABELS:
            name = "redacted"
        _debug_checkpoint(stage, **{
            f"{group}_exception_class": name,
            f"{group}_exception_stage": stage,
        })
        _debug_checkpoint(stage, _failure=True, **{
            f"{group}_exception_class": name,
            f"{group}_exception_stage": stage,
        })
        # Stage comes from a fixed call-site literal, not exception contents.
        raise


__all__ = ["_debug_checkpoint", "_debug_stage"]
