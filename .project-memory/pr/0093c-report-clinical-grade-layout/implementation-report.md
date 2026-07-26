# PR0093C — Implementation Report

## Branch / HEAD

- **Branch:** `0093c-report-clinical-grade-layout`
- **HEAD:** `e6e9ddeaf44df0a082a9a9a9125af6d22b9d53d8`

## Files Changed

| File | Action |
|------|--------|
| `src/bremen/report_ui.py` | Modified — CSS + JS layout upgrade |
| `tests/test_bremen_report_ui.py` | Modified — updated + added tests |

## Aramis Visual Lessons Used

1. **Report masthead** with eyebrow label and structured metadata grid
2. **Dark assessment hero** with kicker, title, subtitle, and metric cards
3. **Two-column analysis information grid** (internal)
4. **Confidential strip** header (internal)
5. **Method & limitations section** with structured list
6. **Supporting evidence section** with clear section headings
7. **Paper-like print layout** with page-break-inside: avoid

## Aramis Content Explicitly NOT Copied

- Tissue Risk Assessment / TRA
- biopsy recommended / biopsy not recommended
- malignant-like patterns
- method sensitivity / specificity
- patient name / surname / age / operator / referring physician
- raw per-measurement probabilities
- raw symmetry feature values
- Aramis algorithm names
- Aramis colors or logo

## Bremen Terminology Preserved

- MRI continuation decision support
- p_mri_needed score
- decision threshold
- QC status
- left/right structural comparison
- Calibration pending (not "Asymmetry assessment is not available")
- Technical demonstration / not clinically validated / not diagnosis
- Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment

## External Layout

1. **Report masthead** — Bremen brand, eyebrow "NON-INVASIVE X-RAY DIFFRACTION ANALYSIS", title, subtitle, metadata grid (Report ID, Generated, Job ID, Request ID)
2. **Assessment hero** (dark, `var(--text-primary)` background) — "MRI CONTINUATION REVIEW" kicker, decision display name, explanation, metric cards (Model Score, Threshold, QC Status, Decision Code)
3. **Decision policy text** — italic policy identifier
4. **Technical demo notice** — visually secondary, tinted amber
5. **Supporting evidence** — signal card grid with 5 signals, "Calibration pending" for not_available
6. **Decision interpretation** — two interpretation cards (DEFER / CONTINUE)
7. **Method & limitations** — structured list on tinted background
8. **Model & provenance** — field table
9. **Footer** — compact safety disclaimer

## Internal Layout

1. **Confidential strip** — dark banner "CONFIDENTIAL — RESEARCH USE ONLY"
2. **Internal header** — brand, running title, title, subtitle, pills
3. **Internal assessment hero** (dark) — decision code, score, threshold, QC
4. **Analysis information** — two-column grid (job identity + model/plugin)
5. **Decision policy** — field table
6. **Boundary note** — checksum prefix only, no PHI
7. **Symmetry signal breakdown** — table with "Reference calibration pending"
8. **Execution trace** — field table
9. **Method & safety disclaimer** — internal-method-note
10. **Footer** — CONFIDENTIAL language

## Safety Decisions

- No raw feature values, deltas, percentile cutoffs, or reference-statistic values
- Checksum prefix only (max 8 hex chars)
- No S3 paths, manifest keys, ARNs, H5 paths, PHI, model internals
- Clinical wording: decision-support only, not diagnosis, not clinically validated
- No sample values in live reports
- No Aramis terminology
- Print: browser-native only, no server-side PDF

## Print / PDF Behavior

- `window.print()` only
- `@media print` hides tabs, print buttons, navigation, loading
- `print-color-adjust: exact` on 12 tinted/colored elements
- `page-break-inside: avoid` on cards, tables, hero blocks
- A4-friendly layout with generous margins

## Tests Added / Updated

- **144 total tests** in test_bremen_report_ui.py (all pass)
- Updated: TestReportHTMLStructure (new clinical-grade class assertions)
- Updated: TestNotAvailableRendering (new copy assertions)
- Updated: TestPrintSavePDF (new classes covered)
- Updated: TestSymmetrySignalDetail (new copy)
- Added: TestClinicalGradeStructure (13 tests — masthead, hero, info grid, method/limitations, etc.)
- Added: TestInternalClinicalGrade (10 tests — confidential strip, info grid, assessment hero, method note, etc.)

## Validation Commands

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `python -m pytest -q tests/test_bremen_report_ui.py -v` | 144 passed |
| `python -m pytest -q tests/test_bremen_api_server.py -v` | 104 passed |
| `python -m pytest -q` | 2197 passed, 1 pre-existing failure, 11 skipped |
| `git diff --check` | PASS |
| Safety greps | All pass |

## Blockers

None.

## Warnings

1. Pre-existing false positive in `test_bremen_control_room.py::test_report_no_bucket_name` — English word "buckets" triggers overly broad substring check. Outside allowed edit scope.

## Next Required Action

1. Human visual review of /demo/report/{job_id} in browser
2. Compare screenshots against Bremen_External_Report_SAMPLE.pdf and Bremen_Internal_Report_SAMPLE.pdf
3. Confirm investor-ready visual impression
