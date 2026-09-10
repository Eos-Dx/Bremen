"""Safe, transport-independent Aramina API diagnostics (no inference changes)."""

from __future__ import annotations

import re
from typing import Any


def is_aramina_selection(body: Any) -> bool:
    """Use catalog routing precedence, including requests failing schema validation."""
    from .model_registry import get_model_entry

    if not isinstance(body, dict):
        return False
    model_id = body.get("model_id")
    entry = get_model_entry(model_id) if isinstance(model_id, str) else None
    return (entry.workflow_id if entry else body.get("workflow_id")) == "aramina"


def invalid_request_details(body: dict) -> dict:
    """Expose field names and remediation, never invalid field values."""
    missing = []
    for field in ("patient_id", "target_side"):
        value = body.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return {
        "error": "Invalid Aramina request fields",
        "error_code": "ARAMINA_INVALID_REQUEST",
        "missing_required_fields": missing,
        "required_fields": ["source_id", "model_id", "workflow_id", "patient_id", "target_side"],
        "allowed_target_side": ["left", "right"],
        "remediation": (
            "Refresh /demo/api/h5/containers, then submit a fresh source_id "
            "with patient_id and target_side."
        ),
        "technical_demo_only": True,
    }


def source_error_details(exc: ValueError) -> dict:
    """Distinguish unavailable handles from other failures without exception text."""
    from .source_registry import SourceUnavailableError

    result = {
        "error": "Could not resolve the selected source.",
        "error_code": "SOURCE_ERROR",
        "technical_demo_only": True,
    }
    if isinstance(exc, SourceUnavailableError):
        result.update({
            "error": "The selected source is no longer available. Please select another container or re-upload.",
            "reason_code": "SOURCE_ID_NOT_AVAILABLE",
            "remediation": "Refresh /demo/api/h5/containers and retry with a fresh source_id.",
        })
    return result


def _safe_sample_id(value: str) -> str:
    # Echo only short sample identifiers; never paths or free-form metadata.
    return value if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value) else "redacted"


def patient_mismatch_details(requested: str, resolved: str) -> dict | None:
    """Compare known H5 identity without deriving identity from filenames."""
    if not resolved or requested.strip() == resolved.strip():
        return None
    return {
        "error": "Aramina request patient_id does not match selected source.",
        "error_code": "ARAMINA_PATIENT_MISMATCH",
        "requested_patient_id": _safe_sample_id(requested.strip()),
        "resolved_patient_display_name": _safe_sample_id(resolved.strip()),
        "remediation": "Use the patient_display_name returned by /demo/api/h5/containers for the selected source_id.",
        "technical_demo_only": True,
    }


def _safe_identifier(value: str) -> str:
    """Echo only short opaque identifiers; never paths or free-form metadata."""
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) else "redacted"


def _safe_basename(value: str) -> str:
    """Return a sanitized basename only when it is already a public label.

    Rejects anything containing a path separator, scheme, or free-form text.
    """
    if not value or "/" in value or "\\" in value or "://" in value:
        return ""
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) else ""


def _safe_sides(values: Any) -> list[str]:
    """Return only allowlisted side labels, sorted and de-duplicated."""
    if not isinstance(values, (list, tuple, set, frozenset)):
        return []
    return sorted({v for v in values if v in {"left", "right"}})


def _safe_count(value: Any) -> int | None:
    """Return a non-negative integer count, or None when unknown/unsafe."""
    if type(value) is int and value >= 0:
        return value
    return None


def unsupported_input_details(
    patient: str,
    side: str,
    version: str,
    *,
    stage: str | None = None,
    model_id: str = "",
    requested_patient_id: str = "",
    resolved_container_id: str = "",
    available_sides: Any = None,
    measurement_count: Any = None,
    preprocessing_release: str = "",
) -> dict:
    """Public input-contract category with an exact safe failing boundary.

    PR0141: ``failure_stage`` is now the allowlisted runtime boundary that
    failed, not a generic ``input_contract`` label. Unknown or missing stages
    collapse to ``unknown_input_contract``. No exception text, path, S3 key,
    stdout/stderr, env var, or measurement data is ever included.
    """
    from .workflow_aramina import FAILURE_STAGES, _STAGE_DETAIL, _STAGE_REMEDIATION

    safe_stage = stage if stage in FAILURE_STAGES else "unknown_input_contract"
    safe_details: dict[str, Any] = {
        "patient_display_name": _safe_sample_id(patient) if patient else "",
        "requested_patient_id": _safe_sample_id(requested_patient_id) if requested_patient_id else "",
        "target_side": side if side in {"left", "right"} else "",
        "model_id": _safe_identifier(model_id) if model_id else "",
        "model_version": _safe_identifier(version) if version else "",
    }
    # Optional fields are omitted entirely when unknown, so the public shape
    # never implies knowledge the runtime does not have.
    container = _safe_basename(resolved_container_id)
    if container:
        safe_details["resolved_container_id"] = container
    sides = _safe_sides(available_sides)
    if sides:
        safe_details["available_sides"] = sides
    count = _safe_count(measurement_count)
    if count is not None:
        safe_details["measurement_count"] = count
    if preprocessing_release in {"v0.1.7-beta", "v0.1.9-beta"}:
        safe_details["preprocessing_release"] = preprocessing_release

    return {
        "failure_stage": safe_stage,
        "failure_reason_code": f"ARAMINA_UNSUPPORTED_INPUT_{safe_stage.upper()}",
        "failure_detail": _STAGE_DETAIL[safe_stage],
        "remediation": _STAGE_REMEDIATION[safe_stage],
        "safe_details": safe_details,
    }
