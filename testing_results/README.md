# Bremen Platform API smoke pack — Standard Model Result Contract v1

Purpose: verify that the existing Bremen Platform endpoints still work after PR0157 and that successful Bremen/Aramina reports expose the additive `report.standard_result` contract without breaking legacy fields.

## Prerequisites

- macOS/Linux shell
- `curl`
- `jq`
- valid Bearer token exported as `ACCESS`
- production/demo base URL, default: `https://bremen.matur.co.uk/demo`

The scripts intentionally do not use `set -euo pipefail`.

## Recommended order

1. `scripts/00_auth_catalog_smoke.sh`
2. `scripts/01_existing_job_contract_smoke.sh` if you already have one successful Bremen job and one successful Aramina job
3. `scripts/02_end_to_end_submit_smoke.sh` when you have known-good source IDs/containers
4. `scripts/03_aramina_negative_smoke.sh` only when you want to verify the allowlisted failure contract

All scripts write evidence under `${OUT:-/tmp/bremen-api-smoke-0157}`.

## Core acceptance criteria

- Existing `/demo/api/...` endpoint paths are unchanged.
- Authentication still protects the API.
- Successful Bremen and Aramina report responses contain `report.standard_result`.
- `standard_result` contains exactly the 18 Standard Model Result Contract v1 fields.
- `risk_probability` and `threshold_value` are numeric and model-owned.
- `target_class_risk_level` is exactly `high` or `low`.
- `model_metrics.sensitivity` and `.specificity` may be `null` until provenance-verified release metrics are supplied.
- Bremen `specific_output` is `{}`.
- Aramina `specific_output` contains `target_side` and `mammography_suspicious_field`.
- Legacy report fields remain available.
- Failed Aramina jobs do not gain a fake `standard_result` and expose only allowlisted safe diagnostics.

## Evidence included

- `results/PR0157_REVIEW_RESULTS.md` — actual pre-commit validation results from PR0157.
- `results/PRODUCTION_BASELINE_2026-09-11.md` — actual production API baseline captured before PR0157. This is intentionally labelled as pre-PR0157 and therefore does not contain `report.standard_result`.
- `results/evidence/*.json` — corresponding pre-PR0157 response evidence.

A fresh post-deploy production run is still required before calling the new `standard_result` contract production-smoke verified.
