"""Tests for the Bremen demo UI module.

Covers:
- build_demo_html_page() returns HTML string
- HTML contains "Bremen" product identity
- HTML contains "technical demo" safety marker
- HTML contains "not a clinical" disclaimer text
- HTML contains inline CSS <style> tag
- HTML has no external URLs (no CDN, fonts, images)
- build_demo_evidence_json_response() returns valid JSON
- Evidence JSON contains technical_demo_only: true
- Evidence JSON contains product: "Bremen"
- Evidence JSON is deterministic
- No Aramis references in HTML or JSON
- No clinical/replacement claims (except safe negation)
- Import/dependency safety
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from bremen.demo_ui import (
    build_demo_html_page,
    build_demo_evidence_json_response,
)

MODULE_PATH = Path(__file__).parents[1] / "src" / "bremen" / "demo_ui.py"


# ===================================================================
# Helpers
# ===================================================================


def _sample_evidence() -> dict:
    """Return a sample evidence bundle for testing."""
    return {
        "technical_demo_only": True,
        "product": "Bremen",
        "product_question": "Should patient continue to MRI?",
        "disclaimer": (
            "This is a technical product demo of Bremen's controlled "
            "decision-support workflow. It is not a clinical result."
        ),
        "evidence_version": "v0.1",
        "scenario_id": "bremen_demo_v1",
        "model_status": "ready",
        "model_version": "smoke-v0.1",
        "feature_schema_version": "bremen.feature_artifact.v0.1",
        "prediction_status": "not_available",
        "checks": {"health": "pass", "model_version": "pass"},
        "warnings": [],
        "safety_notes": [
            "Technical product demo only — not a clinical result.",
            "Not clinically validated.",
            "Does not replace MRI, biopsy, radiologist, clinician, "
            "or clinical judgment.",
            "All clinical decisions must be made by qualified clinicians.",
        ],
        "base_url": "http://127.0.0.1:8000",
        "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    }


# ===================================================================
# Class 1: HTML page content
# ===================================================================


class TestHtmlPageContent:
    def test_returns_string(self):
        """build_demo_html_page returns a string."""
        html = build_demo_html_page()
        assert isinstance(html, str)

    def test_contains_bremen(self):
        """HTML contains 'Bremen' product identity."""
        html = build_demo_html_page()
        assert "Bremen" in html

    def test_contains_technical_demo(self):
        """HTML contains 'Technical demo only' banner."""
        html = build_demo_html_page()
        assert "Technical demo only" in html

    def test_contains_not_a_clinical(self):
        """HTML contains safety disclaimer text."""
        html = build_demo_html_page()
        assert "not a clinical result" in html.lower()

    def test_contains_inline_css(self):
        """HTML contains inline <style> tag."""
        html = build_demo_html_page()
        assert "<style>" in html

    def test_contains_product_question(self):
        """HTML contains the product question."""
        html = build_demo_html_page()
        assert "Should patient continue to MRI?" in html

    def test_with_evidence_uses_evidence_data(self):
        """HTML uses provided evidence data."""
        evidence = _sample_evidence()
        html = build_demo_html_page(evidence=evidence)
        assert "smoke-v0.1" in html
        assert "bremen_demo_v1" in html

    def test_with_request_id(self):
        """HTML includes request_id."""
        evidence = _sample_evidence()
        html = build_demo_html_page(
            evidence=evidence,
            request_id="test-req-123",
        )
        assert "test-req-123" in html

    def test_no_external_urls(self):
        """HTML contains no external network URLs."""
        html = build_demo_html_page()
        # Allow http:// in safe context (base_url display), but no CDN/fonts
        assert "cdn" not in html.lower()
        assert "unpkg" not in html.lower()
        assert "jsdelivr" not in html.lower()
        assert "googleapis" not in html.lower()
        assert "fontawesome" not in html.lower()

    def test_html_has_doctype(self):
        """HTML starts with HTML5 doctype."""
        html = build_demo_html_page()
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_no_javascript(self):
        """HTML contains no <script> tags."""
        html = build_demo_html_page()
        assert "<script>" not in html.lower()

    def test_html_structure(self):
        """HTML has html, head, body tags."""
        html = build_demo_html_page()
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</html>" in html

    def test_with_warnings_includes_warnings_section(self):
        """HTML includes warning section when warnings present."""
        evidence = _sample_evidence()
        evidence["warnings"] = ["Test warning", "Another warning"]
        html = build_demo_html_page(evidence=evidence)
        assert "Test warning" in html
        assert "Another warning" in html

    def test_service_health_card_present(self):
        """HTML includes service health card."""
        html = build_demo_html_page()
        assert "Service Health" in html

    def test_model_source_card_present(self):
        """HTML includes model/source card."""
        html = build_demo_html_page()
        assert "Model / Source" in html

    def test_evidence_bundle_card_present(self):
        """HTML includes evidence bundle card."""
        html = build_demo_html_page()
        assert "Evidence Bundle" in html

    def test_demo_flow_card_present(self):
        """HTML includes demo flow card."""
        html = build_demo_html_page()
        assert "Demo Flow" in html

    def test_footer_has_safety_disclaimer(self):
        """HTML footer includes safety disclaimer."""
        html = build_demo_html_page()
        assert "Does not replace MRI" in html


# ===================================================================
# Class 2: Evidence JSON response
# ===================================================================


class TestEvidenceJsonResponse:
    def test_returns_valid_json(self):
        """build_demo_evidence_json_response returns valid JSON."""
        json_str = build_demo_evidence_json_response()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_contains_technical_demo_only(self):
        """JSON contains technical_demo_only: true."""
        json_str = build_demo_evidence_json_response()
        parsed = json.loads(json_str)
        assert parsed["technical_demo_only"] is True

    def test_contains_product(self):
        """JSON contains product: 'Bremen'."""
        json_str = build_demo_evidence_json_response()
        parsed = json.loads(json_str)
        assert parsed["product"] == "Bremen"

    def test_contains_evidence_version(self):
        """JSON contains evidence_version."""
        json_str = build_demo_evidence_json_response()
        parsed = json.loads(json_str)
        assert "evidence_version" in parsed

    def test_contains_safety_notes(self):
        """JSON contains safety_notes list."""
        json_str = build_demo_evidence_json_response()
        parsed = json.loads(json_str)
        assert isinstance(parsed.get("safety_notes"), list)
        assert len(parsed["safety_notes"]) > 0

    def test_with_explicit_evidence(self):
        """JSON uses explicitly provided evidence."""
        evidence = _sample_evidence()
        evidence["model_version"] = "custom-v1.0"
        json_str = build_demo_evidence_json_response(evidence=evidence)
        parsed = json.loads(json_str)
        assert parsed["model_version"] == "custom-v1.0"

    def test_deterministic_with_same_evidence(self):
        """Same evidence produces identical JSON."""
        evidence = _sample_evidence()
        j1 = build_demo_evidence_json_response(evidence=evidence)
        j2 = build_demo_evidence_json_response(evidence=evidence)
        assert j1 == j2

    def test_content_type_indication(self):
        """JSON string is valid parsable JSON."""
        json_str = build_demo_evidence_json_response()
        # Should not raise
        parsed = json.loads(json_str)
        assert parsed is not None

    def test_no_diagnosis_claim(self):
        """JSON does not contain clinical claims (except safe negation)."""
        evidence = _sample_evidence()
        json_str = build_demo_evidence_json_response(evidence=evidence)
        lower = json_str.lower()
        assert "replaces mri" not in lower
        assert "replaces biopsy" not in lower
        assert "replaces radiologist" not in lower
        assert "replaces clinician" not in lower


# ===================================================================
# Class 3: No Aramis references
# ===================================================================


class TestNoAramisReferences:
    def test_no_aramis_in_html(self):
        """HTML output does not contain Aramis strings."""
        html = build_demo_html_page()
        html_lower = html.lower()
        for pattern in ("aramis", "m2q", "benign vs cancer"):
            assert pattern not in html_lower, (
                f"HTML contains prohibited pattern: {pattern}"
            )

    def test_no_aramis_in_json(self):
        """JSON output does not contain Aramis strings."""
        json_str = build_demo_evidence_json_response()
        json_lower = json_str.lower()
        for pattern in ("aramis", "m2q", "benign vs cancer"):
            assert pattern not in json_lower, (
                f"JSON contains prohibited pattern: {pattern}"
            )

    def test_no_aramis_in_module_source(self):
        """Module source does not contain Aramis references."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "Aramis" not in source
        assert "aramis" not in source


# ===================================================================
# Class 4: Import/dependency safety
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
