# PR0152 — Bremen 3×3 runtime parity

## Starting state and authority

Branch `0152-bremen-3x3-runtime-parity`, HEAD `dac5547` (PR0151, #211), clean
worktree. Reviewed PR0151 PLAN, PRECOMMIT_REVIEW, investigation, frozen reference,
parity tests and JSON fixtures. Preserve their scientific formulas and tolerance
(absolute 1e-10, rtol=0); no scientific reinterpretation.

## Identity investigation before implementation

No model URI/catalog/version/checksum environment is configured in this process;
local process registry is not_configured with zero entries. The PR0151 model
is available in the sibling training repository, checksum
65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0,
version 0.2.0-paper-reference, manifest model_id bremen-paper-reference-v0-2-0,
threshold 0.3585907282566089. Verify its portable parameters through the platform
adapter before implementation. Live production requires deployment smoke.

A separate private-artifacts v0.2 research candidate has checksum
971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4 and threshold
0.4130396520921527. It is NOT selected by any configuration in this environment
and must not be substituted for the PR0151 model or claimed to match. If an
operator selects that candidate, identity verification must fail and require
model-owner resolution before deployment.

## Implementation

Port the frozen computation into one focused production scientific module, with
workflow_bremen orchestrating all six canonical measurements. Retain per-profile
ROI, Savitzky–Golay, p05 normalization (narrow no-op), overlapping finest-step
grid/interpolation, per-side arithmetic mean and sample std ddof=1, two bands,
original-profile raw peaks, exact 15-feature order and raw peak gate.
Consolidate provider scoring onto inference.predict_proba_portable: upstream
finite imputation, zero-scale guard, no added epsilon, class orientation and
unchanged >= threshold. No model parameter/threshold changes.

Validate exactly 3 LEFT and 3 RIGHT before scientific work; use existing
incompatible/input failure envelope and fixed technical reasons. Scientific
exceptions must become safe constant reasons, never interpolated raw exceptions.
No arbitrary replicate sorting. Production never imports tests.

## H5 and test strategy

Create a synthetic H5 in tmp_path containing the six frozen q/profile datasets
and required layout metadata. Use job production adapter selection/canonicalization
and provider execution; assert every profile survives and all frozen values match.
This is H5-container/profile evidence, not a fabricated detector/PONI integration
claim. Inspect loading path for destructive pre-aggregation/alignment.

Add production golden, exhaustive per-side permutation, six independent mutation,
variance/identical-replicate, differing-grid, invalid shape and scoring arithmetic
regressions. Convert old strict xfail to passing assertion. Migrate old valid
workflow fixtures from 1+1 to 3+3 with q support through 23; retain explicitly
invalid fixtures as rejection tests. Do not weaken assertions or add runtime
exceptions for tests. Keep pure helper unit tests separate.

## Scope and checks

Expected production changes: focused feature module, workflow_bremen.py,
inference.py; loading changes only if needed to preserve all six native profiles.
No Aramina/auth/frontend/report schema/lifecycle/S3 discovery/MLflow/infrastructure
redesign, retraining, replacement artifacts or commit.

Run compileall src tests; PR0151/PR0152 parity and workflow tests; affected job /
inference regressions; full pytest; changed-file Ruff; git diff --check. Record
fixture migrations, exact identity evidence and post-deploy smoke procedure.

## Updated request: concrete model-runtime ownership

The user's steering now requires the first model-owned boundary, superseding
this plan's earlier narrower helper-only scope. Add BremenRuntime with structured
BremenFeatures/BremenModelResult. It owns validation, preprocessing/features,
scoring and decision; provider.execute calls runtime.run once with an optional
feature-stage notification for existing event tracing. No generic framework.

Additional justified production scope: h5_layouts provides Bremen-only session,
canonical and calibration loading methods; workflow_orchestrator selects these
for Bremen; model_requirements dry-run passes workflow selection consistently.
Legacy loading methods remain for Aramina, including their old pair semantics.
Bremen session/calibration loading retains all profiles and native q. Canonical
Bremen loading requires explicit physical q instead of inventing array indices.
These changes are necessary to exercise the actual job H5 path without silently
losing replicates or rejecting valid unequal q arrays before model alignment.

The original artifact's portable values match every frozen field; current
adapt_model_package needed support for nested feature_schema.feature_columns and
decision.threshold. Added this structural adaptation without changing any
scientific parameter. All expected fields now match through the runtime adapter.

Fixture migration: workflow provider, runtime events and multi-model tests use
shared non-degenerate 3+3 PR0151 profiles. Requirements dry-run fixtures now have
three profiles per side; inference H5 fixtures supply physical q. A former Nova
configuration-required test now verifies normal six-profile execution; the
wrong-feature-order readiness assertion now correctly requires rejection.

## Identity verification result (recorded during implementation)

The sibling training checkout at commit `c98a950d3fbf0db72d87f2ecd977d80fe35da9e4`
was inspected. The PR0151 artifact
`outputs/paper_reference/training/bremen_paper_reference_symmetry_logreg_0_2_0-paper-reference_20260802T173549Z_6c8b029f/model.joblib`
hashes to `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0`,
matching PR0151 provenance and that run's `manifest.json`. Its manifest records
model_id `bremen-paper-reference-v0-2-0`, version `0.2.0-paper-reference`,
threshold `0.3585907282566089`, feature_schema_version `v0.1`, workflow_id
`bremen`. Every portable parameter (imputer statistics, scaler mean/scale, coef,
intercept, classes `[0,1]`) matches `tests/fixtures/bremen_3x3/model.json`
exactly (max diff 0.0). The artifact stores `feature_schema.feature_columns` and
`decision.threshold` nested; `adapt_model_package` reads those without changing
any scientific parameter. Local runtime artifact identity is verified; live
deployment identity requires post-deploy smoke verification.

## Validation recorded for PR0152

- `python -m compileall -q src tests`: passed.
- `pytest -q tests/test_bremen_3x3_runtime_parity.py`: 52 passed.
- `pytest -q tests/test_bremen_3x3_training_parity.py tests/test_bremen_workflow_bremen.py`:
  68 passed (old strict xfail now passes normally).
- `pytest -q`: 4112 passed, 11 skipped, 0 xfailed.
- Golden 15-feature parity: max abs diff 0.0; probability diff 0.0.
- Raw-H5 end-to-end parity: max abs feature diff 2.2e-16.
- Permutation invariance: 12 cases exact; all-six participation: 13 features
  change per replicate mutation.
- Invalid shapes (3+2, 2+3, 4+2, 2+4, 1+1, 0+6, 6+0, 3+4, 0+0): all fail closed
  with `requires_exactly_3_left_3_right` before science or scoring.
- Changed-file Ruff and `git diff --check`: see final report.
