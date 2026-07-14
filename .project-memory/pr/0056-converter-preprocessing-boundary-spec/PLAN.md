# Plan: PR0056 — Converter Preprosync Preprocessing Boundary Specification

**PR**: 0056-converter-preprocessing-boundary-spec  
**Role**: plan  
**Mode**: planning  
**Branch**: 0056-converter-preprocessing-boundary-spec  
**HEAD**: dd0dc49d4bde2a91db8e35fff2ac114d9378f731  
**PR sequence**: PR0056 (second PR of Product Input Pipeline Readiness block, follows PR0055)  

---

## 1. ROADMAP Alignment

1. **PR0056 follows PR0055.** PR0055 defined the canonical Bremen input
   package contract and inventoried candidate external input forms.
   PR0056 specifies the controlled converter / Preprosync / preprocessing
   boundary that transforms those external forms into the canonical input.

2. **PR0056 is converter/preprocessing boundary specification only.**
   No converter code is implemented. No Preprosync integration.
   No protobuf parsing. No GeoFrame parsing. This is a specification
   contract and static tests.

3. **PR0056 does not start PR0057.** PR0057 (product-like controlled
   input smoke) remains a future PR.

4. **PR0056 does not start PR0058.** PR0058 (investor/operator
   walkthrough) remains a future PR.

---

## 2. Boundary Specification Plan

Create a new specification document at:

```
docs/converter_preprocessing_boundary.md
```

### 2.1 Document structure

| Section | Content |
|---------|---------|
| **1. Purpose** | Define the controlled converter / Preprosync / preprocessing boundary that translates candidate external input forms (GeoFrame, protobuf-derived data, Preprosync output) into the canonical Bremen input package defined in PR0055. Define responsibilities, interface, and constraints — NOT an implementation. |
| **2. Scope** | Specification of the converter boundary, inputs, outputs, metadata contract, runtime interface, error categories, and non-leakage rules. NOT converter implementation, NOT Preprosync container execution, NOT protobuf parsing, NOT GeoFrame parsing. |
| **3. Inputs** | See Input Candidates section 3 below. |
| **4. Outputs** | See Output Contract section 4 below. |
| **5. Boundary Responsibilities** | What the converter IS responsible for. What the converter IS NOT responsible for. |
| **6. Out-of-Scope Responsibilities** | Explicit list: runtime prediction, H5 staging, preflight, preprocessing bridge, inference, decision-support report, model loading, Matador integration, FastAPI, training. |
| **7. Metadata Contract** | Required metadata fields per PR0055 contract. Artifact identifier, layout category, target/control refs, checksum, preprocessing provenance, contract version. |
| **8. Explicit Target/Control Refs** | Refs are required at submit time. The converter must preserve or produce valid refs matching expected layout values. Canonical: `"target"`/`"contralateral"`. Calibration: group path strings. |
| **9. Layout and Preflight Requirements** | The converter output must pass the existing `H5LayoutAdapter` detection and `run_h5_preflight()` validation. No new preflight logic. |
| **10. Canonical Bremen Input Package Compatibility** | The converter output must satisfy all requirements from PR0055 Section 7 (Canonical Bremen Input Package). Format, paths, profiles, metadata, prohibited content. |
| **11. Runtime Interface** | The converter output feeds into the existing `h5_path` / `h5_uri` runtime input modes. No runtime API changes. The converter places (or registers) the canonical H5 where the runtime can stage it via existing mechanisms. |
| **12. Error Classes / Failure Categories** | Specification-level error categories: input parsing failure, schema validation failure, missing required metadata, invalid target/control refs, incompatible layout, checksum mismatch. No implementation of error handling — just categories for the future converter implementation. |
| **13. Non-Leakage Rules** | The converter must not log, store, or embed raw patient identifiers, full S3 URIs, credentials, account IDs, registry URLs, raw checksums, raw feature values, or local machine absolute paths. Committed converter examples must use synthetic/sanitised data. |
| **14. Demo-Safe and Production-Compatible Operation** | The same converter boundary applies to demo and production. No demo-only converter code path. Demo may use synthetic data; production uses real patient data via Matador source-of-record. |
| **15. Implementation Prerequisites** | Before converter implementation can begin: (1) external input form selection, (2) external schema specification, (3) converter deployment architecture decision, (4) credential/access management plan, (5) canonical input package versioning strategy. |
| **16. Open Questions** | Which external input form is first? Who provides schema specs? Converter standalone service or preprocessing container? Credential management? Versioning strategy? Multi-patient handling? |
| **17. Non-Goals** | Explicit list: no converter implementation, no Preprosync, no protobuf parser, no GeoFrame parser, no runtime schema change, no Matador, no FastAPI, no training, no new model, no demo-only code path, no diagnosis, no clinical validation. |

---

## 3. Input Candidates

Treat all four candidate input forms as candidates. Do not claim any
already work unless local repo evidence proves it.

| Candidate | Evidence in repo | Status in boundary spec |
|---|---|---|
| External prepared scan package | No spec, parser, or reference exists | Candidate input form; requires converter specification |
| GeoFrame | No parser, reader, dependency, or test exists | Candidate input form; requires external GeoFrame schema specification |
| Protobuf-derived data | No `.proto` files, `protobuf` dependency, or parsing code exists | Candidate input form; requires external protobuf schema specification |
| Preprosync / preprocessing container output | No Preprosync reference, preprocessing container image, or CI config exists | Candidate input form; requires Preprosync integration specification |

All four are described in the spec as:

> **Candidate input forms. Not yet implemented. Each requires a converter
> specification and implementation before the product input pipeline is
> operational.**

Reference the PR0055 contract document sections 4.1–4.3 (which already
document these as candidates) and the Inventory Findings table (section 5
of the PR0055 contract).

---

## 4. Output Contract

The converter/preprocessing boundary output must satisfy the following
requirements. These reproduce and commit to the canonical input package
contract from PR0055, making it the binding output contract for the
converter.

| # | Requirement | Source |
|---|-------------|--------|
| 1 | Canonical H5 or canonical H5-equivalent artifact (`.h5` HDF5 readable by h5py >= 3.0) | PR0055 Section 7.1 |
| 2 | Compatible with existing Bremen H5 preflight/layout expectations (canonical or calibration_sample layout) | PR0055 Section 7.2–7.3 |
| 3 | Compatible with explicit `target_scan_ref` and `control_scan_ref` (passed at submit time, not embedded in H5) | PR0055 Section 9 |
| 4 | Compatible with existing runtime `h5_path` or `h5_uri` staging (local file or S3-staged) | PR0055 Section 10 |
| 5 | Accompanied by safe metadata: patient identifier, layout category, target/control side values, optional checksum | PR0055 Section 8 |
| 6 | Optionally accompanied by checksum when staged externally (SHA-256) | PR0055 Section 8.4 |
| 7 | Free of raw patient identifiers in committed examples (use synthetic `<PATIENT_ID>` placeholders) | PR0055 Section 8.7 |
| 8 | Free of full S3 URIs in committed examples (use `${VARIABLE}` placeholder notation) | PR0055 Section 7.4 |
| 9 | Free of raw feature values in committed examples (features are computed by runtime, not embedded in input) | PR0055 Section 7.4 |
| 10 | Free of local absolute paths and secrets (no `/Users/`, `/home/`, `AKIA`, `SECRET_ACCESS_KEY`, account IDs) | PR0055 Section 7.4 |

---

## 5. Runtime Preservation Plan

The following runtime behaviors are explicitly preserved and unchanged
by PR0056:

| # | Runtime behavior | Preservation guarantee |
|---|-----------------|----------------------|
| 1 | `POST /predictions` request schema | Unchanged. No new fields. |
| 2 | `h5_path` / `h5_uri` input modes | Unchanged. Both remain supported. |
| 3 | H5 input staging (`src/bremen/h5_inputs.py`) | Unchanged. Existing S3 → local staging. |
| 4 | Preflight behavior (`src/bremen/api/preflight.py`) | Unchanged. Existing layout + metadata validation. |
| 5 | Layout detection (`src/bremen/api/h5_layouts.py`) | Unchanged. Existing adapter protocol. |
| 6 | Preprocessing bridge (`src/bremen/api/preprocessing_bridge.py`) | Unchanged. 15-feature v0.1 extraction. |
| 7 | Inference execution (`src/bremen/api/inference_handler.py`) | Unchanged. Portable logistic regression. |
| 8 | Decision-support report (`src/bremen/api/decision_support.py`) | Unchanged. `report_schema_version: "v0.1"`. |
| 9 | Model loading lifecycle (`ModelState`, `model_loader.py`) | Unchanged. Startup-only loading. |
| 10 | Checksum-before-deserialization boundary | Unchanged. SHA-256 before `joblib.load()`. |
| 11 | Runtime does not train | Unchanged. No training code in runtime. |
| 12 | Runtime does not become converter service | The converter is a separate component. PR0056 does not add a converter module, CLI, or execution path to the runtime. |

---

## 6. Static Test Plan

Create a new static test file at:

```
tests/test_bremen_converter_preprocessing_boundary.py
```

### 6.1 Test classes

| Test class | Tests |
|------------|-------|
| `TestDocumentExists` | `docs/converter_preprocessing_boundary.md` exists |
| `TestBoundaryDefinition` | Boundary doc defines converter / Preprosync / preprocessing boundary with purpose and scope |
| `TestCandidateInputForms` | GeoFrame, protobuf-derived data, Preprosync output described as candidate input forms requiring verification (not implemented) |
| `TestOutputContract` | Output contract requires canonical Bremen input package, H5/preflight/layout compatibility, explicit refs, runtime input mode compatibility |
| `TestExplicitRefsRequired` | `target_scan_ref` and `control_scan_ref` are required at submit time |
| `TestRuntimeModesPreserved` | `h5_path` and `h5_uri` documented as preserved runtime input modes |
| `TestRuntimeSchemaNotChanged` | Boundary spec states runtime request schema is not changed |
| `TestRuntimeNotConverter` | Boundary spec states runtime does NOT become the converter service |
| `TestRuntimeNotTrain` | Boundary spec states runtime does NOT train |
| `TestNoConverterImplementation` | Boundary spec states PR0056 does not implement converter code |
| `TestMatadorFutureWork` | Matador real integration remains future work |
| `TestFastAPIDeferred` | FastAPI remains deferred |
| `TestNoDemoOnlyFork` | No demo-only converter code path |
| `TestDecisionSupportOutputPath` | `decision_support_report` remains the final output path |
| `TestNonLeakageRules` | Non-leakage rules are present (no raw patient identifiers, full S3 URIs, raw checksums, secrets, account IDs, raw feature values, local paths) |
| `TestNoDiagnosis` | No diagnosis claim |
| `TestNoClinicalValidation` | No clinical validation claim |
| `TestNoReplacement` | No replacement of MRI, biopsy, radiologist, clinician, or clinical judgment |
| `TestNoRealArtifacts` | No real `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`, `.parquet`, `.proto`, `.pb` artifact files in committed examples |
| `TestNoSecretsOrIdentifiers` | No `AKIA`, `SECRET_ACCESS_KEY`, `dkr.ecr`, non-placeholder `s3://`, `sha256:` hex strings, `Nova_`, `/Users/`, `/home/`, 12-digit account IDs |
| `TestCrossReferences` | (Optional) Converter boundary doc cross-references the product input pipeline contract if implementation chooses to add a reference |
| `TestTestsAreStatic` | Test file uses no network/AWS/Docker/Terraform/App Runner — only `pathlib.Path`, `pytest`, `re` |

### 6.2 Design notes

- Follow the same pattern as `tests/test_bremen_product_input_pipeline_contract.py`.
- `ROOT = Path(__file__).resolve().parents[1]` for project root.
- `_read_spec()` helper for reading `docs/converter_preprocessing_boundary.md`.
- No synthetic H5 creation, no monkeypatching, no fixtures beyond path resolution.
- All assertions are substring checks on the spec document text.

---

## 7. File Change Plan

### 7.1 Files to be created

| File | Type | Description |
|------|------|-------------|
| `docs/converter_preprocessing_boundary.md` | New | Converter boundary specification (Section 2) |
| `tests/test_bremen_converter_preprocessing_boundary.py` | New | Static tests for the boundary spec (Section 6) |

### 7.2 Files optionally modified (with justification)

| File | Change | Justification | Recommended? |
|------|--------|---------------|-------------|
| `docs/product_input_pipeline_contract.md` | Add a single cross-reference sentence at the end of Section 6 (Controlled Converter / Preprosync / Preprocessing Boundary): "The detailed converter boundary specification is in [docs/converter_preprocessing_boundary.md](converter_preprocessing_boundary.md)." | The PR0055 contract defines the converter boundary at a high level. PR0056's spec is the detailed reference. A cross-reference connects the two documents. | **Yes** — minimal, one-sentence addition. Does not change any PR0055 decisions or requirements. |
| `docs/api_contract.md` | No change. The API contract already cross-references the product input pipeline contract (PR0055). The converter boundary is a lower-level detail that the API contract does not need to reference. | The API contract describes the runtime API. The converter boundary is a separate component outside the runtime. | **No** — no API contract change needed. |
| `docs/release_readiness_operator_notes.md` | No change. The operator notes describe runtime operation. The converter boundary is external to the runtime. | The converter is not part of the runtime service lifecycle. | **No** — no operator notes change needed. |
| `ROADMAP.md` | No change. The roadmap placeholder delegates the execution block decision to human product/engineering. | PR0056 is in a defined execution sequence that the roadmap does not yet enumerate in detail. Updating the roadmap is premature until the execution block stabilises. | **No** — no ROADMAP change. |

**Recommended change set**: 2 new files + 1 minimal cross-reference sentence
in `docs/product_input_pipeline_contract.md`.

### 7.3 Files NOT changed

- `src/` — No source changes.
- `docs/adr/0011-config-governance-gates.md` — No ADR changes.
- `docs/adr/0012-system-of-record-boundary.md` — No ADR changes.
- `docs/api_contract.md` — No changes.
- `docs/production_e2e_smoke.md` — No changes.
- `docs/release_readiness_operator_notes.md` — No changes.
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
# New boundary spec tests
python -m pytest -q tests/test_bremen_converter_preprocessing_boundary.py -v

# PR0055 contract tests (still must pass)
python -m pytest -q tests/test_bremen_product_input_pipeline_contract.py -v

# Existing tests that may be affected by the cross-reference edit
python -m pytest -q tests/test_bremen_api_contract.py -v

# Full test suite
python -m pytest -q
```

### 8.4 Safety validation commands

```bash
# Confirm no unintended file changes
git diff --name-only

# Confirm no source/test/config/infra changes beyond allowed files
git diff --name-only -- src Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml src/bremen/training agents config docs/adr ROADMAP.md

# Confirm no binary artifacts
git diff --name-only | grep -E '\.(h5|hdf5|joblib|pkl|npy|npz|parquet|proto|pb|tfstate|tfstate\.backup)$' || true

# FastAPI/starllete/uvicorn — only in deferred/non-goal context
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n docs tests ROADMAP.md || true

# Matador network libraries — must NOT appear
grep -R "MATADOR_\|Matador.*token\|Matador.*URL\|requests\|httpx\|aiohttp" -n docs tests ROADMAP.md || true

# Secrets/identifiers — must NOT appear
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|s3://\|sha256:\|Nova_\|/Users/\|/home/" -n docs tests ROADMAP.md || true

# Clinical claims — only negated safety language
grep -R "diagnos\|clinical validation\|clinically validated\|replace radiologist\|replace clinician\|replace MRI\|replace biopsy" -n docs tests ROADMAP.md || true
```

### 8.5 Safety validation expectations

| Check | Expected result |
|-------|----------------|
| `git diff --name-only` | Only `docs/converter_preprocessing_boundary.md`, `tests/test_bremen_converter_preprocessing_boundary.py`, optionally `docs/product_input_pipeline_contract.md` |
| `git diff --name-only -- src Dockerfile ...` | Empty — no source/config/infra/agent/ADR changes |
| Binary artifact grep | Empty — no artifacts |
| FastAPI | Only in deferred/non-goal context — safe |
| Matador.*token/URL/requests/httpx/aiohttp | Not present — no network client references |
| AKIA/SECRET_ACCESS_KEY/dkr.ecr | Not present |
| s3:// | Only `${VARIABLE}` placeholders or generic examples — safe |
| sha256: | Only in placeholder context — safe |
| Nova_/Users/home | Not present or in negation context only — safe |
| diagnosis/clinical validation/replace | Only negation language — safe |

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Boundary spec is too prescriptive for a future converter implementation that may have different architecture | Medium | Medium | The spec defines responsibilities and output contract — not implementation details. Converter architecture decisions are deferred to Open Questions section (Section 16). |
| Cross-reference edit to PR0055 contract document breaks existing static tests | Low | Medium | The PR0055 contract tests assert on broad content themes (e.g., "converter", "boundary") — not on absence of cross-references. A one-sentence addition at the end of Section 6 will not break any assertion. Run PR0055 contract tests before merge to confirm. |
| Static test asserts on wording that future converter implementation PR may change | Low | Low | Tests assert on architectural invariants (runtime not converter, Matador future work, h5_path/h5_uri preserved) that are not changed by converter implementation. |
| Candidate input forms described in the spec are interpreted by investors as committed implementation | Medium | Medium | The spec must use explicit CANDIDATE language: "Candidate input forms. Not yet implemented. Each requires a converter specification and implementation." The PR0055 contract already uses this language; the PR0056 spec reinforces it. |

---

## 10. Implementation Order

1. Create `docs/converter_preprocessing_boundary.md`
2. Create `tests/test_bremen_converter_preprocessing_boundary.py`
3. (Optional) Edit `docs/product_input_pipeline_contract.md` Section 6 — add one cross-reference sentence
4. Run validation (Section 8)
5. Commit with message: `feat(pr0056): converter / Preprosync / preprocessing boundary specification`

---

## 11. Non-Goals

1. No converter implementation.
2. No Preprosync implementation.
3. No protobuf parser.
4. No GeoFrame parser.
5. No converter CLI.
6. No preprocessing container execution.
7. No runtime request schema change (`POST /predictions` unchanged).
8. No `h5_path`/`h5_uri` behavior change.
9. No Matador integration.
10. No FastAPI.
11. No runtime training.
12. No model training implementation.
13. No new model.
14. No inference or preprocessing math changes.
15. No demo-only code path.
16. No real data artifacts in committed files.
17. No clinical validation or diagnosis claims.
18. No replacement of MRI, biopsy, radiologist, clinician, or clinical judgment.
19. No PR0057–PR0058 implementation.
20. No ADR changes.
21. No ROADMAP.md changes.
22. No `src/` changes.

---

Implementation role: coder
