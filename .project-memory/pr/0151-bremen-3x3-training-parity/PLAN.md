# PR0151 — investigation and golden contract

Scope: documentation and test-only fixtures/reference; no production changes, MLflow,
retraining, replacement artifacts, public API additions, or commits.

## Provenance (recorded before implementation)

Authoritative source available locally: sibling repository
`/Users/alexred/Projects/Python/bremen-training-pipeline`, commit
`c98a950d3fbf0db72d87f2ecd977d80fe35da9e4`. The requested
`bremen-training-pipeline-main` archive is not attached; use the available source
checkout and record file hashes. Its only worktree change is deleted outputs/.gitkeep.
No archive is used or copied; archive SHA256 is not applicable.

Trace `src/bremen/features.py` (analysis_config, build_feature_frame),
`reference_features.py` (patient_lr_mean_metrics, grid, smoothing, normalization,
band metrics and peaks), `paper_reference.py`, `training.py`, `prediction.py`,
and `config/preprocessing/bremen_paper_reference_all_n256_v0_2.yaml`.
Compare workflow_bremen.py, preprocessing_bridge.py, inference.py and manifests.

Feature order: weightedrms1, sigma_l1, sigma_r1, mahalanobis1, weightedrms2,
sigma_l2, sigma_r2, mahalanobis2, peak14_intensity, mean_peak_value_raw,
wasserstein_distance_muLR, cosine_distance_full_q2,
wasserstein_distance_full_q2, meanrms1, meanrms2.

Model candidate: bremen_paper_reference_symmetry_logreg,
0.2.0-paper-reference. Verify frozen artifact identity and portable parameters
against available platform provenance before declaring probability parity.

## Acceptance criteria

Generate explicit non-degenerate synthetic 3 LEFT + 3 RIGHT profile values and
expected features/probability by executing the authoritative source and existing
fitted estimator (never fit). Freeze source/model hashes and numerical outputs.
Test absolute tolerance 1e-10 (rtol=0), matching upstream parity harness.
Exercise all within-side permutations, all six replicate perturbations, sample
variance, nonidentical q grids/interpolation/out-of-range behavior, raw peaks,
and exact product shape (five invalid) without runtime enforcement changes.
Keep reference entirely under tests and verify no production modifications.
Document exact formulas, upstream preprocessing boundary, deviations and PR0152
requirements. Run compileall, targeted parity/workflow tests, ruff, full pytest,
and git diff --check. Record failures honestly. No clinical validation claim.

## Outcome and evidence

Confirmed source computation on six distinct synthetic integrated profiles using
original upstream build_feature_frame and the existing sklearn estimator. Frozen
model SHA256: 65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0,
matching the local run manifest. Live deployment was not queried. Source file
hashes, fitted portable parameters, vectors and intermediate arrays are committed
as proposed untracked files only (no git commit made).

The source's training features/probability reproduce at absolute 1e-10. Platform
scoring with correct frozen features differs by -1.1408751721120325e-10 due to
its added scaler epsilon. A strict xfail explicitly tracks this PR0152 gap;
production was not changed to make the comparison pass. The source uses sample
std (ddof=1); narrow ROI normalization is a no-op; original-profile raw peaks
remain distinct from the smoothed aggregate peak.

The fixture boundary is integrated profiles, not raw detector H5. The upstream
seven-step paper preprocessing config differs from the general product pipeline;
this is documented, not applied to production. Numerical parity does not validate
the MRI endpoint or establish live deployment identity.

Validation: compileall passed; targeted parity/workflow 67 passed, 1 xfailed;
full pytest 4058 passed, 11 skipped, 1 xfailed (51.10s); changed-file Ruff passed;
repository Ruff has 405 pre-existing findings outside added files. Diff whitespace
checks passed. Only PLAN.md, focused investigation, tests and fixtures added.
No production edits, retraining, MLflow, archive copies or commit.
