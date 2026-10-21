# Production API baseline — 2026-09-11

This is actual evidence captured against `https://bremen.matur.co.uk/demo` before PR0157. It verifies the existing endpoint behavior that PR0157 is required to preserve. Because it predates PR0157, these responses do **not** contain `report.standard_result`.

## Catalog/auth

- `GET /demo/api/models`: HTTP 200 with valid Bearer auth.
- Available models observed: 5 total.
- Bremen and Aramina model entries were available.

## Bremen happy path

Job ID: `c738b3a2-820a-4e0d-97c9-536f62d7d319`

- Job overall status: `completed`.
- Workflow: `bremen`.
- Model: `bremen-mri-triage-logreg-v0-1`.
- Report endpoint returned an available Bremen report.
- Observed probability: `0.9999716577320301`.
- Observed threshold: `0.3640352477169748`.
- Observed recommendation: `CONTINUE_MRI`.
- Legacy report contained `payload.score_and_threshold.p_mri_needed` and `payload.score_and_threshold.threshold`.

This is a historical API compatibility baseline only. Do not use its measurement-count evidence as the current Bremen scientific input contract.

## Aramina happy path

Job ID: `3a98255e-b297-4808-b4af-fbc01abcbb00`

- Job overall status: `completed`.
- Workflow: `aramina`.
- Model version: `0.2.13-beta`.
- Patient fixture: `Nova_214`.
- Target side: `left`.
- Observed risk score: `0.869387073973647`.
- Legacy `payload.risk_score` present.
- Legacy `payload.technical_demo_only=true` present.
- Report links present.

## Aramina negative path

Job ID: `a5f636a1-c7fb-47d4-bec8-e43524131668`

Observed result:

- HTTP submit: 201 (job resource created).
- Job status: `failed`.
- Workflow status: `failed`.
- `failure=ARAMINA_UNSUPPORTED_INPUT`.
- `failure_stage=preprocessing_contract`.
- `failure_reason_code=ARAMINA_UNSUPPORTED_INPUT_PREPROCESSING_CONTRACT`.
- `preprocessing_release=v0.1.9-beta`.
- `preprocessing_transformer=H5PoniGeometryCalculatorTransformer`.
- `preprocessing_reason_code=ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED`.
- Response contained allowlisted diagnostics only; no raw S3/local path, traceback, token, or artifact internals were observed.

## Why this baseline is included

PR0157 intentionally keeps these endpoint contracts backward-compatible and adds the new canonical result only additively on successful report responses. The fresh post-deploy smoke should therefore show the same legacy fields plus `report.standard_result`.
