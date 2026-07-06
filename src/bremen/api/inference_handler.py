"""Inference handler — wires preflight + bridge + portable inference.

Full pipeline from H5 path to prediction JSON.
No prediction route behavior change — this is the handler called
by the API route layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .model_state import ModelState
from .preflight import run_h5_preflight
from .preprocessing_bridge import (
    run_preprocessing_bridge,
    BREMEN_V01_FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
)
from ..inference import (
    validate_portable_logreg_model,
    predict_proba_portable,
)

TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
TRIAGE_RULE_OUT = "MRI_RULE_OUT"


def run_inference(
    h5_path: str,
    patient_id: str | None = None,
) -> dict[str, Any]:
    """Run full inference pipeline from H5 path to prediction JSON.

    Steps:
    1. Preflight H5 container.
    2. Preprocessing bridge (feature extraction).
    3. Validate bridge schema matches model ``feature_columns``.
    4. Portable logistic regression inference.
    5. Apply threshold → triage decision.
    6. Assemble prediction JSON.

    Parameters
    ----------
    h5_path : Path to the H5 container.
    patient_id : Optional override for patient ID.  If ``None``,
        the patient ID from the H5 container is used.

    Returns
    -------
    A dict with all mandatory prediction response fields.
    """
    # 1. Preflight
    preflight = run_h5_preflight(h5_path)
    if not preflight.passed:
        raise RuntimeError(
            f"Preflight did not pass (status={preflight.status}). "
            f"Reason: {[r.message for r in preflight.reasons if not r.passed]}"
        )

    pid = patient_id or preflight.patient_id or "unknown"

    # 2. Preprocessing bridge
    bridge_result = run_preprocessing_bridge(
        h5_path,
        preflight_result=preflight,
    )
    if not bridge_result.passed or bridge_result.feature_vector is None:
        raise RuntimeError("Preprocessing bridge failed to produce features.")

    fv = bridge_result.feature_vector

    # 3. Validate bridge schema matches model feature_columns
    model_pkg = ModelState.get_model()
    if model_pkg is None:
        raise RuntimeError("Model not loaded. Cannot run inference.")

    # Validate portable_logreg model structure
    try:
        validate_portable_logreg_model(model_pkg)
    except Exception as exc:
        raise RuntimeError(f"Model validation failed: {exc}") from exc

    # 4. Validate feature names match model
    plr = model_pkg["portable_logreg"]
    model_cols = [str(c) for c in plr["feature_columns"]]
    if fv.feature_names != model_cols:
        raise RuntimeError(
            f"Feature column mismatch. Bridge has {len(fv.feature_names)} "
            f"columns but model expects {len(model_cols)} columns. "
            f"First mismatch at index "
            f"{_first_mismatch(fv.feature_names, model_cols)}."
        )

    # 5. Portable inference
    inference_result = predict_proba_portable(
        model_pkg, list(fv.features), skip_validation=True
    )

    # 6. Threshold and triage
    prob = inference_result["probability"]
    threshold = inference_result["threshold_applied"]
    triage = TRIAGE_RECOMMENDED if prob >= threshold else TRIAGE_RULE_OUT

    # 7. Gather model metadata
    model_version = plr.get("model_version", "") or str(
        ModelState.get_instance()._model_version or ""
    )
    model_checksum = str(
        ModelState.get_instance()._model_checksum or ""
    )
    threshold_version = plr.get("threshold_version", "") or "v0.1"

    # 8. Assemble prediction JSON
    created_at = datetime.now(timezone.utc).isoformat()

    prediction = {
        "prediction_id": str(uuid.uuid4()),
        "model_version": model_version,
        "model_checksum": model_checksum,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "threshold_version": threshold_version,
        "threshold_value": float(threshold),
        "qc_status": "passed" if bridge_result.passed else "failed",
        "qc_flags": bridge_result.qc_flags,
        "patient_id": pid,
        "p_mri_needed": float(prob),
        "triage_recommendation": triage,
        "created_at_utc": created_at,
    }

    return prediction


def _first_mismatch(
    actual: list[str], expected: list[str]
) -> int:
    """Return index of first mismatch."""
    for i, (a, e) in enumerate(zip(actual, expected)):
        if a != e:
            return i
    return -1 if len(actual) == len(expected) else min(len(actual), len(expected))
