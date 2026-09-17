# PR0161A — `referring_physician` Spike

## Question

How should this field be added for both Bremen and Aramina?

```json
{
  "patient_id": "Nova_214",
  "patient_age": 47,
  "referring_physician": "",
  "scan_date_time": "2025-05-14 12:55:46",
  "operator_id": ""
}
```

## Conclusion

`referring_physician` belongs to the common Standard Result patient/source metadata envelope.

It must not be placed in `specific_output`.

It must not be treated as scientific model output.

It should travel through the existing package-owned source metadata boundary.

Target data flow:

```text
supported raw H5/container
    -> selected model package source metadata adapter
    -> SourceMetadata.referring_physician
    -> RuntimePrediction.source_metadata
    -> generic Standard Result mapper
    -> StandardModelResult.referring_physician
```

## H5 evidence inspected

The following available H5 files were inspected:

1. `Nova_378(1).h5`
2. `benign_one_patient(1).h5` — Nova_227
3. `AlexSynthetic_002(1).h5` — Nova_376

The inspection searched:

- all H5 object paths;
- all attribute names;
- all string attribute values;
- all string dataset values;

for case-insensitive terms:

- `physician`
- `referr`
- `doctor`
- `clinician`

Result:

```text
Nova_378(1).h5             0 matches
benign_one_patient(1).h5  0 matches
AlexSynthetic_002(1).h5   0 matches
```

Examples of metadata that do exist in these H5 files include:

- `session.operator_username`
- patient identifiers / patient name
- detector hardware identifiers
- scan/session metadata

No referring-physician metadata was found.

## Repository evidence

The available repository snapshot contains UI wording referring to a "referring clinician", but no data-model/source-metadata field named `referring_physician`.

An existing UI test in the available snapshot explicitly asserted that the literal "Referring Physician" was not present in that UI.

The current architecture evidence from PR0159/0160 shows `SourceMetadata` as a transport-neutral model-package-produced patient/acquisition metadata contract.

That is the correct boundary for this field.

## REST ownership

Do not add `referring_physician` to `POST /api/jobs` as part of this change.

`analysis_author` and `prediction_comment` are caller-provided analysis metadata.

`referring_physician` is conceptually patient/source metadata.

If a future external source-registration API intentionally accepts patient metadata, that can be designed separately.

## First implementation behavior

Because no authoritative physician value exists in the inspected H5 evidence, the first implementation should produce:

```json
"referring_physician": ""
```

for those containers.

This is a stable contract field, not a fabricated physician value.

Future model packages may populate a real value only when their supported source format has an authoritative field and the package adapter owns that interpretation.

## Expected implementation touchpoints

Core common contract:

- `src/bremen/model_runtime.py`
  - add `referring_physician` to `SourceMetadata` with a safe missing default;

- `src/bremen/api/standard_model_result.py`
  - add the common serialized field immediately after `patient_age`;

- `src/bremen/api/model_result_mapper.py`
  - map `RuntimePrediction.source_metadata.referring_physician` directly;
  - do not parse H5 here.

Package adapters:

- Aramina package source-metadata adapter may populate the field if a supported source field exists in the future;
- Bremen package source-metadata adapter may populate the field if a supported source field exists in the future;
- current inspected evidence supports the empty default only.

Tests/fixtures expected to change:

- Standard Result golden fixtures for Bremen;
- Standard Result golden fixtures for Aramina;
- mapper contract tests;
- metadata completion tests;
- live/smoke assertions that both reports contain the field;
- architecture test ensuring generic mapper/runtime contains no model-specific H5 physician paths or aliases.

## Acceptance criteria

For successful Bremen and Aramina reports:

```json
{
  "patient_id": "...",
  "patient_age": 47,
  "referring_physician": "",
  "scan_date_time": "...",
  "operator_id": "..."
}
```

The key must exist in both workflows.

Current H5 examples must return `""`.

No scientific values may change.

No model-specific H5 parsing may be added to generic platform code.
