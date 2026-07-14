# PR 0040 — Plan S3 Model Download / Startup Staging

Author: plan
Mode: planning only
Branch: 0040-s3-model-startup-staging

## Objective

Make `s3://` model URIs usable at service startup by adding safe S3 model artifact download and local staging, while preserving the checksum-before-deserialization boundary and keeping local/file model loading behavior from PR 0039 unchanged.

## Current state from PR 0039

- PR 0039 added model startup state (`ModelState`), portable-logreg inference, and prediction API wiring.
- PR 0039 intentionally deferred S3 download — `s3://` URIs log a message and mark model not ready.
- Current real Terraform config points to an S3 URI (`s3://matur-misc-uk/bremen/models/bremen-xrd-classifier/v0.1/...`), so the model would remain not ready in a real cloud deployment.
- Local/file model loading works correctly with checksum verification before `joblib.load()`.
- PR 0040 closes the S3 download gap only — no inference changes, no feature schema changes, no training changes.

## Dependency decision

**`boto3` is NOT present** in `requirements.txt` or `pyproject.toml`. It must be added for S3 download. The decision is:

- **Add `boto3>=1.35`** to `requirements.txt` (not `pyproject.toml`, to keep runtime core dependencies minimal). This follows the existing pattern where `requirements.txt` includes additional runtime dependencies beyond the pyproject.toml core.
- `botocore` is an implicit dependency of `boto3` and does not need a separate entry.
- Tests use `unittest.mock` (monkeypatch/fake) — no real AWS calls, no credentials.

## Startup model loading contract

```
read BREMEN_MODEL_URI / BREMEN_MODEL_VERSION / BREMEN_MODEL_CHECKSUM
if local path or file://:
    resolve local file (existing behavior, unchanged)
if s3://:
    download object to local staging temp file (new in PR 0040)
verify SHA-256 against BREMEN_MODEL_CHECKSUM (existing, unchanged)
only after checksum passes:
    call joblib.load() (existing, unchanged)
validate portable-logreg model package (existing, unchanged)
set model_ready=true (existing, unchanged)
```

## Staging directory contract

- Default staging path: `tempfile.gettempdir() / "bremen-models"`.
- Optional override: `BREMEN_MODEL_STAGING_DIR` environment variable.
- Directory created if missing.
- Download to a temporary file first, atomically rename to final path after download completes.
- Delete temporary files and bad checksum files on failure.
- No staging under the repository. No committed staged files.
- No logging of secret values or credentials.

## S3 fetch implementation plan

**New file**: `src/bremen/model_artifacts.py`

```python
"""Model artifact staging utilities — local and S3 download.

Safe S3 model artifact download and staging.
Verifies SHA-256 checksum before returning the staged path.
No deserialization — returns a file path only.
"""

def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse an ``s3://bucket/key`` URI into (bucket, key).
    
    Raises ValueError on invalid or empty bucket/key.
    """

def stage_model_artifact(
    uri: str,
    expected_checksum: str,
    staging_dir: str | Path | None = None,
) -> Path:
    """Download and stage a model artifact, verifying its checksum.
    
    Supports:
    - Local filesystem paths (unchanged behavior).
    - ``file://`` URIs (unchanged behavior).
    - ``s3://`` URIs (new in PR 0040).
    
    Returns the path to the staged file.
    Raises ValueError on checksum mismatch or download failure.
    """

def stage_s3_model_artifact(
    bucket: str,
    key: str,
    expected_checksum: str,
    staging_dir: Path,
    *,
    s3_client=None,
) -> Path:
    """Download an S3 object, verify SHA-256, stage locally.
    
    Uses ``boto3.client('s3')`` by default.
    ``s3_client`` parameter is injectable for testing (monkeypatch/mock).
    
    Downloads to a temp file, verifies checksum, then renames to final path.
    Deletes temp file on checksum mismatch.
    """

def verify_file_sha256(path: Path, expected_checksum: str) -> None:
    """Verify a file's SHA-256 checksum.
    
    Supports ``sha256:<hex>`` and bare hex format.
    Raises ValueError on mismatch. Deletes the file on mismatch.
    """
```

**Key design decisions**:
- `s3_client` parameter is injectable for tests — no real AWS calls in CI.
- Uses AWS default credential provider chain (no hardcoded credentials).
- No account IDs. No registry URLs. No secrets.
- The function returns a `Path`, not a loaded model — the caller (`ModelState`) handles `joblib.load()` after checksum verification.

## Checksum/trust boundary

- **No `joblib.load()` until after checksum verification.** This is enforced by `stage_model_artifact()` which verifies checksum before returning the path. `ModelState.load_at_startup()` calls checksum verification before `joblib.load()`.
- Checksum format supports `sha256:<hex>` (existing format from BREMEN_MODEL_CHECKSUM) and bare hex.
- Checksum mismatch: delete staged candidate, raise ValueError, model remains not ready.
- Checksum failure is a hard load failure, not a warning.

## Model state integration

**File**: `src/bremen/api/model_state.py` — MODIFY (narrow update)

Replace the `s3://` placeholder block with:

```python
if str(model_uri).startswith("s3://"):
    from ..model_artifacts import stage_model_artifact  # noqa: PLC0415
    staged_path = stage_model_artifact(
        uri=str(model_uri),
        expected_checksum=model_checksum,
        staging_dir=staging_dir,
    )
```

Add optional `staging_dir` parameter to `load_at_startup()`.

**No other changes to model_state.py needed.** The existing local path handling, checksum verification, `joblib.load()`, portable-logreg validation, and `is_ready()` logic remain unchanged.

## API behavior

No changes to API routes or response shapes:
- `/health` continues to include `model_ready`.
- `/model/version` remains safe, no secrets exposed.
- POST `/predictions` returns 503 when model not ready.
- When startup S3 load succeeds, prediction works as normal.
- No route schema expansion.

## Terraform/runtime config

- Optionally add `BREMEN_MODEL_STAGING_DIR` to `infra/terraform/variables.tf` if the coder determines it's useful. Not required by default — the `tempfile.gettempdir()` default is sufficient.
- No changes to existing model URI/checksum/version values.
- No secrets. No account IDs. No backend/provider changes.

## Test plan

**New file**: `tests/test_bremen_model_startup_staging.py`

1. `test_parse_s3_uri_valid` — `parse_s3_uri("s3://bucket/key/path")` returns `("bucket", "key/path")`.
2. `test_parse_s3_uri_empty_bucket_rejected` — `s3:///key` raises `ValueError`.
3. `test_parse_s3_uri_empty_key_rejected` — `s3://bucket/` raises `ValueError`.
4. `test_local_path_stages_correctly` — A local file path is staged (copied) to staging dir, verification passes.
5. `test_s3_download_with_fake_client` — Fake `s3_client.get_object()` returns bytes, file staged, checksum verified.
6. `test_checksum_verified_before_return` — `verify_file_sha256()` raises on mismatch.
7. `test_checksum_mismatch_deletes_bad_file` — After mismatch, the staged file no longer exists.
8. `test_ModelState_loads_fake_s3_object` — Monkeypatch `stage_model_artifact`, verify `ModelState.is_ready()` after load.
9. `test_ModelState_not_ready_on_download_failure` — Monkeypatch to fail, verify `is_ready()` is `False`.
10. `test_no_real_aws_credentials_required` — Tests use mocks only; no `boto3.Session()` default chain touched in CI.

## Allowed implementation files

1. `src/bremen/model_artifacts.py` — NEW
2. `src/bremen/api/model_state.py` — MODIFY (wire S3 download)
3. `tests/test_bremen_model_startup_staging.py` — NEW
4. `requirements.txt` — MODIFY (add `boto3>=1.35`)
5. `infra/terraform/variables.tf` — MODIFY (optional, add `BREMEN_MODEL_STAGING_DIR`)

## Forbidden files

- Any real `*.joblib`, `*.pkl`, `*.npy`, `*.npz`, `*.h5`, `*.hdf5`
- `src/bremen/training/**`
- `src/bremen/inference.py` (unchanged)
- `src/bremen/api/inference_handler.py` (unchanged)
- `src/bremen/api/app.py` (unchanged)
- `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md` (unchanged)
- `.github/**`, Dockerfiles
- `.gitignore`
- Secrets, account IDs, access keys, registry URLs
- Matador integration files, clinical report files

## Safety/claims

- No diagnosis claim.
- No clinical validation claim.
- No model performance claim.
- No claim replacing MRI, biopsy, radiologist, or clinician.
- PR 0040 is infrastructure to load the already-delivered research baseline safely.
- S3 download uses AWS SDK default credential chain — no credentials hardcoded.
- Checksum verification prevents loading corrupted or tampered artifacts.

## Validation checklist

```bash
# 1-3) Baseline
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Compile check
python -m compileall src tests

# 5-12) Test suites
python -m pytest -q tests/test_bremen_model_startup_staging.py
python -m pytest -q tests/test_bremen_inference_integration.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_v01_schema_rebaseline.py
python -m pytest -q tests/test_bremen_preprocessing_bridge.py
python -m pytest -q tests/test_bremen_h5_preflight.py
python -m pytest -q

# 13) S3 staging references
grep -R "stage_model_artifact\|stage_s3_model_artifact\|parse_s3_uri\|BREMEN_MODEL_STAGING_DIR\|download_file\|download_fileobj\|get_object" src/bremen tests 2>/dev/null || true

# 14) Checksum/trust boundary
grep -R "joblib.load\|verify.*checksum\|sha256\|checksum" src/bremen tests 2>/dev/null || true

# 15) No secrets/credentials in source
grep -R "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|aws_secret_access_key\|aws_access_key_id\|[0-9]\{12\}\.dkr\.ecr\|/Users/" src tests docs infra .github 2>/dev/null || true

# 16) No sklearn/training in API
grep -R "from sklearn\|import sklearn\|fit(\|fit_transform\|bremen.training" src/bremen/api src/bremen/inference.py tests 2>/dev/null || true

# 17-18) No tracked artifacts
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) -not -path "./.git/*" -not -path "./venv/*" -print

# 19) No forbidden file changes
git diff --name-only -- src/bremen/training docs/adr ROADMAP.md docs/architecture.md .github Dockerfile Dockerfile.training .project-memory/project_contract.yml
```

## Rollback plan

1. **Revert the PR 0040 commit** — service returns to PR 0039 behavior: local/file model loading works, `s3://` marks model not ready, predictions return 503.
2. No S3 artifacts deleted by code except failed local staging temp files.
3. `requirements.txt` reverts to pre-boto3 state.

## Follow-up PRs

- App Runner/ECS runtime smoke test with real S3 model.
- Matador integration for result recording.
- Clinical/report contract for decision-support output.
- Async job queue if synchronous inference is insufficient.
- Model v1.0 retraining with improved validation.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `model_artifacts.py`, `model_state.py` (narrow), `test_bremen_model_startup_staging.py`, `requirements.txt`, and optionally `variables.tf` changed. |
| **S3 fetch drift** | `parse_s3_uri()`, `stage_model_artifact()`, `stage_s3_model_artifact()`, `verify_file_sha256()`. Injectable S3 client for testing. No hardcoded credentials. |
| **Checksum drift** | Verified before `joblib.load()`. Mismatch deletes file and raises. |
| **Model state drift** | Wire S3 download into `load_at_startup()`. Local/file behavior unchanged. `is_ready()` false on failure. |
| **Dependency drift** | `boto3>=1.35` added to `requirements.txt`. Justified — S3 SDK required for download. |
| **API behavior drift** | No route changes. 503 when not ready preserved. Health model_ready preserved. |
| **Test drift** | 10 scenarios with fake S3 client. No real AWS calls. No real model artifact. |
| **Validation drift** | All validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Checksum verification cannot happen before `joblib.load()`.
- Tests require real AWS credentials or make real S3/network calls.
- S3 URI parsing is ambiguous or unsafe.
- Startup load falls back to deserializing unchecked artifact.
- Model loads per request.
- Prediction proceeds when model not ready.
- Real model artifact must be committed.
- Secrets/account IDs are needed.
- Feature schema or inference behavior changes are needed.
- Training code changes are needed.

## Decisions summary

| Decision | Value |
|----------|-------|
| Dependency | Add `boto3>=1.35` to `requirements.txt` (not pyproject.toml). S3 SDK required for download. |
| Module name | `src/bremen/model_artifacts.py` (new) |
| Model state change | Narrow: wire `stage_model_artifact()` for `s3://` URIs. Local behavior unchanged. |
| Staging dir | `tempfile.gettempdir() / "bremen-models"`, overridable via `BREMEN_MODEL_STAGING_DIR`. |
| S3 auth | AWS default credential provider chain. No hardcoded credentials. |
| Testing | Fake/injectable S3 client via `unittest.mock`. No real AWS calls. |
| API routes | Unchanged. 503 when not ready preserved. |
| Terraform | Optionally add `BREMEN_MODEL_STAGING_DIR`. No other changes. |

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0040-s3-model-startup-staging/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0040-s3-model-startup-staging/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after precommit-review.

## Files read

- `.project-memory/project_contract.yml`
- `.project-memory/pr/0039-inference-integration/PLAN.md`
- `.project-memory/pr/0039-inference-integration/reviews/precommit-review.yml`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-two-image-build-training-pipeline-separation.md`
- `docs/adr/0010-v01-feature-schema-rebaseline.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `src/bremen/api/model_state.py`
- `src/bremen/model_loader.py`
- `src/bremen/model_package.py`
- `src/bremen/inference.py`
- `src/bremen/api/inference_handler.py`
- `src/bremen/api/app.py`
- `src/bremen/config.py`
- `src/bremen/api/` (all files)
- `infra/terraform/variables.tf`
- `infra/terraform/apprunner.tf`
- `infra/terraform/ecs.tf`
- `.gitignore`
- `requirements.txt`
- `pyproject.toml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0040-s3-model-startup-staging/PLAN.md` (this file)

## Boundary confirmations

- confirm: branch is `0040-s3-model-startup-staging`: yes
- confirm: PR 0039 model state/inference present: yes
- confirm: `boto3` absent from dependencies — will add narrowly: yes
- confirm: no real AWS credentials or real S3 calls in tests: yes
- confirm: checksum verified before `joblib.load()`: yes
- confirm: no inference/feature schema/training changes: yes
- confirm: no API route changes: yes
- confirm: no model artifact committed: yes
- confirm: no git mutation commands run: yes
