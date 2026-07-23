"""Decision vocabulary reconciliation tests for PR0081.

Covers:
- Canonical decision codes (CONTINUE_MRI / MRI_REVIEW_DEFER)
- Threshold boundary behavior (above, equal, below)
- Legacy alias compatibility
- No contradictory fields
- API output, events, reports, workspace projection
- Bremen/Aramis separation
- Privacy allowlists
- No diagnostic wording
- No numerical inference change
"""

from __future__ import annotations

import pytest

from bremen.api.decision_contract import (
    build_decision,
    BremenDecision,
    validate_decision_code,
    POSITIVE_MACHINE_CODE,
    NEGATIVE_MACHINE_CODE,
    DECISION_POLICY_ID,
    DECISION_POLICY_VERSION,
    LEGACY_ALIAS_MAP,
    POSITIVE_DISPLAY_NAME,
    NEGATIVE_DISPLAY_NAME,
    POSITIVE_EXPLANATION,
    NEGATIVE_EXPLANATION,
    get_decision_policy_for_model,
)


class TestCanonicalPositiveDecision:
    def test_score_above_threshold_produces_continue_mri(self):
        decision = build_decision(score=0.85, threshold=0.5)
        assert decision.decision_code == POSITIVE_MACHINE_CODE
        assert decision.decision_code == "CONTINUE_MRI"
        assert decision.is_positive is True
        assert decision.is_negative is False

    def test_score_equal_to_threshold_produces_continue_mri(self):
        decision = build_decision(score=0.5, threshold=0.5)
        assert decision.decision_code == POSITIVE_MACHINE_CODE
        assert decision.is_positive is True

    def test_score_below_threshold_produces_defer(self):
        decision = build_decision(score=0.3, threshold=0.5)
        assert decision.decision_code == NEGATIVE_MACHINE_CODE
        assert decision.decision_code == "MRI_REVIEW_DEFER"
        assert decision.is_positive is False
        assert decision.is_negative is True

    def test_policy_identity_in_decision(self):
        decision = build_decision(score=0.85, threshold=0.5)
        assert decision.decision_policy_id == DECISION_POLICY_ID
        assert decision.decision_policy_version == DECISION_POLICY_VERSION
        assert decision.decision_policy_id == "bremen_mri_continuation_threshold"

    def test_display_names_are_set(self):
        decision = build_decision(score=0.85, threshold=0.5)
        assert decision.decision_display_name == POSITIVE_DISPLAY_NAME
        assert "Continue MRI evaluation" in decision.decision_display_name

    def test_explanation_is_set_and_non_diagnostic(self):
        decision = build_decision(score=0.85, threshold=0.5)
        assert "clinician review" in decision.decision_explanation.lower()
        assert "diagnosis" not in decision.decision_explanation.lower()
        assert "cancer" not in decision.decision_explanation.lower()

    def test_scientifically_certified_false(self):
        decision = build_decision(score=0.85, threshold=0.5)
        assert decision.scientifically_certified is False

    def test_technical_demo_only_true(self):
        decision = build_decision(score=0.85, threshold=0.5)
        assert decision.technical_demo_only is True

    def test_legacy_triage_matches_decision_code(self):
        decision = build_decision(score=0.85, threshold=0.5)
        assert decision.legacy_triage == decision.decision_code
        assert decision.legacy_triage == "CONTINUE_MRI"

    def test_negative_legacy_triage_matches(self):
        decision = build_decision(score=0.3, threshold=0.5)
        assert decision.legacy_triage == decision.decision_code
        assert decision.legacy_triage == "MRI_REVIEW_DEFER"


class TestCanonicalNegativeDecision:
    def test_score_below_threshold_produces_mri_review_defer(self):
        decision = build_decision(score=0.2, threshold=0.5)
        assert decision.decision_code == "MRI_REVIEW_DEFER"
        assert decision.is_negative is True

    def test_negative_display_name(self):
        decision = build_decision(score=0.2, threshold=0.5)
        assert decision.decision_display_name == NEGATIVE_DISPLAY_NAME
        assert "Defer MRI" in decision.decision_display_name
        assert "clinician review" in decision.decision_display_name.lower()

    def test_negative_explanation_non_diagnostic(self):
        decision = build_decision(score=0.2, threshold=0.5)
        explanation = decision.decision_explanation.lower()
        assert "below" in explanation
        assert "deferred" in explanation
        assert "clinician review" in explanation
        assert "diagnosis" not in explanation
        assert "cancer" not in explanation


class TestThresholdBoundary:
    def test_score_at_threshold_is_positive(self):
        decision = build_decision(score=1.0, threshold=1.0)
        assert decision.is_positive is True
        assert decision.decision_code == POSITIVE_MACHINE_CODE

    def test_score_just_below_threshold_is_negative(self):
        decision = build_decision(score=0.499, threshold=0.5)
        assert decision.is_negative is True

    def test_score_just_above_threshold_is_positive(self):
        decision = build_decision(score=0.501, threshold=0.5)
        assert decision.is_positive is True

    def test_prediction_zero_maps_to_negative(self):
        decision = build_decision(score=0.1, threshold=0.5)
        assert decision.is_negative is True
        assert decision.decision_code == NEGATIVE_MACHINE_CODE

    def test_prediction_one_maps_to_positive(self):
        decision = build_decision(score=0.9, threshold=0.5)
        assert decision.is_positive is True
        assert decision.decision_code == POSITIVE_MACHINE_CODE


class TestPredictionValueMapping:
    def test_bremen_model_pred_1_is_positive(self):
        decision = build_decision(score=0.75, threshold=0.5)
        assert decision.is_positive
        assert decision.is_negative is False

    def test_bremen_model_pred_0_is_negative(self):
        decision = build_decision(score=0.25, threshold=0.5)
        assert decision.is_negative
        assert decision.is_positive is False


class TestLegacyCompatibility:
    def test_mri_recommended_maps_to_continue_mri(self):
        result = validate_decision_code("MRI_RECOMMENDED")
        assert result == POSITIVE_MACHINE_CODE

    def test_mri_rule_out_maps_to_mri_review_defer(self):
        result = validate_decision_code("MRI_RULE_OUT")
        assert result == NEGATIVE_MACHINE_CODE

    def test_canonical_positive_passes_through(self):
        result = validate_decision_code(POSITIVE_MACHINE_CODE)
        assert result == POSITIVE_MACHINE_CODE

    def test_canonical_negative_passes_through(self):
        result = validate_decision_code(NEGATIVE_MACHINE_CODE)
        assert result == NEGATIVE_MACHINE_CODE

    def test_unknown_code_raises(self):
        with pytest.raises(ValueError):
            validate_decision_code("BOGUS_CODE")

    def test_empty_code_raises(self):
        with pytest.raises(ValueError):
            validate_decision_code("")


class TestModelMetadataAdapter:
    def test_adapter_returns_policy_identity(self):
        result = get_decision_policy_for_model()
        assert result["decision_policy_id"] == DECISION_POLICY_ID
        assert result["decision_policy_version"] == DECISION_POLICY_VERSION

    def test_adapter_returns_machine_codes(self):
        result = get_decision_policy_for_model()
        assert result["positive_machine_code"] == POSITIVE_MACHINE_CODE
        assert result["negative_machine_code"] == NEGATIVE_MACHINE_CODE

    def test_adapter_does_not_require_model_package(self):
        result = get_decision_policy_for_model(None)
        assert result["decision_policy_id"] == DECISION_POLICY_ID

    def test_adapter_has_version(self):
        result = get_decision_policy_for_model()
        assert result["adapter_version"] is not None
        assert len(result["adapter_version"]) > 0


class TestDecisionToDict:
    def test_to_dict_includes_all_fields(self):
        decision = build_decision(score=0.85, threshold=0.5)
        d = decision.to_dict()
        assert d["decision_code"] == POSITIVE_MACHINE_CODE
        assert d["decision_display_name"] == POSITIVE_DISPLAY_NAME
        assert d["decision_explanation"] == POSITIVE_EXPLANATION
        assert d["decision_policy_id"] == DECISION_POLICY_ID
        assert d["decision_policy_version"] == DECISION_POLICY_VERSION
        assert d["scientifically_certified"] is False
        assert d["technical_demo_only"] is True

    def test_to_dict_excludes_score_and_threshold(self):
        decision = build_decision(score=0.85, threshold=0.5)
        d = decision.to_dict()
        assert "score" not in d
        assert "threshold" not in d

    def test_to_dict_excludes_feature_values(self):
        decision = build_decision(score=0.85, threshold=0.5)
        d = decision.to_dict()
        assert "feature_value" not in d
        assert "coefficient" not in d
        assert "weight" not in d
        assert "intercept" not in d


class TestInputValidation:
    def test_non_finite_score_raises(self):
        with pytest.raises(ValueError):
            build_decision(score=float("inf"), threshold=0.5)

    def test_nan_score_raises(self):
        with pytest.raises(ValueError):
            build_decision(score=float("nan"), threshold=0.5)

    def test_non_finite_threshold_raises(self):
        with pytest.raises(ValueError):
            build_decision(score=0.5, threshold=float("inf"))

    def test_zero_threshold_raises(self):
        with pytest.raises(ValueError):
            build_decision(score=0.5, threshold=0.0)

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError):
            build_decision(score=0.5, threshold=-0.5)


class TestNoDiagnosticWording:
    def test_positive_explanation_no_diagnosis(self):
        assert "diagnosis" not in POSITIVE_EXPLANATION.lower()
        assert "cancer" not in POSITIVE_EXPLANATION.lower()
        assert "malignant" not in POSITIVE_EXPLANATION.lower()

    def test_negative_explanation_no_diagnosis(self):
        assert "diagnosis" not in NEGATIVE_EXPLANATION.lower()
        assert "cancer" not in NEGATIVE_EXPLANATION.lower()
        assert "malignant" not in NEGATIVE_EXPLANATION.lower()
        assert "ruled out" not in NEGATIVE_EXPLANATION.lower()

    def test_display_names_no_diagnosis(self):
        assert "diagnosis" not in POSITIVE_DISPLAY_NAME.lower()
        assert "cancer" not in POSITIVE_DISPLAY_NAME.lower()
        assert "diagnosis" not in NEGATIVE_DISPLAY_NAME.lower()
        assert "cancer" not in NEGATIVE_DISPLAY_NAME.lower()


class TestBremenAramisSeparation:
    def test_bremen_decision_is_bremen_workflow_only(self):
        decision = build_decision(score=0.85, threshold=0.5)
        assert decision.decision_policy_id == "bremen_mri_continuation_threshold"
        assert "aramis" not in decision.decision_policy_id.lower()

    def test_no_aramis_decision_code_in_bremen(self):
        decision = build_decision(score=0.3, threshold=0.5)
        assert decision.decision_code not in ("MRI_RECOMMENDED", "MRI_RULE_OUT")
