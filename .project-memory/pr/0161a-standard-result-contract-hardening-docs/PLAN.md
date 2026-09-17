# PR0161A — Standard Result Contract Hardening Documentation

Branch: `0161a-standard-result-contract-hardening-docs`

Status: documentation/spike only.

## Goal

Record the production evidence and implementation direction for the next Standard Model Result hardening PR without changing runtime behavior.

This documentation exists because the delivered roadmap diverged from the older 0157–0162 draft:

- 0157 — Standard Model Result Contract v1 documentation
- 0158 — Unified Model Result Mapper v1
- 0158a — Standard Result Contract Hardening
- 0159 — Standard Result Metadata Completion
- 0160 — Model Package Owned Scientific Preprocessing
- 0161A — this documentation/spike
- 0161 — planned implementation: Standard Result Contract Hardening + `referring_physician`

The older draft that described 0161 as a model-native inference API is no longer the current execution order.

## Evidence basis

This plan is based on:

1. live production Standard Result JSON for Bremen and Aramina;
2. the all-patient Bremen/Aramina compatibility smoke;
3. live report-shape audit;
4. Standard Model Result Contract v1 documentation;
5. inspection of three available H5 examples:
   - `Nova_378(1).h5`
   - `benign_one_patient(1).h5` / Nova_227
   - `AlexSynthetic_002(1).h5` / Nova_376
6. current architecture evidence showing package-owned `SourceMetadata`.

## Decisions already made

### `analysis_author`

`analysis_author` is caller-provided REST request metadata.

It is not model output and it is not source/H5 patient metadata.

The current job request contract already accepts it, and the value is transported into the Standard Result.

No change is required to this ownership rule.

### `referring_physician`

Add `referring_physician` to the common Standard Result envelope for both Bremen and Aramina.

Required public position:

```json
{
  "patient_id": "Nova_214",
  "patient_age": 47,
  "referring_physician": "",
  "scan_date_time": "2025-05-14 12:55:46",
  "operator_id": ""
}
```

Contract direction:

- common top-level Standard Result field;
- immediately after `patient_age`;
- not under `specific_output`;
- additive-only;
- current fallback value is `""`;
- do not fabricate a physician name;
- do not add a REST request field merely to populate the report;
- future real extraction must remain package-side/source-metadata-side.

The current inspected H5 evidence contains no referring-physician field.

### Scientific ownership

No part of PR0161 may add H5 paths, field aliases, preprocessing logic, feature logic, gates, thresholds, or scientific interpretation to generic platform mapper/API code.

The allowed direction remains:

`model package source adapter -> SourceMetadata -> RuntimePrediction -> generic mapper -> StandardModelResult`

## Technical debt to address in PR0161

PR0161 is intended to handle these related Standard Result contract issues together.

### 1. Scan timestamp contract drift

Contract v1 requires RFC3339-compatible timestamps with timezone information and no fractional seconds.

Production currently shows different representations:

- Bremen Standard Result: `2025-05-28T10:19:55`
- Bremen runtime/source metadata: `2025-05-28 10:19:55`
- Aramina Standard Result: `2025-05-14T12:55:46+00:00`

This is both:
- a serialization-format inconsistency (` ` vs `T`);
- a timezone-semantics inconsistency (no offset vs explicit offset).

PR0161 must not invent `+00:00` when the source timezone is not authoritative.

The implementation must reconcile the v1 contract with what the source metadata can truthfully provide.

### 2. Failed report endpoint is too sparse

For failed jobs the workflow report endpoint currently returns only a small `REPORT_NOT_AVAILABLE` envelope.

The job detail already contains safe structured failure diagnostics.

PR0161 should define and implement a normalized safe failure-report envelope for both Bremen and Aramina, while preserving existing job-detail diagnostics and backward compatibility.

No raw exceptions, paths, tokens, S3 locations, artifact internals, or non-allowlisted values may leak.

### 3. Missing-value representation is not fully explicit

Observed Standard Result/report values currently mix `null` and `""` for unavailable metadata.

Examples include:
- `eoscan_version: null`
- `mammography_suspicious_field: ""`
- historical empty-string metadata fields

PR0161 should explicitly document field-level missing-value semantics rather than allowing accidental mapper-specific conventions.

The requested `referring_physician` v1 behavior is currently `""` when unavailable.

## Planned PR0161 implementation scope

Branch proposal:

`0161-standard-result-contract-hardening`

One PR should:

1. add `referring_physician` to the Standard Result common envelope;
2. transport it through `SourceMetadata` without generic H5 parsing;
3. return `""` for the currently inspected H5 examples because no authoritative physician value exists;
4. resolve/implement the scan timestamp representation policy consistently for Bremen and Aramina;
5. add a safe normalized failed-report contract;
6. document explicit missing-value semantics for touched fields;
7. preserve all current endpoint paths, authentication, model IDs, job lifecycle, legacy report payloads, scientific outputs, probabilities, thresholds, and decisions.

## Non-goals

- no model retraining;
- no probability changes;
- no threshold changes;
- no preprocessing changes;
- no feature changes;
- no eligibility/gate changes;
- no model-specific H5 knowledge in generic mapper/API/runtime code;
- no clinical claims;
- no PDF work;
- no direct model-native inference API in this PR.

## Validation direction for PR0161

Required tests should cover:

- Bremen Standard Result has `referring_physician`;
- Aramina Standard Result has `referring_physician`;
- current H5 evidence produces `referring_physician == ""`;
- generic mapper does not contain H5 paths/aliases;
- scan timestamp contract is deterministic across workflows;
- timezone is never fabricated without an authoritative source;
- successful legacy payloads remain unchanged;
- failed Bremen report exposes safe normalized diagnostics;
- failed Aramina report exposes safe normalized diagnostics;
- failure report never exposes raw exception text or private source/artifact paths;
- full test suite remains green.
