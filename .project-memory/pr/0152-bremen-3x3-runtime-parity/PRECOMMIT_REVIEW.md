# PR0152 Pre-Commit Review — Bremen 3×3 Runtime Parity

## Branch
`0152-bremen-3x3-runtime-parity` (verified via `git branch --show-current`)

## HEAD
`dac554703d7125fc4ed4f1720e352626e901292b` (verified via `git rev-parse --verify HEAD`; no commit created by this review; worktree at review time 2026-09-14T18:59:34Z)

## PLAN reviewed
`.project-memory/pr/0152-bremen-3x3-runtime-parity/PLAN.md` — read in full, including
the "Updated request: concrete model-runtime ownership" steering addendum and the
recorded identity/validation sections. Source-of-truth set read completely first:
`.project-memory/pr/0151-bremen-3x3-training-parity/PLAN.md`,
`.project-memory/pr/0151-bremen-3x3-training-parity/PRECOMMIT_REVIEW.md`,
`docs/bremen_3x3_training_parity.md` (Parts 1+2),
`tests/reference_0151/{__init__,features,prediction,reference_features}.py`,
`tests/fixtures/bremen_3x3/{golden,model,intermediates,provenance}.json`,
`tests/test_bremen_3x3_training_parity.py`.

## Changed files (all read completely)
`git diff --name-status`: 12 modified; `git status --short`: +4 untracked code/test files
(+ `.project-memory/pr/0152…/{PLAN.md,IMPLEMENTATION_REPORT.txt}`).

| File | Status |
| --- | --- |
| `docs/bremen_3x3_training_parity.md` | M (Part 2 added; Part 1 preserved) |
| `src/bremen/bremen_features.py` | NEW |
| `src/bremen/bremen_runtime.py` | NEW |
| `src/bremen/api/workflow_bremen.py` | M (rewritten as adapter) |
| `src/bremen/api/h5_layouts.py` | M (Bremen-only canonicalizers added) |
| `src/bremen/api/model_requirements.py` | M (workflow_id pass-through, dead import removed) |
| `src/bremen/api/workflow_orchestrator.py` | M (`_normalize_h5(workflow_id=…)` selection) |
| `src/bremen/inference.py` | M (scaler parity, class order, nested metadata adaptation) |
| `tests/bremen_3x3_helpers.py` | NEW |
| `tests/test_bremen_3x3_runtime_parity.py` | NEW |
| `tests/test_bremen_3x3_training_parity.py` | M (strict xfail removed only) |
| `tests/test_bremen_workflow_bremen.py` | M (3+3 fixture migration; assertions strengthened) |
| `tests/test_bremen_inference_integration.py` | M (3+3 + physical q fixtures) |
| `tests/test_bremen_model_requirements_api.py` | M (3-per-side H5 fixtures) |
| `tests/test_bremen_runtime_plugin.py` | M (Nova test → frozen-contract execution) |
| `tests/test_multi_model_execution.py` | M (shared 3+3 case; models differ by coefficients) |

No ZIP, training repository, joblib, real H5, pickle, binary model, private dataset or
large binary fixture was added (`git status --untracked-files=all` scanned; no
`.h5/.joblib/.pkl/.zip/.pt/.onnx/.bin/.npy` entries). `tests/reference_0151` and
`tests/fixtures/bremen_3x3` are untouched.

## PR0151 source contract reviewed
PR0151 is treated as the frozen scientific source of truth: golden fixture
`synthetic-0151` (6 measurements: 3 LEFT 256/257/258 pts + 3 RIGHT 259/260/261 pts),
15-feature order, `expected_features`, probability `0.7388733541967353`,
tolerance absolute `1e-10`, rtol 0; portable scorer semantics (nonfinite imputation,
`isclose(0)→1` scale guard, sigmoid, classes `[0,1]`, threshold `0.3585907282566089`,
positive at `>=`); `ddof=1` replicate std; per-original-profile raw peaks; raw-peak
gate `>= 0.6`.

## Model-runtime boundary assessment
**PASS — dedicated runtime owns the science.**
- `src/bremen/bremen_features.py`: all 20 shared numerical primitives
  (`parse_q_grid`, `apply_roi`, `safe_savgol`, `minimum_reference_value`,
  `normalize_by_minimum`, `build_common_grid`, `resample_to_common`, `side_label`,
  `patient_lr_mean_metrics`, `mask_q`, `mean_rms_band`, `weighted_rms_band`,
  `mahalanobis_band`, `sigma_rms_band`, `peak14_intensity_from_means`,
  `local_peak_in_window`, `patient_mean_raw_peak14`, `cosine_distance`,
  `wasserstein_distance`, plus inner `median_step`) are **AST-identical** to
  `tests/reference_0151/reference_features.py` (verified programmatically).
  `AnalysisConfig` is field-identical except the three fields unused by the frozen
  pipeline (`excluded_patients`, `random_state`, `cv_splits`) which are absent —
  immaterial, matches the PR0151 test config which set `excluded_patients=()`.
- `src/bremen/bremen_runtime.py`: `BremenRuntime` owns input validation, feature
  construction, scoring and decision; returns structured `BremenFeatures` /
  `BremenModelResult`; rejects reordered feature schemas and invalid class orders;
  never exposes raw exceptions (`BremenRuntimeError` fixed messages).
- No generic ModelRuntime protocol, no MLflow/BentoML/KServe (grep: none).

## workflow_bremen responsibility assessment
**PASS — orchestration adapter only.** The legacy `_compute_bremen_features`
(fake 15-feature engine) and the provider's duplicated scaler/logit math were
**deleted** (confirmed in diff). `build_features` delegates to
`runtime.build_features`; `execute` performs exactly one `runtime.run(...)` call
(`test_actual_analysis_job_runs_runtime_once` asserts `run` called once and exactly
one `runtime.features.completed` event). The provider retains only: canonical input
handling, compatibility gate, safe failure translation (fixed constants), result
projection, per-side counts, and job-event emission. No q-grid, smoothing,
normalization, aggregation, replicate statistics, feature generation, model-specific
scaling, or estimator math remains in `workflow_bremen.py`.

## Exact production 3×3 algorithm (as implemented, runtime-owned)
Validate exactly 6 measurements = 3 LEFT + 3 RIGHT (exact case, unknown/extra sides
fail) → per profile: canonical validation (1-D finite strictly-increasing q, matching
intensity length) → inclusive ROI crop `[7.5,23]`/`[2,23]` (≥5 points) →
Savitzky–Golay window 11, poly 3, SciPy `interp` edge → p05 normalization in
`[6.45,6.95]` floored at 1e-3 (narrow ROI = no-op) → common grid from overlap
endpoints + smallest median positive step, `clip(round(span/step)+1,50,5000)` →
`np.interp` with NaN outside bounds + all-row-finite column filter (≥10 columns) →
LEFT/RIGHT grouping → per-side arithmetic mean and **sample std (`ddof=1`)** across
all three replicates → bands B1=[7,15], B2=[15,23] → weighted RMS / sigma_l / sigma_r
/ unreduced Mahalanobis / mean RMS per band with band-specific p05 variance floor and
`1e-12` → `peak14_intensity` (max of averaged means in `[13.5,14.5]`) →
`mean_peak_value_raw` (mean of per-original-profile maxima in `[13,14.8]`, before
crop/smooth/normalize/interpolate/aggregate) → q-weighted CDF Wasserstein (narrow +
wide) → cosine distance (wide) → exact 15-feature order → nonfinite imputation →
scaler (`isclose(0)→1`, **no added epsilon**) → logistic-regression sigmoid →
threshold `0.3585907282566089`, positive at `>=`. Raw-peak gate
(`mean_peak_value_raw >= 0.6`) enforced as `raw_peak_gate_failed`; scientific
failures become the fixed constant `invalid_scientific_profiles`.

## First-pair removal result
**PASS.** `grep -rn "left_ms[0]\|right_ms[0]" src/` → **none**. `first_pair` matches:
stale `__pycache__` binaries only, one pre-existing unrelated Aramina loader test
name (`tests/test_bremen_h5_layouts.py::test_resolves_first_pair_by_default`,
unchanged file, legacy Aramina pair resolver), and the docs statement that no
`first_pair_legacy` contract exists. No "first LEFT/RIGHT" selection remains in
production; no `first_pair_legacy` public contract introduced. Legacy
`normalize_to_canonical` pair semantics remain **only** for Aramina, unchanged
(explicitly commented; verified by `test_canonical_h5_preserves_physical_q_and_legacy_path`).

## Model identity result
**PASS (local artifact). Independently re-verified during this review:**
- Sibling training checkout at commit `c98a950d3fbf0db72d87f2ecd977d80fe35da9e4`
  (re-confirmed via `git rev-parse`).
- Artifact
  `outputs/paper_reference/training/bremen_paper_reference_symmetry_logreg_0_2_0-paper-reference_20260802T173549Z_6c8b029f/model.joblib`
  re-hashed: SHA256 `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0`
  — matches PR0151 provenance and run manifest.
- Loaded the real artifact with the production `adapt_model_package` (nested
  `feature_schema.feature_columns` / `decision.threshold`): all portable parameters
  (imputer statistics, scaler mean/scale, coef, intercept, classes) match
  `tests/fixtures/bremen_3x3/model.json` with **max diff 0.0**; `feature_columns`
  and `threshold 0.3585907282566089` equal; classes `[0,1]`.
- Real artifact on golden features through the production scorer → probability
  `0.7388733541967353`, **diff 0.0**.
- Version `0.2.0-paper-reference`; name `bremen_paper_reference_symmetry_logreg`.
  Note: `model_id` (`bremen-paper-reference-v0-2-0`) is recorded in the training run
  manifest, not in the artifact's `model_identity` block (name+version only) —
  documentation nuance, non-gating.
- The v0.2 private-artifacts candidate (checksum `971b20ba…`, threshold `0.4130…`)
  is not selected by any configuration in this environment and was not substituted.
- **Live deployment identity is not queryable from this review environment.** This is
  non-blocking only because exact post-deploy identity verification is documented
  (docs Part 2 "Post-deploy verification steps" 1–4 and PLAN): deployed checksum,
  loaded threshold/classes, golden 3+3 submission parity, and five-measurement
  rejection smoke. This must be executed before activation.

## Raw-H5 parity result
**PASS.** `test_synthetic_h5_production_job_path`: synthetic session-layout H5
written to `tmp_path` → production `_normalize_h5(..., workflow_id="bremen")` →
6 measurements with native unequal q arrays → `BremenProvider.build_features`
matches golden features at 1e-10 → full `run_workflow_request` job → probability
matches golden → H5 bytes unchanged (read before/after). Trace confirmed:
synthetic H5 → production loading/canonicalization (`SessionLayoutH5Adapter.
normalize_bremen_to_canonical`, all sets retained, native q) → six measurements →
`BremenRuntime.run` → 15 features → probability. Also covered:
`test_calibration_h5_retains_all_native_profiles` (calibration layout, all 6 sets),
`test_canonical_h5_preserves_physical_q_and_legacy_path` (explicit physical q;
missing q → `Missing physical q coordinates`; legacy Aramina canonicalization
unchanged), `test_h5_enumeration_does_not_change_scientific_output` (12 H5 write
orders), `test_h5_invalid_shape` (invalid containers fail; scorer never called).
The fixture is synthetic (formula-generated profiles, opaque IDs `profile-1…6`),
contains no patient/source/private information, and no H5 is committed (generated
in `tmp_path` at test time). Scope note: this is H5-container/profile evidence as
planned, not a detector/PONI integration claim; `MatadorRawH5Adapter` has no Bremen
canonicalizer and falls back to legacy normalization (Bremen session/calibration
layouts are the exercised product path per PLAN).

## 15-feature parity
**PASS.** `test_production_golden_features_and_probability` (and the 52-test
`tests/test_bremen_3x3_runtime_parity.py` suite): production feature names ==
`GOLD['feature_names']` (exact 15-column order), values match
`GOLD['expected_features']` at `atol=1e-10, rtol=0` (PLAN records max abs diff 0.0).
The provider never reorders: `BREMEN_V01_FEATURE_COLUMNS = BremenRuntime.feature_names`
(single source), and `runtime.score` rejects any reordered schema
(`invalid_feature_schema`).

## Probability parity
**PASS.** Production probability equals `0.7388733541967353` (diff 0.0) at the
authoritative tolerance; `threshold_applied == 0.3585907282566089`; prediction `1`.
Independently re-confirmed against the real sibling artifact through the production
adapter/scorer during this review (diff 0.0). Model parameters and feature ordering
were inspected: positional 15-vector in frozen order, balanced-L2 portable logreg
parameters identical to the frozen fixture.

## Replicate-variance parity
**PASS.** `std_left/std_right = np.std(..., ddof=1)` across all three replicates per
side (function AST-identical to the frozen source). `test_sample_std_and_mean_
independently` (PR0151 suite) independently proves ddof=1 (std of [1,2,6] = √7).
`test_identical_replicates_preserve_authoritative_variance` proves production sigma →
0 when replicates are identical and agrees with the reference scorer. Each replicate
mutation changes same-side `sigma_*` features (all-six participation), so the
implementation is not a mean-LEFT vs mean-LEFT comparison.

## Peak-feature parity
**PASS.** `mean_peak_value_raw` = mean of per-original-profile maxima in `[13,14.8]`
computed on raw profiles before crop/smooth/normalize/interpolate/aggregate
(`patient_mean_raw_peak14` identical; `test_peak_is_mean_of_original_maxima` and
`test_roi_precedes_normalization_and_raw_peaks_precede_aggregation` still pass);
`peak14_intensity` = max of the averaged side means in `[13.5,14.5]` (identical
function). No peak(mean profile) substitution. Raw-peak gate `>= 0.6` preserved
(`test_raw_peak_gate_is_preserved`).

## Scaler parity
**PASS.** `src/bremen/inference.py`: the added `1e-10` epsilon is **removed**
(`scaled = (features - scaler_mean) / scaler_scale` with
`np.where(np.isclose(scaler_scale, 0.0), 1.0, scaler_scale)`), imputation covers all
nonfinite values, class orientation `[0,1]`/`[1,0]` handled, sigmoid unchanged,
threshold `>=` unchanged — all matching the frozen portable scorer. The old strict
xfail (`test_current_platform_probability_against_training_golden`) was **removed**
and now **passes normally** (32 passed, 0 xfailed in the PR0151 parity suite).
`workflow_bremen.run_inference`'s duplicated epsilon math was deleted; scoring is
consolidated onto `inference.predict_proba_portable`. Legacy `+1e-10` patterns
remaining in the repo are confined to dormant legacy helpers outside the live Bremen
inference path (`api/preprocessing_bridge.py`, `training/pipeline.py` — both
unchanged, not reachable from the runtime; `inference_handler.run_inference` is a
documented legacy wrapper delegating to `run_workflow_request`). The
`1e-12`/`1e-3` constants in `bremen_features.py` are the authoritative
training-source epsilons (byte-identical to the reference).

## LEFT permutation result
**PASS.** `test_production_permutations` (side_offset 0; all 6 orders) and PR0151
`test_side_permutation_invariance`: features and probability match golden at
absolute 1e-10, rtol 0.

## RIGHT permutation result
**PASS.** `test_production_permutations` (side_offset 3; all 6 orders) plus 6 H5
write-order permutations per side
(`test_h5_enumeration_does_not_change_scientific_output`): parity holds; no
arbitrary replicate sorting was introduced (the frozen contract contains none).

## All-six participation result
**PASS.** `test_production_all_six_participate` mutates each of L1, L2, L3, R1, R2,
R3 independently (`+0.12·exp(-((q-14.1)/0.8)²)`) and asserts the full feature vector
equals the frozen `intermediates.json` mutation vector and that the changed-feature
set equals the frozen `changed_features` (13 features per mutation, non-empty, with
same-side `sigma_*` participating and opposite-side sigma fixed). Counts/metadata
are not used; scientific intermediates respond to each mutation.

## Invalid-shape result
**PASS.** Provider level (`test_invalid_shape_rejected_before_science_or_scoring`):
3+2, 2+3, 4+2, 2+4, 1+1, 0+6, 6+0, 3+4, 0+0 all return
`Incompatible: requires_exactly_3_left_3_right` with **science and scorer
monkeypatched to raise AssertionError and asserted never called** — invalid input
fails before any scientific model inference. `build_bremen_features` raises
`BremenFeatureError('requires_exactly_3_left_3_right')` independently of model
availability. H5 job level (`test_h5_invalid_shape`): invalid containers fail closed;
`score` asserted never called; pair-less containers fail at layout detection.
Scientific-failure sanitization proven by
`test_scientific_failure_is_safe` (a mock exception containing
`/private/source secret token traceback` produces only the fixed constant
`invalid_scientific_profiles`).

## Old xfail status
**RESOLVED.** `tests/test_bremen_3x3_training_parity.py` diff removes only the
`@pytest.mark.xfail(strict=True)` marker (4 lines). The test now passes as a normal
assertion: suite result **32 passed, 0 xfailed**.

## Deduplication assessment
**PASS.** One authoritative production 15-feature implementation exists
(`src/bremen/bremen_features.py`), reached only via `BremenRuntime`.
`workflow_bremen.py` contains no feature/scoring math (legacy engine deleted).
`tests/reference_0151` is imported only by tests; `grep "from tests|import tests" src/`
→ none; production never imports the test reference. Remaining look-alike code
(`api/preprocessing_bridge.py` legacy metric helpers, `training/pipeline.py`
offline helpers, Aramina-specific `sk_*` feature modules) is pre-existing, unchanged,
outside the live Bremen inference path (`build_feature_table` is only self-called;
`inference_handler.run_inference` delegates to `run_workflow_request`). The 15-name
constant now has a single runtime source (`BremenRuntime.feature_names`); other name
copies (server listing, feature-artifact tooling) are metadata, not formula
implementations.

## Public API compatibility
**PASS.** Workflow payload fields unchanged (`prediction_id`, `model_version`,
`model_checksum`, `feature_schema_version`, `probability`, `prediction`,
`threshold_applied`, `triage_recommendation`, `decision_*`; `left/right_measurement_
count` pre-existing). No measurement-selection details became public report fields.
No new report/API fields; auth untouched; job lifecycle unchanged except the intended
Bremen invalid-input envelope (`requires_exactly_3_left_3_right`, fixed safe reasons);
`WorkflowConfigurationRequiredError` class retained for compatibility; Aramina
behavior unchanged (legacy loaders keep pair semantics; Aramina suites pass);
report envelope, frontend, PDF untouched. Event additions are additive and sanitized
(`validate_features` emits counts/order booleans only; privacy-prohibited keys
rejected by existing event schema tests).

## Security/privacy assessment
**PASS.** No local filesystem paths, S3 keys/ARNs, source keys, artifact internal
paths, tracebacks, raw exceptions, tokens, or environment variables are exposed by
the new code (grep-verified; scientific/provider failures translate to fixed
constants; H5 layout errors use fixed messages). No real H5 or training patient data
committed; fixtures are synthetic formula-generated with opaque IDs; H5 source
checksum is a hash only (pre-existing pattern); no secrets in the diff; no binaries.
The only sensitive-looking string is in a test that deliberately plants sensitive
text in a mock exception to prove non-leakage.

## Scope
**PASS.** Changes limited to Bremen workflow integration, Bremen inference/runtime,
Bremen H5 loading methods, tests, and the focused parity doc. No changes to Aramina
logic, auth, frontend, PDF, deployment, S3 discovery, generic serving frameworks,
MLflow/BentoML/KServe, or thresholds/model parameters.

## PR0153 preparation
**REASONABLE.** The numerical core (`bremen_features.py` primitives) is
platform-independent (numpy/pandas/scipy only); `BremenRuntime` is a concrete,
self-contained model-owned class invoked through a single `run(...)` boundary with a
structured result; orchestration is fully outside. No speculative generic protocol
was introduced. Non-gating note: `build_bremen_features` lazily imports
`validate_canonical_measurement` from `bremen.api.xrd_normalization` (platform-adjacent
input validation inside the scientific module) — an acceptable PR0152 seam and the
obvious first candidate to lift into the future ModelRuntime contract.

## Targeted test results (executed during this review)
- `python -m compileall -q src tests` → **exit 0**.
- `pytest -q tests/test_bremen_3x3_training_parity.py` → **32 passed** (0 xfailed).
- `pytest -q tests/test_bremen_workflow_bremen.py` → **36 passed**.
- `pytest -q tests/test_bremen_3x3_runtime_parity.py` (PR0152-specific) → **52 passed**.
- `pytest -q tests/test_bremen_inference_integration.py
  tests/test_bremen_model_requirements_api.py tests/test_bremen_runtime_plugin.py
  tests/test_multi_model_execution.py` → **84 passed, 1 skipped**.
- Neighboring affected suites (`test_bremen_h5_layouts.py`,
  `test_bremen_job_api_handler.py`, `test_aramina_workflow_runtime.py`,
  `test_aramina_provider_contract.py`, `test_bremen_xrd_normalization.py`) →
  **421 passed, 1 skipped**.

## Full pytest result
`pytest -q` → **4112 passed, 11 skipped, 0 xfailed** (41.94s, exit 0). No xfails remain.

## Changed-file Ruff result
`ruff check` on all 15 changed/new Python files → **All checks passed!**
Repository-wide `ruff check .` → 355 findings, all pre-existing outside the changed
files (PR0151 recorded 405; none introduced by this PR; no unrelated lint fixes made).

## git diff --check result
`git diff --check` → **exit 0** (no whitespace errors).

## Legacy-pattern search results
- `left_ms[0]` / `right_ms[0]` in `src/`: **none**.
- `first_pair`: only stale `.pyc` binaries, a pre-existing unchanged Aramina loader
  test name, and the docs' explicit "no `first_pair_legacy`" statement.
- "first LEFT"/"first RIGHT"/"first pair" in `src/`: only a stale `.pyc` binary.
- Duplicated 15-feature formula implementations: one authoritative production
  implementation (`bremen_features.py`); legacy look-alikes are dormant and outside
  the live path (see Deduplication).
- Production imports from `tests` / `tests/reference_0151`: **none**.
- Unauthorized model-specific scientific computation remaining in
  `workflow_bremen.py`: **none** (legacy engine deleted).
- Added `1e-10` scaler arithmetic in the runtime path: **none** (removed; authoritative
  `1e-12`/`1e-3` training epsilons remain, byte-identical to the frozen source).

## Risks / non-gating notes
1. **Live deployment identity unverified** (environment cannot reach production).
   Local runtime artifact identity is fully verified; exact post-deploy smoke
   (checksum, threshold/classes, golden parity, five-measurement rejection) is
   documented and must be run before activation.
2. `execute()` retains a defensive `workflow_configuration_required` branch that is
   now unreachable (exact 3+3 gate replaces the old Nova gate). Dead code, harmless.
3. `model_id` (`bremen-paper-reference-v0-2-0`) is recorded in the training run
   manifest; the artifact's `model_identity` carries name+version only. Documentation
   nuance; repository/runtime identity fields are consistent.
4. `build_bremen_features` lazily imports canonical measurement validation from
   `bremen.api.xrd_normalization` — acceptable for PR0152; flag for PR0153 decoupling.
5. `MatadorRawH5Adapter` has no Bremen-specific canonicalizer (falls back to legacy
   normalization); Bremen raw-H5 evidence covers session/calibration/canonical
   layouts as planned.
6. Repository-wide Ruff has pre-existing findings (355) outside changed files.
7. Raw-H5 parity is H5-container/profile evidence, not a detector/PONI integration
   claim (documented in PLAN and docs).
8. `readiness()` continues to report `scientifically_certified=False` (unchanged,
   honest posture).

## FINAL VERDICT

**READY FOR COMMIT**

All required conditions hold: exact 3+3 production contract enforced before science;
all six measurements scientifically participate; PR0151 15-feature parity (atol 1e-10,
rtol 0, diff 0.0) and probability parity (diff 0.0) pass in production; replicate
variance (`ddof=1`), peak semantics, q-grid behavior and scaler behavior match the
frozen training contract; permutation invariance passes at provider and H5 levels;
raw-H5 production path parity passes; the old training-serving xfail is resolved
(0 xfailed); first-pair scientific selection is removed; `workflow_bremen.py` is an
orchestration adapter and the dedicated `BremenRuntime` owns scientific inference;
no unauthorized scientific change; no unrelated Aramina/API/report/framework change;
no private or real training data committed; full pytest (4112 passed), changed-file
Ruff and `git diff --check` all pass.

Do not commit (review-only task).
