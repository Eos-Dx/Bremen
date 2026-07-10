# Plan: PR0057 — Preprocessing Source Reconciliation And Integration Decision

**PR**: 0057-preprocessing-source-reconciliation  
**Role**: plan  
**Mode**: planning  
**Branch**: 0057-preprocessing-source-reconciliation  
**HEAD**: 84e9891f41adfc701170f7fc403386c8acedc675  
**PR sequence**: PR0057 (third PR of Product Input Pipeline Readiness block, follows PR0055 + PR0056)  

---

## 1. ROADMAP Alignment

1. **PR0057 follows PR0055 and PR0056.** PR0055 defined the canonical input
   contract. PR0056 defined the converter boundary. PR0057 now reconciles
   those documents with real upstream source code.

2. **PR0057 is reconciliation/inventory/decision-planning only.** No
   implementation. No converter integration. No silent correction.

3. **PR0057 does not start product smoke.** PR0058 remains separate.

4. **PR0057 does not start investor walkthrough.** Future PR.

5. **PR0057 does NOT silently redefine the canonical input package.** The
   reconciliation explicitly flags conflicts and defers resolution.

---

## 2. Upstream Source Inventory

Both upstream archives were extracted and inspected under `/tmp/bremen-upstream-inspection/`.
No upstream source was copied into the Bremen repository.

### 2.1 XRD-preprocessing package

| Attribute | Value |
|-----------|-------|
| **Package name** | `xrd-preprocessing` |
| **Version** | `0.1.6b0` (beta) |
| **Python version** | `>=3.13,<3.14` |
| **Build system** | Hatchling >= 1.25 |
| **Dependencies** | numpy, pandas, scipy, scikit-learn, joblib, PyYAML, h5py, **pyFAI>=2025.1**, **fabio>=2025.10**, marimo, matplotlib |
| **Opaque install dep** | `-e /Users/sad/dev/container` in requirements.txt (editable eosdx-container) |
| **YAML templates** | `src/xrd_preprocessing/configs/preprocessing_config_template.yaml` and `preprocessing_branch_config_template.yaml` |
| **Config loader** | `xrd_preprocessing.config.load_preprocessing_config()` validates 8+ required sections |
| **Pipeline builder** | `xrd_preprocessing.pipeline.build_pipeline_from_config()` — builds sklearn `Pipeline` from YAML `pipeline.steps` |
| **Transformer registry** | `TRANSFORMER_REGISTRY` dict (28 transformers) in `pipeline.py` |
| **GFRM conversion** | `src/xrd_preprocessing/gfrm.py` — `gfrm_to_photons()` and `convert_gfrm_to_npy.py` CLI |
| **H5/session readers** | `H5ContainerReader` class in `xrd_preprocessing/h5.py` — reads v0.3 session containers via `eosdx-container` |
| **H5 transformers** | `H5SessionSelectorTransformer`, `H5ToDataFrameTransformer`, `H5BlobDataFrameTransformer` in `transformers/h5.py` |
| **Artifact writer/reader** | `src/xrd_preprocessing/artifacts.py` — joblib artifact assembly/writing for model output |
| **Examples** | `examples/00_product_gfrm_preprocessing_pipeline.py`, `01_h5_session_filter_demo.py`, `03_gfrm_converter_demo.py` |
| **Tests** | 15 test files covering pipeline builder, config validation, H5 v0.3, GFRM, transformers, filters, SNR |

**Key finding**: XRD-preprocessing depends on **pyFAI** (heavy C-extension
scientific library for azimuthal integration) and **fabio** (XRD image
format decoder). These are heavy dependencies that should NOT be added to
the Bremen runtime container.

### 2.2 eosdx-container package (v0.3 branch)

| Attribute | Value |
|-----------|-------|
| **Package name** | `eosdx-container` |
| **Version** | `0.1.0` |
| **Python version** | `>=3.7` |
| **Dependencies** | **Only h5py and numpy!** |
| **Supported versions** | v0_1 (legacy), v0_2 (NeXus-based), v0_3 (session container — this branch) |
| **v0.3 schema** | `src/container/v0_3/schema.py` — `schema_version="0.3"`, `format="xrd-session"` |
| **v0.3 layout** | `/session/sets/set_NNN_label/` groups; no `/scans/target/` or `/scans/contralateral/` |
| **Set naming** | `set_001_dark`, `set_002_label` — zero-padded 3-digit index + label |
| **Set children** | `acquisition/`, `measurements/`, `qc/`, `integration/`, `processing/`, `artifacts/` |
| **Raw file** | `raw_file` — original vendor source bytes (`.gfrm`/`.png`/`.h5`) per measurement |
| **Raw/processed** | `raw/data` (stitched 2D), `processed/data` (final matrix) |
| **Integration** | `integration/q`, `integration/i`, `integration/sigma` |
| **QC** | `qc/` with priority-ordered check groups, verdicts (PASS/WARNING/FAIL/ERROR) |
| **Processing** | `processing/config` (JSON recipe), `processing/step_*` (execution log) |
| **Artifacts** | `artifacts/poni`, `artifacts/preview` |
| **Reader** | `SessionContainer` class — lazy access, no DataFrame conversion |
| **Writer** | `src/container/v0_3/writer.py` — builds session containers programmatically |
| **Validator** | `src/container/v0_3/validator.py` — structural/metadata validation |
| **Examples** | `tests/v0_3/test_v0_3_build.py`, `tests/v0_3/test_v0_3_qc_integration_processing.py` |
| **Tests** | 7 test files covering build, write-once, dependencies, QC/integration/processing, validator |

**Key finding**: eosdx-container v0.3 has **NO** `/scans/target/measurements`
or `/scans/contralateral/` paths. Its layout is session/set-based:
`/session/sets/set_NNN_label/...`. The PR0055/PR0056 "canonical layout"
(`/scans/target/` + `/scans/contralateral/`) does **NOT** match any
eosdx-container v0.3 writer output.

### 2.3 Evidence gaps

| Gap | Status |
|-----|--------|
| Versioning/release status | XRD-preprocessing is v0.1.6b0 (beta). eosdx-container is v0.1.0 (pre-1.0). Neither is a stable release. |
| Dependency strategy | XRD-preprocessing requires pyFAI+fabio (heavy C-ext). Runtime must NOT include these. |
| Runtime compatibility | XRD-preprocessing Python constraint `>=3.13,<3.14` matches Bremen's runtime (3.13). But heavy dependencies make runtime-inclusion infeasible. |
| Adapter architecture | Converter should be a SEPARATE preprocessing service/container, not part of runtime. |

---

## 3. Reconciliation Check

### 3.1 Does the "canonical Bremen input package" layout match eosdx-container v0.3?

**answer**: NO

**evidence**: 
- `eosdx-container` v0.3 schema uses `/session/sets/set_001_label/...` layout
  with `measurements/`, `integration/`, `raw/data`, `processed/data`,
  `raw_file`, `artifacts/poni`, `processing/config` as children of each set group.
- The PR0055 contract (sections 7.2–7.3) defines `/scans/target/measurements`,
  `/scans/target/side`, `/scans/contralateral/measurements`,
  `/scans/contralateral/side` and calibration layout paths — **none of which**
  exist in any eosdx-container v0.1/v0.2/v0.3 writer, schema, or test.
- The XRD-preprocessing `H5ContainerReader` reads from the `/session/sets/`
  layout, not `/scans/target/`.
- The XRD-preprocessing integrated 1D profiles live at `integration/q` and
  `integration/i` under each set group — not at `/scans/target/measurements`.

**consequence**: The `/scans/target/` + `/scans/contralateral/` layout
documented in PR0055 is **not producible by the real eosdx-container
library**. It is an undocumented intermediate format or a Bremen-internal
assumption. PR0055/PR0056 assumed this layout without verifying it against
the upstream container schema.

### 3.2 Does the converter boundary spec repeat the same layout assumption?

**answer**: YES

**evidence**:
- `docs/converter_preprocessing_boundary.md` Section 8 (Output Contract)
  references the PR0055 canonical input package, which uses `/scans/target/`
  layout. Section 9 (Layout and Preflight Requirements) says "The converter
  output must pass the existing `H5LayoutAdapter` detection" — the existing
  adapter detects `/scans/target/measurements` for canonical layout.
- The converter spec therefore inherits the same layout assumption from
  PR0055 without verifying it against upstream.

**consequence**: The converter boundary spec is built on the same
undocumented foundation. Any converter written to this spec would need to
produce a `/scans/target/` layout that does not match the upstream container
output.

### 3.3 If answer to 3.1 is no — explicit statement

**The `/scans/target/` + `/scans/contralateral/` layout is NOT proven
producible by the real eosdx-container v0.3 library.** PR0055/PR0056 assumed
an undocumented intermediate layout that does not correspond to any writer,
schema, reader, validator, or test in the upstream `container-feat-v0_3-eoscan-session-container`
package. This layout must be either:

1. A Bremen-internal intermediate format (needs explicit definition and a
   converter from session/set layout), OR
2. Corrected to match the real `/session/sets/set_NNN_label/` layout.

### 3.4 If answer to 3.1 is yes — evidence

N/A — answer is no.

### 3.5 Does "Bremen feature bridge" refer to preprocessing_bridge.py, pipelines.py, or a new component?

- **Current documentation implies**: `src/bremen/api/preprocessing_bridge.py`
  (PR0055 Section 11 says "existing runtime prediction call" through the
  existing runtime path, which uses `preprocessing_bridge.py`).

- **Current runtime code uses**: `src/bremen/api/preprocessing_bridge.py` —
  duplicated numpy math, 15-feature v0.1 schema, reads from H5 profiles.

- **Current training/product code uses**: `src/bremen/pipelines.py` —
  `BremenPreprocessingPipeline` composed of `xrd_preprocessing` transformers
  (H5ToDataFrameTransformer, AzimuthalIntegration, etc.), reads from real
  eosdx-container v0.3 via XRD-preprocessing.

- **Conflict**: YES — the runtime API path (`preprocessing_bridge.py`)
  duplicates feature computation independently of the training/product path
  (`pipelines.py` + `xrd_preprocessing` transformers). The `pipelines.py`
  path is the real product pipeline that processes real upstream container
  layouts. The `preprocessing_bridge.py` path exists only for the runtime
  API and uses duplicated, standalone numpy math.

- **evidence**: 
  - `pipelines.py` imports `from xrd_preprocessing import ...` and uses
    real transformers (H5ToDataFrameTransformer, AzimuthalIntegration).
  - `preprocessing_bridge.py` has standalone implementations of sigma_rms,
    mahalanobis_difference, wasserstein, etc. — functions that also exist
    in the XRD-preprocessing training path.
  - The pipelines.py path reads from `/session/sets/` layout via
    H5ToDataFrameTransformer. The preprocessing_bridge.py path reads from
    `/scans/target/measurements` — an incompatible layout.

### 3.6 Does src/bremen/api/preprocessing_bridge.py duplicate feature computation?

**answer**: YES

**evidence**: `preprocessing_bridge.py` contains pure numpy implementations
of `_sigma_rms`, `_sigma_rms_r`, `_mahalanobis_difference`,
`_weighted_rms_difference`, `_profile_wasserstein`, `_wasserstein_mulr`,
`_cosine_distance`, `_rms_difference`, `_mean_rms1`, `_peak14_intensity`,
`_mean_peak_value_raw`. These are direct duplicates of similar computations
that exist in the XRD-preprocessing training pipeline. The runtime bridge
does NOT use `xrd_preprocessing` transformers.

**consequence**: The runtime feature bridge has a **maintenance risk** —
any change to the feature computation in the training pipeline must be
manually duplicated in the runtime bridge. There is no shared feature
computation library.

### 3.7 Does src/bremen/pipelines.py use real xrd_preprocessing transformers and real container schema?

**answer**: YES

**evidence**: 
- `pipelines.py` imports `AzimuthalIntegration`, `FaultyPixelDetector`,
  `H5ToDataFrameTransformer`, `SNRTransformer`, etc. from `xrd_preprocessing`.
- `H5ToDataFrameTransformer` reads from the real eosdx-container v0.3
  `/session/sets/` layout.
- `BremenPreprocessingPipeline` composese real transformers from the real
  preprocessing library.

**consequence**: This is the **real product preprocessing pipeline**. It
works with the real upstream container layout. It is the correct source of
truth for the product path. The runtime API bridge (`preprocessing_bridge.py`)
is a separate, incompatible path.

### 3.8 All current incompatible/duplicate paths

| Path | File(s) | Layout assumed | Uses xrd_preprocessing? | Status |
|------|---------|---------------|------------------------|--------|
| Docs contract path | `docs/product_input_pipeline_contract.md` | `/scans/target/` + `/scans/contralateral/` | No | **Undocumented intermediate format** — does not match upstream |
| Converter boundary spec | `docs/converter_preprocessing_boundary.md` | Same as contract | No | Inherits same undocumented assumption |
| Runtime H5/layout path | `src/bremen/api/h5_layouts.py` | `/scans/target/measurements` (canonical) or `/calib_*` (calibration) | No | Legacy layout, incompatible with v0.3 session/set structure |
| Runtime feature bridge | `src/bremen/api/preprocessing_bridge.py` | Same as layout (reads from /scans/target/) | No | **Duplicated numpy math** — incompatible with real product pipeline |
| Training/product pipeline | `src/bremen/pipelines.py` | `/session/sets/` (real v0.3) | **Yes** | Real product pipeline, real upstream schema |
| Upstream container | `eosdx-container` v0.3 | `/session/sets/set_NNN_label/...` | N/A (upstream library) | Real upstream format |

### 3.9 Human decision required

> **Should Bremen redefine the runtime-facing H5/input contract to match
> the real eosdx-container v0.3 schema (`/session/sets/` layout), or should
> the external converter target the PR0055/PR0056 `/scans/target` layout as
> a separate intentional export format?**

If the second option is chosen, someone must explicitly confirm that
`/scans/target` is an intentional Bremen export format and not
eosdx-container v0.3 itself.

This decision must be made before any converter implementation, before any
product smoke, and before any investor walkthrough.

---

## 4. Productizable Pipeline Contract

Based on the evidence above, the corrected productizable path is:

```
RAW GFRM / external scan package
  -> eosdx-container v0.3 (session/set structure, raw_file vendor bytes)
    -> XRD-preprocessing YAML pipeline (H5ToDataFrame → FaultyPixelDetector → AzimuthalIntegration → ...)
      -> preprocessing artifact / DataFrame with radial profiles
        -> reconciled Bremen feature bridge / runtime input contract
          -> decision_support_report
```

The corrected path explicitly rejects:

1. **Demo-only fork** — the path must be the same for demo and production.
   Only the data source differs (synthetic/sanitised vs. real).

2. **Copying converter code into Bremen without a decision** — the converter
   architecture depends on which layout option (A/B/C/D in Section 6) is
   chosen.

3. **Runtime training** — runtime remains prediction-only.

4. **FastAPI** — remains deferred.

5. **Matador integration** — remains future source-of-record.

6. **Clinical validation claims** — no diagnosis, no replacement.

7. **Continuing with ambiguous canonical layout terminology** — the term
   "canonical layout" is ambiguous. It currently means `/scans/target/`
   in the runtime context, but the real upstream layout is `/session/sets/`.
   This must be explicitly disambiguated.

---

## 5. Integration Decision Options

### Option A: Redefine runtime-facing canonical H5/input contract to match eosdx-container v0.3

| Dimension | Assessment |
|-----------|-----------|
| Description | Change the runtime `H5LayoutAdapter` to detect and read `/session/sets/` layout. Add a new adapter (e.g., `SessionContainerV03LayoutAdapter`). Update `preprocessing_bridge.py` to read from the v0.3 integration paths (`integration/q`, `integration/i`) instead of `/scans/target/measurements`. |
| Supports investor demo without demo-only fork | **Yes** — the demo uses the same format as production. |
| Supports productization | **Yes** — matches the real upstream format. Eliminates intermediate format. |
| Requires runtime schema change | **No** — `POST /predictions` and `GET /predictions/{job_id}` unchanged. Only internal H5 reading changes. |
| Requires source/runtime change | **Yes** — `h5_layouts.py` needs a new adapter. `preprocessing_bridge.py` needs to read from integration paths. |
| Risks duplicating preprocessing math | **No** — if the bridge reads pre-integrated 1D profiles from `integration/q` + `integration/i`, it can use the same countour-based math, but the profiles arrive already integrated (azimuthal integration was done by XRD-preprocessing). The duplication risk shifts: the bridge contour math may still need alignment with training contour math. |
| Depends on heavy upstream dependencies in runtime | **No** — eosdx-container only needs h5py + numpy. XRD-preprocessing (with pyFAI) stays OUTSIDE runtime. |

### Option B: Keep PR0055/PR0056 `/scans/target` layout as deliberate Bremen export/intermediate format

| Dimension | Assessment |
|-----------|-----------|
| Description | Keep `/scans/target/` as an intentional Bremen export format. Require the converter (XRD-preprocessing post-processing step or a separate converter service) to transform the v0.3 session/set layout into this format. The runtime never reads v0.3 directly. |
| Supports investor demo without demo-only fork | **Yes** — if the converter pipeline exists and runs during demo. |
| Supports productization | **Partially** — adds an intermediate conversion step. Increases latency. One more component to maintain. |
| Requires runtime schema change | **No** — runtime is unchanged. |
| Requires source/runtime change | **No** — runtime is unchanged. Converter lives outside runtime. |
| Risks duplicating preprocessing math | **Yes** — the converter would need to extract profiles from the v0.3 integration and reformat them into `/scans/target/measurements`. This adds a translation layer. |
| Depends on heavy upstream dependencies in runtime | **No** — converter is a separate service/container. |

### Option C: Keep runtime model-only and consume precomputed feature table/artifact

| Dimension | Assessment |
|-----------|-----------|
| Description | The runtime becomes model-only inference (plus decision-support report). The full preprocessing pipeline (H5 reading → azimuthal integration → contour computation → feature extraction) runs offline or in a separate preprocessing service. The runtime receives a precomputed feature vector with feature schema metadata. |
| Supports investor demo without demo-only fork | **Partially** — demo requires the preprocessing service to be running. Without it, demo cannot produce a feature vector. |
| Supports productization | **Yes** — clean separation. Preprocessing and inference can scale independently. |
| Requires runtime schema change | **Yes** — `POST /predictions` would need to accept a precomputed feature vector (new request schema) or a path to a precomputed feature artifact. |
| Requires source/runtime change | **Yes** — runtime receives features instead of H5. Preprocessing bridge is removed or replaced with a feature loader. |
| Risks duplicating preprocessing math | **Low** — feature computation lives in one place (preprocessing service). Runtime just loads the feature vector and runs inference. |
| Depends on heavy upstream dependencies in runtime | **No** — runtime needs only numpy + joblib. No pyFAI/fabio. |

### Option D: Introduce a dedicated preprocessing service/container

| Dimension | Assessment |
|-----------|-----------|
| Description | A standalone preprocessing service (running XRD-preprocessing + eosdx-container) accepts external scan packages, runs the full product preprocessing pipeline, and writes the canonical Bremen input package (or precomputed features) to a staging location that the runtime can consume via `h5_path` or `h5_uri`. |
| Supports investor demo without demo-only fork | **Yes** — the preprocessing service runs during demo. |
| Supports productization | **Yes** — preprocessing and runtime can be deployed and scaled independently. |
| Requires runtime schema change | **No** — runtime accepts the canonical input package via existing `h5_path`/`h5_uri`. |
| Requires source/runtime change | **Minimal** — runtime stays the same. A new preprocessing service is created (outside this PR). |
| Risks duplicating preprocessing math | **Low** — preprocessing math lives in the preprocessing service using XRD-preprocessing transformers. Runtime bridge can be updated to accept either format (v0.3 integration profiles or precomputed features). |
| Depends on heavy upstream dependencies in runtime | **No** — heavy deps (pyFAI/fabio) stay in the preprocessing service. Runtime needs only h5py + numpy. |

---

## 6. Recommended Next Step

**Human decision gate before PR0058.**

Do not proceed to PR0058 (product smoke) or any converter implementation
until the human product/engineering team selects Option A, B, C, or D from
Section 5.

**Rationale**: All four options have different implementation impacts,
different runtime schema implications, and different converter architecture
requirements. Starting implementation without a decision could produce work
that must be thrown away when the layout conflict is resolved.

**Recommended order**:

1. **PR0057 (this PR)** — docs-only reconciliation document (this plan).
   Mark `/scans/target/` layout as **unverified intermediate format**.
   Document all conflicts.

2. **Human decision gate** — product/engineering team selects Option A/B/C/D.

3. **PR0058** — scope depends on decision:
   - If Option A (redefine runtime H5 contract): PR0058 implements the new
     `SessionContainerV03LayoutAdapter` + updated `preprocessing_bridge.py`.
   - If Option B (keep intermediate format): PR0058 specifies the converter
     from v0.3 → `/scans/target/` format.
   - If Option C (model-only runtime): PR0058 updates the API contract and
     replaces `preprocessing_bridge.py` with feature loader.
   - If Option D (dedicated preprocessing service): PR0058 specifies the
     preprocessing service API contract.

4. **Do not implement converter code in PR0057.** This PR is docs/evidence only.

---

## 7. Docs Plan

Create a new document at:

```
docs/preprocessing_source_reconciliation.md
```

### 7.1 Document structure

| Section | Content |
|---------|---------|
| **1. Purpose** | Reconcile Bremen's documented canonical input contract with the real upstream preprocessing/container pipeline. Identify mismatches and force a human integration decision. |
| **2. Scope** | Source archives inspected, XRD-preprocessing inventory, eosdx-container v0.3 inventory, PR0055/PR0056 canonical layout check, runtime vs training feature path check, duplicate feature computation check, integration decision options, recommended next step. |
| **3. Source Archives Inspected** | `XRD-preprocessing-main.zip` and `container-feat-v0_3-eoscan-session-container.zip` extracted under `/tmp/bremen-upstream-inspection/`. No upstream source vendored into Bremen. |
| **4. XRD-preprocessing Inventory** | Package name, version, deps, YAML templates, config loader, pipeline builder, transformer registry, GFRM converter, H5/session readers, artifact writer, examples. |
| **5. eosdx-container v0.3 Inventory** | Package name, versions, v0.3 session container schema, HDF5 layout (`/session/sets/set_NNN_label/`), set structure, raw_file, raw/processed/integration/processing/qc/artifacts groups, writer/reader/validator, examples. |
| **6. PR0055/PR0056 Canonical Layout Check** | Explicit comparison: PR0055 Section 7.2–7.3 layout vs eosdx-container v0.3 actual layout. **Verdict: NO MATCH.** `/scans/target/measurements` does not exist in any eosdx-container v0.3 writer, schema, or test. |
| **7. Runtime vs Training Feature Path Check** | `preprocessing_bridge.py` (runtime) vs `pipelines.py` + `xrd_preprocessing` (training/product). **Verdict: INCOMPATIBLE.** Different layout assumptions, duplicated feature math, no shared library. |
| **8. Duplicate Feature Computation Check** | `preprocessing_bridge.py` duplicates sigma_rms, mahalanobis, wasserstein, cosine_distance, etc. **Verdict: DUPLICATED.** |
| **9. Integration Decision Options** | Options A/B/C/D as described in Section 5 above. |
| **10. Recommended Next Step** | Human decision gate before PR0058. Options outlined. |
| **11. Safety and Non-Leakage Boundaries** | No vendoring upstream code, no heavy dependencies in runtime, no demo-only fork, no clinical validation claims. |
| **12. Open Questions** | Who decides Option A/B/C/D? Timeline for decision? Is the canonical layout terminology corrected in existing docs? |
| **13. Non-Goals** | No implementation, no converter code, no runtime changes, no silent correction. |

### 7.2 Cross-references

Add a cross-reference sentence to:

1. `docs/product_input_pipeline_contract.md` — at the end of Section 7
   (Canonical Bremen Input Package), add:
   > **Note**: The layout defined in Sections 7.2–7.3 has been verified
   > against the real upstream eosdx-container v0.3 schema in
   > [docs/preprocessing_source_reconciliation.md](preprocessing_source_reconciliation.md).
   > See that document for the reconciliation result and integration
   > decision options.

2. `docs/converter_preprocessing_boundary.md` — at the end of Section 9
   (Layout and Preflight Requirements), add:
   > **Note**: The layout assumptions in this section have been checked
   > against the upstream eosdx-container v0.3 schema in
   > [docs/preprocessing_source_reconciliation.md](preprocessing_source_reconciliation.md).
   > See that document for layout compatibility details.

---

## 8. Static Test Plan

Create a new static test file at:

```
tests/test_bremen_preprocessing_source_reconciliation.py
```

### 8.1 Test classes

| Test class | Tests |
|------------|-------|
| `TestDocumentExists` | `docs/preprocessing_source_reconciliation.md` exists |
| `TestXRDPreprocessingIdentified` | XRD-preprocessing package is identified (name, version, deps) |
| `TestEosdxContainerIdentified` | eosdx-container v0.3 package is identified (layout, structure) |
| `TestYAMLConfigTemplatesIdentified` | YAML config templates identified |
| `TestGFRMConverterIdentified` | GFRM converter functions identified |
| `TestV03SessionSetStructureIdentified` | v0.3 `/session/sets/set_NNN_label/` structure identified |
| `TestCanonicalLayoutCheck` | PR0055/PR0056 canonical layout is checked against real container schema |
| `TestScansTargetNotRealV03` | `/scans/target` layout is NOT silently treated as real eosdx-container v0.3 unless evidence exists (evidence: NO) |
| `TestBremenFeatureBridgeAmbiguity` | Bremen feature bridge ambiguity is documented (preprocessing_bridge.py vs pipelines.py vs new) |
| `TestPreprocessingBridgeDuplication` | `preprocessing_bridge.py` duplication risk is documented |
| `TestPipelinesProductPath` | `src/bremen/pipelines.py` training/product path is documented as using real xrd_preprocessing transformers |
| `TestIntegrationOptions` | Integration options A/B/C/D are documented |
| `TestHumanDecisionGate` | If layout conflict remains unresolved, human decision gate is documented |
| `TestNoDemoOnlyFork` | No demo-only fork allowed |
| `TestNoVendoring` | No vendoring upstream code allowed |
| `TestNoRuntimeTraining` | No runtime training |
| `TestNoFastAPI` | FastAPI remains deferred |
| `TestNoMatador` | Matador remains future work |
| `TestNoDiagnosis` | No diagnosis claim |
| `TestNoClinicalValidation` | No clinical validation claim |
| `TestNoReplacement` | No replacement claims |
| `TestNoArtifactsOrSecrets` | No real `.h5`, `.joblib`, `.gfrm`, `.npy`, `.proto` artifacts; no AKIA, SECRET_ACCESS_KEY, dkr.ecr, non-placeholder s3://, raw checksums, Nova_, /Users/, /home/, 12-digit account IDs |
| `TestTestsAreStatic` | Tests are static/text-only, no network/AWS/Docker/Terraform/App Runner |

---

## 9. File Change Plan

### 9.1 Files to be created

| File | Type | Description |
|------|------|-------------|
| `docs/preprocessing_source_reconciliation.md` | New | Reconciliation document (Section 7) |
| `tests/test_bremen_preprocessing_source_reconciliation.py` | New | Static tests (Section 8) |

### 9.2 Files optionally modified

| File | Change | Justification | Recommended? |
|------|--------|---------------|-------------|
| `docs/product_input_pipeline_contract.md` | Add cross-reference note at end of Section 7 | Warns readers that the layout has been reconciled and may not match upstream | **Yes** — minimal, one-paragraph note |
| `docs/converter_preprocessing_boundary.md` | Add cross-reference note at end of Section 9 | Warns readers that layout assumptions have been checked | **Yes** — minimal, one-paragraph note |

### 9.3 Files NOT changed

- `src/` — No source changes.
- `docs/adr/0011-config-governance-gates.md` — No ADR changes.
- `docs/adr/0012-system-of-record-boundary.md` — No ADR changes.
- `docs/api_contract.md` — No changes.
- `docs/production_e2e_smoke.md` — No changes.
- `docs/release_readiness_operator_notes.md` — No changes.
- `ROADMAP.md` — No changes (decision not yet made).
- `config/`, `Dockerfile*`, `infra/`, `.github/`, `requirements.txt`,
  `pyproject.toml`, `agents/` — No changes.

---

## 10. Validation Plan

### 10.1 Compilation

```bash
python -m compileall src tests
```

### 10.2 Test suite

```bash
# New reconciliation tests
python -m pytest -q tests/test_bremen_preprocessing_source_reconciliation.py -v

# PR0055 contract (cross-reference edit may affect these)
python -m pytest -q tests/test_bremen_product_input_pipeline_contract.py -v

# PR0056 boundary spec (cross-reference edit may affect these)
python -m pytest -q tests/test_bremen_converter_preprocessing_boundary.py -v

# API contract tests
python -m pytest -q tests/test_bremen_api_contract.py -v

# Full suite
python -m pytest -q
```

### 10.3 Safety validation

```bash
git diff --name-only
git diff --name-only -- src Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml src/bremen/training agents config docs/adr ROADMAP.md
git diff --name-only | grep -E '\.(h5|hdf5|gfrm|joblib|pkl|npy|npz|parquet|proto|pb|tfstate|tfstate\.backup)$' || true
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n docs tests ROADMAP.md || true
grep -R "MATADOR_\|Matador.*token\|Matador.*URL\|requests\|httpx\|aiohttp" -n docs tests ROADMAP.md || true
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|s3://\|sha256:\|Nova_\|/Users/\|/home/" -n docs tests ROADMAP.md || true
grep -R "diagnos\|clinical validation\|clinically validated\|replace radiologist\|replace clinician\|replace MRI\|replace biopsy" -n docs tests ROADMAP.md || true
```

---

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Human decision is delayed indefinitely | Medium | High | The plan explicitly flags urgency. Next PR (PR0058) is blocked until the decision is made. |
| Decision is made without reading this plan | Low | High | Cross-reference notes in PR0055/PR0056 docs point to the reconciliation document. |
| Option A is chosen but runtime H5 adapter conflicts with legacy calibration layout | Medium | Medium | Calibration layout (`/calib_*`) is separate from session layout. Option A adds a new adapter, does not remove the old ones. |
| Upstream eosdx-container schema changes after Option A implementation | Low | High | Version the adapter against schema_version=0.3. Future schema versions (0.4+) add new adapters. |
| Investor walkthrough (PR0059+) tries to use v0.3 container directly before converter exists | Medium | Medium | The walkthrough doc must specify which integration option is in use and how the input is staged. |

---

## 12. Non-Goals

1. No converter implementation.
2. No Preprosync implementation.
3. No protobuf parser.
4. No GeoFrame parser.
5. No GFRM conversion execution in Bremen runtime.
6. No pyFAI/fabio dependency addition to runtime.
7. No upstream code vendoring into Bremen.
8. No runtime request schema change.
9. No h5_path/h5_uri behavior change.
10. No Matador integration.
11. No FastAPI.
12. No runtime training.
13. No model training implementation.
14. No new model.
15. No inference/preprocessing math changes.
16. No demo-only fork.
17. No real data artifacts committed.
18. No clinical validation claims.
19. No diagnosis claims.
20. No replacement of clinical judgment.
21. No product smoke implementation (PR0058 scope).
22. No investor walkthrough implementation (PR0059+ scope).
23. No silent canonical layout correction without human decision.

---

Implementation role: coder
