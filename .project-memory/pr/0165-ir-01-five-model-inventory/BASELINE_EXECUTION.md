# BASELINE_EXECUTION.md — IR-01 real local baseline matrix

**Headline: real execution was achieved in this pass.** A genuine
Python 3.13 interpreter was obtained (see "Environment" below), and all
five model artifacts were executed against real local H5 fixtures
through the **existing, unmodified** Bremen/Aramina controlled runtime
(`bremen.platform.runtime.executor.execute`, checksum-verified artifact
loading, the real preprocessing subprocess workers). **91 real
executions ran: 50 completed, 41 failed with typed/expected safe
reasons, 0 unexpected exceptions, 0 crashes.** No new inference logic
was written; no model artifact or fixture was modified; no raw pickle
was loaded outside the existing controlled boundary.

**Provenance caveat (added 2026-10-21, precommit review):**
`/tmp/bremen-ir01-models` and `/tmp/bremen-ir01-fixtures` are described
throughout this document only as **operator-supplied local copies**.
Their artifact *integrity* is independently verified here (SHA256
self-consistency against each artifact's own manifest; see
`INVENTORY_EVIDENCE.md` §9), and the execution results below are real,
reproducible outputs of running the existing controlled runtime against
these specific local files. Neither fact establishes **source
provenance** — no export session, S3 endpoint, authorization context,
or immutable S3 object-version ID was captured to confirm these are the
exact objects currently (or ever) served from the live catalog. Treat
every result below as "this local file, run through the existing
runtime, produced this output," not as "the live App Runner service
produces this output."

## Environment (how the Python 3.13 blocker was actually resolved)

The task's own fallback path applied: *"If the repository venv is
broken, use a temporary environment outside the repository if a valid
Python 3.13 interpreter is available."* A valid interpreter was not
initially available (`python3.13` absent; only Homebrew `python3.10`
and `python3.14` present; the repo's own `venv/bin/python3.13` is a
dangling symlink — same finding as the two prior IR-01 passes). It was
then **made available**, outside the repository, with no dependency
file edited:

```
$ uv python install 3.13
Installed Python 3.13.12 in 650ms
 + cpython-3.13.12-macos-aarch64-none (python3.13)
```

(`uv` itself was already present on this machine at
`/opt/homebrew/bin/uv`; it downloads a standalone CPython build into
`~/.local/share/uv/python/`, outside this repository and outside its
`venv/`.)

A disposable venv was then built from that interpreter, and the
repository's own `pyproject.toml` dependency list was installed into it
by reading (never editing) that file:

```
$ /Users/alexred/.local/share/uv/python/cpython-3.13.12-macos-aarch64-none/bin/python3.13 -m venv /tmp/bremen-ir01-exec-venv
$ /tmp/bremen-ir01-exec-venv/bin/python -m pip install --quiet "."     # from the repo root; installs bremen + its pyproject deps
$ /tmp/bremen-ir01-exec-venv/bin/python -m pip install --quiet pytest pytest-cov httpx
```

Three further disposable venvs were built the same way, mirroring the
Dockerfile's own three dedicated preprocessing environments (none of
this edits `Dockerfile`, `pyproject.toml`, or any other forbidden
file — each is an independent `pip install` target choice in a
throwaway venv outside the repo):

```
$ /tmp/bremen-ir01-preprocess-017b  # xrd-preprocessing pinned to the EXACT commit
                                     # 45d5568248e9774b7938a36e028d80e72b130b19
                                     # (BREMEN_PREPROCESS_PYTHON target)
$ /tmp/bremen-ir01-preprocess-017   # xrd-preprocessing @ tag v0.1.7-beta
                                     # (BREMEN_ARAMINA_PREPROCESS_PYTHON target)
$ /tmp/bremen-ir01-preprocess-019   # xrd-preprocessing @ tag v0.1.9-beta
                                     # (BREMEN_ARAMINA_PREPROCESS_019_PYTHON target)
```

**Why the exact-commit venv was necessary (a real, reproducible
finding):** `src/bremen/model_packages/bremen_v01/bremen_preprocess_worker.py`'s
`_validate_dependency` hard-checks the *installed* `xrd-preprocessing`
distribution's version AND its pip `direct_url.json` VCS commit against
the literal constant `45d5568248e9774b7938a36e028d80e72b130b19`.
Installing by the **tag** `v0.1.7-beta` resolved to a *different*
commit on this date:

```
$ pip install "xrd-preprocessing @ git+...@v0.1.7-beta"
  -> version: 0.1.7b0
  -> direct_url.json commit_id: 1c03a06488e0c56297f49c060dfc69ccce4704c7   # NOT the pinned commit

$ pip install "xrd-preprocessing @ git+...@45d5568248e9774b7938a36e028d80e72b130b19"
  -> version: 0.1.7b0
  -> direct_url.json commit_id: 45d5568248e9774b7938a36e028d80e72b130b19   # matches
```

This is a live reproduction of the exact concern already recorded in
`docs/inference-releases/operations.md` ("the current preprocessing
worker checks version `0.1.7b0` plus VCS commit `45d5568...` through
`direct_url.json`... wheel installation has different provenance
metadata"). It means **the `v0.1.7-beta` git tag has moved since the
artifact's provenance pin was recorded** — a genuine, reproducible
provenance-drift finding, not a bug in this task's harness. Installing
the exact commit SHA (itself already a value recorded in the B2
artifact's own embedded `prediction_preprocessing_yaml` provenance
block) resolved it for this session only; no repository file was
changed to work around it.

Environment variables set (process-local to this session; no
dependency file touched):

```
BREMEN_PREPROCESS_PYTHON=/tmp/bremen-ir01-preprocess-017b/bin/python
BREMEN_ARAMINA_PREPROCESS_PYTHON=/tmp/bremen-ir01-preprocess-017/bin/python
BREMEN_ARAMINA_PREPROCESS_019_PYTHON=/tmp/bremen-ir01-preprocess-019/bin/python
```

## Controlled execution path used (no new inference logic)

Every execution in this matrix went through the **existing, unmodified**
top-level orchestration function
`bremen.platform.runtime.executor.execute(request, registry=...)`,
exactly as the real job service would call it, with:

- the model package loaded via the existing checksum-then-load boundary
  (`bremen.model_packages_bridge.load_staged_artifact` for Bremen;
  `aramina_v0213.inference._load_selected_artifact` internally, for
  Aramina, invoked through a `RegistryModelEntry` pointing
  `_artifact_path`/`_checksum` at the local artifact — the same fields
  the real S3-backed registry populates);
- a fresh `bremen.platform.runtime.registry.RuntimeRegistry()` per run,
  with exactly one `bremen_descriptor(...)` or `aramina_descriptor(...)`
  registered — no platform/registry code was modified, only
  instantiated with local inputs;
- `bremen.contracts.execution.ExecutionRequest(container_path=<local h5>, workflow_id=..., model_id=..., patient_id=..., target_side=...)`
  as the request, identical in shape to a real job request.

No raw `joblib.load` was called directly on any artifact outside this
chain. No H5 array data was read outside the existing H5 reader
transformers. No scientific code was edited or re-implemented; the
harness script
(`/private/tmp/.../scratchpad/baseline_harness.py`, outside the repo)
only wires existing objects together and records their results.

## Model/fixture matrix executed

91 executions: 63 Bremen (21 fixtures × 3 models) + 28 Aramina (7
fixtures × 2 models × 2 target sides). Fixtures were selected to cover
each unique patient identity found in `FIXTURE_INVENTORY.md` plus the
known legacy-layout-incompatible file and the file matching a previously
captured production result, rather than running all 49×5 combinations
(many of the 49 files share patient identity — see
`FIXTURE_INVENTORY.md`'s dedup table — so this is a representative, not
exhaustive, sweep per the task's instruction not to force every fixture
through every model unnecessarily).

### Result totals per model

| Slot | Runs | Completed | Failed (typed/expected) | Unexpected |
|---|---|---|---|---|
| A1 | 14 | 8 | 6 | 0 |
| A2 | 14 | 8 | 6 | 0 |
| B1 | 21 | 8 | 12 + 1 normalization_failed | 0 |
| B2 | 21 | 11 | 10 | 0 |
| B3 | 21 | 15 | 6 | 0 |
| **Total** | **91** | **50** | **41** | **0** |

Zero unexpected exceptions across all 91 runs — every non-success
outcome mapped cleanly onto an existing typed/safe failure reason
already defined in the runtime contract.

## Successful baselines (selected, with scientific output)

### B2 (`bremen-paper-reference-v0-2-0`) — `benign_one_patient.h5` (Nova_227)

```
execution_status=completed
probability=0.7726940329943811
threshold_applied=0.3585907282566089
prediction=1  triage_recommendation=CONTINUE_MRI
left_measurement_count=3  right_measurement_count=3
duration_s=1.6
```

**This exactly reproduces the existing PR0160 golden reference value
`0.7726940329943811`** recorded in
`docs/inference-releases/parity-and-rollout.md` — bit-for-bit, not just
within tolerance. This is strong, real evidence that the local artifact
+ local fixture + the existing controlled runtime, run end-to-end on
this machine, reproduce the documented scientific baseline exactly.

### A1 / A2 — `eoscloud-staging/cabce03d-f9c4-43db-91d1-aec20007ee18.h5` (Nova_214), `target_side=left`

```
A1: probability=0.8693870739736473  threshold=0.24665932038818544
A2: probability=0.8693870739736473  threshold=0.24665932038818544
```

**This file is the exact `container_id` already captured in
`results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`**
(A2, `target_side=left`, previously captured production
`risk_probability=0.869387073973647`). The locally reproduced value
(`0.8693870739736473`) is the same float at full vs. truncated display
precision — an exact match to the real, previously captured production
result, now independently reproduced end-to-end on this machine from
the local artifact.

### B1 (`bremen-mri-triage-logreg-v0-1`) — threshold question resolved

B1's `manifest.json` (local artifact, see `IMPLEMENTATION_REPORT.md`
continuation) declares `threshold_value: -1` /
`"threshold_version": "unconfirmed_placeholder"`. **No threshold was
invented for this task.** Direct execution shows the real runtime never
reads that manifest field — the actual applied threshold comes from the
value embedded inside the joblib artifact's own `portable_logreg`
block, and is applied correctly:

```
benign_one_patient.h5:  probability=0.8524639494195422  threshold_applied=0.3640352477169748
Nova_376.h5:            probability=0.5677291934209037  threshold_applied=0.3640352477169748
```

`0.3640352477169748` matches the threshold already recorded in
`docs/production-contracts-2026-09-18.md` §3.1 for this exact model_id.
The manifest's placeholder field is simply unpopulated sidecar metadata,
not evidence that the runtime is using an unconfirmed value.

### B3 (`bremen-v0-2-0-symmetry-candidate`) — distinct from B2, confirmed by execution

```
benign_one_patient.h5:  probability=0.6848549443589647  threshold_applied=0.4130396520921527
cancer_one_patient.h5:  probability=0.4709477140107444  threshold_applied=0.4130396520921527
```

Both the probability values and the applied threshold
(`0.4130396520921527`, matching B3's own manifest/description) are
different from B2's output on the same fixtures — further execution
confirmation (beyond the artifact-metadata confirmation already
recorded in the prior pass) that B3 is a real, independently-behaving
model, not a relabeled B2. **B3's exploratory-label safety status
(`exploratory_proxy_not_clinically_reviewed`, recorded in the prior
pass) is carried forward** — these are real numeric outputs from a
real but explicitly unreviewed model; do not treat them as having B2's
validation status.

## Expected / typed failures (not bugs)

| Category | Count | Example | Mechanism |
|---|---|---|---|
| `qc_rejection` (raw_peak_gate) | 20 | B1/B2 on `cancer_one_patient.h5`, `Nova_378/383/384.h5`, several `eoscloud-staging` files | `Feature construction failed: raw_peak_gate_failed` — the existing package-owned scientific gate already documented in `docs/production-contracts-2026-09-18.md` §3.2. Not a defect; a designed rejection. |
| `preprocessing_failure` (Aramina, artifact-declared release) | 8 | A1/A2 both sides on `Nova_376.h5`, `Nova_384.h5` | `ARAMINA_UNSUPPORTED_INPUT` / `failure_stage=preprocessing_contract`. Root-caused by direct worker invocation for the already-known `Nova_384` case: `exception_class=ValueError`, `transformer=H5PoniGeometryCalculatorTransformer` — the same transformer/exception already recorded in `docs/production-contracts-2026-09-18.md` §4.3/4.4 for this exact fixture. Reproduced, not newly discovered. |
| `preprocessing_failure` (Bremen, generic safe mapping) | 5 | B2 on `Nova_103_.h5`; B2/B3 on a few `eoscloud-staging` files (e.g. Nova_101, Nova_423) | `Feature construction failed: invalid_scientific_profiles`. Direct worker invocation (bypassing the Model-Runtime-Contract safe wrapper, same technique as the prior environment diagnosis) shows concrete sub-causes: for `Nova_103_.h5`, `"Unsupported container identity"` (legacy `detector_scoped_v1` layout, as predicted in `FIXTURE_INVENTORY.md`); for `eoscloud-staging/07ff0a20-...h5` (Nova_101), `{"stage": "worker_pipeline_execution", "exception_class": "IndexError", "transformer": "AzimuthalIntegration"}` — a real preprocessing-stage failure in the azimuthal-integration step for that specific measurement geometry, not a layout issue. The Model Runtime Contract boundary intentionally collapses both into the same safe public reason (`invalid_scientific_profiles`); this is existing, deliberate safety-by-design (never leaking exception text), not something this task changed or should change. |
| `feature_schema_failure` (post-preprocessing shape gate) | 3 | B3 on `atypical_one_patient.h5`, `Nova_379.h5`, `Nova_384.h5` | `Incompatible: requires_exactly_3_left_3_right`. B3's embedded preprocessing config sets `integration.thickness_correction.require_sample_thickness: true` (unlike B2's `false`) — rows missing `sample_thickness_mm` are dropped by the worker, which can reduce a side below 3 measurements, triggering the existing structural shape gate after preprocessing rather than before it. Config difference already recorded in `INVENTORY_EVIDENCE.md`'s prior-pass local-artifact section; this execution confirms its real effect. |
| `patient_identity_mismatch` (`h5_patient_contract`) | 4 | A1/A2 both sides on `Nova_103_.h5` | `ARAMINA_UNSUPPORTED_INPUT` / `failure_stage=h5_patient_contract` — the legacy-layout file has no resolvable `session/sample/patient_name`/`patientId`, so Aramina's canonical patient-identity check rejects it before preprocessing is attempted at all. |
| `input_incompatible` (normalization ambiguous) | 1 | B1 on `eoscloud-dev/3e7c88e2-...h5` (Nova_402, the 6+6 doubled-measurement-type file) | `execution_status=normalization_failed` (no typed `result_error`; `normalize_legacy_input` itself raised before reaching the model runtime). B1 is the only model using the legacy canonical adapter directly on this file; it could not resolve the ambiguous doubled `sample_main`/`sample_transmission` structure. |

### Categories not exercised in this sample

- **`target_side unavailable`**: not observed. Every resolvable fixture
  in the 49-file set has both sides present (see `FIXTURE_INVENTORY.md`
  side-count table); no single-sided fixture was found to exercise this
  path.
- **`model_configuration_incomplete`**: not triggered as a distinct
  failure in this run (all five artifacts loaded and passed their own
  readiness checks); see the B1 threshold discussion above for the
  related-but-resolved placeholder-metadata question.
- **`inference_failure`** (estimator-level, as opposed to
  preprocessing-level): not distinctly observed; every failure in this
  sample occurred before or at feature construction, not inside the
  scikit-learn estimator call itself.

## A real, notable cross-model finding (not a bug fix — a recorded observation)

**`Nova_103_.h5` (legacy `detector_scoped_v1` layout) is accepted by B1
but rejected by B2, B3, A1 and A2.** B1 uses the older legacy canonical
adapter (`normalize_legacy_input`, which supports this older layout
family), while B2/B3 use the newer raw-container pipeline whose
`container_requirements.json` explicitly lists
`detector_scoped_v1` as unsupported, and Aramina's canonical patient-
identity check rejects the file outright. This means **the five
deployed variants do not currently share one uniform input-layout
compatibility contract** — a real, repository-independent fact
established by direct execution, not an inference from documentation.
This is recorded here as an IR-01 inventory fact for IR-02+ to account
for explicitly (e.g. in the release manifest's compatibility
declarations); this task does not change or recommend changing any of
the three behaviors.

## Validation commands and results

```
$ python -m compileall -q src tests
(eval):3: command not found: python
exit code: 127

$ python3 -m compileall -q src tests     # system python3, no deps
(no output)
exit code: 0

$ /tmp/bremen-ir01-exec-venv/bin/python -m compileall -q src tests   # working Python 3.13 + full deps
(no output)
exit code: 0

$ /tmp/bremen-ir01-exec-venv/bin/python -m pytest -q
3975 passed, 8 skipped, 40 warnings in 22.32s
exit code: 0

$ git diff --check
(no output)
exit code: 0

$ git status --short
 M docs/inference-releases/five-model-inventory.md
 M docs/inference-releases/operations.md
 M docs/inference-releases/parity-and-rollout.md
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? .project-memory/pr/0165-ir-01-five-model-inventory/
?? results/
?? testing_results/

$ git diff --stat
 docs/inference-releases/five-model-inventory.md | 200 +++++++++++++++++++++---
 docs/inference-releases/operations.md           |  41 +++++
 docs/inference-releases/parity-and-rollout.md   |  23 +++
 3 files changed, 246 insertions(+), 18 deletions(-)
```

**The full 3975-test repository suite passes with exit code 0** using
the disposable Python 3.13 environment described above — this is the
authoritative validation result for this task (the repo's own broken
`venv` and bare system `python3` remain unusable, as recorded in both
prior IR-01 passes, but are no longer the blocking constraint once a
real 3.13 interpreter is provisioned outside the repository).

## Remaining IR-01 blockers (after this pass)

1. **Live catalog/App Runner re-confirmation** — unchanged from the
   prior pass. All execution in this task is local; no live AWS/S3/App
   Runner call was made, and none of this task's results constitute
   "App Runner verification" per the HARD RULES.
2. **`/tmp/bremen-ir01-models` and `/tmp/bremen-ir01-fixtures`
   provenance** — still not independently established; both were
   supplied as task input.
3. **B3 exploratory-label clinical review status** — unchanged; real
   numeric outputs now exist (this pass), but the label itself remains
   `exploratory_proxy_not_clinically_reviewed` per the prior pass's
   finding, and that status is not altered by running the model.
4. **The `v0.1.7-beta` xrd-preprocessing tag currently points to a
   different commit than the artifact's provenance pin expects** — a
   newly confirmed, reproducible finding in this pass (see
   "Environment" above). This affects reproducibility outside this
   session's workaround (installing the exact commit SHA) and should
   be raised to whoever owns the `XRD-preprocessing` repository's
   tagging practice; this task does not and must not fix it (no
   dependency file was edited).
5. **Resource/cost/App-Runner-sizing evidence** — unaffected by this
   pass; still outstanding exactly as recorded previously.
6. The exact underlying cause of each individual
   `invalid_scientific_profiles` occurrence was not exhaustively
   root-caused for all 8 instances in this category — two
   representative cases were diagnosed (`Nova_103_.h5` legacy layout;
   `eoscloud-staging/07ff0a20-...h5` AzimuthalIntegration IndexError);
   the remainder are recorded only at the safe-category level, per the
   runtime's own intentional error-sanitization boundary.

## IR-01 gate status: **still BLOCKED**, materially advanced

Checksums, thresholds, feature schemas, and now **real local scientific
execution with 50 real completions and 0 unexpected failures** are
established for all five models. What remains for PASS: live
catalog/App-Runner re-confirmation, resource/cost measurement under the
actual production topology, and B3's clinical review status — none of
which this local session can provide. Per the task's own instruction
("do not claim App Runner verification from local execution"), this
pass explicitly does not claim the gate is satisfied.

## Instructions for the Precommit Reviewer

1. The disposable environments referenced here
   (`/tmp/bremen-ir01-exec-venv`, `/tmp/bremen-ir01-preprocess-017`,
   `-017b`, `-019`, `/tmp/bremen-ir01-h5meta-venv`) are outside the
   repository and were not committed; they may or may not still exist
   on this machine when reviewed. Reproducing them requires: `uv python
   install 3.13`; `pip install .` (repo root) into a fresh venv from
   that interpreter; and the two additional `xrd-preprocessing`
   installs (exact commit for Bremen, tags for Aramina) with the three
   `BREMEN*_PREPROCESS*_PYTHON` environment variables set as shown
   above.
2. Independently confirm at least one result in this document against
   its cited source: the B2/`benign_one_patient.h5` probability against
   `docs/inference-releases/parity-and-rollout.md`'s PR0160 reference,
   and/or the A1-A2/`cabce03d-...h5` probability against
   `results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`.
3. Confirm no file under `src/`, `tests/`, `Dockerfile`, `.github/`,
   `infra/`, `pyproject.toml`, or `requirements.txt` was modified
   (`git status --short` / `git diff --stat` above).
4. Confirm no `.h5` or `.joblib` file was copied into the repository.
