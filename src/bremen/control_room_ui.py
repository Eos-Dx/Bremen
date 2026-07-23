"""Bremen Control Room — product-grade demo.

Owns GET /demo/control-room and its deep links.
Three-column layout with model info, container catalog, pipeline,
job history, and live events.

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
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg-page);color:var(--text-primary);line-height:1.5;-webkit-font-smoothing:antialiased;overflow-x:hidden}
.cr-page{max-width:1440px;margin:0 auto;padding:var(--sp-32);min-height:100vh;display:flex;flex-direction:column}
.cr-header{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-16) 0;border-bottom:1px solid var(--border);margin-bottom:var(--sp-24);flex-wrap:wrap;gap:var(--sp-12)}
.cr-brand{font-size:var(--fs-22);font-weight:600;color:var(--text-primary)}
.cr-question{font-size:var(--fs-14);color:var(--text-secondary);margin-top:var(--sp-4)}
.cr-header-right{display:flex;align-items:center;gap:var(--sp-12);flex-wrap:wrap}
.cr-model-link{font-size:var(--fs-13);color:var(--accent);text-decoration:none}
.cr-model-link:hover{text-decoration:underline}
.cr-badge{display:inline-flex;align-items:center;gap:var(--sp-4);padding:2px 10px;border-radius:var(--radius-pill);font-size:var(--fs-11);font-weight:600}
.cr-badge.available{background:var(--tint-accent);color:var(--status-available)}
.cr-badge.unavailable{background:var(--tint-pending);color:var(--status-pending)}
.cr-badge.not_configured{background:var(--tint-error);color:var(--status-error)}
.cr-badge.pending{background:var(--tint-pending);color:var(--status-pending)}
.cr-main{display:flex;gap:var(--sp-24);flex:1;min-height:0}
.cr-left{width:320px;flex-shrink:0;display:flex;flex-direction:column;gap:var(--sp-16)}
.cr-center{flex:1;min-width:480px;display:flex;flex-direction:column;gap:var(--sp-16)}
.cr-right{width:360px;flex-shrink:0;display:flex;flex-direction:column;gap:var(--sp-16)}
.cr-card{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card);box-shadow:var(--shadow-card);padding:var(--sp-16)}
.cr-card-title{font-size:var(--fs-14);font-weight:600;color:var(--text-primary);margin-bottom:var(--sp-12);text-transform:uppercase;letter-spacing:0.3px}
.cr-card-rail{border-left:3px solid var(--border)}
.cr-field-table{width:100%}
.cr-field-row{display:flex;padding:var(--sp-6) 0;font-size:var(--fs-13);border-bottom:1px solid var(--border)}
.cr-field-row:last-child{border-bottom:none}
.cr-field-label{width:160px;flex-shrink:0;color:var(--text-secondary);padding-right:var(--sp-16)}
.cr-field-value{flex:1;color:var(--text-primary);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:monospace;font-size:var(--fs-11)}
.cr-field-value[title]:hover{overflow:visible;white-space:normal;word-break:break-all}
.cr-container-list{list-style:none;margin:0;padding:0;max-height:240px;overflow-y:auto}
.cr-container-item{padding:var(--sp-8) var(--sp-12);cursor:pointer;border-bottom:1px solid var(--border);transition:background 150ms;display:flex;flex-direction:column;gap:var(--sp-2);border-left:2px solid transparent}
.cr-container-item:hover{background:var(--tint-accent)}
.cr-container-item.selected{border-left-color:var(--accent);background:var(--tint-accent);border:2px solid var(--accent);border-left-width:2px;padding:calc(var(--sp-8) - 1px) calc(var(--sp-12) - 1px)}
.cr-container-name{font-size:var(--fs-13);color:var(--text-primary);font-weight:500}
.cr-container-meta{font-size:var(--fs-11);color:var(--text-secondary)}
.cr-catalog-status{font-size:var(--fs-11);color:var(--text-secondary);margin-bottom:var(--sp-8)}
.cr-source-status{font-size:var(--fs-11);color:var(--text-secondary);margin-top:var(--sp-4);min-height:16px}
.cr-source-status.stale{color:var(--status-pending)}
.cr-upload-area{padding-top:var(--sp-12);border-top:1px solid var(--border);margin-top:var(--sp-8)}
.cr-upload-label{font-size:var(--fs-13);color:var(--text-secondary);margin-bottom:var(--sp-8)}
.btn-primary{background:var(--accent);color:#FFFFFF;border:none;border-radius:var(--radius-card);padding:12px 32px;font-size:var(--fs-17);font-weight:600;cursor:pointer;transition:background 150ms;width:100%}
.btn-primary:hover:not(:disabled){background:var(--accent)}
.btn-primary:disabled{background:var(--status-unconfigured);cursor:not-allowed}
.btn-primary:focus{outline:3px solid var(--accent);outline-offset:2px}
.btn-secondary{background:var(--bg-surface);color:var(--accent);border:1px solid var(--accent);border-radius:var(--radius-card);padding:8px 16px;font-size:var(--fs-13);font-weight:600;cursor:pointer;transition:background 150ms}
.btn-secondary:hover{background:var(--tint-accent)}
.btn-secondary:focus{outline:3px solid var(--accent);outline-offset:2px}
.btn-small{background:none;color:var(--text-secondary);border:1px solid var(--border);border-radius:var(--radius-pill);padding:4px 12px;font-size:var(--fs-11);cursor:pointer;transition:background 150ms}
.btn-small:hover{background:var(--tint-accent);color:var(--accent)}
.btn-small.active{background:var(--tint-accent);color:var(--accent);border-color:var(--accent)}
.cr-pipeline{display:flex;flex-direction:column;gap:0}
.cr-stage{display:flex;align-items:center;gap:var(--sp-12);padding:var(--sp-10) var(--sp-16);border-left:3px solid var(--border);transition:border-color 300ms,background 300ms;font-size:var(--fs-13)}
.cr-stage.active{border-left-color:var(--accent);background:var(--tint-accent)}
.cr-stage.completed{border-left-color:var(--status-available)}
.cr-stage.failed{border-left-color:var(--status-error);background:var(--tint-error)}
.cr-stage-icon{width:16px;text-align:center;font-size:var(--fs-13);flex-shrink:0}
.cr-stage-icon.active{color:var(--accent)}
.cr-stage-icon.completed{color:var(--status-available)}
.cr-stage-icon.failed{color:var(--status-error)}
.cr-stage-icon.pending{color:var(--border)}
.cr-stage-label{flex:1;color:var(--text-primary)}
.cr-stage-dur{font-size:var(--fs-11);color:var(--text-secondary);font-family:monospace}
.cr-decision-card{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card);box-shadow:var(--shadow-card);padding:var(--sp-20) var(--sp-24);border-left:3px solid var(--accent);margin-top:var(--sp-8)}
.cr-decision-headline{font-size:var(--fs-22);font-weight:600;color:var(--text-primary);margin-bottom:var(--sp-4)}
.cr-decision-code{font-size:var(--fs-13);color:var(--text-secondary);font-family:monospace;margin-bottom:var(--sp-12)}
.cr-decision-score{display:flex;align-items:center;gap:var(--sp-12);margin-bottom:var(--sp-8)}
.cr-score-bar{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden;position:relative}
.cr-score-fill{height:100%;background:var(--accent);border-radius:4px;transition:width 500ms}
.cr-score-threshold{position:absolute;top:-2px;width:2px;height:12px;background:var(--status-error)}
.cr-score-label{font-size:var(--fs-13);color:var(--text-secondary);white-space:nowrap}
.cr-decision-meta{font-size:var(--fs-11);color:var(--text-secondary);margin-top:var(--sp-4)}
.cr-report-link{display:inline-block;padding:8px 20px;background:var(--accent);color:#FFFFFF;border:none;border-radius:var(--radius-card);font-size:var(--fs-14);font-weight:600;text-decoration:none;cursor:pointer;margin-top:var(--sp-12);transition:background 150ms}
.cr-report-link:hover{background:var(--accent)}
.cr-history-list{max-height:280px;overflow-y:auto}
.cr-history-item{padding:var(--sp-8) var(--sp-12);cursor:pointer;border-bottom:1px solid var(--border);transition:background 150ms;border-left:2px solid transparent;font-size:var(--fs-13)}
.cr-history-item:hover{background:var(--tint-accent)}
.cr-history-item.completed{border-left-color:var(--status-available)}
.cr-history-item.failed{border-left-color:var(--status-error)}
.cr-history-item.running{border-left-color:var(--accent)}
.cr-history-header{display:flex;align-items:center;gap:var(--sp-6);margin-bottom:var(--sp-2)}
.cr-history-id{color:var(--text-secondary);font-family:monospace;font-size:var(--fs-11)}
.cr-history-time{color:var(--text-secondary);font-size:var(--fs-11);margin-left:auto}
.cr-history-detail{color:var(--text-primary);font-weight:500;font-size:var(--fs-13)}
.cr-history-meta{color:var(--text-secondary);font-size:var(--fs-11)}
.cr-event-panel{display:flex;flex-direction:column;flex:1;min-height:0}
.cr-event-empty{height:120px;display:flex;align-items:center;justify-content:center;font-size:var(--fs-13);color:var(--text-secondary);text-align:center;padding:var(--sp-16)}
.cr-event-list{flex:1;overflow-y:auto;min-height:0}
.cr-event-row{display:flex;align-items:center;gap:var(--sp-8);padding:var(--sp-6) var(--sp-8);margin:1px 0;border-left:2px solid var(--border);font-size:var(--fs-11);font-family:monospace;transition:background 150ms}
.cr-event-row.completed{border-left-color:var(--status-available);background:var(--tint-accent)}
.cr-event-row.failed{border-left-color:var(--status-error);background:var(--tint-error)}
.cr-event-row.active{border-left-color:var(--accent);background:var(--tint-accent)}
.cr-event-seq{color:var(--text-secondary);width:24px;flex-shrink:0}
.cr-event-type{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary)}
.cr-event-status{font-weight:600;font-size:var(--fs-11)}
.cr-event-status.completed{color:var(--status-available)}
.cr-event-status.failed{color:var(--status-error)}
.cr-event-status.active{color:var(--accent)}
.cr-event-time{color:var(--text-secondary);flex-shrink:0}
.cr-event-dur{color:var(--text-secondary);font-size:var(--fs-11);flex-shrink:0}
.cr-event-actions{display:flex;gap:var(--sp-8);padding:var(--sp-8) 0;border-top:1px solid var(--border);flex-wrap:wrap}
.cr-empty{color:var(--text-secondary);font-size:var(--fs-13);text-align:center;padding:var(--sp-16)}
.cr-status-bar{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-8) 0;border-top:1px solid var(--border);margin-top:var(--sp-16);font-size:var(--fs-11);color:var(--text-secondary)}
.cr-status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:var(--sp-4)}
.cr-status-dot.live{background:var(--status-available)}
.cr-status-dot.connecting{background:var(--status-pending)}
.cr-status-dot.disconnected{background:var(--status-error)}
.cr-status-dot.idle{background:var(--border)}
.cr-footer{text-align:center;padding:var(--sp-16) 0;font-size:var(--fs-11);color:var(--text-secondary);border-top:1px solid var(--border);margin-top:var(--sp-24)}
.cr-footer a{color:var(--accent);text-decoration:none}
.hidden{display:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
.cr-status-dot.connecting{animation:pulse 1.5s infinite}
@media(prefers-reduced-motion:reduce){.cr-status-dot.connecting{animation:none}.cr-score-fill{transition:none}}
@media(max-width:1024px){.cr-main{flex-direction:column}.cr-left{width:100%}.cr-center{min-width:0}.cr-right{width:100%}.cr-page{padding:var(--sp-16)}}
@media(max-width:768px){.cr-page{padding:var(--sp-12)}.cr-header{flex-direction:column;align-items:flex-start}}
"""

_JS = r"""
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
var isSubmitting=false;
var selectedSource=null;
var selectedModelId=null;
var selectedModelWorkflowId='bremen';
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
  var params=new URLSearchParams(window.location.search);
  var urlModelId=params.get('model_id');
  var urlWorkflowId=params.get('workflow_id');
  if(urlModelId){selectedModelId=urlModelId}
  if(urlWorkflowId){selectedModelWorkflowId=urlWorkflowId}
  loadReadiness();
  loadContainerCatalog();
  loadModelCatalog();
  loadJobHistory();
  var fileInput=document.getElementById('cr-file-input');
  if(fileInput){
    fileInput.addEventListener('change',handleFileSelect);
  }
  var uploadArea=document.getElementById('cr-upload-area');
  if(uploadArea&&uploadArea.dataset.uploadEnabled==='false'){
    uploadArea.classList.add('hidden');
  }
}

function loadContainerCatalog(){
  var list=document.getElementById('cr-container-list');
  var status=document.getElementById('cr-catalog-status');
  fetch(baseUrl+'/demo/api/h5/containers')
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.storage==='not_configured'){
        if(status){status.textContent='H5 storage not configured.';status.className='cr-badge not_configured'}
        if(list){list.innerHTML='<li class="cr-empty">H5 storage not configured.</li>'}
        updateReadiness();
        return;
      }
      if(data.storage==='list_failed'){
        if(status){status.textContent='Catalog unavailable.';status.className='cr-badge unavailable'}
        if(list){list.innerHTML='<li class="cr-empty">Catalog unavailable.<br><button class="btn-small" onclick="loadContainerCatalog()" style="margin-top:8px">Retry</button></li>'}
        updateReadiness();
        return;
      }
      var containers=data.containers||[];
      if(containers.length===0){
        if(status){status.textContent='No containers found.';status.className='cr-badge unavailable'}
        if(list){list.innerHTML='<li class="cr-empty">No H5 containers found.</li>'}
        updateReadiness();
        return;
      }
      if(status){status.textContent=containers.length+' container(s)';status.className='cr-badge available'}
      var html='';
      var prevSelectedId=selectedSource&&selectedSource.type==='container'?selectedSource.id:null;
      var prevSelectedStillAvailable=false;
      containers.forEach(function(c){
        var name=c.display_name||c.source_id||'unknown';
        var size=c.size_bytes||0;
        var sizeLabel=size>1048576?(size/1048576).toFixed(1)+' MB':(size>1024?(size/1024).toFixed(1)+' KB':size+' B');
        var modified=c.last_modified?c.last_modified.substring(0,10):'';
        var sid=c.source_id||'';
        var isPrev=prevSelectedId===sid;
        if(isPrev){prevSelectedStillAvailable=true}
        html+='<li class="cr-container-item'+(isPrev?' selected':'')+'" data-source-id="'+sid+'" data-sname="'+name.replace(/\'/g,'')+'" data-ssize="'+size+'" tabindex="0" role="button" aria-current="'+(isPrev?'true':'false')+'">'+
          '<span class="cr-container-name">'+name+'</span>'+
          '<span class="cr-container-meta">'+sizeLabel+' | '+modified+'</span>'+
          '</li>';
      });
      if(list){list.innerHTML=html}
      var items=document.querySelectorAll('.cr-container-item');
      items.forEach(function(item){
        item.addEventListener('click',function(){
          var sid=item.getAttribute('data-source-id');
          var name=item.getAttribute('data-sname');
          var size=parseInt(item.getAttribute('data-ssize')||'0');
          selectContainer(item,sid,name,size);
        });
        item.addEventListener('keydown',function(e){
          if(e.key==='Enter'||e.key===' '){
            e.preventDefault();
            var sid=item.getAttribute('data-source-id');
            var name=item.getAttribute('data-sname');
            var size=parseInt(item.getAttribute('data-ssize')||'0');
            selectContainer(item,sid,name,size);
          }
        });
      });
      if(prevSelectedId&&!prevSelectedStillAvailable){
        var ss=document.getElementById('cr-source-status');
        if(ss){ss.textContent='Previously selected container is no longer available. Please select another.';ss.className='cr-source-status stale'}
        selectedSource.stale=true;
      }
      updateReadiness();
    }).catch(function(){
      if(status){status.textContent='Catalog unavailable.';status.className='cr-badge unavailable'}
      if(list){list.innerHTML='<li class="cr-empty">Failed to load catalog.<br><button class="btn-small" onclick="loadContainerCatalog()" style="margin-top:8px">Retry</button></li>'}
      updateReadiness();
    });
}

function selectContainer(el,sid,filename,size){
  var items=document.querySelectorAll('.cr-container-item');
  items.forEach(function(i){i.classList.remove('selected');i.setAttribute('aria-current','false')});
  el.classList.add('selected');
  el.setAttribute('aria-current','true');
  selectedSource={type:'container',id:sid,filename:filename,size:size,stale:false};
  document.getElementById('cr-file-input').value='';
  var ss=document.getElementById('cr-source-status');
  if(ss){ss.textContent='Container: '+filename;ss.className='cr-source-status'}
  setState('source_selected');
  updateReadiness();
}

function handleFileSelect(){
  var file=document.getElementById('cr-file-input').files[0];
  if(!file)return;
  var name=file.name.toLowerCase();
  if(!name.endsWith('.h5')&&!name.endsWith('.hdf5')){
    var ss=document.getElementById('cr-source-status');
    if(ss){ss.textContent='Only .h5 and .hdf5 files are accepted.';ss.className='cr-source-status stale'}
    setState('idle');
    return;
  }
  setState('validating');
  var headers=new Headers();
  headers.append('X-H5-Filename',file.name);
  fetch(baseUrl+'/demo/api/stage',{method:'POST',body:file,headers:headers})
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.status==='staged'){
        var items=document.querySelectorAll('.cr-container-item');
        items.forEach(function(i){i.classList.remove('selected');i.setAttribute('aria-current','false')});
        selectedSource={type:'upload',id:data.upload_id,filename:data.filename,size:data.size_bytes,stale:false};
        var ss=document.getElementById('cr-source-status');
        if(ss){ss.textContent='Upload ready: '+data.filename;ss.className='cr-source-status'}
        setState('ready_to_submit');
      }else{
        var ss=document.getElementById('cr-source-status');
        if(ss){ss.textContent='Upload failed: '+data.error;ss.className='cr-source-status stale'}
        setState('idle');
        if(data.error_code==='SOURCE_ERROR'||data.error_code==='MISSING_SOURCE'){
        }else{
          selectedSource=null;
        }
      }
      updateReadiness();
    }).catch(function(){
      var ss=document.getElementById('cr-source-status');
      if(ss){ss.textContent='Upload failed';ss.className='cr-source-status stale'}
      setState('idle');
      updateReadiness();
    });
}

function loadModelCatalog(){
  var info=document.getElementById('cr-model-info');
  fetch(baseUrl+'/demo/api/models')
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.status==='not_configured'){
        if(info){info.innerHTML='<div class="cr-field-row"><div class="cr-field-label">Status</div><div class="cr-field-value" style="white-space:normal">No model configured</div></div>'}
        modelReady=false;
        modelStatus='not_configured';
        selectedModelId=null;
        updateReadiness();
        return;
      }
      var models=data.models||[];
      var availableModels=models.filter(function(m){return m.availability==='available'});
      if(availableModels.length===0){
        if(info){info.innerHTML='<div class="cr-field-row"><div class="cr-field-label">Status</div><div class="cr-field-value" style="white-space:normal">No models available</div></div>'}
        modelReady=false;
        selectedModelId=null;
        updateReadiness();
        return;
      }
      modelReady=true;
      if(availableModels.length===1){
        var m=availableModels[0];
        selectedModelId=m.model_id;
        selectedModelWorkflowId=m.workflow_id||'bremen';
        var html='';
        html+='<div class="cr-field-row"><div class="cr-field-label">Model</div><div class="cr-field-value" title="'+(m.display_name||m.model_id)+'">'+(m.display_name||m.model_id)+'</div></div>';
        html+='<div class="cr-field-row"><div class="cr-field-label">Version</div><div class="cr-field-value" title="'+(m.model_version||'')+'">'+(m.model_version||'')+'</div></div>';
        html+='<div class="cr-field-row"><div class="cr-field-label">Feature schema</div><div class="cr-field-value" title="'+(m.feature_schema_version||'')+'">'+(m.feature_schema_version||'')+'</div></div>';
        html+='<div class="cr-field-row"><div class="cr-field-label">Decision policy</div><div class="cr-field-value" title="'+(m.decision_policy_id||'')+' v'+(m.decision_policy_version||'')+'">'+(m.decision_policy_id||'')+' v'+(m.decision_policy_version||'')+'</div></div>';
        html+='<div class="cr-field-row"><div class="cr-field-label">Status</div><div class="cr-field-value"><span class="cr-badge available">Available</span></div></div>';
        if(info){info.innerHTML=html}
      }else{
        var html='<div class="cr-field-row"><div class="cr-field-label">Model</div><div class="cr-field-value"><select id="cr-model-select" onchange="onModelSelect(this)" style="width:100%;padding:4px 8px;background:var(--bg-surface);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;font-size:var(--fs-11)">';
        availableModels.forEach(function(m){
          var sel=m.model_id===selectedModelId?' selected':'';
          html+='<option value="'+m.model_id+'" data-workflow="'+(m.workflow_id||'bremen')+'"'+sel+'>'+(m.display_name||m.model_id)+'</option>';
        });
        html+='</select></div></div>';
        if(info){info.innerHTML=html}
        if(!selectedModelId&&availableModels.length>0){
          selectedModelId=availableModels[0].model_id;
          selectedModelWorkflowId=availableModels[0].workflow_id||'bremen';
        }
      }
      var tsEl=document.getElementById('cr-catalog-ts');
      if(tsEl&&data.catalog_timestamp){
        tsEl.textContent='Catalog: '+data.catalog_timestamp.substring(0,19).replace('T',' ');
        tsEl.classList.remove('hidden');
      }
      updateReadiness();
    }).catch(function(){
      if(info){info.innerHTML='<div class="cr-field-row"><div class="cr-field-label">Status</div><div class="cr-field-value" style="white-space:normal;color:var(--status-error)">Catalog unavailable</div></div>'}
      modelReady=false;
      updateReadiness();
    });
}

function onModelSelect(sel){
  selectedModelId=sel.value;
  var opt=sel.options[sel.selectedIndex];
  selectedModelWorkflowId=opt.getAttribute('data-workflow')||'bremen';
  updateReadiness();
}

function updateReadiness(){
  var btn=document.getElementById('cr-analyze-btn');
  if(!btn)return;
  var hasValidSource=selectedSource!==null&&selectedSource.id&&!selectedSource.stale;
  var hasValidModel=selectedModelId!==null&&modelReady;
  var notActive=!isSubmitting&&jobState!=='submitting'&&jobState!=='connecting'&&jobState!=='running'&&jobState!=='reconnecting';
  var canSubmit=hasValidSource&&hasValidModel&&notActive;
  btn.disabled=!canSubmit;
  var ss=document.getElementById('cr-source-status');
  if(selectedSource&&selectedSource.stale&&ss){
    ss.textContent='This source is no longer available. Please select another.';
    ss.className='cr-source-status stale';
  }
}

function startAnalysis(){
  if(isSubmitting)return;
  if(!selectedSource||!selectedModelId||!modelReady)return;
  if(selectedSource.stale){
    var ss=document.getElementById('cr-source-status');
    if(ss){ss.textContent='Cannot analyze: the selected source is no longer available.';ss.className='cr-source-status stale'}
    return;
  }
  isSubmitting=true;
  setState('submitting');
  resetPipeline();
  resetEventPanel();
  setConnectionState('connecting');
  updateReadiness();
  var body={workflow_id:selectedModelWorkflowId||'bremen'};
  body.model_id=selectedModelId;
  if(selectedSource.type==='container'){
    body.source_id=selectedSource.id;
  }else if(selectedSource.type==='upload'){
    body.upload_id=selectedSource.id;
  }
  fetch(baseUrl+'/demo/api/jobs',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)
  }).then(function(r){return r.json()}).then(function(data){
    var job=data.job||{};
    var jid=job.job_id||'';
    if(!jid){
      isSubmitting=false;
      updateReadiness();
      if(data.error){
        var ss=document.getElementById('cr-source-status');
        if(ss){ss.textContent='Error: '+data.error;ss.className='cr-source-status stale'}
        setConnectionState('idle');
        setState('failed');
        return;
      }
      setConnectionState('idle');
      setState('ready_to_submit');
      return;
    }
    currentJobId=jid;
    setState('job_created');
    fetchInitialEvents(jid);
    connectSSE(jid);
    loadJobHistory();
  }).catch(function(){
    isSubmitting=false;
    updateReadiness();
    setConnectionState('idle');
    setState('ready_to_submit');
  });
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
    document.getElementById('cr-readiness').innerHTML='<span class="cr-badge unavailable">Cannot reach server</span>';
    setState('unavailable');
  });
}

function renderReadiness(version,ready,status){
  var html='';
  if(ready){html+='<span class="cr-badge available">Model Ready</span>'}
  else if(status==='not_configured'){html+='<span class="cr-badge not_configured">Not Configured</span>'}
  else if(status==='error'){html+='<span class="cr-badge unavailable">Model Error</span>'}
  else{html+='<span class="cr-badge pending">Loading</span>'}
  html+='<span class="cr-badge pending">Certification: pending</span>';
  html+='<span class="cr-badge not_configured">Technical demo only</span>';
  document.getElementById('cr-readiness').innerHTML=html;
}

function setState(newState){
  var valid=['idle','source_selected','validating','ready_to_submit','submitting','job_created','connecting','running','reconnecting','completed','partial_success','failed','unavailable','expired'];
  if(valid.indexOf(newState)===-1)return;
  jobState=newState;
  var label=document.getElementById('cr-status-label');
  if(label){label.textContent=newState.replace(/_/g,' ')}
  var dot=document.getElementById('cr-status-dot');
  if(dot){
    if(newState==='running'){dot.className='cr-status-dot live'}
    else if(newState==='connecting'||newState==='reconnecting'){dot.className='cr-status-dot connecting'}
    else if(newState==='completed'||newState==='ready_to_submit'){dot.className='cr-status-dot live'}
    else if(newState==='failed'){dot.className='cr-status-dot disconnected'}
    else{dot.className='cr-status-dot idle'}
  }
  updateReadiness();
}

function loadJobHistory(){
  fetch(baseUrl+'/demo/api/jobs')
    .then(function(r){return r.json()})
    .then(function(data){
      var jobs=data.jobs||[];
      var list=document.getElementById('cr-job-list');
      if(!list)return;
      if(jobs.length===0){
        list.innerHTML='<div class="cr-empty">No analysis jobs yet.</div>';
        return;
      }
      var html='';
      var MAX_HISTORY=10;
      jobs.slice(0,MAX_HISTORY).forEach(function(j){
        var status=j.overall_status||'unknown';
        var ts=j.created_at?j.created_at.substring(11,19):'';
        var decision=j.decision_display_name||j.triage_recommendation||'';
        var model=j.model_id||'';
        var reportAvail=j.report_available?'&#128196; ':'';
        html+='<div class="cr-history-item '+status+'" onclick="openJob(\''+j.job_id+'\')">'+
          '<div class="cr-history-header"><span class="cr-history-id">'+j.job_id.substring(0,8)+'</span>'+
          '<span class="cr-history-time">'+ts+'</span></div>'+
          '<div class="cr-history-detail">'+reportAvail+(decision?decision:(status==='completed'?'Completed':status))+'</div>'+
          '<div class="cr-history-meta">'+(model?'Model: '+model.substring(0,16):'')+'</div>'+
          '</div>';
      });
      list.innerHTML=html;
    }).catch(function(){});
}

function openJob(jobId){
  window.location.href=baseUrl+'/demo/report/'+jobId;
}

function fetchInitialEvents(jobId){
  fetch(baseUrl+'/demo/api/jobs/'+jobId+'/events')
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.events){data.events.forEach(function(ev){processEvent(ev)})}
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
    isSubmitting=false;
    updateReadiness();
    fetchDecision(jobId);
    if(eventSource){eventSource.close();eventSource=null}
    setState('completed');
    loadJobHistory();
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
    el.className='cr-stage failed';
    var icon=el.querySelector('.cr-stage-icon');
    if(icon){icon.textContent='\\u2717';icon.className='cr-stage-icon failed'}
  }else if(status==='completed'){
    el.className='cr-stage completed';
    var icon=el.querySelector('.cr-stage-icon');
    if(icon){icon.textContent='\\u2713';icon.className='cr-stage-icon completed'}
  }else if(status==='started'||status==='resolved'){
    el.className='cr-stage active';
    var icon=el.querySelector('.cr-stage-icon');
    if(icon){icon.textContent='\\u25CF';icon.className='cr-stage-icon active'}
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
  else if(status==='started'||status==='resolved')cls+=' active';
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
  while(panel.children.length>MAX_EVENTS){panel.removeChild(panel.firstChild)}
  if(autoScroll){panel.scrollTop=panel.scrollHeight}
}

function resetPipeline(){
  var stages=document.querySelectorAll('.cr-stage');
  stages.forEach(function(s){
    s.className='cr-stage';
    var icon=s.querySelector('.cr-stage-icon');
    if(icon){icon.textContent='\\u25CF';icon.className='cr-stage-icon pending'}
    var dur=s.querySelector('.cr-stage-dur');
    if(dur){dur.textContent=''}
  });
}

function resetEventPanel(){
  var panel=document.getElementById('cr-event-list');
  if(panel){panel.innerHTML=''}
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
      var html='<div class="cr-decision-headline">'+name+'</div>';
      html+='<div class="cr-decision-code">'+code+'</div>';
      if(prob!==null&&thresh!==null){
        var pct=Math.min(100,Math.max(0,prob*100));
        var threshPct=Math.min(100,Math.max(0,thresh*100));
        html+='<div class="cr-decision-score"><div class="cr-score-bar"><div class="cr-score-fill" style="width:'+pct+'%"></div><div class="cr-score-threshold" style="left:'+threshPct+'%"></div></div><span class="cr-score-label">Score: '+prob.toFixed(3)+'</span></div>';
      }
      html+='<div class="cr-decision-meta">Policy: '+policy+'</div>';
      html+='<span class="cr-badge pending">Certification: pending</span>';
      html+='<span class="cr-badge not_configured" style="margin-left:4px">Technical demo only</span>';
      html+='<br><a class="cr-report-link" href="'+baseUrl+'/demo/report/'+jobId+'" target="_blank" rel="noopener">Open report</a>';
      card.innerHTML=html;
      card.classList.remove('hidden');
    }).catch(function(){});
}

function toggleAutoScroll(){
  autoScroll=!autoScroll;
  var btn=document.getElementById('cr-autoscroll-btn');
  if(btn){btn.textContent=autoScroll?'Pause':'Follow';btn.className='btn-small'+(autoScroll?' active':'')}
}

function filterEvents(filter){
  var allBtn=document.getElementById('cr-filter-all');
  var compBtn=document.getElementById('cr-filter-completed');
  var failBtn=document.getElementById('cr-filter-failed');
  if(allBtn){allBtn.className='btn-small'+(filter==='all'?' active':'');allBtn.setAttribute('aria-pressed',filter==='all'?'true':'false')}
  if(compBtn){compBtn.className='btn-small'+(filter==='completed'?' active':'');compBtn.setAttribute('aria-pressed',filter==='completed'?'true':'false')}
  if(failBtn){failBtn.className='btn-small'+(filter==='failed'?' active':'');failBtn.setAttribute('aria-pressed',filter==='failed'?'true':'false')}
  var rows=document.querySelectorAll('.cr-event-row');
  rows.forEach(function(r){
    if(filter==='all'){r.classList.remove('hidden')}
    else if(filter==='completed'&&r.classList.contains('completed')){r.classList.remove('hidden')}
    else if(filter==='failed'&&r.classList.contains('failed')){r.classList.remove('hidden')}
    else{r.classList.add('hidden')}
  });
}

window.loadContainerCatalog=loadContainerCatalog;
window.selectContainer=selectContainer;
window.handleFileSelect=handleFileSelect;
window.loadModelCatalog=loadModelCatalog;
window.onModelSelect=onModelSelect;
window.updateReadiness=updateReadiness;
window.startAnalysis=startAnalysis;
window.loadJobHistory=loadJobHistory;
window.openJob=openJob;
window.toggleAutoScroll=toggleAutoScroll;
window.filterEvents=filterEvents;

init();
})();
</script>
"""


def build_control_room_page(
    base_url: str = "http://localhost:8000",
    request_id: str = "",
) -> str:
    """Build the Bremen Control Room HTML page.

    Parameters
    ----------
    base_url : Base URL of the service.
    request_id : Request ID for correlation.

    Returns
    -------
    A complete HTML5 document as a string.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Control Room — MRI Triage Decision Support</title>
<style>{_CSS}</style>
</head>
<body>
<div class="cr-page">
  <div class="cr-header">
    <div>
      <div class="cr-brand">Bremen</div>
      <div class="cr-question">Should the patient continue to MRI?</div>
    </div>
    <div class="cr-header-right">
      <a href="/demo" class="cr-model-link" id="cr-model-link">Change model</a>
      <div class="cr-badges" id="cr-readiness">
        <span class="cr-badge pending">Checking...</span>
      </div>
    </div>
  </div>

  <div class="cr-main">
    <!-- Left column: 320px -->
    <div class="cr-left">
      <div class="cr-card">
        <div class="cr-card-title">Model</div>
        <div class="cr-field-table" id="cr-model-info">
          <div class="cr-field-row"><div class="cr-field-label">Status</div><div class="cr-field-value" style="white-space:normal">Loading...</div></div>
        </div>
      </div>

      <div class="cr-card">
        <div class="cr-card-title">Container Catalog</div>
        <div id="cr-catalog-status" class="cr-catalog-status">Loading...</div>
        <ul class="cr-container-list" id="cr-container-list" role="list" aria-label="Available containers">
          <li class="cr-empty">Loading containers...</li>
        </ul>
        <div style="margin-top:var(--sp-8)">
          <button class="btn-small" onclick="loadContainerCatalog()" style="width:100%">Refresh Catalog</button>
        </div>
      </div>

      <div class="cr-card">
        <div class="cr-card-title">Source</div>
        <div class="cr-upload-area" id="cr-upload-area">
          <div class="cr-upload-label">Upload a new H5 file for analysis</div>
          <input type="file" id="cr-file-input" accept=".h5,.hdf5" style="display:none">
          <button class="btn-secondary" onclick="document.getElementById('cr-file-input').click()" style="width:100%;margin-bottom:var(--sp-8)">Upload New H5 File</button>
          <p id="cr-source-status" class="cr-source-status">No source selected</p>
        </div>
      </div>

      <button class="btn-primary" id="cr-analyze-btn" onclick="startAnalysis()" disabled aria-label="Start analysis">Analyze</button>
    </div>

    <!-- Center column: flexible -->
    <div class="cr-center">
      <div class="cr-card cr-card-rail">
        <div class="cr-card-title">Execution Pipeline</div>
        <div class="cr-pipeline" role="list" aria-label="Execution stages">
          <div class="cr-stage" id="stage-input">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Input accepted</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-source">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Source validated</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-xrd">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Canonical XRD created</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-workflow">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Bremen workflow resolved</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-artifact">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Model artifact prepared</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-features">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Feature contract validated</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-inference">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Inference completed</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-decision">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Decision policy applied</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-report">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Report generated</span>
            <span class="cr-stage-dur"></span>
          </div>
          <div class="cr-stage" id="stage-complete">
            <span class="cr-stage-icon pending">&#9679;</span>
            <span class="cr-stage-label">Analysis complete</span>
            <span class="cr-stage-dur"></span>
          </div>
        </div>
      </div>

      <div class="cr-decision-card hidden" id="cr-decision-card"></div>
    </div>

    <!-- Right column: 360px -->
    <div class="cr-right">
      <div class="cr-card">
        <div class="cr-card-title">Job History</div>
        <div class="cr-history-list" id="cr-job-list">
          <div class="cr-empty">Loading job history...</div>
        </div>
      </div>

      <div class="cr-card" style="flex:1;display:flex;flex-direction:column;min-height:0">
        <div class="cr-card-title">Live Events <span id="cr-catalog-ts" class="hidden" style="font-weight:400;font-size:var(--fs-11);color:var(--text-secondary);text-transform:none;letter-spacing:0">Catalog: loading</span></div>
        <div class="cr-event-panel">
          <div class="cr-event-empty" id="cr-event-empty">Analysis events will appear here</div>
          <div class="cr-event-list" id="cr-event-list" role="log" aria-live="polite" aria-atomic="false"></div>
        </div>
        <div class="cr-event-actions">
          <button class="btn-small active" id="cr-filter-all" onclick="filterEvents('all')" aria-pressed="true">All</button>
          <button class="btn-small" id="cr-filter-completed" onclick="filterEvents('completed')" aria-pressed="false">Completed</button>
          <button class="btn-small" id="cr-filter-failed" onclick="filterEvents('failed')" aria-pressed="false">Failed</button>
          <button class="btn-small active" id="cr-autoscroll-btn" onclick="toggleAutoScroll()" style="margin-left:auto">Pause</button>
        </div>
      </div>
    </div>
  </div>

  <div class="cr-status-bar">
    <span><span class="cr-status-dot idle" id="cr-status-dot"></span><span id="cr-status-label">Idle</span></span>
    <span><a href="/demo/workspace" style="color:var(--accent);text-decoration:none">Workspace</a> &middot; Technical demo only</span>
  </div>

  <div class="cr-footer">
    Bremen — MRI triage decision support. Not clinically validated.
    Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.
  </div>
</div>
{_JS.replace("__BASE_URL__", base_url)}
</body>
</html>"""
