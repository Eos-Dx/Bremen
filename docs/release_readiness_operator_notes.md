# Bremen Release Readiness Operator Notes

**PR0054** — Release readiness / operator notes.

---

## 1. Purpose

This document is the release readiness checklist for a Bremen deployment.
Bremen provides clinical decision-support for the question of whether a
patient should continue to MRI. Bremen is not a diagnostic system. Bremen
does not diagnose disease, is not clinically validated, and does not
replace MRI, biopsy, radiologist, clinician, or clinical judgment.

This checklist helps a human operator verify that a Bremen deployment is
configured, healthy, operational, and safe before accepting predictions.

---

## 2. Scope

**Covered**: runtime service lifecycle, model readiness, prediction API,
decision-support report, logging expectations, failure triage, rollback
procedure, security boundaries, and clinical-safety boundaries.

**Not covered**: clinical validation, training pipeline, config editing
surface or UI, config state history store, DynamoDB backend, Matador
system-of-record integration, FastAPI migration, AWS account or IAM setup,
real patient data handling.

---

## 3. Current Release Capability

The current release can:

- Accept H5 containers via filesystem path (`h5_path`) or staged S3 URI
  (`h5_uri`).
- Validate H5 container structure and metadata through preflight checks.
- Resolve explicit `target_scan_ref` / `control_scan_ref` through H5
  layout adapters.
- Support both canonical (`/scans/target/` + `/scans/contralateral/`)
  and calibration-sample H5 layouts.
- Extract a 15-feature v0.1 vector via the preprocessing bridge.
- Run portable logistic regression inference (deterministic, no sklearn
  dependency).
- Apply threshold-based triage: `CONTINUE_MRI` / `MRI_REVIEW_DEFER`.
  (Legacy aliases `MRI_RECOMMENDED` and `MRI_RULE_OUT` are accepted
  as compatibility inputs only and are never emitted as new canonical
  output.)
- Return a completed prediction result with a structured decision-support
  report.
- All computation is deterministic and reproducible (same inputs produce
  identical outputs).

**Limitations**:

- Decision-support only — not a diagnosis, not clinically validated.
- Does not replace MRI, biopsy, radiologist, clinician, or clinical
  judgment.
- Current input modes (`h5_path`, `h5_uri`) are controlled
  staging/development modes — not long-term source-of-record ownership.
- The system-of-record boundary exists (PR0052 scaffold) but real
  Matador integration is not implemented.
- No hot-swap of model at runtime. New model version requires redeploy.

---

## 4. Required Runtime Configuration

The service requires the following environment variables. Do not
include real values, full S3 URIs, account IDs, secrets, or local
machine absolute paths in deployed configuration.

| Variable | Required | Description |
|---|---|---|
| `BREMEN_MODEL_VERSION` | Yes | Model version identifier (e.g., `bremen_mri_triage_logreg_v0_1`) |
| `BREMEN_MODEL_URI` | Yes | Model artifact URI — S3 path (`s3://${BUCKET_NAME}/${PREFIX}/model.joblib`) or local filesystem path |
| `BREMEN_MODEL_CHECKSUM` | Yes | SHA-256 hex digest of the model artifact. Accepted bare (`<64-hex-chars>`) or with prefix (`sha256:<64-hex-chars>`) |
| `BREMEN_MODEL_STAGING_DIR` | No | Override the local staging directory for model fetch (default: system temp directory) |

**Prohibitions**:

- Do not set `BREMEN_MODEL_URI` to a raw local developer machine path in
  production.
- Do not embed account IDs, registry URLs, access keys, or secrets in
  version-controlled configuration.
- Do not bypass checksum verification — `BREMEN_MODEL_CHECKSUM` is
  required.

---

## 5. Startup Readiness Checklist

1. Verify `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_URI`, and
   `BREMEN_MODEL_CHECKSUM` are set to the correct values for this
   release.
2. Start the service.
3. Check startup logs for `bremen.model.ready` with `model_ready=true`.
4. If startup logs show `bremen.model.not_ready`, check the `reason=`
   field. Common reasons: `model_uri_not_set`, `s3_staging_failure`,
   `checksum_mismatch`, `joblib_load_failure`,
   `package_validation_failure`.
5. Confirm no model artifact is embedded in the container image. The
   model is fetched at startup from S3 or local staging.
6. Confirm checksum verification occurs before `joblib.load()`.
   Failed verification produces `bremen.model.checksum.verify.failure`
   and `model_ready=false`. The deserialization boundary is controlled
   — no model is loaded without passing checksum verification.

---

## 6. Health and Model Version Checks

### GET /health

```bash
curl -s ${BASE_URL}/health
```

Expected response (200 OK):

```json
{
    "status": "ok",
    "service": "bremen",
    "model_ready": true,
    "version": "<version>",
    "timestamp": "<ISO-8601 UTC>"
}
```

`model_ready` must be `true` before submitting predictions. If
`model_ready` is `false`, check model configuration and startup logs.

### GET /model/version

```bash
curl -s ${BASE_URL}/model/version
```

Expected `model_status` values:

| model_status | Meaning | Action |
|---|---|---|
| `ready` | Model loaded, checksum verified, ready for inference. | Proceed with predictions. |
| `not_configured` | Required env vars are absent. | Set `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_URI`, `BREMEN_MODEL_CHECKSUM`. |
| `configured` | Env vars set but model not yet loaded. | Wait for startup to complete, or redeploy if stuck. |
| `error` | Loading failed. See `error_category`. | Check `error_category` and startup logs. Redeploy with corrected config. |

Safe fields exposed:

- `model_uri_configured` (bool) — whether `BREMEN_MODEL_URI` was set.
  The raw URI string is **not** exposed.
- `checksum_configured` (bool) — whether `BREMEN_MODEL_CHECKSUM` was
  set. The raw checksum hex is **not** exposed through this endpoint.
- `error_category` (str or null) — safe enum-style classification when
  `model_status` is `error`. Not a raw exception message or stack trace.
  Values: `model_uri_not_set`, `s3_staging_failure`,
  `local_file_not_found`, `checksum_mismatch`, `joblib_load_failure`,
  `package_validation_failure`.

---

## 7. Prediction Smoke Checklist

Reference `docs/production_e2e_smoke.md` for the full procedure.
Summary:

1. Submit a prediction via `POST /predictions` with `h5_uri` and
   explicit `target_scan_ref` / `control_scan_ref`.
2. Expect HTTP 202 with a `job_id` and a poll link.
3. Poll `GET /predictions/{job_id}` until `status: "completed"`.
4. Verify `result` contains all 8 mandatory fields.
5. Verify `result["decision_support_report"]` is present and contains
   `report_schema_version: "v0.1"`.

---

## 8. Expected Successful Response Shape

`GET /predictions/{job_id}` when `status: "completed"` (placeholders):

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
        "qc_flags": [],
        "decision_support_report": {
            "report_schema_version": "v0.1",
            "intended_use": "MRI continuation decision support only...",
            "limitations": ["...", "..."],
            "model_metadata": {
                "model_version": "<version>",
                "feature_schema_version": "v0.1"
            },
            "input_summary": {
                "input_mode": "h5_uri",
                "explicit_refs_provided": true,
                "layout_category": "calibration_sample"
            },
            "prediction_summary": {
                "p_mri_needed": 0.75,
                "triage_recommendation": "CONTINUE_MRI",
                "decision_code": "CONTINUE_MRI",
                "decision_display_name": "Continue MRI evaluation",
                "decision_policy_id": "bremen_mri_continuation_threshold",
                "decision_policy_version": "0.1.0",
                "qc_status": "passed",
                "qc_flags": []
            },
            "decision_support": {
                "recommendation": "CONTINUE_MRI",
                "recommendation_label": "Based on the model output...",
                "caution": "This is a decision-support recommendation only..."
            }
        }
    },
    "error": null
}
```

---

## 9. Decision-Support Report Expectations

The `decision_support_report` is added to every completed prediction
result (PR0053). Key expectations:

- `report_schema_version`: Always `"v0.1"`.
- `intended_use`: States "MRI continuation decision support only."
  Explicitly states not a diagnosis, not clinically validated, does not
  replace MRI, biopsy, radiologist, clinician, or clinical judgment.
- `limitations`: Predefined safety limitation list including "Not a
  diagnostic result", "Not clinically validated", and "Does not replace
  MRI, biopsy, radiologist, clinician, or clinical judgment".
- `model_metadata`: Contains safe identification fields only
  (`model_version`, `feature_schema_version`). Does NOT contain raw
  `model_checksum` or model URI.
- `input_summary`: Contains `input_mode` (category string),
  `explicit_refs_provided` (bool or null), `layout_category` (string
  or null). Does NOT contain raw H5 path, full S3 URI, or raw
  target/control refs.
- `prediction_summary`: Contains `p_mri_needed` (float),
  `triage_recommendation` (deprecated compatibility field carrying the
  canonical decision code), `decision_code` (canonical machine-readable
  field — CONTINUE_MRI or MRI_REVIEW_DEFER), `decision_display_name`,
  `decision_policy_id`, `decision_policy_version`, `qc_status`,
  `qc_flags`. Does NOT contain raw feature values or feature vectors.
- `decision_support`: Contains `recommendation` (canonical decision_code
  value), `recommendation_label` (using "may be recommended" / "may not
  be indicated" language), and `caution`. Does NOT contain diagnosis,
  cancer, benign, or malignant labels.
- No raw patient identifiers, raw checksums, full S3 URIs, raw feature
  values, or diagnosis claims are present in any section of the report.

---

## 10. Safe Failure Modes and Triage

| Failure mode | Observable | Triage |
|---|---|---|
| Model not configured | `/health` `model_ready: false`, `/model/version` `model_status: "not_configured"` | Set `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_URI`, `BREMEN_MODEL_CHECKSUM` and redeploy |
| S3 model staging failure | Logs: `bremen.model.artifact.stage.failure`, `/model/version` `model_status: "error"`, `error_category: "s3_staging_failure"` | Check S3 bucket, key, IAM permissions, network connectivity |
| Checksum mismatch (model) | Logs: `bremen.model.checksum.verify.failure`, `model_ready=false`, `error_category: "checksum_mismatch"` | Verify `BREMEN_MODEL_CHECKSUM` matches the published manifest for this model version. Do not bypass checksum validation. |
| Model load/validation failure | Logs: `bremen.model.not_ready`, `error_category: "joblib_load_failure"` or `"package_validation_failure"` | Verify model artifact is a valid joblib file and matches the portable logreg v0.1 schema |
| Checksum mismatch (H5 input) | Job status: `failed`, error mentions SHA-256 mismatch | Verify the H5 file checksum before submission. Re-upload if corrupted. |
| H5 staging failure | Job status: `failed`, error mentions "S3 download failed" | Check S3 bucket, key, IAM permissions for the H5 input path |
| H5 preflight failure | Job status: `failed`, error mentions preflight status | Verify H5 layout compatibility, required metadata paths, and scan refs |
| Explicit ref validation failure | Job status: `failed`, error mentions target/control refs not found | Verify `target_scan_ref` and `control_scan_ref` exist in the H5 container. For calibration layouts, verify the exact group paths. |
| Preprocessing failure | Job status: `failed`, error mentions preprocessing or feature extraction | Check H5 data integrity — missing integration arrays, incompatible dimensions, or non-finite values |
| Inference failure | Job status: `failed`, error mentions inference | Check model compatibility with feature schema. Verify the feature vector has 15 finite values. |

---

## 11. Logging and Leakage Expectations

### What logs contain

- `bremen.*` structured events with safe metadata: URI scheme,
  model version, file basename, checksum presence (boolean), feature
  count, job ID, prediction ID.
- `model_ready=true/false` with safe `reason=` category at startup.
- `job_id` references for tracing specific prediction requests.
- `size_bytes` for staged artifacts.
- `feature_count` for preprocessing results.

### What logs must NOT contain

- Raw patient identifiers (patient names, patient IDs).
- Raw H5 filesystem paths (full path; only basename is safe).
- Full S3 URIs (`s3://bucket/key`).
- Raw target/control scan refs.
- Raw feature values or feature vectors.
- Raw model checksum hex strings.
- AWS credentials, access keys, account IDs, or registry URLs.
- Raw scan arrays or measurement data.

### Audit trail

Every prediction produces a `prediction_id`. The `prediction_id` links
the request, inference result, and decision-support report. No raw
patient data is associated with the `prediction_id` in logs.

---

## 12. Rollback and Recovery Checklist

1. **Verify current image/revision.** Identify the currently deployed
   container image tag or revision before taking action.
2. **Verify env var names are present.** Confirm `BREMEN_MODEL_VERSION`,
   `BREMEN_MODEL_URI`, and `BREMEN_MODEL_CHECKSUM` are set correctly.
3. **Verify model readiness.** Check `/health` for `model_ready` and
   `/model/version` for `model_status`.
4. **Inspect safe error category.** If model status is `error`, read
   `error_category` and check startup logs for the `reason=` field.
5. **Redeploy previous known-good revision if needed.** Revert the
   `BREMEN_MODEL_VERSION` to a known-good value and redeploy. Use the
   previous working container image tag.
6. **Do not bypass checksum validation.** Never skip checksum
   verification as a recovery step. If a checksum mismatch occurs,
   verify the artifact against its published manifest.
7. **Do not use unverified model artifacts.** Never load model artifacts
   from unverified or untrusted sources. Always verify the SHA-256
   checksum before deserialization.

---

## 13. Security and Artifact Boundaries

- **No model artifact in container image.** The model is fetched at
  startup from S3 or local staging — it is never embedded in the
  runtime container image.
- **Checksum-before-deserialization.** SHA-256 checksum verification
  occurs before `joblib.load()`. Failed verification produces a safe
  error and `model_ready=false`. No model is loaded without passing
  verification.
- **H5 input checksum verification is optional but recommended.** The
  `h5_checksum` field in the prediction request enables verification
  of the H5 file before preprocessing.
- **`h5_path` mode is for development and CI only.** It is not suitable
  for production source-of-record integration. It exposes local
  filesystem paths and bypasses platform data ownership.
- **`h5_uri` mode is for controlled staging.** It does not imply
  Matador/system-of-record ownership. It is a convenience staging mode
  that downloads an H5 file from S3 for processing.
- **The system-of-record boundary exists (PR0052).** The
  `system_of_record.py` module defines the typed boundary for future
  Matador integration. Real Matador API calls, credentials, and network
  adapters are **not yet implemented**.
- **No hot-swap of model at runtime.** The model is loaded exactly once
  at startup. New model version requires redeployment.
- **No config editing surface.** Configuration is set at deployment time
  via environment variables. There is no runtime config UI or API.

---

## 14. Clinical-Safety Boundaries

- Bremen does **not** diagnose disease.
- Bremen is **not** clinically validated.
- Bremen does **not** replace MRI, biopsy, radiologist, clinician, or
  clinical judgment.
- All clinical decisions must be made by qualified clinicians based on
  full patient history, diagnostic workup, MRI, and biopsy.
- The decision-support report explicitly states these limitations in its
  `intended_use` and `limitations` fields.
- The term "triage" in `triage_recommendation` is a deprecated compatibility
  field referring to decision-support categorisation only — it is not
  clinical triage.  New consumers must use `decision_code` instead.
- The `recommendation_label` uses only "may be recommended" / "may not
  be indicated" language. It never claims clinical necessity or certainty.

---

## 15. Investor Control Room (PR0082)

The default GET /demo route renders the Bremen Investor Control Room.
GET /demo/workspace remains available for the legacy workspace.

The Control Room operator flow:

1. Open GET /demo in a browser.
2. Verify model readiness: header badges show "Model Ready" (green)
   or "Model Not Configured" (yellow).  Scientific certification is
   always "pending" (red).
3. Select an H5 file using the "Select H5 File" button.  The file is
   uploaded to POST /demo/api/stage and staged to a temporary location.
4. When the source status shows "Ready", click Analyze.  The button is
   disabled until both the model is ready and a source is selected.
5. Observe the ten-stage execution pipeline update in real time as
   authoritative events arrive.
6. Observe the docked structured event panel (right side) receiving
   live SSE events.
7. When the job completes, the decision panel displays the canonical
   CONTINUE_MRI or MRI_REVIEW_DEFER result.
8. Click "View Bremen Report" to access the real generated report.

Operator guidance for common states:

Model Not Configured: The Analyze button is disabled.  The operator
must configure BREMEN_MODEL_URI, BREMEN_MODEL_VERSION, and
BREMEN_MODEL_CHECKSUM and redeploy.  No environment-variable values,
URIs, paths, or credentials are displayed in the UI.

Source Upload Failed: Check that the H5 file is valid and under the
file size limit.  Retry the upload.

Analysis Failed: The pipeline shows the failed stage.  The event
panel shows the failure event.  Check server logs for safe error
categories.

Legacy Analyze Jobs: Jobs created through POST /demo/api/h5/analyze
use a separate workflow and are not imported into the structured
Control Room job list.  The Control Room footer documents this
limitation.

---

## 16. Non-Goals

This release does not include:

- FastAPI, uvicorn, starlette, or any ASGI web framework.
- Real Matador system-of-record integration or Matador API calls.
- Config editing surface, config UI, or config API.
- Config state history store or DynamoDB backend.
- Diagnosis or clinical validation claims.
- Replacement of MRI, biopsy, radiologist, clinician, or clinical
  judgment.
- Hot-swap model loading at runtime.

---

## 17. Release Readiness Sign-Off Checklist

Before marking a Bremen deployment release as ready, complete the
following checks:

- [ ] `BREMEN_MODEL_VERSION` configured with the correct model version.
- [ ] `BREMEN_MODEL_URI` configured (S3 URI or local path with
      placeholder-style path — no raw machine paths in production).
- [ ] `BREMEN_MODEL_CHECKSUM` configured (SHA-256 hex matching the
      published manifest).
- [ ] `GET /health` returns `{"status": "ok", "model_ready": true}`.
- [ ] `GET /model/version` returns `model_status: "ready"` with safe
      metadata only (no raw URI or checksum exposure).
- [ ] `POST /predictions` with a controlled H5 input returns HTTP 202
      with a valid `job_id`.
- [ ] `GET /predictions/{job_id}` polls to `status: "completed"` with
      non-null `result` containing all 8 mandatory fields and a
      `decision_support_report` with `report_schema_version: "v0.1"`.
- [ ] Startup logs show `bremen.model.ready` with `model_ready=true`.
- [ ] Logs do **not** contain raw patient identifiers, full S3 URIs,
      raw target/control refs, raw feature values, raw model checksums,
      AWS credentials, access keys, account IDs, or registry URLs.
- [ ] Rollback plan documented: operators know how to revert
      `BREMEN_MODEL_VERSION` and redeploy the previous working image.
- [ ] Clinical-safety disclaimer reviewed and acknowledged: Bremen does
      not diagnose, is not clinically validated, does not replace MRI,
      biopsy, radiologist, clinician, or clinical judgment.
