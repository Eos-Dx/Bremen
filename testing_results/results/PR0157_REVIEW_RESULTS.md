# PR0157 verified results

These are actual results reported by the independent pre-commit review of `0157-standard-model-result-contract-v1`. They are code/test validation results, not a post-deploy production smoke.

## Result

**VERDICT: READY FOR COMMIT**

## Standard Model Result Contract

- Production schema + mapper implemented.
- One mapping boundary, wired at the existing `get_job_report` integration point.
- Both public report routes are covered through the same integration point.
- Successful reports expose additive `report.standard_result`.
- Failed/default envelopes remain unchanged.
- Exact common contract: 18 top-level standard-result fields.
- Canonical risk level vocabulary: `high` / `low`.
- `model_metrics.sensitivity` and `model_metrics.specificity` are currently `null` because no provenance-verified release metrics exist in the repository.

## API compatibility

- Route inventory baseline: 29 routes.
- Route inventory after PR0157: 29 routes.
- Route sets: identical.
- Auth behavior: unchanged.
- Existing requests: compatible.
- Existing responses: additive-only for valid reports.
- Existing legacy report fields preserved.

## Scientific/result parity

- Bremen golden probability through the mapping integration: `0.7388733541967353` exactly.
- Aramina mapping fixture probability: `0.265` passed through verbatim.
- `threshold_value` remains model-owned; no new API threshold literal.
- `target_class_risk_level` behavior checked below/equal/above threshold.
- Mapper contains no numpy/scipy/pandas or scientific formulas.

## Test results

- New Standard Model Result suite: **36 passed**.
- Bremen/model-package parity and conformance run: **530 passed**.
- Requirements/jobs/registry/discovery: **250 passed, 1 skipped**.
- Report/decision/API-freeze suites: **110 passed**.
- PR0143 guards: **15 passed**.
- Full pytest: **4285 passed, 11 skipped, 0 xfailed**.
- Collection count: **4259 → 4296 = +37, 0 removed**.
- Compileall: exit 0.
- `git diff --check`: exit 0.
- Changed-file Ruff: no new findings; reported findings were pre-existing at HEAD.

## Security

Review found no paths, S3 credentials, tokens, tracebacks, coefficients, scaler internals, or private artifacts in Standard Model Result output. Test fixtures were synthetic.

## Production verification status

A fresh production smoke after deployment is still required to verify the new `report.standard_result` field on the deployed API.
