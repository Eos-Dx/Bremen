# PR 0053 — Plan: Decision Support Output Wrapper

## 1. Title / Branch / Objective

- **Title**: Decision Support Output Wrapper
- **Branch**: `0053-decision-support-output-wrapper`
- **Objective**: Add a safe, structured decision-support report around existing inference results. The report wraps the current prediction dict with schema version, intended-use statement, safety limitations, input summary, model metadata, prediction summary, and decision support classification. All existing runtime behavior is preserved — no math, threshold, staging, layout, preprocessing, or inference changes.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
d7d8719faa2c70bbd0386b3774f696d9dafc8604

$ git branch --show-current
0053-decision-support-output-wrapper

$ git status --short
(clean — no uncommitted changes)
```

Branch matches. Working tree clean.

---

## 3. Problem Summary

### Current state

The `run_inference()` function in `src/bremen/api/inference_handler.py` returns a flat dict with 12 fields:

```python
{
    "prediction_id": "...",
    "model_version": "...",
    "model_checksum": "...",
    "feature_schema_version": "v0.1",
    "threshold_version": "...",
    "threshold_value": 0.5,
    "qc_status": "passed",
    "qc_flags": [],
    "patient_id": "PID",
    "p_mri_needed": 0.75,
    "triage_recommendation": "MRI_RECOMMENDED",
    "created_at_utc": "2026-...",
}
```

However, `handle_submit_prediction()` extracts only the 8 `COMPLETED_RESULT_FIELDS` into `CompletedResult`, and `handle_get_prediction()` returns only those 8 fields in the poll response. The fields `patient_id`, `p_mri_needed`, `triage_recommendation`, and `created_at_utc` are computed during inference but **not exposed to API consumers**.

### The gap

1. **No structured output wrapper.** The 8 mandatory fields are raw model metadata — they lack context, intended-use statement, safety limitations, and decision-support framing.

2. **No decision-support classification output.** The `triage_recommendation` ("MRI_RECOMMENDED" / "MRI_RULE_OUT") is computed but never returned to API consumers.

3. **No safety/limitation language in API output.** Operators and downstream systems need a clear, non-diagnostic statement of what the prediction means (and doesn't mean) baked into the response.

4. **No input summary.** The response does not indicate whether explicit target/control refs were used, which layout was detected, or which input mode (h5_path / h5_uri) was used.

### What PR0053 does

- Adds a new module (`src/bremen/api/decision_support.py`) with a pure function `build_decision_support_report()` that wraps the inference result dict into a structured report.
- Adds `decision_support_report` field to the `CompletedResult` dataclass and returns it through the poll endpoint.
- Preserves all 8 existing `COMPLETED_RESULT_FIELDS` at the top level of the result dict for backward compatibility.
- Updates `docs/api_contract.md` to document the decision-support report schema.
- Adds synthetic tests for report structure, safety limits, and backward compatibility.

---

## 4. Roadmap Alignment

1. **PR0053 follows PR0052.** ROADMAP.md "Next Execution Sequence": PR0050 → PR0051 → PR0052 → PR0053 → PR0054. PR0052 (system-of-record boundary skeleton) has been merged (confirmed by PR0052 precommit-review.yml showing 657 passed tests). PR0053 is the next scheduled item.

2. **PR0053 is decision-support report / output wrapper.** ROADMAP.md: "Controlled output around prediction result. No diagnosis, no clinical validation claim."

3. **PR0054 remains release readiness / operator notes.** ROADMAP.md: "Production checklist, rollback, smoke commands, model artifact notes."

4. **This plan does not start PR0054 work.** No release readiness, no operator runbook changes.

5. **FastAPI remains deferred.** No FastAPI, uvicorn, starlette, or ASGI references.

---

## 5. Output Contract Plan

### 5.1 Decision-support report schema

The `decision_support_report` is a nested dict added to the `CompletedResult` and returned in the `GET /predictions/{job_id}` poll response `result` dict. The existing 8 top-level mandatory fields remain unchanged.

```python
decision_support_report = {
    "report_schema_version": "v0.1",
    "intended_use": "MRI continuation decision support only. "
                     "This output is not a diagnosis. "
                     "It is not clinically validated. "
                     "It does not replace MRI, biopsy, "
                     "radiologist, clinician, or clinical judgment.",
    "limitations": [
        "This is decision-support output only.",
        "Not a diagnostic result.",
        "Not clinically validated.",
        "Does not replace MRI, biopsy, radiologist, clinician, "
        "or clinical judgment.",
        "All clinical decisions must be made by qualified "
        "clinicians based on full patient history and "
        "diagnostic workup.",
    ],
    "model_metadata": {
        "model_version": "<str>",
        "feature_schema_version": "v0.1",
        "threshold_version": "<str>",
        "threshold_value": 0.5,
        # No raw model_checksum — only model_version for identity
        # No raw model URI
    },
    "input_summary": {
        "input_mode": "h5_uri|h5_path",  # safe category only
        "explicit_refs_provided": True,
        "layout_category": "canonical|calibration_sample|unknown",
        # No raw H5 path
        # No full S3 URI
        # No raw target/control refs
    },
    "prediction_summary": {
        "p_mri_needed": 0.75,
        "triage_recommendation": "MRI_RECOMMENDED|MRI_RULE_OUT",
        "qc_status": "passed|failed",
        "qc_flags": [],
    },
    "decision_support": {
        "recommendation": "MRI_RECOMMENDED|MRI_RULE_OUT",
        "recommendation_label": (
            "Based on the model output, MRI follow-up "
            "may be recommended for this patient."
            if triage == "MRI_RECOMMENDED" else
            "Based on the model output, MRI follow-up "
            "may not be indicated for this patient."
        ),
        "caution": (
            "This is a decision-support recommendation only. "
            "It is not a clinical decision. "
            "The final decision must be made by a qualified "
            "clinician."
        ),
    },
}
```

### 5.2 `build_decision_support_report()` — pure function

```python
def build_decision_support_report(
    inference_result: dict,
    *,
    input_mode: str = "unknown",
    explicit_refs: bool | None = None,
    layout_category: str | None = None,
) -> dict:
    """Build a safe decision-support report around an inference result.

    Parameters
    ----------
    inference_result : The dict returned by ``run_inference()``.
    input_mode : The input mode category (h5_uri, h5_path, or
        future source_record_ref).
    explicit_refs : Whether explicit target/control refs were provided.
    layout_category : The detected H5 layout category.

    Returns
    -------
    A decision-support report dict. Does NOT contain raw patient
    identifiers, raw H5 paths, full S3 URIs, raw checksums, raw
    feature values, or secrets.
    """
```

This function:
- Extracts safe fields from the inference result dict only
- Does NOT access ModelState, Config, H5 files, or any global state
- Is pure — output depends only on inputs
- Is deterministic for testing — timestamps are NOT added (the inference result dict already has `created_at_utc`)
- Is safe — no raw identifiers, no full URIs, no raw feature values

### 5.3 Report safety rules

| Field category | Safe content | Forbidden content |
|---|---|---|
| `model_metadata` | `model_version`, `feature_schema_version`, `threshold_version`, `threshold_value` | `model_checksum` (raw hex), full S3 URI, bucket/key |
| `input_summary` | `input_mode` category string, `explicit_refs_provided` bool, `layout_category` string | Raw `h5_path`, full `h5_uri`, raw `target_scan_ref`, raw `control_scan_ref` |
| `prediction_summary` | Numeric `p_mri_needed`, enum `triage_recommendation`, `qc_status`, `qc_flags` list | Raw feature vectors, patient identifiers beyond `patient_id`, H5 paths |
| `decision_support` | Template-based `recommendation_label`, `caution` string | No clinical diagnosis wording, no definitive claims |
| `limitations` | Predefined safe string list | None — fixed safe content |

### 5.4 Input summary construction

The `input_mode` and `explicit_refs` parameters come from the caller context. In the current architecture:

- `handle_submit_prediction()` in `app.py` knows whether `h5_path` or `h5_uri` was used, and knows `target_scan_ref` / `control_scan_ref` were provided.
- `run_inference()` does NOT currently receive this context as structured metadata.

**Plan for passing context to the output wrapper:** Add a new optional `input_mode` parameter to `run_inference()`:

```python
def run_inference(
    h5_path: str,
    patient_id: str | None = None,
    target_scan_ref: str | None = None,
    control_scan_ref: str | None = None,
    input_mode: str | None = None,  # NEW: "h5_uri", "h5_path", or None
) -> dict[str, Any]:
```

This is a pure metadata addition — no behavior change, no math change, no staging change. `handle_submit_prediction()` passes the input mode info through. Default `None` preserves backward compatibility for direct callers.

The `layout_category` is already available from the preflight result metadata (`preflight_result.metadata.get("layout_name")`), which is accessible inside `run_inference()`.

---

## 6. Compatibility Plan

### 6.1 Backward compatibility decisions

| Concern | Decision |
|---------|----------|
| 8 mandatory `COMPLETED_RESULT_FIELDS` at top level | **Preserved.** The `decision_support_report` is nested. Existing clients that read `result["prediction_id"]` etc. continue to work. |
| `CompletedResult` dataclass | **New optional field added.** `decision_support_report: dict | None = None`. The 8 existing fields are unchanged. `build_not_configured_model_response()` unchanged (it returns a `ModelVersionResponse`, not `CompletedResult`). |
| `run_inference()` return dict | **New field added.** `decision_support_report` key added to the flat dict. All 12 existing keys preserved. |
| `handle_get_prediction()` result dict construction | **Updated** to include `decision_support_report` from `CompletedResult` when present. |
| `validate_prediction_request()` | **No change.** Request schema is unchanged. |
| `PredictionRequest` | **No change.** No new request fields. |
| Production smoke test | **Minimal update** — add `decision_support_report` field to expected completed result assertions, but keep existing mandatory field checks untouched. |
| Logging | **No change.** No new log events. The existing inference and job completion events remain unchanged. The report is data, not log events. |

### 6.2 Response shape evolution

**Before PR0053** (`GET /predictions/{job_id}` completed):
```json
{
    "result": {
        "prediction_id": "...",
        "model_version": "...",
        "model_checksum": "...",
        "feature_schema_version": "v0.1",
        "threshold_version": "...",
        "threshold_value": 0.5,
        "qc_status": "passed",
        "qc_flags": []
    },
    ...
}
```

**After PR0053** (`GET /predictions/{job_id}` completed):
```json
{
    "result": {
        "prediction_id": "...",
        "model_version": "...",
        "model_checksum": "...",
        "feature_schema_version": "v0.1",
        "threshold_version": "...",
        "threshold_value": 0.5,
        "qc_status": "passed",
        "qc_flags": [],
        "decision_support_report": { ... }
    },
    ...
}
```

The 8 top-level result fields are unchanged. A new nested dict is appended.

---

## 7. File Change Plan

### 7.1 New files

| File | Purpose |
|------|---------|
| `src/bremen/api/decision_support.py` | Pure module with `REPORT_SCHEMA_VERSION`, `INTENDED_USE`, `LIMITATIONS`, `CAUTION_TEXT` constants and `build_decision_support_report()` function |
| `tests/test_bremen_decision_support_output.py` | Synthetic tests for report structure, safety, backward compatibility |

### 7.2 Modified files

| File | Change | Scope |
|------|--------|-------|
| `src/bremen/api/schemas.py` | Add `decision_support_report: dict \| None = None` field to `CompletedResult`. Keep `COMPLETED_RESULT_FIELDS` unchanged (8 fields — the report is NOT one of the mandatory contract fields; it is an add-on). | **Minimal** — one new field in existing dataclass. |
| `src/bremen/api/inference_handler.py` | (a) Add optional `input_mode: str \| None = None` parameter to `run_inference()`. (b) Import and call `build_decision_support_report()` after assembling the prediction dict. (c) Add `input_mode` and `layout_category` context. (d) Add `decision_support_report` to the returned dict. | **Minimal** — ~5 new lines, no math change, no pipeline change. |
| `src/bremen/api/app.py` | Update `handle_submit_prediction()` to pass `input_mode` to `run_inference()`. Update `handle_get_prediction()` to include `decision_support_report` in the result dict. | **Minimal** — ~3 lines. |
| `docs/api_contract.md` | Add "Decision-Support Report" section documenting the report schema, field meanings, limitations, intended use, and safety rules. | **New section** at end of document. Existing contract sections unchanged. |
| `tests/test_bremen_inference_integration.py` | Update `test_end_to_end_synthetic_inference` to assert `decision_support_report` is present in `run_inference()` output. | **One assertion** added to existing test. |
| `tests/test_bremen_production_smoke.py` | Update completed result assertions to include `decision_support_report` field check. | **One assertion** added to `TestProductionSmokeH5UriExplicitRefs`. |

### 7.3 No changes

| File | Rationale |
|------|-----------|
| `src/bremen/inference.py` | No math change. `predict_proba_portable()` unchanged. |
| `src/bremen/api/jobs.py` | `InMemoryJobStore` and `JobRecord` unchanged — `CompletedResult` carries the report, stored in `record.result`. |
| `src/bremen/api/preprocessing_bridge.py` | No preprocessing change. |
| `src/bremen/api/h5_layouts.py` | No layout change. |
| `src/bremen/api/preflight.py` | No preflight change. |
| `src/bremen/api/model_state.py` | No model state change. |
| `src/bremen/api/model_source.py` | No model source change. |
| `src/bremen/api/system_of_record.py` | No boundary change. |
| `src/bremen/h5_inputs.py` | No staging change. |
| `src/bremen/model_package.py` | No model package change. |
| `tests/test_bremen_predictions.py` | No prediction test changes — `CompletedResult` field addition is backward compatible. |
| `tests/test_bremen_api_skeleton.py` | No skeleton test changes — existing mandatory field assertions unchanged. |
| `tests/test_bremen_api_server.py` | No server test changes — poll response shape fields are backward compatible. |
| `tests/test_bremen_logging.py` | No logging changes — report is data, not log events. |
| `tests/test_bremen_system_of_record_boundary.py` | No boundary test changes. |
| `tests/test_bremen_config_governance.py` | No governance test changes — unless a static ADR check for the report is justified (optional). |
| `docs/production_e2e_smoke.md` | No smoke doc changes — the smoke expected response already shows `result` fields. The report is additive. |

---

## 8. Test Plan

### 8.1 New test file: `tests/test_bremen_decision_support_output.py`

All tests are synthetic/mocked. No AWS, Docker, Terraform, App Runner, network, real H5, real model artifact, real Matador, or credentials.

#### Class A: `TestReportSchema`

1. `test_report_schema_version_is_defined` — `REPORT_SCHEMA_VERSION` constant is a non-empty string.
2. `test_report_contains_schema_version` — `build_decision_support_report({'prediction_id': 'x', ...})["report_schema_version"]` equals `REPORT_SCHEMA_VERSION`.

#### Class B: `TestIntendedUseAndLimitations`

3. `test_report_contains_intended_use` — Report dict has `"intended_use"` key with string value mentioning "decision support".
4. `test_report_contains_limitations_list` — Report dict has `"limitations"` key with a non-empty list of strings.
5. `test_limitations_mention_not_diagnosis` — At least one limitation string contains "not a diagnosis" or "Not a diagnostic".
6. `test_limitations_mention_no_clinical_validation` — At least one limitation mentions "not clinically validated".
7. `test_limitations_mention_no_replacement` — At least one limitation states the output does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.
8. `test_intended_use_contains_mri_continuation` — Intended use string mentions "MRI continuation" or "MRI follow-up".

#### Class C: `TestModelMetadata`

9. `test_report_contains_model_version` — Report's `model_metadata` includes `model_version` from the inference result.
10. `test_report_contains_feature_schema_version` — Report's `model_metadata` includes `feature_schema_version`.
11. `test_report_contains_threshold_version` — Report's `model_metadata` includes `threshold_version`.
12. `test_report_contains_threshold_value` — Report's `model_metadata` includes `threshold_value`.
13. `test_report_does_not_expose_raw_checksum` — Report's `model_metadata` does NOT contain `model_checksum`.
14. `test_report_does_not_expose_model_uri` — Report's `model_metadata` does NOT contain `model_uri` or `model_path`.

#### Class D: `TestInputSummary`

15. `test_report_contains_input_mode` — Report's `input_summary` includes `input_mode` string matching the provided parameter.
16. `test_report_contains_explicit_refs_bool` — Report's `input_summary` includes `explicit_refs_provided` boolean.
17. `test_report_contains_layout_category` — Report's `input_summary` includes `layout_category` string.
18. `test_report_does_not_expose_raw_h5_path` — Report's `input_summary` does NOT contain `h5_path`, `h5_uri`, `target_scan_ref`, or `control_scan_ref` keys.

#### Class E: `TestPredictionSummary`

19. `test_report_contains_p_mri_needed` — Report's `prediction_summary` includes `p_mri_needed` float.
20. `test_report_contains_triage_recommendation` — Report's `prediction_summary` includes `triage_recommendation` string.
21. `test_report_contains_qc_status` — Report's `prediction_summary` includes `qc_status` string.
22. `test_report_contains_qc_flags` — Report's `prediction_summary` includes `qc_flags` list.

#### Class F: `TestDecisionSupport`

23. `test_report_contains_recommendation` — Report's `decision_support` includes `recommendation` string matching the triage value.
24. `test_report_contains_recommendation_label` — Report's `decision_support` includes `recommendation_label` string with safe language.
25. `test_recommendation_label_does_not_say_diagnosis` — The `recommendation_label` does NOT contain "diagnosis", "cancer", "benign", or "malignant".
26. `test_report_contains_caution` — Report's `decision_support` includes a `caution` string.
27. `test_caution_mentions_decision_support` — The `caution` mentions "decision-support" or "not a clinical decision".
28. `test_caution_mentions_clinician` — The `caution` mentions "clinician".

#### Class G: `TestBackwardCompatibility`

29. `test_report_is_additive_does_not_remove_any_field` — Given a synthetic `run_inference()` dict with all 12 fields, `build_decision_support_report()` returns only the report dict; the original fields are preserved in the caller's dict (tested through the full `run_inference()` integration test).
30. `test_report_parameter_defaults_are_safe` — Calling `build_decision_support_report(inference_result={...})` with no optional keyword arguments returns a valid report with sensible defaults (`input_mode="unknown"`, `explicit_refs=None`, `layout_category=None`).

#### Class H: `TestSafetyBoundary`

31. `test_report_does_not_contain_raw_feature_values` — Report's `prediction_summary` does NOT contain feature vectors or raw feature values.
32. `test_report_does_not_contain_patient_identifiers_beyond_patient_id` — Report's `input_summary` and `prediction_summary` do not contain the `patient_id` value (it remains at the top level of the result dict, not duplicated in the report).

### 8.2 Existing test modifications

#### `tests/test_bremen_inference_integration.py`

- `TestEndToEndInference.test_end_to_end_synthetic_inference`: Add assertion that `"decision_support_report" in result` after calling `run_inference()`. Verify the report dict has top-level keys (`report_schema_version`, `intended_use`, `limitations`, etc.).

#### `tests/test_bremen_production_smoke.py`

- `TestProductionSmokeH5UriExplicitRefs.test_production_like_h5_uri_explicit_refs_completes_in_process`: Add assertion that `r.get("decision_support_report")` is not `None` and contains `report_schema_version`. Keep all existing mandatory field assertions.

---

## 9. Doc Plan

### 9.1 `docs/api_contract.md` — Decision-Support Report section

Add a new section at the end of the document (after the existing "System of Record Boundary (PR0052)" section):

```
### Decision-Support Report (PR0053)

When a prediction job completes, the `result` dict includes a
`decision_support_report` field with the following structure:

**report_schema_version**: `"v0.1"` — stable version string for the
decision-support report contract.

**intended_use**: String stating "MRI continuation decision support only."
States that the output is not a diagnosis, not clinically validated, and
does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.

**limitations**: List of predefined safety limitation strings.

**model_metadata**: Safe model identification fields:
- `model_version` (str)
- `feature_schema_version` (str)
- `threshold_version` (str)
- `threshold_value` (float)

Does NOT include raw model_checksum or model URI.

**input_summary**: Safe input context fields:
- `input_mode` (str): `"h5_uri"`, `"h5_path"`, or `"unknown"`
- `explicit_refs_provided` (bool)
- `layout_category` (str): `"canonical"`, `"calibration_sample"`, or `"unknown"`

Does NOT include raw H5 path, full S3 URI, or raw target/control refs.

**prediction_summary**: Model output fields:
- `p_mri_needed` (float): Probability estimate in [0.0, 1.0]
- `triage_recommendation` (str): `"MRI_RECOMMENDED"` or `"MRI_RULE_OUT"`
- `qc_status` (str): `"passed"` or `"failed"`
- `qc_flags` (list)

**decision_support**: Safe recommendation framing:
- `recommendation` (str): Same value as `triage_recommendation`
- `recommendation_label` (str): Human-readable cautionary label
- `caution` (str): Standard decision-support disclaimer

Safety rules:
- No raw patient identifiers in report fields.
- No raw checksum, full S3 URI, or model artifact path.
- No raw feature values or feature vectors.
- No clinical diagnosis or definitive claims.
- `recommendation_label` uses only "may be recommended" / "may not be indicated" language.
```

### 9.2 `docs/production_e2e_smoke.md` — No changes needed

The smoke doc's expected `result` JSON shows the 8 mandatory fields. The `decision_support_report` is additive — existing smoke consumers that check only the mandatory fields continue to work. The smoke doc's "Success criteria" item 4 ("result is non-null and contains all mandatory fields") is unaffected.

---

## 10. Preserved Boundaries

1. No FastAPI — preserved.
2. No Matador integration — preserved.
3. No source-of-record schema change — preserved.
4. No DynamoDB/backend implementation — preserved.
5. No new deployment target — preserved.
6. No Docker changes — preserved.
7. No Terraform changes — preserved.
8. No dependency changes — preserved.
9. No training behavior changes — preserved.
10. No runtime model lifecycle changes — preserved.
11. No checksum boundary changes — preserved.
12. No S3 model staging changes — preserved.
13. No S3 H5 input staging changes — preserved.
14. No H5 layout changes — preserved.
15. No preprocessing changes — preserved.
16. No inference math changes — preserved.
17. No threshold behavior changes — preserved.
18. No production smoke execution — preserved.
19. No clinical validation claims — preserved.
20. No diagnosis — preserved.
21. No replacement of clinical judgment — preserved.
22. No changes to `validate_prediction_request()` — preserved.
23. No changes to `PredictionRequest` schema — preserved.
24. No changes to `COMPLETED_RESULT_FIELDS` (8 mandatory fields) — preserved.

---

## 11. Validation Plan

### 11.1 Implementation validation

```bash
python -m compileall src tests

python -m pytest -q tests/test_bremen_decision_support_output.py -v
python -m pytest -q tests/test_bremen_inference_integration.py -v
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_api_skeleton.py -v
python -m pytest -q tests/test_bremen_api_server.py -v
python -m pytest -q tests/test_bremen_production_smoke.py -v
python -m pytest -q tests/test_bremen_logging.py -v
python -m pytest -q
```

### 11.2 Safety validation

```bash
# 1. Verify only allowed files changed
git diff --name-only

# 2. Verify no forbidden files changed
git diff --name-only -- ROADMAP.md Dockerfile Dockerfile.training infra .github \
  requirements.txt pyproject.toml src/bremen/training agents || true

# 3. Verify no binary artifact changes
git diff --name-only | grep -E '\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$' || true

# 4. Verify no FastAPI/uvicorn/starlette introduced
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n src tests docs requirements.txt pyproject.toml || true

# 5. Verify no Matador network/credentials/URLs introduced
grep -R "MATADOR_\|Matador.*token\|Matador.*URL\|requests\|httpx\|aiohttp" \
  -n src tests docs requirements.txt pyproject.toml || true

# 6. Verify no secrets/identifiers in new or modified files
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|Nova_\|s3://\|/Users/\|/home/" \
  -n src/bremen/api/decision_support.py \
  tests/test_bremen_decision_support_output.py \
  docs/api_contract.md || true

# 7. Verify no diagnosis/clinical validation claims in new output
grep -R "diagnos\|clinical validation\|replace radiologist\|replace clinician\|replace MRI\|replace biopsy" \
  -n src/bremen/api/decision_support.py \
  tests/test_bremen_decision_support_output.py \
  docs/api_contract.md || true

# 8. Verify the safety grep hits are only limitations/safety statements
python -c "
import re, sys
with open('src/bremen/api/decision_support.py') as f:
    content = f.read()
# Check that 'diagnosis' only appears in limitation/safety context
for m in re.finditer(r'(?i)diagnos', content):
    start = max(0, m.start() - 60)
    end = min(len(content), m.end() + 60)
    context = content[start:end].strip()
    assert 'not a diagnosis' in context.lower() or \
           'not a diagnostic' in context.lower() or \
           'not diagnose' in context.lower(), \
        f'Diagnosis reference outside safety context: ...{context}...'
print('All diagnosis references are in safety limitation context')
"
```

---

## 12. Non-Goals

1. No FastAPI.
2. No real Matador adapter.
3. No Matador API calls.
4. No Matador credentials.
5. No public `source_record_ref` request field.
6. No config backend.
7. No DynamoDB implementation.
8. No AWS calls.
9. No App Runner deployment.
10. No Docker or Terraform change.
11. No dependency change.
12. No runtime model loading change.
13. No model package format change.
14. No H5 layout change.
15. No preprocessing or inference math change.
16. No threshold behavior change.
17. No training behavior change.
18. No production smoke execution.
19. No diagnosis.
20. No clinical validation claim.
21. No replacement of clinical judgment.
22. No PR0054 release readiness/operator notes.
23. No new report log events — report is data, not observability.
24. No changes to `COMPLETED_RESULT_FIELDS` — 8 mandatory fields preserved.
25. No changes to `validate_prediction_request()`.

---

## 13. Implementation Agent Assignment

**Agent**: coder

**Ordered task list**:
1. Read this PLAN.md and the required artifacts listed in the task prompt (all read by the plan agent).
2. Create `src/bremen/api/decision_support.py` — new module with constants and `build_decision_support_report()` pure function.
3. Create `tests/test_bremen_decision_support_output.py` — 8 test classes, ~32 test methods. All synthetic/static.
4. Modify `src/bremen/api/schemas.py` — add `decision_support_report: dict | None = None` to `CompletedResult`.
5. Modify `src/bremen/api/inference_handler.py` — add `input_mode` parameter, import and call `build_decision_support_report()`, add report to output dict.
6. Modify `src/bremen/api/app.py` — pass `input_mode` in `handle_submit_prediction()`, include report in `handle_get_prediction()` result.
7. Modify `tests/test_bremen_inference_integration.py` — add one assertion for the report's presence.
8. Modify `tests/test_bremen_production_smoke.py` — add one assertion for the report's presence.
9. Modify `docs/api_contract.md` — add Decision-Support Report section.
10. Run validation checklist (Section 11) and fix any failures.
11. Commit all changes. Verify no forbidden artifacts.

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. The `input_mode` parameter addition to `run_inference()` is a pure metadata pass-through — no behavior change. It affects the function signature but the default `None` preserves backward compatibility for all existing callers.
2. Safety validation grep (step 6) will match `s3://` in types/schemas that accept or reject S3 URIs, `Nova_` in validation patterns that reject raw patient IDs, and `/Users/` in path validation patterns. These are safe. The grep output must be inspected and classified, not hidden.
3. Step 7 grep for "diagnos" will match the `not a diagnosis` / `not a diagnostic` safety language in the new module and tests. The post-grep Python check (step 8) verifies these are in safe limitation context only.
4. The `decision_support_report` field in `CompletedResult` is NOT added to the `COMPLETED_RESULT_FIELDS` list. The 8 mandatory fields remain the contract-level invariant. The report is an additive extension. Governance tests that check `COMPLETED_RESULT_FIELDS` set membership will not be affected.

FILES CHANGED:
- `.project-memory/pr/0053-decision-support-output-wrapper/PLAN.md` — written
- `.project-memory/pr/0053-decision-support-output-wrapper/reviews/plan-review.yml` — future artifact

ROADMAP ALIGNMENT:
PR0053 confirmed as next after PR0052. PR0054 deferred. FastAPI deferred. No PR0054 work started.

PROBLEM SUMMARY:
Existing inference computes `p_mri_needed` and `triage_recommendation` but these fields are lost in the CompletedResult serialization — API consumers see only 8 mandatory fields. No structured decision-support wrapper with safety language, input summary, or limitations exists.

OUTPUT CONTRACT PLAN:
Decision-support report nested dict with 6 sections: report_schema_version, intended_use, limitations (list), model_metadata (safe fields only, no raw checksum/URI), input_summary (mode, refs, layout — no raw paths), prediction_summary (p_mri_needed, triage, qc), and decision_support (recommendation, label, caution). Pure function `build_decision_support_report()` in new module. No raw patient identifiers, feature values, secrets, or diagnosis claims.

COMPATIBILITY PLAN:
All 8 mandatory COMPLETED_RESULT_FIELDS preserved at top level. New `decision_support_report` field is nested/additive. No request schema changes. No validate_prediction_request changes. CompletedResult gets an optional field. run_inference gets an optional input_mode parameter (default None). Existing callers unchanged. Production smoke gets one additional assertion.

FILE CHANGE PLAN:
2 new files (decision_support.py, test file). 4 modified source files (schemas.py, inference_handler.py, app.py — ~10 lines total). 2 modified test files (inference_integration.py, production_smoke.py — 2 assertions total). 1 modified doc (api_contract.md — new section). No changes to 12+ existing files listed as "no changes."

TEST PLAN:
8 test classes (A–H), 32 test methods. Classes: ReportSchema (2), IntendedUse&Limitations (6), ModelMetadata (6), InputSummary (4), PredictionSummary (4), DecisionSupport (6), BackwardCompatibility (2), SafetyBoundary (2). All synthetic/mocked. Existing test files get 2 new assertions total.

DOC PLAN:
New "Decision-Support Report (PR0053)" section at end of api_contract.md documenting all report fields, safety rules, and the no-diagnosis/no-replacement disclaimer. 8 non-goal bullets in the section.

PRESERVED BOUNDARIES:
All 24 boundaries preserved. No math, threshold, staging, layout, preprocessing, or inference changes. Request schema unchanged. COMPLETED_RESULT_FIELDS unchanged. No FastAPI, Matador, DynamoDB, dependencies.

VALIDATION PLAN:
Compileall + 8 test suite commands + full suite + 8 safety/diff/grep scans + Python-based diagnosis-context verification.

NON-GOALS:
25 non-goal categories listed. Key: no COMPLETED_RESULT_FIELDS changes, no request schema changes, no preprocessing/inference/math changes, no new log events, no PR0054 work.

---

Implementation agent: coder
