# PR0161A — Real Standard Result / Report Evidence

## Bremen Standard Result — Nova_227

Observed production result:

```json
{
  "report_id": "934372e6-3a30-43ba-bbc7-d894c9c7ca7d",
  "created_at": "2026-09-17T11:05:05+00:00",
  "analysis_author": "",
  "prediction_comment": "",
  "patient_id": "Nova_227",
  "patient_age": 44,
  "scan_date_time": "2025-05-28T10:19:55",
  "operator_id": "backfill",
  "hardware_version": "v1.0.1",
  "eoscan_version": null,
  "model_name": "bremen_paper_reference_symmetry_logreg",
  "model_version": "0.2.0-paper-reference",
  "model_method": "median_imputer_standard_scaler_balanced_logistic_regression",
  "model_metrics": {
    "sensitivity": 0.9516129032258065,
    "specificity": 0.391304347826087
  },
  "threshold_value": 0.3585907282566089,
  "risk_probability": 0.7726940329943809,
  "target_class_risk_level": "high",
  "specific_output": {}
}
```

The same Bremen job detail exposed source metadata with:

```json
{
  "patient_age": 44,
  "scan_date_time": "2025-05-28 10:19:55",
  "operator_id": "backfill",
  "hardware_version": "v1.0.1",
  "eoscan_version": null
}
```

This proves the current mapper/path changes the date separator while still leaving timezone unspecified.

## Aramina Standard Result — Nova_214 left

Observed production result:

```json
{
  "report_id": "e063951d-119f-4cb6-8921-c4b8af2c88a2",
  "created_at": "2026-09-17T11:18:49+00:00",
  "analysis_author": "Bremen batch compatibility smoke",
  "prediction_comment": "",
  "patient_id": "Nova_214",
  "patient_age": 47,
  "scan_date_time": "2025-05-14T12:55:46+00:00",
  "operator_id": "backfill",
  "hardware_version": "v1.0.0",
  "eoscan_version": null,
  "model_name": "aramina_target_breast_risk",
  "model_version": "0.2.13-beta",
  "model_method": "m2q_gated_target_case",
  "model_metrics": {
    "sensitivity": 0.8175,
    "specificity": 0.37630084054979734
  },
  "threshold_value": 0.24665932038818544,
  "risk_probability": 0.869387073973647,
  "target_class_risk_level": "high",
  "specific_output": {
    "target_side": "left",
    "mammography_suspicious_field": ""
  }
}
```

`analysis_author` above was supplied by the batch `POST /api/jobs` request.

## Report shape audit

Observed live batch shape counts:

### Successful workflow reports

Bremen:

```text
report_scalars = 63
report_nulls = 1
standard_result = present
payload = present
```

Aramina:

```text
report_scalars = 38
report_nulls = 1
standard_result = present
payload = present
```

### Failed workflow reports

Observed for both workflows:

```text
report_scalars = 6
standard_result = absent
payload = absent
report.status = unavailable
report.reason_code = REPORT_NOT_AVAILABLE
```

The corresponding job detail contains richer safe failure diagnostics.

This is the evidence for TD-0161-02.

## Contract v1 timestamp requirement

The existing Standard Model Result Contract v1 requires:

```text
RFC3339-compatible timestamp
with timezone information
without fractional seconds
```

It also states that the mapper may normalize representation but must not invent missing acquisition times or change timestamp meaning.

The current Bremen production `scan_date_time` does not satisfy the timezone portion of that documented contract.
