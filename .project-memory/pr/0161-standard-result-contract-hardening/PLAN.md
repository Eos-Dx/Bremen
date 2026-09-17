# PR0161 implementation plan

Scope: additive Standard Result metadata and safe failed-report representation.
No scientific inference, artifact, Docker, auth, routing, job lifecycle, request,
threshold, probability, or policy changes. Branch already matches the task.

## Exact planned files

- src/bremen/model_runtime.py: SourceMetadata.referring_physician, default "".
- src/bremen/api/standard_model_result.py: common physician field immediately
  after patient_age in canonical serialization.
- src/bremen/api/model_result_mapper.py: consume only normalized physician
  metadata; shared deterministic timestamp syntax policy.
- src/bremen/api/report_failures.py (new): narrow shared public failure projection.
- src/bremen/api/job_api_handler.py: use failure projection at existing report
  endpoint for failed workflow runs/jobs, including configuration failures.
- tests/test_bremen_standard_result_hardening_pr0161.py (new): metadata, timestamp,
  failure endpoint, privacy, and success compatibility regressions.
- tests/fixtures/standard_model_result/{bremen_v01,aramina_v0213}_golden.json:
  insert only referring_physician=""; preserve scientific values.
- Existing metadata contract tests only where exact source key sets need updating.
- docs/standard_model_result_contract_v1.md: truthful field and failure semantics.
- This directory's IMPLEMENTATION_REPORT.md after validation.

Existing report_bremen.py and report_aramina.py inspected: the public sparse
failure branch is in job_api_handler.get_job_report, before provider invocation.
Implement there rather than changing successful provider payloads. Current package
source adapters read started_at verbatim and declare no authoritative referring
physician field; SourceMetadata's empty default supplies it without H5 aliases.

## Compatibility and timestamp policy

Physician is common, additive, immediately after age, not specific_output and
not a new REST request field. Missing/invalid physician => "". Age and
EOSCAN-version missing values remain null; other legacy fields are unchanged.
Caller analysis_author/prediction_comment stay request-owned.

Use the existing shared normalize_timestamp boundary for both workflows:
full calendar date and clock time required, normalize space/T separator to T,
strip fractional seconds, preserve explicit minute offsets, normalize Z to
+00:00. Naive date-times stay naive, explicitly meaning timezone unknown (an
ISO8601 exception to the former strict RFC3339 wording). Never infer UTC.
Empty/invalid/date-only values => ""; do not invent an acquisition clock time.
No reinterpretation of acquisition time; package adapters remain unchanged.

## Failure report shape

Keep report.status="unavailable" and reason_code="REPORT_NOT_AVAILABLE".
Add failure, failure_stage, failure_reason_code, failure_detail, remediation,
workflow_id, model_id, model_version, patient_id, target_side, safe_details.
No payload or standard_result is fabricated. Optional scalar metadata uses "";
safe_details uses {}. Existing job diagnostics are not mutated.

Only exact known public failure strings are echoed. Unknown failures collapse
to WORKFLOW_EXECUTION_FAILED with fixed explanatory text. Bremen's existing
public messages map to fixed reporting categories without interpreting model
science. Aramina unsupported-input diagnostics are regenerated through the
existing public allowlisting helper, not copied wholesale; raw details,
remediation and unknown nested keys cannot leak. Identifiers/side are sanitized.
Failure is scoped to the requested workflow; completed sibling workflows retain
successful reports. Unknown jobs/workflows and pending jobs retain prior behavior.

## Tests and validation

Cover both workflows: field ordering, default and actual normalized physician,
no generic H5 paths, package defaults, timezone-aware/naive/invalid dates,
unchanged scientific values and legacy success payloads, failed reports without
provider/science execution, malformed/private details, unknown codes,
normalization failure, configuration failure, pending/missing workflow, mixed
workflow status, and job-diagnostic immutability. Update golden fixtures only
for the additive field. Run focused suites first, compileall, ruff check src tests,
full pytest, git diff --check, review diff/status. No staging or commit.
