"""Bremen Start page — model selection gateway.

Owns GET /demo. Loads the model catalog from GET /demo/api/models
and renders real configured models. Selected model_id is carried
to the Control Room URL.

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
.start-page{max-width:1440px;margin:0 auto;padding:var(--sp-32);min-height:100vh;display:flex;flex-direction:column}
.start-header{display:flex;align-items:center;justify-content:space-between;padding:var(--sp-24) 0;border-bottom:1px solid var(--border);margin-bottom:var(--sp-48);flex-wrap:wrap;gap:var(--sp-12)}
.start-brand{font-size:var(--fs-22);font-weight:600;color:var(--text-primary)}
.start-question{font-size:var(--fs-14);color:var(--text-secondary);margin-top:var(--sp-4)}
.start-content{flex:1;max-width:720px;margin:0 auto;width:100%}
.start-title{font-size:var(--fs-32);font-weight:700;margin-bottom:var(--sp-8);color:var(--text-primary)}
.start-subtitle{font-size:var(--fs-14);color:var(--text-secondary);margin-bottom:var(--sp-32);line-height:1.6}
.model-grid{display:flex;flex-direction:column;gap:var(--sp-12);margin-bottom:var(--sp-32)}
.model-card{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card);padding:var(--sp-16) var(--sp-24);cursor:pointer;transition:border-color 150ms,box-shadow 150ms;position:relative;display:flex;align-items:flex-start;gap:var(--sp-16)}
.model-card:hover{border-color:var(--accent);box-shadow:var(--shadow-card)}
.model-card.selected{border:2px solid var(--accent);padding:calc(var(--sp-16) - 1px) calc(var(--sp-24) - 1px)}
.model-card.disabled{opacity:0.5;cursor:not-allowed}
.model-card.disabled:hover{border-color:var(--border);box-shadow:none}
.model-card.disabled .model-status-rail{opacity:1}
.model-radio{width:20px;height:20px;border:2px solid var(--border);border-radius:50%;flex-shrink:0;margin-top:2px;display:flex;align-items:center;justify-content:center;transition:border-color 150ms}
.model-card.selected .model-radio{border-color:var(--accent)}
.model-radio-dot{width:10px;height:10px;border-radius:50%;background:var(--accent);opacity:0;transition:opacity 150ms}
.model-card.selected .model-radio-dot{opacity:1}
.model-card.disabled .model-radio{border-color:var(--border)}
.model-card.disabled .model-radio-dot{opacity:0}
.model-info{flex:1;min-width:0}
.model-name{font-size:var(--fs-17);font-weight:600;color:var(--text-primary);margin-bottom:var(--sp-4)}
.model-meta{font-size:var(--fs-13);color:var(--text-secondary);margin-bottom:var(--sp-4)}
.model-detail{font-size:var(--fs-11);color:var(--text-secondary);font-family:monospace}
.model-status-rail{display:inline-flex;align-items:center;gap:var(--sp-4);padding:2px 10px;border-radius:var(--radius-pill);font-size:var(--fs-11);font-weight:600}
.model-status-rail.available{background:var(--tint-accent);color:var(--status-available)}
.model-status-rail.unavailable{background:var(--tint-pending);color:var(--status-pending)}
.model-status-rail.not_configured{background:var(--tint-error);color:var(--status-error)}
.model-reason{font-size:var(--fs-13);color:var(--status-pending);margin-top:var(--sp-4)}
.start-actions{display:flex;gap:var(--sp-12);align-items:center;margin-top:var(--sp-8)}
.btn-primary{background:var(--accent);color:#FFFFFF;border:none;border-radius:var(--radius-card);padding:12px 32px;font-size:var(--fs-17);font-weight:600;cursor:pointer;transition:background 150ms}
.btn-primary:hover:not(:disabled){background:var(--accent)}
.btn-primary:disabled{background:var(--status-unconfigured);cursor:not-allowed}
.btn-primary:focus{outline:3px solid var(--accent);outline-offset:2px}
.start-empty{text-align:center;padding:var(--sp-48) var(--sp-24);background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card)}
.start-empty-title{font-size:var(--fs-17);font-weight:600;color:var(--text-primary);margin-bottom:var(--sp-8)}
.start-empty-text{font-size:var(--fs-14);color:var(--text-secondary);margin-bottom:var(--sp-16)}
.start-footer{text-align:center;padding:var(--sp-24) 0;font-size:var(--fs-13);color:var(--text-secondary);border-top:1px solid var(--border);margin-top:var(--sp-48)}
.start-footer a{color:var(--accent);text-decoration:none}
.start-footer a:hover{text-decoration:underline}
@media(max-width:768px){.start-page{padding:var(--sp-12)}.start-header{margin-bottom:var(--sp-24)}.start-content{max-width:100%}.start-title{font-size:22px}}
"""

_JS = r"""
<script>
(function(){
var baseUrl='__BASE_URL__';

function init(){
  loadModelCatalog();
}

function loadModelCatalog(){
  var grid=document.getElementById('model-grid');
  var actions=document.getElementById('start-actions');
  fetch(baseUrl+'/demo/api/models')
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.status==='not_configured'||!data.models||data.models.length===0){
        grid.innerHTML='<div class="start-empty"><div class="start-empty-title">No models configured</div><div class="start-empty-text">A Bremen model must be configured by the deployment operator before analysis can begin.</div></div>';
        var btn=document.getElementById('start-cta');
        if(btn)btn.disabled=true;
        return;
      }
      var html='';
      var availableModels=data.models.filter(function(m){return m.availability==='available'});
      var hasAvailable=availableModels.length>0;
      data.models.forEach(function(m){
        var isAvail=m.availability==='available';
        var isDisabled=!isAvail?' disabled':'';
        var statusLabel=m.availability==='available'?'Available':m.availability==='unavailable'?'Unavailable':'Not configured';
        var statusClass=m.availability;
        html+='<div class="model-card'+isDisabled+'" data-model-id="'+m.model_id+'" data-workflow="'+(m.workflow_id||'bremen')+'" role="radio" aria-checked="false" tabindex="0">';
        html+='<div class="model-radio"><div class="model-radio-dot"></div></div>';
        html+='<div class="model-info">';
        html+='<div class="model-name">'+(m.display_name||m.model_id)+'</div>';
        html+='<div class="model-meta">Version: '+(m.model_version||'unknown')+'</div>';
        html+='<div class="model-detail">Feature schema: '+(m.feature_schema_version||'v0.1')+' &middot; Decision policy: '+(m.decision_policy_id||'bremen_mri_continuation_threshold')+' v'+(m.decision_policy_version||'0.1.0')+'</div>';
        html+='<div class="model-status-rail '+statusClass+'">'+statusLabel+'</div>';
        if(!isAvail){
          html+='<div class="model-reason">This model is not currently available for analysis.</div>';
        }
        html+='</div></div>';
      });
      grid.innerHTML=html;

      // Attach event listeners
      var cards=grid.querySelectorAll('.model-card:not(.disabled)');
      cards.forEach(function(card){
        card.addEventListener('click',function(){selectModel(card);});
        card.addEventListener('keydown',function(e){
          if(e.key==='Enter'||e.key===' '){
            e.preventDefault();
            selectModel(card);
          }
        });
      });

      // Auto-select if exactly one available
      if(availableModels.length===1){
        var autoCard=grid.querySelector('.model-card:not(.disabled)');
        if(autoCard)selectModel(autoCard);
      }

      // Enable/disable CTA
      updateCTA();
    }).catch(function(){
      grid.innerHTML='<div class="start-empty"><div class="start-empty-title">Model catalog unavailable</div><div class="start-empty-text">Could not load the model catalog. Please check that the server is running.<br><button class="btn-primary" onclick="loadModelCatalog()" style="margin-top:12px">Retry</button></div></div>';
    });
}

function selectModel(card){
  var cards=document.querySelectorAll('.model-card');
  cards.forEach(function(c){c.classList.remove('selected');c.setAttribute('aria-checked','false');});
  card.classList.add('selected');
  card.setAttribute('aria-checked','true');
  updateCTA();
}

function updateCTA(){
  var selected=document.querySelector('.model-card.selected');
  var btn=document.getElementById('start-cta');
  if(!btn)return;
  if(selected){
    btn.disabled=false;
  }else{
    btn.disabled=true;
  }
}

function startAnalysis(){
  var selected=document.querySelector('.model-card.selected');
  if(!selected)return;
  var modelId=selected.getAttribute('data-model-id');
  var workflowId=selected.getAttribute('data-workflow')||'bremen';
  window.location.href=baseUrl+'/demo/control-room?workflow_id='+encodeURIComponent(workflowId)+'&model_id='+encodeURIComponent(modelId);
}

window.loadModelCatalog=loadModelCatalog;
window.selectModel=selectModel;
window.updateCTA=updateCTA;
window.startAnalysis=startAnalysis;

init();
})();
</script>
"""


def build_start_page(base_url: str = "http://localhost:8000") -> str:
    """Build the Bremen Start page HTML.

    Parameters
    ----------
    base_url : Base URL of the service.

    Returns
    -------
    A complete HTML5 document as a string.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen — MRI Triage Decision Support</title>
<style>{_CSS}</style>
</head>
<body>
<div class="start-page">
  <div class="start-header">
    <div>
      <div class="start-brand">Bremen</div>
      <div class="start-question">Should the patient continue to MRI?</div>
    </div>
  </div>

  <div class="start-content">
    <h1 class="start-title">Select a model to begin</h1>
    <p class="start-subtitle">
      Choose a Bremen model for MRI triage decision support.
      The selected model will be used throughout the analysis.
    </p>

    <div class="model-grid" id="model-grid" role="radiogroup" aria-label="Available models">
      <div class="start-empty">
        <div class="start-empty-title">Loading models...</div>
        <div class="start-empty-text">Fetching available models from the server.</div>
      </div>
    </div>

    <div class="start-actions" id="start-actions">
      <button class="btn-primary" id="start-cta" onclick="startAnalysis()" disabled
        aria-label="Open Control Room with selected model">
        Open Control Room
      </button>
    </div>
  </div>

  <div class="start-footer">
    <p>Bremen — MRI triage decision support. Not clinically validated. Technical demo only.
    <a href="/demo/workspace">Legacy Workspace</a></p>
  </div>
</div>
{_JS.replace("__BASE_URL__", base_url)}
</body>
</html>"""
