"""Sanitized Bremen demo Model Playground page.

This module reads the uploaded standalone HTML, sanitizes it to remove
production coefficients, artifact SHA256, and raw model internals, and
adds sandbox/synthetic/technical demo branding plus navigation links.

Safety
------
- No production coefficients, intercept, or threshold are exposed.
- No full artifact SHA256 or checksum.
- No raw model/joblib internals.
- No S3/H5 paths or keys.
- No PHI.
- No diagnostic/clinical claims.
- All content is synthetic sandbox-only.
"""

from __future__ import annotations

import re
from pathlib import Path

_SOURCE_HTML = (
    Path(__file__).resolve().parents[2]
    / ".project-memory" / "pr" / "0104s-demo-model-guide-page"
    / "source-bremen_ML_demo_en.raw.html"
)

# Production SHA256 to replace globally
_PROD_SHA = "971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4"


def _sanitize_html(raw: str) -> str:
    """Remove production coefficients, SHA256, and raw model internals.

    Uses global string replacements to catch all occurrences in both
    JavaScript CFG objects, HTML body text, and translation maps.
    """
    # Global replace of production SHA256
    raw = raw.replace(_PROD_SHA, "sandbox-synthetic-not-production")

    # Global replace of production intercept and threshold
    raw = raw.replace("-0.038341628329418675", "0.0")
    raw = raw.replace("0.4130396520921527", "0.5")

    # Clean up coefficient_source and artifact_verified
    raw = raw.replace(
        '"coefficient_source": "model.joblib portable_logreg, exact"',
        '"coefficient_source": "synthetic sandbox placeholder"',
    )
    raw = raw.replace(
        '"artifact_verified": true',
        '"artifact_verified": false',
    )

    return raw


def _add_nav_links(html: str) -> str:
    """Add navigation links to the playground page."""
    nav_html = (
        '<nav class="guide-nav" aria-label="Demo navigation">'
        '<a href="/demo">Start</a> '
        '<a href="/demo/control-room">Control Room</a> '
        '<a href="/demo/model-guide">Model Guide</a> '
        '<a href="/demo/api-docs">API docs</a>'
        '</nav>'
    )
    # Insert nav after the header opening
    html = html.replace(
        '<header class="hero">',
        f'<header class="hero">{nav_html}',
        1,
    )
    return html


def _add_sandbox_branding(html: str) -> str:
    """Add sandbox/synthetic/technical demo branding."""
    # Add sandbox notice after the shell div
    sandbox_notice = (
        '<div class="sandbox-notice" style="background:#fff4e8;border:1px solid #e7c391;'
        'color:#7a4b13;padding:12px;border-radius:9px;margin:12px 0;font-size:13px;">'
        '<strong>Sandbox / Technical Demo Only</strong> — '
        'This page uses synthetic data and prototype parameters for demonstration '
        'purposes only. It is not connected to real H5 uploads, real jobs, real '
        'reports, or production model mutation. Export scenario and prototype '
        'parameters may be visual only or disabled placeholders. '
        'This does not create a deployable model.'
        '</div>'
    )
    html = html.replace(
        '<div class="shell">',
        f'<div class="shell">{sandbox_notice}',
        1,
    )

    # Update title
    html = html.replace(
        '<title>Bremen \u2014 training and prediction</title>',
        '<title>Bremen Model Playground \u2014 Technical Demo Sandbox</title>',
    )

    # Update hero text to sandbox branding
    html = html.replace(
        '\u041a\u0430\u043a \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442 \u043c\u043e\u0434\u0435\u043b\u044c <strong>Bremen</strong>',
        'Model Playground <strong>Bremen</strong> \u2014 Sandbox',
    )
    html = html.replace(
        'How the model works',
        'Model Playground \u2014 Sandbox',
    )

    return html


def build_model_playground_page() -> str:
    """Build a sanitized, self-contained Model Playground page.

    Returns
    -------
    A complete HTML5 document as a string with:
    - Synthetic sandbox coefficients (not production)
    - Sandbox/synthetic/technical demo branding
    - Navigation links to Start, Control Room, Model Guide, API docs
    - No production model internals, checksums, or PHI
    """
    raw_html = _SOURCE_HTML.read_text(encoding="utf-8")

    # Sanitize production content
    sanitized = _sanitize_html(raw_html)

    # Add navigation and branding
    sanitized = _add_nav_links(sanitized)
    sanitized = _add_sandbox_branding(sanitized)

    return sanitized
