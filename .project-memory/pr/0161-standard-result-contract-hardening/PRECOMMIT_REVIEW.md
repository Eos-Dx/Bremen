# PR0161 Precommit Review

HEAD `99bb691a318ed79c1519f561fc68127606d91b2b` (branch == main; all changes are
unstaged/untracked working-tree state). Snapshot 2026-09-17T14:37:22Z.
Reviewer read: PR0161 PLAN.md + IMPLEMENTATION_REPORT.md; PR0161A PLAN.md,
TECHNICAL_DEBT.md, REFERRING_PHYSICIAN_SPIKE.md (REAL_CONTRACT_EVIDENCE.md checked
by path list — PR0161A docs live on the merged docs branch and match main). Every
claim below was re-verified against code, the diff, or runtime probes; none is
accepted from the coder report.

## Verdict summary

All eight primary review questions PASS. No blockers. Two non-blocking warnings
(one report-surface observation, one job-state-category observation) and several
notes. Validation independently reproduced.

## Diff scope

Modified (unstaged): `docs/standard_model_result_contract_v1.md`,
`src/bremen/api/job_api_handler.py`, `src/bremen/api/model_result_mapper.py`,
`src/bremen/api/standard_model_result.py`, `src/bremen/model_runtime.py`,
both `standard_model_result` golden fixtures, `tests/test_bremen_package_metadata_adapters_pr0159.py`.
New (untracked): `src/bremen/api/report_failures.py`,
`tests/test_bremen_standard_result_hardening_pr0161.py`, PR memory dir.
`git diff main...HEAD` is empty (work not yet committed). No package adapter,
report provider, route/schema, auth, Dockerfile, or science file touched.
All changed/new files were read in full or by complete diff in this session.

## Architecture boundary

Diff scan for new references to H5 dataset paths, session/source aliases,
physician fields, or model-specific science in generic code:
`grep -rn "physician|doctor|referr" src/bremen/api/*.py src/bremen/model_packages/*/source_metadata.py`
→ matches only the canonical `referring_physician` name in mapper/contract types;
adapters unchanged; the `h5_layouts.py:1228` match is a pre-existing
main-tracked comment outside this diff. `test_generic_mapping_has_no_source_aliases`
asserts `h5py`/`/session`/`operator_username`/`started_at`/`backfill_provenance`
absent from `model_result_mapper.py` and `report_failures.py`. The physician flows
package adapter default → `SourceMetadata` → providers' verbatim `to_dict()`
transport (PR0159 path, unchanged) → generic mapper → contract. PASS.

## Referring physician contract

- `SourceMetadata.referring_physician: str = field(default="", kw_only=True)`
  (`model_runtime.py`); `to_dict()` includes it after `patient_age`.
- Positional compatibility genuinely preserved — reviewer probe:
  `SourceMetadata(44, "2025-05-28 10:19:55", "op", "hw", "eos")` constructs with
  identical positions; `StandardModelResult` 13-arg positional construction works
  with `referring_physician` defaulting to `""`.
- `StandardModelResult` dataclass + `CANONICAL_FIELDS` + `to_envelope_dict()`
  expose it immediately after `patient_age` (runtime check: envelope keys[6]).
- Both mappers read `_clean_str(source_metadata.get("referring_physician"))` →
  unavailable/whitespace is exactly `""`; parametrized tests cover both workflows
  and `None`/`''`/`' Dr Example '` (trim, never fabricate; non-str → `""`).
- Not in `specific_output` (asserted), not in `POST /api/jobs`
  (`fastapi_contracts.py` untouched by diff and contains no physician token).
- No physician H5 alias in platform or adapters; the adapter test proves an H5
  `doctor` attribute is NOT promoted (`source.referring_physician == ''`). PASS.

## Timestamp contract

Implementation inspected directly (not just tests). Reviewer ran 15 inputs through
`normalize_timestamp`:
`'2025-05-28 10:19:55'→'2025-05-28T10:19:55'`; naive stays naive; `'…Z'→'…+00:00'`;
`'+02:00'`/`'-05:30'` offsets preserved; fractional seconds truncated;
date-only / `HH:MM` / invalid calendar / out-of-range offset / non-str → `""`;
UTC never fabricated; `-00:00` deliberately preserved (regex gate + explicit
restore because `isoformat()` would print `+00:00`). Syntax regex requires
seconds, so `2025-05-28T10:19` → `""` (fails closed, never midnight).
Both mappers share this one function. Docs now state identical semantics
(ISO8601-naive = timezone-unknown; `-00:00` = unknown offset; examples match).
No invented timezone anywhere. PASS.

## Failed report contract

`report_failures.build_failure_report` keeps `status:"unavailable"` +
`reason_code:"REPORT_NOT_AVAILABLE"` and adds failure/stage/reason/detail/
remediation/identifiers/`safe_details` only. `get_job_report` projects the
requested run **before** provider invocation (`job_api_handler.py:940-976`), so no
science executes on the failure path; tests assert absence of `standard_result`
and `payload` on every failed envelope and immutability of `run.to_dict()`
(projected from copies; `details=dict(...)`, `identity=dict(...)`).
Coverage verified by tests + reviewer probes: Bremen known failures (exact-match
`_BREMEN_FAILURES`, live probe → `requires_exactly_3_left_3_right`),
Aramina unsupported-input (rebuilt via `unsupported_input_details`),
configuration failure, generic `WORKFLOW_EXECUTION_FAILED` fallback,
`SOURCE_PREPARATION_FAILED` (via explicit flag; see W2), scoping to requested
workflow, completed sibling under `overall_status="failed"` (run-level check),
pending jobs and unknown jobs/workflows unchanged (test + code path).
No fabricated standard_result for failed jobs. PASS.

## Security / non-leakage

Adversarial probes run by this reviewer through `build_failure_report`:
paths (`/private/model.joblib`, `/etc/passwd`, `C:\Windows`), `s3://` URIs,
`Traceback token=SECRET`, nested dicts/lists as `failure`/`failure_stage`/
`failure_detail`/`remediation`/nested `safe_details`, `model_checksum`,
unallowlisted preprocessing exception classes/transformers, 200-char identifiers —
none appears in the JSON output; oversized identifiers collapse to `""`;
unknown Aramina stage collapses to `unknown_input_contract`; diagnostics are
regenerated via the pre-existing allowlist helpers
(`unsupported_input_details` + `safe_preprocessing_diagnostic`, which force
`redacted`/`worker_process` for unknown values and emit only fixed scalar keys);
Aramina detail/remediation come from fixed `_STAGE_DETAIL`/`_STAGE_REMEDIATION`
tables. Bremen matching is exact-dict membership — no substring reflection
(probe: `'Feature construction failed: totally_private_internals'` →
`WORKFLOW_EXECUTION_FAILED`, no echo). New test
`test_failure_report_never_echoes_raw_material` parametrizes the same attack set.
Non-string `failure` and non-dict `details` degrade safely. PASS.

## Backward compatibility

No report provider (`report_bremen.py`, `report_aramina.py`,
`report_provider.py`), route, auth, schema, or job-lifecycle file is in the diff.
The FastAPI report routes delegate to `get_job_report` for
`/demo/api/jobs/{id}/reports/{workflow}` (behavior changed only additively); the
independent external/internal report routes were not edited and never carried
`standard_result`. Success payload retains `payload` + `standard_result` +
identity (test `test_successful_report_preserves_legacy_science_and_failed_sibling`
asserts legacy payload presence and scientific-field equality vs pre-change
mapping). Golden fixtures show only the additive `"referring_physician": ""`
insertion; `eoscan_version` was already `null` on main from PR0159 (main doc's `""`
example was the known PR0159 W1 drift, now fixed in this diff). `patient_age`/
`eoscan_version` null semantics and caller-owned `analysis_author`/
`prediction_comment` untouched. Failed responses remain supersets of
`{status, reason_code}`. PASS.

## Scientific regression check

Diff contains no preprocessing, H5-parsing, features, gate, profile, artifact,
probability, threshold, metrics, policy, or eligibility code (changed files list
above). Runtime probe on main-checkout code (worktree == HEAD commit for
untracked science paths unchanged): artifact SHA256
`65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` verified;
Nova_227 authoritative raw-package path → probability
`0.7726940329943811` (isclose abs 1e-10 vs task's
`0.7726940329943809/…1` last-digit drift is float-repr only), threshold
`0.3585907282566089` unchanged. Aramina baseline fixtures
`0.869387073973647`/`0.24665932038818544` intact in PR0158a tests (all pass).
`0.980462…` appears nowhere in `src`/`tests`/`docs` (only in untracked
pre-0160 evidence dirs, correctly unused as a baseline). PASS.

## Missing-value semantics

Narrow, exactly as required: physician `""`, scan_date_time `""`,
patient_age `null`, eoscan_version `null` — documented in a dedicated table and
asserted in tests (`referring_physician == ''`, `patient_age is None`,
`eoscan_version is None`). No other null/empty rewrites anywhere in the diff
(fixture diffs are physician-only; `analysis_author`/`prediction_comment`
handling untouched). PASS.

## Validation results

```
git status --short            → 8 modified + 3 PR-relevant untracked; nothing staged
git diff --check              → exit 0        git diff --cached --check → exit 0
git diff main...HEAD          → empty (work uncommitted, as intended)
compileall -q src tests       → exit 0
ruff check src tests          → 337 findings (pre-existing debt)
  • report_failures.py, pr0161 tests, mapper, standard_model_result,
    model_runtime, pr0159 tests: "All checks passed"
  • job_api_handler.py: 6 findings now == 6 findings at HEAD (same codes/
    messages multiset; independently diffed via git show HEAD | ruff -)
  → zero new findings introduced by PR0161 (verified, not accepted from report)
pytest -q tests/test_bremen_standard_result_hardening_pr0161.py
      + standard_model_result_v1 + pr0158a + pr0159 metadata (both files)
                              → 114 passed (matches report)
pytest -q                     → 4398 passed, 13 skipped (13 = pr0160 11 +
                              pr0158a 2 optional evidence skips; report's
                              "Skips include optional private scientific
                              evidence checks" consistent)
```
Additional reviewer probes (timestamp matrix, positional constructors, five
adversarial failure-report payloads, Nova_227 runtime parity, normalization-path
smoke) all behaved as documented.

Git hygiene: nothing staged; no new commit (HEAD == main); `results/` and
`alexey-smoke-pack-0157/` untouched and excluded from the diff; no private
evidence, tokens, JWTs, H5/joblib files, or generated smoke data in any changed
file (fixture diffs are one key each; test inputs use `SYNTH-*`/private-sentinel
strings only).

## Findings

### Blockers
None.

### Warnings
W1 — Report-surface asymmetry: `handle_job_reports` (job reports list),
`handle_external_report`/`handle_internal_report` and the FastAPI external/
internal routes were intentionally left on the old shape; the new failure
envelope lands only on `GET /demo/api/jobs/{job_id}/reports/{workflow_id}`
(+ its FastAPI mirror, `fastapi_app.py:1237-1240`). Additive and in-scope, but
the surfaces now differ; consider unifying in a follow-up.
W2 — Dead-ish `SOURCE_PREPARATION_FAILED` branch on the real job API:
`create_analysis_job:677-681` sets `overall_status="failed"` (never
`"normalization_failed"`) for normalization failures, so `get_job_report`'s
`normalization_failed=True` only occurs if another writer sets that status; a real
normalization-failed job reports `WORKFLOW_EXECUTION_FAILED` (reviewer probe
confirmed). Still truthful and safe (no leakage, no fabrication), and the branch
is directly unit-tested. Consider mapping the job handler's normalization
failure to `"normalization_failed"` (or removing the unreachable branch) in a
follow-up.

### Notes
- Golden JSON inserts `referring_physician` after `patient_age` while other keys
  stay alphabetical; comparison in `test_bremen_standard_model_result_v1.py` is
  dict-equality, so order is cosmetic (envelope order is correct and asserted).
- Exact-match `_BREMEN_FAILURES` couples reporting to provider message strings;
  unknown strings already degrade safely to `WORKFLOW_EXECUTION_FAILED` — acceptable.
- The PR0161A `REAL_CONTRACT_EVIDENCE.md` doc directory ships on the already-
  merged docs PR (99bb691), not in this working diff; PR0161's contract claims
  match it.
- `0.7726940329943809` (task) vs `0.7726940329943811` (observed/test) is a 2-ulp
  float-representation difference covered by `abs_tol=1e-10`; not drift.

READY FOR COMMIT
