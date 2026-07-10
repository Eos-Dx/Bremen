# Bremen Feature Artifact Ingestion Boundary

**PR0058** — Feature artifact ingestion boundary definition.
Documentation and safe internal module only; no public API wiring.

---

## 1. Purpose

This document defines the safe ingestion boundary for precomputed
feature artifacts produced by upstream preprocessing
(`xrd_preprocessing`/`eosdx-container`). The Bremen runtime remains
model-only and decision-support-only in this PR.

PR0058 is a productization step toward investor readiness. The feature
artifact contract is the same for demo and production — no demo-only
fork.

---

## 2. Scope

**Covered**: Definition of the feature artifact schema, validation
rules, metadata restrictions, mapping to the 15-feature v0.1 model
contract, and safety boundaries. Internal validation module only.

**Not covered**: Public API wiring (`POST /predictions` schema
unchanged), `h5_path`/`h5_uri` behavior changes, upstream
preprocessing execution, `xrd_preprocessing`/`eosdx-container` imports
in the new module, dependency additions, or inference/math changes.

---

## 3. Option C Decision Record

**Decision**: Option C selected for PR0058.

**Context**: PR0057 established that the PR0055/PR0056 `/scans/target/`
layout does not match the real eosdx-container v0.3 `/session/sets/`
layout. The runtime feature bridge (`preprocessing_bridge.py`) contains
duplicated feature computation math. The upstream preprocessing pipeline
(`xrd_preprocessing`/`eosdx-container`) requires heavy dependencies
(pyFAI/fabio) that must not enter the Bremen runtime container.

**Rationale**:

1. Fastest investor-presentable product path without a demo-only fork.
2. Productizable — the same contract applies to demo and production.
3. Avoids pretending `/scans/target/` is eosdx-container v0.3.
4. Keeps heavy GFRM/pyFAI/fabio dependencies outside the runtime.
5. Preserves runtime safety boundaries unchanged.
6. Creates a controlled bridge from upstream preprocessing output to
   Bremen's 15-feature model contract.

**Deferred**:

1. Public API wiring of feature artifact ingestion (`POST /predictions`
   schema extension) — PR0059 or later.
2. Runtime schema extension for direct feature artifact submission.
3. Preprocessing service/container implementation — outside this PR.
4. Direct eosdx-container v0.3 runtime alignment — Option A (deferred).
5. Investor walkthrough implementation — PR0059 or later.

---

## 4. Upstream Source Context

The upstream preprocessing path (documented in PR0057) consists of:

- **xrd-preprocessing v0.1.6b0** — Pipeline from GFRM/H5 container data
  through azimuthal integration to DataFrame output. Requires pyFAI and
  fabio (heavy C-extension dependencies).
- **eosdx-container v0.3** — Session/set-based HDF5 container with
  `/session/sets/set_NNN_label/` layout and integration profiles.

PR0058 consumes a safe precomputed feature artifact contract rather
than raw GFRM, H5 session containers, or protobuf data. The artifact
is produced by the upstream preprocessing path and validated at the
Bremen runtime boundary.

Direct upstream integration is not yet complete. The feature artifact
contract bridges the two worlds while keeping heavy dependencies
outside the runtime.

---

## 5. Feature Artifact Schema

The feature artifact is a JSON-compatible in-memory dictionary with
the following shape:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Must be `"bremen.feature_artifact.v0.1"` |
| `artifact_kind` | string | Yes | Must be `"bremen.precomputed_features"` |
| `feature_columns` | list of strings | Yes | Must match the 15 required feature columns exactly |
| `feature_values` | list of numeric | Yes | Must contain exactly 15 finite float-like values |
| `metadata` | dict or null | No | Safe provenance labels only |

### 5.1 Schema constants

- `schema_version`: `"bremen.feature_artifact.v0.1"`
- `artifact_kind`: `"bremen.precomputed_features"`

### 5.2 Example synthetic artifact

```json
{
    "schema_version": "bremen.feature_artifact.v0.1",
    "artifact_kind": "bremen.precomputed_features",
    "feature_columns": [
        "weightedrms1", "sigma_l1", "sigma_r1", "mahalanobis1",
        "weightedrms2", "sigma_l2", "sigma_r2", "mahalanobis2",
        "peak14_intensity", "mean_peak_value_raw",
        "wasserstein_distance_muLR", "cosine_distance_full_q2",
        "wasserstein_distance_full_q2", "meanrms1", "meanrms2"
    ],
    "feature_values": [0.5, 0.3, 0.4, 1.2, 0.6, 0.2, 0.3, 0.9,
                       0.15, -0.22, 0.01, 0.05, 0.02, 1.1, 0.8],
    "metadata": {
        "preprocessing_source": "xrd_preprocessing",
        "source_package_version": "0.1.6b0",
        "configuration_label": "one-to-one-default"
    }
}
```

---

## 6. Required Model Feature Columns

The exact 15-column order matches `BREMEN_V01_FEATURE_COLUMNS` from
`src/bremen/api/preprocessing_bridge.py`:

1. `weightedrms1`
2. `sigma_l1`
3. `sigma_r1`
4. `mahalanobis1`
5. `weightedrms2`
6. `sigma_l2`
7. `sigma_r2`
8. `mahalanobis2`
9. `peak14_intensity`
10. `mean_peak_value_raw`
11. `wasserstein_distance_muLR`
12. `cosine_distance_full_q2`
13. `wasserstein_distance_full_q2`
14. `meanrms1`
15. `meanrms2`

This is the canonical runtime feature column list. The inference
handler validates `fv.feature_names == model_cols` where
`model_cols = plr["feature_columns"]`. The feature artifact must
provide these 15 columns in this exact order.

---

## 7. Metadata Restrictions

### 7.1 Allowed metadata

Metadata is optional. When present, it must be a dictionary. Allowed
values are safe, low-cardinality provenance labels:

- Upstream package version strings (e.g., `"0.1.6b0"`).
- Safe configuration labels (e.g., `"one-to-one-default"`).
- Safe source identifiers (e.g., `"xrd_preprocessing"`).

### 7.2 Prohibited metadata keys

Metadata keys containing any of the following patterns are prohibited
(case-insensitive substring match):

- `_id` — raw identifiers
- `_ref` — raw scan refs
- `_path` — local filesystem paths
- `_uri` — URI references
- `_checksum` — raw checksums
- `secret` — credential tokens
- `token` — authentication tokens
- `password` — password references
- `account` — account identifiers
- `key` — access key references

### 7.3 Prohibited metadata values

Metadata values matching any of the following patterns are prohibited:

- `AKIA` — AWS access key prefix
- `s3://` — S3 URI scheme
- `sha256:` — checksum prefix
- `Nova_` — raw patient identifier pattern
- `/Users/` — local machine path
- `/home/` — local machine path
- `SECRET_ACCESS_KEY` — secret key reference
- `dkr.ecr` — ECR registry URL pattern
- 12-digit numeric strings — account ID patterns

---

## 8. Validation Rules

The `validate_feature_artifact()` function enforces:

| # | Rule | Error on violation |
|---|------|--------------------|
| 1 | `schema_version` must be `"bremen.feature_artifact.v0.1"` | `FeatureArtifactSchemaError` |
| 2 | `artifact_kind` must be `"bremen.precomputed_features"` | `FeatureArtifactSchemaError` |
| 3 | `feature_columns` must be exactly 15 strings matching the required list | `FeatureArtifactValidationError` |
| 4 | Missing required features are rejected | `FeatureArtifactValidationError` |
| 5 | Extra features beyond the 15 are rejected | `FeatureArtifactValidationError` |
| 6 | Duplicate feature names are rejected | `FeatureArtifactValidationError` |
| 7 | Non-string feature names are rejected | `FeatureArtifactValidationError` |
| 8 | `feature_values` must contain exactly 15 numeric values | `FeatureArtifactValidationError` |
| 9 | Non-numeric values are rejected | `FeatureArtifactValidationError` |
| 10 | Boolean values are rejected (not numeric) | `FeatureArtifactValidationError` |
| 11 | NaN is rejected | `FeatureArtifactValidationError` |
| 12 | Infinity is rejected | `FeatureArtifactValidationError` |
| 13 | Metadata must be a dict or absent | `FeatureArtifactValidationError` |
| 14 | Unsafe metadata keys are rejected | `FeatureArtifactValidationError` |
| 15 | Unsafe metadata values are rejected | `FeatureArtifactValidationError` |

The output is normalized: feature values are ordered to match
`REQUIRED_FEATURE_COLUMNS`. The returned artifact contains
`"feature_values"` as a list of `float`.

---

## 9. Mapping to Bremen Model Input

The validated feature artifact maps directly to the model's feature
input:

1. `feature_values` (list of 15 floats) → model feature row.
2. `feature_columns` (15 strings) → used to verify alignment.
3. The existing inference handler checks `fv.feature_names != model_cols`
   where `model_cols = plr["feature_columns"]`.

PR0058 does **not** score, call the model loader, or invoke the
inference handler. It only validates and normalizes the artifact.
The mapping to the model input is a future wiring step (PR0059).

---

## 10. Safety and Non-Leakage Boundaries

Committed examples, test fixtures, and documentation must not contain:

1. Real GFRM, H5, joblib, parquet, protobuf, or model artifacts.
2. Raw patient identifiers (names, IDs, `Nova_` patterns).
3. Raw target/control scan refs with real patient data.
4. Full S3 URIs (`s3://bucket/key`).
5. Raw SHA-256 checksums.
6. AWS credentials, access keys, account IDs, or registry URLs.
7. Local-machine absolute paths (`/Users/`, `/home/`).
8. Clinical validation claims.
9. Diagnosis claims.
10. Replacement of MRI, biopsy, radiologist, clinician, or clinical
    judgment.

---

## 11. Runtime/API Boundaries Preserved in PR0058

| Boundary | Status |
|----------|--------|
| Public `POST /predictions` request schema | Unchanged — no `feature_artifact_path` or `feature_artifact_uri` |
| `h5_path` / `h5_uri` behavior | Unchanged |
| H5 staging behavior | Unchanged |
| `preprocessing_bridge.py` math | Unchanged |
| Inference handler | Unchanged |
| Model loading | Unchanged |
| `decision_support_report` semantics | Unchanged |
| `xrd_preprocessing`/`eosdx-container` imports in new module | None |
| pyFAI/fabio dependency | Not added |

---

## 12. PR0059 Handoff

PR0059 may wire this internal boundary into a controlled internal or
API path for investor smoke. Specific handoff items:

1. Wire `validate_feature_artifact()` into a prediction flow that
   accepts precomputed feature artifacts alongside or instead of
   H5-based input.
2. Produce a working investor smoke that demonstrates end-to-end flow
   from synthetic feature artifact to decision-support report.
3. Continue preserving `no diagnosis`, `no clinical validation`, and
   `no replacement` claims.
4. No public API schema change is implied by this handoff — PR0059
   must plan and review any schema changes.

---

## 13. Investor Path

### 13.1 What PR0058 delivers

A safe, validated feature artifact ingestion boundary. The runtime can
accept a precomputed 15-feature vector from external preprocessing
(validated by `src/bremen/feature_artifacts.py`).

### 13.2 Investor message

"Bremen now has a controlled bridge from upstream preprocessing output
to model inference. The feature artifact contract is the same for demo
and production."

### 13.3 Productization path

The same contract will be produced by the real
`xrd_preprocessing`/`eosdx-container` pipeline in production. No
separate demo format.

### 13.4 Limitations

PR0058 does not wire the artifact path into the public API. A demo
must use the internal `validate_feature_artifact()` or
`load_feature_artifact_json()` directly (not via `POST /predictions`).
This is temporary — PR0059 will wire the path.

### 13.5 How PR0058 avoids heavy deps

The feature artifact is validated using only the Python standard
library. No numpy, h5py, joblib, pyFAI, fabio, xrd_preprocessing, or
eosdx-container imports. Heavy dependencies remain in the preprocessing
service.

---

## 14. Non-Goals

1. No public runtime request schema change.
2. No `feature_artifact_path` or `feature_artifact_uri` in public API.
3. No `h5_path`/`h5_uri` behavior change.
4. No H5 staging behavior change.
5. No existing `preprocessing_bridge.py` math change.
6. No inference math change.
7. No model loading change.
8. No `decision_support_report` semantic change.
9. No `xrd_preprocessing` import in new runtime module.
10. No `eosdx-container` import in new runtime module.
11. No GFRM conversion execution.
12. No H5 parsing in the new module.
13. No pyFAI/fabio dependency addition.
14. No upstream code vendoring.
15. No Matador integration.
16. No FastAPI, uvicorn, starlette, or ASGI.
17. No runtime training.
18. No model training implementation.
19. No new model.
20. No demo-only fork.
21. No real data artifacts committed.
22. No clinical validation.
23. No diagnosis.
24. No replacement of MRI, biopsy, radiologist, clinician, or clinical
    judgment.
25. No investor walkthrough implementation yet (PR0059).
26. No public API wire-up yet (PR0059).
27. No preprocessing bridge replacement or removal.
