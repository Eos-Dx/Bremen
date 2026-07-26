# PR0093 Implementation Report

**Branch:** `0093-report-rendering-and-pdf-export`
**Status:** Implementation complete
**Date:** 2026-07-26

---

## Files Changed

| File | Change | Description |
|------|--------|-------------|
| `src/bremen/report_ui.py` | Rewritten | Complete rewrite — added External/Internal tabs, symmetry signal rendering, Print/Save PDF, @media print CSS, accessibility, sample mode support |
| `tests/test_bremen_report_ui.py` | New file | 71 tests covering tabs, symmetry signals, Print/Save PDF, safety boundaries, design tokens, accessibility |
| `docs/api_contract.md` | Additive section | Documented Report Page UI route, tab structure, Print/Save PDF, rendering rules, accessibility, design tokens |
| `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/sample-data.json` | New file | Frozen sample data fixture for development-only sample mode |
| `.project-memory/pr/0093-report-rendering-and-pdf-export/implementation-report.md` | This file | Implementation report |

**Not changed:** `src/bremen/api/server.py` (route already existed), `src/bremen/api/symmetry_signals.py`, `src/bremen/api/decision_support.py`, `src/bremen/api/report_bremen.py`, `src/bremen/api/job_api_handler.py`.

## Route Confirmed

`GET /demo/report/{job_id}` → `_handle_report_route()` in `src/bremen/api/server.py` → `build_report_page()` in `src/bremen/report_ui.py`.

No server.py changes needed — the existing route wiring is sufficient.

## Live Report Mode

- Default mode when `job_id` is provided and `sample_data` is `None`.
- JS fetches `/demo/api/jobs/{job_id}` and `/demo/api/jobs/{job_id}/reports/bremen` in parallel.
- External tab renders from job result (`workflow_runs.bremen.result_summary`) and `decision_support_report.symmetry_signals`.
- Internal tab renders from report envelope payload (`supporting_technical_evidence.symmetry_signal_detail`).
- `not_available` signals render as "Calibration pending" (external) or "Reference statistics unavailable" (internal).
- No sample values substituted. No fabricated thresholds.

## Sample Demo Mode

- Available as a local/dev project-memory artifact only — not a server route.
- Frozen fixture: `.project-memory/pr/0093-report-rendering-and-pdf-export/artifacts/sample-data.json`.
- When `sample_data` is passed to `build_report_page()`, data is embedded as JSON in a `<script>` tag and the JS renders from it without fetch calls.
- Prominent banner: "SYNTHETIC DEMONSTRATION SAMPLE — Illustrative values only — Not generated from live runtime calibration — Not clinically validated — Not for patient or external distribution".
- Sample fixture is never used when rendering a live job report.

## External Tab Implementation

- Bremen header with subtitle and audience line.
- Technical demo only safety notice (amber `--tint-pending` background).
- Recommendation card with `role="alert"`, decision display name, decision code, score bar with threshold marker.
- QC status badge (passed = green, failed = red, `--radius-pill`).
- Left/Right Structural Comparison section with 5 symmetry signal chips:
  - Color-coded by `difference_level`: small (green), moderate (amber), larger (red), not_available (grey).
  - Text labels always present — never color-only.
  - Chips use `--radius-pill` and `--tint-*` backgrounds.
- Explanation section with decision-specific text.
- Model table (model ID, version, feature schema, decision policy, certification).
- Report ID and schema version.
- Footer safety disclaimer.

## Internal Tab Implementation

- Request/Job Identity (job ID, workflow, source, created, completed, duration).
- Model/Runtime Plugin Details (model ID, version, feature schema version, checksum prefix — max 8 hex chars via `.substring(0,8)`, decision policy, policy version, report schema version).
- Decision Policy section (policy, score, threshold, decision code).
- QC Status/flags.
- Symmetry Signal Breakdown table with three columns: Signal, Feature Family (comma-separated), Level (color-coded chip).
- Checksum prefix and reference artifact version if available.
- Execution trace summary (stages with status icons and duration).
- Boundary note.
- Footer safety disclaimer.

## Print / Save PDF Implementation

- Real `<button>` elements labeled "Print / Save PDF" — one button visible per active tab.
- Calls `window.print()` via `printActiveTab()` function.
- `@media print` CSS:
  - Hides interactive controls: `.report-nav`, `.report-tabs`, `.tab-btn`, `.tab-spacer`, `.print-button`, `.trace-toggle`, `.trace-content`.
  - Shows only active tab panel: `.tab-panel:not([hidden]) { display:block !important }`.
  - `page-break-inside: avoid` on `.recommendation-card`, `.report-card`, `.signal-detail-table`, `.symmetry-row`.
  - `-webkit-print-color-adjust: exact` / `print-color-adjust: exact` on signal chips, QC badges, score bar.
  - White background, zero padding.
- No server-side PDF generation. No binary PDF response.

## Design Tokens

All design tokens from `docs/design/BREMEN_DESIGN_SPEC_v1.md` §1 verbatim:

**Colors:** `#F7F8F8`, `#FFFFFF`, `#16202A`, `#5B6570`, `#1F6F6B`, `#E3E7E6`, `#2E7D5B`, `#B8894A`, `#9AA3A8`, `#C1483D`, `#F1F5F4`, `#FBF3E9`, `#FBEEEC`.

**Typography:** System font stack, 6 sizes (`--fs-32`, `--fs-22`, `--fs-17`, `--fs-14`, `--fs-13`, `--fs-11`).

**Spacing:** 8 steps (`--sp-4` through `--sp-64`).

**Radii:** `--radius-card: 10px`, `--radius-pill: 999px`.

**Shadows:** `--shadow-card` (`0 1px 2px ... 0 1px 8px ...`).

No new hex colors. No prohibited palette entries.

## Signal Chip Color Mapping

| `difference_level` | Text Color | Background | Border | Token |
|--------------------|-----------|------------|--------|-------|
| `small` | `#2E7D5B` | `#F1F5F4` | `#2E7D5B` | `--status-available`, `--tint-accent` |
| `moderate` | `#B8894A` | `#FBF3E9` | `#B8894A` | `--status-pending`, `--tint-pending` |
| `larger` | `#C1483D` | `#FBEEEC` | `#C1483D` | `--status-error`, `--tint-error` |
| `not_available` | `#9AA3A8` | `#F7F8F8` | `#9AA3A8` | `--status-unconfigured`, `--bg-page` |

## Accessibility

- Tab buttons: `<button role="tab" aria-selected="true|false" aria-controls="panel-id" data-tab="..." tabindex="0|-1">`.
- Tab panels: `<div role="tabpanel" aria-labelledby="tab-id" id="panel-id">`.
- Tab container: `role="tablist" aria-label="Report tabs"`.
- Keyboard navigation: `keydown` listener for ArrowLeft/ArrowRight to cycle tabs.
- Visible focus: `focus-visible` with 3px `--accent` outline.
- Print buttons are real `<button>` elements — no `div-as-button`.
- `prefers-reduced-motion` suppresses spinner animation and tab transitions.
- All signal labels present as visible text — never color-only communication.
- `role="alert"` on recommendation card.

## Safety Confirmation

- No raw feature values or `feature_value` in page source. ✓
- No `percentile_cutoff` or `cutoff` in page source. ✓
- No `s3://` in page source. ✓
- No `manifest_key` in page source. ✓
- No `arn:aws` in page source. ✓
- No full checksum — only `.substring(0,8)` prefix. ✓
- No raw H5 paths (`/scans/`, `/tmp/`). ✓
- No model internals (`coefficient`, `intercept`, `scaler_mean`). ✓
- No raw exceptions (`Traceback`, `Stack trace`). ✓
- No PHI (`patient_id`, `patient_name`). ✓
- No server-side PDF dependencies (WeasyPrint, Chromium, Puppeteer, Playwright, Pango, Cairo). ✓
- Decision vocabulary unchanged. ✓
- POST /predictions schema unchanged. ✓
- Backend inference/preprocessing unchanged. ✓

## Tests Added

**New file:** `tests/test_bremen_report_ui.py` — 71 tests:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestExternalTab` | 7 | External tab existence, selection, header, audience line, tech demo notice, footer disclaimer |
| `TestInternalTab` | 2 | Internal tab existence and deselected default state |
| `TestSampleMode` | 5 | Sample data embedding, banner, clinical use prohibition, distribution prohibition, fixture labeling |
| `TestLiveModeNoSampleLeakage` | 3 | No synthetic banner, no sample JSON embedding, isSample=false |
| `TestPrintSavePDF` | 7 | Print buttons per tab, window.print wired, @media print, controls hidden, nav hidden, layout preserved |
| `TestSymmetrySignals` | 6 | Chip CSS classes, levelChipLabel function, detailLevelLabel function, calibration pending mapping, color tokens |
| `TestNotAvailableRendering` | 3 | External label "Calibration pending", internal label "Reference statistics unavailable", no fabrication |
| `TestSafetyBoundaries` | 12 | No raw feature values, no percentile cutoffs, no full checksum, no S3 paths, no manifest keys, no AWS ARNs, no H5 paths, no model internals, no exceptions, no PHI, no raw target/control refs |
| `TestServerSidePDFAbsence` | 3 | No WeasyPrint, no Chromium/Puppeteer/Playwright, no Pango/Cairo |
| `TestDesignTokens` | 3 | All hex colors approved, no prohibited colors, required tokens defined |
| `TestAccessibility` | 11 | Tab roles, tabpanel roles, aria-selected, aria-controls, tablist role, real button elements, no div-as-button, focus outline, reduced motion, semantic structure, keyboard nav, signal labels in text |
| `TestBackwardCompatibility` | 5 | No-arg call, with job_id, with base_url, HTML5 document, JS present |
| `TestSymmetrySignalDetail` | 6 | Signal detail table, feature family column, checksum prefix, reference artifact version, symmetry_signal_detail key, five signal levels |

## Validation Results

### Pre-validation
```
HEAD:   436a8ad1272097fa1f7f72e1d7c4f0445d884b83
Branch: 0093-report-rendering-and-pdf-export
Status: clean (+ new files)
```

### Compile check
```
python -m compileall src tests
→ PASS — no compile errors
```

### Test execution
```
python -m pytest -q tests/test_bremen_report_ui.py -v
→ 71 passed

python -m pytest -q tests/test_bremen_api_server.py -v
→ 104 passed

python -m pytest -q
→ 2125 passed, 11 skipped
```

### Safety greps

**Hex colors:** All 13 hex colors are approved tokens from `BREMEN_DESIGN_SPEC_v1.md`. No prohibited colors. ✓

**Sample/mockup dependency:** No live runtime dependency on sample/mockup artifacts in `src/bremen/report_ui.py`. ✓

**Unsafe exposure:** No `feature_value`, `raw_feature`, `percentile_cutoff`, `cutoff`, `model_checksum`, `manifest_key`, `s3://`, `arn:aws` in report page output. ✓

**Server-side PDF:** No WeasyPrint, Chromium, Puppeteer, Playwright, Pango, Cairo in dependencies or source. ✓

**Print behavior:** `window.print()`, `@media print`, `Print / Save PDF` all present and tested. ✓

## Non-Goals (Confirmed Not Done)

- No real reference-statistics thresholds.
- No fabricated signal buckets.
- No backend symmetry computation changes.
- No server-side PDF generation.
- No dependency additions.
- No Start Page or Control Room redesign.
- No Aramis integration.
- No clinical validation claims.
- No POST /predictions schema changes.
- No changes to `symmetry_signals.py`, `decision_support.py`, `report_bremen.py`.
- No React, frontend framework, or build step.
- No new hex colors outside BREMEN_DESIGN_SPEC_v1.md.

## Warnings

1. Report reference artifacts (`bremen_external_report.yaml`, `bremen_internal_report.yaml`, `Bremen_External_Report_SAMPLE.pdf`, `Bremen_Internal_Report_SAMPLE.pdf`) were not available. The report layout was derived from the API contract data shapes and BREMEN_DESIGN_SPEC_v1.md. Visual refinement may be needed when artifacts become available.
2. No `--tint-available` token exists in the design spec. `--tint-accent` (`#F1F5F4`) was used for `small` signal chip backgrounds as the closest available match.
3. Sample mode is a development-only artifact — not accessible from the runtime server. No sample data toggle exists in the live report page.

## Future Roadmap Note

A future calibration PR (after PR0093) must:
1. Obtain a safe aggregate reference-statistics artifact from the data science team.
2. Place it in a versioned, checksummed controlled artifact location.
3. Load it through controlled configuration (`BREMEN_REFERENCE_STATISTICS_URI`).
4. Replace `not_available` with real `small`/`moderate`/`larger` buckets.
5. Never expose raw values, raw deltas, or percentile cutoffs in report output.
6. The signal chips and detail table are already structured to display real difference levels without code changes when the data becomes available.
