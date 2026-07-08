"""Inference handler — wires preflight + bridge + portable inference.

Full pipeline from H5 path to prediction JSON.
No prediction route behavior change — this is the handler called
by the API route layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from logging import getLogger as _getLogger
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

_log = _getLogger(__name__)

TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
TRIAGE_RULE_OUT = "MRI_RULE_OUT"


def run_inference(
    h5_path: str,
    patient_id: str | None = None,
    target_scan_ref: str | None = None,
    control_scan_ref: str | None = None,
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
    target_scan_ref : Optional explicit target scan ref for layout-aware
        preflight.  When provided (and ``control_scan_ref`` is provided),
        preflight uses the H5 layout adapter to resolve the target sample
        group path.  When ``None``, the canonical preflight path is used.
    control_scan_ref : Optional explicit control scan ref for layout-aware
        preflight.  Must be provided together with ``target_scan_ref``.

    Returns
    -------
    A dict with all mandatory prediction response fields.
    """
    # 1. H5 received
    explicit_refs = target_scan_ref is not None
    _log.info(
        "bremen.prediction.h5.received\t"
        "stage=h5\tstatus=received\t"
        "h5_input_present=true\t"
        "h5_basename=%s\t"
        "explicit_refs=%s",
        Path(h5_path).name,
        str(explicit_refs).lower(),
    )

    # 2. Preflight
    _log.debug(
        "bremen.prediction.preflight.start\t"
        "stage=preflight\tstatus=started\t"
        "explicit_refs=%s",
        str(explicit_refs).lower(),
    )
    preflight = run_h5_preflight(
        h5_path,
        target_scan_ref=target_scan_ref,
        control_scan_ref=control_scan_ref,
    )
    if not preflight.passed:
        _log.error(
            "bremen.prediction.preflight.failure\t"
            "stage=preflight\tstatus=failed\t"
            "preflight_status=%s",
            preflight.status,
        )
        raise RuntimeError(
            f"Preflight did not pass (status={preflight.status}). "
            f"Reason: {[r.message for r in preflight.reasons if not r.passed]}"
        )

    _log.info(
        "bremen.prediction.preflight.completed\t"
        "stage=preflight\tstatus=completed\t"
        "explicit_refs=%s",
        str(explicit_refs).lower(),
    )

    pid = patient_id or preflight.patient_id or "unknown"

    # 2. Preprocessing bridge
    _log.debug(
        "bremen.prediction.preprocessing.start\t"
        "stage=preprocessing\tstatus=started",
    )
    bridge_result = run_preprocessing_bridge(
        h5_path,
        preflight_result=preflight,
    )
    if not bridge_result.passed or bridge_result.feature_vector is None:
        _log.error(
            "bremen.prediction.preprocessing.failure\t"
            "stage=preprocessing\tstatus=failed\t"
            "reason=bridge_failed_to_produce_features",
        )
        raise RuntimeError("Preprocessing bridge failed to produce features.")

    _log.info(
        "bremen.prediction.preprocessing.completed\t"
        "stage=preprocessing\tstatus=completed\t"
        "feature_count=%s",
        str(len(bridge_result.feature_vector.features)),
    )

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
    _log.debug(
        "bremen.prediction.inference.start\t"
        "stage=inference\tstatus=started",
    )
    try:
        inference_result = predict_proba_portable(
            model_pkg, list(fv.features), skip_validation=True
        )
    except Exception as exc:
        _log.error(
            "bremen.prediction.inference.failure\t"
            "stage=inference\tstatus=failed\t"
            "exception_class=%s\t"
            "safe_reason=%s",
            type(exc).__name__,
            str(exc)[:200],
        )
        raise

    _log.info(
        "bremen.prediction.inference.success\t"
        "stage=inference\tstatus=completed",
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

    _log.info(
        "bremen.prediction.completed\t"
        "stage=prediction\tstatus=completed\t"
        "triage=%s\t"
        "prediction_id=%s",
        triage,
        prediction["prediction_id"],
    )

    return prediction


def _first_mismatch(
    actual: list[str], expected: list[str]
) -> int:
    """Return index of first mismatch."""
    for i, (a, e) in enumerate(zip(actual, expected)):
        if a != e:
            return i
    return -1 if len(actual) == len(expected) else min(len(actual), len(expected))
