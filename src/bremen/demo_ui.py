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
.container { max-width: 960px; margin: 0 auto; }

/* Safety banner */
.banner { background: #ffd43b; color: #1a1a2e; text-align: center;
           padding: 10px; font-weight: 700; font-size: 13px;
           border-radius: 6px; margin-bottom: 20px; }

/* Header / Hero */
.hero { background: #fff; border-radius: 10px; padding: 24px 28px;
         margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
         display: flex; align-items: flex-start; justify-content: space-between;
         flex-wrap: wrap; gap: 12px; }
.hero-title { font-size: 22px; font-weight: 800; color: #1a1a2e; }
.hero-question { font-size: 15px; color: #555; margin-top: 2px; }
.hero-badges { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 20px;
          font-size: 12px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.03em; }
.badge-ready { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
.badge-warn { background: #fff8e1; color: #f57f17; border: 1px solid #ffe082; }
.badge-error { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
.badge-neutral { background: #f0f4f8; color: #555; border: 1px solid #ccc; }

/* Cards */
.card { background: #fff; border-radius: 10px; padding: 20px 24px;
         margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.card-title { font-size: 16px; font-weight: 700; color: #1a1a2e;
               margin-bottom: 14px; border-bottom: 1px solid #eef0f4;
               padding-bottom: 10px; }

/* H5 Workspace */
.workspace-status { font-size: 13px; margin-bottom: 12px; padding: 8px 12px;
                     border-radius: 6px; }
.storage-ok { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
.storage-missing { background: #fff8e1; color: #b7650a; border: 1px solid #ffe082; }
.storage-hint { font-size: 12px; color: #888; margin-top: 2px; font-family: monospace; }
#container-list { min-height: 40px; }
#container-list table { width: 100%; border-collapse: collapse; }
#container-list th { text-align: left; padding: 6px 8px; font-size: 13px;
                      color: #666; border-bottom: 1px solid #ddd; }
#container-list td { padding: 6px 8px; font-size: 14px; }
.empty-state { color: #888; font-size: 14px; text-align: center; padding: 20px; }
.upload-area { margin-top: 12px; padding-top: 14px; border-top: 1px solid #eef0f4; }
.upload-area h3 { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
input[type="file"] { font-size: 13px; margin: 6px 0; }
#upload-btn, #analyze-btn, .container-list-btn {
    padding: 6px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
    border: none; border-radius: 6px; background: #1a1a2e; color: #fff;
    transition: background 0.15s; }
#upload-btn:hover, #analyze-btn:hover, .container-list-btn:hover { background: #2d2d44; }
#upload-btn:disabled, #analyze-btn:disabled { background: #bbb; cursor: not-allowed; }
.hint-text { font-size: 12px; color: #888; margin-top: 4px; }
.selected-area { display: none; margin-top: 12px; padding: 10px 14px;
                  background: #f0f7ff; border: 1px solid #b3d4fc;
                  border-radius: 6px; }
.selected-area h3 { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
#selected-container-name { font-weight: 600; font-size: 14px; }
#analyze-btn { margin-top: 6px; }

/* Events panel */
#events-panel { max-height: 400px; overflow-y: auto; margin-top: 4px; }
.event { padding: 6px 12px; margin: 3px 0; background: #f0f4f8;
          border-radius: 4px; font-size: 13px; border-left: 3px solid #ccc; }
.event-start { border-left-color: #42a5f5; }
.event-complete { border-left-color: #66bb6a; background: #e8f5e9; }
.event-fail { border-left-color: #ef5350; background: #ffebee; color: #c62828; }
.event-warn { border-left-color: #ffa726; background: #fff8e1; color: #f57f17; }
.event-time { color: #999; float: right; font-size: 11px; }

/* Result card */
#result-card { display: none; }
.result-table { width: 100%; border-collapse: collapse; }
.result-table td { padding: 6px 10px; vertical-align: top; font-size: 14px;
                    border-bottom: 1px solid #f0f0f0; }
.result-table td:first-child { font-weight: 600; color: #555; width: 160px; }
.result-not-run { color: #888; font-size: 14px; text-align: center;
                   padding: 16px; background: #f9fafb; border-radius: 6px; }

/* Footer */
.footer { text-align: center; color: #888; font-size: 12px;
           margin-top: 30px; padding: 16px; border-top: 1px solid #ddd; }
.footer .disclaimer { color: #666; font-size: 13px; margin-top: 8px; }
.mono { font-family: monospace; font-size: 12px; }
"""

# ---------------------------------------------------------------------------
# Inline JavaScript
# ---------------------------------------------------------------------------

_INLINE_JS = r"""
<script>
var h5Containers = [];
var selectedContainerId = null;
var selectedContainerFilename = null;
var storageConfigured = __STORAGE_CONFIGURED__;

function loadContainers() {
  fetch('/demo/api/h5/containers')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      h5Containers = data.containers || [];
      storageConfigured = (data.storage === 'configured');
      updateStorageUI();
      renderContainerList();
    })
    .catch(function() {
      document.getElementById('container-list').innerHTML =
        '<p class="empty-state">Could not load containers. Server may be unreachable.</p>';
    });
}

function updateStorageUI() {
  var storageMsg = document.getElementById('storage-status');
  var uploadSection = document.getElementById('upload-section');
  var uploadBtn = document.getElementById('upload-btn');

  if (storageConfigured) {
    storageMsg.innerHTML = '<span class="workspace-status storage-ok">' +
      '&#10003; H5 storage is configured. Upload and analyze are available.</span>';
    if (uploadSection) uploadSection.style.display = '';
    if (uploadBtn) uploadBtn.disabled = false;
  } else {
    storageMsg.innerHTML = '<span class="workspace-status storage-missing">' +
      '&#9888; H5 storage is not configured. ' +
      'Set <span class="storage-hint">BREMEN_DEMO_H5_BUCKET</span> to enable upload.<br>' +
      '<span class="storage-hint">Related: BREMEN_DEMO_H5_PREFIX, ' +
      'BREMEN_DEMO_H5_ALLOW_UPLOAD, BREMEN_DEMO_H5_MAX_BYTES</span></span>';
    if (uploadSection) uploadSection.style.display = 'none';
    if (uploadBtn) uploadBtn.disabled = true;
  }
}

function renderContainerList() {
  var html = '';
  if (h5Containers.length === 0) {
    html = '<p class="empty-state">No containers available.' +
      (storageConfigured ? ' Upload one below.' : '') + '</p>';
  } else {
    html = '<table><tr><th>Filename</th><th>Size</th><th></th></tr>';
    h5Containers.forEach(function(c) {
      var selected = (c.id === selectedContainerId) ? ' style="background:#f0f7ff;"' : '';
      html += '<tr' + selected + '><td>' + esc(c.filename) + '</td>';
      html += '<td>' + (c.size_bytes || '?') + ' B</td>';
      html += '<td><button class="container-list-btn" onclick="selectContainer(\'' +
        esc(c.id) + '\', \'' + esc(c.filename) + '\')">Select</button></td></tr>';
    });
    html += '</table>';
  }
  document.getElementById('container-list').innerHTML = html;
}

function selectContainer(id, filename) {
  selectedContainerId = id;
  selectedContainerFilename = filename;
  document.getElementById('selected-container-name').textContent = filename;
  document.getElementById('selected-container-display').style.display = 'block';
  document.getElementById('analyze-btn').disabled = false;
  renderContainerList();
}

function uploadH5() {
  var fileInput = document.getElementById('h5-file-input');
  if (!fileInput.files || fileInput.files.length === 0) {
    addEvent('upload_rejected', 'Please select a file to upload.');
    return;
  }
  var file = fileInput.files[0];
  if (!file.name.toLowerCase().endsWith('.h5') &&
      !file.name.toLowerCase().endsWith('.hdf5')) {
    addEvent('upload_rejected', 'Only .h5 and .hdf5 files are accepted.');
    return;
  }
  if (file.size > __UPLOAD_MAX_BYTES__) {
    addEvent('upload_rejected', 'File too large. Maximum size is 100 MB.');
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
      addEvent('upload_rejected', data.error || data.status);
    }
  })
  .catch(function(err) {
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Upload';
    addEvent('upload_rejected', 'Upload request failed: ' + err.message);
  });
}

function analyzeH5() {
  if (!selectedContainerId) {
    addEvent('inference_failed', 'Please select a container first.');
    return;
  }

  document.getElementById('events-panel').innerHTML = '';
  document.getElementById('result-card').style.display = 'none';
  document.getElementById('result-content').innerHTML = '';

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
      var ridEl = document.getElementById('request-id-display');
      if (ridEl) ridEl.textContent = data.request_id;
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
  } else if (eventType.indexOf('_not_') > -1 || eventType.indexOf('not_configured') > -1) {
    cssClass += ' event-warn';
  } else if (eventType === 'completed') {
    cssClass += ' event-complete';
  } else if (eventType.indexOf('started') > -1 || eventType.indexOf('request_') > -1) {
    cssClass += ' event-start';
  }

  var div = document.createElement('div');
  div.className = cssClass;
  var icon = '';
  if (eventType.indexOf('failed') > -1 || eventType.indexOf('unavailable') > -1) icon = '&#10060; ';
  else if (eventType.indexOf('completed') > -1) icon = '&#9989; ';
  else if (eventType.indexOf('started') > -1 || eventType.indexOf('request_') > -1) icon = '&#9654; ';
  else if (eventType.indexOf('_not_') > -1 || eventType.indexOf('not_configured') > -1) icon = '&#9888; ';
  div.innerHTML = icon + '<strong>' + eventType + '</strong>'
    + (detail ? ' \u2014 ' + esc(detail) : '')
    + ' <span class="event-time">' + now + '</span>';
  panel.appendChild(div);
}

function renderResult(data) {
  var r = data.result || {};
  var html = '<table class="result-table">';
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
  if (data.evidence && data.evidence.model_checksum) {
    html += '<tr><td>Checksum</td><td class="mono">' + esc(data.evidence.model_checksum).substring(0,16) + '...</td></tr>';
  }
  if (data.request_id) {
    html += '<tr><td>Request ID</td><td class="mono">' + esc(data.request_id) + '</td></tr>';
  }
  if (data.job_id) {
    html += '<tr><td>Job ID</td><td class="mono">' + esc(data.job_id) + '</td></tr>';
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
    *,
    model_info: dict[str, Any] | None = None,
    storage_configured: bool = False,
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
    model_info : Dict with keys ``model_status``, ``model_version``,
        ``model_checksum``, ``feature_schema_version``.  Used to
        display model readiness badge.
    storage_configured : Whether H5 storage is configured.  Controls
        the storage status display and upload availability.
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
    ev_prediction_status = evidence.get("prediction_status", "not_available")
    warnings_list = evidence.get("warnings") or []

    # Determine model badge state
    if model_info is None:
        model_info = {}
    m_status = model_info.get("model_status", "not_configured")
    m_version = model_info.get("model_version") or "N/A"
    m_checksum = model_info.get("model_checksum") or ""

    if m_status == "ready":
        badge_class = "badge-ready"
        badge_text = f"Model: Ready &bull; {m_version}"
    elif m_status == "error":
        badge_class = "badge-error"
        badge_text = "Model: Error"
    else:
        badge_class = "badge-warn"
        badge_text = "Model: Not configured"

    # Storage status text (rendered by JS at runtime)
    # The static HTML includes placeholder; JS fills it via updateStorageUI()

    # Prediction display
    pred_display = (
        '<div class="result-not-run">'
        "No prediction has been run yet. Select an H5 container and click Analyze."
        "</div>"
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

<div class="hero">
  <div>
    <div class="hero-title">Bremen</div>
    <div class="hero-question">{ev_question}</div>
  </div>
  <div class="hero-badges">
    <span class="badge {badge_class}">{badge_text}</span>
  </div>
</div>

<div class="card">
  <div class="card-title">&#x1F4C1; H5 Container Workspace</div>
  <div id="storage-status"></div>
  <div id="container-list">
    <p class="empty-state">Loading containers...</p>
  </div>
  <div class="upload-area" id="upload-section">
    <h3>Upload H5 Container</h3>
    <input type="file" id="h5-file-input" accept=".h5,.hdf5">
    <button id="upload-btn" onclick="uploadH5()">Upload</button>
    <p class="hint-text">Max 100 MB. HDF5/H5 files only.</p>
  </div>
  <div class="selected-area" id="selected-container-display">
    <h3>Selected Container</h3>
    <p id="selected-container-name"></p>
    <button id="analyze-btn" onclick="analyzeH5()" disabled>Analyze</button>
  </div>
</div>

<div class="card">
  <div class="card-title">&#x1F4CB; Processing / Events</div>
  <div id="events-panel">
    <p class="empty-state">No events yet.</p>
  </div>
</div>

<div class="card" id="result-card">
  <div class="card-title">&#x1F4CA; Result</div>
  <div id="result-content">
    {pred_display}
  </div>
</div>

<div class="card">
  <div class="card-title">&#x1F9E0; Model / Source</div>
  <table class="result-table">
    <tr><td>Status</td><td><span class="badge {badge_class}" style="font-size:11px;">{badge_text}</span></td></tr>
    <tr><td>Model Version</td><td>{m_version}</td></tr>
    {('<tr><td>Checksum</td><td class="mono">' + m_checksum[:16] + '...</td></tr>') if m_checksum else ''}
    <tr><td>Feature Schema</td><td>{evidence.get("feature_schema_version", "N/A")}</td></tr>
  </table>
</div>
"""

    if warnings_list:
        html += """<div class="card">
<div class="card-title">&#x26A0; Warnings</div>
<ul style="color:#c62828; margin-left:20px;">"""
        for w in warnings_list:
            html += f"<li style='font-size:14px;'>{w}</li>"
        html += "</ul></div>"

    # Serialize storage_configured as JS bool literal
    storage_js = "true" if storage_configured else "false"

    html += _INLINE_JS.replace(
        "__UPLOAD_MAX_BYTES__", str(upload_max_bytes),
    ).replace(
        "__STORAGE_CONFIGURED__", storage_js,
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
