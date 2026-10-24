# Operator handoff — IR-07 cutover (no commands included, specification only)

This describes what a human operator with AWS authorization does next. It contains no AWS CLI commands — this agent is prohibited from accessing AWS and prepares specifications only.

## STEP 1 — Verify the configured catalog location

Read the live `BREMEN_MODEL_CATALOG_URI` from the deployed App Runner service configuration. Confirm its bucket and prefix. This determines the real `manifest_key` prefix to use in Step 4 (see `TARGET_CATALOG_POINTERS.md`'s unresolved-prefix note).

## STEP 2 — Publish the five immutable IR-07 release directories

Using the local evidence in `RELEASE_PUBLICATION_SPEC.md` (reproduce the releases per `.project-memory/pr/0171-ir-07-xrd-feature-library/PLAN.md`'s build commands if not already retained from this session), upload each release's complete object set under `releases/<release_id>/...` beneath the catalog's real prefix. Releases are immutable: never overwrite an existing key — if a target key already exists, verify byte/SHA identity first (see `RELEASE_PUBLICATION_SPEC.md`'s "Existence at target keys").

## STEP 3 — Read back and verify every object hash

After upload, read every uploaded object back and confirm its SHA-256 matches the value declared in that release's own `manifest.json` `files[]`/`golden_tests[]` entries, and that the manifest object's own bytes hash to the `manifest_sha256` recorded in `TARGET_MODEL_RELEASES.md`. Do not proceed to Step 4 until every hash matches exactly.

## STEP 4 — Update the five catalog `runtime_release` pointers

Using `target-catalog/{a1,a2,b1,b2,b3}-runtime-release.json` as the base, prepend the real catalog prefix to each `manifest_key` (Step 1's finding) and write the resulting `runtime_release` object onto each of the five existing catalog entries. This is additive/pointer-only — do not modify `model_id`, `workflow_id`, artifact identity, threshold, or any other scientific metadata field on these entries (see `TARGET_CATALOG_POINTERS.md`, "What must NOT change").

## STEP 5 — Ensure required platform environment variables match the local contract

Cross-check the live App Runner environment against `APP_ENVIRONMENT_CONTRACT.md`. In particular:

- `BREMEN_MODEL_CATALOG_URI` is set and correct (should already be true from Step 1).
- `BREMEN_FEATURE_LIBRARY_BACKEND` is **not** set globally — if it is, stop and treat it as a blocker (it must only ever be set inside a release Worker process).
- Do not remove any legacy `BREMEN_PREPROCESS_*`/`BREMEN_ARAMINA_PREPROCESS_*`/`BREMEN_CANDIDATE_*` variable at this step — removal is Post-Cutover Cleanup (Step 8) at the earliest, never before successful verification.

## STEP 6 — Start/redeploy/restart Bremen as appropriate

Whatever the operator's normal deployment mechanism is for applying a catalog/config change to the live service (this agent does not know or prescribe App Runner-specific deployment mechanics here, per the AWS prohibition).

## STEP 7 — Verify all five model paths

For each of A1, A2, B1, B2, B3, confirm through the real running service:

- the model resolves and its catalog entry now carries the updated `runtime_release`;
- `ReleaseCache` reaches `READY` for that release (no `smoke_failed`/`offline_install_failed`/etc. error);
- a real request against each model produces the frozen expected result — see `POST_ROLLOUT_VERIFICATION` section of `ROLLBACK_SPEC.md`'s companion checks and the B2 hard gate quoted there.

## STEP 8 — Retain rollback state until the observation window ends

Keep the pre-cutover catalog manifests, the previous application image/config, and the previous release objects retrievable until the agreed observation window ends (per `docs/inference-releases/parity-and-rollout.md`'s rollback-before-cleanup requirement). Only after that may post-cutover cleanup (stale `BREMEN_CANDIDATE_SUBPROCESS_MODELS`, etc.) or IR-08 legacy-code removal proceed — and IR-08 is explicitly out of scope for this PR regardless.
