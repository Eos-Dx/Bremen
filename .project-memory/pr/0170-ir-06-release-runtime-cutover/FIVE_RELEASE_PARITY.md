# IR-06 five-release cutover parity

All five current rebuilt local releases execute through the existing IR-03/04/05
release path and do not require `BREMEN_CANDIDATE_SUBPROCESS_MODELS` after the
cutover. This is local evidence only.

| slot | model_id | manifest SHA-256 | artifact SHA-256 | local result |
|---|---|---|---|---|
| A1 | `aramina_target_breast_risk_0_2_12-beta_9bb911189af6` | `02be0ce3117080bbbf998a81ffaeff993938aaeb6fd2cc98c93ee730f7532b4c` | `9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d` | PASS |
| A2 | `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11` | `7ebd66806b7924202d68d7d74265784300b8dacc64b6df98bb8d4e2984fd4e49` | `f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b` | PASS |
| B1 | `bremen-mri-triage-logreg-v0-1` | `678edd64ddb35a2ba26e92f9bd804ab350303e458b4d152a5a4498ab812bc8ad` | `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` | PASS |
| B2 | `bremen-paper-reference-v0-2-0` | `d6df5c67bee4c9beadecd75fa316883fdcbfed81532ccea298d14f0bdc312321` | `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` | PASS |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `596f8e10c065ae8d7c99201274c8559e8d158bff2393f637d47e8755611887eb` | `971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4` | PASS |

B2 remains exactly `probability=0.7726940329943811`,
`threshold_applied=0.3585907282566089`, `prediction=1`. Existing Aramina
structured failure parity remains covered. B3 remains
`exploratory_proxy_not_clinically_reviewed`.

The test command was:

```text
BREMEN_IR03_RELEASES=/tmp/ir05/releases python -m pytest -q tests/test_ir03_parity.py
```

Result: 21 passed. This does not claim AWS/App Runner parity.
