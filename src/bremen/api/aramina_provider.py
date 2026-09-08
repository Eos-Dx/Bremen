"""Aramina provider contract scaffold.

Defines safe dataclasses, request validation, and normalized result shapes
for future Bremen–Aramina integration.

This is a contract-only scaffold.  No Aramina model is called.
No model.joblib is vendored.  No clinical or regulatory claims are made.

Aramina routing remains closed — workflow_id=aramina is NOT in the
executable allow-list and will not be routed through Bremen.

PR0128 — Aramina provider contract scaffold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import getLogger as _getLogger
from typing import Any, Mapping

_log = _getLogger(__name__)

# ---------------------------------------------------------------------------
# Safe failure stage names — never expose raw exception details
# ---------------------------------------------------------------------------

_ARAMINA_SAFE_FAILURE_STAGES = frozenset({
    "request_payload",
    "container_resolution",
    "aramina_service",
    "aramina_preprocessing",
    "aramina_model_execution",
    "result_normalization",
    "unknown",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AraminaProviderRequest:
    """Validated inbound request for Aramina provider contract.

    All fields are frozen after creation.  No raw paths, S3 keys,
    checksums, tokens, passwords, or model internals are stored.
    """

    container_id: str
    source_id: str
    patient_id: str
    target_side: str  # Normalized to lowercase: "left" or "right"
    analysis_author: str = ""
    prediction_comment: str = ""


@dataclass(frozen=True)
class AraminaProviderResult:
    """Normalized result shape for future Bremen–Aramina integration.

    No probability or risk_score values are invented — those fields
    are reserved for when the Aramina model is actually executed.
    """

    model_family: str = "aramina"
    workflow_id: str = "aramina"
    model_id: str = ""
    model_version: str = ""
    status: str = "passed"  # "passed" | "failed"
    target_side: str = ""
    patient_id_supplied: bool = True
    technical_demo_only: bool = True
    clinical_stage: str = "research draft"
    failure_stage: str | None = None
    safe_reason: str = ""
    # Safe public report derived from the provider response.  Never
    # contains internal_report wholesale or sensitive keys.
    report: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AraminaProviderError:
    """Structured error that never leaks internals.

    Safe failure stages are drawn from _ARAMINA_SAFE_FAILURE_STAGES.
    """

    failure_stage: str = "unknown"
    safe_reason: str = ""
    error_class: str = ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = frozenset({"container_id", "source_id", "patient_id", "target_side"})
_OPTIONAL_FIELDS = frozenset({"analysis_author", "prediction_comment"})
_ALLOWED_TARGET_SIDES = frozenset({"left", "right"})


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def validate_aramina_provider_request(
    payload: Mapping[str, Any],
) -> AraminaProviderRequest:
    """Validate and normalize an inbound Aramina provider request.

    Required fields: container_id, source_id, patient_id, target_side.
    Optional fields: analysis_author, prediction_comment.

    target_side is normalized to lowercase and must be "left" or "right".

    Raises
    ------
    ValueError
        If required fields are missing or target_side is invalid.
        The message is a safe human-readable string — never a traceback,
        path, S3 key, or internal detail.
    """
    missing = [f for f in _REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        raise ValueError(
            f"Missing required fields: {', '.join(sorted(missing))}"
        )

    target_side = str(payload["target_side"]).strip().lower()
    if target_side not in _ALLOWED_TARGET_SIDES:
        raise ValueError(
            f"Invalid target_side: {target_side!r}. "
            f"Allowed values: {', '.join(sorted(_ALLOWED_TARGET_SIDES))}"
        )

    analysis_author_raw = payload.get("analysis_author")
    analysis_author = str(analysis_author_raw).strip() if analysis_author_raw is not None else ""
    prediction_comment_raw = payload.get("prediction_comment")
    prediction_comment = str(prediction_comment_raw).strip() if prediction_comment_raw is not None else ""

    return AraminaProviderRequest(
        container_id=str(payload["container_id"]),
        source_id=str(payload["source_id"]),
        patient_id=str(payload["patient_id"]),
        target_side=target_side,
        analysis_author=analysis_author,
        prediction_comment=prediction_comment,
    )


# ---------------------------------------------------------------------------
# Safe error mapping
# ---------------------------------------------------------------------------


def _safe_aramina_failure_stage(exc: Exception) -> str:
    """Map an exception to a safe stage name for the API response.

    Never exposes traceback, raw exception text, or internal paths.
    """
    msg = str(exc).lower()
    exc_name = type(exc).__name__

    if "request" in msg or "payload" in msg or "missing" in msg:
        return "request_payload"
    if "source" in msg or "upload" in msg or "container" in msg or "resolution" in msg:
        return "container_resolution"
    if "service" in msg or "connect" in msg or "timeout" in msg or "http" in msg:
        return "aramina_service"
    if "preprocess" in msg or "normalize" in msg or "layout" in msg:
        return "aramina_preprocessing"
    if "predict" in msg or "inference" in msg or "model" in msg or "execution" in msg:
        return "aramina_model_execution"
    if "result" in msg or "output" in msg or "parse" in msg:
        return "result_normalization"

    if "ValueError" in exc_name:
        return "request_payload"
    if "ConnectionError" in exc_name or "TimeoutError" in exc_name:
        return "aramina_service"
    if "KeyError" in exc_name:
        return "result_normalization"

    return "unknown"


def build_aramina_safe_error(exc: Exception) -> AraminaProviderError:
    """Wrap an exception into a safe AraminaProviderError.

    No traceback, path, S3 key, bucket, checksum, token, password,
    or model internals are exposed.
    """
    stage = _safe_aramina_failure_stage(exc)
    return AraminaProviderError(
        failure_stage=stage,
        safe_reason="Aramina provider call failed.",
        error_class=type(exc).__name__,
    )
