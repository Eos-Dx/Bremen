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

/* === PR0078: Showcase mode styles === */
.showcase-container { max-width: 1200px; margin: 0 auto; }
.showcase-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 12px; margin-bottom: 24px; }
.summary-item { background: #fff; border-radius: 8px; padding: 14px 16px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.summary-item dt { font-size: 11px; color: #888; text-transform: uppercase;
                    font-weight: 600; margin-bottom: 4px; }
.summary-item dd { font-size: 16px; font-weight: 700; color: #1a1a2e; }

.pipeline { margin-bottom: 24px; }
.pipeline ol { display: flex; list-style: none; gap: 0; padding: 0;
                flex-wrap: wrap; align-items: flex-start; }
.pipeline li { display: flex; flex-direction: column; align-items: center;
                min-width: 90px; flex: 1; position: relative; }
.pipeline li .stage-node { width: 32px; height: 32px; border-radius: 50%;
    border: 3px solid #ccc; background: #fff; display: flex; align-items: center;
    justify-content: center; font-size: 14px; margin-bottom: 6px;
    transition: border-color 300ms, background 300ms; position: relative; z-index: 1; }
.pipeline li .stage-label { font-size: 10px; text-align: center; color: #888;
    max-width: 90px; word-wrap: break-word; }
.pipeline li:not(:last-child)::after { content: ''; position: absolute;
    top: 16px; left: calc(50% + 20px); height: 3px;
    width: calc(100% - 40px); background: #e0e0e0; z-index: 0; }
.pipeline li.completed::after { background: #66bb6a; }
.pipeline li.completed .stage-node { border-color: #66bb6a; background: #e8f5e9; }
.pipeline li.active .stage-node { border-color: #42a5f5; background: #e3f2fd;
    animation: pulse-border 2s infinite; }
.pipeline li.failed .stage-node { border-color: #ef5350; background: #ffebee; }
.pipeline li.blocked .stage-node { border-color: #ffa726; background: #fff8e1; }
.pipeline li.skipped .stage-node { border-color: #bbb; background: #f5f5f5; }
.pipeline li.unavailable .stage-node { border-color: #999; background: #fafafa; }
.pipeline li.not_started .stage-node { border-color: #e0e0e0; background: #fff; }
.pipeline li button.stage-node { cursor: pointer; }
.pipeline li button.stage-node:focus { outline: 3px solid #42a5f5; outline-offset: 2px; }

@media (prefers-reduced-motion: reduce) {
  .pipeline li.active .stage-node { animation: none; }
}

@keyframes pulse-border {
  0%, 100% { border-color: #42a5f5; }
  50% { border-color: #90caf9; }
}

.wf-card { background: #fff; border-radius: 10px; padding: 16px 20px;
            margin-bottom: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.06);
            border-left: 4px solid #42a5f5; }
.wf-card.bremen { border-left-color: #1565c0; }
.wf-card.nova { border-left-color: #ffa726; }
.wf-card.aramis { border-left-color: #999; }
.wf-card-header { display: flex; justify-content: space-between; align-items: center;
                    margin-bottom: 12px; }
.wf-card-header h3 { margin: 0; font-size: 16px; }
.wf-card-body { font-size: 13px; color: #555; }
.wf-card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                 gap: 8px; }
.wf-card-field dt { font-size: 10px; color: #888; text-transform: uppercase; }
.wf-card-field dd { font-size: 13px; color: #1a1a2e; }

.drawer-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%;
                   height: 100%; background: rgba(0,0,0,0.3); z-index: 1000; }
.drawer-overlay.open { display: block; }
.drawer { position: fixed; top: 0; right: 0; width: 360px; max-width: 100vw;
           height: 100%; background: #fff; box-shadow: -2px 0 8px rgba(0,0,0,0.15);
           overflow-y: auto; padding: 24px; z-index: 1001;
           transform: translateX(100%); transition: transform 300ms; }
.drawer.open { transform: translateX(0); }
@media (prefers-reduced-motion: reduce) {
  .drawer { transition: none; }
}
.drawer h2 { font-size: 18px; margin-bottom: 16px; }
.drawer-close { position: absolute; top: 12px; right: 12px; background: none;
                 border: none; font-size: 20px; cursor: pointer; color: #888; }
.drawer-close:hover { color: #1a1a2e; }
.drawer-field { margin-bottom: 12px; }
.drawer-field dt { font-size: 11px; color: #888; text-transform: uppercase;
                    font-weight: 600; margin-bottom: 2px; }
.drawer-field dd { font-size: 14px; color: #1a1a2e; }

.decision-viz { background: #fff; border-radius: 10px; padding: 20px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.06); }
.decision-viz h3 { margin-bottom: 12px; }
.decision-bar { display: flex; height: 8px; border-radius: 4px;
                 background: #e0e0e0; margin: 12px 0; overflow: hidden; }
.decision-bar-fill { background: #1565c0; border-radius: 4px; }
.decision-threshold { position: relative; height: 20px; margin-bottom: 8px; }
.decision-threshold-marker { position: absolute; width: 2px; height: 100%;
    background: #ef5350; }

.showcase-banner { background: #1a1a2e; color: #ffd43b; text-align: center;
                   padding: 6px 12px; font-size: 12px; font-weight: 600; }

.process-link { cursor: pointer; color: #1565c0; }
.process-link:hover { text-decoration: underline; }

/* Responsive */
@media (max-width: 640px) {
  .showcase-summary { grid-template-columns: repeat(2, 1fr); }
  .pipeline ol { flex-direction: column; }
  .pipeline li { flex-direction: row; min-width: 0; }
  .pipeline li:not(:last-child)::after { display: none; }
  .wf-card-grid { grid-template-columns: 1fr; }
}
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

_SHOWCASE_JS = r"""
<script>
/* PR0078: Investor Showcase Mode */
(function() {
  var isShowcase = window.location.search.indexOf('view=showcase') !== -1;
  if (!isShowcase) return;

  var baseUrl = '__BASE_URL__';
  var currentJobId = null;
  var eventSource = null;
  var processMode = 'process';
  var selectedStage = null;
  var selectedWorkflow = null;
  var eventCache = {};
  var streamComplete = false;
  var autoScroll = true;

  function statusClass(s) {
    if (s === 'completed' || s === 'ready') return 'ready';
    if (s === 'failed' || s === 'error') return 'error';
    if (s === 'running' || s === 'active') return 'info';
    if (s === 'partial_success') return 'warn';
    return 'warn';
  }

  function stageStatusClass(s) {
    if (s === 'completed') return 'completed';
    if (s === 'failed') return 'failed';
    if (s === 'blocked') return 'blocked';
    if (s === 'skipped') return 'skipped';
    if (s === 'unavailable') return 'unavailable';
    if (s === 'active' || s === 'running') return 'active';
    return 'not_started';
  }

  function stageIcon(s) {
    if (s === 'completed') return '\u2713';
    if (s === 'failed') return '\u2717';
    if (s === 'blocked') return '\u26D4';
    if (s === 'skipped') return '\u2192';
    if (s === 'unavailable') return '\u2205';
    if (s === 'active' || s === 'running') return '\u25CF';
    return '\u25CB';
  }

  function stageAria(sid, label, status) {
    return label + ': ' + status.replace('_', ' ') + '. ' +
      (status === 'completed' ? 'Complete' :
       status === 'active' ? 'In progress' :
       status === 'failed' ? 'Failed' :
       status === 'blocked' ? 'Blocked' :
       status === 'skipped' ? 'Skipped' :
       status === 'unavailable' ? 'Unavailable' : 'Not started');
  }

  // ===== Convert page to showcase mode =====
  function initShowcase() {
    document.title = 'Bremen Investor Showcase';
    var banner = document.querySelector('.banner');
    if (banner) {
      banner.insertAdjacentHTML('afterend',
        '<div class="showcase-banner" role="status">' +
        'INVESTOR SHOWCASE MODE &mdash; Technical demo only, not scientifically certified</div>');
    }
    // Replace main content with showcase structure
    var main = document.getElementById('main-content');
    if (main) {
      main.className = 'main';
      main.innerHTML = '<div class="showcase-container" id="showcase-root">' +
        '<p class="empty">Select a job from the left panel to begin the showcase.</p>' +
        '</div>';
    }
    // Set up process panel for showcase linkage
    var rightPanel = document.getElementById('right-panel');
    if (rightPanel) {
      var controls = rightPanel.querySelector('.process-controls');
      if (!controls) {
        controls = document.createElement('div');
        controls.className = 'process-controls';
        var h3 = rightPanel.querySelector('h3');
        if (h3) h3.insertAdjacentElement('afterend', controls);
      }
    }
  }

  // ===== Override selectJob for showcase =====
  window._originalSelectJob = window.selectJob;
  window.selectJob = function(jobId) {
    currentJobId = jobId;
    selectedStage = null;
    selectedWorkflow = null;
    eventCache = {};
    streamComplete = false;
    if (eventSource) { eventSource.close(); }
    document.getElementById('events-stream').innerHTML = '';

    var root = document.getElementById('showcase-root');
    if (root) root.innerHTML = '<p class="empty">Loading job data...</p>';

    fetch(baseUrl + '/demo/api/jobs/' + jobId)
      .then(function(r) { return r.json(); })
      .then(function(d) { renderShowcase(d); })
      .catch(function() {
        if (root) root.innerHTML = '<p class="empty">Failed to load job.</p>';
      });

    connectShowcaseSSE(jobId);
  };

  // ===== SSE for showcase =====
  function connectShowcaseSSE(jobId) {
    if (eventSource) { eventSource.close(); }
    eventSource = new EventSource(baseUrl + '/demo/api/jobs/' + jobId + '/events/stream');

    eventSource.addEventListener('job_event', function(e) {
      var evt = JSON.parse(e.data);
      var wid = evt.workflow_id || 'bremen';
      if (!eventCache[wid]) eventCache[wid] = [];
      var seen = eventCache[wid].some(function(x) {
        return x.sequence === evt.sequence || x.event_id === evt.event_id;
      });
      if (!seen) {
        eventCache[wid].push(evt);
      }
      addShowcaseProcessEvent(evt);
      updateShowcaseLive(jobId);
    });

    eventSource.addEventListener('stream_complete', function() {
      streamComplete = true;
      addShowcaseProcessRow('Stream complete', 'completed');
    });

    eventSource.onerror = function() {
      addShowcaseProcessRow('Disconnected - reconnecting...', 'warn');
    };
  }

  function addShowcaseProcessEvent(evt) {
    var panel = document.getElementById('events-stream');
    if (!panel) return;
    var cls = 'event-row';
    if (evt.status === 'completed') cls += ' completed';
    else if (evt.status === 'failed') cls += ' failed';
    else if (evt.status === 'started') cls += ' started';

    var label = processMode === 'process' ?
      (showcaseProcessLabel(evt)) : evt.event_type;
    var ts = evt.timestamp ? evt.timestamp.substring(11, 19) : '';

    var div = document.createElement('div');
    div.className = cls;
    div.setAttribute('data-workflow', evt.workflow_id || '');
    div.setAttribute('data-event-type', evt.event_type || '');
    div.setAttribute('data-status', evt.status || '');
    div.innerHTML = '<strong>' + label + '</strong> ' +
      (processMode === 'technical' ?
       '<span class="mono">' + (evt.workflow_id || '') +
       ' seq=' + evt.sequence + ' dur=' + (evt.duration_ms || '') + 'ms</span> ' : '') +
      '<span style="color:#999;float:right;">' + ts + '</span>';
    panel.appendChild(div);
    if (autoScroll) { panel.scrollTop = panel.scrollHeight; }
  }

  function addShowcaseProcessRow(label, status) {
    var panel = document.getElementById('events-stream');
    if (!panel) return;
    var cls = 'event-row ' + status;
    var div = document.createElement('div');
    div.className = cls;
    div.innerHTML = '<strong>' + label + '</strong>';
    panel.appendChild(div);
    if (autoScroll) { panel.scrollTop = panel.scrollHeight; }
  }

  function showcaseProcessLabel(evt) {
    var labels = {
      'runtime.request.accepted': 'Request accepted',
      'runtime.normalization.started': 'Normalization started',
      'runtime.normalization.completed': 'Normalization completed',
      'runtime.normalization.failed': 'Normalization failed',
      'runtime.workflow.resolved': 'Workflow resolved',
      'runtime.workflow.started': 'Workflow started',
      'runtime.workflow.completed': 'Workflow completed',
      'runtime.workflow.failed': 'Workflow failed',
      'runtime.artifact.verification.completed': 'Artifact verified',
      'runtime.input.preparation.completed': 'Input prepared',
      'runtime.input.preparation.failed': 'Input prep failed',
      'runtime.features.validation.completed': 'Features validated',
      'runtime.inference.completed': 'Inference completed',
      'runtime.output.validation.completed': 'Output validated',
      'runtime.decision.completed': 'Decision completed',
      'runtime.request.completed': 'Request completed',
    };
    return labels[evt.event_type] || evt.event_type;
  }

  // ===== Render showcase =====
  function renderShowcase(job) {
    var root = document.getElementById('showcase-root');
    if (!root) return;
    var html = '';

    // Title
    html += '<h2 style="font-size:20px;margin-bottom:20px;">' +
      'Analysis Showcase <span class="mono">' + job.job_id.substring(0, 8) + '...</span></h2>';

    // Investor summary
    html += renderInvestorSummary(job);

    // Execution traces
    if (job.execution_traces) {
      Object.keys(job.execution_traces).forEach(function(wid) {
        html += renderWorkflowCard(job, wid);
      });
    } else if (job.workflow_runs) {
      Object.keys(job.workflow_runs).forEach(function(wid) {
        html += renderFallbackWorkflowCard(job, wid);
      });
    }

    root.innerHTML = html;
  }

  // ===== Investor summary =====
  function renderInvestorSummary(job) {
    var wfCount = job.requested_workflows ? job.requested_workflows.length : 0;
    var completedWf = 0;
    var modelsExecuted = 0;
    var reportsAvailable = 0;
    var certifiedCount = 0;

    if (job.workflow_runs) {
      Object.keys(job.workflow_runs).forEach(function(wid) {
        var wf = job.workflow_runs[wid];
        if (wf.status === 'completed') completedWf++;
        if (wf.status === 'completed' || wf.status === 'failed') modelsExecuted++;
      });
    }
    if (job.reports) {
      Object.keys(job.reports).forEach(function(wid) {
        var r = job.reports[wid];
        if (r.status === 'available') reportsAvailable++;
        if (r.scientifically_certified) certifiedCount++;
      });
    }

    var techReadiness = (job.overall_status === 'completed') ? 'Ready' :
      (job.overall_status === 'partial_success') ? 'Partial' : 'Not ready';
    var sciCert = (certifiedCount > 0 && certifiedCount === reportsAvailable) ? 'Certified' :
      'NOT CERTIFIED';

    return '<div class="card" style="margin-bottom:24px;">' +
      '<div class="card-title">Investor Summary</div>' +
      '<dl class="showcase-summary">' +
      '<div class="summary-item"><dt>Analysis status</dt><dd>' +
      '<span class="badge badge-' + statusClass(job.overall_status) + '">' +
      job.overall_status + '</span></dd></div>' +
      '<div class="summary-item"><dt>Input layout</dt><dd>' +
      (job.normalization_summary && job.normalization_summary.layout ?
       job.normalization_summary.layout : 'N/A') + '</dd></div>' +
      '<div class="summary-item"><dt>Measurements</dt><dd>' +
      (job.normalization_summary && job.normalization_summary.measurement_count ?
       job.normalization_summary.measurement_count : 'N/A') + '</dd></div>' +
      '<div class="summary-item"><dt>Requested workflows</dt><dd>' +
      wfCount + '</dd></div>' +
      '<div class="summary-item"><dt>Completed workflows</dt><dd>' +
      completedWf + ' / ' + wfCount + '</dd></div>' +
      '<div class="summary-item"><dt>Models executed</dt><dd>' +
      modelsExecuted + '</dd></div>' +
      '<div class="summary-item"><dt>Reports available</dt><dd>' +
      reportsAvailable + '</dd></div>' +
      '<div class="summary-item"><dt>Technical readiness</dt><dd>' +
      '<span class="badge badge-' + (techReadiness === 'Ready' ? 'ready' : 'warn') + '">' +
      techReadiness + '</span></dd></div>' +
      '<div class="summary-item"><dt>Scientific certification</dt><dd>' +
      '<span class="badge badge-' + (sciCert === 'Certified' ? 'ready' : 'error') + '">' +
      sciCert + '</span></dd></div>' +
      '</dl></div>';
  }

  // ===== Workflow card =====
  function renderWorkflowCard(job, wid) {
    var trace = job.execution_traces ? job.execution_traces[wid] : null;
    var wf = job.workflow_runs ? job.workflow_runs[wid] : null;
    var rpt = job.reports ? job.reports[wid] : null;

    var cardClass = 'wf-card ' + wid;
    var html = '<div class="' + cardClass + '">';

    // Header
    html += '<div class="wf-card-header">';
    html += '<h3>' + wid.toUpperCase() + ' Workflow</h3>';
    html += '<div>';
    if (wf) {
      html += '<span class="badge badge-' + statusClass(wf.status) + '">' +
        wf.status + '</span> ';
    }
    if (rpt && !rpt.scientifically_certified) {
      html += '<span class="badge badge-error" title="Not scientifically certified">' +
        'NOT CERTIFIED</span>';
    }
    html += '</div></div>';

    // Pipeline
    if (trace && trace.stages) {
      html += renderPipeline(wid, trace);
    }

    // Card details
    html += '<div class="wf-card-body" style="margin-top:12px;">';
    html += '<dl class="wf-card-grid">';

    if (wf && wf.result_summary && wf.result_summary.probability !== undefined &&
        wf.result_summary.triage_recommendation) {
      html += '<div class="wf-card-field"><dt>Decision</dt><dd>' +
        wf.result_summary.triage_recommendation + '</dd></div>';
      html += '<div class="wf-card-field"><dt>Score</dt><dd>' +
        Number(wf.result_summary.probability).toFixed(3) + '</dd></div>';
      if (wf.result_summary.threshold_applied !== undefined) {
        html += '<div class="wf-card-field"><dt>Threshold</dt><dd>' +
          Number(wf.result_summary.threshold_applied).toFixed(3) + '</dd></div>';
      }
    }

    html += '<div class="wf-card-field"><dt>Current stage</dt><dd>' +
      (trace ? trace.current_stage : 'N/A') + '</dd></div>';
    html += '<div class="wf-card-field"><dt>Stage progress</dt><dd>' +
      (trace ? trace.completed_stage_count + ' / ' + trace.total_applicable_stage_count : 'N/A') +
      '</dd></div>';
    html += '<div class="wf-card-field"><dt>Duration</dt><dd>' +
      (trace && trace.duration_ms ? trace.duration_ms + ' ms' : 'N/A') + '</dd></div>';

    if (rpt) {
      html += '<div class="wf-card-field"><dt>Report</dt><dd>' +
        '<span class="badge badge-' + statusClass(rpt.status) + '">' +
        rpt.status + '</span></dd></div>';
    }

    // Bremen decision visualization
    if (wid === 'bremen' && wf && wf.result_summary &&
        wf.result_summary.probability !== undefined) {
      html += '</dl>';
      html += renderBremenDecision(wf, rpt);
      html += '<dl class="wf-card-grid">';
    }

    html += '</dl></div></div>';
    return html;
  }

  function renderFallbackWorkflowCard(job, wid) {
    var wf = job.workflow_runs ? job.workflow_runs[wid] : null;
    var rpt = job.reports ? job.reports[wid] : null;

    var html = '<div class="wf-card">';
    html += '<div class="wf-card-header">';
    html += '<h3>' + wid.toUpperCase() + ' Workflow</h3>';
    html += '<div>';
    if (wf) {
      html += '<span class="badge badge-' + statusClass(wf.status) + '">' +
        wf.status + '</span>';
    }
    html += '</div></div>';
    html += '<div class="wf-card-body">';

    if (wf && wf.failure) {
      html += '<p style="color:#c62828;">' + wf.failure + '</p>';
    }
    if (wf && wf.status === 'failed') {
      var label = (wf.failure && wf.failure.indexOf('unavailable') !== -1) ?
        'Workflow unavailable' : 'Execution failed';
      html += '<p><span class="badge badge-error">' + label + '</span></p>';
      html += '<p style="font-size:12px;color:#888;">Model lifecycle not started. Report unavailable.</p>';
    } else if (wf && wf.status === 'completed') {
      if (wf.result_summary && wf.result_summary.probability !== undefined) {
        html += '<p>p_mri_needed: ' + Number(wf.result_summary.probability).toFixed(3) + '</p>';
      }
      if (wf.result_summary && wf.result_summary.triage_recommendation) {
        html += '<p>Triage: ' + wf.result_summary.triage_recommendation + '</p>';
      }
    } else {
      html += '<p class="empty">No execution trace available.</p>';
    }
    html += '</div></div>';
    return html;
  }

  // ===== Visual pipeline =====
  function renderPipeline(wid, trace) {
    var html = '<div class="pipeline" role="region" aria-label="' + wid +
      ' execution pipeline">';
    html += '<ol aria-label="Execution stages for ' + wid + '">';

    trace.stages.forEach(function(stage, idx) {
      var cls = stageStatusClass(stage.status);
      var icon = stageIcon(stage.status);
      var ariaLabel = stageAria(stage.stage_id, stage.label, stage.status);
      var isInteractive = (stage.status === 'completed' || stage.status === 'failed' ||
                           stage.status === 'blocked');

      html += '<li class="' + cls + '" data-stage="' + stage.stage_id +
        '" data-workflow="' + wid + '">';
      if (isInteractive) {
        html += '<button class="stage-node" aria-label="' + ariaLabel +
          '" title="' + stage.label + ': ' + stage.status +
          (stage.duration_ms ? ' (' + stage.duration_ms + ' ms)' : '') +
          '" onclick="window._showcaseOpenDrawer(\'' + wid + '\', \'' +
          stage.stage_id + '\')">' + icon + '</button>';
      } else {
        html += '<span class="stage-node" aria-label="' + ariaLabel +
          '" title="' + stage.label + ': ' + stage.status + '">' + icon + '</span>';
      }
      html += '<span class="stage-label">' + stage.label + '</span>';
      if (stage.duration_ms) {
        html += '<span class="stage-label" style="font-size:9px;color:#aaa;">' +
          stage.duration_ms + ' ms</span>';
      }
      html += '</li>';
    });

    html += '</ol></div>';
    return html;
  }

  // ===== Bremen decision visualization =====
  function renderBremenDecision(wf, rpt) {
    var prob = wf.result_summary.probability;
    var threshold = wf.result_summary.threshold_applied || 0.5;
    var triage = wf.result_summary.triage_recommendation;
    var certified = rpt ? rpt.scientifically_certified : false;
    var barPct = Math.min(100, Math.max(0, prob * 100));
    var threshPct = Math.min(100, Math.max(0, threshold * 100));

    return '<div class="decision-viz" style="margin:12px 0;">' +
      '<h3>MRI Continuation Assessment</h3>' +
      '<p style="font-size:13px;">' +
      '<strong>Score:</strong> ' + Number(prob).toFixed(3) +
      ' &nbsp;|&nbsp; <strong>Threshold:</strong> ' + Number(threshold).toFixed(3) + '</p>' +
      '<div class="decision-bar">' +
      '<div class="decision-bar-fill" style="width:' + barPct + '%;"></div>' +
      '</div>' +
      '<div class="decision-threshold">' +
      '<div class="decision-threshold-marker" style="left:' + threshPct + '%;"></div>' +
      '</div>' +
      '<p><strong>Decision:</strong> <span class="badge badge-' +
      (triage === 'MRI_RECOMMENDED' ? 'warn' : 'ready') + '">' +
      triage + '</span></p>' +
      '<p style="font-size:12px;color:#888;margin-top:8px;">' +
      '<strong>Scientifically certified:</strong> ' +
      '<span class="badge badge-' + (certified ? 'ready' : 'error') + '">' +
      (certified ? 'Yes' : 'No') + '</span>' +
      ' &mdash; Technical demo only. No clinical diagnosis.</p>' +
      '</div>';
  }

  // ===== Stage detail drawer =====
  window._showcaseOpenDrawer = function(wid, stageId) {
    selectedWorkflow = wid;
    selectedStage = stageId;

    var wfEvents = eventCache[wid] || [];
    var stageEvents = wfEvents.filter(function(e) {
      return stageFromEventType(e.event_type) === stageId;
    });

    var overlay = document.getElementById('showcase-drawer-overlay');
    var drawer = document.getElementById('showcase-drawer');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'showcase-drawer-overlay';
      overlay.className = 'drawer-overlay';
      overlay.onclick = closeDrawer;
      document.body.appendChild(overlay);
    }
    if (!drawer) {
      drawer = document.createElement('div');
      drawer.id = 'showcase-drawer';
      drawer.className = 'drawer';
      drawer.setAttribute('role', 'dialog');
      drawer.setAttribute('aria-label', 'Stage details');
      document.body.appendChild(drawer);
    }

    var latest = stageEvents.length > 0 ? stageEvents[stageEvents.length - 1] : null;
    var trace = getStageTrace(wid, stageId);

    var html = '<button class="drawer-close" onclick="window._showcaseCloseDrawer()"' +
      ' aria-label="Close stage details">&times;</button>';
    html += '<h2 id="drawer-title">Stage: ' + (trace ? trace.label : stageId) + '</h2>';

    if (trace) {
      html += '<dl>';
      html += '<div class="drawer-field"><dt>Status</dt><dd>' +
        '<span class="badge badge-' + statusClass(trace.status) + '">' +
        trace.status + '</span></dd></div>';
      if (trace.duration_ms) {
        html += '<div class="drawer-field"><dt>Duration</dt><dd>' +
          trace.duration_ms + ' ms</dd></div>';
      }
      html += '</dl>';

      // Safe stage-specific details
      html += renderStageDetails(stageId, latest, trace);

      // Show only safe fields from event details
      if (latest && latest.details) {
        html += '<h3 style="margin-top:16px;font-size:14px;">Safe Metadata</h3><dl>';
        var safeKeys = getSafeKeysForStage(stageId);
        Object.keys(latest.details).forEach(function(k) {
          if (safeKeys.indexOf(k) !== -1) {
            var val = latest.details[k];
            html += '<div class="drawer-field"><dt>' + k + '</dt><dd>' +
              (typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val)) +
              '</dd></div>';
          }
        });
        html += '</dl>';
      }
    } else {
      html += '<p class="empty">No trace data available for this stage.</p>';
    }

    drawer.innerHTML = html;
    overlay.classList.add('open');
    drawer.classList.add('open');

    // Focus the close button
    var closeBtn = drawer.querySelector('.drawer-close');
    if (closeBtn) closeBtn.focus();

    // Highlight process panel events
    highlightProcessEvents(wid, stageId);
  };

  window._showcaseCloseDrawer = closeDrawer;

  function closeDrawer() {
    var overlay = document.getElementById('showcase-drawer-overlay');
    var drawer = document.getElementById('showcase-drawer');
    if (overlay) overlay.classList.remove('open');
    if (drawer) drawer.classList.remove('open');

    // Return focus to the selected stage button
    if (selectedWorkflow && selectedStage) {
      var stageBtn = document.querySelector(
        'li[data-workflow="' + selectedWorkflow + '"][data-stage="' +
        selectedStage + '"] button.stage-node');
      if (stageBtn) stageBtn.focus();
    }
  }

  function renderStageDetails(stageId, latest, trace) {
    var html = '';
    var details = latest ? latest.details || {} : {};

    if (stageId === 'features_validated' || stageId.indexOf('feature') !== -1) {
      html += '<h3 style="margin-top:16px;font-size:14px;">Feature Contract</h3><dl>';
      html += featureField(details, 'feature_schema_version', 'Schema version');
      html += featureField(details, 'expected_count', 'Expected features');
      html += featureField(details, 'produced_count', 'Produced features');
      html += featureField(details, 'missing_count', 'Missing features');
      html += featureField(details, 'non_finite_count', 'Non-finite features');
      html += featureField(details, 'feature_order_valid', 'Order valid');
      html += '</dl>';
    }

    if (stageId.indexOf('artifact') !== -1 || stageId.indexOf('model') !== -1) {
      html += '<h3 style="margin-top:16px;font-size:14px;">Artifact Identity</h3><dl>';
      html += featureField(details, 'model_id', 'Model ID');
      html += featureField(details, 'model_version', 'Model version');
      html += featureField(details, 'model_schema_version', 'Schema version');
      html += featureField(details, 'checksum_status', 'Checksum');
      html += featureField(details, 'adaptation_applied', 'Adaptation applied');
      html += featureField(details, 'validation_status', 'Validation');
      html += '</dl>';
    }

    if (stageId.indexOf('inference') !== -1) {
      html += '<h3 style="margin-top:16px;font-size:14px;">Inference Contract</h3><dl>';
      html += featureField(details, 'model_id', 'Model ID');
      html += featureField(details, 'model_version', 'Model version');
      html += featureField(details, 'output_schema', 'Output schema');
      html += featureField(details, 'output_names', 'Output names');
      html += featureField(details, 'output_count', 'Output count');
      html += '</dl>';
    }

    if (stageId.indexOf('output') !== -1 && stageId.indexOf('validation') !== -1) {
      html += '<h3 style="margin-top:16px;font-size:14px;">Output Validation</h3><dl>';
      html += featureField(details, 'schema_valid', 'Schema valid');
      html += featureField(details, 'output_count', 'Output count');
      html += featureField(details, 'all_finite', 'All finite');
      html += '</dl>';
    }

    if (stageId.indexOf('decision') !== -1) {
      html += '<h3 style="margin-top:16px;font-size:14px;">Decision Policy</h3><dl>';
      html += featureField(details, 'decision_policy_id', 'Policy ID');
      html += featureField(details, 'decision_code', 'Decision code');
      html += featureField(details, 'scientifically_certified', 'Scientifically certified');
      html += '</dl>';
    }

    if (stageId.indexOf('input') !== -1 && stageId.indexOf('prepar') !== -1) {
      html += '<h3 style="margin-top:16px;font-size:14px;">Input Preparation</h3><dl>';
      html += featureField(details, 'layout', 'Layout');
      html += featureField(details, 'measurement_count', 'Measurements');
      html += featureField(details, 'side_count', 'Sides');
      html += featureField(details, 'position_count', 'Positions');
      html += featureField(details, 'compatible', 'Compatible');
      html += '</dl>';
    }

    return html;
  }

  function featureField(details, key, label) {
    if (details[key] === undefined) return '';
    var val = details[key];
    var display = typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val);
    return '<div class="drawer-field"><dt>' + label + '</dt><dd>' + display + '</dd></div>';
  }

  function getSafeKeysForStage(stageId) {
    var common = ['duration_ms', 'reason'];
    if (stageId.indexOf('artifact') !== -1 || stageId.indexOf('model') !== -1) {
      return common.concat(['model_id', 'model_version', 'model_schema_version',
        'checksum_status', 'adaptation_applied', 'validation_status']);
    }
    if (stageId.indexOf('feature') !== -1) {
      return common.concat(['feature_schema_version', 'expected_count', 'produced_count',
        'missing_count', 'non_finite_count', 'feature_order_valid', 'schema_matched']);
    }
    if (stageId.indexOf('inference') !== -1) {
      return common.concat(['model_id', 'model_version', 'output_schema',
        'output_names', 'output_count']);
    }
    if (stageId.indexOf('output') !== -1) {
      return common.concat(['schema_valid', 'output_count', 'all_finite']);
    }
    if (stageId.indexOf('decision') !== -1) {
      return common.concat(['decision_policy_id', 'decision_code', 'scientifically_certified']);
    }
    if (stageId.indexOf('input') !== -1) {
      return common.concat(['layout', 'measurement_count', 'side_count',
        'position_count', 'compatible']);
    }
    return common;
  }

  function stageFromEventType(evtType) {
    var map = {
      'runtime.artifact.verification.completed': 'artifact_verification',
      'runtime.artifact.load.completed': 'artifact_loaded',
      'runtime.artifact.adaptation.completed': 'artifact_adapted',
      'runtime.model.validation.completed': 'model_validated',
      'runtime.input.preparation.completed': 'input_prepared',
      'runtime.input.preparation.failed': 'input_prepared',
      'runtime.features.validation.completed': 'features_validated',
      'runtime.inference.completed': 'inference_completed',
      'runtime.output.validation.completed': 'output_validated',
      'runtime.decision.completed': 'decision_completed',
      'runtime.report.completed': 'report_completed',
    };
    return map[evtType] || '';
  }

  function getStageTrace(wid, stageId) {
    // Try to get stage info from re-fetch
    return null;  // The drawer builds from event data instead
  }

  // ===== Process panel linkage =====
  function highlightProcessEvents(wid, stageId) {
    var panel = document.getElementById('events-stream');
    if (!panel) return;
    var rows = panel.querySelectorAll('.event-row');
    rows.forEach(function(row) {
      row.style.background = '';
    });
    // Highlight rows matching this workflow and stage
    var stageEvtType = '';
    Object.keys({
      'runtime.artifact.verification.completed': 'artifact_verification',
      'runtime.artifact.load.completed': 'artifact_loaded',
      'runtime.artifact.adaptation.completed': 'artifact_adapted',
      'runtime.model.validation.completed': 'model_validated',
      'runtime.input.preparation.completed': 'input_prepared',
      'runtime.input.preparation.failed': 'input_prepared',
      'runtime.features.validation.completed': 'features_validated',
      'runtime.inference.completed': 'inference_completed',
      'runtime.output.validation.completed': 'output_validated',
      'runtime.decision.completed': 'decision_completed',
      'runtime.report.completed': 'report_completed',
    }).forEach(function(evtType, sid) {
      if (sid === stageId) stageEvtType = evtType;
    });
    rows.forEach(function(row) {
      var rowWf = row.getAttribute('data-workflow') || '';
      var rowEvt = row.getAttribute('data-event-type') || '';
      if (rowWf === wid && rowEvt === stageEvtType) {
        row.style.background = '#fff9c4';
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  }

  // ===== Live update =====
  function updateShowcaseLive(jobId) {
    fetch(baseUrl + '/demo/api/jobs/' + jobId)
      .then(function(r) { return r.json(); })
      .then(function(d) { renderShowcase(d); })
      .catch(function() {});
  }

  // ===== Keyboard handling =====
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      var overlay = document.getElementById('showcase-drawer-overlay');
      if (overlay && overlay.classList.contains('open')) {
        closeDrawer();
      }
    }
  });

  // ===== Live region for stage updates =====
  var liveRegion = document.createElement('div');
  liveRegion.setAttribute('aria-live', 'polite');
  liveRegion.setAttribute('aria-atomic', 'true');
  liveRegion.className = 'hidden';
  liveRegion.id = 'showcase-live-region';
  document.body.appendChild(liveRegion);

  // ===== Override process panel toggle/autoscroll for showcase =====
  window.togglePanel = function() {
    var panel = document.getElementById('right-panel');
    if (panel) panel.classList.toggle('collapsed');
    var btn = document.getElementById('toggle-panel-btn');
    if (btn) btn.textContent = panel && panel.classList.contains('collapsed') ? '\u25C0' : '\u25B6';
  };

  window.toggleAutoScroll = function() {
    autoScroll = !autoScroll;
    var btn = document.getElementById('autoscroll-btn');
    if (btn) btn.textContent = autoScroll ? 'Pause' : 'Follow';
  };

  window.switchMode = function(mode) {
    processMode = mode;
    var mp = document.getElementById('mode-process');
    var mt = document.getElementById('mode-technical');
    if (mp) mp.className = 'tab' + (mode === 'process' ? ' active' : '');
    if (mt) mt.className = 'tab' + (mode === 'technical' ? ' active' : '');
  };

  // Start showcase mode
  initShowcase();
})();
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
{_SHOWCASE_JS.replace('__BASE_URL__', base_url)}
</body>
</html>"""
