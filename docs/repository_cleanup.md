# Repository Cleanup: Aramis to Bremen Identity Migration

## Status

This document tracks the progress of migrating the repository identity from Aramis to Bremen. The repository currently inherits source code, tests, configs, documentation, and packaging from the Aramis project. Identity cleanup is being performed incrementally across multiple PRs.

## Completed (PR 0002)

| Item | Status | Details |
|------|--------|---------|
| README.md | ✅ Done | Primary identity changed to Bremen; Aramis acknowledged as source material |
| AGENTS.md | ✅ Done | Title and primary context changed to Bremen; Aramis retained as historical context |
| pyproject.toml description | ✅ Done | Description updated to Bremen; `name` and entrypoints preserved |
| docs/repository_cleanup.md | ✅ Done | This file — documents cleanup status and deferred items |

## Deferred — Inherited Code / Package Path

These items retain the `aramis` package name and will be renamed in a future refactor PR after CI, tests, and build infrastructure are in place.

| Item | Current Name | Target Name | Dependency |
|------|-------------|-------------|------------|
| Source package directory | `src/aramis/` | `src/bremen/` | Requires coordinated rename of imports, tests, configs, examples, and entrypoints |
| Package `__init__.py` | `"""Aramis product draft package."""` | `"""Bremen product draft."""` | Tied to package rename |
| Package `__main__.py` | `prog="aramis"` | `prog="bremen"` | Tied to package rename |
| pyproject.toml `name` | `"aramis"` | `"bremen"` | Changing would break imports; deferred |
| pyproject.toml `[project.scripts]` | `aramis = "aramis.__main__:main"` | `bremen = "bremen.__main__:main"` | Tied to package rename |
| pyproject.toml `packages` | `["src/aramis"]` | `["src/bremen"]` | Tied to package rename |
| Class: `AramisOneToManyPreprocessingPipeline` | `AramisOneToManyPreprocessingPipeline` | `BremenOneToManyPreprocessingPipeline` | Requires coordinated rename |
| Class: `AramisOneToOnePreprocessingPipeline` | `AramisOneToOnePreprocessingPipeline` | `BremenOneToOnePreprocessingPipeline` | Requires coordinated rename |
| Module: `src/aramis/pipelines.py` | `pipelines` | `pipelines` (content rename) | Tied to class rename |
| Module: `src/aramis/mlflow_tracking.py` | Internal Aramis references | Internal Bremen references | Tied to package rename |
| Module: `src/aramis/modeling.py` | Internal Aramis references | Internal Bremen references | Tied to package rename |

## Deferred — Tests

| Item | Current Name | Target Name | Notes |
|------|-------------|-------------|-------|
| Synthetic H5 fixture | `tests/synthetic_aramis_h5.py` | `tests/synthetic_bremen_h5.py` | Contains Aramis-specific names; rename deferred |
| Preprocessing test (one-to-one) | `tests/test_aramis_preprocessing_one_to_one.py` | `tests/test_bremen_preprocessing_one_to_one.py` | Content references Aramis; rename deferred |
| Preprocessing test (one-to-many) | `tests/test_aramis_preprocessing_one_to_many.py` | `tests/test_bremen_preprocessing_one_to_many.py` | Content references Aramis; rename deferred |
| Pipeline config test | `tests/test_aramis_pipeline_config.py` | `tests/test_bremen_pipeline_config.py` | Content references Aramis; rename deferred |
| MLflow tracking test | `tests/test_mlflow_tracking.py` | `tests/test_bremen_mlflow_tracking.py` | Content references Aramis; rename deferred |
| Modeling test | `tests/test_modeling.py` | `tests/test_bremen_modeling.py` | Content references Aramis; rename deferred |
| Real H5 subset test | `tests/test_real_h5_subset_reader.py` | `tests/test_bremen_real_h5_subset_reader.py` | Content references Aramis; rename deferred |
| H5 data fixture | `tests/data/aramis_real_h5_subset_20260128_5_patients.h5` | `tests/data/bremen_real_h5_subset_20260128_5_patients.h5` | Filename contains "aramis"; rename deferred |

## Deferred — Examples

| Item | Current Name | Notes |
|------|-------------|-------|
| DataFrame notebook (one-to-one) | `examples/aramis_dataframe_one_to_one_v0_1.py` | Content references Aramis |
| DataFrame notebook (one-to-many) | `examples/aramis_dataframe_one_to_many_v0_1.py` | Content references Aramis |
| Experimental model notebook | `examples/aramis_final_experimental_model_v0_1.py` | Content references Aramis |
| MLflow draft notebook | `examples/aramis_mlflow_draft.py` | Content references Aramis |
| Logistic baseline notebook | `examples/aramis_one_to_many_logistic_baseline_v0_1.py` | Content references Aramis |
| Product model notebook | `examples/aramis_one_to_many_product_model_v0_1.py` | Content references Aramis |
| Notebook helpers | `examples/aramis_product_notebook_helpers.py` | Content references Aramis |
| Preprocessing shell scripts | `examples/preprocess_*.sh` | Content references Aramis |

## Deferred — Configs

| Item | Notes |
|------|-------|
| `config/aramis_preprocessing_v0_1_config.json` | Audit artifact; content references Aramis |
| `config/aramis_product_versioning.json` | Versioning metadata; content references Aramis |
| `config/human1_diagnoses_metadata_h5_audit.json` | H5 audit artifact; content references "product": "Aramis" |
| `config/human1_diagnoses_metadata.json` | Clinical metadata; embeds Aramis references |
| `config/human1_diagnoses_metadata_h5_mismatches.csv` | Mismatch audit; embeds Aramis references |
| `config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml` | Preprocessing config; references "product: Aramis" |
| `config/preprocessing/aramis_one_to_one_minimal_v0_1.yaml` | Preprocessing config; references "product: Aramis" |
| `config/preprocessing/aramis_one_to_many_benign_cancer_preprocessing_v0_1.yaml` | Preprocessing config; references "product: Aramis" |
| `config/preprocessing/aramis_one_to_many_benign_cancer_minimal_v0_1.yaml` | Preprocessing config; references "product: Aramis" |
| `config/preprocessing/aramis_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml` | Preprocessing config; references "product: Aramis" |
| `config/preprocessing/aramis_one_to_many_benign_cancer_biopsy_minimal_v0_1.yaml` | Preprocessing config; references "product: Aramis" |
| `config/README.md` | Documents "Aramis Human-1 Product Metadata" |

## Deferred — Packaging

| Item | Notes |
|------|-------|
| `packaging/eosproduct_bundle/` | All scripts/references to "Aramis" as external repository; valid as packaging layer |

## Deferred — Documentation Content

| Item | Notes |
|------|-------|
| `docs/product_development_rules.md` | Contains both Aramis and Bremen product sections |
| `docs/data_preprocessing.md` | Content references Aramis preprocessing pipeline |
| `docs/machine_learning_concept.md` | Content references Aramis ML concept |
| `docs/mlflow.md` | Content references Aramis MLflow tracking |
| `docs/agbh_quality_exclusions.md` | Content references Aramis quality exclusions |
| `docs/eosproduct_environment.md` | Content references Aramis environment setup |

## Historical / Source-Material References (May Remain)

These files document the original Aramis dataset and product metadata. They are valid as source-material documentation and may remain with current content:

- `config/aramis_preprocessing_v0_1_config.json` — audit artifact
- `config/aramis_product_versioning.json` — product versioning
- `config/human1_diagnoses_metadata_h5_audit.json` — H5 audit
- `config/human1_diagnoses_metadata.json` — clinical metadata
- `config/human1_diagnoses_metadata_h5_mismatches.csv` — mismatch audit
- `config/preprocessing/*.yaml` — preprocessing configs
- `config/README.md` — config documentation
- `docs/product_development_rules.md` — shared development rules
- `docs/data_preprocessing.md` — preprocessing documentation
- `docs/machine_learning_concept.md` — ML concept doc
- `docs/mlflow.md` — MLflow tracking doc
- `docs/agbh_quality_exclusions.md` — quality exclusion doc
- `docs/eosproduct_environment.md` — environment doc
- `packaging/eosproduct_bundle/` — packaging layer
- `requirements.txt` — legacy dependency wiring (references external Aramis checkout)
- `environment.yml` — symlink to external XRD-preprocessing dependency

## What This PR Does Not Change

- No runtime behavior changes (ML, preprocessing, H5 reading, inference, API)
- No source package rename (`src/aramis/` remains unchanged)
- No import, entrypoint, or CLI rename
- No test file or content changes
- No example file or content changes
- No config file or content changes
- No documentation rewrite beyond this file
- No automated search-and-replace of project names
- No Docker, CI, or infrastructure changes
