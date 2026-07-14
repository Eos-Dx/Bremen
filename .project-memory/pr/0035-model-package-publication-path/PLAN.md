# PR 0035 — Plan Model Package Publication Path

Author: plan
Mode: planning only
Branch: 0035-model-package-publication-path

## Objective

Create the controlled path from a Bremen training artifact to a runtime-loadable model package publication candidate. This PR implements release mechanics and dry-run publication: validate training artifact shape, compute checksum, build ADR-0007-compatible runtime package manifest, stage files into a local release directory, and support dry-run S3 publication metadata without real AWS calls. No real training, H5 access, S3 upload, or runtime changes.

## Preconditions confirmed

- **PR 0034 training pipeline present**: `src/bremen/training/pipeline.py` exists. `REQUIRED_TRAINING_ARTIFACT_FIELDS` defined (21 fields). Artifact `kind == "bremen_training_artifact"`.
- **ADR-0007 runtime model package contract present**: `src/bremen/model_package.py` exists. `EXPECTED_ARTIFACT_TYPE = "bremen.joblib.model_package"`. Manifest fields: `artifact_type`, `model_version`, `model_checksum`, `model_filename`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`.

## Required reads — observed facts

### Training artifact structure (pipeline.py)
- `REQUIRED_TRAINING_ARTIFACT_FIELDS` is a tuple of 21 field names.
- `_patient_training_artifact()` assembles all fields including `models` (trained objects), `thresholds` (per-model float dict), `feature_schema` (list of column names), `training_config_sha256`, `input_dataframe_joblib_sha256`.
- `model_version` in the training artifact is the config's `training.version`.
- `feature_schema` is `list(feature_table.columns)` — a list of strings.
- `thresholds` is a `dict[str, float]` mapping model names to calibrated thresholds.

### ADR-0007 runtime manifest (model_package.py)
- `EXPECTED_ARTIFACT_TYPE = "bremen.joblib.model_package"`.
- Required manifest fields: `artifact_type`, `model_version`, `model_checksum`, `model_filename`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`.
- `validate_model_package()` checks: manifest exists → required fields → path traversal → artifact exists → SHA-256 checksum match.
- `summarize_model_package()` returns `ModelPackageSummary` with `model_path`.

### Existing config.py
- `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_BUCKET` environment variables.
- `_DEFAULT_MANIFEST_KEY = "manifest.json"`.
- Cloud config path for S3 publication dry-run: `s3://{bucket}/{prefix}{model_version}/`.

### CLI design patterns
- `train_classifier.py`: argparse, `--config` required, returns 0/1.
- `__main__.py`: subcommand dispatch with lazy imports.

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`src/bremen/training/model_release.py`** — NEW. Validation + manifest building + staging logic.
2. **`src/bremen/training/publish_model_package.py`** — NEW. CLI entrypoint.
3. **`src/bremen/training/__init__.py`** — MODIFY only if an export update is needed (prefer not).
4. **`config/model_release/bremen_v0_1_release.yaml`** — NEW (optional, only if justified).
5. **`tests/test_bremen_model_release.py`** — NEW.
6. **`tests/test_bremen_publish_model_package_cli.py`** — NEW.

Optional: existing training tests only if they need narrow updates for interface compatibility.

## Forbidden files

- `src/bremen/model_loader.py`, `src/bremen/api/**`, `src/bremen/__main__.py`
- `Dockerfile`, `Dockerfile.training` (unless CLI needs training image command update — it does not)
- `.github/**` (unless dry-run CI validation needed — it is not)
- `infra/**` (unless no-cloud config-only update needed — it is not)
- `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`, `.project-memory/project_contract.yml`
- `requirements.txt`, `pyproject.toml` (no new dependencies)
- `examples/**`, `agents/**`
- Any H5/HDF5, joblib/pkl/npy/npz artifacts (test temp files only)
- Secrets, AWS account IDs, account-specific registry URLs, access keys, secret keys, secret values

## Implementation scope

### 1. `src/bremen/training/model_release.py` — Release logic

This module contains the training artifact validation, manifest building, local staging, and dry-run publication summary generation. It lives under `training/` (offline-only tooling) and must not be imported by any runtime module.

```python
"""Model package release helpers — offline publication tooling only.

Converts a Bremen training artifact into an ADR-0007-compatible runtime
model package candidate. No AWS calls, no network access, no inference.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model_package import EXPECTED_ARTIFACT_TYPE


REQUIRED_RUNTIME_MANIFEST_FIELDS = (
    "artifact_type",
    "model_version",
    "model_checksum",
    "model_filename",
    "feature_schema_version",
    "threshold_version",
    "threshold_value",
    "qc_criteria_version",
)
```

**Functions**:

```python
def load_training_artifact(path: str | Path) -> dict[str, Any]:
    """Load and validate a Bremen training artifact joblib file.

    Verifies:
    - File exists and is a valid joblib file.
    - Loaded object is a dict.
    - ``kind == "bremen_training_artifact"``.
    - All required training artifact fields are present.

    Raises ``ValueError`` with descriptive message on any failure.
    Does NOT load arbitrary joblib files — only validated training artifacts.
    """


def validate_training_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate a training artifact dict in memory.

    Checks all ``REQUIRED_TRAINING_ARTIFACT_FIELDS`` are present.
    Checks ``kind == "bremen_training_artifact"``.
    Returns the validated artifact.
    Raises ``ValueError`` on failure.
    """


def build_runtime_manifest(
    artifact: dict[str, Any],
    *,
    model_version: str,
    model_filename: str,
    feature_schema_version: str,
    threshold_version: str,
    threshold_key: str | None,
    qc_criteria_version: str,
    model_checksum: str,
) -> dict[str, Any]:
    """Build an ADR-0007-compatible runtime model package manifest dict.

    Parameters
    ----------
    artifact : The validated training artifact dict.
    model_version : Explicit model version for the runtime manifest.
    model_filename : The filename of the staged model artifact
        (relative path within the package directory).
    feature_schema_version : Explicit feature schema version.
    threshold_version : Explicit threshold version string.
    threshold_key : Key into ``artifact["thresholds"]`` for the
        threshold value.  If ``None``, use the first available.
    qc_criteria_version : Explicit QC criteria version.
    model_checksum : SHA-256 hex digest of the staged model joblib file.

    Returns a dict with the exact field names and types expected by
    ``model_package.py``::

        {
            "artifact_type": "bremen.joblib.model_package",
            "model_version": str,
            "model_checksum": str,
            "model_filename": str,
            "feature_schema_version": str,
            "threshold_version": str,
            "threshold_value": float,
            "qc_criteria_version": str,
        }

    Raises ``ValueError`` if required inputs are missing or invalid.
    """


def stage_model_package(
    artifact_path: str | Path,
    output_dir: str | Path,
    *,
    model_version: str,
    model_filename: str | None,
    feature_schema_version: str,
    threshold_version: str,
    threshold_key: str | None,
    qc_criteria_version: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Stage a local model package candidate from a training artifact.

    Steps:
    1. Load and validate the training artifact.
    2. Compute SHA-256 of the artifact file (or copied joblib).
    3. Build the runtime manifest.
    4. Write ``manifest.json`` and the model joblib file.
    5. Return a dry-run summary dict.

    Parameters
    ----------
    artifact_path : Path to the training artifact joblib file.
    output_dir : Directory where package files will be staged.
    model_version : Runtime model version for the manifest.
    model_filename : Filename for the copied model joblib file.
        Defaults to ``f"model_{model_version}.joblib"`` if not provided.
    feature_schema_version : Feature schema version.
    threshold_version : Threshold version string.
    threshold_key : Key into artifact thresholds.
    qc_criteria_version : QC criteria version.
    dry_run : When ``True`` (default), validate inputs and print plan
        but do NOT write files.  Writes files only when ``False``.

    Returns
    -------
    A dry-run summary dict containing the publication plan (intended
    paths, filenames, manifest fields, S3 URIs).  No files are written
    when ``dry_run=True``.
    """


def dry_run_publication_summary(
    manifest: dict[str, Any],
    output_dir: str | Path,
    *,
    bucket: str | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    """Generate a dry-run S3 publication summary without network calls.

    Parameters
    ----------
    manifest : The built runtime manifest dict.
    output_dir : Local staging directory.
    bucket : Intended S3 bucket name (optional, for URI generation).
    prefix : Intended S3 key prefix (optional, for URI generation).

    Returns a dict with::

        {
            "package_staging_dir": str,
            "manifest_path": str,
            "model_path": str,
            "intended_s3_uri": str or None,
            "manifest_fields": dict,
        }

    No AWS calls, no network access, no file writes.
    """
```

### 2. `src/bremen/training/publish_model_package.py` — CLI entrypoint

```python
"""CLI entrypoint for model package publication (dry-run / staging).

Usage:
    python -m bremen.training.publish_model_package \\
        --training-artifact <path> \\
        --output-dir <dir> \\
        --model-version <version> \\
        --feature-schema-version <version> \\
        --threshold-version <version> \\
        --qc-criteria-version <version> \\
        --threshold-key <key> \\
        [--dry-run]

This module is offline-only. Never imported by runtime API or service code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bremen-publish",
        description="Stage a model package candidate from a training artifact"
    )
    parser.add_argument(
        "--training-artifact", required=True, type=Path,
        help="Path to training artifact joblib file",
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Directory for staged package output",
    )
    parser.add_argument(
        "--model-version", required=True,
        help="Runtime model version string",
    )
    parser.add_argument(
        "--feature-schema-version", required=True,
        help="Feature schema version string",
    )
    parser.add_argument(
        "--threshold-version", required=True,
        help="Threshold version string",
    )
    parser.add_argument(
        "--qc-criteria-version", required=True,
        help="QC criteria version string",
    )
    parser.add_argument(
        "--threshold-key",
        default=None,
        help="Key into artifact thresholds.  Default: first available.",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually write staged files (default is dry-run only)",
    )

    args = parser.parse_args(argv)

    from .model_release import stage_model_package  # noqa: PLC0415

    try:
        summary = stage_model_package(
            artifact_path=args.training_artifact,
            output_dir=args.output_dir,
            model_version=args.model_version,
            model_filename=f"model_{args.model_version}.joblib",
            feature_schema_version=args.feature_schema_version,
            threshold_version=args.threshold_version,
            threshold_key=args.threshold_key,
            qc_criteria_version=args.qc_criteria_version,
            dry_run=not args.no_dry_run,
        )

        print(json.dumps(summary, indent=2))
    except Exception as exc:
        print(f"Publication failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 3. Optional: `config/model_release/bremen_v0_1_release.yaml`

**Decision: DO NOT ADD a release config file in PR 0035.** The CLI flags provide explicit release parameters, and a release config is not needed until multiple release configurations become standard. Deferred to PR 0036 or later when release automation is built.

### 4. `tests/test_bremen_model_release.py`

Test scenarios (all use synthetic joblib training artifacts via `tmp_path`):

1. **`test_valid_training_artifact_accepted`** — Create a synthetic training artifact dict with all 21 required fields, serialise via `joblib.dump`, load via `load_training_artifact()`, verify returns matching dict.
2. **`test_invalid_kind_rejected`** — Artifact with `kind="some_other"` raises `ValueError`.
3. **`test_missing_training_artifact_field_rejected`** — Artifact missing one required field raises `ValueError`.
4. **`test_manifest_has_exact_adr_0007_fields`** — `build_runtime_manifest()` returns dict with exactly `artifact_type`, `model_version`, `model_checksum`, `model_filename`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`.
5. **`test_manifest_artifact_type_is_bremen_joblib`** — `manifest["artifact_type"] == "bremen.joblib.model_package"`.
6. **`test_checksum_equals_sha256_of_staged_file`** — Compute SHA-256 of synthetic artifact file, build manifest, verify `manifest["model_checksum"]` matches.
7. **`test_manifest_contains_relative_filename_not_absolute_path`** — `model_filename` does not start with `/`, does not contain `..`.
8. **`test_threshold_selection_populates_threshold_value`** — Pass `threshold_key="M0"`, verify `manifest["threshold_value"]` equals `artifact["thresholds"]["M0"]`.
9. **`test_threshold_key_none_uses_first_available`** — Pass `threshold_key=None`, verify threshold_value is set.
10. **`test_stage_model_package_dry_run_does_not_write_files`** — Call `stage_model_package(dry_run=True)`, verify no files exist in output dir after call.
11. **`test_stage_model_package_writes_files_when_not_dry_run`** — Call with `dry_run=False`, verify `manifest.json` and model joblib file exist.
12. **`test_dry_run_summary_contains_intended_s3_uri`** — Call `dry_run_publication_summary(bucket="my-bucket", prefix="models/")`, verify `"s3://my-bucket/models/"` is in the summary.
13. **`test_dry_run_does_not_make_network_calls`** — Verify no `boto3`, `requests`, `urllib`, `awscli` imports in module.

### 5. `tests/test_bremen_publish_model_package_cli.py`

1. **`test_cli_help_works`** — `python -m bremen.training.publish_model_package --help` exits 0.
2. **`test_cli_missing_required_flags_errors`** — Calling without `--training-artifact` exits non-zero.
3. **`test_cli_dry_run_with_synthetic_artifact`** — Create synthetic artifact, run CLI with `--dry-run`, verify stdout contains JSON summary.
4. **`test_cli_does_not_write_files_by_default`** — Run CLI without `--no-dry-run`, verify output dir is empty after.
5. **`test_cli_stages_package_with_no_dry_run`** — Run CLI with `--no-dry-run`, verify `manifest.json` and model joblib file exist in output dir.

### 6. `src/bremen/training/__init__.py` — No change

The package init is already minimal. No export update needed.

## Manifest strategy summary

| Manifest field | Source in PR 0035 |
|----------------|-------------------|
| `artifact_type` | Constant: `"bremen.joblib.model_package"` |
| `model_version` | CLI argument `--model-version` (explicit, not inferred) |
| `model_checksum` | SHA-256 of staged model joblib file |
| `model_filename` | Default: `f"model_{model_version}.joblib"`, or CLI-specified |
| `feature_schema_version` | CLI argument `--feature-schema-version` (explicit) |
| `threshold_version` | CLI argument `--threshold-version` (explicit) |
| `threshold_value` | From `artifact["thresholds"][threshold_key]` (CLI-selected key) |
| `qc_criteria_version` | CLI argument `--qc-criteria-version` (explicit) |

All manifest field names match ADR-0007 exactly. No renamed concepts.

## Dry-run publication summary

The dry-run summary returns a dict with:
- `package_staging_dir` — local output directory path
- `manifest_path` — intended manifest.json path
- `model_path` — intended model joblib path
- `intended_s3_uri` — `s3://{bucket}/{prefix}{model_version}/`
- `manifest_fields` — the full manifest dict for inspection
- `files_written` — `false` (dry-run)

No AWS calls. No network access. Config values for bucket/prefix come from optional function parameters only.

## CLI summary

Command: `python -m bremen.training.publish_model_package`
Required flags: `--training-artifact`, `--output-dir`, `--model-version`, `--feature-schema-version`, `--threshold-version`, `--qc-criteria-version`
Optional flags: `--threshold-key` (default: first available), `--no-dry-run` (default: dry-run)
Exit codes: 0 on success, 1 on error

## Runtime boundary plan

- `src/bremen/training/model_release.py` lives under `training/` (offline-only).
- Runtime modules (`api/`, `model_loader.py`, `__main__.py`) must NOT import from `bremen.training.model_release` or `bremen.training.publish_model_package`.
- `model_loader.py` and `model_package.py` remain unchanged.
- The `validate_model_package()` function from `model_package.py` can be called in tests to verify that the staged manifest is compatible, but the test file itself imports from `bremen.model_package` not `bremen.training` for the validation.

## Non-goals

- No real S3/AWS upload.
- No real model artifacts checked into repo.
- No real H5/data access.
- No training run.
- No runtime model loader changes.
- No runtime API changes.
- No inference integration.
- No clinical claims.
- No Dockerfile.training changes (training image already has the packages needed; the CLI works inside the training container without modification).
- No Dockerfile changes.
- No CI workflow changes.
- No Terraform changes.
- No dependency additions.
- No docs/ADR/roadmap changes.

## Validation checklist

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5) Compile check
python -m compileall src tests

# 6-7) New test files
python -m pytest -q tests/test_bremen_model_release.py
python -m pytest -q tests/test_bremen_publish_model_package_cli.py

# 8) CLI help works
python -m bremen.training.publish_model_package --help

# 9) Release module references ADR-0007 manifest fields
grep -R "bremen.joblib.model_package\|model_version\|model_checksum\|feature_schema_version\|threshold_version\|threshold_value\|qc_criteria_version" src/bremen/training tests config 2>/dev/null || true

# 10) Release module references training artifact fields
grep -R "bremen_training_artifact\|training_config_sha256\|input_dataframe_joblib_sha256" src/bremen/training tests 2>/dev/null || true

# 11) No AWS/network calls in training or tests
grep -R "boto3\|aws s3\|awscli\|put_object\|upload_file\|requests\|urllib" src/bremen/training tests config 2>/dev/null || true

# 12) Runtime does not import training
grep -R "bremen.training" src/bremen/api src/bremen/model_loader.py src/bremen/__main__.py 2>/dev/null || true

# 13) No secrets/account IDs in changed files
grep -R "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|aws_secret_access_key\|account ID\|registry URL\|[0-9]\{12\}\.dkr\.ecr" src tests config docs .github infra 2>/dev/null || true

# 14) Full test suite
python -m pytest -q
```

## Rollback plan

1. **Delete `src/bremen/training/model_release.py`** and **`publish_model_package.py`**.
2. **Delete test files** `test_bremen_model_release.py` and `test_bremen_publish_model_package_cli.py`.
3. No other files affected. Runtime, config, and training pipeline are untouched.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only training/release module + CLI + tests changed. |
| **Manifest drift** | All ADR-0007 fields present. `artifact_type == "bremen.joblib.model_package"`. Field names not renamed. |
| **No-S3 drift** | No `boto3`, `awscli`, `requests`, `urllib`. No real upload. Dry-run only. |
| **Runtime boundary drift** | Release lives under `training/`. Runtime does not import it. |
| **Validation drift** | All validation checks pass. No secrets/account IDs. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- PR 0034 training artifact contract is missing (`REQUIRED_TRAINING_ARTIFACT_FIELDS` not defined).
- ADR-0007 model package contract is missing (`EXPECTED_ARTIFACT_TYPE` not defined).
- Publication requires real S3/AWS call.
- Publication requires real model artifacts checked into repo.
- Publication requires real H5/data access.
- Publication requires runtime model loader/API changes.
- Publication requires inference integration.
- Manifest cannot preserve ADR-0007 field names.
- CLI cannot be implemented without dependency install.
- Secrets/account IDs/registry URLs would be needed.

## Follow-up PR 0036 summary

PR 0036 (next in sequence after PR 0035) — First controlled training run and model package publication on real approved data, using this PR's publication path to stage and validate the package, then publish to S3 with verified `model_checksum` and `feature_schema_version`.

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0035-model-package-publication-path/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0035-model-package-publication-path/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Files read

- `.project-memory/pr/0034-bremen-training-pipeline-implementation/PLAN.md`
- `.project-memory/pr/0034-bremen-training-pipeline-implementation/reviews/precommit-review.yml`
- `docs/adr/0008-two-image-build-training-pipeline-separation.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `.project-memory/project_contract.yml`
- `src/bremen/training/pipeline.py`
- `src/bremen/training/train_classifier.py`
- `src/bremen/model_package.py`
- `src/bremen/model_loader.py`
- `src/bremen/config.py`
- Existing tests
- `.github/workflows/ecr-publish.yml`
- `infra/terraform/ecr.tf`
- `infra/terraform/outputs.tf`

## Files written

- `.project-memory/pr/0035-model-package-publication-path/PLAN.md` (this file)

## Files intentionally ignored

- All runtime source files (not modified).
- All runtime test files (not modified).
- All docs, ADR, and roadmap files (not modified).
- Any H5/HDF5 or model artifact files.

## Boundary confirmations

- confirm: branch is `0035-model-package-publication-path`: yes
- confirm: PR 0034 training artifact contract present: yes
- confirm: ADR-0007 runtime package manifest contract present: yes
- confirm: no implementation files edited during planning: yes
- confirm: no real S3/AWS upload planned: yes
- confirm: no real H5/data access planned: yes
- confirm: no model artifacts planned for repo: yes
- confirm: no runtime loader/API changes planned: yes
- confirm: no inference integration planned: yes
- confirm: no clinical claims planned: yes
- confirm: no git mutation commands run: yes
