# PRECOMMIT_REVIEW.md — PR0160 Model-Package-Owned Scientific Preprocessing (focused)

HEAD: `da1a7f3c0e784760221d729e3ec57a2840704fd4` (PR0159 is merged: `#221`)
Branch: `0160-model-package-owned-scientific-preprocessing`
Snapshot: `2026-09-16T22:31:36Z` · staging area empty (`git diff --cached` clean)

Diff = 11 modified tracked files + 3 untracked PR files
(`bremen_v01/preprocessing.py`, `bremen_v01/bremen_preprocess_worker.py`,
`tests/test_bremen_package_owned_preprocessing_pr0160.py`). All read in this session;
every claim below is backed by runtime-captured output or files physically read.

> NOTE: IMPLEMENTATION_REPORT.md claims `Dockerfile` was changed to add a separate
> commit-pinned `/opt/bremen-preprocess` venv. The current working tree shows `Dockerfile`
> byte-identical to HEAD (`git status`/`git diff` list only 11 files; `md5` of worktree == `git show HEAD:Dockerfile`),
> and `grep bremen-preprocess Dockerfile` → not found. The report's "Files changed" entry for
> Dockerfile is therefore not reflected in the tree. This is a deployment-side documentation/
> evidence mismatch (see W1), not an architectural violation, and the report itself discloses
> "Docker build itself was not run."

---

## RQ1 — Bremen raw-input ownership — PASS
- Orchestrator (`workflow_orchestrator.py` diff) resolves `requires_raw_container` from the
  provider/runtime, then for raw owners does **only** a staged-file SHA256
  (`hashlib.file_digest`) and an empty canonical carrier (`measurements=()`,
  `source_layout="raw_container"`); it does NOT call `_normalize_h5`/`detect_layout`.
  `test_orchestrator_passes_raw_source_without_platform_science` (in the new suite) patches those
  platform normalizers to `pytest.fail(...)` and still completes → platform scientific
  normalization is provably off the paper-reference path.
- `BremenRuntime._predict_from_raw_container` runs the package sequence: artifact
  `prediction_preprocessing_yaml` → `preprocess_bremen` (package) →
  `build_bremen_features_from_frame` (package `features.py`) → frozen gate → `score` → decide.
  H5 compat, preprocessing config, thickness correction (inside xrd-preprocessing), profile and
  feature construction, raw-peak gate, estimator — all under `model_packages/bremen_v01/`.
- `grep -rn "build_bremen_features|patient_lr_mean_metrics|mean_peak_value_raw" src/bremen/api`
  → only in the explicitly-out-of-scope legacy `preprocessing_bridge.py` / `symmetry_signals.py`
  (known debt; not on the active paper-reference path). Generic platform does not construct the
  supplied features.

## RQ2 — Authoritative preprocessing — PASS
- Driver is the **active artifact's** `prediction_preprocessing_yaml` (verified: real artifact has
  it, `release_tag=v0.1.7-beta`, `kind=bremen_paper_reference_model`, `has portable_logreg=True`).
- `preprocessing.SUPPORTED_RELEASES` pins only `v0.1.7-beta`→worker; `bremen_preprocess_worker.
  _validate_dependency` fails closed unless distribution version `0.1.7b0` AND commit
  `45d5568248e9774b7938a36e028d80e72b130b19` match (tested across good/bad commit, version, tag).
- Artifact SHA256 `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` is asserted in
  `_evidence()` before loading. No silent substitution of platform preprocessing: when
  `requires_raw_container` is true but path/config missing, it raises
  `raw_container_required`/`model_not_ready` (`test_raw_artifact_cannot_fall_back_to_integrated_profiles`).

## RQ3 — Nova_378 forensic regression — PASS
This reviewer re-ran the package path against the real `Nova_378.h5` + the evidence artifact:
```
mean_peak_value_raw = 0.46283992131551105   (== authoritative, abs 1e-10)
raw_peak_threshold  = 0.6
build_bremen_features_from_frame -> BremenFeatureError raw_peak_gate_failed
BremenRuntime.predict_model(...) -> ModelPreprocessingFailedError raw_peak_gate_failed
```
`git diff` on `features.py` shows no numeric change to the gate (`0.6` unchanged; only docstring
mentions it). Thickness correction was NOT moved into `preprocessing_bridge.py` (it stays inside the
isolated xrd-preprocessing worker). Gate behavior unchanged.

## RQ4 — Known-good parity — PASS (disclosed value basis)
- Re-ran package raw-H5 inference on a Nova_227 evidence archive extracted unchanged from
  `combined_archive.h5` (`calib_20250528_085450`, both Nova_227 samples + calibration):
```
probability = 0.7726940329943811   (isclose vs 0.772694032994381, rel_tol=0, abs_tol=1e-10 → True)
threshold   = 0.3585907282566089   (unchanged)
```
- This equals the frozen authoritative training record
  (`.../20260802T173549Z_6c8b029f/train_all_predictions.csv`, artifact SHA matches `65866f4…`).
- The task-quoted `0.9804625872094516` is the superseded *legacy platform stored-integration*
  value (it appears only in untracked runtime evidence under `results/`/`alexey-smoke-pack-0157/`,
  never in tracked fixtures). By PR0160's own premise the platform path was non-authoritative, so
  package ownership necessarily changes that number. The report **discloses** this rather than
  masking it; `test_nova227_raw_preprocessing_matches_frozen_training_record` asserts the
  authoritative value at abs 1e-10. Threshold is unchanged. See W2.

## RQ5 — Generic platform boundary — PASS
- Added generic lines contain no Bremen science: no H5 paths, no PONI, no q ranges, no
  `mean_peak_value_raw`, no 0.6/threshold values, no feature formulas. `grep` of added `src/bremen/api`
  + `model_runtime.py` lines → only generic `h5_path`/`container_path` transport tokens.
- `requires_raw_container` is a boolean capability; orchestrator branches on it generically.
- Legacy `preprocessing_bridge.py`/`h5_layouts.py`/`symmetry_signals.py`/`preflight.py` remain
  (allowed; out of scope) and are no longer on the active paper-reference path.

## RQ6 — Aramina dependency direction — PASS
- Reverse dependency removed: `inference.py` no longer imports `bremen.api.workflow_orchestrator`
  (deleted `_validate_aramina_source` shim + its call in `_prepare_features`).
- `test_packages_do_not_import_platform_api` AST-scans every `aramina_v0213/*.py` for `bremen.api`
  imports → passes; reviewer grep finds `bremen.api` only in module docstrings/comments, no code import.
- Source integrity + patient binding moved to platform provider (`workflow_aramina.py` calls
  `_validate_aramina_source` before `predict_model`). `test_aramina_platform_binding_precedes_package`
  proves the package is invoked ONLY on `binding=="match"`, and checksum/patient/missing-checksum
  mismatches yield `ARAMINA_UNSUPPORTED_INPUT`/`h5_patient_contract` without reaching the package.
  Aramina science (features/estimator/thresholds) untouched.

## RQ7 — Result contract — PASS
- `SourceMetadata`/`ModelMetadata`/`ModelMetrics` still defined on `RuntimePrediction`
  (`model_runtime.py:161/195/210/248-250`); `predict_model` still attaches all three from the
  PR0159 package adapter on the raw path.
- `model_result_mapper.py` and `standard_model_result.py` are NOT in the diff (unchanged); mapper
  remains generic with no new H5/artifact aliasing.

## RQ8 — Scope — PASS
- No preprocessing-bridge deletion demanded by the diff; no async/endpoint/Standard Result/
  retraining/MLflow/threshold changes. `git diff --name-only` shows none of those surfaces touched.

---

## Blockers
None. No concrete violation of the eight conditions in the current diff.

## Warnings (non-blocking)
- W1: IMPLEMENTATION_REPORT lists a Dockerfile change that is absent from the working tree; the
  pinned `/opt/bremen-preprocess` env is therefore not reproduced by this Dockerfile. Local evidence
  execution depends on `BREMEN_PREPROCESS_PYTHON` (used for this review) and report states Docker was
  never built. Reconcile the report/Docker before relying on containerized deployment.
- W2: The Nova_227 parity value is the authoritative training record `0.772694032994381`, not the
  task's stale platform-path `0.9804625872094516`. Disclosed and correct for PR0160's premise; flag
  so downstream integrators expecting `0.98046` are aware.

## Focused commands actually run
```
git rev-parse --verify HEAD ; git status --short ; git diff --cached  (clean) ; git diff --stat
git diff -- <8 generic/transport files>          → generic-only additions confirmed
grep h5py/H5-metadata tokens in added api lines  → none
BREMEN_PREPROCESS_PYTHON=... ./venv/bin/python  → Nova_378 mean_peak=0.46283992131551105,
                                                   gate 0.6 -> raw_peak_gate_failed
                                                   Nova_227 p=0.7726940329943811 (abs1e-10), thr unchanged
./venv/bin/python -m compileall -q src tests     → exit 0
./venv/bin/python -m pytest -q                   → 4359 passed, 13 skipped
BREMEN_EVIDENCE_* ./venv/bin/python -m pytest -q tests/test_bremen_package_owned_preprocessing_pr0160.py
                                                 → 31 passed (incl. both real-evidence regressions)
./venv/bin/ruff check <13 changed/new files>     → All checks passed
git diff --check                                 → clean
```

---

# RE-REVIEW (targeted) — 2026-09-17

Scope: only the two requested items. Architecture not re-reviewed; full suite not rerun.

## Check 1 — Dockerfile builds `/opt/bremen-preprocess` — PASS
`git diff -- Dockerfile` now adds exactly (lines 75-77):
```
    python -m venv /opt/bremen-preprocess && \
    /opt/bremen-preprocess/bin/pip install --no-cache-dir \
        "xrd-preprocessing @ git+https://github.com/Eos-Dx/XRD-preprocessing.git@45d5568248e9774b7938a36e028d80e72b130b19" && \
```
- Builds `/opt/bremen-preprocess/bin/python` (matches `preprocessing.SUPPORTED_RELEASES` default path).
- Pinned to commit `45d5568248e9774b7938a36e028d80e72b130b19` (matches the worker's fail-closed
  `_validate_dependency` commit + the training-pipeline `direct_url.json` observed in the prior review).
- Aramina environments UNCHANGED: `git diff HEAD -- Dockerfile | grep '^[+-].*aramina'` → no output;
  `/opt/aramina-preprocess` (v0.1.7-beta) and `/opt/aramina-preprocess-019` (v0.1.9-beta) are context-only.
- W1 from the first review is resolved.

## Check 2 — Scientific regressions remain — PASS
Code: `features.py:59` `raw_peak_threshold = 0.6` unchanged.
Tests (physically read):
- `:194` `assert mean == pytest.approx(0.46283992131551105, rel=0, abs=1e-10)`
- `:195` `assert AnalysisConfig().raw_peak_threshold == 0.6`
- `:196/:198` `raw_peak_gate_failed` on both feature build and runtime
- `:207-208` Nova_227 `math.isclose(prob, 0.7726940329943811, rel_tol=0, abs_tol=1e-10)`
No attempt to restore the stale `0.9804625872094516`: the only occurrence in `src`/`tests` is a
comment labeling it as the superseded platform path (`:206`); no code asserts or returns it.

Focused runs (against real evidence copies + pinned interpreter):
```
pytest -q tests/test_bremen_package_owned_preprocessing_pr0160.py -k "nova378 or nova227" → 2 passed
pytest -q tests/test_bremen_package_owned_preprocessing_pr0160.py                          → 32 passed
git diff --check / git diff --cached --check                                               → clean (exit 0)
```
Full suite not rerun (focused validation passed).

W2 remains as a disclosure note only (authoritative Nova_227 value `0.772694032994381`, not the
legacy platform `0.98046`); it is expected and does not violate any check.

READY FOR COMMIT
