# PARITY_EVIDENCE.md — PR0167 IR-03 five-model frozen-baseline parity

**Result: PASS — 11/11 parity cases across all five variants, executed from
standalone releases in a clean Python 3.13 environment, bit-exact against the
frozen IR-01 baselines.**

## What was compared

Baseline references:

- `.project-memory/pr/0165-ir-01-five-model-inventory/BASELINE_EXECUTION.md`
  (successful baselines and expected/typed failure categories)
- `docs/inference-releases/parity-and-rollout.md` (PR0160 reference
  `0.7726940329943811`; A1/A2 production capture `0.8693870739736473`;
  threshold display-precision note)
- `results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`
  (A2 `risk_probability=0.869387073973647`, full-precision threshold
  `0.24665932038818544`)

Comparison rule: exact equality (`rel_tol=0`, `abs_tol=0`) for probabilities,
thresholds and class/prediction; exact equality for typed error code and safe
reason.  No tolerance was invented.  (Float equality is exact here because both
the baseline and standalone runs execute the same artifact code on the same
fixture; the recorded values are bit-identical.)

## Clean-environment execution

```
host:        macOS-26.5.1-arm64
interpreter: /tmp/ir03/clean-venv-final2/bin/python  (Python 3.13.12)
cwd:         /tmp        (not the repository)
PYTHONPATH:  unset
env:         no Bremen application distribution installed
command:     python -m bremen.ml_plugin.entrypoint \
               --release-dir /tmp/ir03/releases-final/<variant> \
               --job-dir <fresh job dir containing request.json + input.h5>
```

Import isolation in that environment:

```
bremen.__file__ = /tmp/ir03/clean-venv-final2/lib/python3.13/site-packages/bremen/__init__.py
importlib.util.find_spec("bremen.platform") -> None
importlib.util.find_spec("bremen.api")      -> None
importlib.util.find_spec("fastapi")         -> None
import bremen.platform -> ModuleNotFoundError
```

Frozen fixture hashes used by the golden descriptors:

- `benign_one_patient.h5` — `95a2ff8245f130930d8b8b35ed8e2ef3cdc9ffd955ec49708950d4c6abfdc303`
- `cancer_one_patient.h5` — `f09d6f5745afc3285a818e28b53261f84a8ece8d27926c1c439bf436bf6878b7`
- `atypical_one_patient.h5` — recorded in each release's `golden_tests/cases.json`
- `Nova_376.h5` — recorded in each release's `golden_tests/cases.json`
- `eoscloud-staging/cabce03d-f9c4-43db-91d1-aec20007ee18.h5` — recorded in each release's `golden_tests/cases.json`

## Successful cases (exact equality)

| Slot | Case / fixture | Expected (IR-01 frozen) | Standalone actual | Outcome |
|---|---|---|---|---|
| B1 | `benign_one_patient.h5` | probability `0.8524639494195422`, threshold `0.3640352477169748`, prediction `1` | identical | PASS |
| B1 | `Nova_376.h5` | probability `0.5677291934209037`, threshold `0.3640352477169748`, prediction `1` | identical | PASS |
| B2 | `benign_one_patient.h5` | probability `0.7726940329943811`, threshold `0.3585907282566089`, prediction `1` | identical | PASS |
| B3 | `benign_one_patient.h5` | probability `0.6848549443589647`, threshold `0.4130396520921527`, prediction `1` | identical | PASS |
| A1 | `cabce03d-…h5`, patient `Nova_214`, target `left` | risk `0.8693870739736473`, threshold `0.24665932038818544`, class `1` | identical | PASS |
| A2 | `cabce03d-…h5`, patient `Nova_214`, target `left` | risk `0.8693870739736473`, threshold `0.24665932038818544`, class `1` | identical | PASS |

Notes:

- B2's value is the PR0160 reference, reproduced bit-exactly.
- A1/A2 reproduce the previously captured production value; the trailing
  digits are the same float at full precision.
- B1 uses the artifact-owned threshold `0.3640352477169748`; the artifact
  manifest's `threshold_value: -1` placeholder is not read.
- B3 is a genuinely independent model: its probability and threshold differ
  from B2 on the same fixture, preserving the IR-01 finding.  Its
  `exploratory_proxy_not_clinically_reviewed` status is unchanged by this run.

## Expected-failure cases (typed, exact)

| Slot | Case / fixture | Expected (IR-01 frozen) | Standalone actual | Outcome |
|---|---|---|---|---|
| B1 | `cancer_one_patient.h5` | `QC_FAILED` / `raw_peak_gate_failed` | identical | PASS |
| B2 | `cancer_one_patient.h5` | `QC_FAILED` / `raw_peak_gate_failed` | identical | PASS |
| B3 | `atypical_one_patient.h5` | `INPUT_INVALID` / `requires_exactly_3_left_3_right` | identical | PASS |
| A1 | `Nova_376.h5`, target `left` | `QC_FAILED` / `ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract` | identical | PASS |
| A2 | `Nova_376.h5`, target `left` | `QC_FAILED` / `ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract` | identical | PASS |

The Aramina failures preserve the allowlisted public stage
`preprocessing_contract`; the release does not expose the underlying
`H5PoniGeometryCalculatorTransformer` diagnostic, matching the platform's safe
taxonomy.  The Bremen QC/gate failures preserve the exact safe reason.

## Additional clean-environment operation evidence

| Variant | `requirements` | `validate` (benign fixture) |
|---|---|---|
| A1 | `ok`, `aramina`, `0.2.12-beta`, requires target side | `ok`, `compatible=true` |
| A2 | `ok`, `aramina`, `0.2.13-beta`, requires target side | `ok`, `compatible=true` |
| B1 | `ok`, `bremen`, `bremen_mri_triage_logreg_v0_1` | `ok`, `compatible=true` |
| B2 | `ok`, `bremen`, `0.2.0-paper-reference` | `ok`, `compatible=true` |
| B3 | `ok`, `bremen`, `bremen_mri_triage_symmetry_logreg_0_2_0-research` | `ok`, `compatible=true` |

Protocol/staging failures (clean environment):

| Case | Exit | `result.json` written |
|---|---|---|
| `predict` without staged `input.h5` | `2` | no |
| malformed `request.json` | `2` | no |

Simultaneous raw outcomes for all 11 scientific cases:

```
a1 a1-nova214-left PASS
a1 a1-nova376-left-preprocessing-failure PASS
a2 a2-nova214-left PASS
a2 a2-nova376-left-preprocessing-failure PASS
b1 b1-benign PASS
b1 b1-nova376 PASS
b1 b1-cancer-qc PASS
b2 b2-benign PASS
b2 b2-cancer-qc PASS
b3 b3-benign PASS
b3 b3-atypical-shape PASS
PROBLEMS 0
```

## Repository regression parity

The same golden cases also run inside the repository suite
(`tests/test_ir03_parity.py`, skipped when the local `/tmp` evidence is absent):

- New IR-03 tests: **70 passed**
- Targeted existing model-package/runtime suite: **826 passed**
- Full Python 3.13 suite: **4362 passed, 8 skipped, 40 warnings**
- `git diff --check`: exit 0

## Deviations / limitations

- No numeric or categorical deviation was observed for any of the 11 cases.
- `matador_raw` fixtures were not used.  That layout is not shipped by the
  plugin canonicalizer; B2/B3 do not need canonicalization, and no chosen
  successful/failure parity case requires it.  This is a documented input
  compatibility limitation, not a parity difference.
- Artifacts emit `InconsistentVersionWarning` (built with scikit-learn 1.9.0,
  executed with 1.9.1).  This matches the IR-01 execution environment and all
  values are bit-exact; the dependency closure was not changed.
- This run is local-only evidence.  App Runner/service parity remains IR-06.

---

# Review-fix parity rerun (`0167-ir-03-standalone-model-releases-review-fixes`)

**This section supersedes the execution environment in the sections above.**
The scientific cases, fixtures and expected values are unchanged; the
environment was rebuilt with `scikit-learn==1.9.0` and fully hash-locked main
and auxiliary dependencies.

## BLOCKERS RECEIVED

- RELEASE-AUX-HASHES
- RELEASE-AUX-PORTABILITY
- RELEASE-SKLEARN-CLOSURE

## FIXES IMPLEMENTED (parity-relevant)

- Main environment installed from `requirements/main.lock` (13 pins, 13 hash
  lines) with `--no-index --only-binary=:all: --require-hashes`.
- Auxiliary environments installed from their fully hash-locked files the same
  way (`xrd-preprocessing` 0.1.7b0 / 0.1.9b0).
- Release descriptors reference `@aux/<tag>`; the auxiliary interpreter is
  resolved at runtime from `BREMEN_IR03_AUX_ENV_ROOT`.
- `scikit-learn==1.9.0` in the standalone environment.

## SIMPLICITY DECISIONS

No new resolver/factory: the existing `apply_preprocessing_environment`
function resolves `@aux/<tag>`; the existing lock builder fails closed on any
missing wheel hash.

## LOCK INTEGRITY RESULTS

Strict offline installs exited 0 for main, v0.1.7-beta and v0.1.9-beta locks
(see `RELEASE_BUILD_EVIDENCE.md`).  Incomplete hashes are rejected by tests.

## PORTABILITY RESULTS

Copied releases at `/tmp/ir03/relocated/{b2,a1}` ran without descriptor edits
and reproduced their frozen values.

## DEPENDENCY VERSIONS

Clean environment: `scikit-learn==1.9.0`, `numpy==2.5.4`, `pandas==3.0.6`,
`scipy==1.18.1`, `joblib==1.6.0`, `h5py==3.16.0`, `PyYAML==6.0.3`.

## REBUILT RELEASE HASHES

| Slot | manifest SHA-256 |
|---|---|
| A1 | `81a6c75aa4eae4888043452b42d0cb79371ea2d5a99a9a0464a70d101eeabc46` |
| A2 | `35a1e9ba21a9e5f1a716390076e7b22a93aeb7943a52a28b0847e5b482d51208` |
| B1 | `4629a4c455dd52ca1c9b631907aff2a9c293c6815301fcb496f3e1a6f72b7ea1` |
| B2 | `d3eb9d92a8b470ac038d965e9c877617ab4dec67e77f912fa1fd73a072394bc7` |
| B3 | `1e7078b18754f732ab72665b5a3fe8bbe137ce246edf389792fdb16bd4abe49e` |

Plugin wheel: `029af6c73238cd83d31f1dea31fa52cbbd69f4236e14ba317f076e04affa7e82`.

## PARITY RESULTS

Clean environment: `/tmp/ir03/clean-190` (Python 3.13.12), `PYTHONPATH`
unset, `BREMEN_IR03_AUX_ENV_ROOT=/tmp/ir03/aux-env-root`.
`importlib.util.find_spec("bremen.platform")` and `("bremen.api")` return
`None`.

| Slot | Case | Expected | Actual | Outcome |
|---|---|---|---|---|
| B1 | benign | `0.8524639494195422` / `0.3640352477169748` / `1` | identical | PASS |
| B1 | Nova_376 | `0.5677291934209037` / `0.3640352477169748` / `1` | identical | PASS |
| B1 | cancer | `QC_FAILED` / `raw_peak_gate_failed` | identical | PASS |
| B2 | benign | `0.7726940329943811` / `0.3585907282566089` / `1` | identical | PASS |
| B2 | cancer | `QC_FAILED` / `raw_peak_gate_failed` | identical | PASS |
| B3 | benign | `0.6848549443589647` / `0.4130396520921527` / `1` | identical | PASS |
| B3 | atypical | `INPUT_INVALID` / `requires_exactly_3_left_3_right` | identical | PASS |
| A1 | Nova_214 left | `0.8693870739736473` / `0.24665932038818544` / `1` | identical | PASS |
| A1 | Nova_376 left | `QC_FAILED` / `ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract` | identical | PASS |
| A2 | Nova_214 left | `0.8693870739736473` / `0.24665932038818544` / `1` | identical | PASS |
| A2 | Nova_376 left | `QC_FAILED` / `ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract` | identical | PASS |

Result: `PROBLEMS 0`, 11/11 PASS, exact equality.

Additional clean-environment checks: all five `requirements` return `ok` with
the release-specific model version; all five `validate` return
`compatible=true`; missing staged input and malformed request exit `2` with no
`result.json`.

## VALIDATION RESULTS

- `tests/test_ir03_parity.py`: 21 passed
- IR-03 tests combined: 79 passed
- Full suite (Python 3.13.12): 4371 passed, 8 skipped, 40 warnings
- Strict offline hash installs: exit 0 (main + both auxiliary locks)
- Absolute-path grep over generated descriptors: none
- Clean runtime sklearn: 1.9.0

## WARNINGS

- Auxiliary environments include scikit-learn 1.9.1 in their own observed
  closure; they only execute the xrd-preprocessing worker and never import the
  estimator.  The standalone inference environment is 1.9.0.
- `matador_raw` remains an explicit unsupported canonicalization limitation.
- Local evidence only; App Runner parity is IR-06.

## REMAINING BLOCKERS

None for the three received blockers.

## NEXT REQUIRED ACTION

Repeat precommit review.
