# PR 0003 — Full Aramina to Bremen Alignment Plan

Author: planner
Branch: 0003-full-aramina-to-bremen-alignment

## Goal

Plan a controlled repository-wide alignment from Aramina to Bremen. This PR performs the real rename: source package path, imports, tests, configs, examples, docs, CLI surfaces, and project metadata. ML behavior, preprocessing semantics, H5 reading behavior, joblib/model behavior, training logic, and clinical claims must not change.

PR 0002 established public-surface-only cleanup. PR 0003 completes the full alignment. The single artifact from this PR is this PLAN.md. Implementation (coder) and test/policy enforcement (precommit-review) follow after plan approval.

## Core principle

No active `aramina` identity may remain in the working codebase after this PR. Historical references are allowed only in `.project-memory/` evidence artifacts or explicitly marked historical notes. No runtime behavior changes. No ML/preprocessing/H5/joblib semantics changes. No clinical safety claim changes.

## Scope and constraints

### Allowed to change (planned edits)

These files are explicitly allowed for the coder to modify. Each file's planned changes are described in the sections below.

**Source package (4 files):**
1. `src/aramina/__init__.py` — rename package docstring, top-level exports stay
2. `src/aramina/__main__.py` — rename CLI prog name, update all aramina → bremen references
3. `src/aramina/pipelines.py` — rename classes (`AraminaOneToManyPreprocessingPipeline` → `BremenOneToManyPreprocessingPipeline`, etc.), update internal references
4. `src/aramina/modeling.py` — rename all Aramina references in docstrings, comments, default values
5. `src/aramina/mlflow_tracking.py` — rename `DEFAULT_EXPERIMENT_NAME`, `build_run_name`, all Aramina string refs

**Tests (5 files + optional focused test):**
6. `tests/synthetic_aramina_h5.py` — rename module filename to `tests/synthetic_bremen_h5.py`, update all internal Aramina references to Bremen (config lookup, docstrings, comments), rename exported symbol references where used
7. `tests/test_aramina_preprocessing_one_to_one.py` — rename file to `tests/test_bremen_preprocessing_one_to_one.py`, update imports to `bremen` package, update any "aramina" references in assertions/strings (e.g., H5 filenames in test data)
8. `tests/test_aramina_preprocessing_one_to_many.py` — rename file to `tests/test_bremen_preprocessing_one_to_many.py`, same import/string updates
9. `tests/test_aramina_pipeline_config.py` — rename file to `tests/test_bremen_pipeline_config.py`, same import/string updates
10. `tests/test_mlflow_tracking.py` — rename file to `tests/test_bremen_mlflow_tracking.py`, update imports, update "Aramina" strings in assertions
11. `tests/test_modeling.py` — rename file to `tests/test_bremen_modeling.py`, update imports, update comments/docstrings
12. `tests/test_real_h5_subset_reader.py` — rename file to `tests/test_bremen_real_h5_subset_reader.py`, update imports
13. New focused test: `tests/test_bremen_import_identity.py` — verifies `import bremen` works, `bremen.__name__ == "bremen"`, `bremen.__main__.main` is callable, CLI `python -m bremen --help` produces expected output. This is mandatory.

**Project metadata:**
14. `pyproject.toml` — update `name = "bremen"`, `description` to Bremen-appropriate, update `[project.scripts]` entrypoint from `"aramina = aramina.__main__:main"` to `"bremen = bremen.__main__:main"`, update `[tool.setuptools.packages.find]` to `where = ["src"]` (no change needed if already) and confirm package discovery works with `src/bremen/`. Update any other "aramina" references.

**CLI and module execution:**
15. All shell scripts under `examples/` that call `python -m aramina` — update to `python -m bremen`
16. `examples/README.md` — update all `python -m aramina`, `cd .../Aramina`, `Aramina/` path references to `bremen`/`Bremen`

**Docs and public identity:**
17. `README.md` — full rewrite to Bremen identity; retain single sentence acknowledging Aramina as source material
18. `AGENTS.md` — convert from mixed Aramina/Bremen Codex rules to Bremen-focused (PR 0002 scope, reaffirmed here)
19. `docs/repository_cleanup.md` — update to reflect the full alignment (PR 0002 scope, updated here)

**Configs (identity references only, no semantic changes):**
20. `config/preprocessing/aramina_one_to_one_preprocessing_v0_1.yaml` — rename file to `config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml`. Update `aramina_preprocessing:` key to `bremen_preprocessing:`, `name:` field, `product:` field, `provenance.*` Aramina paths, `canonical_location:`, `used_by:`, `documentation:` references
21. `config/preprocessing/aramina_one_to_many_benign_cancer_preprocessing_v0_1.yaml` — rename file to `config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml`. Same identity updates
22. `config/preprocessing/aramina_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml` — rename file to `config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml`. Same identity updates
23. `config/preprocessing/aramina_one_to_one_minimal_v0_1.yaml` — rename file to `config/preprocessing/bremen_one_to_one_minimal_v0_1.yaml`. Same identity updates
24. `config/preprocessing/aramina_one_to_many_benign_cancer_minimal_v0_1.yaml` — rename file to `config/preprocessing/bremen_one_to_many_benign_cancer_minimal_v0_1.yaml`. Same identity updates
25. `config/preprocessing/aramina_one_to_many_benign_cancer_biopsy_minimal_v0_1.yaml` — rename file to `config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_minimal_v0_1.yaml`. Same identity updates
26. `config/README.md` — update "Aramina" → "Bremen" in identity references; preserve technical content unchanged
27. `config/aramina_preprocessing_v0_1_config.json` — update `product: "Aramina"` → `"Bremen"`, update `canonical_location` and provenance paths. This is an audit artifact; identity fields change, structural data stays.
28. `config/aramina_product_versioning.json` — update `product: "Aramina"` → `"Bremen"`, update path references
29. `config/human1_diagnoses_metadata_h5_audit.json` — update `product: "Aramina"` → `"Bremen"` if present. Structural audit data stays.

**Examples:**
30. All example `.py` files (marimo notebooks) under `examples/` — rename files from `aramina_*.py` to `bremen_*.py`. Update import statements from `from aramina` to `from bremen`. Update all "Aramina" string references (titles, markdown, docstrings, defaults). The full list is enumerated below.
31. All example shell scripts under `examples/` that reference `aramina` — rename files from `preprocess_aramina*.sh`-style names or `preprocess_*.sh` if they contain `python -m aramina`, update those calls.
32. `examples/aramina_product_notebook_helpers.py` — rename to `examples/bremen_product_notebook_helpers.py`. Update all "Aramina" references.

**Docs (identity references only):**
33. `docs/product_development_rules.md` — update active Aramina identity references to Bremen. Preserve all shared pipeline, data, and regulatory content.
34. `docs/data_preprocessing.md` — update "Aramina" → "Bremen" in identity references. Preserve all technical content.
35. `docs/machine_learning_concept.md` — same
36. `docs/mlflow.md` — same
37. `docs/agbh_quality_exclusions.md` — same
38. `docs/eosproduct_environment.md` — same
39. `docs/h5_metadata_contract.md` — same
40. `docs/api_contract.md` — same
41. `docs/model_release_package.md` — same

**Directory renames (git mv):**
42. `src/aramina/` → `src/bremen/` — move the source package directory
43. All test file renames (git mv, listed above)
44. All config file renames (git mv, listed above)
45. All example file renames (git mv, listed above)

### Forbidden to change

- **H5/HDF5 data files**: `tests/data/aramina_real_h5_subset_20260128_5_patients.h5` — must not be read, modified, or renamed. H5 internal metadata is out of scope.
- **Binary/model artifacts**: none exist; any `.joblib` output files are generated, not committed.
- **`.project-memory/` files**: these are evidence artifacts. They may reference Aramina historically. Do not modify.
- **`agents/` files**: PR 0001 domain. No changes in this PR.
- **`packaging/eosproduct_bundle/`**: all files reference the upstream `Aramina` GitHub repository as an external dependency. These are deployment scripts for the original eosproduct bundle and point to the canonical `Eos-Dx/Aramina` repo. They must not be changed in this PR — they describe the upstream, not the Bremen fork.
- **`environment.yml`**: symlink to `../XRD-preprocessing/environment.yml` (external dependency). No changes.
- **`requirements.txt`**: lists external dependencies including `-e /Users/sad/dev/Aramina[dev]`. This is legacy developer-specific wiring and must be cleaned up in a separate PR.
- **`.gitignore`**: no changes.
- **Infrastructure files**: no Docker, CI, `.github/` files exist to change.
- **Classes/functions that have `aramina` in their name but are not identity strings**: `AraminaOneToManyPreprocessingPipeline`, `AraminaOneToOnePreprocessingPipeline` — these are runtime code. They should be updated to `Bremen...` as part of the source package rename (allowed under `src/aramina/pipelines.py` above).
- **No ML logic changes**: do not modify sklearn calls, numpy operations, pandas transforms, or model training behavior.
- **No preprocessing semantic changes**: do not change integration parameters, normalization windows, SNR thresholds, profile gates, filter rules, or label mappings.
- **No H5 reader behavior changes**: do not change `H5ToDataFrameTransformer`, `H5SessionFilter`, or any xrd_preprocessing call pattern.
- **No joblib/model behavior changes**: do not change model serialization/deserialization.
- **No clinical claims**: do not introduce or modify safety/disclaimer text. Preserve existing clinical safety language.

## Exact rename strategy

### Directory rename plan

```
src/aramina/                      → src/bremen/
tests/synthetic_aramina_h5.py     → tests/synthetic_bremen_h5.py
tests/test_aramina_preprocessing_one_to_one.py   → tests/test_bremen_preprocessing_one_to_one.py
tests/test_aramina_preprocessing_one_to_many.py  → tests/test_bremen_preprocessing_one_to_many.py
tests/test_aramina_pipeline_config.py            → tests/test_bremen_pipeline_config.py
tests/test_mlflow_tracking.py                   → tests/test_bremen_mlflow_tracking.py
tests/test_modeling.py                          → tests/test_bremen_modeling.py
tests/test_real_h5_subset_reader.py             → tests/test_bremen_real_h5_subset_reader.py
config/preprocessing/aramina_one_to_one_preprocessing_v0_1.yaml                → config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml
config/preprocessing/aramina_one_to_many_benign_cancer_preprocessing_v0_1.yaml → config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml
config/preprocessing/aramina_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml → config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
config/preprocessing/aramina_one_to_one_minimal_v0_1.yaml                      → config/preprocessing/bremen_one_to_one_minimal_v0_1.yaml
config/preprocessing/aramina_one_to_many_benign_cancer_minimal_v0_1.yaml       → config/preprocessing/bremen_one_to_many_benign_cancer_minimal_v0_1.yaml
config/preprocessing/aramina_one_to_many_benign_cancer_biopsy_minimal_v0_1.yaml → config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_minimal_v0_1.yaml
examples/aramina_dataframe_one_to_one_v0_1.py                   → examples/bremen_dataframe_one_to_one_v0_1.py
examples/aramina_dataframe_one_to_many_v0_1.py                  → examples/bremen_dataframe_one_to_many_v0_1.py
examples/aramina_one_to_many_logistic_baseline_v0_1.py          → examples/bremen_one_to_many_logistic_baseline_v0_1.py
examples/aramina_one_to_many_product_model_v0_1.py              → examples/bremen_one_to_many_product_model_v0_1.py
examples/aramina_final_experimental_model_v0_1.py               → examples/bremen_final_experimental_model_v0_1.py
examples/aramina_mlflow_draft.py                                 → examples/bremen_mlflow_draft.py
examples/aramina_product_notebook_helpers.py                     → examples/bremen_product_notebook_helpers.py
examples/aramina_one_to_one_model_v0_1.py (if exists)            → examples/bremen_one_to_one_model_v0_1.py
examples/aramina_fusion_model_v0_1.py (if exists)                → examples/bremen_fusion_model_v0_1.py
```

### Import rename plan

All imports of the form `from aramina import ...` or `import aramina` or `aramina.` dotted access must become `bremen`. This applies to:

| File | Import pattern to update |
|------|-------------------------|
| `tests/test_bremen_preprocessing_one_to_one.py` | `from aramina.pipelines import AraminaOneToOnePreprocessingPipeline` → `from bremen.pipelines import AraminaOneToOnePreprocessingPipeline` → then also rename the class |
| `tests/test_bremen_preprocessing_one_to_many.py` | `from aramina.pipelines import AraminaOneToManyPreprocessingPipeline` → same |
| `tests/test_bremen_pipeline_config.py` | `from aramina.__main__ import main`, `from aramina.pipelines import ...` |
| `tests/test_bremen_mlflow_tracking.py` | `from aramina import build_run_name, dataset_fingerprint, log_product_run` |
| `tests/test_bremen_modeling.py` | `from aramina.modeling import ...` |
| `tests/test_bremen_real_h5_subset_reader.py` | No aramina import (uses xrd_preprocessing directly) |
| All `examples/bremen_*.py` | `from aramina.modeling import ...` → `from bremen.modeling import ...`; `from aramina import ...` → `from bremen import ...` |
| `examples/bremen_product_notebook_helpers.py` | Check for `from aramina` or `import aramina` |

### CLI/entrypoint plan

- `pyproject.toml`: `[project.scripts] aramina = "aramina.__main__:main"` → `bremen = "bremen.__main__:main"`
- `src/aramina/__main__.py`: `prog="aramina"` in argparse → `prog="bremen"`
- All shell scripts: `python -m aramina` → `python -m bremen`
- All config `canonical_location` paths: `Aramina/...` → `Bremen/...`
- All config `io.input_h5_path` and `io.output_joblib_path` values: path segments `Aramina` → `Bremen` if present (these are runtime paths, not identity strings — but they contain the project name in the path, which should be updated)

### Class name rename plan

In `src/bremen/pipelines.py`:
- `AraminaOneToOnePreprocessingPipeline` → `BremenOneToOnePreprocessingPipeline`
- `AraminaOneToManyPreprocessingPipeline` → `BremenOneToManyPreprocessingPipeline`

In test files that import these classes, update import names accordingly.

## Test update plan

### File renames (git mv)

7 test files renamed as listed in the directory rename plan above.

### Import updates

All `from aramina` imports in test files become `from bremen`.

### String/assertion updates

| Test file | Assertion/String changes |
|-----------|-------------------------|
| `test_bremen_preprocessing_one_to_one.py` | `"known_synthetic_aramina.h5"` → `"known_synthetic_bremen.h5"` (test-local path strings), `"aramina_one_to_one_dataframe.joblib"` → `"bremen_one_to_one_dataframe.joblib"`, `"aramina_one_to_one_preprocessing_v0_1.yaml"` → `"bremen_one_to_one_preprocessing_v0_1.yaml"` |
| `test_bremen_preprocessing_one_to_many.py` | Same pattern for all filename strings |
| `test_bremen_pipeline_config.py` | Update `"Unknown Aramina preprocessing branch"` to `"Unknown Bremen preprocessing branch"` (error message string), update all filename strings |
| `test_bremen_mlflow_tracking.py` | `build_run_name("Aramina")` → `build_run_name("Bremen")`, `"aramina_draft_"` → `"bremen_draft_"`, experiment_name `"Aramina"` → `"Bremen"`, product_name `"Aramina"` → `"Bremen"`, env var `ARAMINA_LOG_MLFLOW_MODEL` → `BREMEN_LOG_MLFLOW_MODEL` |
| `test_bremen_modeling.py` | Update all docstring/test-name references from "Aramina" to "Bremen" if present |
| `test_bremen_real_h5_subset_reader.py` | `ARAMINA_CONFIG` → `BREMEN_CONFIG`, `aramina_real_h5_subset_*` → reference to H5 file unchanged (H5 file is out of scope, but the variable name in the test changes) |

### New focused tests

**`tests/test_bremen_import_identity.py`** — mandatory new file:

```python
"""Verifies Bremen package identity after Aramina-to-Bremen alignment."""

from __future__ import annotations

import sys
from pathlib import Path


def test_bremen_package_importable():
    import bremen
    assert bremen.__name__ == "bremen"
    assert hasattr(bremen, "__version__") or True  # version is optional


def test_bremen_main_is_callable():
    from bremen.__main__ import main
    assert callable(main)


def test_bremen_pipelines_classes_available():
    from bremen.pipelines import BremenOneToManyPreprocessingPipeline
    from bremen.pipelines import BremenOneToOnePreprocessingPipeline
    assert callable(BremenOneToManyPreprocessingPipeline)
    assert callable(BremenOneToOnePreprocessingPipeline)


def test_bremen_modeling_functions_available():
    from bremen.modeling import (
        fit_repeated_one_to_many_logistic,
        load_one_to_many_dataframe,
        profile_matrix,
    )
    assert callable(fit_repeated_one_to_many_logistic)
    assert callable(load_one_to_many_dataframe)
    assert callable(profile_matrix)


def test_bremen_mlflow_exports_available():
    from bremen import DEFAULT_EXPERIMENT_NAME, build_run_name, log_product_run
    assert isinstance(DEFAULT_EXPERIMENT_NAME, str)
    assert callable(build_run_name)
    assert callable(log_product_run)


def test_old_aramina_import_raises_module_not_found():
    """The old aramina package must not be importable after the rename."""
    import importlib
    spec = importlib.util.find_spec("aramina")
    assert spec is None, "aramina package should not be findable"
```

Note: the last test (`test_old_aramina_import_raises_module_not_found`) is optional and should be included only if no compatibility shim is kept. This PLAN does not preserve an `aramina` compatibility package.

### No H5 test data modifications

The H5 test data file `tests/data/aramina_real_h5_subset_20260128_5_patients.h5` must NOT be read, modified, or renamed. The test `test_real_h5_subset_reader.py` reads this file by variable name — after rename, the variable `BREMEN_CONFIG` points to the renamed config path, but the H5 file path reference stays unchanged.

## Validation commands

Precommit-review must execute all validations below before approving merge. Evidence must be captured under `.project-memory/pr/0003-full-aramina-to-bremen-alignment/evidence/`.

### 1. Working tree check
```bash
git status --short
```
Must show only the planned changes. No dirty state from unrelated files.

### 2. Allowed file drift check
```bash
git diff --name-only --cached | grep -vE "^(src/bremen/|tests/test_bremen_|tests/synthetic_bremen|tests/test_bremen_import_identity|config/preprocessing/bremen_|config/README|config/aramina_preprocessing_v0_1_config|config/aramina_product_versioning|config/human1|README|AGENTS|pyproject|examples/bremen_|examples/preprocess_|docs/repository_cleanup|docs/product_development|docs/data_preprocessing|docs/machine_learning|docs/mlflow|docs/agbh_quality|docs/eosproduct|docs/h5_metadata|docs/api_contract|docs/model_release_package)" && exit 1 || echo "OK"
```

### 3. Source package path check
```bash
test -d src/bremen && echo "src/bremen exists" || echo "ERROR: src/bremen missing"
test ! -d src/aramina && echo "src/aramina removed" || echo "ERROR: src/aramina still present"
```

### 4. No active Aramina references in code
```bash
! grep -R -I -q -E "from aramina|import aramina|aramina\.|python -m aramina|src/aramina" src tests config examples docs --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" --include="*.md" --include="*.sh" 2>/dev/null
```
Must exit with code 0 (no matches found). Exclude the single line in `README.md` that acknowledges Aramina as source material.

### 5. No active Aramina identity strings in code surfaces
```bash
! grep -R -I -q -E "product: Aramina|product: \"Aramina\"|\"product\": \"Aramina\"|name: aramina|aramina_preprocessing:|prog=\"aramina\"|DEFAULT_EXPERIMENT_NAME = \"Aramina\"|ARAMINA_LOG_MLFLOW_MODEL" src tests config examples --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" --include="*.sh" 2>/dev/null
```
Must exit with code 0.

### 6. pyproject.toml package name check
```bash
grep -q '^name = "bremen"' pyproject.toml && echo "pyproject name is bremen" || echo "ERROR: pyproject name not bremen"
grep -q 'bremen = "bremen.__main__:main"' pyproject.toml && echo "entrypoint is bremen" || echo "ERROR: entrypoint not bremen"
```

### 7. CLI module execution check
```bash
grep -q 'python -m bremen' examples/preprocess_all.sh && echo "CLI updated" || echo "ERROR: CLI not updated in preprocess_all.sh"
```

### 8. .project-memory untouched
```bash
git diff --name-only --cached | grep -q "\.project-memory/" && exit 1 || echo "project-memory untouched"
```

### 9. agents/ untouched
```bash
git diff --name-only --cached | grep -q "agents/" && exit 1 || echo "agents untouched"
```

### 10. packaging/ untouched
```bash
git diff --name-only --cached | grep -q "packaging/" && exit 1 || echo "packaging untouched"
```

### 11. H5/HDF5 files not changed
```bash
git diff --name-only --cached | grep -qE "\.h5$|\.hdf5$" && exit 1 || echo "no H5 files changed"
```

### 12. Syntax validation
```bash
python -m compileall src tests 2>&1 | tail -5
```
Must show no syntax errors.

### 13. Test execution (all tests pass)
```bash
python -m pytest -q 2>&1 | tail -10
```
Must show all tests passing (or known failures explicitly documented with reasons).

### 14. Focused import identity test
```bash
python -m pytest -q tests/test_bremen_import_identity.py -v 2>&1
```
Must pass all tests.

### 15. No .DS_Store
```bash
find . -name ".DS_Store" -print | wc -l | xargs test 0 -eq || echo "WARNING: .DS_Store found"
```
Should output 0 (warning if not).

### 16. H5 test data unchanged
```bash
test -f tests/data/aramina_real_h5_subset_20260128_5_patients.h5 && echo "H5 data intact" || echo "ERROR: H5 data missing or renamed"
```

## Stop conditions

- Block if the working tree is dirty before coder begins (uncommitted changes outside allowed set).
- Block if any file outside the allowed-to-change list appears in `git diff --name-only --cached`.
- Block if `src/aramina/` still exists after rename.
- Block if any `src/` or `tests/` or `config/` or `examples/` file still contains `from aramina`, `import aramina`, `python -m aramina`, or `aramina.` as active code (excluding README.md legal acknowledgment and `.project-memory/` historical evidence).
- Block if H5/HDF5 files were modified, renamed, or read by the coder.
- Block if ML behavior, preprocessing semantics, H5 reader, joblib/model, or training logic was changed.
- Block if `packaging/` or `agents/` or `.project-memory/` files were modified.
- Block if `test_bremen_import_identity.py` is missing or failing.
- Block if `python -m compileall` fails on `src/` or `tests/`.
- Block if `python -m pytest -q` shows test failures without documented, pre-approved reasons.
- Block if Bremen safety/disclaimer language is weakened or removed.

## Plan Drift Gate requirements

Precommit-review must enforce a Plan Drift Gate. The gate checks:

1. **File drift**: only files from the allowed list (or intermediate `git mv` operations) appear in `git diff --name-only --cached`. No forbidden paths.
2. **Package-path drift**: `src/bremen/` exists; `src/aramina/` does not exist.
3. **Import drift**: all `from aramina` / `import aramina` in src/tests/config/examples/docs(selective) are replaced with `bremen`.
4. **CLI drift**: `python -m bremen` is the only module execution reference; `pyproject.toml` entrypoint is `bremen`.
5. **Test drift**: all test files renamed, imports updated, `test_bremen_import_identity.py` exists and passes.
6. **Config/example drift**: all config YAMLs and example files renamed, identity string "Aramina" → "Bremen" within them, no semantic changes.
7. **Behavior drift**: `git diff` shows only text/identity changes; no sklearn, numpy, h5py, joblib, or xrd_preprocessing call changes.
8. **ML/preprocessing/H5/joblib drift**: no changes to these call sites or parameters.
9. **Validation drift**: all 16 validation commands from this PLAN.md are run and pass.
10. **Semantic drift**: the "Aramina" → "Bremen" rename is text-only. Clinical safety language, disclaimers, and decision-support posture are unchanged.
11. **Future-scope drift**: no Docker, CI, API, FastAPI, containerization, or production deployment changes.
12. **Aramina-reference drift**: after validation command 4 and 5 pass (grep checks for active Aramina references), only `.project-memory/` historical evidence contains "Aramina" strings. README.md may contain one line acknowledging Aramina provenance.
13. **Bremen safety drift**: Bremen is not claimed to be clinically validated, to diagnose cancer, or to replace MRI/biopsy/clinician judgment.
14. **Accepted deviations**: any deviation from this PLAN.md must be documented in the precommit-review.yml with a justification and a blocker/safety assessment.
15. **Blockers**: any blocking condition found during drift gate evaluation prevents merge until resolved.

## Aramina/Bremen reference policy

- **Active code references** (imports, strings, CLI, config identity fields, class names): must be changed to "Bremen". Zero tolerance.
- **Historical evidence** (`.project-memory/`, `.git/` history): may remain unchanged. These are evidence artifacts.
- **README.md provenance**: may retain one sentence: "This repository was derived from the Aramina project."
- **Config values that are data identity, not project identity** (e.g., `product: Aramina` in a config that defines the Human-1 product metadata): change to `product: Bremen`. The Human-1 product metadata is about the data's product context, but the config is now a Bremen config.
- **H5 internal metadata**: out of scope. H5 files are not read or modified.
- **Packaging scripts** referencing the upstream `Eos-Dx/Aramina` GitHub repo: do NOT change. These scripts describe an external dependency, not the Bremen codebase.

## Behavior-preservation policy

- **Zero behavior change**: every `git diff` line that is not a text/identity string change is subject to rejection.
- **Test semantics preserved**: test assertions about dataframe values, pipeline stages, model metrics, and H5 reader output must remain identical. Only module/class names and "aramina" strings in assertions change.
- **Config semantics preserved**: no YAML key or value that affects preprocessing logic may be changed. Only `name:`, `product:`, `provenance.canonical_location`, and identity string fields change.
- **Clinical claims preserved**: all `clinical_safety_note` fields, decision-support language, and disclaimer text are unchanged.
- **Import chain preserved**: `from bremen.pipelines import BremenOneToOnePreprocessingPipeline` has the same behavior as `from aramina.pipelines import AraminaOneToOnePreprocessingPipeline` did.

## Deferred capabilities

- **Packaging scripts** (`packaging/eosproduct_bundle/`): deferred to a future PR that aligns the bundle with Bremen (requires external repo coordination).
- **`requirements.txt` cleanup**: deferred. The `-e /Users/sad/dev/Aramina[dev]` line is developer-specific and unrelated to project identity.
- **`environment.yml` sync**: deferred. It's a symlink to an external repo.
- **H5 test data rename**: `tests/data/aramina_real_h5_subset_20260128_5_patients.h5` will remain with "aramina" in the filename. H5 internal metadata is out of scope for this PR. A future PR may rename this file if safe.
- **Legacy `ARAMINA_LOG_MLFLOW_MODEL` env var**: changed to `BREMEN_LOG_MLFLOW_MODEL` in source code. Any existing user environments using the old var must update.
- **Git history rewrite**: not performed. This PR does not rebase, squash, or rewrite history. Historical commits still reference "Aramina".

## Rollback/safety strategy

If the rename breaks imports or tests unexpectedly:
1. Revert the commit: `git revert <commit-hash>`
2. Re-open PR with corrected rename scope
3. The `src/aramina/` package is removed in the rename — a rollback restores it
4. H5 data files are never touched, so they cannot be corrupted
5. Precommit-review blocks any change that does not pass all validation commands, so a broken state should never reach `main`

## Decisions summary

### Allowed files
Source: 5 files in `src/bremen/` (after git mv from `src/aramina/`)
Tests: 7 existing test files renamed + 1 new test file + `synthetic_bremen_h5.py`
Project metadata: `pyproject.toml`
Docs: `README.md`, `AGENTS.md`, `docs/repository_cleanup.md` + 8 docs files for identity-only updates
Configs: 6 preprocessing YAMLs renamed + `config/README.md` + 3 config JSONs (identity-only)
Examples: 7+ marimo notebooks renamed + `examples/README.md` + shell scripts + helpers file
CLI: all `python -m aramina` → `python -m bremen`

### Forbidden files
All `.h5`/`.hdf5` files, `tests/data/` content, `packaging/`, `agents/`, `.project-memory/`, `environment.yml`, `requirements.txt`, `.gitignore`, all binary artifacts, all infrastructure files

### Directory rename plan
`src/aramina/` → `src/bremen/` (git mv)
6 config YAML renames under `config/preprocessing/`
7 test file renames under `tests/`
7+ example file renames under `examples/`

### Import rename plan
All `from aramina` → `from bremen`
All `import aramina` → `import bremen`
All `aramina.` dotted access → `bremen.`

### CLI/entrypoint plan
`pyproject.toml` scripts entry: `aramina = "aramina.__main__:main"` → `bremen = "bremen.__main__:main"`
`__main__.py`: `prog="aramina"` → `prog="bremen"`
All shell scripts: `python -m aramina` → `python -m bremen`

### Test update plan
7 test files renamed
All imports updated from aramina to bremen
String/assertion updates for renamed filenames, error messages, MLflow attributes
New file: `tests/test_bremen_import_identity.py` with 6 focused tests

### Config/example plan
6 config YAMLs renamed, identity fields updated
3 config JSONs updated (identity fields only)
7+ example notebooks renamed, all imports and identity strings updated
Shell scripts updated

### Docs/public identity plan
README.md rewritten to Bremen identity
AGENTS.md converted to Bremen focus
docs/repository_cleanup.md updated
8 docs files receive identity-only updates (no technical content changes)

### Validation commands
16 validation commands covering file drift, package path, imports, pyproject, CLI, test execution, import identity, H5 safety, syntax checks, and behavior preservation

### Stop conditions
16 block conditions covering dirty tree, drift, source path, active Aramina references, H5 safety, ML behavior, missing tests, syntax errors, and safety language

### Plan Drift Gate requirements
15 drift-check criteria enforced by precommit-review

### Deferred capabilities
Packaging scripts, requirements.txt, environment.yml, H5 test data filename, git history rewrite

### Blockers
- None for writing this PLAN.md. Implementation blockers: `python -m compileall` must pass, `python -m pytest -q` must pass, all validation commands must pass, active Aramina references in code must be zero.

### Warnings
- The H5 test data file `tests/data/aramina_real_h5_subset_20260128_5_patients.h5` retains "aramina" in its filename. This is intentional and documented as deferred.
- `packaging/eosproduct_bundle/` scripts still reference `Eos-Dx/Aramina` external repo. Not changed in this PR.
- `requirements.txt` still references `/Users/sad/dev/Aramina[dev]`. Deferred.
- Config `filters.quality_exclusions.reason_doc` fields currently point to `Aramina/docs/agbh_quality_exclusions.md`. These are provenance strings pointing to the historical docs location. They should be updated to `Bremen/docs/agbh_quality_exclusions.md` since the docs have been renamed.

## Files read
- `.project-memory/project_contract.yml`
- `.project-memory/memory_index.yml`
- `.project-memory/pr/0001-bremen-agent-workflow/PLAN.md`
- `.project-memory/pr/0001-bremen-agent-workflow/reviews/plan-review.yml`
- `.project-memory/pr/0001-bremen-agent-workflow/reviews/precommit-review.yml`
- `.project-memory/pr/0002-aramina-to-bremen-cleanup/PLAN.md`
- `.project-memory/pr/0002-aramina-to-bremen-cleanup/reviews/plan-review.yml`
- `README.md`
- `AGENTS.md`
- `pyproject.toml`
- `src/aramina/__init__.py`
- `src/aramina/__main__.py`
- `src/aramina/pipelines.py`
- `src/aramina/modeling.py`
- `src/aramina/mlflow_tracking.py`
- `tests/synthetic_aramina_h5.py`
- `tests/test_aramina_preprocessing_one_to_one.py`
- `tests/test_aramina_preprocessing_one_to_many.py`
- `tests/test_aramina_pipeline_config.py`
- `tests/test_mlflow_tracking.py`
- `tests/test_modeling.py`
- `tests/test_real_h5_subset_reader.py`
- `config/README.md`
- `config/preprocessing/aramina_one_to_one_preprocessing_v0_1.yaml`
- `examples/README.md`
- `examples/aramina_dataframe_one_to_one_v0_1.py`
- `examples/aramina_one_to_many_logistic_baseline_v0_1.py`
- `examples/aramina_mlflow_draft.py`
- `examples/preprocess_one_to_one.sh`
- `examples/preprocess_all.sh`
- `packaging/eosproduct_bundle/environment.yml`
- `packaging/eosproduct_bundle/scripts/install.sh`
- `packaging/eosproduct_bundle/scripts/run_aramina_notebooks.sh`
- `packaging/eosproduct_bundle/scripts/run_tests.sh`

## Files written
- `.project-memory/pr/0003-full-aramina-to-bremen-alignment/PLAN.md` (this file)

## Files intentionally ignored
- `tests/data/aramina_real_h5_subset_20260128_5_patients.h5` — H5 data, not modified
- `packaging/eosproduct_bundle/` — external deployment scripts, deferred
- `agents/` — PR 0001 domain
- `.project-memory/` — evidence artifacts with historical Aramina references
- `environment.yml` — symlink to external repo
- `requirements.txt` — legacy developer wiring, deferred
- `.gitignore` — no changes
- All binary, image, or non-source files

## Boundary confirmations

- confirm: only PLAN.md written: yes
- confirm: no code written: yes
- confirm: no tests written: yes
- confirm: no review artifact written: yes
- confirm: no runtime behavior changed: yes
- confirm: no ML/preprocessing/H5/joblib behavior change planned: yes
- confirm: tests are mandatory in implementation and precommit-review: yes
- confirm: no files over 5000 lines read or planned for editing: yes
- confirm: no H5/HDF5 files read or planned for editing: yes
- confirm: no git mutation commands run: yes
- confirm: Plan Drift Gate required: yes
- confirm: clinical safety/disclaimer language preserved: yes
- confirm: zero active Aramina references in code after implementation: yes
- confirm: packaging/scripts left untouched (upstream external dependency): yes

## Final output

PLAN written: yes
