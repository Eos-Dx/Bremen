# FIVE_RELEASE_PARITY.md — PR0169 IR-05

**Current evidence uses only the rebuilt release root `/tmp/ir05/releases`.**
Every release there embeds its own plugin wheel, dependency wheels and golden
fixtures, and was installed through the real `ReleaseCache.install()` before
being driven by the real `SubprocessRuntime` and a real Worker process.

Superseded: any earlier IR-05 table that referenced `/tmp/ir03/releases-final`
or directly constructed `InstalledRelease` records. Those releases predate the
`ml_plugin/inference.py` change and are not current evidence.

## Builds

| Item | Value |
|---|---|
| Plugin wheel | `bremen_ml_plugin-0.1.0-py3-none-any.whl` |
| OLD plugin SHA-256 | `029af6c73238cd83d31f1dea31fa52cbbd69f4236e14ba317f076e04affa7e82` |
| NEW plugin SHA-256 | `f4c4bf1ee52b7002b49598a1d40200517469b97e9f8f6809761949595d23d626` |
| Release root | `/tmp/ir05/releases` |
| Install root | `/tmp/ir05/cache/<variant>` |

| Slot | release_id | manifest SHA-256 | main wheels | aux wheels | golden files |
|---|---|---|---|---|---|
| A1 | `aramina-target-breast-risk-0-2-12-beta-9bb9111` | `02be0ce3117080bbbf998a81ffaeff993938aaeb6fd2cc98c93ee730f7532b4c` | 13 | 54 | 2 |
| A2 | `aramina-target-breast-risk-0-2-13-beta-f5e4a04` | `7ebd66806b7924202d68d7d74265784300b8dacc64b6df98bb8d4e2984fd4e49` | 13 | 54 | 2 |
| B1 | `bremen-mri-triage-logreg-v0-1` | `678edd64ddb35a2ba26e92f9bd804ab350303e458b4d152a5a4498ab812bc8ad` | 13 | 0 | 3 |
| B2 | `bremen-paper-reference-v0-2-0` | `d6df5c67bee4c9beadecd75fa316883fdcbfed81532ccea298d14f0bdc312321` | 13 | 54 | 2 |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `596f8e10c065ae8d7c99201274c8559e8d158bff2393f637d47e8755611887eb` | 13 | 54 | 2 |

## Method

Script: `/tmp/ir05/supervisor_parity.py` (real code, local S3 stub serving the
new release directories, `catalog_uri=s3://trusted-bucket/`).

For each variant:

1. `ReleaseCache.install(entry)` — real offline install from the release-local
   wheelhouses, mandatory golden gate, READY marker.
2. `SubprocessRuntime(entry=entry, release_cache=cache)`.
3. `model_requirements()` — real Worker process.
4. `predict_model(ModelInput(...))` on the representative success fixture —
   real Worker process, `result.json`, existing decode path.

The Worker runs as a separate process with the restricted child environment.

## Results (success paths)

| Variant | Installed release digest | Requirements model version | Fixture | Expected | Actual | Outcome |
|---|---|---|---|---|---|---|
| B1 | `678edd64…c8ad` | `bremen_mri_triage_logreg_v0_1` | `benign_one_patient.h5` | `0.8524639494195422` / `0.3640352477169748` / `1` | identical | PASS |
| B2 | `d6df5c67…2321` | `0.2.0-paper-reference` | `benign_one_patient.h5` | `0.7726940329943811` / `0.3585907282566089` / `1` | identical | PASS |
| B3 | `596f8e10…87eb` | `bremen_mri_triage_symmetry_logreg_0_2_0-research` | `benign_one_patient.h5` | `0.6848549443589647` / `0.4130396520921527` / `1` | identical | PASS |
| A1 | `02be0ce3…2b4c` | `0.2.12-beta` | `cabce03d…h5`, `Nova_214`, left | `0.8693870739736473` / `0.24665932038818544` | identical | PASS |
| A2 | `7ebd6680…4e49` | `0.2.13-beta` | `cabce03d…h5`, `Nova_214`, left | `0.8693870739736473` / `0.24665932038818544` | identical | PASS |

Install times (real pip, local wheelhouses): B1 28.7 s, B2 83.3 s, B3 77.4 s,
A1 78.2 s, A2 75.9 s.

**B2 remains exactly: probability `0.7726940329943811`, threshold
`0.3585907282566089`, prediction `1`.
No scientific output changed.

## Expected-failure paths through the same supervisor

Script: `/tmp/ir05/failure_cases.py` using the installed releases and
`SubprocessRuntime`.

| Variant | Fixture | Typed exception | Safe reason |
|---|---|---|---|
| B1 | `cancer_one_patient.h5` | `ModelPreprocessingFailedError` | `raw_peak_gate_failed` |
| B2 | `cancer_one_patient.h5` | `ModelPreprocessingFailedError` | `raw_peak_gate_failed` |
| B3 | `atypical_one_patient.h5` | `ModelInputInvalidError` | `requires_exactly_3_left_3_right` |

Aramina preprocessing failure (A1, `Nova_376.h5`, left) through the full
executor path preserves the structured diagnostic — see
`SUPERVISOR_EVIDENCE.md` (legacy == candidate, `PARITY True`).

## IR-03 parity against the same new releases

`BREMEN_IR03_RELEASES=/tmp/ir05/releases pytest -q tests/test_ir03_parity.py`
→ **21 passed**.

## Notes

- No `InstalledRelease` was constructed by hand in this evidence; the real
  `ReleaseCache.install()` produced it.
- No legacy in-process runtime was invoked on these cases.
- No live S3 was used; the S3 boundary is a deterministic local stub.
