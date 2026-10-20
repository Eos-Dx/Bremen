# Five-model inventory: evidence and blockers

Status: NOT COMPLETE. Repository snapshot is not live deployment evidence. The user reports two Aramina and three Bremen variants. All five require current catalog/artifact verification before implementation assumptions become accepted.

| Slot | Identity evidence | Current readiness |
|---|---|---|
| A1 | Historical `aramina_target_breast_risk_0_2_12-beta_9bb911189af6`, version `0.2.12-beta` | Verify active catalog, artifact and preprocessing mapping |
| A2 | Historical `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11`, version `0.2.13-beta` | Verify active catalog, artifact and preprocessing mapping |
| B1 | Exact current identity unresolved | Blocking inventory task |
| B2 | Exact current identity unresolved | Blocking inventory task |
| B3 | Exact current identity unresolved | Blocking inventory task |

Historical Bremen evidence includes `bremen-mri-triage-logreg-v0-1` / `bremen_mri_triage_logreg_v0_1`. Code also contains the paper-reference manifest identity `bremen-paper-reference-v0-2-0` / `0.2.0-paper-reference`. Neither proves three distinct active catalog entries. Do not assign these examples to slots or invent B3 without deployment evidence. Python namespace `bremen_v01` is not a reliable deployed model version.

## Required record for each slot

Capture exact catalog URI/key and version, model ID/version, manifest bytes/hash, artifact URI/version/hash, runtime entrypoint, pickle class paths, Python/OS/architecture, installed dependency versions, preprocessing release and commit, config/YAML hash, raw versus legacy input path, ordered features and aggregation, imputation/scaling, probability class ordering, threshold source and value, output/error schema, scientific owner, approved fixtures and baseline outputs. Keep patient data and secrets outside committed evidence; commit fixture identifiers and controlled-access references/hashes.

Also capture the current image digest and configuration names, without secret values. Record deployed values for resource and timeout settings in authorized operational evidence. Do not reconstruct a baseline by installing the latest compatible dependencies from broad pyproject ranges.

## Scientific differences already evidenced

- Aramina has distinct compatibility implementations for `aramina.m2q_model.GatedSymmetryLogistic` and `aramina.target_breast_model.GatedSymmetryLogistic`. Preserve each artifact's exact class resolution and transformation behavior.
- Aramina supports preprocessing `v0.1.7-beta` and `v0.1.9-beta`. Determine the mapping from each actual artifact; do not infer it from model version alone. Preserve per-measurement prediction, logit aggregation, age/symmetry construction, artifact feature ordering and final classification.
- Bremen has raw-H5/artifact-YAML paper-reference behavior and a legacy integrated-profile path. Do not force all three variants into one path without inventory evidence. The raw reference path uses the frozen 15-feature computation over three left and three right measurements.
- Bremen portable logistic inference has explicit class-order handling, nonfinite-feature handling, scaler behavior and inclusive threshold comparison. These are part of the baseline, not cleanup opportunities.

## Gate record

For each slot maintain: inventory status, extraction status, local parity status, App Runner parity status, activation status, rollback evidence and reviewer/date. Allowed statuses: pending, blocked, passed, failed. Every passed status requires evidence links. This bundle sets none to passed.
