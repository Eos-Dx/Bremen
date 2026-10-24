# Target model-release matrix (IR-07)

All values below are frozen from merged repository evidence:
`src/bremen/ml_plugin/variants.py` (model identity), and
`.project-memory/pr/0171-ir-07-xrd-feature-library/{WHEEL_EVIDENCE,FEATURE_CONTRACTS}.md`
(release/wheel hashes, feature contracts). No AWS-derived value appears here.

| Field | A1 | A2 | B1 | B2 | B3 |
|---|---|---|---|---|---|
| model_id | `aramina_target_breast_risk_0_2_12-beta_9bb911189af6` | `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11` | `bremen-mri-triage-logreg-v0-1` | `bremen-paper-reference-v0-2-0` | `bremen-v0-2-0-symmetry-candidate` |
| model_version | `0.2.12-beta` | `0.2.13-beta` | `bremen_mri_triage_logreg_v0_1` | `0.2.0-paper-reference` | `bremen_mri_triage_symmetry_logreg_0_2_0-research` |
| workflow_id | `aramina` | `aramina` | `bremen` | `bremen` | `bremen` |
| artifact_sha256 | `9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d` | `f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b` | `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` | `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` | `971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4` |
| preprocessing_release | `v0.1.7-beta` | `v0.1.9-beta` | `none` | `v0.1.7-beta` | `v0.1.7-beta` |
| release_id | `aramina-target-breast-risk-0-2-12-beta-9bb9111` | `aramina-target-breast-risk-0-2-13-beta-f5e4a04` | `bremen-mri-triage-logreg-v0-1` | `bremen-paper-reference-v0-2-0` | `bremen-v0-2-0-symmetry-candidate` |
| release manifest_sha256 | `94a0033b64fd8e664cbd515607cf5d03f3820b9f9ebc0125edcecd5bf2984498` | `2126e2c325003b014a80db7d927d31285ff71b03afa172dd0dd7c3b9ee8025df` | `b9169e1766c3ffb56561c5668af0c2f264a363ec6493f893e35e48c8b2b59088` | `c384a27f21d98d78025360ed77c4db5eb72f1cf9b007a549b52591c7a56a69a2` | `940c41427b2d7b4bba6d39c4e1905dd5d661ce8273a261205e3db8a65fb1d9a3` |
| plugin wheel sha256 | `67ed55226d7c8088f013a11aa9723f8bc0b3b346053e2f0000403563b196efae` (shared by all five) |||||
| feature-library distribution | `xrd-inference-features` (shared) |||||
| feature-library version | `0.1.0` (shared) |||||
| feature-library wheel filename | `xrd_inference_features-0.1.0-py3-none-any.whl` (shared) |||||
| feature-library wheel sha256 | `75498c315990dbe26e591c13c9cb64f06eb9b4139f57608bba4b8576db84a72d` (shared) |||||
| feature contract | `aramina_sk_symmetry_v0_2` | `aramina_sk_symmetry_v0_2` | `bremen_feature_schema_v0.1` | `bremen_feature_schema_v0.1` | `bremen_feature_schema_v0.1` |
| feature_order_hash | `1795926ceacf4eba522f5c5dd41f233cd37af851d7a867a9aed5df935d5b1567` | (same as A1) | `12ccf77a581adcc13a5587563476ef5db513d8b5a404f85c81102b9f39cb78a9` | (same as B1) | (same as B1) |

Notes:

- Plugin wheel and feature-library wheel are byte-identical across all five releases because the source they're built from (`src/bremen/{contracts,model_packages,ml_plugin}` and `packages/xrd-inference-features/src`) is identical for this rebuild — this is expected determinism, not evidence reuse (see `.project-memory/pr/0171-ir-07-xrd-feature-library/WHEEL_EVIDENCE.md`).
- A1/A2's shared `aramina_sk_symmetry_v0_2` contract and distinct `preprocessing_release` values were both confirmed from the actual staged artifacts, not assumed — see `FEATURE_CONTRACTS.md` in the same IR-07 evidence directory.
- No value in this table required AWS access; all are reproducible locally via `src/bremen/release_build/assemble.py` against the same local build inputs documented in IR-07's `PLAN.md`/`WHEEL_EVIDENCE.md`.
