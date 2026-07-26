# PR0093D — Implementation Report

## Branch / HEAD

- **Branch:** `0093d-report-data-contract-fill`
- **HEAD:** `97c9dd716a5d15daae4546a32bbe6183a9899b70`

## Files Changed

| File | Action |
|------|--------|
| `src/bremen/report_ui.py` | Modified — builders + JS hero fix |
| `tests/test_bremen_report_ui.py` | Modified — 27 new tests added |

## Root Cause

`build_external_report_json()` searched for `payload["decision_support_report"]` → `prediction_summary` shape (legacy), but the actual `BremenReportProvider._build_report()` produces a v0.2 payload with different keys:

- `payload["score_and_threshold"]` (not `prediction_summary`)
- `payload["measurement_qc_summary"]` (not `qc_status` at top level)
- `payload["model_identity"]` (not `model_metadata`)
- `payload["audit_information"]` (for timestamps)
- `payload["workflow_readiness"]` (for status)

The envelope-level `workflow_status` was not read for `job_identity.status`.

The JS internal hero read `policy.threshold_value` for both Score and Threshold.

## Real Source Paths Found

### BremenReportProvider v0.2 envelope:
```
envelope["job_id"], envelope["generated_at"], envelope["workflow_status"]
envelope["model_version"], envelope["report_id"]
```

### BremenReportProvider v0.2 payload:
```
payload["score_and_threshold"]["p_mri_needed"] = probability
payload["score_and_threshold"]["threshold"] = threshold
payload["score_and_threshold"]["triage_recommendation"] = decision code
payload["measurement_qc_summary"]["qc_status"]
payload["measurement_qc_summary"]["qc_flags"]
payload["model_identity"]["model_version"]
payload["model_identity"]["feature_schema_version"]
payload["model_identity"]["model_checksum"]
payload["supporting_technical_evidence"]["symmetry_signal_detail"]
payload["audit_information"]["job_id"], ["generated_at"]
payload["workflow_readiness"] — configured, model_ready, scientifically_certified
```

## External Fields Fixed

- `prediction_summary.p_mri_needed` — now reads from `score_and_threshold.p_mri_needed`
- `prediction_summary.decision_code` — now reads from `score_and_threshold.triage_recommendation`
- `prediction_summary.qc_status` — now reads from `measurement_qc_summary.qc_status`
- `prediction_summary.qc_flags` — now reads from `measurement_qc_summary.qc_flags`
- `prediction_summary.decision_display_name` — derived from decision_code
- `model_metadata.model_version` — now reads from `model_identity.model_version`
- `model_metadata.threshold_value` — now reads from `score_and_threshold.threshold`
- `generated_at` — now reads from `envelope["generated_at"]`
- `report_id` — now reads from `envelope["report_id"]`

## Internal Fields Fixed

- `job_identity.status` — now reads from `envelope["workflow_status"]`
- `job_identity.completed_at` — now reads from `envelope["generated_at"]`
- `decision_policy.decision_code` — now reads from `score_and_threshold.triage_recommendation`
- `decision_policy.threshold_value` — now reads from `score_and_threshold.threshold`
- `decision_policy.qc_status` — now reads from `measurement_qc_summary.qc_status`
- `decision_policy.score` (NEW) — now reads from `score_and_threshold.p_mri_needed`
- `model_and_plugin.model_version` — now reads from `model_identity.model_version`
- `model_and_plugin.model_checksum_prefix` — now reads from `model_identity.model_checksum`
- JS hero: Score now reads `policy.score` instead of `policy.threshold_value`

## Fallback Behavior

- Legacy `decision_support_report` → `prediction_summary` shape still searched
- Empty/old reports render `—` without crashing
- Safe defaults preserved for genuinely absent data

## Visual Structure Preserved

All PR0093C classes remain: clinical-report-page, report-masthead, assessment-hero, assessment-metric-card, interpretation-grid, supporting-evidence, method-limitations, confidential-strip, internal-assessment, internal-info-grid, internal-method-note, signal-breakdown-table, execution-trace-summary

## Safety Confirmation

- No raw feature values, deltas, percentile cutoffs, or reference-statistic values
- Checksum prefix only (max 8 hex chars)
- No S3 paths, manifest keys, ARNs, H5 paths, PHI, model internals
- No sample values as live fallback
- No fabricated thresholds

## Tests Added / Updated

- 171 total tests in test_bremen_report_ui.py (all pass)
- 27 new tests:
  - TestPR0093DInternalDataFill (9 tests)
  - TestPR0093DExternalDataFill (7 tests)
  - TestPR0093DConsistency (3 tests)
  - TestPR0093DSymmetryDetail (3 tests)
  - TestPR0093DOldJobFallback (2 tests)
  - TestPR0093DHeroRendering (2 tests)
  - TestPR0093DVisualStructurePreserved (1 test)

## Validation Commands

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `python -m pytest -q tests/test_bremen_report_ui.py -v` | 171 passed |
| `python -m pytest -q tests/test_bremen_api_server.py -v` | 104 passed |
| `python -m pytest -q` | 2224 passed, 1 pre-existing failure, 11 skipped |
| `git diff --check` | PASS |
| Safety greps | All pass |

## Blockers

None.

## Warnings

1. Pre-existing false positive in `test_bremen_control_room.py::test_report_no_bucket_name`.

## Next Required Action

1. Deploy and verify a real completed Bremen job report
2. Confirm Internal assessment hero shows real score/threshold/QC
3. Confirm External prediction_summary fields populate from real data
4. Verify QC status matches between External and Internal
