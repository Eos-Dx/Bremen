# PR0160 implementation report

Status: implementation complete, research draft. No staging, commit, deployment,
model retraining, or clinical-validation claim. This report supersedes the
provisional PLAN.md where the implementation differs.

## Work found and completed

The working tree already contained a provisional Bremen worker/runtime migration,
Aramina changes, and tests. The orchestrator still scientifically normalized the
raw source, the provider still required canonical profiles before invoking the
runtime, and ordinary tests unconditionally loaded an artifact from a
developer's filesystem. These implementation gaps are resolved. W1 now adds
the isolated Bremen worker environment to the production Dockerfile. Removed
the provisional no-op Aramina binding hook and unnecessary
package-side binding carrier; real binding is now unconditional on the platform.

## Execution path

Before:

`POST /jobs -> source materialization -> run_workflow_request -> _normalize_h5
-> h5_layouts.normalize_bremen_to_canonical -> platform profiles -> BremenProvider
-> BremenRuntime -> package feature/gate/estimator -> RuntimePrediction -> report`

After, for the paper-reference artifact:

`POST /jobs -> existing source resolution/materialization -> provider selection
-> staged-file SHA256 (no H5 scientific parsing) -> BremenProvider
-> ModelInput(container_path=raw staged H5) -> BremenRuntime
-> package compatibility adapter -> artifact prediction_preprocessing_yaml
-> pinned xrd-preprocessing build_pipeline_from_config(...).fit_transform(...)
-> package 3 LEFT / 3 RIGHT and single-patient checks -> frozen 15 features
-> unchanged raw peak gate -> unchanged portable estimator and decision threshold
-> RuntimePrediction -> existing generic mapper/report lifecycle`

The orchestrator consumes a generic `requires_raw_container` capability exposed
by the provider from its runtime. It does not inspect YAML, H5 paths, thresholds,
or scientific field aliases. Its empty canonical carrier records checksum and
raw-source provenance only; it does not supply scientific measurements.

Successful measurement counts are returned by the package after its shape gate
and translated into the existing workflow payload fields. The PR0159 normalized
SourceMetadata/ModelMetadata/ModelMetrics extraction remains package-owned. The
Standard Result mapper was not modified.

## Authoritative preprocessing and provenance

- Training contract: `c98a950d3fbf0db72d87f2ecd977d80fe35da9e4`.
- Artifact name/version: `bremen_paper_reference_symmetry_logreg`,
  `0.2.0-paper-reference`.
- Evidence artifact SHA256 verified by the integration tests:
  `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0`.
- The exact artifact YAML is passed to the worker; no replacement pipeline,
  thickness formula, calibration formula, normalization, or threshold is defined
  by platform code.
- Dependency: xrd-preprocessing `v0.1.7-beta` / distribution `0.1.7b0`, commit
  `45d5568248e9774b7938a36e028d80e72b130b19`.
- The production Dockerfile now creates `/opt/bremen-preprocess` and installs
  the exact commit above using its own pip, following the existing Aramina
  isolated-venv pattern. `/opt/bremen-preprocess/bin/python` is the runtime
  default; `BREMEN_PREPROCESS_PYTHON` remains an explicit local/test override.
  The platform-global dependency installation and both Aramina environments
  are unchanged. The worker requires the distribution version and exact commit
  in `direct_url.json`, failing closed on a mismatch or absent provenance.
- The local evidence run used the training checkout's isolated interpreter;
  its installed version and commit were inspected and match these values.
- W1 explicitly authorizes this Dockerfile correction. The production build
  now provisions the environment; an actual Docker image build was not run.
  Unit tests verify default/override interpreter selection without Docker.

## Legacy compatibility

Canonical `xrd-session` and `xrd-session-archive` schema 0.3 inputs pass directly
to the upstream reader. For the established `/session` layout with missing root
identity attributes, only the package creates a temporary copy and adds missing
`format=xrd-session` and `schema_version=0.3`. Conflicting identity values are
rejected. Original staged bytes are never mutated; temporary files are removed.
No broader legacy-layout compatibility is claimed.

Legacy artifacts without raw preprocessing retain their integrated-profile
route. Paper-reference artifacts cannot fall back to that route when the raw
path or artifact configuration is missing. The frozen synthetic profile
probability remains unchanged within absolute tolerance `1e-10`.

## Scientific evidence

Nova_378: six corrected peaks reproduced within absolute tolerance `1e-10`:

| Side / position | Peak |
| --- | ---: |
| Right P1 | 0.3635513484477997 |
| Right P2 | 0.355907678604126 |
| Right P3 | 0.49898195266723633 |
| Left P1 | 0.42200028896331787 |
| Left P2 | 0.459202378988266 |
| Left P3 | 0.6773958802223206 |

`mean_peak_value_raw = 0.46283992131551105`; both feature construction and the
runtime reject it with `raw_peak_gate_failed`. The raw peak threshold remains
`0.6`. Evidence uses the pre-existing forensic H5 copy in the temporary directory;
macOS denied access to the Downloads originals even outside the sandbox. A
separate temporary copy with the two root identity attributes removed also
exercises the package adapter and verifies that original input bytes remain
unchanged. These are real evidence copies, not invented detector data.

Nova_227: the real patient sessions and associated calibration were extracted
unchanged from the existing training `combined_archive.h5` into a temporary
archive. Package raw-H5 inference matches the frozen training record
`0.7726940329943811` with `math.isclose(rel_tol=0, abs_tol=1e-10)`. The decision
threshold remains `0.3585907282566089`.

W2 confirms the forensic distinction: the old platform-owned scientific path
produced approximately `0.9804625872094516`; the independently reproduced
package-owned path produces approximately `0.7726940329943811`. The latter is
PR0160's authoritative parity baseline. The frozen training CSV records the
rounding-equivalent `0.772694032994381`. No model, preprocessing, feature, or
threshold was changed to recover the superseded platform result. PR0160-owned
references were inspected; the old value remains only as historical explanation.
Unrelated historical evidence and PRECOMMIT_REVIEW.md were not modified.

No private H5, raw profiles, or model artifacts were added to the repository.
Real evidence tests are opt-in using `BREMEN_EVIDENCE_ARTIFACT`,
`BREMEN_EVIDENCE_NOVA378`, `BREMEN_EVIDENCE_NOVA227`, and
`BREMEN_PREPROCESS_PYTHON`. Ordinary tests use existing deterministic synthetic
profile fixtures for wiring only; they do not claim synthetic H5 science parity.

## Aramina boundary cleanup

Removed `inference.py -> bremen.api.workflow_orchestrator` and the package's
source-binding hook entirely. The platform provider validates/normalizes request
fields, checks staged SHA256 and patient binding, then invokes the package.
Empty or incorrect checksums do not bypass verification. Mismatches retain
`ARAMINA_UNSUPPORTED_INPUT` / `h5_patient_contract`. The model package's
preprocessing, scientific feature construction, estimator, and thresholds are
unchanged. AST tests inspect all Aramina package Python modules for API imports.
Existing workflow tests plus new ordering/integrity tests preserve behavior.

## Validation

- `./venv/bin/python -m compileall -q src tests`: passed.
- Focused Bremen, Aramina, runtime/provider, Standard Result and PR0159 metadata
  tests: 507 passed, 2 optional evidence tests skipped (before the final
  measurement-count projection adjustment; final full suite covers it).
- PR0160 suite with real evidence and exact pinned dependency: 32 passed
  (W1/W2 correction pass).
- `./venv/bin/python -m pytest -q`: 4360 passed, 13 skipped,
  1676 warnings in 55.93 seconds (W1/W2 correction pass).
- Ruff over every changed/new Python file: passed.
- `./venv/bin/ruff check .`: 354 existing findings outside changed/new Python
  files. Unrelated repository lint cleanup is deferred.
- `git diff --check`: passed; `git diff` and `git status --short` inspected.

## Files changed

- `Dockerfile`: W1 adds the separate commit-pinned Bremen preprocessing venv.

- `src/bremen/api/workflow_orchestrator.py`: route raw-source owners around
  scientific normalization; document platform binding.
- `src/bremen/api/workflow_bremen.py`: raw-input delegation and existing count
  projection from model output.
- `src/bremen/api/workflow_aramina.py`: platform-side source binding.
- `src/bremen/model_packages/bremen_v01/preprocessing.py`: new pinned worker bridge.
- `src/bremen/model_packages/bremen_v01/bremen_preprocess_worker.py`: new upstream
  pipeline execution and temporary legacy adapter.
- `src/bremen/model_packages/bremen_v01/features.py`: authoritative frame entry
  point, single-patient/shape validation, unchanged mathematical sequence.
- `src/bremen/model_packages/bremen_v01/runtime.py`: complete raw-container route.
- `src/bremen/model_packages/bremen_v01/manifest.py`: corrected input note.
- `src/bremen/model_packages/aramina_v0213/inference.py`: remove reverse dependency.
- `src/bremen/model_runtime.py`, `docs/model_runtime_contract_v1.md`: correct stale
  raw-container ownership comments without changing contract fields.
- `tests/test_bremen_package_owned_preprocessing_pr0160.py`: new portable and
  opt-in scientific regressions.
- `tests/test_aramina_v0213_package.py`,
  `tests/test_bremen_model_runtime_contract_v1.py`: move platform binding mocks
  to the actual platform seam.
- This implementation report.

## Deferred legacy code / limitations

`api/preprocessing_bridge.py`, `api/h5_layouts.py`, and
`api/symmetry_signals.py` remain for legacy/other paths, but are no longer the
scientific source for paper-reference inference. Bremen's existing decision
vocabulary import from `api.decision_contract` is unchanged; removing that
separate non-preprocessing bridge is outside this task. Existing Aramina science
and canonical normalization behavior remain unchanged.

The pre-existing untracked `alexey-smoke-pack-0157/` and `results/` were not
modified. No endpoint/job/Standard Result redesign, threshold change, MLflow
work, stage, commit, or deployment was performed. Research draft only;
requires radiologist review, not clinically validated by these software tests.

## Focused precommit correction (W1 / W2)

The new explicit W1 request supersedes the earlier Dockerfile scope restriction.
This pass changes only Dockerfile, the PR0160 regression test file, and this
report. Runtime interpreter selection was already correct and required no code
change. No scientific logic was moved back into generic platform code.

Correction-pass validation (2026-09-17):

- Compileall over `src tests`: passed.
- PR0160 tests without private-evidence variables: 30 passed, 2 skipped.
- Focused default/override interpreter-selection tests: 2 passed.
- PR0160 tests with real pinned interpreter and both real H5 evidence inputs:
  32 passed. Nova_378 mean remains `0.46283992131551105` within `1e-10`, with
  unchanged `0.6` gate and `raw_peak_gate_failed`. Nova_227 matches
  `0.7726940329943811` with `rel_tol=0, abs_tol=1e-10`; threshold remains
  `0.3585907282566089`.
- Full pytest: 4360 passed, 13 skipped, 1676 warnings in 55.93 seconds.
- Ruff over every changed/new Python file: passed. Repository-wide Ruff still
  reports 354 unrelated existing findings; no broad cleanup performed.
- Dockerfile diff inspected and mechanically checked: removing only the three
  added Bremen-venv lines reproduces HEAD byte-for-byte. Global installation,
  both Aramina environments, and the smoke build target are unchanged.
- `git diff --check`: passed. Full diff and status inspected. PRECOMMIT_REVIEW.md
  SHA256 is unchanged. No staging or commit.
- No implementation blockers. Actual Docker image build/publish was not run;
  the production build recipe now provisions the required environment.
