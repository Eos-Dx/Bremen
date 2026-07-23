"""Bremen decision-policy contract — single authoritative vocabulary source.

Defines machine codes, display vocabulary, policy identity, threshold
application, and legacy alias handling for the Bremen MRI continuation
decision.

PR0081 — Bremen Decision Vocabulary Reconciliation.

This is the ONLY source of truth for Bremen decision vocabulary.
No API, event, report, trace, or workspace surface may define its own
decision vocabulary constants or independently apply thresholds.

DecisionOutput (lifecycle_contracts.py) is a downstream event projection
created from a BremenDecision instance and must not independently apply
thresholds, map labels, or define vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Canonical machine codes — stable, versioned, suitable for API/audit/events
# ---------------------------------------------------------------------------

POSITIVE_MACHINE_CODE: str = "CONTINUE_MRI"
NEGATIVE_MACHINE_CODE: str = "MRI_REVIEW_DEFER"

# ---------------------------------------------------------------------------
# Controlled display vocabulary — human-readable, non-diagnostic
# ---------------------------------------------------------------------------

POSITIVE_DISPLAY_NAME: str = "Continue MRI evaluation"
NEGATIVE_DISPLAY_NAME: str = "Defer MRI pending clinician review"

POSITIVE_EXPLANATION: str = (
    "The model score meets or exceeds the configured decision threshold. "
    "This case is flagged for clinician review regarding continuation to MRI."
)
NEGATIVE_EXPLANATION: str = (
    "The model score is below the configured decision threshold. "
    "MRI continuation may be deferred, subject to clinician review "
    "and the complete clinical context."
)

# ---------------------------------------------------------------------------
# Policy identity — versioned contract
# ---------------------------------------------------------------------------

DECISION_POLICY_ID: str = "bremen_mri_continuation_threshold"
DECISION_POLICY_VERSION: str = "0.1.0"

# ---------------------------------------------------------------------------
# Clinical question — the Bremen product scope
# ---------------------------------------------------------------------------

CLINICAL_QUESTION: str = "Should the patient continue to MRI?"

# ---------------------------------------------------------------------------
# Legacy alias map — accepted at compatibility boundary only
# ---------------------------------------------------------------------------

LEGACY_ALIAS_MAP: dict[str, str] = {
    "MRI_RECOMMENDED": POSITIVE_MACHINE_CODE,
    "MRI_RULE_OUT": NEGATIVE_MACHINE_CODE,
}

# ---------------------------------------------------------------------------
# BremenDecision — canonical decision object for one inference run
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BremenDecision:
    """A single canonical Bremen decision produced from numerical inference.

    Created exactly once per successful inference run from score,
    threshold, and the decision policy.  All downstream surfaces (API,
    events, reports, traces, workspace) derive their decision fields
    from this object.

    Fields
    ------
    decision_code : Canonical machine-readable code (CONTINUE_MRI or
        MRI_REVIEW_DEFER).
    decision_display_name : Human-readable controlled display text.
    decision_explanation : One-sentence clinical context explanation.
    score : The computed probability (sigmoid output).
    threshold : The threshold value applied for the decision.
    decision_policy_id : The decision policy that produced this result.
    decision_policy_version : Version of the decision policy.
    scientifically_certified : Always ``False`` until certified.
    technical_demo_only : Always ``True``.
    """

    decision_code: str
    decision_display_name: str
    decision_explanation: str
    score: float
    threshold: float
    decision_policy_id: str
    decision_policy_version: str
    scientifically_certified: bool = False
    technical_demo_only: bool = True

    @property
    def is_positive(self) -> bool:
        """Return ``True`` when the decision code is the positive outcome."""
        return self.decision_code == POSITIVE_MACHINE_CODE

    @property
    def is_negative(self) -> bool:
        """Return ``True`` when the decision code is the negative outcome."""
        return self.decision_code == NEGATIVE_MACHINE_CODE

    @property
    def legacy_triage(self) -> str:
        """Return the legacy triage_recommendation field value.

        During the compatibility period, this field carries the canonical
        machine code.  Future versions may deprecate this.
        """
        return self.decision_code

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a safe dictionary for API/event/report surfaces.

        Does NOT expose feature values, coefficients, weights, intercept,
        scaler/imputer parameters, raw arrays, private paths, or patient
        identifiers.
        """
        return {
            "decision_code": self.decision_code,
            "decision_display_name": self.decision_display_name,
            "decision_explanation": self.decision_explanation,
            "decision_policy_id": self.decision_policy_id,
            "decision_policy_version": self.decision_policy_version,
            "scientifically_certified": self.scientifically_certified,
            "technical_demo_only": self.technical_demo_only,
        }


# ---------------------------------------------------------------------------
# Factory — create a BremenDecision from numerical inference result
# ---------------------------------------------------------------------------


def build_decision(
    score: float,
    threshold: float,
    *,
    scientifically_certified: bool = False,
) -> BremenDecision:
    """Create a canonical BremenDecision from numerical inference output.

    This is the ONE place where threshold comparison occurs for decision
    vocabulary.  No API, event, report, or workspace surface may perform
    its own threshold comparison.

    Parameters
    ----------
    score : The sigmoid probability from portable logistic regression.
    threshold : The threshold value from the model package.
    scientifically_certified : Always ``False`` until certified.

    Returns
    -------
    A ``BremenDecision`` with the correct canonical machine code and
    display vocabulary.

    Raises
    ------
    ValueError
        If *score* or *threshold* is not finite, or if *threshold* is
        not a positive float.
    """
    if not isinstance(score, (int, float)) or not (
        -float("inf") < float(score) < float("inf")
    ):
        raise ValueError(f"score must be finite, got {score!r}")
    if not isinstance(threshold, (int, float)) or float(threshold) <= 0 or not (
        -float("inf") < float(threshold) < float("inf")
    ):
        raise ValueError(f"threshold must be positive and finite, got {threshold!r}")

    score_f = float(score)
    threshold_f = float(threshold)

    # prediction = 1 is the positive class (above-threshold)
    # prediction = 0 is the negative class (below-threshold)
    #
    # The same >= comparison operator used by the numerical inference
    # at run_inference() in workflow_bremen.py: prediction = 1 if prob >= threshold else 0
    if score_f >= threshold_f:
        code = POSITIVE_MACHINE_CODE
        display = POSITIVE_DISPLAY_NAME
        explanation = POSITIVE_EXPLANATION
    else:
        code = NEGATIVE_MACHINE_CODE
        display = NEGATIVE_DISPLAY_NAME
        explanation = NEGATIVE_EXPLANATION

    return BremenDecision(
        decision_code=code,
        decision_display_name=display,
        decision_explanation=explanation,
        score=score_f,
        threshold=threshold_f,
        decision_policy_id=DECISION_POLICY_ID,
        decision_policy_version=DECISION_POLICY_VERSION,
        scientifically_certified=scientifically_certified,
        technical_demo_only=True,
    )


# ---------------------------------------------------------------------------
# Validation — fail-closed on unknown codes
# ---------------------------------------------------------------------------


def validate_decision_code(code: str) -> str:
    """Validate and normalise a decision code.

    Accepts canonical codes (CONTINUE_MRI, MRI_REVIEW_DEFER) and legacy
    aliases (MRI_RECOMMENDED, MRI_RULE_OUT).  Returns the canonical code.

    Raises ``ValueError`` for unknown codes.
    """
    if code in (POSITIVE_MACHINE_CODE, NEGATIVE_MACHINE_CODE):
        return code
    if code in LEGACY_ALIAS_MAP:
        return LEGACY_ALIAS_MAP[code]
    raise ValueError(
        f"Unknown decision code: {code!r}. "
        f"Expected one of {POSITIVE_MACHINE_CODE!r}, "
        f"{NEGATIVE_MACHINE_CODE!r}, or accepted legacy aliases."
    )


# ---------------------------------------------------------------------------
# Model metadata adapter — inject policy metadata the model package lacks
# ---------------------------------------------------------------------------

# The current portable_logreg model package does not contain:
#   class_labels, positive_class, decision_policy_id, decision_policy_version
#
# This adapter supplies those missing fields at runtime without mutating
# the stored model package on S3.  It does NOT alter numerical inference.
# It does NOT claim the vocabulary is embedded in the training artifact.

MODEL_METADATA_ADAPTER_VERSION: str = "0.1.0"


def get_decision_policy_for_model(
    model_package: dict | None = None,
) -> dict[str, Any]:
    """Return the decision policy to apply for the currently configured model.

    Parameters
    ----------
    model_package : The portable_logreg model package dict (not mutated).

    Returns
    -------
    A dict with safe decision-policy metadata.
    """
    return {
        "decision_policy_id": DECISION_POLICY_ID,
        "decision_policy_version": DECISION_POLICY_VERSION,
        "positive_machine_code": POSITIVE_MACHINE_CODE,
        "negative_machine_code": NEGATIVE_MACHINE_CODE,
        "positive_display_name": POSITIVE_DISPLAY_NAME,
        "negative_display_name": NEGATIVE_DISPLAY_NAME,
        "adapter_version": MODEL_METADATA_ADAPTER_VERSION,
        "adapter_note": (
            "Model package lacks explicit decision-policy metadata. "
            "This adapter supplies the runtime policy identity. "
            "Numerical inference (coefficients, threshold, class order) "
            "is unchanged."
        ),
    }
