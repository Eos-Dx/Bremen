# PR0160 — Model-Package-Owned Scientific Preprocessing (Bremen)

## 1. Current failure mode

Bremen paper-reference inference (workflow `bremen`) still consumes the
platform canonical `CanonicalXRDCase` produced by `bremen.api.h5_layouts`
(`normalize_bremen_to_canonical` on session/canonical/calibration adapters) and
feeds those pre-integrated q/intensity arrays directly into
`bremen_v01.features.build_bremen_features`.

The platform normalization reads **stored `/session/sets/*/integration/q,i`
arrays** (2000-point pre-integrated) OR re-derives profiles, and it is NOT the
authoritative paper-reference preprocessing.  The authoritative pipeline is the
artifact-owned `prediction_preprocessing_yaml` (xrd-preprocessing `v0.1.7-beta`,
commit `45d5568…`), which:

- reads raw detector frames via `H5ToDataFrameTransformer` (raw_file/GFRM);
- applies product column building, k-alpha q-coverage and position filters;
- runs `AzimuthalIntegration` with 256 npt, PONI calibration, poisson errors,
  **thickness correction** (`require_sample_thickness: false`,
  `require_calibrant_thickness: true`);
- keeps only the frozen output columns.

Forensic evidence (Nova_378): the authoritative path produces
`mean_peak_value_raw = 0.46283992131551105` (per-profile corrected peaks
Right P1/P2/P3 = 0.3635513/0.3559077/0.4989820, Left P1/P2/P3 =
0.4220003/0.4592024/0.6773959) and **fails the frozen 0.6 raw-peak gate**, while
the platform's stored-integration path produces a materially different
intermediate (~0.295 / 0.2829) that happens to also fail.

This PR moves the scientific source of truth into the Bremen model package.

## 2. Chosen minimal boundary

Add a package-owned preprocessing module and pinned worker to
`bremen.model_packages.bremen_v01` (mirroring the established Aramina
`aramina_v0213/preprocessing.py` + `aramina_preprocess_worker.py` pattern):

- `src/bremen/model_packages/bremen_v01/preprocessing.py` — orchestration:
  reads the artifact's `prediction_preprocessing_yaml`, selects the pinned
  xrd-preprocessing release, runs the isolated worker subprocess, returns the
  measurement DataFrame (safe columns only).
- `src/bremen/model_packages/bremen_v01/bremen_preprocess_worker.py` — isolated
  worker (no Bremen/Aramina platform imports) that:
  - validates the xrd-preprocessing version against the release tag;
  - builds the pipeline from the artifact YAML;
  - applies a **package-owned, read-only legacy-container compatibility
    adapter** (temporary copy adding root `schema_version=0.3` /
    `format=xrd-session` when absent — required because the authoritative
    `list_h5_sessions` rejects containers without root container identity, e.g.
    Nova_378), then runs the pipeline;
  - emits JSON rows (patientId, side, position, sample_thickness_mm,
    thickness_adjustment_applied, q_range, radial_profile_data) plus a safe
    source_metadata object (age/scan/operator/hardware from the package's own
    `source_metadata.py` adapter — unchanged PR0159 contract).

`BremenRuntime.predict_model` becomes:

1. validate 3+3 product contract (unchanged, measurements from
   `ModelInput.measurements`);
2. load the artifact package (existing `self.package`);
3. read `prediction_preprocessing_yaml` from the artifact;
4. run package-owned preprocessing against `ModelInput.container_path` (raw
   staged H5);
5. build the frozen 15 features from the preprocessed frame
   (`build_bremen_features` — unchanged science, consumes the authoritative
   radial profiles);
6. run the frozen estimator (unchanged `predict_proba_portable`);
7. apply the unchanged 0.6 raw-peak gate and threshold;
8. return `RuntimePrediction` with the normalized
   `SourceMetadata`/`ModelMetadata`/`ModelMetrics` (PR0159 contract).

The platform path (`run_workflow_request` → `_normalize_h5` → `h5_layouts`)
is **no longer the scientific source** for paper-reference inference.  The
orchestrator still normalizes for generic layout/event/report purposes, and the
Bremen provider still receives `container_path` (already plumbed in PR0159) —
but the runtime now ignores the platform canonical measurement arrays for
science and uses the raw staged container.

`workflow_bremen.py` changes are minimal: it already passes
`container_path=h5_path`; it will keep passing the canonical case for
compatibility/event purposes, but `predict_model` no longer receives
measurements as the science input.  `validate_compatibility` still enforces
3+3 on the canonical measurements (unchanged product contract).

## 3. Existing class(es) to modify

| File | Change |
| --- | --- |
| `src/bremen/model_packages/bremen_v01/preprocessing.py` | **new** — package-owned preprocessing orchestrator + worker invocation |
| `src/bremen/model_packages/bremen_v01/bremen_preprocess_worker.py` | **new** — isolated pinned worker + legacy compatibility adapter |
| `src/bremen/model_packages/bremen_v01/runtime.py` | `predict_model` executes package-owned preprocessing + feature + estimator from raw container |
| `src/bremen/model_packages/bremen_v01/features.py` | **no scientific change**; add a frame-consuming entry (`build_bremen_features_from_frame`) that reuses the frozen `patient_lr_mean_metrics` / raw-peak / band functions verbatim |
| `src/bremen/api/workflow_bremen.py` | pass raw `container_path` through `ModelInput` (already done in PR0159); `execute` unchanged; ensure `predict_model` is called with the raw path |
| `src/bremen/api/workflow_orchestrator.py` | keep `_normalize_h5` for generic purposes; **Aramina**: move source/patient binding to the platform before package invocation (remove `_validate_aramina_source` reverse import) |
| `src/bremen/model_packages/aramina_v0213/inference.py` | remove `bremen.api.workflow_orchestrator` lazy import; accept a platform-provided binding callback/result via the runtime input instead |
| `src/bremen/model_packages/aramina_v0213/runtime.py` | `predict_model` accepts platform-verified source binding (patient/source integrity) from `ModelInput`; drop internal `_validate_aramina_source` call |
| `src/bremen/model_runtime.py` | update stale container_path comment; add optional `source_checksum` / `source_patient_id` binding fields to `ModelInput` (transport only) |

## 4. New production classes necessary?

- **One new production class**: the isolated worker is a new module but is
  script-like (mirrors the Aramina `aramina_preprocess_worker.py`).  The
  preprocessing orchestrator is a module of functions, not a new class.
- The runtime's raw-path science is an extension of the existing
  `BremenRuntime.predict_model` (existing class).
- **No new DTO family, no new retrieval/framework, no new repository layer.**

Total new production classes: **0** (two new modules, both function-based,
mirroring the Aramina precedent; the worker is invoked as a subprocess script).

## 5. Deterministic acceptance/rejection rule

- Authoritative raw-peak eligibility: `mean_peak_value_raw >= 0.6`
  (unchanged, package-owned, from the frozen `AnalysisConfig`).
- Nova_378 must reproduce `mean_peak_value_raw ≈ 0.46283992131551105`
  (tolerance appropriate to deterministic preprocessing, e.g. abs `1e-9`) and
  fail with `raw_peak_gate_failed`.
- Known-good Nova_227 (from `combined_archive.h5` / benign_one_patient): must
  produce the authoritative paper-reference probability
  `≈ 0.772694032994381` (the training-pipeline record), passing the gate, with
  `math.isclose(rel_tol=0, abs_tol=1e-10)`.
  (The legacy platform's stored-integration `0.98046` is NOT the paper
  reference value; the authoritative frozen training record for Nova_227 is
  `0.772694032994381`, as verified from the frozen training
  `train_all_predictions.csv`.)
- The frozen synthetic `bremen_3x3` fixture (integrated-profile boundary)
  continues to pass through the existing `build_bremen_features` path unchanged
  (the fixture is integrated profiles, not raw detector frames; the package
  feature science and estimator are unchanged, so `0.7388733541967353` remains
  exact for that boundary).

## 6. Positive-query behavior

Known-good paper-reference containers (e.g. Nova_227 from
`combined_archive.h5`) retrieve governed knowledge with correct citations —
unchanged (no RAG change in this PR).

## 7. Negative/unknown-term behavior

Not applicable to this PR (no retrieval relevance change).

## 8. Effect on citations/evidence

Not applicable to this PR (no RAG/citation change).

## 9. Tests to add/change

New file `tests/test_bremen_package_owned_preprocessing_pr0160.py`:

1. `test_package_preprocessing_is_used_not_platform` — patch the package
   preprocessing module; assert `BremenRuntime.predict_model` invokes it and
   the platform `h5_layouts`/`preprocessing_bridge` is NOT the feature source.
2. `test_authoritative_config_from_active_artifact` — `predict_model` reads
   `prediction_preprocessing_yaml` from the artifact; assert the release tag is
   `v0.1.7-beta` and the config matches the frozen 7-step pipeline.
3. `test_nova378_reproduces_authoritative_mean_peak_and_fails_gate` — using a
   deterministic temporary copy of the evidence H5 (root identity attrs added by
   the package adapter), assert `mean_peak_value_raw ≈ 0.46283992131551105`
   (abs `1e-9`) and the run fails `raw_peak_gate_failed`.
4. `test_nova227_authoritative_parity` — using `combined_archive.h5`
   (Nova_227 row subset) or the fixture evidence, assert the paper-reference
   probability `≈ 0.772694032994381` with `math.isclose(rel_tol=0, abs_tol=1e-10)`.
5. `test_frozen_synthetic_fixture_unchanged` — `build_bremen_features` on the
   `bremen_3x3` golden still yields `0.7388733541967353` (abs `1e-10`).
6. `test_legacy_container_compatibility_adapter` — a container without root
   `schema_version`/`format` (like Nova_378) is accepted by the package adapter
   (temporary read-only copy) and rejected upstream without it.
7. `test_aramina_no_bremen_api_import` — AST/import test proving
   `aramina_v0213` no longer imports `bremen.api.*`.
8. `test_aramina_source_binding_preserved` — platform-side source/patient
   binding still rejects mismatches with the same `h5_patient_contract`
   failure semantics.

Updated existing tests:

- `tests/test_bremen_model_runtime_contract_v1.py` — Bremen
  `predict_model` now takes raw container; the 3x3 synthetic fixture path uses
  the legacy integrated profile path (still supported for the frozen boundary),
  and the delegation fake is adjusted.
- `tests/test_aramina_v0213_package.py` / `tests/test_aramina_workflow_runtime.py`
  — update `_validate_aramina_source` monkeypatches to the new platform-bound
  input field.
- `tests/test_bremen_3x3_runtime_parity.py` — keep the frozen synthetic
  integrated-profile parity (unchanged boundary); add a raw-path parity test.

## 10. Runtime validation

1. `./venv/bin/python -m compileall -q src tests`
2. Focused Bremen package/runtime tests:
   `./venv/bin/python -m pytest -q tests/test_bremen_package_owned_preprocessing_pr0160.py tests/test_bremen_v01_package.py tests/test_bremen_model_runtime_contract_v1.py tests/test_bremen_3x3_runtime_parity.py`
3. Focused Aramina tests:
   `./venv/bin/python -m pytest -q tests/test_aramina_v0213_package.py tests/test_aramina_workflow_runtime.py`
4. Focused workflow/orchestrator tests affected by the source-validation move:
   `./venv/bin/python -m pytest -q tests/test_bremen_3x3_runtime_parity.py tests/test_bremen_fastapi_jobs_report_parity.py tests/test_aramina_workflow_runtime.py`
5. `./venv/bin/python -m pytest -q`
6. `./venv/bin/ruff check <all changed/new Python files>`
7. `git diff --check`
8. `git status --short` / `git diff` inspection

## 11. Boundary / non-goals

- No model coefficients, thresholds, gate, feature formulas, or estimator
  changes.
- No new generic platform scientific logic; `preprocessing_bridge.py`,
  `h5_layouts.py`, `symmetry_signals.py` remain for legacy/other functionality
  and are NOT deleted (deferred cleanup).
- No public endpoint, job, report, Standard Result v1, requirements API, or
  Aramina science changes.
- No MLflow, no third model, no async jobs.
- No commit/push/PR.

## 12. Evidence / provenance

- Authoritative artifact: `bremen_paper_reference_symmetry_logreg`
  `0.2.0-paper-reference`, SHA256
  `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0`.
- Artifact-owned preprocessing YAML: `prediction_preprocessing_yaml`,
  xrd-preprocessing `v0.1.7-beta` (commit `45d5568248e9774b7938a36e028d80e72b130b19`).
- Nova_378 evidence verified: `mean_peak_value_raw = 0.46283992131551105`,
  per-profile peaks reproduced exactly, gate fails.
- Nova_227 paper-reference record: probability `0.772694032994381`
  (frozen training `train_all_predictions.csv`), gate passes.
- The isolated worker environment mirrors the Aramina pinned-env pattern
  (`BREMEN_*_PREPROCESS_PYTHON` env var + `/opt/...` default; v0.1.7-beta only
  for Bremen, matching the artifact's release tag).
