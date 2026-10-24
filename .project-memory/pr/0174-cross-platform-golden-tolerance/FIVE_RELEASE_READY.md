# FIVE_RELEASE_READY.md — PR0174 Linux production releases

Five already-built Linux/amd64 production releases were installed through the
real offline `ReleaseCache` path after the golden probability tolerance fix.

- Release root (unchanged, not rebuilt): `~/ir07-linux-amd64-work/releases/{a1,a2,b1,b2,b3}`
- Install root: `~/ir07-linux-amd64-work/cache-0174/<variant>` (new, local)
- Execution: x86_64 Linux userland, CPython 3.13.17,
  ABI `cpython-313-x86_64-linux-gnu` (container runtime on the local machine)
- AWS: **not used** — the S3 boundary was a deterministic reader over the
  release directories
- Catalog URI: `s3://trusted-bucket/`
- Path: `ReleaseCache.resolve()` → `ReleaseCache.install()` (release-local
  wheelhouses, `--no-index --only-binary=:all: --require-hashes`) → mandatory
  golden smoke → READY

## READY results

| Variant | Manifest SHA-256 (release digest) | Result | Install (s) |
|---|---|---|---|
| A1 | `0f4b387694656cd10930d87a7e68b433cae838b06bff38f040e01aa10a296591` | **READY** | 301.5 |
| A2 | `8ad42898ab2ed23cf3983b42f2f0b1a6606cd7b11f8003cc0c6576b346fe710f` | **READY** | 266.4 |
| B1 | `825de1d34fbd05a647ebbbea84512075ff298b35ee9c46ddbd1588a8b4bfc97e` | **READY** | 108.4 |
| B2 | `1ead9f84d7921deca72fe822673d08eed5557089f22de9b2eb1e8f636eca6038` | **READY** | 319.2 |
| B3 | `059575df328b6a7b95b7f6bf581dba11ff8871fa00df9b182f7a2789bbef138e` | **READY** | 297.5 |

Every READY marker was written only after all release-declared golden cases
(including the expected typed-failure cases) passed.

## Actual outputs vs frozen golden values

Success cases (first successful case per release):

| Variant | Case | Field | Golden | Linux actual | Abs diff | Exact |
|---|---|---|---|---|---|---|
| A1 | `a1-nova214-left` | risk_probability | `0.8693870739736473` | `0.869387073973647` | `3.33e-16` | no (tolerated) |
| A1 | `a1-nova214-left` | decision_threshold | `0.24665932038818544` | `0.24665932038818544` | `0` | **yes** |
| A1 | `a1-nova214-left` | target_class_risk_level | `1` | `1` | — | **yes** |
| A2 | `a2-nova214-left` | risk_probability | `0.8693870739736473` | `0.869387073973647` | `3.33e-16` | no (tolerated) |
| A2 | `a2-nova214-left` | decision_threshold | `0.24665932038818544` | `0.24665932038818544` | `0` | **yes** |
| A2 | `a2-nova214-left` | target_class_risk_level | `1` | `1` | — | **yes** |
| B1 | `b1-benign` | probability | `0.8524639494195422` | `0.8524639494195415` | `6.66e-16` | no (tolerated) |
| B1 | `b1-benign` | threshold_applied | `0.3640352477169748` | `0.3640352477169748` | `0` | **yes** |
| B1 | `b1-benign` | prediction | `1` | `1` | — | **yes** |
| B2 | `b2-benign` | probability | `0.7726940329943811` | `0.7726940329943845` | `3.44e-15` | no (tolerated) |
| B2 | `b2-benign` | threshold_applied | `0.3585907282566089` | `0.3585907282566089` | `0` | **yes** |
| B2 | `b2-benign` | prediction | `1` | `1` | — | **yes** |
| B3 | `b3-benign` | probability | `0.6848549443589647` | `0.6848549443589693` | `4.66e-15` | no (tolerated) |
| B3 | `b3-benign` | threshold_applied | `0.4130396520921527` | `0.4130396520921527` | `0` | **yes** |
| B3 | `b3-benign` | prediction | `1` | `1` | — | **yes** |

## B2 hard gate

```
probability        = 0.7726940329943845   (|Δ| = 3.44e-15 vs 0.7726940329943811)
threshold_applied  = 0.3585907282566089   EXACT
prediction         = 1                    EXACT
```

Accepted solely because the probability difference is within
`GOLDEN_PROBABILITY_ABS_TOLERANCE = 1e-12`.

## Typed failure cases (golden gate, exact)

Each release's expected-failure cases passed with exact status/code/reason as
part of the same golden gate (e.g. B1/B2 `cancer_one_patient.h5` →
`QC_FAILED` / `raw_peak_gate_failed`; B3 `atypical_one_patient.h5` →
`INPUT_INVALID` / `requires_exactly_3_left_3_right`;
A1/A2 `Nova_376.h5` → `QC_FAILED` /
`ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract`).

## Local artefacts

- Scripts: `~/ir07-linux-amd64-work/scripts/{install_linux.py,run_linux.py}`
- Results: `~/ir07-linux-amd64-work/cache-0174-result.json`,
  `~/ir07-linux-amd64-work/cache-0174-predict.json`
- These are local evidence only and are not committed.
