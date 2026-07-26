"""Bremen Report page — presentation-ready report with External/Internal tabs.

Owns GET /demo/report/{job_id}. Reads job data from
GET /demo/api/jobs/{job_id} and report data from
GET /demo/api/jobs/{job_id}/reports/bremen.

PR0082b — Bremen Product-Grade Demo Redesign.
PR0093 — Presentation-grade report renderer with Print/Save PDF.
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

/* Header */
.report-header{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-24) 0;border-bottom:1px solid var(--border);margin-bottom:var(--sp-24);flex-wrap:wrap;gap:var(--sp-12)}
.report-brand{font-size:var(--fs-22);font-weight:600;color:var(--text-primary)}
.report-subtitle{font-size:var(--fs-13);color:var(--text-secondary);margin-top:var(--sp-4)}
.report-nav{font-size:var(--fs-14)}
.report-nav a{color:var(--accent);text-decoration:none}
.report-nav a:hover{text-decoration:underline}

/* Tabs */
.report-tabs{display:flex;align-items:center;gap:var(--sp-4);border-bottom:2px solid var(--border);margin-bottom:var(--sp-24);padding-bottom:0;position:relative}
.tab-btn{background:none;border:none;color:var(--text-secondary);font-size:var(--fs-14);font-weight:500;padding:var(--sp-12) var(--sp-24);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:color 0.15s,border-color 0.15s}
.tab-btn:hover{color:var(--text-primary)}
.tab-btn[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
.tab-btn:focus-visible{outline:3px solid var(--accent);outline-offset:-3px;border-radius:2px}
.tab-spacer{flex:1}
.print-button{background:var(--accent);color:#FFFFFF;border:none;border-radius:var(--radius-card);padding:var(--sp-8) var(--sp-16);font-size:var(--fs-13);font-weight:600;cursor:pointer;white-space:nowrap}
.print-button:hover{opacity:0.9}
.print-button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
@media(prefers-reduced-motion:reduce){.tab-btn{transition:none}}

/* Content area */
.report-content{flex:1;max-width:960px;margin:0 auto;width:100%}
.tab-panel[hidden]{display:none}

/* Loading / error */
.report-loading{text-align:center;padding:var(--sp-64) var(--sp-24)}
.report-loading-spinner{display:inline-block;width:32px;height:32px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.8s linear infinite;margin-bottom:var(--sp-16)}
@keyframes spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.report-loading-spinner{animation:none}}
.report-loading-text{font-size:var(--fs-14);color:var(--text-secondary)}
.report-error{text-align:center;padding:var(--sp-48) var(--sp-24);background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card)}
.report-error-title{font-size:var(--fs-17);font-weight:600;color:var(--status-error);margin-bottom:var(--sp-8)}
.report-error-text{font-size:var(--fs-14);color:var(--text-secondary);margin-bottom:var(--sp-16)}

/* Cards */
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
.threshold-caption{font-size:var(--fs-11);color:var(--text-secondary);margin-top:var(--sp-4);font-family:monospace}

/* QC badge */
.qc-badge{display:inline-block;padding:var(--sp-4) var(--sp-12);border-radius:var(--radius-pill);font-size:var(--fs-13);font-weight:600}
.qc-badge.passed{background:var(--tint-accent);color:var(--status-available);border:1px solid var(--status-available)}
.qc-badge.failed{background:var(--tint-error);color:var(--status-error);border:1px solid var(--status-error)}

/* Signal chips */
.signal-chip{display:inline-block;padding:var(--sp-4) var(--sp-12);border-radius:var(--radius-pill);font-size:var(--fs-13);font-weight:600;margin-right:var(--sp-8);white-space:nowrap}
.signal-chip.small{background:var(--tint-accent);color:var(--status-available);border:1px solid var(--status-available)}
.signal-chip.moderate{background:var(--tint-pending);color:var(--status-pending);border:1px solid var(--status-pending)}
.signal-chip.larger{background:var(--tint-error);color:var(--status-error);border:1px solid var(--status-error)}
.signal-chip.not_available{background:var(--bg-page);color:var(--status-unconfigured);border:1px solid var(--status-unconfigured)}

/* Symmetry signal row */
.symmetry-row{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-12) 0;border-bottom:1px solid var(--border);font-size:var(--fs-14);gap:var(--sp-12);flex-wrap:wrap}
.symmetry-row:last-child{border-bottom:none}
.symmetry-label{flex:1;color:var(--text-primary);min-width:200px}
.symmetry-note{font-size:var(--fs-13);color:var(--text-secondary);margin-top:var(--sp-12);font-style:italic}

/* Summary note */
.symmetry-summary{font-size:var(--fs-13);color:var(--text-secondary);margin-bottom:var(--sp-8)}

/* Signal detail table (internal) */
.signal-detail-table{width:100%;border-collapse:collapse;font-size:var(--fs-13);margin:var(--sp-12) 0}
.signal-detail-table th{text-align:left;padding:var(--sp-8) var(--sp-12);border-bottom:2px solid var(--border);color:var(--text-secondary);font-weight:600;font-size:var(--fs-11);text-transform:uppercase;letter-spacing:0.5px}
.signal-detail-table td{padding:var(--sp-8) var(--sp-12);border-bottom:1px solid var(--border);color:var(--text-primary)}
.signal-detail-table td.feature-family{font-family:monospace;font-size:var(--fs-11);color:var(--text-secondary);word-break:break-all}
.signal-detail-table .detail-chip{font-weight:600}

/* Tech demo notice */
.tech-demo-notice{background:var(--tint-pending);border:1px solid var(--status-pending);border-radius:var(--radius-card);padding:var(--sp-12) var(--sp-16);margin-bottom:var(--sp-16);font-size:var(--fs-13);color:var(--text-primary)}
.tech-demo-notice strong{color:var(--status-pending)}

/* Sample mode banner */
.sample-banner{background:var(--tint-error);border:2px solid var(--status-error);border-radius:var(--radius-card);padding:var(--sp-16) var(--sp-24);margin-bottom:var(--sp-24);text-align:center}
.sample-banner-title{font-size:var(--fs-17);font-weight:700;color:var(--status-error);margin-bottom:var(--sp-8)}
.sample-banner-text{font-size:var(--fs-13);color:var(--text-primary);line-height:1.6}

/* Field table */
.field-table{width:100%}
.field-row{display:flex;padding:var(--sp-8) 0;border-bottom:1px solid var(--border);font-size:var(--fs-14)}
.field-row:last-child{border-bottom:none}
.field-label{width:200px;flex-shrink:0;color:var(--text-secondary);font-weight:500;padding-right:var(--sp-16)}
.field-value{flex:1;color:var(--text-primary);min-width:0;word-break:break-all}
.field-value.mono{font-family:monospace;font-size:var(--fs-11)}

/* Decision policy text */
.decision-policy-text{font-size:var(--fs-14);color:var(--text-primary);line-height:1.7;margin-top:var(--sp-8);border-left:2px solid var(--accent);padding-left:var(--sp-16)}

/* Explanation section */
.explanation-section{font-size:var(--fs-14);color:var(--text-primary);line-height:1.7;margin-top:var(--sp-8)}

/* Boundary note */
.boundary-note{font-size:var(--fs-13);color:var(--text-secondary);font-style:italic;padding:var(--sp-12) var(--sp-16);background:var(--tint-pending);border-radius:var(--radius-card);margin:var(--sp-16) 0}

/* Execution trace */
.trace-toggle{background:none;border:none;color:var(--accent);font-size:var(--fs-14);font-weight:600;cursor:pointer;padding:var(--sp-8) 0;display:flex;align-items:center;gap:var(--sp-8)}
.trace-toggle:hover{text-decoration:underline}
.trace-toggle:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
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

/* Section spacing */
.section-title{font-size:var(--fs-17);font-weight:600;color:var(--text-primary);margin:var(--sp-24) 0 var(--sp-12) 0;padding-bottom:var(--sp-8);border-bottom:1px solid var(--border)}

/* Footer */
.report-footer{text-align:center;padding:var(--sp-24) 0;font-size:var(--fs-13);color:var(--text-secondary);border-top:1px solid var(--border);margin-top:var(--sp-48)}
.report-footer p{max-width:720px;margin:0 auto}

/* Responsive */
@media(max-width:768px){.report-page{padding:var(--sp-12)}.report-content{max-width:100%}.field-label{width:120px}.tab-btn{padding:var(--sp-8) var(--sp-12);font-size:var(--fs-13)}.print-button{padding:var(--sp-8) var(--sp-12);font-size:var(--fs-11)}.signal-detail-table td.feature-family{max-width:120px}}

/* Print */
@media print {
  body{background:#FFFFFF;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .report-page{padding:0;max-width:100%}
  .report-nav,.report-tabs,.tab-btn,.tab-spacer,.print-button,
  .trace-toggle,.trace-content,.report-loading,.report-error,
  .report-loading-spinner{display:none !important}
  .tab-panel[hidden]{display:none !important}
  .tab-panel:not([hidden]){display:block !important}
  .recommendation-card{box-shadow:none;page-break-inside:avoid;border:1px solid #E3E7E6;border-left:3px solid #1F6F6B;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .report-card{box-shadow:none;page-break-inside:avoid;border:1px solid #E3E7E6;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .score-bar{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .score-fill{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .score-threshold{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .signal-chip{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .qc-badge{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .tech-demo-notice{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .boundary-note{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .decision-policy-text{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .sample-banner{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .trace-stage{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .signal-detail-table{page-break-inside:avoid}
  .symmetry-row{page-break-inside:avoid}
  .report-header{border-bottom:1px solid #E3E7E6}
  .report-footer{border-top:1px solid #E3E7E6}
  .section-title{border-bottom:1px solid #E3E7E6}
}
"""

# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

_JS = r"""
<script>
(function(){
var baseUrl='__BASE_URL__';
var jobId='__JOB_ID__';
var isSample='__IS_SAMPLE__'==='1';
var sampleData=null;
var activeTab='external';

function init(){
  if(isSample){
    try{
      var el=document.getElementById('sample-data-json');
      if(el) sampleData=JSON.parse(el.textContent);
    }catch(e){}
    if(sampleData){
      document.getElementById('sample-banner').hidden=false;
      renderAll(sampleData.job,sampleData.report);
    }
    return;
  }
  if(jobId){
    loadReport(jobId);
  }
}

function loadReport(jid){
  var content=document.getElementById('report-content');
  Promise.all([
    fetch(baseUrl+'/demo/api/jobs/'+jid).then(function(r){return r.json()}),
    fetch(baseUrl+'/demo/api/jobs/'+jid+'/reports/bremen').then(function(r){return r.json()})
  ]).then(function(results){
    renderAll(results[0],results[1]);
  }).catch(function(){
    content.innerHTML='<div class="report-error"><div class="report-error-title">Failed to load report</div><div class="report-error-text">Could not load the report data. The job may have expired or the server may be unavailable.</div></div>';
  });
}

function renderAll(job,reportData){
  var report=reportData.report||{};
  renderExternalTab(job,report);
  renderInternalTab(job,report,reportData);
}

/* ---------- External tab ---------- */

function renderExternalTab(job,report){
  var panel=document.getElementById('panel-external');
  var wfRun=job.workflow_runs?job.workflow_runs['bremen']:null;
  var rs=wfRun?wfRun.result_summary||{}:{};
  var dsr=rs.decision_support_report||{};
  var decisionCode=rs.decision_code||'';
  var decisionName=rs.decision_display_name||'';
  var probability=rs.probability!==undefined?rs.probability:null;
  var threshold=rs.threshold_applied!==undefined?rs.threshold_applied:null;
  var modelId=job.input_summary?job.input_summary.model_id||'':'';

  var html='';

  // Sample mode banner placeholder (hidden in live mode)
  html+='<div id="sample-banner" class="sample-banner" hidden><div class="sample-banner-title">SYNTHETIC DEMONSTRATION SAMPLE</div><div class="sample-banner-text">Illustrative values only. Not generated from live runtime calibration. Not clinically validated. Not for patient or external distribution.</div></div>';

  // Technical demo notice
  html+='<div class="tech-demo-notice"><strong>Technical demo only.</strong> This report is produced by a technical product demo. It is not a clinical result. It is not clinically validated. It does not replace MRI, biopsy, a radiologist, a clinician, or clinical judgment.</div>';

  if(decisionName){
    html+='<div class="recommendation-card" role="alert">';
    html+='<div class="recommendation-headline">'+escapeHtml(decisionName)+'</div>';
    html+='<div class="recommendation-code">'+escapeHtml(decisionCode)+'</div>';
    if(probability!==null){
      var pct=Math.min(100,Math.max(0,probability*100));
      html+='<div class="recommendation-score">';
      html+='<div class="score-bar"><div class="score-fill" style="width:'+pct+'%"></div>';
      if(threshold!==null){
        var threshPct=Math.min(100,Math.max(0,threshold*100));
        html+='<div class="score-threshold" style="left:'+threshPct+'%" title="Threshold: '+threshold.toFixed(3)+'"></div>';
      }
      html+='</div>';
      html+='<span class="score-label">Score: '+probability.toFixed(3)+'</span>';
      html+='</div>';
      if(threshold!==null){
        html+='<div class="threshold-caption">Threshold: '+threshold.toFixed(3)+'</div>';
      }
    }
    html+='</div>';
  }else if(report.status==='unavailable'||report.status==='job_not_found'){
    html+='<div class="report-card"><div class="report-card-title">Report unavailable</div><p style="font-size:var(--fs-14);color:var(--text-secondary)">The report for this job is not available.</p></div>';
  }

  // QC Status — read from report payload (same authoritative source as Internal)
  var extQcSummary=report.payload?report.payload.measurement_qc_summary||{}:{};
  var qcStatus=extQcSummary.qc_status||rs.qc_status||'—';
  var qcClass=qcStatus==='passed'?'passed':'failed';
  html+='<div class="report-card">';
  html+='<div class="report-card-title">Quality Control</div>';
  html+='<span class="qc-badge '+qcClass+'">QC: '+escapeHtml(qcStatus)+'</span>';
  var qcFlags=extQcSummary.qc_flags||rs.qc_flags||[];
  if(qcFlags.length>0){
    html+='<p style="font-size:var(--fs-13);color:var(--text-secondary);margin-top:var(--sp-8)">Flags: '+escapeHtml(qcFlags.join(', '))+'</p>';
  }
  html+='</div>';

  // Left/Right Structural Comparison — Symmetry Signals
  var symData=dsr.symmetry_signals||null;
  html+='<div class="report-card">';
  html+='<div class="report-card-title">Left/Right Structural Comparison</div>';
  if(symData&&symData.signals&&symData.signals.length>0){
    html+='<p class="symmetry-summary">'+escapeHtml(symData.measurement_summary||'')+'</p>';
    for(var i=0;i<symData.signals.length;i++){
      var sig=symData.signals[i];
      var level=sig.difference_level||'not_available';
      var chipLabel=levelChipLabel(level);
      var chipClass='signal-chip '+level;
      html+='<div class="symmetry-row">';
      html+='<span class="symmetry-label">'+escapeHtml(sig.label||'')+'</span>';
      html+='<span class="'+chipClass+'">'+escapeHtml(chipLabel)+'</span>';
      html+='</div>';
    }
    if(symData.note){
      html+='<p class="symmetry-note">'+escapeHtml(symData.note)+'</p>';
    }
  }else{
    html+='<p style="font-size:var(--fs-14);color:var(--text-secondary)">Asymmetry assessment is not available.</p>';
  }
  html+='</div>';

  // Explanation section
  html+='<div class="report-card">';
  html+='<div class="report-card-title">Explanation</div>';
  if(decisionCode==='CONTINUE_MRI'){
    html+='<div class="explanation-section">Based on the model output, MRI follow-up may be recommended for this patient. The model assessed features extracted from the target and contralateral control scan. The score exceeds the decision threshold, suggesting that MRI continuation should be considered by the reviewing clinician.</div>';
  }else if(decisionCode==='MRI_REVIEW_DEFER'){
    html+='<div class="explanation-section">Based on the model output, MRI follow-up may not be indicated for this patient. The model assessed features extracted from the target and contralateral control scan. The score is below the decision threshold, suggesting that MRI continuation may be deferred subject to clinician review.</div>';
  }else{
    html+='<div class="explanation-section">Model output is not conclusive. A qualified clinician must review the full case and determine the appropriate next steps.</div>';
  }
  html+='<div class="decision-policy-text" style="margin-top:var(--sp-16)">Decision policy: '+escapeHtml(rs.decision_policy_id||'bremen_mri_continuation_threshold')+' v'+escapeHtml(rs.decision_policy_version||'0.1.0')+'</div>';
  html+='</div>';

  // Model table
  html+='<div class="report-card">';
  html+='<div class="report-card-title">Model</div>';
  html+='<div class="field-table">';
  html+='<div class="field-row"><div class="field-label">Model</div><div class="field-value mono">'+escapeHtml(modelId||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Version</div><div class="field-value mono">'+escapeHtml(rs.model_version||job.model_version||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Feature schema</div><div class="field-value mono">'+escapeHtml(rs.feature_schema_version||'v0.1')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Decision policy</div><div class="field-value mono">'+escapeHtml(rs.decision_policy_id||'bremen_mri_continuation_threshold')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Certification</div><div class="field-value">Scientific certification: pending</div></div>';
  html+='</div></div>';

  // Report ID
  html+='<div class="report-card">';
  html+='<div class="report-card-title">Report</div>';
  html+='<div class="field-table">';
  html+='<div class="field-row"><div class="field-label">Report ID</div><div class="field-value mono">'+escapeHtml(report.report_id||dsr.report_schema_version||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Schema version</div><div class="field-value mono">'+escapeHtml(dsr.report_schema_version||'v0.1')+'</div></div>';
  html+='</div></div>';

  panel.innerHTML=html;
  if(isSample&&sampleData){document.getElementById('sample-banner').hidden=false;}
}

/* ---------- Internal tab ---------- */

function renderInternalTab(job,report,reportData){
  var panel=document.getElementById('panel-internal');
  var payload=report.payload||{};
  var audit=payload.audit_information||{};
  var modelIdent=payload.model_identity||{};
  var qcSummary=payload.measurement_qc_summary||{};
  var scoreThresh=payload.score_and_threshold||{};
  var techEvidence=payload.supporting_technical_evidence||{};
  var symDetail=techEvidence.symmetry_signal_detail||null;
  var wfRun=job.workflow_runs?job.workflow_runs['bremen']:null;

  // checksum prefix — max 8 hex chars
  var rawChecksum=modelIdent.model_checksum||'';
  var checksumPrefix=rawChecksum.length>=8?rawChecksum.substring(0,8):rawChecksum;

  var html='';

  // Job / Request identity
  html+='<div class="section-title">Request / Job Identity</div>';
  html+='<div class="report-card">';
  html+='<div class="field-table">';
  html+='<div class="field-row"><div class="field-label">Job ID</div><div class="field-value mono">'+escapeHtml(job.job_id||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Workflow</div><div class="field-value mono">bremen</div></div>';
  html+='<div class="field-row"><div class="field-label">Source</div><div class="field-value mono">'+escapeHtml(job.input_summary?job.input_summary.container_id||job.input_summary.filename||'—':'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Created</div><div class="field-value mono">'+escapeHtml(job.created_at?job.created_at.substring(0,19).replace('T',' '):'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Completed</div><div class="field-value mono">'+escapeHtml(job.completed_at?job.completed_at.substring(0,19).replace('T',' '):'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Duration</div><div class="field-value mono">'+escapeHtml(job.completed_at&&job.created_at?((new Date(job.completed_at)-new Date(job.created_at))/1000).toFixed(1)+'s':'—')+'</div></div>';
  html+='</div></div>';

  // Model / Runtime Plugin Details
  html+='<div class="section-title">Model / Runtime Plugin Details</div>';
  html+='<div class="report-card">';
  html+='<div class="field-table">';
  html+='<div class="field-row"><div class="field-label">Model ID</div><div class="field-value mono">'+escapeHtml(report.model_id||reportData.model_id||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Model version</div><div class="field-value mono">'+escapeHtml(report.model_version||modelIdent.model_version||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Feature schema version</div><div class="field-value mono">'+escapeHtml(modelIdent.feature_schema_version||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Checksum prefix</div><div class="field-value mono">'+escapeHtml(checksumPrefix||'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Decision policy</div><div class="field-value mono">bremen_mri_continuation_threshold</div></div>';
  html+='<div class="field-row"><div class="field-label">Policy version</div><div class="field-value mono">0.1.0</div></div>';
  html+='<div class="field-row"><div class="field-label">Report schema version</div><div class="field-value mono">'+escapeHtml(payload.report_schema_version||report.report_schema_version||'—')+'</div></div>';
  html+='</div></div>';

  // Decision policy
  html+='<div class="section-title">Decision Policy</div>';
  html+='<div class="report-card">';
  html+='<div class="field-table">';
  html+='<div class="field-row"><div class="field-label">Policy</div><div class="field-value mono">bremen_mri_continuation_threshold</div></div>';
  html+='<div class="field-row"><div class="field-label">Score</div><div class="field-value mono">'+escapeHtml(scoreThresh.p_mri_needed!==undefined?scoreThresh.p_mri_needed.toFixed(3):'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Threshold</div><div class="field-value mono">'+escapeHtml(scoreThresh.threshold!==undefined?scoreThresh.threshold.toFixed(3):'—')+'</div></div>';
  html+='<div class="field-row"><div class="field-label">Decision</div><div class="field-value mono">'+escapeHtml(scoreThresh.triage_recommendation||'—')+'</div></div>';
  html+='</div></div>';

  // QC Status
  html+='<div class="section-title">QC Status</div>';
  html+='<div class="report-card">';
  var qcStatus2=qcSummary.qc_status||'—';
  var qcClass2=qcStatus2==='passed'?'passed':'failed';
  html+='<span class="qc-badge '+qcClass2+'">QC: '+escapeHtml(qcStatus2)+'</span>';
  var qcFlags2=qcSummary.qc_flags||[];
  if(qcFlags2.length>0){
    html+='<p style="font-size:var(--fs-13);color:var(--text-secondary);margin-top:var(--sp-8)">Flags: '+escapeHtml(qcFlags2.join(', '))+'</p>';
  }
  html+='</div>';

  // Symmetry signal breakdown
  html+='<div class="section-title">Symmetry Signal Breakdown</div>';
  html+='<div class="report-card">';
  if(symDetail&&symDetail.signals&&symDetail.signals.length>0){
    html+='<p class="symmetry-summary">'+escapeHtml(symDetail.measurement_summary||'')+'</p>';
    html+='<table class="signal-detail-table">';
    html+='<thead><tr><th>Signal</th><th>Feature Family</th><th>Level</th></tr></thead>';
    html+='<tbody>';
    for(var j=0;j<symDetail.signals.length;j++){
      var dsig=symDetail.signals[j];
      var dlevel=dsig.difference_level||'not_available';
      var dchipLabel=detailLevelLabel(dlevel);
      var dchipClass='signal-chip '+dlevel;
      var famStr=(dsig.feature_family||[]).join(', ');
      html+='<tr>';
      html+='<td>'+escapeHtml(dsig.label||'')+'</td>';
      html+='<td class="feature-family">'+escapeHtml(famStr)+'</td>';
      html+='<td><span class="'+dchipClass+' detail-chip">'+escapeHtml(dchipLabel)+'</span></td>';
      html+='</tr>';
    }
    html+='</tbody></table>';
    if(symDetail.checksum_prefix){
      html+='<p style="font-size:var(--fs-11);color:var(--text-secondary);margin-top:var(--sp-12);font-family:monospace">Checksum prefix: '+escapeHtml(symDetail.checksum_prefix)+'</p>';
    }
    if(symDetail.reference_artifact_version){
      html+='<p style="font-size:var(--fs-11);color:var(--text-secondary);font-family:monospace">Reference artifact version: '+escapeHtml(symDetail.reference_artifact_version)+'</p>';
    }
    if(symDetail.note){
      html+='<p class="symmetry-note">'+escapeHtml(symDetail.note)+'</p>';
    }
  }else{
    html+='<p style="font-size:var(--fs-14);color:var(--text-secondary)">No symmetry signal data available.</p>';
  }
  html+='</div>';

  // Execution trace
  var traces=job.execution_traces||{};
  var bremenTrace=traces['bremen']||null;
  if(bremenTrace&&bremenTrace.stages&&bremenTrace.stages.length>0){
    html+='<div class="section-title">Execution Trace</div>';
    html+='<div class="report-card">';
    bremenTrace.stages.forEach(function(stage){
      var statusClass=stage.status||'not_started';
      var icon=statusClass==='completed'?'&#10003;':statusClass==='failed'?'&#10007;':'&#9679;';
      var iconClass=statusClass==='completed'?'completed':statusClass==='failed'?'failed':'';
      html+='<div class="trace-stage '+statusClass+'">';
      html+='<span class="trace-stage-icon '+iconClass+'">'+icon+'</span>';
      html+='<span class="trace-stage-label">'+escapeHtml(stage.label||stage.stage_id||'')+'</span>';
      if(stage.duration_ms!=null){html+='<span class="trace-stage-dur">'+stage.duration_ms+'ms</span>';}
      html+='</div>';
    });
    html+='</div>';
  }

  // Boundary note
  html+='<div class="boundary-note">Boundary note: This is a technical product demo of the Bremen MRI triage decision-support workflow. It is not a clinical result. It is not clinically validated.</div>';

  panel.innerHTML=html;
}

/* ---------- Helpers ---------- */

function levelChipLabel(level){
  switch(level){
    case 'small': return 'Small';
    case 'moderate': return 'Moderate';
    case 'larger': return 'Larger';
    case 'not_available': return 'Calibration pending';
    default: return 'Calibration pending';
  }
}

function detailLevelLabel(level){
  switch(level){
    case 'small': return 'Small';
    case 'moderate': return 'Moderate';
    case 'larger': return 'Larger';
    case 'not_available': return 'Reference statistics unavailable';
    default: return 'Reference statistics unavailable';
  }
}

function escapeHtml(str){
  if(!str)return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ---------- Tab switching ---------- */

function switchTab(tabId){
  activeTab=tabId;
  var tabs=document.querySelectorAll('.tab-btn[role="tab"]');
  for(var i=0;i<tabs.length;i++){
    var t=tabs[i];
    var selected=t.getAttribute('data-tab')===tabId;
    t.setAttribute('aria-selected',selected?'true':'false');
    t.tabIndex=selected?0:-1;
  }
  var panels=document.querySelectorAll('.tab-panel[role="tabpanel"]');
  for(var j=0;j<panels.length;j++){
    var p=panels[j];
    if(p.id==='panel-'+tabId){p.removeAttribute('hidden');}
    else{p.setAttribute('hidden','');}
  }
  // Show only the active print button
  var btnExt=document.getElementById('print-btn-external');
  var btnInt=document.getElementById('print-btn-internal');
  if(btnExt) btnExt.style.display=tabId==='external'?'':'none';
  if(btnInt) btnInt.style.display=tabId==='internal'?'':'none';
}

function printActiveTab(){
  switchTab(activeTab);
  window.print();
}

/* ---------- Keyboard navigation ---------- */
document.addEventListener('keydown',function(e){
  if(e.key==='ArrowRight'||e.key==='ArrowLeft'){
    var tabs=document.querySelectorAll('.tab-btn[role="tab"]');
    var currentIdx=-1;
    for(var i=0;i<tabs.length;i++){
      if(tabs[i].getAttribute('aria-selected')==='true'){currentIdx=i;break;}
    }
    if(currentIdx>=0){
      if(e.key==='ArrowRight') currentIdx=(currentIdx+1)%tabs.length;
      else currentIdx=(currentIdx-1+tabs.length)%tabs.length;
      var nextTab=tabs[currentIdx].getAttribute('data-tab');
      if(nextTab) switchTab(nextTab);
      tabs[currentIdx].focus();
    }
    e.preventDefault();
  }
});

window.switchTab=switchTab;
window.printActiveTab=printActiveTab;
window.loadReport=loadReport;

init();
})();
</script>
"""


def build_report_page(
    base_url: str = "http://localhost:8000",
    job_id: str = "",
    sample_data: dict | None = None,
) -> str:
    """Build the Bremen Report page HTML.

    Parameters
    ----------
    base_url : Base URL of the service.
    job_id : The job ID to display the report for.
    sample_data : Optional sample data dict for offline sample mode.
        When provided, data is embedded directly in the HTML and no
        fetch calls are made. The page displays a prominent synthetic
        sample banner. Must NOT be used in production.

    Returns
    -------
    A complete HTML5 document as a string.
    """
    is_sample = "1" if sample_data else "0"
    sample_json = ""
    if sample_data:
        sample_json = (
            '<script type="application/json" id="sample-data-json">'
            + _json.dumps(sample_data, ensure_ascii=False)
            + "</script>"
        )

    js = _JS.replace("__BASE_URL__", base_url)
    js = js.replace("__JOB_ID__", job_id)
    js = js.replace("__IS_SAMPLE__", is_sample)

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
      <div class="report-subtitle">MRI-Continuation Decision-Support Report</div>
      <div class="report-subtitle" style="color:var(--text-secondary)">For referring clinician / breast-imaging radiologist</div>
    </div>
    <div class="report-nav">
      <a href="/demo/control-room">Back to Control Room</a>
    </div>
  </div>

  <div class="report-tabs" role="tablist" aria-label="Report tabs">
    <button class="tab-btn" role="tab" id="tab-external-btn"
            aria-selected="true" aria-controls="panel-external"
            data-tab="external" onclick="switchTab('external')"
            tabindex="0">External</button>
    <button class="tab-btn" role="tab" id="tab-internal-btn"
            aria-selected="false" aria-controls="panel-internal"
            data-tab="internal" onclick="switchTab('internal')"
            tabindex="-1">Internal</button>
    <div class="tab-spacer"></div>
    <button class="print-button" id="print-btn-external"
            onclick="printActiveTab()">Print / Save PDF</button>
    <button class="print-button" id="print-btn-internal"
            onclick="printActiveTab()" style="display:none">Print / Save PDF</button>
  </div>

  <div class="report-content" id="report-content">
    <div id="panel-external" class="tab-panel" role="tabpanel"
         aria-labelledby="tab-external-btn">
      <div class="report-loading">
        <div class="report-loading-spinner"></div>
        <div class="report-loading-text">Loading report...</div>
      </div>
    </div>
    <div id="panel-internal" class="tab-panel" role="tabpanel"
         aria-labelledby="tab-internal-btn" hidden>
      <div class="report-loading">
        <div class="report-loading-spinner"></div>
        <div class="report-loading-text">Loading report...</div>
      </div>
    </div>
  </div>

  <div class="report-footer">
    <p>Bremen — MRI triage decision support. This report is produced by a technical product demo. It is not a clinical result. It is not clinically validated. Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment. The final decision must be made by a qualified clinician.</p>
  </div>
</div>
{sample_json}
{js}
</body>
</html>"""
