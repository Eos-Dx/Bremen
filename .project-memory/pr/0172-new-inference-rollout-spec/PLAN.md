# PR 0172 — local rollout specification for the new (IR-07) inference workflow

Status: implementation in progress on branch `0172-new-inference-rollout-spec`. Not a review/approval artifact.

## Scope

IR-06 and IR-07 are merged. This PR makes **no architecture change**. Its only output is a local specification — built entirely from merged repository evidence, local IR-07 build evidence, and source-code configuration contracts — that a human operator can later use to actually cut Bremen over to the new release-backed route. No AWS of any kind was accessed to produce it (confirmed: no `aws`/boto3/CLI calls were made in this session for this branch).

## Why no AWS

The prior interrupted task attempted a live inventory against the deployed App Runner service/S3 catalog. The user replaced it with this task, which is explicit: prepare the spec from local/merged evidence only, and mark anything that depends on the live deployed state as `UNKNOWN — OPERATOR MUST VERIFY`. That boundary is honored throughout every output file below.

## What was produced

1. **Target five-release identity matrix** (`TARGET_MODEL_RELEASES.md`) — frozen from `.project-memory/pr/0171-ir-07-xrd-feature-library/{WHEEL_EVIDENCE,FEATURE_CONTRACTS}.md`, cross-checked against `src/bremen/ml_plugin/variants.py` (`VariantSpec` table) for `model_id`/`model_version`/`artifact_checksum`.
2. **Target catalog pointer fragments** (`target-catalog/{a1,a2,b1,b2,b3}-runtime-release.json`) — the exact `runtime_release` object each catalog entry should carry, built to the schema `bremen.contracts.inference_release.SCHEMA_ID` / `ReleaseCache.resolve()`'s exact accepted shape (`schema_version`, `release_id`, `manifest_key`, `manifest_sha256`). `manifest_key` uses the relative convention derived from `release_build/assemble.py::_file_ref`'s own `s3_key = f"releases/{release_id}/{relative_path}"` pattern, assuming an empty catalog prefix; the real deployed prefix is unknown (see `TARGET_CATALOG_POINTERS.md`).
3. **Environment variable contract audit** (`APP_ENVIRONMENT_CONTRACT.md`) — every `BREMEN_*` variable relevant to the release-backed route, classified by reading `release_cache.py`, `subprocess_runtime.py`, `registry.py`, `ml_plugin/release.py`, and the embedded preprocessing modules — not by inspecting any deployed environment.
4. **Release publication spec** (`RELEASE_PUBLICATION_SPEC.md`) — what must eventually be uploaded, from where, with which hashes; existence in the real S3 catalog is explicitly `UNKNOWN — OPERATOR MUST VERIFY`.
5. **Operator handoff** (`OPERATOR_HANDOFF.md`) and **rollback spec** (`ROLLBACK_SPEC.md`) — human-executed steps, no AWS CLI commands included.
6. **New test** `tests/test_ir07_target_catalog_pointers.py` — validates the five generated fragments against the real contract validators (`ReleaseCache.resolve()`) and cross-checks them against the frozen IR-07 evidence, entirely offline.

## Non-goals (held)

No AWS access of any kind. No scientific change. No IR-08 cleanup. No live inventory. No secret values anywhere in this PR's output.
