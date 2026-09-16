# PR0158a Pre-Commit Review — Standard Model Result Contract Hardening

## Scope reviewed
Branch `0158a-standard-result-contract-hardening`; HEAD `0cdc3e312f6ea9d31dfe66914e4a0094e3c49936`
(on top of the merged PR0157 line: #218 contract docs, #219 mapper implementation).
The PR0158a change is the **current uncommitted working-tree diff**:

- `M src/bremen/api/fastapi_contracts.py` (+8 lines: four optional request fields)
- `M src/bremen/api/job_api_handler.py` (+27/−2: stable Standard Model Result identity sourcing)
- `?? tests/test_bremen_standard_result_hardening_pr0158a.py` (NEW, 12 tests)

Untracked and **not part of the diff**: `alexey-smoke-pack-0157/` and `results/`
(operator-only live smoke artifacts — see Diff hygiene). No PR memory
PLAN/IMPLEMENTATION_REPORT exists for 0158a; all findings below were verified
directly against the working tree. HEAD additionally carries
`0cdc3e3` ("test: tolerate platform float drift in Bremen golden result") —
reviewed under §Bremen parity (it aligns the golden assertion with the frozen
contract tolerance).

## Contract checks
1. **Standard Model Result identity stability — FIXED.** `get_job_report()` now
   snapshots `stored_report = job.reports.get(workflow_id)` under the same
   `_jobs_lock` that reads `wf_run` (consistent with `_generate_job_reports`/
   report-delete, which mutate `job.reports` under that lock), and sources
   canonical identity from the **stored ReportMetadata**:
   - `standard_result.report_id` ← `stored_report.report_id`
   - `standard_result.created_at` ← `stored_report.generated_at` (raw stored
     value; still normalized by the mapper)
   with a fallback to the freshly generated envelope **only** when no stored
   report exists (legacy/test-only jobs), preserving prior behavior there.
   `job.reports[wid]` is populated at job completion by `_generate_job_reports`
   (`ReportMetadata(report_id=report.report_id, generated_at=report.generated_at, …)`),
   which is the authoritative stable source required by the task.
2. **Timestamp contract — preserved.** The existing shared
   `model_result_mapper.normalize_timestamp()` is reused (called on the stored
   `generated_at`); **no duplicate normalization logic** was introduced (grep:
   the only normalization implementation remains in the mapper; the handler passes
   the raw stored string). Offsets are preserved (not forced to UTC, no `Z`
   requirement), fractional seconds removed, naive values not coerced; absent
   source → `""` (no fabrication); `scan_date_time` remains `""` for both models.
3. **Aramina requirements validation request contract — FIXED.**
   `ModelRequirementsValidateRequest` now declares `patient_id`, `target_side`,
   `analysis_author`, `prediction_comment` (all `Optional[str] = None`). They
   therefore survive `req.model_dump(exclude_none=True)` (`fastapi_app.py:413`)
   and reach the existing validation layer (`model_requirements.
   _validate_request_payload`) intact — request-contract **preservation**, not
   duplicated Aramina validation logic in FastAPI. Omitting the fields leaves the
   dump unchanged (Bremen no-op path preserved).

## Bremen stability findings
`test_bremen_standard_result_identity_stable_across_gets` (two reads of the same
completed Bremen job → identical `standard_result.report_id` and `created_at`)
and `test_bremen_standard_result_identity_from_stored_report_metadata`
(canonical values equal `job.reports["bremen"].report_id` /
`normalize_timestamp(job.reports["bremen"].generated_at)`; seconds precision; no
fractional part; offset preserved) both **pass**. Scientific fields unchanged:
golden `risk_probability` ≈ 0.7388733541967353 (abs 1e-10), threshold
0.3585907282566089, level `high`, `specific_output == {}`, and legacy
`payload.score_and_threshold.p_mri_needed` identical. **PASS.**

## Aramina stability findings
`test_aramina_standard_result_identity_stable_across_gets` and
`test_aramina_standard_result_identity_from_stored_report_metadata` **pass**
(stored-metadata equality after normalization). The structural mapping matches the
known live technical-demo reference values encoded in the test fixture
(0.869387073973647 / 0.24665932038818544 / `high` / `Nova_Synth` / `left`):
`external_report.risk_probability` → `risk_probability` verbatim,
`external_report.decision_threshold` → `threshold_value` verbatim,
`specific_output = {"target_side": "left", "mammography_suspicious_field": ""}`,
and the legacy `payload.risk_score`/`technical_demo_only` contract untouched.
`test_legacy_envelope_report_id_still_freshly_generated` explicitly proves the
scope boundary: legacy `.report.report_id` remains fresh-per-GET (unchanged
historical behavior) while `standard_result.report_id` is stable. **PASS.**

## Timestamp findings
- `test_normalize_timestamp_fractional_seconds_with_tz` proves the exact required
  example: `"2026-09-16T12:29:53.320768+00:00"` → `"2026-09-16T12:29:53+00:00"`.
- `test_normalize_timestamp_preserves_offset_no_utc_conversion` proves `+02:00`
  stays `+02:00` (no UTC coercion, no `Z` requirement).
- Reused implementation verified: `normalize_timestamp` is imported from
  `bremen.api.model_result_mapper`; no second normalizer exists (grep).
- Absence: `stored_report.generated_at` falsy → falls back to the fresh envelope
  value; mapper normalizer returns `""` for empty/unparseable — nothing fabricated.
- PR0157's normalization tests remain green (offset-preserving, idempotent,
  naive-preserving variants).

## Aramina requirements-validation findings
- Model-level: `test_requirements_request_model_preserves_aramina_fields` proves
  `patient_id`, `target_side`, `analysis_author`, `prediction_comment` survive
  `ModelRequirementsValidateRequest(**body).model_dump(exclude_none=True)` intact.
- Absence: `test_requirements_request_model_bremen_absence_unchanged` proves a
  Bremen-style body without patient/side dumps without those keys (request shape
  unchanged for existing consumers).
- Route-level: `test_aramina_requirements_validate_preserves_patient_and_side`
  posts a valid Aramina request (container/source + `patient_id` + `target_side`)
  with auth enabled and asserts `missing_required_fields` no longer contains
  `patient_id`/`target_side` and `failure_stage != "request_payload"` (the dry run
  is forced to fail at source resolution, isolating the request-payload stage).
- Bremen regression: `test_bremen_requirements_validate_behavior_unchanged`
  proves a Bremen entry requiring only container_id+source_id still validates with
  `missing_required_fields == []` and no `request_payload` failure. **PASS.**

## Legacy compatibility findings
- Diff scope is strictly the two fixes plus tests; no endpoint, auth, job-creation,
  registry, discovery, rerun-protection, or report-provider logic touched
  (`fastapi_app.py` untouched by this diff; route table re-verified: 29 routes,
  set-identical to the PR0157 baseline).
- Legacy Bremen report payload (`score_and_threshold.p_mri_needed`, disclaimer
  fields) and legacy Aramina payload (`risk_score`, `technical_demo_only`,
  `external_report` shape) asserted unchanged by the new tests and by the
  passing PR0157 compatibility suite (48 tests green across both standard-result
  files).
- `standard_result` attachment remains conditional on `workflow_status ==
  AVAILABLE` with finite probability/threshold — failed/unavailable reports
  continue to serialize without `standard_result` (PR0157 tests re-run green).
- Additive-only confirmed: the fresh legacy envelope identity semantics are
  explicitly regression-tested as unchanged.

## Model-science boundary findings
The diff touches only a Pydantic request contract and the report-read identity
sourcing. **No change** to Bremen or Aramina preprocessing, feature generation,
estimator execution, probability calculation, thresholds, `>=` decision
semantics, manifests, or package contents (packages not in the diff; parity and
conformance suites green). The mapper is unchanged and remains a translation
boundary: no probability recomputation/rounding, no new threshold, no invented
metrics or patient metadata, no coefficient inspection. Bremen parity
(207-test run) and Aramina suites (323-test run incl. runtime/provider/scaffold/
direct package) pass.

## Test evidence
- `pytest -q tests/test_bremen_standard_result_hardening_pr0158a.py` → **12 passed**
  (Bremen stability ×2 + science-unchanged; Aramina stability ×2 + legacy-envelope
  distinction; timestamp ×2 incl. the required example; request-model preservation
  ×2; route-level Aramina validation + Bremen validation regression).
- `pytest -q tests/test_bremen_standard_model_result_v1.py
  tests/test_bremen_standard_result_hardening_pr0158a.py` → **48 passed**
  (PR0157 suite green against the hardening change).
- `pytest -q tests/test_bremen_model_requirements_api.py
  tests/test_bremen_fastapi_model_api_docs_parity.py` → **54 passed**.
- Job/report/freeze/decision suites → **146 passed**; Model Package Standard +
  dedup + Aramina runtime/provider/scaffold/package → **323 passed**; Bremen
  package + PR0151/0152/0154 parity + workflow + contract → **207 passed**.
- `python -m compileall -q src` → **exit 0**.
- Full `pytest -q` → **4298 passed, 11 skipped, 0 xfailed** (45.7s, exit 0;
  4298+11 = 4309 = exact collection count).
- Collection vs pre-change baseline (stashed): **4296 → 4309 = +13, 0 removed**
  (12 new hardening tests + 1 auto-parametrized no-server-spawning case for the
  new test file). No scientific regression test removed or weakened; the only
  test *modified* on the branch (commit `0cdc3e3`, already part of HEAD) replaces
  a bit-exact Bremen golden assertion with the frozen-contract tolerance
  (`abs=1e-10, rel=0`) **plus a stronger verbatim-mapping assertion**
  (`standard_result.risk_probability == payload.score_and_threshold.p_mri_needed`)
  — appropriate per the task's §6 and not a weakening of the scientific contract.
- `git diff --check` → **exit 0** (no whitespace errors).
- Ruff on changed files: 6 findings in `job_api_handler.py`, **verified
  pre-existing at HEAD** (identical rules, lines shifted by the +27 hunks);
  `fastapi_contracts.py` and the new test file clean; zero new findings.
- No PR0158a implementation report exists in PR memory; all counts above were
  produced by running the commands in this review, not accepted from claims.

## Diff hygiene
- Diff is minimal and focused: 2 production files (13/27-line hunks) + 1 new test
  file; no unrelated refactors, formatting churn, renames, dead code, or
  duplicate timestamp logic (the shared normalizer is reused, not copied).
- No accidental endpoint changes (route table re-verified identical), no legacy
  payload changes, no generated artifacts **in the diff**.
- **Flag (non-blocking, action required before commit):** the untracked operator
  directories `alexey-smoke-pack-0157/` and `results/` contain live smoke output,
  including **JWT access tokens** in `auth.json` files
  (`"access_token":"eyJ…"`), and are **not covered by `.gitignore`**. They are not
  part of the reviewed diff and must **not** be `git add`-ed/committed; recommend
  gitignoring or deleting them (and treating the embedded tokens as ephemeral —
  they were issued by the local/live smoke runs).
- No model-science logic outside packages; no secrets in the production diff.

## Blocking issues
None. Both confirmed defects are fixed exactly as specified, scoped to
`report.standard_result` and the request contract respectively, with direct
regression tests for both models, no scientific change, and no legacy
compatibility regression.

## Non-blocking observations
1. Smoke artifacts with live JWTs are untracked but not gitignored (see Diff
   hygiene) — remove/ignore before any `git add -A`.
2. `standard_result.report_id` can now legitimately differ from the same
   response's legacy `report.report_id` (stored vs freshly generated). This is the
   explicitly required scope boundary and is regression-tested; consumers of the
   legacy envelope are unaffected.
3. The fallback path (no stored report → fresh envelope identity) preserves the
   PR0157 behavior for legacy/in-memory jobs; stored metadata is the expected path
   for every completed job produced through the normal lifecycle.
4. Branch-base note: HEAD also carries commit `0cdc3e3` (golden-tolerance test
   alignment), reviewed above; it is consistent with §6 and the frozen contract.

## Final verdict

Both confirmed platform-contract defects are fixed exactly and only as specified:
Standard Model Result identity/timestamp now derive from the authoritative stored
`job.reports[workflow_id]` metadata (stable across repeated GETs for Bremen and
Aramina, normalized by the existing shared normalizer, legacy envelope semantics
untouched), and `ModelRequirementsValidateRequest` preserves
`patient_id`/`target_side` (+ author/comment parity fields) through
`model_dump(exclude_none=True)` so Aramina requirements validation no longer
spuriously reports them missing while Bremen validation is unchanged. All model
science, thresholds, decisions, manifests, and packages are untouched; legacy
compatibility is additive-only; all required tests exist and pass; full pytest,
compileall, Ruff (no new findings) and `git diff --check` are clean.

READY FOR COMMIT
