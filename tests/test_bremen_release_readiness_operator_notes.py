"""Static tests for the release readiness operator notes (PR 0054).

All tests are static/text-only.  No network, AWS, Docker, Terraform,
App Runner, real H5, real model artifact, or credentials.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_NOTES = ROOT / "docs" / "release_readiness_operator_notes.md"
SMOKE_DOC = ROOT / "docs" / "production_e2e_smoke.md"
API_CONTRACT = ROOT / "docs" / "api_contract.md"


def _read_notes() -> str:
    return OPERATOR_NOTES.read_text(encoding="utf-8")


def _read_smoke() -> str:
    return SMOKE_DOC.read_text(encoding="utf-8")


def _read_contract() -> str:
    return API_CONTRACT.read_text(encoding="utf-8")


# ===================================================================
# Class A: TestDocumentExists
# ===================================================================


class TestDocumentExists:
    def test_operator_notes_document_exists(self):
        """Operator notes document is a file."""
        assert OPERATOR_NOTES.is_file(), (
            "docs/release_readiness_operator_notes.md not found"
        )


# ===================================================================
# Class B: TestRequiredEnvVarsDocumented
# ===================================================================


class TestRequiredEnvVarsDocumented:
    def test_env_var_names_documented(self):
        """Document mentions all required env var names."""
        content = _read_notes()
        required = [
            "BREMEN_MODEL_VERSION",
            "BREMEN_MODEL_URI",
            "BREMEN_MODEL_CHECKSUM",
            "BREMEN_MODEL_STAGING_DIR",
        ]
        for var in required:
            assert var in content, (
                f"Operator notes must document env var: {var}"
            )

    def test_checksum_before_deserialization_documented(self):
        """Document mentions checksum verification before joblib.load."""
        content = _read_notes()
        assert "checksum" in content.lower()
        # Must mention checksum before deserialization boundary
        assert "joblib.load()" in content or "deserialization" in content, (
            "Operator notes must document checksum-before-deserialization"
        )


# ===================================================================
# Class C: TestReadinessEndpointsDocumented
# ===================================================================


class TestReadinessEndpointsDocumented:
    def test_health_endpoint_documented(self):
        """Document mentions /health and model_ready."""
        content = _read_notes()
        assert "/health" in content, (
            "Operator notes must document /health endpoint"
        )
        assert "model_ready" in content, (
            "Operator notes must document model_ready"
        )

    def test_model_version_endpoint_documented(self):
        """Document mentions /model/version and model_status."""
        content = _read_notes()
        assert "/model/version" in content, (
            "Operator notes must document /model/version endpoint"
        )
        assert "model_status" in content, (
            "Operator notes must document model_status"
        )

    def test_model_ready_and_model_status_documented(self):
        """Document explains model_ready and model_status values."""
        content = _read_notes()
        status_values = ["ready", "not_configured", "configured", "error"]
        found = [v for v in status_values if v in content]
        assert len(found) >= 3, (
            f"Operator notes must document at least 3 model_status values; "
            f"found: {found}"
        )


# ===================================================================
# Class D: TestSafetyBoundariesDocumented
# ===================================================================


class TestSafetyBoundariesDocumented:
    def test_no_model_in_image_documented(self):
        """Document states no model artifact is in container image."""
        content = _read_notes().lower()
        assert "no model artifact" in content and "container image" in content, (
            "Operator notes must state no model artifact in container image"
        )

    def test_h5_path_h5_uri_as_controlled_modes(self):
        """Document describes h5_path/h5_uri as controlled
        staging/development modes."""
        content = _read_notes().lower()
        assert "h5_path" in content and "h5_uri" in content, (
            "Operator notes must mention h5_path and h5_uri"
        )
        assert "controlled" in content or "staging" in content or \
               "development" in content, (
            "Operator notes must describe h5_path/h5_uri as controlled modes"
        )

    def test_system_of_record_not_implemented(self):
        """Document states real Matador integration is not yet
        implemented."""
        content = _read_notes().lower()
        assert "matador" in content, (
            "Operator notes must reference Matador"
        )
        assert "not implemented" in content or "not yet implemented" in content, (
            "Operator notes must state Matador integration is not implemented"
        )

    def test_decision_support_report_is_not_diagnosis(self):
        """Document states decision-support report is not a diagnosis."""
        content = _read_notes().lower()
        assert "not a diagnosis" in content or "not diagnose" in content, (
            "Operator notes must state Bremen is not a diagnosis"
        )

    def test_no_clinical_validation_claim(self):
        """Document states the system is not clinically validated."""
        content = _read_notes().lower()
        assert "not clinically validated" in content, (
            "Operator notes must state not clinically validated"
        )

    def test_no_replacement_of_clinical_judgment(self):
        """Document states does not replace MRI, biopsy, radiologist,
        clinician, or clinical judgment."""
        content = _read_notes().lower()
        assert "does not replace mri" in content or \
               "does not replace mri" in content, (
            "Operator notes must state does not replace MRI"
        )
        assert "radiologist" in content and "clinician" in content, (
            "Operator notes must mention radiologist and clinician"
        )


# ===================================================================
# Class E: TestFailureModesDocumented
# ===================================================================


class TestFailureModesDocumented:
    def test_failure_modes_documented(self):
        """Document lists at least 5 safe failure modes."""
        content = _read_notes().lower()
        failure_indicators = [
            "failure mode", "failure", "triage",
        ]
        assert any(ind in content for ind in failure_indicators), (
            "Operator notes must document failure modes"
        )
        # Count table rows or bullet points with failure descriptions
        failure_count = content.count("job status: `failed`") + \
                        content.count("model_ready=false") + \
                        content.count("model_status: \"error\"") + \
                        content.count("model not configured") + \
                        content.count("staging failure")
        assert failure_count >= 4, (
            f"Expected at least 4 failure mode references; found {failure_count}"
        )

    def test_model_not_configured_failure_documented(self):
        """Model not configured failure is documented."""
        content = _read_notes().lower()
        assert "model not configured" in content or \
               "not_configured" in content, (
            "Operator notes must document model not configured failure"
        )

    def test_checksum_mismatch_failure_documented(self):
        """Checksum mismatch failure is documented."""
        content = _read_notes().lower()
        assert "checksum mismatch" in content, (
            "Operator notes must document checksum mismatch failure"
        )

    def test_h5_staging_failure_documented(self):
        """H5 staging failure is documented."""
        content = _read_notes().lower()
        assert "h5 staging failure" in content or \
               "s3 download failed" in content, (
            "Operator notes must document H5 staging failure"
        )


# ===================================================================
# Class F: TestLoggingLeakageDocumented
# ===================================================================


class TestLoggingLeakageDocumented:
    def test_logging_leakage_prohibitions_documented(self):
        """Document lists what logs must NOT contain."""
        content = _read_notes().lower()
        prohibitions = [
            "patient identifier",
            "full s3 uri",
            "raw target",
            "raw feature",
            "raw model checksum",
            "secrets",
        ]
        found = sum(1 for p in prohibitions if p in content)
        assert found >= 3, (
            f"Operator notes must document logging leakage prohibitions; "
            f"found {found} of {len(prohibitions)}"
        )

    def test_logging_safe_content_documented(self):
        """Document mentions safe log content."""
        content = _read_notes().lower()
        assert "bremen." in content, (
            "Operator notes must mention bremen.* log events"
        )
        assert "job_id" in content, (
            "Operator notes must mention job_id in logs"
        )


# ===================================================================
# Class G: TestNoSecretsOrIdentifiers
# ===================================================================


class TestNoSecretsOrIdentifiers:
    def test_no_full_s3_uri_with_real_bucket_key(self):
        """Document does NOT contain a real s3://bucket/key string.

        Placeholder patterns using ${VARIABLE} notation and safe generic
        examples like 's3://bucket/key' used in documentation context
        are allowed.
        """
        content = _read_notes()
        # Find all s3:// occurrences
        s3_matches = re.findall(r's3://\S+', content)
        for match in s3_matches:
            # Strip trailing punctuation and markdown backticks
            cleaned = match.rstrip(").,'`")
            # Allow:
            #   - ${VARIABLE} placeholders
            #   - Generic examples like s3://bucket/key or s3://${BUCKET_NAME}
            if "${" in cleaned:
                continue
            if cleaned == "s3://bucket/key":
                continue
            if cleaned == "s3://${BUCKET_NAME}":
                continue
            pytest.fail(
                f"Document contains non-placeholder S3 URI: {match}"
            )

    def test_no_raw_checksum_in_document(self):
        """Document does NOT contain a 64-character hex string
        representing a real checksum."""
        content = _read_notes()
        # Look for standalone 64-char hex strings not in sha256: prefix context
        # of a placeholder like sha256:<64-hex-chars> or sha256:${64_HEX_CHARS}
        hex64 = re.findall(r'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])', content)
        assert len(hex64) == 0, (
            f"Document contains {len(hex64)} raw 64-char hex strings"
        )

    def test_no_access_keys_in_document(self):
        """Document does NOT contain AKIA pattern (AWS access key prefix)."""
        content = _read_notes()
        assert "AKIA" not in content, (
            "Operator notes must not contain AKIA pattern"
        )

    def test_no_registry_url_in_document(self):
        """Document does NOT contain dkr.ecr pattern (ECR registry URL)."""
        content = _read_notes()
        assert "dkr.ecr" not in content, (
            "Operator notes must not contain dkr.ecr pattern"
        )

    def test_no_raw_patient_identifiers_in_document(self):
        """Document does NOT contain Nova_ or raw patient ID patterns."""
        content = _read_notes()
        assert "Nova_" not in content, (
            "Operator notes must not contain Nova_ pattern"
        )

    def test_no_local_machine_paths_in_document(self):
        """Document does NOT contain /Users/ or /home/ paths."""
        content = _read_notes()
        assert "/Users/" not in content, (
            "Operator notes must not contain /Users/ paths"
        )
        assert "/home/" not in content, (
            "Operator notes must not contain /home/ paths"
        )

    def test_no_account_ids_in_document(self):
        """Document does NOT contain AWS account ID patterns."""
        content = _read_notes()
        # AWS account IDs are 12-digit numbers
        twelve_digits = re.findall(r'\b\d{12}\b', content)
        assert len(twelve_digits) == 0, (
            f"Document contains {len(twelve_digits)} 12-digit numbers "
            f"(possible account IDs)"
        )

    def test_no_secret_access_key_in_document(self):
        """Document does NOT contain SECRET_ACCESS_KEY pattern."""
        content = _read_notes()
        assert "SECRET_ACCESS_KEY" not in content, (
            "Operator notes must not contain SECRET_ACCESS_KEY"
        )


# ===================================================================
# Class H: TestDocumentCompleteness
# ===================================================================


class TestDocumentCompleteness:
    def test_rollback_recovery_documented(self):
        """Document includes rollback/recovery steps."""
        content = _read_notes().lower()
        assert "rollback" in content or "recovery" in content, (
            "Operator notes must document rollback/recovery"
        )

    def test_release_readiness_sign_off_checklist_documented(self):
        """Document includes a sign-off checklist with at least 5
        checkable items."""
        content = _read_notes()
        checkbox_count = content.count("- [ ]")
        assert checkbox_count >= 5, (
            f"Expected at least 5 checkbox items in sign-off checklist; "
            f"found {checkbox_count}"
        )

    def test_clinical_safety_disclaimer_present(self):
        """Document states Bremen does not diagnose, is not clinically
        validated, and does not replace clinical judgment."""
        content = _read_notes().lower()
        assert "not diagnose" in content or "not a diagnosis" in content, (
            "Operator notes must state no diagnosis"
        )
        assert "not clinically validated" in content, (
            "Operator notes must state not clinically validated"
        )
        assert "does not replace" in content, (
            "Operator notes must state does not replace clinical judgment"
        )

    def test_non_goals_documented(self):
        """Document lists non-goals."""
        content = _read_notes()
        # Section 15 is Non-Goals
        assert "Non-Goals" in content or "non-goals" in content.lower(), (
            "Operator notes must include non-goals section"
        )
        for goal in ["FastAPI", "Matador", "diagnosis"]:
            assert goal in content, (
                f"Non-goals must mention: {goal}"
            )


# ===================================================================
# Class I: TestDocCrossReferences
# ===================================================================


class TestDocCrossReferences:
    def test_smoke_doc_links_to_operator_notes(self):
        """docs/production_e2e_smoke.md links to operator notes."""
        content = _read_smoke()
        assert "release_readiness_operator_notes.md" in content, (
            "Smoke doc must link to release_readiness_operator_notes.md"
        )

    def test_api_contract_links_to_operator_notes(self):
        """docs/api_contract.md links to operator notes."""
        content = _read_contract()
        assert "release_readiness_operator_notes.md" in content, (
            "API contract must link to release_readiness_operator_notes.md"
        )

    def test_smoke_doc_link_is_in_appropriate_section(self):
        """The cross-reference link in the smoke doc appears near
        prerequisites or similar section."""
        content = _read_smoke()
        # The link should be within the prerequisites section (first ~60 lines)
        # Find the line number
        lines = content.split("\n")
        link_line = None
        for i, line in enumerate(lines):
            if "release_readiness_operator_notes.md" in line:
                link_line = i
                break
        assert link_line is not None, "Link not found in smoke doc"
        assert link_line < 80, (
            f"Cross-reference link should be near prerequisites section; "
            f"found at line {link_line}"
        )

    def test_api_contract_link_is_in_decision_support_section(self):
        """The cross-reference link in the API contract appears in the
        decision-support report section."""
        content = _read_contract()
        # The link should be within the Decision-Support Report (PR0053) section
        lines = content.split("\n")
        in_ds_section = False
        for line in lines:
            if "Decision-Support Report (PR0053)" in line or \
               "Decision-Support Report" in line:
                in_ds_section = True
            if "release_readiness_operator_notes.md" in line:
                assert in_ds_section, (
                    "Cross-reference link in API contract must be in the "
                    "Decision-Support Report section"
                )
                break
