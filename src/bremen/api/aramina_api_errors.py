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


def unsupported_input_details(patient: str, side: str, version: str) -> dict:
    """Public input-contract category, not a claim about a private failing step."""
    return {
        "failure_stage": "input_contract",
        "failure_detail": "Selected H5 could not be used for the requested Aramina patient and target side.",
        "safe_details": {
            "patient_display_name": _safe_sample_id(patient) if patient else "",
            "target_side": side if side in {"left", "right"} else "",
            "model_version": version if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", version) else "redacted",
        },
    }
