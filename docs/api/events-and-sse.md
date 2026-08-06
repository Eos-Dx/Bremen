# Events & SSE

## GET /demo/api/jobs/{job_id}/events

Poll the event log for a completed or running job.

### Auth

Bearer token required.

### Response — 200 OK

```json
{
  "events": [
    {
      "schema_version": "1",
      "event_id": "<UUID>",
      "sequence": 13,
      "timestamp": "2025-08-05T12:00:05Z",
      "job_id": "<JOB_ID>",
      "request_id": "<REQUEST_ID>",
      "workflow_id": "bremen",
      "stage": "inference",
      "event_type": "runtime.inference.completed",
      "status": "completed",
      "duration_ms": 42,
      "details": {}
    }
  ],
  "cursor": 18,
  "job_id": "<JOB_ID>",
  "request_id": "<REQUEST_ID>",
  "technical_demo_only": true
}
```

### Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Always `"1"` |
| `event_id` | string | UUID |
| `sequence` | int | Monotonic per-job counter |
| `timestamp` | string | ISO 8601 UTC |
| `job_id` | string | Job UUID |
| `request_id` | string | Request UUID |
| `workflow_id` | string | Workflow name (e.g. `"bremen"`) |
| `stage` | string | Pipeline stage name |
| `event_type` | string | Typed event identifier |
| `status` | string | `"started"`, `"completed"`, `"failed"` |
| `duration_ms` | int or null | Stage duration in milliseconds |
| `details` | object | Safe technical metadata only |

### Event Lifecycle (Typical Bremen Flow)

```
runtime.request.accepted
runtime.normalization.started
runtime.normalization.completed
runtime.workflow.resolved
runtime.workflow.started
runtime.artifact.verification.completed
runtime.artifact.load.completed
runtime.artifact.adaptation.completed
runtime.model.validation.completed
runtime.input.preparation.completed
runtime.features.completed
runtime.features.validation.completed
runtime.inference.completed
runtime.output.validation.completed
runtime.decision.completed
runtime.workflow.completed
runtime.request.completed
runtime.report.completed
```

> Event types may change across versions. Always handle unknown event types
> gracefully.

---

## POST /demo/api/jobs/{job_id}/auth/ticket

Mint a short-lived, job-bound ticket for browser flows that cannot send
Authorization headers (EventSource, `window.location.href`).

### Auth

Bearer token required.

### Request

```json
{
  "purpose": "stream"
}
```

| Field | Values | Description |
|-------|--------|-------------|
| `purpose` | `"stream"` or `"report"` | What the ticket grants access to |

### Response — 201 Created

```json
{
  "ticket": "<STREAM_TICKET>",
  "expires_in": 60,
  "token_type": "stream_ticket",
  "job_id": "<JOB_ID>",
  "purpose": "stream",
  "technical_demo_only": true
}
```

### Errors

| Status | Meaning |
|--------|---------|
| 400 | Invalid or missing `purpose` |
| 401 | No valid Bearer token |
| 404 | Job not found |

---

## GET /demo/api/jobs/{job_id}/events/stream

Server-Sent Events (SSE) endpoint for live job progress.

### Auth

Native `EventSource` cannot attach Authorization headers. The browser flow
mints a short-lived stream ticket first and passes it as `auth_ticket`:

```
GET /demo/api/jobs/{job_id}/events/stream?auth_ticket=<STREAM_TICKET>
```

### Response

```
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
```

### Example SSE Frame

```
id: 13
event: job_event
data: {"schema_version":"1","event_id":"...","sequence":13,"timestamp":"...","job_id":"...","event_type":"runtime.inference.completed","status":"completed","duration_ms":42,"details":{}}
```

### Stream Lifecycle

1. Sends any buffered events since the client's `Last-Event-ID`.
2. Enters a polling loop waiting for new events (15-second heartbeat).
3. On job terminal status (`completed`, `failed`, etc.), drains remaining events and sends `stream_complete`.
4. Connection closes after a 5-minute maximum.

### Security Notes

- `access_token` and `refresh_token` must **never** appear in URLs.
- Only a short-lived `stream_ticket` (60-second TTL, job-bound, purpose-bound) may appear in the query string.
- The ticket is validated for `token_type == "stream_ticket"`, matching `job_id`, and `purpose == "stream"`.
