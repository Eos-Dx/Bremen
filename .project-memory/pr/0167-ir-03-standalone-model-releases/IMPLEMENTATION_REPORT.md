# IMPLEMENTATION_REPORT.md — PR0167 IR-03 standalone model releases

## TASK COMPLETE

IR-03 implemented standalone ML plugin releases for the five verified model
variants.  Each variant now has:

- a reproducible, application-independent `bremen-ml-plugin` wheel containing
  only neutral contracts, the scientific model packages, the package bridge and
  the new plugin boundary;
- an allowlisted `bremen.worker.v1` entrypoint supporting `requirements`,
  `validate` and `predict` from a staged `input.h5` plus explicit request
  metadata;
- a locally assembled `bremen.inference-release.v1` Model Release containing
  the manifest, plugin wheel, checksum-verified artifact, configs,
  hash-locked requirements, explicit provenance and golden-test descriptors;
- clean-environment parity against the frozen IR-01 baselines.

All five variants execute successfully from the release in a fresh Python
3.13 environment with no Bremen application checkout, no `bremen.platform`
module and no live dependency resolution.  Scientific thresholds,
preprocessing, features, QC and model mathematics were not changed.

## FILES CHANGED

New plugin / release-build code:

- `src/bremen/ml_plugin/__init__.py` — plugin identity/version
- `src/bremen/ml_plugin/errors.py` — fixed safe failure vocabulary
- `src/bremen/ml_plugin/canonical.py` — neutral H5 canonicalization for
  `canonical`, `calibration_sample` and `session_layout`
- `src/bremen/ml_plugin/variants.py` — the five pinned variant descriptors,
  artifact loading, runtime construction, staged `ModelInput` building
- `src/bremen/ml_plugin/release.py` — local release descriptor loading,
  release-digest binding, pinned preprocessing environment application
- `src/bremen/ml_plugin/inference.py` — `requirements`/`validate`/`predict`
  execution and safe typed error mapping
- `src/bremen/ml_plugin/entrypoint.py` — file-based Worker entrypoint
- `src/bremen/release_build/__init__.py`
- `src/bremen/release_build/wheel.py` — deterministic PEP 427 wheel builder
- `src/bremen/release_build/provenance.py` — explicit observed dependency
  closure and preprocessing provenance capture
- `src/bremen/release_build/assemble.py` — local Model Release assembler

Modified scientific packages (provenance only; no science):

- `src/bremen/model_packages/bremen_v01/bremen_preprocess_worker.py` — accepts
  explicit release provenance when configured; preserves the historical
  `direct_url.json` commit check as fallback; cross-checks both when present
- `src/bremen/model_packages/aramina_v0213/aramina_preprocess_worker.py` — same
  explicit provenance support, including the known v0.1.7-beta source commit

New tests:

- `tests/test_ir03_plugin_import_boundary.py`
- `tests/test_ir03_plugin_wheel.py`
- `tests/test_ir03_standalone_runtime.py`
- `tests/test_ir03_parity.py`

Project memory:

- `.project-memory/pr/0167-ir-03-standalone-model-releases/IMPLEMENTATION_REPORT.md`
- `.project-memory/pr/0167-ir-03-standalone-model-releases/RELEASE_BUILD_EVIDENCE.md`
- `.project-memory/pr/0167-ir-03-standalone-model-releases/PARITY_EVIDENCE.md`

Not changed: `src/bremen/platform/**`, `src/bremen/api/**`, `src/bremen/contracts/**`,
`Dockerfile`, `.github/**`, `infra/**`, `requirements.txt`, `pyproject.toml`,
existing model artifacts and training code.  No H5 or joblib file was added to
the repository.

## PLUGIN ARCHITECTURE

```
release/
  manifest.json                  # bremen.inference-release.v1
  configs/runtime.json           # release identity, artifact sha, pinned envs
  configs/artifact_manifest.json # original artifact sidecar (provenance)
  plugin/bremen_ml_plugin-0.1.0-py3-none-any.whl
  model/<artifact>.joblib        # checksum-verified copy of the original
  requirements/main.lock         # hash-locked main closure
  requirements/aux-<tag>.lock    # exact observed auxiliary closure
  provenance/build.json          # build identity, hashes, observed closure
  provenance/xrd-preprocessing-<tag>.json
  golden_tests/cases.json        # fixture references + frozen expected values
  release.json                   # local build summary (not part of the manifest)
```

Import boundary:

- `bremen.ml_plugin` imports only stdlib, `numpy`/`h5py`, neutral
  `bremen.contracts` and the scientific `bremen.model_packages` /
  `bremen.model_packages_bridge`.
- It does not import `bremen.platform`, `bremen.api`, FastAPI, boto3, the
  catalog/discovery layer or application job orchestration.
- The plugin wheel contains an explicit allowlist: `bremen/__init__.py`,
  `bremen/model_packages_bridge.py`, `bremen/contracts/**`,
  `bremen/model_packages/**`, `bremen/ml_plugin/**`.  It contains no
  `bremen/platform`, `bremen/api`, application ODM/UI or training modules.

Entrypoint:

```
python -m bremen.ml_plugin.entrypoint \
  --release-dir /path/to/release \
  --job-dir /path/to/job
```

`<job>/request.json` is validated by the IR-02 `bremen.worker.v1` validator;
`<job>/input.h5` is mandatory for `validate`/`predict`; `<job>/result.json` is
the sole authoritative output.  Malformed requests/missing staged input exit
nonzero without a result (Harness maps that to `PROTOCOL_ERROR`); scientific
failures are normal `status=error` results.

Execution path:

1. verify `request.model_id` and `request.release_digest` against the release
   (`release_digest` is SHA-256 of the exact `manifest.json` bytes);
2. apply the release's pinned `BREMEN*_PREPROCESS*` interpreter/provenance
   variables;
3. load the artifact through the existing checksum-verifying bridge;
4. build the unchanged `ModelInput`:
   - B1: canonical measurements from the neutral session adapter;
   - B2/B3: raw staged container only (artifact-owned preprocessing);
   - A1/A2: canonical case + raw staged container;
5. call the unchanged `BremenRuntime` / `AraminaRuntime` methods;
6. encode the result with the IR-02 strict codecs and write `result.json`.

No Harness supervision, installation, S3, lifecycle or activation is
implemented.

## FIVE RELEASE DESCRIPTORS

| Slot | model_id | model_version | artifact SHA-256 | release manifest SHA-256 |
|---|---|---|---|---|
| A1 | `aramina_target_breast_risk_0_2_12-beta_9bb911189af6` | `0.2.12-beta` | `9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d` | `33babf2ce23e2f82d08d0065c0b48f6d9c266eea3593c724fc64616705336f70` |
| A2 | `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11` | `0.2.13-beta` | `f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b` | `35d174fb2811ed2dc234eefd690740dc5b8f42c338d2dc038e6fca4c08fbe851` |
| B1 | `bremen-mri-triage-logreg-v0-1` | `bremen_mri_triage_logreg_v0_1` | `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` | `6f9f02145201ea9f3e28b0f3319358bbf1fe964354de29da54fb4e4e5988b4eb` |
| B2 | `bremen-paper-reference-v0-2-0` | `0.2.0-paper-reference` | `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` | `99aa118ebf01d9f999744fb9e1f38d98783140262e56a32a61fb24c7d5f71320` |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `bremen_mri_triage_symmetry_logreg_0_2_0-research` | `971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4` | `76607bf3b48fe7062a0e7806692d21f6dbe401fe07f36d3b3a248410da2c520f` |

B2 and B3 are independent release descriptors with distinct model IDs,
artifact checksums and preprocessing YAML.  B1's manifest
`threshold_value: -1` placeholder is not used; the artifact's own
`portable_logreg` threshold is authoritative, exactly as in IR-01.

## DEPENDENCY CLOSURE

Main environment (exact observed closure, pinned and hash-locked in
`requirements/main.lock`):

```
numpy==2.5.4
pandas==3.0.6
scipy==1.18.1
scikit-learn==1.9.1
joblib==1.6.0
h5py==3.16.0
PyYAML==6.0.3
python-dateutil==2.9.0.post0
six==1.17.0
threadpoolctl==3.7.0
packaging==26.3
cloudpickle==3.1.2
narwhals==2.27.1
```

The main environment does not need `xrd-preprocessing`; all raw preprocessing
runs in the release's pinned auxiliary environments.

Auxiliary environments (captured exactly, not resolved at runtime):

- `v0.1.7-beta` (`xrd-preprocessing==0.1.7b0`), source commit
  `45d5568248e9774b7938a36e028d80e72b130b19`
- `v0.1.9-beta` (`xrd-preprocessing==0.1.9b0`), source commit
  `88dcaa277c5a0d4be2ab637bc5827a14bd106bea`

Offline wheelhouses were built for the main environment (13 wheels), the
v0.1.7-beta auxiliary environment (54 wheels) and the v0.1.9-beta auxiliary
environment (55 wheels); both auxiliary environments were installed from those
wheelhouses with `--no-index`.  See `RELEASE_BUILD_EVIDENCE.md`.

## PROVENANCE

- Release provenance is explicit: `provenance/build.json` records the source
  commit (read from real `git rev-parse HEAD`), plugin wheel hash, artifact
  hash, lock hashes and observed auxiliary provenance.  No commit is fabricated;
  the builder fails if no commit is available.
- Preprocessing provenance is an explicit JSON record shipped inside the
  release.  It was captured from the observed VCS `direct_url.json` where
  available, or from the exact source commit used to build the wheelhouse
  wheel when a wheel install has no VCS metadata.  Values are checked against
  the established commit map before being recorded.
- The Bremen worker's historical rule (`v0.1.7-beta` == version `0.1.7b0` ==
  commit `45d5568...`) is preserved.  The Aramina worker preserves the same
  v0.1.7-beta requirement and records the observed v0.1.9-beta commit.
- The legacy `direct_url.json` check remains as a fallback when no explicit
  record is configured, so existing environments behave exactly as before.

## DEVIATIONS

1. **Neutral canonicalization carrier instead of a platform import.**  B1 and
   A1/A2 need the existing canonical case.  The platform adapter module is
   forbidden to the plugin, so `bremen/ml_plugin/canonical.py` carries the same
   established dataset/side/case logic for `canonical`, `calibration_sample`
   and `session_layout`.  It performs no new scientific computation.  The
   unsupported `matador_raw` archive layout fails closed with
   `unsupported_container_layout` (B2/B3 never canonicalize; their raw
   artifact-owned preprocessing is unaffected).
2. **Release-identity override for `requirements`.**  The Bremen package's
   static `model_requirements()` reports the paper-reference model version for
   B1/B2/B3.  The plugin binds only `model_version` in the requirements payload
   to the concrete release descriptor.  No measurement side, feature schema,
   threshold or QC field is changed.
3. **Explicit auxiliary source-commit build input.**  A wheel-installed
   `xrd-preprocessing` has no `direct_url.json`.  The builder accepts the exact
   source commit of the wheelhouse sdist and validates it against the
   established commit map; it does not invent a commit.

## KNOWN LIMITATIONS

- The main plugin environment is fully relocatable; the auxiliary interpreter
  paths in `configs/runtime.json` are absolute and machine-local.  IR-04's
  installer is expected to materialize digest-qualified auxiliary environments;
  this PR does not implement installation/cache lifecycle.
- `matador_raw` canonicalization is not shipped.  It is not required by any
  successful IR-03 parity case; B2/B3 still consume matador-raw H5 through
  their own artifact-owned preprocessing.
- Aramina `predict` deserializes the artifact twice in one process (once for
  release readiness, once inside the unchanged package pipeline).  This is an
  efficiency note, not a correctness difference.
- Artifacts were trained with scikit-learn 1.9.0; the observed IR-01/IR-03
  runtime is 1.9.1 and emits `InconsistentVersionWarning`.  All frozen
  baseline values reproduce bit-exactly under 1.9.1, so the closure was not
  changed.
- This PR does not publish to S3, implement READY/ACTIVE, add a release cache,
  or verify App Runner.

## SECURITY / IMPORT-BOUNDARY CHECKS

- AST tests forbid `bremen.platform`, `bremen.api`, FastAPI, boto3/uvicorn in
  plugin and release-build modules.
- A subprocess meta-path blocker imports the entire plugin with
  `bremen.platform`, `bremen.api`, `fastapi`, `boto3` and `uvicorn` blocked;
  it succeeds.
- Wheel content tests assert no platform/API/application modules are packaged.
- Artifact bytes are SHA-256 verified before deserialization through the
  existing controlled bridge.
- `release_digest` binds each request to the exact manifest bytes.
- The staged input must be exactly `<job>/input.h5`; symlinks and real-path
  escapes are rejected.
- Error results carry exactly `code` + `safe_reason`; no traceback, path,
  artifact internals, patient data or exception text crosses the boundary.
- No AWS/S3 code, credentials or network calls were added.
- No `.h5`, `.joblib` or other model artifact is committed.

## VALIDATION RESULTS

Environment: `/tmp/bremen-ir01-exec-venv` (Python 3.13.12) for repository
tests; `/tmp/ir03/clean-venv-final2` (fresh Python 3.13.12 venv) for the
standalone clean-environment run.

| Command | Result |
|---|---|
| `python3 -m compileall -q src tests` (system 3.14.7) | exit 0 |
| `PATH=…python3 -m compileall -q src tests` (3.13.12) | exit 0 |
| `pytest -q tests/test_ir03_plugin_import_boundary.py tests/test_ir03_plugin_wheel.py tests/test_ir03_standalone_runtime.py tests/test_ir03_parity.py` | 70 passed |
| targeted existing model-package/runtime parity suite (9 files, incl. worker/inference contracts, discovery/registry) | 826 passed |
| `pytest -q` (Python 3.13.12) | **4362 passed, 8 skipped, 40 warnings** |
| `python3 -m pytest -q` (system 3.14.7) | 58 pre-existing collection errors (missing numpy/h5py/fastapi/jwt/argon2/joblib), exit 2 — environment-only, unchanged |
| `git diff --check` | exit 0 |
| `git status --short` | only intended changes; unrelated files preserved |
| `git diff --stat` | 2 tracked worker files modified (91 insertions, 1 deletion); new files untracked |

Full suite count 4362 = previous 4292 + 70 new IR-03 tests (exact).

## REMAINING BLOCKERS

None for the IR-03 local scope.

Explicitly out of scope and still open for later roadmap items: S3 publication,
installation/cache lifecycle, Harness supervisor, READY/ACTIVE markers, App
Runner verification, and live catalog activation.

## NEXT REQUIRED ACTION

Precommit review of PR0167, using:

- `RELEASE_BUILD_EVIDENCE.md` for wheel/manifest/lock hashes and commands
- `PARITY_EVIDENCE.md` for the five-model frozen-baseline comparison

This report is mandatory handoff context for the Precommit Reviewer.

---

# Review-fix pass (`0167-ir-03-standalone-model-releases-review-fixes`)

## BLOCKERS RECEIVED

From `.project-memory/pr/0167-ir-03-standalone-model-releases/reviews/precommit-review.yml`
(`VERDICT: block`), scoped strictly to release reproducibility:

- **RELEASE-AUX-HASHES** — auxiliary locks were not fully hash-locked and
  `provenance/build.json` recorded `hash_locked_aux=false`.
- **RELEASE-AUX-PORTABILITY** — `configs/runtime.json` embedded machine-local
  absolute auxiliary interpreter paths.
- **RELEASE-SKLEARN-CLOSURE** — the standalone environment pinned
  scikit-learn 1.9.1 while artifacts record training with 1.9.0.

Scientific parity had already passed and was not redesigned.

## FIXES IMPLEMENTED

1. **Fully hash-locked auxiliary closures.**
   `_lock_lines` now builds a `(normalized name, version) -> wheel hashes`
   map from the supplied wheelhouse and **fails closed** when any requirement
   has no corresponding local wheel. The auxiliary lock now receives the
   *auxiliary* wheelhouse (`--aux-wheelhouse TAG=PATH`) rather than the main
   one, and an auxiliary environment without a wheelhouse is rejected.
   `provenance/build.json` records `hash_locked_aux=true` only for releases
   that actually have auxiliary locks.

2. **Portable auxiliary environment references.**
   Release descriptors now store logical references only:
   `"BREMEN_PREPROCESS_PYTHON": "@aux/v0.1.7-beta"`. At runtime,
   `apply_preprocessing_environment` resolves `@aux/<tag>` to
   `<release>/aux/<tag>/bin/python` when the release ships its own
   environment, otherwise to `$BREMEN_IR03_AUX_ENV_ROOT/<tag>/bin/python`.
   `@release/<path>` continues to resolve inside the release for provenance
   records. Absolute interpreter/provenance values are now rejected rather
   than accepted. Manifest `environments.<aux>` entries use
   `"environment_ref": "@aux/<tag>"` instead of `python_executable`.

3. **scikit-learn 1.9.0.**
   `PLUGIN_REQUIRES_DIST` now pins `scikit-learn==1.9.0`. The exact CPython
   3.13/macOS arm64 wheel is available (`scikit_learn-1.9.0-cp313-cp313-macosx_12_0_arm64.whl`,
   SHA-256 `5b934c45c252844a91d69fda3a34cff5e7307e1db10d77cb10a3980312c74713`),
   so the offline wheelhouse, main lock, clean environment and all releases
   were rebuilt against 1.9.0. The substitution was not retained on the basis
   of selected-fixture parity.

## FILES CHANGED

- `src/bremen/release_build/assemble.py` — hash-complete lock generation,
  auxiliary wheelhouse input, logical `@aux` references, no absolute
  interpreter in manifest environments, accurate `hash_locked_aux`.
- `src/bremen/release_build/wheel.py` — `scikit-learn==1.9.0` pin.
- `src/bremen/ml_plugin/release.py` — `@aux/<tag>` resolver and rejection of
  absolute descriptor values.
- `tests/test_ir03_plugin_wheel.py` — hash-completeness/negative tests,
  no-absolute-path assertions.
- `tests/test_ir03_standalone_runtime.py` — portability/resolution tests.
- `tests/test_ir03_parity.py` — auxiliary environment root for evidence runs.
- Project-memory evidence files (this report,
  `RELEASE_BUILD_EVIDENCE.md`, `PARITY_EVIDENCE.md`).

No scientific code, threshold, preprocessing, QC, feature, platform, API,
Docker, CI or infra file was modified.

## SIMPLICITY DECISIONS

- Reused the existing lock builder and runtime-config applier; no new module,
  registry or abstraction layer was added.
- The portable representation is a single `@aux/<tag>` prefix handled by the
  existing `apply_preprocessing_environment` function.
- The resolver checks the release-local `aux/<tag>` layout first and falls
  back to one environment variable. This is the minimum needed for a copied or
  reconstructed release to work without editing `runtime.json`; the IR-04
  installer is still not implemented.
- Hashes are derived from actual wheel files rather than a new verification
  subsystem; pip's own `--require-hashes` mode performs the final proof.

## LOCK INTEGRITY RESULTS

All locks are fully hash-pinned and installable offline with
`--no-index --only-binary=:all: --require-hashes`:

| Lock | Pins | Hash lines | SHA-256 |
|---|---|---|---|
| `requirements/main.lock` | 13 | 13 | `5c7127cf3cfee9eea495f6fab68c2ff01d148167f44d4391ebc0ae0be71af343` |
| `requirements/aux-v0.1.7-beta.lock` | 54 | 54 | `f04603782be34685410e6faa294c971d304ff5db35413480165fd945438dd2f7` |
| `requirements/aux-v0.1.9-beta.lock` | 54 | 54 | `c31e23d2ed22c3bd1bc797b827f594b04fb583431df48916381619b9188cfdb6` |

Independent strict installs (fresh venvs, no network index):

```
pip install --no-index --only-binary=:all: --require-hashes \
  --find-links /tmp/ir03/wh190-main -r .../requirements/main.lock        -> exit 0
pip install --no-index --only-binary=:all: --require-hashes \
  --find-links /tmp/ir03/wheelhouse-aux-017b \
  -r .../requirements/aux-v0.1.7-beta.lock                               -> exit 0
pip install --no-index --only-binary=:all: --require-hashes \
  --find-links /tmp/ir03/wheelhouse-aux-019 \
  -r .../requirements/aux-v0.1.9-beta.lock                               -> exit 0
```

Negative tests prove incomplete hashes fail closed:
`test_lock_lines_require_a_hash_for_every_requirement`,
`test_lock_lines_reject_missing_wheelhouse`,
`test_aux_lock_rejects_missing_wheelhouse`,
`test_main_lock_is_fully_hash_pinned`.

## PORTABILITY RESULTS

- `configs/runtime.json` values are `@aux/<tag>` / `@release/<path>`; a grep
  for absolute `/tmp` or `/private/tmp` paths across all generated
  `configs/**` and `manifest.json` files returns nothing.
- `manifest.json` auxiliary environments contain `environment_ref` only; no
  `python_executable` field remains.
- Runtime resolution test: a release copied to `/tmp/ir03/relocated/<variant>`
  ran without editing any descriptor, resolving the auxiliary interpreter from
  `BREMEN_IR03_AUX_ENV_ROOT`:
  - B2 `benign_one_patient.h5` → probability `0.7726940329943811` (ok)
  - A1 `cabce03d-…h5`, left → risk `0.8693870739736473` (ok)
- Missing auxiliary environment fails closed with
  `auxiliary_environment_missing` (PROTOCOL_ERROR), it does not silently fall
  back to an arbitrary interpreter.
- Tests: `TestPreprocessingEnvironmentPortability` (5 cases) plus the
  no-absolute-path release-assembly assertion.

## DEPENDENCY VERSIONS

Main standalone environment (clean venv, installed from main lock):

```
scikit-learn==1.9.0      numpy==2.5.4        pandas==3.0.6
scipy==1.18.1            joblib==1.6.0       h5py==3.16.0
PyYAML==6.0.3            python-dateutil==2.9.0.post0
six==1.17.0              threadpoolctl==3.7.0 packaging==26.3
cloudpickle==3.1.2       narwhals==2.27.1
```

Runtime check in the clean environment: `sklearn.__version__ == "1.9.0"`.
Auxiliary environments: `xrd-preprocessing==0.1.7b0` (commit
`45d5568248e9774b7938a36e028d80e72b130b19`) and `0.1.9b0` (commit
`88dcaa277c5a0d4be2ab637bc5827a14bd106bea`). Auxiliary environments are used
only by the preprocessing workers (numpy/pandas/yaml/xrd-preprocessing); the
scientific estimator runs in the main environment.

## REBUILT RELEASE HASHES

Rebuilt plugin wheel: `bremen_ml_plugin-0.1.0-py3-none-any.whl`
SHA-256 `029af6c73238cd83d31f1dea31fa52cbbd69f4236e14ba317f076e04affa7e82`
(size `112060`).

| Slot | release_id | manifest SHA-256 | artifact SHA-256 |
|---|---|---|---|
| A1 | `aramina-target-breast-risk-0-2-12-beta-9bb9111` | `81a6c75aa4eae4888043452b42d0cb79371ea2d5a99a9a0464a70d101eeabc46` | `9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d` |
| A2 | `aramina-target-breast-risk-0-2-13-beta-f5e4a04` | `35a1e9ba21a9e5f1a716390076e7b22a93aeb7943a52a28b0847e5b482d51208` | `f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b` |
| B1 | `bremen-mri-triage-logreg-v0-1` | `4629a4c455dd52ca1c9b631907aff2a9c293c6815301fcb496f3e1a6f72b7ea1` | `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` |
| B2 | `bremen-paper-reference-v0-2-0` | `d3eb9d92a8b470ac038d965e9c877617ab4dec67e77f912fa1fd73a072394bc7` | `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `1e7078b18754f732ab72665b5a3fe8bbe137ce246edf389792fdb16bd4abe49e` | `971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4` |

These supersede every earlier hash table in this report and in
`RELEASE_BUILD_EVIDENCE.md`.

## PARITY RESULTS

Re-run in a clean Python 3.13.12 environment installed from the rebuilt
wheel/locks, `PYTHONPATH` unset, with `scikit-learn==1.9.0`:

- 11/11 frozen cases PASS with exact equality (B1 benign/Nova_376, B2 benign,
  B3 benign, A1/A2 Nova_214 left; B1/B2 cancer QC, B3 atypical shape, A1/A2
  Nova_376 preprocessing failure).
- All five `requirements` and `validate` operations return `ok`.
- Missing staged input and malformed request exit `2` without `result.json`.
- Relocated B2/A1 releases reproduce their frozen values with no descriptor
  edits.

## VALIDATION RESULTS

| Command | Result |
|---|---|
| `python3 -m compileall -q src tests` | exit 0 |
| `PATH=…python3 -m compileall -q src tests` (3.13.12) | exit 0 |
| `pytest -q tests/test_ir03_plugin_import_boundary.py` | 13 passed |
| `pytest -q tests/test_ir03_plugin_wheel.py` | 12 passed |
| `pytest -q tests/test_ir03_standalone_runtime.py` | 33 passed |
| `pytest -q tests/test_ir03_parity.py` | 21 passed |
| IR-03 files combined | **79 passed** |
| `pytest -q` (Python 3.13.12) | **4371 passed, 8 skipped, 40 warnings** |
| `python3 -m pytest -q` (system 3.14.7) | 58 pre-existing dependency collection errors |
| `git diff --check` | exit 0 |
| `git status --short` | only intended files |
| `git diff --stat` | 2 preprocessing-worker files modified; new files untracked |
| strict offline `pip --require-hashes` installs | main + both auxiliary locks exit 0 |
| absolute path grep over generated descriptors | none found |
| clean runtime `sklearn.__version__` | `1.9.0` |

Full suite: 4371 = previous 4362 + 9 new review-fix tests.

## WARNINGS

- Auxiliary environments still contain scikit-learn 1.9.1 as part of their
  observed closure. They only run the xrd-preprocessing worker and never
  import the estimator; the standalone main environment that executes model
  inference is pinned to 1.9.0.
- `matador_raw` canonicalization remains an explicit unsupported limitation.
- Auxiliary interpreter locations are resolved through
  `BREMEN_IR03_AUX_ENV_ROOT` (or release-local `aux/<tag>`); IR-04 still owns
  actual installation/materialization.
- Aramina double-deserialization remains a known efficiency note.
- These are local executions only; App Runner verification remains IR-06.

## REMAINING BLOCKERS

None for the three received blockers.

## NEXT REQUIRED ACTION

Repeat precommit review.
