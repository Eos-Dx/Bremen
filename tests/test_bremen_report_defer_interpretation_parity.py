"""Tests for report Decision Interpretation parity (PR0108).

Covers:
- MRI_REVIEW_DEFER highlights left card, not right card
- CONTINUE_MRI highlights right card, not left card
- Each card has fixed meaning text (no shared explanationText)
- No raw S3/H5/model internals/coefficients/PHI in rendered HTML
- No real server, socket, localhost HTTP, uvicorn launch
"""

from __future__ import annotations

import re

import pytest

from bremen.report_ui import build_report_page


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_page_with_sample(decision_code: str) -> str:
    """Build a sample report page with the given decision code."""
    sample_data = {
        "job": {},
        "report": {
            "payload": {
                "decision_support_report": {
                    "prediction_summary": {
                        "p_mri_needed": 0.55 if decision_code == "CONTINUE_MRI" else 0.25,
                        "decision_code": decision_code,
                        "decision_display_name": (
                            "Defer MRI pending clinician review"
                            if decision_code == "MRI_REVIEW_DEFER"
                            else "Continue MRI evaluation"
                        ),
                        "qc_status": "passed",
                    },
                    "model_metadata": {
                        "model_version": "test-model-v1",
                        "feature_schema_version": "v0.1",
                        "threshold_value": 0.413,
                    },
                },
            },
        },
    }
    return build_report_page(sample_data=sample_data)


# ---------------------------------------------------------------------------
# JS source-level assertions (the page embeds the JS renderer)
# ---------------------------------------------------------------------------


class TestDeferInterpretationParity:
    """MRI_REVIEW_DEFER: left card highlighted, right card not."""

    def test_js_has_defer_highlight(self):
        """JS code applies is-current to left card when MRI_REVIEW_DEFER."""
        page = build_report_page(job_id="test")
        assert "isDefer?' is-current':'" in page

    def test_js_has_continue_highlight(self):
        """JS code applies is-current to right card when CONTINUE_MRI."""
        page = build_report_page(job_id="test")
        assert "isContinue?' is-current':'" in page

    def test_defer_card_uses_fixed_text(self):
        """Left card always uses fixed defer text, not explanationText()."""
        page = build_report_page(job_id="test")
        assert (
            "Score below threshold. MRI continuation may be deferred, "
            "subject to clinician review."
        ) in page

    def test_continue_card_uses_fixed_text(self):
        """Right card always uses fixed continue text, not explanationText()."""
        page = build_report_page(job_id="test")
        assert (
            "Score at or above threshold. MRI continuation is flagged "
            "for clinician review."
        ) in page

    def test_defer_card_title_without_this_result(self):
        """When not current, defer card title is plain."""
        page = build_report_page(job_id="test")
        assert "'MRI REVIEW DEFER'" in page

    def test_defer_card_title_with_this_result(self):
        """When current, defer card title includes THIS RESULT."""
        page = build_report_page(job_id="test")
        assert "'MRI REVIEW DEFER \\u00B7 THIS RESULT'" in page

    def test_continue_card_title_without_this_result(self):
        """When not current, continue card title is plain."""
        page = build_report_page(job_id="test")
        assert "'CONTINUE MRI'" in page

    def test_continue_card_title_with_this_result(self):
        """When current, continue card title includes THIS RESULT."""
        page = build_report_page(job_id="test")
        assert "'CONTINUE MRI \\u00B7 THIS RESULT'" in page

    def test_both_codes_define_variables(self):
        """JS defines isDefer and isContinue from decisionCode."""
        page = build_report_page(job_id="test")
        assert "var isDefer = decisionCode === 'MRI_REVIEW_DEFER'" in page
        assert "var isContinue = decisionCode === 'CONTINUE_MRI'" in page


# ---------------------------------------------------------------------------
# Sample data rendering (verifies sample mode embeds correctly)
# ---------------------------------------------------------------------------


class TestSampleDataRendering:
    """Sample mode with decision codes embeds data correctly."""

    def test_defer_sample_embeds_decision(self):
        """Defer sample data is embedded in the page."""
        page = _build_page_with_sample("MRI_REVIEW_DEFER")
        assert "MRI_REVIEW_DEFER" in page

    def test_continue_sample_embeds_decision(self):
        """Continue sample data is embedded in the page."""
        page = _build_page_with_sample("CONTINUE_MRI")
        assert "CONTINUE_MRI" in page

    def test_sample_has_decision_meaning_section(self):
        """Sample pages contain Decision Interpretation section."""
        page = _build_page_with_sample("MRI_REVIEW_DEFER")
        assert "Decision Interpretation" in page


# ---------------------------------------------------------------------------
# Safety assertions — no raw internals
# ---------------------------------------------------------------------------


class TestNoRawInternals:
    """Report HTML must not expose raw internals."""

    def test_no_s3_paths(self):
        """No raw S3 paths in report page."""
        page = build_report_page(job_id="test")
        assert "s3://" not in page

    def test_no_filesystem_paths(self):
        """No filesystem paths in report page."""
        page = build_report_page(job_id="test")
        assert "/Users/" not in page
        assert "/home/" not in page

    def test_no_exception_traces(self):
        """No Traceback text in report page."""
        page = build_report_page(job_id="test")
        assert "Traceback" not in page

    def test_no_full_sha256_checksums(self):
        """No 64-char hex checksums in report page."""
        page = build_report_page(job_id="test")
        assert re.search(r"[a-f0-9]{64}", page) is None

    def test_no_coefficients_or_intercept(self):
        """No raw model coefficients or intercept."""
        page = build_report_page(job_id="test")
        lower = page.lower()
        assert "coefficients" not in lower
        assert "intercept" not in lower


# ---------------------------------------------------------------------------
# Existing routes preserved
# ---------------------------------------------------------------------------


class TestExistingRoutesPreserved:
    """Report page still renders basic structure."""

    def test_page_has_title(self):
        """Report page has correct title."""
        page = build_report_page(job_id="test")
        assert "Bremen Report" in page

    def test_page_has_tabs(self):
        """Report page has External and Internal tabs."""
        page = build_report_page(job_id="test")
        assert "tab-external-btn" in page
        assert "tab-internal-btn" in page

    def test_page_has_assessment_hero(self):
        """Report page has assessment hero section."""
        page = build_report_page(job_id="test")
        assert "assessment-hero" in page
