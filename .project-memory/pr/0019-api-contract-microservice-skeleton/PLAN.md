# PR 0019 — Plan API Contract and Async Microservice Skeleton

Author: plan
Mode: planning only
Branch: 0019-api-contract-microservice-skeleton

## Objective

Add Bremen's API contract (`docs/api_contract.md`) and a minimal async microservice skeleton (standard-library-only route-shaped handlers, in-memory job store). This is a Platform Readiness Track PR that delegates real inference/H5/model-loading to later PRs.

## Context

PR 0012 closed G-API-1 (DECIDED: async submit → `job_id` → poll) and G-API-2 (DECIDED: ECS Fargate). PR 0013 added local model package validation helpers (`model_package.py`).

The current `docs/architecture.md` states:

> DRAFT — not a binding contract until PR 0019 is merged.

PR 0019 resolves that dependency. It creates the API contract document and a stub implementation with route-shaped handler functions, an in-memory async job store, and contract tests.

**No web framework is available in the existing dependency set** (pyproject.toml has no FastAPI/Flask/Starlette/uvicorn). The skeleton uses standard-library-only dataclasses and dict builders. Route-shaped handler functions are designed to be pluggable into any web framework when one is selected.

## Numbering rule

PR 0019 is an already reserved Platform Readiness Track number. PR 0019–0024 are not renumbered. Product Track sequence positions (items 1–12) are ordering, not PR identifiers.

## Exact allowed implementation files

The coder may create or modify exactly these files:

1. **`docs/api_contract.md`** — NEW. API contract document.
2. **`src/bremen/api/__init__.py`** — NEW. API package init.
3. **`src/bremen/api/schemas.py`** — NEW. Request/response schemas as dataclasses.
4. **`src/bremen/api/jobs.py`** — NEW. In-memory async job store.
5. **`src/bremen/api/app.py`** — NEW. Route-shaped handler functions.
6. **`tests/test_bremen_api_contract.py`** — NEW. Contract document tests.
7. **`tests/test_bremen_api_skeleton.py`** — NEW. Skeleton handler tests.

Optional only if strongly justified:
8. `src/bremen/__main__.py` — MODIFY only if needed to expose API test hooks.
9. `tests/test_bremen_cli_entrypoint.py` — MODIFY only if CLI command surface changes.

## Exact forbidden files

- `ROADMAP.md`, `docs/architecture.md`, `docs/adr/**`
- `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`
- `.github/**`, `Dockerfile`, `.dockerignore`
- `requirements.txt`, `pyproject.toml`, `sonar-project.properties`, `environment.yml`, `Makefile`
- `config/**`, `examples/**`, `tests/data/**`
- `agents/**`
- Any H5/HDF5 files
- Any model/joblib/pkl/npy/npz artifacts
- Terraform/CDK/CloudFormation/IaC files

## Required reads (completed for this PLAN.md)

- `ROADMAP.md` — Platform Readiness Track PR 0019 entry
- `docs/architecture.md` — existing API Surface (Draft) section
- `docs/adr/0003-bremen-microservice-api-architecture.md` — endpoint skeleton, mandatory response fields
- `docs/adr/0007-model-artifact-lifecycle.md` — model package lifecycle
- `.project-memory/project_contract.yml` — safety invariants
- `src/bremen/model_package.py` — existing validation module for safe imports
- `tests/test_bremen_model_package.py` — existing test patterns
- `src/bremen/config.py` — existing module design patterns
- `src/bremen/__main__.py` — CLI entrypoint
- `pyproject.toml` — confirms no web framework in dependencies
- `AGENTS.md` — agent role definitions

## Implementation phase assignment

- **Agent**: coder
- **Mode**: implementation

## API contract: `docs/api_contract.md`

The coder creates this file with the following endpoints and shapes.

### 1. `GET /health`

Purpose: Service health check. No model inference. No H5 inspection.

Response shape:
```json
{
  "status": "ok",
  "service": "bremen",
  "version": "<package_version or 'unknown'>",
  "timestamp": "<ISO-8601 UTC>"
}
```

### 2. `GET /model/version`

Purpose: Expose configured model package metadata/status. Must not call `joblib.load()`. Must not deserialize model artifacts.

Response shape:
```json
{
  "model_configured": false,
  "model_version": null,
  "model_checksum": null,
  "feature_schema_version": null,
  "threshold_version": null,
  "threshold_value": null,
  "qc_criteria_version": null,
  "model_status": "not_configured"
}
```

`model_status` values: `not_configured`, `configured`, `invalid`, `unavailable`.

Future integration with `model_package.validate_model_package()` is described but not fully implemented unless purely local and safe (i.e., the handler can safely report the current stub/not_configured state).

### 3. `POST /predictions`

Purpose: Submit asynchronous prediction job. Request must use opaque platform references, not local machine paths. Request must not read H5/HDF5, run preprocessing, run inference, train, call Matador, or call AWS/S3/network.

Request shape:
```json
{
  "target_scan_ref": "<opaque_platform_reference>",
  "control_scan_ref": "<opaque_platform_reference>",
  "request_id": "<optional_idempotency_key>"
}
```

Rules:
- `target_scan_ref` and `control_scan_ref` are required and must be explicit (the runtime contract distinguishes target from control).
- `request_id` is optional for idempotency.
- No local filesystem paths accepted as platform contract.
- Additional metadata fields are allowed only if non-clinical and non-diagnostic.

Response shape (HTTP 202 semantics):
```json
{
  "job_id": "<uuid>",
  "status": "accepted",
  "submitted_at": "<ISO-8601 UTC>",
  "links": {
    "poll": "/predictions/<job_id>"
  }
}
```

### 4. `GET /predictions/{job_id}`

Purpose: Poll asynchronous job status.

Response shape:
```json
{
  "job_id": "<uuid>",
  "status": "<status_value>",
  "submitted_at": "<ISO-8601 UTC or null>",
  "updated_at": "<ISO-8601 UTC or null>",
  "result": null,
  "error": null
}
```

`status` values: `accepted`, `queued`, `running`, `completed`, `failed`, `not_found`.

When `status` is `completed`, the `result` field must include all project_contract-required prediction fields:
```json
{
  "prediction_id": "<uuid>",
  "model_version": "<string>",
  "model_checksum": "<string>",
  "feature_schema_version": "<string>",
  "threshold_version": "<string>",
  "threshold_value": <number>,
  "qc_status": "<string>",
  "qc_flags": "<list or dict>"
}
```

Rules:
- Stub must not fabricate completed predictions unless explicitly testing schema-only fixtures.
- No clinical diagnosis wording (no "cancer detected", no replacement of MRI/biopsy/radiologist/clinician judgment).
- `not_found` status for unknown/synthetic `job_id`.

## Microservice skeleton: `src/bremen/api/`

### Design: standard-library only

No web framework dependency. Route-shaped functions accept and return typed dicts/dataclasses.

### `src/bremen/api/__init__.py`

Package init. Exports key types and functions for external use.

### `src/bremen/api/schemas.py`

Request/response schemas as dataclasses:

```python
@dataclass
class HealthResponse:
    status: str
    service: str
    version: str | None
    timestamp: str

@dataclass
class ModelVersionResponse:
    model_configured: bool
    model_version: str | None
    model_checksum: str | None
    feature_schema_version: str | None
    threshold_version: str | None
    threshold_value: float | None
    qc_criteria_version: str | None
    model_status: str  # "not_configured" | "configured" | "invalid" | "unavailable"

@dataclass
class PredictionRequest:
    target_scan_ref: str
    control_scan_ref: str
    request_id: str | None = None

@dataclass
class PredictionResponse:
    job_id: str
    status: str
    submitted_at: str
    links: dict | None = None

@dataclass
class PredictionStatusResponse:
    job_id: str
    status: str
    submitted_at: str | None
    updated_at: str | None
    result: dict | None = None
    error: str | None = None

@dataclass
class CompletedResult:
    prediction_id: str
    model_version: str
    model_checksum: str
    feature_schema_version: str
    threshold_version: str
    threshold_value: float
    qc_status: str
    qc_flags: list | dict
```

### `src/bremen/api/jobs.py`

In-memory async job store:

```python
class InMemoryJobStore:
    """In-memory job store. Not persistent — for test/stub use only."""

    def create_job(self, request_id: str | None = None) -> JobRecord: ...
    def get_job(self, job_id: str) -> JobRecord | None: ...
    def update_status(self, job_id: str, status: str, **kwargs) -> None: ...
```

Uses an in-memory `dict` keyed by UUID string. No persistence. No background worker. No concurrency handling beyond basic safety.

`JobRecord` dataclass:
```python
@dataclass
class JobRecord:
    job_id: str
    status: str
    submitted_at: str
    updated_at: str | None
    request: PredictionRequest | None
    result: CompletedResult | None
    error: str | None
```

### `src/bremen/api/app.py`

Route-shaped handler functions:

```python
def handle_health() -> HealthResponse:
    """Return service health information."""
    ...

def handle_model_version() -> ModelVersionResponse:
    """Return configured model package metadata (stub)."""
    ...

def handle_submit_prediction(
    request: PredictionRequest, job_store: InMemoryJobStore
) -> PredictionResponse:
    """Create an asynchronous prediction job."""
    ...

def handle_get_prediction(
    job_id: str, job_store: InMemoryJobStore
) -> PredictionStatusResponse:
    """Return the status of an existing prediction job."""
    ...
```

All handlers are stateless pure functions (except job_store parameter). No HTTP binding here — the handler functions are designed to be called by any future web framework adapter.

### Model package boundary

- The API skeleton may import safe types from `src/bremen/model_package.py` (e.g., `ModelPackageSummary`) only if useful for the `GET /model/version` stub.
- It must not validate a real package by default.
- It must not call `joblib.load()`.
- It must not import `joblib` or `pickle`.
- It must not deserialize any model artifact.

### Async job behavior

1. `handle_submit_prediction` creates a UUID `job_id`, stores a `JobRecord` with status `"accepted"`, returns `PredictionResponse`.
2. `handle_get_prediction` looks up the `JobRecord` by `job_id`. Returns `not_found` status for unknown IDs.
3. No background worker transitions jobs from `"accepted"` to any other status in this PR. Jobs remain at `"accepted"` or may be manually set for testing.
4. No preprocessing, inference, H5 loading, model loading, or Matador call.

## Contract tests

### `tests/test_bremen_api_contract.py`

Test the contract document:

1. `docs/api_contract.md` exists.
2. Endpoint names documented: `/health`, `/model/version`, `/predictions`, `/predictions/{id}`.
3. Async submit → `job_id` → poll pattern documented.
4. Mandatory completed-result fields documented (all 7 project_contract fields).
5. Target/control refs required and explicit in request schema.
6. Local machine paths not required by the public API contract.
7. No clinical/diagnostic wording in the contract.
8. No Aramis identity in the contract.
9. After reviewing the contract with grep, verify no prohibited claims.

### `tests/test_bremen_api_skeleton.py`

Test the handler functions:

1. `handle_health()` returns `HealthResponse` with expected shape.
2. `handle_model_version()` returns `ModelVersionResponse` with `model_configured=False` and `model_status="not_configured"`.
3. `handle_submit_prediction()` returns `PredictionResponse` with a UUID `job_id` and `status="accepted"`.
4. `handle_get_prediction()` with valid `job_id` returns the expected status.
5. `handle_get_prediction()` with invalid/missing `job_id` returns `status="not_found"`.
6. `InMemoryJobStore.create_job()` creates distinct job_ids.
7. `InMemoryJobStore.get_job()` returns `None` for unknown IDs.
8. Target/control refs in `PredictionRequest` are required.
9. `CompletedResult` schema includes all mandatory prediction response fields.
10. No `joblib.load()` or `pickle.load()` in any API source file.
11. No `joblib` or `pickle` imports in any API source file.
12. No H5/HDF5 references in any API source file.
13. No AWS/S3/network calls in any API source file.
14. No clinical/diagnostic wording in any API source or test file.
15. No Aramis identity in any API source or test file.
16. Import safety — importing `bremen.api` does not trigger joblib/pickle/H5/AWS side effects.

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1-2) Baseline state
git rev-parse --verify HEAD
git branch --show-current

# 3-4) Working tree
git status --short
git diff --name-only

# 5-11) File existence
test -f docs/api_contract.md || exit 1
test -f src/bremen/api/__init__.py || exit 1
test -f src/bremen/api/schemas.py || exit 1
test -f src/bremen/api/jobs.py || exit 1
test -f src/bremen/api/app.py || exit 1
test -f tests/test_bremen_api_contract.py || exit 1
test -f tests/test_bremen_api_skeleton.py || exit 1

# 12-17) Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_api_contract.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_model_package.py
python -m pytest -q tests/test_bremen_config_loading.py
python -m pytest -q tests/test_bremen_import_identity.py
python -m pytest -q

# 18) CLI help still works
python -m bremen --help

# 19) Security: no joblib/pickle in API source or tests
grep -R -I -n -E "joblib\.load|pickle\.load|import joblib|from joblib|import pickle|from pickle" \
  src/bremen/api tests/test_bremen_api_contract.py tests/test_bremen_api_skeleton.py 2>/dev/null || true

# 20) No H5/HDF5 in API source or tests
grep -R -I -n -E "\.h5|\.hdf5|h5py" \
  src/bremen/api tests/test_bremen_api_contract.py tests/test_bremen_api_skeleton.py 2>/dev/null || true

# 21) No network/AWS/S3 in API source or tests
grep -R -I -n -E "boto3|requests|urllib|httpx|s3|aws" \
  src/bremen/api tests/test_bremen_api_contract.py tests/test_bremen_api_skeleton.py 2>/dev/null || true

# 22) No prohibited clinical/diagnostic wording
grep -R -I -n -E "diagnos|cancer detected|replace MRI|replace biopsy|replace radiologist|replace clinician" \
  docs/api_contract.md src/bremen/api tests/test_bremen_api_contract.py tests/test_bremen_api_skeleton.py 2>/dev/null || true

# 23) No Aramis identity
grep -R -I -n -E "Aramis|aramis" \
  docs/api_contract.md src/bremen/api tests/test_bremen_api_contract.py tests/test_bremen_api_skeleton.py 2>/dev/null || true

# 24) No forbidden file changes
git diff --name-only -- ROADMAP.md docs/architecture.md docs/adr README.md docs/roadmap.md docs/machine_learning_concept.md docs/repository_cleanup.md .github Dockerfile .dockerignore requirements.txt pyproject.toml sonar-project.properties environment.yml Makefile config examples tests/data agents
# Must return nothing

# 25) No model artifacts created
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz)$" || true

# 26) No H5/model artifacts in working tree
find . -path "./.git" -prune -o -path "./venv" -prune -o -path "./.venv" -prune -o -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) -print

# 27) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

If the API contract or skeleton contains errors:

1. **Revert `docs/api_contract.md`** — delete the file.
2. **Revert `src/bremen/api/`** — delete the entire `api/` directory.
3. **Revert test files** — `tests/test_bremen_api_contract.py` and `tests/test_bremen_api_skeleton.py`.

## Non-goals

- No real HTTP server dependency (no web framework added).
- No dependency additions (pyproject.toml, requirements.txt unchanged).
- No CI/Docker changes.
- No Terraform/IaC.
- No AWS/S3/network calls.
- No Matador integration.
- No H5/HDF5 reads.
- No preprocessing or feature extraction.
- No model deserialization or `joblib.load()`.
- No `joblib` or `pickle` imports.
- No training or inference.
- No model artifacts committed.
- No prediction fabrication (no completed results from stubs).
- No clinical or reporting layer.
- No patient-facing report template.
- No ROADMAP.md, architecture.md, or ADR changes.
- No ADR rewrite.
- No PR 0019–0024 renumbering.
- No Product Track renumbering.
- No APRANA implementation.
- No Aramis active architecture.

## Follow-up PRs

- **PR 0021** — Container dependency hygiene (ADR-0005, separate from API work)
- **PR 0022** — Terraform/ECR/ECS/S3 IaC skeleton
- **PR 0020** — Cloud-aware config sourcing (depends on PR 0019)
- **Later** — Runtime model package loader integration with API stub (PR 0016 or later)
- **Later** — H5 inspect gate and preprocessing workflow
- **Later** — Real inference pipeline

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only the 7 allowed files (api/**, docs/api_contract.md, test files) changed. |
| **API contract drift** | All 4 endpoints documented: /health, /model/version, POST /predictions, GET /predictions/{id}. Async submit → job_id → poll. Mandatory result fields from project_contract.yml. No local machine paths in request schema. Target/control refs explicit. |
| **Skeleton drift** | Standard-library only. No web framework dependency. Route-shaped handler functions. In-memory job store. No joblib/pickle/H5/network/AWS. |
| **Async job drift** | submit_prediction creates job with status "accepted". get_prediction returns status. No background worker. No inference. |
| **Model package boundary drift** | May import safe types from model_package.py but must not validate real package by default. No joblib.load(). No deserialization. |
| **No-dependency drift** | pyproject.toml and requirements.txt unchanged. Standard library only. |
| **Clinical safety drift** | No "cancer detected", no diagnosis wording, no MRI/biopsy/radiologist replacement language. |
| **Identity drift** | No Aramis active architecture. Bremen identity preserved. |
| **Infrastructure drift** | No CI/Docker/IaC changes. No ROADMAP.md/architecture/ADR changes. |
| **Test drift** | All validation scenarios covered. Import safety verified. Prohibited-reference grep checks pass. |
| **Validation drift** | All 27 validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan adds dependencies (changes pyproject.toml or requirements.txt).
- Plan changes CI/Docker/IaC files.
- Plan changes ROADMAP.md, architecture.md, or ADR files.
- Plan implements real H5 reading, preprocessing, inference, or training.
- Plan calls `joblib.load()` or imports `joblib`/`pickle`.
- Plan adds AWS/S3/network calls.
- Plan creates model artifacts.
- Plan creates clinical report or patient-facing output.
- Plan makes Aramis active architecture.
- Plan renumbers PR 0019–0024.
- Any file outside the seven allowed files is changed (unless __main__.py or CLI test change is strongly justified and pre-approved).

## Decisions summary

### Allowed files
1. `docs/api_contract.md` — NEW
2. `src/bremen/api/__init__.py` — NEW
3. `src/bremen/api/schemas.py` — NEW
4. `src/bremen/api/jobs.py` — NEW
5. `src/bremen/api/app.py` — NEW
6. `tests/test_bremen_api_contract.py` — NEW
7. `tests/test_bremen_api_skeleton.py` — NEW

### Forbidden files
- ROADMAP.md, docs/architecture.md, docs/adr/**, README.md, docs/**
- All infrastructure files (CI, Docker, pyproject, env, Makefile)
- config/**, examples/**, tests/data/**
- agents/**
- H5/HDF5, model artifacts, IaC files

### API contract summary
4 endpoints: GET /health (service health), GET /model/version (configured model metadata), POST /predictions (async submit with opaque platform refs), GET /predictions/{job_id} (poll status). All mandatory prediction response fields from project_contract.yml. No local machine paths. No clinical wording.

### Microservice skeleton summary
Standard-library-only. Route-shaped handler functions (health, model_version, submit_prediction, get_prediction). In-memory job store with dataclass records. No web framework dependency. Designed to be plugged into any future framework.

### Async job shape summary
submit → status "accepted" with job_id → poll returns status. Completed result carries all 7 project_contract fields. No background worker. Stub does not fabricate completions.

### Model package boundary summary
Safe types may be imported from model_package.py. No joblib/pickle. No deserialization. No real package validation by default.

### Safety/non-goals summary
No web framework added. No dependency changes. No CI/Docker/IaC. No H5/model/AWS/Matador. No training/inference. No clinical claims. No Aramis. No PR renumbering.

### Validation summary
27 checks: git state, file existence (7), compile and test (6), CLI help, security grep (5), forbidden path check, model artifact scan, .DS_Store.

### Follow-up sequencing
PR 0021 → PR 0022 → PR 0020 → later runtime loader integration → later H5/preprocessing → later inference.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0019-api-contract-microservice-skeleton/PLAN.md`
2. Human runs: `git add .project-memory/pr/0019-api-contract-microservice-skeleton/PLAN.md`
3. Human runs: `git commit -m "PR 0019 — Plan API contract and async microservice skeleton"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the seven allowed files.

## Files read

- `ROADMAP.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `.project-memory/project_contract.yml`
- `src/bremen/model_package.py`
- `tests/test_bremen_model_package.py`
- `src/bremen/config.py`
- `src/bremen/__main__.py`
- `pyproject.toml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0019-api-contract-microservice-skeleton/PLAN.md` (this file)

## Files intentionally ignored

- All infrastructure files (CI, Docker, pyproject, env, Makefile)
- All docs files not in the allowed set (ROADMAP.md, architecture.md, ADRs, README.md)
- All config, example, test data files
- All existing source files not named in the allowed set
- Any H5/HDF5 or model artifact files

## Boundary confirmations

- confirm: PR 0019 number preserved: yes
- confirm: no PR 0019–0024 renumbering planned: yes
- confirm: `docs/api_contract.md` planned: yes
- confirm: async submit → `job_id` → poll planned: yes
- confirm: no dependency additions planned: yes
- confirm: no CI/Docker/IaC changes planned: yes
- confirm: no H5/HDF5 reads planned: yes
- confirm: no preprocessing/inference/training planned: yes
- confirm: no `joblib.load` planned: yes
- confirm: no AWS/S3/network calls planned: yes
- confirm: no model artifacts planned: yes
- confirm: no clinical report planned: yes
- confirm: no implementation files modified: yes
- confirm: no git mutation commands run: yes
