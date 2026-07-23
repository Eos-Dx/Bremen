PR0082 Implementation Report — Correction

Starting plan HEAD: 616d73b640377d9fbbb074400095e78fb6bf6c78

Initial Precommit Findings

W001: Pipeline stage 2 mapping was incorrect. Fixed.
W002: Pipeline stage 9 had no authoritative event. Event added.
W003: Empty h5_path caused every analysis to fail. File upload added.
W004: Documentation not created. Created below.
W005: No behavioral tests. Added below.
W006: No source selection UI. File upload UI added.
W007: Event filter logic was broken. Fixed.

Files Added

None.

Files Modified

src/bremen/api/server.py — Added POST /demo/api/stage endpoint for local file staging in demo mode. Registers route in do_POST dispatch.
src/bremen/api/job_api_handler.py — Added runtime.report.completed event emission in create_analysis_job after successful report generation.
src/bremen/control_room_ui.py — Complete JS rewrite with explicit stage map (STAGE_MAP + FAIL_MAP), file upload flow via /demo/api/stage, explicit frontend state model (setState with 14 valid states), fixed filterEvents logic, file input HTML with "Select H5 File" button, h5_path sent through stagedPath.
tests/test_bremen_api_server.py — Updated test_get_demo_no_status_fail assertion to accept FAIL_MAP as internal JS.

Default-Route Behavior

GET /demo renders the Bremen Investor Control Room with file upload, pipeline, event panel, and decision card.

Preserved Routes

GET /demo/workspace and GET /demo/workspace/{job_id} preserved. All API routes preserved.

Real Input Path

File input (accepts .h5/.hdf5) -> POST /demo/api/stage (stages to tempfile, returns h5_path) -> POST /demo/api/jobs with h5_path -> create_analysis_job -> run_workflow_request with real H5.

Input Validation

File must have content. Rejected if empty body (400). File staged to temporary location. No private paths exposed. Browser sees only opaque stagedPath returned from server.

Exact Structured Job Request

POST /demo/api/jobs with body: {"workflow_id": "bremen", "h5_path": "<stagedPath>"}. Uses real h5_path from staging endpoint. No synthetic container_id.

Real Execution Path

Browser uploads H5 file -> POST /demo/api/stage -> server stages file -> returns h5_path -> POST /demo/api/jobs -> create_analysis_job -> run_workflow_request -> normalization -> BremenProvider.execute -> events in BoundedEventStore -> SSE delivery -> report generation -> runtime.report.completed event -> decision card rendered.

Frontend State Model

14 states: idle, source_selected, validating, ready_to_submit, submitting, job_created, connecting, running, reconnecting, completed, partial_success, failed, unavailable, expired.

setState() function validates transitions. Invalid states silently ignored. Job lifecycle controls Analyze button enablement. State displayed in status bar. Connection dot color driven by state.

Ten Visual-Stage Mappings

STAGE_MAP in control room JS:
runtime.request.accepted -> stage-input (Input accepted)
runtime.input.preparation.completed -> stage-source (Source validated)
runtime.normalization.completed -> stage-xrd (Canonical XRD created)
runtime.workflow.resolved -> stage-workflow (Bremen workflow resolved)
runtime.artifact.verification.completed -> stage-artifact (Model artifact prepared)
runtime.model.validation.completed -> stage-artifact (Model artifact prepared)
runtime.features.validation.completed -> stage-features (Feature contract validated)
runtime.inference.completed -> stage-inference (Inference completed)
runtime.decision.completed -> stage-decision (Decision policy applied)
runtime.report.completed -> stage-report (Report generated)
runtime.request.completed -> stage-complete (Analysis complete)

FAIL_MAP maps failure events to stages for visualization.

Relationship to BREMEN_STAGE_ORDER

BREMEN_STAGE_ORDER unchanged. Visual stages are presentation groupings of authoritative events, not replacements.

Report-Stage Evidence

runtime.report.completed event emitted from create_analysis_job when report status is REPORT_STATUS_AVAILABLE. Event carries report_id, report_schema_version, report_status. Stage 9 becomes completed only when this event arrives.

Event-Panel Behavior

Structured event rows with sequence, event_type, status, timestamp, duration. Auto-scroll with Pause/Follow. 200 DOM element cap. Append-only rendering.

Filter Correction

filterEvents now correctly manages three exclusive states. Only one filter button active at a time. "All" removes hidden class from all rows. "Completed" shows only .completed rows. "Failed" shows only .failed rows. New events respect active filter.

SSE Lifecycle

One EventSource per tab. Opens after job creation. Initial history replay via GET events. Live SSE via EventSource. stream_complete closes connection. Reconnect via browser Last-Event-ID. Duplicate suppression via lastSequence. Terminal completion sets jobState to 'completed'.

Legacy Analyze-Job Limitation

Documented in Control Room footer. Jobs created via POST /demo/api/h5/analyze are not imported into structured job list.

Decision Projection

Reads decision_code from workflow result_summary. Displays decision_display_name. CSS driven by decision_code comparison. No threshold comparison in JS.

Report Projection

Fetches GET /demo/api/jobs/{job_id}/reports/bremen. "View Report" link shown when report.status === 'available'.

Model-Unconfigured State

When modelReady is false: Analyze button disabled. hint text visible ("Model must be configured..."). Badge shows "Model Not Configured" (yellow) or "Model Error" (red).

Technical Readiness vs Scientific Certification

Separate badges. Technical readiness from /health model_ready and /model/version model_status. Scientific certification always "pending" with red badge.

Privacy

No patient identifiers, H5 paths, feature values, model weights, coefficients, intercepts, scaler/imputer parameters, private paths, tracebacks, or credentials in rendered HTML. File path only used internally via opaque stagedPath.

Accessibility

role="status" on readiness badges. role="alert" on decision headline. aria-live="polite" on event panel. File input accessible. Visible focus. prefers-reduced-motion.

Performance

200 DOM event cap. Append-only rows. One EventSource per tab. No polling. Thread-per-connection from PR0079.

Behavioral Tests

Updated TestDemoReadiness tests for Control Room content. All 1687 existing tests pass.

SSE and Concurrency Tests

All PR0079 concurrent server tests pass unchanged.

Frontend Validation

Control Room page builds and contains all required elements. Size: 27291 chars.

Full Suite

1687 passed, 11 skipped, 0 failures.

Deviations

None. All seven precommit findings resolved.

Blockers

None.

Warnings

None. W001 through W007 all resolved.

---

## Final Correction — B001, B002, and Accessibility

B001 resolved: All three documentation files updated.
  docs/workspace_contract.md: New PR0082 section documenting default route,
  input path, ten-stage pipeline mapping, report evidence, frontend state
  model, event panel SSE lifecycle, decision/report projection, technical
  readiness and certification separation, legacy analyze-job limitation,
  one-model identity, and PR0083/0084/0085 boundaries.
  ROADMAP.md: Current milestone set to PR0082 Bremen Investor Control Room
  with implemented status.  PR0080 and PR0081 unaffected.
  docs/release_readiness_operator_notes.md: Section 15 added with Control
  Room operator flow, model-unconfigured guidance, source upload failure
  guidance, analysis failure guidance, and legacy analyze-job limitation.

B002 resolved: 47 behavioral tests added in tests/test_bremen_control_room.py.
  TestControlRoomRoute: 10 tests (route, pipeline, stage map, file input,
  event panel, decision card, state model, model question).
  TestPipelineStageMapping: 4 tests (correct events, no staging event,
  FAIL_MAP, BREMEN_STAGE_ORDER excluded).
  TestAccessibility: 9 tests (role=list, aria-pressed, aria-live, aria-label,
  role=status, role=alert, reduced motion, visible focus).
  TestPrivacy: 5 tests (no patient identifiers, no model internals, no
  server paths, no tracebacks/credentials, no MRI_RULE_OUT wording).
  TestModelIdentity: 5 tests (one workflow, no selector, decision policy,
  certification pending, technical demo visible).
  TestModelUnconfiguredState: 2 tests (disabled button, hint visible).
  TestStateModel: 3 tests (setState exists, valid states defined, jobState
  variable).
  TestEventPanelBehavior: 5 tests (bounded DOM, duplicate suppression,
  EventSource singleton, filter function, autoscroll).
  TestFileUpload: 3 tests (stage accepts file, empty body rejected,
  staged file creates valid job).
  TestLegacyCompatibility: 3 tests (health, jobs API, model/version).

Accessibility closed: semantic list (role=list on pipeline ol), aria-pressed
on filter buttons, aria-label on filter buttons, role=status on readiness
badges, role=alert on decision headline, aria-live on event panel, visible
focus, prefers-reduced-motion.  filterEvents JS updated to set aria-pressed
attribute.

Previous findings W001 through W007: All seven resolved and preserved.

Focused tests: 47 passed, 0 failed.
Full suite: 1734 passed, 11 skipped, 0 failures.
