"""Safe report projection of existing workflow failures; no model science.

Never copy failure detail dictionaries or arbitrary exception strings into a
report. Reuse established public diagnostics and fixed reporting categories.
"""
from __future__ import annotations

import re
from typing import Any

from bremen.platform.reports.diagnostics import unsupported_input_details
from bremen.model_packages.aramina_v0213.errors import _SAFE_FAILURES

# Existing provider messages, matched exactly (no interpretation of model gates).
_BREMEN_FAILURES = {
    "Feature construction failed: raw_peak_gate_failed": ("raw_peak_gate_failed", "features"),
    "Feature construction failed: invalid_scientific_profiles": ("invalid_scientific_profiles", "features"),
    "Incompatible: requires_exactly_3_left_3_right": ("requires_exactly_3_left_3_right", "input"),
    "Incompatible: invalid_feature_schema": ("invalid_feature_schema", "input"),
    "Incompatible: raw_container_required": ("raw_container_required", "input"),
    "Incompatible: not_a_canonical_case": ("not_a_canonical_case", "input"),
    "Workflow configuration required for multi-position input": ("workflow_configuration_required", "configuration"),
    "Model not ready": ("model_not_ready", "model"),
    "Model execution failed": ("model_execution_failed", "inference"),
    "Workflow unavailable — model not ready": ("model_not_ready", "model"),
}


def _identifier(value: Any) -> str:
    """Bounded public identifier only; never paths or diagnostic free text."""
    if not isinstance(value, str):
        return ""
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) else ""


def build_failure_report(
    workflow_id: str, *, failure: Any = None, failure_details: Any = None,
    model_identity: Any = None, job_context: Any = None,
    normalization_failed: bool = False,
) -> dict[str, Any]:
    """Preserve unavailable/report reason keys and add safe failure metadata."""
    identity = model_identity if isinstance(model_identity, dict) else {}
    context = job_context if isinstance(job_context, dict) else {}
    details = failure_details if isinstance(failure_details, dict) else {}
    failure = failure if isinstance(failure, str) else ""
    side = context.get("target_side")
    result = {
        "status": "unavailable",
        "reason_code": "REPORT_NOT_AVAILABLE",
        "failure": "WORKFLOW_EXECUTION_FAILED",
        "failure_stage": "workflow",
        "failure_reason_code": "WORKFLOW_EXECUTION_FAILED",
        "failure_detail": "The workflow did not produce a valid result.",
        "remediation": "Review the selected source and model configuration before retrying.",
        "workflow_id": _identifier(workflow_id),
        "model_id": _identifier(identity.get("model_id")),
        "model_version": _identifier(identity.get("model_version")),
        "patient_id": _identifier(context.get("patient_id")),
        "target_side": side if isinstance(side, str) and side in {"left", "right"} else "",
        "safe_details": {},
    }
    if normalization_failed:
        result.update(
            failure="SOURCE_PREPARATION_FAILED", failure_stage="normalization",
            failure_reason_code="SOURCE_PREPARATION_FAILED",
            failure_detail="The source could not be prepared for model execution.",
        )
    elif workflow_id == "bremen" and failure in _BREMEN_FAILURES:
        code, stage = _BREMEN_FAILURES[failure]
        result.update(failure=failure, failure_stage=stage, failure_reason_code=code,
                      failure_detail=failure)
    elif workflow_id == "aramina" and failure in _SAFE_FAILURES:
        result.update(failure=failure, failure_reason_code=failure)
        if failure == "ARAMINA_UNSUPPORTED_INPUT":
            # Rebuild the established safe vocabulary; ignore supplied free text.
            safe = details.get("safe_details")
            safe = safe if isinstance(safe, dict) else {}
            stage = details.get("failure_stage")
            diagnostic = {k: v for k, v in safe.items() if isinstance(v, str)}
            result.update(unsupported_input_details(
                result["patient_id"], result["target_side"], result["model_version"],
                stage=stage if isinstance(stage, str) else None,
                model_id=result["model_id"],
                requested_patient_id=_identifier(safe.get("requested_patient_id")),
                preprocessing_release=diagnostic.get("preprocessing_release", ""),
                preprocessing_diagnostic=diagnostic,
            ))
    return result
