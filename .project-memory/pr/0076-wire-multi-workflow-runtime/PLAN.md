# PR 0076 — Plan Wire Canonical Multi-Workflow Runtime into Public Inference Paths

Author: plan
Mode: planning only
Branch: 0076-wire-multi-workflow-runtime

## Objective

Connect the canonical XRD normalization, workflow registry, Bremen provider, Aramis provider, and per-workflow model state introduced in PR0075 to the actual public runtime entry points (`_handle_demo_h5_analyze`, `run_inference`, `/predictions`). After this PR, the public paths must resolve workflows through the registry and providers, not through the legacy preflight/preprocessing/inference pipeline.

## Production Evidence

- 1495 tests pass.
- PR0075 created `WorkflowProvider`, `WorkflowRegistry`, `WorkflowBremenProvider`, `WorkflowAramisProvider`, `CanonicalXRDCase`, `normalize_to_canonical()` on all adapters.
- PR0075 did NOT wire any of these into public routes.
- `_handle_demo_h5_analyze` (server.py:1037) calls `run_inference(str(staged_path))`.
- `run_inference` (inference_handler.py:35) calls `run_h5_preflight`, `run_preprocessing_bridge`, `validate_portable_logreg_model`.
- `preprocessing_bridge.py` has `_extract_matador_profiles` for legacy Matador raw path.
- `adapt_model_package()` is NOT in `inference.py` (spike-only, not merged).
- Deployed logs show Nova reaches `_extract_matador_profiles` and fails with "No PONI calibration text found" — proving the canonical path is not connected.
- Aramis-style container hits `target_scan_ref must be a non-empty string` — proving workflow routing is not connected.

## Root Cause

PR0075 implemented and tested the new architecture as isolated components with unit tests. The public route integration — `_handle_demo_h5_analyze`, `run_inference`, `/predictions` — was not migrated. The spike succeeded by exercising normalization and providers directly, not through the application HTTP routes.

## Scope

A bounded integration change covering: one runtime orchestrator, workflow-registry bootstrap, public route wiring, legacy compatibility wrapper, Bremen model adaptation, canonical Nova normalization, typed Aramis routing, route-level tests, and readiness verification.

## Non-Goals

- No new scientific policy (P1/P2/P3, normalization, feature formulas)
- No certification of Bremen scientific parity
- No recreation of Aramis scientific logic
- No model training
- No combining Bremen and Aramis results
- No changes to Docker or CI/CD
- No committed private artifacts

## Current Public Call Graph

```
server.py:_handle_demo_h5_analyze
  → run_inference(h5_path)
    → run_h5_preflight(h5_path)
    → run_preprocessing_bridge(h5_path, preflight_result)
      → build_feature_table(h5_path)
        → canonical adapter path (for session/canonical)
        → _extract_matador_profiles(h5_path)  [LEGACY — for Matador raw]
    → validate_portable_logreg_model(model_pkg) [before adaptation]
    → predict_proba_portable(model, features)

app.py:handle_submit_prediction
  → run_inference(h5_path, target_scan_ref, control_scan_ref)
```

## Target Public Call Graph

```
server.py:_handle_demo_h5_analyze
  → run_workflow_request(h5_path, workflow_id="bremen")
    → detect_layout → normalize_to_canonical (once)
    → WorkflowRegistry.resolve("bremen")
    → WorkflowBremenProvider.execute(canonical_case)
      → _adapt_model_package(model_pkg)  [inside provider]
      → validate adapted view
      → _compute_bremen_features(canonical_case)
      → predict_proba_portable(adapted_model, features)
    → MultiWorkflowResult envelope

app.py:handle_submit_prediction
  → same orchestrator with explicit or default workflow_id

inference_handler.py:run_inference (legacy compatibility wrapper)
  → delegates to orchestrator with workflow_id="bremen"
  → maps result back to old dict shape
```

## Runtime Orchestrator Contract

New function in a new or existing module:

```python
def run_workflow_request(
    h5_path: str,
    workflow_id: str,
    *,
    target_scan_ref: str | None = None,
    control_scan_ref: str | None = None,
) -> MultiWorkflowResult:
    """Normalize the H5 once, resolve the workflow provider, execute it.

    Returns a typed envelope with normalization status, per-workflow
    results, and overall status.
    """
```

Implementation steps:
1. Open H5, detect layout via `detect_layout()`
2. Call `adapter.normalize_to_canonical(h5_file)` — single normalisation pass
3. Resolve `WorkflowRegistry.resolve(workflow_id)`
4. Call `provider.validate_compatibility(canonical_case)` before execution
5. Call `provider.execute(canonical_case)` for compatible cases
6. Return `MultiWorkflowResult` with typed status

Location preference: `src/bremen/api/workflow_orchestrator.py` (NEW).

## Workflow Selection

Public request body:

```json
{
  "container_id": "example.h5",
  "workflow_id": "bremen"
}
```

Backward-compatible default: when `workflow_id` is absent, default to `"bremen"`. This default exists only at the public API compatibility boundary. It is never inferred from H5 layout, filename, metadata, model package, or patient properties.

Public routes that need migration:
1. `server.py:_handle_demo_h5_analyze` — current body contains `{"container_id": "..."}` only; add `workflow_id` with default `"bremen"`.
2. `app.py:handle_submit_prediction` — current `target_scan_ref`/`control_scan_ref` based; add `workflow_id` field.
3. `inference_handler.py:run_inference` — becomes a wrapper.

## Public Route Migration

### `server.py:_handle_demo_h5_analyze`

Replace:
```python
result = run_inference(str(staged_path))
```

With:
```python
# Determine workflow_id from request body (default "bremen")
workflow_id = body_dict.get("workflow_id", "bremen")
result = run_workflow_request(
    h5_path=str(staged_path),
    workflow_id=workflow_id,
)
```

Remove premature event emission (`preprocessing_started`, `model_inference_started`) — already removed in prior PRs.

### `app.py:handle_submit_prediction`

Replace:
```python
result_dict = run_inference(
    h5_path=resolved_h5_path,
    patient_id=raw_request.get("patient_id"),
    target_scan_ref=request.target_scan_ref,
    control_scan_ref=request.control_scan_ref,
    input_mode=input_mode,
)
```

With:
```python
workflow_id = raw_request.get("workflow_id", "bremen")
mw_result = run_workflow_request(
    h5_path=resolved_h5_path,
    workflow_id=workflow_id,
    target_scan_ref=request.target_scan_ref,
    control_scan_ref=request.control_scan_ref,
)
# Extract workflow result from envelope
wf_result = mw_result.workflows.get(workflow_id, {})
# Map to existing result dict shape for backward compatibility
result_dict = {
    "prediction_id": wf_result.get("prediction_id", ""),
    "model_version": wf_result.get("model_version", ""),
    "model_checksum": wf_result.get("model_checksum", ""),
    # ... remaining fields from workflow result ...
}
```

## Legacy Compatibility Wrapper

`inference_handler.py:run_inference()` becomes a thin wrapper:

```python
def run_inference(h5_path, patient_id=None, target_scan_ref=None, control_scan_ref=None, input_mode=None):
    """Legacy compatibility wrapper — delegates to run_workflow_request."""
    from .workflow_orchestrator import run_workflow_request

    mw_result = run_workflow_request(
        h5_path=h5_path,
        workflow_id="bremen",
        target_scan_ref=target_scan_ref,
        control_scan_ref=control_scan_ref,
    )

    bremen_result = mw_result.workflows.get("bremen", {})
    # Map to original dict shape
    return {
        "prediction_id": bremen_result.get("prediction_id", ""),
        "model_version": bremen_result.get("model_version", ""),
        "model_checksum": bremen_result.get("model_checksum", ""),
        "feature_schema_version": bremen_result.get("feature_schema_version", ""),
        "threshold_version": bremen_result.get("threshold_version", ""),
        "threshold_value": bremen_result.get("threshold_value", 0.0),
        "p_mri_needed": bremen_result.get("p_mri_needed", 0.0),
        "triage_recommendation": bremen_result.get("triage_recommendation", ""),
        "qc_status": bremen_result.get("qc_status", "passed"),
        "qc_flags": bremen_result.get("qc_flags", []),
        "decision_support_report": bremen_result.get("decision_support_report"),
    }
```

The wrapper does NOT call `run_h5_preflight`, `run_preprocessing_bridge`, `build_feature_table`, `_extract_matador_profiles`, or `validate_portable_logreg_model` directly.

## Bremen Provider Wiring

The `WorkflowBremenProvider` must:
1. Receive the validated `CanonicalXRDCase`.
2. Load the model via its own `WorkflowModelState` (per-workflow, checksum-verified).
3. Call `_adapt_model_package(model_pkg)` before validation.
4. Validate the adapted view.
5. Call `_compute_bremen_features(canonical_case)`.
6. Call `predict_proba_portable(adapted_model, features)`.
7. Produce `WorkflowResult` with typed result schema.

`_adapt_model_package` must be added to `inference.py` (it was spike-only in PR0075):

```python
def adapt_model_package(package: dict) -> dict:
    """Adapt a real Bremen model package to the runtime-expected format.

    The real package stores feature_columns and threshold at root level.
    This produces a compatible view without modifying the original dict.
    """
    if "portable_logreg" not in package:
        return package
    plr = dict(package["portable_logreg"])
    needs_patch = False
    if "feature_columns" not in plr and "feature_columns" in package:
        plr["feature_columns"] = package["feature_columns"]
        needs_patch = True
    if "threshold" not in plr and "threshold" in package:
        plr["threshold"] = package["threshold"]
        needs_patch = True
    if needs_patch:
        patched = dict(package)
        patched["portable_logreg"] = plr
        return patched
    return package
```

## Bremen Model Adaptation

The real model package maps:

| Root field | Maps to | Runtime location |
|------------|---------|-----------------|
| `root.feature_columns` | `root.portable_logreg.feature_columns` | `adapt_model_package()` |
| `root.threshold` | `root.portable_logreg.threshold` | `adapt_model_package()` |
| `root.portable_logreg.coef` | same | validated directly |
| `root.portable_logreg.intercept` | same | validated directly |
| `root.portable_logreg.imputer_statistics` | same | validated directly |
| `root.portable_logreg.scaler_mean` | same | validated directly |
| `root.portable_logreg.scaler_scale` | same | validated directly |
| `root.portable_logreg.classes` | same | validated directly |

The adapter runs inside the Bremen provider trust boundary, not in UI, API, or H5 code. Source artifact is not modified. Checksum verified before `joblib.load()`.

## Legacy Preprocessing Isolation

After migration:
- `_handle_demo_h5_analyze` does not call `run_inference` → does not call legacy pipeline
- `run_inference` (wrapper) delegates to orchestrator → does not call legacy pipeline
- `run_preprocessing_bridge`, `build_feature_table`, `_extract_matador_profiles` remain in the codebase for:
  - Backward-compatible internal imports (no breaking of existing test imports)
  - Migration reference
  - Isolated historical tests

These functions are marked clearly as non-authoritative and unreachable from public inference. A `warnings.warn("LEGACY: this path is not used by public routes", DeprecationWarning)` is acceptable but not required for this PR.

## HTTP and Result Contract

### Demo route (`POST /demo/api/h5/analyze`)

HTTP 200 with typed body. Result states:

| State | Meaning |
|-------|---------|
| `completed` | Normalization + workflow execution succeeded |
| `workflow_configuration_required` | Workflow needs policy config (e.g., Nova P1/P2/P3) |
| `workflow_unavailable` | Workflow provider not configured |
| `workflow_incompatible` | Input not compatible with requested workflow |
| `selection_required` | Input requires explicit target/control refs |
| `normalization_failed` | Canonical normalization failed |
| `inference_failed` | Workflow execution failed |

### Application route (`POST /predictions`)

Same body semantics. HTTP 202 on accepted (async), with the `run_workflow_request` executing synchronously within the request lifecycle. If the workflow returns `workflow_configuration_required`, the job status is `failed` with reason code in the result.

No raw traceback or private path in public JSON. Safe error details via `_safe_error_detail()` (introduced in prior PRs).

## Readiness

Per-workflow readiness exposed through `WorkflowReadiness`:

```json
{
  "platform": {"alive": true, "normalization_ready": true},
  "workflows": {
    "bremen": {"configured": true, "model_ready": true, "scientifically_certified": false, "ready": true},
    "aramis": {"configured": false, "model_ready": false, "scientifically_certified": false, "ready": false}
  }
}
```

Existing `/health` endpoint continues to report platform liveness. A new `/api/v1/readiness` endpoint provides per-workflow detail.

Readiness does not claim Bremen model readiness if the public route would validate the unadapted package.

## Observability

New structured events:

| Event | When |
|-------|------|
| `runtime.orchestration.started` | Entry into `run_workflow_request` |
| `runtime.normalization.completed` | After `normalize_to_canonical` |
| `runtime.workflow.resolved` | After `WorkflowRegistry.resolve` |
| `runtime.workflow.completed` | After successful provider execution |
| `runtime.workflow.failed` | After provider failure |
| `runtime.request.completed` | Final envelope assembled |

Each event includes: `workflow_id`, `stage`, `typed_status`, correlation IDs. No raw arrays, patient identifiers, PONI contents, H5 internal paths, or model parameters.

## Route-Level Test Strategy

All tests use synthetic HDF5 fixtures (no committed H5 artifacts).

### Session + real-model package test

```
POST /demo/api/h5/analyze
body: {"container_id": "...", "workflow_id": "bremen"}
→ canonical Session normalization
→ adapt_model_package called
→ BremenProvider executed
→ legacy preprocessing bridge NOT called
→ typed completed result
```

### Nova canonical normalization test

```
POST /demo/api/h5/analyze
body: {"container_id": "...", "workflow_id": "bremen"}
→ canonical Nova normalizer
→ six measurements integrated
→ three P1/P2/P3 pairs retained
→ workflow_configuration_required
→ no legacy PONI search
```

### Aramis routing test

```
POST /demo/api/h5/analyze
body: {"container_id": "...", "workflow_id": "aramis"}
→ AramisProvider called
→ workflow_unavailable when unconfigured
→ Bremen preflight never called
```

### Aramis-style container + Bremen workflow test

```
POST /demo/api/h5/analyze
body: {"container_id": "...", "workflow_id": "bremen"}
→ selection_required or workflow_incompatible
→ no raw ValueError
```

### Call-path assertion tests

Use mocks/spies to verify that `_handle_demo_h5_analyze` does NOT call:
- `run_preprocessing_bridge`
- `build_feature_table`
- `_extract_matador_profiles`
- Legacy direct `run_h5_preflight`
- Raw `validate_portable_logreg_model` before adaptation

## Private-Artifact Route Certification

Operator runs actual local server against private artifacts:
- Session atypical/benign/cancer
- Nova raw
- Aramis multi-patient subset
- Real Bremen model package

Checks: route enters orchestrator, correct normalizer, correct provider, no legacy calls, typed result, checksums unchanged.

## Expected Files to Change

| File | Change |
|------|--------|
| `src/bremen/api/workflow_orchestrator.py` | NEW — `run_workflow_request()` function |
| `src/bremen/api/server.py` | MODIFY — `_handle_demo_h5_analyze` calls orchestrator |
| `src/bremen/api/app.py` | MODIFY — `handle_submit_prediction` calls orchestrator |
| `src/bremen/api/inference_handler.py` | MODIFY — `run_inference` becomes legacy wrapper |
| `src/bremen/inference.py` | MODIFY — add `adapt_model_package()` |
| `src/bremen/api/workflow_bremen.py` | MODIFY — call `adapt_model_package` inside provider |
| `tests/test_bremen_route_multi_workflow.py` | NEW — route-level tests |
| `tests/test_bremen_orchestrator.py` | NEW — orchestrator tests |

## Implementation Sequence

1. Add `adapt_model_package()` to `inference.py`
2. Create `workflow_orchestrator.py` with `run_workflow_request()`
3. Wire `_handle_demo_h5_analyze` to orchestrator
4. Wire `handle_submit_prediction` to orchestrator
5. Convert `run_inference` to legacy wrapper
6. Update `WorkflowBremenProvider` to call `adapt_model_package`
7. Add `_api/v1/readiness` endpoint (optional, minimal)
8. Add route-level tests with call-path assertions
9. Run full test suite

## Risks

1. **`adapt_model_package()` not merged** — It was spike-only; must be added in this PR. Low risk — pure function.
2. **`run_inference` signature preservation** — The legacy wrapper must preserve the exact return dict shape. Verify against existing callers.
3. **Per-workflow model state coexistence with singleton** — PR0075's `WorkflowModelState` must coexist with the existing `ModelState` singleton. Verify no startup conflicts.
4. **Aramis provider always unavailable** — Expected for this PR (scaffold only). Controlled result, not an error.

## Stop Conditions

Block if implementation would require:
- Inventing P1/P2/P3 behavior
- Combining q and intensity arrays
- Loading joblib before checksum verification
- Running Aramis through Bremen logic
- Changing feature formulas without training evidence
- Committing private artifacts
- Breaking existing Bremen clients without explicit migration
- Retaining two competing authoritative public execution paths

## Acceptance Criteria

| Gate | Criteria |
|------|----------|
| Public route wiring pass | `_handle_demo_h5_analyze` calls orchestrator, not legacy pipeline |
| Legacy bypass pass | Public routes do not call legacy preprocessing bridge |
| Session route pass | Session fixture completes through orchestrator |
| Real model adaptation pass | `adapt_model_package` applied inside Bremen provider |
| Nova canonical pass | Nova fixture reaches `workflow_configuration_required` |
| Aramis routing pass | Aramis fixture returns `workflow_unavailable` |
| HTTP contract pass | Typed result body with safe error details |
| Readiness pass | Per-workflow readiness reflects configured state |
| Full regression pass | 1495+ tests pass |
| Deployment smoke pass | Operator-run local server certification |

PR completion does not claim Bremen scientific certification or Nova model inference readiness.

## Files written

- `.project-memory/pr/0076-wire-multi-workflow-runtime/PLAN.md` (this file)

## Boundary confirmations

- confirm: canonical runtime orchestrator planned: yes
- confirm: workflow registry integrated into public routes: yes
- confirm: explicit workflow selection planned: yes
- confirm: backward-compatible Bremen default planned: yes
- confirm: legacy run_inference wrapper planned: yes
- confirm: adapt_model_package added to inference.py: yes
- confirm: Bremen provider calls adaptation inside provider boundary: yes
- confirm: Nova canonical normalization connected: yes
- confirm: Aramis routing connected: yes
- confirm: legacy preprocessing bridge isolated from public routes: yes
- confirm: typed HTTP result contract planned: yes
- confirm: per-workflow readiness planned: yes
- confirm: route-level tests with call-path assertions planned: yes
- confirm: no scientific policy invented in this PR: yes
- confirm: no model training or private artifacts committed: yes
- confirm: no changes to Docker/CI/CD: yes
- confirm: implementation assigned to Agent: coder: yes
- confirm: no git mutation commands run: yes
