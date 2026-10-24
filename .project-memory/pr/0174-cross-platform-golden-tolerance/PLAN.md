# PLAN — PR0174 cross-platform golden probability tolerance

## Objective

Make the IR-04 golden smoke gate portable across the supported production
platforms (macOS arm64 developer/evidence hosts and Linux amd64 production
releases) without weakening any discrete or contract-level check.

## Problem

Five production Model Releases rebuilt on Linux/amd64 (CPython 3.13.17, ABI
`cpython-313-x86_64-linux-gnu`) pass every compatibility check but fail
`ReleaseCache.install()` during golden smoke because
`_verify_golden_case` compares probability fields with exact Python equality.

Observed cross-platform behaviour:

| Variant | Golden (macOS/Darwin) | Linux/amd64 | Abs diff |
|---|---|---|---|
| A1 | `0.8693870739736473` | `0.869387073973647` | `3.33e-16` |
| A2 | `0.8693870739736473` | `0.869387073973647` | `3.33e-16` |
| B1 | `0.8524639494195422` | `0.8524639494195415` | `6.66e-16` |
| B2 | `0.7726940329943811` | `0.7726940329943845` | `3.44e-15` |
| B3 | `0.6848549443589647` | `0.6848549443589693` | `4.66e-15` |

Thresholds, predictions, target classes, statuses and typed errors are
identical on both platforms.

## Decision

- Only the continuous probability fields (`probability`, `risk_probability`)
  use a narrow **absolute** tolerance.
- Maximum observed drift across the five releases: **4.66e-15**, i.e. below
  `1e-13`, so per the task's rule the tolerance is
  `GOLDEN_PROBABILITY_ABS_TOLERANCE = 1e-12`.
- `threshold_applied`, `decision_threshold`, `prediction`,
  `target_class_risk_level`, `status`, `error.code` and `safe_reason` remain
  exact.
- Booleans, non-numeric values, NaN and infinity never match.

## Scope

Changed:

- `src/bremen/platform/models/release_cache.py` — golden comparison only.
- `tests/test_ir04_release_cache.py` — focused tolerance tests.

Not changed: model artifacts, thresholds, feature formulas/order,
preprocessing, scientific configuration, Worker protocol, `runtime_release`
schema, release manifests, dependencies, AWS configuration.

## Verification

- Focused unit tests (exact match, observed Darwin/Linux pair, within/above
  tolerance, NaN/Inf, non-numeric, threshold drift, prediction/class mismatch,
  error-code/safe-reason mismatch).
- Five Linux production releases installed through the real offline
  `ReleaseCache` path (no rebuild, no manifest edits) until READY.
- macOS B2 reinstall to confirm no regression on the host that produced the
  frozen values.
- Full repository suite, `git diff --check`.
