"""Sanitized Bremen demo model guide page.

This module intentionally does not load model artifacts or the source
standalone HTML at request time.  It provides a curated, self-contained
HTML page derived from the supplied guide concept while removing private
artifact identifiers, exact learned parameters, raw model internals, paths,
and clinical claims.
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
.guide-page {
  max-width: 1180px;
  margin: 0 auto;
  min-height: 100vh;
  padding: 32px;
}
.guide-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 0 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 28px;
}
.brand { font-size: 22px; font-weight: 650; }
.question { color: var(--text-secondary); font-size: 14px; margin-top: 4px; }
.guide-nav { display: flex; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }
.guide-nav a {
  color: var(--accent);
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
}
.guide-nav a:hover { text-decoration: underline; }
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr);
  gap: 28px;
  align-items: center;
  margin-bottom: 28px;
}
h1 {
  font-size: 34px;
  line-height: 1.12;
  margin: 0 0 12px;
}
.lede {
  color: var(--text-secondary);
  font-size: 16px;
  max-width: 720px;
}
.notice {
  border-left: 4px solid var(--accent-2);
  background: var(--tint-warn);
  border-radius: 0 10px 10px 0;
  padding: 12px 14px;
  margin-top: 18px;
  color: #5D4720;
  font-size: 13px;
}
.diagram {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 18px;
}
.flow {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}
.flow-step {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 10px;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 10px;
  background: #FFFFFF;
}
.n {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--tint-accent);
  color: var(--accent);
  font-weight: 800;
  font-size: 12px;
}
.flow-step b { display: block; font-size: 13px; }
.flow-step span { color: var(--text-secondary); font-size: 11px; }
.sections {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 18px;
}
.card h2 {
  margin: 0 0 8px;
  font-size: 17px;
}
.card p, .card li {
  color: var(--text-secondary);
  font-size: 13px;
}
.card ul {
  margin: 10px 0 0 18px;
  padding: 0;
}
.wide {
  grid-column: 1 / -1;
}
.safe-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.safe-item {
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 10px;
  background: #FBFCFD;
}
.safe-item b { display: block; font-size: 12px; margin-bottom: 3px; }
.safe-item span { color: var(--text-secondary); font-size: 11px; }
.mini-chart {
  height: 120px;
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  align-items: end;
  gap: 5px;
  margin-top: 12px;
  border-bottom: 1px solid var(--border);
}
.mini-chart span {
  display: block;
  border-radius: 6px 6px 0 0;
  background: var(--accent);
  min-height: 18px;
  opacity: .75;
}
.footer {
  color: var(--text-secondary);
  font-size: 12px;
  border-top: 1px solid var(--border);
  padding-top: 18px;
  margin-top: 28px;
}
@media (max-width: 900px) {
  .guide-page { padding: 18px; }
  .guide-header, .hero { grid-template-columns: 1fr; display: grid; }
  .guide-nav { justify-content: flex-start; }
  .sections, .safe-grid { grid-template-columns: 1fr; }
  h1 { font-size: 26px; }
}
"""


def build_model_guide_page() -> str:
    """Build a sanitized, self-contained HTML model guide page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Model Guide — Technical Demo</title>
<style>{_CSS}</style>
</head>
<body>
<main class="guide-page">
  <header class="guide-header">
    <div>
      <div class="brand">Bremen</div>
      <div class="question">MRI-continuation decision support research prototype</div>
    </div>
    <nav class="guide-nav" aria-label="Demo navigation">
      <a href="/demo">Start</a>
      <a href="/demo/control-room">Control Room</a>
      <a href="/demo/model-playground">Model playground</a>
      <a href="/demo/api-docs">API docs</a>
    </nav>
  </header>

  <section class="hero">
    <div>
      <h1>How the demo model works</h1>
      <p class="lede">
        This guide explains the Bremen demo at a conceptual level: how an H5
        measurement set is transformed into a feature table, how a simple
        linear model produces a risk score, and how the score supports a
        radiologist or qualified breast-imaging clinician reviewing whether
        MRI should continue.
      </p>
      <div class="notice">
        Technical demo only. This page is not clinical validation, not a
        diagnostic claim, and not a replacement for clinician review.
      </div>
    </div>
    <div class="diagram" aria-label="Conceptual model flow">
      <div class="flow">
        <div class="flow-step"><span class="n">1</span><div><b>Input contract</b><span>Structured H5 measurements and metadata enter the product pipeline.</span></div></div>
        <div class="flow-step"><span class="n">2</span><div><b>Preprocessing</b><span>Product filters, quality checks, integration, SNR, and q-window normalization run before modeling.</span></div></div>
        <div class="flow-step"><span class="n">3</span><div><b>Feature table</b><span>Stable feature names and ordering are checked before prediction.</span></div></div>
        <div class="flow-step"><span class="n">4</span><div><b>Risk score</b><span>A transparent linear baseline maps features to a probability-like score.</span></div></div>
        <div class="flow-step"><span class="n">5</span><div><b>Clinical review</b><span>The output is decision support for review, not autonomous diagnosis.</span></div></div>
      </div>
    </div>
  </section>

  <section class="sections">
    <article class="card">
      <h2>Training Concept</h2>
      <p>
        Model development uses patient-safe splits so held-out patients are not
        used to fit model weights or choose the operating point. The demo uses
        synthetic illustrations to show that separation and review workflow.
      </p>
    </article>
    <article class="card">
      <h2>Prediction Concept</h2>
      <p>
        At prediction time, the runtime applies the same preprocessing contract
        used for model development, checks the feature schema, and returns an
        MRI-continuation risk score for clinical review.
      </p>
    </article>
    <article class="card">
      <h2>Interpretability</h2>
      <p>
        Logistic regression is used here as a simple baseline because its
        behavior can be explained without exposing private learned parameters
        or raw model artifacts in the public demo.
      </p>
    </article>

    <article class="card wide">
      <h2>What This Page Deliberately Does Not Publish</h2>
      <p>
        The public guide removes private artifact identifiers and learned
        numerical internals from the provided standalone guide before serving it in the
        demo application.
      </p>
      <div class="safe-grid">
        <div class="safe-item"><b>No artifact fingerprint</b><span>Full cryptographic fingerprints remain server-private.</span></div>
        <div class="safe-item"><b>No learned weights</b><span>Feature-level learned values are not displayed.</span></div>
        <div class="safe-item"><b>No model internals</b><span>Serialized artifact details and package keys are not exposed.</span></div>
        <div class="safe-item"><b>No private data paths</b><span>H5 locations, storage keys, and patient identifiers are omitted.</span></div>
      </div>
    </article>

    <article class="card wide">
      <h2>Reading the Score</h2>
      <p>
        The demo score is an input to a decision-support workflow. Reliability
        checks, data sufficiency, intended use, and clinician review remain
        separate controls. A low or high score is not a standalone clinical
        conclusion.
      </p>
      <div class="mini-chart" aria-hidden="true">
        <span style="height:25%"></span><span style="height:42%"></span>
        <span style="height:36%"></span><span style="height:58%"></span>
        <span style="height:70%"></span><span style="height:48%"></span>
        <span style="height:64%"></span><span style="height:82%"></span>
        <span style="height:55%"></span><span style="height:74%"></span>
        <span style="height:68%"></span><span style="height:88%"></span>
      </div>
    </article>
  </section>

  <footer class="footer">
    Bremen research draft. Technical demo only. Not clinically validated.
    Requires radiologist or qualified breast-imaging clinician review.
  </footer>
</main>
</body>
</html>"""
