# PR 0049 — Plan: Production End-to-End Smoke Hardening

## 1. Title / Branch / Objective

- **Title**: Production End-to-End Smoke Hardening
- **Branch**: `0049-production-e2e-smoke-hardening`
- **Objective**: Make the production end-to-end Bremen smoke path repeatable, safe, and reviewable without changing runtime behavior or requiring real production access in default tests. Deliver an operator runbook (`docs/production_e2e_smoke.md`) and a synthetic production-like automated test (`tests/test_bremen_production_smoke.py`) that exercises the full HTTP prediction path — POST /predictions with h5_uri mode (monkeypatched S3 staging), explicit target/control refs, synthetic calibration H5, async job completion with non-null result, and strict no-log-leakage assertions. No FastAPI. No web framework migration. No App Runner deployment. No actual production smoke execution by the agent.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
078a74cc5d125741d85661bebe1834524ad56420

$ git branch --show-current
0049-production-e2e-smoke-hardening

$ git status --short
(clean — no uncommitted changes)
```

Required files all read. PR0048 (HTTP explicit-ref wiring) confirmed merged — `inference_handler.py` accepts `target_scan_ref`/`control_scan_ref`, `app.py` forwards them, preflight populates `PreflightResult.metadata`, preprocessing bridge reconstructs `H5PredictionContext` from metadata. Full prediction path works.

---

## 3. Current State After PR0048

### What works (HTTP prediction path, fully wired)

| Layer | Status |
|-------|--------|
| `GET /health` | Returns `status: "ok"`, `service: "bremen"`, `model_ready: bool` |
| `GET /model/version` | Returns `model_configured`, `model_version`, `model_checksum`, `model_status` |
| `POST /predictions` | Body validated → `PredictionRequest` → `run_inference()` with refs → preflight → bridge → inference → completed/failed job |
| `GET /predictions/{job_id}` | Returns status, result (with all mandatory fields), error |
| `h5_path` mode | Direct filesystem path accepted, refs forwarded |
| `h5_uri` mode | S3 URI → `stage_h5_input()` → checksum verify → refs forwarded |
| Canonical layout | `target_scan_ref="target"`, `control_scan_ref="contralateral"` → preflight → bridge → inference |
| Calibration sample layout | Explicit refs → adapter detect → context resolve → bridge reads integration i/q → 15 v0.1 features → inference |
| Model readiness gate | `ModelNotReadyError` → HTTP 503 |
| Logging | `bremen.*` structured events, no raw patient identifiers, no raw refs, no full S3 URIs |
| Job system | Create → submit → run → completed (non-null result) or failed (non-null error) |

### What is missing

1. **No production operator runbook** — Operators have no documented script for smoke-testing a deployed Bremen instance. No curl examples. No environment variable table. No success/failure criteria.
2. **No synthetic end-to-end production-like test** — The existing tests cover individual layers (preflight, bridge, inference, server, logging) but no single test wires the full path: `POST /predictions` with `h5_uri` → monkeypatched S3 staging → explicit refs → synthetic calibration layout → async poll → non-null completed result → log leakage check.
3. **No synthetic h5_uri mode exercise** — Existing server tests use `h5_path` mode only. The `h5_uri` → `stage_h5_input()` → checksum verify path is tested in `test_bremen_h5_input_staging.py` at the unit level but never through the HTTP server.

### The hardening gap

```
Production Bremen deployed on App Runner or ECS
  → Operator needs a single command to verify:
    → Model is ready (/health, /model/version)
    → POST /predictions with explicit refs accepts job (202)
    → Poll until completed shows non-null result
    → No patient data leaked in logs
    → Known failure modes produce safe errors

No runbook for this. No automated test exercising this path.
```

---

## 4. FastAPI Deferral Summary

FastAPI is **not** part of PR0049. FastAPI remains deferred until after production smoke hardening is proven on the standard-library HTTP server. FastAPI must eventually be a thin transport adapter only — it must not change model loading, H5 staging, preprocessing, inference math, job semantics, response schemas, or log events.

All source files (`src/bremen/**`) must remain free of `FastAPI`, `fastapi`, `uvicorn`, `starlette`, and `asgi` references.

---

## 5. Production Smoke Scope Decision

### Decision: docs runbook + synthetic automated test

The implementation shape is two files:

| File | Purpose | Status |
|------|---------|--------|
| `docs/production_e2e_smoke.md` | Operator runbook — curl examples, env var tables, success/failure criteria, rollback notes | **Implementation target** |
| `tests/test_bremen_production_smoke.py` | Synthetic production-like test — full HTTP path with monkeypatched S3 staging | **Implementation target** |

### Why not an actual production smoke script?

- An actual production smoke requires App Runner or ECS endpoint, authentication, real S3 buckets, and deployment — all forbidden in this PR.
- The synthetic test and runbook together provide the pattern. Operators can follow the runbook with real endpoints when deploying.

### Why not a bash script?

- Bash scripts with curl are documented in the runbook. A separate `.sh` file would duplicate the runbook and cannot be tested in CI (no real endpoint).
- The Python test exercises the exact same path deterministically and can run in CI.

### Existing files that may be updated

If the implementation proves that an existing test file needs a narrow expectation adjustment (e.g., a test asserts exactly N total tests and the new test adds one, or a conftest fixture needs extension), the plan allows that. Any such change must:
1. Be isolated to a single test file.
2. Be the minimum change possible (a line count, an import, a fixture scope).
3. Be documented in this plan's Deviations section after implementation review.

No source files may be changed unless a blocker prevents the production-like smoke from passing. If such a blocker is discovered, it must be documented here with a rationale before implementation.

---

## 6. Runbook Plan (`docs/production_e2e_smoke.md`)

### 6.1 Structure and sections

The runbook must be a plain markdown file (`docs/production_e2e_smoke.md`) with the following sections:

#### 6.1.1 Title and goal

> # Production End-to-End Smoke
> 
> **Goal**: Verify that a deployed Bremen instance can accept an H5 container via S3 URI, process it through the full inference pipeline (preflight → preprocessing → inference), and return a non-null prediction result — without leaking raw patient data.

#### 6.1.2 Prerequisites

- Bremen instance URL (e.g., `https://bremen.abc123.apprunner.com` or `http://localhost:8000`)
- S3 H5 URI (`s3://my-bucket/path/to/calibration.h5`) with sha256 checksum
- Explicit `target_scan_ref` and `control_scan_ref` matching the H5 layout
- `curl` installed

#### 6.1.3 Environment variables table

| Variable | Required | Example (placeholder) | Purpose |
|----------|----------|----------------------|---------|
| `BREMEN_URL` | Yes | `https://<app-runner-host>.awsapps.com` | Base URL of running Bremen instance |
| `BREMEN_S3_H5_URI` | Yes | `s3://<bucket>/calibration.h5` | S3 URI of H5 container |
| `BREMEN_S3_H5_CHECKSUM` | Yes | `sha256:abc123...full64hex` | SHA-256 checksum of H5 file |
| `BREMEN_TARGET_SCAN_REF` | Yes | `calib_20260128_132622/sample_01_..._Right` | Explicit target scan ref |
| `BREMEN_CONTROL_SCAN_REF` | Yes | `calib_20260128_132622/sample_02_..._Left` | Explicit control scan ref |

**Rules**:
- Must use `https://` or `http://` prefix — never a bare hostname.
- S3 URI must use `s3://` scheme — never `https://s3-...`.
- Checksum must be `sha256:<64 hex chars>`.
- No hardcoded real account IDs, registry URLs, or access keys.

#### 6.1.4 Health check

```bash
curl -s "${BREMEN_URL}/health" | jq .
```

Expected:
```json
{"status": "ok", "service": "bremen", "model_ready": true, ...}
```

If `model_ready` is `false`, stop — check model configuration.

#### 6.1.5 Model version check

```bash
curl -s "${BREMEN_URL}/model/version" | jq .
```

Expected: `model_configured: true`, `model_status: "configured"`.

#### 6.1.6 Submit prediction (S3 H5 URI mode)

Redacted request shape:

```bash
curl -s -X POST "${BREMEN_URL}/predictions" \
  -H "Content-Type: application/json" \
  -d '{
    "target_scan_ref": "'"${BREMEN_TARGET_SCAN_REF}"'",
    "control_scan_ref": "'"${BREMEN_CONTROL_SCAN_REF}"'",
    "h5_uri": "'"${BREMEN_S3_H5_URI}"'",
    "h5_checksum": "'"${BREMEN_S3_H5_CHECKSUM}"'"
  }' | jq .
```

Expected:
```json
{"status": "accepted", "job_id": "<uuid>", "links": {"poll": "/predictions/<uuid>"}}
```

#### 6.1.7 Poll for result

```bash
JOB_ID="<uuid from above>"
curl -s "${BREMEN_URL}/predictions/${JOB_ID}" | jq .
```

Expected (completed):
```json
{
  "job_id": "<uuid>",
  "status": "completed",
  "result": {
    "prediction_id": "...",
    "model_version": "...",
    "model_checksum": "...",
    "feature_schema_version": "v0.1",
    "threshold_version": "...",
    "threshold_value": 0.5,
    "qc_status": "passed",
    "qc_flags": []
  },
  "error": null
}
```

#### 6.1.8 Success criteria

1. `GET /health` returns `model_ready: true` ✓
2. `GET /model/version` returns `model_configured: true` ✓
3. `POST /predictions` returns HTTP 202 with `job_id` ✓
4. `GET /predictions/{job_id}` eventually returns `status: "completed"` ✓
5. `result` is non-null and contains all mandatory fields ✓
6. No raw patient identifiers, raw target/control refs, full S3 URI, raw feature values, or raw scan arrays appear in CloudWatch logs ✓

#### 6.1.9 Safe failure criteria

These are NOT errors — they are expected safe behaviours for specific conditions:

| Condition | Expected | Safe? |
|-----------|----------|-------|
| Model not configured | `POST /predictions` → HTTP 503 | ✓ Safe |
| S3 staging failure (wrong bucket) | Job → `failed`, error: "S3 download failed" | ✓ Safe |
| Checksum mismatch | Job → `failed`, error: "SHA-256 mismatch" | ✓ Safe |
| Invalid H5 refs (nonexistent group) | Job → `failed`, error: "Target scan group not found" | ✓ Safe |
| Missing H5 metadata | Job → `failed`, error: "H5MetadataError" | ✓ Safe |
| Preprocessing failure (missing i/q) | Job → `failed`, error: "PreprocessingBridgeError" | ✓ Safe |
| Inference failure (bad model) | Job → `failed`, error: "Model validation failed" | ✓ Safe |
| Timeout (slow H5) | Job → `failed`, error: "RuntimeError" | ✓ Safe |

**Rule**: A failed job is acceptable only when the error is safe and expected for the test condition. An unexpected internal server error (HTTP 500) without a job or with a null error is never acceptable.

#### 6.1.10 Safety and privacy

- No raw patient identifiers (`Nova_376`, `patient_id` values) in curl examples or expected outputs.
- No raw `target_scan_ref` / `control_scan_ref` values — use environment variable substitution (`${BREMEN_TARGET_SCAN_REF}`).
- No full S3 URI — use `${BREMEN_S3_H5_URI}`.
- No raw feature values or vectors in output examples.
- No raw scan arrays or detector arrays.
- No secrets, account IDs, registry URLs, or access keys.
- The smoke is decision-support plumbing validation, **not clinical validation**. No claims about diagnostic accuracy.

#### 6.1.11 Rollback / recovery notes

- If a live deployment fails smoke: check model startup logs for `bremen.model.not_ready`, verify `BREMEN_MODEL_URI` / `BREMEN_MODEL_VERSION` / `BREMEN_MODEL_CHECKSUM` env vars.
- If S3 staging fails: verify IAM role permissions, bucket exists, key exists.
- If preprocessing fails: verify H5 layout is supported (canonical or calibration sample), verify refs match group paths.
- Rollback: redeploy previous working image tag (e.g., `app-runner` stable tag or specific SHA).
- Escalation: contact platform team with `job_id`, timestamps, and `bremen.*` event log excerpts (no raw patient data).

---

## 7. Production-Like Test Plan (`tests/test_bremen_production_smoke.py`)

### 7.1 Test design principles

1. **Synthetic by default** — All H5 data generated in memory with `h5py` + `numpy`. No real H5 files.
2. **Deterministic** — Fixed random seed (`np.random.default_rng(42)`). Reproducible.
3. **No network** — AWS, S3, Docker, Terraform, App Runner calls forbidden. S3 staging is monkeypatched.
4. **Full HTTP path** — Uses real `HTTPServer` on random port (same pattern as `test_bremen_api_server.py`).
5. **Async polling** — Submit job, poll `GET /predictions/{job_id}` until completed or timeout.
6. **Calibration layout** — Exercises explicit ref wiring end-to-end with calibration sample H5 layout.
7. **Log leakage checks** — `caplog` + string assertions for forbidden patterns.
8. **Multiple failure modes** — Tests cover successful completion, generic-refs safe failure, and missing-refs safe failure.

### 7.2 Fixtures

#### `synthetic_calibration_h5(tmp_path)` → Path

Creates a synthetic calibration sample H5 with:
- One `calib_*` group
- Target sample with `sample/patient_name`, `sample/sample_type`, 3 sets with integration i/q
- Control sample with same patient_name, opposite sample_type, 3 sets with integration i/q
- Random data with fixed seed

Mirrors the `_create_calibration_h5()` helper from `test_bremen_calibration_preprocessing.py` and `test_bremen_h5_layouts.py`.

#### `smoke_server_info(tmp_path)` → `(host: str, port: int, job_store: InMemoryJobStore)`

Creates a full HTTP server with:
- `load_model=True` (synthetic model via `_load_synthetic_model()`)
- Random free port
- Daemon thread (auto-cleanup)
- Yields `(host, port, job_store)`

Mirrors the `server_info` fixture pattern from `test_bremen_api_server.py`.

### 7.3 Test cases

#### A. `test_production_smoke_h5_uri_completes`

**Purpose**: Full production-like smoke: h5_uri mode with monkeypatched S3 staging, explicit refs, synthetic calibration H5, async poll, completed with non-null result.

**Steps**:
1. Create synthetic calibration H5 at `h5_path`.
2. Compute `sha256:<hex>` checksum of the H5 file.
3. Monkeypatch `bremen.h5_inputs.stage_h5_input` to return `h5_path`.
4. Start server with `load_model=True` via `smoke_server_info`.
5. `POST /predictions` with `h5_uri=f"s3://fake-bucket/calibration.h5"`, `h5_checksum`, explicit target/control refs.
6. Assert HTTP 202 with `job_id` and poll link.
7. Poll `GET /predictions/{job_id}` until `status` is `"completed"` (max 5 retries, 100ms backoff).
8. Assert `result` is non-null.
9. Assert all mandatory result fields present: `prediction_id`, `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_status`, `qc_flags`.

#### B. `test_production_smoke_generic_refs_fail_safely`

**Purpose**: Generic refs (`"target"`, `"contralateral"`) on a calibration H5 fail safely — no auto-selection.

**Steps**:
1. Create synthetic calibration H5.
2. Monkeypatch `bremen.h5_inputs.stage_h5_input`.
3. Start server with `load_model=True`.
4. `POST /predictions` with generic `target_scan_ref="target"`, `control_scan_ref="contralateral"`.
5. Assert HTTP 202.
6. Poll until completed or failed.
7. Assert `status` is `"failed"` with safe error message (e.g., "Target scan group not found" or adapter error).
8. Assert `result` is null.
9. Assert no auto-selection of first patient.

#### C. `test_production_smoke_missing_h5_staging_fails_safely`

**Purpose**: S3 staging failure (simulated by monkeypatch raising) produces failed job with safe error.

**Steps**:
1. Monkeypatch `bremen.h5_inputs.stage_h5_input` to raise `ValueError("S3 download failed for test: simulated")`.
2. Start server.
3. Submit with `h5_uri` + valid refs.
4. Assert HTTP 202.
5. Poll until `status` is `"failed"`.
6. Assert error contains safe text, no raw S3 URI or credentials.

#### D. `test_production_smoke_no_log_leakage`

**Purpose**: No raw patient identifiers, raw refs, raw feature values, raw scan arrays, or full S3 URI in logs.

**Steps**:
1. Use `caplog` at `logging.INFO` level.
2. Run test A (successful completion).
3. Assert forbidden strings absent from `caplog.text`:
   - `"Nova_376"` (raw patient identifier)
   - `"calib_20260128_132622/"` as a contiguous raw ref (the full ref string)
   - `"s3://fake-bucket/calibration.h5"` (full S3 URI — the redacted scheme is allowed, but not the full URI with basename)
   - Any raw feature value from the known output range
   - Any raw scan array shape like `"(3, 100)"` or `"(100,)"` from measurement content
4. Assert safe log fields present:
   - `"explicit_refs=true"`
   - `"h5_input_present=true"`
   - `"bremen.prediction.completed"`
   - `"bremen.prediction.preflight.completed"`
   - `"bremen.prediction.preprocessing.completed"`
   - `"bremen.prediction.inference.success"`

#### E. `test_production_smoke_h5_path_mode_still_works`

**Purpose**: Backward compatibility — `h5_path` mode with canonical refs still works through the production smoke path.

**Steps**:
1. Create synthetic canonical H5 (`/scans/target/measurements`, `/scans/contralateral/measurements`).
2. Start server with `load_model=True`.
3. `POST /predictions` with `h5_path`, `target_scan_ref="target"`, `control_scan_ref="contralateral"`.
4. Assert HTTP 202.
5. Poll until completed.
6. Assert non-null result.

#### F. `test_production_smoke_missing_target_ref_400`

**Purpose**: Missing `target_scan_ref` in body returns HTTP 400 before job creation.

**Steps**:
1. Start server.
2. `POST /predictions` with only `control_scan_ref` and `h5_path`.
3. Assert HTTP 400 and error message referencing `target_scan_ref`.

#### G. Optional real H5 / App Runner smoke (skipped by default)

```python
@pytest.mark.skipif(
    "BREMEN_E2E_SMOKE_URL" not in os.environ,
    reason="Set BREMEN_E2E_SMOKE_URL to enable real deployment smoke",
)
def test_production_smoke_real_deployment():
    """Run smoke against a real deployed Bremen instance.

    Requires:
      BREMEN_E2E_SMOKE_URL=https://<host>
      BREMEN_E2E_S3_H5_URI=s3://<bucket>/calibration.h5
      BREMEN_E2E_S3_H5_CHECKSUM=sha256:<64hex>
      BREMEN_E2E_TARGET_SCAN_REF=...
      BREMEN_E2E_CONTROL_SCAN_REF=...

    NOTE: This test makes real HTTP requests and requires a running
    deployment.  Skipped by default.
    """
```

### 7.4 Test timing and concurrency

- Server starts in daemon thread, identical to `test_bremen_api_server.py`.
- Poll loop: up to 5 attempts with 100ms sleep between polls.
- Total worst-case test time per completion test: ~600ms (startup + 5 polls × 100ms).
- Tests isolated: each test recreates server fixture + synthetic H5.

### 7.5 Assertion details

**Completed result fields**:
```python
assert result["prediction_id"] is not None
assert result["model_version"] == "smoke-v0.1"
assert result["model_checksum"] is not None
assert result["feature_schema_version"] == "v0.1"
assert result["threshold_version"] is not None
assert result["threshold_value"] == pytest.approx(0.5)
assert result["qc_status"] == "passed"
assert isinstance(result["qc_flags"], list)
```

**No null result on completed**:
```python
assert result is not None, "Completed job must have non-null result"
```

**Safe error on failed**:
```python
assert "Target scan group not found" in error or \
       "SHA-256 mismatch" in error or \
       "S3 download failed" in error
```

---

## 8. API Contract Preservation Summary

| Contract feature | Preserved? | Evidence |
|-----------------|-----------|----------|
| `POST /predictions` returns `job_id` | ✓ | No change — server route unchanged |
| `GET /predictions/{job_id}` returns status, result, error | ✓ | No change — same response shape |
| Async submit-then-poll | ✓ | No change — existing job semantics |
| `target_scan_ref` / `control_scan_ref` required | ✓ | No change — validated by schema |
| `h5_path` / `h5_uri` mutual exclusivity | ✓ | No change — validated by schema |
| `h5_checksum` optional `sha256:<64hex>` | ✓ | No change — validated by schema |
| Completed result mandatory fields | ✓ | No change — `CompletedResult` same fields |
| Model loading unchanged | ✓ | No change — `ModelState.load_at_startup()` same |
| S3 model staging unchanged | ✓ | No change — `stage_s3_model_artifact()` same |
| S3 H5 staging unchanged | ✓ | No change — `stage_h5_input()` same |
| Preprocessing feature math unchanged | ✓ | No change — `build_feature_table()` same 15 functions |
| v0.1 feature schema order unchanged | ✓ | No change — `BREMEN_V01_FEATURE_COLUMNS` same |
| Inference math unchanged | ✓ | No change — `predict_proba_portable()` same |
| No raw patient data logged | ✓ | Enforced by test D (log leakage check) |
| No clinical claims | ✓ | Runbook states "decision-support plumbing validation" |
| FastAPI deferred | ✓ | No FastAPI/uvicorn/starlette references added |

---

## 9. Safety and Privacy Summary

### What is enforced

1. **No raw patient identifiers in logs or docs** — Patient name `Nova_376` must never appear in test assertions, runbook examples, or expected outputs. Use placeholder patterns like `${BREMEN_TARGET_SCAN_REF}`.
2. **No raw target_scan_ref or control_scan_ref values in logs or docs** — Refs used in runbook must use environment variable substitution. Test refs are synthetic test fixtures — never real H5 paths.
3. **No full S3 URI in committed docs or tests** — Runbook uses `${BREMEN_S3_H5_URI}`. Tests use `s3://fake-bucket/calibration.h5` (safe — clearly synthetic).
4. **No raw feature values or vectors in logs** — Test D asserts no raw feature values appear in `caplog.text`.
5. **No raw scan arrays or detector arrays in logs** — Test D asserts no measurement shape patterns appear.
6. **No secrets, account IDs, registry URLs, or access keys** — Runbook explicitly forbids hardcoded values. Test environment uses no real credentials.
7. **No clinical validation claims** — Runbook states: "The smoke is decision-support plumbing validation, not clinical validation."
8. **No real H5 or model artifacts committed** — All H5 data is synthetic and generated at test time. No `*.h5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` files are tracked.

### Log leakage check strategy (Test D)

The test captures all log output emitted during a successful prediction flow and asserts the absence of:

| Pattern | Reason |
|---------|--------|
| `Nova_376` | Raw patient identifier from synthetic H5 |
| `calib_20260128_132622/sample_01_20260128_Nova_376_Right` | Full raw target scan ref |
| `s3://fake-bucket/calibration.h5` | Full S3 URI |
| `sample/patient_name` | Raw H5 metadata path content |
| `integration/i` or `integration/q` followed by array data | Raw scan array data |
| Feature float values matching known range | Raw feature vector data |

---

## 10. Validation Run

The implementation agent must run these commands (following `.project-memory/AGENT_TEST_DEBUGGING_RULES.md` — no `tail`/`head` on failing pytest):

```bash
# 1. Verify working tree is clean (planning artifacts only)
git diff --name-only

# 2. Verify only allowed files changed
git diff --name-only -- src/ tests/ docs/ ROADMAP.md requirements.txt pyproject.toml Dockerfile Dockerfile.training infra/ .github/ src/bremen/training/ docs/adr/

# 3. Scan for FastAPI references
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n src/bremen tests requirements.txt pyproject.toml || true

# 4. Compile all source and test files
python -m compileall src tests

# 5. Run the new production smoke test
python -m pytest -q tests/test_bremen_production_smoke.py -v

# 6. Run existing prediction tests (regression)
python -m pytest -q tests/test_bremen_predictions.py -v

# 7. Run existing inference integration tests (regression)
python -m pytest -q tests/test_bremen_inference_integration.py -v

# 8. Run existing API server tests (regression)
python -m pytest -q tests/test_bremen_api_server.py -v

# 9. Run existing API skeleton tests (regression)
python -m pytest -q tests/test_bremen_api_skeleton.py -v

# 10. Run existing calibration preprocessing tests (regression)
python -m pytest -q tests/test_bremen_calibration_preprocessing.py -v

# 11. Run existing logging tests (regression)
python -m pytest -q tests/test_bremen_logging.py -v

# 12. Run full test suite
python -m pytest -q

# 13. Verify no dependency changes
git diff --name-only -- requirements.txt pyproject.toml Dockerfile Dockerfile.training infra/ .github/ src/bremen/training/ docs/adr/ ROADMAP.md

# 14. Verify no real artifacts committed
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" \
  -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) \
  -not -path "./.git/*" -not -path "./venv/*" -not -path "./.venv/*" -print

# 15. Verify runbook exists and has required sections
grep -c "## " docs/production_e2e_smoke.md
python -c "
import re
with open('docs/production_e2e_smoke.md') as f:
    content = f.read()
checks = [
    'Production End-to-End Smoke' in content,
    'Goal' in content,
    'Prerequisites' in content,
    'Environment variables' in content,
    'Health check' in content,
    'Model version check' in content,
    'Submit prediction' in content,
    'Poll for result' in content,
    'Success criteria' in content,
    'Safe failure criteria' in content,
    'Safety and privacy' in content,
    'Rollback' in content or 'recovery' in content.lower(),
    'decision-support' in content,
]
for i, c in enumerate(checks):
    assert c, f'Runbook check {i} failed'
print(f'All {len(checks)} runbook checks passed')
"
```

---

## 11. Deviations from Plan

This section is populated by the implementation agent after implementation. Before implementation, it is empty.

| # | Deviation | Rationale | Approved? |
|---|-----------|-----------|-----------|
| — | None yet | — | — |

If no deviations occur, mark as "None — plan followed exactly."

---

## 12. Boundary Confirmations

| File/Directory | Changed in this PR? | Rationale |
|---------------|---------------------|-----------|
| `docs/production_e2e_smoke.md` | **YES** — new | Operator runbook |
| `tests/test_bremen_production_smoke.py` | **YES** — new | Synthetic production-like test |
| `src/bremen/api/app.py` | **NO** | No source changes needed — refs already wired |
| `src/bremen/api/inference_handler.py` | **NO** | No source changes needed — refs already forwarded |
| `src/bremen/api/preflight.py` | **NO** | No source changes needed — adapter path works |
| `src/bremen/api/h5_layouts.py` | **NO** | No source changes needed — calibration adapter works |
| `src/bremen/api/preprocessing_bridge.py` | **NO** | No source changes needed — bridge reconstructs context |
| `src/bremen/api/schemas.py` | **NO** | No schema changes needed — contract stable |
| `src/bremen/api/jobs.py` | **NO** | No job semantics change |
| `src/bremen/api/server.py` | **NO** | No server changes needed — routes stable |
| `src/bremen/api/model_state.py` | **NO** | No model loading change |
| `src/bremen/h5_inputs.py` | **NO** | S3 staging unchanged |
| `src/bremen/**` (all others) | **NO** | Forbidden |
| `tests/test_bremen_predictions.py` | **NO** (unless narrow adjustment needed) | Existing tests unchanged |
| `tests/test_bremen_api_server.py` | **NO** (unless narrow adjustment needed) | Existing tests unchanged |
| `tests/test_bremen_inference_integration.py` | **NO** (unless narrow adjustment needed) | Existing tests unchanged |
| `tests/test_bremen_logging.py` | **NO** (unless narrow adjustment needed) | Existing tests unchanged |
| `tests/test_bremen_calibration_preprocessing.py` | **NO** (unless narrow adjustment needed) | Existing tests unchanged |
| `tests/test_bremen_h5_layouts.py` | **NO** (unless narrow adjustment needed) | Existing tests unchanged |
| `tests/test_bremen_h5_preflight.py` | **NO** (unless narrow adjustment needed) | Existing tests unchanged |
| `docs/**` (except new runbook) | **NO** | Forbidden — no existing doc changes |
| `docs/adr/**` | **NO** | Forbidden |
| `ROADMAP.md` | **NO** | Forbidden |
| `requirements.txt` | **NO** | Forbidden — no dependency changes |
| `pyproject.toml` | **NO** | Forbidden |
| `Dockerfile` | **NO** | Forbidden |
| `Dockerfile.training` | **NO** | Forbidden |
| `infra/**` | **NO** | Forbidden |
| `.github/**` | **NO** | Forbidden |
| `src/bremen/training/**` | **NO** | Forbidden |
| `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` | **NO** | Forbidden — no real artifacts committed |

---

## 13. Implementation Scope Checklist

| Item | Included? |
|------|-----------|
| `docs/production_e2e_smoke.md` — operator runbook | ✓ Yes |
| `tests/test_bremen_production_smoke.py` — synthetic production-like test | ✓ Yes |
| Existing test file narrow adjustments (if proven necessary) | ✓ Conditional — document in Deviations |
| Any source file changes | ✗ No — unless blocker proven |
| FastAPI, uvicorn, starlette, ASGI | ✗ No |
| App Runner, Docker, Terraform, AWS commands | ✗ No |
| Real H5 or model artifact files | ✗ No |
| Secrets, account IDs, registry URLs, access keys | ✗ No |
| S3 staging implementation change | ✗ No |
| Preprocessing math change | ✗ No |
| Inference math change | ✗ No |
| Model loading change | ✗ No |
| Schema or contract change | ✗ No |
| Clinical validation claims | ✗ No |

---

## 14. Next Required Action

The implementation agent (`coder`) must:

1. Create `docs/production_e2e_smoke.md` following Section 6 of this plan.
2. Create `tests/test_bremen_production_smoke.py` following Section 7 of this plan.
3. Run the validation checklist (Section 10) and fix any failures.
4. If a source file change is required (blocker), document in Section 11 (Deviations) with rationale before implementation.
5. If an existing test needs a narrow adjustment, document in Section 11 with rationale before making the change.
6. Commit only allowed files, verify no forbidden artifacts.

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. The synthetic calibration H5 must use exactly the same layout structure as `_create_calibration_h5()` in `test_bremen_calibration_preprocessing.py` — the `sample/patient_name` dataset is a child of the sample group, not at the calib level. Test D (log leakage) asserts `Nova_376` is not logged — ensure this holds even though the raw name exists in the H5 file.
2. The monkeypatch target is `bremen.h5_inputs.stage_h5_input` — this must be patched before `handle_submit_prediction()` imports it. In `app.py`, the import is lazy (`from ..h5_inputs import stage_h5_input` inside the function), so patching at module scope before server creation works (`@patch("bremen.h5_inputs.stage_h5_input")` on the test function).
3. The synthetic H5 checksum must be computed from the written H5 bytes, not from the random data before writing. Compute checksum after `h5py.File` is closed.
4. The `_load_synthetic_model()` function in `server.py` is called when `load_model=True`. It creates a tempfile-based synthetic model. This is sufficient for production smoke — the test does not need a real S3 model package.
5. If the optional real-deployment smoke test is added, it must be skipped by default with a clear env var guard. Do not document real S3 URIs or account IDs in the test file.

FILES CHANGED:
- `.project-memory/pr/0049-production-e2e-smoke-hardening/PLAN.md` — written

FASTAPI DEFERRAL SUMMARY:
FastAPI remains deferred until after PR0049. No FastAPI, uvicorn, starlette, or ASGI references added anywhere. PR0049 is pure docs + test hardening on the existing standard-library HTTP server.

CURRENT STATE SUMMARY:
PR0043–PR0048 delivered: S3 H5 staging, H5 layout adapter boundary, calibration preprocessing bridge, and explicit target/control ref wiring through predictions. The HTTP prediction path is complete: POST /predictions accepts h5_path or h5_uri with explicit refs, runs preflight → bridge → inference, returns completed/failed job. Missing: operator runbook for production smoke, synthetic production-like test exercising the full path with h5_uri mode and async polling.

PRODUCTION SMOKE SCOPE DECISION:
Docs runbook (`docs/production_e2e_smoke.md`) + synthetic automated test (`tests/test_bremen_production_smoke.py`). No bash script, no actual production smoke by agent. The runbook documents curl commands with placeholder environment variables. The test monkeypatches S3 staging to return synthetic local H5, exercises full HTTP path, asserts non-null completed result, and verifies no log leakage.

RUNBOOK PLAN:
12 required sections: title/goal, prerequisites, env var table, health check, model version check, submit prediction (redacted), poll for result, success criteria (6 items), safe failure criteria (8 conditions), safety and privacy (6 rules), rollback/recovery notes (high-level), and decision-support disclaimer. All examples use `${VARIABLE}` substitution. No raw identifiers or full S3 URIs.

PRODUCTION-LIKE TEST PLAN:
7 test cases (A–G): h5_uri mode completes with non-null result, generic refs fail safely, S3 staging failure produces safe error, no log leakage of raw identifiers/refs/features/S3 URIs, h5_path canonical mode backward compatible, missing target ref returns 400, and optional real deployment smoke (skipped by default). Uses same server fixture pattern as test_bremen_api_server.py. All synthetic H5 with fixed random seed.

API CONTRACT PRESERVATION SUMMARY:
All 16 contract items preserved. No schema, handler, job, model loading, preprocessing, inference, or staging changes. Only docs and test additions.

SAFETY AND PRIVACY SUMMARY:
8 enforcement rules (no raw patient identifiers, no raw refs, no full S3 URI, no raw features/arrays, no secrets, no clinical claims, no real artifacts committed). Log leakage test (Test D) asserts absence of 6 forbidden pattern categories. Runbook uses placeholder substitution for all sensitive values.

VALIDATION RUN:
15-step checklist: working tree check, allowed files diff, FastAPI scan, compile all, new smoke test, 6 regression test suites, full suite, dependency/artifact scans, runbook section content check. All steps must pass.

DEVIATIONS FROM PLAN:
None yet — section reserved for implementation agent to document any adjustments.

BOUNDARY CONFIRMATIONS:
All 25+ file boundaries confirmed. Only two new files added: runbook and test. Zero source files, zero existing tests, zero docs, zero infra files changed — unless a narrow adjustment is proven necessary and documented.

IMPLEMENTATION AGENT ASSIGNMENT: coder
