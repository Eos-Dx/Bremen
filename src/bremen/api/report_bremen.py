"""Bremen MRI triage report (v0.2).

Extends the existing ``decision_support_report`` schema (PR0053) with
workflow readiness, model identity, audit information, measurement QC
summary, supporting technical evidence, and an explicit scientific
certification flag.

PR0077 — multi-workflow analysis workspace, event stream, and reports.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .report_provider import (
    ReportEnvelope,
    ReportProvider,
    REPORT_STATUS_AVAILABLE,
    REPORT_STATUS_UNAVAILABLE,
    REPORT_STATUS_FAILED,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BREMEN_REPORT_SCHEMA_VERSION = "v0.2"

BREMEN_INTENDED_USE = (
    "MRI continuation decision support only. "
    "This output is not a diagnosis. "
    "It is not clinically validated. "
    "It does not replace MRI, biopsy, "
    "radiologist, clinician, or clinical judgment."
)

BREMEN_LIMITATIONS = [
    "This is decision-support output only.",
    "Not a diagnostic result.",
    "Not clinically validated.",
    "Does not replace MRI, biopsy, radiologist, clinician, "
    "or clinical judgment.",
    "All clinical decisions must be made by qualified "
    "clinicians based on full patient history and "
    "diagnostic workup.",
]

BREMEN_CAUTION = (
    "This is a decision-support recommendation only. "
    "It is not a clinical decision. "
    "The final decision must be made by a qualified "
    "clinician."
)

BREMEN_DISCLAIMER = (
    "This is a technical product demo of the Bremen MRI triage "
    "decision-support workflow. It is not a clinical result. "
    "It is not clinically validated. It does not replace MRI, "
    "biopsy, a radiologist, a clinician, or clinical judgment."
)


# ---------------------------------------------------------------------------
# Bremen report provider
# ---------------------------------------------------------------------------


class BremenReportProvider(ReportProvider):
    """Bremen MRI triage report provider.

    Produces a v0.2 report envelope from a Bremen workflow result.
    Owns the Bremen report schema and language rules.
    """

    workflow_id = "bremen"

    def generate_report(
        self,
        job_id: str,
        workflow_result: dict[str, Any],
        *,
        model_identity: dict[str, str] | None = None,
        readiness_snapshot: dict[str, bool] | None = None,
    ) -> ReportEnvelope:
        """Generate a Bremen v0.2 report from workflow output.

        When the workflow result is empty or indicates failure, returns
        an unavailable report with a typed reason code.
        """
        model_identity = model_identity or {}
        readiness_snapshot = readiness_snapshot or {}

        if not workflow_result or workflow_result.get("status") == "failed":
            return ReportEnvelope(
                report_id=str(uuid.uuid4()),
                workflow_id=self.workflow_id,
                job_id=job_id,
                report_schema_version=BREMEN_REPORT_SCHEMA_VERSION,
                workflow_status=REPORT_STATUS_UNAVAILABLE,
                model_id=model_identity.get("model_id"),
                model_version=model_identity.get("model_version"),
                scientifically_certified=readiness_snapshot.get(
                    "scientifically_certified", False
                ),
                disclaimer=BREMEN_DISCLAIMER,
                payload={
                    "reason_code": "WORKFLOW_RESULT_NOT_AVAILABLE",
                    "message": "Bremen workflow did not produce a valid result.",
                },
            )

        try:
            return self._build_report(
                job_id, workflow_result, model_identity, readiness_snapshot,
            )
        except Exception:
            return ReportEnvelope(
                report_id=str(uuid.uuid4()),
                workflow_id=self.workflow_id,
                job_id=job_id,
                report_schema_version=BREMEN_REPORT_SCHEMA_VERSION,
                workflow_status=REPORT_STATUS_FAILED,
                model_id=model_identity.get("model_id"),
                model_version=model_identity.get("model_version"),
                scientifically_certified=readiness_snapshot.get(
                    "scientifically_certified", False
                ),
                disclaimer=BREMEN_DISCLAIMER,
                payload={
                    "reason_code": "REPORT_GENERATION_FAILED",
                    "message": "Internal error generating Bremen report.",
                },
            )

    # ---- Internal ----

    @staticmethod
    def _build_report(
        job_id: str,
        workflow_result: dict[str, Any],
        model_identity: dict[str, str],
        readiness_snapshot: dict[str, bool],
    ) -> ReportEnvelope:
        now = datetime.now(timezone.utc).isoformat()

        probability = workflow_result.get("probability")
        triage = workflow_result.get("triage_recommendation", "")
        threshold = workflow_result.get("threshold_applied")

        # --- Analysis summary ---
        analysis_summary = {
            "product_question": "Should the patient continue to MRI?",
            "intended_use": BREMEN_INTENDED_USE,
            "analysis_type": "mri_triage_decision_support",
        }

        # --- MRI continuation assessment ---
        mri_assessment = {
            "caution": BREMEN_CAUTION,
        }
        if triage == "MRI_RECOMMENDED":
            mri_assessment["assessment"] = (
                "Based on the model output, MRI follow-up "
                "may be recommended for this patient."
            )
        elif triage == "MRI_RULE_OUT":
            mri_assessment["assessment"] = (
                "Based on the model output, MRI follow-up "
                "may not be indicated for this patient."
            )
        else:
            mri_assessment["assessment"] = (
                "Model output is not conclusive. "
                "A qualified clinician must review the full case."
            )

        # --- Score and threshold ---
        score_and_threshold: dict[str, Any] = {}
        if probability is not None:
            score_and_threshold["p_mri_needed"] = probability
        if threshold is not None:
            score_and_threshold["threshold"] = threshold
        if triage:
            score_and_threshold["triage_recommendation"] = triage

        # --- Measurement QC summary ---
        measurement_qc = {
            "qc_status": workflow_result.get("qc_status", "passed"),
            "qc_flags": workflow_result.get("qc_flags", []),
        }

        # --- Supporting technical evidence ---
        technical_evidence: dict[str, Any] = {}
        if probability is not None:
            technical_evidence["logistic_regression_probability"] = probability
        if triage:
            technical_evidence["decision_rule"] = (
                f"probability >= {threshold}" if threshold
                else "threshold-based"
            )

        # --- Model identity ---
        model_id_block = {
            "model_version": model_identity.get(
                "model_version", workflow_result.get("model_version", "unknown")
            ),
            "feature_schema_version": workflow_result.get(
                "feature_schema_version", "v0.1"
            ),
            "model_checksum": model_identity.get("model_checksum", ""),
        }

        # --- Workflow readiness ---
        wf_readiness = {
            "configured": readiness_snapshot.get("configured", True),
            "model_ready": readiness_snapshot.get("model_ready", True),
            "scientifically_certified": readiness_snapshot.get(
                "scientifically_certified", False
            ),
        }

        # --- Audit information ---
        audit = {
            "job_id": job_id,
            "workflow_id": "bremen",
            "report_schema_version": BREMEN_REPORT_SCHEMA_VERSION,
            "generated_at": now,
        }

        payload = {
            "report_schema_version": BREMEN_REPORT_SCHEMA_VERSION,
            "report_type": "bremen_mri_triage",
            "analysis_summary": analysis_summary,
            "mri_continuation_assessment": mri_assessment,
            "score_and_threshold": score_and_threshold,
            "measurement_qc_summary": measurement_qc,
            "supporting_technical_evidence": technical_evidence,
            "model_identity": model_id_block,
            "feature_schema_identity": {
                "feature_schema_version": workflow_result.get(
                    "feature_schema_version", "v0.1"
                ),
            },
            "workflow_readiness": wf_readiness,
            "limitations": list(BREMEN_LIMITATIONS),
            "technical_demo_only_disclaimer": BREMEN_DISCLAIMER,
            "audit_information": audit,
        }

        return ReportEnvelope(
            report_id=str(uuid.uuid4()),
            workflow_id="bremen",
            job_id=job_id,
            report_schema_version=BREMEN_REPORT_SCHEMA_VERSION,
            workflow_status=REPORT_STATUS_AVAILABLE,
            model_id=model_identity.get("model_id"),
            model_version=model_identity.get("model_version"),
            scientifically_certified=readiness_snapshot.get(
                "scientifically_certified", False
            ),
            disclaimer=BREMEN_DISCLAIMER,
            payload=payload,
        )
