# PR0157 Pre-Commit Review — Standard Model Result Contract v1

## Scope
Branch `0157-standard-model-result-contract-v1`; main `957c373` (PR0157 implementation
base) → HEAD `4f643337110e70365e64a162ec4f183077de73ae` ("docs: define standard model
result contract v1": contract + ADR-0018 + roadmap, read completely) → working tree
(the implementation, reviewed as produced). No commit/push created by this review.
The complete diff against main = the three committed docs + the working-tree
implementation below. Every claim in the IMPLEMENTATION_REPORT was independently
re-verified against code and commands.

## Files reviewed (all read completely)
- NEW `src/bremen/api/standard_model_result.py` — frozen canonical dataclass.
- NEW `src/bremen/api/model_result_mapper.py` — the single mapping boundary.
- MOD `src/bremen/api/report_provider.py` (+6: optional `standard_result` envelope
  field; serialized only when set).
- MOD `src/bremen/api/job_api_handler.py` (+91/−1: sanitizer, additive
  `analysis_author`/`prediction_comment` kwargs + `input_summary` keys,
  `_mapper_job_context`, one integration point in `get_job_report`).
- MOD `src/bremen/api/fastapi_app.py` (+5: forwards raw-body author/comment into
  `create_analysis_job`; no route/auth/schema change).
- NEW `tests/test_bremen_standard_model_result_v1.py` (36 tests),
  NEW `tests/fixtures/standard_model_result/{bremen_v01,aramina_v0213}_golden.json`
  (synthetic metadata; authoritative numbers only).
- Docs at HEAD: `docs/standard_model_result_contract_v1.md`,
  `docs/adr/0018-standard-model-result-contract-v1.md`,
  `docs/model_architecture_roadmap_0157_0162.md`.
Untracked scan: no binaries, no H5/joblib/ZIP, no private data.

## Contract assessment
**Implemented in production code — not documentation-only.** `StandardModelResult`
is a frozen dataclass whose `CANONICAL_FIELDS` exactly match the contract's 18
top-level fields in the documented order (report_id, created_at, analysis_author,
prediction_comment, patient_id, patient_age, scan_date_time, operator_id,
hardware_version, eoscan_version, model_name, model_version, model_method,
model_metrics{sensitivity,specificity}, threshold_value, risk_probability,
target_class_risk_level, specific_output — asserted by test). The high/low
vocabulary is exactly {`high`,`low`} (constants, set-inclusion tested).
`specific_output` is always a `dict` (`{}` Bremen; Aramina extension object).
The mapper is real and wired into the live report path (`get_job_report`, which the
legacy `handle_job_report` delegates to — both public report routes covered), so the
contract is observable through existing endpoints without any endpoint change.

## Architecture assessment
**Matches the required flow.** Model package runtime result (native) + platform/
source metadata → `bremen.api.model_result_mapper.build_standard_result`
(workflow_id dispatch, `_MAPPERS`) → `StandardModelResult.to_envelope_dict()` →
`ReportEnvelope.standard_result` (optional, additive) → existing API/report
consumers. The mapper/schema live in `api/` (platform integration concern); they
import only the two package **manifests** (platform→package, the allowed direction)
— never package science internals. Model packages do not import the schema/mapper
(Model Package Standard conformance suites re-run green; packages unchanged in this
diff). `ModelRuntime` remains the only runtime contract — no second runtime
abstraction, no base class, no model-specific API framework (the schema is a plain
dataclass matching `api/*` conventions; Pydantic remains reserved for inbound
requests and was deliberately not used).

## Field-source audit (independently traced)
Classification per contract legend (GEN platform-generated / SRC source-container /
RUN model runtime result / PKG package manifest / ART artifact metadata / MAP
compatibility mapping):

| Field | Bremen | Aramina |
| --- | --- | --- |
| report_id | GEN (`envelope.report_id`) | GEN (same) |
| created_at | GEN (`generated_at`, tz-aware UTC) normalized | same |
| analysis_author | SRC (sanitized request metadata; `""` if absent) | same |
| prediction_comment | SRC (same convention) | same |
| patient_id | SRC (`patient_display_name` from H5 metadata) | same |
| patient_age | SRC absent → `null` | SRC absent → `null` |
| scan_date_time | SRC absent → `""` | same |
| operator_id / hardware_version / eoscan_version | SRC absent → `""` | same |
| model_name | PKG (`bremen_v01.manifest.MODEL_NAME`) | ART (`external_report.model_name`) else PKG |
| model_version | RUN (`result_summary.model_version`) else PKG | ART else RUN else PKG |
| model_method | MAP (== model_version) | MAP (== model_version) |
| model_metrics | explicit absence (`null`/`null`) | explicit absence (`null`/`null`) |
| threshold_value | RUN (`result_summary.threshold_applied`) | RUN (`external_report.decision_threshold`) |
| risk_probability | RUN (`result_summary.probability`) | RUN (`external_report.risk_probability`) |
| target_class_risk_level | RUN (`result_summary.prediction` 0/1) | RUN (`external_report.target_class_risk_level` 0/1) |
| specific_output | contract: `{}` | RUN (`target_side`) + `""` mammography field |

No fabricated values anywhere: authors/comments/paths/secrets are dropped by
`_clean_metadata_field`; absent age → `null`; absent scan/operator/hardware/eoscan →
`""`; absent metrics → `null`; absent timestamps → `""`; malformed/failed results →
mapper returns `None` and the report is left untouched (tested). The empty strings
are exactly the contract's documented absence convention. `patient_id` is the
sanitized H5 `patient_display_name` via the unchanged locked PR0143 job context —
never invented.

## Bremen mapping assessment
**PASS.** All newly required metadata fields are mapped with the documented
explicit-absence semantics (`prediction_comment`/`analysis_author` from sanitized
request; `patient_id` from container metadata; `patient_age`→null;
`scan_date_time`/`operator_id`/`hardware_version`/`eoscan_version`→`""`;
`model_method`==version). `specific_output == {}` per the accepted contract (the
contract text itself states Bremen currently has no model-specific extension
fields — unchanged before implementation). Legacy fields preserved and tested:
`report.payload.score_and_threshold.p_mri_needed` (0.7388733541967353 exact),
`triage_recommendation`, `technical_demo_only`-family fields; Aramina-side
`report.payload.risk_score` and `report.payload.technical_demo_only` asserted
present and unchanged. Bremen's probability name in the payload is
`score_and_threshold.p_mri_needed` (v0.2 nested shape) — untouched; the standard
result carries the same authoritative number as `risk_probability` with no
modification (`test_bremen_report_golden_probability_exact` asserts
`== 0.7388733541967353` exactly).

## Aramina mapping assessment
**PASS.** Exactly the same envelope; `specific_output =
{"target_side": <allowlisted left/right>, "mammography_suspicious_field": ""}`
(the contract's agreed Aramina extension; mammography field is `""` because the
current result provides no value — never fabricated; target_side falls back only to
the sanitized allowlisted request side, else `""`). `risk_probability` is the
native `external_report.risk_probability` verbatim (repo's Aramina native field;
the legacy `risk_score` alias is untouched). `threshold_value` is the native
`decision_threshold`. `target_class_risk_level` is the native 0/1 model decision
translated to high/low. No preprocessing/LR1/logit/symmetry/final-model/threshold
change (packages untouched in this diff; all Aramina suites pass; `ARAMINA_*`
taxonomy byte-identical — moved vocabulary re-exported by the shim, 15 PR0143
guard tests green). No unsafe diagnostic leakage (leak tests plant sensitive text
and assert non-leakage).

## Model metrics provenance
`risk_probability`-adjacent release metrics: **no authoritative
sensitivity/specificity exists anywhere** in package manifests, artifact metadata,
or runtime results for either current release. I independently confirmed the
contract/PR0155 example values (0.96053 / 0.49495 / 0.41303) appear nowhere in the
repository (grep) — they are illustrative. ADR-0008's `target_sensitivity` is a
threshold-calibration target, explicitly not an achieved metric. Occurrence
classification: `sensitivity/specificity` appear only in offline training code
(`training/pipeline.py`, `modeling.py`), a trace-allowlist string, and
`report_aramina.py` docstrings that explicitly decline to compute them — no
API-route or per-patient calculation anywhere. The mapper emits explicit `null`
absence for both models (schema supports future provenance-verified population;
`_empty_metrics` documents the rule). **No made-up metric. No blocker.**

## Model method assessment
`model_method` exists for both models via ONE central rule
(`mapper._model_method(version) == version`), documented in the mapper and tested
for both models + the single-implementation rule. No per-provider duplicates
(grep: `model_method` occurs only in the mapper/schema).

## Probability assessment
`risk_probability` is a pure translation: `float(...)` passthrough of the
authoritative runtime value — no recalculation, no rounding, no clamping
(`_clean_number` performs type checking only). Tested: Bremen golden
0.7388733541967353 end-to-end exact; Aramina 0.265 verbatim; the legacy
`payload.risk_score` alias remains the identical number.

## Threshold assessment
`threshold_value` comes only from model-owned runtime outputs
(`threshold_applied` / `decision_threshold`). New-threshold-literal search across
`src/bremen/api/`: **none** (the only threshold-adjacent literals in `api/` are
pass-through plumbing of runtime-produced values; package manifests own provenance
constants). `test_mapper_does_not_hardcode_aramina_threshold` proves a different
authoritative threshold flows through unchanged. Existing model thresholds
unchanged (0.3585907282566089 Bremen — verified exact; Aramina artifact-owned).

## Decision assessment
`target_class_risk_level` prefers the model-owned decision (`prediction` 0/1 /
`target_class_risk_level` int) and only falls back to `probability >= threshold`
using model-owned values — the exact operator the package predictor/pipeline
applies. Independently proven at the boundaries by test:
`_risk_level(None, probability=0.4, threshold=0.4) == "high"` (equal → high),
`0.399/0.4 → "low"` (below), above → high; and the model-decision-driven path is
exercised for both models (0→low, 1→high, including a threshold=0.9 case where the
model decision still wins). No independent decision logic exists.

## Timestamp assessment
`normalize_timestamp` (single shared implementation): parses ISO/RFC3339
(Python 3.13 `fromisoformat` accepts `Z`), strips fractional seconds
(`microsecond=0`), re-emits `isoformat()` which preserves the source offset —
never converts to host-local time and never invents a zone for naive input.
Independently tested: microseconds removed with offset preserved
(`…19:48:36.123456+02:00` → `2026-09-04T19:48:36+02:00` — the contract's exact
example shape), `Z` → `+00:00`, already-normalized idempotence, naive preserved
naive, empty/`None`/unparseable → `""`. `created_at` derives from
`generated_at = datetime.now(timezone.utc).isoformat()` — always tz-aware, so the
contract's "timezone included where authoritative timezone exists" rule holds.
`scan_date_time` absent → `""` (never fabricated).

## Specific output assessment
Always a mapping: Bremen `{}` (per the accepted contract text, unchanged);
Aramina `{"target_side": …, "mammography_suspicious_field": ""}`. Model-specific
fields stay out of the top level (PR0143 unknown-key guard + schema test).

## Legacy report compatibility
`ReportEnvelope.standard_result` is optional and serialized **only when set**;
default/unavailable/failed envelopes serialize with the exact pre-PR0157 key set
(tested: `"standard_result" not in report` for a failed job). `_report_job_context`
(the locked PR0143 provider contract) is byte-unchanged — only the separate
`_mapper_job_context` adds sanitized author/comment for the mapper. Existing
response keys preserved; the sole externally visible addition is the additive
`report.standard_result` block on valid completed reports. Report-UI builders
tolerate the additive key (all report parity/UI suites pass unmodified).
`create_analysis_job` gained default-valued kwargs only; `input_summary` gained two
additive keys (job identity keyed by source_key/workflow_id/model_id/target_side —
unchanged).

## Route inventory baseline/result
Independently captured via `create_fastapi_app()` route tables (method+path sets)
at the stashed baseline and at the worktree: **29 routes at baseline, 29 at
worktree, set-identical** (added: none; removed: none; renamed: none; method
changes: none). The only endpoint-adjacent file touched (`fastapi_app.py`) changed
solely inside the job-create handler body (raw-body kwargs forwarding). New tests
lock: set equality vs the frozen 29, count == 29, and that no
standard-result/mapper endpoint exists.

## Auth compatibility
No auth module or dependency changed. Report routes keep their existing upstream
auth gating (PR0156 freeze suite green; health/model-version open-route behavior
tested; report-parity suites pass). No auth requirement removed, weakened, or
added.

## Request compatibility
`POST /demo/api/jobs` request model untouched; author/comment are read from the
raw body dict as optional extras, so validation semantics are unchanged
(`MISSING_SOURCE` 400 behavior asserted identical). No renamed/new required fields,
type changes, enum changes, or model_id/job/source identifier semantic changes
(`model_id`/`workflow_id` values and routing untouched; mapper identity comes from
PKG/ART, deliberately not from registry routing ids — tested).

## Response compatibility
Additive-only as described; all existing consumers keep working without code
changes (report parity/UI/data-route/HTML-route/decision suites: 110 passed; full
suite green). No legacy field removed or renamed.

## Science-boundary analysis
Mapper/schema contain **no scientific logic**: no numpy/scipy/pandas imports, no
feature/normalization/smoothing/q-grid/scaler/estimator/LR1/symmetry formulas, no
artifact interpretation, no threshold application. Their imports are: the schema,
the two package manifests, and stdlib (datetime/typing/dataclasses). The mapper
consumes `WorkflowRun.result_summary` (already-produced payload) and never calls
into model packages' scientific modules.

## Duplicate-mapping search
`risk_probability` / `target_class_risk_level` / `threshold_value` /
`model_metrics` / `sensitivity` / `specificity` / `model_method` occurrences in
production src classified: **mapper/schema = the one authoritative mapping
boundary**; Aramina package `inference.py` = model-native production fields (the
consumed source, correct); Bremen manifest `THRESHOLD_VALUE`/`threshold_value` =
PR0154 provenance metadata (not applied behavior); `report_ui.py` = pre-existing
legacy payload rendering (untouched); offline training/`modeling.py` = historical
training metrics (out of inference path); `report_aramina.py` docstrings only. No
scattered route/provider-level mapping implementations exist
(`build_standard_result`/`standard_result` referenced only in `job_api_handler.py`
— the single integration point).

## Model Package Standard conformance
Both packages remain conformant: standard conformance + deduplication + reverse-
import guards re-run green inside the 530-test combined run; packages gained no
FastAPI/job/report/auth/link/schema dependencies (packages are untouched by this
diff; mapper→manifest is the allowed platform→package direction).

## Bremen parity evidence
Bremen direct package (50) + PR0151/0152/0154 parity + workflow + contract +
conformance + Aramina package/provider/scaffold/runtime + dedup → **530 passed**
(golden probability 0.7388733541967353 atol 1e-10 rtol 0; 3 LEFT + 3 RIGHT; all six
measurements; 15 features; q-grid/smoothing/normalization; ddof=1 replicate
variance; per-measurement peak semantics; portable estimator; threshold; decision;
raw-H5 parity; invalid shapes). No scientific delta.

## Aramina parity evidence
Aramina runtime (238) / provider contract / scaffold / direct package suites all
pass inside the same runs; science untouched; taxonomy, target_side, symmetry,
preprocessing release gating, LR1/logit/final-model behavior unchanged; PR0141–
PR0143 guard tests green (15 pr0143 tests re-run explicitly).

## Security findings
No filesystem paths, S3 credentials/keys, artifact paths, tokens, environment
secrets, tracebacks, joblib internals, estimator coefficients, or scaler internals
in the standard result (fields are fixed; mapper consumes only the enumerated
authoritative values). `_clean_metadata_field` rejects path/URI/secret-like/
oversized/control-character request metadata before it can reach the public
result (tested: `/etc/passwd`, `s3://bucket/key`, `aws-secret`, 300-char, non-str
→ `""`). Fixtures contain synthetic placeholders only (`PAT-SYNTH-1`,
"Nova_Synth", "Synthetic Author"); no real patient/private data added; no binaries
added.

## Compileall / targeted tests / full pytest / counts / Ruff / diff-check
- `python -m compileall -q src tests` → **exit 0**.
- New suite `tests/test_bremen_standard_model_result_v1.py` → **36 passed**
  (schema/frozen/order; both-model probability/threshold/decision; no-recompute
  boundary cases; model_method rule; metrics absence; specific_output; absence
  semantics; timestamps; legacy preservation incl. failed-envelope key set;
  end-to-end Bremen golden + Aramina envelope; sanitizer; route freeze; auth;
  request schema; dispatch; frozen fixtures; conformance intact; mapper imports).
- Parity/conformance/compat runs: **530 passed** (packages+parity+contract) and
  **250 passed, 1 skipped** (requirements/inference/jobs/catalog/registry/discovery)
  and **110 passed** (report/decision/freeze suites); PR0143 subset 15 passed.
- Full `pytest -q` → **4285 passed, 11 skipped, 0 xfailed** (50.5s, exit 0).
- Test-count vs main: 4259 → 4296 collected = **+37, 0 removed** (36 new tests in
  the new file + 1 auto-parametrized no-server-spawning case for the new file;
  verified by stashed collection diff; modified files collect identically; no
  skipped/xfail changes — 0 new xfail/skip markers).
- Ruff on all changed/new files: 6 findings, all in `job_api_handler.py`,
  **verified pre-existing at HEAD** (same rules, lines only shifted); every other
  changed/new file clean; **zero new findings**.
- `git diff --check` → **exit 0**.

## Warnings (non-gating)
1. `model_metrics.sensitivity/specificity` are `null` for both models — the honest
   outcome: no provenance-verified release metrics exist yet (the contract-doc
   example numbers are illustrative and appear nowhere in the repo). Intentional,
   documented, tested; population is a roadmap-0159/0160 release-metadata task.
2. Bremen `model_version` prefers the runtime payload value; a provider constructed
   without an explicit version would surface the platform sentinel `"unknown"`
   rather than the manifest fallback. In every production job path the registry
   entry supplies the real release version (integration test shows
   `0.2.0-paper-reference`); cosmetic robustness note only.
3. The Aramina provenance spelling variant (`aramina-target-brest-risk`,
   PR0156 finding) is untouched per guidance: runtime-unused, not referenced by the
   mapper (model_name uses MODEL_NAME), public IDs/routing/job/report semantics
   unchanged; correction remains roadmap-0159 work.
4. Sequencing note: the roadmap document labels the mapper implementation "0158",
   while this PR implements it under 0157 per the reviewed task/ADR follow-up.
   Documentation-only numbering inconsistency; no architectural impact (ADR-0018's
   "Follow-up" requirement is satisfied by this PR).
5. The sanitizer is deliberately conservative (any string containing
   aws/token/secret/password/s3/bearer collapses to `""`), so an author name
   containing such a substring is dropped rather than echoed — safe-side behavior,
   consistent with the no-fabrication rule.

## Blockers
None.

## Remaining roadmap work
- 0159: release-boundary hardening (container/bytes abstraction, `_validate_aramina_
  source` lift, provenance typo correction, standalone package importability).
- 0160: release packaging (MLflow pyfunc) over conforming packages; release metrics
  provenance threading into `model_metrics`.
- 0161: additive technical model-native inference API (may return
  `StandardModelResult` directly); 0162: registry/lifecycle evaluation.
- Follow-up cleanup: pre-existing Ruff findings in `job_api_handler.py` (untouched
  per scope rules).

## FINAL VERDICT

VERDICT: READY FOR COMMIT
