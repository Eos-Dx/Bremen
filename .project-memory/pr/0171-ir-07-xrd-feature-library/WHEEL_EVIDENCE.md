# IR-07 wheel evidence

All hashes below are from the current working tree (branch
`0171-ir-07-xrd-feature-library`), not reused from IR-06. Releases were
rebuilt twice during this PR (once before, once after adding the
`feature_library_backend` runtime-config field); the hashes below are from
the **final** rebuild, reproduced by the commands in `PLAN.md`.

## Feature-library wheel

Deterministic build, confirmed byte-identical across two independent builds
in the same session:

```
distribution: xrd-inference-features
version:      0.1.0
filename:     xrd_inference_features-0.1.0-py3-none-any.whl
sha256:       75498c315990dbe26e591c13c9cb64f06eb9b4139f57608bba4b8576db84a72d
size_bytes:   9695
```

This exact SHA-256 appears in all five rebuilt release manifests'
`feature_library.wheel_sha256` and matching `files[].sha256` for the
`feature_library_wheel` role — expected, since all five currently share the
same library version/contract set (Bremen's single contract, Aramina's dual
contract) and the build is bit-for-bit deterministic. Per the task's own
framing: "if two releases happen to build the same deterministic wheel bytes
... that is acceptable" — this is not reused evidence, it is the same
evidence independently reproduced by five separate `assemble_release()` calls.

## Plugin wheel

```
distribution: bremen-ml-plugin
version:      0.1.0
filename:     bremen_ml_plugin-0.1.0-py3-none-any.whl
sha256:       67ed55226d7c8088f013a11aa9723f8bc0b3b346053e2f0000403563b196efae
size_bytes:   115993
```

(Changed from the IR-06 plugin wheel SHA because the plugin source tree now
includes the IR-07 backend-selection seam in `bremen_v01/runtime.py` and
`aramina_v0213/inference.py`, and `ml_plugin/release.py`'s new
`apply_feature_library_backend`.)

## Five rebuilt release manifests

| Variant | release_id | manifest sha256 |
|---|---|---|
| A1 | `aramina-target-breast-risk-0-2-12-beta-9bb9111` | `94a0033b64fd8e664cbd515607cf5d03f3820b9f9ebc0125edcecd5bf2984498` |
| A2 | `aramina-target-breast-risk-0-2-13-beta-f5e4a04` | `2126e2c325003b014a80db7d927d31285ff71b03afa172dd0dd7c3b9ee8025df` |
| B1 | `bremen-mri-triage-logreg-v0-1` | `b9169e1766c3ffb56561c5668af0c2f264a363ec6493f893e35e48c8b2b59088` |
| B2 | `bremen-paper-reference-v0-2-0` | `c384a27f21d98d78025360ed77c4db5eb72f1cf9b007a549b52591c7a56a69a2` |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `940c41427b2d7b4bba6d39c4e1905dd5d661ce8273a261205e3db8a65fb1d9a3` |

Each manifest's `feature_library` block (identical across all five except
`contract`):

```json
{
  "distribution": "xrd-inference-features",
  "version": "0.1.0",
  "wheel_filename": "xrd_inference_features-0.1.0-py3-none-any.whl",
  "wheel_sha256": "75498c315990dbe26e591c13c9cb64f06eb9b4139f57608bba4b8576db84a72d"
}
```

`contract` is `aramina_sk_symmetry_v0_2` for A1/A2 and `bremen_feature_schema_v0.1`
for B1/B2/B3 — see `FEATURE_CONTRACTS.md` for how this was derived from the
actual staged artifacts, not guessed.

`scientific_metadata.feature_order_hash` (now derived from
`xrd_inference_features`, never the embedded modules):

```
Aramina (A1, A2): 1795926ceacf4eba522f5c5dd41f233cd37af851d7a867a9aed5df935d5b1567
Bremen (B1, B2, B3): 12ccf77a581adcc13a5587563476ef5db513d8b5a404f85c81102b9f39cb78a9
```

## Build-input blocker resolved (scikit-learn)

The pinned main-environment requirement is exactly `scikit-learn==1.9.0`
(unchanged, `release_build/wheel.py:PLUGIN_REQUIRES_DIST`). The wheelhouse
initially tried for this rebuild (`/tmp/ir03/wheelhouse`) only had
`scikit_learn-1.9.1`. The exact `1.9.0` wheel for this platform/Python
already existed locally from prior IR-04 build evidence:

```
/tmp/ir04/wheelhouse-all/scikit_learn-1.9.0-cp313-cp313-macosx_12_0_arm64.whl
sha256: 5b934c45c252844a91d69fda3a34cff5e7307e1db10d77cb10a3980312c74713
```

That wheelhouse (`/tmp/ir04/wheelhouse-all`) was used as `--wheelhouse` for
all five rebuilds instead of `/tmp/ir03/wheelhouse`; no pin was loosened, no
hash check was disabled, no network resolution was used.
