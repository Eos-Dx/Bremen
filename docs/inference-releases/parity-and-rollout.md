# Parity, activation and rollback gates

## Baseline before extraction

Run the current verified deployment/image against approved fixtures and retain raw outputs, errors and scientific intermediate values where available. Record model/artifact/config/image/dependency hashes for each run. Compare the candidate against that frozen baseline, not against a newer implementation in another repository. Training and inference transformations must remain aligned.

Per variant cover a successful representative input, threshold-near inputs where feasible, missing/invalid measurement or metadata, supported target/laterality cases, expected QC rejection, and artifact-specific compatibility behavior. Cover missing/nonfinite values, feature ordering, preprocessing arrays, aggregates, probabilities, class ordering, thresholds, decisions, output schema, error mapping and report projection as applicable. Record explicit reasons for nonapplicable cases.

Exact equality is required for identities, feature names/order, class/decision, threshold selection and contractual error/schema semantics. Numerical tolerances must be approved per stage and variant from existing evidence; do not apply an arbitrary common tolerance. Probability agreement alone is insufficient if features or decisions differ. A threshold-crossing decision is a failure even when the probability difference is within tolerance.

Existing PR 0160 reference values are input-specific: corrected raw-H5 baseline probability `0.7726940329943811` and a separate synthetic golden `0.7388733541967353`. They are not universal expected values for all Bremen variants, and old profile-path results must not be substituted. Refer to original evidence and fixture identities before reuse.

IR-01 repository-evidence pass (2026-10-20): two captured production
executions of the same B2 release (`bremen-paper-reference-v0-2-0`,
checksum `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0`,
Nova_227) — distinct `job_id`/`request_id` values roughly four hours
apart, so each reflects a separately executed job rather than a
duplicated static capture — recorded `probability=0.7726940329943809`
(`results/live-pr0160-smoke/detail-nova227.json`,
`results/post0161-prod-smoke-20260917-163154/detail-bremen-success-nova227.json`).
This differs from the PR0160 reference value above only past the 12th
significant digit and is within the already-approved tolerance recorded
in `.project-memory/pr/0160-model-package-owned-scientific-preprocessing/PRECOMMIT_REVIEW.md`
(`math.isclose(prob, 0.7726940329943811, rel_tol=0, abs_tol=1e-10)` →
True). This is recorded as a confirmed-consistent reproduction, not a new
discrepancy — do not re-open W2 from that precommit review on this basis
alone.

IR-01 local-artifact pass (2026-10-20): the Aramina A1/A2 artifact
manifests record `threshold_target: 0.24666` (5 decimal places), while
the previously captured production executions recorded the applied
decision threshold as `0.24665932038818544` (full precision). These are
the same threshold at reduced display precision in the artifact
manifest, not a parity failure — exact-equality comparisons for A1/A2
must use the full-precision value from the executed result, not the
manifest's rounded display field.

IR-01 real local baseline pass (2026-10-21): a genuine Python 3.13
environment, built outside the repository, executed all five models
against real local H5 fixtures through the existing controlled runtime
(91 runs, 50 completed, 0 unexpected exceptions). Two results are
bit-exact reproductions of pre-existing golden/production values: B2 on
`benign_one_patient.h5` matches the PR0160 reference
`0.7726940329943811` exactly, and A1/A2 on
`eoscloud-staging/cabce03d-...h5` match the previously captured
production result in
`results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`
exactly. Full matrix and failure-category breakdown are in
`.project-memory/pr/0165-ir-01-five-model-inventory/BASELINE_EXECUTION.md`.
This is local-only evidence; it does not establish App Runner parity.

## Required evidence table per model

Each run records fixture hash/reference, baseline identity, candidate release digest, environment/image identity, comparison stage, expected/actual values or redacted evidence reference, approved tolerance, outcome, resource usage and reviewer. Include both success and failure fixtures. Historical test counts are not fresh validation.

## Local and service verification

IR-03 verifies all five releases independently of the application with network package fetching disabled. IR-05 adds protocol, timeout, crash, malformed-event, concurrency and cleanup tests. IR-06 cuts catalog-backed entries over to the same immutable release path and verifies local route parity; App Runner repetition, cold installation, cache hit, cache eviction, restart, missing S3 object and checksum failure remain separately authorized operational rollout work.

For comparison runs, keep the old route authoritative. Prefer sequential paired runs to avoid doubling peak memory. Candidate results must not create duplicate reports, external writes or user-visible decisions. Do not mirror production data without the existing authorization/data-handling controls. A shadow result is evidence only.

Activate one exact catalog identity at a time after its evidence is reviewed, moving that release through VERIFIED → READY → ACTIVE (see [Architecture and normative contracts](architecture-and-contract.md)). Record old and new pointers, image digest, operator, timestamp and rollback trigger. Confirm the resolved digest in diagnostics. Observe the existing service health/error contract and measured latency/memory/disk budget before the next identity. Never treat activation of a workflow family as completion for all its models.

## Rollback

Retain the old application image, compatible catalog manifest versions, artifacts and configuration until the agreed observation window ends. Before cleanup, demonstrate how to restore the prior image AND catalog/configuration; pointer rollback alone is insufficient if the current image has removed legacy code. Workers already running must retain their pinned release; do not mutate their environment. A failed candidate request does not automatically rerun on a different implementation.

IR-08 (legacy inference cleanup, formerly numbered IR-07) is blocked until IR-07 (external XRD feature-library integration) is accepted, all five identities pass, and the rollback procedure is tested in an authorized environment. Removal of obsolete environment variables must not remove information needed to restore the previous deployment. Production rollout/rollback actions follow existing operator authorization; this documentation does not perform or approve them.
