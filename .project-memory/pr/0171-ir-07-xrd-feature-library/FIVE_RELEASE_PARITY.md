# IR-07 five-release parity evidence

Real chain exercised for all five rebuilt releases, using only the IR-07
release directories at `/tmp/ir07/releases/{a1,a2,b1,b2,b3}` (see
`WHEEL_EVIDENCE.md` for their manifest hashes):

```
release manifest
-> ReleaseCache.install()  (real pip/venv, local-file-backed S3 stub only)
-> release-owned venv
-> feature wheel installed (xrd_inference_features)
-> plugin wheel installed
-> Worker subprocess (bremen.ml_plugin.entrypoint)
-> _smoke_golden: every golden case, full expected-result comparison
-> READY
```

No release result was accepted by directly importing
`xrd_inference_features` from the repository; every value below is produced
by `ReleaseCache._smoke_golden` running the release's own installed Worker
subprocess against its own golden fixtures, with
`BREMEN_FEATURE_LIBRARY_BACKEND=xrd_inference_features` set inside that
Worker process by `ml_plugin.release.apply_feature_library_backend` (because
each manifest declares a `feature_library` block).

`ReleaseCache.install()` raises `ReleaseCacheError("smoke_failed", ...)` on
any status/field mismatch for any golden case and the release is never
written as READY — so every row below reaching READY is a hard pass across
*all* of that release's golden cases, not a partial check.

## Result

| Variant | status | golden cases (from manifest) |
|---|---|---|
| A1 | READY | nova214-left (ok), nova376-left (QC_FAILED/preprocessing_contract) |
| A2 | READY | nova214-left (ok), nova376-left (QC_FAILED/preprocessing_contract) |
| B1 | READY | benign (ok), Nova_376 (ok), cancer-qc (QC_FAILED/raw_peak_gate_failed) |
| B2 | READY | benign (ok), cancer-qc (QC_FAILED/raw_peak_gate_failed) |
| B3 | READY | benign (ok), atypical-shape (INPUT_INVALID/requires_exactly_3_left_3_right) |

## B2 hard gate (explicitly required)

B2's `b2-benign` golden case declares, and `_smoke_golden` confirmed exact
match for:

```
probability:       0.7726940329943811
threshold_applied: 0.3585907282566089
prediction:        1
```

This is the same value frozen since PR0160/IR-01 — reproduced here through
the external `xrd_inference_features` backend end-to-end via the real
Worker subprocess, not approximated and not skipped.

## Scope note

This is local evidence (temporary `ReleaseCache` roots under `/tmp`, a
local-file-backed S3 stub standing in for real S3 `get_object`, real
`pip`/`venv`). It is not App Runner/live-deployment evidence — consistent
with IR-07's non-goals (no AWS, no App Runner, no activation). The stub
only replaces the S3 transport; manifest validation, checksum verification,
wheel-closure verification, venv creation, and the Worker subprocess
execution are all real, unmocked code paths.
