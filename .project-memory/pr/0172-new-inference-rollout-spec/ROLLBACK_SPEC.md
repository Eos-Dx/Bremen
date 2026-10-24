# Rollback spec and post-rollout verification (conceptual — no live identifiers)

This agent did not access AWS and cannot state actual deployed rollback identifiers (image digest, current catalog manifest bytes, current environment variable values). Every such field below is explicitly marked for the operator to capture **before** cutover.

## What a future operator must retain before cutover

| Item | Status |
|---|---|
| The five current catalog manifest object keys and their exact bytes/SHA-256 | OPERATOR MUST CAPTURE BEFORE CUTOVER |
| The five current `runtime_release` references (or absence thereof, if still pre-IR-06 for any entry) | OPERATOR MUST CAPTURE BEFORE CUTOVER |
| The currently deployed application image identifier/digest | OPERATOR MUST CAPTURE BEFORE CUTOVER |
| The currently deployed App Runner environment variable configuration (names and, for non-secret ones, values) | OPERATOR MUST CAPTURE BEFORE CUTOVER |
| Auth (`BREMEN_AUTH_*`) and demo (`BREMEN_DEMO_H5_*`) configuration | UNCHANGED BY NEW INFERENCE WORKFLOW — retain as-is, no action needed |
| Legacy-compatible application state (embedded feature code, legacy preprocessing env wiring) | Retained automatically — IR-07 changed nothing here; do not remove before IR-08 |

## Rollback procedure (conceptual)

1. Restore the five catalog manifests to their pre-cutover bytes (captured above) — pointer-only rollback is sufficient as long as the legacy in-process code and legacy environment variables were never removed (they were not, per IR-07/IR-08 sequencing).
2. Redeploy the previously-captured application image/config if the image itself changed.
3. Confirm each of the five models resolves back through its pre-cutover runtime path and reproduces its pre-cutover frozen expected results.
4. A release Worker already running under the new release must not have its environment mutated; a failed candidate request does not automatically retry under the old path (per `docs/inference-releases/parity-and-rollout.md`).

## Post-rollout verification spec (for the human operator to run against the real service)

For each of A1, A2, B1, B2, B3:

- [ ] Catalog identity resolves (model_id/workflow_id unchanged, `runtime_release` present and valid).
- [ ] The live release manifest's SHA-256 matches the catalog pointer's `manifest_sha256`.
- [ ] `ReleaseCache` reaches `READY` for that release (no `wheel_closure_incomplete`/`offline_install_failed`/`smoke_failed`).
- [ ] The feature-library wheel is installed in that release's **own** venv (`xrd_inference_features` resolves under `<digest>/env/...`, never system/parent/another release) — see `.project-memory/pr/0171-ir-07-xrd-feature-library/IMPLEMENTATION_REPORT.md`'s "Release-venv import proof" for the local technique used to prove this offline; the operator reproduces the equivalent check against the live service.
- [ ] The Worker process starts from that release's own venv, not the parent/application interpreter.
- [ ] Public inference succeeds/fails per frozen expectations.

### B2 exact gate (must reproduce exactly on the live service)

```
probability:       0.7726940329943811
threshold_applied: 0.3585907282566089
prediction:        1
```

(Same value frozen since PR0160/IR-01, reproduced locally through the external feature backend end-to-end in `.project-memory/pr/0171-ir-07-xrd-feature-library/FIVE_RELEASE_PARITY.md`.)

### Also verify

- B1/B3 success and QC-failure golden cases reproduce their frozen `status`/`probability`/`threshold_applied`/`prediction` or `error_code`/`safe_reason` exactly (see each release's `golden_tests/cases.json`, summarized in `.project-memory/pr/0171-ir-07-xrd-feature-library/FIVE_RELEASE_PARITY.md`).
- A1/A2 success case (`risk_probability`, `decision_threshold`, `target_class_risk_level`) and QC-failure case (`error_code=QC_FAILED`, `safe_reason=ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract`) reproduce exactly.
- Aramina's structured diagnostic transport (the existing safe-reason/error-code mapping, not raw exception text) is preserved end-to-end through the live service, matching the typed-error contract in `docs/inference-releases/architecture-and-contract.md`.

None of the above was run against AWS by this agent; this section specifies what the operator runs against the real, live service.
