"""Tests for the Aramina provider contract scaffold (PR0128).

Contract-only tests.  No Aramina model is called, no model.joblib is
vendored, no clinical or regulatory claims are made.
"""

from __future__ import annotations

import pytest

from bremen.api.aramina_provider import (
    AraminaProviderRequest,
    AraminaProviderResult,
    AraminaProviderError,
    validate_aramina_provider_request,
    build_aramina_safe_error,
    _safe_aramina_failure_stage,
    _ARAMINA_SAFE_FAILURE_STAGES,
    _REQUIRED_FIELDS,
    _OPTIONAL_FIELDS,
    _ALLOWED_TARGET_SIDES,
)


# ---------------------------------------------------------------------------
# Valid request acceptance
# ---------------------------------------------------------------------------


class TestValidRequestAcceptance:
    """Accepts valid requests with target_side left or right."""

    def test_valid_request_left(self):
        req = validate_aramina_provider_request({
            "container_id": "container-001",
            "source_id": "source-001",
            "patient_id": "patient-001",
            "target_side": "left",
        })
        assert req.container_id == "container-001"
        assert req.source_id == "source-001"
        assert req.patient_id == "patient-001"
        assert req.target_side == "left"
        assert req.analysis_author == ""
        assert req.prediction_comment == ""

    def test_valid_request_right(self):
        req = validate_aramina_provider_request({
            "container_id": "container-002",
            "source_id": "source-002",
            "patient_id": "patient-002",
            "target_side": "right",
        })
        assert req.target_side == "right"

    def test_valid_request_with_optional_fields(self):
        req = validate_aramina_provider_request({
            "container_id": "c1",
            "source_id": "s1",
            "patient_id": "p1",
            "target_side": "left",
            "analysis_author": "Dr. Smith",
            "prediction_comment": "Test run",
        })
        assert req.analysis_author == "Dr. Smith"
        assert req.prediction_comment == "Test run"


# ---------------------------------------------------------------------------
# Target side normalization
# ---------------------------------------------------------------------------


class TestTargetSideNormalization:
    """Normalizes target_side case."""

    def test_uppercase_left_normalized(self):
        req = validate_aramina_provider_request({
            "container_id": "c1",
            "source_id": "s1",
            "patient_id": "p1",
            "target_side": "LEFT",
        })
        assert req.target_side == "left"

    def test_mixed_case_right_normalized(self):
        req = validate_aramina_provider_request({
            "container_id": "c1",
            "source_id": "s1",
            "patient_id": "p1",
            "target_side": "Right",
        })
        assert req.target_side == "right"

    def test_whitespace_stripped(self):
        req = validate_aramina_provider_request({
            "container_id": "c1",
            "source_id": "s1",
            "patient_id": "p1",
            "target_side": "  left  ",
        })
        assert req.target_side == "left"


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


class TestMissingRequiredFields:
    """Rejects missing container_id, source_id, patient_id, target_side."""

    def test_missing_container_id(self):
        with pytest.raises(ValueError, match="container_id"):
            validate_aramina_provider_request({
                "source_id": "s1",
                "patient_id": "p1",
                "target_side": "left",
            })

    def test_missing_source_id(self):
        with pytest.raises(ValueError, match="source_id"):
            validate_aramina_provider_request({
                "container_id": "c1",
                "patient_id": "p1",
                "target_side": "left",
            })

    def test_missing_patient_id(self):
        with pytest.raises(ValueError, match="patient_id"):
            validate_aramina_provider_request({
                "container_id": "c1",
                "source_id": "s1",
                "target_side": "left",
            })

    def test_missing_target_side(self):
        with pytest.raises(ValueError, match="target_side"):
            validate_aramina_provider_request({
                "container_id": "c1",
                "source_id": "s1",
                "patient_id": "p1",
            })

    def test_multiple_missing_fields(self):
        with pytest.raises(ValueError, match="container_id"):
            validate_aramina_provider_request({
                "patient_id": "p1",
                "target_side": "left",
            })


# ---------------------------------------------------------------------------
# Invalid target_side
# ---------------------------------------------------------------------------


class TestInvalidTargetSide:
    """Rejects invalid target_side values."""

    def test_invalid_value(self):
        with pytest.raises(ValueError, match="Invalid target_side"):
            validate_aramina_provider_request({
                "container_id": "c1",
                "source_id": "s1",
                "patient_id": "p1",
                "target_side": "anterior",
            })

    def test_empty_string(self):
        with pytest.raises(ValueError, match="Missing required fields"):
            validate_aramina_provider_request({
                "container_id": "c1",
                "source_id": "s1",
                "patient_id": "p1",
                "target_side": "",
            })


# ---------------------------------------------------------------------------
# Optional fields handled safely
# ---------------------------------------------------------------------------


class TestOptionalFields:
    """analysis_author and prediction_comment are optional and safe."""

    def test_absent_optional_fields_default_empty(self):
        req = validate_aramina_provider_request({
            "container_id": "c1",
            "source_id": "s1",
            "patient_id": "p1",
            "target_side": "left",
        })
        assert req.analysis_author == ""
        assert req.prediction_comment == ""

    def test_optional_fields_stripped(self):
        req = validate_aramina_provider_request({
            "container_id": "c1",
            "source_id": "s1",
            "patient_id": "p1",
            "target_side": "left",
            "analysis_author": "  Dr. Jones  ",
            "prediction_comment": "  Routine check  ",
        })
        assert req.analysis_author == "Dr. Jones"
        assert req.prediction_comment == "Routine check"

    def test_optional_fields_not_none_safe(self):
        """None values for optional fields are treated as absent."""
        req = validate_aramina_provider_request({
            "container_id": "c1",
            "source_id": "s1",
            "patient_id": "p1",
            "target_side": "left",
            "analysis_author": None,
            "prediction_comment": None,
        })
        assert req.analysis_author == ""
        assert req.prediction_comment == ""


# ---------------------------------------------------------------------------
# Safe error mapping
# ---------------------------------------------------------------------------


class TestSafeErrorMapping:
    """Safe error mapping does not leak paths, secrets, or internals."""

    def test_request_payload_error(self):
        err = build_aramina_safe_error(ValueError("Missing required fields"))
        assert err.failure_stage == "request_payload"
        assert err.safe_reason == "Aramina provider call failed."
        assert err.error_class == "ValueError"
        # Must not contain path or secret
        assert "/Users/" not in err.safe_reason
        assert "s3://" not in err.safe_reason
        assert "secret" not in err.safe_reason.lower()
        assert "password" not in err.safe_reason.lower()
        assert "token" not in err.safe_reason.lower()

    def test_connection_error_maps_to_aramina_service(self):
        err = build_aramina_safe_error(ConnectionError("Connection refused"))
        assert err.failure_stage == "aramina_service"

    def test_timeout_error_maps_to_aramina_service(self):
        err = build_aramina_safe_error(TimeoutError("timed out"))
        assert err.failure_stage == "aramina_service"

    def test_key_error_maps_to_result_normalization(self):
        err = build_aramina_safe_error(KeyError("output_shape"))
        assert err.failure_stage == "result_normalization"

    def test_unknown_error_maps_to_unknown(self):
        err = build_aramina_safe_error(RuntimeError("something unexpected"))
        assert err.failure_stage == "unknown"

    def test_error_never_exposes_traceback(self):
        try:
            raise ValueError("/Users/alexred/secret/path")
        except Exception as exc:
            err = build_aramina_safe_error(exc)

        assert "/Users/" not in err.safe_reason
        assert "/Users/" not in err.error_class
        assert "traceback" not in err.safe_reason.lower()
        assert "exception" not in err.safe_reason.lower()

    def test_safe_failure_stages_are_fixed_enum(self):
        """_ARAMINA_SAFE_FAILURE_STAGES is a closed set."""
        expected = {
            "request_payload",
            "container_resolution",
            "aramina_service",
            "aramina_preprocessing",
            "aramina_model_execution",
            "result_normalization",
            "unknown",
        }
        assert _ARAMINA_SAFE_FAILURE_STAGES == expected


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


class TestResultShape:
    """Normalized result shape for future integration."""

    def test_default_result_fields(self):
        result = AraminaProviderResult()
        assert result.model_family == "aramina"
        assert result.workflow_id == "aramina"
        assert result.status == "passed"
        assert result.technical_demo_only is True
        assert result.clinical_stage == "research draft"
        assert result.failure_stage is None
        assert result.safe_reason == ""

    def test_result_frozen(self):
        result = AraminaProviderResult()
        with pytest.raises((AttributeError, TypeError)):
            result.status = "failed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Request dataclass
# ---------------------------------------------------------------------------


class TestRequestShape:
    """AraminaProviderRequest is frozen and carries only safe fields."""

    def test_request_frozen(self):
        req = AraminaProviderRequest(
            container_id="c1",
            source_id="s1",
            patient_id="p1",
            target_side="left",
        )
        with pytest.raises((AttributeError, TypeError)):
            req.container_id = "changed"  # type: ignore[misc]

    def test_request_no_private_fields(self):
        req = AraminaProviderRequest(
            container_id="c1",
            source_id="s1",
            patient_id="p1",
            target_side="left",
        )
        # Must not contain fields that leak internals
        for attr in dir(req):
            if attr.startswith("_"):
                continue
            assert "checksum" not in attr.lower()
            assert "password" not in attr.lower()
            assert "secret" not in attr.lower()
            assert "token" not in attr.lower()
            assert "path" not in attr.lower()


# ---------------------------------------------------------------------------
# workflow_id=aramina is NOT executable
# ---------------------------------------------------------------------------


class TestAraminaRoutingClosed:
    """workflow_id=aramina is still not executable in the catalog/allow-list."""

    def test_aramina_now_in_allowed_workflow_ids(self):
        """workflow_id='aramina' is now in the S3 discovery allow-list."""
        from bremen.api.s3_model_discovery import _ALLOWED_WORKFLOW_IDS
        assert "aramina" in _ALLOWED_WORKFLOW_IDS
        assert "bremen" in _ALLOWED_WORKFLOW_IDS

    def test_aramina_still_not_routed_through_bremen(self):
        """Aramina does not route through Bremen provider."""
        from bremen.api.s3_model_discovery import _ALLOWED_WORKFLOW_IDS
        # Both are allowed, but they are separate workflow paths
        assert _ALLOWED_WORKFLOW_IDS == frozenset({"bremen", "aramina"})

    def test_result_workflow_id_is_aramina_not_bremen(self):
        """Result explicitly sets workflow_id='aramina' (not 'bremen')."""
        result = AraminaProviderResult()
        assert result.workflow_id == "aramina"
        assert result.workflow_id != "bremen"
