# PR0143 precommit review — Aramina report contract: patient_id, target_side, links

- Reviewer: precommit-review agent (Bremen)
- Date (UTC): 2026-09-10T18:47:01Z .. 2026-09-10T18:50:25Z
- Head: `9c2474b6d7eeaabc4636cccc6c5691f4e5a4c6fe`
- Branch: `0143-aramina-report-contract-target-side-links` (matches required branch)
- Note: no PLAN.txt exists for this PR (the PR memory directory did not exist before this
  review). The task's EXPECTED PR SCOPE was used as the source of truth.

## Verdict

**READY FOR COMMIT**

## Exact commands run (all on this branch, via `venv/bin/python`; bare `python` is absent
from PATH in this environment)

| Command | Result |
| --- | --- |
| `python -m compileall -q src tests` | exit 0 |
| `pytest -q tests/test_aramina_workflow_runtime.py` | exit 0 — 238 passed |
| `pytest -q tests/test_catalog_api_multi_model.py` | exit 0 — 25 passed |
| `pytest -q tests/test_bremen_model_requirements_api.py` | exit 0 — 35 passed |
| `pytest -q tests/test_bremen_model_catalog.py tests/test_model_registry.py tests/test_catalog_api_multi_model.py` | exit 0 — 73 passed |
| `pytest -q` (full) | exit 0 — **4026 passed, 11 skipped, 0 failed** |
| `git diff --check` | exit 0 (clean) |

## Changed files summary (5 files, 273 insertions / 2 deletions; all fully read)

- `src/bremen/api/report_provider.py` (+20/−1): `ReportEnvelope` gains three OPTIONAL
  fields — `patient_id: str | None = None`, `target_side: str | None = None`,
  `links: dict[str, str] = {}` — and `to_dict()` appends them ONLY when set, so an
  envelope that does not set them serializes with its exact previous key set (asserted by
  `test_pr0143_report_envelope_defaults_unchanged`). The abstract `ReportProvider.
  generate_report` signature gains `job_context: dict[str, Any] | None = None` (documented
  as safe job-level metadata; providers that do not need it ignore it). Additive only.
- `src/bremen/api/report_bremen.py` (+5): `BremenReportProvider.generate_report` accepts
  `job_context` for interface parity and explicitly ignores it. No other change — Bremen
  report contract unchanged (verified by test).
- `src/bremen/api/report_aramina.py` (+6/−1): `AraminaReportProvider` (the unavailable
  placeholder boundary) accepts `job_context` for parity and ignores it; docstring
  updated. No behavior change.
- `src/bremen/api/job_api_handler.py` (+50): (1) new `_safe_report_identifier()` — echoes
  only `[A-Za-z0-9_.-]{1,80}`, rejects `/`, `\`, `://`, empty/oversized values;
  (2) `_AraminaLocalReportProvider.generate_report` accepts `job_context`, derives
  `target_side` strictly from the scored workflow result (`external_report.target_side`
  must be exactly `left`/`right`), derives `patient_id` via the sanitizer from job
  context, and sets `links = {"job": f"/demo/api/jobs/{job_id}",
  "json": f"/demo/api/jobs/{job_id}/reports/aramina"}` — no pdf link; (3) new
  `_report_job_context()` exposing ONLY `patient_id` (from `input_summary.
  patient_display_name`) and `target_side` — never source_key, paths, or artifact
  internals; (4) the two job-report call sites (`get_job_report`, `_generate_job_reports`)
  now pass `job_context`. The other four `generate_report` call sites (Bremen
  external/internal report routes in job_api_handler + fastapi_app) pass no job_context
  and rely on the default — Bremen reports unaffected.
- `tests/test_aramina_workflow_runtime.py` (+193): 15 new PR0143 tests (detail below).

## Contract compatibility assessment

Production-smoke field list vs. implementation (verified by code read AND typed test):

| Smoke field | Status |
| --- | --- |
| `report.job_id`, `report.workflow_id`, `report.workflow_status`, `report.report_schema_version`, `report.report_id`, `report.generated_at`, `report.model_id`, `report.model_version`, `report.scientifically_certified`, `report.disclaimer` | preserved, same names/types (`test_pr0143_existing_contract_fields_present_and_typed`) |
| `report.payload.risk_score` | preserved inside payload (`test_pr0143_payload_fields_preserved`; payload key set asserted to be exactly `{risk_score, technical_demo_only}`) |
| `report.payload.technical_demo_only` | preserved inside payload (same test) |
| `report.patient_id` | ADDED — sanitized, omitted when unsafe (`test_pr0143_report_includes_patient_id`, `test_pr0143_unsafe_patient_id_omitted`) |
| `report.target_side` | ADDED — strict `left`/`right` from the scored result, omitted otherwise (`test_pr0143_report_includes_target_side`, `test_pr0143_unknown_target_side_omitted`) |
| `report.links.job` = `/demo/api/jobs/{job_id}` | ADDED (`test_pr0143_report_includes_links_job_and_json`) |
| `report.links.json` = `/demo/api/jobs/{job_id}/reports/aramina` | ADDED (same test) |
| `report.links.pdf` | NOT added — and guarded: `test_pr0143_no_pdf_link_without_endpoint` asserts `set(links) == {"job", "json"}`; `test_pr0143_no_pdf_endpoint_exists` asserts the string `application/pdf` appears nowhere under `src/bremen` |

- No existing field was renamed, moved, or removed (greps + typed-contract test +
  full-payload-key-set test).
- Failed/unavailable Aramina reports keep `workflow_status: unavailable` + empty payload;
  only the safe links are added (`test_pr0143_failed_report_keeps_unavailable_behavior`).
- Bremen report contract unchanged: Bremen provider ignores `job_context`; Bremen
  envelopes never set the new fields; `test_pr0143_bremen_report_contract_unchanged`
  asserts `patient_id`/`target_side`/`links` are absent from Bremen reports; Bremen
  external/internal report builders receive unchanged shapes.
- Additive-only confirmed: the 2 deleted lines are `return {` → `result = {` in
  `to_dict` and one docstring line; every other change is a pure insertion.
- Not touched (verified by `git diff --name-only`): auth, async/job lifecycle,
  source_id/source_registry, duplicate/idempotency logic, scoring, preprocessing, model
  artifacts, thresholds, frontend, `report_ui.py`, `fastapi_app.py`.

## Security / safety review (report JSON)

- `report.patient_id`: double-sanitized — upstream `extract_patient_display_name` already
  rejects >80 chars, `s3://`, `/tmp/`, slashes, and marker words; `_safe_report_identifier`
  re-applies a strict opaque-identifier regex and the field is OMITTED ENTIRELY when
  unsafe (path-like, scheme-bearing, >80 chars, spaces — all tested). For Aramina the
  display name equals the requested `patient_id` (existing mismatch gate), consistent with
  data already exposed by the containers API and `ARAMINA_PATIENT_MISMATCH` responses —
  no new leak class.
- `report.target_side`: allowlisted `{left, right}` only; anything else omitted (tested).
- `report.links`: relative `/demo/api/jobs/...` paths built from the server-generated
  `job_id` (uuid4); tested to contain no `://`, no `\`, and to start with `/demo/api/jobs/`.
- `job_context` carries only `patient_id` + `target_side` (exact key set tested with a
  private `source_key` present in the job — asserted absent).
- End-to-end public-JSON leak test through the real job path
  (`test_pr0143_public_report_leaks_nothing`): no source path, artifact path, checksum,
  `_package`, `source_key`, `Traceback`, `token`, `s3://`, `/tmp/` in the report JSON.
- Mandated leak grep over changed files was effectively covered by these targeted tests;
  the only sensitive-adjacent strings in the diff are the sanitizer/omit logic and test
  fixtures asserting absence — no leak path introduced.

## Risks / non-gating notes

1. `links.json` hardcodes the `aramina` workflow segment. `_AraminaLocalReportProvider`
   is registered only for `workflow_id = "aramina"`, so this is correct today; if the
   provider were ever reused for another workflow id the link would need to follow.
   Informational.
2. The unavailable/failed Aramina report now also carries `links` (tested intentional).
   Clients treating extra keys permissively are unaffected; clients doing exact-shape
   comparison on failed reports would see the additive keys. No such strict consumer
   exists in-repo (report_ui handles Bremen only).
3. `report.patient_id` reflects the resolved patient display name from H5 metadata rather
   than the raw request field; for Aramina these are forced equal by the existing
   patient-mismatch gate, so the semantics match the smoke expectation (`patient_id`).
4. No PLAN.txt / plan-review artifact exists for this PR; scope was reviewed against the
   task's EXPECTED PR SCOPE. Nothing was committed; commit remains a human action.
