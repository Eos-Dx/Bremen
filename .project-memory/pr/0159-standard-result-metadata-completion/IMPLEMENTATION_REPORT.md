# IMPLEMENTATION_REPORT.md — PR0159 Standard Model Result Metadata Completion

## 1. Task Completed

PR0159 — Standard Model Result Metadata Completion (including the architecture
correction: model-specific parsing must live in the model packages, not the
API/runner).

## 2. Branch / PR

- Branch: `0159-standard-result-metadata-completion`
- PR: 0159
- HEAD: working tree on top of `5d4f34e` (no commits made; no commit performed)

## 3. Files Changed

### Created

- `src/bremen/model_packages/bremen_v01/source_metadata.py`
- `src/bremen/model_packages/aramina_v0213/source_metadata.py`
- `tests/test_bremen_package_metadata_adapters_pr0159.py`
- `tests/test_bremen_standard_result_metadata_pr0159.py`
- `.project-memory/pr/0159-standard-result-metadata-completion/PLAN.md`
- `.project-memory/pr/0159-standard-result-metadata-completion/IMPLEMENTATION_REPORT.md` (this file)

### Modified

- `src/bremen/model_runtime.py` — added transport-neutral normalized contract
  (`SourceMetadata`, `ModelMetadata`, `ModelMetrics`) and three new
  `RuntimePrediction` fields.  `SourceMetadata.eoscan_version` is
  `str | None`; the default is `None` (no authoritative package-owned Eoscan
  version source).
- `src/bremen/api/workflow_orchestrator.py` — passes the platform-staged
  `h5_path` to the Bremen provider too (documented `ModelInput.container_path`
  bridge); TypeError fallbacks preserved.
- `src/bremen/api/workflow_bremen.py` — `execute(..., *, h5_path="")`, passes
  `container_path` into `ModelInput`, projects the normalized contract into the
  workflow payload.
- `src/bremen/api/workflow_aramina.py` — projects the normalized contract into
  the workflow payload.
- `src/bremen/model_packages/bremen_v01/runtime.py` — attaches the normalized
  contract to the `RuntimePrediction` (source metadata parsed by the Bremen
  package adapter; metrics from the active package's
  `final_fit_training_metrics`).
- `src/bremen/model_packages/aramina_v0213/runtime.py` — attaches the
  normalized contract to the `RuntimePrediction`.
- `src/bremen/model_packages/aramina_v0213/inference.py` — `_run_local_artifact`
  now returns `(report, source_metadata, model_metadata, model_metrics)`; the
  model-native report dict is unchanged.
- `src/bremen/model_packages/bremen_v01/source_metadata.py` and
  `src/bremen/model_packages/aramina_v0213/source_metadata.py` — both package
  adapters now return `eoscan_version=None`; `producer_version` is NOT mapped
  to `eoscan_version` (see Key Decisions #7).
- `src/bremen/api/model_result_mapper.py` — consumes only the normalized
  contract keys (`source_metadata`, `model_metadata`, `model_metrics`) from the
  runtime result; `_clean_age`/`_clean_metrics`/`_clean_eoscan_version`
  helpers; `model_method` falls back to the documented rule when the package
  provides none.  `eoscan_version` passes through `None` when absent.
- `src/bremen/api/standard_model_result.py` — `eoscan_version` is
  `str | None` with default `None` (explicit absence when no authoritative
  package-owned Eoscan version source exists).
- `tests/test_bremen_model_runtime_contract_v1.py` — Aramina delegation fakes
  updated to the new `_run_local_artifact` return shape.
- `tests/test_aramina_workflow_runtime.py` — payload key-set assertions updated
  to include the three normalized metadata transport keys.
- `tests/test_bremen_standard_model_result_v1.py` — absence assertion for
  `eoscan_version` updated to `None`.
- `tests/fixtures/standard_model_result/bremen_v01_golden.json` and
  `tests/fixtures/standard_model_result/aramina_v0213_golden.json` —
  `eoscan_version` updated to `null` (explicit absence).
- `tests/test_bremen_package_metadata_adapters_pr0159.py` — canonical-source
  expectation updated to `eoscan_version: None`; the old
  producer_version-promotion test replaced with explicit non-promotion tests
  for BOTH Bremen and Aramina.
- `tests/test_bremen_standard_result_metadata_pr0159.py` — integration
  assertion updated: `standard_result.eoscan_version is None`.

### Removed (reworked per architecture correction)

- `src/bremen/api/h5_source_metadata.py` (API-owned H5 parser — removed)
- `tests/test_bremen_h5_source_metadata_pr0159.py` (API-owned H5 parsing tests
  — removed)
- The API-level `MultiWorkflowResult.source_metadata`,
  `WorkflowRun.source_metadata`, `_mapper_job_context` extension and
  orchestrator extraction were reverted (the API no longer parses or carries
  model-specific H5 metadata).

## 4. Implementation Summary

The seven previously-empty Standard Model Result v1 fields are now populated
for both Bremen and Aramina through the corrected architecture:

```
model-specific parser/preprocessing
→ model-package adapter (Bremen / Aramina)
→ common normalized metadata contract (bremen.model_runtime)
→ ModelRuntime transport (RuntimePrediction)
→ Standard Result mapper
```

Each model package owns the interpretation of its own container/artifact
metadata (`bremen_v01/source_metadata.py` and
`aramina_v0213/source_metadata.py`) and produces the SAME normalized
`SourceMetadata` / `ModelMetadata` / `ModelMetrics` contract.  The
`RuntimePrediction` transports the contract; each provider projects it into the
workflow payload verbatim; the mapper performs only normalized runtime result →
Standard Model Result.

## 5. Key Decisions Made During Implementation

1. **Normalized contract types live in `bremen/model_runtime.py`** — the
   existing neutral platform/model semantic boundary already imported by both
   packages; adding the dataclasses there keeps the transport types shared
   without any H5/model knowledge.
2. **Aramina metrics source = active artifact held-out evaluation**
   (`model_performance.held_out_metrics.sensitivity.mean` /
   `specificity.mean`), per the correction; NOT `final_fit_training_metrics`
   (which would hardcode 0.2.12-style train-on-all values).
3. **Bremen metrics source = the exact active `0.2.0-paper-reference`
   package's own `final_fit_training_metrics`** (verified the paper-reference
   artifact has no `model_performance`; the values are the artifact's own, not
   copied from the `0.2.0-research` artifact).  Absent metrics → `None`.
4. **`model_method` = package's own model-type/inference-method field**
   (Bremen `model_definition.architecture`, Aramina top-level `model_type`),
   with the PR0157 documented `model_method == model_version` fallback when the
   package provides none (preserves existing mapper-unit and frozen-fixture
   behavior for synthetic fixtures that lack those fields).
5. **`_run_local_artifact` return shape changed to a 4-tuple** so the
   artifact-derived normalized metadata (which requires the loaded package
   dict) reaches the runtime; the model-native report dict is unchanged and
   the two affected delegation tests were updated accordingly.
6. **Bremen `h5_path` plumbed via the documented `ModelInput.container_path`
   bridge** (`execute(..., *, h5_path="")`); TypeError fallbacks keep
   legacy/fake providers working.
7. **`producer_version` is NOT mapped to `eoscan_version`.**  Observed
   provenance (`producer_software = "omniscan-backfill"`,
   `producer_version = "0.1.0"`) shows the producer is the omniscan backfill
   pipeline, not the Eoscan acquisition software, and there is no
   package/artifact/schema evidence that the attribute semantically means
   Eoscan version.  Both package adapters therefore return
   `eoscan_version=None` (explicit absence); no H5 alias is promoted.  The
   normalized contract type, the mapper, and the Standard Model Result
   contract represent this as `None`/`null`.

## 6. Deviations From PLAN.md

The PLAN.md was updated in-place to reflect the architecture correction before
final implementation.  Final implementation matches the updated PLAN.md.

## 7. Warnings / Unresolved Questions

- Ruff on `tests/test_aramina_workflow_runtime.py` reports 6 pre-existing
  `F401` findings (unused `AraminaPreprocessingError` imports) in test
  functions untouched by this PR (verified identical on `HEAD`).
- No other warnings.

## 8. Validation Commands and Results

| Command | Result |
| --- | --- |
| `./venv/bin/python -m compileall -q src tests` | pass (exit 0) |
| Focused tests (`tests/test_bremen_package_metadata_adapters_pr0159.py`, `tests/test_bremen_standard_result_metadata_pr0159.py`) | 29 passed |
| Relevant existing suites (standard result v1, PR0158a hardening, ModelRuntime contract v1, Bremen v0.1 package, Aramina v0.2.13 package + workflow runtime, Bremen workflow/3x3 parity, job API handler, H5 layouts/sample metadata/preflight, requirements API, FastAPI jobs/report parity, model package standard, import identity) | 809 passed, 3 skipped |
| `./venv/bin/python -m pytest -q` (full suite) | 4329 passed, 11 skipped (exit 0) |
| `git diff --check` | pass (exit 0) |
| `./venv/bin/ruff check` (all new/changed files) | All checks passed (new/changed files) |

## 9. Safety Checks

- `git diff` grep for secrets/forbidden patterns (AKIA, SECRET_ACCESS_KEY,
  dkr.ecr, `s3://`, `Nova_`, `/Users/`, `/home/`, private key headers): none
  introduced.
- No supplied H5 binaries, no patient datasets, no joblib artifacts added.
- No new endpoints; no endpoint path changes; no auth/requirements/legacy
  payload changes.
- No probabilities/thresholds altered; no model coefficients/artifacts changed.
- No clinical diagnosis wording introduced.
- `eoscan_version` is never promoted from `producer_version` (verified by
  `test_bremen_eoscan_version_not_promoted_from_producer_version` and
  `test_aramina_eoscan_version_not_promoted_from_producer_version`); null is
  the correct representation when provenance is unknown.
- API/runner contains no model-specific H5 metadata parsing (verified by
  `test_package_parsers_are_model_owned_not_api` and
  `test_mapper_consumes_only_normalized_names`).

## 10. Boundaries Preserved

- Only PLAN.md-allowed paths changed (source under `src/bremen/api`,
  `src/bremen/model_runtime.py`, `src/bremen/model_packages/*`, tests,
  `.project-memory/pr/0159-*`).
- `agents/`, `docs/`, `config/`, `infra/`, CI, Docker, dependencies, training,
  ADRs, ROADMAP untouched.
- Pre-existing untracked `alexey-smoke-pack-0157/` and `results/` directories
  and the pre-existing `agents/coder.yml` modification were left untouched.
- No git mutation commands run; no commit made.

## 11. Commit Readiness

ready for commit (implementation complete; no commit performed by the coder).

## 12. Recommended Next Action

proceed to precommit review.
