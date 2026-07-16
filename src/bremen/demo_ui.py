"""Bremen /demo route UI page generator.

Produces a self-contained, board-friendly HTML page from an existing
Bremen demo evidence/result bundle.  Inline CSS only — no external
assets, no CDN, no network requests.

No web framework dependency.  Standard library only.

Safety
------
- No model loading or deserialization.
- No H5 reads or writes.
- No network calls from generated HTML.
- No clinical diagnosis or replacement claims.
- ``technical_demo_only`` prominent in generated output.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAFETY_DISCLAIMER = (
    "This is a technical product demo. Not a clinical result. "
    "Not clinically validated. Does not replace MRI, biopsy, "
    "radiologist, clinician, or clinical judgment."
)

# Inline CSS — self-contained, no external assets
_INLINE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
       Helvetica, Arial, sans-serif; background: #f5f7fa; color: #1a1a2e;
       line-height: 1.6; padding: 20px; }
.container { max-width: 900px; margin: 0 auto; }
.banner { background: #ffd43b; color: #1a1a2e; text-align: center;
           padding: 12px; font-weight: 700; font-size: 14px;
           border-radius: 6px; margin-bottom: 20px; }
h1 { font-size: 28px; margin-bottom: 4px; }
.subtitle { color: #555; font-size: 14px; margin-bottom: 20px; }
.card { background: #fff; border-radius: 8px; padding: 20px;
         margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.card h2 { font-size: 18px; color: #1a1a2e; margin-bottom: 12px;
            border-bottom: 1px solid #eee; padding-bottom: 8px; }
.card table { width: 100%; border-collapse: collapse; }
.card td { padding: 6px 8px; vertical-align: top; font-size: 14px; }
.card td:first-child { font-weight: 600; color: #555; width: 140px; }
.status-pass { color: #2e7d32; font-weight: 700; }
.status-fail { color: #c62828; font-weight: 700; }
.footer { text-align: center; color: #888; font-size: 12px;
           margin-top: 30px; padding: 16px; border-top: 1px solid #ddd; }
.footer .disclaimer { color: #666; font-size: 13px; margin-top: 8px; }
"""

# ---------------------------------------------------------------------------
# HTML page builder
# ---------------------------------------------------------------------------


def build_demo_html_page(
    evidence: dict[str, Any] | None = None,
    base_url: str | None = None,
    request_id: str | None = None,
) -> str:
    """Build a self-contained HTML page for the /demo route.

    Parameters
    ----------
    evidence : Optional evidence bundle dict (from
        ``build_demo_evidence_bundle()``).  If ``None``, uses
        a default set of safe fields.
    base_url : Base URL of the service.
    request_id : Optional request ID for traceability.

    Returns
    -------
    A complete HTML5 document as a string.
    """
    evidence = evidence or {}
    ev_version = evidence.get("evidence_version", "N/A")
    ev_scenario = evidence.get("scenario_id", "N/A")
    ev_safety = evidence.get("safety_notes", [])
    ev_product = evidence.get("product", "Bremen")
    ev_question = evidence.get(
        "product_question", "Should patient continue to MRI?"
    )
    ev_model_status = evidence.get("model_status", "N/A")
    ev_model_version = evidence.get("model_version", "N/A")
    ev_prediction_status = evidence.get("prediction_status", "N/A")
    checks = evidence.get("checks", {})
    warnings_list = evidence.get("warnings") or []

    # Determine pass/fail display
    health_pass = checks.get("health", "") == "pass"
    model_pass = checks.get("model_version", "") == "pass"
    pred_pass = checks.get("prediction", "") == "pass"

    rows: list[str] = []

    def _tr(label: str, value: str) -> None:
        rows.append(f"<tr><td>{label}</td><td>{value}</td></tr>")

    def _status(val: bool) -> str:
        return (
            '<span class="status-pass">PASS</span>'
            if val
            else '<span class="status-fail">FAIL</span>'
        )

    _tr("Product", ev_product)
    _tr("Question", ev_question)
    _tr("Base URL", base_url or evidence.get("base_url", "N/A"))
    _tr("Request ID", request_id or evidence.get("request_id", "N/A"))
    _tr("Evidence Version", ev_version)
    _tr("Scenario", ev_scenario)

    health_status = (
        evidence.get("base_url", "N/A") if evidence.get("base_url") else "ok"
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Product Demo</title>
<style>{_INLINE_CSS}</style>
</head>
<body>
<div class="container">

<div class="banner">&#x26A0; Technical demo only — not a clinical result.</div>

<h1>Bremen Product Demo</h1>
<p class="subtitle">Board-friendly demo view of the Bremen decision-support workflow.</p>

<div class="card">
<h2>&#x1F4CB; Overview</h2>
<table>
{"".join(rows)}
</table>
</div>

<div class="card">
<h2>&#x1F3E5; Service Health</h2>
<table>
<tr><td>Status</td><td>ok</td></tr>
<tr><td>Model Ready</td><td>{_status(health_pass)}</td></tr>
<tr><td>Health Check</td><td>{_status(health_pass)}</td></tr>
<tr><td>Model Version Check</td><td>{_status(model_pass)}</td></tr>
<tr><td>Prediction Check</td><td>{_status(pred_pass)}</td></tr>
</table>
</div>

<div class="card">
<h2>&#x1F9E0; Model / Source</h2>
<table>
<tr><td>Status</td><td>{ev_model_status}</td></tr>
<tr><td>Model Version</td><td>{ev_model_version}</td></tr>
<tr><td>Feature Schema</td><td>{evidence.get("feature_schema_version", "N/A")}</td></tr>
</table>
</div>

<div class="card">
<h2>&#x1F4CA; Evidence Bundle</h2>
<table>
<tr><td>Version</td><td>{ev_version}</td></tr>
<tr><td>Scenario</td><td>{ev_scenario}</td></tr>
<tr><td>Prediction Status</td><td>{ev_prediction_status}</td></tr>
</table>
</div>

<div class="card">
<h2>&#x1F3AF; Demo Flow</h2>
<table>
<tr><td>Synthetic Feature Artifact</td><td>15 features loaded</td></tr>
<tr><td>Bremen Service</td><td>HTTP endpoint responding</td></tr>
<tr><td>Evidence Bundle</td><td>Generated</td></tr>
<tr><td>Technical Demo Output</td><td>Produced</td></tr>
</table>
</div>
"""

    if warnings_list:
        html += """<div class="card">
<h2>&#x26A0; Warnings</h2>
<ul style="color:#c62828; margin-left:20px;">"""
        for w in warnings_list:
            html += f"<li style='font-size:14px;'>{w}</li>"
        html += "</ul></div>"

    html += f"""<div class="footer">
<p>&#x26A0; {_SAFETY_DISCLAIMER}</p>
</div>

</div>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# Evidence JSON response builder
# ---------------------------------------------------------------------------


def build_demo_evidence_json_response(
    evidence: dict[str, Any] | None = None,
) -> str:
    """Build the JSON response for the /demo/api/evidence endpoint.

    Parameters
    ----------
    evidence : Optional evidence bundle dict.  If ``None``, builds
        a minimal safe bundle with defaults.

    Returns
    -------
    A JSON string suitable for the HTTP response body.
    """
    if evidence is None:
        evidence = _build_default_evidence_bundle()

    return json.dumps(evidence, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_default_evidence_bundle() -> dict[str, Any]:
    """Build a minimal safe evidence bundle when none is provided."""
    return {
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
        "model_status": "ready",
        "prediction_status": "not_available",
        "safety_notes": [
            "Technical product demo only — not a clinical result.",
            "Not clinically validated.",
            "Does not replace MRI, biopsy, radiologist, clinician, "
            "or clinical judgment.",
            "All clinical decisions must be made by qualified clinicians.",
        ],
    }
