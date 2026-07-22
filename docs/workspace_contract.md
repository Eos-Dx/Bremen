# Analysis Workspace Contract

PR0077 — Multi-Workflow Analysis Workspace, Event Stream, and Reports.

## Workspace Route

| Attribute | Value |
|-----------|-------|
| Route | `GET /demo/workspace` |
| Content-Type | `text/html; charset=utf-8` |
| Pop-out | `GET /demo/workspace/{job_id}` |

The workspace is a self-contained HTML page with inline CSS and JavaScript.
No external assets, no framework dependency. All API data is fetched from
the job/event/report endpoints at runtime.

## Job Lifecycle

```
queued → staging → normalizing → running
  → completed
  → partial_success
  → workflow_configuration_required
  → failed
  → cancelled
  → expired
```

Job status is determined by the outcomes of all requested workflows.
A job with one successful and one failed workflow is `partial_success`.

## Workflow Lifecycle

```
pending → running
  → completed
  → workflow_unavailable
  → workflow_incompatible
  → workflow_configuration_required
  → selection_required
  → model_invalid
  → inference_failed
  → report_failed
```

Each workflow run is independent. A failed Aramis run does not affect
a completed Bremen run.

## Event Schema

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Stable version identifier (`"1"`) |
| `event_id` | string | Opaque UUID |
| `sequence` | int | Monotonic per-job counter |
| `timestamp` | string | ISO-8601 UTC |
| `job_id` | string | Opaque job UUID |
| `request_id` | string | Opaque request UUID |
| `workflow_id` | string \| null | Workflow scope (null for job-level events) |
| `stage` | string | Execution stage (e.g., `"normalization"`, `"workflow"`) |
| `event_type` | string | Dot-separated typed event (e.g., `"runtime.normalization.completed"`) |
| `status` | string | `"started"` \| `"completed"` \| `"failed"` \| `"resolved"` |
| `duration_ms` | int \| null | Duration in milliseconds |
| `details` | object | Allowlisted safe metadata |

### Event Types

```
runtime.request.accepted
runtime.input.staging.started
runtime.input.staging.completed
runtime.normalization.started
runtime.normalization.completed
runtime.normalization.failed
runtime.workflow.resolved
runtime.workflow.started
runtime.workflow.not_found
runtime.model.load.started
runtime.model.load.completed
runtime.model.validation.started
runtime.model.validation.completed
runtime.features.started
runtime.features.completed
runtime.inference.started
runtime.inference.completed
runtime.decision.started
runtime.decision.completed
runtime.report.started
runtime.report.completed
runtime.workflow.completed
runtime.workflow.failed
runtime.request.completed
```

## Job API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/demo/api/jobs` | List recent jobs (last 20) |
| `POST` | `/demo/api/jobs` | Create and execute an analysis job |
| `GET` | `/demo/api/jobs/{job_id}` | Get job status and workflow runs |
| `GET` | `/demo/api/jobs/{job_id}/events` | Get all events for a job |
| `GET` | `/demo/api/jobs/{job_id}/reports` | List reports per workflow |
| `GET` | `/demo/api/jobs/{job_id}/reports/{workflow_id}` | Get specific workflow report |

All responses include:
- `request_id`: opaque correlation ID
- `technical_demo_only: true`

Storage metadata included in list/get responses:
- `storage_mode`: `"ephemeral"`
- `retention_seconds`: configurable (default 3600)
- `max_jobs`: configurable (default 100)

## Event API

### GET /demo/api/jobs/{job_id}/events

Query parameters via headers:
- `X-Event-Cursor`: sequence cursor (default 0)

Response:
```json
{
  "events": [...],
  "cursor": 42,
  "job_id": "..."
}
```

## SSE Contract

| Attribute | Value |
|-----------|-------|
| Route | `GET /demo/api/jobs/{job_id}/events/stream` |
| Content-Type | `text/event-stream` |
| Cache-Control | `no-cache` |

### Cursor and Reconnect

- `Last-Event-ID` header specifies the starting cursor (sequence number)
- Events with `sequence > Last-Event-ID` are delivered
- On reconnect, events are delivered from the cursor position without replay

### Heartbeat Semantics

- `:keepalive` comment frame sent when no events arrive within ~15 seconds
- Keeps the connection alive and confirms the stream is operational

### Terminal Stream Behavior

- `event: stream_complete` sent when the job reaches a terminal status
- Terminal statuses: `completed`, `failed`, `partial_success`, `workflow_configuration_required`
- After `stream_complete`, the server closes the connection

### Real-Time Delivery

Events are delivered using `threading.Condition`-based notification:
- New events trigger immediate delivery (sub-second latency)
- No busy polling; no 15-second polling interval
- The heartbeat interval is only reached when no events arrive

### Connection Limits

- Maximum stream duration: ~5 minutes
- Client disconnect detected on write error (next keepalive or event)
- Server does not depend on active client for job execution

## Ephemeral Retention

- All event history is in-memory and process-local
- Jobs expire after `max_age_seconds` (default 1 hour)
- Maximum `max_jobs` (default 100) with LRU eviction
- Maximum `max_events_per_job` (default 1000) per job
- Process restart clears all history

## Process vs Technical Modes

### Process Mode

Human-readable stage labels derived from structured events:
- `"Request accepted"` ← `runtime.request.accepted`
- `"Normalization completed"` ← `runtime.normalization.completed`
- `"Workflow completed"` ← `runtime.workflow.completed`

### Technical Mode

Exposes allowlisted structured fields:
- `timestamp`, `event_type`, `stage`, `status`
- `workflow_id`, `duration_ms`, `sequence`
- `request_id`, `job_id`

## Report Lifecycle

```
not_requested → pending → generating
  → available
  → failed
  → unavailable
```

## Bremen Report Boundary

- Schema version: `v0.2`
- Sections: analysis_summary, mri_continuation_assessment, score_and_threshold,
  measurement_qc_summary, supporting_technical_evidence, model_identity,
  feature_schema_identity, workflow_readiness, limitations,
  technical_demo_only_disclaimer, audit_information
- Language: decision-support only; no diagnosis, no clinician-replacement
- `scientifically_certified: false` visible in report

## Aramis Unavailable Report Boundary

When no authoritative Aramis report runtime is configured:
- Status: `unavailable`
- Reason code: `WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED`
- No fabricated TRA probabilities, reliability, or recommendations

## Audit Fields

Safe immutable identifiers exposed:
```
job_id, request_id, workflow_id, model_id, model_version,
model_checksum, feature_schema_version, report_schema_version,
started_at, completed_at, final_status, storage_mode
```

Not exposed: patient identifiers, local paths, PONI contents,
model coefficients, raw H5 metadata.

## Privacy Allowlists

Four zones with per-field allowlists:

| Zone | Allowed | Prohibited |
|------|---------|------------|
| Technical events | event_type, stage, status, duration_ms | patient_id, raw_data, traceback |
| Workflow results | p_mri_needed, triage, model metadata | raw feature vectors |
| Internal reports | Report sections per schema | Event streams |
| Audit metadata | job_id, timestamps, checksums | PII, coefficients |

### Prohibited Detail Keys

The following keys are rejected at event storage:
`patient_id`, `patient_name`, `operator_id`, `scan_session_id`,
`specimen_id`, `ponifile`, `poni_text`, `raw_data`, `raw_array`,
`h5_path`, `dataset_path`, `local_path`, `model_coefficients`,
`traceback`, `exception_object`

### Prohibited Data

The following must not appear in any API response or workspace HTML:
- Patient identifiers
- Raw H5 paths or internal dataset paths
- PONI text contents
- Raw tracebacks or exception objects
- Model coefficients
- Private filesystem paths

## Multi-Workflow Partial Success

- A job with mixed workflow outcomes is `partial_success`
- Each workflow card displays its independent status
- Report availability is per-workflow
- A failed Aramis does not erase a completed Bremen result

## Scientific Certification Display

- `scientifically_certified: false` is displayed prominently
- When `false`, the report must not visually imply clinical readiness
- Certification is separate from technical model readiness

## Accessibility Behavior

- All interactive elements are semantic (buttons, tabs)
- Status conveyed via text labels, not only color
- Keyboard-operable controls
- Responsive layout (flexbox)
- `aria-` labels where appropriate

## Known Limitations

- Event storage is ephemeral (process-local, in-memory)
- No persistent history across restarts
- No multi-instance event durability
- Aramis report provider is not configured (returns unavailable)
- Bremen scientific certification is pending
- P1/P2/P3 policy is not resolved
- PDF generation is not implemented (JSON reports only)
- No role-based access controls
- Maximum 5-minute SSE stream duration per connection
