# PR0093 Plan — Presentation-Grade Bremen Report Renderer with Browser-Native Print / Save PDF

**Branch**: `0093-report-rendering-and-pdf-export`  
**Status**: Planning  
**Agent role**: plan

---

## 1. Precondition verification

```
HEAD:   b5f75533de511f837be85c0b22b4627a77cbdd1d
Branch: 0093-report-rendering-and-pdf-export (verified ✓)
Status: clean — no modified/untracked files (except PR0093 directory creation)
```

### PR0092 merge check

```
symmetry_signals    — found in decision_support.py  ✓
                    — found in symmetry_signals.py  ✓
                    — found in docs/api_contract.md  ✓
symmetry_signal_detail — found in report_bremen.py  ✓
                       — found in docs/api_contract.md  ✓
```

PR0092 is fully merged. Blockers cleared.

---

## 2. Required reads — evidence summary

### 2.1 `docs/design/BREMEN_DESIGN_SPEC_v1.md` (full read)

Defines:
- **Color System** (§1): 6 base colors, 4 status colors, 3 tint colors. All hex values listed. Prohibited colors enumerated.
- **Typography** (§2): System font stack, 6 font sizes (32, 22, 17, 14, 13, 11px).
- **Spacing Scale** (§3): 8 steps (4, 8, 12, 16, 24, 32, 48, 64px).
- **Radii** (§4): `--radius-card: 10px`, `--radius-pill: 999px`.
- **Shadows** (§5): `--shadow-card` and `--shadow-elevated` defined.
- **Status Rails** (§6): 3px left rail for state-bearing cards.
- **Page Layout** (§9): 1440px max, 32px desktop/16px tablet/12px mobile padding.
- **Component Specifications** (§10): Cards, primary button, selected card, pipeline stages, decision summary card, tech demo notice.
- **Accessibility** (§11): Keyboard, aria roles, focus outlines, semantic HTML.
- **Responsive Breakpoints** (§12): 1440px+, 768–1439px, <768px.

**Report page section 3.3**: Not found in the design spec. The spec covers Control Room, Start Page, and general components. Report-specific layout and External/Internal tabs must be derived from the sample YAML/PDF artifacts.

### 2.2 `PR0083_design_system_prompt.md`

Not present in the repository. Design tokens are sourced from `BREMEN_DESIGN_SPEC_v1.md` directly (§1 Color System), which is the authoritative source.

### 2.3 Report reference artifacts

Not present in the repository. The directory structure was created:
```
.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/report-reference/
```
but contains no files. The following artifacts must be placed here before rendering can match the intended design:

- `bremen_external_report.yaml`
- `bremen_internal_report.yaml`
- `Bremen_External_Report_SAMPLE.pdf`
- `Bremen_Internal_Report_SAMPLE.pdf`

**The plan proceeds without these artifacts.** The External/Internal report structure is derived from the API contracts (`docs/api_contract.md` §Symmetry Signals) and from the existing `BremenReportProvider._build_report()` payload shape. The visual layout and component structure are documented here in the plan but may require refinement when the reference artifacts are placed.

### 2.4 `src/bremen/api/decision_support.py` (full read)

`build_decision_support_report()` produces the v0.1 report with fields:
`report_schema_version`, `intended_use`, `limitations`, `model_metadata`,
`input_summary`, `prediction_summary`, `decision_support`, `symmetry_signals`.

PR0092 added `symmetry_signals` and the `feature_values` / `ref_stats` parameters.

### 2.5 `src/bremen/api/symmetry_signals.py` (full read)

`compute_symmetry_signals()` and output formatters (`_format_external`, `_format_internal`).
Phase 1: all signals return `not_available`. Feature-to-signal map, signal labels,
feature families all defined.

### 2.6 `src/bremen/api/report_bremen.py` (full read)

`BremenReportProvider._build_report()` produces the v0.2 envelope with `payload` containing:
`analysis_summary`, `mri_continuation_assessment`, `score_and_threshold`,
`measurement_qc_summary`, `supporting_technical_evidence` (includes
`symmetry_signal_detail` from PR0092), `model_identity`, `feature_schema_identity`,
`workflow_readiness`, `limitations`, `technical_demo_only_disclaimer`, `audit_information`.

### 2.7 Current report route and rendering files

**Confirmed route**: `GET /demo/report/{job_id}`

Dispatched by `_handle_report_route()` in `src/bremen/api/server.py` (line 1484).
Calls `build_report_page()` in `src/bremen/report_ui.py` (line 239).

**Current `report_ui.py`** (287 lines):
- Single-tab report page with `_CSS`, `_JS`, and `build_report_page()`.
- JS fetches `/demo/api/jobs/{jid}` and `/demo/api/jobs/{jid}/reports/bremen` via `Promise.all()`.
- Renders: technical demo notice → recommendation card (decision name, code, score bar) → model panel → audit panel → execution trace.
- No External/Internal tabs.
- No symmetry signals rendering.
- No Print / Save PDF button.
- Uses design tokens from `BREMEN_DESIGN_SPEC_v1.md`.

**No sample/demo mode exists in the current report route.**

### 2.8 `src/bremen/api/job_api_handler.py` (full read)

`get_job_report()` generates reports via `BremenReportProvider.generate_report()`.
The report envelope `to_dict()` returns full payload including `supporting_technical_evidence`.
No changes needed here for report data — the v0.2 envelope already carries all required data.

### 2.9 `docs/api_contract.md` (full read)

Complete contract including PR0092 symmetry signals sections.
`decision_support_report` (v0.1) and Bremen report envelope (v0.2) documented.

### 2.10 `.project-memory/project_contract.yml` and `AGENTS.md`

Read. Safety invariants confirmed.

---

## 3. Report experience decision

### 3.1 Primary UX

A web report page at `/demo/report/{job_id}` with:
- **External tab** — clinician-facing, plain-language symmetry signals.
- **Internal tab** — technical/audit-facing, feature families, execution trace, checksum prefix.
- **Print / Save PDF button** per tab.

### 3.2 PDF export mechanism

**Option 1 — browser-native `window.print()` + `@media print` CSS.**

Chosen unless source evidence proves server-side PDF generation is a hard requirement. No evidence of a server-side PDF requirement exists. The existing report is pure HTML/CSS/JS served inline.

Justification:
- Zero new dependencies.
- Works in all modern browsers.
- `@media print` CSS handles page breaks, hide controls, print-only layout.
- No WeasyPrint, Chromium, Puppeteer, Playwright, Pango, Cairo, or GDK libraries.

Button label: `Print / Save PDF` — accurate, not misleading. The browser's native print dialog offers "Save as PDF" as a destination.

---

## 4. Report reference artifacts

### 4.1 Artifact directory

```
.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/report-reference/
```

### 4.2 Required artifacts (not yet placed)

The following four files must be placed in the directory above before
report rendering can match the intended visual design:

1. `bremen_external_report.yaml` — External report structure definition
2. `bremen_internal_report.yaml` — Internal report structure definition
3. `Bremen_External_Report_SAMPLE.pdf` — External report visual sample
4. `Bremen_Internal_Report_SAMPLE.pdf` — Internal report visual sample

### 4.3 Contingency

The plan defines the External and Internal report layouts from the API
contract data shapes. When the reference artifacts are placed, the
rendering may need refinement of visual placement, ordering, or chip
styling. A follow-up visual polish PR may be warranted.

---

## 5. Two report modes

### 5.1 Live report mode (default)

Uses real job/report data from the Bremen API.

- Loads via `GET /demo/api/jobs/{jid}` and `GET /demo/api/jobs/{jid}/reports/bremen`.
- Renders `symmetry_signals` from `decision_support_report` (External tab).
- Renders `symmetry_signal_detail` from report envelope payload (Internal tab).
- If `difference_level` is `not_available`, renders:

  **External**: `Calibration pending` chip label with pending/neutral styling.
  **Internal**: `Reference statistics not available for this signal` with status explanation.

- Does **not** hide the signal.
- Does **not** substitute sample/example values.
- Does **not** fabricate `small`/`moderate`/`larger`.

### 5.2 Sample demonstration mode

A separate, clearly labeled sample report for owner/CTO demo of intended
visual presentation.

**Recommendation: Option B — locally generated project-memory artifact.**

The sample mode is a static HTML page stored as a project-memory development
artifact, **not** a server route. Rationale:

- No risk of sample mode being confused with live runtime output in production.
- No route pollution in the demo server.
- The developer/owner can open the static HTML file in a browser for review.
- Sample data is frozen in a JSON fixture file, not in live code.
- No sample toggle/button that could accidentally activate in production.

**Implementation**:

1. Create `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/sample-data.json`
   — a frozen JSON fixture file with realistic-but-illustrative report data.
2. Provide a script or Makefile target `make sample-report` that generates
   the static HTML from the sample data fixture using `build_report_page()`.
3. The generated HTML file is placed at:
   `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/sample-report.html`
4. The page header displays prominently:

   ```
   SYNTHETIC DEMONSTRATION SAMPLE
   Illustrative values only
   Not generated from live runtime calibration
   Not clinically validated
   Not for patient or external distribution
   ```

5. Sample mode is **never** served from the runtime server. It is a
   file-system-only artifact.

### 5.3 Mode isolation

- Live mode uses real HTTP API calls to the running server.
- Sample mode uses a static JSON fixture file on disk.
- The same `build_report_page()` function is used for both, but the
  data injection path differs:
  - Live: Async JS `fetch()` calls in browser.
  - Sample: Pre-rendered HTML with fixture data inlined at generation time.
- No runtime code path can accidentally serve sample data.

---

## 6. External report target

The External report (clinician-facing) must include:

### 6.1 Report structure

```
┌─────────────────────────────────────────────────────┐
│ Bremen                                              │
│ MRI-Continuation Decision-Support Report            │
│ For referring clinician / breast-imaging radiologist│
│ Job: <job_id>  |  Generated: <timestamp>            │
├─────────────────────────────────────────────────────┤
│ [TECHNICAL DEMO ONLY — safety notice]               │
├─────────────────────────────────────────────────────┤
│ RECOMMENDATION CARD                                 │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Continue MRI evaluation                        │ │
│ │ CONTINUE_MRI                                   │ │
│ │ ████████████████████████░░  Score: 0.751       │ │
│ │ ▴ threshold: 0.500                              │ │
│ └─────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────┤
│ QC STATUS: passed                                   │
├─────────────────────────────────────────────────────┤
│ LEFT/RIGHT STRUCTURAL COMPARISON (Symmetry Signals) │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Profile difference magnitude   [moderate]       │ │
│ │ Weighted profile asymmetry      [small]         │ │
│ │ Statistical shape deviation [Calibration pending]│ │
│ │ Distributional divergence       [larger]        │ │
│ │ Bilateral profile intensity    [not_available]  │ │
│ │                                                 │ │
│ │ Signal chips: moderate / small / calibration    │ │
│ │ pending / larger / not_available                │ │
│ └─────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────┤
│ EXPLANATION SECTION                                 │
│ This result means:                                  │
│ Based on the model output, MRI follow-up may be     │
│ recommended for this patient.                       │
├─────────────────────────────────────────────────────┤
│ MODEL TABLE                                         │
│ Model: bremen-current                               │
│ Version: v0.1                                       │
│ Feature schema: v0.1                                │
│ Decision policy: bremen_mri_continuation_threshold  │
│ Certification: pending                              │
├─────────────────────────────────────────────────────┤
│ Report ID: <uuid>                                   │
│ Schema version: v0.1                                │
├─────────────────────────────────────────────────────┤
│ FOOTER SAFETY DISCLAIMER                            │
│ This is a technical product demo...                 │
│ Does not replace MRI, biopsy, radiologist...        │
└─────────────────────────────────────────────────────┘
```

### 6.2 Signal chip rendering

Each signal gets a color-coded chip/pill:

| `difference_level` | Chip color | CSS token | Label |
|--------------------|------------|-----------|-------|
| `small` | Green | `--status-available` | Small |
| `moderate` | Yellow/amber | `--status-pending` | Moderate |
| `larger` | Red | `--status-error` | Larger |
| `not_available` | Grey | `--status-unconfigured` | Calibration pending |

- Chips use `--radius-pill` (999px) and the appropriate status rail colors.
- Text labels are always present — no color-only communication.
- Chips are rendered as `<span>` elements with inline classes, not as background images.

### 6.3 Live mode rules

- Every field is sourced from the runtime report fields.
- If a field is `null` or missing, render a safe `—` (em dash).
- If `symmetry_signals` is `schema_status: "unavailable"`, render:
  `"Reference statistics not configured. Asymmetry assessment is not available."`
- No sample text substitution.

---

## 7. Internal report target

The Internal report (technical/audit-facing) must include:

### 7.1 Report structure

```
┌─────────────────────────────────────────────────────┐
│ Bremen                                              │
│ Internal Technical Report                           │
│ Scientific certification: pending                   │
│ Technical demo only                                 │
│ Job: <job_id>  |  Request: <request_id>             │
│ Generated: <timestamp>                              │
├─────────────────────────────────────────────────────┤
│ [TECHNICAL DEMO ONLY — safety notice]               │
├─────────────────────────────────────────────────────┤
│ REQUEST / JOB IDENTITY                              │
│ Job ID: <uuid>                                      │
│ Workflow: bremen                                    │
│ Source: <container_id or filename>                  │
│ Created: <timestamp>                                │
│ Completed: <timestamp>                              │
│ Duration: <seconds>                                 │
├─────────────────────────────────────────────────────┤
│ MODEL / RUNTIME PLUGIN DETAILS                      │
│ Model ID: bremen-current                            │
│ Model version: v0.1                                 │
│ Feature schema version: v0.1                        │
│ Checksum prefix: a1b2c3d4 (8 hex chars)             │
│ Decision policy: bremen_mri_continuation_threshold  │
│ Policy version: 0.1.0                               │
│ Plugin ID: bremen                                   │
│ Plugin version: from model package                  │
│ Report schema version: v0.2                         │
├─────────────────────────────────────────────────────┤
│ DECISION POLICY                                     │
│ Policy: bremen_mri_continuation_threshold           │
│ Score: 0.751                                        │
│ Threshold: 0.500                                    │
│ Decision: CONTINUE_MRI                              │
├─────────────────────────────────────────────────────┤
│ QC STATUS                                           │
│ Status: passed                                      │
│ Flags: (none or list)                               │
├─────────────────────────────────────────────────────┤
│ SYMMETRY SIGNAL BREAKDOWN                           │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Signal                    | Features      | Lvl │ │
│ │────────────────────────────────────────────│─────│ │
│ │ Profile diff magnitude    | sigma_l1+...  | mod │ │
│ │ Weighted profile asym     | weightedrms*  | sm  │ │
│ │ Statistical shape dev     | mahalanobis*  | n/a │ │
│ │ Distributional divergence | wasserstein+  | lrg │ │
│ │ Bilateral profile int     | peak14+mean   | n/a │ │
│ └─────────────────────────────────────────────────┘ │
│ Reference artifact version: 0.1.0                    │
│ Checksum prefix: a1b2c3d4                            │
├─────────────────────────────────────────────────────┤
│ EXECUTION TRACE (if available)                       │
│ ✓ Preprocessing     243ms                            │
│ ✓ Feature extraction 86ms                            │
│ ✓ Inference          12ms                            │
│ ✓ Report generation   5ms                            │
├─────────────────────────────────────────────────────┤
│ Boundary note: This is a technical product demo...   │
├─────────────────────────────────────────────────────┤
│ FOOTER SAFETY DISCLAIMER                             │
└─────────────────────────────────────────────────────┘
```

### 7.2 Safety boundary

Internal report must **never** expose:
- Raw feature values or feature vectors
- Raw deltas between target and control
- Percentile cutoffs
- Full checksum (prefix only: first 8 hex chars)
- Raw target/control scan refs
- Patient names, patient IDs, or PHI
- Raw H5 paths or S3 URIs
- Model internals (coefficients, weights, intercepts)
- Exception text or stack traces
- Raw AWS ARNs or manifest keys

### 7.3 Signal detail rendering

- Feature family names are listed per signal (e.g. `sigma_l1, sigma_l2, sigma_r1, sigma_r2, meanrms1, meanrms2`).
- `difference_level` values use the same four allowed strings.
- `not_available` renders as `Reference statistics unavailable` with a brief explanation.
- Checksum prefix is exactly 8 hex characters, never longer.

---

## 8. Tab implementation

### 8.1 Tab structure (External / Internal)

Two `<button>` tabs with `role="tab"` and `aria-selected`:
- External (default active)
- Internal

Two `<div>` tab panels with `role="tabpanel"`:
- External content panel
- Internal content panel

### 8.2 JS tab switching

```javascript
function switchTab(tabId) {
  // Update tab buttons: aria-selected, class
  // Update panels: show/hide
}
```

- Keyboard accessible: Enter/Space to activate a tab.
- Arrow keys for tab navigation (optional enhancement).
- Visible focus ring using 3px `--accent` outline.

### 8.3 Tab data loading

- External tab data from `decision_support_report` in the job result.
- Internal tab data from the report envelope `payload` (GET `/demo/api/jobs/{jid}/reports/bremen`).
- Both are loaded in parallel on page load.
- Tab switching is instant after initial load — no additional network requests.

---

## 9. Print / Save PDF

### 9.1 UX

- **External tab**: `Print / Save PDF` button in the tab bar.
- **Internal tab**: `Print / Save PDF` button in the tab bar.
- Clicking triggers `window.print()`.
- The active tab's content is printed.
- JavaScript detects the active tab and shows/hides print content accordingly.

### 9.2 `@media print` CSS

```css
@media print {
  /* Hide interactive controls */
  .report-nav, .report-tabs, .print-button, .report-footer,
  .trace-toggle, .trace-content { display: none; }

  /* Show selected tab content */
  .tab-panel { display: block !important; }

  /* Page break control */
  .report-card { page-break-inside: avoid; }
  .recommendation-card { page-break-inside: avoid; }

  /* Print-specific layout */
  body { background: white; }
  .report-page { padding: 0; max-width: 100%; }

  /* Signal chips print nicely */
  .signal-chip { border: 1px solid #ccc; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
```

### 9.3 Print-only tab content

A hidden print-only section renders the current tab's content for printing:

```html
<div class="print-only" id="print-external">
  <!-- Full external report content, independent of interactive layout -->
</div>
```

This ensures:
- Only the selected tab is printed.
- No interactive elements appear in the PDF.
- Page breaks are controlled.
- The print output is clean and self-contained.

### 9.4 No server-side PDF

No WeasyPrint, Chromium, Puppeteer, Playwright, Pango, Cairo, GDK, or
any other server-side PDF dependency. No binary PDF response. No new
Python dependency.

---

## 10. Design token plan

### 10.1 Color tokens (from BREMEN_DESIGN_SPEC_v1.md §1 — verbatim)

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-page` | `#F7F8F8` | Page background |
| `--bg-surface` | `#FFFFFF` | Card, panel backgrounds |
| `--text-primary` | `#16202A` | Primary text, headings |
| `--text-secondary` | `#5B6570` | Secondary text, metadata |
| `--accent` | `#1F6F6B` | Primary actions, active states |
| `--border` | `#E3E7E6` | Borders, dividers |
| `--status-available` | `#2E7D5B` | Completed, small signal |
| `--status-pending` | `#B8894A` | Pending, moderate signal |
| `--status-unconfigured` | `#9AA3A8` | Unconfigured, not_available |
| `--status-error` | `#C1483D` | Error, larger signal |
| `--tint-accent` | `#F1F5F4` | Active background |
| `--tint-pending` | `#FBF3E9` | Warning/notice background |
| `--tint-error` | `#FBEEEC` | Error background |

**No new hex colors.** All signal chip colors use existing status tokens.

### 10.2 Signal chip color mapping

| `difference_level` | Color token | Background |
|--------------------|-------------|------------|
| `small` | `--status-available` | `--tint-accent` or `--tint-available` (none defined — use `--tint-accent` for green tint) |
| `moderate` | `--status-pending` | `--tint-pending` |
| `larger` | `--status-error` | `--tint-error` |
| `not_available` | `--status-unconfigured` | transparent or `--bg-page` |

**Note**: No `--tint-available` token exists in the spec. For `small` signal
chips, either `--tint-accent` (already `#F1F5F4`, a greenish tint) is used,
or no background tint — just text + border using `--status-available`. The
`--tint-accent` token is the closest available match.

### 10.3 Typography

System font stack, 6 font sizes as defined in the design spec. No additions.

### 10.4 Spacing and radii

All from the design spec. No 20px, no 6px, no custom values.

### 10.5 Prohibited colors

No `#0969da`, `#1a7f37`, `#cf222e`, `#9a6700`, `#d0d7de`, `#656d76`,
`#1f2328`. No gradients. No pink. No rose. No blue accent system.
No GitHub palette.

---

## 11. Accessibility plan

- Tab buttons: `<button role="tab" aria-selected="true|false">`.
- Tab panels: `<div role="tabpanel" aria-labelledby="tab-id">`.
- Tab switching via keyboard: Enter/Space (built-in for `<button>`).
- Focus management: active tab receives focus outline (3px `--accent`).
- Print button: `<button class="print-button">Print / Save PDF</button>` — real button, not `div-as-button`.
- Signal chips: `<span>` with text label — never conveyed only by color.
- Decision recommendation card: `role="alert"` (already present in current implementation).
- Safety notices: visible text, not hidden or minimized.
- No inline `onclick` if avoidable — `addEventListener` in JS.
- `prefers-reduced-motion`: suppress animations.
- Semantic HTML: `<h1>`, `<h2>`, `<h3>` headings in document outline.
- Tab panel content uses `<dl>` / `<dt>` / `<dd>` for field/value pairs.

---

## 12. Files for implementation

### 12.1 Allowed files

| File | Purpose | Changes |
|------|---------|---------|
| `src/bremen/report_ui.py` | Primary target — rewrite to add External/Internal tabs, symmetry signals rendering, Print / Save PDF, sample mode support. | Major rewrite of `_CSS`, `_JS`, `build_report_page()`. |
| `src/bremen/api/server.py` | Add `/demo/report/sample` route if sample mode is served. Only if sample mode is Option A (not recommended). | Minimal — likely no change if using Option B. |
| `docs/api_contract.md` | Document the two-tab report design, Print/Save PDF behavior, and rendering rules. | Additive only. |
| `tests/test_bremen_report_ui.py` | New test file for report rendering tests. | Create new file. |
| `tests/test_bremen_api_server.py` | Test that `/demo/report/{job_id}` returns HTML 200. | Additive test only. |
| `.project-memory/pr/0093-report-rendering-and-pdf-export/implementation-report.md` | Implementation report. | Create. |
| `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/sample-data.json` | Frozen sample data fixture. | Create. |

### 12.2 Forbidden files

- `src/bremen/api/symmetry_signals.py` — read-only. No changes.
- `src/bremen/api/preprocessing_bridge.py` — no changes.
- `src/bremen/api/decision_support.py` — no changes.
- `src/bremen/api/report_bremen.py` — no changes.
- `src/bremen/api/report_provider.py` — no changes.
- `src/bremen/api/job_api_handler.py` — no changes unless report data fetch needs safe additive fields (unlikely).
- `src/bremen/control_room_ui.py` — no redesign in this PR.
- `src/bremen/start_page_ui.py` — no changes.
- All model artifacts, private H5 files, Dockerfile, requirements.txt, pyproject.toml — no changes.
- All frontend framework files (package.json, node_modules) — no changes.
- All Aramis files — no changes.

---

## 13. Implementation sequence (for coder)

### Step 1: Create sample data fixture

Create `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/sample-data.json`
with frozen illustrative report data:

```json
{
  "meta": {
    "description": "Frozen sample report data for presentation demo only",
    "generated_at": "2026-07-26T00:00:00Z",
    "synthetic": true,
    "not_for_clinical_use": true
  },
  "job": {
    "job_id": "00000000-0000-0000-0000-000000000001",
    "created_at": "2026-07-25T14:30:00Z",
    "completed_at": "2026-07-25T14:31:15Z",
    "overall_status": "completed",
    "requested_workflows": ["bremen"],
    "input_summary": {
      "model_id": "bremen-current",
      "filename": "sample_patient_001.h5",
      "container_id": "synthetic"
    }
  },
  "report": {
    "report_id": "11111111-1111-1111-1111-111111111111",
    "workflow_id": "bremen",
    "report_schema_version": "v0.2",
    "workflow_status": "available",
    "model_id": "bremen-current",
    "model_version": "v0.1",
    "payload": {
      "report_schema_version": "v0.2",
      "report_type": "bremen_mri_triage",
      "mri_continuation_assessment": {
        "assessment": "Based on the model output, MRI follow-up may be recommended for this patient.",
        "caution": "This is a decision-support recommendation only..."
      },
      "score_and_threshold": {
        "p_mri_needed": 0.751,
        "threshold": 0.500,
        "triage_recommendation": "CONTINUE_MRI"
      },
      "supporting_technical_evidence": {
        "logistic_regression_probability": 0.751,
        "symmetry_signal_detail": {
          "schema_status": "unavailable",
          "signals": [
            {"label": "Profile difference magnitude", "feature_family": ["sigma_l1", "sigma_l2", "sigma_r1", "sigma_r2", "meanrms1", "meanrms2"], "difference_level": "not_available"},
            ...
          ]
        }
      }
    }
  },
  "decision_support_report": {
    "symmetry_signals": {
      "schema_status": "unavailable",
      "signals": [
        {"label": "Profile difference magnitude", "difference_level": "not_available"},
        ...
      ]
    }
  }
}
```

### Step 2: Rewrite `src/bremen/report_ui.py`

Key changes to `build_report_page()`:

1. Add External/Internal tab HTML structure.
2. Add Print / Save PDF button per tab.
3. Add sample mode argument: `build_report_page(..., sample_data: dict | None = None)`.
   - When `sample_data` is provided, inline the data and render immediately without fetch.
   - When `sample_data` is `None` (default), use the existing fetch-based live mode.
4. Render symmetry signals in External tab from `decision_support_report.symmetry_signals`.
5. Render symmetry signal detail in Internal tab from `payload.supporting_technical_evidence.symmetry_signal_detail`.
6. Add signal chip rendering with color-coded pills.
7. Add `@media print` CSS.
8. Add `window.print()` button handler.
9. Add `prefers-reduced-motion` support.
10. Ensure all accessibility requirements.

### Step 3: Add sample mode generation

Create a standalone script or Makefile target that:
1. Reads `artifacts/sample-data.json`.
2. Builds the complete HTML via `build_report_page(base_url="", sample_data=...)`.
3. Writes `artifacts/sample-report.html`.

The script is NOT part of the runtime server. It is a development-only tool.

### Step 4: Update docs

- `docs/api_contract.md`: Add section documenting the two-tab report page,
  Print/Save PDF behavior, and rendering rules.

### Step 5: Tests

Create `tests/test_bremen_report_ui.py` with the required tests (§15).
Update `tests/test_bremen_api_server.py` with a route existence test.

### Step 6: Validation

Run all validation checks (§16).

---

## 14. Non-goals — explicitly excluded

- No real reference-statistics thresholds.
- No fabricated signal buckets.
- No backend symmetry computation changes.
- No server-side PDF generation.
- No dependency additions (no WeasyPrint, Chromium, etc.).
- No Start Page redesign.
- No Control Room redesign.
- No Aramis integration.
- No clinical validation claims.
- No POST /predictions schema changes.
- No changes to `symmetry_signals.py`, `decision_support.py`, `report_bremen.py`.
- No changes to preprocessing, inference, or model catalog.
- No React, frontend framework, or build step.

---

## 15. Test plan

### 15.1 Test file

`tests/test_bremen_report_ui.py` (new file)

### 15.2 Required tests

| # | Test | Priority |
|---|------|----------|
| 1 | `test_external_tab_renders` — `build_report_page()` with live data returns HTML containing External tab button and `role="tabpanel"` for external content. | Required |
| 2 | `test_internal_tab_renders` — Internal tab button exists and panel is present. | Required |
| 3 | `test_external_contains_recommendation` — External tab includes decision name, decision code, score bar, and model table. | Required |
| 4 | `test_external_contains_safety_language` — External tab includes intended use, limitations, technical demo notice, and footer disclaimer. | Required |
| 5 | `test_internal_contains_job_identity` — Internal tab includes job ID, workflow, source, timestamps. | Required |
| 6 | `test_internal_contains_model_metadata` — Internal tab includes model ID, version, feature schema version, checksum prefix (max 8 chars). | Required |
| 7 | `test_internal_contains_signal_breakdown` — Internal tab includes feature family names and difference levels for all 5 signals. | Required |
| 8 | `test_not_available_renders_calibration_pending` — When `difference_level` is `not_available`, the chip shows "Calibration pending" (external) or "Reference statistics unavailable" (internal). | Required |
| 9 | `test_live_does_not_use_sample_values` — Live mode output does not contain the sample fixture's illustrative values. | Required |
| 10 | `test_sample_mode_labeled_synthetic` — Sample mode output contains visible "SYNTHETIC DEMONSTRATION SAMPLE" and "Illustrative values only". | Required |
| 11 | `test_print_button_exists` — External and Internal tabs each have a `Print / Save PDF` button. | Required |
| 12 | `test_print_css_hides_controls` — `@media print` CSS hides tab buttons, print buttons, navigation, and footer interactive elements. | Required |
| 13 | `test_print_prints_selected_tab_only` — Print-only section renders only the active tab's content. | Required |
| 14 | `test_no_raw_feature_values_exposed` — Neither tab renders raw feature values, percentile cutoffs, full checksums, S3 paths, or raw target/control refs. | Required |
| 15 | `test_no_server_side_pdf_dependency` — No WeasyPrint, Chromium, Puppeteer, Playwright, Pango, Cairo, GDK references in test files. | Required |
| 16 | `test_no_new_hex_colors` — Every hex color in the report CSS matches the BREMEN_DESIGN_SPEC_v1.md palette. | Required |
| 17 | `test_backward_compatible_route` — `/demo/report/{job_id}` returns HTML 200. Existing tests pass. | Required |
| 18 | `test_signal_chip_color_mapping` — Signal chips use the correct status color for each `difference_level`. | Required |

### 15.3 Existing tests must continue passing

```
python -m pytest -q tests/test_bremen_decision_support_output.py -v
python -m pytest -q tests/test_bremen_preprocessing_bridge.py -v
python -m pytest -q tests/test_bremen_api_server.py -v
```

---

## 16. Validation plan

### 16.1 Pre-validation checks

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only
```

### 16.2 Compile and lint

```bash
python -m compileall src tests
```

### 16.3 Test execution

```bash
python -m pytest -q tests/test_bremen_report_ui.py -v
python -m pytest -q tests/test_bremen_api_server.py -v
python -m pytest -q
```

### 16.4 Safety greps

```bash
# Check all hex colors are from BREMEN_DESIGN_SPEC_v1.md
grep -oE '#[0-9A-Fa-f]{6}' src/bremen/report_ui.py | sort -u

# Check no sample artifact dependency in live code
grep -rn "Bremen_External_Report_SAMPLE\|Bremen_Internal_Report_SAMPLE\|hardcoded\|example" src/ tests/ || true

# Check no unsafe exposure in report UI
grep -rn "feature_value\|raw_feature\|percentile_cutoff\|cutoff\|model_checksum\|manifest_key\|s3://\|arn:aws" src/bremen/ tests/ || true

# Check no server-side PDF dependencies
grep -rn "WeasyPrint\|weasyprint\|playwright\|puppeteer\|chromium\|pango\|cairo" requirements.txt pyproject.toml Dockerfile src/ tests/ docs/ || true

# Check window.print and @media print are present
grep -rn "window.print\|@media print\|Print / Save PDF" src/ tests/ docs/
```

### 16.5 Manual confirmations

1. Open `/demo/report/<job_id>` in a browser.
2. Verify External tab renders with recommendation, score bar, model table, symmetry signals.
3. Switch to Internal tab — verify job identity, model metadata, signal breakdown, checksum prefix.
4. Click Print / Save PDF — verify browser print dialog opens.
5. Verify printed preview hides interactive controls, shows clean content.
6. Verify sample report (if generated) is clearly labeled synthetic.

---

## 17. Future roadmap note

A future calibration PR (after PR0093) must:
1. Obtain a safe aggregate reference-statistics artifact from the data science team.
2. Place it in a versioned, checksummed controlled artifact location.
3. Load it through controlled configuration (`BREMEN_REFERENCE_STATISTICS_URI`).
4. Replace `not_available` with real `small` / `moderate` / `larger` buckets.
5. Never expose raw values, raw deltas, or percentile cutoffs in report output.
6. The signal chips in the External and Internal reports will then display real
   difference levels instead of "Calibration pending".

---

## 18. Summary of decisions

| Decision | Value | Justification |
|----------|-------|---------------|
| PDF export mechanism | Browser-native `window.print()` + `@media print` CSS | Zero dependencies, works in all browsers, required by task |
| Button label | `Print / Save PDF` | Accurate, not misleading about download |
| Sample mode | Option B — local project-memory artifact | No risk of sample/live confusion, no route pollution |
| External tab data source | `decision_support_report.symmetry_signals` | Already populated by PR0092, safe external shape |
| Internal tab data source | Report envelope `payload.supporting_technical_evidence.symmetry_signal_detail` | Existing v0.2 report envelope carries this |
| Tab implementation | Native HTML/CSS/JS with `role="tab"` / `role="tabpanel"` | No framework needed, accessible |
| Signal chip colors | Use existing status tokens from design spec | No new colors, no palette violation |
| `not_available` rendering | "Calibration pending" (external), "Reference statistics not available" (internal) | Honest, clear, non-fabricated |
| No new hex colors | Confirmed — all from BREMEN_DESIGN_SPEC_v1.md §1 | Every color verified against spec |
| No server-side PDF | Confirmed | No dependency changes |
| No backend changes | Confirmed | Symmetry signals, reports, and decision support are read-only |

---

TASK COMPLETE

BLOCKERS
1. Report reference artifacts (bremen_external_report.yaml, bremen_internal_report.yaml, Bremen_External_Report_SAMPLE.pdf, Bremen_Internal_Report_SAMPLE.pdf) are not present in the repository. The `artifacts/report-reference/` directory has been created but is empty. Visual layout may need refinement when these are placed. A follow-up visual polish PR may be warranted.

WARNINGS
1. `PR0083_design_system_prompt.md` does not exist in the repository. Design tokens are sourced directly from `BREMEN_DESIGN_SPEC_v1.md` §1, which is the authoritative source.
2. No `--tint-available` token exists for `small` signal chip background. The plan uses `--tint-accent` (greenish tint `#F1F5F4`) as the closest match, or no tint at all.
3. The External/Internal report visual layout is derived from the API contract data shapes, not from the sample YAML/PDF files. Layout may need refinement when reference artifacts arrive.
4. Sample mode requires creating a frozen data fixture. The sample values must be clearly synthetic and not misrepresentable as live runtime output.

FILES CHANGED
- `.project-memory/pr/0093-report-rendering-and-pdf-export/PLAN.md` (this file — planning only)
- `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/report-reference/` (empty directory — artifact placement will happen later)

CONFIRMED REPORT ROUTE
`GET /demo/report/{job_id}` → `_handle_report_route()` in `src/bremen/api/server.py` (line 1484) → `build_report_page()` in `src/bremen/report_ui.py` (line 239).
Current implementation is a single-tab page with recommendation, model panel, audit panel, execution trace. No symmetry signals. No Print/Save PDF.

REFERENCE ARTIFACTS
- Not present in repository. Directory created at `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/report-reference/`.
- Four artifacts required: `bremen_external_report.yaml`, `bremen_internal_report.yaml`, `Bremen_External_Report_SAMPLE.pdf`, `Bremen_Internal_Report_SAMPLE.pdf`.
- Plan proceeds from API contract data shapes. Visual refinement may follow when artifacts arrive.

LIVE REPORT MODE PLAN
- Default mode. Uses real API data from `/demo/api/jobs/{jid}` and `/demo/api/jobs/{jid}/reports/bremen`.
- Renders External tab from `decision_support_report.symmetry_signals`.
- Renders Internal tab from report envelope `payload.supporting_technical_evidence.symmetry_signal_detail`.
- `not_available` → External: "Calibration pending" chip. Internal: "Reference statistics not available for this signal".
- No sample value substitution.

SAMPLE DEMO MODE PLAN
- Option B: Local project-memory artifact, not a server route.
- Frozen fixture: `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/sample-data.json`.
- Generated static HTML: `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/sample-report.html`.
- Clearly labeled: "SYNTHETIC DEMONSTRATION SAMPLE — Illustrative values only — Not generated from live runtime calibration — Not clinically validated — Not for patient or external distribution".
- Generation tool is development-only, not part of runtime server.

EXTERNAL REPORT PLAN
Clinician-facing layout with: Bremen header, MRI-Continuation Decision-Support Report title, audience line, job/generated metadata, recommendation card (decision name, code, score bar with threshold), QC status, symmetry signal chips (5 signals with color-coded difference levels), explanation section, model table, report ID, footer safety disclaimer.

INTERNAL REPORT PLAN
Technical/audit-facing layout with: Bremen header, Internal Technical Report title, certification status, job/request identity, model/runtime plugin details (checksum prefix only — max 8 hex chars), decision policy, QC status/flags, symmetry signal breakdown (feature family names + difference levels for all 5 signals), reference artifact version, execution trace summary, boundary note, footer safety disclaimer.

PRINT / SAVE PDF DECISION
Browser-native `window.print()` + `@media print` CSS. No server-side PDF. No dependencies. Button label: `Print / Save PDF`. Print button per tab. Print-only section renders current tab's content. Interactive controls hidden in print. Page breaks controlled.

DESIGN TOKEN PLAN
All tokens from `BREMEN_DESIGN_SPEC_v1.md` §1 verbatim. No new hex colors. Signal chip colors map difference_level to existing status tokens. Typography, spacing, radii from spec. Prohibited colors confirmed.

ACCESSIBILITY PLAN
Tab buttons with `role="tab"` / `aria-selected`, tab panels with `role="tabpanel"` / `aria-labelledby`. Keyboard accessible. Visible focus outline (3px `--accent`). Print buttons are real `<button>` elements. Signal chips have text labels — no color-only communication. Semantic headings, `<dl>`/`<dt>`/`<dd>` for field/value. `role="alert"` on recommendation card. `prefers-reduced-motion` support.

SAFETY PLAN
No raw feature values, deltas, percentile cutoffs, full checksums, S3/H5 paths, PHI, model internals, coefficients, exception text, or AWS ARNs in any output. Decision vocabulary unchanged. No clinical replacement language. No diagnosis claims.

TEST PLAN
18 required tests in `tests/test_bremen_report_ui.py` (new file). Covers: External/Internal tabs, recommendation content, safety language, signal breakdown, not_available rendering, sample mode labeling, print button, print CSS, no raw exposure, no server-side PDF dependency, no new hex colors, backward compatibility.

VALIDATION PLAN
Pre-validation checks, `compileall`, targeted pytest, full suite, safety greps for hex colors, sample artifact leakage, unsafe exposure, PDF dependencies, print behavior. Manual browser verification.

FUTURE ROADMAP NOTE
Future calibration PR will obtain real reference-statistics artifact, wire percentile-position bucketing, replace `not_available` with real `small`/`moderate`/`larger` buckets. Never expose raw values or cutoffs.

NON-GOALS CONFIRMED
No real thresholds. No fabricated buckets. No backend changes. No server-side PDF. No dependency changes. No Start Page/Control Room redesign. No Aramis. No clinical claims. No POST /predictions changes. No changes to symmetry_signals.py, decision_support.py, report_bremen.py.

STOP CONDITIONS CONFIRMED
- PR0092 merged with symmetry_signals present ✓
- Current report route found (report_ui.py, server.py line 1484) ✓
- No fabricated buckets — not_available rendering defined ✓
- No sample values as live fallback ✓
- No raw values/cutoffs/checksums/S3/H5/model internals/PHI exposed ✓
- No server-side PDF dependency ✓
- No frontend framework/build step ✓
- No new colors outside PR0083 §A ✓
- No backend inference/preprocessing changes ✓
- No decision vocabulary changes ✓
- No POST /predictions schema changes ✓
- No Aramis work ✓
- Safety language preserved ✓

NEXT REQUIRED ACTION
Implementation agent: coder — proceed with Steps 1–6 as defined in §13.
