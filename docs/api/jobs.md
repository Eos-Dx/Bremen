# Jobs

## POST /demo/api/jobs

Create a new analysis job.

### Auth

Bearer token required.

### Request

- **Content-Type:** `application/json`

```json
{
  "workflow_id": "bremen",
  "source_id": "<SOURCE_ID>",
  "patient_display_name": "Nova_378",
  "model_id": "bremen-mri-triage-logreg-v0-1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow_id` | string | Yes | Workflow to run (typically `"bremen"`) |
| `source_id` | string | Yes* | Opaque container ID from `/demo/api/h5/containers` |
| `model_id` | string | Conditional | Required when multiple models are available |
| `patient_display_name` | string | No | Display name for the patient |

> \* Exactly one of `source_id`, `upload_id`, or `h5_path` must be provided.

### Response — 201 Created

```json
{
  "job": {
    "job_id": "<JOB_ID>",
    "request_id": "<REQUEST_ID>",
    "created_at": "2025-08-05T12:00:00Z",
    "started_at": "2025-08-05T12:00:01Z",
    "completed_at": "2025-08-05T12:00:15Z",
    "overall_status": "completed",
    "input_summary": { "..." : "..." },
    "workflow_runs": { "bremen": { "..." : "..." } },
    "reports": { "bremen": { "..." : "..." } }
  },
  "storage_mode": "ephemeral"
}
```

> **Important:** The `job_id` is nested at `.job.job_id`, not at top level.

### Example

```bash
export MODEL_ID="bremen-mri-triage-logreg-v0-1"

jq -n \
  --arg workflow_id "bremen" \
  --arg source_id "$SOURCE_ID" \
  --arg patient_display_name "$PATIENT_NAME" \
  --arg model_id "$MODEL_ID" \
  '{
    workflow_id: $workflow_id,
    source_id: $source_id,
    patient_display_name: $patient_display_name,
    model_id: $model_id
  }' \
  | tee /tmp/bremen-job-payload.json

curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/jobs" \
  -d @/tmp/bremen-job-payload.json \
  | tee /tmp/bremen-job-create.json | jq .

export JOB_ID="$(jq -r '.job.job_id // .job_id // .id // .jobId // empty' /tmp/bremen-job-create.json)"
echo "JOB_ID=$JOB_ID"
```

### Errors

| Status | Meaning |
|--------|---------|
| 401 | Authentication failed |
| 400 | Invalid JSON body, missing source, or `model_id` required when multiple models exist |
| 409 | Report already exists for this source and model (rerun guard) |
| 400 | `SOURCE_ERROR` — selected source has already been used |

---

## GET /demo/api/jobs

List recent analysis jobs.

### Auth

Bearer token required.

### Query Parameters

| Parameter | Description |
|-----------|-------------|
| `model_id` | Filter by model ID |
| `workflow_id` | Filter by workflow ID |

### Response — 200 OK

```json
{
  "jobs": [
    {
      "job_id": "<JOB_ID>",
      "created_at": "2025-08-05T12:00:00Z",
      "overall_status": "completed",
      "report_available": true,
      "model_id": "bremen-mri-triage-logreg-v0-1",
      "decision_code": "MRI_REVIEW_DEFER"
    }
  ],
  "storage_mode": "ephemeral",
  "retention_seconds": [REDACTED],
  "max_jobs": [REDACTED],
  "technical_demo_only": true,
  "request_id": "<REQUEST_ID>"
}
```

---

## GET /demo/api/jobs/{job_id}

Retrieve one job's status, execution traces, and report metadata.

### Auth

Bearer token required.

### Path Parameters

| Parameter | Description |
|-----------|-------------|
| `job_id` | UUID of the analysis job |

### Response — 200 OK

Returns the full job record including `overall_status`, `workflow_runs`,
`reports`, `execution_traces`, and `storage_mode`.

### Execution Trace Stages

Current Bremen workflow trace includes these stages:

- `artifact_verification`
- `artifact_loaded`
- `artifact_adapted`
- `model_validated`
- `input_prepared`
- `features_produced`
- `features_validated`
- `inference_completed`
- `output_validated`
- `decision_completed`
- `report_completed`

> These reflect the current Bremen workflow implementation and may evolve.

### Successful Result Summary Fields

When a job completes, `workflow_runs.bremen.result_summary` includes:

- `probability` — decision-support probability score
- `threshold_applied` — decision threshold
- `decision_code` — e.g. `CONTINUE_MRI` or `MRI_REVIEW_DEFER`
- `decision_display_name` — human-readable decision
- `decision_policy_id` / `decision_policy_version`
- `model_version`, `feature_schema_version`
- `triage_recommendation`
- `left_measurement_count`, `right_measurement_count`

### Errors

| Status | Meaning |
|--------|---------|
| 401 | Authentication failed |
| 404 | Job not found |
| 410 | Job has expired (known to event store but evicted from memory) |
