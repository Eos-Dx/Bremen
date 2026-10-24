# IMPLEMENTATION_REPORT.md — PR0174 cross-platform golden probability tolerance

Status: implementation complete; five Linux production releases now install to
READY. No AWS access was used.

## TASK COMPLETE

Golden smoke previously compared all six result fields with exact equality.
Continuous probability output differs across BLAS/LAPACK platforms at the
1e-15 level, so the five Linux/amd64 releases failed READY admission even
though every discrete result matched.

The gate now uses a narrow **absolute** tolerance for the two probability
fields only. Everything else is unchanged and exact.

## SOURCE CHANGES

`src/bremen/platform/models/release_cache.py`

- New module constant `GOLDEN_PROBABILITY_ABS_TOLERANCE = 1e-12` (exported).
- New private helper `_golden_probability_matches(actual, expected)`:
  rejects `bool`, non-numeric values, NaN and ±infinity; otherwise
  `abs(actual - expected) <= 1e-12`.
- `_verify_golden_case` now:
  - `threshold_applied`, `decision_threshold`, `prediction`,
    `target_class_risk_level` → **exact** equality (unchanged);
  - `probability`, `risk_probability` → tolerant comparison;
  - `status`, `error.code`, `safe_reason` → exact (unchanged).

No other module changed. Worker output, model code, scientific expected
values, release manifests and the `bremen.inference-release.v1` /
`bremen.worker.v1` contracts are untouched.

`tests/test_ir04_release_cache.py`

- New `TestGoldenProbabilityTolerance` (17 collected cases) plus
  `test_golden_tolerance_is_narrow_and_documented`.
- IR-04 file: 65 → **83** passing tests.

## OBSERVED MAX PROBABILITY DRIFT

Measured against the frozen golden values in the already-built Linux releases
(no rebuild, no manifest edits), by running the real installed releases:

| Variant | Golden (Darwin) | Linux amd64 actual | Abs diff |
|---|---|---|---|
| A1 | `0.8693870739736473` | `0.869387073973647` | `3.3306690738754696e-16` |
| A2 | `0.8693870739736473` | `0.869387073973647` | `3.3306690738754696e-16` |
| B1 | `0.8524639494195422` | `0.8524639494195415` | `6.661338147750939e-16` |
| B2 | `0.7726940329943811` | `0.7726940329943845` | `3.4416913763379853e-15` |
| B3 | `0.6848549443589647` | `0.6848549443589693` | `4.6629367034256575e-15` |

**Maximum observed drift: `4.6629367034256575e-15`** (B3), i.e. below
`1e-13`. The task rule therefore selects `1e-12`; no larger tolerance was
needed or used.

## TOLERANCE POLICY

- Absolute only: `abs(actual - expected) <= 1e-12`.
- Probability fields only: `probability`, `risk_probability`.
- Rejected: `bool`, `str`, `None`, lists, NaN, ±infinity, non-finite.
- Exact (no tolerance): thresholds, prediction/class, status, error code,
  safe reason, and every other manifest/identity check.
- The comparison does not fall back to relative tolerance.

## FOCUSED TESTS

`tests/test_ir04_release_cache.py::TestGoldenProbabilityTolerance`

1. exact probability still passes
2. observed Darwin/Linux B2 pair passes (`0.7726940329943811` vs
   `0.7726940329943845`)
3. difference within `1e-12` passes (`+5e-13`)
4. difference above `1e-12` fails (`+2e-12`)
5. NaN fails (also +inf/−inf)
6. infinity fails
7. non-numeric probability fails (`"0.77"`, `None`, `True`, `[0.77]`)
8. tiny threshold drift (`+1e-15`) still fails
9. prediction mismatch still fails
10. target_class_risk_level mismatch still fails
11. error code mismatch still fails
12. safe_reason mismatch still fails
13. Linux `risk_probability` drift (A1/A2) passes
14. tolerance constant is exactly `1e-12`

## LINUX FIVE-RELEASE VALIDATION

Releases (built under PR0173, **not rebuilt, manifests unmodified**):

```
~/ir07-linux-amd64-work/releases/{a1,a2,b1,b2,b3}
```

Execution environment: native x86_64 Linux userland
(`python:3.13-slim`, `platform.machine() == "x86_64"`,
`CPython 3.13.17`) running on the local container runtime. No AWS service was
contacted; S3 was replaced by a deterministic reader over the release
directories, exactly as in earlier IR-04/IR-05 evidence.

Path exercised: `ReleaseCache.resolve()` → `ReleaseCache.install()`
(release-local wheelhouses, hash-locked offline pip) → mandatory golden smoke
→ READY.

See `FIVE_RELEASE_READY.md` for per-release digests, timings and outputs.

## VALIDATION RESULTS

Host: macOS 26.5.1 arm64, `/tmp/bremen-ir01-exec-venv` (Python 3.13.12).

| Command | Result |
|---|---|
| `python3 -m compileall -q src tests packages/xrd-inference-features/src` | exit 0 |
| `pytest -q tests/test_ir04_release_cache.py` | **83 passed** (was 65) |
| `pytest -q tests/test_ir05_subprocess_runtime.py tests/test_ir06_release_cutover.py tests/test_ir07_feature_library_parity.py tests/test_ir07_target_catalog_pointers.py` | **92 passed** |
| `pytest -q tests/test_s3_model_discovery.py tests/test_model_registry.py tests/test_inference_release_contract.py tests/test_worker_protocol_contract.py` | **487 passed** |
| `pytest -q` | **4550 passed, 19 skipped, 40 warnings** |
| `git diff --check` | exit 0 |
| `git status --short` | only `release_cache.py`, `test_ir04_release_cache.py` (+ pre-existing untracked `.claude/`) |
| `git diff --stat` | 2 files, +234 / −1 |

macOS regression check: B2 installed from `/tmp/ir05/releases/b2` into a fresh
cache through the real offline path → **READY** (`d6df5c67…2321`, 88.1 s),
proving the exact-match Darwin path still passes.

## SCIENTIFIC CONTRACT

No change to model artifacts, thresholds, feature formulas, feature order,
preprocessing, scientific configuration, Worker protocol, `runtime_release`
schema or release manifests. The change affects only release-admission golden
comparison.

## WARNINGS

- The five-release Linux validation ran under x86_64 emulation on the local
  container runtime (no native Linux/amd64 host or AWS access available). The
  emulated run reproduced the same x86_64 probability values recorded in the
  native Linux evidence (`0.7726940329943845` for B2), which supports the
  measurement; it is still emulation, not a native Linux host.
- The releases were not rebuilt; their manifest hashes are unchanged from
  PR0173 and are recorded as read.
- Golden numeric tolerance applies to probability only. A future variant whose
  probability drift exceeds `1e-12` must stop and be investigated rather than
  widening this constant.

## REMAINING BLOCKERS

None for this change.

## NEXT REQUIRED ACTION

Precommit review.
