PLAN COMPLETE

PLAN FILE

.project-memory/pr/0082a-control-room-data-selection/PLAN.md

HEAD

cfae8448e928cce0e6d16865b08f3429aeb7d9ee

BRANCH

0082a-control-room-data-selection

CURRENT ROUTES

All routes are defined in src/bremen/api/server.py, do_GET and do_POST methods.

Existing GET routes:
  /health -> handle_health
  /model/version -> handle_model_version
  /predictions/{uuid} -> handle_get_prediction
  /demo -> _handle_control_room_route (PR0082)
  /demo/workspace -> _handle_workspace_route
  /demo/workspace/{job_id} -> deep link in workspace route
  /demo/api/evidence -> _handle_demo_evidence_route
  /demo/api/h5/containers -> _handle_demo_h5_containers_list
  /demo/api/jobs -> _handle_demo_jobs_list (handle_jobs_list in job_api_handler)
  /demo/api/jobs/{job_id} -> handle_job_get
  /demo/api/jobs/{job_id}/events -> handle_job_events
  /demo/api/jobs/{job_id}/events/stream -> handle_job_events_stream (SSE)
  /demo/api/jobs/{job_id}/reports -> handle_job_reports
  /demo/api/jobs/{job_id}/reports/{workflow_id} -> handle_job_report

Existing POST routes:
  /predictions -> handle_submit_prediction (legacy)
  /demo/api/h5/containers -> _handle_demo_h5_containers_upload
  /demo/api/stage -> _handle_demo_stage (file upload staging)
  /demo/api/h5/analyze -> _handle_demo_h5_analyze (legacy analyze)
  /demo/api/jobs -> _handle_demo_jobs_create (handle_jobs_create in job_api_handler)

CURRENT INPUT CONTRACT

The Control Room (src/bremen/control_room_ui.py) currently uses two input paths:

1. File upload via POST /demo/api/stage (src/bremen/api/server.py line 1357).
   The endpoint accepts a raw H5 file body, writes it to a NamedTemporaryFile,
   and returns the local filesystem path as h5_path in the response.
   The frontend stores this path and sends it as h5_path in the job request.
   This exposes a local filesystem path to the browser and uses h5_path
   directly rather than an opaque source identifier.

2. S3 objects are listed by GET /demo/api/h5/containers (server.py, _list_s3_containers),
   but the Control Room does not currently consume this endpoint. The frontend
   only provides a file upload input (line 505: <input type="file">) and has no
   container selection UI.

CURRENT MODEL CONTRACT

There is no model catalog. The Control Room fetches /model/version and /health
to get model status and version. These show whether the single configured model
is loaded. There is no model selection mechanism. The job request always sends
workflow_id: "bremen" and does not include a model_id.

The single model is configured via environment variables BREMEN_MODEL_URI,
BREMEN_MODEL_VERSION, BREMEN_MODEL_CHECKSUM, loaded at server startup through
ModelState in src/bremen/api/model_state.py.

S3 CATALOG DESIGN

The existing _list_s3_containers function in server.py is the authoritative S3
listing mechanism. It reads BREMEN_DEMO_H5_BUCKET and BREMEN_DEMO_H5_PREFIX
from the environment. It filters to .h5 and .hdf5 extensions only. It returns
safe metadata: id (the S3 key), filename (basename), size_bytes, last_modified.

This function is used by GET /demo/api/h5/containers which the Control Room
currently does not call. The plan is to call this endpoint from the Control Room
JavaScript and present the returned containers as a selectable list.

No changes to the S3 listing logic itself. The existing endpoint already:
  Uses deployment IAM credentials implicitly (boto3 default credential chain).
  Filters supported H5 extensions.
  Rejects non-H5 objects.
  Returns opaque "id" (S3 key) rather than exposing the bucket.
  Does not accept AWS credentials from the browser.
  Does not expose credentials through APIs or logs.
  Does not allow browser-supplied bucket names.
  Returns unavailable state when bucket is not configured.
  Returns empty catalog when the prefix has no H5 files.

Additions to the existing endpoint:
  Filter objects exceeding BREMEN_DEMO_H5_MAX_BYTES (size_bytes > upload_max_bytes).
  Limit result count to a bounded maximum (e.g., 100 objects).
  Return the server-side upload_max_bytes value (already done in upload handler)
    so the frontend can filter client-side as well.
  Order results by last_modified descending (newest first).

The GET /demo/api/h5/containers response schema is unchanged:
  storage: "configured" | "not_configured" | "list_failed"
  containers: list of safe item dicts
  technical_demo_only: true

SOURCE IDENTITY

The current approach of using raw S3 keys (id field) and local filesystem paths
(h5_path) must be replaced with opaque validated source references.

Design: source_id is a server-generated opaque token created at the point when
the user selects a catalog object or uploads a file. The Control Room receives
source_id rather than a raw S3 key or filesystem path.

However, the minimum safe approach for PR0082a is to use the existing
container_id pattern (already used by POST /demo/api/h5/analyze) plus a new
uploaded_source_id. Specifically:

For S3 catalog objects:
  The existing containers endpoint returns id (which is the S3 key under the
  configured prefix). This is not a raw arbitrary S3 key - it is constrained
  to objects already listed under BREMEN_DEMO_H5_PREFIX. The server validates
  it server-side at job submission by reconstructing the full S3 URI and
  calling stage_h5_input. The id is opaque to the end user (they see display
  names derived from filename, not the key itself).

  The Control Room selects a container by its id, sends it as source_id in
  the job request body. The server revalidates by constructing
  s3://{bucket}/{prefix}{source_id} and attempting to stage the object.
  If the object no longer exists, or was tampered with, the staging call fails
  and returns a controlled error.

For uploaded files:
  The /demo/api/stage endpoint already stages the file to a temp path. However,
  it currently returns the raw local path. The plan is to return an opaque
  uploaded_source_id (a new UUID) that the server stores alongside the temp
  path in a new in-memory uploads registry. The browser sends this upload_id
  instead of h5_path.

  The uploads registry is:
    A new dict in job_api_handler.py: _staged_uploads: dict[str, StagedUpload]
    StagedUpload has: upload_id, h5_path (tempfile path), filename, size_bytes,
    created_at.
    Evicted after a timeout period or after the upload is consumed by a job.

  The POST /demo/api/stage response changes from:
    { "status": "staged", "h5_path": "/tmp/tmpXXXX.h5" }
  To:
    { "status": "staged", "upload_id": "opaque-uuid", "filename": "sample.h5",
      "size_bytes": 12345 }

  The job request accepts upload_id alongside source_id.

Validation rules for source identity at job submission:
  If source_id is provided: look up in S3 under configured prefix, re-verify
    extension, re-verify size.
  If upload_id is provided: look up in _staged_uploads registry.
  If neither provided: reject with error.
  If both provided: reject with error.
  If source is unknown, stale, oversized, unsupported: reject with typed error.
  No raw S3 key from the browser is accepted without server-side revalidation.
  No local filesystem path from the browser is accepted.

INPUT CATALOG API

The existing GET /demo/api/h5/containers endpoint is the input catalog API.
No new route is needed. The Control Room calls this endpoint and presents the
results as a selectable list.

Additions to the endpoint (server.py _handle_demo_h5_containers_list):
  Add upload_max_bytes to the response so the frontend can display limits.
  Filter oversized objects server-side.
  Limit result count to 100 objects maximum.
  Order by last_modified descending.

The Control Room JavaScript:
  Fetches GET /demo/api/h5/containers on page load.
  Renders the list of available containers with display_name (filename),
    size, and last_modified.
  Allows clicking one to select it. The selected source_id is stored.
  Selected container remains displayed until job creation or explicit
    deselection.
  Refresh button re-fetches the list but does not silently clear the
    current selection.
  If the selected container disappears from the refreshed list, the
    selection is marked as stale and the job creation is blocked.

UPLOAD PATH

When BREMEN_DEMO_H5_ALLOW_UPLOAD is true, the Control Room shows the file
upload input in addition to the container list.

The upload flow is:
  1. User selects a local H5 file.
  2. Frontend sends the file to POST /demo/api/stage.
  3. Server stages the file to a tempfile, stores the mapping in
     _staged_uploads.
  4. Server returns { status: "staged", upload_id: "...", filename: "...",
     size_bytes: ... }.
  5. Frontend stores upload_id as the selected source. The upload_id is
     used in the subsequent job request.

When upload is disabled, the file input is hidden.

MODEL CATALOG DESIGN

Create a new server-owned Bremen model catalog.

Implementation: A new module src/bremen/api/model_catalog.py containing:
  ModelEntry dataclass:
    model_id: str
    display_name: str
    workflow_id: str
    model_version: str
    artifact_type: str
    feature_schema_version: str
    decision_policy_id: str
    decision_policy_version: str
    technical_ready: bool
    scientifically_certified: bool
    technical_demo_only: bool
    availability: str  # "available" | "unavailable" | "not_configured"

  build_model_catalog() function:
    Reads the current ModelState to build catalog entries.
    With the existing single-model configuration, returns one entry:
      model_id: "bremen-current"
      display_name: "Bremen Current"
      workflow_id: "bremen"
      model_version: from ModelState._model_version
      artifact_type: "portable_logreg"
      feature_schema_version: "v0.1"
      decision_policy_id: "bremen_mri_continuation_threshold"
      decision_policy_version: "0.1.0"
      technical_ready: ModelState.is_ready()
      scientifically_certified: false
      technical_demo_only: true
      availability: "available" if ready else "unavailable"

    When no model is configured, returns an empty list or an entry with
    availability: "not_configured".

  The catalog is rebuilt on every call so it reflects current model state
  without requiring server restart.

  Privacy: No artifact URIs, S3 model keys, local paths, checksums,
  coefficients, weights, intercepts, scaler values, imputer values, or
  reference distributions are exposed.

MODEL CONFIGURATION

The authoritative configuration mechanism remains the existing environment
variables (BREMEN_MODEL_URI, BREMEN_MODEL_VERSION, BREMEN_MODEL_CHECKSUM)
loaded through ModelState in src/bremen/api/model_state.py.

For PR0082a, the model catalog adapter reads this single configuration and
exposes it as one catalog entry. No structured multi-model configuration
mechanism is added. The single-model legacy configuration is the only
configuration format. Precedence is unambiguous because there is only one
source of configuration.

MODEL SELECTION CONTRACT

New endpoint: GET /demo/api/models
  Returns the model catalog built by model_catalog.build_model_catalog().
  Response:
    schema_version: "v1"
    models: list[ModelEntry]
    default_model_id: str or null
    status: "available" | "not_configured" | "error"

The Control Room fetches this endpoint on page load and presents the
available model(s). With the current single-model configuration, the
model is pre-selected as the default. The frontend renders model metadata
from this response rather than from the previous /model/version endpoint.

Job request changes:
  The job request body gains an optional model_id field.
  When present, the server resolves model_id against the catalog.
  When absent and the catalog has exactly one available model, the
  server uses it as the default.
  When absent and the catalog has zero or multiple available models,
  the server rejects the request with a typed error.
  The model_id must be known and available.
  Incompatible model (wrong workflow, wrong feature schema) is rejected.
  The selected model is bound to the job before execution begins.

Server-side validation (in job_api_handler.py handle_jobs_create):
  1. Parse model_id from request body.
  2. If absent, attempt default resolution.
  3. Call model_catalog.resolve_model(model_id) which validates:
     - model_id exists in catalog
     - model.availability == "available"
     - model.workflow_id matches the requested workflow
  4. Pass the resolved model_id through to the orchestrator and provider.

JOB REQUEST CONTRACT

The job request for the new Control Room contract:

{
  "workflow_id": "bremen",
  "model_id": "bremen-current",
  "source_id": "container-key-from-catalog",
  "upload_id": null
}

OR

{
  "workflow_id": "bremen",
  "model_id": "bremen-current",
  "upload_id": "uuid-from-stage-endpoint",
  "source_id": null
}

Exactly one of source_id or upload_id must be present.
model_id is required unless exactly one model is available (then default).

The existing h5_path and container_id fields are preserved as legacy
compatibility inputs.

Validation rules:
  If source_id is provided, reconstruct the S3 URI and validate the
    object exists with correct size and extension.
  If upload_id is provided, look up in _staged_uploads and validate
    the temp path exists.
  If model_id is provided, validate against catalog.
  If model_id is absent, attempt default resolution.
  Reject with typed error code on any validation failure.

SOURCE RESOLUTION

Server-side source resolution (new function in job_api_handler.py):

_resolve_source(source_id: str | None, upload_id: str | None) -> str
  Returns the resolved local filesystem h5_path for the orchestrator.

  If source_id: read demo_config, construct
    s3://{bucket}/{prefix}{source_id}, call existing stage_h5_input from
    h5_inputs.py.
  If upload_id: look up in _staged_uploads dict, return stored h5_path.
  If neither: raise ValueError with typed error.
  If staging fails: raise ValueError with typed safe error.

The resolved path is passed to run_workflow_request as the existing h5_path
parameter. The orchestrator code is unchanged.

Cleanup: For S3-staged files, the existing stage_h5_input lifecycle applies
(tempfile deleted by tempfile cleanup or process exit). For uploaded files,
the _staged_uploads entry is removed after the job completes or after a
timeout period.

MODEL BINDING

The selected model is bound to the job record and propagated through:

1. Job record (AnalysisJob.input_summary.model_id)
2. WorkflowRun.model_identity (model_id, model_version)
3. WorkflowResult payload (decision fields already include model metadata)
4. Events (runtime events already include model_id and model_version in details)
5. Execution trace (safe_summary fields already include model identity)
6. Report metadata (model_id, model_version already in ReportMetadata)
7. Report content (report payload already includes model identity)
8. Job API response (workflow_run result_summary already includes model_version)

The model identity is set once at job creation and never changed. No fallback
model is substituted. No model switching occurs after the job starts.

JOB HISTORY

The existing list_analysis_jobs() and get_analysis_job() functions already
provide structured job history. The Control Room already fetches the job list
at page load (line 204-205 in control_room_ui.js: fetch("base_url+/demo/api/jobs")).

For PR0082a, the history summary must include:
  model_id
  model_display_name
  source_display_name (from input_summary)
  decision_display_name (from workflow run result)
  report_available

These are added to the job list response and the Control Room rendering.

The existing history already has: job_id, created_at, overall_status,
requested_workflows.

The Plan: Extend the list_analysis_jobs() response to include a summary
of the first workflow run and its decision outcome. Add a detail card
when a historical job is selected.

Legacy POST /demo/api/h5/analyze jobs are not imported into the _jobs store.
The Control Room clearly states that only jobs created through POST /demo/api/jobs
appear in history.

WORKSPACE CONNECTIVITY

The workspace screenshot reports "Cannot reach server." The base_url
construction was fixed in PR0081a (commit cfae844) to use
X-Forwarded-Proto header for correct HTTPS handling when behind a load
balancer. The control room already uses this pattern:

  forwarded_proto = handler.headers.get("X-Forwarded-Proto", "http")
  base_url = f"{forwarded_proto}://{host_header}"

The workspace_ui.py was also fixed. The Control Room uses
base_url from the server (injected into JavaScript at render time as
__BASE_URL__). All fetch calls use this base_url. No hardcoded hostnames.

No additional connectivity changes are needed for PR0082a beyond:
  Ensuring the /demo/api/stage, /demo/api/jobs, and /demo/api/models
  endpoints are reachable from the same origin.
  Using X-Forwarded-Proto consistently.
  Verifying all fetch calls use the server-supplied base_url.

DECISION AND REPORT CONSISTENCY

The approved PR0081 decision contract is used:
  decision_code: CONTINUE_MRI or MRI_REVIEW_DEFER
  decision_policy_id: bremen_mri_continuation_threshold
  decision_policy_version: 0.1.0

The selected model_id is propagated to the report provider through the
WorkflowRun.model_identity dict. The report provider (BremenReportProvider)
uses this dict to set model_id and model_version in the ReportEnvelope
and report payload.

No frontend threshold comparison. No MRI_RULE_OUT public wording.

BACKWARD COMPATIBILITY

Preserve:
  GET /demo/workspace (unchanged)
  GET /demo/workspace/{job_id} (unchanged)
  GET /health (unchanged)
  GET /model/version (unchanged)
  POST /predictions (unchanged)
  GET /predictions/{job_id} (unchanged)
  POST /demo/api/h5/containers (unchanged response, enhanced filtering)
  POST /demo/api/h5/analyze (unchanged, legacy)
  POST /demo/api/stage (response extended with upload_id, h5_path kept for compat)
  GET /demo/api/jobs (extended with additional summary fields)
  POST /demo/api/jobs (extended with model_id, source_id, upload_id;
    existing h5_path and container_id fields preserved as legacy compat inputs)
  GET /demo/api/jobs/{job_id} (unchanged response structure, enriched fields)
  Existing SSE protocol (unchanged)
  Existing report routes (unchanged)

Schema versioning: No version bump is required for this PR. The existing
responses are additive (new fields added, no fields removed). The legacy
h5_path field is preserved in job requests.

PRIVACY

Additions to the privacy allowlist:

Model catalog:
  model_id: safe (stable opaque string)
  display_name: safe (controlled display name)
  workflow_id: safe
  model_version: safe
  artifact_type: safe
  feature_schema_version: safe
  decision_policy_id: safe
  decision_policy_version: safe
  availability: safe

Not exposed:
  Artifact URI, S3 model key, local path, checksum, coefficients,
  weights, intercepts, scaler values, imputer values, reference
  distributions, patient identifiers.

Upload staging:
  upload_id: safe (opaque UUID)
  filename: safe (user-provided basename only)
  size_bytes: safe

Not exposed:
  Local temp path, bucket name (unless already approved), raw S3 key
  (the id field is the S3 key but it is constrained to the configured
  prefix and not exposed as a public filesystem path).

FAILURE STATES

Input catalog loading: Show loading spinner. On failure, show
"Container catalog unavailable. Check storage configuration." with
retry button.

Input catalog empty: "No H5 containers found in configured storage."

Input catalog not configured: "H5 storage not configured. Set
BREMEN_DEMO_H5_BUCKET to enable container selection."

Upload disabled: File input hidden.

Upload too large: "File exceeds maximum upload size of {max_bytes}."
Rejected server-side with 413 status.

Upload invalid format: "Only .h5 and .hdf5 files are accepted."

Source disappears after selection: When the user clicks analyze and
the source is no longer available (stale), job creation returns a typed
error. "The selected source is no longer available. Please select
another container or re-upload."

Model catalog loading: Show loading spinner. On failure, show
"Model catalog unavailable."

Model not configured: "No Bremen model is configured. Analysis is
unavailable. Configure BREMEN_MODEL_URI to enable model execution."

Model unavailable: "The selected model is not ready. Model status: {status}."

Job submission rejected: Show the typed error from the server response.
"Cannot create analysis: {reason}" with specific error code.

S3 download failure: "Could not download the selected source from storage."
Normalization failure, workflow failure, SSE failure, historical job expired:
Existing safe error handling applies.

TESTING

Behavioral tests for:

S3 catalog listing:
  List objects under configured prefix returns only H5/HDF5 files.
  Objects outside prefix excluded.
  Non-H5 extensions excluded (.txt, .pdf, .csv).
  Oversized objects excluded (size > upload_max_bytes).
  Results limited to 100.
  Ordered by last_modified descending.
  Catalog unavailable (bucket not configured) returns storage: "not_configured".
  Catalog empty returns empty containers list.
  Storage failure returns storage: "list_failed".
  No AWS credentials in response.

Source identity:
  source_id resolved to S3 URI under configured prefix.
  Unknown source_id rejected.
  Stale source_id (object deleted) fails staging.
  Source outside prefix rejected.
  Upload_id resolved to temp path.
  Unknown upload_id rejected.
  Upload_id consumed by a job cannot be reused.
  Upload_id evicted after timeout.

Model catalog:
  Model catalog returns one entry from ModelState.
  Model catalog empty when no model configured.
  Model catalog fields are privacy-allowlisted.
  No artifact URI or path exposed.

Model selection:
  model_id in job request selects the correct model.
  Unknown model_id rejected.
  Unavailable model rejected.
  Default model used when exactly one available and no model_id sent.
  Default not applied when zero models available.
  Default not applied when multiple models available (future scenario).

Job request contract:
  Valid source_id + valid model_id creates job.
  Valid upload_id + valid model_id creates job.
  source_id and upload_id both absent rejected.
  source_id and upload_id both present rejected.
  h5_path legacy compat still works (backward compat test).

Source resolution:
  S3 source staged and resolved to temp path.
  Upload source resolves to temp path.
  Staging failure returns typed error.
  Cleanup after terminal job (upload registry entry removed).

Model binding:
  model_id appears in job record input_summary.
  model_id appears in WorkflowRun.model_identity.
  model_version appears in WorkflowResult payload.
  model_id appears in report metadata.
  model_id consistent across all surfaces.

Job history:
  list_analysis_jobs returns decision_display_name for completed jobs.
  Historical job can be reopened and displays selected model.
  Legacy /demo/api/h5/analyze jobs not in history.

Decision and report consistency:
  PR0081 decision code used.
  MRI_RULE_OUT not displayed as public wording.
  Report and decision from same authoritative source.

Connectivity:
  All fetch calls use server-supplied base_url.
  X-Forwarded-Proto respected.
  Health endpoint reachable on same origin.

Privacy:
  No local paths exposed in API responses.
  No S3 bucket names exposed (unless already approved).
  No model artifact URIs exposed.
  No model parameters exposed.

Tests use fake S3 clients and synthetic non-private test fixtures.
No network calls to AWS in tests.

DOCUMENTATION

Update docs/workspace_contract.md:
  Document input catalog endpoint (GET /demo/api/h5/containers).
  Document model catalog endpoint (GET /demo/api/models).
  Document source_id and upload_id contract.
  Document model selection contract.
  Document job request schema (model_id, source_id, upload_id).
  Document backward compatibility with h5_path.
  Document history behavior (only structured jobs).
  Document upload registry lifecycle.
  Document failure states.

Update docs/api_contract.md:
  Document GET /demo/api/models response schema.
  Document expanded job request fields.

Update docs/release_readiness_operator_notes.md:
  Document model catalog and selection behavior.
  Document upload registry and temp file lifecycle.

Update ROADMAP.md:
  Set current milestone to PR0082a: Control Room Data and Selection Foundation.
  Keep PR0082b as the next visual redesign milestone.
  Keep PR0083, PR0084, PR0085 as documented.

PR0082B DEPENDENCY

PR0082b (visual redesign) depends on PR0082a being merged. PR0082b owns:
  Layout, typography, visual hierarchy, responsive product polish.
  Animations and motion design.
  Presentation mode and final visual acceptance.
  No data or selection contract changes.

EXPECTED FILES

New files:
  src/bremen/api/model_catalog.py
    ModelEntry dataclass.
    build_model_catalog() function.
    resolve_model() function.

Modified files:
  src/bremen/api/server.py
    Add GET /demo/api/models route dispatch.
    Update _handle_demo_stage to return upload_id.
    Update _handle_demo_h5_containers_list to filter oversized,
      limit to 100, sort by last_modified, include upload_max_bytes.
    Add _handle_demo_models handler (lazy import to model_catalog).

  src/bremen/api/job_api_handler.py
    Add _staged_uploads dict and lock.
    Add _resolve_source function.
    Update handle_jobs_create to accept model_id, source_id, upload_id.
    Update create_analysis_job to accept model_id.
    Extend list_analysis_jobs to include workflow run summary.
    Add upload registry cleanup logic.

  src/bremen/api/workflow_provider.py
    Add model_id parameter to execute() signature (optional, default None).

  src/bremen/api/workflow_bremen.py
    Pass model_id through execute and run_inference.
    Include model_id in WorkflowResult payload if provided.
    model_id already appears in events via existing code.

  src/bremen/api/workflow_orchestrator.py
    Accept model_id parameter in run_workflow_request.
    Pass to provider.execute(model_id=...).

  src/bremen/control_room_ui.py
    Add container list fetch and render.
    Add model catalog fetch and render.
    Add source selection state (catalog or upload).
    Add model selection state (single model pre-selected).
    Update job request to send source_id or upload_id and model_id.
    Add history panel with decision display.
    Add controlled failure states.
    Update base_url usage (already fixed).

  src/bremen/api/report_bremen.py
    Ensure selected model_id is propagated through report.
    (Already reads from model_identity dict, which already gets model_id.)

  ROADMAP.md
    Update current milestone.

  docs/workspace_contract.md
    Document new contracts.

  docs/api_contract.md
    Document model catalog response.

  docs/release_readiness_operator_notes.md
    Document model catalog and upload registry.

  tests/test_bremen_model_catalog.py (new)
    Model catalog tests.

  tests/test_bremen_data_selection.py (new)
    Source identity, upload registry, job request contract tests.

  tests/test_bremen_control_room.py
    Add Control Room data selection tests.

  .project-memory/pr/0082a-control-room-data-selection/implementation-report.md (new)

Files NOT modified:
  src/bremen/api/event_schema.py
  src/bremen/api/event_store.py
  src/bremen/api/job_models.py
  src/bremen/api/decision_contract.py
  src/bremen/api/lifecycle_contracts.py
  src/bremen/api/execution_trace.py
  src/bremen/api/runtime_plugin.py
  src/bremen/api/execution_context.py
  src/bremen/api/model_state.py
  src/bremen/api/schemas.py
  src/bremen/api/app.py
  src/bremen/api/jobs.py
  src/bremen/api/h5_layouts.py
  src/bremen/api/preflight.py
  src/bremen/api/preprocessing_bridge.py
  src/bremen/api/xrd_normalization.py
  src/bremen/api/report_provider.py
  src/bremen/api/report_aramis.py
  src/bremen/inference.py
  src/bremen/demo_ui.py
  src/bremen/demo_presentation.py
  src/bremen/demo_evidence.py
  src/bremen/workspace_ui.py
  All Docker, CI/CD, Terraform files

BLOCKERS

None at planning stage.

The configured S3 prefix is accessible through deployment IAM (the existing
_list_s3_containers and stage_h5_input functions already use boto3 with
default credential chain). Safe server-side source identity is implementable
via the existing container_id pattern and a new upload registry. The single
configured model is available through ModelState. The provider architecture
supports passing model_id through execute() without redesign.

No fake or unavailable model entries would populate the selector (only the
real configured model appears). No real patient data is required to test the
flow (synthetic fixtures work). No model mathematics, preprocessing,
thresholds, or decision policy changes are required.

WARNINGS

The upload registry (_staged_uploads) is in-memory and ephemeral. If the
server restarts, all uploaded but unconsumed files are lost. This is
acceptable for a technical demo. The registry only holds uploaded files,
not S3 catalog objects (those are re-staged on each job request).

The model catalog uses the current ModelState at call time. If the model
is loaded after the Control Room page renders but before the job is created,
the catalog will show the updated state. If the model becomes unavailable
between catalog fetch and job creation, the job will fail with a typed
error. Retry with a refreshed catalog resolves this.

The single-model legacy configuration means the model selector shows one
pre-selected option. The model selection UI is minimal (informational card,
not a dropdown). When future model configurations exist, the selection UI
will need enhancement, but this PR provides the contract.
