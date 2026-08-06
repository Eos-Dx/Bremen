# Errors & Troubleshooting

## Common HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 201 | Resource created (job, ticket) |
| 400 | Bad request — invalid JSON, missing fields, or invalid parameters |
| 401 | Authentication failed — wrong credentials, expired token, or no token |
| 404 | Resource not found — unknown job_id or missing route |
| 409 | Conflict — report already exists for this source and model |
| 410 | Gone — job has expired from in-memory store |
| 500 | Internal server error — no trace details exposed to client |
| 503 | Service unavailable — auth not configured or server error |

## Troubleshooting

### 1. 301 redirect to `:443`

**Symptom:** Response includes `location: https://bremen.matur.co.uk:443/...`

**Fix:** Use the base URL with port explicitly:

```bash
export BASE="https://bremen.matur.co.uk:443"
```

### 2. 401 Authentication failed

**Meaning:** The endpoint is reachable but credentials or token are wrong/expired.

**Fix:** Log in again and refresh your access token:

```bash
curl -sS -L \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/auth/token" \
  -d '{"username":"<USERNAME>","password":"<PASSWORD>"}' \
  | jq .
```

### 3. `/openapi.json` returns 404

**Meaning:** Production does not currently expose OpenAPI JSON at `/openapi.json`.

**Fix:** Use this Swagger-style static documentation (this file) instead.

### 4. `POST /predictions` returns 404

**Meaning:** `/predictions` is **not** the current production submit route.

**Fix:** Use `POST /demo/api/jobs` as documented in [jobs.md](jobs.md).

### 5. `model_id` required

**Symptom:** `"Multiple available models — model_id is required."`

**Fix:** Include `model_id` in the create-job payload. Extract it from the models catalog:

```bash
export MODEL_ID="$(jq -r '.models[0].model_id' /tmp/bremen-models.json)"
```

### 6. `SOURCE_ERROR` — selected source already used

**Symptom:** `"The selected source has already been used. Please select another container."`

**Fix:** Choose a different container from `/demo/api/h5/containers`.

### 7. `job_id` is empty after create-job

**Symptom:** `JOB_ID` is empty after creating a job.

**Common cause:** The `job_id` is nested at `.job.job_id`, not at top level.

**Fix:**

```bash
export JOB_ID="$(jq -r '.job.job_id // .job_id // .id // .jobId // empty' /tmp/bremen-job-create.json)"
echo "JOB_ID=$JOB_ID"
```

### 8. SSE or report ticket length is 0

**Symptom:** `STREAM_TICKET_LEN=0` or `REPORT_TICKET_LEN=0`

**Common cause:** The access token expired before minting the ticket, or the ticket endpoint returned an error.

**Fix:** Log in again, then immediately mint the stream/report ticket:

```bash
# Re-login
curl -sS -L \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/auth/token" \
  -d '{"username":"<USERNAME>","password":"<PASSWORD>"}' \
  | jq .

export ACCESS="$(jq -r '.access_token // empty' /tmp/bremen-token.json)"

# Mint stream ticket immediately
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/jobs/$JOB_ID/auth/ticket" \
  -d '{"purpose":"stream"}' \
  | jq .
```
