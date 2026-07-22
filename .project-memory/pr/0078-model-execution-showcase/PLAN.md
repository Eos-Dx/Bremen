# PR 0078 — Model Runtime Plugin Tracing and Investor Showcase

## Objective

Turn the existing multi-workflow Analysis Workspace into a clear, visually compelling, event-driven investor demonstration that shows how each workflow executes internally.

The interface must answer:
- What input was accepted?
- How was it normalized?
- Which workflow was selected?
- Which model artifact was prepared?
- Which contract was validated?
- How many features were produced?
- Did inference execute?
- Which decision policy was applied?
- Was a report generated?
- What is technically ready?
- What remains scientifically uncertified?

The UI must visualize actual execution, not a simulated progress animation.

The runtime architecture must support:

```
CanonicalXRDCase → WorkflowRegistry → WorkflowRuntimePlugin
  → artifact verification
  → artifact adaptation
  → model validation
  → workflow input preparation
  → feature construction
  → feature validation
  → inference
  → output validation
  → decision policy
  → report provider
→ structured execution trace
→ workflow result
```

## Current Foundation

PR0075–PR0077 provide:
- canonical XRD normalization via CanonicalXRDCase
- explicit workflow registry (WorkflowRegistry → WorkflowProvider)
- independent Bremen and Aramis providers
- public runtime orchestration (run_workflow_request)
- structured job events (JobEvent, EventType enum, 24 typed event types)
- bounded ephemeral event storage (BoundedEventStore)
- SSE live delivery with Last-Event-ID reconnect
- workflow-specific reports (ReportEnvelope, ReportProvider)
- Analysis Workspace UI (timeline, workflow cards, process panel, audit view)
- Four-zone privacy boundaries with prohibited-detail validation
- Module-level event store in job_api_handler._event_store

**The remaining problem**: The model/provider execution boundary is still insufficiently explicit and visually understandable. Users can see that a workflow completed, but cannot clearly see:
- model artifact preparation
- compatibility adaptation
- validation
- input preparation
- feature generation
- inference
- decision application
- report generation

Current provider.execute() collapses all stages into one opaque call. Events are emitted at workflow/orchestrator level, not at individual lifecycle stages.

## Product Goal

Add an investor-facing showcase mode that communicates technical credibility without exposing proprietary or sensitive internals.

The experience should create confidence through:
- real live stages
- clear model identity/version
- contract validation
- durations
- counts
- typed outcomes
- visible technical vs scientific readiness
- workflow isolation
- honest unavailable/not-started states

Do not create credibility through decorative fake activity.

## Scientific and Security Boundary

Never expose:
- model coefficients, intercepts, imputer statistics, scaler parameters
- raw feature vectors or feature values
- raw q/intensity arrays
- raw H5 datasets
- PONI contents
- patient identifiers
- operator identifiers
- private paths
- tracebacks
- model-package internals
- training data

Safe model execution metadata:
- workflow_id, plugin_id, plugin_version
- model_id, model_version, model_schema_version, feature_schema_version
- feature_count, expected_feature_count, missing_feature_count, non_finite_feature_count
- measurement_count
- decision_policy_id, report_schema_version
- duration_ms
- typed reason codes
- scientifically_certified

Score and threshold may be displayed only where the existing workflow result/report contract explicitly permits them (Bremen's p_mri_needed and threshold_applied).

## Scope

- Formal runtime plugin lifecycle (WorkflowRuntimePlugin)
- Explicit execution context (WorkflowExecutionContext)
- Typed intermediate contracts (PreparedArtifact, PreparedWorkflowInput, FeatureSet, FeatureValidation, ModelOutput, OutputValidation, DecisionOutput)
- Per-stage structured events (28 new event types for artifact, input, feature validation, output validation stages)
- Bremen lifecycle instrumentation
- Aramis lifecycle boundary (early stop at readiness check)
- Model execution trace API fields
- Investor showcase frontend mode
- Visual pipeline (stage-by-stage)
- Per-model execution timeline
- Stage detail drawer
- Model identity and contract cards
- Decision visualization
- Process panel linking
- Responsive/accessibility work
- Plugin isolation tests
- Event-order tests
- Privacy tests
- Roadmap update

## Non-Goals

This PR does **not**:
- Define Bremen P1/P2/P3 science
- Train, tune, calibrate, or replace models
- Certify Bremen scientifically
- Implement missing Aramis science
- Combine model results
- Diagnose disease
- Replace clinicians
- Expose model weights or coefficients
- Fabricate feature importance
- Implement explainability not already supported
- Add candidate-model shadow inference
- Add offline evaluation or replay
- Redesign Docker, App Runner, or CI/CD
- Add a persistent event database

## Existing Provider Architecture

```
WorkflowRegistry
→ WorkflowProvider (abstract)
  → BremenProvider
    → readiness()
    → validate_compatibility()
    → build_features()
    → run_inference()
    → execute()  -- monolithic
  → AramisProvider (scaffold)
    → readiness()
    → validate_compatibility()  -- always compatible
    → execute()  -- returns unavailable
```

The `execute()` method is a single opaque call. Events are emitted by the orchestrator at the workflow level, not by individual lifecycle stages within the provider.

## Target Runtime Plugin Contract

Do not replace the existing `WorkflowProvider` contract. Create a `WorkflowRuntimePlugin` that a provider may optionally compose into its `execute()` method, or that the orchestrator may call instead of `execute()` where the provider supports it.

Conceptual interface:

```python
class WorkflowRuntimePlugin:
    workflow_id: str
    plugin_id: str
    plugin_version: str

    def readiness(self, context: WorkflowExecutionContext) -> WorkflowReadiness
    def prepare_artifact(self, context: WorkflowExecutionContext) -> PreparedArtifact
    def prepare_input(self, canonical_case, context) -> PreparedWorkflowInput
    def build_features(self, prepared_input, context) -> FeatureSet
    def validate_features(self, features, context) -> FeatureValidation
    def run_model(self, artifact, features, context) -> ModelOutput
    def validate_output(self, output, context) -> OutputValidation
    def apply_decision(self, output, context) -> DecisionOutput
    def build_report(self, decision, context) -> ReportEnvelope
```

The plugin is NOT a second registry. The `WorkflowRegistry` remains authoritative. The plugin is owned by the provider and called from within its `execute()` or from the orchestrator when the provider exposes it.

The existing `WorkflowProvider.execute()` method is preserved for backward compatibility. Providers that implement `WorkflowRuntimePlugin` advertise this via an `implements_plugin` flag or protocol check.

## Execution Context

```python
@dataclass(frozen=True)
class WorkflowExecutionContext:
    job_id: str
    request_id: str
    workflow_id: str
    runtime_build_version: str
    event_sink: EventSink  # callable protocol
    started_at: str
    deadline: int | None  # optional max duration seconds
```

Requirements:
- All identifiers are non-empty strings
- `event_sink` is a callable protocol: `(event: JobEvent) -> None`
- No hidden lookup of global event store from provider code
- No placeholder IDs
- No patient identifiers
- Provider cannot emit events for another workflow
- Lifecycle remains testable without HTTP

## Intermediate Contracts

Safe typed objects representing lifecycle boundaries:

```python
@dataclass(frozen=True)
class PreparedArtifact:
    model_id: str
    model_version: str
    model_schema_version: str
    checksum_status: str  # "verified" | "not_configured" | "failed"
    adaptation_applied: bool
    validation_status: str
    details: dict  # safe metadata only

@dataclass(frozen=True)
class PreparedWorkflowInput:
    layout: str
    measurement_count: int
    side_count: int
    position_count: int
    compatibility_ok: bool
    details: dict

@dataclass(frozen=True)
class FeatureSet:
    feature_schema_version: str
    feature_names: tuple[str, ...]  # names only, not values
    produced_count: int
    missing_count: int
    non_finite_count: int
    details: dict

@dataclass(frozen=True)
class FeatureValidation:
    feature_schema_version: str
    expected_count: int
    produced_count: int
    order_valid: bool
    all_finite: bool
    details: dict

@dataclass(frozen=True)
class ModelOutput:
    output_schema: str
    output_count: int
    output_names: tuple[str, ...]  # names only
    details: dict

@dataclass(frozen=True)
class OutputValidation:
    schema_valid: bool
    output_count: int
    all_finite: bool
    details: dict

@dataclass(frozen=True)
class DecisionOutput:
    decision_policy_id: str
    decision_code: str  # "MRI_RECOMMENDED" | "MRI_RULE_OUT" | etc.
    scientifically_certified: bool
    details: dict
```

These objects expose metadata, counts, versions, and validation status.
They do **not** automatically serialize full feature values, model weights, raw arrays, or unsafe model package objects.

## Lifecycle State Machine

### Normal Bremen path:
```
workflow resolved
→ artifact verification
→ artifact loaded
→ artifact adapted
→ model validated
→ input prepared
→ features produced
→ features validated
→ inference completed
→ output validated
→ decision completed
→ report completed
→ workflow completed
```

### Nova (configuration required):
```
workflow resolved
→ input compatibility evaluated
→ workflow_configuration_required
→ feature stage not started
→ inference not started
→ report unavailable
```

### Aramis unconfigured:
```
workflow resolved
→ readiness evaluated
→ workflow_unavailable
→ model stages not started
→ report unavailable
```

Rules:
- Block impossible event ordering
- Do not emit a completed event without a corresponding started event where the stage actually executes
- A skipped stage emits `runtime.<stage>.skipped` — it does not emit `started`/`completed`

## New Event Types (28 additions to EventType enum)

```python
# Artifact lifecycle
ARTIFACT_VERIFICATION_STARTED = "runtime.artifact.verification.started"
ARTIFACT_VERIFICATION_COMPLETED = "runtime.artifact.verification.completed"
ARTIFACT_LOAD_STARTED = "runtime.artifact.load.started"
ARTIFACT_LOAD_COMPLETED = "runtime.artifact.load.completed"
ARTIFACT_ADAPTATION_STARTED = "runtime.artifact.adaptation.started"
ARTIFACT_ADAPTATION_COMPLETED = "runtime.artifact.adaptation.completed"
MODEL_VALIDATION_STARTED = "runtime.model.validation.started"
MODEL_VALIDATION_COMPLETED = "runtime.model.validation.completed"

# Input preparation
INPUT_PREPARATION_STARTED = "runtime.input.preparation.started"
INPUT_PREPARATION_COMPLETED = "runtime.input.preparation.completed"
INPUT_PREPARATION_FAILED = "runtime.input.preparation.failed"

# Feature validation
FEATURES_VALIDATION_STARTED = "runtime.features.validation.started"
FEATURES_VALIDATION_COMPLETED = "runtime.features.validation.completed"
FEATURES_VALIDATION_FAILED = "runtime.features.validation.failed"

# Output validation
OUTPUT_VALIDATION_STARTED = "runtime.output.validation.started"
OUTPUT_VALIDATION_COMPLETED = "runtime.output.validation.completed"
OUTPUT_VALIDATION_FAILED = "runtime.output.validation.failed"

# Report extension
REPORT_UNAVAILABLE = "runtime.report.unavailable"

# Skipped stages
STAGE_SKIPPED = "runtime.stage.skipped"
```

The existing `EventType` enum from PR0077 already contains 24 event types. These 28 additions bring the total to 52.

## Artifact Stages

Safe event details for artifact stages:
```json
{
  "model_id": "bremen_mri_triage_logreg",
  "model_version": "v0.1",
  "model_checksum": "sha256:abc...",
  "checksum_status": "verified",
  "adaptation_applied": true,
  "validation_status": "completed"
}
```

**Critical rule**: Do not claim checksum verification when no trusted checksum was configured. The checksum_status must be one of: `verified`, `not_configured`, `failed`.

## Input Preparation Stages

Safe event details:
```json
{
  "layout": "canonical",
  "measurement_count": 2,
  "side_count": 2,
  "position_count": 1,
  "compatible": true,
  "selected_workflow_policy": "first_left_right_pair"
}
```

Nova with unresolved P1/P2/P3 must stop at `input_preparation.failed` with reason `workflow_configuration_required`. It must not emit feature or inference completion events.

## Feature Stages

Safe event details for feature construction:
```json
{
  "feature_schema_version": "v0.1",
  "expected_feature_count": 15,
  "produced_feature_count": 15
}
```

Safe event details for feature validation:
```json
{
  "feature_schema_version": "v0.1",
  "expected_count": 15,
  "produced_count": 15,
  "missing_count": 0,
  "unexpected_feature_count": 0,
  "non_finite_count": 0,
  "feature_order_valid": true,
  "schema_matched": true
}
```

Do not expose: feature values, coefficients, patient-specific contribution values, invented feature importance.

## Inference Stages

Safe event details:
```json
{
  "model_id": "bremen_mri_triage_logreg",
  "model_version": "v0.1",
  "output_schema": "bremen_logreg_output_v1",
  "output_names": ["probability", "prediction", "triage_recommendation"],
  "output_count": 3
}
```

Output validation safe details:
```json
{
  "schema_valid": true,
  "output_count": 3,
  "all_finite": true
}
```

A score may appear only in workflow result/report surfaces already approved for that score. The general technical timeline should not reveal extra proprietary model output.

## Decision Stages

Safe event details:
```json
{
  "decision_policy_id": "bremen_threshold_v1",
  "decision_code": "MRI_RECOMMENDED",
  "scientifically_certified": false
}
```

Bremen decision language must remain: "Should the patient continue to MRI?"

Do not add: diagnosis language, biopsy recommendations, malignant-pattern claims, clinician replacement claims.

## Report Stages

Add `runtime.report.unavailable` for scenarios where a report is not generated.

Safe event details:
```json
{
  "report_schema_version": "v0.2",
  "report_status": "available",
  "reason_code": null
}
```

For unavailable:
```json
{
  "report_schema_version": "v0.1",
  "report_status": "unavailable",
  "reason_code": "WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED"
}
```

A report failure must not erase completed inference or decision.

## Execution Trace Projection

Add to the job API response an `execution_trace` field per workflow:

```json
{
  "execution_trace": {
    "workflow_id": "bremen",
    "current_stage": "report",
    "completed_stage_count": 10,
    "total_applicable_stage_count": 11,
    "started_at": "2026-07-22T00:00:00Z",
    "completed_at": null,
    "duration_ms": 142,
    "stages": [
      {
        "stage_id": "artifact_verification",
        "label": "Artifact verification",
        "status": "completed",
        "started_at": "...",
        "completed_at": "...",
        "duration_ms": 3,
        "safe_summary": {"model_id": "bremen_mri_triage_logreg"},
        "reason_code": null
      }
    ]
  }
}
```

The trace is derived from structured events, not from a second divergent lifecycle state in the frontend.

## Event Schema Changes

No schema version bump required for PR0078. The same `SCHEMA_VERSION = "1"` continues, with the addition of new `EventType` enum members.

The `details` field in `JobEvent` continues to use the same privacy allowlist (prohibited keys from PR0077).

## Bremen Instrumentation

Bremen's `execute()` or a new `WorkflowRuntimePlugin.execute_with_trace()` will be instrumented to emit stage events at each lifecycle boundary.

Current Bremen boundaries to instrument:
1. **Artifact**: `_adapt_package()`, `__init__()` where model_package is set
2. **Validation**: `_validate_model_internal()` — current structured logging replaced with `runtime.model.validation.completed` event
3. **Compatibility**: `validate_compatibility()` — becomes `runtime.input.preparation.completed`
4. **Features**: `build_features()` — emits `runtime.features.started` and `runtime.features.completed`
5. **Feature validation**: New stage validating feature vector against expected schema
6. **Inference**: `run_inference()` — emits `runtime.inference.started` and `runtime.inference.completed`
7. **Output validation**: New stage validating inference output structure
8. **Decision**: Decision policy application — emits `runtime.decision.completed`
9. **Report**: Delegates to `BremenReportProvider`

Do not duplicate Bremen feature construction. Do not change the 15-feature order. Do not change numerical behavior. Do not make Bremen scientifically certified.

## Aramis Boundary

The Aramis provider must expose the same plugin lifecycle interface even where the runtime is unavailable.

```
workflow resolved → readiness checked → workflow_unavailable
  → model lifecycle not started
  → feature not started
  → inference not started
  → report unavailable
```

Expected trace for Aramis:
```json
{
  "execution_trace": {
    "workflow_id": "aramis",
    "current_stage": "unavailable",
    "completed_stage_count": 1,
    "total_applicable_stage_count": 1,
    "stages": [
      {
        "stage_id": "readiness",
        "label": "Workflow readiness",
        "status": "completed",
        "safe_summary": {"configured": true, "model_ready": false},
        "reason_code": null
      }
    ]
  }
}
```

Do not fabricate deeper stages. Do not recreate Aramis scientific runtime.

## Job API Changes

Extend existing responses with `execution_trace`:

| Method | Path | Change |
|--------|------|--------|
| `GET` | `/demo/api/jobs/{job_id}` | Add `execution_trace` per workflow |
| `GET` | `/demo/api/jobs/{job_id}/reports/{workflow_id}` | Unchanged |

The `execution_trace` is projected from stored events at query time, not stored separately.

Add optional query parameter:
`GET /demo/api/jobs/{job_id}/events?stage=artifact&workflow=bremen`
for filtered event queries.

## Event Sink Protocol

Define a simple callable protocol for decoupled event emission:

```python
class EventSink(Protocol):
    def __call__(self, event: JobEvent) -> None: ...
```

Implementation at the orchestrator level wraps `BoundedEventStore.append()`.

The provider and plugin receive `EventSink` via the `WorkflowExecutionContext`, not via a direct store reference.

## Investor Showcase

New route or view mode: `/demo/workspace?view=showcase`

or a standalone route `/demo/showcase/{job_id}`.

Use the same real APIs and event stream as the technical workspace.

Do **not** use:
- static mock jobs
- fake timers
- random progress
- pre-scripted stage completion
- invented model results

The showcase must render from the same `/demo/api/jobs/{job_id}` and `/demo/api/jobs/{job_id}/events` endpoints.

## Visual Pipeline

Central visual pipeline showing stages in order:

```
Input → Canonical XRD → Workflow Plugin → Model Contract → Features → Inference → Decision → Report
```

Requirements:
- Current stage highlighted with subtle animation
- Completed stages distinctly checked
- Failed/blocked/not-started states visually distinct
- Status communicated by text AND icon (not color alone)
- Event-driven transitions
- Subtle motion only (CSS transitions, ~300ms)
- `prefers-reduced-motion` support
- No implication that blocked stages executed

Stage connectors animate only when the corresponding runtime event confirms the transition.

## Workflow Execution Cards

Extended version of PR0077's workflow cards with expanded execution mode:

Show:
- workflow name
- plugin ID/version
- model ID/version
- technical readiness (configured, model_ready)
- scientific certification (scientifically_certified flag)
- current stage name
- completed stage count / total stages
- duration
- decision status
- report status

The card must be generated from workflow data. Unknown workflows must use a generic fallback showing only common fields and a "stage execution not available" notice.

## Stage Detail Drawer

Clicking a stage opens a safe detail drawer.

Example — feature stage:
```
Feature contract
Schema: bremen_features_v1
Expected: 15  Produced: 15  Missing: 0  Non-finite: 0
Order: valid
Duration: 18 ms
```

Example — model stage:
```
Model contract
Model: bremen_mri_triage_logreg v0.1
Output schema: bremen_logreg_output_v1
Outputs: probability, prediction, triage_recommendation
Checksum: verified
Duration: 4 ms
```

Stage details must be allowlisted per stage type. Do not show feature values or coefficients.

## Decision Visualization

Where a workflow result contains an approved score and threshold, display a clear decision visualization.

For Bremen:
```
MRI continuation assessment
Score: 0.85  Threshold: 0.5
Decision: MRI_RECOMMENDED
Scientifically certified: false
Technical demo only
```

Requirements:
- Score and threshold labels explicit
- No probability interpretation beyond existing result contract
- No diagnosis wording
- No clinical-certification implication
- Visible technical-demo-only notice

When no score exists, render a typed unavailable/configuration-required state instead of an empty chart.

## Process Panel Integration

Retain Process and Technical modes from PR0077.

Add:
- Filters by workflow, model lifecycle stage, status
- Click a process event to highlight the corresponding visual pipeline stage
- Bidirectional linking: pipeline stage selection scrolls process panel to matching events

Do not display raw logs.

## Plugin Provenance

Expose safe provenance:
```json
{
  "workflow_id": "bremen",
  "plugin_id": "bremen_mri_triage_plugin",
  "plugin_version": "v0.1",
  "provider_class": "BremenProvider",
  "model_id": "bremen_mri_triage_logreg",
  "model_version": "v0.1",
  "feature_schema_version": "v0.1",
  "decision_policy_id": "bremen_threshold_v1",
  "report_schema_version": "v0.2",
  "runtime_build_version": "sha:abc123",
  "configuration_digest": "sha:def456"
}
```

Avoid filesystem/module paths in public APIs.

## Privacy

The existing four-zone privacy model from PR0077 is extended:

New prohibited detail keys for stage events:
- `feature_value` — individual feature values
- `coefficient` — model coefficient values
- `scaler_mean` — scaler parameter
- `scaler_scale` — scaler parameter
- `imputer_value` — imputer statistic
- `intercept` — model intercept
- `raw_feature_vector` — full vector
- `model_coefficients` — already prohibited

Existing privacy tests must pass with the additional keys.

## Accessibility

Investor-facing does not mean inaccessible.

Requirements:
- All interactive elements have aria-labels
- Keyboard navigation for all sections (tab, enter, escape, arrow keys)
- Status conveyed by text label AND icon (not color alone)
- Color contrast meets WCAG AA minimum (4.5:1 for text)
- `prefers-reduced-motion` respected (no animation when enabled)
- No flashing or strobing effects
- Stage list is a semantic `<ol>` with `<li>` items
- Screen reader announces stage transitions
- Responsive layout (flexbox, min-width 320px)
- Clean large-screen presentation (max-width 1400px centered)

## Performance

The tracing layer must have bounded overhead:
- Normal Bremen run: approximately 20 events (started+completed for ~10 stages)
- Each event: ~500 bytes serialized JSON
- Total overhead per run: ~10 KB for events
- Event store bounds apply (max 1000 events per job)
- UI event processing: < 50ms for full trace reconstruction
- SSE: events delivered within < 100ms of emission

No event is emitted for every numerical operation or feature. Events represent meaningful lifecycle stages only.

## Testing Strategy

**Backend tests** (extend `tests/test_bremen_event_stream.py`):
- Plugin lifecycle order (artifact → input → features → inference → decision → report)
- Execution context validation (no empty identifiers)
- Artifact-stage events (verification, load, adaptation, validation)
- Feature-stage events (construction + validation)
- Inference-stage events (inference + output validation)
- Decision-stage events
- Report-stage events
- Started/completed pairing per stage
- Impossible-order rejection (no inference event before features event)
- Nova early stop (no feature/inference events after configuration_required)
- Aramis unavailable early stop (no model/inference events after workflow_unavailable)
- Bremen full trace (all stages present in order)
- Provider isolation (Bremen events not affecting Aramis)
- Plugin provenance fields
- Safe stage details (no coefficient exposure, no feature-value exposure)
- No raw arrays in event details
- Event-store bounds preserved under stage event load
- SSE replay reconstructs execution trace
- Module-reload safety
- Report failure isolation

**Frontend tests** (extend `tests/test_bremen_workspace_ui.py`):
- Showcase route/mode rendering
- Investor summary header
- Real API data rendering (not mock data)
- Visual pipeline with all stage states (active, completed, blocked, not-started, failed)
- Per-workflow execution card with expanded mode
- Stage detail drawer with correct fields per stage type
- Feature-contract view (expected vs produced counts, no values)
- No weights or coefficients in rendered output
- Bremen decision visualization
- Certification pending state
- Nova configuration-required state
- Aramis unavailable state
- Unknown workflow generic fallback
- Event click highlights corresponding pipeline stage
- SSE reconnect/late subscriber reconstruction
- Terminal job stops animation
- Keyboard navigation (tab through pipeline stages, enter opens drawer)
- Reduced motion (prefers-reduced-motion disables animations)
- Responsive layout (narrow screen fallback)
- Privacy (no prohibited fields in rendered HTML)

## Existing CI/CD

Reuse existing pipeline in `.github/workflows/quality.yml` and `ecr-publish.yml`.

Additions:
- Existing test files are extended (not replaced) — pytest auto-discovers new test classes
- No new Docker build stages
- No new cloud infrastructure
- No new dependencies

## Roadmap Update

Replace ROADMAP.md's "Next milestone" section with:

### Current milestone (PR0078):

```
Model Runtime Plugin Tracing and Investor Showcase
- Formal WorkflowRuntimePlugin lifecycle contract
- Execution context with explicit event sink
- Typed intermediate contracts (PreparedArtifact, FeatureSet, ModelOutput, etc.)
- 28 new lifecycle event types (artifact, input, feature validation, output validation)
- Lifecycle state machine with ordering rules
- Bremen instrumentation for all lifecycle stages
- Nova (configuration-required) early-stop trace
- Aramis unavailable lifecycle boundary
- Execution trace projection in job API
- Investor showcase mode (real API, real SSE, live visualization)
- Visual pipeline (stage-by-stage layout)
- Per-model expanded execution cards
- Stage detail drawer (allowlisted per-stage metadata)
- Decision visualization (score/threshold where approved)
- Process panel ↔ pipeline bidirectional linking
- Plugin provenance display
- Accessibility (keyboard, WCAG AA, reduced motion)
- Privacy enforcement (extended prohibited-key list)
```

### Next milestone:

```
- Authoritative Aramis runtime integration
- Aramis report parity
- Persistent job/event history (database backend)
- PDF/report artifact storage
- Bremen scientific parity evidence
- Bremen P1/P2/P3 policy
- Report access controls
```

### Later milestone:

```
- Additional workflow providers
- Long-term audit retention
- Operational dashboards
- Cross-version report comparison
- Certification evidence bundles
- Role-based report access
- Offline replay framework
- Candidate-model comparison
- Feature parity reports
```

## Implementation Sequence

20 incremental gates:

1. **Execution context** — WorkflowExecutionContext, EventSink protocol
2. **Typed lifecycle contracts** — PreparedArtifact, PreparedWorkflowInput, FeatureSet, FeatureValidation, ModelOutput, OutputValidation, DecisionOutput
3. **Event schema extension** — 28 new EventType enum members
4. **Lifecycle state machine** — Ordering rules, started/completed pairing, stage_skipped
5. **WorkflowRuntimePlugin interface** — Plugin contract, protocol check from provider
6. **Event sink wiring** — Wire EventSink through orchestrator → execution context → plugin
7. **Artifact stage events** — verification, load, adaptation, validation events in Bremen prep
8. **Input preparation stage** — compatibility check → input_preparation events
9. **Feature stage** — feature construction + feature validation events in BremenProvider
10. **Feature validation** — validation counts, order, finiteness
11. **Inference stage** — inference started/completed events
12. **Output validation** — output validation events
13. **Decision stage** — decision policy application events
14. **Report stage** — report generation events
15. **Nova/Aramis early-stop trace** — lifecycle ends at configuration_required/unavailable
16. **Execution trace projection** — derive execution_trace from stored events
17. **Job API extension** — add execution_trace field, filtered event queries
18. **Showcase frontend** — visual pipeline, expanded cards, stage drawer, decision viz
19. **Process panel linking** — bidirectional highlight between pipeline and process log
20. **Accessibility, privacy, roadmap** — final polish

## Expected Files to Change

### New files:
- `src/bremen/api/runtime_plugin.py` — WorkflowRuntimePlugin interface, EventSink protocol
- `src/bremen/api/lifecycle_contracts.py` — Typed intermediate contracts (PreparedArtifact, FeatureSet, ModelOutput, DecisionOutput, etc.)
- `src/bremen/api/execution_context.py` — WorkflowExecutionContext dataclass
- `src/bremen/api/lifecycle_state_machine.py` — Ordering rules, sequence validation
- `src/bremen/api/execution_trace.py` — Trace projection from stored events
- `src/bremen/showcase_ui.py` — Investor showcase HTML page generator
- `tests/test_bremen_runtime_plugin.py` — Plugin lifecycle and trace tests

### Modified files:
- `src/bremen/api/event_schema.py` — Add 28 new EventType enum members, extend prohibited keys
- `src/bremen/api/workflow_provider.py` — Add WorkflowRuntimePlugin protocol check, optional event_sink
- `src/bremen/api/workflow_bremen.py` — Instrument with lifecycle stage events
- `src/bremen/api/workflow_aramis.py` — Instrument with early-stop trace
- `src/bremen/api/workflow_orchestrator.py` — Wire EventSink through execution context
- `src/bremen/api/job_api_handler.py` — Add execution_trace to job responses, filtered event queries
- `src/bremen/api/server.py` — Register showcase route, pass event_store to handlers
- `src/bremen/workspace_ui.py` — Add showcase mode, visual pipeline, expanded cards, stage drawer
- `tests/test_bremen_event_stream.py` — Add lifecycle stage tests, event ordering, early-stop
- `tests/test_bremen_workspace_ui.py` — Add showcase UI tests, stage drawer, decision viz
- `ROADMAP.md` — Update current milestone to PR0078
- `docs/workspace_contract.md` — Document event schema additions, execution trace

### Files NOT modified:
- `src/bremen/api/xrd_normalization.py` — No changes to canonical normalization
- `src/bremen/api/h5_layouts.py` — No changes to layout detection
- `src/bremen/api/preflight.py` — No changes to preflight
- `src/bremen/api/preprocessing_bridge.py` — No changes to preprocessing
- `src/bremen/inference.py` — No changes to inference math
- `src/bremen/api/model_state.py` — No changes to model loading
- `src/bremen/api/model_source.py` — No changes to model source resolution
- `src/bremen/api/report_bremen.py` — No changes to report schema
- `src/bremen/api/report_aramis.py` — No changes to report boundary
- `src/bremen/api/report_provider.py` — No changes to report contract
- `src/bremen/api/jobs.py` — No changes to InMemoryJobStore
- `src/bremen/api/schemas.py` — No changes to response schemas
- Docker files — No changes
- CI/CD workflows — No changes
- Terraform — No changes

## Risks

| Risk | Mitigation |
|------|------------|
| Plugin interface duplicates provider contract | Plugin is a composable stage layer owned by provider, not a second registry. Provider.execute() is preserved for backward compatibility |
| Stage events cause unbounded store growth | Normal run ~20 events. Max 1000 per job. Well within bounds. Tested. |
| Failed plugin not detected | Each stage has try/except with explicit failure event. Orchestrator validates plugin support before calling |
| Feature values accidentally logged | Prohibited keys list extended. Validate_event_details called on every append. Privacy tests verify |
| UI overwhelms investor with detail | Default view shows summary with expandable drawers. Technical depth on demand |
| Animation implies fake execution | Only real event-driven transitions. No timers, no progress bars, no simulated stages. Reduced-motion supported |
| Process panel and pipeline diverge | Both derived from same event store. Pipeline stages are events. Bidirectional linking forces consistency |
| Trace ordering violated | Lifecycle state machine validates ordering at emission. Tests verify impossible-order rejection |

## Stop Conditions

Stop planning with a blocker if:
- A lifecycle stage cannot be mapped to real code
- UI would need fake stage progression
- Model weights would need to be exposed
- Feature values would need to be logged
- Bremen numerical behavior would need to change
- Aramis stages would need to be fabricated
- Training/evaluation code would enter production runtime
- A second competing plugin registry would be required
- Provider code would need hidden global event state
- Private artifacts would enter Git

## Acceptance Criteria

### Gate 1: Runtime plugin contract pass
- WorkflowRuntimePlugin interface defined with all lifecycle methods
- EventSink protocol defined and wired through execution context
- Provider can advertise plugin support via protocol check
- execute() preserved for backward compatibility

### Gate 2: Execution context pass
- WorkflowExecutionContext with non-empty identifiers
- Event sink injected explicitly, no hidden global state
- No patient identifiers in context
- Provider cannot emit events for another workflow

### Gate 3: Lifecycle order pass
- Bremen trace order: artifact → input → features → inference → decision → report
- Nova trace: input compatibility → configuration_required (stop)
- Aramis trace: readiness → unavailable (stop)
- No completion event without corresponding started event
- Impossible-order events rejected

### Gate 4: Bremen trace pass
- All 10 lifecycle stages emit started/completed events
- Feature validation reports counts (expected, produced, missing, non-finite)
- Output validation reports schema validity
- Decision reports policy ID and decision code
- Report reports schema version and status

### Gate 5: Nova early-stop trace pass
- Input compatibility evaluated
- Workflow_configuration_required status
- No feature/inference/report events emitted
- Trace shows stopped stage

### Gate 6: Aramis unavailable trace pass
- Readiness evaluated
- Workflow_unavailable status
- No model/lifecycle events emitted
- Trace shows stopped stage

### Gate 7: Safe provenance pass
- plugin_id, plugin_version, model_id, model_version exposed
- No filesystem paths
- No model coefficients
- No feature values

### Gate 8: Execution trace projection pass
- Trace derived from stored events (not separate state)
- current_stage matches last active event
- completed_stage_count matches completed events
- Stage durations match
- Reconnect from SSE reconstructs correct trace

### Gate 9: Showcase UI pass
- Showcase route renders without errors
- Uses same real API endpoints (no mock data)
- Visual pipeline shows all stages
- Active stage highlighted
- Completed stages marked
- Blocked states clearly distinguished

### Gate 10: Stage drawer pass
- Click opens drawer with correct fields per stage
- Feature stage shows expected/produced/missing/non-finite counts
- Model stage shows output names and checksum status
- No feature values or coefficients shown
- Drawer closes on Escape or click outside

### Gate 11: Decision visualization pass
- Bremen score and threshold displayed
- Decision code displayed
- Scientifically_certified flag displayed
- Technical-demo-only notice visible
- No score states render unavailable/configuration_required

### Gate 12: Process panel linking pass
- Click event highlights pipeline stage
- Pipeline stage selection scrolls to matching events
- Bidirectional synchronization maintained on SSE updates

### Gate 13: Accessibility pass
- Keyboard navigation through all sections
- Status conveyed by text + icon (not only color)
- prefers-reduced-motion disables animations
- Stage list is semantic <ol>
- Color contrast meets WCAG AA

### Gate 14: Privacy pass
- No prohibited keys in any stage event
- Prohibited key list extended with feature_value, coefficient, scaler_*, imputer_*, intercept
- Existing privacy tests pass
- No patient identifiers in any rendered output

### Gate 15: Roadmap pass
- ROADMAP.md current milestone set to PR0078
- Next/later milestones accurately reflect remaining work
- No false claims about scientific certification

### Gate 16: Full regression pass
- All existing PR0075–PR0077 tests pass
- New plugin lifecycle tests pass
- New showcase UI tests pass
- No regressions in event storage, SSE, or privacy

### Gate 17: Deployment smoke pass
- Server starts with new routes
- Workspace loads in browser
- Showcase mode renders with real data
- Visual pipeline updates from live SSE events

---

**PLAN COMPLETE: yes**

PLAN FILE: `.project-memory/pr/0078-model-execution-showcase/PLAN.md`
HEAD: `b0ae6cadb45981725b7f0d0a10781bb3ac7d6a9c`
BRANCH: `0078-model-execution-showcase`
TARGET PLUGIN CONTRACT: WorkflowRuntimePlugin interface in runtime_plugin.py — composable stage layer owned by provider, not a second registry
EXECUTION CONTEXT: WorkflowExecutionContext with EventSink protocol — no hidden global state, no patient identifiers
LIFECYCLE STATE MACHINE: Formal ordering rules — Bremen (10 stages), Nova (early stop), Aramis (early stop) — impossible-order rejection
SAFE EVENT MODEL: 28 new EventType members, extended prohibited keys (feature_value, coefficient, scaler_*, imputer_*, intercept)
BREMEN INSTRUMENTATION: All 10 lifecycle stages emit started/completed events — artifact → input → features → inference → decision → report
NOVA EARLY STOP: Input compatibility → configuration_required — no feature/inference/report events
ARAMIS BOUNDARY: Readiness → unavailable — no model/lifecycle events
TRACE PROJECTION: execution_trace derived from stored events at query time, not separate state
INVESTOR SHOWCASE: `/demo/workspace?view=showcase` — real APIs, real SSE, no mock data, no fake timers
VISUAL PIPELINE: Input → XRD → Plugin → Contract → Features → Inference → Decision → Report — event-driven transitions
STAGE DETAILS: Allowlisted per stage — feature contract shows counts only, model shows output names only — no coefficients/values
DECISION VISUALIZATION: Score + threshold + decision code + scientific certification flag — no diagnosis language
PRIVACY: Extended prohibited-key list, four-zone model preserved, all existing privacy tests pass
ACCESSIBILITY: Keyboard nav, text+icon status, prefers-reduced-motion, semantic <ol>, WCAG AA contrast
ROADMAP UPDATE: Current = PR0078, Next = Aramis integration + persistent storage, Later = more providers + dashboards
IMPLEMENTATION SEQUENCE: 20 incremental gates from execution context through deployment smoke
EXPECTED FILES: 6 new files, 12 modified files
BLOCKERS: None — all stop conditions checked and clear
WARNINGS: None
