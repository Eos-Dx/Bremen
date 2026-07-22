"""Analysis Workspace HTML page generator for the multi-workflow workspace.

Produces a self-contained HTML page at ``/demo/workspace`` with:
- Job list / job selection
- Job summary and normalization info
- Dynamic workflow cards
- Timeline from structured events
- Process panel with Process/Technical modes
- Report and audit tabs

PR0077 — multi-workflow analysis workspace, event stream, and reports.
"""

from __future__ import annotations

import json as _json
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAFETY_BANNER = (
    "Technical demo only — not a clinical result. "
    "Not clinically validated. Does not replace MRI, biopsy, "
    "radiologist, clinician, or clinical judgment."
)

_INLINE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
       Helvetica, Arial, sans-serif; background: #f5f7fa; color: #1a1a2e;
       line-height: 1.6; }
.banner { background: #ffd43b; color: #1a1a2e; text-align: center;
           padding: 8px; font-weight: 700; font-size: 13px; }
.layout { display: flex; height: calc(100vh - 36px); }
.left-panel { width: 240px; min-width: 200px; background: #fff;
              border-right: 1px solid #e0e0e0; overflow-y: auto; padding: 12px; }
.main { flex: 1; overflow-y: auto; padding: 16px; }
.right-panel { width: 360px; min-width: 280px; background: #fff;
               border-left: 1px solid #e0e0e0; overflow-y: auto; padding: 12px;
               display: flex; flex-direction: column; }
.right-panel.collapsed { width: 0; min-width: 0; padding: 0; overflow: hidden; }

h2 { font-size: 16px; font-weight: 700; margin-bottom: 8px; }
h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.card { background: #fff; border-radius: 8px; padding: 12px 16px;
         margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.card-title { font-size: 14px; font-weight: 700; margin-bottom: 8px;
               border-bottom: 1px solid #eee; padding-bottom: 6px; }

.badge { display: inline-block; padding: 2px 10px; border-radius: 12px;
          font-size: 11px; font-weight: 700; text-transform: uppercase; }
.badge-ready { background: #e8f5e9; color: #2e7d32; }
.badge-warn { background: #fff8e1; color: #f57f17; }
.badge-error { background: #ffebee; color: #c62828; }
.badge-info { background: #e3f2fd; color: #1565c0; }

table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 4px 8px; text-align: left; border-bottom: 1px solid #f0f0f0; }
th { color: #888; font-weight: 600; }

button { padding: 6px 14px; font-size: 12px; font-weight: 600; cursor: pointer;
          border: none; border-radius: 6px; background: #1a1a2e; color: #fff; }
button:hover { background: #2d2d44; }
button:disabled { background: #bbb; cursor: not-allowed; }
button.small { padding: 3px 8px; font-size: 11px; }

.event-row { padding: 4px 8px; margin: 2px 0; font-size: 12px;
              border-left: 3px solid #ccc; background: #f8f9fb;
              font-family: monospace; }
.event-row.completed { border-left-color: #66bb6a; background: #e8f5e9; }
.event-row.failed { border-left-color: #ef5350; background: #ffebee; }
.event-row.started { border-left-color: #42a5f5; background: #e3f2fd; }
.event-row.warn { border-left-color: #ffa726; background: #fff8e1; }

.timeline-item { padding: 6px 12px; margin: 4px 0; font-size: 13px;
                  border-left: 3px solid #42a5f5; background: #f0f4f8; }
.timeline-item.done { border-left-color: #66bb6a; background: #e8f5e9; }
.timeline-item.skipped { border-left-color: #ccc; background: #fafafa; color: #999; }

.tabs { display: flex; gap: 4px; margin-bottom: 12px; }
.tab { padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
        border: none; border-bottom: 2px solid transparent; background: none; color: #666; }
.tab.active { border-bottom-color: #1a1a2e; color: #1a1a2e; }

.process-controls { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px;
                     align-items: center; }
.process-controls select { font-size: 12px; padding: 3px 6px; }

#events-stream { flex: 1; overflow-y: auto; font-size: 12px; }

.hidden { display: none; }
.empty { color: #888; font-size: 13px; padding: 16px; text-align: center; }
.mono { font-family: monospace; font-size: 11px; }
"""

_INLINE_JS = r"""
<script>
var baseUrl = '__BASE_URL__';
var currentJobId = null;
var eventSource = null;
var autoScroll = true;
var processMode = 'process'; // process | technical

function init() {
  loadJobList();
  var jobId = '__JOB_ID__';
  if (jobId) { selectJob(jobId); }
}

function loadJobList() {
  fetch(baseUrl + '/demo/api/jobs')
    .then(r => r.json())
    .then(d => {
      var html = '<h3>Jobs</h3>';
      if (!d.jobs || d.jobs.length === 0) {
        html += '<p class="empty">No jobs yet.</p>';
      } else {
        d.jobs.forEach(function(j) {
          html += '<div style="padding:4px 0;cursor:pointer;font-size:13px;" ' +
            'onclick="selectJob(\'' + j.job_id + '\')">' +
            '<span class="badge badge-' + statusClass(j.overall_status) + '">' +
            j.overall_status + '</span> ' +
            '<span class="mono">' + j.job_id.substring(0,8) + '</span></div>';
        });
      }
      html += '<p style="font-size:11px;color:#888;margin-top:12px;">' +
        'Storage: ' + (d.storage_mode||'ephemeral') + '</p>';
      document.getElementById('job-list').innerHTML = html;
    })
    .catch(function() {
      document.getElementById('job-list').innerHTML =
        '<p class="empty">Cannot reach server.</p>';
    });
}

function statusClass(s) {
  if (s === 'completed') return 'ready';
  if (s === 'failed') return 'error';
  if (s === 'running') return 'info';
  return 'warn';
}

function selectJob(jobId) {
  currentJobId = jobId;
  if (eventSource) { eventSource.close(); }
  document.getElementById('main-content').innerHTML = '<p class="empty">Loading...</p>';
  document.getElementById('events-stream').innerHTML = '';

  fetch(baseUrl + '/demo/api/jobs/' + jobId)
    .then(r => r.json())
    .then(d => renderJob(d))
    .catch(function() {
      document.getElementById('main-content').innerHTML =
        '<p class="empty">Failed to load job.</p>';
    });

  // Connect SSE
  connectSSE(jobId);
}

function renderJob(job) {
  var html = '';
  html += '<h2>Analysis Job <span class="mono">' + job.job_id.substring(0,8) +
    '...</span></h2>';

  // Overall status
  html += '<div class="card">';
  html += '<div class="card-title">Status</div>';
  html += '<p>Overall: <span class="badge badge-' + statusClass(job.overall_status) +
    '">' + job.overall_status + '</span></p>';
  if (job.normalization_summary) {
    html += '<p>Layout: ' + (job.normalization_summary.layout || 'N/A') +
      ' | Measurements: ' + (job.normalization_summary.measurement_count || 'N/A') + '</p>';
  }
  html += '</div>';

  // Workflow cards
  if (job.workflow_runs) {
    Object.keys(job.workflow_runs).forEach(function(wid) {
      var wf = job.workflow_runs[wid];
      html += '<div class="card">';
      html += '<div class="card-title">Workflow: ' + wid + '</div>';
      html += '<p>Status: <span class="badge badge-' + statusClass(wf.status) +
        '">' + wf.status + '</span></p>';
      if (wf.result_summary && wf.result_summary.probability !== undefined) {
        html += '<p>p_mri_needed: ' + Number(wf.result_summary.probability).toFixed(3) + '</p>';
      }
      if (wf.result_summary && wf.result_summary.triage_recommendation) {
        html += '<p>Triage: ' + wf.result_summary.triage_recommendation + '</p>';
      }
      if (wf.failure) {
        html += '<p style="color:#c62828;">' + wf.failure + '</p>';
      }
      html += '</div>';
    });
  }

  // Reports
  if (job.reports) {
    html += '<div class="card">';
    html += '<div class="card-title">Reports</div>';
    Object.keys(job.reports).forEach(function(wid) {
      var r = job.reports[wid];
      html += '<p>' + wid + ': <span class="badge badge-' +
        statusClass(r.status) + '">' + r.status + '</span>';
      if (!r.scientifically_certified) {
        html += ' <span class="badge badge-warn">NOT CERTIFIED</span>';
      }
      html += '</p>';
    });
    html += '</div>';
  }

  // Audit
  html += '<div class="card">';
  html += '<div class="card-title">Audit</div>';
  html += '<table>';
  html += '<tr><td>Job ID</td><td class="mono">' + job.job_id + '</td></tr>';
  html += '<tr><td>Request ID</td><td class="mono">' + job.request_id + '</td></tr>';
  html += '<tr><td>Created</td><td>' + job.created_at + '</td></tr>';
  html += '<tr><td>Completed</td><td>' + (job.completed_at||'N/A') + '</td></tr>';
  html += '<tr><td>Status</td><td>' + job.overall_status + '</td></tr>';
  html += '</table>';
  html += '</div>';

  document.getElementById('main-content').innerHTML = html;
}

function connectSSE(jobId) {
  if (eventSource) { eventSource.close(); }
  eventSource = new EventSource(baseUrl + '/demo/api/jobs/' + jobId + '/events/stream');

  eventSource.addEventListener('job_event', function(e) {
    var event = JSON.parse(e.data);
    addProcessEvent(event);
  });

  eventSource.addEventListener('stream_complete', function(e) {
    addProcessRow('stream_complete', 'Stream complete', 'completed');
  });

  eventSource.onerror = function() {
    addProcessRow('disconnected', 'Disconnected — reconnecting...', 'warn');
  };
}

function processLabel(ev) {
  var labels = {
    'runtime.request.accepted': 'Request accepted',
    'runtime.normalization.started': 'Normalization started',
    'runtime.normalization.completed': 'Normalization completed',
    'runtime.normalization.failed': 'Normalization failed',
    'runtime.workflow.resolved': 'Workflow resolved',
    'runtime.workflow.started': 'Workflow started',
    'runtime.model.validation.started': 'Model validation started',
    'runtime.model.validation.completed': 'Model validation completed',
    'runtime.features.started': 'Features started',
    'runtime.features.completed': 'Features completed',
    'runtime.workflow.completed': 'Workflow completed',
    'runtime.workflow.failed': 'Workflow failed',
    'runtime.request.completed': 'Request completed',
  };
  return labels[ev.event_type] || ev.event_type;
}

function addProcessEvent(ev) {
  var panel = document.getElementById('events-stream');
  var cls = 'event-row';
  if (ev.status === 'completed') cls += ' completed';
  else if (ev.status === 'failed') cls += ' failed';
  else if (ev.status === 'started') cls += ' started';

  var label = processMode === 'process' ? processLabel(ev) : ev.event_type;
  var ts = ev.timestamp ? ev.timestamp.substring(11,19) : '';

  var div = document.createElement('div');
  div.className = cls;
  div.innerHTML = '<strong>' + label + '</strong> ' +
    (processMode === 'technical' ?
     '<span class="mono">' + (ev.workflow_id||'') +
     ' seq=' + ev.sequence + ' dur=' + (ev.duration_ms||'') + 'ms</span> ' : '') +
    '<span style="color:#999;float:right;">' + ts + '</span>';
  panel.appendChild(div);

  if (autoScroll) { panel.scrollTop = panel.scrollHeight; }
}

function addProcessRow(evType, label, status) {
  var panel = document.getElementById('events-stream');
  var cls = 'event-row ' + status;
  var div = document.createElement('div');
  div.className = cls;
  div.innerHTML = '<strong>' + label + '</strong>';
  panel.appendChild(div);
  if (autoScroll) { panel.scrollTop = panel.scrollHeight; }
}

function togglePanel() {
  var panel = document.getElementById('right-panel');
  panel.classList.toggle('collapsed');
  var btn = document.getElementById('toggle-panel-btn');
  btn.textContent = panel.classList.contains('collapsed') ? '\u25C0' : '\u25B6';
}

function toggleAutoScroll() {
  autoScroll = !autoScroll;
  document.getElementById('autoscroll-btn').textContent =
    autoScroll ? 'Pause' : 'Follow';
}

function switchMode(mode) {
  processMode = mode;
  document.getElementById('mode-process').className =
    'tab' + (mode === 'process' ? ' active' : '');
  document.getElementById('mode-technical').className =
    'tab' + (mode === 'technical' ? ' active' : '');
}

init();
</script>
"""


def build_workspace_page(
    base_url: str = "http://localhost:8000",
    request_id: str = "",
    job_id: str | None = None,
) -> str:
    """Build the Analysis Workspace HTML page.

    Parameters
    ----------
    base_url : Base URL of the service.
    request_id : Request ID for correlation.
    job_id : Optional pre-selected job ID from URL path.
    """
    job_id_js = _json.dumps(job_id) if job_id else "''"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Analysis Workspace</title>
<style>{_INLINE_CSS}</style>
</head>
<body>
<div class="banner">&#x26A0; {_SAFETY_BANNER}</div>
<div class="layout">
  <!-- Left panel: job list -->
  <div class="left-panel" id="job-list">
    <h3>Jobs</h3>
    <p class="empty">Loading...</p>
  </div>

  <!-- Main content -->
  <div class="main" id="main-content">
    <h2>Analysis Workspace</h2>
    <p class="empty">Select a job from the left panel or create a new analysis.</p>
    <div class="card">
      <div class="card-title">New Analysis</div>
      <p class="empty">Use the <a href="/demo">/demo</a> page to run H5 analysis,
      then return here to view the workspace.</p>
    </div>
  </div>

  <!-- Right panel: process log -->
  <div class="right-panel" id="right-panel">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h3>Process</h3>
      <div>
        <button class="small" id="autoscroll-btn" onclick="toggleAutoScroll()"
          title="Follow newest event">Pause</button>
        <button class="small" id="toggle-panel-btn" onclick="togglePanel()"
          title="Toggle panel">&#x25B6;</button>
      </div>
    </div>

    <div class="tabs">
      <button class="tab active" id="mode-process"
        onclick="switchMode('process')">Process</button>
      <button class="tab" id="mode-technical"
        onclick="switchMode('technical')">Technical</button>
    </div>

    <div id="events-stream">
      <p class="empty">No events yet. Select a job to begin.</p>
    </div>
  </div>
</div>

{_INLINE_JS.replace('__BASE_URL__', base_url).replace("'__JOB_ID__'", job_id_js)}
</body>
</html>"""
