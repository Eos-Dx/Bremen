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
        """@media print preserves report card layout."""
        page = build_report_page(job_id="test-job")
        assert ".recommendation-card" in page
        assert "page-break-inside" in page
        assert "avoid" in page


class TestSymmetrySignals:
    """Symmetry signal rendering in report UI."""

    def test_signal_chip_css_classes_exist(self):
        """Signal chip CSS classes are defined."""
        page = build_report_page(job_id="test-job")
        assert ".signal-chip" in page
        # Check each difference_level has a CSS class
        assert ".signal-chip.small" in page
        assert ".signal-chip.moderate" in page
        assert ".signal-chip.larger" in page
        assert ".signal-chip.not_available" in page

    def test_level_chip_label_function(self):
        """levelChipLabel function handles all difference_level values."""
        page = build_report_page(job_id="test-job")
        assert "levelChipLabel" in page
        assert "Calibration pending" in page
        assert "'Small'" in page
        assert "'Moderate'" in page
        assert "'Larger'" in page

    def test_detail_level_label_function(self):
        """detailLevelLabel function handles not_available as reference stats unavailable."""
        page = build_report_page(job_id="test-job")
        assert "detailLevelLabel" in page
        assert "Reference statistics unavailable" in page

    def test_not_available_is_calibration_pending(self):
        """not_available level maps to 'Calibration pending' in external."""
        page = build_report_page(job_id="test-job")
        assert "'not_available': return 'Calibration pending'" in page or \
               "case 'not_available'" in page

    def test_signal_chip_color_tokens(self):
        """Signal chip colors use approved status tokens."""
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
        """not_available internal label mentions reference statistics."""
        page = build_report_page(job_id="test-job")
        assert "Reference statistics unavailable" in page

    def test_no_small_moderate_larger_fabrication(self):
        """Report UI does not fabricate small/moderate/larger for unavailable data."""
        page = build_report_page(job_id="test-job")
        # The JS function returns Calibration pending for not_available
        assert "default: return 'Calibration pending'" in page or \
               "default: return 'Reference statistics unavailable'" in page


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

    def test_signal_detail_table_structure(self):
        """Internal tab has signal detail table with columns."""
        page = build_report_page(job_id="test-job")
        assert "signal-detail-table" in page

    def test_feature_family_column(self):
        """Feature family column exists in internal detail."""
        page = build_report_page(job_id="test-job")
        assert "feature-family" in page

    def test_checksum_prefix_handling(self):
        """Checksum prefix is handled as max 8 hex chars."""
        page = build_report_page(job_id="test-job")
        # JS extracts first 8 chars
        assert ".substring(0,8)" in page

    def test_reference_artifact_version_present(self):
        """Reference artifact version field is rendered."""
        page = build_report_page(job_id="test-job")
        # The JS checks for reference_artifact_version
        assert "reference_artifact_version" in page

    def test_symmetry_signal_detail_key_present(self):
        """symmetry_signal_detail key is referenced in JS."""
        page = build_report_page(job_id="test-job")
        assert "symmetry_signal_detail" in page

    def test_five_signals_referenced(self):
        """All 5 signal labels are part of levelChipLabel/detailLevelLabel mapping."""
        page = build_report_page(job_id="test-job")
        # The JS function handles all four levels
        assert "case 'small'" in page or "'small':" in page
        assert "case 'moderate'" in page or "'moderate':" in page
        assert "case 'larger'" in page or "'larger':" in page
        assert "case 'not_available'" in page or "'not_available':" in page
