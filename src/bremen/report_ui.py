"""Bremen Report page — presentation-ready report.

Owns GET /demo/report/{job_id}. Reads job data from
GET /demo/api/jobs/{job_id} and report data from
GET /demo/api/jobs/{job_id}/reports/bremen.

PR0082b — Bremen Product-Grade Demo Redesign.
"""

from __future__ import annotations

import json as _json
from typing import Any

# ---------------------------------------------------------------------------
# Design tokens (from BREMEN_DESIGN_SPEC_v1.md)
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg-page: #F7F8F8;
  --bg-surface: #FFFFFF;
  --text-primary: #16202A;
  --text-secondary: #5B6570;
  --accent: #1F6F6B;
  --border: #E3E7E6;
  --status-available: #2E7D5B;
  --status-pending: #B8894A;
  --status-unconfigured: #9AA3A8;
  --status-error: #C1483D;
  --tint-accent: #F1F5F4;
  --tint-pending: #FBF3E9;
  --tint-error: #FBEEEC;
  --radius-card: 10px;
  --radius-pill: 999px;
  --shadow-card: 0 1px 2px rgba(22,32,42,0.04), 0 1px 8px rgba(22,32,42,0.03);
  --fs-32: 32px;
  --fs-22: 22px;
  --fs-17: 17px;
  --fs-14: 14px;
  --fs-13: 13px;
  --fs-11: 11px;
  --sp-4: 4px;
  --sp-8: 8px;
  --sp-12: 12px;
  --sp-16: 16px;
  --sp-24: 24px;
  --sp-32: 32px;
  --sp-48: 48px;
  --sp-64: 64px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg-page);color:var(--text-primary);line-height:1.5;-webkit-font-smoothing:antialiased}
.report-page{max-width:1440px;margin:0 auto;padding:var(--sp-32);min-height:100vh;display:flex;flex-direction:column}
.report-header{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-24) 0;border-bottom:1px solid var(--border);margin-bottom:var(--sp-32);flex-wrap:wrap;gap:var(--sp-12)}
.report-brand{font-size:var(--fs-22);font-weight:600;color:var(--text-primary)}
.report-nav{font-size:var(--fs-14)}
.report-nav a{color:var(--accent);text-decoration:none}
.report-nav a:hover{text-decoration:underline}
.report-content{flex:1;max-width:960px;margin:0 auto;width:100%}
.report-loading{text-align:center;padding:var(--sp-64) var(--sp-24)}
.report-loading-spinner{display:inline-block;width:32px;height:32px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.8s linear infinite;margin-bottom:var(--sp-16)}
@keyframes spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.report-loading-spinner{animation:none}}
.report-loading-text{font-size:var(--fs-14);color:var(--text-secondary)}
.report-error{text-align:center;padding:var(--sp-48) var(--sp-24);background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card)}
.report-error-title{font-size:var(--fs-17);font-weight:600;color:var(--status-error);margin-bottom:var(--sp-8)}
.report-error-text{font-size:var(--fs-14);color:var(--text-secondary);margin-bottom:var(--sp-16)}
.report-card{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card);box-shadow:var(--shadow-card);padding:var(--sp-24);margin-bottom:var(--sp-16)}
.report-card-title{font-size:var(--fs-17);font-weight:600;color:var(--text-primary);margin-bottom:var(--sp-16);padding-bottom:var(--sp-12);border-bottom:1px solid var(--border)}
.recommendation-card{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card);box-shadow:var(--shadow-card);padding:var(--sp-24);margin-bottom:var(--sp-16);border-left:3px solid var(--accent)}
.recommendation-headline{font-size:var(--fs-22);font-weight:600;color:var(--text-primary);margin-bottom:var(--sp-8)}
.recommendation-code{font-size:var(--fs-13);color:var(--text-secondary);font-family:monospace;margin-bottom:var(--sp-12)}
.recommendation-score{display:flex;align-items:center;gap:var(--sp-12);margin-bottom:var(--sp-12)}
.score-bar{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden;position:relative}
.score-fill{height:100%;background:var(--accent);border-radius:4px;transition:width 500ms}
.score-label{font-size:var(--fs-13);color:var(--text-secondary);white-space:nowrap}
.score-threshold{position:absolute;top:-2px;width:2px;height:12px;background:var(--status-error)}
.tech-demo-notice{background:var(--tint-pending);border:1px solid var(--status-pending);border-radius:var(--radius-card);padding:var(--sp-12) var(--sp-16);margin-bottom:var(--sp-16);font-size:var(--fs-13);color:var(--text-primary)}
.tech-demo-notice strong{color:var(--status-pending)}
.field-table{width:100%}
.field-row{display:flex;padding:var(--sp-8) 0;border-bottom:1px solid var(--border);font-size:var(--fs-14)}
.field-row:last-child{border-bottom:none}
.field-label{width:160px;flex-shrink:0;color:var(--text-secondary);font-weight:500;padding-right:var(--sp-16)}
.field-value{flex:1;color:var(--text-primary);min-width:0;word-break:break-all}
.field-value.mono{font-family:monospace;font-size:var(--fs-11)}
.trace-toggle{background:none;border:none;color:var(--accent);font-size:var(--fs-14);font-weight:600;cursor:pointer;padding:var(--sp-8) 0;display:flex;align-items:center;gap:var(--sp-8)}
.trace-toggle:hover{text-decoration:underline}
.trace-toggle:focus{outline:3px solid var(--accent);outline-offset:2px}
.trace-content{display:none;margin-top:var(--sp-12)}
.trace-content.open{display:block}
.trace-stage{display:flex;align-items:center;gap:var(--sp-12);padding:var(--sp-8) var(--sp-12);border-left:2px solid var(--border);margin-bottom:var(--sp-4);font-size:var(--fs-13)}
.trace-stage.completed{border-left-color:var(--status-available)}
.trace-stage.failed{border-left-color:var(--status-error);background:var(--tint-error)}
.trace-stage-icon{width:16px;text-align:center;font-size:var(--fs-13)}
.trace-stage-icon.completed{color:var(--status-available)}
.trace-stage-icon.failed{color:var(--status-error)}
.trace-stage-label{flex:1;color:var(--text-primary)}
.trace-stage-dur{font-size:var(--fs-11);color:var(--text-secondary);font-family:monospace}
.report-footer{text-align:center;padding:var(--sp-24) 0;font-size:var(--fs-13);color:var(--text-secondary);border-top:1px solid var(--border);margin-top:var(--sp-48)}
@media(max-width:768px){.report-page{padding:var(--sp-12)}.report-content{max-width:100%}.field-label{width:120px}}
"""

_JS = r"""
<script>
(function(){
var baseUrl='__BASE_URL__';
var jobId='__JOB_ID__';

function init(){
  if(jobId){
    loadReport(jobId);
  }
}

function loadReport(jid){
  var content=document.getElementById('report-content');
  // Load job data
  Promise.all([
    fetch(baseUrl+'/demo/api/jobs/'+jid).then(function(r){return r.json()}),
    fetch(baseUrl+'/demo/api/jobs/'+jid+'/reports/bremen').then(function(r){return r.json()})
  ]).then(function(results){
    var job=results[0];
    var reportData=results[1];
    renderReport(job,reportData);
  }).catch(function(){
    content.innerHTML='<div class="report-error"><div class="report-error-title">Failed to load report</div><div class="report-error-text">Could not load the report data. The job may have expired or the server may be unavailable.</div><button class="btn-primary" onclick="loadReport(\''+jid+'\')">Retry</button></div>';
  });
}

function renderReport(job,reportData){
  var content=document.getElementById('report-content');
  var report=reportData.report||{};
  var wfRun=job.workflow_runs?job.workflow_runs['bremen']:null;
  var rs=wfRun?wfRun.result_summary||{}:{};
  var decisionCode=rs.decision_code||'';
  var decisionName=rs.decision_display_name||'';
  var probability=rs.probability!==undefined?rs.probability:null;
  var threshold=rs.threshold_applied!==undefined?rs.threshold_applied:null;
  var modelId=job.input_summary?job.input_summary.model_id||'':'';

  if(report.status==='job_not_found'){
    content.innerHTML='<div class="report-error"><div class="report-error-title">Job not found</div><div class="report-error-text">No job exists with ID: '+jid+'</div></div>';
    return;
  }

  var html='';

  // Technical demo notice
  html+='<div class="tech-demo-notice"><strong>Technical demo only.</strong> This report is produced by a technical product demo. It is not a clinical result. It is not clinically validated. It does not replace MRI, biopsy, a radiologist, a clinician, or clinical judgment.</div>';

  if(report.status==='available'&&decisionName){
    // Recommendation card
    html+='<div class="recommendation-card" role="alert">';
    html+='<div class="recommendation-headline">'+decisionName+'</div>';
    html+='<div class="recommendation-code">'+decisionCode+'</div>';
    if(probability!==null&&threshold!==null){
      var pct=Math.min(100,Math.max(0,probability*100));
      var threshPct=Math.min(100,Math.max(0,threshold*100));
      html+='<div class="recommendation-score">';
      html+='<div class="score-bar"><div class="score-fill" style="width:'+pct+'%"></div><div class="score-threshold" style="left:'+threshPct+'%"></div></div>';
      html+='<span class="score-label">Score: '+probability.toFixed(3)+'</span>';
      html+='</div>';
    }
    html+='</div>';
  }else if(report.status==='unavailable'){
    html+='<div class="report-card"><div class="report-card-title">Report unavailable</div><p style="font-size:var(--fs-14);color:var(--text-secondary)">The report for this job is not available. The workflow may not have completed successfully.</p></div>';
  }else if(report.status==='failed'){
    html+='<div class="report-card"><div class="report-card-title">Report generation failed</div><p style="font-size:var(--fs-14);color:var(--status-error)">An error occurred while generating the report.</p></div>';
  }

  // Model panel
  html+='<div class="report-card">';
  html+='<div class="report-card-title">Model</div>';
  html+='<div class="field-table">';
  html+='<div class="field-row"><div class="field-label">Model</div><div class="field-value mono">'+(modelId||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Version</div><div class="field-value mono">'+(rs.model_version||job.model_version||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Feature schema</div><div class="field-value mono">'+(rs.feature_schema_version||'v0.1')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Decision policy</div><div class="field-value mono">'+(rs.decision_policy_id||'bremen_mri_continuation_threshold')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Certification</div><div class="field-value">Scientific certification: pending</div></div>';
  html+='</div></div>';

  // Audit panel
  html+='<div class="report-card">';
  html+='<div class="report-card-title">Audit</div>';
  html+='<div class="field-table">';
  html+='<div class="field-row"><div class="field-label">Job ID</div><div class="field-value mono">'+(job.job_id||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Workflow</div><div class="field-value mono">bremen</div></div>';
  html+='<div class="field-row"><div class="field-label">Created</div><div class="field-value mono">'+(job.created_at?job.created_at.substring(0,19).replace('T',' '):'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Completed</div><div class="field-value mono">'+(job.completed_at?job.completed_at.substring(0,19).replace('T',' '):'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Source</div><div class="field-value mono">'+(job.input_summary?job.input_summary.container_id||job.input_summary.filename||'—':'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Duration</div><div class="field-value mono">'+(job.completed_at&&job.created_at?((new Date(job.completed_at)-new Date(job.created_at))/1000).toFixed(1)+'s':'—')+'</div></div>';
  html+='</div></div>';

  // Technical trace
  html+='<div class="report-card">';
  html+='<div class="report-card-title">Execution</div>';
  html+='<button class="trace-toggle" onclick="toggleTrace()" aria-expanded="false" id="trace-toggle-btn">View technical trace</button>';
  html+='<div class="trace-content" id="trace-content">';
  var traces=job.execution_traces||{};
  var bremenTrace=traces['bremen']||null;
  if(bremenTrace&&bremenTrace.stages){
    bremenTrace.stages.forEach(function(stage){
      var statusClass=stage.status||'not_started';
      var icon=statusClass==='completed'?'&#10003;':statusClass==='failed'?'&#10007;':statusClass==='active'?'&#9679;':'&#9679;';
      var iconClass=statusClass==='completed'?'completed':statusClass==='failed'?'failed':'';
      html+='<div class="trace-stage '+statusClass+'">';
      html+='<span class="trace-stage-icon '+iconClass+'">'+icon+'</span>';
      html+='<span class="trace-stage-label">'+(stage.label||stage.stage_id||'')+'</span>';
      if(stage.duration_ms){html+='<span class="trace-stage-dur">'+stage.duration_ms+'ms</span>';}
      html+='</div>';
    });
  }else{
    html+='<p style="font-size:var(--fs-13);color:var(--text-secondary)">No execution trace available for this job.</p>';
  }
  html+='</div></div>';

  content.innerHTML=html;
}

function toggleTrace(){
  var content=document.getElementById('trace-content');
  var btn=document.getElementById('trace-toggle-btn');
  if(!content||!btn)return;
  var isOpen=content.classList.toggle('open');
  btn.setAttribute('aria-expanded',isOpen?'true':'false');
  btn.textContent=isOpen?'Hide technical trace':'View technical trace';
}

window.loadReport=loadReport;
window.toggleTrace=toggleTrace;

init();
})();
</script>
"""


def build_report_page(
    base_url: str = "http://localhost:8000",
    job_id: str = "",
) -> str:
    """Build the Bremen Report page HTML.

    Parameters
    ----------
    base_url : Base URL of the service.
    job_id : The job ID to display the report for.

    Returns
    -------
    A complete HTML5 document as a string.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Report — MRI Triage Decision Support</title>
<style>{_CSS}</style>
</head>
<body>
<div class="report-page">
  <div class="report-header">
    <div>
      <div class="report-brand">Bremen</div>
    </div>
    <div class="report-nav">
      <a href="/demo/control-room">Back to Control Room</a>
    </div>
  </div>

  <div class="report-content" id="report-content">
    <div class="report-loading">
      <div class="report-loading-spinner"></div>
      <div class="report-loading-text">Loading report...</div>
    </div>
  </div>

  <div class="report-footer">
    <p>Bremen — MRI triage decision support. Not clinically validated.
    Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.</p>
  </div>
</div>
{_JS.replace("__BASE_URL__", base_url).replace("__JOB_ID__", job_id)}
</body>
</html>"""
