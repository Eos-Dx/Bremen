# Reports

## GET /demo/api/jobs/{job_id}/reports

List generated reports for a job.

### Auth

Bearer token required.

### Response — 200 OK

```json
{
  "reports": {
    "bremen": {
      "report_id": "<UUID>",
      "workflow_id": "bremen",
      "report_schema_version": "v0.2",
      "status": "available",
      "generated_at": "2025-08-05T12:00:15Z",
      "model_id": "bremen-mri-triage-logreg-v0-1",
      "model_version": "v0.1",
      "scientifically_certified": false
    }
  },
  "job_id": "<JOB_ID>",
  "technical_demo_only": true,
  "request_id": "<REQUEST_ID>"
}
```

---

## GET /demo/api/jobs/{job_id}/reports/{workflow_id}

Retrieve structured report JSON for a specific workflow.

### Auth

Bearer token required.

### Path Parameters

| Parameter | Description |
|-----------|-------------|
| `job_id` | Job UUID |
| `workflow_id` | Workflow name (e.g. `"bremen"`) |

### Response — 200 OK

Returns the full report payload for the requested workflow, including prediction
summary, model metadata, symmetry signals, and decision-support fields.

---

## GET /demo/api/reports/{job_id}/external

Return the normalized **external** report JSON (clinician-facing).

### Auth

Bearer token required.

### Response — 200 OK

Contains the decision-support report with prediction summary, model metadata,
input summary, symmetry signals, and limitations.

### Example

```bash
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/demo/api/reports/$JOB_ID/external" \
  | jq .
```

---

## GET /demo/api/reports/{job_id}/internal

Return the **internal** report JSON (audit / provenance detail).

### Auth

Bearer token required.

### Response — 200 OK

Contains additional internal fields: job identity, model and plugin metadata,
decision policy details, execution trace summary, and symmetry signal breakdown.

---

## GET /demo/report/{job_id}

Render the clinician-facing HTML report page.

### Auth

Browser navigation cannot attach Authorization headers, so the browser flow
mints a short-lived report ticket first and passes it as `auth_ticket`:

```
GET /demo/report/{job_id}?auth_ticket=<REPORT_TICKET>
```

### Response

```
Content-Type: text/html; charset=utf-8
```

### Example

```bash
curl -sS -L \
  -D /tmp/bremen-report.headers \
  "$BASE/demo/report/$JOB_ID?auth_ticket=$REPORT_TICKET" \
  -o /tmp/bremen-report.html

cat /tmp/bremen-report.headers
echo "REPORT=/tmp/bremen-report.html"
```

> The report is a **decision-support communication artifact**, not a diagnosis.
> It does not replace clinician judgment.
