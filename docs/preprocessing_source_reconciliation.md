# Bremen Preprocessing Source Reconciliation

**PR0057** — Preprocessing source reconciliation and integration
decision. Documentation and static tests only; no implementation.

---

## 1. Purpose

This document reconciles Bremen's documented canonical input contract
and runtime assumptions with the real upstream preprocessing and
container source code.

**PR0057 does not:**
- Implement converter or preprocessing integration code.
- Change runtime behavior.
- Choose the final canonical layout or integration option.
- Silently correct the PR0055/PR0056 canonical input contract.

**PR0057 creates a human decision gate** before any further
implementation can proceed toward PR0058 (product smoke) or
investor walkthrough.

---

## 2. Scope

**Covered**: Inventory of upstream source packages (XRD-preprocessing,
eosdx-container v0.3), verification of PR0055/PR0056 canonical layout
against real container output, runtime vs training feature path
comparison, duplicate feature computation assessment, four integration
decision options (A/B/C/D), and recommended next step.

**Not covered**: Converter implementation, GFRM parsing in runtime,
pyFAI/fabio dependency addition, upstream code vendoring, runtime
request schema changes, Matador integration, FastAPI, runtime
training, clinical validation, or diagnosis.

---

## 3. Source Archives Inspected

Two upstream source archives were extracted and inspected outside the
Bremen repository:

- **XRD-preprocessing source archive** — extracted inspection copy
  containing the `xrd-preprocessing` Python package (v0.1.6b0 beta).
- **eosdx-container v0.3 source archive** — extracted inspection copy
  containing the `eosdx-container` Python package (v0.1.0) on the
  `feat-v0_3-eoscan-session-container` branch.

No upstream source was vendored, copied, or committed into the Bremen
repository. All inspection was read-only.

---

## 4. XRD-Preprocessing Inventory

### 4.1 Package identity

| Attribute | Value |
|-----------|-------|
| Package name | `xrd-preprocessing` |
| Version | `0.1.6b0` (beta) |
| Python requirement | `>=3.13,<3.14` |
| Build system | Hatchling >= 1.25 |

### 4.2 Dependencies

| Dependency | Version | Risk to runtime inclusion |
|-----------|---------|--------------------------|
| numpy | >= 1.26, <3 | Low — already in runtime |
| pandas | >= 2.2 | Low |
| scipy | >= 1.14 | Low |
| scikit-learn | >= 1.5 | Low |
| joblib | >= 1.4 | Low — already in runtime |
| PyYAML | >= 6.0 | Low |
| h5py | >= 3.12 | Low — already in runtime |
| **pyFAI** | **>= 2025.1** | **High — heavy C-extension; azimuthal integration** |
| **fabio** | **>= 2025.10** | **High — XRD image format decoder** |
| marimo | >= 0.10 | Low (notebook tool, not runtime-critical) |
| matplotlib | >= 3.9 | Low (plotting, not runtime-critical) |

**Key risk**: pyFAI and fabio are heavy scientific C-extension
libraries. They should NOT be added to the lightweight Bremen runtime
container.

### 4.3 YAML configuration templates

- `preprocessing_config_template.yaml` — Main preprocessing pipeline
  configuration template.
- `preprocessing_branch_config_template.yaml` — Branch-specific
  (one_to_one / one_to_many) configuration template.

Both templates define 8+ required config sections.

### 4.4 Config loader and validator

- `xrd_preprocessing.config.load_preprocessing_config()` — Loads and
  validates YAML preprocessing config.
- `validate_preprocessing_config()` — Validates config structure against
  required sections.

### 4.5 Pipeline builder and transformer registry

- `xrd_preprocessing.pipeline.build_pipeline_from_config()` — Builds
  a scikit-learn `Pipeline` from YAML `pipeline.steps`.
- `build_pipeline_steps_from_config()` — Resolves transformer names
  against the `TRANSFORMER_REGISTRY`.
- `TRANSFORMER_REGISTRY` — Registry dict with 28 transformers.

### 4.6 GFRM converter functions

Located in `src/xrd_preprocessing/gfrm.py`:

- `decode_gfrm()` — Decode GFRM raw vendor bytes.
- `gfrm_to_photons()` — Convert GFRM to photon-count image.
- `gfrm_conversion_metadata()` — Extract GFRM conversion metadata.
- `gfrm_photon_statistics()` — Compute photon statistics from GFRM.
- `save_gfrm_as_npy()` — Save converted GFRM as NPY artifact.
- `convert_gfrm_to_npy.py` — CLI entry point for GFRM conversion.

### 4.7 H5 and DataFrame transformers

Located in `xrd_preprocessing/transformers/h5.py`:

- `H5SessionSelectorTransformer` — Filter H5 sessions by criteria.
- `H5MeasurementSetAuditTransformer` — Audit measurement sets.
- `H5ToDataFrameTransformer` — Read v0.3 session containers into
  pandas DataFrames using `eosdx-container`.
- `H5BlobDataFrameTransformer` — Read blob-based H5 data.

### 4.8 Preprocessing artifact writer and reader

Located in `src/xrd_preprocessing/artifacts.py`:

- `save_preprocessing_artifact()` — Serialize preprocessing results
  to joblib artifact.
- `load_preprocessing_artifact()` — Load preprocessing artifact.
- `load_preprocessing_dataframe()` — Load preprocessing DataFrame.

### 4.9 Examples

- `examples/00_product_gfrm_preprocessing_pipeline.py` — Full product
  pipeline from GFRM through preprocessing.
- `examples/01_h5_session_filter_demo.py` — H5 session filtering.
- `examples/03_gfrm_converter_demo.py` — GFRM conversion demo.

### 4.10 Tests

15 test files covering pipeline builder, config validation, H5 v0.3
container reading, GFRM conversion, transformers, filters, SNR, faulty
pixel detection, azimuthal integration, normalization.

---

## 5. eosdx-Container v0.3 Inventory

### 5.1 Package identity

| Attribute | Value |
|-----------|-------|
| Package name | `eosdx-container` |
| Version | `0.1.0` |
| Python requirement | `>=3.7` |
| Dependencies | **h5py and numpy only** (lightweight) |

### 5.2 Supported container versions

- **v0_1** — Legacy format (deprecated).
- **v0_2** — NeXus-based technical container.
- **v0_3** — Session container (the branch inspected; `feat-v0_3-eoscan-session-container`).

### 5.3 v0.3 session container schema

**Schema version**: `"0.3"`
**Format**: `"xrd-session"`
**Layout root**: `/session`
**Set naming**: `set_{NNN}_{label}` — zero-padded 3-digit index (1-based) + label.

### 5.4 HDF5 layout — groups and datasets

#### Root groups

| Path | Description |
|------|-------------|
| `/session/` | Session root |
| `/session/sample/` | Sample metadata |
| `/session/instrument/` | Instrument metadata |
| `/session/instrument/detector_sets/` | Per-detector-set metadata |
| `/session/dependencies/` | Dependency graph (edges) |
| `/session/sets/` | **Measurement sets (core data)** |

#### Per-set structure

Each set (`/session/sets/{set_id}/`) contains:

| Path | Description |
|------|-------------|
| `{set_id}/acquisition/` | Acquisition metadata |
| `{set_id}/measurements/` | Per-measurement data |
| `{set_id}/qc/` | Quality-control results (priority-ordered `qc_NN_name` groups with verdicts: PASS/WARNING/FAIL/ERROR) |
| `{set_id}/integration/` | Azimuthal integration: `i`, `q`, `sigma` (1D profiles) |
| `{set_id}/processing/` | Processing provenance: `config` (JSON recipe), `step_*` (execution logs) |
| `{set_id}/artifacts/` | Artifacts: `poni`, `preview` |
| `{set_id}/raw_file` | Original vendor source bytes (`.gfrm`/`.png`/`.h5`) |
| `{set_id}/raw/data` | Stitched 2D raw data |
| `{set_id}/processed/data` | Final processed matrix |

### 5.5 Reader, writer, and validator

- `SessionContainer` class in `reader.py` — Lazy-access reader for v0.3
  session containers. No DataFrame conversion.
- `writer.py` — Programmatic builder for v0.3 session containers.
- `validator.py` — Structural and metadata validation.

### 5.6 Examples and tests

- `tests/v0_3/test_v0_3_build.py` — Builds and validates full session
  containers programmatically.
- `tests/v0_3/test_v0_3_qc_integration_processing.py` — Tests QC,
  integration, and processing group population.
- `tests/v0_3/test_v0_3_validator.py` — Schema validator tests.
- 7 test files total covering build, write-once, dependencies,
  QC/integration/processing, and validator.

### 5.7 CRITICAL FINDING: No `/scans/target/` or `/scans/contralateral/`

The eosdx-container v0.3 schema, writer, reader, validator, tests, and
examples contain **NO** reference to `/scans/target/`,
`/scans/contralateral/`, or any path starting with `/scans/`. The
session/set-based layout (`/session/sets/set_NNN_label/`) is the only
layout produced by this library.

---

## 6. PR0055/PR0056 Canonical Layout Check

### 6.1 Does the PR0055 canonical input package layout match eosdx-container v0.3?

**Answer**: NO.

**Evidence**:

- PR0055 `docs/product_input_pipeline_contract.md` Sections 7.2–7.3
  define the canonical Bremen input package as using:
  - `/scans/target/measurements`, `/scans/target/side`
  - `/scans/contralateral/measurements`, `/scans/contralateral/side`
  - Calibration layout: `/calib_*/sample_*/sample/patient_name`,
    `sample/sample_type`, `sets/{set_n}/integration/i`,
    `sets/{set_n}/integration/q`
- eosdx-container v0.3 uses `/session/sets/set_NNN_label/` with
  sub-groups `acquisition/`, `measurements/`, `qc/`, `integration/`,
  `processing/`, `artifacts/`, plus `raw_file`, `raw/data`,
  `processed/data` datasets.
- No path starting with `/scans/` exists in any eosdx-container v0.3
  writer, schema, reader, validator, or test.

**Consequence**: The `/scans/target/` + `/scans/contralateral/` layout
documented in PR0055 is **not producible by the real eosdx-container
library**. It is either:
- An undocumented intermediate format for Bremen-internal use, OR
- An incorrect assumption about the upstream container layout.

This must be explicitly resolved before any converter implementation or
product smoke.

### 6.2 Does the converter boundary spec repeat the same assumption?

**Answer**: YES.

**Evidence**: `docs/converter_preprocessing_boundary.md` Section 8
(Output Contract) and Section 9 (Layout and Preflight Requirements)
reference the PR0055 canonical input package as the output target. The
existing `H5LayoutAdapter` protocol detects `/scans/target/measurements`
for the canonical layout, which does not match the upstream container.

**Consequence**: The converter boundary spec inherits the same
undocumented layout assumption from PR0055. A converter written to this
spec would need to transform v0.3 session/set data into a
`/scans/target/` layout, adding an unnecessary intermediate format
unless that format is deliberately chosen.

### 6.3 Required disclaimer

**The `/scans/target/` + `/scans/contralateral/` layout is NOT proven
producible by the real eosdx-container v0.3 library.** If this layout
is retained, it must be explicitly approved as a deliberate Bremen
export/intermediate format, not mislabeled as eosdx-container v0.3.

---

## 7. Runtime vs Training Feature Path Check

### 7.1 What current docs imply

PR0055 and PR0056 describe the "Bremen feature bridge" as the
runtime-side path from H5 input to feature vector and inference.
The context implies `src/bremen/api/preprocessing_bridge.py`.

### 7.2 What the runtime code uses

| File | Role | Layout assumed |
|------|------|---------------|
| `src/bremen/api/h5_layouts.py` | H5 layout detection (adapter protocol) | `/scans/target/measurements` (canonical); `/calib_*` (calibration) |
| `src/bremen/api/preprocessing_bridge.py` | Feature extraction (15 features v0.1) | Same as detected layout |
| `src/bremen/api/inference_handler.py` | Orchestrates preflight → bridge → inference | Consumes bridge output |

The runtime bridge reads H5 profiles via `h5py`, extracts numpy arrays,
and computes 15 features using standalone numpy math — no dependency
on `xrd_preprocessing` transformers.

### 7.3 What the training/product code uses

| File | Role | Layout assumed |
|------|------|---------------|
| `src/bremen/pipelines.py` | Product preprocessing pipeline | Real eosdx-container v0.3 `/session/sets/` layout |

`pipelines.py` imports `xrd_preprocessing` transformers directly:

- `H5ToDataFrameTransformer` — reads from v0.3 session/set layout
- `AzimuthalIntegration` — azimuthal integration with pyFAI
- `FaultyPixelDetector` — pixel defect detection
- `SNRTransformer`, `SNRFilter` — signal-to-noise
- `QRangeNormalizer`, `RadialProfileValueFilter` — normalization

This is the **real product preprocessing pipeline** that works with
actual upstream container layouts.

### 7.4 Conflict assessment

**Verdict**: INCOMPATIBLE.

The runtime path (`preprocessing_bridge.py`) and the training/product
path (`pipelines.py` + `xrd_preprocessing`) assume different H5
layouts, use different computation libraries, and produce features
through independent code paths. There is no shared feature computation
module.

---

## 8. Duplicate Feature Computation Check

### 8.1 Does preprocessing_bridge.py duplicate feature computation?

**Answer**: YES.

**Evidence**: `src/bremen/api/preprocessing_bridge.py` contains
standalone numpy implementations of the following 12 functions:

| Function | Purpose |
|----------|---------|
| `_sigma_rms` | L1/L2 symmetry measures |
| `_sigma_rms_r` | RMS with alternate normalization |
| `_mahalanobis_difference` | Mahalanobis1 and Mahalanobis2 features |
| `_weighted_rms_difference` | Weighted RMS asymmetry (weightedrms1) |
| `_weighted_rms_difference_v2` | Weighted RMS variant (weightedrms2) |
| `_profile_wasserstein` | Wasserstein distance (wasserstein_distance_full_q2) |
| `_wasserstein_mulr` | Wasserstein mu/LR variant |
| `_cosine_distance` | Cosine distance (cosine_distance_full_q2) |
| `_rms_difference` | Root-mean-square asymmetry (meanrms2) |
| `_mean_rms1` | L1 mean absolute difference (meanrms1) |
| `_peak14_intensity` | Intensity at index 14 (peak14_intensity) |
| `_mean_peak_value_raw` | Mean of top-5 intensities |

These functions compute the same 15-feature v0.1 schema that the
training/product pipeline computes using `xrd_preprocessing`
transformers. They are maintained as **independent, duplicated** code.

**Consequence**: Any change to feature computation in the training
pipeline (e.g., bug fix, normalization adjustment, schema update) must
be manually duplicated in the runtime bridge. There is no shared
feature computation library.

**Warning**: Duplicated math must not become the long-term product
truth without an explicit decision. A single source of truth for
feature computation should be established.

---

## 9. Incompatible or Duplicate Paths

| # | Path | File(s) | Layout assumed | Uses xrd_preprocessing? | Status |
|---|------|---------|---------------|------------------------|--------|
| 1 | Docs contract path | `docs/product_input_pipeline_contract.md` | `/scans/target/` + `/scans/contralateral/` | No | Undocumented intermediate format — does not match upstream |
| 2 | Converter boundary spec | `docs/converter_preprocessing_boundary.md` | Same as contract | No | Inherits same undocumented assumption |
| 3 | Runtime H5/layout path | `src/bremen/api/h5_layouts.py` | `/scans/target/measurements` (canonical) or `/calib_*` (calibration) | No | Legacy layout, incompatible with v0.3 session/set |
| 4 | Runtime feature bridge | `src/bremen/api/preprocessing_bridge.py` | Same as layout | No | Duplicated numpy math; incompatible with real product pipeline |
| 5 | Training/product pipeline | `src/bremen/pipelines.py` | `/session/sets/` (real v0.3) | **Yes** | Real product pipeline, real upstream schema |
| 6 | Upstream container | `eosdx-container` v0.3 | `/session/sets/set_NNN_label/...` | N/A (upstream library) | Real upstream format |

---

## 10. Integration Decision Options

Four options are presented below. **No option is selected by PR0057.**
A human product/engineering decision is required before PR0058.

### Option A: Redefine runtime-facing canonical H5/input contract to match eosdx-container v0.3

**Summary**: Change the runtime `H5LayoutAdapter` to detect and read
the real `/session/sets/` layout. Add a new adapter. Update
`preprocessing_bridge.py` to read from v0.3 integration paths.

| Dimension | Assessment |
|-----------|-----------|
| Investor demo fit | **Good** — demo uses the same format as production, no intermediate conversion |
| Productization fit | **Good** — matches real upstream format, eliminates intermediate format |
| Runtime schema change | **No** — `POST /predictions` unchanged |
| Source/runtime changes | **Yes** — new adapter in `h5_layouts.py`, updated bridge reader |
| Preprocessing math duplication risk | **Partial** — bridge reads pre-integrated 1D profiles but still computes contour math |
| Heavy deps in runtime | **No** — eosdx-container only needs h5py + numpy; XRD-preprocessing stays outside |
| Risk level | Medium — new adapter and bridge changes required |

### Option B: Keep PR0055/PR0056 /scans/target layout as deliberate Bremen export/intermediate format

**Summary**: Keep `/scans/target/` as an intentional Bremen export
format. Require a converter to transform v0.3 session/set data into
this format before the runtime consumes it.

| Dimension | Assessment |
|-----------|-----------|
| Investor demo fit | **Conditional** — only if converter pipeline exists and runs during demo |
| Productization fit | **Partial** — adds intermediate conversion step, extra component to maintain |
| Runtime schema change | **No** — runtime is unchanged |
| Source/runtime changes | **No** — converter lives outside runtime |
| Preprocessing math duplication risk | **High** — converter adds translation layer; duplicated math remains in bridge |
| Heavy deps in runtime | **No** — converter is separate service/container |
| Risk level | Medium — requires explicit confirmation that `/scans/target/` is intentional |

### Option C: Keep runtime model-only and consume precomputed feature table/artifact

**Summary**: Runtime becomes model-only inference (plus decision-support
report). Full preprocessing runs offline or in a separate service. The
runtime receives a precomputed feature vector with schema metadata.

| Dimension | Assessment |
|-----------|-----------|
| Investor demo fit | **Conditional** — requires preprocessing service to be running for demo |
| Productization fit | **Good** — clean separation; independent scaling |
| Runtime schema change | **Yes** — `POST /predictions` needs new request schema for feature artifact |
| Source/runtime changes | **Yes** — bridge replaced with feature loader |
| Preprocessing math duplication risk | **Low** — feature computation lives in one place |
| Heavy deps in runtime | **No** — runtime only needs numpy + joblib |
| Risk level | High — major API contract and runtime architecture change |

### Option D: Introduce a dedicated preprocessing service/container

**Summary**: Standalone preprocessing service runs XRD-preprocessing +
eosdx-container, outputs canonical Bremen input package to staging.
Runtime consumes via existing `h5_path`/`h5_uri`.

| Dimension | Assessment |
|-----------|-----------|
| Investor demo fit | **Good** — preprocessing service runs during demo |
| Productization fit | **Good** — independent scaling of preprocessing and inference |
| Runtime schema change | **No** — runtime consumes via existing modes |
| Source/runtime changes | **Minimal** — runtime stays same; new preprocessing service created |
| Preprocessing math duplication risk | **Low** — preprocessing math in service; runtime bridge can be updated |
| Heavy deps in runtime | **No** — heavy deps stay in preprocessing service |
| Risk level | Medium — new service to deploy and operate |

---

## 11. Recommended Next Step

**Human product/engineering decision gate before PR0058.**

No implementation should proceed until Option A, B, C, or D is
selected by the human product/engineering team.

**Decision guidance**:

1. If **Option A** (redefine runtime H5 contract): PR0058 should
   implement the new `SessionContainerV03LayoutAdapter` and update
   `preprocessing_bridge.py` to read from v0.3 integration paths.
2. If **Option B** (keep intermediate format): Humans must explicitly
   confirm `/scans/target/` as an intentional Bremen export/intermediate
   layout, not eosdx-container v0.3. PR0058 should specify the
   converter contract from v0.3 → `/scans/target/`.
3. If **Option C** (model-only runtime): PR0058 should update the API
   contract and replace `preprocessing_bridge.py` with a feature
   artifact loader.
4. If **Option D** (preprocessing service): PR0058 should specify the
   preprocessing service API contract and staging interface.

**No demo-only fork is allowed.** Whatever option is chosen must apply
equally to investor demonstrations and production deployments.

**PR0058 update**: Option C was selected.  The feature artifact
ingestion boundary is defined in
[docs/feature_artifact_ingestion_boundary.md](feature_artifact_ingestion_boundary.md).
PR0058 implements internal validation only — no public API wiring.
Options A, B, and D remain deferred.
`/scans/target/` remains not eosdx-container v0.3.

---

## 12. Safety and Non-Leakage Boundaries

This reconciliation document and all committed examples must not
contain:

1. Real GFRM, H5, joblib, parquet, protobuf, or model artifacts.
2. Raw patient identifiers (names, IDs, `Nova_` patterns).
3. Raw target/control scan refs with real patient data.
4. Full S3 URIs (`s3://bucket/key`); use `${VARIABLE}` notation.
5. Raw SHA-256 checksums.
6. AWS credentials, access keys, account IDs, or registry URLs.
7. Local-machine absolute paths (`/Users/`, `/home/`).
8. Clinical validation claims.
9. Diagnosis claims.
10. Replacement of MRI, biopsy, radiologist, clinician, or clinical
    judgment.

---

## 13. Open Questions

1. **Which option (A/B/C/D) should be selected?** Final decision rests
   with human product/engineering.
2. **Is `/scans/target/` an intentional Bremen export format?** If
   Option B is chosen, this must be explicitly confirmed.
3. **Should runtime align to eosdx-container v0.3 directly?** Option A
   resolution.
4. **Should xrd_preprocessing remain offline-only or enter runtime as
   optional dependency?** Determines whether pyFAI/fabio enter the
   runtime dependency tree.
5. **Where should heavy dependencies (pyFAI/fabio) live?** If they
   cannot enter runtime, they must be isolated in a preprocessing
   service or container.
6. **What is the minimal investor-presentable product path after the
   decision?** Determines scope and priority of PR0058.

---

## 14. Non-Goals

1. No converter implementation.
2. No Preprosync implementation.
3. No protobuf parser.
4. No GeoFrame parser.
5. No GFRM conversion execution in Bremen runtime.
6. No pyFAI/fabio dependency addition to runtime.
7. No upstream code vendoring into Bremen.
8. No runtime request schema change.
9. No `h5_path`/`h5_uri` behavior change.
10. No Matador integration.
11. No FastAPI, uvicorn, starlette, or ASGI.
12. No runtime training.
13. No model training implementation.
14. No new model.
15. No inference or preprocessing math changes.
16. No demo-only fork.
17. No real data artifacts committed.
18. No clinical validation.
19. No diagnosis.
20. No replacement of MRI, biopsy, radiologist, clinician, or clinical
    judgment.
21. No product smoke implementation (PR0058 scope).
22. No investor walkthrough implementation (PR0059+ scope).
23. No silent canonical layout correction without human decision.
