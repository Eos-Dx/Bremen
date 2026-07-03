# PR 0013 — Plan Model Package Contract and Local Validation Helpers

Author: plan
Mode: planning only
Branch: 0013-model-package-contract

## Objective

Create the local model package contract and validation helpers that future API/runtime work can call before any model loading or inference. This PR implements the contract defined by ADR-0007 (Model Artifact Lifecycle) without deserializing joblib, without importing joblib or pickle, and without creating real model artifacts.

## Context

PR 0012 introduced ADR-0007 and closed G-API-1, G-API-2, and G-INFRA-1. ADR-0007 establishes that:
- joblib is built offline only.
- Runtime service must not train.
- Runtime service must load only checksum-verified model packages.
- Initial artifact store is S3 versioned bucket.
- `joblib.load()` uses pickle deserialization and must be treated as a security boundary.

PR 0013 creates the local validation foundation (manifest schema, checksum verification, path safety checks) that future API/runtime PRs (PR 0014, PR 0016) will use. This PR does not call `joblib.load()`, does not create real model artifacts, and does not implement API routes or IaC.

## Exact allowed implementation files

The coder may create exactly these files:

1. **`src/bremen/model_package.py`** — NEW. Model package manifest contract and validation helpers.
2. **`tests/test_bremen_model_package.py`** — NEW. Tests for the model package module.

Optional only if strongly justified:
3. **`src/bremen/__init__.py`** — MODIFY only if an import-level export is needed. Prefer explicit imports over __init__.py changes.

## Exact forbidden files

- `ROADMAP.md`, `docs/architecture.md`, `docs/adr/**`, `docs/api_contract.md`
- `README.md`, `docs/**`
- `.github/**`, `Dockerfile`, `.dockerignore`, `requirements.txt`, `pyproject.toml`
- `sonar-project.properties`, `environment.yml`, `Makefile`
- `config/**`, `examples/**`, `tests/data/**`
- Any H5/HDF5 files, any model/joblib/pkl/npy/npz artifacts
- Terraform/CDK/CloudFormation/IaC files
- `agents/**`

## Required reads (completed for this PLAN.md)

- `docs/adr/0007-model-artifact-lifecycle.md` — model package contract requirements
- `.project-memory/project_contract.yml` — safety invariants, mandatory response fields
- `src/bremen/config.py` — existing pattern for import-safe module design, exception hierarchy
- `tests/test_bremen_config_loading.py` — existing test patterns
- `AGENTS.md` — agent role definitions
- `ROADMAP.md` — current roadmap state
- `docs/architecture.md` — current architecture baseline

## Implementation phase assignment

- **Agent**: coder
- **Mode**: implementation

**Reason**: These are ordinary source and test files (`src/bremen/**`, `tests/**`), not architect-reserved paths.

## Model package contract

### Manifest schema

Define a local manifest contract in Python. The manifest is a JSON file that describes the model package contents and metadata.

Recommended fields:

| Field | Type | Description |
|-------|------|-------------|
| `model_version` | str | Version string for the model |
| `model_checksum` | str | SHA-256 hex digest of the model artifact file |
| `model_filename` | str | Filename of the model artifact within the package directory |
| `feature_schema_version` | str | Version string for the feature schema |
| `threshold_version` | str | Version string for the decision threshold |
| `threshold_value` | float | The decision threshold value |
| `qc_criteria_version` | str | Version string for the QC criteria |
| `training_config_ref` | str | Reference to the training config used |
| `created_at` | str | ISO-8601 timestamp |
| `artifact_type` | str | Expected value: `"bremen.joblib.model_package"` |

The manifest may include additional safe metadata but must not require clinical patient data.

### Local package layout

A simple local package directory contract for development/testing:

```
model_package/
  manifest.json       # JSON file with the manifest schema
  <model_filename>    # Model artifact file (named by manifest.model_filename)
```

Tests may create temporary fake bytes files with a `.joblib` extension only inside `tmp_path`. No repository model artifact may be added.

### Public API

Functions to implement:

```python
def read_model_manifest(path: str | Path) -> dict[str, Any]:
    """Read and parse a manifest.json file from the given path.

    Returns the parsed manifest as a dict.
    Raises ModelPackageNotFoundError if the file does not exist.
    Raises ModelPackageManifestError if the file is not valid JSON.
    """

def compute_sha256(path: str | Path) -> str:
    """Compute the SHA-256 hex digest of a file.

    Returns the hex digest string.
    Raises ModelPackageNotFoundError if the file does not exist.
    """

def validate_model_manifest(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a manifest dict against the required schema.

    Returns the validated manifest dict.
    Raises ModelPackageManifestError if required fields are missing or
    have invalid types.
    """

def validate_model_package(package_dir: str | Path) -> dict[str, Any]:
    """Validate the entire model package directory.

    Checks:
    - manifest.json exists and is valid
    - All required manifest fields are present
    - model_filename does not escape package_dir (path traversal prevention)
    - Model artifact file exists
    - Computed SHA-256 matches manifest.model_checksum

    Returns the validated manifest dict.
    Raises ModelPackageNotFoundError, ModelPackageManifestError,
    ModelPackageChecksumError, or ModelPackageSecurityError.
    """

def summarize_model_package(package_dir: str | Path) -> dict[str, str | float | None]:
    """Return a safe summary of the model package.

    Returns a dict with: model_version, model_checksum (truncated),
    feature_schema_version, threshold_version, threshold_value,
    qc_criteria_version, artifact_type.

    Does NOT return the model artifact file contents or any clinical data.
    """
```

### Exception hierarchy

```python
class ModelPackageError(Exception):
    """Base exception for model package errors."""

class ModelPackageNotFoundError(ModelPackageError):
    """Model package or manifest file not found."""

class ModelPackageManifestError(ModelPackageError):
    """Manifest is missing, invalid, or has missing required fields."""

class ModelPackageChecksumError(ModelPackageError):
    """Computed checksum does not match manifest checksum."""

class ModelPackageSecurityError(ModelPackageError):
    """Security violation detected (e.g., path traversal)."""
```

## Validation behavior details

### Required field validation

`validate_model_manifest()` must check that these fields exist and have expected types:

- `model_version` (str, non-empty)
- `model_checksum` (str, non-empty, 64-char hex pattern)
- `model_filename` (str, non-empty)
- `feature_schema_version` (str, non-empty)
- `threshold_version` (str, non-empty)
- `threshold_value` (int or float)
- `qc_criteria_version` (str, non-empty)
- `artifact_type` (str, expected value `"bremen.joblib.model_package"`)

Fields like `training_config_ref` and `created_at` are recommended but not required for local package validation.

### Path traversal prevention

`validate_model_package()` must verify that `model_filename` resolves inside `package_dir`. Reject paths containing `..`, absolute paths, or symlinks that escape the package directory.

### Checksum verification

`validate_model_package()` must compute SHA-256 of the artifact file and compare it against `manifest.model_checksum`. A mismatch raises `ModelPackageChecksumError`.

### Fail-closed behavior

All validation functions must raise controlled exceptions on any error. No silent fallback to "valid." No default values that mask validation failures.

## Security boundaries

This PR enforces the following security rules from ADR-0007:

1. **No joblib import** — The module must not import `joblib` at any level.
2. **No pickle import** — The module must not import `pickle` at any level.
3. **No `joblib.load()`** — The module must not contain the string `joblib.load(`.
4. **No model deserialization** — The module reads text JSON only. It never reads or interprets the model artifact bytes.
5. **Fail closed** — Missing manifest, invalid JSON, missing fields, missing artifact, checksum mismatch, and path traversal all raise controlled exceptions.
6. **Path traversal prevention** — `model_filename` must not escape `package_dir`.
7. **Explicit checksum verification** — SHA-256 computed and compared. No silent assumption that the manifest checksum is correct.
8. **No network/S3 calls** — This PR is local filesystem only.
9. **No secrets** — No credentials, tokens, or keys.
10. **No AWS dependencies** — No boto3, no S3 SDK.

## Testing strategy

### Test file: `tests/test_bremen_model_package.py`

Cover these scenarios:

1. **Valid local package passes validation** — Create a temp directory with `manifest.json` (all required fields) and a matching dummy artifact file. Call `validate_model_package()`. Verify it returns the manifest dict.

2. **Missing manifest fails** — Create an empty temp directory. Call `validate_model_package()`. Verify `ModelPackageNotFoundError`.

3. **Invalid JSON manifest fails** — Create a temp directory with a non-JSON manifest file. Call `validate_model_package()`. Verify `ModelPackageManifestError`.

4. **Missing required field fails** — Create a manifest missing `model_version`. Verify `ModelPackageManifestError`.

5. **Missing model artifact fails** — Create a valid manifest but no artifact file. Verify `ModelPackageNotFoundError`.

6. **Checksum mismatch fails** — Create a valid manifest and a dummy artifact file whose SHA-256 does not match the manifest checksum. Verify `ModelPackageChecksumError`.

7. **Path traversal in model_filename fails** — Set `model_filename` to `../etc/passwd`. Verify `ModelPackageSecurityError`.

8. **`summarize_model_package()` returns expected fields** — Call on a valid package. Verify returned dict contains `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`.

9. **`read_model_manifest()` returns parsed content** — Call on a valid manifest. Verify the returned dict matches expected content.

10. **`compute_sha256()` returns correct hex** — Create a file with known content. Verify the computed SHA-256 matches.

11. **Import safety** — Verify that importing `bremen.model_package` does not import `joblib`, `pickle`, `h5py`, or any AWS SDK. Use AST inspection of the module source or `sys.modules` check.

12. **No `joblib.load(` string** — Grep the source file for `joblib.load(`. Must return nothing.

13. **No H5/HDF5 references** — Grep for `.h5`, `.hdf5`, `h5py`. Must return nothing.

14. **No Aramis identity** — Grep for `Aramis`, `aramis`. Must return nothing.

### What tests must NOT do

- Call `joblib.load()`
- Import `joblib` or `pickle`
- Create real model artifacts in the repository
- Read H5/HDF5 files
- Make network calls
- Modify existing test files or config files

## Non-goals

- No actual model loading or `joblib.load()` call.
- No `joblib` or `pickle` imports.
- No model training or inference.
- No API/service routes — this is a library module.
- No async job implementation.
- No S3 or AWS SDK integration.
- No Terraform or IaC files.
- No CI/Docker changes.
- No documentation updates (ROADMAP.md, docs/, README.md).
- No H5/HDF5 reads.
- No model artifacts committed to the repository.
- No clinical or reporting behavior.
- No Aramis active architecture.

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1-2) Baseline state
git rev-parse --verify HEAD
git branch --show-current

# 3-4) Working tree
git status --short
git diff --name-only

# 5-7) Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_model_package.py
python -m pytest -q tests/test_bremen_config_loading.py
python -m pytest -q tests/test_bremen_import_identity.py
python -m pytest -q

# 8) CLI help still works
python -m bremen --help

# 9-11) Security grep checks in new module and tests
grep -R -I -n -E "joblib|pickle|load\(" src/bremen/model_package.py tests/test_bremen_model_package.py 2>/dev/null || true

# 12) No H5/HDF5 references
grep -R -I -n -E "\.h5|\.hdf5|h5py" src/bremen/model_package.py tests/test_bremen_model_package.py 2>/dev/null || true

# 13) No Aramis identity
grep -R -I -n -E "Aramis|aramis" src/bremen/model_package.py tests/test_bremen_model_package.py 2>/dev/null || true

# 14) No forbidden file changes
git diff --name-only -- ROADMAP.md docs docs/adr docs/api_contract.md .github Dockerfile .dockerignore requirements.txt pyproject.toml sonar-project.properties environment.yml Makefile config examples tests/data agents

# 15) No model artifacts created in repo
find . -path "./.git" -prune -o -path "./venv" -prune -o -path "./.venv" -prune -o -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) -print

# 16) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

If the model package module or tests contain errors:

1. **Revert `src/bremen/model_package.py`** — delete the file.
2. **Revert `tests/test_bremen_model_package.py`** — delete the file.
3. **Revert `src/bremen/__init__.py`** — if modified, revert to pre-PR-0013 version.

## Follow-up PRs

After PR 0013 merges:

- **PR 0014** — API contract + async microservice skeleton (delegated from ADR-0003; creates `docs/api_contract.md` + non-functional stub routes)
- **PR 0015** — Terraform/ECR/ECS/S3 IaC skeleton (delegated from ADR-0006; uses G-INFRA-1/G-API-2 decisions)
- **PR 0016** — Runtime model package loader integration with API stub (calls `model_package.validate_model_package()`)
- **Later** — Real training pipeline and `bremen_v1.joblib` publication flow

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `src/bremen/model_package.py`, `tests/test_bremen_model_package.py`, and optionally `src/bremen/__init__.py` changed. |
| **No joblib/pickle drift** | Module does not import `joblib` or `pickle`. Does not call `joblib.load()`. |
| **No artifact drift** | No model artifacts committed to repository. Tests use `tmp_path` only. |
| **No training/inference drift** | No training, inference, or model deserialization code. |
| **No API/IaC drift** | No API routes, no S3/AWS calls, no Terraform/IaC. |
| **No CI/Docker/docs drift** | No changes to CI, Docker, docs, ROADMAP.md, or architecture.md. |
| **Security drift** | Path traversal prevention. Fail-closed validation. SHA-256 checksum verification. No secrets. |
| **Test drift** | All validation scenarios covered. Import safety verified. No joblib.load() in tests. |
| **Validation drift** | All 16 validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan includes `joblib.load()`, imports `joblib`, or imports `pickle`.
- Plan creates model artifacts in the repository.
- Plan reads H5/HDF5 files.
- Plan adds S3/AWS SDK calls.
- Plan includes inference, training, or model deserialization.
- Plan changes CI/Docker/IaC files.
- Plan changes ROADMAP.md, docs/, or README.md.
- Plan makes Aramis active architecture.
- Any file outside the two allowed implementation files is changed (unless __init__.py change is strongly justified and pre-approved).

## Decisions summary

### Allowed files
1. `src/bremen/model_package.py` — NEW
2. `tests/test_bremen_model_package.py` — NEW
3. `src/bremen/__init__.py` — MODIFY (optional, only if strongly justified)

### Forbidden files
- ROADMAP.md, docs/**, docs/adr/**, docs/api_contract.md, README.md
- All infrastructure files (CI, Docker, pyproject, env)
- config/**, examples/**, tests/data/**
- H5/HDF5, model artifacts, IaC files
- agents/**

### Model package contract summary
- Manifest schema with 10 fields: model_version, model_checksum, model_filename, feature_schema_version, threshold_version, threshold_value, qc_criteria_version, training_config_ref, created_at, artifact_type.
- Local package layout: manifest.json + model artifact file.
- Public API: read_model_manifest(), compute_sha256(), validate_model_manifest(), validate_model_package(), summarize_model_package().
- Exception hierarchy: ModelPackageError → ModelPackageNotFoundError, ModelPackageManifestError, ModelPackageChecksumError, ModelPackageSecurityError.

### Security boundary summary
- No joblib/pickle import or deserialization.
- Path traversal prevention for model_filename.
- SHA-256 checksum verification.
- Fail-closed on any validation failure.
- No network/S3/AWS calls.

### Testing summary
14 test scenarios covering: valid package, missing manifest, invalid JSON, missing fields, missing artifact, checksum mismatch, path traversal, summary output, manifest reading, checksum computation, import safety, no joblib/pickle/H5/Aramis references.

### Validation summary
16 checks: git state, compileall, model package tests, existing tests (config loading, identity, full suite), CLI help, security grep checks, forbidden path check, model artifact scan, .DS_Store.

### Follow-up sequencing
PR 0014 (API skeleton) → PR 0015 (Terraform IaC) → PR 0016 (runtime loader integration) → later training pipeline.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0013-model-package-contract/PLAN.md`
2. Human runs: `git add .project-memory/pr/0013-model-package-contract/PLAN.md`
3. Human runs: `git commit -m "PR 0013 — Plan model package contract and local validation helpers"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the two allowed files.

## Files read

- `docs/adr/0007-model-artifact-lifecycle.md`
- `.project-memory/project_contract.yml`
- `src/bremen/config.py`
- `tests/test_bremen_config_loading.py`
- `AGENTS.md`
- `ROADMAP.md`
- `docs/architecture.md`

## Files written

- `.project-memory/pr/0013-model-package-contract/PLAN.md` (this file)

## Files intentionally ignored

- All infrastructure files (CI, Docker, SonarCloud, pyproject, env)
- All docs files (ROADMAP.md, docs/, README.md)
- All config, example, test data files
- All existing source files not named in the allowed set
- Any H5/HDF5 or model artifact files

## Boundary confirmations

- confirm: no `joblib.load` planned: yes
- confirm: no `joblib`/`pickle` import planned: yes
- confirm: no model artifact planned: yes
- confirm: no training/inference planned: yes
- confirm: no API routes planned: yes
- confirm: no S3/AWS calls planned: yes
- confirm: no CI/Docker/IaC changes planned: yes
- confirm: no docs/ROADMAP changes planned: yes
- confirm: no H5/HDF5 reads planned: yes
- confirm: no implementation files modified: yes
- confirm: no git mutation commands run: yes
