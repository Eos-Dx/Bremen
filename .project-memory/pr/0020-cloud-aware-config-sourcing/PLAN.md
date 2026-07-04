# PR 0020 — Plan Cloud-Aware Config Sourcing

Author: plan
Mode: planning only
Branch: 0020-cloud-aware-config-sourcing

## Objective

Add cloud-aware runtime configuration sourcing to Bremen's config layer. The runtime will read deployment/cloud configuration from environment variables (matching the Terraform ECS env var shape from PR 0022A) without contacting AWS, S3, or any network service. Existing local config discovery remains intact.

## Context

PR 0019 added the API skeleton. PR 0022A added Terraform outputs and ECS task definition environment variables (`BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_VERSION`). PR 0022B added the ECR publish workflow.

PR 0020 was reserved in the ROADMAP Platform Readiness Track for cloud-aware config sourcing. This PR implements it: making the runtime code able to consume the cloud/runtime configuration shape created by 0022A.

The existing `src/bremen/config.py` handles local filesystem config discovery (YAML/TOML). This PR extends it to also read cloud/runtime config from environment variables, without modifying the local discovery behavior.

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`src/bremen/config.py`** — MODIFY. Add cloud/runtime config function(s) to the existing module.
2. **`tests/test_bremen_cloud_config.py`** — NEW. Tests for cloud config reading.

Optional only if strongly justified:

3. **`src/bremen/api/app.py`** — MODIFY to let `model_version()` handler report whether cloud model config is configured. No AWS lookup, no S3 read, no model manifest fetch, no false claim that model exists in S3.
4. **`tests/test_bremen_api_skeleton.py`** — MODIFY if API integration is added.

Default: do NOT modify API files. This PLAN.md recommends keeping the PR focused on the config layer only.

## Forbidden files

- `.github/**`, `infra/terraform/**`, `docs/**`, `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`
- `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`
- `Dockerfile`, `.dockerignore`, `requirements.txt`, `pyproject.toml`
- `config/**`, `examples/**`, `tests/data/**`
- `agents/**`
- Any H5/HDF5 files, joblib/pkl/npy/npz artifacts
- Terraform/CDK/CloudFormation/IaC files

## Required reads (completed for this PLAN.md)

- `src/bremen/config.py` — current import-safe config module, discovery contract
- `tests/test_bremen_config_loading.py` — existing test patterns
- `src/bremen/api/app.py` — optional integration point for model_version handler
- `tests/test_bremen_api_skeleton.py` — existing API tests
- `infra/terraform/outputs.tf` — Terraform outputs showing consumed values
- `infra/terraform/ecs.tf` — ECS environment variables being configured
- `infra/terraform/README.md` — deployment context
- `docs/adr/0004-bremen-configuration-management-strategy.md` — config management strategy
- `docs/adr/0007-model-artifact-lifecycle.md` — model package lifecycle
- `.project-memory/project_contract.yml` — safety invariants
- `AGENTS.md` — agent role definitions
- `pyproject.toml` — confirms no AWS SDK dependency

## Implementation phase assignment

- **Agent**: coder
- **Mode**: implementation

## Environment variable contract

These environment variables are defined by the Terraform ECS task definition (PR 0022A) and consumed by this PR:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BREMEN_MODEL_BUCKET` | Yes (for cloud config) | None | S3 bucket name for model packages. Bucket name only — reject `s3://` prefix and local paths. |
| `BREMEN_MODEL_PREFIX` | Yes (if bucket set) | `"model-packages/"` | Object key prefix within the bucket. Normalized to safe prefix style. |
| `BREMEN_MODEL_VERSION` | No | `""` (empty) | Optional model version string. |
| `BREMEN_MODEL_MANIFEST_KEY` | No | `"manifest.json"` | Manifest filename within the model package prefix. |
| `BREMEN_SERVICE_ENV` | No | `""` (empty) | Deployment environment label (dev, staging, prod). |
| `BREMEN_AWS_REGION` | No | `""` (empty) | AWS region (mirrors Terraform provider region). |

## Implementation design

### 1. Preserve existing config behavior

Existing config behavior must remain unchanged:
- `discover_config()` — explicit path → BREMEN_CONFIG env → bremen.yml → bremen.yaml → bremen.toml → ConfigNotFoundError.
- `load_config()` — explicit path loading.
- All existing `test_bremen_config_loading.py` tests must pass without modification.

### 2. Add cloud config function

Add a new public function to `src/bremen/config.py`:

```python
@dataclass(frozen=True)
class CloudConfig:
    """Runtime/cloud environment configuration.

    All fields are read from environment variables. No network calls,
    no AWS SDK, no model loading.
    """
    configured: bool                       # True if bucket is set
    model_bucket: str | None               # BREMEN_MODEL_BUCKET
    model_prefix: str                      # BREMEN_MODEL_PREFIX (default "model-packages/")
    model_version: str | None              # BREMEN_MODEL_VERSION
    model_manifest_key: str                # BREMEN_MODEL_MANIFEST_KEY (default "manifest.json")
    service_env: str | None                # BREMEN_SERVICE_ENV
    aws_region: str | None                 # BREMEN_AWS_REGION


def read_cloud_config() -> CloudConfig:
    """Read runtime/cloud configuration from environment variables.

    Returns a CloudConfig dataclass. If BREMEN_MODEL_BUCKET is not set
    or is empty, configured is False and all model fields are None.

    No network calls. No AWS SDK. No model loading. No H5/HDF5 reads.
    """
```

### 3. Validation rules

The function must enforce:

| Rule | Behavior |
|------|----------|
| Bucket absent → not configured | If `BREMEN_MODEL_BUCKET` is unset/empty/whitespace → `configured=False`, model fields `None` |
| Bucket present → configured | If `BREMEN_MODEL_BUCKET` is set → `configured=True` |
| Prefix default | If `BREMEN_MODEL_PREFIX` is unset → default `"model-packages/"` |
| Version optional | `BREMEN_MODEL_VERSION` may be empty string |
| Bucket rejects `s3://` | Raise `ConfigSyntaxError` if bucket starts with `s3://` |
| Bucket rejects absolute path | Raise `ConfigSyntaxError` if bucket is an absolute filesystem path (starts with `/`) or macOS `/Users/`, Linux `/home/` |
| Prefix rejects absolute path | Raise `ConfigSyntaxError` if prefix is an absolute path |
| Prefix normalization | Ensure prefix ends with `/` if non-empty |
| No network calls | No import of `boto3`, `requests`, `httpx`, `urllib` |
| No model deserialization | No import of `joblib`, `pickle` |

### 4. Import safety

The new function must follow the same import-safety rules as the existing module:
- No `joblib` or `pickle` imports at any level.
- No `boto3` or `botocore` imports.
- No `requests`, `httpx`, or `urllib` imports.
- No H5/HDF5 reads.
- The `os.environ` reads are safe (standard library).

### 5. Exception reuse

Reuse the existing `ConfigSyntaxError` for validation errors (bucket rejects `s3://`, bucket rejects absolute path, prefix rejects absolute path). This keeps the exception hierarchy consistent.

### 6. Optional API integration

If the plan chooses to update `src/bremen/api/app.py` (not recommended by default, but acceptable if small):

```python
def handle_model_version() -> ModelVersionResponse:
    from ..config import read_cloud_config  # lazy import
    
    cloud = read_cloud_config()
    if not cloud.configured:
        return ModelVersionResponse(
            model_configured=False,
            model_status="not_configured",
            # ... other fields None
        )
    return ModelVersionResponse(
        model_configured=True,
        model_version=cloud.model_version or "",
        model_status="configured",
        # ... other fields from cloud config
    )
```

Rules for API integration if implemented:
- No AWS lookup.
- No S3 read.
- No model manifest fetch.
- No false claim that model exists in S3 (model_configured=True means "config is present," not "model is present in S3").

## Testing strategy

### New test file: `tests/test_bremen_cloud_config.py`

Tests must cover:

1. **No env vars → not_configured** — No environment variables set. `read_cloud_config().configured` is `False`.
2. **Bucket + prefix → configured** — Set `BREMEN_MODEL_BUCKET` and `BREMEN_MODEL_PREFIX`. Verify configured=True, model_bucket, model_prefix.
3. **Bucket only → configured with default prefix** — Set only `BREMEN_MODEL_BUCKET`. Verify prefix defaults to `"model-packages/"`.
4. **Optional model version preserved** — Set `BREMEN_MODEL_VERSION`. Verify cloud_config.model_version matches.
5. **Prefix normalization** — Set prefix without trailing `/`. Verify it gets normalized.
6. **Bucket rejects `s3://`** — Set `BREMEN_MODEL_BUCKET` to `s3://my-bucket`. Verify `ConfigSyntaxError`.
7. **Bucket rejects local absolute path** — Set `BREMEN_MODEL_BUCKET` to `/Users/foo/model`. Verify `ConfigSyntaxError`.
8. **Prefix rejects absolute path** — Set `BREMEN_MODEL_PREFIX` to `/absolute/path/`. Verify `ConfigSyntaxError`.
9. **Import safety** — Verify no `boto3`, `joblib`, `pickle`, `requests`, `httpx`, `urllib` imports triggered by importing `bremen.config`.
10. **Existing config loading tests still pass** — `test_bremen_config_loading.py` unchanged and passing.
11. **No H5/HDF5/joblib/pickle references** in the new test file or modified source.
12. **No Terraform/GitHub/Docker files changed** — verify via `git diff --name-only`.

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5-6) File existence
test -f src/bremen/config.py || exit 1
test -f tests/test_bremen_cloud_config.py || exit 1

# 7-13) Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_cloud_config.py
python -m pytest -q tests/test_bremen_config_loading.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_model_package.py
python -m pytest -q tests/test_bremen_dependency_hygiene.py
python -m pytest -q
python -m bremen --help

# 14) No AWS/network imports in new/modified source
grep -R -I -n "boto3\|botocore\|requests\|httpx\|urllib\|s3://" src/bremen tests/test_bremen_cloud_config.py || true

# 15) No joblib/pickle in new/modified source
grep -R -I -n "joblib\.load\|pickle\.load\|import joblib\|import pickle" src/bremen tests/test_bremen_cloud_config.py || true

# 16) No H5/HDF5 references
grep -R -I -n "\.h5\|\.hdf5\|h5py" src/bremen tests/test_bremen_cloud_config.py || true

# 17) No forbidden file changes
git diff --name-only -- .github infra/terraform docs ROADMAP.md Dockerfile requirements.txt pyproject.toml config examples tests/data agents
# Must return nothing

# 18) No model/terraform/tfstate artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true

# 19) .DS_Store check
find . -name ".DS_Store" -print
```

## Non-goals

- No AWS/S3 calls.
- No `boto3`/`botocore` dependency.
- No network calls.
- No model package download.
- No model deserialization.
- No `joblib.load()`.
- No inference.
- No preprocessing.
- No H5/HDF5 reads.
- No Matador integration.
- No Terraform changes.
- No GitHub Actions changes.
- No Dockerfile/dependency changes.
- No docs/ADR/ROADMAP changes.
- No clinical claims.
- No APRANA.
- No modification of the existing local config discovery contract.

## Rollback plan

1. **Revert `src/bremen/config.py`** — remove the cloud config function and CloudConfig dataclass. The existing config discovery functions remain unchanged.
2. **Revert `tests/test_bremen_cloud_config.py`** — delete the file.
3. **Revert API files** — if modified, revert to pre-PR-0020 version.

## Follow-up PRs

- **Future PR** — Runtime model package loader integration using `read_cloud_config()` to locate model packages in S3.
- **Future PR** — PR 0019 API integration to surface cloud config status.
- **Future human-only action** — Human deploys to ECS with configured environment variables.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only config.py, test file, and optionally API files changed. |
| **Config contract drift** | Existing discover_config/load_config unchanged. Cloud config is additive. |
| **Environment variable drift** | BREMEN_MODEL_BUCKET, BREMEN_MODEL_PREFIX, BREMEN_MODEL_VERSION consumed. BREMEN_MODEL_MANIFEST_KEY, BREMEN_SERVICE_ENV, BREMEN_AWS_REGION optional. |
| **Validation drift** | Bucket rejects s3://, absolute paths. Prefix normalized. Not-configured when bucket absent. |
| **Network drift** | No boto3/botocore/requests/httpx/urllib. No AWS calls. |
| **Model loading drift** | No joblib/pickle. No deserialization. No inference. |
| **Infrastructure drift** | No Terraform/CI/Docker/docs changes. |
| **Test drift** | Full coverage of cloud config scenarios. Existing config tests pass. |
| **Validation drift** | All 19 validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan does not add runtime config behavior (docs-only).
- Plan modifies Terraform files, GitHub Actions, Dockerfile, or pyproject.toml.
- Plan adds AWS SDK or network dependency.
- Plan reads S3 or downloads model packages.
- Plan loads model/joblib/pickle artifacts.
- Plan modifies H5 files or commits model artifacts.
- Plan changes docs/ADR/ROADMAP.
- Plan changes existing config loading behavior (backward incompatible change).
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

### Allowed files
1. `src/bremen/config.py` — MODIFY (add `read_cloud_config()` function and `CloudConfig` dataclass)
2. `tests/test_bremen_cloud_config.py` — NEW (cloud config tests)

### Environment variable contract
- Required: `BREMEN_MODEL_BUCKET` (bucket name only, not s3:// URL)
- Required (if bucket set): `BREMEN_MODEL_PREFIX` (defaults to `"model-packages/"`)
- Optional: `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_MANIFEST_KEY`, `BREMEN_SERVICE_ENV`, `BREMEN_AWS_REGION`

### Config sourcing summary
- New `read_cloud_config()` function returns `CloudConfig` dataclass.
- No network calls, no AWS SDK, no model loading.
- Validates bucket name (rejects `s3://`, absolute paths, local machine paths).
- Existing `discover_config()` and `load_config()` unchanged.
- Existing config tests continue passing.

### Testing summary
12 test scenarios: not_configured when no env vars, configured when bucket+prefix set, default prefix, optional version, prefix normalization, s3:// rejection, absolute path rejection (bucket + prefix), import safety, existing config tests pass, no H5/model references.

### Validation summary
19 checks: git state, file existence, compileall, all test suites, CLI help, AWS/network grep (no matches), joblib/pickle grep (no matches), H5 grep (no matches), forbidden file check, artifact scan, .DS_Store.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0020-cloud-aware-config-sourcing/PLAN.md`
2. Human runs: `git add .project-memory/pr/0020-cloud-aware-config-sourcing/PLAN.md`
3. Human runs: `git commit -m "PR 0020 — Plan cloud-aware config sourcing"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the allowed files.

## Files read

- `src/bremen/config.py`
- `tests/test_bremen_config_loading.py`
- `src/bremen/api/app.py`
- `tests/test_bremen_api_skeleton.py`
- `infra/terraform/outputs.tf`
- `infra/terraform/ecs.tf`
- `infra/terraform/README.md`
- `docs/adr/0004-bremen-configuration-management-strategy.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `.project-memory/project_contract.yml`
- `AGENTS.md`
- `pyproject.toml`

## Files written

- `.project-memory/pr/0020-cloud-aware-config-sourcing/PLAN.md` (this file)

## Files intentionally ignored

- All Infrastructure files (CI, Docker, Terraform)
- All docs files not in required reads
- All existing source files not in allowed set
- Any H5/HDF5 or model artifact files

## Boundary confirmations

- confirm: real runtime config feature planned: yes
- confirm: existing config loading preserved: yes
- confirm: Terraform/ECS env names consumed: yes
- confirm: no AWS/S3/network calls planned: yes
- confirm: no model loading/inference planned: yes
- confirm: no H5/HDF5 reads planned: yes
- confirm: no Terraform/GitHub Actions changes planned: yes
- confirm: no Docker/dependency changes planned: yes
- confirm: no docs/ADR/ROADMAP changes planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
