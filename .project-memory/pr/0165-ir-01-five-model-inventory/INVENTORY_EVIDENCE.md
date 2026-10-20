# INVENTORY_EVIDENCE.md — IR-01 five-model inventory

Branch: `0165-ir-01-five-model-inventory`. All evidence below is read-only
repository evidence (committed files already present in this working
tree before this task started: `results/`, `testing_results/`, and
tracked docs/code). No live AWS/S3/App Runner call was made. No patient
H5 content, credentials, or raw artifact bytes are reproduced here —
only identifiers, hashes, and numeric outputs already present in
pre-existing, already-committed-or-already-untracked-but-present
repository files.

## 1. Catalog identity evidence (all five)

**Corrected 2026-10-21 (precommit review B1):** the table below was
previously mislabeled — six of seven rows showed each file's
`last_discovery_at` field value under a `catalog_timestamp` header. It
now shows each file's actual `catalog_timestamp` field value, verified
directly against the JSON on disk (`python3 -c "import json;
print(json.load(open(path))['catalog_timestamp'])"` for each file),
plus `last_discovery_at` as a separate, explicitly labeled column so
both previously-recorded figures remain available and nothing is
silently dropped.

Seven captured catalog snapshots, stored as separate JSON files dated
2026-09-10 through 2026-09-17, each contain an identical five-entry
catalog listing with `candidate_count: 5`, `available_count: 5`,
`rejected_count: 0`:

| Capture file | `catalog_timestamp` (verified) | `last_discovery_at` (verified) |
|---|---|---|
| `testing_results/results/evidence/pre0157-auth-check.json` | `2026-09-11T08:53:23.108255+00:00` | `2026-09-10T19:05:54.409789+00:00` |
| `results/post0158-live/models.json` | `2026-09-16T12:05:41.863270+00:00` | `2026-09-16T11:59:06.107914+00:00` |
| `testing_results/results/live-2026-09-16/models.json` | `2026-09-16T11:20:47.419705+00:00` | `2026-09-16T10:51:29.531646+00:00` |
| `results/post0158a-live/models.json` | `2026-09-16T13:41:53.960056+00:00` | `2026-09-16T13:34:17.511732+00:00` |
| `results/live-pr0160-smoke/models.json` | `2026-09-17T11:05:29.272081+00:00` | `2026-09-17T10:36:17.879908+00:00` |
| `results/all-patients-model-matrix-20260917-121431/models.json` | `2026-09-17T11:14:44.731223+00:00` | `2026-09-17T10:36:17.879908+00:00` |
| `results/post0161-prod-smoke-20260917-163154/models.json` | `2026-09-17T15:31:49.268596+00:00` | `2026-09-17T15:11:50.540690+00:00` |

Each lists exactly:

```
aramina_target_breast_risk_0_2_12-beta_9bb911189af6  / 0.2.12-beta
aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11  / 0.2.13-beta
bremen-mri-triage-logreg-v0-1                        / bremen_mri_triage_logreg_v0_1
bremen-paper-reference-v0-2-0                        / 0.2.0-paper-reference
bremen-v0-2-0-symmetry-candidate                     / bremen_mri_triage_symmetry_logreg_0_2_0-research
```

**On independence (precommit review B2):** these seven files are
confirmed to be distinct stored JSON artifacts (distinct SHA256 hashes,
distinct `catalog_timestamp`/`last_discovery_at` values), and the model
identities/counts repeat consistently across all seven. That repetition
is the useful fact this inventory relies on. None of the seven files
contains a capture command, endpoint/session identifier, request ID,
deployment identity, or other provenance field that would prove they
are independent observations (separate sessions, separate operators,
or separate underlying deployments) rather than repeated exports
collected in one run or from one source. This document therefore does
**not** claim the seven captures are independent — only that they are
seven separately stored historical snapshots that consistently show
the same five-entry catalog. This is **not** a live confirmation for
today; the catalog could have changed since September 2026.

## 2. A1 — `aramina_target_breast_risk_0_2_12-beta_9bb911189af6`

- Fresh production execution, `docs/production-contracts-2026-09-18.md`
  §4.1: `job_id=225f10bc-18f8-4343-a11e-eb86d77ac58f`, patient `Nova_257`,
  `target_side=left`, `risk_probability=0.9430773645281599`,
  `threshold_value=0.24665932038818544`, HTTP 201/200 end-to-end.
- Expected-failure execution, §4.3: `Nova_384`/left,
  `failure=ARAMINA_UNSUPPORTED_INPUT`,
  `preprocessing_release=v0.1.7-beta`,
  `preprocessing_transformer=H5PoniGeometryCalculatorTransformer`. This
  directly evidences (not infers) that A1 maps to preprocessing release
  `v0.1.7-beta` for this input.
- `src/bremen/model_packages/aramina_v0213/manifest.py`:
  `ALLOWED_PREPROCESSING_RELEASES = {"v0.1.7-beta", "v0.1.9-beta"}` (both
  releases allowlisted; this file does not itself say which model_id
  maps to which — the production capture above is what resolves that for
  this one input).
- **Not found:** full artifact SHA256; S3 manifest key/bytes/hash;
  current deployed image digest; a repository-committed golden fixture
  for A1 specifically (only live-capture spot checks exist).

## 3. A2 — `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11`

- Fresh production execution, `docs/production-contracts-2026-09-18.md`
  §4.2: `job_id=42d8adc3-1d4a-44ee-9a67-21adb31c8899`, patient `Nova_257`,
  `target_side=left`, same `risk_probability=0.9430773645281599` and
  `threshold_value=0.24665932038818544` as A1 for this one input (the
  document explicitly notes this equality is input-specific, not a
  general claim both releases always agree).
- Also independently confirmed in `results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`
  for a **different** patient (`Nova_214`, left):
  `risk_probability=0.869387073973647`,
  `decision_threshold=0.24665932038818544`,
  `model_metrics={"sensitivity":0.8175,"specificity":0.37630084054979734}`,
  `model_method="m2q_gated_target_case"`. This is a second, distinct
  fixture/output pair for A2, useful as an additional golden candidate.
- Expected-failure execution, §4.4: `Nova_384`/left,
  `preprocessing_release=v0.1.9-beta` — directly evidences A2 maps to
  `v0.1.9-beta` for this input.
- **Not found:** same gaps as A1 (full SHA256, S3 manifest, image
  digest, dedicated committed golden fixture).

## 4. B1 — `bremen-mri-triage-logreg-v0-1`

- Catalog entries (all seven captures above) give
  `model_version=bremen_mri_triage_logreg_v0_1`,
  `feature_schema_version=v0.1`,
  `decision_policy_id=bremen_mri_continuation_threshold`,
  `decision_policy_version=0.1.0`.
- `docs/production-contracts-2026-09-18.md` §3.1: fresh production job
  `job_id=2b174fb6-01f6-4c00-91a3-6eca87923f6b`, patient `Nova_376`,
  `risk_probability=0.5677291934209008`,
  `threshold_value=0.3640352477169748`, `reliability=HIGH_TECHNICAL`.
- `testing_results/results/evidence/pre0157-report-bremen.json` (earlier
  capture, 2026-09-11): same `model_id`/`model_version`, threshold
  `0.3640352477169748` again, but a **different** probability
  (`p_mri_needed=0.9999716577320301`) for a different patient/fixture
  (reliability `LOW_TECHNICAL`, 1 left / 1 right measurement) — this is
  expected (different input), not a contradiction; recorded here so the
  next agent does not conflate the two probabilities as the same
  fixture. That same report's `model_identity.model_checksum` field is
  present but **empty (`""`)** — the checksum was not populated for B1
  in this historical capture.
- `docs/production-contracts-2026-09-18.md` §13 separately flags
  `model_name`/`model_version`/`model_method` as "NEEDS VERIFICATION"
  for this model_id — an open, pre-existing concern this pass does not
  resolve.
- **Unverified lead (do not treat as confirmed):**
  `.project-memory/pr/0039-inference-integration/PLAN.md` references SHA256
  `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` and
  S3 URI `s3://matur-misc-uk/bremen/models/bremen-xrd-classifier/v0.1/bremen_mri_triage_logreg_v0_1_model_package.joblib`
  as design-time defaults in an old PR's Terraform variable defaults.
  This long predates the catalog captures above and is not corroborated
  by any execution evidence found in this pass; it must be independently
  re-verified (e.g. against the live S3 object and the artifact actually
  loaded by the running service) before being treated as B1's current
  checksum.

## 5. B2 — `bremen-paper-reference-v0-2-0`

Best-evidenced of the five; three independent sources agree:

| Field | Value | Sources |
|---|---|---|
| Artifact SHA256 | `65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0` | `src/bremen/model_packages/bremen_v01/manifest.py` (`ARTIFACT_SHA256`); `docs/bremen_3x3_training_parity.md`; `results/post0161-prod-smoke-20260917-163154/detail-bremen-success-nova227.json` (`model_checksum`); `results/live-pr0160-smoke/detail-nova227.json` (`model_checksum`) |
| Threshold | `0.3585907282566089` | `manifest.py` (`THRESHOLD_VALUE`); both captures above (`threshold_applied`) |
| Feature schema | `v0.1`, 15 features | `manifest.py` (`FEATURE_SCHEMA_VERSION`); captured execution trace stage `features_validated`: `expected_count:15, produced_count:15, missing_count:0, non_finite_count:0, feature_order_valid:true, schema_matched:true` |
| Golden/raw-H5 probability | `0.7726940329943809` (captured) vs `0.7726940329943811` (PR0160 reference) for Nova_227, raw path | `results/live-pr0160-smoke/detail-nova227.json`; `results/post0161-prod-smoke-20260917-163154/detail-bremen-success-nova227.json`; `docs/inference-releases/parity-and-rollout.md` (PR0160 reference) |
| Tolerance already approved for the above pair | `abs_tol=1e-10, rel_tol=0` → `True` | `.project-memory/pr/0160-model-package-owned-scientific-preprocessing/PRECOMMIT_REVIEW.md` |
| Synthetic golden fixture probability | `0.7388733541967353` | `tests/fixtures/bremen_3x3/` (per `docs/bremen_3x3_training_parity.md`, `docs/model_package_standard_v1.md`); not re-executed in this pass (pytest unusable — see §7) |

This is the only one of the five with a reproducible, cross-confirmed
checksum/threshold/feature-count triple, and the only one with a
repository-committed golden fixture (`tests/fixtures/bremen_3x3/`),
though that fixture was not re-run in this session.

## 6. B3 — `bremen-v0-2-0-symmetry-candidate`

Exhaustive search of the repository (`grep -rln` across `*.py`, `*.md`,
`*.json` for `symmetry-candidate` and `symmetry_logreg_0_2_0`) found:

- The catalog string itself, identically, in every capture listed in §1
  — so this is a real, currently-registered (as of Sept 2026) catalog
  entry, not a fabricated slot.
- A superficially similar name,
  `bremen_paper_reference_symmetry_logreg_0_2_0-paper-reference_20260802T173549Z_6c8b029f`,
  referenced in `.project-memory/pr/0151-bremen-3x3-training-parity/PRECOMMIT_REVIEW.md`,
  `.project-memory/pr/0152-bremen-3x3-runtime-parity/PLAN.md`,
  `.project-memory/pr/0152-bremen-3x3-runtime-parity/PRECOMMIT_REVIEW.md`,
  and `docs/bremen_3x3_training_parity.md`. **Verified these all refer to
  B2's training run** (same SHA256 `65866f44...`, same `manifest.json`
  identity `bremen-paper-reference-v0-2-0`), **not** B3. Do not conflate
  "symmetry" appearing in both names as evidence they are the same
  artifact — they are not.
- No checksum, no training-run record, no exercised job/prediction, and
  no fixture referencing the exact string `bremen-v0-2-0-symmetry-candidate`
  or `bremen_mri_triage_symmetry_logreg_0_2_0-research` was found
  anywhere else in the repository.

**B3 is the clearest open blocker of the five.** It exists in the
catalog but has zero behavioral or provenance evidence in this
repository.

## 7. Resource/feasibility evidence (repository-code only)

- `Dockerfile`: base `python:3.13-slim`; production target builds the
  main app venv plus three auxiliary venvs —
  `/opt/bremen-preprocess` (xrd-preprocessing @ commit
  `45d5568248e9774b7938a36e028d80e72b130b19`),
  `/opt/aramina-preprocess` (`v0.1.7-beta`),
  `/opt/aramina-preprocess-019` (`v0.1.9-beta`). No numeric image-size
  measurement is available in this repository.
- `src/bremen/platform/jobs/service.py`:
  `_executor = ThreadPoolExecutor(max_workers=2, ...)` — current
  concurrency ceiling is 2 in-process threads, not process-isolated
  workers.
- `infra/terraform/apprunner.tf`: defines only a "smoke / proving target
  only" service (its own header comment; cross-references ADR-0008,
  which at the time named ECS Fargate, not App Runner, as the intended
  long-term production target — since superseded by ADR-0019/this
  roadmap). No `instance_configuration` (CPU/memory) override is set in
  this file. **This file is not confirmed to be the production
  service's actual definition** — the real production App Runner
  service's Terraform/console configuration is not present in this
  repository and must be obtained via authorized deployment access.
- No "OpenResty" reference exists anywhere in source, `infra/`, or
  `.github/workflows/` — only in this roadmap's own planning docs, which
  already treat it as an explicit, unconfirmed assumption. This is
  consistent with (but does not prove) the working assumption that
  "OpenResty" means the existing App Runner deployment.
- AWS App Runner's documented limits (120s request timeout, 5-minute
  startup health window, 3 GB ephemeral storage) were already recorded
  in `docs/inference-releases/operations.md` prior to this pass and are
  unchanged by it; they were not independently re-verified against
  AWS documentation in this session (no network access to re-check the
  cited URL).

## 8. What this pass did NOT and could not do

- No live call to the actual S3 catalog, model registry, or App Runner
  service — no deployment credentials were available in this session.
- No image digest, CPU/RSS/cost measurement, or cold/warm timing was
  collected — all of §7 is static repository-code reading, not a
  measurement.
- No golden fixture was executed (`pytest` could not run in this
  session — see IMPLEMENTATION_REPORT.md §8 for the environment
  failure). The B2 numbers above are from **previously captured**
  production/test evidence files already present in the repository
  tree, re-read and cross-checked in this pass, not freshly executed.
- Full artifact SHA256 for A1, A2, and B1 was not found anywhere in the
  repository. B3 has no evidence beyond its catalog string.
- The one unverified SHA256/S3-URI lead for B1 (§4) was explicitly
  flagged as unverified, not adopted as fact.

## 9. Local artifact-directory pass (2026-10-20, continuation)

A second evidence pass used five local artifact directories supplied for
this task at `/tmp/bremen-ir01-models` (external, read-only input — not
copied into git, per HARD RULES).

**Provenance caveat (added 2026-10-21, precommit review):** these five
directories are described here only as **operator-supplied local
copies**, understood to originate from the project's S3 model storage
but not independently confirmed as such in this session. No capture/
export command, S3 endpoint, request/session identifier, authorization
context, or immutable S3 object-version ID was captured alongside
these directories to prove when, how, or by whom they were exported,
or that they match a specific live S3 object version. This is
distinct from **artifact integrity**, which *is* independently verified
below: every artifact's SHA256 matches its own co-located manifest's
declared `model_checksum` (an internal self-consistency check,
performed by this agent with `shasum -a 256`), and several of those
checksums also match values independently recorded elsewhere in this
repository's evidence (catalog captures, production executions, or a
prior PR's design-time reference — see §2–§6). Self-consistency and
cross-matches establish that the local files are not corrupted and are
consistent with other evidence already in this repository; they do
**not** by themselves establish an audited chain of custody from a
specific S3 object to this local directory. Inventory:

```
/tmp/bremen-ir01-models/0.2.0-paper-reference/   4 files (manifest.json, model.joblib, container_requirements.json, model_description.yaml)
/tmp/bremen-ir01-models/aramina_0_2_12-beta/     11 files (manifest.json, model.joblib, preprocessing_config.yaml, training_config.yaml, model_description.yaml, container_requirements.json, evaluation.yaml, evaluation_metrics.csv, evaluation_predictions.csv, prediction_preprocessing_config.yaml, preprocess_and_train_config.yaml)
/tmp/bremen-ir01-models/aramina_0_2_13-beta/     11 files (same set as 0_2_12-beta)
/tmp/bremen-ir01-models/v0.1/                     3 files (manifest.json, bremen_mri_triage_logreg_v0_1_model_package.joblib, container_requirements.json)
/tmp/bremen-ir01-models/v0.2.0/                  12 files (manifest.json, model.joblib, bremen_mri_triage_symmetry_logreg_v0.2.0.joblib [byte-identical to model.joblib, confirmed via `cmp`], feature_schema.json, label_mapping.json, metrics.json, model_description.yaml, training_config.yaml, preprocessing_config.yaml, prediction_preprocessing_config.yaml, evaluation.yaml, container_requirements.json)
```

Commands run (all read-only; no `joblib.load`/unpickling performed —
only `find`, `ls -la`, `cat`, `diff`, `cmp`, and `shasum -a 256`):

```
find /tmp/bremen-ir01-models -type f -exec ls -la {} \;
cat <dir>/manifest.json   (all five)
shasum -a 256 <every file in all five directories>
cmp v0.2.0/model.joblib v0.2.0/bremen_mri_triage_symmetry_logreg_v0.2.0.joblib
diff aramina_0_2_12-beta/{training_config,preprocess_and_train_config,preprocessing_config,model_description}.yaml \
     aramina_0_2_13-beta/{training_config,preprocess_and_train_config,preprocessing_config,model_description}.yaml
cat <dir>/{model_description.yaml,feature_schema.json,metrics.json,label_mapping.json,container_requirements.json,training_config.yaml}  (as present per dir)
```

### Directory → catalog-slot mapping (confirmed by manifest `model_id`, not by directory name)

| Local directory | `manifest.json` → `model_id` | Mapped slot |
|---|---|---|
| `0.2.0-paper-reference/` | `bremen-paper-reference-v0-2-0` | B2 |
| `aramina_0_2_12-beta/` | `aramina_target_breast_risk_0_2_12-beta_9bb911189af6` | A1 |
| `aramina_0_2_13-beta/` | `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11` | A2 |
| `v0.1/` | `bremen-mri-triage-logreg-v0-1` | B1 |
| `v0.2.0/` | `bremen-v0-2-0-symmetry-candidate` | B3 |

Each mapping is from the manifest's own declared `model_id` field, not
inferred from the directory name (the directory names are themselves
version strings/aliases, e.g. `v0.2.0` for B3, which could otherwise be
confused with B2's `0.2.0-paper-reference` — the manifest content is
what disambiguates them).

### Checksum verification (every artifact self-consistent)

```
65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0  0.2.0-paper-reference/model.joblib   == manifest model_checksum  (B2)
9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d  aramina_0_2_12-beta/model.joblib     == manifest model_checksum  (A1)
f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b  aramina_0_2_13-beta/model.joblib     == manifest model_checksum  (A2)
8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e  v0.1/bremen_mri_triage_logreg_v0_1_model_package.joblib == manifest model_checksum  (B1)
971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4  v0.2.0/model.joblib                   == manifest model_checksum  (B3)
```

All five: computed SHA256 == that same artifact's own manifest's
`model_checksum`. This proves internal self-consistency of each local
package; it does **not** by itself prove these are the exact bytes
currently live in S3/App Runner today — see §9c.

### Cross-check against prior evidence (§1–§6 above)

- A1: local checksum `9bb911189af6...` — the model_id's own suffix
  (`9bb911189af6`) is confirmed to be the literal SHA256 prefix, not an
  arbitrary tag.
- A2: same pattern, suffix `f5e4a04cad11` confirmed as SHA256 prefix.
- B1: local checksum `8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e`
  **exactly matches** the previously-flagged "unverified lead" from
  `.project-memory/pr/0039-inference-integration/PLAN.md` (§4 above).
  That lead is now artifact-confirmed, not merely a historical Terraform
  default — though still not independently confirmed against the live
  S3 object.
- B2: local checksum matches the value already cross-confirmed from
  three prior sources (§5) — a fourth independent match.
- B3: **no prior value existed anywhere in the repository**; this is
  new evidence.

### B1 — confirmed artifact-level gap

`v0.1/manifest.json` itself declares
`"threshold_value": -1, "threshold_version": "unconfirmed_placeholder", "qc_criteria_version": "unconfirmed_placeholder"`.
This is the artifact's own manifest admitting its threshold/QC identity
were never finalized in this manifest — the real applied threshold
(`0.3640352477169748`, from §4's production capture) must be sourced
from inside the joblib artifact at runtime (e.g. an embedded model
contract), not from this manifest file. No `feature_schema.json` or
`model_description.yaml` exists for B1 locally, unlike B2/B3/A1/A2 — B1
remains the least-documented of the five even with local artifact
access.

### B3 — resolved: real, distinct, exploratory-label model

`v0.2.0/model_description.yaml`, `feature_schema.json`,
`label_mapping.json` and `metrics.json` together fully describe a real,
trained, distinct artifact:

- Same 15-feature contract (`bremen_h5_15feature_v0_2`) and architecture
  family as B2, but a **different label**:
  `label_column: mri_presence_proxy_label`,
  `label_status: exploratory_proxy_not_clinically_reviewed`,
  `allow_exploratory_proxy: true`. `model_description.yaml`'s own
  limitations section states: "Current runnable model uses an
  MRI-presence proxy, not a reviewed MRI-continuation endpoint" and
  "not clinically validated."
- Distinct threshold `0.4130396520921527`
  (`threshold_source: train_all_target_sensitivity`) and distinct
  decision classes (`CONTINUE_MRI`/`MRI_REVIEW_DEFER`) vs. B2's
  (`CANCER`/`NON-CANCER`, threshold `0.3585907282566089`).
- This closes the open question "is B3 real or only a catalog string?"
  — **real**, and explicitly ruled out as a duplicate of B2 (which the
  superficial "symmetry" name match in §6 could have suggested).
- **Safety carry-forward:** the `exploratory_proxy_not_clinically_reviewed`
  label status must be preserved into any future IR-02+ release
  metadata for B3; it must not be presented as equivalent in validation
  status to B2's reviewed paper-reference baseline.

### A1/A2 — preprocessing mapping upgraded from single-fixture to artifact-declared

`aramina_0_2_12-beta/preprocessing_config.yaml` declares
`release_tag: v0.1.7-beta`; `aramina_0_2_13-beta/preprocessing_config.yaml`
declares `release_tag: v0.1.9-beta`. `diff` confirms all other
config/training files between the two directories are identical except
version-identity fields. This directly confirms, from the artifact's own
declared config (not only from one shared production fixture as in §2–3
above), that A1↔v0.1.7-beta and A2↔v0.1.9-beta generally, not only for
the one input tested in September.

Both artifacts' `model_description.yaml` confirm final model class
`GatedSymmetryLogistic` with the exact `base_feature_columns`/
`symmetry_feature_columns` matching
`src/bremen/model_packages/aramina_v0213/manifest.py`'s
`FINAL_FEATURE_COLUMNS`. `threshold_target: 0.24666` in the artifact
manifest is the same value as the production-captured
`decision_threshold=0.24665932038818544`, rounded to 5 decimals in the
artifact's description file — not a new discrepancy (see
`parity-and-rollout.md`'s new precision note).

### 9.1 What this local-artifact pass did NOT do

- Did **not** run `joblib.load()` or otherwise unpickle any of the five
  `.joblib` files — only SHA256 hashing (byte-level, not
  deserialization) and plain-text YAML/JSON reading, per the HARD RULE
  against loading pickle/joblib outside the existing controlled
  model-loading boundary.
- Did **not** execute any baseline prediction. This session's Python
  environment remains broken (same failure recorded in
  IMPLEMENTATION_REPORT.md §8 of the prior pass: dangling
  `venv/bin/python3.13` symlink; system `python3` missing
  `numpy`/`h5py`), and no H5 input fixture was supplied alongside these
  five directories to exercise a full prediction even if the
  environment worked.
- Did **not** independently establish the provenance of
  `/tmp/bremen-ir01-models` itself (who produced it, when, from which
  authorized source) — it was supplied as task input. Its content is
  self-consistent and corroborates prior evidence strongly, but this is
  not equivalent to an independently-authorized live S3/catalog pull.
- Did **not** copy any file from `/tmp/bremen-ir01-models` into the git
  working tree.

### 9.2 Residual blockers after this pass

1. Live catalog/S3/App Runner re-confirmation as of today, 2026-10-20 —
   still not performed (no deployment credentials in this session).
2. No baseline execution — environment broken, no H5 fixtures.
3. B1 feature schema / real threshold source — still not documented
   anywhere, local or repository; only its checksum and (placeholder)
   manifest are known.
4. App Runner resource/cost measurement — unaffected by this pass,
   still blocked exactly as before.
5. Independent confirmation that `/tmp/bremen-ir01-models` reflects the
   artifacts the *live* service currently loads (as opposed to a
   point-in-time export) is still required from whoever has live access.

## 10. Real local baseline execution pass (2026-10-21)

A third pass (`0165-ir-01-local-baseline-execution`) obtained a genuine
Python 3.13 interpreter outside the repository
(`uv python install 3.13`; no dependency file edited) and executed all
five models against 49 real local H5 fixtures
(`/tmp/bremen-ir01-fixtures/v0.1`, ~318 MB, external read-only input)
through the existing, unmodified
`bremen.platform.runtime.executor.execute` orchestration. Full detail,
the complete 91-run matrix, exact commands, and the per-category
failure breakdown are in
`.project-memory/pr/0165-ir-01-five-model-inventory/BASELINE_EXECUTION.md`
and the fixture discovery/identity work is in
`.project-memory/pr/0165-ir-01-five-model-inventory/FIXTURE_INVENTORY.md`.
Headline results:

- **91 real executions: 50 completed, 41 failed with typed/expected
  safe reasons, 0 unexpected exceptions.**
- B2 on `benign_one_patient.h5` reproduced the PR0160 golden reference
  probability `0.7726940329943811` bit-for-bit.
- A1 and A2 on `eoscloud-staging/cabce03d-f9c4-43db-91d1-aec20007ee18.h5`
  (confirmed to be the exact file already referenced by `container_id`
  in `results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`)
  reproduced that captured production result exactly.
- B1's "unconfirmed placeholder" manifest threshold (§4 above) was
  **not** invented or substituted: direct execution shows the runtime
  reads the real threshold from inside the artifact's own
  `portable_logreg` block (`0.3640352477169748`, matching
  `docs/production-contracts-2026-09-18.md`), never from the manifest
  sidecar field.
- A genuine, reproducible dependency-provenance finding: the
  `xrd-preprocessing` `v0.1.7-beta` git tag currently resolves to a
  different commit (`1c03a06488e0c56297f49c060dfc69ccce4704c7`) than
  the artifact's own pinned provenance
  (`45d5568248e9774b7938a36e028d80e72b130b19`). Installing the exact
  commit SHA (not the tag) in a disposable venv resolved this for the
  session; no repository dependency file was changed.
- A genuine cross-model finding: `Nova_103_.h5` (legacy
  `detector_scoped_v1` layout) is **accepted by B1** (legacy canonical
  adapter) but **rejected by B2, B3, A1 and A2** — the five variants do
  not share one uniform input-layout compatibility contract today.

No new inference logic was written. No model artifact was modified. No
`.h5`/`.joblib` file was copied into git. No raw pickle was loaded
outside the existing controlled loading boundary
(`load_staged_artifact`, `_load_selected_artifact`).

## 11. What the baseline execution pass did NOT and could not do

- Did not call any live AWS/S3/App Runner endpoint; this is local
  execution only and is not App Runner verification.
- Did not exhaustively root-cause every one of the 41 failures to its
  exact underlying exception; two representative cases were diagnosed
  by directly invoking the existing worker scripts (not by adding new
  diagnostic code) — see `BASELINE_EXECUTION.md`'s failure-category
  table.
- Did not run all 49×5 = 245 possible fixture/model combinations; a
  representative 91-run sample was used, selected to cover every
  unique patient identity found in `FIXTURE_INVENTORY.md` (per the
  task's own instruction not to force every fixture through every
  model when unnecessary).
- Did not change B3's exploratory-label review status — real outputs
  now exist, but the label (`exploratory_proxy_not_clinically_reviewed`)
  is unaffected by running the model.
- Did not establish the provenance of `/tmp/bremen-ir01-models` or
  `/tmp/bremen-ir01-fixtures` (export date, process, authorization) —
  both were supplied as task input.

## 12. Instructions for the next agent (live-access holder)

1. Call the live catalog endpoint today and diff the result against the
   five-entry table in §1. If it differs, update
   `docs/inference-releases/five-model-inventory.md` and record the
   diff — do not silently assume continuity.
2. For each of the five, pull the S3 manifest bytes/hash and the actual
   loaded artifact's SHA256 directly from the deployed environment;
   compare against the values recorded in §2–§6 and flag any mismatch
   with the historical evidence (especially the unverified B1 lead in
   §4, which should be confirmed or discarded).
3. ~~Run `tests/fixtures/bremen_3x3/` end-to-end in a working Python
   environment~~ — **done in §10**: a genuine Python 3.13 environment
   was obtained outside the repository
   (`uv python install 3.13`) and 91 real executions were run; the full
   `pytest` suite also now passes (3975 passed, 0 failed) under that
   environment. The synthetic golden value `0.7388733541967353`
   (`tests/fixtures/bremen_3x3/`) specifically was not independently
   re-verified in §10 (which used real H5 fixtures, not that synthetic
   fixture) — re-running that specific test file is a small remaining
   step, not a blocked one, now that a working environment exists.
4. Obtain the actual production App Runner service definition (Terraform
   state or console) — `infra/terraform/apprunner.tf` in this repository
   is explicitly a smoke/proving definition, not confirmed production.
   Measure real CPU/RSS/cost/cold-start numbers per §7's starting point.
   Local execution durations are recorded in `BASELINE_EXECUTION.md` but
   are not a substitute for production measurement.
5. Confirm or refute the OpenResty/topology assumption directly against
   the deployed infrastructure, not from absence-of-evidence in this
   repository.
6. For B3 specifically: the local artifact in §9 and real execution in
   §10 resolve "is it real?" (yes) and "does it run?" (yes, 15/21 local
   fixtures completed) — what remains is its clinical review status
   (still `exploratory_proxy_not_clinically_reviewed`) and live/S3
   confirmation that this exact artifact is what App Runner serves.
7. Investigate the `xrd-preprocessing` `v0.1.7-beta` tag/commit drift
   recorded in §10 with the repository that owns that tag — it is an
   external dependency-tagging concern, not a Bremen code defect.
