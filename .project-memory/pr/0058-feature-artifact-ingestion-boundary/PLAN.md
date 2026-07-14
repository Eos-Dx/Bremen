# Plan: PR0058 — Feature Artifact Ingestion Boundary

**PR**: 0058-feature-artifact-ingestion-boundary  
**Role**: plan  
**Mode**: planning  
**Branch**: 0058-feature-artifact-ingestion-boundary  
**HEAD**: a4018ea30daf302ed5e6b56b04671df1eee35401  
**PR sequence**: PR0058 (fourth PR of Product Input Pipeline Readiness block, after PR0055 + PR0056 + PR0057 + process gatekeeper)  

---

## 1. Roadmap And Decision Alignment

1. **PR0058 follows PR0057 and the process gatekeeper PR.** PR0057
   reconciled upstream sources and established a human decision gate.
   The process gatekeeper PR formalized implementation reporting and
   precommit-review gatekeeping.

2. **PR0058 selects Option C from PR0057.** The human product/engineering
   decision is: keep Bremen runtime model-only and consume a precomputed
   feature table/artifact produced by the upstream
   `xrd_preprocessing`/`eosdx-container` preprocessing path.

3. **PR0058 does NOT implement Option A, B, or D.** No runtime H5 layout
   redefinition to v0.3. No retention of `/scans/target/` as canonical
   truth. No dedicated preprocessing service implementation yet.

4. **PR0058 does NOT redefine the eosdx-container v0.3 layout.** The
   v0.3 `/session/sets/` layout remains a future consideration. PR0058
   builds the bridge from the *other side* — it defines how the runtime
   accepts precomputed features without knowing the input container
   layout.

5. **PR0058 does NOT keep `/scans/target/` as canonical truth.** The
   PR0055/PR0056 canonical layout is acknowledged as an undocumented
   intermediate format that does not match upstream. It is not used or
   extended in PR0058.

6. **PR0058 does NOT change the public prediction request schema.**
   No `feature_artifact_path`, `feature_artifact_uri`, or any new
   public API field is added. The feature artifact ingestion is an
   *internal* capability in PR0058.

7. **PR0058 is an investor-path productization step, not demo-only.**
   The feature artifact contract defined here is the same contract that
   a production preprocessing service would produce. No separate
   demo-only format.

---

## 2. Option C Decision Record Plan

Add a decision record section to the new contract document. The
reconciliation document (`docs/preprocessing_source_reconciliation.md`)
already documents all four options. The new contract document captures
the decision and its consequences.

The decision record must state:

> **Decision**: Option C selected for PR0058.
>
> **Context**: PR0057 established that the PR0055/PR0056 `/scans/target/`
> layout does not match the real eosdx-container v0.3 `/session/sets/`
> layout. The runtime feature bridge (`preprocessing_bridge.py`) contains
> duplicated feature computation math. The upstream preprocessing pipeline
> (`xrd_preprocessing`/`eosdx-container`) requires heavy dependencies
> (pyFAI/fabio) that must not enter the Bremen runtime container.
>
> **Rationale**: Option C provides the fastest investor-presentable
> product path without a demo-only fork. It avoids pretending `/scans/target/`
> is eosdx-container v0.3. It avoids pulling heavy GFRM/pyFAI/fabio
> preprocessing into the runtime. It keeps the public prediction request
> schema unchanged in PR0058. It creates a controlled bridge from
> upstream preprocessing output to Bremen's 15-feature model contract.
>
> **Consequences**: The Bremen runtime accepts precomputed feature
> artifacts rather than raw upstream container data in this PR. The
> existing h5_path/h5_uri H5-based path remains intact for backward
> compatibility. The feature artifact path is internal only — not wired
> to the public API schema yet. The preprocessing service/container
> that produces the feature artifact is future work.
>
> **Deferred**:
> 1. Public API wiring of feature artifact ingestion (`POST /predictions`
>    schema extension) — PR0059 or later.
> 2. Preprocessing service/container implementation — outside this PR.
> 3. Direct eosdx-container v0.3 runtime alignment — Option A (deferred).
> 4. Investor walkthrough using the feature artifact path — PR0059 or
>    later.
> 5. Retirement or replacement of `preprocessing_bridge.py` — deferred.

---

## 3. Feature Artifact Contract Plan

Create a new document at:

```
docs/feature_artifact_ingestion_boundary.md
```

### 3.1 Document structure

| Section | Content |
|---------|---------|
| **1. Purpose** | Define the feature artifact ingestion boundary for the Bremen runtime. A precomputed feature artifact carries the 15-feature v0.1 vector from upstream preprocessing to the runtime, without requiring the runtime to parse upstream container layouts. |
| **2. Scope** | Definition of the feature artifact schema, validation rules, safety boundaries, and mapping to the Bremen model input. PR0058 implements internal ingestion only — no public API wiring. |
| **3. Option C Decision** | Decision record (Section 2 of this plan). |
| **4. Upstream Source Context** | Brief summary of PR0057 findings: XRD-preprocessing v0.1.6b0, eosdx-container v0.3 with `/session/sets/` layout, heavy pyFAI/fabio deps, duplicated feature math in runtime bridge. |
| **5. Feature Artifact Schema** | See Section 3.2 below. |
| **6. Required Model Feature Columns** | The exact 15 columns from `BREMEN_V01_FEATURE_COLUMNS` with order. |
| **7. Metadata Restrictions** | What metadata is allowed (safe provenance strings, config labels) and forbidden (raw patient IDs, raw scan refs, full S3 URIs, raw checksums, local absolute paths). |
| **8. Validation Rules** | Schema version check, artifact kind check, feature column count and order check, numeric type check, finite value check (reject NaN/Inf), metadata safety check. |
| **9. Mapping to Bremen Model Input** | The validated feature artifact maps directly to the model's `plr["feature_columns"]` via exact column match and order. The existing `inference_handler.py` comparison logic (`fv.feature_names != model_cols`) is reused. |
| **10. Safety and Non-Leakage Boundaries** | No raw patient identifiers, raw scan refs, full S3 URIs, raw checksums, local paths, secrets, or real feature values in committed examples. |
| **11. Runtime/API Boundaries Preserved in PR0058** | Public request schema unchanged. h5_path/h5_uri behavior unchanged. Preprocessing_bridge unchanged. Inference_handler unchanged. Decision_support_report unchanged. Model loading unchanged. |
| **12. PR0059 Handoff** | PR0059 may wire the feature artifact path into an internal or API-controlled prediction flow for investor smoke. This PR only defines and validates the contract. |
| **13. Non-Goals** | No public API wiring, no H5 layout changes, no preprocessing bridge changes, no inference math changes, no model loading changes, no dependency additions, no upstream code vendoring, no Option A/B/D implementation. |

### 3.2 Feature artifact schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Must be `"bremen.feature_artifact.v0.1"` |
| `artifact_kind` | string | Yes | Must be `"feature_table"` |
| `feature_columns` | list of strings | Yes | Must match the 15 model feature columns exactly, in order |
| `feature_values` | list of floats | Yes | Must contain exactly 15 finite float values |
| `preprocessing_provenance` | string or null | No | Safe category string (e.g., `"xrd_preprocessing_v0.1.6b0"`) |
| `upstream_package_versions` | dict or null | No | Safe version strings (e.g., `{"xrd_preprocessing": "0.1.6b0"}`) |
| `configuration_label` | string or null | No | Safe configuration identifier |

**Prohibited metadata keys**: any key containing `_id`, `_ref`, `_path`,
`_uri`, `_checksum`, `secret`, `token`, `password`, `account`, `key`.

**Prohibited metadata values**: patterns matching `AKIA`, `s3://`,
`sha256:`, `Nova_`, `/Users/`, `/home/`, 12-digit numbers (account IDs),
`SECRET_ACCESS_KEY`, `dkr.ecr`.

### 3.3 Required feature columns

The exact 15-column order from `src/bremen/api/preprocessing_bridge.py`
(`BREMEN_V01_FEATURE_COLUMNS`):

```
weightedrms1
sigma_l1
sigma_r1
mahalanobis1
weightedrms2
sigma_l2
sigma_r2
mahalanobis2
peak14_intensity
mean_peak_value_raw
wasserstein_distance_muLR
cosine_distance_full_q2
wasserstein_distance_full_q2
meanrms1
meanrms2
```

**Source evidence**: `BREMEN_V01_FEATURE_COLUMNS` in
`src/bremen/api/preprocessing_bridge.py` lines 35–51. This is the
canonical runtime feature column list. The inference handler
(`inference_handler.py` line 157) validates `fv.feature_names != model_cols`
where `model_cols = plr["feature_columns"]`. The bridge's feature list
must match the model's `feature_columns` exactly.

---

## 4. Implementation File Plan

### 4.1 Files to create

| File | Type | Description |
|------|------|-------------|
| `docs/feature_artifact_ingestion_boundary.md` | New | Feature artifact contract document (Section 3) |
| `src/bremen/feature_artifacts.py` | New | Feature artifact validation and loading module (Section 5) |
| `tests/test_bremen_feature_artifacts.py` | New | Unit tests for feature artifact module (Section 6) |
| `.project-memory/pr/0058-feature-artifact-ingestion-boundary/IMPLEMENTATION_REPORT.md` | New | Implementation report (per new workflow) |

### 4.2 Files optionally modified

| File | Change | Justification | Recommended? |
|------|--------|---------------|-------------|
| `docs/preprocessing_source_reconciliation.md` | Add cross-reference to `docs/feature_artifact_ingestion_boundary.md` | The reconciliation document documents Option C as an option. Adding a note that Option C was selected and links to the implementation PR is context-appropriate. | **Yes** — add one paragraph at the end of Section 11 (Recommended Next Step) |

### 4.3 Files NOT changed

- `src/bremen/api/preprocessing_bridge.py` — No change.
- `src/bremen/api/inference_handler.py` — No change.
- `src/bremen/api/h5_layouts.py` — No change.
- `src/bremen/api/preflight.py` — No change.
- `src/bremen/api/schemas.py` — No change (public schema unchanged).
- `src/bremen/api/decision_support.py` — No change.
- `src/bremen/api/model_state.py` — No change.
- `src/bremen/h5_inputs.py` — No change.
- `src/bremen/pipelines.py` — No change.
- `src/bremen/model_loader.py` — No change.
- `src/bremen/inference.py` — No change.
- `docs/api_contract.md` — No change (public schema unchanged).
- `docs/product_input_pipeline_contract.md` — No change.
- `docs/converter_preprocessing_boundary.md` — No change.
- `docs/production_e2e_smoke.md` — No change.
- `docs/release_readiness_operator_notes.md` — No change.
- `ROADMAP.md` — No change.
- `docs/adr/` — No ADR changes.
- `config/`, `Dockerfile*`, `infra/`, `.github/`, `requirements.txt`,
  `pyproject.toml`, `agents/` — No changes.

---

## 5. Feature Artifact Module Plan

Create a pure, small module at:

```
src/bremen/feature_artifacts.py
```

### 5.1 Module requirements

| # | Requirement |
|---|-------------|
| 1 | Use only standard library plus already-present project dependencies (numpy, but avoid it if possible). The module should work with just `json`, `math`, `typing`, and standard library. |
| 2 | Define safe exception classes: `FeatureArtifactError` (base), `FeatureArtifactValidationError` (validation failures), `FeatureArtifactSchemaError` (schema version / artifact kind mismatch). |
| 3 | Define `FEATURE_ARTIFACT_SCHEMA_VERSION = "bremen.feature_artifact.v0.1"` as the expected schema version. |
| 4 | Define `REQUIRED_FEATURE_COLUMNS` as the exact 15-column tuple matching `BREMEN_V01_FEATURE_COLUMNS` from `preprocessing_bridge.py`. (Duplicate from `preprocessing_bridge.py` rather than importing from it — this keeps the feature artifact module independent and avoids coupling to the H5-based bridge. The duplication is documented in the module docstring.) |
| 5 | Define `EXPECTED_FEATURE_COUNT = 15`. |
| 6 | Define `validate_feature_artifact(artifact: dict) -> dict` — validates the artifact dict against all rules: schema_version, artifact_kind, feature_columns exact match, feature_values count, finite values, unsafe metadata keys/values. Returns the validated artifact dict with feature values coerced to `float`. Raises `FeatureArtifactValidationError` or `FeatureArtifactSchemaError` on any violation. |
| 7 | Define `load_feature_artifact_from_dict(artifact: dict) -> dict` — calls `validate_feature_artifact` and returns the validated, normalized artifact dict. This is the primary entry point for in-memory usage. |
| 8 | Define `load_feature_artifact_from_json(path: str) -> dict` — reads a JSON file, parses it, and calls `validate_feature_artifact`. For controlled dev/test use only. Does not perform network calls or S3 staging. |
| 9 | Define `_check_unsafe_metadata(metadata: dict) -> list[str]` — checks metadata dict for prohibited keys and values. Returns list of warning strings (does not raise). |
| 10 | Define `_check_forbidden_value(value: str) -> bool` — checks a single string value against forbidden patterns. |
| 11 | Do NOT import `xrd_preprocessing`, `eosdx-container`, `boto3`, `requests`, `httpx`, `h5py`, or `joblib`. |
| 12 | Do NOT perform network calls, file system writes, or H5 parsing. |
| 13 | Do NOT call `ModelState`, `model_loader`, or `inference_handler`. |
| 14 | Do NOT modify the artifact in place (defensive copy). |

### 5.2 Example usage (documentation only)

```python
from bremen.feature_artifacts import load_feature_artifact_from_dict

artifact = {
    "schema_version": "bremen.feature_artifact.v0.1",
    "artifact_kind": "feature_table",
    "feature_columns": ["weightedrms1", "sigma_l1", ..., "meanrms2"],
    "feature_values": [0.5, 0.3, ..., 0.8],
    "preprocessing_provenance": "xrd_preprocessing_v0.1.6b0",
}
validated = load_feature_artifact_from_dict(artifact)
# validated["feature_values"] is a list of 15 floats
# validated["feature_columns"] matches REQUIRED_FEATURE_COLUMNS
```

### 5.3 Prohibited metadata key detection

```python
_PROHIBITED_METADATA_KEY_PATTERNS = (
    "_id", "_ref", "_path", "_uri", "_checksum",
    "secret", "token", "password", "account", "key",
)
```

A metadata key is unsafe if any pattern in `_PROHIBITED_METADATA_KEY_PATTERNS`
is a substring of the lowercased key (case-insensitive).

### 5.4 Forbidden value patterns

```python
_FORBIDDEN_VALUE_PATTERNS = (
    "AKIA", "s3://", "sha256:", "Nova_",
    "/Users/", "/home/", "SECRET_ACCESS_KEY", "dkr.ecr",
)
```

Metadata values matching any pattern are unsafe. Additionally, any string
matching a 12-digit number (AWS account ID pattern) via regex is unsafe.

### 5.5 Docstring note on duplication

The module docstring must include:

> This module duplicates the feature column list from
> ``src/bremen/api/preprocessing_bridge.BREMEN_V01_FEATURE_COLUMNS``
> intentionally. This preserves independence from the H5-based
> preprocessing bridge and avoids coupling the feature artifact
> ingestion path to H5 layout assumptions. The two lists must be kept
> in sync. A future PR may extract a shared feature column constant.

---

## 6. Static and Unit Test Plan

Create a new test file at:

```
tests/test_bremen_feature_artifacts.py
```

### 6.1 Test requirements

All tests use synthetic in-memory data only. No real artifact files,
no H5 files, no model artifacts.

| Test class | Tests |
|------------|-------|
| `TestRequiredColumns` | `REQUIRED_FEATURE_COLUMNS` matches the exact 15 columns from `BREMEN_V01_FEATURE_COLUMNS` in `preprocessing_bridge.py`. `EXPECTED_FEATURE_COUNT == 15`. |
| `TestValidArtifact` | A valid synthetic artifact passes `validate_feature_artifact()` and returns a dict with correct structure and float values. |
| `TestFeatureOrderNormalization` | If features are supplied in a different order, the module normalizes them to match `REQUIRED_FEATURE_COLUMNS` order. (Design note: if the plan chooses strict order-only instead of normalization, update this test.) |
| `TestMissingFeatureRejected` | An artifact missing a required feature column is rejected with `FeatureArtifactValidationError`. |
| `TestExtraFeatureRejected` | An artifact with extra columns beyond the 15 is rejected. |
| `TestNonNumericValueRejected` | A non-numeric feature value (string, None, dict) is rejected. |
| `TestNaNRejected` | A `float('nan')` feature value is rejected. |
| `TestInfinityRejected` | A `float('inf')` or `float('-inf')` feature value is rejected. |
| `TestWrongSchemaVersionRejected` | A `schema_version` other than `"bremen.feature_artifact.v0.1"` is rejected with `FeatureArtifactSchemaError`. |
| `TestWrongArtifactKindRejected` | An `artifact_kind` other than `"feature_table"` is rejected. |
| `TestUnsafeMetadataKeyRejected` | A metadata key containing `_id`, `_ref`, `_path`, `_uri`, `_checksum`, `secret`, `token`, `password`, `account`, or `key` is rejected. |
| `TestUnsafeMetadataValueRejected` | A metadata value containing `AKIA`, `s3://`, `sha256:`, `Nova_`, `/Users/`, `/home/`, `SECRET_ACCESS_KEY`, `dkr.ecr`, or a 12-digit number is rejected. |
| `TestRawPatientIdentifierRejected` | A metadata value containing `Nova_` pattern is rejected. |
| `TestRawScanRefRejected` | A metadata value containing scan ref patterns is rejected (test with plausible ref string). |
| `TestFullS3UriRejected` | A metadata value looking like `s3://bucket/key` is rejected. |
| `TestChecksumLikeRejected` | A metadata value that is a 64-character hex string (checksum-like) is rejected. |
| `TestLocalPathRejected` | A metadata value containing `/Users/` or `/home/` is rejected. |
| `TestNoXRDImport` | Loading the `feature_artifacts` module does NOT import `xrd_preprocessing`, `eosdx-container`, `boto3`, `requests`, `httpx`, `joblib`, or `h5py`. (AST check on import lines.) |
| `TestNoH5PathH5UriChange` | The module does not reference `h5_path`, `h5_uri`, or `h5_inputs`. (String search.) |
| `TestNoInferenceCall` | The module does not import or call `inference_handler`, `model_state`, `model_loader`, `preprocessing_bridge`. (AST check.) |
| `TestDocLinkToFeatureArtifact` | `docs/feature_artifact_ingestion_boundary.md` exists and documents the schema. |
| `TestNoDemoOnlyFork` | The contract doc states this is not a demo-only format. |
| `TestNoDiagnosis` | The contract doc states no diagnosis. |
| `TestNoClinicalValidation` | The contract doc states no clinical validation. |
| `TestNoReplacement` | The contract doc states no replacement of MRI, biopsy, radiologist, clinician, or clinical judgment. |
| `TestNoRealArtifacts` | No real `.h5`, `.hdf5`, `.gfrm`, `.joblib`, `.pkl`, `.npy`, `.npz`, `.parquet`, `.proto`, `.pb` files in committed examples. |
| `TestNoSecrets` | No `AKIA`, `SECRET_ACCESS_KEY`, `dkr.ecr`, non-placeholder `s3://`, `sha256:` hex strings, `Nova_`, `/Users/`, `/home/`, 12-digit account IDs in committed docs or tests. |

---

## 7. Investor Path Plan

### 7.1 PR0058 impact on investor demonstration

| Aspect | Impact |
|--------|--------|
| **What PR0058 delivers** | A safe, validated feature artifact ingestion boundary. The runtime can accept a precomputed 15-feature vector from external preprocessing. |
| **Investor message** | "Bremen now has a controlled bridge from upstream preprocessing output to model inference. The feature artifact contract is the same for demo and production." |
| **Productization path** | The same contract will be produced by the real `xrd_preprocessing`/`eosdx-container` pipeline in production. No separate demo format. |
| **Limitations** | PR0058 does not wire the artifact path into the public API. A demo must use the internal `load_feature_artifact_from_dict()` or `load_feature_artifact_from_json()` directly (not via `POST /predictions`). This is temporary — PR0059 will wire the API path. |
| **Next step** | PR0059 wires an internal or API-controlled feature artifact prediction path for investor smoke. |

### 7.2 How PR0058 avoids demo-only formats

The feature artifact schema (`bremen.feature_artifact.v0.1`) is the same
contract that a production preprocessing service would produce. The only
difference is the preprocessing path: synthetic data for demo, upstream
`xrd_preprocessing`/`eosdx-container` for production. The runtime does
not distinguish between the two.

### 7.3 How PR0058 avoids heavy deps in runtime

The feature artifact is validated using only standard library types
(JSON parsing, string matching, basic math). No numpy, no h5py, no
joblib, no pyFAI, no fabio, no xrd_preprocessing, no eosdx-container.
The heavy dependencies remain in the preprocessing service.

---

## 8. New Workflow Requirements

### 8.1 Implementation report

The coder implementing PR0058 must create:

```
.project-memory/pr/0058-feature-artifact-ingestion-boundary/IMPLEMENTATION_REPORT.md
```

The implementation report must include all required fields from
`.project-memory/IMPLEMENTATION_REPORT_WORKFLOW.md` Section 5,
including:

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

The precommit-review agent for PR0058 must read and reconcile:

| # | Source | Purpose |
|---|--------|---------|
| 1 | `.project-memory/pr/0058-feature-artifact-ingestion-boundary/PLAN.md` | Planned scope and allowed files |
| 2 | `.project-memory/pr/0058-feature-artifact-ingestion-boundary/reviews/plan-review.yml` | Plan-review approval |
| 3 | `.project-memory/pr/0058-feature-artifact-ingestion-boundary/IMPLEMENTATION_REPORT.md` | Coder claims and validation |
| 4 | `git status --short` | Working tree state |
| 5 | `git diff --name-only` | Actual changed files |
| 6 | Relevant changed files (selected sections) | Implementation quality |
| 7 | Relevant unchanged boundary files | Files outside scope not touched |
| 8 | Validation output from implementation report | Compare with own validation |

The precommit-review agent must write:

```
.project-memory/pr/0058-feature-artifact-ingestion-boundary/reviews/precommit-review.yml
```

with `final_gatekeeper_summary` per the IMPLEMENTATION_REPORT_WORKFLOW.md
schema.

### 8.3 Blocking conditions for this PR

The precommit-review must block if:
- IMPLEMENTATION_REPORT.md is missing.
- Implementation report contradicts PLAN.md.
- Implementation report contradicts git diff.
- Any source file outside the allowed set was changed.
- The new module imports `xrd_preprocessing`, `eosdx-container`, `boto3`,
  or any network client.
- The new module uses `h5py` or `joblib`.
- The new module modifies `h5_path`/`h5_uri` behavior.
- Any safety check reveals secrets or forbidden patterns.

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
# New feature artifact tests
python -m pytest -q tests/test_bremen_feature_artifacts.py -v

# PR0057 reconciliation tests (should still pass)
python -m pytest -q tests/test_bremen_preprocessing_source_reconciliation.py -v

# API contract tests (schema unchanged)
python -m pytest -q tests/test_bremen_api_contract.py -v

# Full suite
python -m pytest -q
```

### 9.4 Safety validation

```bash
# Confirm no unintended file changes
git diff --name-only

# Confirm no restricted files changed
git diff --name-only -- Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml src/bremen/training agents config docs/adr ROADMAP.md

# Confirm no binary artifacts
git diff --name-only | grep -E '\.(h5|hdf5|gfrm|GFRM|joblib|pkl|npy|npz|parquet|proto|pb|tfstate|tfstate\.backup)$' || true

# FastAPI/uvicorn/starlette — not introduced
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n docs tests src ROADMAP.md || true

# Matador/network clients — not introduced in new module
grep -R "MATADOR_\|Matador.*token\|Matador.*URL\|requests\|httpx\|aiohttp" -n docs tests src ROADMAP.md || true

# Secrets/identifiers — not present
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|s3://\|sha256:\|Nova_\|/Users/\|/home/" -n docs tests src .project-memory || true

# Clinical claims — only negated safety language
grep -R "diagnos\|clinical validation\|clinically validated\|replace radiologist\|replace clinician\|replace MRI\|replace biopsy" -n docs tests src .project-memory || true
```

---

## 10. Implementation Order

1. Create `docs/feature_artifact_ingestion_boundary.md`
2. Create `src/bremen/feature_artifacts.py`
3. Create `tests/test_bremen_feature_artifacts.py`
4. (Optional) Add cross-reference note to `docs/preprocessing_source_reconciliation.md`
5. Create `.project-memory/pr/0058-feature-artifact-ingestion-boundary/IMPLEMENTATION_REPORT.md`
6. Run validation (Section 9)
7. Commit with message: `feat(pr0058): feature artifact ingestion boundary — Option C, safe validation module`

---

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Feature columns diverge between `feature_artifacts.py` and `preprocessing_bridge.py` | Medium | High | Documented duplication with warning in module docstring. Future PR should extract shared constant. |
| New module is accidentally wired into public API in this PR | Low | High | Plan explicitly prohibits API schema changes. Tests verify no API surface change. |
| Upstream feature schema changes before PR0059 | Low | Medium | The contract version (`bremen.feature_artifact.v0.1`) is versioned. Schema changes require a new version. |
| Preprocessing service produces artifact with wrong column order | Medium | Low | The loader validates exact column order. Reordering or column count mismatch is caught by `validate_feature_artifact()`. |

---

## 12. Non-Goals

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
12. No H5 parsing implementation.
13. No pyFAI/fabio dependency addition.
14. No upstream code vendoring.
15. No Matador integration.
16. No FastAPI.
17. No runtime training.
18. No model training implementation.
19. No new model.
20. No demo-only fork.
21. No real data artifacts committed.
22. No clinical validation claims.
23. No diagnosis claims.
24. No replacement of clinical judgment.
25. No investor walkthrough implementation yet.
26. No public API wire-up yet (PR0059).
27. No preprocessing bridge replacement or removal.

---

Implementation role: coder
