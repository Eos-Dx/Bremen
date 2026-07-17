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
.event { padding: 6px 10px; margin: 4px 0; background: #f0f4f8;
          border-radius: 4px; font-size: 13px; }
.event-fail { background: #ffebee; color: #c62828; }
.event-warn { background: #fff8e1; color: #f57f17; }
.event-success { background: #e8f5e9; color: #2e7d32; }
.event-time { color: #999; float: right; font-size: 11px; }
.hint { font-size: 12px; color: #888; margin-top: 4px; }
#upload-section { margin-top: 12px; padding-top: 12px;
                   border-top: 1px solid #eee; }
#upload-section h3 { font-size: 15px; margin-bottom: 8px; }
#container-list table { width: 100%; border-collapse: collapse; }
#container-list th { text-align: left; padding: 6px 8px; font-size: 13px;
                      color: #666; border-bottom: 1px solid #ddd; }
#container-list td { padding: 6px 8px; font-size: 14px; }
#container-list button, #upload-section button, #analyze-btn {
    padding: 6px 14px; font-size: 13px; cursor: pointer;
    border: 1px solid #ccc; border-radius: 4px; background: #1a1a2e;
    color: #fff; }
#container-list button:hover, #upload-section button:hover, #analyze-btn:hover {
    background: #2d2d44; }
input[type="file"] { font-size: 13px; margin: 8px 0; }
#events-panel { max-height: 400px; overflow-y: auto; }
"""

# ---------------------------------------------------------------------------
# Inline JavaScript
# ---------------------------------------------------------------------------

_INLINE_JS = r"""
<script>
var h5Containers = [];
var selectedContainerId = null;
var selectedContainerFilename = null;

function loadContainers() {
  fetch('/demo/api/h5/containers')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      h5Containers = data.containers || [];
      var storageStatus = data.storage || 'unknown';
      var html = '';
      if (h5Containers.length === 0) {
        html = '<p>No containers available. Upload one below.</p>';
      } else {
        html = '<table><tr><th>Filename</th><th>Size</th><th></th></tr>';
        h5Containers.forEach(function(c) {
          html += '<tr><td>' + esc(c.filename) + '</td>';
          html += '<td>' + (c.size_bytes || '?') + ' B</td>';
          html += '<td><button onclick="selectContainer(\'' +
            esc(c.id) + '\', \'' + esc(c.filename) + '\')">Select</button></td></tr>';
        });
        html += '</table>';
      }
      document.getElementById('container-list').innerHTML = html;
    })
    .catch(function() {
      document.getElementById('container-list').innerHTML =
        '<p>Could not load containers. Storage may not be configured.</p>';
    });
}

function selectContainer(id, filename) {
  selectedContainerId = id;
  selectedContainerFilename = filename;
  document.getElementById('selected-container-name').textContent = filename;
  document.getElementById('selected-container-display').style.display = 'block';
}

function uploadH5() {
  var fileInput = document.getElementById('h5-file-input');
  if (!fileInput.files || fileInput.files.length === 0) {
    alert('Please select a file to upload.');
    return;
  }
  var file = fileInput.files[0];
  if (!file.name.toLowerCase().endsWith('.h5') &&
      !file.name.toLowerCase().endsWith('.hdf5')) {
    alert('Only .h5 and .hdf5 files are accepted.');
    return;
  }
  if (file.size > __UPLOAD_MAX_BYTES__) {
    alert('File too large. Maximum size is 100 MB.');
    return;
  }

  var uploadBtn = document.getElementById('upload-btn');
  uploadBtn.disabled = true;
  uploadBtn.textContent = 'Uploading...';

  fetch('/demo/api/h5/containers', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/octet-stream',
      'X-H5-Filename': file.name
    },
    body: file
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Upload';
    if (data.status === 'uploaded') {
      addEvent('container_uploaded', 'Uploaded: ' + data.filename);
      loadContainers();
    } else {
      alert('Upload failed: ' + (data.error || data.status));
    }
  })
  .catch(function(err) {
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Upload';
    alert('Upload failed: ' + err.message);
  });
}

function analyzeH5() {
  if (!selectedContainerId) {
    alert('Please select a container first.');
    return;
  }

  document.getElementById('events-panel').innerHTML = '';
  document.getElementById('result-card').style.display = 'none';

  addEvent('request_received', 'Analyze requested');

  var analyzeBtn = document.getElementById('analyze-btn');
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = 'Analyzing...';

  fetch('/demo/api/h5/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ container_id: selectedContainerId })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = 'Analyze';

    var events = data.events || [];
    events.forEach(function(e) {
      addEvent(e.event, e.detail || '');
    });

    if (data.result) {
      document.getElementById('result-card').style.display = 'block';
      document.getElementById('result-content').innerHTML = renderResult(data);
    }
    if (data.request_id) {
      document.getElementById('request-id-display').textContent = data.request_id;
    }
  })
  .catch(function(err) {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = 'Analyze';
    addEvent('inference_failed', 'Request error: ' + err.message);
  });
}

function addEvent(eventType, detail) {
  var now = new Date().toISOString();
  var panel = document.getElementById('events-panel');
  var cssClass = 'event';
  if (eventType.indexOf('failed') > -1 || eventType.indexOf('unavailable') > -1) {
    cssClass += ' event-fail';
  } else if (eventType.indexOf('_not_') > -1) {
    cssClass += ' event-warn';
  } else if (eventType === 'completed') {
    cssClass += ' event-success';
  }
  var div = document.createElement('div');
  div.className = cssClass;
  div.innerHTML = '<strong>' + eventType + '</strong>'
    + (detail ? ' \u2014 ' + esc(detail) : '')
    + ' <span class="event-time">' + now + '</span>';
  panel.appendChild(div);
}

function renderResult(data) {
  var r = data.result || {};
  var html = '<table>';
  html += '<tr><td>Status</td><td>' + (data.status || 'N/A') + '</td></tr>';
  if (r.p_mri_needed !== undefined) {
    html += '<tr><td>p_mri_needed</td><td>' + Number(r.p_mri_needed).toFixed(3) + '</td></tr>';
  }
  if (r.triage_recommendation) {
    html += '<tr><td>Recommendation</td><td>' + esc(r.triage_recommendation) + '</td></tr>';
  }
  if (r.qc_status) {
    html += '<tr><td>QC Status</td><td>' + esc(r.qc_status) + '</td></tr>';
  }
  if (r.model_version) {
    html += '<tr><td>Model Version</td><td>' + esc(r.model_version) + '</td></tr>';
  }
  if (data.evidence && data.evidence.model_version) {
    html += '<tr><td>Model</td><td>' + esc(data.evidence.model_version) + '</td></tr>';
  }
  if (data.request_id) {
    html += '<tr><td>Request ID</td><td style="font-family:monospace;font-size:12px;">'
      + esc(data.request_id) + '</td></tr>';
  }
  if (data.job_id) {
    html += '<tr><td>Job ID</td><td style="font-family:monospace;font-size:12px;">'
      + esc(data.job_id) + '</td></tr>';
  }
  html += '</table>';
  return html;
}

function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

loadContainers();
</script>
"""

# ---------------------------------------------------------------------------
# HTML page builder
# ---------------------------------------------------------------------------


def build_demo_html_page(
    evidence: dict[str, Any] | None = None,
    base_url: str | None = None,
    request_id: str | None = None,
    upload_max_bytes: int = 100 * 1024 * 1024,
) -> str:
    """Build a self-contained HTML page for the /demo route.

    Parameters
    ----------
    evidence : Optional evidence bundle dict (from
        ``build_demo_evidence_bundle()``).  If ``None``, uses
        a default set of safe fields.
    base_url : Base URL of the service.
    request_id : Optional request ID for traceability.
    upload_max_bytes : Client-side upload size limit in bytes
        (default: 100 * 1024 * 1024, i.e. 100 MiB).  Serialized
        as a numeric literal in the generated JS.

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
<h2>&#x1F4C1; H5 Container Workspace</h2>
<div id="container-list">
  <p>Loading containers...</p>
</div>
<div id="upload-section">
  <h3>Upload H5 Container</h3>
  <input type="file" id="h5-file-input" accept=".h5,.hdf5">
  <button id="upload-btn" onclick="uploadH5()">Upload</button>
  <p class="hint">Max 100 MB. HDF5/H5 files only.</p>
</div>
<div id="selected-container-display" style="display:none; margin-top:12px; padding-top:12px; border-top:1px solid #eee;">
  <h3>Selected Container</h3>
  <p id="selected-container-name" style="font-weight:600;"></p>
  <button id="analyze-btn" onclick="analyzeH5()" style="margin-top:8px;">Analyze</button>
</div>
</div>

<div class="card">
<h2>&#x1F4CB; Events / Logs</h2>
<div id="events-panel">
  <p>No events yet.</p>
</div>
</div>

<div class="card" id="result-card" style="display:none;">
<h2>&#x1F4CA; Prediction Result</h2>
<div id="result-content"></div>
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
<h2>&#x1F4E1; Details</h2>
<table>
<tr><td>Request ID</td><td id="request-id-display" style="font-family:monospace;font-size:12px;">{request_id or 'N/A'}</td></tr>
<tr><td>Base URL</td><td>{base_url or 'N/A'}</td></tr>
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

    html += _INLINE_JS.replace(
        "__UPLOAD_MAX_BYTES__", str(upload_max_bytes),
    )

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
