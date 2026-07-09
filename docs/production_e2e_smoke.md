# Production End-to-End Smoke

**Operator Runbook**

## Goal

Validate that the Bremen decision-support request path works end-to-end:
from `h5_uri` input through S3 staging simulation, explicit H5 refs,
calibration layout, preprocessing, model inference, and completed job
result — **without requiring external systems by default**.

**This smoke validates decision-support plumbing, not clinical performance
or clinical validation.** A passing smoke does not mean the model is
clinically valid or safe for patient-facing use.

---

## Prerequisites

- Python 3.13+ with Bremen dependencies installed.
- Synthetic test H5 file (or compatible real patient H5 for opt-in smoke).
- Baselined model package (default smoke uses a synthetic model).

---

## Environment variables

Use placeholder values only — never real account IDs, registry URLs, full
S3 URIs, patient names, sample refs, access keys, or secrets.

| Variable | Example (placeholder) | Description |
|---|---|---|
| `BREMEN_E2E_SMOKE_URL` | `http://127.0.0.1:8000` | Base URL of the Bremen instance under test |
| `BREMEN_E2E_S3_H5_URI` | `s3://${BUCKET_NAME}/${H5_KEY}` | S3 URI of the H5 input file |
| `BREMEN_E2E_S3_H5_CHECKSUM` | `sha256:<64-hex-chars>` | SHA-256 checksum of the H5 file |
| `BREMEN_E2E_TARGET_SCAN_REF` | `${TARGET_SAMPLE_REF}` | Explicit target scan reference |
| `BREMEN_E2E_CONTROL_SCAN_REF` | `${CONTROL_SAMPLE_REF}` | Explicit control scan reference |

---

## Health check

```bash
curl -s ${BREMEN_E2E_SMOKE_URL}/health | python -m json.tool
```

Expected response (200 OK):
```json
{
    "status": "ok",
    "service": "bremen",
    "model_ready": true,
    "timestamp": "<ISO-8601 UTC>"
}
```

The `model_ready` field **must** be `true` before submitting a prediction.

---

## Model version check

```bash
curl -s ${BREMEN_E2E_SMOKE_URL}/model/version | python -m json.tool
```

Expected response (200 OK):
```json
{
    "model_configured": true,
    "model_version": "<version-string>",
    "model_checksum": "<sha256-hex>",
    "feature_schema_version": "v0.1",
    "threshold_version": "<version>",
    "threshold_value": 0.5,
    "qc_criteria_version": null,
    "model_status": "ready",
    "model_uri_configured": true,
    "checksum_configured": true,
    "error_category": null
}
```

---

## Submit prediction

Redacted request shape — substitute placeholder values only.

```bash
curl -s -X POST ${BREMEN_E2E_SMOKE_URL}/predictions \
    -H "Content-Type: application/json" \
    -d '{
        "h5_uri": "${BREMEN_E2E_S3_H5_URI}",
        "h5_checksum": "${BREMEN_E2E_S3_H5_CHECKSUM}",
        "target_scan_ref": "${BREMEN_E2E_TARGET_SCAN_REF}",
        "control_scan_ref": "${BREMEN_E2E_CONTROL_SCAN_REF}"
    }' | python -m json.tool
```

Expected response (202 Accepted):
```json
{
    "job_id": "<uuid>",
    "status": "accepted",
    "submitted_at": "<ISO-8601 UTC>",
    "links": {
        "poll": "/predictions/<uuid>"
    }
}
```

---

## Poll for result

```bash
curl -s ${BREMEN_E2E_SMOKE_URL}/predictions/${JOB_ID} | python -m json.tool
```

Replace `${JOB_ID}` with the `job_id` from the submit response.

Expected completed response:
```json
{
    "job_id": "<uuid>",
    "status": "completed",
    "submitted_at": "<ISO-8601 UTC>",
    "updated_at": "<ISO-8601 UTC>",
    "result": {
        "prediction_id": "<uuid>",
        "model_version": "<version>",
        "model_checksum": "<sha256-hex>",
        "feature_schema_version": "v0.1",
        "threshold_version": "<version>",
        "threshold_value": 0.5,
        "qc_status": "passed",
        "qc_flags": []
    },
    "error": null
}
```

---

## Success criteria

1. **`model_ready` is `true`** in the `/health` response.
2. **HTTP 202 accepted** returned from `POST /predictions` with a valid
   `job_id` and poll link.
3. **Polling returns `"status": "completed"`** within a reasonable timeout.
4. **`result` is non-null** and contains all mandatory fields:
   `prediction_id`, `model_version`, `model_checksum`,
   `feature_schema_version`, `threshold_version`, `threshold_value`,
   `qc_status`, `qc_flags`.
5. **`error` is null** on the completed job.
6. **No raw patient identifiers, raw sample refs, full S3 URIs, raw feature
   values, or raw scan arrays** appear in application logs.

---

## Safe failure criteria

The following conditions must produce a safe error (failed job or HTTP 4xx/5xx)
without leaking sensitive information:

| Condition | Expected outcome |
|---|---|
| Model not loaded (`model_ready: false`) | HTTP 503 with safe error message |
| S3 staging failure (network, permissions) | HTTP 400 or failed job with safe error; no full S3 URI or credentials in logs |
| Checksum mismatch (`h5_checksum` does not match) | HTTP 400 or failed job with safe error |
| Invalid H5 refs (target/control paths not found) | Failed job with safe error message |
| Missing H5 metadata (required groups/fields absent) | Failed job with safe error message |
| Preprocessing failure (feature extraction fails) | Failed job with safe error message |
| Inference failure (model error, invalid features) | Failed job with safe error message |
| Timeout (job takes too long) | Timeout handled gracefully; no hang |

---

## Safety and privacy

1. **No raw patient identifiers** in logs, error messages, or HTTP responses.
2. **No raw `target_scan_ref` or `control_scan_ref`** values in logs.
3. **No full S3 URI** in logs — the bucket and key are not concatenated.
4. **No raw feature values** or feature vectors in logs.
5. **No raw scan arrays** or measurement data in logs.
6. **No secrets, account IDs, registry URLs, or access keys** in any output.

---

## Rollback and recovery notes

- If smoke fails on a new model version, revert the model package and
  restart the service.
- If smoke fails on a config change, revert `BREMEN_MODEL_VERSION`,
  `BREMEN_MODEL_CHECKSUM`, or H5-related environment variables.
- If smoke fails on infrastructure (network, permissions), check App Runner
  service logs and IAM roles.
- If smoke fails with leaked raw patient data in logs, **stop immediately**
  and escalate to the security contact.
- Smoke tests do not modify patient data or model artifacts.

---

## Manual smoke execution

**Actual production smoke is manual and opt-in.** The default automated
tests (see `tests/test_bremen_production_smoke.py`) do **not** call AWS,
App Runner, Docker, Terraform, network, or real S3. They use:

- Synthetic H5 files generated at test time.
- Monkeypatched S3 staging that returns local synthetic H5 paths.
- A synthetic in-process model (not a real training artifact).
- An in-process HTTP server on a random local port.

To run a real production smoke against a deployed instance, set the
`BREMEN_E2E_SMOKE_URL` environment variable and use the opt-in
`test_production_smoke_real_deployment` test (skipped by default).

---

## Decision-support disclaimer

This smoke validates request/response plumbing only. It does **not**
validate:

- Clinical performance (sensitivity, specificity, AUC).
- Model calibration or decision boundary correctness.
- Safety for autonomous clinical decision-making.
- Suitability for any specific patient population or imaging protocol.

All clinical decisions must be made by qualified clinicians based on
full MRI, biopsy, and patient history review.
