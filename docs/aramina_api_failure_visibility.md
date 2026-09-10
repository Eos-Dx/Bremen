# Aramina API failure visibility — PR0140

Research draft. These changes describe technical request failures, not clinical
validity. Scoring, preprocessing, artifacts, thresholds, provider construction,
frontend layout and synchronous execution remain unchanged.

## Request errors

Both FastAPI and the legacy POST handler expose the same Aramina diagnostics:

| Condition | HTTP | Error code | Additional fields |
| --- | --- | --- | --- |
| Missing or invalid Aramina fields | 400 | `ARAMINA_INVALID_REQUEST` | `missing_required_fields`, `required_fields`, `allowed_target_side`, `remediation`, `technical_demo_only` |
| Unknown, consumed, expired or invalidated catalog handle | 400 | `SOURCE_ERROR` | `reason_code=SOURCE_ID_NOT_AVAILABLE`, `remediation`, `technical_demo_only` |
| Requested patient differs from known H5 patient metadata | 400 | `ARAMINA_PATIENT_MISMATCH` | sanitized requested/resolved identifiers, `remediation`, `technical_demo_only` |

`missing_required_fields` contains absent, null or blank patient/side fields.
An invalid nonempty value is not reported as missing. Values from schema
validation errors and raw exceptions are not echoed in Aramina responses.
The `required_fields` list describes the catalog submission; existing upload
and legacy source alternatives remain accepted. Catalog routing takes precedence
over the supplied workflow ID.

Source handles live in process memory, expire after one hour, and are consumed
on resolution. Fetch `/demo/api/h5/containers` before a new submission. A
download/configuration failure is not mislabeled as an unavailable handle.
The typed source exception remains a `ValueError` with the existing message,
preserving Bremen responses.

The patient check uses the existing fault-tolerant H5 metadata extractor after
source resolution and before job creation. It does not trust `container_id`
or infer patient identity from a filename. Unknown metadata is not a mismatch;
the runtime still validates the input. A mismatch consumes the resolved handle,
so retry with a freshly listed handle. Sample identifiers containing paths or
free-form text are redacted from the new diagnostic fields.

## Failed jobs

For Aramina `ARAMINA_UNSUPPORTED_INPUT`, the serialized workflow run adds
`failure_stage=input_contract`, a fixed `failure_detail`, and `safe_details`
containing the available patient display identifier, requested side and model
version. The fields are present in POST and subsequent job detail responses.
The failure code and unavailable report status remain unchanged. Report schemas
are unchanged; these details live on the workflow run.

`input_contract` is a public category, not the exact failing preprocessing
function. Exact internal stages still come from private sanitized diagnostics.
This PR does not establish why Nova_384 failed. Successful runs and Bremen runs
do not acquire these extra fields.

## Evidence and validation scope

User-provided production results show 0.2.12-beta / Nova_214 left completing with
a fresh handle and an available report; earlier results show 0.2.13-beta /
Nova_227 right completing. These observations do not validate every input.

Regression tests cover both transports, pre-job rejection, real source-registry
unavailable states, H5 metadata mismatch, synthetic artifact execution with both
version identities, failed-job serialization, private-data exclusion, and
unchanged Bremen source-error responses. Synthetic artifact tests do not replace
real model/H5 integration or clinical validation.
