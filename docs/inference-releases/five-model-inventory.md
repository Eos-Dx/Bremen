# Five-model inventory: evidence and blockers

Status: **Identity, checksum, threshold and real local scientific
execution now resolved for all five slots.** Live catalog/App Runner
re-confirmation is still outstanding — see "What remains blocked"
below. This document was updated in three passes: (1)
repository-evidence-only (committed production-smoke captures), (2)
local artifact-directory evidence at `/tmp/bremen-ir01-models` (five
directories, one per model, containing manifest/config/joblib
sidecars), and (3) real local baseline execution against 49 fixtures at
`/tmp/bremen-ir01-fixtures/v0.1` through the existing controlled
runtime (none of these external directories were committed to git).
Full citation trail, checksums and commands are in
`.project-memory/pr/0165-ir-01-five-model-inventory/INVENTORY_EVIDENCE.md`,
`FIXTURE_INVENTORY.md` and `BASELINE_EXECUTION.md`.

## Resolved identity table

| Slot | model_id | model_version | Artifact SHA256 (local, verified by `shasum -a 256`) | Threshold (artifact) |
|---|---|---|---|---|
| A1 | `aramina_target_breast_risk_0_2_12-beta_9bb911189af6` | `0.2.12-beta` | `9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d` | `0.24666` (manifest) / `0.24665932038818544` (prior production capture, full precision) |
| A2 | `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11` | `0.2.13-beta` | `f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b` | same as A1 |
| B1 | `bremen-mri-triage-logreg-v0-1` | `bremen_mri_triage_logreg_v0_1` | `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` | manifest says `-1` / `"unconfirmed_placeholder"`; prior production capture recorded applied threshold `0.3640352477169748` |
| B2 | `bremen-paper-reference-v0-2-0` | `0.2.0-paper-reference` | `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` | `0.3585907282566089` |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `bremen_mri_triage_symmetry_logreg_0_2_0-research` | `971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4` | `0.4130396520921527` |

Every local artifact's SHA256 was independently computed with `shasum -a
256` and matched exactly against that same artifact's own
`manifest.json` `model_checksum` field — all five are internally
self-consistent (manifest claims match artifact bytes). Four of the five
checksums also exactly match values already seen in this repository's
*other* evidence before this local-artifact pass: A1, A2 and B2's
checksums match the live production-catalog/execution captures recorded
earlier in this document's history (see git history of this file); B1's
checksum exactly matches the SHA256 that `.project-memory/pr/0039-inference-integration/PLAN.md`
had previously recorded as an unverified design-time lead — this local
artifact evidence promotes that lead from "unverified" to
"artifact-confirmed," though it is still not a live-deployment
re-confirmation. B3's checksum is **new** evidence; nothing in the
repository previously recorded it.

## B3 resolved: real, distinct, exploratory model — not just a catalog string

The open question "is B3 a real distinct model artifact or only a
catalog identity?" is now answered: **real.** `/tmp/bremen-ir01-models/v0.2.0/`
contains a complete package — `manifest.json`, `model_description.yaml`,
`feature_schema.json`, `label_mapping.json`, `metrics.json`,
`training_config.yaml`, `preprocessing_config.yaml`,
`prediction_preprocessing_config.yaml`, `evaluation.yaml`,
`container_requirements.json`, and the joblib artifact itself (present
twice, under `model.joblib` and
`bremen_mri_triage_symmetry_logreg_v0.2.0.joblib` — both files are
byte-identical, confirmed by `cmp`).

B3 shares its 15-feature contract (`bremen_h5_15feature_v0_2`) and
architecture (`median_imputer_standard_scaler_balanced_logistic_regression`)
with B2, but is trained on a **different, explicitly exploratory**
label: `label_mapping.label_column: mri_presence_proxy_label`,
`label_status: exploratory_proxy_not_clinically_reviewed`,
`allow_exploratory_proxy: true`. Its `model_description.yaml` states
plainly: "Current runnable model uses an MRI-presence proxy, not a
reviewed MRI-continuation endpoint" and "not clinically validated."
Decision classes are also named differently from B2
(`CONTINUE_MRI`/`MRI_REVIEW_DEFER` vs B2's `CANCER`/`NON-CANCER`), and
its threshold (`0.4130396520921527`, source
`train_all_target_sensitivity`) is distinct from B2's
(`0.3585907282566089`). This closes the earlier open caution about not
conflating B3 with B2's similarly-"symmetry"-named training run — they
are confirmed as genuinely distinct artifacts with distinct provenance,
not the same model under two names.

**Safety note carried forward:** B3's label is an unreviewed proxy, not
a clinically reviewed outcome. Any future IR-02+ work on B3 must carry
this `exploratory_proxy_not_clinically_reviewed` status forward in its
release metadata; it must not be presented as equivalent in validation
status to B2.

## Per-slot detail (local artifact evidence)

### A1 / A2 — Aramina 0.2.12-beta / 0.2.13-beta

`aramina_0_2_12-beta/preprocessing_config.yaml` declares
`release_tag: v0.1.7-beta`; `aramina_0_2_13-beta/preprocessing_config.yaml`
declares `release_tag: v0.1.9-beta`. This is now an **artifact-declared
general mapping**, not only the single-fixture production-capture
inference recorded earlier in this document — it upgrades that earlier,
narrower finding. All other config/training files between the two
directories are otherwise identical except version-identity fields
(confirmed by `diff`), consistent with both being the same training
pipeline run twice under two preprocessing releases.

Both artifacts declare final model class `GatedSymmetryLogistic` with
`base_feature_columns` (`profile_p_cancer_logit_average`, `age`,
`age_available`) and `symmetry_feature_columns`
(`sk_wasserstein_distance_full_q2`, `sk_weightedrms1`,
`sk_weightedrms2`, `sk_mean_peak_value_abs_delta`), gated by
`symmetry_available` — matching
`src/bremen/model_packages/aramina_v0213/manifest.py`'s
`FINAL_FEATURE_COLUMNS` exactly. `threshold_target: 0.24666` in the
artifact manifest is the same value as the previously captured
production `decision_threshold=0.24665932038818544`, rounded to 5
decimal places in the artifact's own description file — not a
discrepancy, just reduced display precision in that one field.

Full artifact SHA256 is now known (table above) — this closes the
previously-open "full artifact hash not found" gap for both.

### B1 — `bremen-mri-triage-logreg-v0-1`

The local artifact directory (`v0.1/`) is sparse: only
`manifest.json`, `container_requirements.json`, and the joblib file — no
`model_description.yaml`, `feature_schema.json`, or training/evaluation
records exist locally for B1, unlike B2 and B3. The manifest's own
`threshold_value: -1` / `threshold_version: "unconfirmed_placeholder"`
and `qc_criteria_version: "unconfirmed_placeholder"` confirm, in the
artifact's own metadata, that this release's manifest was never
completed with a real threshold/QC identity — the actual applied
threshold (`0.3640352477169748`, from the earlier production capture)
must come from inside the joblib artifact itself at runtime, not from
this manifest file. This is now a **confirmed artifact-level gap**, not
a guess: B1 is the least-documented of the five at the artifact level.

### B2 — `bremen-paper-reference-v0-2-0`

Full `model_description.yaml` confirms architecture
(`median_imputer_standard_scaler_balanced_logistic_regression`), the
exact 15 `feature_columns`, threshold `0.3585907282566089`
(`threshold_source: paper_train_all_target_sensitivity`), and a
`paper_reference_parity` block recording `passed: true` against its own
training-time reference comparison (not re-executed in this pass).
This is the same checksum, threshold and feature count already
cross-confirmed from repository evidence in the prior pass — the local
artifact is simply a fourth, directly-matching confirmation.

### B3 — see dedicated section above.

## Required record for each slot — status after this pass

| Field | A1 | A2 | B1 | B2 | B3 |
|---|---|---|---|---|---|
| model_id / version | resolved | resolved | resolved | resolved | resolved |
| Full artifact SHA256 | resolved | resolved | resolved | resolved | resolved |
| Manifest bytes/hash | resolved (local copy; S3 object hash not independently re-verified) | resolved (same caveat) | resolved (same caveat) | resolved (same caveat) | resolved (same caveat) |
| Feature schema / columns | resolved | resolved | **not found locally** | resolved | resolved |
| Threshold | resolved (rounded) | resolved (rounded) | **manifest placeholder; real value only from prior production capture** | resolved | resolved |
| Preprocessing release mapping | resolved (artifact-declared) | resolved (artifact-declared) | n/a (Bremen workflow, no external preprocessing release split) | n/a | n/a |
| Golden/reference fixture execution | not re-run this session | not re-run this session | not re-run this session | not re-run this session (existing `tests/fixtures/bremen_3x3/`) | not re-run this session |
| Current image digest / S3 object identity | **still not available** (no live access) | same | same | same | same |

## Real local baseline execution (2026-10-21)

A follow-up pass obtained a genuine Python 3.13 interpreter outside the
repository (`uv python install 3.13`, no dependency file edited) and
executed all five models against real local H5 fixtures
(`/tmp/bremen-ir01-fixtures/v0.1`) through the existing, unmodified
`bremen.platform.runtime.executor.execute` orchestration — the same
checksum-verified loading and real preprocessing subprocess workers the
production service uses. **91 real executions: 50 completed, 41 failed
with typed/expected safe reasons, 0 unexpected exceptions.** B2's
result on `benign_one_patient.h5` (`probability=0.7726940329943811`)
is an exact, bit-for-bit match to the existing PR0160 golden reference
in `parity-and-rollout.md`. A1/A2's result on
`eoscloud-staging/cabce03d-...h5` exactly reproduces a previously
captured real production result
(`results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`).
B1's "unconfirmed placeholder" manifest threshold was *not* invented or
used — direct execution confirms the runtime reads the real threshold
from inside the joblib artifact itself (`0.3640352477169748`, matching
`docs/production-contracts-2026-09-18.md`), not from the manifest
sidecar field. Full matrix, per-category failure breakdown, and a
cross-model finding (B1 accepts the legacy `detector_scoped_v1` layout
that B2/B3/A1/A2 reject) are recorded in
`.project-memory/pr/0165-ir-01-five-model-inventory/BASELINE_EXECUTION.md`.
This execution is local only; it does not constitute App Runner
verification.

## What remains blocked

1. **Live re-confirmation.** All identity/checksum/threshold facts above
   come from a local artifact directory snapshot
   (`/tmp/bremen-ir01-models`, provided for this task) and from
   September 2026 production captures. Neither is a call to the live
   catalog/S3/App Runner made today. The local directories' provenance
   (how/when they were produced, whether they match what is currently
   live) was not independently established in this session — they were
   supplied as read-only input, not fetched by this agent from an
   authorized source.
2. **App Runner resource/cost verification** is unaffected by the local
   baseline execution and remains blocked exactly as before (see
   `docs/inference-releases/operations.md`). Local execution timing
   (recorded in `BASELINE_EXECUTION.md`) is not a substitute for
   production resource measurement.
3. **B3's exploratory-label clinical review status** is unchanged by
   running it — real numeric outputs now exist, but the model remains
   `exploratory_proxy_not_clinically_reviewed`.
4. A newly confirmed, reproducible finding: the `xrd-preprocessing`
   `v0.1.7-beta` git tag currently resolves to a different commit than
   the artifact's own provenance pin expects (see
   `BASELINE_EXECUTION.md` "Environment"). This is a dependency/tagging
   concern outside this repository, not something this task changed.

## Gate record

| Slot | Inventory status | Extraction status | Local parity status | App Runner parity status | Activation status | Rollback evidence | Reviewer/date |
|---|---|---|---|---|---|---|---|
| A1 | identity+checksum+threshold resolved; live re-confirmation pending | pending | **passed** — 8/14 local fixtures completed, exact match to captured production value on a shared fixture; 6/14 typed/expected failures, 0 unexpected | pending | pending | n/a | coder, 2026-10-21 |
| A2 | same as A1 | pending | **passed** — 8/14 completed incl. bit-exact match to captured production `detail-aramina-success-nova214-left.json`; 6/14 typed/expected failures, 0 unexpected | pending | pending | n/a | coder, 2026-10-21 |
| B1 | identity+checksum resolved; real threshold source confirmed (embedded in artifact, not manifest); live re-confirmation pending | pending | **passed** — 8/21 completed with threshold matching `docs/production-contracts-2026-09-18.md`; 12/21 expected QC rejections (`raw_peak_gate_failed`), 1/21 input-incompatible, 0 unexpected | pending | pending | n/a | coder, 2026-10-21 |
| B2 | identity+checksum+threshold+feature-schema resolved and quadruply cross-confirmed; live re-confirmation pending | pending | **passed** — 11/21 completed incl. bit-exact match to the PR0160 golden reference `0.7726940329943811`; 10/21 typed/expected failures, 0 unexpected | pending | pending | n/a | coder, 2026-10-21 |
| B3 | identity+checksum+threshold+feature-schema resolved; confirmed real and distinct from B2; exploratory-label safety note recorded; live re-confirmation pending | pending | **passed** — 15/21 completed with outputs distinct from B2 on identical fixtures; 6/21 typed/expected failures, 0 unexpected | pending | pending | n/a | coder, 2026-10-21 |

Local parity is now `passed` for all five, evidenced by
`.project-memory/pr/0165-ir-01-five-model-inventory/BASELINE_EXECUTION.md`
(91 real executions, 50 completed, 0 unexpected failures, two
bit-exact reproductions of pre-existing golden/production values).
**App Runner parity remains `pending` for all five** — this task
explicitly does not and cannot claim App Runner verification from
local execution. IR-01's full acceptance gate (per
`.project-memory/pr/ir-01/PLAN.md`) also still requires live
catalog/S3 re-confirmation and a reviewed resource/cost budget, neither
of which this pass could perform.

See `.project-memory/pr/0165-ir-01-five-model-inventory/INVENTORY_EVIDENCE.md`
for the complete, file-by-file evidence trail, exact commands run, and
instructions for the next agent, and
`.project-memory/pr/0165-ir-01-five-model-inventory/IMPLEMENTATION_REPORT.md`
for the updated IR-01 gate decision.
