# PR0159 — Standard Model Result Metadata Completion

## Scope

Populate the currently-empty Standard Model Result v1 fields for both Bremen and
Aramina from authoritative existing data:

* `patient_age`
* `scan_date_time`
* `operator_id`
* `hardware_version`
* `eoscan_version`
* `model_metrics.sensitivity`
* `model_metrics.specificity`

No contract redesign, no model-science change, no fallback-value invention, no
new endpoints, no legacy-payload changes.

## Architecture (corrected)

```
model-specific parser/preprocessing
→ model-package adapter (Bremen / Aramina)
→ common normalized metadata contract (bremen.model_runtime)
→ ModelRuntime transport (RuntimePrediction)
→ Standard Result mapper
```

The platform never parses model-specific H5 metadata, artifact internals,
preprocessing dataframe columns, or joblib structure.  Each model package owns
the interpretation of its own container/artifact metadata and produces the same
normalized contract.

## 1. Common normalized contract

Defined in `bremen/model_runtime.py` (transport-neutral dataclasses, no H5
knowledge):

* `SourceMetadata` — `patient_age`, `scan_date_time`, `operator_id`,
  `hardware_version`, `eoscan_version`
* `ModelMetadata` — `model_method`
* `ModelMetrics` — `sensitivity`, `specificity`

Carried on `RuntimePrediction` and projected into the workflow payload by each
provider under the same normalized keys.  The mapper consumes only these
normalized names.

## 2. Bremen adapter (`bremen_v01/source_metadata.py`)

Container sources (Bremen xrd-session layout):

| Canonical field | Source | Rule |
| --- | --- | --- |
| `patient_age` | `/session/sample.attrs["age"]` | Numeric preserved (int/float) |
| `scan_date_time` | `/session.attrs["started_at"]` | Raw string; mapper normalizes (never invents tz; preserves offset; strips fractional seconds) |
| `operator_id` | `/session.attrs["operator_username"]` | Verbatim |
| `hardware_version` | `/session/sets/<set>/metadata` JSON `backfill_provenance.human1_version` | Consensus: exactly one unique non-empty -> it; none -> `""`; conflicting -> `""` |
| `eoscan_version` | (none) | No authoritative package-owned Eoscan version source exists.  `producer_version` is omniscan-backfill provenance and is NOT mapped; `None` is returned (never a promoted alias) |

Artifact sources (the ACTIVE `0.2.0-paper-reference` package):

* `model_definition.architecture` -> `model_metadata.model_method`
* `final_fit_training_metrics.sensitivity/specificity` -> `model_metrics.*`
  (the exact active package's own values; nothing copied from the previously
  inspected `0.2.0-research` artifact; absent -> `None`)

## 3. Aramina adapter (`aramina_v0213/source_metadata.py`)

Container sources (Aramina xrd-session layout): same canonical mapping as
Bremen.  `patient_age` prefers the model-owned preprocessing frame age
(`age_available`) with the container attribute as fallback.

Artifact sources (the ACTIVE selected artifact):

* artifact top-level `model_type` -> `model_metadata.model_method`
* `model_performance.held_out_metrics.sensitivity.mean` /
  `model_performance.held_out_metrics.specificity.mean` -> `model_metrics.*`
  (held-out evaluation of the exact active artifact; nothing hardcoded from
  another version such as 0.2.12)

## 4. Platform responsibilities (transport only)

* `bremen/model_runtime.py` — normalized contract types + `RuntimePrediction`
  fields (transport-neutral).
* `workflow_orchestrator.py` — passes the platform-staged `h5_path` to both
  providers (documented `ModelInput.container_path` bridge).
* `workflow_bremen.py` / `workflow_aramina.py` — project the normalized
  contract verbatim into the workflow payload (translation only; no
  workflow-specific `if workflow == ...` branches for generic metadata).
* `job_api_handler.py` — unchanged for metadata (mapper context stays
  request-metadata only).
* `model_result_mapper.py` — normalized runtime result -> Standard Model
  Result only.  Reads `source_metadata` / `model_metadata` / `model_metrics`
  from the result summary; model_method falls back to the documented
  model_method==model_version rule when the package provides none.

## 5. Unchanged behavior

* PR0158a: `standard_result.report_id`/`created_at` still come from stored
  `job.reports[workflow_id]`; repeated GETs stay stable.
* Existing mappings (`analysis_author`, `prediction_comment`, `patient_id`,
  `model_name`, `model_version`, `threshold_value`, `risk_probability`,
  `target_class_risk_level`, `specific_output`) unchanged.
* Probabilities and thresholds untouched.
* Legacy report envelopes/payloads, endpoint paths, auth, jobs, requirements,
  source/model IDs, discovery, availability semantics unchanged.
* `_report_job_context` key set unchanged.

## 6. Files

### New

* `src/bremen/model_packages/bremen_v01/source_metadata.py`
* `src/bremen/model_packages/aramina_v0213/source_metadata.py`
* `tests/test_bremen_package_metadata_adapters_pr0159.py`
* `tests/test_bremen_standard_result_metadata_pr0159.py`

### Modified

* `src/bremen/model_runtime.py` — `SourceMetadata` / `ModelMetadata` /
  `ModelMetrics` + `RuntimePrediction` fields
* `src/bremen/api/workflow_orchestrator.py` — pass `h5_path` to both providers
* `src/bremen/api/workflow_bremen.py` — `execute(h5_path=...)`, project
  normalized contract
* `src/bremen/api/workflow_aramina.py` — project normalized contract
* `src/bremen/model_packages/bremen_v01/runtime.py` — attach normalized
  contract to runtime result
* `src/bremen/model_packages/aramina_v0213/runtime.py` — attach normalized
  contract to runtime result
* `src/bremen/model_packages/aramina_v0213/inference.py` — return normalized
  contract alongside the model-native report
* `src/bremen/api/model_result_mapper.py` — consume normalized contract;
  `_clean_age` / `_clean_metrics` helpers
* `tests/test_bremen_model_runtime_contract_v1.py` — delegation fakes updated
* `tests/test_aramina_workflow_runtime.py` — payload key-set assertions updated

## 7. Tests

* Package-adapter tests: each package maps its own container/artifact
  representation into the SAME canonical contract; patient_age / scan_date_time
  (naive + offset) / operator_id / hardware_version (single/repeated/missing/
  conflicting) / eoscan_version (not schema_version); model_method; metrics
  source-to-canonical equality; absence -> `None`; API/mapper has no
  model-specific field names.
* Integration (Bremen + Aramina): fixture H5 -> job -> standard_result receives
  the five metadata fields; metrics equality with the runtime result;
  PR0158a repeated-GET stability retained.

## 8. Validation

1. Focused new tests.
2. Relevant existing suites (standard result v1, PR0158a hardening, Bremen
   workflow/3x3 parity, ModelRuntime contract v1, Bremen v0.1 package, Aramina
   v0.2.13 package + workflow runtime, H5 layouts/sample metadata/preflight,
   job API handler, requirements API, FastAPI jobs/report parity).
3. `python -m compileall src`
4. Full `pytest`
5. `git diff --check`
6. `ruff` on changed files (pre-existing findings in untouched test functions
   are reported separately).

No commit; no registry push; no secrets; no supplied H5 binaries added.
