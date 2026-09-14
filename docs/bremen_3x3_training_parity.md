# Bremen 3×3 training parity — PR0151 research investigation

**AUTHORITATIVE BREMEN 3x3 TRAINING CONTRACT CONFIRMED** at the integrated-profile
boundary for the source/model identified below. This verdict does **not** mean
current platform inference has parity: its features differ, and even with frozen
features its probability fails the requested tolerance. No production behavior
was changed. Research decision support requiring radiologist review; no clinical
validation or release claim is established here.

## Source and evidence boundary

The available authoritative source is the sibling `bremen-training-pipeline`
checkout at commit `c98a950d3fbf0db72d87f2ecd977d80fe35da9e4` (local path recorded
in PLAN.md). No `bremen-training-pipeline-main` ZIP was attached or used, so no
archive hash or assertion of archive equality is possible. The checkout has no
modified source files; its only pre-existing difference was deleted outputs/.gitkeep.

`tests/fixtures/bremen_3x3/provenance.json` records SHA256s of the exact source
files, preprocessing config, numerical-library versions, and model. The model is
`bremen_paper_reference_symmetry_logreg`, `0.2.0-paper-reference`, from run
`bremen_paper_reference_symmetry_logreg_0_2_0-paper-reference_20260802T173549Z_6c8b029f`.
Its SHA256 is
`65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0`, matching that
run's `manifest.json` (`bremen-paper-reference-v0-2-0`). The fixture freezes its
existing fitted portable parameters, not a replacement model. Live deployment
identity was not queried: PR0152 must verify its loaded checksum against this
artifact before activation.

Source anchors (paths relative to the training repository):

| Concern | Exact source |
| --- | --- |
| Input loading / preprocessing dispatch | `src/bremen/preprocessing.py:BremenPreprocessingPipeline.transform` |
| Raw H5 / integration configuration | `config/preprocessing/bremen_paper_reference_all_n256_v0_2.yaml:pipeline.steps` |
| Feature settings, grouping orchestration, raw peak gate | `src/bremen/features.py:analysis_config`, `build_feature_frame`, `accepted_features` |
| q decoding, ROI, smoothing, normalization | `src/bremen/reference_features.py:parse_q_grid`, `apply_roi`, `safe_savgol`, `minimum_reference_value`, `normalize_by_minimum` |
| Common grid, interpolation, mean and variance | `reference_features.py:build_common_grid`, `resample_to_common`, `patient_lr_mean_metrics` |
| Bands / peaks / distances | `reference_features.py:weighted_rms_band`, `mahalanobis_band`, `sigma_rms_band`, `mean_rms_band`, `peak14_intensity_from_means`, `patient_mean_raw_peak14`, `wasserstein_distance`, `cosine_distance` |
| Fitted estimator and probability | `src/bremen/paper_reference.py:_make_estimator`, `run_paper_reference_training_from_config`; `src/bremen/prediction.py:predict_proba_portable` |
| Exact tolerance | `config/training/bremen_paper_reference_train_v0_2.yaml:paper_contract.numeric_tolerance`; `tests/test_paper_reference_parity.py` |

## Preprocessing from H5

The authoritative paper route has seven steps: H5ToDataFrameTransformer (GFRM
payload preference, SAMPLE sessions/sets, do not drop missing sample thickness),
ProductColumnBuilder, K-alpha PONI coverage filter (`>=23 nm^-1`), position filter
(P1/P2/P3/P1_R/P2_R/P3_R), AzimuthalIntegration, SNR audit, KeepColumnsTransformer.
The delegated implementation is `xrd_preprocessing/transformers/h5.py:
H5ToDataFrameTransformer.transform` → `xrd_preprocessing/h5.py:h5_to_df`, and
`xrd_preprocessing/azimuthal.py:AzimuthalIntegration` (PONI integration helpers).
The source config pins upstream commit
`45d5568248e9774b7938a36e028d80e72b130b19`, release `v0.1.7-beta`.

Each measurement uses native PONI geometry, 256 radial points, Poisson errors,
and thickness adjustment when sample thickness exists, using calibrant thickness
as reference. Missing sample thickness is retained with adjustment metadata.
Native q arrays are retained; the configuration's 2–23 range is not passed as a
radial-range argument to this integration step. SNR uses Poisson and is audit
only. There is no faulty-pixel filter, SNR rejection, QRangeValueNormalizer,
diagnosis filter, or per-profile q14 gate in this historical route. This differs
from the repository's general product pipeline; PR0151 documents the difference
without silently replacing either route.

The golden fixture starts **after integration**, with q and intensity arrays.
It does not claim raw detector/H5/PONI numerical parity. PR0152 must preserve or
separately validate this upstream boundary before end-to-end activation.

## Exact six-profile computation

Valid product input is **exactly 3 LEFT + 3 RIGHT**, six total; five is incomplete
and invalid. The scientific source itself is more permissive (at least one per
side), so count enforcement is a separate PR0152 product requirement. This PR's
shape test expresses that requirement without modifying upstream/runtime behavior.

For a patient's rows, side aliases L/LEFT and R/RIGHT are case-insensitive after
stripping. Unknown sides are skipped in side metrics, but raw peak extraction
iterates all patient rows. Product validation must prevent unknown/extra rows.
No side swapping or replicate selection is performed.

Run the following **twice**, with inclusive ROIs [7.5,23] and [2,23]:

1. Decode each q array. ndarray means explicit q coordinates; a two-scalar
   list/tuple or string `min-max` / `min:max` means linspace across profile length.
   Longer lists are explicit coordinates. Length mismatches raise.
2. Crop each original profile to ROI (fewer than five points raises).
3. Smooth each cropped profile with Savitzky–Golay window 11, polynomial 3,
   SciPy default edge mode `interp`. The helper makes even windows odd, caps
   to available odd length, reduces polynomial to window−2, and bypasses
   smoothing for fewer than five points or window below five.
4. Divide by the absolute fifth-percentile reference in [6.45,6.95], floored at
   0.001, only when at least three samples and a finite reference exist.
   **The narrow ROI excludes this entire window: normalization is a no-op.**
   Wide-pass normalization uses the smoothed cropped profile. It is not the
   product median normalization on [6.7,7.1].
5. Compute overlap endpoints as max of all six minima and min of all six maxima.
   Select the smallest median positive finite step of the six sorted q arrays.
   Grid length is `clip(round((qmax-qmin)/max(step,1e-12))+1,50,5000)`;
   construct an inclusive linspace. No overlap raises. A grid with no positive
   steps uses `(qmax-qmin)/max(len(q),2)` as its candidate step.
6. Sort each q with its intensities and `np.interp` onto the common grid, using
   NaN outside source bounds. If any NaN occurs, retain only columns finite in
   **every** row; fewer than ten valid columns raises. This is the exact source
   conditional, not a new general finite-value repair policy.
7. Compute arithmetic mean per side and **sample std (`ddof=1`)** per q across
   its three interpolated profiles. These are replicate stds, not standard
   errors or azimuthal Poisson sigma. The source's single-replicate fallback
   is zeros, but single-replicate input is invalid for the product.

Changing row order changes only possible floating-point reduction roundoff;
all six permutations of each side preserve every feature/probability within
absolute `1e-10`, rtol zero. Bitwise equality is not promised.

## Exact 15-feature contract

Let `d=mu_left-mu_right` and `v=std_left²+std_right²` on the narrow grid.
Bands B1=[7,15], B2=[15,23] are inclusive (q=15 can belong to both).
Their effective support is restricted by the narrow ROI and overlap.
For each weighted/Mahalanobis band, mask finite d/v; require ten points;
floor v by its fifth percentile among strictly positive values, if any;
then let `w=1/(v+1e-12)`. This floor is band-specific.

| Index | Name | Authoritative value |
| --- | --- | --- |
| 1 | weightedrms1 | sqrt(sum(w*d²)/sum(w)), B1 |
| 2 | sigma_l1 | sqrt(mean(std_left²)), B1 |
| 3 | sigma_r1 | sqrt(mean(std_right²)), B1 |
| 4 | mahalanobis1 | sqrt(sum(d²/(v+1e-12))), B1; not reduced by dof |
| 5 | weightedrms2 | weighted RMS as above, B2 |
| 6 | sigma_l2 | sqrt(mean(std_left²)), B2 |
| 7 | sigma_r2 | sqrt(mean(std_right²)), B2 |
| 8 | mahalanobis2 | Mahalanobis as above, B2 |
| 9 | peak14_intensity | max((mu_left+mu_right)/2) over [13.5,14.5], at least 3 finite values |
| 10 | mean_peak_value_raw | mean of finite per-original-profile maxima over [13,14.8], before cropping/smoothing/normalization/interpolation/aggregation; each maximum needs 3 finite values |
| 11 | wasserstein_distance_muLR | q-weighted CDF distance of narrow side means, as below |
| 12 | cosine_distance_full_q2 | 1−clip(dot(L,R)/(norm(L)*norm(R)),−1,1), wide side means |
| 13 | wasserstein_distance_full_q2 | q-weighted CDF distance of wide side means |
| 14 | meanrms1 | sqrt(mean(d²)), B1 |
| 15 | meanrms2 | sqrt(mean(d²)), B2 |

Sigma and mean RMS independently mask finite inputs and require ten band points.
Insufficient support produces NaN. Wasserstein clips intensities to nonnegative,
keeps jointly finite q/a/b, requires ten points and each intensity sum >1e-12,
sorts by q, normalizes each side to unit sum, and returns
`sum(abs(cumsum(a/sum(a))[:-1]-cumsum(b/sum(b))[:-1])*diff(q))`.
Cosine requires ten jointly finite points and norm product >1e-12, otherwise NaN.
The raw peak eligibility gate is `mean_peak_value_raw >= 0.6`.
Errors become explicit rows in `build_feature_frame`'s error frame; this fixture
requires that frame to be empty, so silent patient drops cannot pass.

## Probability and interpretation

The frozen estimator has median SimpleImputer → StandardScaler → balanced L2
LogisticRegression (C=1, liblinear, max_iter=5000, random_state=0). No fitting is
performed here. Frozen statistics/scales/coefficients/intercept are in model.json.
Portable scoring imputes nonfinite entries, replaces scales `isclose(0)` with 1,
then applies sigmoid to `((x-mean)/scale) @ coef + intercept`, classes [0,1]
([1,0] would invert the probability). The fixed threshold is
`0.3585907282566089`, with positive decision at `>=`.

The paper source's label definition is CANCER/NON-CANCER and its probability is
named p_cancer; the platform presents MRI-continuation decision support. This PR
preserves and documents those distinct semantics, and does not establish a
clinically validated MRI endpoint or alter labels. No cohort splitting or model
training is performed, hence no new leakage, class-balance, validation-performance,
or safety claim follows from numerical parity. Existing train-all results are
not independent validation.

## Golden fixture and tests

`tests/fixtures/bremen_3x3/golden.json` freezes all six q/intensity arrays, feature
order, 15 numeric expectations, and estimator probability **0.7388733541967353**.
Opaque synthetic IDs only; no patient identifiers or storage paths. For replicate
index i=0..5 the generation formula was:

```
q = linspace(2 + .013*i, 23.4 - .017*i, 256+i)
y = .75 + .015*q + (.8+.07*i)*exp(-((q-13.8-.08*i)/1.2)**2)
    + .045*sin(q*(.65+.04*i)) + .018*i*cos(q/2.1)
```

Indices 0..2 are LEFT, 3..5 RIGHT. Original upstream `build_feature_frame` and
`artifact['estimator'].predict_proba` generated expectations, independently of the
copied test reference. `intermediates.json` freezes both grids, means and stds,
and six perturbation feature vectors. Each perturbation adds
`.12*exp(-((q-14.1)/.8)**2)` to just one profile. Its explicit `changed_features`
list answers which features change; the untouched side's sigma features stay
fixed, while same-side variance and bilateral features participate.

`tests/reference_0151` contains verbatim selected source definitions, the upstream
feature orchestrator and portable scorer, with reduced imports only. It is never
imported by production. Tests need neither external repository nor joblib artifact.
They cover golden features/probability, per-side permutations, every replicate,
independent sample variance calculation, differing q grids, interpolation and
out-of-range NaNs, grid bounds, raw peaks and normalization order, and shape.
Tolerance is **absolute 1e-10, rtol=0**, unchanged from authoritative feature/paper
probability harness. The separate upstream prediction consistency check uses
1e-12; that is not a license to loosen paper parity.

## Current runtime evidence and PR0152 work

Evidence: platform `src/bremen/api/workflow_bremen.py:build_features`,
`_compute_bremen_features`; `src/bremen/api/preprocessing_bridge.py:
build_feature_table` and metric helpers; `src/bremen/inference.py:
predict_proba_portable`, `adapt_model_package`.

| Operation / feature | Training behavior | Current runtime behavior | Match? | PR0152 action |
| --- | --- | --- | --- | --- |
| Measurement count consumed | All six valid profiles | Provider takes left_ms[0], right_ms[0]; accepts fewer than six | No | Validate exact 3+3 and consume all |
| Side aggregation | Means after per-profile preprocessing/alignment | Provider none; bridge averages extracted profiles by array index | No | Reproduce two passes |
| Replicate variance | Per-side sample std | Lost before features / pair variance substitute | No | Retain both std arrays |
| q-grid handling | Overlap, finest median step, interpolation | Provider feature helper ignores q; bridge Matador length/tolerance check | No | Implement source grid and edge behavior |
| Normalization | ROI then smoothing then p05 reference (narrow no-op) | Feature helper has no such preprocessing | No | Preserve order and fallback |
| Weighted RMS | Inverse pooled replicate variance, two bands | Intensity-derived weights over entire pair | No | Use exact band floor and epsilon |
| Sigma | Per-side RMS of sample std per band | Mean absolute difference / RMS / ratios of pair difference | No | Use correct side/band std |
| Mahalanobis | sqrt summed variance-normalized differences per band | Pair variance, mean/reduced or damped difference | No | Implement unreduced band sums |
| Peaks | q-window averaged-mean peak; original per-profile maxima | Index 14; top-five absolute values of pair | No | Respect q and original profiles |
| Wasserstein | CDF distance integrated over q | Intensity-weighted absolute difference / sorted normalized intensity CDF | No | Use q-sorted CDF integral |
| Cosine | Wide preprocessed means, finite masks and clipped dot | Pair norm with additive epsilon | No | Use wide pass and exact guards |
| Mean RMS | RMS difference in each band | Whole-pair absolute mean / RMS | No | Band-specific RMS |
| Feature ordering | Frozen 15 columns above | Same provider/bridge names and order | Yes | Preserve ordering |
| Probability | Scale without added epsilon | inference.py adds 1e-10 to every scale; only imputes NaN | No at 1e-10 | Match upstream scoring guards and arithmetic |

With **correct frozen features**, platform probability is `0.7388733540826478`,
a difference of `-1.1408751721120325e-10`. The strict xfail comparison names this
known discrepancy; it is not hidden by increasing tolerance. PR0152 must remove
that xfail when scoring is corrected. Passing test-only reference tests does not
certify the current runtime.

PR0152 must also bind the verified model checksum, preprocessing version, feature
schema, input contract and existing threshold together; preserve raw peaks until
feature construction; surface input/feature failures explicitly; and exercise this
fixture against the actual provider as well as the portable scorer. Validate raw
H5-to-profile parity separately and reconcile the historical preprocessing route
through change control before claiming end-to-end parity. No public first-pair
contract should be introduced. This PR does not authorize changes to endpoints,
labels, reports, decision threshold, or model parameters.

## Validation recorded for PR0151

Using the repository `venv/bin` Python 3.13 environment:

- `python -m compileall -q src tests`: passed.
- Targeted parity plus `tests/test_bremen_workflow_bremen.py`: **67 passed,
  1 xfailed** (the known platform scorer discrepancy).
- `pytest -q`: **4058 passed, 11 skipped, 1 xfailed**, 1635 warnings, 51.10s.
- Ruff on added Python files: passed. `ruff check .`: **405 existing findings**
  outside the new files; no unrelated lint fixes made.
- `git diff --check`: passed; new untracked files also checked separately.
- Production diff: empty. No commit created.
