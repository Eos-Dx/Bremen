"""Decision-support report wrapper around inference results.

Pure module — no model state, no H5, no network, no runtime dependencies.
Produces a safe, structured report from an existing inference result dict.

PR 0053: Decision Support Output Wrapper.
"""

from __future__ import annotations

from .decision_contract import POSITIVE_MACHINE_CODE, NEGATIVE_MACHINE_CODE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPORT_SCHEMA_VERSION = "v0.1"

INTENDED_USE = (
    "MRI continuation decision support only. "
    "This output is not a diagnosis. "
    "It is not clinically validated. "
    "It does not replace MRI, biopsy, "
    "radiologist, clinician, or clinical judgment."
)

LIMITATIONS = [
    "This is decision-support output only.",
    "Not a diagnostic result.",
    "Not clinically validated.",
    "Does not replace MRI, biopsy, radiologist, clinician, "
    "or clinical judgment.",
    "All clinical decisions must be made by qualified "
    "clinicians based on full patient history and "
    "diagnostic workup.",
]

CAUTION_TEXT = (
    "This is a decision-support recommendation only. "
    "It is not a clinical decision. "
    "The final decision must be made by a qualified "
    "clinician."
)

# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def build_decision_support_report(
    inference_result: dict,
    *,
    input_mode: str | None = None,
    explicit_refs: bool | None = None,
    layout_category: str | None = None,
) -> dict:
    """Build a safe decision-support report around an inference result.

    Parameters
    ----------
    inference_result : The dict returned by ``run_inference()``.
    input_mode : The input mode category (h5_uri, h5_path, or
        future source_record_ref).  Defaults to "unknown" in the report
        when ``None`` is passed.
    explicit_refs : Whether explicit target/control refs were provided.
        ``None`` means unknown — reported as ``null``.
    layout_category : The detected H5 layout category.  Reported as
        ``null`` when ``None``.

    Returns
    -------
    A decision-support report dict. Does NOT contain raw patient
    identifiers, raw H5 paths, full S3 URIs, raw checksums, raw
    feature values, or secrets.
    """
    # --- Safe model metadata ---
    model_metadata: dict = {
        "model_version": inference_result.get("model_version"),
        "feature_schema_version": inference_result.get("feature_schema_version"),
    }
    # Include threshold metadata only when available
    if "threshold_version" in inference_result:
        model_metadata["threshold_version"] = inference_result["threshold_version"]
    if "threshold_value" in inference_result:
        model_metadata["threshold_value"] = inference_result["threshold_value"]

    # --- Safe input summary ---
    input_summary: dict = {
        "input_mode": input_mode or "unknown",
        "explicit_refs_provided": explicit_refs,
        "layout_category": layout_category,
    }

    # --- Safe prediction summary ---
    prediction_summary: dict = {}
    if "p_mri_needed" in inference_result:
        prediction_summary["p_mri_needed"] = inference_result["p_mri_needed"]
    if "triage_recommendation" in inference_result:
        prediction_summary["triage_recommendation"] = (
            inference_result["triage_recommendation"]
        )
    if "qc_status" in inference_result:
        prediction_summary["qc_status"] = inference_result["qc_status"]
    if "qc_flags" in inference_result:
        prediction_summary["qc_flags"] = inference_result["qc_flags"]

    # --- Decision-support framing ---
    triage = inference_result.get("triage_recommendation", "")
    decision_support: dict = {
        "recommendation": triage or None,
        "recommendation_label": _build_recommendation_label(triage),
        "caution": CAUTION_TEXT,
    }

    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "intended_use": INTENDED_USE,
        "limitations": list(LIMITATIONS),
        "model_metadata": model_metadata,
        "input_summary": input_summary,
        "prediction_summary": prediction_summary,
        "decision_support": decision_support,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_recommendation_label(triage: str) -> str:
    """Build a safe recommendation label from the triage value.

    Uses "may be recommended" / "may not be indicated" language.
    Does not claim diagnosis, clinical validation, or clinical certainty.
    """
    if triage == POSITIVE_MACHINE_CODE or triage == "MRI_RECOMMENDED":
        return (
            "Based on the model output, MRI follow-up "
            "may be recommended for this patient."
        )
    if triage == NEGATIVE_MACHINE_CODE or triage == "MRI_RULE_OUT":
        return (
            "Based on the model output, MRI follow-up "
            "may not be indicated for this patient."
        )
    return (
        "Model output is not conclusive. "
        "A qualified clinician must review the full case."
    )
