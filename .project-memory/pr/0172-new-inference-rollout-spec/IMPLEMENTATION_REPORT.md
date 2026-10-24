# IR-07 rollout-spec implementation report (PR 0172)

## TASK COMPLETE

A complete local rollout specification was produced for cutting Bremen over to the IR-07 release-backed route for A1, A2, B1, B2, B3 — built entirely from merged repository evidence, local IR-07 build evidence, and source-code configuration contracts. **No AWS CLI command, boto3/botocore client, or any AWS API call was made in this session on this branch.**

## AWS access

NOT USED. Verified: no `aws`, no `boto3`, no network call to any AWS endpoint was executed while producing any file listed below. (An earlier, separate task on a different branch — `0172-new-inference-rollout-inventory` — had begun live AWS inspection before the user interrupted it and replaced it with this strictly-local task; that branch was abandoned with zero commits and no local changes, and this branch was created fresh from merged `main`.)

## Files changed

```
.project-memory/pr/0172-new-inference-rollout-spec/PLAN.md
.project-memory/pr/0172-new-inference-rollout-spec/TARGET_MODEL_RELEASES.md
.project-memory/pr/0172-new-inference-rollout-spec/TARGET_CATALOG_POINTERS.md
.project-memory/pr/0172-new-inference-rollout-spec/APP_ENVIRONMENT_CONTRACT.md
.project-memory/pr/0172-new-inference-rollout-spec/RELEASE_PUBLICATION_SPEC.md
.project-memory/pr/0172-new-inference-rollout-spec/OPERATOR_HANDOFF.md
.project-memory/pr/0172-new-inference-rollout-spec/ROLLBACK_SPEC.md
.project-memory/pr/0172-new-inference-rollout-spec/IMPLEMENTATION_REPORT.md (this file)
.project-memory/pr/0172-new-inference-rollout-spec/target-catalog/a1-runtime-release.json
.project-memory/pr/0172-new-inference-rollout-spec/target-catalog/a2-runtime-release.json
.project-memory/pr/0172-new-inference-rollout-spec/target-catalog/b1-runtime-release.json
.project-memory/pr/0172-new-inference-rollout-spec/target-catalog/b2-runtime-release.json
.project-memory/pr/0172-new-inference-rollout-spec/target-catalog/b3-runtime-release.json
tests/test_ir07_target_catalog_pointers.py
```

No `src/` file was modified. No scientific, architectural, or infrastructure change.

## Target five releases

See `TARGET_MODEL_RELEASES.md` for the full matrix. Summary:

```
A1: aramina_target_breast_risk_0_2_12-beta_9bb911189af6
    release_id aramina-target-breast-risk-0-2-12-beta-9bb9111
    manifest_sha256 94a0033b64fd8e664cbd515607cf5d03f3820b9f9ebc0125edcecd5bf2984498
    contract aramina_sk_symmetry_v0_2

A2: aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11
    release_id aramina-target-breast-risk-0-2-13-beta-f5e4a04
    manifest_sha256 2126e2c325003b014a80db7d927d31285ff71b03afa172dd0dd7c3b9ee8025df
    contract aramina_sk_symmetry_v0_2

B1: bremen-mri-triage-logreg-v0-1
    release_id bremen-mri-triage-logreg-v0-1
    manifest_sha256 b9169e1766c3ffb56561c5668af0c2f264a363ec6493f893e35e48c8b2b59088
    contract bremen_feature_schema_v0.1

B2: bremen-paper-reference-v0-2-0
    release_id bremen-paper-reference-v0-2-0
    manifest_sha256 c384a27f21d98d78025360ed77c4db5eb72f1cf9b007a549b52591c7a56a69a2
    contract bremen_feature_schema_v0.1

B3: bremen-v0-2-0-symmetry-candidate
    release_id bremen-v0-2-0-symmetry-candidate
    manifest_sha256 940c41427b2d7b4bba6d39c4e1905dd5d661ce8273a261205e3db8a65fb1d9a3
    contract bremen_feature_schema_v0.1
```

No disagreement was found between merged repository evidence sources (`variants.py` VariantSpec table vs. the IR-07 evidence docs) — all values cross-checked cleanly.

## Target catalog pointers

Five `runtime_release` JSON fragments in `target-catalog/`, schema-valid per `bremen.contracts.inference_release.SCHEMA_ID` and `ReleaseCache.resolve()`'s exact accepted shape. `manifest_key` uses the code-derived relative convention `releases/<release_id>/manifest.json`, explicitly flagged as assuming an empty catalog prefix — the real deployed prefix is `UNKNOWN — OPERATOR MUST VERIFY` (see `TARGET_CATALOG_POINTERS.md`).

## Environment variable contract

Full audit in `APP_ENVIRONMENT_CONTRACT.md`.

- **REQUIRED**: `BREMEN_MODEL_CATALOG_URI` (deployed value unknown).
- **OPTIONAL**: `BREMEN_RELEASE_CACHE_ROOT`, `BREMEN_RELEASE_CACHE_MAX_BYTES`, `BREMEN_CANDIDATE_INVOCATION_TIMEOUT_SECONDS`, `BREMEN_IR03_AUX_ENV_ROOT`.
- **LEGACY_COMPATIBILITY**: `BREMEN_CANDIDATE_SUBPROCESS_MODELS` (confirmed dead for routing — `registry.py::_candidate_runtime_for` never calls the allowlist functions), `BREMEN_PREPROCESS_PYTHON`/`BREMEN_ARAMINA_PREPROCESS_PYTHON`/`BREMEN_ARAMINA_PREPROCESS_019_PYTHON`/`BREMEN_PREPROCESS_PROVENANCE`/`BREMEN_ARAMINA_PREPROCESS_PROVENANCE` (dual-purpose: legacy-global and release-Worker-scoped by the same name).
- **WORKER_OWNED**: `BREMEN_FEATURE_LIBRARY_BACKEND`.
- **MUST_NOT_BE_GLOBAL**: `BREMEN_FEATURE_LIBRARY_BACKEND` — flagged explicitly as a rollout blocker if ever found set globally on the live service (not checked here, no AWS access).
- **UNRELATED_APPLICATION_CONFIG**: `BREMEN_AUTH_*`, `BREMEN_DEMO_H5_*` (unchanged, not inspected further), `BREMEN_MODEL_STAGING_DIR`, and other platform/product config.

## Required variables / optional variables / legacy variables / worker-owned variables / must-not-be-global variables

See the five sections of `APP_ENVIRONMENT_CONTRACT.md` above — not restated here to avoid duplication/drift.

## Release publication spec

`RELEASE_PUBLICATION_SPEC.md`: object layout derived from `release_build/assemble.py::_file_ref`'s own convention; per-release hash table; existence at target S3 keys explicitly `UNKNOWN — OPERATOR MUST VERIFY` (not checked, no AWS access).

## Operator handoff

`OPERATOR_HANDOFF.md`: 8 steps, no AWS CLI commands included, as required.

## Post-rollout verification

`ROLLBACK_SPEC.md`'s verification checklist, including the B2 exact hard gate (`probability=0.7726940329943811`, `threshold_applied=0.3585907282566089`, `prediction=1`) and the other four releases' frozen success/failure expectations, plus Aramina's structured diagnostic preservation requirement.

## Rollback spec

`ROLLBACK_SPEC.md`: every field that would require live AWS inspection is marked `OPERATOR MUST CAPTURE BEFORE CUTOVER`; auth/demo config marked `UNCHANGED BY NEW INFERENCE WORKFLOW`.

## Validation results (actual, this session)

```
tests/test_ir07_target_catalog_pointers.py tests/test_inference_release_contract.py
tests/test_ir04_release_cache.py tests/test_ir05_subprocess_runtime.py
tests/test_ir06_release_cutover.py tests/test_ir07_feature_library_parity.py
tests/test_s3_model_discovery.py tests/test_model_registry.py: 383 passed

python -m compileall -q src tests packages/xrd-inference-features/src: passed

Full repo suite: 4553 passed, 8 skipped, 39 warnings
  (4536 pre-existing + 17 new target-catalog-pointer tests)

git diff --check: passed (clean)
git status --short: only new files listed above (untracked); no tracked file modified
git diff --stat: empty (no tracked file changed)
```

## Warnings

- `manifest_key` in every generated fragment assumes an empty catalog prefix; it is explicitly not safe to use as-is against a deployed catalog with a non-empty prefix (see `TARGET_CATALOG_POINTERS.md`).
- All hash/identity values are reproductions of `.project-memory/pr/0171-ir-07-xrd-feature-library/WHEEL_EVIDENCE.md`; this PR does not re-derive them independently (no rebuild was performed here), it only reads and cross-checks that evidence plus `variants.py`.

## Remaining unknown operator values

- Deployed `BREMEN_MODEL_CATALOG_URI` (bucket + prefix).
- Whether the five target S3 keys already exist, and if so their byte/hash identity (`SAME`/`CONFLICT`).
- Current live App Runner environment variable values/configuration (names classified in `APP_ENVIRONMENT_CONTRACT.md`; live values not inspected).
- Current deployed application image identifier/digest.
- Whether `BREMEN_FEATURE_LIBRARY_BACKEND` is, incorrectly, set globally on the live service today.

## Remaining blockers

None identified from local/merged evidence alone. The items in "Remaining unknown operator values" above are not blockers by themselves — they are exactly the facts the operator must establish during Steps 1–3 of `OPERATOR_HANDOFF.md` before Step 4 (catalog pointer update) can proceed safely.

## Next required action

Precommit review.
