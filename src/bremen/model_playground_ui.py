"""Sanitized Bremen demo Model Playground page.

The playground is a self-contained synthetic sandbox inspired by the uploaded
standalone HTML.  It intentionally does not read raw HTML, load model
artifacts, call H5/job/report APIs, or expose production learned parameters.
"""

from __future__ import annotations


_CSS = """
:root {
  --bg-page: #F7F8F8;
  --bg-surface: #FFFFFF;
  --text-primary: #16202A;
  --text-secondary: #5B6570;
  --accent: #1F6F6B;
  --accent-2: #7D6E3F;
  --border: #E3E7E6;
  --risk-low: #2E7D5B;
  --risk-high: #B8894A;
  --tint-accent: #F1F5F4;
  --tint-warn: #FBF3E9;
  --radius-card: 10px;
  --shadow-card: 0 1px 2px rgba(22,32,42,0.04), 0 1px 8px rgba(22,32,42,0.03);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg-page);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
button, input { font: inherit; }
.page { max-width: 1220px; margin: 0 auto; min-height: 100vh; padding: 32px; }
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 0 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}
.brand { font-size: 22px; font-weight: 650; }
.question { color: var(--text-secondary); font-size: 14px; margin-top: 4px; }
.nav { display: flex; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }
.nav a { color: var(--accent); text-decoration: none; font-size: 13px; font-weight: 600; }
.nav a:hover { text-decoration: underline; }
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(310px, .75fr);
  gap: 20px;
  align-items: stretch;
  margin-bottom: 18px;
}
.hero h1 { font-size: 32px; line-height: 1.12; margin: 0 0 10px; }
.lede { color: var(--text-secondary); font-size: 15px; max-width: 760px; }
.notice {
  background: var(--tint-warn);
  border: 1px solid #E8D2AB;
  border-left: 4px solid var(--accent-2);
  border-radius: 0 10px 10px 0;
  padding: 12px 14px;
  color: #5D4720;
  font-size: 13px;
  margin-top: 14px;
}
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 18px;
  min-width: 0;
}
.card h2 { margin: 0 0 8px; font-size: 17px; }
.card p { margin: 0 0 10px; color: var(--text-secondary); font-size: 13px; }
.grid { display: grid; grid-template-columns: 330px minmax(0, 1fr) 330px; gap: 16px; }
.controls { display: grid; gap: 14px; }
.control label { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; font-weight: 700; }
.control input[type="range"] { width: 100%; margin-top: 7px; }
.value { color: var(--accent); font-variant-numeric: tabular-nums; }
.segmented { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.segmented button, .export-btn {
  border: 1px solid var(--border);
  background: #FFFFFF;
  color: var(--text-primary);
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 12px;
  font-weight: 700;
}
.segmented button.active { background: var(--accent); border-color: var(--accent); color: #FFFFFF; }
.export-btn[disabled] { color: var(--text-secondary); background: #F1F3F3; cursor: not-allowed; }
.score { font-size: 54px; font-weight: 750; line-height: 1; margin: 8px 0; }
.score.low { color: var(--risk-low); }
.score.high { color: var(--risk-high); }
.meter { height: 16px; border-radius: 999px; background: #E7ECEB; overflow: hidden; }
.fill { height: 100%; width: 0; background: var(--accent); transition: width 150ms; }
.verdict {
  display: inline-block;
  margin-top: 10px;
  border-radius: 999px;
  padding: 7px 10px;
  background: var(--tint-accent);
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
}
.chart { height: 260px; border: 1px solid var(--border); border-radius: 10px; background: #FBFCFD; }
.bars { display: grid; gap: 8px; margin-top: 10px; }
.bar-row { display: grid; grid-template-columns: 110px minmax(0, 1fr) 44px; gap: 8px; align-items: center; font-size: 12px; }
.track { height: 10px; border-radius: 999px; background: #E7ECEB; position: relative; overflow: hidden; }
.track span { position: absolute; inset: 0 auto 0 50%; width: 0; background: var(--accent); }
.track span.neg { right: 50%; left: auto; background: var(--accent-2); }
.footer { margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--border); color: var(--text-secondary); font-size: 12px; }
@media (max-width: 1050px) { .grid, .hero { grid-template-columns: 1fr; } }
@media (max-width: 720px) { .page { padding: 18px; } .header { display: grid; } .nav { justify-content: flex-start; } .score { font-size: 42px; } }
"""

_JS = """
<script>
(function(){
var mode = "balanced";
var params = [
  {id:"sym", label:"Symmetry signal", value:0.56, weight:0.46},
  {id:"shape", label:"Profile shape", value:0.48, weight:0.32},
  {id:"snr", label:"Signal quality", value:0.70, weight:-0.18},
  {id:"consistency", label:"Measurement consistency", value:0.62, weight:-0.24}
];

function $(id){ return document.getElementById(id); }
function sigmoid(x){ return 1 / (1 + Math.exp(-x)); }
function clamp(v){ return Math.max(0, Math.min(1, v)); }

function renderControls(){
  var html = "";
  params.forEach(function(p){
    html += '<div class="control">';
    html += '<label for="'+p.id+'"><span>'+p.label+'</span><span class="value" id="'+p.id+'Val">'+p.value.toFixed(2)+'</span></label>';
    html += '<input id="'+p.id+'" type="range" min="0" max="1" step="0.01" value="'+p.value+'">';
    html += '</div>';
  });
  $("controls").innerHTML = html;
  params.forEach(function(p){
    $(p.id).addEventListener("input", function(ev){
      p.value = Number(ev.target.value);
      render();
    });
  });
}

function score(){
  var bias = mode === "sensitive" ? 0.12 : -0.04;
  var z = bias;
  params.forEach(function(p){ z += (p.value - 0.5) * p.weight; });
  return clamp(sigmoid(z));
}

function setMode(next){
  mode = next;
  $("balanced").className = next === "balanced" ? "active" : "";
  $("sensitive").className = next === "sensitive" ? "active" : "";
  render();
}

function renderChart(s){
  var width = 720, height = 260, pad = 28;
  var points = "";
  for(var i=0;i<44;i++){
    var x = pad + (width - pad * 2) * (i / 43);
    var wave = Math.sin(i * 0.63) * 0.10 + Math.cos(i * 0.21) * 0.06;
    var y = height - pad - (height - pad * 2) * clamp(0.45 + wave + (s - 0.5) * 0.55);
    var color = i % 5 === 0 ? "#7D6E3F" : "#1F6F6B";
    points += '<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="4" fill="'+color+'" opacity=".72"/>';
  }
  $("chart").innerHTML = '<svg viewBox="0 0 '+width+' '+height+'" width="100%" height="100%" role="img" aria-label="Synthetic patient cloud">'
    + '<line x1="'+pad+'" y1="'+(height-pad)+'" x2="'+(width-pad)+'" y2="'+(height-pad)+'" stroke="#D8E0DF"/>'
    + '<line x1="'+pad+'" y1="'+pad+'" x2="'+pad+'" y2="'+(height-pad)+'" stroke="#D8E0DF"/>'
    + '<path d="M '+pad+' '+(height-pad-45)+' C 230 185, 340 80, '+(width-pad)+' 70" fill="none" stroke="#1F6F6B" stroke-width="3" opacity=".35"/>'
    + points + '</svg>';
}

function renderBars(){
  var html = "";
  params.forEach(function(p){
    var contribution = (p.value - 0.5) * p.weight;
    var pct = Math.min(50, Math.abs(contribution) * 120);
    html += '<div class="bar-row"><span>'+p.label+'</span><div class="track"><span class="'+(contribution < 0 ? "neg" : "")+'" style="width:'+pct.toFixed(1)+'%"></span></div><b>'+contribution.toFixed(2)+'</b></div>';
  });
  $("bars").innerHTML = html;
}

function render(){
  params.forEach(function(p){
    if($(p.id+"Val")) $(p.id+"Val").textContent = p.value.toFixed(2);
  });
  var s = score();
  $("score").textContent = Math.round(s * 100) + "%";
  $("score").className = s >= 0.55 ? "score high" : "score low";
  $("fill").style.width = Math.round(s * 100) + "%";
  $("verdict").textContent = s >= 0.55 ? "Sandbox output: MRI continuation signal higher" : "Sandbox output: MRI continuation signal lower";
  renderChart(s);
  renderBars();
}

window.addEventListener("DOMContentLoaded", function(){
  renderControls();
  $("balanced").addEventListener("click", function(){ setMode("balanced"); });
  $("sensitive").addEventListener("click", function(){ setMode("sensitive"); });
  render();
});
})();
</script>
"""


def build_model_playground_page() -> str:
    """Build a self-contained synthetic Model Playground page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Model Playground — Technical Demo Sandbox</title>
<style>{_CSS}</style>
</head>
<body>
<main class="page">
  <header class="header">
    <div>
      <div class="brand">Bremen</div>
      <div class="question">Synthetic model sandbox for MRI-continuation decision support concepts</div>
    </div>
    <nav class="nav" aria-label="Demo navigation">
      <a href="/demo">Start</a>
      <a href="/demo/control-room">Control Room</a>
      <a href="/demo/model-guide">Model guide</a>
      <a href="/demo/api-docs">API docs</a>
    </nav>
  </header>

  <section class="hero">
    <div class="card">
      <h1>Model playground</h1>
      <p class="lede">
        Explore a synthetic, sandbox-only version of the Bremen model workflow.
        The controls below use prototype parameters for visual demonstration.
        They are not connected to real H5 uploads, jobs, reports, or production
        model mutation.
      </p>
      <div class="notice">
        Technical demo only. Synthetic patients and prototype parameters only.
        Export scenario is a disabled placeholder and does not create a
        deployable model.
      </div>
    </div>
    <div class="card">
      <h2>Sandbox Score</h2>
      <p>Move the controls to see how a simple illustrative score changes.</p>
      <div class="score low" id="score">0%</div>
      <div class="meter"><div class="fill" id="fill"></div></div>
      <div class="verdict" id="verdict">Sandbox output pending</div>
    </div>
  </section>

  <section class="grid">
    <aside class="card">
      <h2>Prototype Controls</h2>
      <p>These controls are visual only and use synthetic values.</p>
      <div class="segmented" aria-label="Sandbox operating mode">
        <button id="balanced" class="active" type="button">Balanced view</button>
        <button id="sensitive" type="button">Sensitivity view</button>
      </div>
      <div class="controls" id="controls" style="margin-top:14px"></div>
      <button class="export-btn" type="button" disabled>Export scenario</button>
    </aside>

    <section class="card">
      <h2>Synthetic Patient Cloud</h2>
      <p>
        Dots and curve are generated in the browser for explanation only. They
        are not real patient records and do not come from H5 analysis.
      </p>
      <div class="chart" id="chart"></div>
    </section>

    <aside class="card">
      <h2>Visual Drivers</h2>
      <p>
        Bars show relative synthetic influence in this sandbox. They are not
        production learned parameters.
      </p>
      <div class="bars" id="bars"></div>
    </aside>
  </section>

  <footer class="footer">
    Bremen research draft. Technical demo only. Not clinically validated.
    Requires radiologist or qualified breast-imaging clinician review.
  </footer>
</main>
{_JS}
</body>
</html>"""
