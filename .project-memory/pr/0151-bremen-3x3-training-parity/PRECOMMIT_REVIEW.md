# PR0151 Pre-Commit Review — Bremen 3×3 Training Parity

## Branch
`0151-bremen-3x3-training-parity`

## HEAD
`3409357146f1023af488dc31d1e8884da4fbb0cc` (unchanged; no commit created)

## PLAN reviewed
`.project-memory/pr/0151-bremen-3x3-training-parity/PLAN.md` — read in full.
Scope: documentation + test-only fixtures/reference; no production changes, no
MLflow, no retraining, no replacement artifacts, no public API additions, no commit.

## Changed files
All changes are untracked additions; `git diff --name-status` and `git diff --stat`
are empty (no tracked modifications). `git status --porcelain --untracked-files=all`:

```
?? .project-memory/pr/0151-bremen-3x3-training-parity/PLAN.md
?? docs/bremen_3x3_training_parity.md
?? tests/fixtures/bremen_3x3/golden.json
?? tests/fixtures/bremen_3x3/intermediates.json
?? tests/fixtures/bremen_3x3/model.json
?? tests/fixtures/bremen_3x3/provenance.json
?? tests/reference_0151/__init__.py
?? tests/reference_0151/features.py
?? tests/reference_0151/prediction.py
?? tests/reference_0151/reference_features.py
?? tests/test_bremen_3x3_training_parity.py
```

Every changed file was read completely. No binary/model artifact, no `.joblib`,
`.h5`, `.zip`, `.pkl`, `.pt`, `.onnx`, or `.bin` file was added. No `__pycache__`
appears in git status. No production file under `src/bremen/` was modified.

## Training provenance
Authoritative source: sibling checkout `/Users/alexred/Projects/Python/bremen-training-pipeline`
at commit `c98a950d3fbf0db72d87f2ecd977d80fe35da9e4` (verified via `git rev-parse HEAD`).
Its only worktree change is `D outputs/.gitkeep` (pre-existing, unrelated).

Independently recomputed SHA256 of the six recorded source files and compared to
`tests/fixtures/bremen_3x3/provenance.json` — **all six match exactly**:

| File | SHA256 (recorded == observed) |
| --- | --- |
| `src/bremen/reference_features.py` | `707cbf33…d567a84` |
| `src/bremen/features.py` | `21097008…8a55a8f` |
| `src/bremen/prediction.py` | `ca764f7c…f6a5351` |
| `src/bremen/paper_reference.py` | `d4da6b08…cc781f4` |
| `src/bremen/training.py` | `5743e245…d7578d6` |
| `config/preprocessing/bremen_paper_reference_all_n256_v0_2.yaml` | `ef6f624b…724a8be` |

Model artifact: `outputs/paper_reference/training/bremen_paper_reference_symmetry_logreg_0_2_0-paper-reference_20260802T173549Z_6c8b029f/model.joblib`
SHA256 `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` — matches
`provenance.json`, `model.json`, and that run's `manifest.json` (`model_checksum`).
The `manifest.json` `threshold_value` `0.3585907282566089` matches `model.json`.

The `bremen-training-pipeline-main` ZIP was not attached; the PLAN and docs record
this honestly and use the available checkout. No archive is copied into Bremen.

## Authoritative 3×3 algorithm summary
Verified by extracting each function from the authoritative source and comparing
byte-for-byte against `tests/reference_0151/reference_features.py`. **All 20
functions are IDENTICAL** (no formula inferred from feature names):

`parse_q_grid`, `apply_roi`, `safe_savgol`, `minimum_reference_value`,
`normalize_by_minimum`, `build_common_grid`, `resample_to_common`, `side_label`,
`patient_lr_mean_metrics`, `mask_q`, `mean_rms_band`, `weighted_rms_band`,
`mahalanobis_band`, `sigma_rms_band`, `peak14_intensity_from_means`,
`local_peak_in_window`, `patient_mean_raw_peak14`, `cosine_distance`,
`wasserstein_distance`, `prepare_one_to_one_dataframe`.

`tests/reference_0151/features.py` (`build_feature_frame`, `analysis_config`,
`accepted_features`) and `tests/reference_0151/prediction.py`
(`predict_proba_portable`) are verbatim copies of the source orchestrator and
portable scorer with reduced imports only.

Confirmed from source:
- q ROI/filtering: inclusive `[qmin,qmax]`, `<5` points raises.
- smoothing: Savitzky–Golay window 11, poly 3, SciPy default `interp` edge mode.
- normalization: divide by abs p05 reference in `[6.45,6.95]`, floored at `1e-3`;
  narrow ROI `[7.5,23]` excludes the window → **no-op** (verified in test).
- q-grid: overlap endpoints, smallest median positive step, `clip(round(...)+1,50,5000)`.
- resampling: `np.interp` with NaN outside bounds; all-row-finite column filter.
- LEFT/RIGHT grouping: case-insensitive `L/LEFT`, `R/RIGHT`; unknown sides skipped.
- per-side aggregation: arithmetic mean per q.
- **replicate std: `np.std(..., ddof=1)` — sample std, confirmed at source lines 283–284.**
- peak extraction: `peak14_intensity` = max of averaged mean over `[13.5,14.5]`;
  `mean_peak_value_raw` = mean of per-original-profile maxima over `[13,14.8]`
  (before cropping/smoothing/normalization/interpolation/aggregation).
- 15-feature generation, order, imputation, scaling, logistic regression,
  probability, threshold: all match source and `model.json`.

## Golden fixture summary
`tests/fixtures/bremen_3x3/golden.json`:
- `fixture_id`: `synthetic-0151` (opaque; no patient identifiers).
- `boundary`: `"integrated radial profiles; not raw detector H5"` (honest boundary).
- 6 measurements: 3 LEFT (q lengths 256/257/258) + 3 RIGHT (259/260/261), each with
  explicit `q` and `intensity` arrays — sufficient to reproduce independently.
- `feature_names`: the frozen 15-column order.
- `expected_features`: 15 numeric values.
- `expected_probability`: `0.7388733541967353`.
- `absolute_tolerance`: `1e-10`.

`intermediates.json` freezes both grids (narrow 189 pts, wide 256 pts), means and
stds, and six perturbation feature vectors with explicit `changed_features`.
`model.json` freezes the fitted portable parameters (imputer/scaler/coef/intercept,
classes `[0,1]`, threshold). `provenance.json` records source/model hashes and
library versions.

No patient-identifying, private filesystem, or storage information present
(grep for `alexred`, `/Users/`, `Nova_`, `patient`, `specimen`, `diagnosis`,
`CANCER`, `BENIGN`, `s3://`, `gs://`, `arn:aws` found only the provenance
"no patient data" note).

## 15-feature parity result
Independently reproduced by executing the **authoritative source** (`bremen.features.build_feature_frame`)
on the fixture profiles, not the copied reference:
- `errors.empty == True`
- max abs feature diff vs `expected_features` = **0.0**
- `np.allclose(..., atol=1e-10, rtol=0) == True`

## Probability parity result
Authoritative `bremen.prediction.predict_proba_portable` on the golden features:
- probability = `0.7388733541967353`, diff = **0.0**, matches at `1e-10`.
- `model.json` portable parameters match the artifact's `portable_logreg` exactly
  (imputer/scaler/coef/intercept, classes); `feature_columns` and `threshold` are
  faithful consolidations of the artifact's `feature_schema.feature_columns` and
  `decision.threshold` (both verified equal).

## Permutation tests
`test_side_permutation_invariance` parametrizes all 6 permutations of each side
(12 cases). Independently confirmed: max LEFT-permutation feature diff = `1.07e-14`
(within `1e-10`). Order behavior matches the training implementation (order-independent
up to floating-point reduction roundoff); bitwise equality is not claimed.

## All-six participation tests
`test_every_replicate_participates` mutates each of the 6 replicates and asserts the
exact `changed_features` list plus side-specific sigma participation. Independently
confirmed:
- Changing only L2 changes 13 features including `sigma_l1` (not `sigma_r1`).
- Changing only R2 changes 13 features including `sigma_r1` (not `sigma_l1`).
- A simulated first-pair-only implementation differs from golden by `1.06e6` and
  **would fail** the golden test — regression to first-pair-only is impossible to
  pass silently.

## q-grid test result
`test_nonidentical_grids_and_intermediate_arrays` (narrow + wide) and
`test_common_grid_intersection_finest_step_and_out_of_range` cover non-identical
grids, finest-median-step selection, interpolation, out-of-range NaNs, grid bounds
(50/5000 clip), and no-overlap error. Independently reproduced both grids' means
and stds from the authoritative source with max diff `0.0`.

## Peak-feature test result
`test_peak_is_mean_of_original_maxima` and
`test_roi_precedes_normalization_and_raw_peaks_precede_aggregation` prove
`mean_peak_value_raw` is the mean of per-original-profile maxima (not a peak of an
averaged profile) and that raw peaks precede aggregation. Independently reproduced
all six mutation vectors from the authoritative source with max diff `0.0`.

## Targeted pytest results
- `pytest -q tests/test_bremen_3x3_training_parity.py` → **31 passed, 1 xfailed**.
- `pytest -q tests/test_bremen_workflow_bremen.py` → **36 passed**.
- Combined → **67 passed, 1 xfailed** (matches PLAN).
- The xfail is `strict=True` and names the PR0152 platform-scaler discrepancy; it
  is not hidden by loosening tolerance.

## Full pytest result
`pytest -q` → **4058 passed, 11 skipped, 1 xfailed, 1635 warnings in 39.49s** (exit 0).
Matches the PLAN's recorded result.

## git diff --check result
`git diff --check` → exit 0. Untracked added files also checked for trailing
whitespace → none found.

## Scope/compatibility assessment
- No tracked modifications; `git status --short -- src/` is empty.
- No production behavior change in `workflow_bremen.py`, `report_bremen.py`, job API
  handlers, model artifacts, thresholds, preprocessing runtime, Aramina runtime, or
  frontend.
- No production import of `tests/reference_0151` or `bremen_3x3` fixtures.
- No `first_pair_legacy` public contract, no invented aggregation, no new API/report
  fields, no new thresholds, no retraining, no MLflow, no Aramina changes.
- `compileall -q src tests` → exit 0. Ruff on added Python files → all checks passed.
- The 3+3=6 contract is documented and frozen as a product requirement; the shape
  test expresses it without modifying upstream/runtime validation (5 = invalid).

## Risks / non-gating notes
- The fixture boundary is integrated profiles, not raw detector H5; raw H5→profile
  parity is explicitly deferred to PR0152. This is documented, not hidden.
- The current runtime is training-serving skew: `workflow_bremen.py` consumes
  `left_ms[0]`/`right_ms[0]` (first-pair), and `inference.py` adds `1e-10` to every
  scale. Independently reproduced platform probability `0.7388733540826478`, diff
  `-1.1408751721120325e-10` vs golden. The docs identify this skew explicitly and
  defer the fix to PR0152; PR0151 does not fix it (correctly out of scope).
- The docs do not use the literal phrase "training-serving skew", but the runtime
  table's `Match? No` column and the explicit probability discrepancy make the skew
  unambiguous. Non-gating.
- `analysis_config()` in the test reference sets `excluded_patients=()` vs the
  source default `("Nova_255",)`; immaterial for the synthetic fixture. Non-gating.
- `model.json` adds `feature_columns`/`threshold` keys not present in the artifact's
  `portable_logreg`; both are verified equal to the artifact's `feature_schema` and
  `decision` values. Non-gating.
- Repository-wide Ruff has 405 pre-existing findings outside the added files; no
  unrelated lint fixes were made. Non-gating.

## Final verdict
**READY FOR COMMIT**

All required conditions hold: authoritative training provenance established (source
and model hashes verified), golden 3+3 contract reproducible (features and
probability reproduce at `1e-10` from the authoritative source), 15-feature parity
passes, probability parity passes, all-six participation demonstrated, order
behavior matches training, no production inference changes, full pytest passes,
`git diff --check` clean, and scope is clean.
