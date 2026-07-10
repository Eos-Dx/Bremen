# Plan: PR0059 — Controlled Feature Artifact Prediction Flow

**PR**: 0059-feature-artifact-prediction-flow  
**Role**: plan  
**Mode**: planning  
**Branch**: 0059-feature-artifact-prediction-flow  
**HEAD**: 10e825ac861f1c7a10ae33a9ef0df51e54b11c10  
**PR sequence**: PR0059 (fifth PR of Product Input Pipeline Readiness block, after PR0055 + PR0056 + PR0057 + process gatekeeper + PR0058)  

---

## 1. Roadmap And Investor Alignment

1. **PR0059 follows PR0058.** PR0058 defined and validated the feature
   artifact ingestion boundary (`src/bremen/feature_artifacts.py`).
   PR0059 wires it into a controlled internal prediction flow.

2. **PR0059 continues Option C.** The runtime remains model-only and
   decision-support-only. Precomputed feature artifacts are validated
   at the boundary and passed to model inference. No raw upstream
   container data enters the runtime.

3. **PR0059 does NOT implement Option A, B, or D.** No runtime H5 layout
   redefinition to v0.3. No retention of `/scans/target/` as canonical
   truth. No dedicated preprocessing service implementation.

4. **PR0059 is an investor-path productization step.** The controlled
   flow demonstrates end-to-end capability from validated feature
   artifact to decision-support report, without demo-only forks.

5. **PR0059 is not a demo-only fork.** The same internal flow will be
   used by the production path once the preprocessing service is
   implemented. Only the data source differs (synthetic for demo, real
   preprocessing service for production).

6. **PR0059 does not claim clinical validation.** All disclaimers from
   the existing decision-support report are preserved.

7. **PR0059 does NOT change the public prediction request schema.**
   No `POST /predictions` schema changes. No `feature_artifact_path`
   or `feature_artifact_uri` in the public API. The flow is internal
   only.

8. **PR0059 prepares PR0060 for investor smoke/walkthrough.** PR0060
   may wire the flow into an internal API path or create a standalone
   smoke script that exercises the end-to-end path.

---

## 2. Controlled Flow Contract

The intended controlled flow is:

```
feature artifact dict (in-memory) or controlled JSON file
  -> load_feature_artifact_from_dict() or load_feature_artifact_from_json()
    -> validate_feature_artifact() — validates schema, columns, values, metadata
      -> normalized 15-feature model input (list of float)
        -> feature_artifact_predict() — internal prediction runner
          -> ModelState.get_model() — existing loaded model
          -> predict_proba_portable(model_pkg, feature_values) — existing inference
          -> build_decision_support_report(prediction_dict, input_mode="feature_artifact")
            -> structured prediction result dict
```

### Key clarifications

1. **This is internal in PR0059.** The flow is exercised through a new
   internal module function. No HTTP endpoint, no route registration.
   The function signature accepts in-memory dicts for testability.

2. **This is not public HTTP schema wiring yet.** PR0060 may wire it
   behind an endpoint. PR0059 only creates the internal capability and
   proves it with synthetic tests.

3. **This is not raw preprocessing.** No GFRM, no H5, no protobuf, no
   GeoFrame parsing occurs. The artifact is already a precomputed
   15-feature vector.

4. **This is not /scans/target/ canonicalization.** The feature artifact
   path is independent of the H5-based canonical layout. The artifact
   carries features directly — no layout detection needed.

5. **This is not eosdx-container runtime parsing.** The eosdx-container
   library stays outside the runtime. The artifact is the bridge.

---

## 3. Implementation File Plan

### 3.1 Files to create

| File | Type | Description |
|------|------|-------------|
| `docs/feature_artifact_prediction_flow.md` | New | Flow contract document (Section 6) |
| `src/bremen/api/feature_artifact_prediction.py` | New | Internal prediction runner module (Section 4) |
| `tests/test_bremen_feature_artifact_prediction_flow.py` | New | Tests for the prediction flow (Section 5) |
| `.project-memory/pr/0059-feature-artifact-prediction-flow/IMPLEMENTATION_REPORT.md` | New | Implementation report (per new workflow) |

### 3.2 Files optionally modified

| File | Change | Justification | Recommended? |
|------|--------|---------------|-------------|
| `docs/feature_artifact_ingestion_boundary.md` | Add a one-paragraph cross-reference at the end of Section 12 (PR0059 Handoff) linking to `docs/feature_artifact_prediction_flow.md` | The ingestion boundary doc already describes the handoff to PR0059. Adding a concrete reference to the PR0059 flow document completes the link. | **Yes** |

### 3.3 Files NOT changed

- `src/bremen/inference.py` — No change. `predict_proba_portable()` is
  called by the new module but the function itself is unchanged.
- `src/bremen/api/inference_handler.py` — No change. `run_inference()`
  is not modified. The new module provides an alternative entry point,
  not a replacement.
- `src/bremen/api/decision_support.py` — No change. `build_decision_support_report()`
  is called by the new module but the function itself is unchanged.
- `src/bremen/api/model_state.py` — No change. `ModelState.get_model()`
  is called by the new module but the singleton is unchanged.
- `src/bremen/feature_artifacts.py` — No change. The new module imports
  from it.
- `src/bremen/api/schemas.py` — No change. Public schema unchanged.
- `src/bremen/api/preprocessing_bridge.py` — No change.
- `src/bremen/api/h5_layouts.py` — No change.
- `src/bremen/api/preflight.py` — No change.
- `src/bremen/h5_inputs.py` — No change.
- `src/bremen/pipelines.py` — No change.
- `src/bremen/model_loader.py` — No change.
- `docs/api_contract.md` — No change (public schema unchanged).
- `docs/product_input_pipeline_contract.md` — No change.
- `docs/converter_preprocessing_boundary.md` — No change.
- `docs/production_e2e_smoke.md` — No change.
- `docs/release_readiness_operator_notes.md` — No change.
- `ROADMAP.md` — No change.
- `docs/adr/` — No ADR changes.
- `config/`, `Dockerfile*`, `infra/`, `.github/`, `requirements.txt`,
  `pyproject.toml`, `agents/` — No changes.
- No dependency changes.

---

## 4. Internal Prediction Module Plan

Create a narrow, focused module at:

```
src/bremen/api/feature_artifact_prediction.py
```

### 4.1 Module purpose

Bridge the gap between a validated feature artifact (from
`feature_artifacts.py`) and the existing model prediction interface
(in `inference.py` and `decision_support.py`). Provides a single
internal function that takes a validated artifact dict and returns
a structured prediction result with a decision-support report.

### 4.2 Module requirements

| # | Requirement |
|---|-------------|
| 1 | Import `validate_feature_artifact` from `bremen.feature_artifacts` |
| 2 | Import `predict_proba_portable` (and optionally `validate_portable_logreg_model`) from `bremen.inference` |
| 3 | Import `build_decision_support_report` from `bremen.api.decision_support` |
| 4 | Import `ModelState` from `bremen.api.model_state` |
| 5 | Import `uuid`, `datetime`, `logging` from standard library |
| 6 | Do NOT import `h5py`, `joblib`, `boto3`, `requests`, `httpx`, `numpy` unless required by the existing inference interface — the existing `predict_proba_portable` uses `numpy` internally but the new module should not import it directly. |
| 7 | Do NOT import `xrd_preprocessing`, `eosdx-container` |
| 8 | Do NOT import from `preprocessing_bridge`, `h5_layouts`, `preflight`, `h5_inputs` |
| 9 | Do NOT call `run_inference`, `run_preprocessing_bridge`, `run_h5_preflight` |
| 10 | Do NOT perform `joblib.load()` — the model is already loaded by `ModelState` |

### 4.3 Public function

```python
def predict_from_feature_artifact(
    artifact: dict,
    *,
    skip_validation: bool = False,
    patient_id: str | None = None,
    input_mode: str = "feature_artifact",
) -> dict:
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `artifact` | dict | (required) | Feature artifact dict. Validated via `validate_feature_artifact()` unless `skip_validation=True`. |
| `skip_validation` | bool | `False` | If `True`, skip `validate_feature_artifact()` (caller has already validated). |
| `patient_id` | str or None | `None` | Optional label for the prediction. If `None`, defaults to `"feature_artifact"`. |
| `input_mode` | str | `"feature_artifact"` | Input mode category passed to `build_decision_support_report()`. |

**Returns:**

A dict matching the shape of existing prediction results (same fields
as `run_inference()` output):

```python
{
    "prediction_id": "<uuid>",
    "model_version": "<str>",
    "model_checksum": "<str>",
    "feature_schema_version": "v0.1",
    "threshold_version": "<str>",
    "threshold_value": <float>,
    "qc_status": "passed",
    "qc_flags": [],
    "patient_id": "<str>",
    "p_mri_needed": <float>,
    "triage_recommendation": "MRI_RECOMMENDED" | "MRI_RULE_OUT",
    "created_at_utc": "<ISO-8601>",
    "decision_support_report": { ... },
}
```

### 4.4 Internal flow

1. **Validate artifact** — If `skip_validation=False`, call
   `validate_feature_artifact(artifact)`. If validation fails, propagate
   the exception. If `skip_validation=True`, assume `artifact` is already
   validated and extract `feature_values` directly.

2. **Check model readiness** — Call `ModelState.get_model()`. If `None`,
   raise `RuntimeError("Model not loaded. Cannot run inference.")`.

3. **Validate model package** — Call
   `validate_portable_logreg_model(model_pkg)`. If invalid, propagate
   exception.

4. **Verify feature columns match model** — Compare
   `artifact["feature_columns"]` against `model_pkg["portable_logreg"]["feature_columns"]`.
   If mismatch, raise `RuntimeError` with descriptive message.

5. **Run inference** — Call `predict_proba_portable(model_pkg, feature_values,
   skip_validation=True)`.

6. **Assemble prediction dict** — Build the prediction result dict with
   required fields (same as `run_inference()` output):
   - `prediction_id`: `str(uuid.uuid4())`
   - `model_version`: from model package
   - `model_checksum`: from `ModelState`
   - `feature_schema_version`: `"v0.1"`
   - `threshold_version`: from model package
   - `threshold_value`: from inference result
   - `qc_status`: `"passed"` — feature artifacts bypass H5 QC
   - `qc_flags`: `[]`
   - `patient_id`: parameter or `"feature_artifact"`
   - `p_mri_needed`: from inference result
   - `triage_recommendation`: computed from probability vs threshold
   - `created_at_utc`: current UTC ISO-8601

7. **Build decision-support report** — Call
   `build_decision_support_report(prediction_dict, input_mode=input_mode,
   explicit_refs=False, layout_category=None)`. This reuses the existing
   safety language (`INTENDED_USE`, `LIMITATIONS`, `CAUTION_TEXT`) and
   produces a valid report with `input_mode="feature_artifact"`.

8. **Return** — The assembled prediction dict with
   `decision_support_report` attached.

### 4.5 Exception and error behavior

| Condition | Exception |
|-----------|-----------|
| Invalid artifact (schema, columns, values, metadata) | `FeatureArtifactError` subclass (from `feature_artifacts.py`) |
| Model not loaded | `RuntimeError("Model not loaded. Cannot run inference.")` |
| Model validation failure | `PortableLogRegModelError` (from `inference.py`) |
| Feature column mismatch | `RuntimeError` with descriptive message |
| Inference failure | Exception from `predict_proba_portable()` |

### 4.6 Module-level constants

```python
TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
TRIAGE_RULE_OUT = "MRI_RULE_OUT"
DEFAULT_PATIENT_ID = "feature_artifact"
LOGGER_NAME = "bremen.feature_artifact_prediction"
```

### 4.7 Logging

Standard `bremen.*` structured logging events:

| Event | When |
|-------|------|
| `bremen.feature_artifact.prediction.start` | Prediction started |
| `bremen.feature_artifact.validation.success` | Artifact validated |
| `bremen.feature_artifact.model.valid` | Model validated |
| `bremen.feature_artifact.inference.success` | Inference completed |
| `bremen.feature_artifact.prediction.completed` | Prediction completed — triage value logged |

### 4.8 Source evidence for interface reuse

- `predict_proba_portable(package, feature_vector, skip_validation)`
  accepts `list[float]` — verified at `src/bremen/inference.py:72`
- `build_decision_support_report(inference_result, input_mode=..., explicit_refs=..., layout_category=...)`
  accepts a dict and keyword args — verified at `src/bremen/api/decision_support.py:60`
- `ModelState.get_model()` returns `dict[str, Any] | None` — verified at
  `src/bremen/api/model_state.py`
- `ModelState.get_instance()._model_version` and `._model_checksum` exist
  for metadata — verified at `src/bremen/api/model_state.py`
- The `CompletedResult` dataclass in `schemas.py:136` defines the shape.
  The function returns a dict matching that shape. No need to instantiate
  the dataclass — the dict shape is the contract.
- `plr["feature_columns"]` is a list of strings — verified at
  `inference_handler.py:157`

---

## 5. Test Plan

Create a new test file at:

```
tests/test_bremen_feature_artifact_prediction_flow.py
```

### 5.1 Test design

All tests use synthetic in-memory feature artifacts. No real model
artifact files, no H5 files, no network calls.

Tests require a fake/stub model package. Use
`ModelState.reset_for_tests()` to isolate state between test classes.
Create a synthetic model package dict matching the `portable_logreg`
shape (with `feature_columns`, `coef`, `intercept`, `threshold`,
`scaler_mean`, `scaler_scale`, `imputer_statistics`,
`model_version`, `threshold_version`).

### 5.2 Test classes

| Test class | Tests |
|------------|-------|
| `TestPredictFromValidArtifact` | A valid synthetic artifact reaches prediction and returns a structured result with all mandatory fields. |
| `TestValidationCalledBeforePrediction` | `validate_feature_artifact` is called (or skip_validation=True is respected). Test with invalid artifact and expect validation error before inference. |
| `TestModelInputOrder` | Feature values are passed to `predict_proba_portable` in `REQUIRED_FEATURE_COLUMNS` order. (Use a model with known coefficients to verify output matches expected sign/direction.) |
| `TestShuffledArtifactColumnsNormalized` | An artifact with shuffled `feature_columns` is normalized to required order before inference. |
| `TestInvalidArtifactRejectedBeforePrediction` | An artifact with missing features is rejected by `validate_feature_artifact` before prediction is attempted. |
| `TestMissingFeatureRejected` | An artifact missing a required column is rejected. |
| `TestUnsafeMetadataRejected` | An artifact with unsafe metadata keys is rejected before prediction. |
| `TestModelNotLoadedError` | When `ModelState.get_model()` returns `None`, a clear `RuntimeError` is raised. |
| `TestFeatureColumnMismatchError` | When artifact `feature_columns` do not match model `feature_columns`, a `RuntimeError` is raised with a descriptive message. |
| `TestPredictorReceivesOneRow` | `predict_proba_portable` receives exactly 15 feature values (list of float, length 15). |
| `TestOutputShape` | The returned dict contains all mandatory fields: `prediction_id`, `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_status`, `qc_flags`, `patient_id`, `p_mri_needed`, `triage_recommendation`, `created_at_utc`, `decision_support_report`. |
| `TestDecisionSupportReportPresent` | Output contains `decision_support_report` with `report_schema_version: "v0.1"`, `intended_use`, `limitations`, `input_summary` (with `input_mode: "feature_artifact"`), `prediction_summary`, `decision_support`. |
| `TestDecisionSupportSafetyLanguage` | `decision_support_report.limitations` includes "not a diagnostic result", "not clinically validated", "does not replace MRI, biopsy, radiologist, clinician, or clinical judgment". |
| `TestNoH5PathRequired` | The flow does not require `h5_path` or `h5_uri`. |
| `TestNoPublicSchemaField` | The module does not reference `feature_artifact_path` or `feature_artifact_uri`. |
| `TestNoXRDPreprocessingImport` | The module file does not import `xrd_preprocessing` or `eosdx-container`. |
| `TestNoBoto3RequestsHTTPX` | The module file does not import `boto3`, `requests`, `httpx`, `aiohttp`, `FastAPI`, `uvicorn`, `starlette`. |
| `TestNoRealArtifacts` | No real `.h5`, `.hdf5`, `.gfrm`, `.joblib`, `.pkl`, `.npy`, `.npz`, `.parquet`, `.proto`, `.pb` files in committed examples. |
| `TestDocExists` | `docs/feature_artifact_prediction_flow.md` exists. |
| `TestDocInvestorPath` | The flow doc describes the investor path and PR0060 handoff. |
| `TestNoDemoOnlyFork` | The flow doc states this is not a demo-only format. |
| `TestNoClinicalClaims` | The flow doc states no diagnosis, no clinical validation, no replacement of clinical judgment. |

### 5.3 Synthetic model package helper

```python
def _stub_model_package(feature_columns=None, threshold=0.5):
    """Create a synthetic model package dict for testing."""
    fcols = feature_columns or list(REQUIRED_FEATURE_COLUMNS)
    n = len(fcols)
    return {
        "portable_logreg": {
            "feature_columns": fcols,
            "coef": [0.1] * n,
            "intercept": -0.5,
            "threshold": threshold,
            "scaler_mean": [0.0] * n,
            "scaler_scale": [1.0] * n,
            "imputer_statistics": [0.0] * n,
            "model_version": "test-v0.1",
            "threshold_version": "v0.1",
        }
    }
```

### 5.4 ModelState fixture

```python
@pytest.fixture(autouse=True)
def _reset_model_state():
    """Reset ModelState before each test to ensure isolation."""
    ModelState.reset_for_tests()
    yield
    ModelState.reset_for_tests()

@pytest.fixture
def loaded_model():
    """Load a synthetic model package into ModelState."""
    pkg = _stub_model_package()
    ModelState.get_instance()._model_package = pkg
    ModelState.get_instance()._model_version = "test-v0.1"
    ModelState.get_instance()._model_checksum = "a" * 64
    ModelState.get_instance()._loaded = True
    ModelState.get_instance()._load_attempted = True
    return pkg
```

---

## 6. Doc Plan

Create a new document at:

```
docs/feature_artifact_prediction_flow.md
```

### 6.1 Required sections

| Section | Content |
|---------|---------|
| **1. Purpose** | Define the controlled internal prediction flow from validated feature artifact to decision-support report. PR0059 is an investor-path productization step — no demo-only fork. |
| **2. Scope** | Internal prediction flow, synthetic test coverage, PR0060 handoff. Not public API schema wiring, not upstream preprocessing. |
| **3. Option C Continuation** | Brief restatement: Option C selected in PR0058, continued in PR0059. Runtime remains model-only. Precomputed feature artifacts are the bridge. |
| **4. Controlled Prediction Flow** | Artifact diagram: validated feature artifact → `predict_from_feature_artifact()` → `ModelState` → `predict_proba_portable()` → `build_decision_support_report()` → structured result. |
| **5. Internal API/Module Boundary** | `src/bremen/api/feature_artifact_prediction.py` — single public function `predict_from_feature_artifact()`. Not a public HTTP endpoint. |
| **6. Model Input Mapping** | Validated artifact feature values (list of 15 floats) → `predict_proba_portable()` input. Feature columns validated against model `feature_columns`. |
| **7. Decision-Support Report Behavior** | `input_mode="feature_artifact"` passed to `build_decision_support_report()`. Report includes `input_summary.input_mode: "feature_artifact"`. Same safety language. |
| **8. Investor Path** | What PR0059 delivers (Section 7 of this plan). |
| **9. Runtime/API Boundaries Preserved** | Table of preserved boundaries. |
| **10. Safety and Non-Leakage Boundaries** | Same rules as PR0058. |
| **11. PR0060 Handoff** | PR0060 may wire the flow into an internal API path or standalone smoke script. No public schema change implied. |
| **12. Non-Goals** | No public schema change, no H5 changes, no preprocessing bridge changes, no inference math changes, no model loading changes, no dependency additions, no upstream code vendoring, no investor walkthrough yet. |

---

## 7. Investor Path Plan

### 7.1 Investor impact

| Aspect | Impact |
|--------|--------|
| **PR0058 delivered** | Safe feature artifact ingestion boundary. The runtime can validate precomputed features. |
| **PR0059 delivers** | End-to-end prediction flow from validated feature artifact to decision-support report. The product story is concrete. |
| **Investor narrative** | "Upstream preprocessing produces safe feature artifacts. Bremen validates them, runs prediction, and produces a decision-support report. No demo-only fork. The same contract works in production." |
| **Clinical safety** | "This is decision support, not diagnosis. Not clinically validated. Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment." |
| **PR0060 handoff** | PR0060 can package this flow into an investor walkthrough: a script or notebook that creates a synthetic artifact, runs prediction, and displays the decision-support report. |

### 7.2 Demo vs production path

| Aspect | Demo | Production |
|--------|------|-----------|
| Feature source | Synthetic in-memory artifact | Upstream `xrd_preprocessing` + `eosdx-container` preprocessing service |
| Artifact format | Same `bremen.feature_artifact.v0.1` | Same `bremen.feature_artifact.v0.1` |
| Validation | Same `validate_feature_artifact()` | Same `validate_feature_artifact()` |
| Prediction | Same `predict_from_feature_artifact()` | Same `predict_from_feature_artifact()` |
| Report | Same `build_decision_support_report()` | Same `build_decision_support_report()` |
| Claims | No diagnosis, no clinical validation | No diagnosis, no clinical validation |

There is **no** separate demo-only code path. The runtime does not
distinguish between demo and production feature artifacts.

---

## 8. New Workflow Requirements

### 8.1 Implementation report

The coder implementing PR0059 must create:

```
.project-memory/pr/0059-feature-artifact-prediction-flow/IMPLEMENTATION_REPORT.md
```

The implementation report must include all required fields from
`.project-memory/IMPLEMENTATION_REPORT_WORKFLOW.md` Section 5:

1. Task Completed
2. Branch / PR
3. Files Changed
4. Implementation Summary
5. Key Decisions Made During Implementation
6. Deviations From PLAN.md
7. Warnings / Unresolved Questions
8. Validation Commands and Results
9. Safety Checks
10. Boundaries Preserved
11. Commit Readiness
12. Recommended Next Action

### 8.2 Precommit-review requirements

The precommit-review agent for PR0059 must read and reconcile:

| # | Source | Purpose |
|---|--------|---------|
| 1 | `.project-memory/pr/0059-feature-artifact-prediction-flow/PLAN.md` | Planned scope and allowed files |
| 2 | `.project-memory/pr/0059-feature-artifact-prediction-flow/reviews/plan-review.yml` | Plan-review approval |
| 3 | `.project-memory/pr/0059-feature-artifact-prediction-flow/IMPLEMENTATION_REPORT.md` | Coder claims and validation |
| 4 | `git status --short` | Working tree state |
| 5 | `git diff --name-only` | Actual changed files |
| 6 | Relevant changed files (selected sections) | Implementation quality |
| 7 | Relevant unchanged boundary files | Files outside scope not touched |
| 8 | Validation output | Compare with own validation |

The precommit-review agent must write:

```
.project-memory/pr/0059-feature-artifact-prediction-flow/reviews/precommit-review.yml
```

with `final_gatekeeper_summary` per the
`.project-memory/IMPLEMENTATION_REPORT_WORKFLOW.md` schema.

### 8.3 Blocking conditions

The precommit-review must block if:

| # | Condition |
|---|-----------|
| 1 | IMPLEMENTATION_REPORT.md is missing |
| 2 | Implementation report contradicts PLAN.md |
| 3 | Implementation report contradicts git diff |
| 4 | Any file outside the allowed set was changed |
| 5 | The new module imports `xrd_preprocessing`, `eosdx-container`, `boto3`, `requests`, `httpx`, `FastAPI` |
| 6 | Public schema files were changed (`src/bremen/api/schemas.py`, `docs/api_contract.md`) |
| 7 | The new module uses `h5py`, `joblib`, `h5_inputs`, `preprocessing_bridge` |
| 8 | The new module calls `run_inference()` or `run_preprocessing_bridge()` |
| 9 | Any safety check reveals secrets or forbidden patterns |
| 10 | Tests are weakened or assertions removed to pass |

---

## 9. Validation Plan

### 9.1 Pre-implementation validation

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
```

### 9.2 Post-implementation compilation

```bash
python -m compileall src tests
```

### 9.3 Post-implementation test suite

```bash
# PR0058 feature artifact tests (must still pass)
python -m pytest -q tests/test_bremen_feature_artifacts.py -v

# New prediction flow tests
python -m pytest -q tests/test_bremen_feature_artifact_prediction_flow.py -v

# Existing inference/decision-support tests (must still pass)
python -m pytest -q tests/test_bremen_inference_integration.py -v
python -m pytest -q tests/test_bremen_decision_support_output.py -v

# API contract tests (schema unchanged)
python -m pytest -q tests/test_bremen_api_contract.py -v

# Full suite
python -m pytest -q
```

### 9.4 Safety validation

```bash
# Confirm no unintended file changes
git diff --name-only

# Confirm restricted files unchanged
git diff --name-only -- Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml src/bremen/training agents config docs/adr ROADMAP.md docs/api_contract.md docs/product_input_pipeline_contract.md docs/converter_preprocessing_boundary.md src/bremen/api/schemas.py src/bremen/api/inference_handler.py src/bremen/api/h5_layouts.py src/bremen/h5_inputs.py src/bremen/pipelines.py src/bremen/model_loader.py src/bremen/api/preprocessing_bridge.py

# Confirm no feature_artifact_path or feature_artifact_uri in source/docs
grep -R "feature_artifact_path\|feature_artifact_uri" -n src tests docs || true

# Confirm no FastAPI/uvicorn/starlette
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n docs tests src ROADMAP.md || true

# Confirm no Matador/network clients
grep -R "MATADOR_\|Matador.*token\|Matador.*URL\|requests\|httpx\|aiohttp" -n docs tests src ROADMAP.md || true

# Confirm no secrets/identifiers
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|s3://\|sha256:\|Nova_\|/Users/\|/home/" -n docs tests src .project-memory || true

# Confirm no clinical claims (only negated safety language)
grep -R "diagnos\|clinical validation\|clinically validated\|replace radiologist\|replace clinician\|replace MRI\|replace biopsy" -n docs tests src .project-memory || true
```

### 9.5 Safety validation expectations

| Check | Expected result |
|-------|----------------|
| `git diff --name-only` | Only new + optionally modified files per Section 3 |
| Restricted files check | Empty — no changes outside allowed scope |
| `feature_artifact_path` grep | Empty — no public API field introduced |
| FastAPI grep | Empty — no FastAPI introduced |
| Matador/network grep | Empty — no network clients introduced |
| Secrets grep | Empty — no secrets in committed files |
| Clinical claims grep | Only negated safety language — all positive claims absent |

---

## 10. Implementation Order

1. Create `src/bremen/api/feature_artifact_prediction.py`
2. Create `tests/test_bremen_feature_artifact_prediction_flow.py`
3. Create `docs/feature_artifact_prediction_flow.md`
4. (Optional) Add cross-reference note to `docs/feature_artifact_ingestion_boundary.md`
5. Create `.project-memory/pr/0059-feature-artifact-prediction-flow/IMPLEMENTATION_REPORT.md`
6. Run validation (Section 9)
7. Commit with message: `feat(pr0059): controlled feature artifact prediction flow — internal module, synthetic tests, investor path`

---

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New module accidentally wired into `POST /predictions` handler | Low | High | Plan explicitly prohibits public API changes. Tests verify no schema changes. `schemas.py` is a forbidden file. |
| ModelState singleton leakage between tests | Medium | Medium | `reset_for_tests()` fixture defined. Each test class uses `autouse=True` fixture to reset state. |
| Feature columns diverge between `feature_artifacts.py` and model package | Low | Medium | Column mismatch is caught at inference time by `feature_columns` comparison in `predict_from_feature_artifact()`. |
| Predictor receives wrong column order | Low | Medium | Artifact columns are normalized to `REQUIRED_FEATURE_COLUMNS` order by `validate_feature_artifact()`. The module uses the validated order. |

---

## 12. Non-Goals

1. No public runtime request schema change (`POST /predictions` unchanged).
2. No `feature_artifact_path` or `feature_artifact_uri` in any public API.
3. No `h5_path`/`h5_uri` behavior change.
4. No H5 staging behavior change.
5. No existing `preprocessing_bridge.py` math change.
6. No inference math change.
7. No model loading change.
8. No `decision_support_report` semantic change.
9. No `xrd_preprocessing` import in new runtime module.
10. No `eosdx-container` import in new runtime module.
11. No GFRM conversion execution.
12. No H5/protobuf/GeoFrame parser implementation.
13. No pyFAI/fabio dependency addition.
14. No upstream code vendoring.
15. No Matador integration.
16. No FastAPI, uvicorn, starlette, or ASGI.
17. No runtime training.
18. No model training implementation.
19. No new model.
20. No demo-only fork.
21. No real data artifacts committed.
22. No real model artifacts committed.
23. No clinical validation claims.
24. No diagnosis claims.
25. No replacement of clinical judgment.
26. No investor walkthrough implementation yet (PR0060).

---

Implementation role: coder
