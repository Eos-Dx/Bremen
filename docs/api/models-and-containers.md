# Models & Containers

## GET /demo/api/models

List available models in the Bremen catalog.

### Auth

None (public endpoint).

### Response — 200 OK

```json
{
  "schema_version": "1",
  "catalog_timestamp": "2025-08-05T12:00:00",
  "models": [
    {
      "model_id": "bremen-mri-triage-logreg-v0-1",
      "display_name": "Bremen MRI Triage LogReg v0.1",
      "workflow_id": "bremen",
      "model_version": "v0.1",
      "artifact_type": "logistic_regression",
      "feature_schema_version": "v0.1",
      "decision_policy_id": "threshold-v0.1",
      "decision_policy_version": "v0.1",
      "technical_ready": true,
      "scientifically_certified": false,
      "technical_demo_only": true,
      "availability": "available"
    }
  ],
  "default_model_id": "bremen-mri-triage-logreg-v0-1",
  "status": "ready",
  "candidate_count": 1,
  "available_count": 1,
  "technical_demo_only": true,
  "request_id": "<REQUEST_ID>"
}
```

> `scientifically_certified: false` for all current models.

When multiple models are available, the `model_id` field is **required** in
the create-job request. You can extract the default model from the catalog:

```bash
curl -sS -L "$BASE/demo/api/models" | jq .
```

## GET /demo/api/h5/containers

List H5 containers available for analysis.

### Auth

Bearer token required.

### Response — 200 OK

```json
{
  "storage": "configured",
  "containers": [
    {
      "source_id": "<SOURCE_ID>",
      "display_name": "Nova_378",
      "patient_display_name": "Nova_378",
      "stable_source_key": "<STABLE_KEY>",
      "size_bytes": 1048576,
      "last_modified": "2025-08-01T10:30:00Z",
      "workflow_id": "bremen"
    }
  ],
  "upload_max_bytes": 104857600,
  "technical_demo_only": true,
  "request_id": "<REQUEST_ID>"
}
```

### Example

```bash
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/demo/api/h5/containers" \
  | tee /tmp/bremen-containers.json | jq .

export SOURCE_ID="$(jq -r '.containers[0].source_id' /tmp/bremen-containers.json)"
export PATIENT_NAME="$(jq -r '.containers[0].patient_display_name // .containers[0].display_name' /tmp/bremen-containers.json)"
echo "SOURCE_ID=$SOURCE_ID  PATIENT=$PATIENT_NAME"
```

### POST /demo/api/h5/containers

Upload an H5 file. The upload endpoint exists; the exact request format is documented
in the source code (`_handle_h5_upload_bytes`). The upload is multipart/form-data with
an `X-H5-Filename` header.

> Detailed upload contract is finalized in source; refer to the FastAPI route
> definition for current field names and size limits.
