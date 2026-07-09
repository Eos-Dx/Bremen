# Bremen Converter / Preprosync / Preprocessing Boundary Specification

**PR0056** — Converter / Preprosync / preprocessing boundary
specification. Specification and static tests only; no implementation.

---

## 1. Purpose

This document defines the controlled converter / Preprosync /
preprocessing boundary that translates candidate external input
forms into the canonical Bremen input package (defined in
`docs/product_input_pipeline_contract.md`, PR0055).

The boundary is the controlled point where:

- An external scan package (GeoFrame, protobuf-derived data,
  Preprosync output, or other candidate input form) is ingested.
- Required metadata is verified.
- Explicit target/control refs are resolved.
- A canonical H5 (or H5-equivalent) artifact is produced.
- The artifact is made available to the existing Bremen runtime
  via `h5_path` or `h5_uri`.

This is a **specification contract**, not an implementation. No
converter code, Preprosync integration, protobuf parsing, GeoFrame
parsing, or converter CLI is delivered in PR0056.

---

## 2. Scope

**Covered**: Specification of the converter boundary — inputs,
outputs, responsibilities, metadata contract, layout and preflight
requirements, runtime interface, error categories, non-leakage
rules, demo-safe operation, implementation prerequisites, and open
questions.

**Not covered**: Converter implementation, Preprosync container
execution, protobuf parsing, GeoFrame parsing, converter CLI,
runtime request schema changes, Matador integration, FastAPI,
runtime training, clinical validation, or diagnosis.

---

## 3. Inputs

The following external input forms are candidate inputs. None are
implemented yet. Each requires a converter specification and
implementation before the product input pipeline is operational
(see PR0055 Sections 4 and 5 for inventory detail).

### 3.1 External prepared scan package

**Status**: Candidate input form. Requires verification.

No specification, parser, or reference exists in the Bremen
repository. This represents a generic external scan package that
may be provided by clinical or research partners.

### 3.2 GeoFrame-derived data

**Status**: Candidate input form. Requires external GeoFrame
schema specification.

No GeoFrame parser, reader, dependency, or test exists in the
Bremen repository. GeoFrame schema mapping and data-access
specification must be provided by the Bremen/GeoFrame integration
team before a converter can be designed.

### 3.3 Protobuf-derived data

**Status**: Candidate input form. Requires external protobuf schema
specification.

No protobuf `.proto` files, `protobuf` dependency, or protobuf
parsing code exists in the Bremen repository. Protobuf schema
definitions must be provided before a converter can parse
protobuf-derived scan data.

### 3.4 Preprosync / preprocessing container output

**Status**: Candidate input form. Requires Preprosync integration
specification.

No Preprosync references, preprocessing container Docker image,
or CI configuration for a separate preprocessing container exists
in the Bremen repository. The Preprosync input format and
integration contract must be specified before a converter can
ingest Preprosync output.

---

## 4. Outputs

The converter/preprocessing boundary must produce a canonical
Bremen input package satisfying all requirements from PR0055
Section 7 (Canonical Bremen Input Package). The output contract is:

| # | Requirement | Source |
|---|---|---|
| 1 | Canonical H5 or canonical H5-equivalent artifact (`.h5` HDF5, readable by `h5py >= 3.0`) | PR0055 Section 7.1 |
| 2 | Compatible with existing Bremen H5 preflight and layout expectations (canonical or calibration_sample layout, detectable by `H5LayoutAdapter`) | PR0055 Sections 7.2–7.3 |
| 3 | Compatible with explicit `target_scan_ref` and `control_scan_ref` (passed at submit time, not embedded in H5) | PR0055 Section 9 |
| 4 | Compatible with existing runtime `h5_path` or `h5_uri` staging (local file or S3-staged) | PR0055 Section 10 |
| 5 | Accompanied by safe metadata: patient identifier, layout category, target/control side values, optional checksum | PR0055 Section 8 |
| 6 | Optionally accompanied by SHA-256 checksum for integrity verification at staging time | PR0055 Section 8.4 |
| 7 | Free of raw patient identifiers in committed examples (use synthetic `<PATIENT_ID>` placeholders) | PR0055 Section 8.7 |
| 8 | Free of full S3 URIs in committed examples (use `${VARIABLE}` placeholder notation) | PR0055 Section 7.4 |
| 9 | Free of raw feature values in committed examples (features are computed by the runtime, not embedded in input) | PR0055 Section 7.4 |
| 10 | Free of local absolute paths and secrets (no `/Users/`, `/home/`, `AKIA`, `SECRET_ACCESS_KEY`, account IDs, registry URLs) | PR0055 Section 7.4 |

---

## 5. Boundary Responsibilities

The converter / preprocessing boundary is responsible for:

1. **Accept or identify candidate external input form category.**
   Determine which external input form is being processed
   (GeoFrame, protobuf-derived, Preprosync, or other).

2. **Verify required metadata presence.** Confirm that the
   external input contains or can produce all metadata required
   by the canonical input package contract (patient identifier,
   target/control side, layout category).

3. **Ensure explicit target/control refs are available.** Resolve
   or preserve `target_scan_ref` and `control_scan_ref` values.
   Pass them alongside the canonical H5 at submit time — not
   embedded inside the H5.

4. **Produce canonical H5 or canonical H5-equivalent artifact.**
   Translate scan profiles, metadata, and refs into a valid HDF5
   file satisfying the canonical input package specification.

5. **Preserve layout/preflight compatibility.** The output must
   pass `H5LayoutAdapter` detection and `run_h5_preflight()`
   validation. No new preflight logic is required.

6. **Produce safe metadata for runtime staging.** The converter
   output must include metadata required by the runtime's staging,
   preflight, preprocessing, and inference pipeline.

7. **Avoid leaking identifiers or raw values into committed
   examples.** Use synthetic placeholders (`<PATIENT_ID>`,
   `<SAMPLE_REF>`) in committed test fixtures, docs, and examples.

---

## 6. Out-of-Scope Responsibilities

The converter boundary is NOT responsible for:

| Category | Responsibility | Owned by |
|---|---|---|
| Runtime prediction | Submitting jobs, polling, handling results | Bremen runtime (`src/bremen/api/`) |
| H5 staging | Download from S3, checksum verification at staging | `src/bremen/h5_inputs.py` |
| H5 preflight | Validating container structure and metadata | `src/bremen/api/preflight.py` |
| Preprocessing bridge | 15-feature v0.1 extraction | `src/bremen/api/preprocessing_bridge.py` |
| Inference | Portable logistic regression execution | `src/bremen/api/inference_handler.py` |
| Decision-support report | Building safe structured output report | `src/bremen/api/decision_support.py` |
| Model loading | Startup model fetch, checksum, `joblib.load()` | `src/bremen/api/model_state.py` |
| Matador system-of-record | Resolving patient/scan refs to H5 sources | Future — scaffold in `src/bremen/system_of_record.py` |
| FastAPI transport | ASGI web framework | Deferred — not implemented |
| Model training | Feature computation for training, model fitting | `src/bremen/training/` (offline) |
| Clinical interpretation | Diagnosis, clinical decision-making | Human clinician |

---

## 7. Metadata Contract

The converter output must carry the following metadata, aligned
with PR0055 Section 8:

### 7.1 Artifact identifier

An opaque input package ID (external ref or generated UUID).

### 7.2 Layout category

Either `canonical` or `calibration_sample`. Detected by the
runtime's `H5LayoutAdapter` protocol.

### 7.3 Target/control refs

`target_scan_ref` and `control_scan_ref` strings. Canonical
layout expects `"target"`/`"contralateral"`. Calibration layout
expects group paths (e.g., `calib_*/sample_01_*`).

### 7.4 Checksum

Optional SHA-256 checksum (`sha256:<64-hex>`) for integrity
verification at staging time.

### 7.5 Preprocessing provenance

Category indicating which external input form produced this
package and what conversion was applied. Not consumed by the
current runtime; reserved for future pipeline audits.

### 7.6 Contract version

`contract_version` field (e.g., `"v0.1"`) to support future
contract evolution.

### 7.7 Safety

No patient-identifying metadata in committed examples. Use
synthetic placeholders.

---

## 8. Explicit Target/Control Refs

`target_scan_ref` and `control_scan_ref` are **required** at
submit time. The converter must preserve or produce valid refs
matching the expected values for the target layout:

| Layout | `target_scan_ref` | `control_scan_ref` |
|---|---|---|
| Canonical | `"target"` | `"contralateral"` |
| Calibration sample | Group path (e.g., `calib_*/sample_01_*`) | Group path (e.g., `calib_*/sample_02_*`) |

Refs are passed alongside the H5 path in the prediction request —
not embedded in the H5 file itself. The runtime validates refs
during preflight via the H5 layout adapter.

---

## 9. Layout and Preflight Requirements

The converter output must pass the existing `H5LayoutAdapter`
detection and `run_h5_preflight()` validation. No new preflight
logic is required.

**Supported layouts** (from `src/bremen/api/h5_layouts.py`):

- **Canonical**: `/patient/id`, `/scans/target/measurements`,
  `/scans/target/side`, `/scans/contralateral/measurements`,
  `/scans/contralateral/side`.
- **Calibration sample**: Top-level `calib_*` groups with
  `sample/patient_name`, `sample/sample_type`,
  `sets/{set_n}/integration/i`, `sets/{set_n}/integration/q`.

The converter must produce output matching one of these two layout
categories.

---

## 10. Canonical Bremen Input Package Compatibility

The converter output must satisfy all requirements from PR0055
Section 7 (Canonical Bremen Input Package). In summary:

| Area | Requirement |
|---|---|
| Format | HDF5 `.h5`, readable by `h5py >= 3.0` |
| Layout | Canonical or calibration_sample (detectable by adapter) |
| Profiles | 1D or 2D numpy float arrays, at least 1 per side |
| Metadata | Patient identifier, side values, layout category |
| Ref handling | Refs passed at submit time, not embedded in H5 |
| Prohibited | No raw patient names, full S3 URIs, secrets, local paths, raw feature values |

---

## 11. Runtime Interface

The converter output feeds into the existing Bremen runtime via
the unchanged `h5_path` and `h5_uri` input modes.

**Workflow:**

1. Converter produces canonical H5 artifact.
2. Artifact is placed at a local path (dev/test) or uploaded to
   S3 (staging/production).
3. A prediction request is submitted via `POST /predictions`
   with `h5_path` or `h5_uri`, `target_scan_ref`, and
   `control_scan_ref`.
4. Runtime stages the H5 (if S3), runs preflight, preprocessing,
   inference, and returns the decision-support report.

**No runtime API changes.** The `POST /predictions` request schema
is unchanged. The converter does not call the runtime API — it
produces artifacts that the runtime consumes via existing
mechanisms.

---

## 12. Error Classes / Failure Categories

The following specification-level error categories are defined for
the future converter implementation. PR0056 defines these as
specification categories only — no error handling is implemented.

| Error category | Description |
|---|---|
| `unsupported_input_category` | External input form is not a recognised candidate type |
| `missing_required_metadata` | External input lacks required metadata fields |
| `invalid_target_control_refs` | Refs are missing, malformed, or do not match layout |
| `layout_incompatibility` | Converter output does not pass H5 layout detection |
| `preflight_incompatibility` | Converter output fails runtime preflight validation |
| `unsafe_metadata_detected` | Metadata contains potential identifier leakage |
| `checksum_required` | External staging requires checksum but none provided |
| `canonical_package_incompatible` | Converter output violates canonical input contract |

---

## 13. Non-Leakage Rules

The converter / preprocessing boundary must comply with the same
non-leakage rules defined in PR0055 Section 14. Committed
converter examples, test fixtures, and docs must **not** contain:

- Raw patient identifiers (names, IDs, `Nova_` patterns).
- Full S3 URIs (`s3://bucket/key`); use `${VARIABLE}` notation.
- Raw target/control scan refs with real patient data.
- Raw feature values or feature vectors.
- Raw model checksum hex strings.
- AWS credentials, access keys, account IDs, or registry URLs.
- Raw scan arrays or measurement data with real values.
- Local-machine absolute paths (`/Users/`, `/home/`).

---

## 14. Demo-Safe and Production-Compatible Operation

The same converter boundary applies to demo and production
scenarios. There is no separate demo-only converter code path.

| Scenario | Data source | Converter behavior |
|---|---|---|
| Demo / investor walkthrough | Synthetic or sanitised placeholder data | Same converter contract; same output format |
| Production | Real patient data via Matador source-of-record | Same converter contract; same output format |

The only difference is the source of the input data. The converter
must not change behavior, output format, or validation rules based
on the deployment context.

---

## 15. Implementation Prerequisites

Before converter implementation can begin, the following must be
resolved:

1. **External input form selection.** Which candidate input form
   (GeoFrame, protobuf-derived, Preprosync, or other) is the first
   converter target?
2. **External schema specification.** GeoFrame schema, protobuf
   schema, or Preprosync contract must be provided by the
   respective integration teams.
3. **Converter deployment architecture.** Is the converter a
   standalone service, a CLI tool, or a preprocessing container?
4. **Credential and access management.** How will the converter
   securely access external scan packages and write canonical
   H5 artifacts?
5. **Canonical input package versioning.** How will contract
   versions be managed as the canonical input evolves?

---

## 16. Open Questions

1. Which external input form is the first converter target?
2. Who provides the GeoFrame/protobuf schema specification?
3. Is the converter a standalone service or a preprocessing
   container?
4. How are credentials/secrets for the external input source
   managed?
5. What is the canonical input package versioning strategy?
6. How does the converter handle multi-patient external inputs?

---

## 17. Non-Goals

1. No converter implementation.
2. No Preprosync implementation.
3. No protobuf parser.
4. No GeoFrame parser.
5. No converter CLI.
6. No preprocessing container execution.
7. No runtime request schema change (`POST /predictions` unchanged).
8. No `h5_path`/`h5_uri` behavior change.
9. No Matador system-of-record integration.
10. No FastAPI, uvicorn, starlette, or ASGI.
11. No runtime training.
12. No model training implementation.

**The Bremen runtime does not train.** No training code is executed
or invoked by the converter boundary or the runtime inference path.

**The Bremen runtime does not become the converter service.**
The converter is a separate component outside the runtime.
The runtime consumes canonical H5 artifacts but does not parse
external input formats.

13. No new model.
14. No inference or preprocessing math changes.
15. No demo-only code path.
16. No real data artifacts in committed files.
17. No clinical validation.
18. No diagnosis.
19. No replacement of MRI, biopsy, radiologist, clinician, or
    clinical judgment.
20. No PR0057–PR0058 implementation.
