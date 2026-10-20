# Parity, activation and rollback gates

## Baseline before extraction

Run the current verified deployment/image against approved fixtures and retain raw outputs, errors and scientific intermediate values where available. Record model/artifact/config/image/dependency hashes for each run. Compare the candidate against that frozen baseline, not against a newer implementation in another repository. Training and inference transformations must remain aligned.

Per variant cover a successful representative input, threshold-near inputs where feasible, missing/invalid measurement or metadata, supported target/laterality cases, expected QC rejection, and artifact-specific compatibility behavior. Cover missing/nonfinite values, feature ordering, preprocessing arrays, aggregates, probabilities, class ordering, thresholds, decisions, output schema, error mapping and report projection as applicable. Record explicit reasons for nonapplicable cases.

Exact equality is required for identities, feature names/order, class/decision, threshold selection and contractual error/schema semantics. Numerical tolerances must be approved per stage and variant from existing evidence; do not apply an arbitrary common tolerance. Probability agreement alone is insufficient if features or decisions differ. A threshold-crossing decision is a failure even when the probability difference is within tolerance.

Existing PR 0160 reference values are input-specific: corrected raw-H5 baseline probability `0.7726940329943811` and a separate synthetic golden `0.7388733541967353`. They are not universal expected values for all Bremen variants, and old profile-path results must not be substituted. Refer to original evidence and fixture identities before reuse.

## Required evidence table per model

Each run records fixture hash/reference, baseline identity, candidate release digest, environment/image identity, comparison stage, expected/actual values or redacted evidence reference, approved tolerance, outcome, resource usage and reviewer. Include both success and failure fixtures. Historical test counts are not fresh validation.

## Local and service verification

IR-03 verifies all five releases independently of the application with network package fetching disabled. IR-05 adds protocol, timeout, crash, malformed-event, concurrency and cleanup tests. IR-06 repeats scientific parity on App Runner with the same immutable releases and representative resource conditions, including cold installation, cache hit, cache eviction, restart, missing S3 object and checksum failure.

For comparison runs, keep the old route authoritative. Prefer sequential paired runs to avoid doubling peak memory. Candidate results must not create duplicate reports, external writes or user-visible decisions. Do not mirror production data without the existing authorization/data-handling controls. A shadow result is evidence only.

Activate one exact catalog identity at a time after its evidence is reviewed, moving that release through VERIFIED → READY → ACTIVE (see [Architecture and normative contracts](architecture-and-contract.md)). Record old and new pointers, image digest, operator, timestamp and rollback trigger. Confirm the resolved digest in diagnostics. Observe the existing service health/error contract and measured latency/memory/disk budget before the next identity. Never treat activation of a workflow family as completion for all its models.

## Rollback

Retain the old application image, compatible catalog manifest versions, artifacts and configuration until the agreed observation window ends. Before cleanup, demonstrate how to restore the prior image AND catalog/configuration; pointer rollback alone is insufficient if the current image has removed legacy code. Workers already running must retain their pinned release; do not mutate their environment. A failed candidate request does not automatically rerun on a different implementation.

IR-07 is blocked until all five identities pass and the rollback procedure is tested in an authorized environment. Removal of obsolete environment variables must not remove information needed to restore the previous deployment. Production rollout/rollback actions follow existing operator authorization; this documentation does not perform or approve them.
