PLAN COMPLETE

PLAN FILE

.project-memory/pr/0082-bremen-investor-control-room/PLAN.md

HEAD

e622b5e1900f352acf11d8c7a0b32b0316800345

BRANCH

0082-bremen-investor-control-room

DEFAULT ROUTE

The default /demo route is replaced by the Investor Control Room.

The server route dispatch currently is:
  GET /demo -> _handle_demo_route -> build_demo_html_page (old workspace)

This is changed to:
  GET /demo -> _handle_control_room_route -> build_control_room_page (new)

The existing /demo/workspace route is preserved unchanged for backward
compatibility. The old /demo?view=showcase hidden mode is retired.

The route change is a single URL-to-handler mapping in do_GET. No router
framework change. No new dependencies.

All existing API endpoints remain at their current paths:
  GET /health
  GET /model/version
  POST /predictions
  GET /predictions/{job_id}
  GET /demo/workspace
  GET /demo/workspace/{job_id}
  GET /demo/api/evidence
  GET /demo/api/h5/containers
  POST /demo/api/h5/containers
  POST /demo/api/h5/analyze
  GET /demo/api/jobs
  POST /demo/api/jobs
  GET /demo/api/jobs/{job_id}
  GET /demo/api/jobs/{job_id}/events
  GET /demo/api/jobs/{job_id}/events/stream
  GET /demo/api/jobs/{job_id}/reports
  GET /demo/api/jobs/{job_id}/reports/{workflow_id}

No existing route is removed. No existing deep link is broken.

CURRENT UI INVENTORY

Current routes:
  /demo (GET) -> build_demo_html_page. Single-column H5 upload and
    analyze page. Inline CSS and JS in demo_ui.py (585 lines).
    Includes container browser, upload, analyze button, events panel,
    result card. Uses the old PR0077 legacy /demo/api/h5/analyze
    endpoint which does not use the structured event store.

  /demo/workspace (GET) -> build_workspace_page. Multi-workflow
    analysis workspace. Inline CSS and JS in workspace_ui.py
    (1265 lines). Includes job navigation, timeline, workflow cards,
    decision visualization, audit view, and showcase mode
    (?view=showcase). This is the current primary workspace.

  /demo/workspace/{job_id} (GET) -> workspace with a preselected job.

  /demo/workspace?view=showcase (GET) -> PR0078 showcase mode,
    now implicitly active in the JS when the query parameter is present.

  /demo/api/evidence (GET) -> JSON evidence bundle.

  /demo/api/h5/containers (GET, POST) -> list and upload H5 files.

  /demo/api/jobs (GET, POST) -> list and create analysis jobs.

  /demo/api/jobs/{job_id} (GET) -> job status with execution traces.

  /demo/api/jobs/{job_id}/events (GET) -> event history.

  /demo/api/jobs/{job_id}/events/stream (GET) -> SSE.

  /demo/api/jobs/{job_id}/reports (GET) -> report list.

  /demo/api/jobs/{job_id}/reports/{workflow_id} (GET) -> report.

  /health (GET), /model/version (GET), /predictions (POST),
  /predictions/{job_id} (GET) -> existing platform API.

Current frontend architecture:
  All pages are server-generated HTML with inline CSS and JavaScript.
  No framework. No external assets. No CDN. Standard library only.
  Pages fetch JSON from API endpoints at runtime.
  EventSource for SSE.

Static assets: None. All CSS and JS is inline.

REAL BREMEN MODEL

The one real Bremen model is the currently configured ModelState model.
It is loaded at server startup from the environment variables
BREMEN_MODEL_URI, BREMEN_MODEL_VERSION, BREMEN_MODEL_CHECKSUM.
The model package contains portable_logreg with feature columns,
imputer statistics, scaler mean/scale, coefficients, intercept,
and threshold.

Safe metadata for display:
  Workflow name: Bremen
  Workflow ID: bremen
  Model display name: MRI Triage Model
  Model version: from ModelState._model_version
  Artifact type: portable_logreg
  Decision-policy ID: bremen_mri_continuation_threshold
  Decision-policy version: 0.1.0
  Feature schema version: v0.1
  Technical readiness: from ModelState.is_ready()
  Scientific certification: false (until formally certified)
  Technical demo status: true

Not exposed:
  Artifact storage paths. Checksums not already approved.
  Feature values or vectors. Coefficients. Intercepts. Weights.
  Scaler parameters. Imputer parameters. Reference distributions.
  Private configuration paths. Patient identifiers.

No model selector is implemented. No second model variant is fabricated.
No unavailable model is listed as selectable.

REAL EXECUTION PATH

The complete browser-to-runtime path for one analysis:

1. User clicks "Analyze" on a preconfigured or uploaded source.
2. Frontend calls POST /demo/api/jobs with body:
     { "container_id": "...", "workflow_id": "bremen", "h5_path": "..." }
   Server file: src/bremen/api/server.py, _handle_demo_jobs_create.
   Handler file: src/bremen/api/job_api_handler.py, handle_jobs_create.
3. Server creates AnalysisJob with status "running".
   Creates WorkflowRun for bremen.
   Stores in shared _jobs dict.
4. Server calls run_workflow_request with the staged H5 path.
   Server file: src/bremen/api/workflow_orchestrator.py,
   run_workflow_request.
5. Orchestrator normalizes H5 to CanonicalXRDCase.
   Emits runtime.request.accepted, runtime.normalization.started,
   runtime.normalization.completed events to BoundedEventStore.
6. Orchestrator resolves bremen provider from WorkflowRegistry.
   Emits runtime.workflow.resolved, runtime.workflow.started events.
7. BremenProvider.execute runs:
   Compatibility check -> emits runtime.input.preparation.completed.
   Artifact preparation -> emits runtime.artifact.verification.completed.
   Model validation -> emits runtime.model.validation.completed.
   Features -> emits runtime.features.completed.
   Inference -> emits runtime.inference.completed.
   Output validation -> emits runtime.output.validation.completed.
   Decision -> emits runtime.decision.completed.
   Result returned with decision_code, decision_display_name,
   decision_policy_id, triage_recommendation.
8. Orchestrator emits runtime.workflow.completed, runtime.request.completed.
9. Report generation via BremenReportProvider.
10. Job marked completed in _jobs dict.
11. All events are stored in BoundedEventStore.

Frontend reads:
  POST /demo/api/jobs -> 201 { job: { job_id, overall_status, ... } }
  SSE: /demo/api/jobs/{job_id}/events/stream -> receives events live.
  GET /demo/api/jobs/{job_id} -> full status with traces.
  GET /demo/api/jobs/{job_id}/reports/bremen -> report.

Test coverage: Existing tests cover run_workflow_request,
BremenProvider.execute, event emission, job creation, API responses.

Error paths:
  Model not ready -> 503 response.
  H5 staging failure -> job status failed with safe error.
  Normalization failure -> job status normalization_failed.
  Workflow not found -> job status failed.
  Provider execution failure -> job status failed with safe reason.
  Report generation failure -> report status failed, job status
    remains partial_success.

FRONTEND STATE MODEL

The explicit frontend state machine for the Control Room:

  idle: Initial state. No source selected. No job exists.
    Displays welcome message and model/readiness information.

  source_selected: A container or input source has been chosen.
    Show source summary. Enable Analyze button.

  validating: Source validation in progress (preflight checks).

  ready_to_submit: Source validated. User can click Analyze.

  submitting: POST /demo/api/jobs in flight.
    Show loading indicator. Disable Analyze button to prevent
    duplicate submissions.

  job_created: Job accepted (201 response with job_id).
    Show job created confirmation.
    Initialize SSE connection.

  connecting: EventSource opening.
    Show "Connecting..." indicator.

  running: Events arriving via SSE. Pipeline stages active.
    Visual pipeline shows current stage highlighted.
    Event panel receives and renders events.

  reconnecting: SSE connection lost, EventSource reconnecting.
    Show "Reconnecting..." indicator. Preserve existing events.
    Use Last-Event-ID for cursor on reconnect.

  completed: Job reached terminal completed status.
    SSE stream_complete received.
    Show final pipeline state. Show result card.
    Decision panel shows approved vocabulary.
    Report link available.

  partial_success: Workflow completed but report failed.
    Result visible. Report shows unavailable.

  failed: Job failed. Show failure reason from safe error.
    Pipeline shows failed stage.

  unavailable: Workflow not available. Show typed reason.

  expired: Job expired from event store. Show expiration notice.
    SSE returns 404 on reconnect attempt.

Allowed transitions:
  idle -> source_selected -> validating -> ready_to_submit ->
  submitting -> job_created -> connecting -> running ->
  completed | partial_success | failed | unavailable | expired

  running -> reconnecting -> running (reconnect success)
  running -> reconnecting -> failed (reconnect fails, job expired)

  Any terminal state (completed, partial_success, failed,
  unavailable, expired) -> source_selected (new analysis)

Prevented combinations:
  completed AND running simultaneously.
  report ready before job created.
  SSE connected before job_id exists.
  positive and negative decision styles simultaneously.
  technical readiness shown as scientific certification.

PIPELINE STAGES

Ten visual stages mapped to authoritative events:

1. Input accepted
   Event: runtime.request.accepted
2. Source validated
   Event: runtime.input.staging.completed
3. Canonical XRD created
   Event: runtime.normalization.completed
4. Bremen workflow resolved
   Event: runtime.workflow.resolved
5. Model artifact prepared
   Event: runtime.artifact.verification.completed
6. Feature contract validated
   Event: runtime.features.validation.completed
   Detail: expected_count, produced_count, missing_count, non_finite_count
   (harden also catches runtime.model.validation.completed)
7. Inference completed
   Event: runtime.inference.completed
   Detail: model_id, model_version, output_count
8. Decision policy applied
   Event: runtime.decision.completed
   Detail: decision_policy_id, decision_code
9. Report generated
   Event: runtime.report.completed
10. Analysis complete
    Event: runtime.request.completed

Stage states:
  pending: No event for this stage yet. Grey icon.
  active: Most recent started stage without completed pair.
    Bold with animated indicator. (pulse on the connector arrow)
  completed: Stage completed event received. Green check.
  failed: Stage failed event received (e.g., runtime.normalization.failed).
    Red X. Show safe reason.
  unavailable: Stage was skipped (configuration_required or
    workflow_unavailable). Yellow warning. Show typed reason.

Stage ordering is enforced by the existing lifecycle state machine
in runtime_plugin.py. The frontend renders stages in the order
defined by BREMEN_STAGE_ORDER.

Each stage card shows:
  Stage name (from label mapping).
  Status icon.
  Elapsed duration when available (from event duration_ms).
  Safe detail summary when available (from event details).

No fabricated stages. No stage claims completion without evidence.

EVENT PANEL

The docked structured live event panel is a required first-class element.

Location: Right side of the control room layout, occupying approximately
35 percent of viewport width on large screens. Below the pipeline and
result area on narrow screens.

Visible states:
  idle: "Analysis events will appear here."
  connecting: "Connecting to live event stream..."
  running: Real events rendering. Auto-scroll enabled.
  paused: Auto-scroll paused. "Scroll paused" indicator.
  reconnecting: "Reconnecting..." with count of preserved events.
  completed: All events rendered. "Analysis complete" summary.
  failed: "Analysis failed." Last event shows failure.
  expired: "This job has expired."

Functionality:
  Auto-scroll during live execution (scroll follows newest event).
  Manual scroll pauses auto-scroll.
  Resume button to re-enable auto-scroll.
  Displayed fields per event row:
    Sequence number.
    Timestamp.
    Workflow ID.
    Stage name.
    Event type (short, human-readable).
    Status (started/completed/failed).
    Duration (when available).
  Click an event to highlight the corresponding pipeline stage.
  Click a pipeline stage to scroll the event list to matching events.
  Filters (dropdown or toggle):
    All events.
    Completed stages only.
    Failed stages only.
    Current workflow only (always filtered to bremen since there is one).
  "Copy event details" button per row copies safe JSON to clipboard.

Event rendering limits:
  Show at most the last 200 events in the DOM to prevent unbounded
  memory growth. Full history is always available via API
  GET /demo/api/jobs/{job_id}/events.
  Older events are replaced by newer ones if the limit is reached.
  The limit is enforced on the DOM, not on the API fetch.

No raw Python tracebacks. No model internals. No raw exception objects.
No patient identifiers.

SSE LIFECYCLE

EventSource lifecycle in the Control Room:

1. Connect: After job creation succeeds (201 response with job_id),
   open EventSource to /demo/api/jobs/{job_id}/events/stream.

2. Initial replay: Server sends all events since sequence 0
   (the job is newly created, so only the first few orchestration
   events may already exist). The frontend captures the last
   received event_id as the cursor.

3. Live delivery: Events arrive as event: job_event with id.
   The frontend appends each to the event panel and advances the
   pipeline stage when a stage-completed event arrives.

4. Heartbeat: EventSource receives :keepalive comments. These are
   ignored by the EventSource API and do not trigger events.

5. Stream complete: When the job reaches terminal status, the server
   sends event: stream_complete. The frontend closes the EventSource
   and marks the job as completed.

6. Reconnect: On connection loss, the browser EventSource API
   automatically reconnects. The server reads Last-Event-ID from the
   request headers and replays events since that cursor. The frontend
   receives missed events without gaps.

7. Duplicate suppression: EventSource may deliver the same event_id
   on reconnect. The frontend checks event.sequence against the
   last observed sequence. Duplicates are ignored.

8. Stale/expired job: If the job has expired from the event store,
   the SSE endpoint returns 404. The frontend renders the expired
   state and does not retry.

9. Completion: After stream_complete, the EventSource is closed
   via eventSource.close(). No reconnect is attempted.

10. Route changes: If the user navigates away (control room to
    workspace or another page), the EventSource is closed. If they
    return, a new connection is established. If the job is already
    complete, the full event history is fetched via GET
    /demo/api/jobs/{job_id}/events.

One EventSource per Control Room tab. No uncontrolled duplicate
connections. No polling fallback is required during normal operation.
A polling fallback exists only if EventSource constructor fails
(for very old browsers), with a maximum 5-second interval and
immediate stop on terminal state.

DECISION PROJECTION

The decision panel reads from the job API response.

The authoritative decision object is in:
  job.workflow_runs.bremen.result_summary

Fields consumed:
  decision_code: str (CONTINUE_MRI or MRI_REVIEW_DEFER)
  decision_display_name: str (from decision contract)
  decision_explanation: str (from decision contract)
  decision_policy_id: str (bremen_mri_continuation_threshold)
  decision_policy_version: str (0.1.0)
  probability: float (p_mri_needed)
  threshold_applied: float
  triage_recommendation: str (legacy compatibility, not used for display)

The Control Room renders decision_display_name and decision_explanation
as the primary decision text. It does not perform threshold comparison
in JavaScript. It does not interpret the decision_code independently.
It does not display MRI_RULE_OUT as public wording.

Decision visualization:
  A card with the decision_display_name as the headline.
  The score bar (probability vs threshold) for visual context
    (already approved for public display in existing result cards).
  The decision_policy_id as a metadata label.
  The scientifically_certified: false flag as a notice.
  A technical_demo_only: true notice.

Positive decision (CONTINUE_MRI):
  Card background: subtle blue/amber tone.
  Headline: "Continue MRI evaluation".

Negative decision (MRI_REVIEW_DEFER):
  Card background: subtle neutral tone.
  Headline: "Defer MRI pending clinician review".

No positive/negative CSS class based on display text interpretation.
The CSS class is derived from decision_code via an approved mapping
object, not from hardcoded string comparison against display text.

REPORT PROJECTION

The report link reads from the job API.

The report status is in:
  job.reports.bremen.status

The report endpoint is:
  GET /demo/api/jobs/{job_id}/reports/bremen

The Control Room shows:
  Report status (available, generating, failed, unavailable).
  Report schema version.
  Open button or link to fetch and display the report.
  When the report is available, clicking Open fetches the report
    JSON and displays it in the report panel area.

The report and the on-screen decision originate from the same
authoritative decision object (result_summary). The report provider
(BremenReportProvider) uses the same decision object. No second
decision path exists.

TECHNICAL READINESS

Technical readiness is obtained from:
  GET /model/version -> model_status field.
  GET /health -> model_ready field.

Displayed in the header as a badge. Values:
  ready: Model loaded and validated. Green badge.
  configured: Environment set but not yet loaded. Yellow badge.
  not_configured: Model environment not set. Grey badge.
  error: Model load or validation failed. Red badge with
    safe error category.

Also displayed in a "System Status" card:
  Server status (alive).
  Model status (from model/version endpoint).
  Workflow status (bremen provider readiness).
  Feature schema version.

SCIENTIFIC CERTIFICATION

Scientific certification is a separate badge next to technical readiness.

Current value: false (not certified).

The badge reads:
  Scientific certification: pending

This is always visible and distinct from technical readiness.
It does not change color based on technical readiness.
It does not imply clinical validation.

When scientifically_certified is false:
  The decision panel includes a notice:
  "Scientific certification: pending. This is a technical demo."

This notice is not visually alarming. It is informative and stable.

BACKEND CHANGES

Backend changes are minimal:

1. server.py:
   Change GET /demo dispatch from _handle_demo_route to
   _handle_control_room_route.
   Add lazy import of the control room page builder.

2. No changes to:
   workflow_bremen.py, workflow_orchestrator.py, workflow_provider.py
   event_schema.py, event_store.py, execution_trace.py
   report_bremen.py, report_aramis.py, report_provider.py
   decision_contract.py, lifecycle_contracts.py
   job_api_handler.py, job_models.py, model_state.py
   All existing API endpoints remain unchanged.

FRONTEND CHANGES

Frontend changes are concentrated in one new file:

1. New file: src/bremen/control_room_ui.py
   The Investor Control Room HTML page generator.
   Inline CSS and JavaScript. Standard library only.
   Self-contained, no external assets, no framework.
   Approximately 800-1000 lines.

   Layout:
     Header bar with model status and readiness badges.
     Left panel with source selection and model info.
     Center panel with 10-stage visual pipeline.
     Right panel with docked live event stream.
     Bottom panel with decision result and report link.

2. Modified file: src/bremen/api/server.py
   Add _handle_control_room_route function.
   Change GET /demo dispatch.
   Preserve GET /demo/workspace route for backward compatibility.

3. No changes to:
   workspace_ui.py (preserved as-is)
   demo_ui.py (preserved but no longer the default route)

API COMPATIBILITY

All existing API endpoints are unchanged:
  Response formats preserved.
  Status codes preserved.
  Error codes preserved.
  SSE protocol preserved.
  Event schema preserved.
  No new API routes required for the Control Room.
  The Control Room consumes existing GET /demo/api/jobs,
  GET /demo/api/jobs/{job_id}, GET /demo/api/jobs/{job_id}/events,
  GET /demo/api/jobs/{job_id}/events/stream,
  GET /demo/api/jobs/{job_id}/reports/bremen,
  GET /health, GET /model/version.

No API version bump required.

PRIVACY

All existing privacy allowlists are enforced.
The frontend never receives:
  Patient identifiers.
  H5 file paths or internal H5 structure.
  Dataset paths.
  Raw q or intensity arrays.
  Feature values or vectors.
  Model weights, coefficients, intercepts, scaler, imputer parameters.
  Reference distributions.
  Tracebacks or raw exception objects.
  Environment variables or credentials.

The existing prohibited detail keys in event_schema.py are effective.
The control room only renders fields that are already allowlisted
in the job API response and event details.

The only display of score/probability is p_mri_needed and threshold,
which are already approved for public display in the existing
decision support report and workspace result cards.

ACCESSIBILITY

Keyboard access:
  Tab through header badges, source selection, Analyze button,
  pipeline stages, event panel, decision card, report link.
  Enter or Space to trigger Analyze button and report link.
  Arrow keys to navigate pipeline stages.
  Escape to clear event filter or close expanded card.

Visible focus:
  All interactive elements have visible focus outline.
  Focus style respects prefers-contrast.

ARIA:
  Live event panel: aria-live="polite" on the event container.
  Pipeline: role="list" with role="listitem" for each stage.
  Header badges: role="status".
  Decision headline: role="alert" when result arrives.
  Analyze button: aria-label="Start analysis".

Reduced motion:
  prefers-reduced-motion media query disables all stage transitions.
  Pulse animation on active stage replaced by static bold border.
  Connector arrow animation replaced by static color change.
  No animation-dependent information.

Color:
  Status communicated by text and icon, not by color alone.
  Green check for completed. Spinner for active. Red X for failed.
  Grey dash for pending. Yellow exclamation for unavailable.
  Contrast ratio at least 4.5:1 for text, 3:1 for large text.

Responsive:
  Single column below 768px viewport width.
  Two-column between 768px and 1024px.
  Three-column above 1024px.
  Event panel collapses below event list header on narrow screens,
    expandable via toggle.

PERFORMANCE

Bounded DOM event history:
  Maximum 200 event rows rendered in the DOM.
  Events beyond 200 are dropped from the DOM oldest-first.
  Full history is always available via API.

Efficient rendering:
  Events are appended as DOM elements (no full list re-render).
  No innerHTML rebuild of the event list per event.
  Pipeline stages are updated by class toggling, not full rebuild.

No SSE duplication:
  One EventSource per tab. No polling during normal operation.
  Duplicate event_id suppression.

No unbounded growth:
  Event panel capped at 200 DOM elements.
  Pipeline stages fixed at 10.
  Header and summary panels fixed size.

No blocking operations:
  All calls are async (fetch, EventSource).
  No synchronous XHR.

Server thread behavior unchanged from PR0079.
One thread per SSE connection. 5-minute deadline.
ThreadingHTTPServer with daemon_threads.

TESTING

Behavioral tests for:

Default route:
  GET /demo returns HTML containing "Bremen" and
  "Should the patient continue to MRI?".
  GET /demo/workspace continues to return the old workspace.

Header:
  Model status badge rendered.
  Scientific certification badge rendered.
  Technical demo indicator rendered.

Source selection:
  Upload area or container list rendered when configured.
  Analyze button disabled when no source selected.
  Analyze button enabled when source selected.

Pipeline:
  All 10 stages rendered in order.
  Initial state shows all stages as pending.
  Event for a completed stage updates that stage to completed.
  Current active stage highlighted.
  Failed stage shows failure state.
  Missing stage shows pending, not skipped.

Event panel:
  Visible by default.
  Shows empty state before connection.
  Shows connecting state during EventSource open.
  Events rendered with sequence, timestamp, stage, type, status.
  Events received from real SSE stream.
  Auto-scroll enabled during live execution.
  Manual scroll pauses auto-scroll.
  Resume button re-enables auto-scroll.
  Duplicate event_id suppressed.
  Reconnect after cursor restores missed events.
  Maximum 200 DOM events.

Decision panel:
  CONTINUE_MRI displays approved positive display name.
  MRI_REVIEW_DEFER displays approved negative display name.
  No MRI_RULE_OUT in public wording.
  No threshold comparison in JavaScript.
  Score and threshold bar rendered when available.
  Scientific certification flag visible.
  Technical demo notice visible.

Report:
  Report link shown when report status is available.
  Report link hidden when report status is unavailable.
  Clicking link fetches and displays report.

SSE lifecycle:
  EventSource opened after job creation.
  Last-Event-ID sent on reconnect.
  stream_complete closes EventSource.
  Expired job returns 404 on reconnect attempt.

State machine:
  Correct transitions.
  Impossible states not rendered.
  New analysis resets to source_selected state.

Accessibility:
  Tab order navigable.
  aria-live on event panel.
  prefers-reduced-motion disables animations.
  Color not sole status indicator.
  Responsive layout.

Privacy:
  No patient identifiers in rendered HTML.
  No model parameters in rendered HTML.
  No tracebacks in rendered HTML.

Backward compatibility:
  GET /demo/workspace returns old workspace.
  GET /demo/workspace/{job_id} returns old workspace with job.
  All existing API endpoints respond correctly.
  SSE endpoints unchanged.

Frontend test strategy:
  Server-side HTML assertion: Parse the generated HTML and assert
  required elements, classes, data attributes exist.
  DOM simulation: Create a minimal DOM from the HTML string,
  expose JavaScript functions, call them with synthetic event data,
  assert DOM updates.
  Real HTTP integration: Start the test server, create a job,
  fetch the HTML, verify dynamic content renders correctly.
  SSE simulation: Use a real EventSource or socket against the
  test server, emit events, verify frontend state updates.

Existing tests that cover the old /demo HTML should continue to pass
(they test demo_ui.py directly, not via route dispatch).

VISUAL ACCEPTANCE

1. The Control Room is the first page shown at GET /demo.
2. The active workflow (Bremen) and real model version are visible
   without scrolling on a 1280x800 viewport.
3. The central pipeline is visually dominant (larger than the event
   panel, more prominent than source selection).
4. The current active stage is obvious (bold, animated connector
   or bright border).
5. The structured event panel is visible by default (not hidden
   behind a toggle) and occupies approximately 35 percent of width.
6. The event panel visibly updates from real SSE events within
   2 seconds of emission.
7. The decision panel uses approved PR0081 terminology
   (CONTINUE_MRI, MRI_REVIEW_DEFER). No MRI_RULE_OUT wording.
8. Technical readiness and scientific certification are both visible
   and distinct (separate badges, different colors, different labels).
9. The generated report is reachable from the completed state via a
   single click.
10. Failed and disconnected states show presentation-ready messaging
    (not raw tracebacks or developer error text).
11. No model selector is displayed.
12. The page remains usable at 768px viewport width (single column).
13. prefers-reduced-motion users see the same information without
    animated dependency.

DOCUMENTATION

Update docs/workspace_contract.md:
  Document new default route (GET /demo -> Control Room).
  Document Control Room regions (header, source selection, pipeline,
    event panel, decision panel, report access).
  Document that GET /demo/workspace is preserved.
  Document pipeline stage mapping from events.
  Document SSE lifecycle for the Control Room.
  Document decision and report projection.
  Document technical readiness and scientific certification display.

Update ROADMAP.md:
  Set current milestone to PR0082: Bremen Investor Control Room.
  Document that PR0083 (XRD preprocessing parity) is next.
  Document that PR0084 (scientific investigation) is separate.
  Document that PR0085 (model variants) is separate and blocked on
    additional model configurations.

No changes needed to docs/api_contract.md (API unchanged).
No changes needed to docs/release_readiness_operator_notes.md.

EXPECTED FILES

New files:
  src/bremen/control_room_ui.py
    Investor Control Room HTML page generator.
    Inline CSS and JavaScript.
    Approximately 800-1000 lines.

Modified files:
  src/bremen/api/server.py
    Add _handle_control_room_route function.
    Change GET /demo dispatch.
    Minimal change. Approximately 10 lines added, 1 line changed.

  ROADMAP.md
    Update current milestone.

  docs/workspace_contract.md
    Document new Control Room.

  tests/test_bremen_workspace_ui.py
    Add Control Room UI tests.
    Existing workspace UI tests remain unchanged.

  .project-memory/pr/0082-bremen-investor-control-room/implementation-report.md
    Generated during implementation.
    Records decisions, route inventory, real execution trace,
    state model, stage mapping, SSE lifecycle, deviations.

Files NOT modified:
  src/bremen/api/workflow_bremen.py
  src/bremen/api/workflow_orchestrator.py
  src/bremen/api/workflow_provider.py
  src/bremen/api/event_schema.py
  src/bremen/api/event_store.py
  src/bremen/api/execution_trace.py
  src/bremen/api/lifecycle_contracts.py
  src/bremen/api/decision_contract.py
  src/bremen/api/report_bremen.py
  src/bremen/api/report_aramis.py
  src/bremen/api/report_provider.py
  src/bremen/api/job_api_handler.py
  src/bremen/api/job_models.py
  src/bremen/api/model_state.py
  src/bremen/api/model_source.py
  src/bremen/api/app.py
  src/bremen/api/schemas.py
  src/bremen/api/jobs.py
  src/bremen/api/h5_layouts.py
  src/bremen/api/preflight.py
  src/bremen/api/preprocessing_bridge.py
  src/bremen/api/xrd_normalization.py
  src/bremen/api/runtime_plugin.py
  src/bremen/api/execution_context.py
  src/bremen/workspace_ui.py
  src/bremen/demo_ui.py
  src/bremen/demo_presentation.py
  src/bremen/demo_evidence.py
  src/bremen/inference.py
  All Docker, CI/CD, Terraform files

PR0083 BOUNDARY

PR0083 becomes: XRD Preprocessing Parity Investigation.

It owns:
  Parity between runtime xrd-preprocessing v0.1.5-beta and training
    pipeline v0.1.7-beta.
  Paper-reference versus product-contract preprocessing mapping.
  Feature computation verification.
  Preprocessing mathematics review.

PR0083 may begin after PR0082 is merged.
PR0083 does not change the Control Room.

PR0084 BOUNDARY

PR0084 becomes: Scientific Investigation and Model Baseline.

It owns:
  AUC 0.443 investigation.
  Training cohort selection review.
  QC-stage effects on model performance.
  Model retraining if warranted.
  Scientific certification evidence.

PR0084 may begin after PR0083 is complete.
PR0084 does not change the Control Room or decision vocabulary.

PR0085 BOUNDARY

PR0085 becomes: Provider-Owned Model Variants.

It owns:
  ModelVariantCatalog.
  ModelVariant dataclass.
  model_variant_id and model_run_id.
  Multiple model runs.
  Independent results and reports.
  Model selector.

PR0085 may begin only after additional real model configurations exist.
PR0085 does not change the one-model Control Room experience.

BLOCKERS

None at planning stage.

The real execution path is traceable end-to-end.
The decision contract from PR0081 is committed and provides canonical
vocabulary. The SSE endpoint works and supports concurrent clients
from PR0079. The one real Bremen model is loaded from ModelState.

No fabricated events are required.
No fabricated model availability is required.
No frontend-only fake execution engine is required.
No patient data or model internals are required to be exposed.

WARNINGS

The Control Room assumes the real configured model is available.
If BREMEN_MODEL_URI is not set at deployment time, the model_status
will be "not_configured" and the Control Room will show an informative
message rather than a full execution experience. This is acceptable
behavior for a demo that documents its dependencies.

The upload path (POST /demo/api/h5/containers) requires S3 storage
configuration. When storage is not configured, the Control Room shows
an informational message and the Analyze button is disabled. This
matches the current /demo behavior.

The /demo/api/h5/analyze endpoint is preserved for backward
compatibility but is not used by the Control Room. The Control Room
uses the structured /demo/api/jobs path instead. This means jobs
created via the old analyze endpoint will not appear in the Control
Room job list (they bypass the _jobs store). This is documented in
the workspace_contract update.
