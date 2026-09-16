# PR0157 — Standard Model Result Contract v1 — Implementation Plan

## Branch / baseline
- Branch: `0157-standard-model-result-contract-v1`
- HEAD: `4f643337110e70365e64a162ec4f183077de73ae` ("docs: define standard model
  result contract v1"). Clean worktree.
- Captured baseline (verify after impl, must match):
  - HTTP routes: **29** (`create_fastapi_app()`, method+path set identical to
    PR0156 `FROZEN_ROUTES`). Confirmed 29 independently; do NOT trust blindly.
  - pytest collection: **4259 tests** (`pytest --collect-only`).
- Do not commit/push/PR.

## Source-of-truth read
- docs/standard_model_result_contract_v1.md (canonical fields + mapping rules).
- docs/adr/0018-standard-model-result-contract-v1.md (Accepted; threshold/prob/
  metrics/compatibility rules; follow-up = implement mapper).
- docs/model_architecture_roadmap_0157_0162.md (0158 mapper scope; 0159+ later).
- docs/model_runtime_contract_v1.md, docs/model_package_standard_v1.md,
  docs/adr/0016, docs/adr/0017 (contract/standard layering).
- PR0156 report/review (Aramina manifest MODEL_ID provenance note; bridges).
- PR0154 report (Bremen identity/threshold provenance).
- Implementations read: api/report_provider.py, api/report_aramina.py,
  api/report_bremen.py, api/job_api_handler.py (_AraminaLocalReportProvider,
  get_job_report, create/handle_jobs_create), api/fastapi_app.py (report
  routes + auth), api/fastapi_contracts.py (Pydantic convention),
  api/workflow_aramina.py, model_packages/aramina_v0213/{manifest,inference,
  runtime}.py, model_packages/bremen_v01/{manifest,runtime,predictor}.py,
  api/decision_contract.py, api/preflight.py, report_ui.build_external_report_json.
- PR0156 contract-test seams confirmed: `AraminaRuntime(entry=SimpleNamespace
  (model_id=…, model_version=…, feature_schema_version=…))` — runtime must stay
  lazy (attribute access only in methods, not __init__).

## Architecture
```
Model package runtime result (native)  +  platform/source metadata
              │
              ▼
  Standard Model Result Mapper (platform integration boundary)
              │
              ▼
  Standard Model Result v1 (frozen dataclass + to_envelope_dict)
              │
              ▼
  existing report envelope (get_job_report / handle_job_report) → consumers
```
- Mapper is platform-side only. Model packages keep owning science + release
  metadata; they are NOT given report_id/routes/auth/jobs knowledge.
- Mapper **consumes** the authoritative runtime result; it does not recompute.

## Files
- New: `src/bremen/api/standard_model_result.py` (frozen dataclass + canonical
  field constants + risk-level vocabulary + `to_envelope_dict()`).
- New: `src/bremen/api/model_result_mapper.py` (ONE mapper boundary: shared
  helpers + `map_bremen_result` / `map_aramina_result`).
- New tests (below). NO production change to model packages, providers, routes,
  jobs, reports, auth.

## One integration point
`job_api_handler.get_job_report()` and `handle_job_report()` (legacy http.server
equivalent) both call `provider.generate_report(...)`. The **narrowest** wiring
that covers both public report paths for both models is: after the envelope is
produced, attach a Standard Model Result **only when the report is valid**
(`workflow_status == available` and the model-native probability/threshold are
present and finite). `ReportEnvelope` gains an OPTIONAL
`standard_result: dict | None` field; `to_dict()` includes `"standard_result"`
only when non-None → default/failed/unavailable envelopes serialize EXACTLY as
before (preserves `test_pr0143_*`). No new/changed/removed route; auth and
request handling untouched (both report handlers already auth-gate upstream).
Report-UI `build_external_report_json(report.to_dict())` is tolerant: unknown
top-level keys are ignored, so `build_external_report_json`/`build_internal_report_json`
contracts and parity tests remain valid; `report.payload.risk_score` and
`report.payload.technical_demo_only` are NOT moved/renamed/removed.

## Field source map

### Classification legend
- GEN = platform-generated metadata
- SRC = source/container metadata
- RUN = model runtime result (model-native)
- PKG = model package manifest (authoritative release metadata)
- ART = model artifact/release metadata
- RPT = existing report metadata
- MAP = explicit compatibility mapping

### Bremen
| canonical field | source | detail |
| --- | --- | --- |
| report_id | GEN | `envelope.report_id` |
| created_at | GEN | `envelope.generated_at` normalized (UTC isoformat, tz, no frac secs) |
| analysis_author | SRC/GEN | `job_context` author (default "" — no fabrication) |
| prediction_comment | SRC/GEN | `job_context` (default "" — schema empty string) |
| patient_id | SRC | `job_context.patient_id` (patient_display_name from H5) |
| patient_age | SRC | **absent** → `null` (H5 preflight exposes no age for Bremen; do not fabricate) |
| scan_date_time | SRC | **absent** → `""` (container metadata not in report context; do not fabricate) |
| operator_id | SRC | **absent** → `""` |
| hardware_version | SRC | **absent** → `""` |
| eoscan_version | SRC | **absent** → `""` |
| model_name | PKG | `bremen_v01.manifest.MODEL_NAME` (="bremen_paper_reference_symmetry_logreg") |
| model_version | RUN/PKG | `result.model_version` (registry) else PKG `MODEL_VERSION` |
| model_method | MAP | equals `model_version` (single documented rule, in mapper) |
| model_metrics.sensitivity | — | **absent** → `null` (release metrics not in PKG; ADR-0008 forbids presenting training target as achieved) |
| model_metrics.specificity | — | **absent** → `null` |
| threshold_value | RUN | `result["threshold_applied"]` (model-owned; predictor already applied it) |
| risk_probability | RUN | `result["probability"]` (authoritative; not recalculated) |
| target_class_risk_level | RUN | `result["prediction"]` (0/1 model-owned decision) → `high`/`low` |
| specific_output | — | `{}` (contract: Bremen has no model-specific fields) |

### Aramina
| canonical field | source | detail |
| --- | --- | --- |
| report_id | GEN | `envelope.report_id` |
| created_at | GEN | `envelope.generated_at` normalized |
| analysis_author | SRC/GEN | `job_context` ("" if none) |
| prediction_comment | SRC/GEN | `job_context` ("" if none) |
| patient_id | SRC | `job_context.patient_id` (sanitized `patient_display_name`) |
| patient_age | SRC | **absent from report metadata** → `null` (age lives in the preprocessing frame inside the package, not exposed publicly; do NOT re-derive). |
| scan_date_time | SRC | **absent** → `""` (do not fabricate; preserve-if-present) |
| operator_id | SRC | **absent** → `""` |
| hardware_version | SRC | **absent** → `""` |
| eoscan_version | SRC | **absent** → `""` |
| model_name | PKG/ART | native `external_report.model_name` (artifact `model_identity.name`) else PKG `MODEL_NAME` |
| model_version | RUN/ART | `external_report.model_version` else `envelope.model_version` else PKG |
| model_method | MAP | equals `model_version` |
| model_metrics.sensitivity | — | **absent** → `null` (do not fabricate; see Metrics) |
| model_metrics.specificity | — | **absent** → `null` |
| threshold_value | RUN | `external_report["decision_threshold"]` (model-owned threshold) |
| risk_probability | RUN | `external_report["risk_probability"]` (== legacy `risk_score` alias) |
| target_class_risk_level | RUN | `external_report["target_class_risk_level"]` (int 0/1) → `high`/`low` |
| specific_output | RUN | `{target_side: external_report["target_side"], mammography_suspicious_field: ""}` (target_side unchanged semantics; field is absent → `""`, never fabricated) |

Notes:
- probability name: repo Aramina native field is `risk_probability` (NOT
  literally `p_mri_needed`; `p_mri_needed` is the *Bremen* report field). The
  contract's "p_mri_needed → risk_probability" describes the concept; both
  models' authoritative native probability maps to `risk_probability`.
- Do NOT read `job.reports` / `ReportMetadata` inside the mapper — those hold
  runtime-registry ids (`bremen-current`), which differ from the scientific
  model name/version (PKG/ART). model_name/version come from PKG/ART only.

## model_method rule
Implemented ONCE in `model_result_mapper._model_method(model_version)` =
`model_version`. Documented + tested. No per-provider constant duplication.

## model_metrics rule
`sensitivity`/`specificity` are release metadata; NO provenance-verified values
exist in PKG/ART/RUN for either release (example numbers in the doc are
illustrative; ADR-0008 `target_sensitivity` is a training target, not achieved).
→ emit `null` for both (contract "explicit absence", never fabricated). The
schema/models carry optional metric fields so a FUTURE package-metadata
release (roadmap 0159/0160) can populate them from an authoritative source; the
mapper reads from that source if/when present and never hardcodes.

## timestamp rule
Shared `normalize_timestamp(value)` in the mapper: parse ISO/RFC3339 (accept
Z / offset); drop microseconds/milliseconds (`.replace(microsecond=0)`); emit
`datetime.isoformat()` (keeps offset, e.g. `+00:00`, `+02:00`). Preserve the
source instant; do NOT coerce a missing tz to local time. If the value carries
no trustworthy tz, keep the naive representation (do not invent a zone). Empty/
absent `scan_date_time` → `""`; absent `patient_age` → `None`. `created_at`
comes from tz-aware `generated_at` so it is always tz-aware.

## Schema
`standard_model_result.StandardModelResult` = frozen dataclass with the exact
canonical field names/shape + `to_envelope_dict()` emitting the contract field
ORDER. Frozen dataclass chosen (not Pydantic) because it serializes straight
into the JSON report like the rest of `api/*` dataclasses; Pydantic is reserved
for request models in `fastapi_contracts.py`. No second runtime/model interface.
No model package depends on the schema (dependency direction preserved).

## risk-level rule (canonical high/low)
`high` iff model-owned positive decision (probability >= threshold, already
applied by the package) else `low`. Derived from the authoritative 0/1
`prediction`/`target_class_risk_level`; mapper does NOT recompute the numeric
comparison independently (consumes model decision). Both values tested.

## scientific parity strategy
Bremen: probability/threshold/decision consumed from `WorkflowResult`
(result_summary) unchanged; golden 0.7388733541967353 at atol 1e-10 rtol 0 via
unchanged runtime; mapper only relabels. Aramina: consumes native
`external_report` numbers verbatim. No science/threshold/failure-taxonomy/
target_side/symmetry change. Mapper never recalculates probability/decision.

## public compatibility strategy
- Routes frozen; assert route set == PR0156 `FROZEN_ROUTES` and auth still
  applied (report-detail route returns 401/403 without ticket when enforced).
- Response: all existing keys preserved; single NEW key `report.standard_result`
  (inside `report`), present only on valid completed reports; default/failed
  envelope serialization asserted unchanged (extend `test_pr0143_*`).
- Request: no change to `POST /demo/api/jobs` schema/auth.
- model_id/workflow_id values unchanged (mapper uses PKG/ART for name/version;
  `envelope.model_id` untouched).
- `report.payload.risk_score`, `report.payload.technical_demo_only` unchanged.

## Tests
New `tests/test_bremen_standard_model_result_v1.py`:
- schema shape + exact field order/set.
- risk_probability/threshold_value mapping for BOTH models.
- high decision + low decision (both models) from model-owned inputs.
- model_method == model_version rule (single impl).
- model_metrics null-absence (no fabrication).
- specific_output Bremen `{}`; Aramina `{target_side, mammography_suspicious_field:""}`.
- prediction_comment / patient / scan / operator / hardware / eoscan source
  routing (present, absent→correct empty/null).
- created_at normalization (tz-aware, frac-strip, already-normalized, no local
  tz invention); scan_date_time normalization + absent "".
- legacy preservation: `risk_score`/`technical_demo_only` present; default/failed
  envelope unchanged (`standard_result` absent).
New `tests/test_bremen_api_freeze_pr0157.py` (or extend PR0156 guard):
- route path+method inventory identical to frozen set (count + exact set).
- existing report response keys preserved; additive `standard_result` only.
- existing request compat + auth behavior on report route unchanged.
New frozen mapping fixtures:
- `tests/fixtures/standard_model_result/bremen_v01_golden.json`
- `tests/fixtures/standard_model_result/aramina_v0213_golden.json`
  (synthetic metadata values + authoritative numbers from PR0151 golden run /
  PR0156 synthetic Aramina artifact; assert mapper output == fixture).
Integration:
- end-to-end `create_analysis_job`→`get_job_report` standard_result for Bremen
  and Aramina (reuse existing aramina source fixture pattern);
  route-level via TestClient for report-detail auth + body shape.
Direct package regression: PR0151/0152/0154 + PR0156 package suites + conformance.

## Dependency direction
mapper/schema in `api/` (platform integration) import model-package PUBLIC
entry points/manifest only (allowed: platform→package). Model packages do not
import the schema/mapper. report_provider/report envelope: no science. No cycle
(schema has no imports from report_provider; providers import schema+mapper).

## Remaining platform bridges (context, unchanged)
Canonical `validate_canonical_measurement`/`NormalizationError` remain the
single canonical-input bridge (decision_contract + canonical_input + the
Aramina `_validate_aramina_source`/`load_staged_artifact` bridges from PR0156)
— untouched by PR0157.

## Aramina manifest typo (MODEL_ID="aramina-target-brest-risk")
Provenance-only, runtime-unused, and NOT exposed through the standard result
(mapper uses MODEL_NAME for `model_name`, never MODEL_ID). Public model IDs
(byte-for-byte) are unchanged regardless. Per task guidance: do NOT touch it;
leave documented for the release-boundary follow-up (roadmap 0159). No risk to
0157 mapping.

## Non-goals
No new/renamed/removed endpoint; no auth/request/job/report/route redesign; no
scientific/retrain/threshold/new-model-version change; no ModelPackage rewrite;
no MLflow/registry/BentoML/KServe; no frontend/storage/PDF work. No fabricated
metrics/author/timestamps/age. No new `target_side`/`model_name` top-level keys
on envelopes (guarded by test_pr0143_unknown_target_side_omitted /
bremen_report_contract_unchanged).

## Validation commands
- `python -m compileall -q src tests`
- new mapper/schema tests; API freeze tests; Bremen mapping/integration; Aramina
  mapping/integration; Model Package Standard conformance; PR0151/0152/0154/0156
  parity; Aramina runtime/provider/package; model requirements; job; report; API
  contract; **full `pytest -q`** (expect ≥ 4259, 0 removed; explain delta = only
  new PR0157 tests + no regressions)
- `ruff check` on every changed/new file (must be clean; no unrelated fixes)
- `git diff --check`
- duplication searches (risk_probability/target_class_risk_level/threshold/
  sensitivity/specificity literals; scattered route-level mapping)
- security scan (no paths/S3/tokens/coefficients/raw exceptions added).
