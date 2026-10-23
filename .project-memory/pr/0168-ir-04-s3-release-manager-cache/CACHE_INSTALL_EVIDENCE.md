# CACHE_INSTALL_EVIDENCE.md — PR0168 IR-04

All evidence is local. No AWS call was made.

**LIVE_S3_EVIDENCE: NOT RUN - NO AUTHORIZED ACCESS**

## Environment

```
host:        macOS 26.5.1 arm64
python:      3.13.12 (/tmp/bremen-ir01-exec-venv/bin/python)
releases:    /tmp/ir04/releases/<variant>   (rebuilt IR-03 output)
caches:      /tmp/ir04/cache-all-final/<variant>, /tmp/ir04/cache-prefix
catalog:     s3://trusted-bucket/           (root prefix run)
             s3://trusted-bucket/catalog/   (prefix-boundary run)
```

Inputs are operator-local and not committed. The S3 boundary is a deterministic
stub that serves exactly the manifest-bound keys from the local release
directory; `venv` and `pip` are real, and no network index is used.

## Rebuilt release closure

| Slot | manifest SHA-256 | main wheels | aux wheels | golden fixtures |
|---|---|---|---|---|
| A1 | `12c72fb463a216e16f0feee5ac1196bd293f8844401c3ee737dac66834d35491` | 13 | 54 | 2 |
| A2 | `ec77dfe981224f8fb3ad88aabe93a88e5d4dd7ac9e0a779bec8d0c5b102cf935` | 13 | 54 | 2 |
| B1 | `8f651fc100aceff22fda490b896c4f12569d77678b4a87ff8ca897c8cb7d0e13` | 13 | 0 | 3 |
| B2 | `6f6d5b863e0f9d419dd3bf1f9b3ee098b61d1ba493c34ee981db3280634e88e4` | 13 | 54 | 2 |
| B3 | `ea313396b4bbbef2bea3584ab1ca4f81bba309df4e7968189cb0011ead4f5d17` | 13 | 54 | 2 |

Plugin wheel `029af6c73238cd83d31f1dea31fa52cbbd69f4236e14ba317f076e04affa7e82`.
Per-file wheel and golden-fixture hashes are listed in
`RELEASE_CLOSURE_EVIDENCE.md`.

## Cold release-bound installation

No `BREMEN_RELEASE_WHEELHOUSE` and no `BREMEN_RELEASE_GOLDEN_FIXTURES` were
set (both variables no longer exist in the implementation). Each release was
installed from its own declared objects only.

| Release | digest | cold s | warm s | golden cases | bucket observed | READY |
|---|---|---|---|---|---|---|
| B1 | `8f651fc1…0e13` | 25.8 | 0.0 | 3 | `trusted-bucket` | yes |
| B2 | `6f6d5b86…88e4` | 79.4 | 0.0 | 2 | `trusted-bucket` | yes |
| B3 | `ea313396…4f5d17` | 68.6 | 0.0 | 2 | `trusted-bucket` | yes |
| A1 | `12c72fb4…5491` | 67.3 | 0.0 | 2 | `trusted-bucket` | yes |
| A2 | `ec77dfe9…8935` | 80.0 | 0.0 | 2 | `trusted-bucket` | yes |

Command: `/tmp/ir04/full_cache_check_final.py` (real installer, local stub S3,
root-prefix catalog configuration). Warm installs reused READY with no
installer command.

## Closure verification

`ReleaseCache._verify_wheel_closure` ran on every install and confirmed:

- every manifest-declared wheel exists at its release path and matches its
  declared SHA-256;
- no undeclared wheel file exists in `wheelhouse/main` or `wheelhouse/aux/*`;
- every hash referenced by `requirements/main.lock` and each
  `requirements/aux-<tag>.lock` is present in that environment's release-local
  wheelhouse.

pip was invoked only with release-local `--find-links` directories, plus
`--no-index --only-binary=:all: --require-hashes`.

## Mandatory golden READY gate

Every release reached READY only after every release-defined case passed.

- B2 benign: probability `0.7726940329943811`, threshold
  `0.3585907282566089`, prediction `1` — exact.
- B1 benign `0.8524639494195422` / `0.3640352477169748` / `1`; Nova_376
  `0.5677291934209037` / `0.3640352477169748` / `1`; cancer
  `QC_FAILED` / `raw_peak_gate_failed`.
- B3 benign `0.6848549443589647` / `0.4130396520921527` / `1`; atypical
  `INPUT_INVALID` / `requires_exactly_3_left_3_right`.
- A1/A2 Nova_214 left `0.8693870739736473` / `0.24665932038818544` / `1`;
  Nova_376 `QC_FAILED` / `ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract`.

A post-install predict of B2 through the installed interpreter reproduced
`0.7726940329943811` / `0.3585907282566089` / `1`.

## Trusted bucket and prefix

Run with `catalog_uri=s3://trusted-bucket/catalog/`:

| Test | Result |
|---|---|
| inside-prefix install (`catalog/releases/<id>/manifest.json`) | installed, READY written, digest matches |
| outside-prefix key (`releases/<id>/manifest.json`) | `release_reference_invalid`, **0 S3 requests** |
| lookalike prefix (`catalog-evil/…`) | `release_reference_invalid`, 0 S3 requests |
| nested valid key (`catalog/releases/team/model/manifest.json`) | resolves |
| root prefix (`s3://trusted-bucket/`) | all five releases installed and READY |
| absolute / `..` / other-prefix keys | `release_reference_invalid` |

All observed S3 bucket arguments were `trusted-bucket`; no call supplied a
different bucket.

## Corruption and negative proofs

| Tamper | Result category | READY |
|---|---|---|
| corrupt dependency wheel (same-length byte flip) | `release_file_checksum_mismatch` | no |
| corrupt golden fixture (same-length byte flip) | `release_file_checksum_mismatch` | no |
| wrong expected probability in `cases.json` | `smoke_failed` | no |

Additional unit coverage: missing manifest/object/wheel, file size mismatch,
path traversal, duplicate relative path, identity mismatch, incompatible host
(implementation/version/ABI/OS/arch/protocol), offline install failure,
interrupted install + retry, three-way concurrent install, corrupt READY,
insufficient disk and budget, inactive eviction, protected survival, partial
entries never evicted.

## Subprocess environment isolation

Parent seeded with `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_SESSION_TOKEN` and `PYTHONPATH`. A real child process under the restricted
environment saw only:

```
HOME, LANG, PATH, PIP_DISABLE_PIP_VERSION_CHECK, PIP_NO_INPUT,
PYTHONDONTWRITEBYTECODE, PYTHONNOUSERSITE, TMPDIR, __CF_USER_TEXT_ENCODING
```

No `AWS*`, `BOTO*` or `PYTHONPATH` keys. The same restricted environment is
applied to `venv`, pip and the scientific entrypoint, and the installed B2
release still produced its frozen value under it.

## Current validation counts

| Command | Result |
|---|---|
| `python3 -m compileall -q src tests` | exit 0 |
| `pytest -q tests/test_ir04_release_cache.py` | 65 passed |
| targeted discovery/registry/contracts/worker/IR-04 | 528 passed |
| IR-03 plugin/wheel/import tests | 59 passed |
| runtime + IR-03 parity against rebuilt releases | 21 passed |
| full suite | 4437 passed, 8 skipped, 40 warnings |
| `git diff --check` | exit 0 |

## Not run

- Live S3 upload/list/version evidence (no authorized access).
- IR-05 worker supervision.
- IR-06 App Runner verification.
