# PR 0077 — Multi-Workflow Analysis Workspace, Event Stream, and Reports

## Objective

Design and implement an observable multi-workflow analysis experience covering:

```
H5 input → staging → canonical normalization → one or more explicitly selected workflows
→ workflow-specific model execution → workflow-specific report generation
→ live process visualization → audit trail
```

The interface must make the distinction clear between:
- HTTP request completion
- normalization completion
- workflow completion
- model inference completion
- report completion
- scientific certification

The architecture must support any number of registered workflows, beginning with:
- `bremen`
- `aramis`

Bremen and Aramis must retain separate:
- model identity
- model readiness
- scientific certification
- process events
- result payload
- report schema
- report renderer
- decision contract

**No combined clinical verdict.**

## Current Runtime Evidence

The deployed runtime now emits structured orchestration events such as:
- `bremen.h5_input.stage.start`
- `bremen.h5_input.stage.success`
- `runtime.orchestration.started`
- `runtime.normalization.completed`
- `runtime.workflow.resolved`
- `runtime.request.completed`

Session containers report two normalized measurements. Nova reports six normalized measurements. The runtime completes without previous legacy preprocessing and model-package errors.

**Current limitations:**
1. Model execution between `workflow.resolved` and `request.completed` is not sufficiently visible.
2. `VALIDATE: SUCCESS` is unstructured and does not identify: workflow, model, model version, validation stage, feature schema, duration.
3. Frontend users cannot inspect a job-specific event stream.
4. There is no separate process panel per job/workflow.
5. There is no general per-workflow report contract.
6. There is no frontend presentation for: partial success, workflow unavailable, workflow configuration required, per-workflow readiness, scientific certification pending.
7. Current logs are application logs, not a user-facing job event model.

## Product and Clinical Boundary

- Bremen's product question: "Should the patient continue to MRI?"
- Bremen report language must remain decision-support only
- No diagnosis claim, no clinician-replacement claim
- No biopsy recommendation copied from Aramis
- Scientific certification status must be visible — a `scientifically_certified = false` report must not visually imply certified clinical readiness
- Aramis unavailable state: `WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED`
- Do not fabricate TRA probabilities, reliability, symmetry features, sensitivity/specificity, or recommendations

## Scope

- Job event model and bounded event storage
- Live event delivery via SSE
- Job status API, report metadata API
- Workflow-specific report contracts
- Bremen report renderer v1
- Aramis report provider boundary
- Analysis Workspace frontend (new route under /demo/)
- Timeline, workflow cards, process-log panel, report tabs, audit view
- Privacy and redaction boundaries
- Roadmap update

## Non-Goals

This PR does **not**:
- Define Bremen P1/P2/P3 science
- Certify Bremen scientifically
- Implement missing Aramis science
- Combine model results
- Diagnose disease
- Replace clinicians
- Redesign Docker or CI/CD
- Add a durable cloud event database
- Commit private H5/model/report artifacts
- Expose raw application logs
- Redesign the scientific runtime introduced in PR0075–PR0076
- Redesign Docker or deployment infrastructure

## Analysis Job Model

```python
@dataclass
class AnalysisJob:
    job_id: str
    request_id: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    overall_status: str  # queued | staging | normalizing | running | completed | partial_success | workflow_configuration_required | failed | cancelled | expired
    input_summary: dict  # safe: container_id, bucket, size_bytes
    normalization_summary: dict  # safe: measurement_count, side_count, layout
    requested_workflows: tuple[str, ...]
    workflow_runs: dict[str, WorkflowRun]
    reports: dict[str, ReportMetadata]
    event_cursor: int  # monotonic sequence number of last emitted event
```

Safety rules:
- No raw arrays
- No PONI contents
- No H5 internal paths
- No private local paths
- No patient identifiers in the technical job envelope
- Safe input basename may be exposed only where current privacy rules permit
- Identifiers used for correlation must be opaque UUIDs

## Workflow Run Model

```python
@dataclass
class WorkflowRun:
    workflow_id: str
    status: str  # pending | running | completed | workflow_unavailable | workflow_incompatible | workflow_configuration_required | selection_required | model_invalid | inference_failed | report_failed
    model_identity: dict  # model_id, model_version, model_checksum (safe fields only)
    readiness_snapshot: dict  # configured, model_ready, scientifically_certified at time of execution
    started_at: str | None
    completed_at: str | None
    duration_ms: int | None
    result_summary: dict  # safe summary: prediction_id, probability, recommendation
    report_metadata: ReportMetadata | None
    failure: str | None  # safe typed error
```

Isolation rules:
- A failed Aramis workflow must not remove a completed Bremen result
- A failed Bremen workflow must not remove a completed Aramis result

## Event Schema

```json
{
  "schema_version": "1",
  "event_id": "opaque-uuid",
  "sequence": 12,
  "timestamp": "2026-07-21T23:40:09Z",
  "job_id": "opaque-job-id",
  "request_id": "opaque-request-id",
  "workflow_id": "bremen",
  "stage": "inference",
  "event_type": "runtime.inference.completed",
  "status": "completed",
  "duration_ms": 18,
  "details": {
    "model_id": "bremen_mri_triage_logreg",
    "model_version": "v0.1"
  }
}
```

Requirements:
- `schema_version` is a stable version string
- `event_id` is a stable UUID
- `sequence` is monotonic per job
- `timestamp` is ISO-8601 UTC
- `details` is allowlisted per event type
- No arbitrary exception serialization
- No raw Python object dumping

## Event Lifecycle

Required structured events replacing current unstructured log lines:

```
runtime.request.accepted
runtime.input.staging.started
runtime.input.staging.completed
runtime.normalization.started
runtime.normalization.completed
runtime.workflow.resolved
runtime.workflow.started
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

Where a stage is not applicable, do not fabricate it.
An unavailable Aramis provider should not emit model inference completion.

Replace `VALIDATE: SUCCESS` with a structured `runtime.model.validation.completed` event containing: workflow_id, model_version, model_checksum, feature_schema_version, duration_ms.

## Event Storage

**First implementation**: Bounded in-memory store with:
- Maximum jobs: 100 (configurable via constant)
- Maximum events per job: 1000 (configurable)
- Maximum age: 1 hour (configurable)
- Deterministic LRU eviction when limits reached
- Thread safety via `threading.Lock`
- No unbounded growth
- No cross-job event leakage
- No raw sensitive payloads
- Clear process-restart semantics (all events are ephemeral)

```python
class BoundedEventStore:
    def __init__(self, max_jobs=100, max_events_per_job=1000, max_age_seconds=3600)
    def append(self, job_id: str, event: JobEvent) -> None
    def get_events(self, job_id: str, since_sequence: int = 0) -> list[JobEvent]
    def get_job_event_count(self, job_id: str) -> int
    def evict_old(self) -> int  # returns count of evicted events
```

The interface is designed so a future persistent implementation (database or durable event store) can replace it without changing API contracts.

In-memory history is ephemeral — this is documented in the API response schema.

## SSE Delivery

```
GET /demo/api/jobs/{job_id}/events/stream
```

- Content-Type: `text/event-stream`
- Connection lifecycle: open on GET, close on client disconnect or job expiry
- Event cursor using `Last-Event-ID` header for reconnect
- Heartbeat: `:keepalive` comment every 15 seconds
- Stream completion: `event: stream_complete` when job reaches terminal status
- Unavailable/expired job: `event: error` with `data: {"code": "job_not_found"}`
- Maximum connection duration: 5 minutes (configurable)
- Cleanup: background thread removes stale connections
- Client disconnect: socket close detected by write error on next heartbeat
- **Job execution must not depend on an active browser connection**

## Job API

```
POST   /demo/api/jobs              — create a new analysis job
GET    /demo/api/jobs/{job_id}     — get job status and summary
GET    /demo/api/jobs/{job_id}/events         — get all events for a job
GET    /demo/api/jobs/{job_id}/events/stream  — SSE event stream
GET    /demo/api/jobs              — list recent jobs (safe metadata only)
```

The existing `POST /predictions` and `GET /predictions/{job_id}` endpoints remain unchanged for backward compatibility.

The new `/demo/api/jobs/*` endpoints are the multi-workflow-aware successors.

## Report API

```
GET /demo/api/jobs/{job_id}/reports               — list available reports per workflow
GET /demo/api/jobs/{job_id}/reports/{workflow_id} — get specific workflow report
```

Decisions:
- Report payload is JSON for v1 (the existing `decision_support_report` schema is the basis for Bremen)
- Report schemas are versioned via `report_schema_version`
- Unavailable reports: `{"report_status": "unavailable", "reason_code": "..."}`
- Under current demo constraints, reports are accessible without auth
- No report filesystem paths are exposed — reports are built from stored result data

## Common Report Envelope

```python
@dataclass
class ReportEnvelope:
    report_id: str
    workflow_id: str
    job_id: str
    report_schema_version: str
    generated_at: str
    workflow_status: str
    model_id: str | None
    model_version: str | None
    scientifically_certified: bool
    disclaimer: str
    payload: dict  # workflow-specific
```

Common metadata:
- report ID, workflow ID, job ID
- model ID/version
- report schema version
- generation timestamp
- technical/research disclaimer
- workflow status
- scientific certification flag

## Bremen Report v1

Built on the existing `decision_support_report` schema (PR0053). Extended with:

```json
{
  "report_schema_version": "v0.2",
  "report_type": "bremen_mri_triage",
  "analysis_summary": { ... },
  "mri_continuation_assessment": { ... },
  "score_and_threshold": {
    "p_mri_needed": 0.85,
    "threshold": 0.5,
    "triage_recommendation": "MRI_RECOMMENDED"
  },
  "input_measurement_qc": { ... },
  "supporting_technical_evidence": { ... },
  "model_identity": {
    "model_version": "v0.1",
    "feature_schema_version": "v0.1",
    "model_checksum": "abc123..."
  },
  "workflow_readiness": {
    "configured": true,
    "model_ready": true,
    "scientifically_certified": false
  },
  "limitations": [ ... ],
  "technical_demo_disclaimer": "...",
  "audit_information": { ... }
}
```

Bremen language rules:
- "MRI decision support" only
- No diagnosis claim
- No clinician-replacement claim
- No biopsy recommendation copied from Aramis
- If `scientifically_certified = false`, the report must not visually imply certified clinical readiness

## Aramis Report Provider Boundary

Aramis must have its own report provider/renderer registered in the workflow registry.

```python
class AramisReportProvider:
    workflow_id = "aramis"

    def get_report(self, workflow_result: WorkflowResult) -> ReportEnvelope:
        if workflow_result.status == "failed":
            return ReportEnvelope(
                report_status="unavailable",
                reason_code="WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED",
            )
        # Future: delegate to authoritative Aramis report generator
```

Where the authoritative Aramis report generator is configured, the platform should reference or adapt its output without recreating scientific content.

Where it is unavailable:
```json
{"report_status": "unavailable", "reason_code": "WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED"}
```

Do not fabricate:
- TRA probabilities
- reliability
- symmetry features
- sensitivity/specificity
- recommendations

## Analysis Workspace

New route: `/demo/workspace`

Conceptual layout:

```
left panel:
  job navigation / job list

center:
  job summary header
  normalization card (measurement count, sides, layout)
  workflow cards (one per workflow)
  report/audit tabs

right panel (collapsible):
  live process event stream
```

The workspace is a new section under the `/demo/` namespace. It does not replace the existing `/demo` route — both coexist.

Frontend states to handle:
- no job selected
- queued
- active analysis (events arriving)
- completed (all success)
- partial success (mixed outcomes)
- workflow configuration required
- workflow unavailable
- normalization failure
- expired job
- disconnected event stream
- reconnecting stream

## Timeline

A human-readable timeline rendered from structured events.

Safe display mapping:
```
Input staged                ← runtime.input.staging.completed
Layout detected             ← runtime.normalization.layout_detected
Canonical normalization complete  ← runtime.normalization.completed
N measurements available    ← from normalization_summary
Bremen workflow resolved    ← runtime.workflow.resolved
Model validated             ← runtime.model.validation.completed
Features constructed        ← runtime.features.completed
Inference completed         ← runtime.inference.completed
Decision applied            ← runtime.decision.completed
Report generated            ← runtime.report.completed
```

Rules:
- The timeline must not claim a stage completed unless the corresponding event exists
- Nova with `configuration_required`: "Bremen workflow configuration required — inference not started — Report unavailable"

## Workflow Cards

Each workflow gets an independent card rendering.

Safe information displayed:
- Workflow name (from `workflow_id`)
- Status (typed: completed, failed, unavailable, configuration_required)
- Model ID/version (when available)
- Technical readiness (configured, model_ready)
- Scientific certification status
- Score/decision where available (Bremen only)
- Report availability
- Duration in ms
- Typed reason when unavailable

Design rule: Do not use a single red/green state for all workflows. A job with one success and one unavailable workflow must render as `partial_success` in the overall job status, with each card showing its independent state.

## Process Log Panel

Resizable right-side panel with:

Functionality:
- Open/close toggle
- Resize handle (draggable width)
- Filter by workflow (dropdown)
- Filter by stage (dropdown or text)
- Follow newest event (auto-scroll)
- Pause auto-scroll toggle
- Reconnect state indicator
- Copy safe technical details (button per event)
- Open in dedicated browser route/tab (`/demo/workspace/{job_id}/process-log`)
- Link an event to its workflow/report section

Two presentation modes:
1. **Process** — user-readable descriptions ("Model loaded", "Features computed")
2. **Technical details** — safe structured fields (event_type, stage, status, duration_ms)

Do not show raw App Runner stdout. Do not show raw traceback.

## Audit View

Separate section containing safe immutable identifiers:

```json
{
  "job_id": "uuid",
  "request_id": "uuid",
  "runtime_build_version": "sha or version",
  "workflow_id": "bremen",
  "model_id": "bremen_mri_triage_logreg",
  "model_version": "v0.1",
  "model_checksum": "sha256:...",
  "configuration_digest": "sha256:...",
  "feature_schema_version": "v0.1",
  "report_schema_version": "v0.2",
  "input_checksum": "sha256:...",
  "started_at": "ISO-8601",
  "completed_at": "ISO-8601",
  "final_status": "completed"
}
```

Do not expose:
- model coefficients
- local paths
- raw H5 values
- PONI contents
- patient identifiers

## Privacy and Access Boundaries

Four explicit zones with per-field allowlists:

| Zone | Content | Allowed fields | Not allowed |
|------|---------|---------------|-------------|
| Technical events | Process logs | job_id, event_type, stage, status, duration_ms | patient identifiers, raw paths, operator names |
| Workflow results | Prediction output | p_mri_needed, triage, model metadata | patient identifiers, raw feature vectors |
| Internal reports | Clinical context | Patient/session only where privacy rules permit | Event streams, console |
| Audit metadata | Immutable trail | job_id, model identity, timestamps, checksums | PII, coefficients, raw values |

Tests must fail on prohibited field names and values.

## Frontend Architecture

Follow existing demo frontend conventions (inline HTML/CSS/JS in `demo_ui.py`).

Design decisions:
- The workspace is generated server-side via an extended `build_demo_html_page()` or a new `build_workspace_page()` function
- State is owned in the browser via JavaScript closures and DOM
- Event-stream lifecycle managed via `EventSource` API
- Component boundaries: job list, job summary, workflow cards, timeline, process panel, report tabs, audit view
- Error boundaries: each section independently handles loading/error/empty states
- Accessibility: aria-labels, keyboard navigation, role attributes
- Responsive layout: CSS flexbox, min-width breakpoints
- No new frontend framework — follow existing standard-library-only approach
- Backward-compatible: the existing `/demo` route is untouched

## Multi-Workflow Extensibility

The frontend must render workflows from response data. Do not hardcode UI as:

```javascript
// ANTIPATTERN
if (workflow === "bremen") { ... }
else if (workflow === "aramis") { ... }
```

Workflow-specific report renderers may be registered by workflow ID, but:
- Unknown workflow cards must still render with safe generic technical renderer
- Common status/timeline must continue to work for unregistered workflows
- Missing specialized renderer must use a safe generic renderer showing metadata only

## Report Lifecycle

```
not_requested → pending → generating → available
                                        → failed
                                        → unavailable
```

Rules:
- A report failure must not erase a successful model result
- Model completed + report failed = overall `partial_success`
- One report available + another unavailable = overall `partial_success`
- Workflow unavailable = overall `partial_success`
- Normalization failed before reports = overall `failed`

## Testing Strategy

**Backend tests** (new file: `tests/test_bremen_event_stream.py`):
- Event schema validation
- Monotonic sequence per job
- Event ordering within a job
- Bounded retention (max events per job, max jobs)
- LRU eviction behavior
- Thread safety (concurrent append/read)
- Job isolation (events from job A not leaked to job B)
- SSE reconnect via `Last-Event-ID`
- Expired job behavior
- Stream completion on terminal status
- Privacy allowlist (no prohibited fields in events)
- Structured model events (no `VALIDATE: SUCCESS`)
- Report metadata correctness
- Independent report failure (report fails, model result preserved)

**Frontend tests** (new file: `tests/test_bremen_workspace_ui.py`):
- Active job timeline rendering
- Completed job rendering
- Partial success rendering
- Bremen completed state
- Bremen scientific certification pending state
- Nova workflow configuration required state
- Aramis unavailable state
- Unknown workflow rendering
- Process mode vs technical details mode
- Filtering by workflow/stage
- Resize behavior (CSS class checks)
- Pop-out route state
- Disconnect/reconnect indicators
- Report tab visibility
- Audit tab content
- Privacy redaction (no patient identifiers in rendered output)
- Accessibility (aria attributes, keyboard nav)

Use synthetic data only in committed tests.

## Observability Recursion Safeguard

The event system itself must not create recursive logging or event emission:

```
store event → optionally log safe event (application log, not job event)
            → do NOT create another job event from that log
```

Implementation: The `BoundedEventStore.append()` method logs via `logging.debug()` with a distinct logger name (`bremen.event.store`) that is filtered from any event-capture mechanism.

## Existing CI/CD

Reuse existing pipeline in `.github/workflows/quality.yml` and `ecr-publish.yml`.

Additions:
- New test file `test_bremen_event_stream.py` is picked up automatically by pytest discovery
- No new Docker build stages
- No new cloud infrastructure

## Roadmap Update

Add to ROADMAP.md:

### Current milestone (PR0077):

```
Multi-Workflow Analysis Workspace
- Structured job events and bounded event store
- SSE live event stream
- Workflow cards with independent status per workflow
- Bremen report v1 (extended from PR0053 decision_support_report)
- Aramis report provider boundary
- Job/report API endpoints
- Analysis Workspace frontend (timeline, process panel, report/audit tabs)
- Privacy/redaction enforcements
- Audit metadata display
```

### Next milestone:

```
- Authoritative Aramis runtime integration
- Aramis report parity
- Persistent job/event history (database backend)
- Report access controls
- PDF/report artifact storage
- Bremen scientific parity evidence
- Bremen P1/P2/P3 policy
```

### Later milestone:

```
- Additional workflow providers
- Long-term audit retention
- Operational dashboards
- Cross-version report comparison
- Certification evidence bundles
- Role-based report access
```

Distinguish: committed | planned | blocked by scientific evidence | future.

Do not describe unavailable Aramis inference or Bremen scientific certification as completed.

## Implementation Sequence

16 incremental gates in order:

1. **Event schema** — Define `JobEvent` dataclass, event types enum, serialization/validation
2. **Bounded event store** — `BoundedEventStore` with retention/eviction/thread safety
3. **Orchestrator event emission** — Emit structured events from `workflow_orchestrator.py` and `workflow_bremen.py`; replace `VALIDATE: SUCCESS`
4. **Job query API** — `/demo/api/jobs/*` endpoints with `AnalysisJob` and `WorkflowRun` models
5. **SSE stream** — EventSource-compatible endpoint with reconnect/cursor/heartbeat
6. **Workflow report contracts** — `ReportEnvelope` and per-workflow `ReportProvider` protocol
7. **Bremen report v1** — Extend `decision_support_report` to v0.2 with workflow readiness, audit, disclaimer
8. **Aramis report-provider boundary** — `AramisReportProvider` returning unavailable for now
9. **Workspace shell** — New `/demo/workspace` route with layout, job list, job summary
10. **Timeline** — Render structured events as human-readable timeline
11. **Workflow cards** — Render per-workflow status, model identity, readiness, results
12. **Process panel** — Collapsible right panel with filter, follow, pop-out
13. **Report/audit tabs** — Tab switcher between report and audit views
14. **Privacy tests** — Failing tests for prohibited field names/values in events and reports
15. **Roadmap update** — Update ROADMAP.md with current/next/later milestones
16. **Full local/browser validation** — End-to-end manual walkthrough

Avoid monolithic frontend rewrite — each frontend gate is additive.

## Expected Files to Change

### New files:
- `src/bremen/api/event_schema.py` — Event dataclass, event types, serialization
- `src/bremen/api/event_store.py` — BoundedEventStore implementation
- `src/bremen/api/job_models.py` — AnalysisJob, WorkflowRun, ReportMetadata dataclasses
- `src/bremen/api/job_api_handler.py` — Job/report API endpoint handlers
- `src/bremen/api/sse_handler.py` — SSE stream handler
- `src/bremen/api/report_provider.py` — ReportEnvelope, ReportProvider protocol
- `src/bremen/api/report_bremen.py` — Bremen report v1 renderer
- `src/bremen/api/report_aramis.py` — Aramis report provider (scaffold)
- `src/bremen/workspace_ui.py` — Analysis Workspace HTML page generator
- `tests/test_bremen_event_stream.py` — Backend event/timeline/SSE tests
- `tests/test_bremen_workspace_ui.py` — Frontend workspace tests
- `docs/workspace_contract.md` — Workspace architecture and API contract (lightweight)

### Modified files:
- `src/bremen/api/workflow_orchestrator.py` — Emit structured events during orchestration
- `src/bremen/api/workflow_bremen.py` — Emit model validation/inference events; replace `VALIDATE: SUCCESS`
- `src/bremen/api/workflow_provider.py` — Add event emission hooks to abstract provider
- `src/bremen/api/server.py` — Register new `/demo/api/jobs/*` and SSE routes
- `src/bremen/api/app.py` — Wire new handler functions
- `src/bremen/api/schemas.py` — Add AnalysisJob, WorkflowRun to schema exports
- `ROADMAP.md` — Add multi-workflow workspace milestone

### Files NOT modified:
- `src/bremen/api/xrd_normalization.py` — No changes to canonical normalization
- `src/bremen/api/h5_layouts.py` — No changes to layout detection
- `src/bremen/api/preflight.py` — No changes to preflight
- `src/bremen/api/preprocessing_bridge.py` — No changes to preprocessing
- `src/bremen/inference.py` — No changes to inference math
- `src/bremen/api/model_state.py` — No changes to model loading
- `src/bremen/api/model_source.py` — No changes to model source resolution
- Docker files — No changes
- CI/CD workflows — No changes
- Terraform — No changes

## Risks

| Risk | Mitigation |
|------|------------|
| Event store grows unbounded | Bounded with max jobs, max events per job, max age, deterministic eviction |
| SSE connections leak | Background cleanup thread, max connection duration, proper close handling |
| Frontend too large for single HTML file | Server-generated HTML with modular JS sections; no framework dependency |
| Privacy boundary violations | Explicit allowlists per zone; tests that fail on prohibited fields |
| Report content fabrication | Report providers return `unavailable` unless authoritative data exists |
| Recursive event emission | Distinct logger name for event store; no event emission from event store |
| Frontend hardcodes workflow IDs | Response-driven rendering with generic fallback for unknown workflows |
| Missing events break timeline | Timeline uses only confirmed events; missing stages are not claimed |

## Stop Conditions

Stop planning with a blocker if:
- Event payloads require raw patient/H5 data
- Report content would need fabrication
- Aramis report content would need reverse engineering
- Frontend requires direct access to App Runner logs
- Job storage would be unbounded
- Live stream depends on browser connection for job execution
- Workflow cards require hardcoded two-model orchestration
- Roadmap would falsely claim scientific completion

## Acceptance Criteria

### Gate 1: Event schema pass
- `JobEvent` dataclass is defined with all required fields
- Event types enum covers all required lifecycle events
- JSON serialization produces valid, versioned output
- No prohibited fields in event schema

### Gate 2: Bounded storage pass
- `BoundedEventStore` respects max_jobs, max_events_per_job, max_age
- Thread-safe concurrent appends and reads
- Eviction removes oldest jobs first
- No cross-job leakage

### Gate 3: SSE pass
- EventSource connection delivers events in order
- Last-Event-ID reconnect delivers missed events
- Heartbeat prevents timeout on idle connections
- Stream complete event on terminal job status
- Expired job returns graceful error event

### Gate 4: Job API pass
- `/demo/api/jobs` list returns safe metadata only
- `POST /demo/api/jobs` creates job and returns job_id
- `GET /demo/api/jobs/{job_id}` returns full status
- `GET /demo/api/jobs/{job_id}/events` returns ordered events

### Gate 5: Workflow isolation pass
- Bremen workflow events are separate from Aramis workflow events
- Failed Aramis does not affect Bremen outcome
- Partial success status rendered when outcomes differ
- Report generation is independent per workflow

### Gate 6: Bremen report pass
- Report contains analysis_summary, mri_continuation_assessment, score_and_threshold
- Report includes model_identity, workflow_readiness, scientifically_certified flag
- Report language is decision-support only
- `scientifically_certified=false` report does not imply clinical readiness

### Gate 7: Aramis report-boundary pass
- Aramis report returns `unavailable` with typed reason code
- No fabricated TRA probabilities, reliability, or recommendations
- No cross-import of Bremen report logic

### Gate 8: Workspace pass
- `/demo/workspace` route renders without errors
- No job selected state shows guidance
- Job list populated from API
- Workflow cards render from response data

### Gate 9: Timeline pass
- Human-readable timeline renders from structured events
- Missing stages omitted from timeline
- Nova configuration_required shows "not started" labels

### Gate 10: Process-panel pass
- Panel opens/closes via toggle
- Filter by workflow and stage works
- Follow newest event auto-scrolls
- Pause/play toggle stops auto-scroll
- Pop-out route preserves state

### Gate 11: Privacy pass
- No patient identifiers in event streams
- No raw H5 paths in job metadata
- No raw checksums in frontend display
- No raw exception messages in process panel
- Tests fail on prohibited field values

### Gate 12: Accessibility pass
- All interactive elements have aria-labels
- Keyboard navigation works for all sections
- Color contrast meets WCAG AA minimum
- Screen reader announces timeline events

### Gate 13: Roadmap pass
- ROADMAP.md updated with current/next/later milestones
- No false claims about scientific certification or Aramis completion

### Gate 14: Full regression pass
- All existing tests pass
- New event stream tests pass
- New workspace UI tests pass
- No regressions in inference or normalization

### Gate 15: Deployment smoke pass
- Server starts and registers new routes
- Health endpoint returns OK
- Workspace route loads in browser
- Basic end-to-end: select container → analyze → see events → see report

Production scientific certification remains a separate workflow-specific gate.

---

**PLAN COMPLETE: yes**

PLAN FILE: `.project-memory/pr/0077-multi-workflow-analysis-workspace/PLAN.md`
HEAD: `4a02fb7a0ef481c4f75d9b022e6953ac4331b292`
BRANCH: `0077-multi-workflow-analysis-workspace`
JOB MODEL: AnalysisJob + WorkflowRun dataclasses in `job_models.py`
EVENT SCHEMA: JobEvent dataclass + typed event types enum in `event_schema.py`
EVENT STORE: BoundedEventStore in `event_store.py` (max_jobs=100, max_events_per_job=1000, max_age=3600s)
SSE CONTRACT: GET /demo/api/jobs/{job_id}/events/stream with Last-Event-ID, heartbeat, stream completion
JOB API: POST/GET /demo/api/jobs/* endpoints in `job_api_handler.py`
REPORT ARCHITECTURE: ReportEnvelope + ReportProvider protocol in `report_provider.py`
BREMEN REPORT: v0.2 extension of decision_support_report in `report_bremen.py`
ARAMIS REPORT BOUNDARY: AramisReportProvider scaffold in `report_aramis.py`
ANALYSIS WORKSPACE: `/demo/workspace` route in `workspace_ui.py`
PROCESS PANEL: Resizable right panel with Process/Technical modes
AUDIT VIEW: Immutable identifier section in workspace
PRIVACY MODEL: Four-zone allowlist with per-field verification tests
ROADMAP UPDATE: Current/next/later milestones added to ROADMAP.md
IMPLEMENTATION SEQUENCE: 16 incremental gates from event schema through browser validation
EXPECTED FILES: 11 new files, 7 modified files, 0 deleted files
BLOCKERS: None
WARNINGS: None — all stop conditions checked and clear
