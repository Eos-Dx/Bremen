# Bremen Runtime API Contract

**Draft** — this is a draft API contract for the Bremen runtime service. This PR defines the async service shape only. No real inference, no H5/HDF5 reading, no preprocessing, no model deserialization, no `joblib.load()`, no training, no Matador integration, no AWS/S3/network integration. Bremen is not a diagnostic replacement and does not replace MRI, biopsy, radiologists, clinicians, or clinical judgment.

## Endpoints

### `GET /health`

**Purpose:** Service health check. No model inference. No H5 inspection. No model loading.

**Response:**

```json
{
  "status": "ok",
  "service": "bremen",
  "version": "<package_version or 'unknown'>",
  "timestamp": "<ISO-8601 UTC>"
}
```

### `GET /model/version`

**Purpose:** Expose configured model package metadata/status. Must not call `joblib.load()`. Must not deserialize model artifacts.

**Response (not configured):**

```json
{
  "model_configured": false,
  "model_version": null,
  "model_checksum": null,
  "feature_schema_version": null,
  "threshold_version": null,
  "threshold_value": null,
  "qc_criteria_version": null,
  "model_status": "not_configured",
  "model_uri_configured": false,
  "checksum_configured": false,
  "error_category": null
}
```

**Response (configured — env set, not yet loaded):**

```json
{
  "model_configured": true,
  "model_version": null,
  "model_checksum": null,
  "feature_schema_version": null,
  "threshold_version": null,
  "threshold_value": null,
  "qc_criteria_version": null,
  "model_status": "configured",
  "model_uri_configured": true,
  "checksum_configured": false,
  "error_category": null
}
```

**Response (ready — fully loaded and validated):**

```json
{
  "model_configured": true,
  "model_version": "<version>",
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

**Response (error — load/staging/checksum/validation failed):**

```json
{
  "model_configured": true,
  "model_version": "<version>",
  "model_checksum": "<sha256-hex>",
  "feature_schema_version": null,
  "threshold_version": null,
  "threshold_value": null,
  "qc_criteria_version": null,
  "model_status": "error",
  "model_uri_configured": true,
  "checksum_configured": true,
  "error_category": "<safe_category>"
}
```

`model_status` values: `not_configured`, `configured`, `ready`, `error`.

- `not_configured` — Required model configuration (env vars) is absent. Model is not available.
- `configured` — Required model configuration exists but model has not been fully loaded and validated yet (or loading has not been attempted).
- `ready` — Model artifact has been staged, checksum verified, loaded, and validated. Ready for inference.
- `error` — Model configuration exists but staging, checksum verification, loading, or validation failed. `error_category` provides a safe enum-style classification.

Safe fields:
- `model_uri_configured` (bool) — whether `BREMEN_MODEL_URI` was configured. No raw URI string is exposed.
- `checksum_configured` (bool) — whether `BREMEN_MODEL_CHECKSUM` was configured. No raw checksum string is exposed.
- `error_category` (str or null) — safe classification when `model_status` is `"error"`. Values: `model_uri_not_set`, `s3_staging_failure`, `local_file_not_found`, `checksum_mismatch`, `joblib_load_failure`, `package_validation_failure`. Not a raw exception message or stack trace.

### `POST /predictions`

**Purpose:** Submit an asynchronous prediction job. Request must use opaque platform references, not local machine paths. Must not read H5/HDF5, run preprocessing, run inference, train, call Matador, or call AWS/S3/network.

**Request:**

```json
{
  "target_scan_ref": "<opaque_platform_reference>",
  "control_scan_ref": "<opaque_platform_reference>",
  "request_id": "<optional_idempotency_key>"
}
```

Rules:
- `target_scan_ref` and `control_scan_ref` are required and must be explicit (the runtime contract distinguishes target from control).
- `request_id` is optional for idempotency.
- No local filesystem paths accepted as platform contract.
- Additional metadata fields are allowed only if non-clinical and non-diagnostic.

**Response (HTTP 202 semantics):**

```json
{
  "job_id": "<uuid>",
  "status": "accepted",
  "submitted_at": "<ISO-8601 UTC>",
  "links": {
    "poll": "/predictions/<job_id>"
  }
}
```

### `GET /predictions/{job_id}`

**Purpose:** Poll the status of an asynchronous prediction job.

**Response:**

```json
{
  "job_id": "<uuid>",
  "status": "<status_value>",
  "submitted_at": "<ISO-8601 UTC or null>",
  "updated_at": "<ISO-8601 UTC or null>",
  "result": null,
  "error": null
}
```

`status` values: `accepted`, `queued`, `running`, `completed`, `failed`, `not_found`.

When `status` is `completed`, the `result` field must include:

```json
{
  "prediction_id": "<uuid>",
  "model_version": "<string>",
  "model_checksum": "<string>",
  "feature_schema_version": "<string>",
  "threshold_version": "<string>",
  "threshold_value": <number>,
  "qc_status": "<string>",
  "qc_flags": "<list or dict>"
}
```

Rules:
- Stub must not fabricate completed clinical predictions.
- No clinical diagnosis wording, no replacement of MRI/biopsy/radiologist/clinician judgment.
- `not_found` status for unknown/synthetic `job_id`.

## System-of-Record Boundary (PR0052)

Bremen currently supports two request input modes for H5 containers:

| Mode | Request field | Description | Status |
|---|---|---|---|
| Direct path | `h5_path` | Local filesystem path | Dev/test convenience mode |
| S3 staging | `h5_uri` | S3 URI with optional checksum | Staging/smoke mode |

Both modes remain fully supported and unchanged in PR0052. They are
**convenience/staging modes**, not long-term source-of-record ownership.

The future source of record for patient/scan/H5 resolution is Matador.

### Boundary scaffold (PR0052)

PR0052 introduces a typed boundary skeleton in
`src/bremen/system_of_record.py`:

- `ExternalRecordRef` — opaque system-of-record reference with
  validation (rejects empty refs, local paths, S3 URIs, raw patient
  identifiers).
- `ResolvedInput` — resolved H5 source with exactly one of `h5_uri`
  or `h5_path`, plus target/control refs and optional checksum.
- `RecordResolver` — protocol for future resolver implementations.
- `UnconfiguredRecordResolver` — default resolver that raises a safe
  `ResolutionNotConfiguredError`.

### What PR0052 does NOT add

- No public `source_record_ref` request field in `POST /predictions`.
- No real Matador API calls, credentials, or network adapters.
- No change to existing `h5_path`/`h5_uri` behavior.
- No new dependencies.

### Safety rules

- Raw external refs must not appear in public API error messages.
- Resolution errors must be subclasses of `ResolutionError` (safe by
  default).
- The `UnconfiguredRecordResolver` returns a safe message telling
  operators to use `h5_path`/`h5_uri` or configure Matador.

For the product input pipeline contract defining the canonical Bremen
input package, see
[docs/product_input_pipeline_contract.md](product_input_pipeline_contract.md).

## Decision-Support Report (PR0053)

When a prediction job completes, the `result` dict includes a
`decision_support_report` field with the following structure.

### report_schema_version

`"v0.1"` — stable version string for the decision-support report
contract.

### intended_use

String stating "MRI continuation decision support only." States that
the output is not a diagnosis, not clinically validated, and does not
replace MRI, biopsy, radiologist, clinician, or clinical judgment.

### limitations

List of predefined safety limitation strings. Captures that this is
decision-support output only, not a diagnostic result, not clinically
validated, and does not replace MRI, biopsy, radiologist, clinician,
or clinical judgment.

### model_metadata

Safe model identification fields:

- `model_version` (str)
- `feature_schema_version` (str)
- `threshold_version` (str) — when available
- `threshold_value` (float) — when available

Does NOT include raw `model_checksum` or model URI.

### input_summary

Safe input context fields:

- `input_mode` (str): `"h5_uri"`, `"h5_path"`, or `"unknown"`
- `explicit_refs_provided` (bool or null)
- `layout_category` (str or null): `"canonical"`,
  `"calibration_sample"`, or `"unknown"`

Does NOT include raw H5 path, full S3 URI, or raw target/control refs.

### prediction_summary

Model output fields:

- `p_mri_needed` (float): Probability estimate in [0.0, 1.0]
- `triage_recommendation` (str): `"MRI_RECOMMENDED"` or
  `"MRI_RULE_OUT"`
- `qc_status` (str): `"passed"` or `"failed"`
- `qc_flags` (list)

### decision_support

Safe recommendation framing:

- `recommendation` (str): Same value as `triage_recommendation`
- `recommendation_label` (str): Human-readable cautionary label
  using "may be recommended" / "may not be indicated" language
- `caution` (str): Standard decision-support disclaimer stating
  the final decision must be made by a qualified clinician

### Safety rules

- No raw patient identifiers in report fields.
- No raw checksum, full S3 URI, or model artifact path.
- No raw feature values or feature vectors.
- No clinical diagnosis or definitive claims.
- `recommendation_label` uses only "may be recommended" / "may not
  be indicated" language.
- No replacement of MRI, biopsy, radiologist, clinician, or clinical
  judgment.
- No clinical validation claim.
- All eight mandatory result fields (`prediction_id`, `model_version`,
  `model_checksum`, `feature_schema_version`, `threshold_version`,
  `threshold_value`, `qc_status`, `qc_flags`) remain at the top level
  of the result dict for backward compatibility.

For the full release readiness operator notes, see
[docs/release_readiness_operator_notes.md](release_readiness_operator_notes.md).
