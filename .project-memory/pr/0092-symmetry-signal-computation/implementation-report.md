# PR0092 Implementation Report — Real Symmetry Difference-Level Computation

## Reference Statistics Status

No reference-statistics artifact exists in the repository. The artifact
must be a small JSON file with aggregate percentile bounds per signal
family, computed from the training cohort. Expected location:
S3 alongside model catalog manifests.

## Phase 1 Fail-Closed Behavior

All 5 signals emit `difference_level: "not_available"` with
`schema_status: "unavailable"` until the reference-statistics artifact
is delivered. No defaults to `small`, no inference from score, no
hidden signals.

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/bremen/api/symmetry_signals.py` | CREATED | +520 lines |
| `src/bremen/api/decision_support.py` | MODIFIED | +25/-1 |
| `src/bremen/api/report_bremen.py` | MODIFIED | +6 |
| `src/bremen/api/feature_artifact_prediction.py` | MODIFIED | +5 |
| `tests/test_bremen_symmetry_signals.py` | CREATED | +395 lines |
| `docs/api_contract.md` | MODIFIED | +83 |

## Feature-to-Signal Mapping

Verified from `preprocessing_bridge.py` source analysis. 15 features
mapped to 5 signal families by computational logic:

1. `profile_difference_magnitude` — sigma_l1, sigma_l2, sigma_r1,
   sigma_r2, meanrms1, meanrms2 (6 features, 3 unique)
2. `weighted_profile_asymmetry` — weightedrms1, weightedrms2
3. `statistical_shape_deviation` — mahalanobis1, mahalanobis2
4. `distributional_divergence` — wasserstein_distance_full_q2,
   wasserstein_distance_muLR, cosine_distance_full_q2
5. `bilateral_profile_intensity` — peak14_intensity, mean_peak_value_raw

## Duplicate Feature Handling

sigma_l1==meanrms1 and sigma_l2==sigma_r2==meanrms2 are computational
duplicates. Both are mapped to `profile_difference_magnitude`. The
aggregation uses "most extreme level across features" — duplicates
produce the same level and do not inflate the result.

## Bucketing Behavior

`_percentile_bucket()`: Pure function, percentile-position against
reference bounds. Returns `not_available` for None bounds, non-numeric
values, or non-finite (NaN/Inf). Otherwise:
- value ≤ `bounds.small` → `"small"`
- value ≤ `bounds.moderate` → `"moderate"`
- value > `bounds.moderate` → `"larger"`

`_aggregate_signal_level()`: Most extreme (highest) level across
per-feature levels. Conservative and safety-preserving.

## Output Wiring

- `build_decision_support_report()` (decision_support.py): New optional
  params `feature_values` and `ref_stats`. Produces `symmetry_signals`
  external-safe dict.
- `BremenReportProvider._build_report()` (report_bremen.py): Reads
  `symmetry_signal_detail` from workflow_result if present, adds to
  `supporting_technical_evidence`.
- `feature_artifact_prediction.py`: Passes feature values to
  `build_decision_support_report()`.
- `inference_handler.py` and `app.py` call sites: Backward-compatible
  — call without feature_values/ref_stats, get `not_available`.

## Not_Available Behavior

- Reference stats None or not configured → all `not_available`
- Invalid artifact shape → all `not_available`, `schema_status: error`
- Signal missing from artifact → that signal `not_available`
- Non-finite feature value → `not_available` for that feature
- All 5 signals always present in output list

## Safety Confirmation

- No raw feature values in external or internal output
- No percentile cutoffs in external or internal output
- checksum_prefix truncated to ≤ 8 chars
- No full checksums, S3 paths, manifest keys, model internals
- No sample/mockup values as runtime data
- Decision vocabulary unchanged (CONTINUE_MRI, MRI_REVIEW_DEFER)
- POST /predictions schema unchanged
- No HTTP routes, HTML, CSS, or PDF rendering
- No new dependencies
- No inference/preprocessing semantics changed

## Tests Added

35 tests in `tests/test_bremen_symmetry_signals.py`:

| Class | Tests | Coverage |
|-------|-------|----------|
| TestComputeSymmetrySignals | 9 | Core computation logic |
| TestDecisionSupportSymmetry | 6 | Decision support integration |
| TestInternalReportSymmetry | 7 | Internal report integration |
| TestPercentileBucket | 6 | Bucketing logic |
| TestLoadReferenceStatistics | 5 | Loader boundary |
| TestNoRenderingLeak | 2 | No rendering/UI introduced |

## Validation

```
python -m compileall src tests — passed
python -m pytest -q tests/test_bremen_symmetry_signals.py -v — 35 passed
python -m pytest -q tests/test_bremen_decision_support_output.py -v — 38 passed
python -m pytest -q tests/test_bremen_preprocessing_bridge.py -v — 28 passed, 1 skipped
python -m pytest -q tests/test_catalog_api_multi_model.py -v — 20 passed
python -m pytest -q — 2054 passed, 11 skipped, 28 warnings
git diff --check — clean
```

## Safety Greps

- `difference_level` values: all string constants (small/moderate/larger/not_available)
- No runtime sample/mockup dependency
- No raw feature values, checksums, S3 paths in output paths
- No percentile cutoffs in external/internal output

## Warnings

- Phase 2 (real bucketing) requires the data science team to deliver
  a safe aggregate reference-statistics JSON artifact before `not_available`
  can transition to real difference levels.
- `inference_handler.py` and `app.py` call sites do not pass feature_values
  yet — they default to `not_available`. A follow-up can wire feature values
  through the workflow orchestrator result payload.

## Non-Goals Confirmed

No rendering, PDF, UI, frontend, new routes, POST /predictions schema
changes, fabricated thresholds, raw value exposure, percentile cutoffs
in output, Aramis data reuse, mockup values, inference/preprocessing
changes, catalog changes, dependency changes, model artifact changes.

## Next Required Action

Data science team (Slava): deliver the aggregate reference-statistics
JSON artifact so Phase 2 (real percentile-position bucketing) can proceed.
