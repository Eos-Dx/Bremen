"""Tests for the Bremen demo presentation formatter.

Covers:
- format_pretty() returns a string
- format_pretty() includes "Bremen" product identity
- format_pretty() includes "technical demo" disclaimer
- format_pretty() includes health status
- format_pretty() includes model status
- format_pretty() includes prediction status
- format_pretty() includes request_id
- format_pretty() includes evidence bundle
- format_pretty() handles not_available gracefully
- format_pretty() handles fail status with warnings
- format_pretty() has no terminal control codes
- format_pretty() is deterministic
- format_pretty_header() output
- format_pretty_footer() output
- No Aramis references in output
- No clinical/replacement claims (except safe negation)
- Import/dependency safety
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from bremen.demo_presentation import (
    format_pretty,
    format_pretty_header,
    format_pretty_footer,
)

MODULE_PATH = Path(__file__).parents[1] / "src" / "bremen" / "demo_presentation.py"


# ===================================================================
# Helpers: sample result dicts
# ===================================================================


def _make_pass_result() -> dict:
    """Return a demo-run result dict representing a full pass scenario."""
    return {
        "technical_demo_only": True,
        "base_url": "http://127.0.0.1:52731",
        "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "status": "pass",
        "checks": {
            "health": "pass",
            "model_version": "pass",
            "prediction": "pass",
        },
        "health": {
            "status": "ok",
            "model_ready": True,
            "service": "bremen",
            "version": "v0.1",
        },
        "model_version": {
            "model_configured": True,
            "model_status": "ready",
            "model_version": "smoke-v0.1",
            "model_checksum": "a1b2c3d4e5f6...7890abcdef1234",
            "feature_schema_version": "bremen.feature_artifact.v0.1",
        },
        "prediction": {
            "status": "completed",
            "job_id": "f6e5d4c3-b2a1-0987-6543-210fedcba987",
            "poll_status": "completed",
            "completed": True,
            "qc_status": "passed",
            "decision_support": {
                "report_schema_version": "v0.1",
                "p_mri_needed": 0.620,
                "triage_recommendation": "MRI_RECOMMENDED",
            },
        },
        "evidence": {
            "technical_demo_only": True,
            "product": "Bremen",
            "product_question": "Should patient continue to MRI?",
            "disclaimer": (
                "This is a technical product demo of Bremen's controlled "
                "decision-support workflow. It is not a clinical result. "
                "It is not clinically validated. It does not replace MRI, "
                "biopsy, a radiologist, a clinician, or clinical judgment."
            ),
            "evidence_version": "v0.1",
            "scenario_id": "bremen_demo_v1",
            "safety_notes": [
                "Technical product demo only — not a clinical result.",
                "Not clinically validated.",
                "Does not replace MRI, biopsy, radiologist, clinician, "
                "or clinical judgment.",
                "All clinical decisions must be made by qualified clinicians.",
            ],
            "base_url": "http://127.0.0.1:52731",
            "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "model_status": "ready",
            "model_version": "smoke-v0.1",
            "feature_schema_version": "bremen.feature_artifact.v0.1",
            "prediction_status": "completed",
        },
        "warnings": [],
        "timestamp": "2026-07-15T10:00:00",
    }


def _make_not_available_result() -> dict:
    """Return a result dict where prediction was skipped."""
    return {
        "technical_demo_only": True,
        "base_url": "http://127.0.0.1:52731",
        "request_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "status": "pass",
        "checks": {
            "health": "pass",
            "model_version": "pass",
        },
        "health": {
            "status": "ok",
            "model_ready": True,
            "service": "bremen",
            "version": "v0.1",
        },
        "model_version": {
            "model_configured": True,
            "model_status": "ready",
            "model_version": "smoke-v0.1",
        },
        "prediction": {
            "status": "not_available",
            "reason": "Prediction check was skipped via --skip-prediction flag.",
        },
        "evidence": {
            "technical_demo_only": True,
            "product": "Bremen",
            "product_question": "Should patient continue to MRI?",
            "disclaimer": (
                "This is a technical product demo of Bremen's controlled "
                "decision-support workflow. It is not a clinical result."
            ),
            "evidence_version": "v0.1",
            "scenario_id": "bremen_demo_v1",
            "safety_notes": [
                "Technical product demo only — not a clinical result.",
                "Not clinically validated.",
            ],
            "base_url": "http://127.0.0.1:52731",
            "request_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        },
        "warnings": [],
        "timestamp": "2026-07-15T10:01:00",
    }


def _make_fail_result() -> dict:
    """Return a result dict representing a failure scenario with warnings."""
    return {
        "technical_demo_only": True,
        "base_url": "http://127.0.0.1:1",
        "request_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "status": "fail",
        "checks": {
            "health": "fail",
            "model_version": "fail",
        },
        "health": {
            "error": "Health check connection error: Connection refused",
        },
        "model_version": {
            "error": "Model version check connection error: Connection refused",
        },
        "prediction": {
            "status": "not_available",
            "reason": "Prediction check was skipped via --skip-prediction flag.",
        },
        "evidence": {
            "technical_demo_only": True,
            "product": "Bremen",
            "product_question": "Should patient continue to MRI?",
            "disclaimer": (
                "This is a technical product demo of Bremen's controlled "
                "decision-support workflow. It is not a clinical result."
            ),
            "evidence_version": "v0.1",
            "scenario_id": "bremen_demo_v1",
            "safety_notes": [
                "Technical product demo only — not a clinical result.",
                "Not clinically validated.",
            ],
            "base_url": "http://127.0.0.1:1",
            "request_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        },
        "warnings": [
            "Health check connection error: Connection refused",
            "Model version check connection error: Connection refused",
        ],
        "timestamp": "2026-07-15T10:02:00",
    }


# ===================================================================
# Class 1: Basic output
# ===================================================================


class TestFormatPrettyBasic:
    def test_returns_string(self):
        """format_pretty returns a string."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert isinstance(output, str)

    def test_output_is_multiline(self):
        """Output contains newlines."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "\n" in output


# ===================================================================
# Class 2: Product identity
# ===================================================================


class TestProductIdentity:
    def test_includes_bremen(self):
        """Output includes 'Bremen' product identity."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "Bremen" in output

    def test_includes_product_question(self):
        """Output includes the product question."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "Should patient continue to MRI?" in output


# ===================================================================
# Class 3: technical_demo_only
# ===================================================================


class TestTechnicalDemoOnly:
    def test_includes_technical_demo_text(self):
        """Output includes 'Technical demo only' text."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "Technical demo only" in output

    def test_header_includes_disclaimer(self):
        """Header includes disclaimer about not being clinical."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "not a clinical result" in output.lower()

    def test_footer_includes_safety(self):
        """Footer includes safety disclaimer."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "Not clinically validated" in output
        assert "Does not replace MRI" in output


# ===================================================================
# Class 4: Health/model/evidence/prediction statuses
# ===================================================================


class TestStatusSections:
    def test_includes_health_status(self):
        """Output shows health status 'ok'."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "ok" in output

    def test_includes_model_status(self):
        """Output shows model status 'ready'."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "ready" in output

    def test_includes_prediction_status(self):
        """Output shows prediction status 'completed'."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "completed" in output

    def test_includes_prediction_metadata(self):
        """Output shows p_mri_needed and recommendation."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "0.620" in output
        assert "MRI_RECOMMENDED" in output

    def test_includes_evidence_version(self):
        """Output shows evidence_version."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "v0.1" in output

    def test_includes_safety_notes(self):
        """Output includes safety_notes content."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "qualified clinicians" in output.lower()


# ===================================================================
# Class 5: request_id
# ===================================================================


class TestRequestId:
    def test_includes_request_id(self):
        """Output includes request_id."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" in output

    def test_request_id_different_for_different_results(self):
        """Two different results show different request IDs."""
        r1 = _make_pass_result()
        r2 = _make_not_available_result()
        o1 = format_pretty(r1)
        o2 = format_pretty(r2)
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" in o1
        assert "b2c3d4e5-f6a7-8901-bcde-f12345678901" in o2


# ===================================================================
# Class 6: not_available handling
# ===================================================================


class TestNotAvailable:
    def test_shows_not_available(self):
        """not_available prediction state is shown."""
        result = _make_not_available_result()
        output = format_pretty(result)
        assert "not_available" in output

    def test_shows_reason(self):
        """Reason for not_available is shown."""
        result = _make_not_available_result()
        output = format_pretty(result)
        assert "--skip-prediction" in output

    def test_unavailable_prediction_does_not_show_error(self):
        """not_available prediction should not show error section."""
        result = _make_not_available_result()
        output = format_pretty(result)
        assert "Error" not in output.split("Prediction")[1].split(
            "Evidence"
        )[0] if "Prediction" in output and "Evidence" in output else True


# ===================================================================
# Class 7: Fail status with warnings
# ===================================================================


class TestFailWithWarnings:
    def test_shows_fail_status(self):
        """Fail status is shown."""
        result = _make_fail_result()
        output = format_pretty(result)
        assert "FAIL" in output

    def test_shows_warnings(self):
        """Warnings are shown."""
        result = _make_fail_result()
        output = format_pretty(result)
        assert "Connection refused" in output

    def test_warnings_section_present(self):
        """Warnings section is present with content."""
        result = _make_fail_result()
        output = format_pretty(result)
        assert "Warnings" in output

    def test_no_warnings_shows_none(self):
        """When there are no warnings, shows '(none)'."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "(none)" in output


# ===================================================================
# Class 8: No terminal control codes
# ===================================================================


class TestNoTerminalCodes:
    def test_no_ansi_escape_codes(self):
        """Output contains no ANSI escape sequences."""
        result = _make_pass_result()
        output = format_pretty(result)
        # ANSI escape sequences start with \x1b or \033
        assert "\x1b" not in output
        assert "\033" not in output

    def test_plain_ascii_only(self):
        """Output contains no ANSI escape sequences or terminal control codes."""
        result = _make_pass_result()
        output = format_pretty(result)
        # No ANSI escape codes
        assert "\x1b" not in output
        assert "\033" not in output
        # No terminal control characters (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F)
        for ch in output:
            code = ord(ch)
            if code == 0x0A:  # \n allowed
                continue
            if code < 0x09:  # 0x00-0x08 are control chars
                pytest.fail(f"Control character found: U+{code:04X}")
            if 0x0B <= code <= 0x0C:  # vertical tab / form feed
                pytest.fail(f"Control character found: U+{code:04X}")
            if 0x0E <= code <= 0x1F:  # shift out / unit separator
                pytest.fail(f"Control character found: U+{code:04X}")


# ===================================================================
# Class 9: Deterministic
# ===================================================================


class TestDeterministic:
    def test_same_input_produces_same_output(self):
        """Two calls with the same input produce identical output."""
        result = _make_pass_result()
        o1 = format_pretty(result)
        o2 = format_pretty(result)
        assert o1 == o2

    def test_different_inputs_produce_different_output(self):
        """Different inputs produce different output."""
        r1 = _make_pass_result()
        r2 = _make_fail_result()
        o1 = format_pretty(r1)
        o2 = format_pretty(r2)
        assert o1 != o2


# ===================================================================
# Class 10: Header and footer helpers
# ===================================================================


class TestHeaderFooter:
    def test_header_returns_string(self):
        """format_pretty_header returns a string."""
        result = _make_pass_result()
        header = format_pretty_header(result)
        assert isinstance(header, str)

    def test_header_includes_bremen(self):
        """Header includes Bremen product identity."""
        result = _make_pass_result()
        header = format_pretty_header(result)
        assert "BREMEN" in header
        assert "Technical demo only" in header

    def test_footer_returns_string(self):
        """format_pretty_footer returns a string."""
        result = _make_pass_result()
        footer = format_pretty_footer(result)
        assert isinstance(footer, str)

    def test_footer_includes_safety(self):
        """Footer includes safety disclaimer."""
        result = _make_pass_result()
        footer = format_pretty_footer(result)
        assert "Not clinically validated" in footer
        assert "Does not replace MRI" in footer

    def test_header_raises_on_non_mapping(self):
        """format_pretty_header raises TypeError on non-mapping."""
        with pytest.raises(TypeError, match="must be a Mapping"):
            format_pretty_header("bad input")


# ===================================================================
# Class 11: No Aramis references
# ===================================================================


class TestNoAramisReferences:
    def test_no_aramis_in_pretty_output(self):
        """format_pretty output does not contain Aramis strings."""
        result = _make_pass_result()
        output = format_pretty(result)
        output_lower = output.lower()
        for pattern in ("aramis", "m2q", "benign vs cancer"):
            assert pattern not in output_lower, (
                f"Output contains prohibited pattern: {pattern}"
            )

    def test_no_aramis_in_module_source(self):
        """Module source does not contain Aramis references."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "Aramis" not in source
        assert "aramis" not in source


# ===================================================================
# Class 12: No clinical/replacement claims
# ===================================================================


class TestNoClinicalReplacementLanguage:
    def test_no_diagnosis_claim_in_output(self):
        """format_pretty output does not contain clinical claims (except
        safe negation in footer)."""
        result = _make_pass_result()
        output = format_pretty(result)
        output_lower = output.lower()
        # Check for non-disclaimer contexts
        # "diagnosis" only appears in safety disclaimer context
        assert "replaces mri" not in output_lower
        assert "replaces biopsy" not in output_lower
        assert "replaces radiologist" not in output_lower
        assert "replaces clinician" not in output_lower

    def test_safety_footer_uses_negation(self):
        """Safety footer uses negation language, not claims."""
        result = _make_pass_result()
        output = format_pretty(result)
        assert "Does not replace MRI" in output
        assert "Not clinically validated" in output


# ===================================================================
# Class 13: Edge cases
# ===================================================================


class TestEdgeCases:
    def test_handles_empty_evidence(self):
        """Handles result with empty evidence gracefully."""
        result = _make_pass_result()
        result.pop("evidence", None)
        output = format_pretty(result)
        assert isinstance(output, str)
        # Should not crash

    def test_handles_empty_checks(self):
        """Handles result with empty checks gracefully."""
        result = _make_pass_result()
        result["checks"] = {}
        output = format_pretty(result)
        assert isinstance(output, str)

    def test_raises_on_non_mapping(self):
        """format_pretty raises TypeError on non-mapping input."""
        with pytest.raises(TypeError, match="must be a Mapping"):
            format_pretty("bad input")  # type: ignore[arg-type]

    def test_handles_minimal_dict(self):
        """Handles a minimal result dict without crashing."""
        result = {
            "technical_demo_only": True,
            "status": "pass",
            "base_url": "http://localhost",
        }
        output = format_pretty(result)
        assert isinstance(output, str)
        assert "PASS" in output

    def test_health_error_shown(self):
        """Health with error shows error message."""
        result = _make_fail_result()
        output = format_pretty(result)
        assert "Connection refused" in output


# ===================================================================
# Class 14: Import/dependency safety
# ===================================================================


class TestImportSafety:
    def test_no_h5_references(self):
        """Module does not reference h5, hdf5, or h5py."""
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        assert ".h5" not in source
        assert ".hdf5" not in source
        assert "h5py" not in source

    def test_no_joblib_or_pickle(self):
        """Module does not reference joblib or pickle."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "joblib" not in source.lower()
        assert "pickle" not in source

    def test_no_boto3_or_requests(self):
        """Module does not import boto3, requests, httpx."""
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in (
                        "boto3", "requests", "httpx", "botocore"
                    ), f"Module imports {name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                assert top not in (
                    "boto3", "requests", "httpx", "botocore"
                ), f"Module imports {module}"
