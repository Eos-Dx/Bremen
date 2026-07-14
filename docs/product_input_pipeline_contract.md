# Bremen Product Input Pipeline Contract

**PR0055** — Product input pipeline inventory and canonical input contract.

---

## 1. Purpose

This document defines the productizable input pipeline contract for
Bremen. External scan packages — from GeoFrame, protobuf-derived data,
Preprosync output, or other external sources — must be converted to a
**canonical Bremen input package** that the existing Bremen runtime can
accept. This contract defines what that canonical input package looks
like, what metadata it must carry, and how it connects to the existing
runtime prediction and decision-support path.

This is **not** a demo-only format. The canonical input package contract
is intended for both demo/presentability and future production use.

---

## 2. Scope

**Covered**: Definition of the productizable input pipeline, candidate
external input forms, the controlled converter / preprocessing boundary,
the canonical Bremen input package specification, required metadata,
explicit target/control refs, accepted runtime input modes, the
investor-presentable workflow, non-leakage rules, and open questions
before implementation.

**Not covered**: Converter implementation, Preprosync integration,
protobuf parsing, GeoFrame parsing, Matador system-of-record
integration, FastAPI, runtime request schema changes, model training,
clinical validation, or diagnosis.

---

## 3. Productizable Workflow

The target productizable workflow is:

```
external prepared scan package / GeoFrame / protobuf-derived data
  -> controlled converter / Preprosync / preprocessing boundary
    -> canonical Bremen input package
      -> existing Bremen runtime (POST /predictions)
        -> decision_support_report
```

This workflow is not demo-only. Investor walkthroughs must use the same
contract intended for productization.

### Key assertions

1. **Bremen runtime remains stable.** The existing
   `POST /predictions → GET /predictions/{job_id}` path, preflight
   gate, preprocessing bridge, inference handler, and decision-support
   report are unchanged. The canonical input package is an *external
   input contract* — it describes what goes *into* the staging/preflight
   boundary, not a new runtime path.

2. **Runtime does not become the converter service.** The converter
   (GeoFrame → canonical H5, protobuf → canonical H5, Preprosync
   output → canonical H5) is a separate component that lives outside
   the Bremen runtime. PR0055 defines the contract that the converter
   must produce; it does not implement the converter.

3. **Runtime does not train.** No training code is added, modified, or
   invoked by this contract.

4. **Matador remains future source-of-record integration.** The
   canonical input package is a staging/development input contract.
   Long-term source-of-record ownership remains with Matador
   (ADR-0012). This contract does not change that.

5. **FastAPI remains deferred.** No FastAPI, uvicorn, starlette, or
   ASGI framework is introduced.

---

## 4. Candidate External Input Forms

The following external input forms have been identified as candidates.
None are implemented yet. Each requires a converter specification and
implementation (tracked as future PR0056+ work).

### 4.1 GeoFrame-derived data

**Status**: Candidate input form. Requires verification.

No GeoFrame parser, reader, dependency, or test exists in the Bremen
repository. GeoFrame schema mapping is not yet defined. A converter
must be specified and implemented to translate GeoFrame-derived data
into the canonical Bremen input package.

### 4.2 Protobuf-derived data

**Status**: Candidate input form. Requires verification.

No protobuf `.proto` files, `protobuf` dependency, or protobuf
parsing code exists in the Bremen repository. Protobuf schema
definitions are not yet available. A converter must be specified and
implemented to translate protobuf-derived data into the canonical
Bremen input package.

### 4.3 Preprosync / preprocessing container output

**Status**: Candidate input form. Requires verification.

No Preprosync references, preprocessing container Docker image, or
CI configuration for a separate preprocessing container exists in the
Bremen repository. Preprosync integration is not yet defined. A
converter or integration boundary must be specified.

---

## 5. Inventory Findings and Evidence Status

| Category | Evidence in repo | Status |
|---|---|---|
| GeoFrame references | None | Candidate only; requires specification |
| Protobuf / `.proto` files | None | Candidate only; requires specification |
| Converter module/interface | None | Not implemented; PR0056+ |
| Preprosync integration | None | Candidate only; requires specification |
| Canonical input contract | This document (PR0055) | First definition |
| H5 layout adapters | `src/bremen/api/h5_layouts.py` | Runtime-side detection (canonical + calibration_sample) |
| H5 preflight | `src/bremen/api/preflight.py` | Runtime-side validation |
| H5 staging | `src/bremen/h5_inputs.py` | Runtime-side S3 → local staging |
| Preprocessing bridge | `src/bremen/api/preprocessing_bridge.py` | Runtime-side 15-feature v0.1 extraction |
| System-of-record boundary | `src/bremen/system_of_record.py` | Scaffold only; real Matador resolver not implemented |

The existing runtime provides H5 layout detection, preflight validation,
H5 staging, preprocessing, and inference. The missing piece is the
**converter** that translates external input forms into a canonical H5
that the runtime can already accept.

---

## 6. Controlled Converter / Preprosync / Preprocessing Boundary

A **controlled converter** is the boundary between external scan
packages and the canonical Bremen input package. The converter:

1. Ingests one external input form (GeoFrame data, protobuf-derived
   data, or Preprosync output).
2. Translates scan profiles, metadata, and refs into the canonical
   Bremen input package format.
3. Produces an HDF5 (`.h5`) file that satisfies the canonical input
   package specification (Section 7).
4. Is a **separate component** — not part of the Bremen runtime.
5. Is responsible for any external-format parsing (GeoFrame reader,
   protobuf deserialization, Preprosync connector).
6. Must not embed patient-identifying metadata in committed examples.

The converter is **not yet implemented**. PR0055 defines the output
contract the converter must satisfy. Converter specification and
interface design are tracked as future work (PR0056+).

The detailed converter boundary specification is in
[docs/converter_preprocessing_boundary.md](converter_preprocessing_boundary.md).

---

## 7. Canonical Bremen Input Package

The canonical Bremen input package is an HDF5 container (`.h5` file)
that the existing Bremen runtime can accept via `h5_path` or `h5_uri`.

### 7.1 Format

| Requirement | Specification |
|---|---|
| Format | HDF5 (`.h5`), readable by `h5py >= 3.0` |
| Layout | Either `canonical` or `calibration_sample` (detectable by `H5LayoutAdapter`) |
| Profiles | 1D or 2D numpy arrays of float values. At least 1 profile per side. |
| Conversion | Produced by a controlled converter from an external input form |

### 7.2 Canonical layout paths

| Path | Type | Required | Description |
|---|---|---|---|
| `/patient/id` | Scalar string | Yes (or fallback via calibration metadata) | Patient identifier |
| `/scans/target/measurements` | Array (1D or 2D) | Yes | Target scan profiles |
| `/scans/target/side` | Scalar string | Yes | Target side (L, R, LEFT, RIGHT) |
| `/scans/contralateral/measurements` | Array (1D or 2D) | Yes | Contralateral scan profiles |
| `/scans/contralateral/side` | Scalar string | Yes | Contralateral side |

### 7.3 Calibration sample layout paths

| Path | Type | Required | Description |
|---|---|---|---|
| `/{calib_group}/{sample_group}/sample/patient_name` | Scalar string | Yes | Patient name (fallback identifier) |
| `/{calib_group}/{sample_group}/sample/sample_type` | Scalar string | Yes | Sample type (e.g., "RIGHT BREAST") |
| `/{calib_group}/{sample_group}/sets/{set_n}/integration/i` | 1D array | Yes | Integration I-channel profile |
| `/{calib_group}/{sample_group}/sets/{set_n}/integration/q` | 1D array | Yes | Integration Q-channel profile |

`{calib_group}` is a top-level group with a `calib_*` prefix.
`{sample_group}` identifies a specific sample. At least one
`{set_n}` (named `set_001`, `set_002`, etc.) is required per sample.

### 7.4 Prohibited content

The canonical input package must **not** contain:

- Raw patient names in committed examples (use synthetic identifiers
  like `<PATIENT_ID>`).
- Raw scan arrays with real patient data in committed examples.
- Full S3 URIs, credentials, access keys, account IDs, or registry
  URLs anywhere in H5 metadata.
- Local-machine absolute paths (`/Users/`, `/home/`).
- Raw feature values (features are computed by the runtime, not
  embedded in the input).

**Note**: The layout defined in Sections 7.2–7.3 has been verified
against the real upstream eosdx-container v0.3 schema in
[docs/preprocessing_source_reconciliation.md](preprocessing_source_reconciliation.md).
See that document for the reconciliation result and integration
decision options.

---

## 8. Required Metadata

### 8.1 Artifact identifier

Each canonical input package should carry a stable artifact identifier
or opaque input package ID in its metadata. This can be an external
ref (e.g., `<SCAN_PACKAGE_REF>`) or a generated UUID.

### 8.2 Layout category

The layout category (`canonical` or `calibration_sample`) is detected
by the runtime's `H5LayoutAdapter` protocol. The converter should
produce consistent layouts matching one of the supported categories.

### 8.3 Target/control ref presence

`target_scan_ref` and `control_scan_ref` strings are provided alongside
the H5 path at submit time. For canonical layouts, the expected values
are `"target"` and `"contralateral"`. For calibration layouts, the refs
are group paths (e.g., `calib_*/sample_01_*`).

### 8.4 Checksum presence

An optional SHA-256 checksum (`sha256:<64-hex>`) can be provided for
integrity verification at staging time. The checksum is verified before
the H5 container is passed to preflight.

### 8.5 Preprocessing provenance category

The converter should track which external input form produced the
canonical input package and what conversion steps were applied. This
metadata is not consumed by the current runtime but will be used in
future pipeline audits.

### 8.6 Schema/contract version

A `contract_version` field (e.g., `"v0.1"`) should be included in the
package metadata to support future contract evolution.

### 8.7 No patient-identifying metadata

Committed examples, test fixtures, and documentation must not contain
real patient identifiers. Use synthetic placeholders (e.g.,
`<PATIENT_ID>`, `<SAMPLE_REF>`).

---

## 9. Explicit Target/Control Refs

Explicit target and control scan refs are **required** for all
prediction requests. The refs are passed alongside the H5 path at
submit time — they are not embedded in the H5 file itself.

| Layout | target_scan_ref value | control_scan_ref value |
|---|---|---|
| Canonical | `"target"` | `"contralateral"` |
| Calibration sample | Group path (e.g., `calib_*/sample_01_*`) | Group path (e.g., `calib_*/sample_02_*`) |

Refs must be non-empty strings that match existing group paths in the
H5 container. The runtime's H5 layout adapter validates refs during
preflight.

---

## 10. Accepted Controlled Runtime Input Modes

The canonical Bremen input package is staged into the runtime via the
existing controlled input modes:

| Mode | Description | Status |
|---|---|---|
| `h5_path` | Local filesystem path to the canonical H5 file | Dev/test convenience mode |
| `h5_uri` | S3 URI (with optional checksum) pointing to the canonical H5 file | Staging/smoke mode |

Both modes are **controlled staging/development modes**, not long-term
source-of-record ownership modes. In production, the source-of-record
boundary (Matador, via `RecordResolver`) will resolve a patient/scan
ref to a `ResolvedInput` containing an `h5_uri` or `h5_path` pointing
to the canonical input package.

**No request schema change in PR0055.** The existing
`POST /predictions` request body (`h5_path`, `h5_uri`,
`target_scan_ref`, `control_scan_ref`) is unchanged.

---

## 11. Runtime Prediction and Decision-Support Output

Once the canonical input package is staged, the existing runtime path
is used:

1. `POST /predictions` — Submit the canonical input package via
   `h5_path` or `h5_uri` with explicit `target_scan_ref` and
   `control_scan_ref`.
2. `GET /predictions/{job_id}` — Poll until `status: "completed"`.
3. `result.decision_support_report` — Contains the triage
   recommendation with safety disclaimers.

The decision-support report includes:
- `report_schema_version: "v0.1"`
- `intended_use` stating MRI continuation decision support only
- `limitations` stating not a diagnosis, not clinically validated,
  does not replace MRI/biopsy/radiologist/clinician/clinical judgment
- `model_metadata`, `input_summary`, `prediction_summary`,
  `decision_support` with safe framing

No change to the existing output path.

---

## 12. Investor-Presentable Workflow Without Demo-Only Fork

### 12.1 Workflow steps

1. **Sanitised/synthetic external input placeholder.** A synthetic or
   sanitised scan package (representing GeoFrame/protobuf-derived
   data output) is prepared outside the runtime. This demonstrates the
   input form without requiring real patient data.

2. **Converter/preprocessing boundary placeholder.** A placeholder
   converter (or documented conversion step) transforms the external
   input into the canonical Bremen input package. In demo mode, this
   can be a script, a notebook cell, or a documented manual step —
   the same contract applies.

3. **Canonical Bremen input package.** The conversion produces a valid
   `.h5` file satisfying the canonical input package specification.

4. **Existing runtime prediction call.** The canonical input package
   is submitted to `POST /predictions` via `h5_path` or `h5_uri`.

5. **Completed job response.** Poll `GET /predictions/{job_id}` until
   `status: "completed"`.

6. **Decision-support report.** The `result.decision_support_report`
   contains the triage recommendation with safety disclaimers.

### 12.2 Demo-safe guarantee

The workflow described above uses the same canonical input package
contract that a production system would use. There is **no separate
demo-only format**. A production deployment receives the same file
format, the same metadata, and produces the same decision-support
output. The only difference is the source of the data: a synthetic
or sanitised placeholder for demo, and real patient data (via
Matador source-of-record) in production.

### 12.3 Safety language

The walkthrough explicitly states that this is a product pipeline
demonstration, not a clinical validation, not a diagnosis, and does
not replace MRI, biopsy, radiologist, clinician, or clinical judgment.

---

## 13. Demo-Safe and Production-Compatible Constraints

1. The canonical input package format is **identical** for demo and
   production. Only the data source differs.
2. Synthetic/sanitised data must use placeholder identifiers
   (e.g., `<PATIENT_ID>`, `<SAMPLE_REF>`), not real patient data.
3. No hardcoded local paths in demo scripts. Use environment
   variables or temp directories.
4. No real S3 URIs, account IDs, or credentials in committed
   examples or test fixtures.
5. Demo scripts must not bypass checksum verification or preflight
   gates.
6. Demo scripts must not invoke the converter directly from the
   runtime. The converter is a separate step.

---

## 14. Non-Leakage Rules

Committed examples, test fixtures, and documentation must **not**
contain:

- Raw patient identifiers (names, IDs, `Nova_` patterns).
- Raw H5 filesystem paths (full paths; basenames only).
- Full S3 URIs (`s3://bucket/key`).
- Raw target/control scan refs with real patient data.
- Raw feature values or feature vectors.
- Raw model checksum hex strings.
- AWS credentials, access keys, account IDs, or registry URLs.
- Raw scan arrays or measurement data with real values.
- Local-machine absolute paths (`/Users/`, `/home/`).

---

## 15. Open Questions Before Implementation

1. **Which external input form is the first converter target?**
   GeoFrame, protobuf-derived data, or Preprosync output must be
   decided before converter specification begins.
2. **Who provides the GeoFrame/protobuf schema specification?**
   External schema definitions are needed before the converter can
   be designed.
3. **Is the converter a standalone service or a preprocessing
   container?** Architectural decision needed for converter
   deployment and lifecycle.
4. **How are credentials/secrets for the external input source
   managed?** Secure access to external scan packages (GeoFrame
   storage, Preprosync container) requires credential management.
5. **What is the canonical input package versioning strategy?**
   Future contract evolution (schema changes, new layout categories)
   needs a versioning approach.
6. **How does the converter handle multi-patient H5 containers?**
   If an external input contains multiple patients, the converter
   must either split into per-patient packages or expose selection.

---

## 16. Non-Goals

1. No converter implementation.
2. No Preprosync implementation.
3. No protobuf parser.
4. No GeoFrame parser.
5. No runtime request schema change (`POST /predictions` is unchanged).
6. No Matador system-of-record integration.
7. No FastAPI, uvicorn, starlette, or ASGI.
8. No runtime training.
9. No model training implementation.
10. No new model.
11. No inference or preprocessing math changes.
12. No demo-only fork.
13. No real data artifacts in committed files.
14. No clinical validation.
15. No diagnosis.
16. No replacement of MRI, biopsy, radiologist, clinician, or clinical
    judgment.
17. No PR0056–PR0058 implementation.
