# IR-07 feature-contract mapping

Derived from actual staged artifacts and current runtime behavior — **not guessed**. Method and evidence below; reproduce with the commands shown.

## Mapping

| Variant | model_id | feature_library.contract | Basis |
|---|---|---|---|
| A1 | `aramina_target_breast_risk_0_2_12-beta_9bb911189af6` | `aramina_sk_symmetry_v0_2` | Read from the artifact's own `models["aramina_target_breast_risk"]["symmetry_feature_contract"]` |
| A2 | `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11` | `aramina_sk_symmetry_v0_2` | Same field, same artifact structure, different preprocessing release (`v0.1.9-beta`) |
| B1 | `bremen-mri-triage-logreg-v0-1` | `bremen_feature_schema_v0.1` | Single Bremen feature contract (no v0.1/v0.2 fork exists for the 15 features) |
| B2 | `bremen-paper-reference-v0-2-0` | `bremen_feature_schema_v0.1` | Same |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `bremen_feature_schema_v0.1` | Same |

## Evidence

### Aramina (A1/A2)

Both A1 and A2 declare `"feature_schema_version": "aramina_target_breast_risk_v0.2"` in their artifact manifest (`configs/artifact_manifest.json`), but that field names the **model** schema, not the symmetry feature contract. The actual symmetry contract a request executes under is read at runtime from the trained artifact's own pickle (`aramina_v0213/inference.py:468`: `model_info.get("symmetry_feature_contract", "aramina_sk_symmetry_v0_1")`). This was inspected directly, for both artifacts, via the existing compatibility bridge:

```python
import joblib
from bremen.model_packages.aramina_v0213.artifact_compat import ensure_compatibility_bridge
ensure_compatibility_bridge()
for v in ("a1", "a2"):
    pkg = joblib.load(f"/tmp/ir03/releases-final/{v}/model/model.joblib")
    for name, info in pkg["models"].items():
        print(v, name, info["symmetry_feature_contract"])
# a1 aramina_target_breast_risk aramina_sk_symmetry_v0_2
# a2 aramina_target_breast_risk aramina_sk_symmetry_v0_2
```

Both resolve to `aramina_sk_symmetry_v0_2` — confirmed identical despite A1/A2 using different preprocessing releases (`v0.1.7-beta` vs. `v0.1.9-beta`). `release_build/assemble.py::_feature_library_contract` performs exactly this read (via the same artifact bytes already checksum-bound to the release by `_artifact_files`), so build-time and request-time always agree by construction — it is never a hardcoded per-variant constant.

### Bremen (B1/B2/B3)

All three artifact manifests declare `"feature_schema_version": "v0.1"`, and all three bind the same single module, `bremen_v01.features` (there is no `v0.2` fork of the 15-feature computation — only of *model artifacts/thresholds* that consume those same 15 features). `release_build/assemble.py::_feature_library_contract` returns the library's own `CONTRACT_ID` constant (`xrd_inference_features.bremen_contract.CONTRACT_ID == "bremen_feature_schema_v0.1"`) for every non-Aramina `VariantSpec`.

## Distinctness preserved

- Bremen's single contract and Aramina's two contracts are never unified: the library ships `bremen_contract.py` and `aramina_symmetry.py` as separate modules with separate, byte-identical ROI/normalization/pairing/neutral-fallback behavior per contract (see `packages/xrd-inference-features/README.md` and the differential tests in `tests/test_ir07_feature_library_parity.py`).
- Aramina's v0.1-vs-v0.2 selection remains **artifact-declared at request time**, not release-build-time or hardcoded — IR-07 only moved *where* the math for both contracts lives, not *when* the contract is chosen.
- Aramina consumes only its CORE4 + `symmetry_available` subset; it is not forced onto the Bremen 15-feature output contract.
