"""Inference handler — wires preflight + bridge + portable inference.

LEGACY: ``run_inference`` is now a thin backward-compatible wrapper
over ``run_workflow_request``.  Public inference paths use the
workflow orchestrator directly.

The old preflight/bridge/inference pipeline is no longer called
from public routes.  Internal helper functions may remain for
isolated historical tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from logging import getLogger as _getLogger
from pathlib import Path
from typing import Any

from .model_state import ModelState
from .preprocessing_bridge import (
    BREMEN_V01_FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
)
from ..inference import (
    validate_portable_logreg_model,
    predict_proba_portable,
)
from .decision_support import build_decision_support_report

_log = _getLogger(__name__)

TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
TRIAGE_RULE_OUT = "MRI_RULE_OUT"


def run_inference(
    h5_path: str,
    patient_id: str | None = None,
    target_scan_ref: str | None = None,
    control_scan_ref: str | None = None,
    input_mode: str | None = None,
) -> dict[str, Any]:
    """Legacy compatibility wrapper — delegates to ``run_workflow_request``.

    This function preserves the existing external result shape for
    callers that depend on the old dict-based return format.  It does
    NOT call the legacy preflight/bridge/inference pipeline directly.

    Default ``workflow_id="bremen"`` exists only at this backward-
    compatibility boundary.  It is never inferred from H5 layout,
    filename, metadata, or model package.

    Parameters
    ----------
    h5_path : Path to the H5 container.
    patient_id : Optional override for patient ID.  When ``None``,
        the patient ID from the H5 container is used.
    target_scan_ref : Optional explicit target scan ref.
    control_scan_ref : Optional explicit control scan ref.
    input_mode : Optional input mode category ("h5_uri", "h5_path").

    Returns
    -------
    A dict with all mandatory prediction response fields, matching
    the legacy ``run_inference`` return shape.
    """
    from .workflow_orchestrator import run_workflow_request  # noqa: PLC0415

    _log.info(
        "bremen.prediction.legacy_wrapper\t"
        "stage=prediction\tstatus=delegating\t"
        "target=new_orchestrator",
    )

    mw_result = run_workflow_request(
        h5_path=h5_path,
        workflow_id="bremen",
        target_scan_ref=target_scan_ref,
        control_scan_ref=control_scan_ref,
    )

    bremen_result = mw_result.workflows.get("bremen")
    if bremen_result is None or bremen_result.payload is None:
        # Workflow not found or not executed
        raise RuntimeError(
            f"Bremen workflow failed: "
            f"{bremen_result.error if bremen_result else 'no result'}"
        )

    payload = bremen_result.payload

    # Gather model metadata for backward compatibility
    model_version = payload.get("model_version", "")
    model_checksum = payload.get("model_checksum", "")
    threshold_value = float(payload.get("threshold_applied", 0.5))
    prob = float(payload.get("probability", 0.0))
    triage = payload.get("triage_recommendation", TRIAGE_RULE_OUT)

    created_at = datetime.now(timezone.utc).isoformat()

    prediction = {
        "prediction_id": payload.get("prediction_id", str(uuid.uuid4())),
        "model_version": model_version,
        "model_checksum": model_checksum,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "threshold_version": "v0.1",
        "threshold_value": threshold_value,
        "qc_status": "passed",
        "qc_flags": [],
        "patient_id": patient_id or "unknown",
        "p_mri_needed": prob,
        "triage_recommendation": triage,
        "created_at_utc": created_at,
    }

    # Build decision-support report around the prediction result
    prediction["decision_support_report"] = build_decision_support_report(
        prediction,
        input_mode=input_mode or "unknown",
        explicit_refs=target_scan_ref is not None,
        layout_category="canonical",
    )

    _log.info(
        "bremen.prediction.completed\t"
        "stage=prediction\tstatus=completed\t"
        "triage=%s\t"
        "prediction_id=%s",
        triage,
        prediction["prediction_id"],
    )

    return prediction
