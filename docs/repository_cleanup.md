# Repository Cleanup: Aramis to Bremen Identity Migration

## Status

This document tracks the progress of migrating the repository identity from Aramis to Bremen. The repository now uses `bremen` as the primary package name across source code, tests, configs, examples, and documentation. Aramis references that remain are either:

- **Historical/source-material**: Config audit artifacts, dataset metadata, and documentation that document the original Aramis dataset
- **Inherited infrastructure**: `packaging/eosproduct_bundle/` and `environment.yml` which reference the external `XRD-preprocessing` dependency

## Completed (PR 0002 — Identity Surfaces)

| Item | Status | Details |
|------|--------|---------|
| README.md | ✅ Done | Primary identity changed to Bremen; Aramis acknowledged as source material |
| AGENTS.md | ✅ Done | Title and primary context changed to Bremen; Aramis retained as historical context |
| pyproject.toml description | ✅ Done | Description updated to Bremen; `name` and entrypoints preserved |
| docs/repository_cleanup.md | ✅ Done | This file — documents cleanup status and deferred items |

## Completed (PR 0003 — Full Alignment)

| Item | Status | Details |
|------|--------|---------|
| Source package directory | ✅ Done | `src/aramis/` → `src/bremen/` |
| Package `__init__.py` | ✅ Done | Docstring updated to Bremen; exports use `Bremen*` class names |
| Package `__main__.py` | ✅ Done | `prog="aramis"` → `prog="bremen"` |
| pyproject.toml `name` | ✅ Done | `"aramis"` → `"bremen"` |
| pyproject.toml `[project.scripts]` | ✅ Done | `aramis = "aramis.__main__:main"` → `bremen = "bremen.__main__:main"` |
| pyproject.toml `packages` | ✅ Done | `["src/aramis"]` → `["src/bremen"]` |
| Class: `AramisOneToManyPreprocessingPipeline` | ✅ Done | Renamed to `BremenOneToManyPreprocessingPipeline` |
| Class: `AramisOneToOnePreprocessingPipeline` | ✅ Done | Renamed to `BremenOneToOnePreprocessingPipeline` |
| Class: `AramisPreprocessingPipeline` | ✅ Done | Renamed to `BremenPreprocessingPipeline` |
| Module: `pipelines.py` | ✅ Done | Internal references updated to Bremen |
| Module: `mlflow_tracking.py` | ✅ Done | Internal references updated to Bremen; env var `ARAMIS_LOG_MLFLOW_MODEL` → `BREMEN_LOG_MLFLOW_MODEL` |
| Module: `modeling.py` | ✅ Done | Docstrings and internal references updated to Bremen |
| Synthetic H5 fixture | ✅ Done | `tests/synthetic_aramis_h5.py` → `tests/synthetic_bremen_h5.py`; content references updated |
| Preprocessing test (one-to-one) | ✅ Done | Renamed and imports updated to `bremen.pipelines.BremenOneToOnePreprocessingPipeline` |
| Preprocessing test (one-to-many) | ✅ Done | Renamed and imports updated to `bremen.pipelines.BremenOneToManyPreprocessingPipeline` |
| Pipeline config test | ✅ Done | Renamed and imports updated to `bremen` |
| MLflow tracking test | ✅ Done | Renamed and imports updated to `bremen`; env var updated |
| Modeling test | ✅ Done | Renamed and imports updated to `bremen.modeling` |
| Real H5 subset test | ✅ Done | Renamed and config path updated to `bremen_*` YAML |
| CLI/module execution | ✅ Done | CLI entrypoint renamed; `python -m bremen` works |
| Config YAML filenames | ✅ Done | `config/preprocessing/aramis_*.yaml` → `config/preprocessing/bremen_*.yaml` |
| Config YAML content | ✅ Done | `product: Aramis` → `product: Bremen`; `aramis_preprocessing:` → `bremen_preprocessing:` |
| Config YAML `extends` chain | ✅ Done | Minimal YAMLs now extend `bremen_*` YAMLs |
| Import identity test | ✅ Done | New test `tests/test_bremen_import_identity.py` verifies `bremen` imports correctly |
| README.md CLI/module references | ✅ Done | `python -m aramis` → `python -m bremen`; code references updated |
| AGENTS.md code references | ✅ Done | `src/aramis` → `src/bremen`; historical context updated |
| README.md test/config references | ✅ Done | Updated to `bremen_*` filenames and `Bremen*` class names |

## Completed (PR 0011A — Identity Architecture Baseline)

| Item | Status | Details |
|------|--------|---------|
| ADR-0001 (Bremen product identity) | ✅ Done | PR 0011A. Product identity ADR with clinical question, classification task, 7 feature families, Aramis contrast. |
| ADR-0002 (Twin product separation) | ✅ Done | PR 0011A. Permanent separation from Aramis; XRD-preprocessing as only shared surface. |
| ROADMAP.md (root-level) | ✅ Done | PR 0011A. Product Track roadmap with 12 sequenced items. |
| docs/architecture.md | ✅ Done | PR 0011A. Architecture baseline with core chain and 11 safety invariants. |

## Completed (PR 0011B — Identity Documentation Cascade)

| Item | Status | Details |
|------|--------|---------|
| README.md identity rewrite | ✅ Done | PR 0011B. Product description aligned to ADR-0001: MRI-continuation clinical question, NORMAL vs BENIGN+CANCER, 7 Bremen feature families. |
| docs/roadmap.md stub | ✅ Done | PR 0011B. Replaced with redirect stub pointing to root ROADMAP.md. |
| docs/machine_learning_concept.md rewrite | ✅ Done | PR 0011B. Title, clinical workflow, modeling goal, and feature families aligned to ADR-0001. |
| docs/repository_cleanup.md update | ✅ Done | PR 0011B. ADR-0011A/B rows added; stale Future PR Sequencing table replaced. |

## Historical / Source-Material References (May Remain)

These files document the original Aramis dataset and product metadata. They are valid as source-material documentation and may remain with current content:

- `config/aramis_preprocessing_v0_1_config.json` — audit artifact
- `config/aramis_product_versioning.json` — product versioning
- `config/human1_diagnoses_metadata_h5_audit.json` — H5 audit
- `config/human1_diagnoses_metadata.json` — clinical metadata
- `config/human1_diagnoses_metadata_h5_mismatches.csv` — mismatch audit
- `config/README.md` — config documentation (references Aramis)
- `docs/product_development_rules.md` — shared development rules
- `docs/data_preprocessing.md` — preprocessing documentation
- `docs/machine_learning_concept.md` — ML concept doc (now identity-aligned)
- `docs/mlflow.md` — MLflow tracking doc
- `docs/agbh_quality_exclusions.md` — quality exclusion doc
- `docs/eosproduct_environment.md` — environment doc
- `packaging/eosproduct_bundle/` — packaging layer
- `requirements.txt` — legacy dependency wiring
- `environment.yml` — symlink to external XRD-preprocessing dependency
- `tests/data/aramis_real_h5_subset_20260128_5_patients.h5` — H5 data fixture (filename unchanged)

## What This PR (PR 0003) Changed

- **Package rename**: `src/aramis/` → `src/bremen/` (directory renamed; all imports updated)
- **Class rename**: `Aramis*` → `Bremen*` (three pipeline classes)
- **Config rename**: `config/preprocessing/aramis_*.yaml` → `bremen_*.yaml` (filenames and content)
- **Test rename**: Seven test files renamed; imports and content updated
- **CLI/module entrypoint**: `python -m aramis` → `python -m bremen`; `[project.scripts]` entrypoint renamed
- **pyproject.toml**: `name`, `packages`, `[project.scripts]` updated to `bremen`
- **MLflow env var**: `ARAMIS_LOG_MLFLOW_MODEL` → `BREMEN_LOG_MLFLOW_MODEL`
- **New identity test**: `tests/test_bremen_import_identity.py`
- **README.md**: CLI, code, and test references updated
- **AGENTS.md**: Historical context updated; code references updated
- **docs/repository_cleanup.md**: Updated to reflect completion

## What PR 0003 Does Not Change

- No ML logic changes
- No preprocessing semantic changes
- No H5 reader behavior changes
- No joblib/model behavior changes
- No training logic changes
- No API/FastAPI implementation
- No Docker/CI work
- No dependency changes
- No H5/HDF5 file modifications

## Future PR Sequencing

The authoritative Bremen development roadmap is now maintained in [ROADMAP.md](../ROADMAP.md) (repository root). This file retains only the completed cleanup items above.
