# Bremen Platform production contracts, smoke baseline, and demo readiness

Date: 2026-09-18

## 1. Purpose

This document records what was actually verified in production before PR0163, what contracts are working, what regressions were found, and what must be fixed before the upcoming demo.

PR0163 is an orchestration / observability / contract-hardening PR.

It MUST NOT change scientific model behavior.

Scientific hard fence:

- no model coefficient changes;
- no decision-threshold changes;
- no raw-peak-threshold changes;
- no feature-definition changes;
- no preprocessing-artifact changes;
- no target-side semantic changes;
- no report interpretation changes.

---

## 2. Executive status

### Scientific / model execution

| Area | Status | Evidence |
| --- | --- | --- |
| Bremen execution | PASS | Fresh production execution completed and report available |
| Aramina 0.2.12 execution | PASS | Fresh Nova_257 left completed |
| Aramina 0.2.13 execution | PASS | Fresh Nova_257 left completed |
| Aramina unsupported-input handling | PASS | Nova_384 left failed safely on both releases |
| Bremen report JSON | PASS | Report 200 and StandardResult available |
| Aramina report JSON | PASS | Report 200 and StandardResult available |
| Alexey StandardResult shape | PASS | Bare object, no workflow wrapper |
| Exact replay recovery | PASS | HTTP 409 + existing job_id + successful report retrieval |
| Aramina preflight validation | FAIL | 32/32 false-negative validations |
| Aramina execution trace | FAIL | Completed jobs projected as not_started / readiness / 0 of 1 |
| Failed trace projection | FAIL / INCOMPLETE | Failure stage not projected into a useful trace |
| H5 patient display identity | FAIL / DEMO ISSUE | Known patient sources can appear as container filenames |
| Bremen current model metadata | NEEDS VERIFICATION | model_name appears inconsistent with selected model_id |

### Demo readiness

The scientific execution path is working.

The demo is NOT fully ready until the orchestration/UI regressions are fixed because:

1. Aramina preflight currently rejects known-good inputs.
2. Aramina trace can show a completed job as not started.
3. Patient identity can be lost in the H5 catalog/UI and replaced by the container filename.
4. Bremen StandardResult model_name needs package-owned metadata verification.

If the frontend gates submission on preflight, Aramina can appear unusable even though real execution works.

---

## 3. Production smoke executions

### 3.1 Bremen happy path

Verified production job:

```text
job_id=2b174fb6-01f6-4c00-91a3-6eca87923f6b
workflow=bremen
patient=Nova_376
model_id=bremen-mri-triage-logreg-v0-1
model_version=bremen_mri_triage_logreg_v0_1
overall_status=completed
report=available
```

Observed result:

```text
risk_probability=0.5677291934209008
threshold_value=0.3640352477169748
target_class_risk_level=high
left_measurement_count=3
right_measurement_count=3
reliability=HIGH_TECHNICAL
technical_demo_only=true
scientifically_certified=false
```

The report endpoint returned HTTP 200.

### 3.2 Bremen expected scientific failure

The Bremen package can reject an input at feature construction with:

```text
raw_peak_gate_failed
```

This is a package-owned scientific gate, not an estimator failure.

The threshold/science must not be changed in PR0163.

Expected semantics:

```text
raw H5
-> Bremen package preprocessing
-> profiles/features
-> mean_peak_value_raw
-> raw peak gate
-> estimator only if gate passes
```

---

## 4. Aramina production executions

### 4.1 Aramina 0.2.12 happy path

Fresh production job:

```text
job_id=225f10bc-18f8-4343-a11e-eb86d77ac58f
patient=Nova_257
target_side=left
model_id=aramina_target_breast_risk_0_2_12-beta_9bb911189af6
model_version=0.2.12-beta
HTTP POST /jobs=201
overall_status=completed
report=available
```

Observed result:

```text
risk_probability=0.9430773645281599
risk_score=0.9430773645281599
threshold_value=0.24665932038818544
target_class_risk_level=high
technical_demo_only=true
```

Report retrieval:

```text
GET /demo/api/jobs/225f10bc-18f8-4343-a11e-eb86d77ac58f/reports/aramina
HTTP 200
```

### 4.2 Aramina 0.2.13 happy path

Fresh production job:

```text
job_id=42d8adc3-1d4a-44ee-9a67-21adb31c8899
patient=Nova_257
target_side=left
model_id=aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11
model_version=0.2.13-beta
HTTP POST /jobs=201
overall_status=completed
report=available
```

Observed result:

```text
risk_probability=0.9430773645281599
risk_score=0.9430773645281599
threshold_value=0.24665932038818544
target_class_risk_level=high
technical_demo_only=true
```

The equal score between 0.2.12 and 0.2.13 is only a parity observation for this specific input. It is not a requirement that all inputs have equal scores across releases.

### 4.3 Aramina 0.2.12 expected unsupported input

Fresh production job:

```text
job_id=de9d425e-6060-4101-8058-a116bca1706c
patient=Nova_384
target_side=left
model_version=0.2.12-beta
HTTP POST /jobs=201
overall_status=failed
```

Stable safe classification:

```text
failure=ARAMINA_UNSUPPORTED_INPUT
failure_stage=preprocessing_contract
failure_reason_code=ARAMINA_UNSUPPORTED_INPUT_PREPROCESSING_CONTRACT
preprocessing_release=v0.1.7-beta
preprocessing_stage=worker_pipeline_execution
preprocessing_exception_class=ValueError
preprocessing_transformer=H5PoniGeometryCalculatorTransformer
preprocessing_reason_code=ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED
```

Report endpoint returned HTTP 200 with:

```text
report.status=unavailable
reason_code=REPORT_NOT_AVAILABLE
```

### 4.4 Aramina 0.2.13 expected unsupported input

Fresh production job:

```text
job_id=741063de-6aa2-4a1b-a770-ea7cebcc4194
patient=Nova_384
target_side=left
model_version=0.2.13-beta
HTTP POST /jobs=201
overall_status=failed
```

Stable safe classification:

```text
failure=ARAMINA_UNSUPPORTED_INPUT
failure_stage=preprocessing_contract
failure_reason_code=ARAMINA_UNSUPPORTED_INPUT_PREPROCESSING_CONTRACT
preprocessing_release=v0.1.9-beta
preprocessing_stage=worker_pipeline_execution
preprocessing_exception_class=ValueError
preprocessing_transformer=H5PoniGeometryCalculatorTransformer
preprocessing_reason_code=ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED
```

Report endpoint returned HTTP 200 with:

```text
report.status=unavailable
reason_code=REPORT_NOT_AVAILABLE
```

---

## 5. Aramina patient compatibility evidence

Important: current `/requirements/validate` cannot be used as the source of truth for compatibility because it produces false negatives.

### Fresh production executions verified on 2026-09-18

| Patient | 0.2.12 | 0.2.13 | Side | Status |
| --- | --- | --- | --- | --- |
| Nova_257 | PASS | PASS | left | Fresh real executions completed |
| Nova_384 | EXPECTED FAIL | EXPECTED FAIL | left | Fresh real executions classified unsupported |

### Retained / historical successful evidence

| Patient | 0.2.12 | 0.2.13 | Notes |
| --- | --- | --- | --- |
| Nova_214 | Previously completed | Previously completed | 0.2.13 left retained report risk 0.869387073973647 |
| Nova_227 | Previously completed | Previously completed | Known-good smoke combinations |
| Nova_257 | Previously completed left/right | Previously completed left/right | Fresh left reconfirmed on both models |

Known historical/current unsupported preprocessing examples include:

```text
Nova_376
Nova_378
Nova_379
Nova_383
Nova_384
```

These are technical H5/model preprocessing compatibility observations, not clinical statements.

### Not yet fully re-executed in the current session

The following were included in the 32 preflight matrix but were not all re-run as fresh real jobs in both models and both sides during this session:

```text
Nova_214
Nova_227
Nova_376
Nova_378
Nova_379
Nova_383
```

Do not classify those solely from current preflight results.

---

## 6. Confirmed regression: Aramina requirements validation

A production preflight matrix was executed for:

```text
8 patients
x 2 Aramina model versions
x 2 target sides
= 32 validations
```

Patients:

```text
Nova_257
Nova_214
Nova_227
Nova_376
Nova_378
Nova_379
Nova_383
Nova_384
```

All 32 returned:

```text
validation.status=failed
validation.ready_to_run=false
failure_stage=model_execution
next_step.can_submit_job=false
```

This is proven wrong because real fresh execution immediately succeeded for:

```text
Nova_257 / 0.2.12 / left
Nova_257 / 0.2.13 / left
```

Therefore the current dry-run/preflight path is not equivalent to the real job execution path.

### Required fix

Validation must reuse the same package-owned scientific execution contract as the real job, but without:

- persistence;
- report creation;
- externally visible side effects.

Expected happy behavior:

```text
validation.status=passed
validation.ready_to_run=true
next_step.can_submit_job=true
```

Expected unsupported behavior:

```text
validation.status=failed
validation.ready_to_run=false
failure classification consistent with real execution
```

The HTTP/platform layer must not reimplement scientific preprocessing.

---

## 7. Confirmed regression: Aramina execution trace

Fresh completed Aramina jobs return a contradictory trace:

```text
workflow.status=completed

trace.current_stage=readiness
trace.status=not_started
trace.completed_stage_count=0
trace.total_applicable_stage_count=1
trace.duration_ms=0
```

The real executions took approximately 23 seconds and produced reports.

### Required fix

Completed workflow:

```text
trace.status=completed
trace.current_stage=<final applicable stage>
completed stages accurately represented
duration_ms reflects actual execution duration
```

Failed workflow:

```text
trace.status=failed
trace.current_stage=<actual failure stage>
failing stage marked failed
safe reason_code projected where available
```

A resolved workflow event must not be shown as a failed workflow in the UI.

---

## 8. Patient identity / frontend demo issue

A production UI problem was observed: instead of a patient name/identifier, the frontend can show the H5 container filename.

Examples of physical names seen in the catalog include:

```text
atypical_one_patient.h5
cancer_one_patient.h5
benign_one_patient.h5
```

Those stable sources historically corresponded to known patient identities, but the current catalog can return an empty `patient_display_name`.

### What is known

The issue is not that the frontend should derive the patient from the filename.

The correct rule is:

```text
display label = patient_display_name || display_name
```

But `patient_display_name` must first be preserved by the backend/catalog when legitimate patient identity is available from source metadata/registration.

### Required fix

- Preserve legitimate `patient_display_name` in `/api/h5/containers`.
- Frontend should prefer `patient_display_name`.
- Fall back to `display_name` only when patient identity is unavailable.
- Never infer patient identity from `cancer`, `benign`, `atypical`, or other filename text.
- Never hardcode stable-source-key -> patient mappings in product code.

This is demo-critical because showing filenames instead of patient identifiers makes the workflow appear incorrect even when inference succeeds.

---

## 9. StandardResult contract for Alexey Platform

The canonical result is:

```text
report.standard_result
```

It is a bare StandardResult object.

There is no extra workflow wrapper.

Correct:

```json
{
  "report_id": "...",
  "created_at": "...",
  "analysis_author": "...",
  "prediction_comment": "",
  "patient_id": "Nova_257",
  "patient_age": 49,
  "referring_physician": "",
  "scan_date_time": "2025-07-24T10:00:20",
  "operator_id": "backfill",
  "hardware_version": "v1.0.1",
  "eoscan_version": null,
  "model_name": "aramina_target_breast_risk",
  "model_version": "0.2.13-beta",
  "model_method": "m2q_gated_target_case",
  "model_metrics": {
    "sensitivity": 0.8175,
    "specificity": 0.37630084054979734
  },
  "threshold_value": 0.24665932038818544,
  "risk_probability": 0.9430773645281599,
  "target_class_risk_level": "high",
  "specific_output": {
    "target_side": "left",
    "mammography_suspicious_field": ""
  }
}
```

Must NOT be:

```json
{
  "aramina": {
    "...": "..."
  }
}
```

Must NOT be:

```json
{
  "bremen": {
    "...": "..."
  }
}
```

Production was checked for both workflows:

```text
has_aramina_wrapper=false
has_bremen_wrapper=false
```

### Bremen workflow-specific output

Bremen currently returns:

```json
"specific_output": {}
```

### Aramina workflow-specific output

Aramina currently returns:

```json
"specific_output": {
  "target_side": "left",
  "mammography_suspicious_field": ""
}
```

---

## 10. Existing report envelope compatibility

Do not move or rename the existing public fields:

```text
report.payload.risk_score
report.payload.technical_demo_only
```

`standard_result` is additive inside the existing workflow report.

There is no separate `/standard-result` endpoint.

Primary workflow report endpoints:

```text
GET /demo/api/jobs/{job_id}/reports/bremen
GET /demo/api/jobs/{job_id}/reports/aramina
```

Legacy `/reports/{job_id}/external` and `/internal` are Bremen-oriented and are not the primary Aramina integration endpoints.

---

## 11. Idempotency / replay behavior

### What was actually tested

Exact replay/recovery was tested in production for both Bremen and Aramina.

#### Bremen

Repeating the same source/model analysis returned:

```text
HTTP 409
error=report_already_exists
job_id=2b174fb6-01f6-4c00-91a3-6eca87923f6b
workflow_id=bremen
```

The existing job could then be retrieved and:

```text
GET /api/jobs/{job_id}/reports/bremen
HTTP 200
```

#### Aramina

Repeating the same source/model/patient/target_side returned:

```text
HTTP 409
error=report_already_exists
job_id=f053d74c-2f27-4d53-9ae9-3171866599bf
workflow_id=aramina
existing_target_side=left
requested_target_side=left
```

The existing job and report could then be retrieved successfully.

### Conclusion

Current exact-request replay is working as a recoverable contract:

```text
duplicate request
-> HTTP 409 report_already_exists
-> existing job_id
-> GET job
-> GET report
```

### What was NOT fully tested in this session

The full idempotency identity matrix was not exhaustively re-tested.

In particular, before the demo we should explicitly verify:

```text
same source + same model + same patient + same target_side
=> replay existing result

same source + same model + same patient + opposite target_side
=> distinct Aramina analysis

same source + different model_id
=> distinct analysis

newly registered source identity for same patient
=> new independent analysis
```

The current production behavior is HTTP 409 for an exact duplicate.

A future product behavior may prefer:

```text
HTTP 200
reused_existing=true
```

PR0163 does not need to redesign idempotency unless the frontend cannot recover the existing job/report.

---

## 12. H5 source identity rules

`source_id` is ephemeral.

Clients must refresh the H5 catalog immediately before submission:

```text
GET /demo/api/h5/containers
-> obtain fresh source_id
-> POST /demo/api/jobs
```

Do not cache `source_id`.

`stable_source_key` represents stable source identity, but should not be used as a patient-name lookup table.

---

## 13. Bremen model metadata check

Observed production StandardResult for:

```text
model_id=bremen-mri-triage-logreg-v0-1
```

contained:

```text
model_name=bremen_paper_reference_symmetry_logreg
model_version=bremen_mri_triage_logreg_v0_1
model_method=bremen_mri_triage_logreg_v0_1
```

This looks inconsistent and must be verified against package-owned manifest/metadata.

Do not invent or overwrite model metadata in the platform layer.

Only change it if the package/manifest proves that the current `model_name` is incorrect.

---

## 14. Contract status before demo

| Contract | Status |
| --- | --- |
| Auth Bearer token | PASS in production smoke |
| Model catalog | PASS |
| Model requirements discovery | PASS |
| H5 catalog/source resolution | PASS with patient-display regression |
| Fresh source_id submission | PASS |
| Bremen POST /jobs | PASS |
| Aramina POST /jobs | PASS |
| Bremen successful report | PASS |
| Aramina successful report | PASS |
| Bremen StandardResult | PASS |
| Aramina StandardResult | PASS |
| Stable report.payload fields | PASS |
| Aramina target_side in result | PASS |
| Safe unsupported-input failure | PASS |
| Failed report unavailable contract | PASS |
| Exact duplicate replay/recovery | PASS |
| Aramina requirements validation | FAIL |
| Aramina trace projection | FAIL |
| Patient name display/catalog projection | FAIL |
| Full idempotency dimension matrix | NOT YET FULLY VERIFIED |
| Bremen model_name metadata | NEEDS VERIFICATION |

---

## 15. PR0163 implementation scope

PR0163 should fix:

1. Aramina requirements/preflight false negatives.
2. Aramina completed trace projection.
3. Aramina failed trace projection.
4. H5 `patient_display_name` preservation.
5. Frontend patient-label preference.
6. Regression tests for Alexey StandardResult.
7. Verification/fix of Bremen `model_name` only if package-owned metadata proves a mismatch.
8. Documentation of production smoke and replay semantics.

PR0163 should NOT:

- change scientific algorithms;
- change preprocessing releases;
- change model thresholds;
- change risk scores;
- invent patient identity from filenames;
- hardcode stable-source mappings;
- redesign public report JSON unnecessarily.

---

## 16. Required regression tests

### StandardResult

For Bremen and Aramina:

```python
standard = response["report"]["standard_result"]

assert isinstance(standard, dict)
assert "bremen" not in standard
assert "aramina" not in standard
assert "patient_id" in standard
assert "model_name" in standard
assert "model_version" in standard
assert "threshold_value" in standard
assert "risk_probability" in standard
assert "target_class_risk_level" in standard
assert "specific_output" in standard
```

Keep stable:

```python
assert "risk_score" in response["report"]["payload"]
assert "technical_demo_only" in response["report"]["payload"]
```

### Aramina preflight parity

Known happy:

```text
Nova_257 / 0.2.12 / left
Nova_257 / 0.2.13 / left
```

Expected:

```text
preflight PASS
real execution PASS
```

Known unsupported:

```text
Nova_384 / 0.2.12 / left
Nova_384 / 0.2.13 / left
```

Expected:

```text
preflight classified FAIL
real execution classified FAIL
```

### Traces

Completed workflow:

```text
trace.status=completed
completed_stage_count > 0
duration_ms > 0
```

Failed workflow:

```text
trace.status=failed
current_stage represents the failing execution stage
```

### Patient identity

When patient identity is legitimately available:

```text
patient_display_name is preserved
```

UI selection label:

```text
patient_display_name || display_name
```

### Replay

Exact duplicate:

```text
409 report_already_exists
job_id present
GET job succeeds
GET report succeeds
```

Aramina opposite target side:

```text
left and right are distinct analyses
```

Different model:

```text
same source + different model_id are distinct analyses
```

---

## 17. Pre-demo acceptance gate

Before demo, rerun at minimum:

```text
1. Bremen Nova_376 happy execution + report
2. Aramina 0.2.12 Nova_257 left preflight + execution + report
3. Aramina 0.2.13 Nova_257 left preflight + execution + report
4. Aramina 0.2.12 Nova_384 left preflight + safe failed execution
5. Aramina 0.2.13 Nova_384 left preflight + safe failed execution
6. exact duplicate replay for Bremen
7. exact duplicate replay for Aramina
8. Aramina same source left vs right distinct-analysis check
9. same source different model_id distinct-analysis check
10. frontend patient label shows patient identity, not generic filename
11. completed trace is actually completed
12. failed trace shows the real failure stage
```

Demo gate:

```text
No known-good Aramina input may be blocked by preflight.
No completed job may appear as not_started.
No known patient may be presented as only a generic container filename when patient identity is available.
Alexey StandardResult must remain backward-compatible.
```
