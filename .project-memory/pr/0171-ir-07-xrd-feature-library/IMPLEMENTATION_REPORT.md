# IR-07 implementation report — external XRD feature-library integration

## TASK COMPLETE

The standalone `xrd-inference-features` package now owns the Bremen 15-feature
and Aramina CORE4 (v0.1/v0.2) scientific contracts, byte-identically extracted.
Every Model Release independently builds and binds the exact feature-library
wheel it needs; it is never a Bremen/App Runner application dependency.
Release-backed Worker execution computes features through the library;
legacy in-process execution is unchanged until IR-08.

## Architecture before / after

Before: `release_build/assemble.py` built only the plugin wheel; manifests had
no feature-wheel binding; `feature_order_hash` was computed by importing the
embedded `bremen_v01.features`/`aramina_v0213.manifest` modules directly;
`ReleaseCache` installed only the plugin wheel.

After: `assemble_release` also builds a deterministic `xrd_inference_features`
wheel, resolves that release's real feature contract from its own staged
artifact bytes, and emits an additive `feature_library` manifest block
(`distribution`/`version`/`contract`/`wheel_filename`/`wheel_sha256`) plus a
`feature_library_wheel` file role. `ReleaseCache._install_environments`
installs that wheel into the release's own venv (reusing the exact plugin-wheel
installer, `_pip_install_wheel`). The Worker process explicitly selects the
external backend via `BREMEN_FEATURE_LIBRARY_BACKEND`
(`ml_plugin.release.apply_feature_library_backend`, called only when the
manifest declares a `feature_library` block); `bremen_v01/runtime.py` and
`aramina_v0213/inference.py` check that one environment variable at call time
and route to `xrd_inference_features` or the embedded module accordingly.
`feature_order_hash` is now derived from the library, never the embedded
modules.

## Files changed

```
.project-memory/pr/ir-07/PLAN.md                        (rewritten for current IR-07 scope)
.project-memory/pr/0171-ir-07-xrd-feature-library/**     (new: PLAN, this report, FEATURE_CONTRACTS, WHEEL_EVIDENCE, FIVE_RELEASE_PARITY)
packages/xrd-inference-features/**                        (new standalone package)
src/bremen/contracts/inference_release.py                (+feature_library block, validator)
src/bremen/release_build/feature_wheel.py                 (new deterministic builder)
src/bremen/release_build/assemble.py                      (build/bind feature wheel; contract resolution; feature_order_hash from library)
src/bremen/platform/models/release_cache.py               (install feature_library_wheel role)
src/bremen/ml_plugin/release.py                           (feature_library_backend config + apply_feature_library_backend)
src/bremen/ml_plugin/inference.py                         (call apply_feature_library_backend)
src/bremen/model_packages/bremen_v01/runtime.py            (backend-selection seam)
src/bremen/model_packages/aramina_v0213/inference.py       (backend-selection seam)
tests/test_ir07_feature_library_parity.py                 (new: differential parity, backend-selection regression, parent-import-boundary)
tests/test_inference_release_contract.py                  (+12 feature_library tests)
tests/test_aramina_workflow_runtime.py                     (extended reviewed env-call allowlist)
```

No source/runtime file outside this list was touched. No scientific
coefficient, threshold, ROI, normalization, pairing, feature name, or feature
order changed anywhere.

## Standalone package status

`packages/xrd-inference-features/` installs and tests cleanly in a brand-new
venv with **no Bremen present** (15/15 tests pass there). It depends only on
`numpy==2.5.4`, `pandas==3.0.6`, `scipy==1.18.1` — the same versions already
pinned for the plugin wheel. `xrd-inference-features` is **not** in Bremen's
root `pyproject.toml` `[project.dependencies]` (confirmed unmodified).

## Feature contracts

See `FEATURE_CONTRACTS.md` for the full derivation. Summary:

```
A1: aramina_sk_symmetry_v0_2
A2: aramina_sk_symmetry_v0_2
B1: bremen_feature_schema_v0.1
B2: bremen_feature_schema_v0.1
B3: bremen_feature_schema_v0.1
```

Both read directly from the actual staged artifacts (Aramina) or the single
known embedded module (Bremen) — never guessed.

## Plugin external-feature integration

`bremen_v01/runtime.py::_compute_bremen_features[_from_frame]` and
`aramina_v0213/inference.py::_compute_symmetry_features` check
`os.environ.get("BREMEN_FEATURE_LIBRARY_BACKEND") == "xrd_inference_features"`
at call time and import `xrd_inference_features` lazily only then; otherwise
they call the embedded implementation unchanged. This is explicit and
release-scoped (set only inside a release Worker process by
`apply_feature_library_backend`), not import-presence duck typing — verified
by a regression test (`test_backend_default_is_embedded_even_with_library_importable`)
proving the library being importable in the test process never flips legacy
behavior, and by running the full relevant suite both with and without the
package installed in the dev venv.

## Release Cache installation

`_install_environments` now also looks up the optional `feature_library_wheel`
role (`_role_path_optional`, new) and, when present, installs it exactly the
way the plugin wheel is installed (`_pip_install_wheel`: `--no-index --no-deps
--force-reinstall`, no change to `main.lock`/`--require-hashes`). No second
installer mechanism was added. All 65 pre-existing IR-04 release-cache tests
pass unmodified.

## Parent import boundary

`test_platform_discovery_and_registry_import_without_feature_library` spawns a
fresh subprocess that blocks `import xrd_inference_features` and confirms
`bremen.platform.models.discovery`, `release_cache`, `bremen.platform.runtime.
registry`, `subprocess_runtime`, and `bremen.contracts.inference_release` all
import cleanly without it. A second test
(`test_platform_parent_modules_do_not_import_feature_library`) statically
confirms (AST) that none of those modules reference
`xrd_inference_features` at all.

## Release-venv import proof

The real `ReleaseCache.install()` run for B2 resolved
`xrd_inference_features.__file__` to
`<cache_root>/<digest>/env/lib/python3.13/site-packages/xrd_inference_features/__init__.py`
— strictly inside that release's own installed venv. Captured via a
test-only diagnostic script (`.project-memory/pr/0171-.../_scratch_install_proof.py`);
no filesystem path is exposed through any public result contract.

## Differential feature parity

`tests/test_ir07_feature_library_parity.py`: 16 tests, all passing — exact
equality (`rtol=0, atol=0`) between the embedded implementation and the
library for all 15 Bremen features (including left/right-permutation
invariance) on the real frozen fixture (`tests/bremen_3x3_helpers.make_case`),
and for both Aramina contracts across varying target/contralateral counts
plus the no-contralateral neutral case.

## New feature wheel

```
filename: xrd_inference_features-0.1.0-py3-none-any.whl
version:  0.1.0
sha256:   75498c315990dbe26e591c13c9cb64f06eb9b4139f57608bba4b8576db84a72d
```

## New plugin wheel

```
sha256: 67ed55226d7c8088f013a11aa9723f8bc0b3b346053e2f0000403563b196efae
```

## Rebuilt releases (manifest sha256, see WHEEL_EVIDENCE.md)

```
A1: 94a0033b64fd8e664cbd515607cf5d03f3820b9f9ebc0125edcecd5bf2984498
A2: 2126e2c325003b014a80db7d927d31285ff71b03afa172dd0dd7c3b9ee8025df
B1: b9169e1766c3ffb56561c5668af0c2f264a363ec6493f893e35e48c8b2b59088
B2: c384a27f21d98d78025360ed77c4db5eb72f1cf9b007a549b52591c7a56a69a2
B3: 940c41427b2d7b4bba6d39c4e1905dd5d661ce8273a261205e3db8a65fb1d9a3
```

## Five-release parity

All five reached READY through a real `ReleaseCache.install()` (real
pip/venv, local-file-backed S3 stub only) with every golden case passing
`_smoke_golden`'s full expected-result comparison, including B2's exact hard
gate (`probability=0.7726940329943811`, `threshold_applied=0.3585907282566089`,
`prediction=1`). See `FIVE_RELEASE_PARITY.md`.

## Validation (actual current counts, this session)

```
python -m compileall -q src tests packages/xrd-inference-features/src: passed
Full repo suite: 4536 passed, 8 skipped, 39 warnings
Standalone package (isolated venv, no bremen): 15 passed
git diff --check: passed
```

## Scikit-learn build-input resolution

Blocker: the build wheelhouse first tried (`/tmp/ir03/wheelhouse`) had only
`scikit_learn-1.9.1`, not the pinned `1.9.0`. Resolution: the exact
`scikit_learn-1.9.0-cp313-cp313-macosx_12_0_arm64.whl` (sha256
`5b934c45c252844a91d69fda3a34cff5e7307e1db10d77cb10a3980312c74713`) already
existed locally in `/tmp/ir04/wheelhouse-all` from prior IR-04 build evidence;
that wheelhouse was used for all five rebuilds instead. No pin was loosened,
no hash check disabled, no network install used.

## Warnings

- Evidence scripts (`_scratch_install_proof.py`, `_scratch_five_release_parity.py`,
  `_five_release_parity_result.json`) live under `.project-memory/pr/0171-.../`
  as manual, non-pytest reproducibility evidence; they are not part of the test
  suite and were explicitly excluded from pytest collection by location.
- This is local evidence only (temporary cache roots, local-file-backed S3
  stub). No AWS/App Runner/live deployment evidence was gathered or claimed.

## Remaining blockers

None identified for IR-07's own scope. IR-08 (legacy inference cleanup) is
explicitly out of scope for this PR and untouched.

## Next required action

Precommit review.
