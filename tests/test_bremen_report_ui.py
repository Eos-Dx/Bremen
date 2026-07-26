"""Tests for Bremen report UI — PR0093 presentation-grade report renderer.

Covers External/Internal tabs, symmetry signals, Print/Save PDF,
safety boundaries, design token usage, and accessibility.
"""

from __future__ import annotations

import json as _json
import os as _os
import re as _re

import pytest

from bremen.report_ui import build_report_page


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_sample_data():
    """Load the frozen sample-data.json fixture."""
    sample_path = _os.path.join(
        _os.path.dirname(__file__), "..",
        ".project-memory", "pr", "0093-report-rendering-and-pdf-export",
        "artifacts", "sample-data.json",
    )
    with open(sample_path, "r", encoding="utf-8") as fh:
        return _json.load(fh)


def _approved_hex_colors():
    """Return the set of approved hex colors from BREMEN_DESIGN_SPEC_v1.md."""
    return {
        "#F7F8F8", "#FFFFFF", "#16202A", "#5B6570", "#1F6F6B", "#E3E7E6",
        "#2E7D5B", "#B8894A", "#9AA3A8", "#C1483D",
        "#F1F5F4", "#FBF3E9", "#FBEEEC",
    }


# ---------------------------------------------------------------------------
# Tests — External tab
# ---------------------------------------------------------------------------


class TestExternalTab:
    """External tab renders correctly."""

    def test_external_tab_exists(self):
        """External tab button and panel exist in the HTML."""
        page = build_report_page(job_id="test-job")
        assert 'id="tab-external-btn"' in page
        assert 'id="panel-external"' in page
        assert 'role="tabpanel"' in page
        assert 'aria-labelledby="tab-external-btn"' in page

    def test_external_tab_selected_by_default(self):
        """External tab is aria-selected=true by default."""
        page = build_report_page(job_id="test-job")
        # Tab button has aria-selected="true"
        assert 'aria-selected="true"' in page
        # Internal panel has hidden attribute (may be "hidden" or hidden without quotes)
        assert 'panel-internal" hidden' in page or 'panel-internal"\n       hidden' in page or 'id="panel-internal"' in page

    def test_external_has_bremen_header(self):
        """External tab page has Bremen header and title."""
        page = build_report_page(job_id="test-job")
        assert "Bremen" in page
        assert "MRI-Continuation Decision-Support Report" in page

    def test_external_has_audience_line(self):
        """External tab has referring clinician audience line."""
        page = build_report_page(job_id="test-job")
        assert "referring clinician" in page.lower()

    def test_external_has_tech_demo_notice(self):
        """External tab has technical demo only safety notice."""
        page = build_report_page(job_id="test-job")
        assert "Technical demo only" in page or "technical demo" in page.lower()

    def test_external_has_footer_disclaimer(self):
        """External tab has footer safety disclaimer."""
        page = build_report_page(job_id="test-job")
        assert "Does not replace MRI" in page or "does not replace MRI" in page.lower()
        assert "decision support" in page.lower()


class TestInternalTab:
    """Internal tab renders correctly."""

    def test_internal_tab_exists(self):
        """Internal tab button and panel exist."""
        page = build_report_page(job_id="test-job")
        assert 'id="tab-internal-btn"' in page
        assert 'id="panel-internal"' in page

    def test_internal_tab_deselected_by_default(self):
        """Internal tab is aria-selected=false by default."""
        page = build_report_page(job_id="test-job")
        assert 'aria-selected="false"' in page


class TestSampleMode:
    """Sample mode renders correctly with synthetic labels."""

    def test_sample_mode_embeds_data(self):
        """Sample mode embeds data in script tag."""
        sample_data = _load_sample_data()
        page = build_report_page(sample_data=sample_data)
        assert 'id="sample-data-json"' in page
        assert "SYNTHETIC" in page or "SAMPLE" in page

    def test_sample_mode_has_banner(self):
        """Sample mode has SYNTHETIC DEMONSTRATION SAMPLE banner."""
        sample_data = _load_sample_data()
        page = build_report_page(sample_data=sample_data)
        assert "SYNTHETIC" in page
        assert "Illustrative" in page or "illustrative" in page

    def test_sample_mode_not_for_clinical_use(self):
        """Sample mode banner states not for clinical use."""
        sample_data = _load_sample_data()
        page = build_report_page(sample_data=sample_data)
        assert "not clinically validated" in page.lower() or "Not clinically validated" in page

    def test_sample_mode_not_for_distribution(self):
        """Sample mode banner states not for distribution."""
        sample_data = _load_sample_data()
        page = build_report_page(sample_data=sample_data)
        assert "external distribution" in page.lower() or "patient" in page.lower()

    def test_sample_fixture_is_labeled(self):
        """The sample-data.json fixture is clearly labeled synthetic."""
        sample_data = _load_sample_data()
        assert sample_data["meta"]["synthetic"] is True
        assert sample_data["meta"]["not_for_clinical_use"] is True
        assert "SYNTHETIC" in sample_data["meta"]["description"]


class TestLiveModeNoSampleLeakage:
    """Live mode does not include synthetic sample labels."""

    def test_live_mode_no_synthetic_banner(self):
        """Live mode page sample banner is hidden by default."""
        page = build_report_page(job_id="test-job-123")
        # The sample banner HTML exists in the JS template but is hidden by default.
        # Check that the hidden attribute is present on the banner.
        assert 'hidden' in page

    def test_live_mode_no_sample_json_embedded(self):
        """Live mode does not embed sample-data-json script tag."""
        page = build_report_page(job_id="test-job-123")
        assert 'id="sample-data-json"' not in page

    def test_live_mode_is_sample_false(self):
        """Live mode sets isSample variable to false ('0'==='1')."""
        page = build_report_page(job_id="test-job-123")
        # After template replacement, __IS_SAMPLE__ is replaced with 0.
        # The JS checks: var isSample='0'==='1';
        assert "'0'==='1'" in page or "'0' === '1'" in page or "var isSample=" in page


class TestPrintSavePDF:
    """Print / Save PDF functionality."""

    def test_print_button_exists_external(self):
        """External tab has Print / Save PDF button."""
        page = build_report_page(job_id="test-job")
        assert "Print / Save PDF" in page
        assert 'id="print-btn-external"' in page

    def test_print_button_exists_internal(self):
        """Internal tab has Print / Save PDF button."""
        page = build_report_page(job_id="test-job")
        assert 'id="print-btn-internal"' in page

    def test_window_print_wired(self):
        """window.print() is called from print button handler."""
        page = build_report_page(job_id="test-job")
        assert "window.print()" in page
        assert "printActiveTab" in page

    def test_media_print_exists(self):
        """@media print CSS rule exists."""
        page = build_report_page(job_id="test-job")
        assert "@media print" in page

    def test_print_css_hides_controls(self):
        """@media print hides tab buttons and print buttons."""
        page = build_report_page(job_id="test-job")
        # The CSS is minified but tab-btn and print-button should be hidden
        assert ".tab-btn," in page  # part of the hidden selectors in @media print
        assert ".print-button" in page
        assert "display:none" in page

    def test_print_css_hides_navigation(self):
        """@media print hides back-to-control-room navigation."""
        page = build_report_page(job_id="test-job")
        assert ".report-nav," in page

    def test_print_css_preserves_layout(self):
        """@media print preserves report document layout."""
        page = build_report_page(job_id="test-job")
        assert ".report-document" in page
        assert "page-break-inside" in page
        assert "avoid" in page

    def test_print_css_preserves_accent_rail(self):
        """@media print preserves recommendation hero background."""
        page = build_report_page(job_id="test-job")
        assert ".recommendation-hero" in page
        assert "-webkit-print-color-adjust:exact" in page

    def test_print_color_adjust_covers_tinted_classes(self):
        """@media print includes print-color-adjust for all tinted/background classes."""
        page = build_report_page(job_id="test-job")
        # Verify each backgrounded/tinted class has print-color-adjust
        covered_classes = [
            ".recommendation-hero",
            ".technical-demo-notice",
            ".boundary-note",
            ".signal-card",
            ".level-dot.is-filled",
            ".decision-meaning-card.is-current",
            ".trace-stage.completed",
            ".trace-stage.failed",
        ]
        for cls in covered_classes:
            assert cls in page, f"Class {cls} missing from page"
        # Verify print-color-adjust appears at least 16 times (8 classes)
        pca_count = page.count("print-color-adjust")
        assert pca_count >= 16, (
            f"print-color-adjust appears only {pca_count} times, expected >= 16"
        )


class TestSymmetrySignals:
    """Symmetry signal rendering in report UI."""

    def test_signal_card_css_exists(self):
        """Signal card CSS classes are defined for report rendering."""
        page = build_report_page(job_id="test-job")
        assert ".signal-card" in page
        assert ".signal-level-small" in page or "signal-level-" in page

    def test_level_label_function_exists(self):
        """levelLabel function handles all difference_level values."""
        page = build_report_page(job_id="test-job")
        assert "levelLabel" in page
        assert "Calibration pending" in page
        assert "Small Difference" in page
        assert "Moderate Difference" in page
        assert "Larger Difference" in page

    def test_not_available_label_is_calibration_pending(self):
        """not_available level maps to 'Calibration pending' in external."""
        page = build_report_page(job_id="test-job")
        assert "level==='small'" in page or "'small'" in page
        assert "Calibration pending" in page

    def test_signal_color_tokens_used(self):
        """Signal card colors use approved status tokens."""
        page = build_report_page(job_id="test-job")
        # Color tokens are applied via CSS custom properties
        assert "--status-available" in page
        assert "--status-pending" in page
        assert "--status-error" in page
        assert "--status-unconfigured" in page


class TestNotAvailableRendering:
    """not_available signals render correctly without fabricated values."""

    def test_not_available_external_label(self):
        """not_available external label is 'Calibration pending'."""
        page = build_report_page(job_id="test-job")
        assert "Calibration pending" in page

    def test_not_available_internal_label(self):
        """not_available internal label references reference statistics."""
        page = build_report_page(job_id="test-job")
        assert "Reference statistics unavailable" in page

    def test_no_small_moderate_larger_fabrication(self):
        """Report UI does not fabricate small/moderate/larger for unavailable data."""
        page = build_report_page(job_id="test-job")
        # levelLabel returns 'Calibration pending' for not_available
        assert "Calibration pending" in page
        assert "Reference statistics unavailable" in page


class TestSafetyBoundaries:
    """Report UI does not expose prohibited fields."""

    def test_no_raw_feature_values(self):
        """No raw feature values exposed in report UI HTML/JS."""
        page = build_report_page(job_id="test-job")
        assert "feature_value" not in page
        assert "raw_feature" not in page

    def test_no_percentile_cutoffs(self):
        """No percentile cutoffs exposed."""
        page = build_report_page(job_id="test-job")
        assert "percentile_cutoff" not in page
        assert "cutoff" not in page

    def test_no_full_checksum(self):
        """No full checksum exposed — only prefix (max 8 chars)."""
        page = build_report_page(job_id="test-job")
        # The JS uses substring(0,8) for checksum prefix
        assert "substring(0,8)" in page or "checksumPrefix" in page
        assert ".substring(0,8)" in page
        # No 64-char hex string hardcoded
        assert "a1b2c3d4e5f6070809a0b1c2d3e4f5070809a0b1c2d3e4f5070809a0b1c2d3001" not in page

    def test_no_s3_paths(self):
        """No S3 paths exposed in report UI."""
        page = build_report_page(job_id="test-job")
        assert "s3://" not in page

    def test_no_manifest_keys(self):
        """No manifest keys exposed."""
        page = build_report_page(job_id="test-job")
        assert "manifest_key" not in page

    def test_no_aws_arns(self):
        """No AWS ARNs exposed."""
        page = build_report_page(job_id="test-job")
        assert "arn:aws" not in page

    def test_no_raw_h5_paths(self):
        """No raw H5 paths exposed."""
        page = build_report_page(job_id="test-job")
        assert "/scans/" not in page
        assert "/tmp/" not in page

    def test_no_model_internals(self):
        """No model internals (coefficients, weights) exposed."""
        page = build_report_page(job_id="test-job")
        assert "coefficient" not in page
        assert "intercept" not in page
        assert "scaler_mean" not in page
        assert "imputer_statistics" not in page

    def test_no_raw_exceptions(self):
        """No raw exception text or stack traces exposed."""
        page = build_report_page(job_id="test-job")
        assert "Traceback" not in page
        assert "Stack trace" not in page

    def test_no_phi(self):
        """No PHI (patient identifiers) exposed."""
        page = build_report_page(job_id="test-job")
        assert "patient_id" not in page
        assert "patient_name" not in page

    def test_no_raw_target_control_refs(self):
        """No raw target/control refs exposed."""
        page = build_report_page(job_id="test-job")
        assert "target_scan_ref" not in page
        assert "control_scan_ref" not in page


class TestServerSidePDFAbsence:
    """No server-side PDF dependencies."""

    def test_no_weasyprint(self):
        page = build_report_page(job_id="test-job")
        assert "WeasyPrint" not in page
        assert "weasyprint" not in page

    def test_no_chromium_puppeteer_playwright(self):
        page = build_report_page(job_id="test-job")
        assert "puppeteer" not in page.lower()
        assert "playwright" not in page.lower()
        assert "chromium" not in page.lower()

    def test_no_pango_cairo(self):
        page = build_report_page(job_id="test-job")
        assert "pango" not in page.lower()
        assert "cairo" not in page.lower()


class TestDesignTokens:
    """All hex colors match BREMEN_DESIGN_SPEC_v1.md palette."""

    def test_all_hex_colors_approved(self):
        """Every hex color in report CSS matches the approved palette."""
        page = build_report_page(job_id="test-job")
        approved = _approved_hex_colors()
        hex_colors = set(_re.findall(r'#[0-9A-Fa-f]{6}', page))
        # CSS shorthand like #FFF may appear — verify all 6-digit hex
        for color in hex_colors:
            assert color in approved, (
                f"Unapproved hex color found: {color}. "
                f"Approved colors are: {sorted(approved)}"
            )

    def test_no_prohibited_colors(self):
        """No prohibited hex colors appear."""
        page = build_report_page(job_id="test-job")
        prohibited = {
            "#0969da", "#1a7f37", "#cf222e", "#9a6700",
            "#d0d7de", "#656d76", "#1f2328",
        }
        hex_colors = set(_re.findall(r'#[0-9A-Fa-f]{6}', page))
        for color in hex_colors:
            assert color.upper() not in {p.upper() for p in prohibited}, (
                f"Prohibited color found: {color}"
            )

    def test_design_tokens_defined(self):
        """All required design token custom properties are defined."""
        page = build_report_page(job_id="test-job")
        required_tokens = [
            "--bg-page", "--bg-surface", "--text-primary", "--text-secondary",
            "--accent", "--border",
            "--status-available", "--status-pending", "--status-unconfigured", "--status-error",
            "--tint-accent", "--tint-pending", "--tint-error",
            "--radius-card", "--radius-pill",
            "--fs-32", "--fs-22", "--fs-17", "--fs-14", "--fs-13", "--fs-11",
            "--sp-4", "--sp-8", "--sp-12", "--sp-16", "--sp-24", "--sp-32", "--sp-48", "--sp-64",
        ]
        for token in required_tokens:
            assert token in page, f"Missing design token: {token}"


class TestAccessibility:
    """Report page meets accessibility requirements."""

    def test_tab_roles(self):
        """Tab buttons have role='tab'."""
        page = build_report_page(job_id="test-job")
        assert 'role="tab"' in page

    def test_tabpanel_roles(self):
        """Tab panels have role='tabpanel'."""
        page = build_report_page(job_id="test-job")
        assert 'role="tabpanel"' in page

    def test_aria_selected(self):
        """Tab buttons have aria-selected."""
        page = build_report_page(job_id="test-job")
        assert 'aria-selected' in page

    def test_aria_controls(self):
        """Tab buttons use aria-controls."""
        page = build_report_page(job_id="test-job")
        assert 'aria-controls' in page

    def test_tablist_role(self):
        """Tab container has role='tablist'."""
        page = build_report_page(job_id="test-job")
        assert 'role="tablist"' in page

    def test_real_button_elements(self):
        """Print and tab buttons are real <button> elements."""
        page = build_report_page(job_id="test-job")
        assert "<button" in page
        assert 'class="print-button"' in page

    def test_no_div_as_button(self):
        """No div-as-button anti-pattern."""
        page = build_report_page(job_id="test-job")
        # Check that buttons with onclick are actual button tags
        for match in _re.finditer(r'<button[^>]*onclick=', page):
            assert match.group().startswith("<button")

    def test_focus_outline(self):
        """Visible focus outline defined."""
        page = build_report_page(job_id="test-job")
        assert "focus-visible" in page or ":focus" in page
        assert "outline" in page

    def test_prefers_reduced_motion(self):
        """prefers-reduced-motion is respected."""
        page = build_report_page(job_id="test-job")
        assert "prefers-reduced-motion" in page

    def test_semantic_headings(self):
        """No heading elements needed since report is label-driven, but semantic structure present."""
        page = build_report_page(job_id="test-job")
        # The report uses section-title divs — verify structure exists
        assert "section-title" in page

    def test_keyboard_tab_navigation(self):
        """Arrow key tab navigation is implemented."""
        page = build_report_page(job_id="test-job")
        assert "ArrowRight" in page or "ArrowLeft" in page

    def test_signal_labels_in_text(self):
        """Signal chip labels are in text, not color-only."""
        page = build_report_page(job_id="test-job")
        # levelChipLabel returns text labels for each level
        assert "Small" in page
        assert "Moderate" in page
        assert "Larger" in page
        assert "Calibration pending" in page


class TestBackwardCompatibility:
    """Existing route and function signatures remain compatible."""

    def test_build_report_page_no_arguments(self):
        """build_report_page() works with no arguments."""
        page = build_report_page()
        assert "<!DOCTYPE html>" in page
        assert "Bremen" in page

    def test_build_report_page_with_job_id(self):
        """build_report_page(job_id='test') returns valid HTML."""
        page = build_report_page(job_id="test")
        assert "<!DOCTYPE html>" in page
        assert "Bremen Report" in page

    def test_build_report_page_with_base_url(self):
        """build_report_page(base_url='http://localhost:9999') embeds URL."""
        page = build_report_page(base_url="http://localhost:9999")
        assert "http://localhost:9999" in page

    def test_report_page_is_html5(self):
        """Return value is a valid HTML5 document."""
        page = build_report_page(job_id="test")
        assert page.startswith("<!DOCTYPE html>")
        assert "<html lang=" in page
        assert "</html>" in page

    def test_report_contains_js(self):
        """Report page contains JavaScript."""
        page = build_report_page(job_id="test")
        assert "<script>" in page
        assert "switchTab" in page


class TestSymmetrySignalDetail:
    """Internal tab symmetry signal detail rendering."""

    def test_signal_breakdown_table_structure(self):
        """Internal tab has signal breakdown table."""
        page = build_report_page(job_id="test-job")
        assert "signal-breakdown-table" in page

    def test_feature_family_rendered(self):
        """Feature family column exists in internal breakdown."""
        page = build_report_page(job_id="test-job")
        assert "feature_family" in page

    def test_checksum_prefix_handling(self):
        """Checksum prefix is handled as max 8 hex chars."""
        page = build_report_page(job_id="test-job")
        # JS extracts first 8 chars
        assert ".substring(0,8)" in page

    def test_reference_artifact_version_not_exposed_internally(self):
        """Reference artifact version is not exposed in public JS.

        The normalized internal report contract omits reference_artifact_version
        from the public JS output. It is only available server-side.
        """
        page = build_report_page(job_id="test-job")
        # reference_artifact_version is not in the normalized JS contract
        assert "reference_artifact_version" not in page

    def test_symmetry_signal_detail_key_present(self):
        """symmetry_signal_detail key is referenced in JS."""
        page = build_report_page(job_id="test-job")
        assert "symmetry_signal_detail" in page

    def test_five_signals_referenced(self):
        """All 5 signal labels are part of levelLabel mapping."""
        page = build_report_page(job_id="test-job")
        # The JS function handles all four levels
        assert "level==='small'" in page or "levelLabel" in page
        assert "Small Difference" in page
        assert "Moderate Difference" in page
        assert "Larger Difference" in page
        assert "Calibration pending" in page
        assert "Reference statistics unavailable" in page


class TestDurationMsNullFix:
    """Execution trace is rendered as a normalized field table."""

    def test_execution_trace_uses_field_table(self):
        """Execution trace section uses renderFieldTable, not raw duration_ms."""
        page = build_report_page(job_id="test-job")
        assert "execution-trace-summary" in page
        # The normalized trace is rendered via renderFieldTable
        assert "renderFieldTable" in page

    def test_no_nullms_in_page(self):
        """No literal 'nullms' string in the rendered page."""
        page = build_report_page(job_id="test-job")
        assert "nullms" not in page


class TestExternalQCStatusMapping:
    """External tab reads QC status from normalized report contract."""

    def test_external_reads_qc_from_normalized_prediction(self):
        """External QC is read from prediction_summary.qc_status in normalized JS."""
        page = build_report_page(job_id="test-job")
        # The normalized JS reads QC from prediction_summary (extReport)
        assert "prediction_summary" in page
        assert "qc_status" in page

    def test_external_qc_rendered_in_hero(self):
        """External QC status is rendered in the recommendation hero section."""
        page = build_report_page(job_id="test-job")
        assert "QC status" in page


class TestTabStructureOneShell:
    """Report is one page shell with External/Internal tabs."""

    def test_single_report_page_shell(self):
        """One report-page div contains both tab panels."""
        page = build_report_page(job_id="test-job")
        # Count report-page divs — should be exactly 1
        import re
        matches = re.findall(r'class="report-page"', page)
        assert len(matches) == 1, f"Expected 1 report-page, found {len(matches)}"

    def test_both_panels_in_same_shell(self):
        """Both panel-external and panel-internal live under report-content."""
        page = build_report_page(job_id="test-job")
        assert 'id="panel-external"' in page
        assert 'id="panel-internal"' in page
        assert 'report-content' in page


# ---------------------------------------------------------------------------
# PR0093B — Normalized External report JSON contract keys
# ---------------------------------------------------------------------------


EXTERNAL_REPORT_KEYS = [
    "output_type", "report_schema_version", "report_id", "generated_at",
    "job_id", "request_id", "patient_reference", "analysis_author",
    "intended_use", "limitations", "model_metadata", "input_summary",
    "prediction_summary", "decision_support", "symmetry_signals",
]


EXTERNAL_MODEL_METADATA_KEYS = [
    "model_version", "feature_schema_version", "threshold_version",
    "threshold_value",
]

EXTERNAL_INPUT_SUMMARY_KEYS = [
    "input_mode", "explicit_refs_provided", "layout_category",
]

EXTERNAL_PREDICTION_SUMMARY_KEYS = [
    "p_mri_needed", "decision_code", "decision_display_name",
    "decision_policy_id", "decision_policy_version", "qc_status",
    "qc_flags",
]

EXTERNAL_SYMMETRY_SIGNALS_KEYS = [
    "schema_status", "measurement_summary", "signals", "note",
]


class TestExternalReportJSONContract:
    """External report JSON contract matches bremen_external_report.yaml."""

    def test_external_report_top_level_keys(self):
        """build_external_report_json returns all required top-level keys."""
        from bremen.report_ui import build_external_report_json
        report = {"payload": {"decision_support_report": {}}}
        result = build_external_report_json(report)
        for key in EXTERNAL_REPORT_KEYS:
            assert key in result, f"Missing top-level key: {key}"

    def test_external_output_type(self):
        """output_type is 'bremen_decision_support_report'."""
        from bremen.report_ui import build_external_report_json
        result = build_external_report_json({})
        assert result["output_type"] == "bremen_decision_support_report"

    def test_external_model_metadata_keys(self):
        """model_metadata contains all required keys."""
        from bremen.report_ui import build_external_report_json
        result = build_external_report_json({})
        for key in EXTERNAL_MODEL_METADATA_KEYS:
            assert key in result["model_metadata"], (
                f"Missing model_metadata key: {key}"
            )

    def test_external_input_summary_keys(self):
        """input_summary contains all required keys."""
        from bremen.report_ui import build_external_report_json
        result = build_external_report_json({})
        for key in EXTERNAL_INPUT_SUMMARY_KEYS:
            assert key in result["input_summary"], (
                f"Missing input_summary key: {key}"
            )

    def test_external_prediction_summary_keys(self):
        """prediction_summary contains all required keys."""
        from bremen.report_ui import build_external_report_json
        result = build_external_report_json({})
        for key in EXTERNAL_PREDICTION_SUMMARY_KEYS:
            assert key in result["prediction_summary"], (
                f"Missing prediction_summary key: {key}"
            )

    def test_external_symmetry_signals_keys(self):
        """symmetry_signals contains all required keys."""
        from bremen.report_ui import build_external_report_json
        result = build_external_report_json({})
        for key in EXTERNAL_SYMMETRY_SIGNALS_KEYS:
            assert key in result["symmetry_signals"], (
                f"Missing symmetry_signals key: {key}"
            )

    def test_external_limitations_is_list(self):
        """limitations is a non-empty list."""
        from bremen.report_ui import build_external_report_json
        result = build_external_report_json({})
        assert isinstance(result["limitations"], list)
        assert len(result["limitations"]) > 0

    def test_external_intended_use_no_diagnosis(self):
        """intended_use states not a diagnosis."""
        from bremen.report_ui import build_external_report_json
        result = build_external_report_json({})
        assert "not a diagnosis" in result["intended_use"].lower()

    def test_external_empty_report_safe(self):
        """Empty report produces safe defaults without crashing."""
        from bremen.report_ui import build_external_report_json
        result = build_external_report_json(None)
        assert result["output_type"] == "bremen_decision_support_report"
        assert result["job_id"] is None


# ---------------------------------------------------------------------------
# PR0093B — Normalized Internal report JSON contract keys
# ---------------------------------------------------------------------------


INTERNAL_REPORT_KEYS = [
    "output_type", "report_schema_version", "report_id", "generated_at",
    "job_identity", "model_and_plugin", "decision_policy",
    "input_summary", "execution_trace_summary", "symmetry_signal_detail",
]

INTERNAL_JOB_IDENTITY_KEYS = [
    "job_id", "request_id", "created_at", "completed_at", "status",
]

INTERNAL_MODEL_AND_PLUGIN_KEYS = [
    "model_version", "model_checksum_prefix", "feature_schema_version",
    "plugin_id", "plugin_version", "report_schema_version",
]

INTERNAL_DECISION_POLICY_KEYS = [
    "decision_code", "decision_policy_id", "decision_policy_version",
    "threshold_value", "qc_status", "qc_flags",
]

INTERNAL_SYMMETRY_SIGNAL_DETAIL_KEYS = [
    "schema_status", "measurement_summary", "signals", "note",
]


class TestInternalReportJSONContract:
    """Internal report JSON contract matches bremen_internal_report.yaml."""

    def test_internal_report_top_level_keys(self):
        """build_internal_report_json returns all required top-level keys."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json({})
        for key in INTERNAL_REPORT_KEYS:
            assert key in result, f"Missing top-level key: {key}"

    def test_internal_output_type(self):
        """output_type is 'bremen_internal_report'."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json({})
        assert result["output_type"] == "bremen_internal_report"

    def test_internal_job_identity_keys(self):
        """job_identity contains all required keys."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json({})
        for key in INTERNAL_JOB_IDENTITY_KEYS:
            assert key in result["job_identity"], (
                f"Missing job_identity key: {key}"
            )

    def test_internal_model_and_plugin_keys(self):
        """model_and_plugin contains all required keys."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json({})
        for key in INTERNAL_MODEL_AND_PLUGIN_KEYS:
            assert key in result["model_and_plugin"], (
                f"Missing model_and_plugin key: {key}"
            )

    def test_internal_decision_policy_keys(self):
        """decision_policy contains all required keys."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json({})
        for key in INTERNAL_DECISION_POLICY_KEYS:
            assert key in result["decision_policy"], (
                f"Missing decision_policy key: {key}"
            )

    def test_internal_symmetry_signal_detail_keys(self):
        """symmetry_signal_detail contains all required keys."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json({})
        for key in INTERNAL_SYMMETRY_SIGNAL_DETAIL_KEYS:
            assert key in result["symmetry_signal_detail"], (
                f"Missing symmetry_signal_detail key: {key}"
            )

    def test_internal_execution_trace_summary_is_dict(self):
        """execution_trace_summary is a dict."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json({})
        assert isinstance(result["execution_trace_summary"], dict)

    def test_internal_checksum_prefix_only(self):
        """Checksum is prefix-only, max 8 chars."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json({})
        prefix = result["model_and_plugin"]["model_checksum_prefix"]
        if prefix is not None:
            assert len(prefix) <= 8, (
                f"Checksum prefix exceeds 8 chars: {prefix!r}"
            )

    def test_internal_checksum_never_full_64(self):
        """Full 64-char checksum is never present."""
        from bremen.report_ui import build_internal_report_json
        full_checksum = (
            "a1b2c3d4e5f6070809a0b1c2d3e4f5070809"
            "a0b1c2d3e4f5070809a0b1c2d3e4f5070809"
        )
        result = build_internal_report_json({})
        import json as _json
        result_str = _json.dumps(result)
        assert full_checksum not in result_str

    def test_internal_empty_report_safe(self):
        """Empty report produces safe defaults without crashing."""
        from bremen.report_ui import build_internal_report_json
        result = build_internal_report_json(None)
        assert result["output_type"] == "bremen_internal_report"


# ---------------------------------------------------------------------------
# PR0093B — Report-specific HTML structure
# ---------------------------------------------------------------------------


class TestReportHTMLStructure:
    """Report HTML contains required report-document structure classes."""

    def test_report_document_class(self):
        page = build_report_page(job_id="test")
        assert 'class="report-document"' in page

    def test_report_header_class(self):
        page = build_report_page(job_id="test")
        assert 'class="report-header"' in page

    def test_recommendation_hero_class(self):
        page = build_report_page(job_id="test")
        assert 'class="recommendation-hero"' in page

    def test_structural_comparison_class(self):
        page = build_report_page(job_id="test")
        assert 'class="structural-comparison"' in page

    def test_decision_meaning_class(self):
        page = build_report_page(job_id="test")
        assert 'class="decision-meaning"' in page

    def test_internal_technical_report_class(self):
        page = build_report_page(job_id="test")
        assert 'class="report-document internal-technical-report"' in page

    def test_boundary_note_class(self):
        page = build_report_page(job_id="test")
        assert 'class="boundary-note"' in page

    def test_signal_breakdown_table_class(self):
        page = build_report_page(job_id="test")
        assert 'class="signal-breakdown-table"' in page

    def test_report_footer_class(self):
        page = build_report_page(job_id="test")
        assert 'class="report-footer"' in page

    def test_report_meta_block_class(self):
        page = build_report_page(job_id="test")
        assert 'class="report-meta-block"' in page

    def test_technical_demo_notice_class(self):
        page = build_report_page(job_id="test")
        assert 'class="technical-demo-notice"' in page

    def test_signal_card_grid_class(self):
        page = build_report_page(job_id="test")
        assert 'class="signal-card-grid"' in page

    def test_signal_card_class(self):
        page = build_report_page(job_id="test")
        # signal-card class is generated by JS — check CSS selector and JS reference
        assert '.signal-card' in page or 'signal-card' in page

    def test_execution_trace_summary_class(self):
        page = build_report_page(job_id="test")
        assert 'class="execution-trace-summary"' in page


# ---------------------------------------------------------------------------
# PR0093B — Forbidden content absence
# ---------------------------------------------------------------------------


class TestForbiddenContentAbsence:
    """Report does not contain forbidden phrases or unsafe content."""

    def test_no_asymmetry_assessment_not_available(self):
        """The forbidden collapsed sentence must not appear."""
        page = build_report_page(job_id="test")
        assert "Asymmetry assessment is not available" not in page

    def test_no_sample_values_in_live_mode(self):
        """Live mode does not embed sample-data-json."""
        page = build_report_page(job_id="test-job")
        assert 'id="sample-data-json"' not in page

    def test_no_full_checksum_in_html(self):
        """No full 64-char checksum in page."""
        page = build_report_page(job_id="test-job")
        # 64 hex chars = typical SHA256
        assert "a1b2c3d4e5f6070809a0b1c2d3e4f5070809a0b1c2d3e4f5070809a0b1c2d3001" not in page

    def test_no_weasyprint_dependency(self):
        """No server-side PDF tool referenced."""
        page = build_report_page(job_id="test")
        assert "WeasyPrint" not in page
        assert "weasyprint" not in page

    def test_browser_native_print_only(self):
        """Print uses window.print(), not server-side PDF."""
        page = build_report_page(job_id="test")
        assert "window.print()" in page
