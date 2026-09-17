# PR0161 — Standard Result contract hardening

Implementation complete on `0161-standard-result-contract-hardening`.
No staging, commit, deployment, or clinical-validation claim.

## Contract changes

1. `SourceMetadata.referring_physician` now flows into the common Standard Result
   field immediately after `patient_age`. Default/unavailable value is exactly
   `""`; it is never added to `specific_output` or the jobs request schema.
   The new dataclass fields are keyword-only, preserving existing positional
   constructor arguments. Existing package adapters automatically supply the
   empty default; no unsupported H5 physician aliases were introduced.
2. Both workflows use the existing common timestamp normalizer, now explicitly
   validating full calendar-date/clock-time syntax. It normalizes space to `T`,
   truncates fractional seconds, preserves minute offsets, converts `Z` to
   `+00:00`, and retains `-00:00` as an unknown-offset marker. Naive timestamps
   remain naive: timezone unknown, not UTC. Empty/invalid/date-only inputs map
   to `""`; midnight is never fabricated. Documentation now truthfully permits
   naive ISO8601 acquisition timestamps instead of requiring an invented offset.
3. Failed report responses retain `status="unavailable"` and
   `reason_code="REPORT_NOT_AVAILABLE"`, and add the safe fields below.
4. Missing physician and scan time use `""`; missing patient age and EOSCAN
   version retain `null`. Aramina mammography placeholder remains `""`.
   Caller-owned `analysis_author` and `prediction_comment` are unchanged.

## Timestamp source inspection

Both Bremen and Aramina package source adapters read their supported
`/session` acquisition `started_at` attribute verbatim into SourceMetadata.
Neither supplies evidence that naive timestamps are UTC. No package reader was
changed; formatting is enforced at the existing common mapping boundary.
Naive source example: `2025-05-28 10:19:55` becomes
`2025-05-28T10:19:55`. Aware example:
`2025-05-14T12:55:46.123+02:00` becomes `2025-05-14T12:55:46+02:00`.

## Safe failed-report envelope

The existing `get_job_report` path projects failed job/workflow records through
`api/report_failures.py` before report-provider invocation. Added keys inside
`report`:

- `failure`, `failure_stage`, `failure_reason_code`, `failure_detail`, `remediation`;
- `workflow_id`, `model_id`, `model_version`, `patient_id`, `target_side`;
- `safe_details` (empty object when none).

No `standard_result` or scientific result payload is fabricated. Known Bremen
provider messages are matched exactly to reporting categories; their gates are
not interpreted or recomputed. Unknown failures collapse to a fixed
`WORKFLOW_EXECUTION_FAILED` report. Explicit normalization failures use
`SOURCE_PREPARATION_FAILED`. Unknown optional identifiers are empty strings.

Aramina unsupported-input diagnostics are rebuilt through the existing
`unsupported_input_details`/preprocessing allowlists. Supplied detail/remediation
strings and extra nested keys are never echoed. Only bounded identifiers and
allowlisted target sides are projected. Tests inject paths, S3 locations,
tracebacks, tokens, checksums, malformed stages and nested values and confirm
that none is emitted. Existing job-detail diagnostics remain unchanged.

Failures are scoped to the requested workflow. A completed sibling remains
reportable even if the overall job failed. Configuration failures are handled;
unknown jobs/workflows and pending jobs keep their existing behavior. Existing
report providers and successful legacy payloads were not modified.

## Ownership and scientific behavior

The path remains package adapter -> SourceMetadata -> RuntimePrediction ->
generic mapper -> StandardModelResult. No generic H5 parsing, scientific field
aliases, preprocessing, feature construction, profile selection, gates,
thresholds, model artifacts, probability calculations, decision policies,
metrics, or eligibility behavior changed. **Scientific inference behavior did
not change.** Both golden fixtures differ only by the additive physician field;
probabilities, thresholds, and classifications are unchanged.

Endpoint inventory, Bearer-auth handling, model IDs, caller metadata semantics,
workflow routing, job lifecycle and duplicate/replay logic were not edited.
This work concerns software result contracts only, not clinical validation.

## Files changed

- `src/bremen/model_runtime.py` — normalized physician metadata transport.
- `src/bremen/api/standard_model_result.py` — field and canonical serialization.
- `src/bremen/api/model_result_mapper.py` — physician mapping and timestamp policy.
- `src/bremen/api/report_failures.py` (new) — safe failure projection.
- `src/bremen/api/job_api_handler.py` — use projection at existing report boundary.
- `tests/test_bremen_standard_result_hardening_pr0161.py` (new) — 38 regressions.
- `tests/test_bremen_package_metadata_adapters_pr0159.py` — additive exact-key expectations.
- `tests/fixtures/standard_model_result/bremen_v01_golden.json` — physician only.
- `tests/fixtures/standard_model_result/aramina_v0213_golden.json` — physician only.
- `docs/standard_model_result_contract_v1.md` — fields, timestamps, absence, failures.
- This directory's `PLAN.md` (created before implementation) and this report.

## Validation

- Read all requested PR0161A evidence/debt/planning documents; they match `main`.
- Focused PR0161, Standard Result, PR0158a, PR0159 metadata and package adapter
  suites: **114 passed**, 33 warnings.
- `./venv/bin/python -m compileall -q src tests`: passed.
- `./venv/bin/ruff check src tests`: **337 existing findings**. Compared every
  reported file's code/message multiset with lint of its HEAD contents:
  **zero new findings**. Six pre-existing findings are in the touched
  job_api_handler.py; other changed/new Python files pass. Unrelated lint
  cleanup was intentionally not included.
- `./venv/bin/python -m pytest -q`: **4398 passed, 13 skipped**, 1676 warnings,
  57.29 seconds. Skips include optional private scientific evidence checks.
- `git diff --check`: passed. Diff and status inspected; no staged changes.

No implementation blockers. Repository-wide lint remains pre-existing debt.
The pre-existing untracked `alexey-smoke-pack-0157/` and `results/` directories
were not modified. No private evidence was added, no commit was created.
