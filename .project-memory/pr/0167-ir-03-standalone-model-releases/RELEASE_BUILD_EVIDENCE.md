# RELEASE_BUILD_EVIDENCE.md — PR0167 IR-03 standalone model releases

All work is local.  No S3 publication, registry push, network-serving call or
model activation was performed.  Local evidence lives under `/tmp/ir03`; it is
operator-local evidence and is intentionally not committed.

## Environment

```
Python:      3.13.12 (CPython, macOS arm64)
Platform:    macOS-26.5.1-arm64-arm-64bit
Interpreter: /tmp/bremen-ir01-exec-venv/bin/python3   (repository tests/build)
             /tmp/ir03/clean-venv-final2/bin/python   (clean standalone run)
Aux:         /tmp/ir03/aux-clean-017b/bin/python      (xrd-preprocessing 0.1.7b0)
             /tmp/ir03/aux-clean-019/bin/python       (xrd-preprocessing 0.1.9b0)
```

`xrd-preprocessing` source commits used:

| Release tag | Distribution version | Source commit |
|---|---|---|
| `v0.1.7-beta` | `0.1.7b0` | `45d5568248e9774b7938a36e028d80e72b130b19` |
| `v0.1.9-beta` | `0.1.9b0` | `88dcaa277c5a0d4be2ab637bc5827a14bd106bea` |

The v0.1.7-beta tag had moved to a different commit (IR-01 finding).  The
wheelhouse wheel was built from the exact pinned commit above; the release
provenance records that explicit value rather than relying on the moved tag or
on `direct_url.json` (absent for wheel installs).

## Plugin wheel

Deterministic build command:

```bash
python3 -m bremen.release_build.assemble \
  --variant <a1|a2|b1|b2|b3> \
  --artifact-dir <IR-01 artifact directory> \
  --output-dir /tmp/ir03/releases-final/<variant> \
  --fixtures /tmp/bremen-ir01-fixtures/v0.1 \
  --wheelhouse /tmp/ir03/wheelhouse \
  --aux-python v0.1.7-beta=/tmp/ir03/aux-clean-017b/bin/python \
  --aux-python v0.1.9-beta=/tmp/ir03/aux-clean-019/bin/python \
  --aux-source-commit v0.1.7-beta=45d5568248e9774b7938a36e028d80e72b130b19 \
  --aux-source-commit v0.1.9-beta=88dcaa277c5a0d4be2ab637bc5827a14bd106bea
```

Only the auxiliary flags required by that variant are passed (B1 needs none).

| Property | Value |
|---|---|
| Distribution | `bremen-ml-plugin` |
| Version | `0.1.0` |
| Filename | `bremen_ml_plugin-0.1.0-py3-none-any.whl` |
| SHA-256 | `324902c4a277613034d6cb35997d72833844f20f4777f241b7b5316b8a4fdf9b` |
| Size | `111548` bytes |
| Entrypoint | `bremen.ml_plugin.entrypoint:main` |
| Console script | `bremen-ml-worker` |

Reproducibility: two independent builds of the same source produced identical
bytes/SHA-256 (`tests/test_ir03_plugin_wheel.py::test_plugin_wheel_is_byte_reproducible`).
Wheel members are sorted, timestamps fixed at `2020-01-01T00:00:00`, and
`RECORD` hashes are verified by test.

Wheel contents (allowlist): `bremen/__init__.py`,
`bremen/model_packages_bridge.py`, `bremen/contracts/**`,
`bremen/model_packages/**`, `bremen/ml_plugin/**`, `.dist-info`.  No
`bremen/platform`, `bremen/api`, FastAPI, boto3, UI, training or application
modules.

## Five release descriptors

Every release uses the same plugin wheel and its own immutable artifact copy.
`s3_key` values in the manifests are intended future object keys; nothing was
uploaded.

| Slot | release_id | model_version | artifact SHA-256 | manifest SHA-256 |
|---|---|---|---|---|
| A1 | `aramina-target-breast-risk-0-2-12-beta-9bb9111` | `0.2.12-beta` | `9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d` | `33babf2ce23e2f82d08d0065c0b48f6d9c266eea3593c724fc64616705336f70` |
| A2 | `aramina-target-breast-risk-0-2-13-beta-f5e4a04` | `0.2.13-beta` | `f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b` | `35d174fb2811ed2dc234eefd690740dc5b8f42c338d2dc038e6fca4c08fbe851` |
| B1 | `bremen-mri-triage-logreg-v0-1` | `bremen_mri_triage_logreg_v0_1` | `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` | `6f9f02145201ea9f3e28b0f3319358bbf1fe964354de29da54fb4e4e5988b4eb` |
| B2 | `bremen-paper-reference-v0-2-0` | `0.2.0-paper-reference` | `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` | `99aa118ebf01d9f999744fb9e1f38d98783140262e56a32a61fb24c7d5f71320` |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `bremen_mri_triage_symmetry_logreg_0_2_0-research` | `971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4` | `76607bf3b48fe7062a0e7806692d21f6dbe401fe07f36d3b3a248410da2c520f` |

Manifests validate with `bremen.contracts.inference_release.validate_release_manifest`
for all five variants (`tests/test_ir03_parity.py::test_release_manifest_is_valid`).

Release file hashes (first 16 hex chars shown; full values in
`release.json` / the manifest):

| File | A1 | A2 | B1 | B2 | B3 |
|---|---|---|---|---|---|
| `plugin/bremen_ml_plugin-0.1.0-py3-none-any.whl` | `324902c4a2776130` | same | same | same | same |
| `configs/runtime.json` | `9b6a5bce7cdcde3f` | `1d8e3b661f696f27` | `939bbc5e1fec127c` | `67e73bbd8c5dee10` | `fd135fba39a0d090` |
| `configs/artifact_manifest.json` | `e866efb02cba5875` | `4da2017914a84ed0` | `98fa089f21e5403c` | `ab6924c76b29ae26` | `b6a8817158585088` |
| `provenance/build.json` | `69c8b762f368e914` | `7ffac71277f11ac1` | `b599f266859f5387` | `20ba21dc67689e19` | `dab27befe94abe11` |
| `requirements/main.lock` | `b7be527baf7771d1` | same | same | same | same |
| `golden_tests/cases.json` | `40a0ccaeab38a366` | `814df782969d5f00` | `31af56ee636ce702` | `7759a628676f7a0f` | `0022d24e06e0d229` |

## Dependency closure

Main environment — exact observed versions, hash-locked in every release
(`requirements/main.lock`):

```
numpy==2.5.4 --hash=sha256:6d6a71b9d9a97c03633aa12565ef2825ffa036cc1d99cfd50dacf0f128af4fe2
pandas==3.0.6 --hash=sha256:60d81f9e1799b36f3739e7fff44d1fbb2e8fd5a271b3863e03de9715fccda0fa
scipy==1.18.1 --hash=sha256:ea324d9dd34c38bfb9bec8ca4d1b407db97dbb74029f566b8e322b1b6fe56fe6
scikit-learn==1.9.1 --hash=sha256:61cd968ab831a76d0ecbaf0347ab2270268716da28f94fd022497e3d6f205f13
joblib==1.6.0 --hash=sha256:3dbbf9f6e4b592a2357b854608e980fe6390d131d7a82f011a377ef2ebef7aba
h5py==3.16.0 --hash=sha256:42108e93326c50c2810025aade9eac9d6827524cdccc7d4b75a546e5ab308edb
PyYAML==6.0.3 --hash=sha256:2283a07e2c21a2aa78d9c4442724ec1eb15f5e42a723b99cb3d822d48f5f7ad1
python-dateutil==2.9.0.post0 --hash=sha256:a8b2bc7bffae282281c8140a97d3aa9c14da0b136dfe83f850eea9a5f7470427
six==1.17.0 --hash=sha256:4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274
threadpoolctl==3.7.0 --hash=sha256:cd8b60b5641b45c67bbf73c64c843235fc2d8a480c87389f52f5dbee893b86be
packaging==26.3 --hash=sha256:d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c
cloudpickle==3.1.2 --hash=sha256:9acb47f6afd73f60dc1df93bb801b472f05ff42fa6c84167d25cb206be1fbf4a
narwhals==2.27.1 --hash=sha256:d057df13f5852b8e157596e82eb5e955fad267425df5e420e0ee9863da483b31
```

Main wheelhouse: `/tmp/ir03/wheelhouse`, 13 wheels, all hashes recorded in the
lock.  `xrd-preprocessing` is deliberately absent from the main lock.

Auxiliary environments — exact observed closures written to
`requirements/aux-v0.1.7-beta.lock` (54 pins) and
`requirements/aux-v0.1.9-beta.lock` (54 pins).  The auxiliary wheelhouses are:

- `/tmp/ir03/wheelhouse-aux-017b` (54 wheels), including
  `xrd_preprocessing-0.1.7b0-py3-none-any.whl`
  SHA-256 `8e5631290a99719383425f13f09b876490a9373aca22d8808aa0535e2811ea1c`
- `/tmp/ir03/wheelhouse-aux-019` (55 files), including
  `xrd_preprocessing-0.1.9b0-py3-none-any.whl`
  SHA-256 `6cdb2540df3531734582299a2eccd701677f88bdd31c4cbb16d5f2e1e2d441a6`
  (built from `xrd-preprocessing-0.1.9b0.zip`,
  SHA-256 `95d09af57e2909ebead7d5ce7b79a6f188675a1904fbbd10affc163329d10bfd`)

Both auxiliary environments were installed fully offline:

```bash
python3.13 -m venv /tmp/ir03/aux-clean-017b
python3.13 -m venv /tmp/ir03/aux-clean-019
/tmp/ir03/aux-clean-017b/bin/pip install --no-index \
  --find-links /tmp/ir03/wheelhouse-aux-017b xrd-preprocessing==0.1.7b0
/tmp/ir03/aux-clean-019/bin/pip install --no-index \
  --find-links /tmp/ir03/wheelhouse-aux-019 xrd-preprocessing==0.1.9b0
```

(No network index was used in either command; both completed successfully.)

## Clean main environment

```bash
python3.13 -m venv /tmp/ir03/clean-venv-final2
/tmp/ir03/clean-venv-final2/bin/pip install --no-index \
  --find-links /tmp/ir03/wheelhouse \
  /tmp/ir03/releases-final/b2/plugin/bremen_ml_plugin-0.1.0-py3-none-any.whl
```

Installed packages (exact, no application distribution):

```
bremen-ml-plugin 0.1.0        numpy 2.5.4          pandas 3.0.6
scipy 1.18.1                  scikit-learn 1.9.1   joblib 1.6.0
h5py 3.16.0                   PyYAML 6.0.3         python-dateutil 2.9.0.post0
six 1.17.0                    threadpoolctl 3.7.0  packaging 26.3
cloudpickle 3.1.2             narwhals 2.27.1
```

Boundary checks:

```
bremen.__file__            = /tmp/ir03/clean-venv-final2/lib/python3.13/site-packages/bremen/__init__.py
importlib spec bremen.platform = None
importlib spec bremen.api      = None
importlib spec fastapi         = None
import bremen.platform         -> ModuleNotFoundError
```

## Reproducibility / provenance notes

- Release `build.commit` is the real repository HEAD read via
  `git rev-parse HEAD`; the builder refuses to build if no commit is available.
- `build_id` is `ir03-<variant>-<commit[:12]>`.
- Artifact bytes are copied and re-hashed; a mismatch against the IR-01 pinned
  checksum fails assembly.
- Preprocessing provenance records whether it came from observed
  `direct_url.json` or from the explicit wheelhouse source commit.  For
  v0.1.7-beta both the version and the exact commit are mandatory.
- No generated wheel, release, artifact, fixture or wheelhouse is committed to
  the repository.

---

# Review-fix rebuild (`0167-ir-03-standalone-model-releases-review-fixes`)

**All hashes, locks and environments in the sections above are superseded by
this section.**  They were produced before the three reproducibility blockers
were fixed and are retained only as history.

## BLOCKERS RECEIVED

- RELEASE-AUX-HASHES — auxiliary locks not fully hash-pinned.
- RELEASE-AUX-PORTABILITY — absolute machine-local auxiliary interpreter paths
  in release descriptors.
- RELEASE-SKLEARN-CLOSURE — standalone environment pinned scikit-learn 1.9.1
  while artifacts record training with 1.9.0.

## FIXES IMPLEMENTED

- Auxiliary locks are generated from each auxiliary wheelhouse; a missing wheel
  hash is a hard build failure.  There is no fallback to an unpinned line.
- Release descriptors use logical `@aux/<tag>` references.  Runtime resolution:
  `<release>/aux/<tag>/bin/python` first, then
  `$BREMEN_IR03_AUX_ENV_ROOT/<tag>/bin/python`.  Absolute values are rejected.
  Manifest `environments.<aux>` carries `environment_ref`, not a path.
- Main environment pins `scikit-learn==1.9.0`; the exact CPython 3.13/macOS
  arm64 wheel is available and was installed from the local wheelhouse.

## SIMPLICITY DECISIONS

Existing lock builder, assembler and runtime-config applier were extended;
no new source module, registry, factory or abstraction layer was introduced.

## LOCK INTEGRITY RESULTS

| Lock | Pins | Hash lines | SHA-256 |
|---|---|---|---|
| `requirements/main.lock` | 13 | 13 | `5c7127cf3cfee9eea495f6fab68c2ff01d148167f44d4391ebc0ae0be71af343` |
| `requirements/aux-v0.1.7-beta.lock` | 54 | 54 | `f04603782be34685410e6faa294c971d304ff5db35413480165fd945438dd2f7` |
| `requirements/aux-v0.1.9-beta.lock` | 54 | 54 | `c31e23d2ed22c3bd1bc797b827f594b04fb583431df48916381619b9188cfdb6` |

Strict offline installs, each in a fresh venv:

```bash
pip install --no-index --only-binary=:all: --require-hashes \
  --find-links /tmp/ir03/wh190-main \
  -r /tmp/ir03/releases-final/b2/requirements/main.lock
# exit 0

pip install --no-index --only-binary=:all: --require-hashes \
  --find-links /tmp/ir03/wheelhouse-aux-017b \
  -r /tmp/ir03/releases-final/b2/requirements/aux-v0.1.7-beta.lock
# exit 0

pip install --no-index --only-binary=:all: --require-hashes \
  --find-links /tmp/ir03/wheelhouse-aux-019 \
  -r /tmp/ir03/releases-final/a2/requirements/aux-v0.1.9-beta.lock
# exit 0
```

`provenance/build.json` now records `hash_locked_main=true` and
`hash_locked_aux=true` for releases with auxiliary environments (B1 has no
auxiliary environment and records `hash_locked_aux=false` legitimately).

Negative tests (incomplete hashes rejected):

- `test_lock_lines_require_a_hash_for_every_requirement`
- `test_lock_lines_reject_missing_wheelhouse`
- `test_aux_lock_rejects_missing_wheelhouse`
- `test_main_lock_is_fully_hash_pinned`

## PORTABILITY RESULTS

Generated `configs/runtime.json` example (B2):

```json
{
  "preprocessing_environment": {
    "BREMEN_PREPROCESS_PROVENANCE": "@release/provenance/xrd-preprocessing-v0.1.7-beta.json",
    "BREMEN_PREPROCESS_PYTHON": "@aux/v0.1.7-beta"
  }
}
```

Manifest auxiliary environment entry:

```json
{
  "environment_ref": "@aux/v0.1.7-beta",
  "preprocessing_release": "v0.1.7-beta",
  "requirements_lock_sha256": "f04603782be34685410e6faa294c971d304ff5db35413480165fd945438dd2f7"
}
```

No absolute `/tmp` or `/private/tmp` path exists in any generated
`configs/**` or `manifest.json`.  A copied release at
`/tmp/ir03/relocated/{b2,a1}` ran unchanged and reproduced its frozen value;
the only machine-specific input is the `BREMEN_IR03_AUX_ENV_ROOT` environment
variable that locates materialized auxiliary environments (IR-04 will own
materializing them).

## DEPENDENCY VERSIONS

Clean main environment (`/tmp/ir03/clean-190`), installed from the main lock:

```
PyYAML==6.0.3
bremen-ml-plugin==0.1.0
cloudpickle==3.1.2
h5py==3.16.0
joblib==1.6.0
narwhals==2.27.1
numpy==2.5.4
packaging==26.3
pandas==3.0.6
python-dateutil==2.9.0.post0
scikit-learn==1.9.0
scipy==1.18.1
six==1.17.0
threadpoolctl==3.7.0
```

`sklearn.__version__` in that environment: `1.9.0`.

Auxiliary environments:

- `/tmp/ir03/lockcheck-aux17` — `xrd-preprocessing==0.1.7b0`
- `/tmp/ir03/lockcheck-aux19` — `xrd-preprocessing==0.1.9b0`
- both installed strictly from their hash-locked files with `--no-index
  --only-binary=:all: --require-hashes`.

Main wheelhouse `/tmp/ir03/wh190-main` (13 wheels), including:

```
scikit_learn-1.9.0-cp313-cp313-macosx_12_0_arm64.whl
sha256 5b934c45c252844a91d69fda3a34cff5e7307e1db10d77cb10a3980312c74713  8228299 bytes
```

Auxiliary wheelhouses: `/tmp/ir03/wheelhouse-aux-017b` (54 files),
`/tmp/ir03/wheelhouse-aux-019` (55 files).

## REBUILT RELEASE HASHES

Plugin wheel: `bremen_ml_plugin-0.1.0-py3-none-any.whl`,
SHA-256 `029af6c73238cd83d31f1dea31fa52cbbd69f4236e14ba317f076e04affa7e82`,
size `112060`.

| Slot | manifest SHA-256 | artifact SHA-256 |
|---|---|---|
| A1 | `81a6c75aa4eae4888043452b42d0cb79371ea2d5a99a9a0464a70d101eeabc46` | `9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d` |
| A2 | `35a1e9ba21a9e5f1a716390076e7b22a93aeb7943a52a28b0847e5b482d51208` | `f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b` |
| B1 | `4629a4c455dd52ca1c9b631907aff2a9c293c6815301fcb496f3e1a6f72b7ea1` | `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` |
| B2 | `d3eb9d92a8b470ac038d965e9c877617ab4dec67e77f912fa1fd73a072394bc7` | `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` |
| B3 | `1e7078b18754f732ab72665b5a3fe8bbe137ce246edf389792fdb16bd4abe49e` | `971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4` |

Release file hashes:

| File | A1 | A2 | B1 | B2 | B3 |
|---|---|---|---|---|---|
| `plugin/…whl` | `029af6c73238cd83` | same | same | same | same |
| `configs/runtime.json` | `b6b0f4a8ecd77bb9` | `653cb3b2d3ef2649` | `939bbc5e1fec127c` | `4dac6e5d70b32b05` | `1778e58aff7c2b4b` |
| `configs/artifact_manifest.json` | `e866efb02cba5875` | `4da2017914a84ed0` | `98fa089f21e5403c` | `ab6924c76b29ae26` | `b6a8817158585088` |
| `provenance/build.json` | `8f9fc39370d5b4e4` | `53eb807bc35f9d5e` | `893ca75b4dd1f0b0` | `ecff2301070cb050` | `c64a34b728b9703d` |
| `requirements/main.lock` | `5c7127cf3cfee9ee` | same | same | same | same |
| `golden_tests/cases.json` | `40a0ccaeab38a366` | `814df782969d5f00` | `31af56ee636ce702` | `7759a628676f7a0f` | `0022d24e06e0d229` |

Rebuild command (per variant; only the flags that variant needs):

```bash
python3 -m bremen.release_build.assemble \
  --variant <a1|a2|b1|b2|b3> \
  --artifact-dir <IR-01 artifact dir> \
  --output-dir /tmp/ir03/releases-final/<variant> \
  --fixtures /tmp/bremen-ir01-fixtures/v0.1 \
  --wheelhouse /tmp/ir03/wh190-main \
  --aux-python v0.1.7-beta=/tmp/ir03/lockcheck-aux17/bin/python \
  --aux-wheelhouse v0.1.7-beta=/tmp/ir03/wheelhouse-aux-017b \
  --aux-source-commit v0.1.7-beta=45d5568248e9774b7938a36e028d80e72b130b19
# v0.1.9-beta is used only by A2, with its own env/wheelhouse/commit
```

## VALIDATION RESULTS

See `IMPLEMENTATION_REPORT.md` § Review-fix pass for the full validation
table.  Key results: IR-03 tests 79 passed; full suite 4371 passed,
8 skipped; strict offline hash installs passed for main and both auxiliary
locks; absolute path grep clean; clean runtime scikit-learn 1.9.0; 11/11
frozen parity cases pass.

## WARNINGS

- Auxiliary environments retain scikit-learn 1.9.1 in their observed closure.
  They only execute the xrd-preprocessing worker; the standalone inference
  environment is pinned to 1.9.0.
- `matador_raw` canonicalization remains an explicit unsupported limitation.
- Auxiliary environments are materialized outside the release for this pass and
  located through `BREMEN_IR03_AUX_ENV_ROOT`; IR-04 owns actual installation.
- Local-only evidence; App Runner remains IR-06.

## REMAINING BLOCKERS

None for the three received release-reproducibility blockers.

## NEXT REQUIRED ACTION

Repeat precommit review.
