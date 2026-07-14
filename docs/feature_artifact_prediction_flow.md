# Feature Artifact Prediction Flow

**PR0059 — Controlled Feature Artifact Prediction Flow**

---

## 1. Purpose

PR0059 proves the controlled internal path from validated feature artifact
to model prediction and `decision_support_report`.  Bremen remains a
model-only, decision-support-only system.  This is a productization step
toward investor readiness, not a demo-only fork.

---

## 2. Scope

- Internal controlled prediction flow only.
- No public HTTP request schema change.
- No `feature_artifact_path` or `feature_artifact_uri` public fields.
- No `h5_path`/`h5_uri` behavior change.
- No H5 staging change.
- No raw GFRM/H5/protobuf/GeoFrame preprocessing.
- No `xrd_preprocessing`/`eosdx-container` imports.
- No new dependencies.
- Synthetic test coverage only.

---

## 3. Option C Continuation

PR0059 continues **Option C** selected in PR0058:

- The runtime remains model-only and decision-support-only.
- Precomputed feature artifacts, validated at the ingestion boundary
  (`feature_artifacts.py`), are the bridge into model inference.
- Options A, B, and D remain deferred.
- `/scans/target` is **not** claimed as `eosdx-container` v0.3.
- Feature artifacts are a controlled, productizable boundary, not a
  fake container layout.

---

## 4. Controlled Prediction Flow

```
feature artifact (dict)
    │
    ▼
validate_feature_artifact(artifact)
    │   validates schema, features, metadata safety
    │   normalises feature columns to REQUIRED_FEATURE_COLUMNS order
    │
    ▼
run_feature_artifact_prediction(artifact, predictor)
    │
    ├── extract feature_values[0:15] in REQUIRED_FEATURE_COLUMNS order
    │
    ├── predict_proba_portable(predictor, feature_values)
    │       portable logistic regression (scaling + sigmoid + threshold)
    │
    ├── resolve probability, prediction, threshold
    │
    ├── assemble prediction dict (matching inference_handler shape)
    │
    ├── build_decision_support_report(prediction, input_mode="feature_artifact")
    │       same safety language, same report schema v0.1
    │
    └── return FeatureArtifactPredictionResult
```

The flow is internal only — no HTTP endpoint, no route registration,
no public API schema change.

---

## 5. Internal API / Module Boundary

- **Module**: `src/bremen/api/feature_artifact_prediction.py`
- **Public function**: `run_feature_artifact_prediction(artifact, predictor, *, model_version=None)`
- Accepts an in-memory feature artifact mapping (dict).
- Accepts an already-loaded model package dict (`portable_logreg` format).
- Does **not** load models.
- Does **not** use `joblib`.
- Does **not** make network calls.
- Does **not** touch the public request schema (`PredictionRequest`).

---

## 6. Model Input Mapping

- Input feature values follow `REQUIRED_FEATURE_COLUMNS` (15 features) exactly.
- `validate_feature_artifact()` normalises shuffled feature columns to the
  required order before `run_feature_artifact_prediction()` receives them.
- Missing, extra, invalid, or unsafe feature artifact data is rejected
  **before** the predictor is called.

---

## 7. Prediction Interface

The predictor is the already-loaded model package dict returned by
`ModelState.get_model()`.  It conforms to the `portable_logreg` v0.1 format:

```python
predictor = {
    "portable_logreg": {
        "feature_columns": [...],   # 15 strings
        "coef": [...],              # 15 floats
        "intercept": ...,           # float
        "threshold": ...,           # float
        "scaler_mean": [...],       # 15 floats
        "scaler_scale": [...],      # 15 floats
        "imputer_statistics": [...], # 15 floats
        "model_version": "...",
        "threshold_version": "...",
    }
}
```

Inference is performed by `predict_proba_portable(predictor, feature_values)`,
which handles scaling, sigmoid computation, and threshold application.

---

## 8. Decision-Support Report Behavior

The existing `build_decision_support_report()` helper is called with
`input_mode="feature_artifact"`.  The report:

- Uses `report_schema_version: "v0.1"`.
- Includes the same `intended_use` and `limitations` safety language.
- States "not a diagnostic result", "not clinically validated",
  "does not replace MRI, biopsy, radiologist, clinician, or clinical judgment".
- Includes `input_summary.input_mode: "feature_artifact"`.

---

## 9. Investor Path

| PR | What it delivers |
|----|-----------------|
| **PR0058** | Safe feature artifact ingestion boundary. The runtime can validate precomputed features. |
| **PR0059** | End-to-end prediction flow from validated feature artifact to decision-support report. The product story is concrete. |
| **PR0060** (planned) | May package an investor smoke/walkthrough around this controlled flow — a script or notebook that creates a synthetic artifact, runs prediction, and displays the decision-support report. |

**Investor narrative**: "Upstream preprocessing produces safe feature
artifacts.  Bremen validates them, runs prediction, and produces a
decision-support report.  No demo-only fork.  The same contract works
in production."

---

## 10. Runtime / API Boundaries Preserved

| Boundary | Status |
|----------|--------|
| `POST /predictions` schema | Unchanged — no `feature_artifact_path` / `feature_artifact_uri` |
| `h5_path` / `h5_uri` behavior | Unchanged |
| H5 staging (`h5_inputs.py`) | Unchanged |
| H5 layout detection (`h5_layouts.py`) | Unchanged |
| Preprocessing bridge math (`preprocessing_bridge.py`) | Unchanged |
| Inference math (`inference.py`) | Unchanged |
| Model loading (`model_loader.py`) | Unchanged |
| Decision-support report semantics (`decision_support.py`) | Unchanged |
| Public schemas (`schemas.py`) | Unchanged |
| Dependencies | None added |

---

## 11. Safety and Non-Leakage Boundaries

- No real artifact examples committed.
- No raw feature values from real data.
- No raw patient identifiers.
- No raw scan refs.
- No full S3 URIs, checksums, or secrets.
- No diagnosis claims.
- No clinical validation claims.
- No replacement of MRI, biopsy, radiologist, clinician, or clinical judgment.

---

## 12. PR0060 Handoff

PR0060 may wire this flow into an internal API path or standalone smoke
script.  No public schema change is implied.  The internal function
`run_feature_artifact_prediction()` is the contract — PR0060 will call it
with a synthetic artifact and an already-loaded predictor.

---

## 13. Non-Goals

1. No public API schema change (`POST /predictions` unchanged).
2. No `feature_artifact_path` or `feature_artifact_uri` in any public API.
3. No `h5_path`/`h5_uri` behavior change.
4. No H5 staging behavior change.
5. No preprocessing bridge math change.
6. No inference math change.
7. No model loading change.
8. No decision-support report semantic change.
9. No `xrd_preprocessing` import in new runtime module.
10. No `eosdx-container` import in new runtime module.
11. No GFRM conversion execution.
12. No H5/protobuf/GeoFrame parser implementation.
13. No `pyFAI`/`fabio` dependency addition.
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
