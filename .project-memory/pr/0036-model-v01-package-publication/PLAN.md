# PR 0036 — Plan Model v0.1 Package Publication

Author: plan
Mode: planning only
Branch: 0036-model-v01-package-publication

## Objective

Package the human-provided `bremen_v0.1.joblib` (from Kubytskyi, outside the repository) into a checksum-gated runtime model package candidate with ADR-0007 manifest, add `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_URI`, and `BREMEN_MODEL_CHECKSUM` to Terraform/runtime configuration, and provide an opt-in smoke path against the real v0.1 artifact. This is the first step on the critical path to Bremen's first working prediction in July 2026.

## Preconditions

- **ADR-0007 runtime model package contract**: `src/bremen/model_package.py` exists. `EXPECTED_ARTIFACT_TYPE = "bremen.joblib.model_package"`. Manifest fields: `artifact_type`, `model_version`, `model_checksum`, `model_filename`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`.
- **PR 0035 release helpers**: `src/bremen/training/model_release.py` and `src/bremen/training/publish_model_package.py` exist and provide `build_runtime_manifest()`, `stage_model_package()`, `dry_run_publication_summary()`.
- **Terraform**: ECS task definition already has `BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_VERSION` environment variables. S3 model bucket exists.
- All preconditions confirmed present.

## Roadmap override context

Bremen roadmap was redefined on 2026-07-06. Bremen is now on the critical path to the first working prediction in July 2026. The critical path sequence is:
- PR 0036 — Model v0.1 Package Publication (this PR)
- PR 0037 — H5 Preflight Gate
- PR 0038 — Preprocessing Bridge
- PR 0039 — Inference Integration / First Working Prediction

## Human/agent boundary

| Action | Who | Notes |
|--------|-----|-------|
| Provide `bremen_v0.1.joblib` | Human | Outside repository |
| Package, validate, stage, create manifest | Agent | Uses existing `model_release.py` |
| Add Terraform variables | Agent | No secrets, no AWS account IDs |
| Write smoke test for real artifact | Agent | Opt-in via `BREMEN_V01_JOBLIB_PATH` env var |
| Write synthetic tests | Agent | `tmp_path` joblib only |
| Upload to S3 | Human | Agent must not run AWS commands |
| Set real `BREMEN_MODEL_URI` | Human | Agent provides expected URI |
| Confirm final checksum | Human | Agent computes and reports it |
| Terraform apply | Human | Agent must not run Terraform commands |

## Required reads — observed facts

### Existing release helpers (`model_release.py`)
- `build_runtime_manifest()` — builds ADR-0007 manifest from training artifact dict. Requires explicit `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_key`, `qc_criteria_version`.
- `stage_model_package()` — stages package with manifest + copied joblib. Supports `dry_run=True/False`.
- `dry_run_publication_summary()` — generates S3 URI for given bucket/prefix.
- Works with training artifacts (`kind == "bremen_training_artifact"`). The v0.1 artifact from Kubytskyi may not be a training artifact dict — it's likely a raw joblib (sklearn model or dict). The release helper currently requires a training artifact shape. For PR 0036, a narrow v0.1-specific wrapper is needed that accepts a raw joblib path directly (not a training artifact) and produces the manifest.

### Terraform ECS task definition
- Already has environment variables: `BREMEN_MODEL_BUCKET` (from `aws_s3_bucket.model_packages.bucket`), `BREMEN_MODEL_PREFIX` (from `var.model_package_prefix`), `BREMEN_MODEL_VERSION` (empty string).
- No `BREMEN_MODEL_URI` or `BREMEN_MODEL_CHECKSUM` variables exist yet.
- Terraform S3 bucket exists at `aws_s3_bucket.model_packages`.

### Terraform App Runner
- Does NOT have the environment variables that ECS has. No `BREMEN_MODEL_BUCKET`/`PREFIX`/`VERSION` in App Runner service config.

### Existing config.py
- Reads `BREMEN_MODEL_VERSION` from env via `read_cloud_config()`. Supports `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_MANIFEST_KEY`.
- Does NOT read `BREMEN_MODEL_URI` or `BREMEN_MODEL_CHECKSUM` from env.

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`src/bremen/training/publish_v01.py`** — NEW. Narrow v0.1-specific publication wrapper. Accepts raw joblib path (not training artifact), computes checksum, calls existing `build_runtime_manifest()` with v0.1-specific defaults, stages package, prints summary.
2. **`infra/terraform/variables.tf`** — MODIFY. Add `model_version` (default `"v0.1"`), `model_uri` (no default, human-provided), `model_checksum` (no default, human-provided).
3. **`infra/terraform/ecs.tf`** — MODIFY. Add `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_URI`, `BREMEN_MODEL_CHECKSUM` environment variables to the ECS task definition.
4. **`infra/terraform/apprunner.tf`** — MODIFY. Add the same three environment variables to App Runner service (consistent with ECS).
5. **`infra/terraform/outputs.tf`** — MODIFY. Add model version/uri/checksum outputs.
6. **`infra/terraform/README.md`** — MODIFY. Document human-only publication/apply steps.
7. **`tests/test_bremen_model_v01_publication.py`** — NEW. Tests using synthetic joblib artifacts.
8. **`tests/test_bremen_model_package_terraform_env.py`** — NEW. Tests for Terraform env var wiring.

Optional: `src/bremen/config.py` — MODIFY only if `BREMEN_MODEL_URI` and `BREMEN_MODEL_CHECKSUM` should be read at runtime (deferred to PR 0039 when the runtime actually uses them).

## Forbidden files

- `src/bremen/model_loader.py`, `src/bremen/api/**`, `src/bremen/__main__.py`
- `src/bremen/training/model_release.py` (reused, not modified)
- `src/bremen/training/publish_model_package.py` (reused, not modified)
- `Dockerfile`, `Dockerfile.training`, `.github/**`
- `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`, `.project-memory/project_contract.yml`
- `requirements.txt`, `pyproject.toml`
- `examples/**`, `agents/**`
- Any H5/HDF5, joblib/pkl/npy/npz files in repo (test temp files only)
- Real model artifacts (`.joblib`, `.pkl`, `.npy`, `.npz`)
- Secrets, AWS account IDs, account-specific registry URLs, access keys, secret keys, secret values

## Implementation scope

### 1. `src/bremen/training/publish_v01.py` — v0.1 publication wrapper

A thin CLI module that takes a raw joblib path (not a training artifact), computes its SHA-256, and stages a model package using existing helpers. Since the v0.1 artifact from Kubytskyi is a raw joblib (not a `bremen_training_artifact` dict), this module constructs the minimal required metadata directly without requiring a full training artifact.

```python
"""Publish the human-provided bremen_v0.1.joblib as a runtime model package.

Usage:
    python -m bremen.training.publish_v01 --joblib-path <path> --output-dir <dir>

Requires explicit metadata flags or will derive from defaults.
Dry-run by default. Use --no-dry-run to stage files locally.

This module is offline-only tooling. Never imported by runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

MANIFEST_FILENAME = "manifest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bremen-publish-v01",
        description="Package bremen_v0.1.joblib into a runtime model package"
    )
    parser.add_argument(
        "--joblib-path", required=True, type=Path,
        help="Path to the bremen_v0.1.joblib file (outside repo)",
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Output directory for the staged model package",
    )
    parser.add_argument(
        "--model-version", default="v0.1",
        help="Model version (default: v0.1)",
    )
    parser.add_argument(
        "--feature-schema-version", required=True,
        help="Feature schema version string (required)",
    )
    parser.add_argument(
        "--threshold-version", default="v0.1",
        help="Threshold version (default: v0.1)",
    )
    parser.add_argument(
        "--threshold-value", type=float, default=0.5,
        help="Decision threshold value (default: 0.5)",
    )
    parser.add_argument(
        "--qc-criteria-version", default="v0.1",
        help="QC criteria version (default: v0.1)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually stage files (default is dry-run only)",
    )
    args = parser.parse_args(argv)

    joblib_path = Path(args.joblib_path)
    if not joblib_path.exists():
        print(f"Error: joblib not found: {joblib_path}", file=sys.stderr)
        return 1

    # Compute checksum
    checksum = _sha256(joblib_path)

    # Build manifest
    manifest = _build_manifest(
        model_version=args.model_version,
        model_checksum=checksum,
        model_filename=joblib_path.name,
        feature_schema_version=args.feature_schema_version,
        threshold_version=args.threshold_version,
        threshold_value=args.threshold_value,
        qc_criteria_version=args.qc_criteria_version,
    )

    output_dir = Path(args.output_dir)

    # Stage or dry-run
    if not args.no_dry_run:
        print("=== DRY RUN ===")
        print(json.dumps(manifest, indent=2))
        print(f"Would stage to: {output_dir.resolve()}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        model_target = output_dir / joblib_path.name
        shutil.copy2(joblib_path, model_target)
        (output_dir / MANIFEST_FILENAME).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        print(f"Staged model package to: {output_dir.resolve()}")
        print(f"Manifest: {output_dir / MANIFEST_FILENAME}")
        print(f"Model: {model_target}")

    print(f"\nChecksum (SHA-256): {checksum}")
    print(f"Model version: {args.model_version}")

    return 0


def _build_manifest(
    *,
    model_version: str,
    model_checksum: str,
    model_filename: str,
    feature_schema_version: str,
    threshold_version: str,
    threshold_value: float,
    qc_criteria_version: str,
) -> dict[str, Any]:
    """Build ADR-0007-compatible manifest for v0.1."""
    return {
        "artifact_type": "bremen.joblib.model_package",
        "model_version": model_version,
        "model_checksum": model_checksum,
        "model_filename": model_filename,
        "feature_schema_version": feature_schema_version,
        "threshold_version": threshold_version,
        "threshold_value": threshold_value,
        "qc_criteria_version": qc_criteria_version,
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
```

### 2. `infra/terraform/variables.tf` — New variables

```hcl
variable "model_version" {
  description = "BREMEN_MODEL_VERSION — active model version string for the runtime."
  type        = string
  default     = "v0.1"
}

variable "model_uri" {
  description = "BREMEN_MODEL_URI — S3 URI or equivalent reference for the active model package."
  type        = string
  default     = ""
}

variable "model_checksum" {
  description = "BREMEN_MODEL_CHECKSUM — SHA-256 hex digest of the active model package joblib file."
  type        = string
  default     = ""
}
```

### 3. `infra/terraform/ecs.tf` — Environment variables

Add to the ECS task definition `environment` block:

```hcl
{
  name  = "BREMEN_MODEL_VERSION"
  value = var.model_version
},
{
  name  = "BREMEN_MODEL_URI"
  value = var.model_uri
},
{
  name  = "BREMEN_MODEL_CHECKSUM"
  value = var.model_checksum
}
```

Replace the existing `BREMEN_MODEL_VERSION: ""` line with the variable-driven version above.

### 4. `infra/terraform/apprunner.tf` — Environment variables

App Runner currently has no environment variable block. Add one to the `image_configuration` block (App Runner supports env vars in `image_configuration`):

```hcl
image_configuration {
  port = var.container_port

  environment_variables = {
    BREMEN_MODEL_VERSION = var.model_version
    BREMEN_MODEL_URI     = var.model_uri
    BREMEN_MODEL_CHECKSUM = var.model_checksum
  }
}
```

### 5. `infra/terraform/outputs.tf` — New outputs

```hcl
output "model_version" {
  description = "Active model version string for the runtime."
  value       = var.model_version
}

output "model_uri" {
  description = "S3 URI or equivalent reference for the active model package."
  value       = var.model_uri
}

output "model_checksum" {
  description = "SHA-256 hex digest of the active model package joblib file."
  value       = var.model_checksum
}
```

### 6. `infra/terraform/README.md` — Human-only publication steps

Add a section:

```markdown
### Model v0.1 Package Publication (Human-Only)

1. **Human obtains `bremen_v0.1.joblib`** from Kubytskyi (outside this repository).
2. **Agent or human runs dry-run:**
   ```
   python -m bremen.training.publish_v01 \
     --joblib-path /path/to/bremen_v0.1.joblib \
     --output-dir /tmp/model-package-v0.1 \
     --feature-schema-version v0.1
   ```
3. **Human verifies SHA-256 checksum** from the dry-run output.
4. **Human stages package locally:**
   ```
   python -m bremen.training.publish_v01 \
     --joblib-path /path/to/bremen_v0.1.joblib \
     --output-dir /tmp/model-package-v0.1 \
     --feature-schema-version v0.1 \
     --no-dry-run
   ```
5. **Human uploads staged package to S3:**
   ```
   aws s3 cp /tmp/model-package-v0.1/ s3://<bucket>/model-packages/v0.1/ --recursive
   ```
6. **Human sets Terraform variables:**
   ```
   model_version = "v0.1"
   model_uri     = "s3://<bucket>/model-packages/v0.1/"
   model_checksum = "<sha256 from step 3>"
   ```
7. **Human applies Terraform** to update ECS/App Runner environment variables.
8. **Human verifies runtime model package** by checking `/model/version` endpoint after deployment.

**Agent must not:** run `aws` commands, run `terraform apply`, handle credentials, upload to S3, commit the model artifact.
```

### 7. `tests/test_bremen_model_v01_publication.py`

Test scenarios (all use synthetic temp joblib files):

1. `test_v01_publish_dry_run_does_not_write_files` — Run `publish_v01` with `--no-dry-run` absent, verify output dir is empty.
2. `test_v01_publish_stages_files` — Run with `--no-dry-run`, verify `manifest.json` and joblib file exist in output dir.
3. `test_v01_manifest_has_correct_artifact_type` — Manifest `artifact_type == "bremen.joblib.model_package"`.
4. `test_v01_checksum_matches_staged_file` — SHA-256 of staged joblib matches manifest `model_checksum`.
5. `test_v01_model_filename_is_relative` — `model_filename` does not start with `/`.
6. `test_v01_missing_joblib_file_rejected` — Non-existent `--joblib-path` exits non-zero.
7. `test_v01_requires_feature_schema_version` — Missing `--feature-schema-version` exits non-zero.
8. `test_v01_cli_help_works` — `python -m bremen.training.publish_v01 --help` exits 0.
9. `test_v01_validate_model_package_accepts_staged_package` — Call `validate_model_package()` on staged output dir, verify it passes.

### 8. `tests/test_bremen_model_package_terraform_env.py`

1. `test_terraform_variables_exist` — Parse `variables.tf`, verify `model_version`, `model_uri`, `model_checksum` variables.
2. `test_terraform_ecs_env_vars_exist` — Parse `ecs.tf`, verify `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_URI`, `BREMEN_MODEL_CHECKSUM` environment variables.
3. `test_terraform_ecs_uses_variable_refs` — ECS env var values reference `var.model_version`, `var.model_uri`, `var.model_checksum` (not hardcoded).
4. `test_terraform_apprunner_env_vars_exist` — Parse `apprunner.tf`, verify the same three env vars.

## Real artifact smoke path (opt-in)

A smoke test that runs only when `BREMEN_V01_JOBLIB_PATH` environment variable is set:

```python
import os
import subprocess
import sys

def test_v01_real_artifact_smoke():
    """Smoke test for the real v0.1 artifact. Skipped by default.

    Set BREMEN_V01_JOBLIB_PATH=/path/to/bremen_v0.1.joblib to enable.
    Requires a real artifact file provided by a human outside the repo.
    """
    joblib_path = os.environ.get("BREMEN_V01_JOBLIB_PATH")
    if not joblib_path:
        pytest.skip("BREMEN_V01_JOBLIB_PATH not set — skipping real artifact smoke test")
    # Run the publication CLI in dry-run mode
    result = subprocess.run(
        [sys.executable, "-m", "bremen.training.publish_v01",
         "--joblib-path", joblib_path,
         "--output-dir", "/tmp/bremen-v01-smoke",
         "--feature-schema-version", "v0.1"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "Checksum" in result.stdout
    assert "DRY RUN" in result.stdout
```

## S3 publication boundary

All agent actions stop at local staging and dry-run summary. Human-only actions:
1. Verify SHA-256 checksum from dry-run output.
2. Run the CLI with `--no-dry-run` to stage package files locally.
3. Upload to S3 via `aws s3 cp` or console.
4. Set Terraform variables with the real bucket/URI/checksum.
5. Run Terraform apply.

## Runtime boundary

- `model_loader.py` — NOT modified. The v0.1 publication path produces packages that `model_loader.py` can load, but loader changes are deferred to PR 0039.
- `src/bremen/api/` — NOT modified.
- `src/bremen/config.py` — NOT modified. The `BREMEN_MODEL_URI` and `BREMEN_MODEL_CHECKSUM` env vars are added to Terraform but not yet read by runtime config. Runtime reads of these vars are deferred to a follow-up PR.
- `src/bremen/__main__.py` — NOT modified.

## Non-goals

- No training pipeline changes.
- No feature computation changes.
- No inference code.
- No H5 preflight.
- No preprocessing bridge.
- No API route changes.
- No clinical report.
- No Matador integration.
- No real training run.
- No committed model artifact.
- No real AWS upload by agent.
- No Terraform apply by agent.
- No changes to `model_loader.py`.
- No changes to runtime config reader (deferred).
- No changes to existing release helpers.

## Validation checklist

```bash
# 1-3) Baseline
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5) Compile check
python -m compileall src tests

# 6-7) New tests
python -m pytest -q tests/test_bremen_model_v01_publication.py
python -m pytest -q tests/test_bremen_model_package_terraform_env.py

# 8-10) Env var references in Terraform and config
grep -R "BREMEN_MODEL_VERSION\|BREMEN_MODEL_URI\|BREMEN_MODEL_CHECKSUM" infra/terraform tests src 2>/dev/null || true

# 11) ADR-0007 manifest field names present
grep -R "bremen.joblib.model_package\|model_version\|model_checksum\|model_filename\|feature_schema_version\|threshold_version\|threshold_value\|qc_criteria_version" src/training tests infra 2>/dev/null || true

# 12) No AWS/network calls
grep -R "boto3\|aws s3\|awscli\|put_object\|upload_file\|requests\|urllib" src/training tests infra 2>/dev/null || true

# 13) Runtime does not import training
grep -R "bremen.training" src/bremen/api src/bremen/model_loader.py src/bremen/__main__.py 2>/dev/null || true

# 14) No model artifacts in repo
find . -type f \( -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" -o -name "*.h5" -o -name "*.hdf5" \) -print

# 15) No secrets/account IDs
grep -R "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|aws_secret_access_key\|account ID\|registry URL\|[0-9]\{12\}\.dkr\.ecr" src tests config docs .github infra 2>/dev/null || true

# 16) Full test suite
python -m pytest -q
```

## Rollback plan

1. **Delete `src/bremen/training/publish_v01.py`**.
2. **Revert Terraform files** — remove the model_version/uri/checksum variables, env vars, and outputs.
3. **Delete test files**.
4. No other files affected. Existing release helpers, training pipeline, and runtime are untouched.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only allowed files changed. |
| **Manifest drift** | ADR-0007 fields preserved. `artifact_type == "bremen.joblib.model_package"`. |
| **No-S3 drift** | No `boto3`, `awscli`, `requests`, `urllib`. Dry-run only. Human-only upload. |
| **Runtime boundary drift** | `model_loader.py`, `api/`, `config.py` unchanged. |
| **Real artifact drift** | Smoke test is opt-in via `BREMEN_V01_JOBLIB_PATH`. Not run in CI. |
| **Validation drift** | All validation checks pass. No secrets/account IDs. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- v0.1 packaging would require committing the joblib to the repository.
- Publication would require agent-run AWS commands.
- Tests would require the real artifact in CI.
- Real H5/data would be needed.
- Inference code would need to change.
- Runtime API would need to change.
- `model_loader.py` changes would become broad (narrow smoke-test-only compatibility is OK but must be scoped).
- Terraform would need real secrets/account IDs.
- Checksum cannot be computed deterministically.
- Manifest cannot preserve ADR-0007 field names.
- S3 URI cannot be represented safely as configuration.
- Human-only steps cannot be separated from agent-implemented code.

## Follow-up PR 0037 summary

PR 0037 — H5 Preflight Gate. Target/control H5 metadata validation, same-patient/opposite-side checks, config integrity validation. No inference.

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0036-model-v01-package-publication/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0036-model-v01-package-publication/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Files read

- `.project-memory/project_contract.yml`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-two-image-build-training-pipeline-separation.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `src/bremen/model_package.py`
- `src/bremen/model_loader.py`
- `src/bremen/config.py`
- `src/bremen/__main__.py`
- `src/bremen/training/pipeline.py`
- `src/bremen/training/model_release.py`
- `src/bremen/training/publish_model_package.py`
- `infra/terraform/variables.tf`
- `infra/terraform/ecs.tf`
- `infra/terraform/apprunner.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/s3.tf`
- `infra/terraform/README.md`
- Existing tests

## Files written

- `.project-memory/pr/0036-model-v01-package-publication/PLAN.md` (this file)

## Files intentionally ignored

- All runtime source files not in allowed set.
- All training pipeline files not in allowed set.
- All docs, ADR, and roadmap files.
- Any H5/HDF5 or model artifact files.

## Boundary confirmations

- confirm: branch is `0036-model-v01-package-publication`: yes
- confirm: ADR-0007 runtime package manifest contract present: yes
- confirm: `model_package.py` validator present: yes
- confirm: PR 0035 release helpers present: yes
- confirm: no implementation files edited during planning: yes
- confirm: no model artifact planned for repo: yes
- confirm: no real H5/data access planned: yes
- confirm: no inference/API changes planned: yes
- confirm: no agent-run AWS/Terraform commands planned: yes
- confirm: no clinical claims planned: yes
- confirm: no git mutation commands run: yes
