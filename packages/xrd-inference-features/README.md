# xrd-inference-features

Standalone, independently versioned Python distribution owning the reusable
XRD scientific feature computation consumed by Bremen and Aramina Model
Releases (see the Bremen inference-release roadmap, IR-07).

This package has **no** dependency on `bremen`, the Bremen platform, S3, the
catalog, or the Worker protocol. It is a pure scientific-feature library so it
can be moved to its own repository later without changing its public API or
the Model Release contract that binds it.

## Frozen contracts

- `xrd_inference_features.bremen_contract`: the 15 frozen Bremen feature names
  and values (`FEATURE_COLS`, `build_bremen_features_from_frame`),
  byte-identical extraction of the `bremen_v0_1_integrated_profile` contract.
- `xrd_inference_features.aramina_symmetry`: the Aramina CORE4 symmetry
  features (`CORE4`, `symmetry_features`), preserving the distinct
  `aramina_sk_symmetry_v0_1` and `aramina_sk_symmetry_v0_2` contracts exactly.

Each Model Release binds the exact wheel version and contract it needs; this
package is never installed as a shared/global runtime dependency.

## Scientific freeze

This package is an extraction of existing, previously reviewed scientific
code. It changes no ROI boundaries, normalization, pairing, peak windows,
thresholds, or numerical behavior. See `FEATURE_CONTRACTS.md` under
`.project-memory/pr/0171-ir-07-xrd-feature-library/` for the exact per-model
contract bindings and the extraction oracle used to verify parity.
