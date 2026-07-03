"""Tests for the API contract document (``docs/api_contract.md``).

Covers:
- Contract file exists
- All 4 endpoints documented
- Async submit -> job_id -> poll pattern documented
- Mandatory completed-result fields documented
- Target/control refs required and explicit
- No local machine path dependency
- No clinical/diagnostic wording
- No Aramis identity
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
API_CONTRACT = ROOT / "docs" / "api_contract.md"


def test_contract_exists():
    """docs/api_contract.md must exist."""
    assert API_CONTRACT.is_file(), "docs/api_contract.md not found"


def _read_contract() -> str:
    return API_CONTRACT.read_text(encoding="utf-8")


class TestEndpointsDocumented:
    def test_health_documented(self):
        """GET /health must appear in the contract."""
        assert "/health" in _read_contract()

    def test_model_version_documented(self):
        """GET /model/version must appear in the contract."""
        assert "/model/version" in _read_contract()

    def test_submit_predictions_documented(self):
        """POST /predictions must appear in the contract."""
        assert "POST /predictions" in _read_contract()

    def test_get_prediction_documented(self):
        """GET /predictions/{job_id} must appear in the contract."""
        assert "GET /predictions/{job_id}" in _read_contract()


class TestAsyncPattern:
    def test_async_submit_poll_documented(self):
        """Contract must document the async submit -> job_id -> poll pattern."""
        content = _read_contract()
        assert "job_id" in content
        assert "poll" in content
        assert "HTTP 202" in content or "202" in content


class TestCompletedResultFields:
    def test_prediction_id_documented(self):
        """Completed result must include prediction_id."""
        assert "prediction_id" in _read_contract()

    def test_model_version_documented(self):
        """Completed result must include model_version."""
        assert "model_version" in _read_contract()

    def test_model_checksum_documented(self):
        """Completed result must include model_checksum."""
        assert "model_checksum" in _read_contract()

    def test_feature_schema_version_documented(self):
        """Completed result must include feature_schema_version."""
        assert "feature_schema_version" in _read_contract()

    def test_threshold_version_documented(self):
        """Completed result must include threshold_version."""
        assert "threshold_version" in _read_contract()

    def test_threshold_value_documented(self):
        """Completed result must include threshold_value."""
        assert "threshold_value" in _read_contract()

    def test_qc_status_documented(self):
        """Completed result must include qc_status."""
        assert "qc_status" in _read_contract()

    def test_qc_flags_documented(self):
        """Completed result must include qc_flags."""
        assert "qc_flags" in _read_contract()


class TestRequestFields:
    def test_target_scan_ref_documented(self):
        """POST /predictions must document target_scan_ref."""
        assert "target_scan_ref" in _read_contract()

    def test_control_scan_ref_documented(self):
        """POST /predictions must document control_scan_ref."""
        assert "control_scan_ref" in _read_contract()


class TestSafety:
    def test_no_local_machine_paths(self):
        """Contract must not require local machine paths."""
        content = _read_contract()
        # The contract explicitly states: "Request must use opaque platform
        # references, not local machine paths."
        # Check that the contract does NOT suggest relative/absolute paths
        # as the primary mechanism.
        assert "opaque platform reference" in content or (
            "not local machine paths" in content
        )

    def test_no_clinical_validation_claim(self):
        """Contract must not claim clinical validation."""
        content = _read_contract().lower()
        prohibited = [
            "clinically validated",
            "fda cleared",
            "fda approved",
        ]
        for phrase in prohibited:
            assert phrase not in content, (
                f"Contract contains prohibited phrase: {phrase}"
            )

    def test_no_diagnostic_replacement_claim(self):
        """Contract must state it is not a diagnostic replacement."""
        content = _read_contract().lower()
        assert "not a diagnostic replacement" in content or (
            "does not replace" in content
        ), "Contract must contain disclaimer"

    def test_no_cancer_detected_wording(self):
        """Contract must not use 'cancer detected' wording."""
        content = _read_contract().lower()
        assert "cancer detected" not in content, (
            "Contract must not use 'cancer detected'"
        )

    def test_no_aramis_identity(self):
        """Contract must not reference Aramis as active architecture."""
        content = _read_contract()
        assert "aramis" not in content.lower(), (
            "Contract must not reference Aramis"
        )
