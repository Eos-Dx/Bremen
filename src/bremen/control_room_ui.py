"""Bremen Investor Control Room HTML page generator.

Produces a self-contained HTML page at GET /demo with:
- Presentation header with model identity and readiness
- Central visual execution pipeline (10 stages)
- Docked structured live event panel (SSE-fed)
- Decision panel using approved PR0081 vocabulary
- Report access

PR0082 — Bremen Investor Control Room.
"""

from __future__ import annotations

import json as _json
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONTROL_ROOM_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:#0d1117;color:#c9d1d9;line-height:1.6;overflow-x:hidden}
.cr-header{background:#161b22;border-bottom:1px solid #30363d;padding:12px 24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.cr-title{font-size:20px;font-weight:700;color:#f0f6fc}
.cr-subtitle{font-size:13px;color:#8b949e}
.cr-badges{display:flex;gap:8px;flex-wrap:wrap}
.cr-badge{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.cr-badge-ready{background:#1a3329;color:#3fb950;border:1px solid #3fb950}
.cr-badge-warn{background:#2a2311;color:#d29922;border:1px solid #d29922}
.cr-badge-info{background:#0d1f3d;color:#58a6ff;border:1px solid #58a6ff}
.cr-badge-error{background:#2a1518;color:#f85149;border:1px solid #f85149}
.cr-badge-pending{background:#1d1d2b;color:#8b949e;border:1px solid #8b949e}
.cr-badge-disabled{background:#161b22;color:#484f58;border:1px solid#30363d}
.cr-main{display:flex;gap:0;min-height:calc(100vh - 128px);max-width:1600px;margin:0 auto}
.cr-left{width:260px;min-width:200px;background:#161b22;border-right:1px solid #30363d;padding:16px;display:flex;flex-direction:column;gap:16px;overflow-y:auto}
.cr-center{flex:1;padding:24px;overflow-y:auto}
.cr-right{width:400px;min-width:300px;background:#161b22;border-left:1px solid #30363d;padding:16px;display:flex;flex-direction:column;overflow:hidden}
.cr-section-title{font-size:14px;font-weight:600;color:#f0f6fc;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
.cr-model-card{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:14px}
.cr-model-card h3{font-size:15px;color:#f0f6fc;margin-bottom:8px}
.cr-model-field{display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:12px}
.cr-model-field dt{color:#8b949e}
.cr-model-field dd{color:#c9d1d9;font-family:monospace;font-size:11px}
.cr-input-area{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:14px}
.cr-input-area .cr-btn{width:100%;margin-top:8px}
.cr-btn{padding:8px 20px;font-size:13px;font-weight:600;cursor:pointer;border:none;border-radius:6px;background:#238636;color:#fff;transition:background 200ms}
.cr-btn:hover:not(:disabled){background:#2ea043}
.cr-btn:disabled{background:#21262d;color:#484f58;cursor:not-allowed}
.cr-btn:focus{outline:3px solid #58a6ff;outline-offset:2px}
.cr-btn-warn{background:#d29922;color:#0d1117}
.cr-btn-warn:hover:not(:disabled){background:#e3b341}

.cr-pipeline{position:relative;padding:8px 0}
.cr-pipeline ol{list-style:none;position:relative}
.cr-pipeline li{display:flex;align-items:center;gap:12px;padding:10px 16px;border-left:3px solid #21262d;margin-left:20px;position:relative;transition:border-color 300ms}
.cr-pipeline li:last-child{border-left-color:transparent}
.cr-pipeline li::before{content:'';position:absolute;left:-11px;top:16px;width:18px;height:18px;border-radius:50%;background:#21262d;border:3px solid #30363d;z-index:1;transition:background 300ms,border-color 300ms}
.cr-pipeline li.completed{border-left-color:#3fb950}
.cr-pipeline li.completed::before{background:#1a3329;border-color:#3fb950}
.cr-pipeline li.active{border-left-color:#58a6ff}
.cr-pipeline li.active::before{background:#0d1f3d;border-color:#58a6ff;animation:pulse-active 2s infinite}
.cr-pipeline li.failed{border-left-color:#f85149}
.cr-pipeline li.failed::before{background:#2a1518;border-color:#f85149}
.cr-pipeline li.unavailable{border-left-color:#d29922}
.cr-pipeline li.unavailable::before{background:#2a2311;border-color:#d29922}
.cr-pipeline li.pending{border-left-color:#21262d}
.cr-pipeline li.pending::before{background:#0d1117;border-color:#30363d}
@keyframes pulse-active{0%,100%{border-color:#58a6ff}50%{border-color:#1f6feb}}
@media(prefers-reduced-motion:reduce){.cr-pipeline li.active::before{animation:none}}
.cr-stage-label{font-size:13px;color:#c9d1d9;font-weight:500}
.cr-stage-status{font-size:11px;color:#8b949e;margin-left:auto}
.cr-stage-icon{font-size:12px;width:18px;text-align:center}
.cr-stage-icon.completed{color:#3fb950}
.cr-stage-icon.active{color:#58a6ff}
.cr-stage-icon.failed{color:#f85149}
.cr-stage-icon.pending{color:#484f58}

.cr-decision-card{background:#0d1117;border:1px solid #3fb950;border-radius:10px;padding:20px;margin-top:24px}
.cr-decision-card.negative{border-color:#8b949e}
.cr-decision-card h2{font-size:18px;color:#f0f6fc;margin-bottom:8px}
.cr-decision-card .cr-decision-text{font-size:14px;color:#8b949e;margin-bottom:12px}
.cr-decision-score{display:flex;height:8px;border-radius:4px;background:#21262d;margin:12px 0;overflow:hidden}
.cr-decision-score-fill{background:#58a6ff;border-radius:4px;transition:width 800ms}
.cr-decision-threshold-marker{position:absolute;width:2px;height:20px;background:#f85149;top:0}
.cr-decision-meta{font-size:11px;color:#484f58;margin-top:8px}
.cr-decision-cert{display:inline-block;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:600;background:#2a1518;color:#f85149;border:1px solid #f85149;margin-top:8px}

.cr-event-panel{flex:1;overflow-y:auto;font-size:12px;font-family:monospace}
.cr-event-row{padding:4px 8px;margin:1px 0;border-left:3px solid #30363d;background:#0d1117;transition:background 150ms}
.cr-event-row.completed{border-left-color:#3fb950;background:#0d1a14}
.cr-event-row.failed{border-left-color:#f85149;background:#1a0d0f}
.cr-event-row.started{border-left-color:#58a6ff;background:#0d1525}
.cr-event-row span{display:inline-block;margin-right:8px}
.cr-event-seq{color:#484f58;width:30px}
.cr-event-type{color:#8b949e;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cr-event-status{font-weight:600}
.cr-event-status.completed{color:#3fb950}
.cr-event-status.failed{color:#f85149}
.cr-event-status.started{color:#58a6ff}
.cr-event-time{color:#484f58}
.cr-event-dur{color:#484f58;font-size:10px}
.cr-event-panel-actions{display:flex;gap:8px;padding:8px 0;border-top:1px solid #30363d}
.cr-event-panel-btn{font-size:11px;padding:3px 10px;background:#21262d;color:#8b949e;border:1px solid #30363d;border-radius:4px;cursor:pointer}
.cr-event-panel-btn:hover{color:#c9d1d9}
.cr-event-panel-btn.active{background:#0d1f3d;color:#58a6ff;border-color:#58a6ff}

.cr-empty{color:#484f58;font-size:13px;text-align:center;padding:24px}
.cr-connecting{color:#d29922;font-size:12px;text-align:center;padding:12px}
.cr-status-bar{padding:6px 24px;background:#161b22;border-top:1px solid #30363d;display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#484f58}
.cr-status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.cr-status-dot.live{background:#3fb950}
.cr-status-dot.connecting{background:#d29922;animation:pulse-active 2s infinite}
.cr-status-dot.disconnected{background:#f85149}
.cr-status-dot.idle{background:#484f58}

.cr-report-link{display:inline-block;padding:6px 16px;background:#0d1f3d;color:#58a6ff;border:1px solid #1f6feb;border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;cursor:pointer;margin-top:8px}
.cr-report-link:hover{background:#0d2a4d}

.cr-footer{text-align:center;padding:12px;font-size:11px;color:#484f58}
.hidden{display:none}

@media(max-width:1024px){.cr-main{flex-wrap:wrap}.cr-right{width:100%;border-left:none;border-top:1px solid #30363d;max-height:400px}.cr-left{width:100%;border-right:none;border-bottom:1px solid #30363d}}
@media(max-width:768px){.cr-header{flex-direction:column;align-items:flex-start}.cr-center{padding:16px}.cr-pipeline li{margin-left:12px;padding:8px 12px}}
"""

_CONTROL_ROOM_JS = r"""
<script>
(function(){
var baseUrl='__BASE_URL__';
var currentJobId=null;
var eventSource=null;
var autoScroll=true;
var lastSequence=0;
var eventCache=[];
var MAX_EVENTS=200;
var modelReady=false;
var modelStatus='unknown';
var jobState='idle';
var stagedPath=null;
var STAGE_MAP={
  'runtime.request.accepted':'stage-input',
  'runtime.input.preparation.completed':'stage-source',
  'runtime.normalization.completed':'stage-xrd',
  'runtime.workflow.resolved':'stage-workflow',
  'runtime.artifact.verification.completed':'stage-artifact',
  'runtime.model.validation.completed':'stage-artifact',
  'runtime.features.validation.completed':'stage-features',
  'runtime.inference.completed':'stage-inference',
  'runtime.decision.completed':'stage-decision',
  'runtime.report.completed':'stage-report',
  'runtime.request.completed':'stage-complete'
};
var FAIL_MAP={
  'runtime.normalization.failed':'stage-xrd',
  'runtime.workflow.failed':'stage-workflow',
  'runtime.input.preparation.failed':'stage-source',
  'runtime.features.failed':'stage-features',
  'runtime.inference.failed':'stage-inference'
};

function init(){
  loadReadiness();
  var fileInput=document.getElementById('cr-file-input');
  if(fileInput){
    fileInput.addEventListener('change',handleFileSelect);
  }
}
function handleFileSelect(){
  var file=document.getElementById('cr-file-input').files[0];
  if(!file)return;
  setState('validating');
  fetch(baseUrl+'/demo/api/stage',{method:'POST',body:file})
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.status==='staged'){
        stagedPath=data.h5_path;
        document.getElementById('cr-source-status').textContent='Ready: '+file.name;
        setState('ready_to_submit');
      }else{
        document.getElementById('cr-source-status').textContent='Invalid';
        setState('idle');
      }
    }).catch(function(){
      document.getElementById('cr-source-status').textContent='Failed';
      setState('idle');
    });
}
function setState(newState){
  var valid=['idle','source_selected','validating','ready_to_submit','submitting',
    'job_created','connecting','running','reconnecting','completed',
    'partial_success','failed','unavailable','expired'];
  if(valid.indexOf(newState)===-1)return;
  jobState=newState;
  var btn=document.getElementById('cr-analyze-btn');
  if(btn){
    btn.disabled=!(modelReady&&newState==='ready_to_submit');
    if(newState==='submitting'){btn.textContent='Submitting...';btn.disabled=true}
  }
  var label=document.getElementById('cr-status-label');
  if(label){label.textContent=newState.replace(/_/g,' ')}
  var dot=document.getElementById('cr-status-dot');
  if(dot){
    if(newState==='running'){dot.className='cr-status-dot live'}
    else if(newState==='connecting'||newState==='reconnecting'){dot.className='cr-status-dot connecting'}
    else if(newState==='completed'||newState==='ready_to_submit'){dot.className='cr-status-dot live'}
    else{dot.className='cr-status-dot idle'}
  }
}

function loadReadiness(){
  Promise.all([
    fetch(baseUrl+'/health').then(function(r){return r.json()}),
    fetch(baseUrl+'/model/version').then(function(r){return r.json()})
  ]).then(function(results){
    var health=results[0];
    var version=results[1];
    modelReady=health.model_ready===true;
    modelStatus=version.model_status||'unknown';
    renderReadiness(version,modelReady,modelStatus);
  }).catch(function(){
    document.getElementById('cr-readiness').innerHTML='<span class="cr-badge cr-badge-error">Cannot reach server</span>';
  });
}
function renderReadiness(version,ready,status){
  var html='';
  if(ready){
    html+='<span class="cr-badge cr-badge-ready" role="status">Model Ready</span> ';
  }else if(status==='not_configured'){
    html+='<span class="cr-badge cr-badge-warn" role="status">Model Not Configured</span> ';
  }else if(status==='error'){
    html+='<span class="cr-badge cr-badge-error" role="status">Model Error</span> ';
  }else{
    html+='<span class="cr-badge cr-badge-pending" role="status">Model Loading</span> ';
  }
  html+='<span class="cr-badge cr-badge-pending" role="status">Scientific certification: pending</span> ';
  html+='<span class="cr-badge cr-badge-disabled" role="status">Technical demo only</span>';
  document.getElementById('cr-readiness').innerHTML=html;

  var info=document.getElementById('cr-model-info');
  if(info){
    var v=version.model_version||'unknown';
    var fs=version.feature_schema_version||'v0.1';
    info.innerHTML='<dl>'+
      '<div class="cr-model-field"><dt>Model</dt><dd>'+v+'</dd></div>'+
      '<div class="cr-model-field"><dt>Feature schema</dt><dd>'+fs+'</dd></div>'+
      '<div class="cr-model-field"><dt>Decision policy</dt><dd>bremen_mri_continuation_threshold v0.1.0</dd></div>'+
      '</dl>';
  }

  var hint=document.getElementById('cr-model-hint');
  if(hint){if(!ready){hint.classList.remove('hidden')}else{hint.classList.add('hidden')}}
  setState(jobState);
}
function startAnalysis(){
  if(jobState!=='ready_to_submit'||!modelReady||!stagedPath)return;
  setState('submitting');
  resetPipeline();
  resetEventPanel();
  setConnectionState('connecting');

  fetch(baseUrl+'/demo/api/jobs',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({workflow_id:'bremen',h5_path:stagedPath})
  }).then(function(r){return r.json()}).then(function(data){
    var job=data.job||{};
    var jid=job.job_id||'';
    if(!jid){
      setConnectionState('idle');
      setState('ready_to_submit');
      return;
    }
    currentJobId=jid;
    setState('job_created');
    fetchInitialEvents(jid);
    connectSSE(jid);
  }).catch(function(){
    setConnectionState('idle');
    setState('ready_to_submit');
  });
}
function fetchInitialEvents(jobId){
  fetch(baseUrl+'/demo/api/jobs/'+jobId+'/events')
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.events){
        data.events.forEach(function(ev){processEvent(ev)});
      }
    }).catch(function(){});
}
function connectSSE(jobId){
  if(eventSource){eventSource.close()}
  eventSource=new EventSource(baseUrl+'/demo/api/jobs/'+jobId+'/events/stream');
  setConnectionState('connecting');
  eventSource.addEventListener('job_event',function(e){
    try{var ev=JSON.parse(e.data);setState('running');processEvent(ev)}catch(ex){}
  });
  eventSource.addEventListener('stream_complete',function(){
    setConnectionState('live');
    fetchDecision(jobId);
    if(eventSource){eventSource.close();eventSource=null}
    setState('completed');
  });
  eventSource.onopen=function(){setConnectionState('live');setState('running')};
  eventSource.onerror=function(){
    if(eventSource&&eventSource.readyState===EventSource.CLOSED){
      setConnectionState('disconnected');setState('failed');
    }else{setConnectionState('reconnecting');setState('reconnecting')}
  };
}
function processEvent(ev){
  if(!ev)return;
  if(ev.sequence<=lastSequence)return;
  lastSequence=ev.sequence;
  eventCache.push(ev);
  updatePipeline(ev);
  addEventRow(ev);
}
function updatePipeline(ev){
  var stage=ev.event_type||'';
  var status=ev.status||'';
  var id=STAGE_MAP[stage]||FAIL_MAP[stage]||'';
  if(!id)return;
  var el=document.getElementById(id);
  if(!el)return;
  var isFail=FAIL_MAP[stage]!==undefined;
  if(isFail||status==='failed'){
    el.className='failed';
    el.querySelector('.cr-stage-icon').textContent=String.fromCharCode(10007);
    el.querySelector('.cr-stage-icon').className='cr-stage-icon failed';
  }else if(status==='completed'){
    el.className='completed';
    el.querySelector('.cr-stage-icon').textContent=String.fromCharCode(10003);
    el.querySelector('.cr-stage-icon').className='cr-stage-icon completed';
  }else if(status==='started'||status==='resolved'){
    el.className='active';
    el.querySelector('.cr-stage-icon').textContent=String.fromCharCode(9679);
    el.querySelector('.cr-stage-icon').className='cr-stage-icon active';
  }
  var dur=el.querySelector('.cr-stage-dur');
  if(dur&&ev.duration_ms){dur.textContent=ev.duration_ms+' ms'}
}
function addEventRow(ev){
  var panel=document.getElementById('cr-event-list');
  if(!panel)return;
  var status=ev.status||'';
  var cls='cr-event-row';
  if(status==='completed')cls+=' completed';
  else if(status==='failed')cls+=' failed';
  else if(status==='started'||status==='resolved')cls+=' started';
  var ts=ev.timestamp?ev.timestamp.substring(11,19):'';
  var typeLabel=ev.event_type||'';
  if(typeLabel.length>40)typeLabel=typeLabel.substring(0,37)+'...';
  var div=document.createElement('div');
  div.className=cls;
  div.innerHTML='<span class="cr-event-seq">'+ev.sequence+'</span>'+
    '<span class="cr-event-type" title="'+ev.event_type+'">'+typeLabel+'</span>'+
    '<span class="cr-event-status '+status+'">'+status+'</span>'+
    '<span class="cr-event-time">'+ts+'</span>'+
    (ev.duration_ms?'<span class="cr-event-dur">'+ev.duration_ms+'ms</span>':'');
  panel.appendChild(div);
  while(panel.children.length>MAX_EVENTS){
    panel.removeChild(panel.firstChild);
  }
  if(autoScroll){panel.scrollTop=panel.scrollHeight}
}
function resetPipeline(){
  var stages=document.querySelectorAll('.cr-pipeline li');
  stages.forEach(function(s){
    s.className='pending';
    var icon=s.querySelector('.cr-stage-icon');
    if(icon){icon.textContent=String.fromCharCode(9679);icon.className='cr-stage-icon pending'}
    var dur=s.querySelector('.cr-stage-dur');
    if(dur){dur.textContent=''}
  });
}
function resetEventPanel(){
  var panel=document.getElementById('cr-event-list');
  if(panel){panel.innerHTML='<div class="cr-empty">Analysis events will appear here</div>'}
  eventCache=[];
  lastSequence=0;
}
function setConnectionState(state){
  var dot=document.getElementById('cr-status-dot');
  if(dot){
    dot.className='cr-status-dot '+state;
    if(state==='live')dot.className='cr-status-dot live';
    else if(state==='connecting'||state==='reconnecting')dot.className='cr-status-dot connecting';
    else if(state==='disconnected')dot.className='cr-status-dot disconnected';
    else dot.className='cr-status-dot idle';
  }
}
function fetchDecision(jobId){
  fetch(baseUrl+'/demo/api/jobs/'+jobId)
    .then(function(r){return r.json()})
    .then(function(job){
      var wf=job.workflow_runs?job.workflow_runs['bremen']:null;
      if(!wf||!wf.result_summary)return;
      var rs=wf.result_summary;
      var code=rs.decision_code||rs.triage_recommendation||'';
      var name=rs.decision_display_name||code;
      var policy=rs.decision_policy_id||'';
      var prob=rs.probability!==undefined?rs.probability:null;
      var thresh=rs.threshold_applied!==undefined?rs.threshold_applied:null;
      var card=document.getElementById('cr-decision-card');
      if(!card)return;
      card.className='cr-decision-card'+(code==='MRI_REVIEW_DEFER'?' negative':'');
      card.innerHTML='<h2 role="alert">'+name+'</h2>'+
        '<div class="cr-decision-text">'+code+'</div>'+
        (prob!==null&&thresh!==null?
          '<div style="position:relative">'+
          '<div class="cr-decision-score"><div class="cr-decision-score-fill" style="width:'+(Math.min(100,Math.max(0,prob*100)))+'%"></div></div>'+
          '<div class="cr-decision-threshold-marker" style="left:'+(Math.min(100,Math.max(0,thresh*100)))+'%;"></div>'+
          '<div class="cr-decision-meta">Score: '+prob.toFixed(3)+' | Threshold: '+thresh.toFixed(3)+'</div></div>':'')+
        '<div class="cr-decision-meta">Policy: '+policy+'</div>'+
        '<span class="cr-decision-cert">Scientific certification: pending</span> '+
        '<span class="cr-badge cr-badge-disabled" style="margin-left:4px">Technical demo only</span>';
      card.classList.remove('hidden');
      loadReport(jobId,rs);
    }).catch(function(){});
}
function loadReport(jobId,rs){
  fetch(baseUrl+'/demo/api/jobs/'+jobId+'/reports/bremen')
    .then(function(r){return r.json()})
    .then(function(data){
      var rpt=data.report||{};
      if(rpt.status==='available'){
        var link=document.getElementById('cr-report-link');
        if(link){
          link.classList.remove('hidden');
          link.textContent='View Bremen Report (v'+ (rpt.report_schema_version||'')+')';
        }
      }
    }).catch(function(){});
}
function toggleAutoScroll(){
  autoScroll=!autoScroll;
  var btn=document.getElementById('cr-autoscroll-btn');
  if(btn){btn.textContent=autoScroll?'Pause':'Follow';btn.className='cr-event-panel-btn'+(autoScroll?' active':'')}
}
function filterEvents(filter){
  var allBtn=document.getElementById('cr-filter-all');
  var compBtn=document.getElementById('cr-filter-completed');
  var failBtn=document.getElementById('cr-filter-failed');
  if(allBtn){allBtn.className='cr-event-panel-btn'+(filter==='all'?' active':'');allBtn.setAttribute('aria-pressed',filter==='all'?'true':'false')}
  if(compBtn){compBtn.className='cr-event-panel-btn'+(filter==='completed'?' active':'');compBtn.setAttribute('aria-pressed',filter==='completed'?'true':'false')}
  if(failBtn){failBtn.className='cr-event-panel-btn'+(filter==='failed'?' active':'');failBtn.setAttribute('aria-pressed',filter==='failed'?'true':'false')}
  var rows=document.querySelectorAll('.cr-event-row');
  rows.forEach(function(r){
    if(filter==='all'){r.classList.remove('hidden')}
    else if(filter==='completed'&&r.classList.contains('completed')){r.classList.remove('hidden')}
    else if(filter==='failed'&&r.classList.contains('failed')){r.classList.remove('hidden')}
    else{r.classList.add('hidden')}
  });
}
init();
})();
</script>
"""


def build_control_room_page(
    base_url: str = "http://localhost:8000",
    request_id: str = "",
) -> str:
    """Build the Bremen Investor Control Room HTML page.

    This page is the default experience at GET /demo.
    It renders one real configured Bremen model through the existing
    job API, SSE endpoint, decision contract, and report provider.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Investor Control Room</title>
<style>{_CONTROL_ROOM_CSS}</style>
</head>
<body>

<div class="cr-header">
  <div>
    <div class="cr-title">Bremen</div>
    <div class="cr-subtitle">Should the patient continue to MRI?</div>
  </div>
  <div class="cr-badges" id="cr-readiness">
    <span class="cr-badge cr-badge-pending">Checking readiness...</span>
  </div>
</div>

<div class="cr-main">
  <div class="cr-left">
    <div class="cr-section-title">Bremen Workflow</div>
    <div class="cr-model-card" id="cr-model-info">
      <h3>MRI Triage Model</h3>
      <p style="font-size:12px;color:#8b949e">Loading model details...</p>
    </div>
    <div class="cr-input-area">
      <div class="cr-section-title" style="margin-bottom:4px">Analysis</div>
      <p style="font-size:11px;color:#8b949e;margin-bottom:8px">Run a controlled Bremen analysis using the configured model</p>
      <div style="margin-bottom:8px">
      <input type="file" id="cr-file-input" accept=".h5,.hdf5" style="display:none">
      <button class="cr-btn cr-btn-warn" onclick="document.getElementById('cr-file-input').click()"
        style="width:100%;margin-bottom:4px">Select H5 File</button>
      <p id="cr-source-status" style="font-size:11px;color:#8b949e;margin-top:4px">No source selected</p>
      </div>
      <button class="cr-btn" id="cr-analyze-btn" onclick="startAnalysis()" disabled
        aria-label="Start analysis">Analyze</button>
      <p id="cr-model-hint" style="font-size:11px;color:#d29922;margin-top:8px">Model must be configured by the deployment operator</p>
    </div>
    <div style="font-size:10px;color:#484f58;margin-top:8px">
      <p>Jobs created via legacy analyze endpoint are not imported into this job list.</p>
    </div>
  </div>

  <div class="cr-center">
    <div class="cr-section-title">Execution Pipeline</div>
    <div class="cr-pipeline">
      <ol role="list" aria-label="Execution stages">
        <li class="pending" id="stage-input">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Input accepted</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-source">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Source validated</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-xrd">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Canonical XRD created</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-workflow">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Bremen workflow resolved</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-artifact">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Model artifact prepared</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-features">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Feature contract validated</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-inference">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Inference completed</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-decision">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Decision policy applied</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-report">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Report generated</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
        <li class="pending" id="stage-complete">
          <span class="cr-stage-icon pending">&#9679;</span>
          <span class="cr-stage-label">Analysis complete</span>
          <span class="cr-stage-dur cr-stage-status"></span>
        </li>
      </ol>
    </div>

    <div class="cr-decision-card hidden" id="cr-decision-card">
    </div>

    <div style="margin-top:16px">
      <a class="cr-report-link hidden" id="cr-report-link" href="#" target="_blank" rel="noopener">View Report</a>
    </div>
  </div>

  <div class="cr-right">
    <div class="cr-section-title">Live Events</div>
    <div class="cr-event-panel" id="cr-event-list" aria-live="polite" aria-atomic="false">
      <div class="cr-empty">Analysis events will appear here</div>
    </div>
    <div class="cr-event-panel-actions">
      <button class="cr-event-panel-btn active" id="cr-filter-all" onclick="filterEvents('all')"
        aria-pressed="true" aria-label="Show all events">All</button>
      <button class="cr-event-panel-btn" id="cr-filter-completed" onclick="filterEvents('completed')"
        aria-pressed="false" aria-label="Show completed events only">Completed</button>
      <button class="cr-event-panel-btn" id="cr-filter-failed" onclick="filterEvents('failed')"
        aria-pressed="false" aria-label="Show failed events only">Failed</button>
      <button class="cr-event-panel-btn active" id="cr-autoscroll-btn" onclick="toggleAutoScroll()" style="margin-left:auto">Pause</button>
    </div>
  </div>
</div>

<div class="cr-status-bar">
  <span><span class="cr-status-dot idle" id="cr-status-dot"></span>
    <span id="cr-status-label">Idle</span></span>
  <span>
    <a href="/demo/workspace" style="color:#58a6ff;text-decoration:none;font-size:11px">Workspace</a>
    &nbsp;|&nbsp;
    <span style="color:#484f58">Technical demo only &mdash; not a clinical result.</span>
  </span>
</div>

<div class="cr-footer">
  Bremen Investor Control Room &mdash; Not clinically validated. Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.
</div>

{_CONTROL_ROOM_JS.replace('__BASE_URL__', base_url)}
</body>
</html>"""
