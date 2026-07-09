# Plan: PR0055 — Product Input Pipeline Inventory And Canonical Input Contract

**PR**: 0055-product-input-pipeline-inventory  
**Role**: plan  
**Mode**: planning  
**Branch**: 0055-product-input-pipeline-inventory  
**HEAD**: eda0224d7ba78eebcea9df5d621ca0c823337e83  
**PR sequence**: PR0055 (first PR of Product Input Pipeline Readiness block)  

---

## 1. ROADMAP Alignment

1. **PR0055 follows the post-PR0054 Product Input Pipeline Readiness block.**  
   The roadmap correction is complete. ROADMAP.md now shows "Current state
   through PR0054" and a "Next Execution Block (post-PR0054)" placeholder.
   This PR confirms the human product/engineering decision described in the
   CONTEXT: the next selected block is Product Input Pipeline Readiness.

2. **PR0055 is inventory/contract first.**  
   No converter implementation. No Preprosync integration. No protobuf
   parser. No GeoFrame parser. PR0055 defines what the input pipeline is,
   what forms it accepts, what canonical shape it produces, and what
   converter boundary exists — in a contract document.

3. **PR0056 remains converter/preprocessing boundary specification.**  
   PR0056 is referenced in the plan as the next PR after PR0055. It will
   specify the converter interface/protocol. It is NOT started in PR0055.

4. **PR0057 remains product-like controlled input smoke.**  
   PR0057 is referenced as the PR that adds a smoke test using the
   productizable input path. It is NOT started in PR0055.

5. **PR0058 remains investor/operator walkthrough.**  
   PR0058 is referenced as the PR that delivers the walkthrough doc. It
   is NOT started in PR0055.

6. **PR0055 does not start PR0056–PR0058.**  
   Strict scope boundary: inventory + contract only.

---

## 2. Productizable Workflow

The target productizable workflow is:

```
external prepared scan package / GeoFrame / protobuf-derived data
  -> controlled converter / Preprosync / preprocessing boundary
    -> canonical Bremen input package
      -> existing Bremen runtime
        -> decision_support_report
```

### Key assertions

1. **This is not demo-only.** The canonical input package contract defined
   in PR0055 is intended for both demo/presentability and future production
   use. There is no separate demo format.

2. **Demo walkthrough must use the same contract.** Any investor walkthrough
   (PR0058) will exercise the same canonical input package that a production
   deployment would accept. The only difference is the data source
   (synthetic/sanitised vs. real patient data).

3. **Bremen runtime remains stable.** The existing runtime
   (`POST /predictions`, `GET /predictions/{job_id}`, preflight,
   preprocessing bridge, inference handler, decision-support report) is
   unchanged by PR0055. The canonical input package is an *external input
   contract* that describes what goes *into* the staging/preflight
   boundary, not a new runtime path.

4. **Runtime does not become the converter service in PR0055.** The
   converter (GeoFrame → canonical H5, protobuf → canonical H5,
   Preprosync output → canonical H5) is a separate component that lives
   outside the Bremen runtime. PR0055 defines the contract that the
   converter must produce; it does not implement the converter.

5. **Runtime does not train.** No training code is added, modified, or
   invoked by PR0055.

6. **Matador remains future source-of-record integration.** The canonical
   input package is a staging/development input contract. Long-term
   source-of-record ownership remains with Matador (ADR-0012). PR0055
   does not change this.

7. **FastAPI remains deferred.** No FastAPI, uvicorn, starlette, or ASGI
   framework is introduced.

---

## 3. Inventory Plan

The plan must inventory existing local repo evidence for each of the
following categories. Where evidence exists, cite it. Where evidence
is missing, mark as "candidate input form; requires verification".

### 3.1 GeoFrame references

**Inventory result**: No GeoFrame references exist in the repo. The target
workflow mentions GeoFrame as a candidate external input form, but no
GeoFrame parser, reader, dependency, or test references any GeoFrame format.

**Plan in contract**: "GeoFrame-derived data is a candidate external input
form. GeoFrame parsing and schema mapping are not yet implemented and
require external specification from the Bremen/GeoFrame integration team."

### 3.2 Protobuf / proto references

**Inventory result**: No protobuf `.proto` files, `protobuf` dependency,
or protobuf parsing code exists in the repo. The `config/` directory
contains `measurement_protocol` references in JSON config — these are
metadata fields in `aramis_product_versioning.json`, not related to
protobuf serialization format.

**Plan in contract**: "Protobuf-derived data is a candidate external input
form. Protobuf schema definitions and parsing are not yet implemented and
require external specification."

### 3.3 Converter references

**Inventory result**: No converter module, converter class, converter
interface, or converter test exists in the repo. The word "converter"
does not appear in any source, test, or doc file.

**Plan in contract**: "A controlled converter is the boundary between
external scan packages (GeoFrame, protobuf-derived data, Preprosync
output) and the canonical Bremen input package. The converter is not yet
implemented. PR0055 defines the output contract the converter must
satisfy. The converter implementation is tracked as future work
(PR0056+)."

### 3.4 Preprosync / preprocessing container references

**Inventory result**: No Preprosync references exist in the repo. No
preprocessing container Docker image, Dockerfile section, or CI
configuration references a preprocessing container separate from the
runtime and training containers.

**Plan in contract**: "Preprosync / preprocessing container output is a
candidate external input form. Preprosync integration is not yet
implemented and requires external specification."

### 3.5 Canonical H5 / Bremen input contract references

**Inventory result**: No document or module in the repo defines a
"canonical Bremen input package" or "canonical H5" contract. The
existing `docs/api_contract.md` defines the *runtime API* contract
(`h5_path`, `h5_uri`, `POST /predictions` request schema). The existing
`docs/` documents describe the H5 layout adapter protocol (`h5_layouts.py`,
`CanonicalH5LayoutAdapter`, `CalibrationSampleH5LayoutAdapter`) — these
describe how the runtime *reads* H5 containers that arrive, not what
contract the input must satisfy.

**Plan in contract**: PR0055 creates this contract definition for the
first time. The canonical Bremen input package is what the converter
output must satisfy for the runtime to accept it.

### 3.6 Existing H5 layout and preprocessing bridge assumptions

**Inventory result**: The existing runtime assumes:

1. An H5 container (`.h5` / HDF5 format) that can be opened with `h5py`.
2. Either canonical layout (`/scans/target/measurements` +
   `/scans/contralateral/measurements`) or calibration sample layout
   (top-level `calib_*` groups with `sample/patient_name` and
   `sample/sample_type`).
3. Explicit `target_scan_ref` and `control_scan_ref` for multi-sample
   layouts.
4. Profiles readable as 1D or 2D numpy arrays from measurements or
   integration i/q paths.
5. `h5_path` (local filesystem) or `h5_uri` (S3 → staged locally) as
   input transport modes.
6. Metadata: patient identifier, side values, measurement counts.
7. 15-feature v0.1 schema after preprocessing bridge.

**Plan in contract**: These assumptions are codified in the canonical
input contract. The contract describes what the converter must produce.

### 3.7 Existing runtime h5_path/h5_uri input staging

**Inventory result**: `src/bremen/h5_inputs.py` (`stage_h5_input`)
provides S3 → local staging with checksum verification. The runtime
accepts either a local `h5_path` (direct) or an `h5_uri` (staged from
S3). These are controlled runtime input modes, not long-term
source-of-record modes.

**Plan in contract**: The canonical input package is staged via the
existing `h5_path` or `h5_uri` mechanisms. The converter output is
placed where the runtime can access it — either as a local file
(dev/test) or as an S3 object (staging/integration). The existing
staging code does not change.

### 3.8 Existing system-of-record boundary constraints

**Inventory result**: `src/bremen/system_of_record.py` defines
`ExternalRecordRef`, `ResolvedInput`, `RecordResolver` protocol, and
`UnconfiguredRecordResolver`. The runtime does NOT currently use
`RecordResolver` for request processing. `h5_path`/`h5_uri` remain
the only input modes.

**Plan in contract**: The canonical input package is compatible with
the existing `h5_path`/`h5_uri` input modes. The system-of-record
boundary is a *future* integration layer that will resolve a
Matador ref to a `ResolvedInput` (which contains an `h5_uri` or
`h5_path` pointing to the canonical input). PR0055 does not wire
the system-of-record boundary into the request path.

---

## 4. Canonical Input Contract Plan

Create a new contract document at:

```
docs/product_input_pipeline_contract.md
```

### 4.1 Document structure

| Section | Content |
|---------|---------|
| **Purpose** | Define the productizable input pipeline contract for Bremen. External scan packages (GeoFrame, protobuf-derived data, Preprosync output) are converted to a canonical Bremen input package that the existing runtime can accept. |
| **Scope** | Input pipeline from external scan package to canonical Bremen input package. Does NOT cover converter implementation, Matador source-of-record, FastAPI, runtime schema changes, or clinical validation. |
| **Candidate External Input Forms** | GeoFrame-derived data, protobuf-derived data, Preprosync / preprocessing container output. Each form is unverified; requires converter specification. |
| **Converter / Preprocessing Boundary** | A controlled converter translates each external form to the canonical Bremen input package. The runtime is NOT the converter. The converter lives outside the runtime. |
| **Canonical Bremen Input Package** | See section 4.2 below. |
| **Required Metadata** | Patient identifier (string), target/control side values (LEFT/RIGHT), layout category (canonical or calibration_sample), optional checksum. |
| **Explicit Target/Control Refs** | `target_scan_ref` and `control_scan_ref` are required. Values are adapter-dependent: `"target"`/`"contralateral"` for canonical layout, group path for calibration layout. |
| **Accepted Controlled Runtime Input Modes** | `h5_path` (dev/test convenience), `h5_uri` (S3 staging mode). Both are staging/controlled modes, not long-term source-of-record. |
| **Decision-Support Output Path** | `POST /predictions` → `GET /predictions/{job_id}` → `result.decision_support_report`. No change to the existing output path. |
| **Demo-Safe and Production-Compatible Constraints** | The canonical input package format is identical for demo and production. Only the data source differs (sanitised synthetic vs. real). No separate demo-only format. |
| **Non-Leakage Rules** | No raw patient identifiers, full S3 URIs, raw checksums, raw feature values, or raw scan arrays in committed examples, test fixtures, or docs. |
| **Non-Goals** | No converter implementation, no Preprosync integration, no GeoFrame parser, no protobuf parser, no Matador integration, no FastAPI, no runtime schema change, no runtime training, no new model, no clinical validation, no diagnosis. |
| **Open Questions Before Implementation** | Which external input form is the first converter target? Who provides the GeoFrame/protobuf schema specification? Is the converter a standalone service or a preprocessing container? How are credentials/secrets for the external input source managed? |

### 4.2 Canonical Bremen input package specification

The canonical Bremen input package is an HDF5 container (`.h5` file)
that satisfies the following requirements:

| Requirement | Specification |
|-------------|---------------|
| Format | HDF5 (`.h5`) readable by `h5py >= 3.0` |
| Layout | Either canonical or calibration_sample (detectable by `H5LayoutAdapter`) |
| Canonical layout paths | `/patient/id` (scalar), `/scans/target/measurements` (array), `/scans/target/side` (scalar), `/scans/contralateral/measurements` (array), `/scans/contralateral/side` (scalar) |
| Calibration layout paths | `/{calib_group}/{sample_group}/sample/patient_name`, `/{calib_group}/{sample_group}/sample/sample_type`, `/{calib_group}/{sample_group}/sets/{set_n}/integration/i`, `/{calib_group}/{sample_group}/sets/{set_n}/integration/q` |
| Profile arrays | 1D or 2D numpy arrays of float values. Each profile represents one measurement (integrated or raw). At least 1 profile per side. |
| Metadata | Patient identifier (string), side values ("LEFT"/"RIGHT" or "L"/"R" or breast type strings). |
| explicit_refs | `target_scan_ref` and `control_scan_ref` strings are passed alongside the H5 path at submit time. They are not embedded in the H5 file itself. |
| Checksum | Optional SHA-256 checksum for integrity verification at staging time. |
| Prohibited content | Raw patient names (only patient IDs allowed in `/patient/id`). Raw scan arrays in metadata paths. Full S3 URIs, credentials, or secrets inside H5 metadata. |
| Converter role | The converter must produce an H5 file that satisfies these layout and metadata requirements. The converter is NOT part of the runtime. |

### 4.3 Runtime stability guarantee

The contract document must explicitly state:

> The Bremen runtime's `POST /predictions` endpoint, `GET /predictions/{job_id}`
> endpoint, preflight gate, preprocessing bridge, inference handler, and
> decision-support report are stable and unchanged by this contract. The
> canonical input package is designed to work with the existing runtime as-is.
> The runtime does not become the converter service. The runtime does not
> train models. The runtime does not implement Matador integration.

---

## 5. Investor Workflow Plan

The contract document must include a section describing the investor-
presentable flow. This is not a separate document or demo-only format.

### 5.1 Workflow steps

1. **Sanitised/synthetic external input placeholder.** A synthetic or
   sanitised scan package (representing GeoFrame/protobuf-derived data
   output) is prepared outside the runtime. This placeholder demonstrates
   the input form without requiring real patient data.

2. **Converter/preprocessing boundary placeholder.** A placeholder
   converter (or documented conversion step) transforms the external
   input into the canonical Bremen input package. In demo mode, this
   can be a script, a notebook cell, or a documented manual step —
   the same contract applies.

3. **Canonical Bremen input package.** The conversion produces a valid
   `.h5` file satisfying the canonical input package specification.

4. **Existing runtime prediction call.** The canonical input package is
   submitted to `POST /predictions` via `h5_path` or `h5_uri`.

5. **Completed job response.** Poll `GET /predictions/{job_id}` until
   `status = "completed"`.

6. **Decision-support report.** The `result.decision_support_report`
   contains the triage recommendation with safety disclaimers.

7. **Clear safety language.** The walkthrough explicitly states that
   this is a product pipeline demonstration, not a clinical validation,
   not a diagnosis, and does not replace MRI/biopsy/radiologist/
   clinician/clinical judgment.

### 5.2 Demo-safe guarantee

> The workflow described above uses the same canonical input package
> contract that a production system would use. There is no separate
> demo-only format. A production deployment receives the same file
> format, the same metadata, and produces the same decision-support
> output. The only difference is the source of the data: a synthetic
> or sanitised placeholder for demo, and real patient data (via
> Matador source-of-record) in production.

---

## 6. Static Test Plan

Plan a new static test file at:

```
tests/test_bremen_product_input_pipeline_contract.py
```

### 6.1 Test requirements

All tests are static/text-only — no network, no AWS, no Docker, no
Terraform, no App Runner, no real H5, no real model artifacts.

| Test class | Tests |
|------------|-------|
| `TestContractDocumentExists` | `docs/product_input_pipeline_contract.md` exists |
| `TestProductizableWorkflow` | Productizable workflow is documented with external input → converter → canonical package → runtime → decision_support_report |
| `TestNoDemoOnlyFork` | No separate demo-only format allowed. Contract must state demo uses same format as production. |
| `TestCandidateInputForms` | GeoFrame, protobuf-derived data, Preprosync output are described as candidate input forms to inventory, not as proven implemented (unless local repo evidence proves otherwise). Since evidence is missing, tests assert they are described as candidates requiring verification. |
| `TestConverterBoundary` | Converter/preprocessing boundary is documented. Runtime is NOT the converter. |
| `TestRuntimeStability` | Runtime remains stable. Runtime does not become converter service. Runtime does not train. |
| `TestCanonicalInputPackage` | Canonical Bremen input package is documented with format, layout, metadata, explicit refs, and prohibited content. |
| `TestExplicitRefsRequired` | Contract requires explicit `target_scan_ref` and `control_scan_ref`. |
| `TestInputModes` | `h5_path` / `h5_uri` are documented as controlled runtime input modes. |
| `TestMatadorFutureWork` | Matador real integration is documented as future work, not implemented. |
| `TestFastAPIDeferred` | FastAPI is documented as deferred, not implemented. |
| `TestDecisionSupportOutputPath` | `decision_support_report` is documented as the output path. |
| `TestNoDiagnosis` | Contract states no diagnosis. |
| `TestNoClinicalValidation` | Contract states no clinical validation. |
| `TestNoReplacement` | Contract states no replacement of MRI, biopsy, radiologist, clinician, or clinical judgment. |
| `TestNoRealDataArtifacts` | No real H5, joblib, pickle, numpy, parquet, protobuf, GeoFrame, or model artifacts in committed examples. |
| `TestNoSecretsOrIdentifiers` | No full S3 URIs, checksums, secrets, account IDs, raw patient IDs, raw refs, raw feature values, or local machine absolute paths. |

### 6.2 Design notes

- Tests import only `pathlib.Path`, `pytest`, and `re` (no network,
  no AWS, no Docker).
- Assertions are `in` / `not in` substring checks on the contract
  document content.
- Use `ROOT = Path(__file__).resolve().parents[1]` pattern (same as
  existing static test files).
- No synthetic H5 file creation, no monkeypatching, no fixtures
  beyond file path resolution.

---

## 7. File Change Plan

### 7.1 Files to be created

| File | Type | Description |
|------|------|-------------|
| `docs/product_input_pipeline_contract.md` | New | Canonical input contract (section 4) |
| `tests/test_bremen_product_input_pipeline_contract.py` | New | Static tests for the contract (section 6) |

### 7.2 Files to be optionally modified (with justification)

| File | Change | Justification | Recommended? |
|------|--------|---------------|-------------|
| `docs/release_readiness_operator_notes.md` | Add cross-reference to product input pipeline contract in Section 3 (Current Release Capability) or Section 15 (Non-Goals) | The operator notes describe current release capability. If the input pipeline contract is part of the release, a cross-reference helps operators understand supported input forms. | **No** — PR0055 is contract-only. No runtime capability changes yet. Add cross-reference in PR0056 or PR0057 when converter exists. |
| `docs/api_contract.md` | Add cross-reference to product input pipeline contract in the System-of-Record Boundary (PR0052) section | The API contract describes input modes. A cross-reference to the canonical input package specification would be helpful for implementers. | **Yes** — a minimal single-sentence cross-reference at the end of the System-of-Record Boundary section: "For the product input pipeline contract defining the canonical Bremen input package, see [docs/product_input_pipeline_contract.md](product_input_pipeline_contract.md)." This is justified because the API contract already documents input modes and the system-of-record boundary — the input pipeline contract is a natural sibling document. |
| `ROADMAP.md` | Mark PR0055 in the Next Execution Block or add a separate Product Input Pipeline Readiness section | The roadmap currently has a placeholder block. Adding PR0055 detail would be premature since the human product/engineering decision was made in the task CONTEXT, not in the roadmap. | **No** — preferred no ROADMAP change. The roadmap placeholder already delegates the decision. Adding PR0055 before the placeholder is resolved creates inconsistency. |

**Preferred change set**: 2 new files + 1 minimal cross-reference edit to
`docs/api_contract.md`.

### 7.3 Files NOT changed

- `src/` — No source changes.
- `docs/adr/0011-config-governance-gates.md` — No ADR changes.
- `docs/adr/0012-system-of-record-boundary.md` — No ADR changes.
- `docs/production_e2e_smoke.md` — No changes. The existing production
  smoke test uses H5 path/URI and is unaffected by the input pipeline
  contract. PR0057 will add a product-path smoke.
- `docs/release_readiness_operator_notes.md` — No changes (see 7.2).
- `config/`, `Dockerfile*`, `infra/`, `.github/`, `requirements.txt`,
  `pyproject.toml`, `agents/` — No changes.

---

## 8. Validation Plan

### 8.1 Pre-implementation validation

```bash
# Verify branch and HEAD
git rev-parse --verify HEAD
git branch --show-current
git status --short
```

### 8.2 Post-implementation compilation

```bash
python -m compileall src tests
```

### 8.3 Post-implementation test suite

```bash
# New contract tests
python -m pytest -q tests/test_bremen_product_input_pipeline_contract.py -v

# Existing tests (must still pass)
python -m pytest -q tests/test_bremen_release_readiness_operator_notes.py -v
python -m pytest -q tests/test_bremen_api_contract.py -v
python -m pytest -q tests/test_bremen_h5_input_staging.py -v
python -m pytest -q tests/test_bremen_h5_layouts.py -v
python -m pytest -q tests/test_bremen_system_of_record_boundary.py -v

# Full test suite
python -m pytest -q
```

### 8.4 Safety validation

```bash
# Confirm no unintended file changes beyond allowed set
git diff --name-only

# Confirm no source/test/config/infra changes
git diff --name-only -- src Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml src/bremen/training agents config docs/adr

# Confirm no binary artifacts
git diff --name-only | grep -E '\.(h5|hdf5|joblib|pkl|npy|npz|parquet|proto|pb|tfstate|tfstate\.backup)$' || true

# FastAPI/starllete/uvicorn — only in deferred/non-goal context
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n docs tests ROADMAP.md || true

# Matador network libraries — must NOT appear
grep -R "MATADOR_\|Matador.*token\|Matador.*URL\|requests\|httpx\|aiohttp" -n docs tests ROADMAP.md || true

# Secrets/identifiers — must NOT appear
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|s3://\|sha256:\|Nova_\|/Users/\|/home/" -n docs tests ROADMAP.md || true

# Clinical claims — only negated safety language, no positive claims
grep -R "diagnos\|clinical validation\|clinically validated\|replace radiologist\|replace clinician\|replace MRI\|replace biopsy" -n docs tests ROADMAP.md || true
```

### 8.5 Safety validation expectations

| Check | Expected result |
|-------|----------------|
| `git diff --name-only` | Only new files + `docs/api_contract.md` edit (if that option is chosen) |
| `git diff --name-only -- src Dockerfile ...` | Empty — no source/config/infra/agent changes |
| Binary artifact grep | Empty — no artifacts |
| FastAPI | Only in deferred/non-goal context — safe |
| Matador.*token/URL/requests/httpx/aiohttp | Not present — no network client references |
| AKIA/SECRET_ACCESS_KEY/dkr.ecr | Not present |
| s3:// | Only `${VARIABLE}` placeholders or generic examples — safe |
| sha256: | Only in placeholder context — safe |
| Nova_/Users/home | Not present |
| diagnosis/clinical validation/replace | Only negation language — safe |

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Contract document defines converter boundary that contradicts future converter PR | Medium | Medium | The contract explicitly states "Open Questions Before Implementation" and does not commit to a specific converter architecture. The converter implementation PR (PR0056) will refine the boundary. |
| API contract cross-reference edit creates test failure | Low | Medium | The existing `test_bremen_api_contract.py` does not test for the absence of cross-references. Adding a single line at the end of the System-of-Record Boundary section will not break any existing assertion. |
| Static test asserts on wording that future PRs may change | Low | Low | Tests assert on broad contract concepts (e.g., "runtime is not the converter", "Matador is future work") that are architectural invariants — not implementation detail wording. |
| GeoFrame/protobuf/Preprosync are described as "candidates" but investor expects working integration | Medium | Medium | The contract document must use explicit language: "candidate input form; requires converter specification and implementation." The investor walkthrough (PR0058) will clarify that converter implementation is a future step. |

---

## 10. Implementation Order

1. Create `docs/product_input_pipeline_contract.md`
2. Create `tests/test_bremen_product_input_pipeline_contract.py`
3. (Optional) Edit `docs/api_contract.md` — add one cross-reference sentence
4. Run validation (section 8)
5. Commit with message: `feat(pr0055): product input pipeline inventory and canonical input contract`

---

## 11. Non-Goals

1. No converter implementation.
2. No Preprosync implementation.
3. No protobuf parser.
4. No GeoFrame parser.
5. No runtime input schema change (`POST /predictions` request body unchanged).
6. No Matador integration.
7. No FastAPI.
8. No runtime training.
9. No model training workflow implementation.
10. No new model.
11. No inference/preprocessing math changes.
12. No demo-only fork.
13. No real data artifacts in committed files.
14. No clinical validation or diagnosis claims.
15. No replacement of MRI, biopsy, radiologist, clinician, or clinical judgment.
16. No PR0056–PR0058 implementation.
17. No ADR changes.
18. No ROADMAP.md changes.
19. No `src/` changes.

---

Implementation role: coder
