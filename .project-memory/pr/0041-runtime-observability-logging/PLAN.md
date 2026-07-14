# PR 0041 — Runtime Observability Logging Plan

**Branch**: `0041-runtime-observability-logging`
**Agent role**: planner
**Mode**: planning only

## 1. Title / Branch / Objective

**Title**: PR 0041 — Runtime Observability Logging  
**Branch**: `0041-runtime-observability-logging`  
**Objective**: Make Bremen's runtime no longer blind in App Runner by adding a minimal, targeted logging layer at key lifecycle and decision points. No log spam. No patient data. No change to inference, feature schema, or model package format.

## 2. Runtime Observability Problem Statement

When Bremen runs in AWS App Runner, the only observability is:

- The `/health` endpoint response (JSON, but no root-cause for false statuses).
- The `/model/version` endpoint response.
- CloudWatch logs — which currently contain **nothing useful** (or only `print()` stdout).

The current codebase has:
- `print()` calls in `__main__.py` and `server.py` — go to stdout but are unstructured, grep-unfriendly, and absent for most failure paths.
- `logging.getLogger()` in `model_state.py` and `model_artifacts.py` — but **no `logging.basicConfig()`** anywhere, so these loggers produce no output in App Runner unless `logging.basicConfig()` is called at the earliest entry point.
- `log_message` is **silenced** (overridden with `pass`) in the server handler, which means even access logs are gone.
- No logging for CLI dispatch, model config detection, S3 staging, checksum verification, preflight, preprocessing, inference stages.

Result: operators see `model_ready=false` or `model_status=not_configured` and cannot tell **why** without checking environment variables, IAM roles, S3 bucket permissions, or stale images — all blind from CloudWatch.

## 3. Runtime Flow Map

The actual runtime path from process start to prediction result:

```
CLI entrypoint (bremen serve --host X --port Y)
  │
  ├── main() in __main__.py
  │     └── _handle_serve()
  │           ├── [1] CLI serve dispatch
  │           └── run_server(host, port)
  │                 ├── [2] Server startup
  │                 ├── _make_handler(job_store, version, load_model=...)
  │                 │     └── [3] _load_synthetic_model()  (dev/smoke only)
  │                 │           └── ModelState.load_at_startup()
  │                 │                 ├── [4] Model config read (env vars)
  │                 │                 ├── [5a] S3 staging (if s3:// URI)
  │                 │                 │     ├── S3 download
  │                 │                 │     ├── Checksum verification
  │                 │                 │     └── Temp file cleanup
  │                 │                 ├── [5b] Local file staging (if file:// or path)
  │                 │                 ├── [6] Checksum verification
  │                 │                 ├── [7] joblib.load()
  │                 │                 ├── [8] Package validation
  │                 │                 └── [9] Model readiness state set
  │                 └── HTTPServer.serve_forever()
  │                       ├── GET /health          → handle_health()
  │                       ├── GET /model/version   → handle_model_version()
  │                       ├── POST /predictions    → handle_submit_prediction()
  │                       │     └── [10] Prediction request accepted
  │                       │           ├── [11] Model not ready rejection (503)
  │                       │           └── run_inference()
  │                       │                 ├── [12] H5 preflight
  │                       │                 ├── [13] Preprocessing bridge
  │                       │                 ├── [14] Inference call
  │                       │                 └── [15] Result assembled
  │                       └── GET /predictions/{id} → handle_get_prediction()
```

Numbers in square brackets correspond to the minimum observability points defined in Section 6.

## 4. Logging Placement Criteria

### Allowed (must answer at least one):

| Criterion | Description | Example point(s) |
|-----------|-------------|------------------|
| **Lifecycle boundary** | Process reaches a distinguishable stage of its startup/shutdown lifecycle | CLI dispatch, server starting, model startup begin/end |
| **External dependency boundary** | Crossing into a network call, filesystem I/O, or third-party library call | S3 download, `joblib.load()`, H5 open |
| **Trust/deserialization boundary** | Crossing into code that interprets untrusted data | Checksum verification, `joblib.load()`, model package validation |
| **Critical state transition** | Model readiness, job status, config detected/missing | `model_ready=true/false`, config detected/missing |
| **Safe degraded-mode explanation** | Service is up but in a known degraded state | Checksum skipped (no env var), model not configured |
| **Failure root-cause marker** | A failure that an operator must diagnose without shell access | S3 download failure, checksum mismatch, `joblib.load()` failure |
| **One request-level summary** | One event per request for high-value routes (`/predictions`) | Request accepted, request failed (with stage) |

### Not allowed:

| Prohibition | Rationale |
|-------------|-----------|
| Inside tight loops | Per-measurement, per-profile iteration |
| Per feature | Feature extraction has 15 named features — log event once, not per feature |
| Per row/measurement | No per-measurement logs |
| Per array | No per-array logs |
| Repeated health-check noise | `/health` is polled every few seconds — no per-request log |
| Duplicating another nearby event | One event per stage boundary, not stage entry + exit + inner |
| Only confirming normal internal function call | `entering extract_profiles` is noise — only log at stage boundaries |
| Exposing patient data | Patient ID, scan metadata, H5 paths |
| Exposing raw paths | `/Users/...` local developer paths |
| Exposing secrets | AWS credentials, tokens, signed URLs |
| Exposing feature values | 15 feature values are model input — not logged |
| Exposing H5 contents | Raw arrays, spectra, measurements |

## 5. Proposed Logging Architecture

### Central module: `src/bremen/logging_config.py`

A small (~30 line) module:

```python
"""Bremen logging configuration — single point of config.

Idempotent. Safe for testing. No heavy dependencies.
"""

import logging
import os

_BREMEN_LOG_LEVEL_VAR = "BREMEN_LOG_LEVEL"
_DEFAULT_LOG_LEVEL = "INFO"


def configure_logging() -> None:
    """Configure root logger for Bremen runtime.

    - Default level: INFO
    - Override via BREMEN_LOG_LEVEL env var
    - Format: simple key=value text
    - Output: stdout (stderr for WARNING+)
    - Idempotent: safe to call multiple times
    """
    level_name = os.environ.get(_BREMEN_LOG_LEVEL_VAR, _DEFAULT_LOG_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = "%(levelname)s\t%(name)s\t%(message)s"

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger already configured for Bremen event format.

    Parameter *name* should be ``__name__`` from the calling module.
    """
    return logging.getLogger(name)
```

**Design decisions:**
- No JSON logging — justified because App Runner CloudWatch can parse text and key=value pairs; JSON adds complexity without operator benefit at this stage.
- `logging.StreamHandler()` writes to `sys.stderr` by default — stderr is captured by App Runner and separated from stdout; this is deliberate so application logs do not mix with HTTP response output.
- Tab-separated level and name for easy `grep` filtering.
- No heavy dependency — uses only Python stdlib.
- Idempotent — `addHandler()` is not guarded; `logging.basicConfig()` is NOT used because it may already have been called by an imported library. Instead, use explicit handler setup with a guard flag if needed during testing.

### Wiring

`configure_logging()` is called once, at the earliest entry point: the `main()` function in `__main__.py`, before any argument parsing or imports that produce logs.

```python
def main(argv: list[str] | None = None) -> int:
    from .logging_config import configure_logging
    configure_logging()
    ...
```

This ensures all downstream loggers (`model_state`, `model_artifacts`, and new loggers) have a working root config.

## 6. Event Taxonomy

Event names are prefixed with `bremen.` and use dotted-hierarchy. Level guidance below.

| Event name | Level | When emitted | Answers |
|------------|-------|-------------|---------|
| `bremen.startup.begin` | INFO | `main()` reached, after `configure_logging()` | Did the process start? |
| `bremen.cli.serve.dispatch` | INFO | `_handle_serve()` entered | Was `serve` command dispatched? |
| `bremen.server.starting` | INFO | `run_server()` called with host/port | Did server startup begin? |
| `bremen.server.started` | INFO | `HTTPServer.serve_forever()` called | Is server now listening? |
| `bremen.model.config.read` | INFO | Environment vars read, configured=true/false plus safe summary | Is model config present? |
| `bremen.model.config.missing` | WARNING | No env vars found for model | Why is model not configured? |
| `bremen.model.config.detected` | INFO | Model env vars found + safe fields | What config was detected? |
| `bremen.model.artifact.stage.start` | INFO | Before S3 download or local copy begins | Which stage path was selected? |
| `bremen.model.artifact.stage.success` | INFO | After successful stage (with size_bytes) | Did staging complete? |
| `bremen.model.artifact.stage.failure` | ERROR | Stage raised exception | Why did staging fail? |
| `bremen.model.checksum.verify.start` | DEBUG | Before checksum read/comparison | Is checksum verification running? |
| `bremen.model.checksum.verify.success` | INFO | Checksum matched | Trust boundary crossed safely |
| `bremen.model.checksum.verify.failure` | ERROR | Checksum mismatch | Trust boundary violated |
| `bremen.model.checksum.verify.skipped` | WARNING | No checksum env var set to compare against | Trust was skipped |
| `bremen.model.load.start` | DEBUG | Before `joblib.load()` | Trace for timing debugging |
| `bremen.model.load.success` | INFO | After `joblib.load()` returns dict | Load completed |
| `bremen.model.load.failure` | ERROR | `joblib.load()` raised | Load failed |
| `bremen.model.validation.success` | INFO | Package dict type check passed | Loaded artifact is valid structure |
| `bremen.model.validation.failure` | ERROR | Package is not dict or missing keys | Loaded artifact is corrupt/wrong format |
| `bremen.model.ready` | INFO | `ModelState._loaded` set true with version | End of startup — model ready |
| `bremen.model.not_ready` | WARNING | `ModelState.is_ready()` false, reason encoded | Why model is not ready at startup end |
| `bremen.prediction.request.accepted` | INFO | `handle_submit_prediction` accepted job | A prediction was submitted |
| `bremen.prediction.request.rejected` | WARNING | Request rejected (model not ready) | Why 503 was returned |
| `bremen.prediction.preflight.start` | DEBUG | `run_h5_preflight` entered | Stage boundary |
| `bremen.prediction.preflight.completed` | INFO | Preflight passed | H5 container is valid |
| `bremen.prediction.preflight.failure` | ERROR | Preflight failed (reason category) | H5 container is invalid |
| `bremen.prediction.preprocessing.start` | DEBUG | `run_preprocessing_bridge` entered | Stage boundary |
| `bremen.prediction.preprocessing.completed` | INFO | Bridge produced feature vector | Features extracted |
| `bremen.prediction.preprocessing.failure` | ERROR | Bridge failed (reason category) | Feature extraction failed |
| `bremen.prediction.inference.start` | DEBUG | `predict_proba_portable` called | Stage boundary |
| `bremen.prediction.inference.success` | INFO | Inference completed | Prediction produced |
| `bremen.prediction.inference.failure` | ERROR | Inference raised | Inference engine failed |
| `bremen.prediction.completed` | INFO | Job stored as completed | Async job finished |
| `bremen.prediction.failed` | ERROR | Job stored as failed with safe error category | Async job failed |

**Level classification summary:**
- **INFO**: Successful lifecycle transitions, startup milestones, successful stage boundaries.
- **WARNING**: Configured degraded state (checksum skipped, model not ready but service still answers health/version), request rejected due to unready model.
- **ERROR**: Startup load failure, S3 failure, checksum mismatch, `joblib.load()` failure, validation failure, preflight failure, preprocessing failure, inference failure, job failure.
- **DEBUG**: Stage boundaries that are useful for timing analysis but not required for normal App Runner smoke verification (checksum start, load start, preflight/preprocessing/inference start).

## 7. Startup Log Events

Add log events at these points:

1. **`__main__.py` `main()`** — After `configure_logging()`, emit:
   - `bremen.startup.begin` INFO — process start, no args.

2. **`__main__.py` `_handle_serve()`** — Emit:
   - `bremen.cli.serve.dispatch` INFO — serve command reached, host/port logged (safe — no secrets in host/port).

3. **`server.py` `run_server()`** — Emit:
   - `bremen.server.starting` INFO — host/port logged.
   - `bremen.server.started` INFO — after `server.serve_forever()` called.

4. **`server.py` `_make_handler()`** — If `_load_synthetic_model()` is called (dev mode only), retain the existing `print()` but also emit:
   - `bremen.model.synthetic_mode` INFO — dev/smoke synthetic model loaded.

5. **`model_state.py` `load_at_startup()`** — Already has some logging but missing events. Replace/add:
   - `bremen.model.config.read` INFO at entry with safe fields.
   - Existing `_logger.warning` for missing URI → `bremen.model.config.missing`.
   - After successful load + validation → `bremen.model.ready` INFO.

## 8. Configuration Log Events

Add in `model_state.py` `load_at_startup()`:

- `bremen.model.config.read` — logged after env var read. Safe fields:
  - `model_version` value (safe version string).
  - `uri_scheme` — one of `s3`, `file`, `local`, `missing`.
  - `checksum_present` — boolean.
  - `checksum_algorithm` — hardcoded `sha256`.
  - `staging_dir_source` — `config` or `default` (not the actual path value).
- `bremen.model.config.missing` — logged when `model_uri` is empty (already partially present as `_logger.warning`).
- `bremen.model.config.detected` — logged when all env vars are present and non-empty.

Do NOT log:
- Full S3 URI (bucket/key may be sensitive — log `uri_scheme=s3` only).
- Full local filesystem paths.
- Raw checksum value (log `checksum_present=true` only; test/debug level may differ).

## 9. Model Artifact Staging Log Events

Add in `model_artifacts.py`:

Function `stage_model_artifact()`:
- `bremen.model.artifact.stage.start` INFO — scheme selected: `s3` or `local`.

Function `stage_s3_model_artifact()`:
- `bremen.model.artifact.stage.start` INFO — S3 download begins.
- `bremen.model.artifact.stage.success` INFO — S3 download complete, log `size_bytes` if available.
- `bremen.model.artifact.stage.failure` ERROR — log exception class and safe message (first sentence of error string, no stack trace in the log message — the exception traceback is separate).
- Temp file cleanup: on failure, if cleanup raises, do NOT log a separate event (the failure event is sufficient).

Function `_stage_local_artifact()`:
- Same three events as S3, but less critical (local staging is unlikely in App Runner).

## 10. Checksum / Trust Boundary Log Events

Add in `model_artifacts.py` `verify_file_sha256()`:

- `bremen.model.checksum.verify.start` DEBUG — checksum verification about to begin.
- `bremen.model.checksum.verify.success` INFO — verification passed.

Add in `model_state.py` `load_at_startup()`:
- `bremen.model.checksum.verify.failure` ERROR — mismatch with safe summary (no full checksum logged).
- `bremen.model.checksum.verify.skipped` WARNING — no expected checksum configured.

The existing `_logger.error()` in `model_state.py` already logs a mismatch — replace with the structured event name.

Do NOT log:
- Full SHA-256 hex digest. Log `checksum_present=true` and `checksum_algorithm=sha256`. If debugging requires full checksum, use DEBUG level with explicit justification.

Rationale: An operator needs to know *that* checksum verification succeeded or failed, not *what* the digest is. Full digests may appear in CloudWatch and add noise.

## 11. Model Load / Package Validation Log Events

Add in `model_state.py` `load_at_startup()`:

- `bremen.model.load.start` DEBUG — before `joblib.load()` call.
- `bremen.model.load.success` INFO — after `joblib.load()` returns.
- `bremen.model.load.failure` ERROR — exception from `joblib.load()`, log exception class and safe first-line message.

- `bremen.model.validation.success` INFO — after `isinstance(package, dict)` check.
- `bremen.model.validation.failure` ERROR — package is not dict, log actual type.

- `bremen.model.ready` INFO — final state: `model_ready=true`, model_version, artifact size.
- `bremen.model.not_ready` WARNING — final state: `model_ready=false`, failure reason stage.

The existing `_logger.info("Model loaded: version=%s, path=%s, size=%d bytes")` in `model_state.py` is close to what we need — convert to `bremen.model.ready` with safely formatted message (path logged only as basename, not full path).

## 12. API Route Logging Scope

Add log events at these route-level points only:

### `POST /predictions` — in `server.py` `do_POST()` or `app.py` `handle_submit_prediction()`:

- `bremen.prediction.request.accepted` INFO — job_id (UUID, safe), no request body fields.
- `bremen.prediction.request.rejected` WARNING — model not ready, safe reason string.

Do NOT log:
- Every `/health` GET request — App Runner health check polling would flood logs.
- Every `/model/version` GET request — polled frequently.
- Every `/predictions/{id}` GET request — low value, would add noise.
- Full request body.
- `target_scan_ref` or `control_scan_ref` values (these may be sensitive paths or identifiers).

### Request-level trace ID

No explicit trace ID is required in PR 0041. The job_id is already generated and returned. For DEBUG-level logs, the job_id can be included where available.

## 13. H5 Preflight / Preprocessing / Inference Observability

Add minimal stage boundary logs in `inference_handler.py` `run_inference()`:

- `bremen.prediction.preflight.completed` INFO — preflight passed.
- `bremen.prediction.preflight.failure` ERROR — preflight failed, log `preflight.status`.
- `bremen.prediction.preprocessing.completed` INFO — preprocessing bridge passed.
- `bremen.prediction.preprocessing.failure` ERROR — bridge failed, log exception class and safe message.
- `bremen.prediction.inference.success` INFO — inference produced probability (log as safe ordinal, e.g., `probability_ordinal=high|medium|low`, not raw value).
- `bremen.prediction.inference.failure` ERROR — inference exception, log exception class and safe message.

Add in `inference.py` `predict_proba_portable()`:
- `bremen.prediction.inference.start` DEBUG — stage boundary.
- Do NOT log feature values, coefficients, or intermediate math.

Do NOT add logs in:
- `preflight.py` `run_h5_preflight()` — too granular, individual check results would be noise.
- `preprocessing_bridge.py` `build_feature_table()` — per-feature computation would be noise.
- Individual feature computation functions (`_sigma_rms`, `_mahalanobis_difference`, etc.).

## 14. Redaction and Safe Fields Policy

### Allowed fields in log messages:

| Field | Example | Notes |
|-------|---------|-------|
| `event` | `bremen.model.ready` | Always first in message |
| `stage` | `startup`, `config`, `staging`, `load`, `prediction` | Categorisation |
| `status` | `started`, `completed`, `failed` | Outcome |
| `exception_class` | `ValueError`, `ClientError` | From `type(exc).__name__` |
| `safe_reason` | `S3 download failed` | First sentence of exception, truncated to 200 chars |
| `uri_scheme` | `s3`, `file`, `local`, `missing` | **Not** the full URI |
| `model_version` | `v0.1` | Version string is safe |
| `checksum_present` | `true`, `false` | Boolean only |
| `checksum_algorithm` | `sha256` | Always sha256 |
| `staging_dir_source` | `config`, `default` | Source indicator only, not the value |
| `size_bytes` | `123456` | File size — safe integer |
| `host` | `0.0.0.0` | From server config |
| `port` | `8000` | Integer port |
| `job_id` | UUID string | Non-sensitive job identifier |
| `model_ready` | `true`, `false` | Boolean state |
| `model_configured` | `true`, `false` | Boolean state |
| `count` | `15` | Feature count, measurement count — safe integers |

### Forbidden fields (must never appear in log messages):

| Forbidden | Rationale |
|-----------|-----------|
| `patient_id` | Patient-identifying information |
| `target_scan_ref` | May contain patient or study identifiers |
| `control_scan_ref` | May contain patient or study identifiers |
| Raw H5 arrays | Spectral data is patient-derived |
| Feature values (raw 15 floats) | Model-input data is patient-derived |
| Model coefficients | Model IP |
| Full local path containing `/Users/` | Developer's local machine path |
| `AWS_ACCESS_KEY_ID` | Credential |
| `AWS_SECRET_ACCESS_KEY` | Credential |
| `AWS_SESSION_TOKEN` | Credential |
| `Authorization` header | Auth token |
| Request body | May contain sensitive refs |
| Full S3 URI (bucket+key) | Bucket/key naming may encode study info |
| Full raw checksum hex string | Operational noise, no debugging value at INFO level |
| Raw registry URL | Account ID leakage |

## 15. Implementation Files

### Allowed to modify:

| File | Changes |
|------|---------|
| `src/bremen/logging_config.py` | **New file.** Central logging config module. |
| `src/bremen/__main__.py` | Add `configure_logging()` call in `main()`. Add `bremen.startup.begin` and `bremen.cli.serve.dispatch` events. |
| `src/bremen/api/server.py` | Add `bremen.server.starting` and `bremen.server.started` logs in `run_server()`. Add `bremen.prediction.request.accepted`/`rejected` in `do_POST()` for `/predictions`. Retain existing `print()` for backwards compatibility. |
| `src/bremen/api/model_state.py` | Replace free-text logging with structured event logs: `bremen.model.config.read`, `bremen.model.config.missing`, `bremen.model.config.detected`, `bremen.model.checksum.verify.*`, `bremen.model.load.*`, `bremen.model.validation.*`, `bremen.model.ready`, `bremen.model.not_ready`. |
| `src/bremen/model_artifacts.py` | Add `bremen.model.artifact.stage.*` and `bremen.model.checksum.verify.*` events. Inject logger via `get_logger(__name__)`. |
| `src/bremen/api/inference_handler.py` | Add stage boundary logs: `bremen.prediction.preflight.*`, `bremen.prediction.preprocessing.*`, `bremen.prediction.inference.*`, `bremen.prediction.completed`, `bremen.prediction.failed`. |
| `tests/test_bremen_logging.py` | **New file.** Tests for logging config and event emission. |
| Existing runtime tests | Add narrow assertions for event emission (e.g., test that model startup failure logs `bremen.model.not_ready`). |
| `.project-memory/pr/0041-runtime-observability-logging/reviews/plan-review.yml` | Created by plan_review agent. |
| `.project-memory/pr/0041-runtime-observability-logging/reviews/precommit-review.yml` | Created by precommit_review agent. |

### Forbidden to modify:

- `src/bremen/training/**` — No training code changes.
- Feature schema files.
- `docs/adr/**` — No ADR changes.
- `docs/api_contract.md`, `docs/h5_metadata_contract.md`, `docs/model_release_package.md`, `docs/qc_gates.md` — No contract changes.
- `docs/architecture.md` — Not modified unless a tiny note is justified (not justified here).
- `ROADMAP.md` — Not modified (logging is operational, not roadmap-relevant).
- `Dockerfile` — No Docker changes.
- `.github/**` — No CI/CD changes.
- `infra/terraform/**` — No infra changes.
- Real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` artifacts.
- Secrets, account IDs, access keys.

## 16. Test Plan

### New file: `tests/test_bremen_logging.py`

Must contain:

| Test | Purpose |
|------|---------|
| `test_default_level_is_info` | `configure_logging()` sets root level to INFO when no env var. |
| `test_env_var_respected` | `BREMEN_LOG_LEVEL=DEBUG` sets root level to DEBUG. |
| `test_idempotent` | Calling `configure_logging()` multiple times does not duplicate handlers. |
| `test_missing_model_config_emits_event` | Simulate missing env vars in `ModelState.load_at_startup()`, verify `bremen.model.config.missing` is emitted via `caplog`. |
| `test_detected_model_config_logs_safe_fields` | Simulate present env vars, verify log contains `uri_scheme`, `model_version`, `checksum_present` — not raw URI, not full checksum, not full path. |
| `test_s3_staging_success_events` | With fake S3 client, verify `bremen.model.artifact.stage.start` and `bremen.model.artifact.stage.success` are emitted, and `bremen.model.artifact.stage.failure` is NOT emitted. |
| `test_s3_staging_failure_events` | With fake S3 client that raises, verify `bremen.model.artifact.stage.start` and `bremen.model.artifact.stage.failure` are emitted. |
| `test_checksum_mismatch_logs_failure` | With mismatched checksum, verify `bremen.model.checksum.verify.failure` is emitted and `bremen.model.load.start` is NOT emitted. |
| `test_successful_model_load_logs_ready` | With valid local joblib, verify `bremen.model.ready` is emitted with `model_ready=true`. |
| `test_failed_model_load_logs_not_ready` | With invalid joblib, verify `bremen.model.not_ready` is emitted with `model_ready=false` and safe reason. |
| `test_prediction_rejected_logs_one_event` | When model not ready, `POST /predictions` emits exactly one `bremen.prediction.request.rejected` event — not request body, not stack trace. |
| `test_no_secrets_in_logs` | Inject `AWS_ACCESS_KEY_ID=test_key`, `AWS_SECRET_ACCESS_KEY=test_secret`, `Authorization=Bearer test` into environment or request headers, run startup and prediction scenarios, verify none of these values appear in `caplog.text`. |
| `test_no_patient_data_in_logs` | Run prediction with synthetic H5 containing `patient_id=TEST-PATIENT`, verify log does not contain `TEST-PATIENT`. |
| `test_no_raw_paths_in_logs` | Use a local model path under `/Users/`, verify log does not contain `/Users/`. |
| `test_health_no_noisy_logs` | Call `handle_health()`, verify no `bremen.health` or `bremen.prediction` events are emitted. |

### Existing tests — narrow additions:

- `tests/test_bremen_model_startup_staging.py` — Add `caplog` assertions to verify event emission alongside existing mock-based assertions (e.g., `test_ModelState_not_ready_on_download_failure` should also verify `bremen.model.artifact.stage.failure` and `bremen.model.not_ready` are emitted).
- `tests/test_bremen_api_server.py` — Add assertion to `test_submit_returns_503_when_model_not_ready` that verifies `bremen.prediction.request.rejected` is emitted.
- `tests/test_bremen_inference_integration.py` — Add assertion to `test_end_to_end_synthetic_inference` that verifies `bremen.prediction.inference.success` is emitted.
- `tests/test_bremen_h5_preflight.py` — Add assertion to `test_valid_synthetic_h5_passes` that verifies `bremen.prediction.preflight.completed` is not emitted by `run_h5_preflight()` alone (only by `run_inference()`).
- `tests/test_bremen_preprocessing_bridge.py` — Add assertion to `test_valid_produces_15_features` that verifies `bremen.prediction.preprocessing.completed` is not emitted by `run_preprocessing_bridge()` alone (only by `run_inference()`).

## 17. Validation Commands

```
# Compile check
python -m compileall src tests

# New logging tests
python -m pytest -q tests/test_bremen_logging.py

# Existing test suites (must still pass)
python -m pytest -q tests/test_bremen_model_startup_staging.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_inference_integration.py
python -m pytest -q tests/test_bremen_h5_preflight.py
python -m pytest -q tests/test_bremen_preprocessing_bridge.py

# Full suite
python -m pytest -q

# Secret/pattern grep checks (must return no matches)
grep -rn 'AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|session.token\|/Users/' src/bremen/ --include='*.py' | grep -v '.pyc' || echo "No secrets leaked"
grep -rn '\.h5$\|\.hdf5$\|\.joblib$\|\.pkl$' src/bremen/ --include='*.py' | grep -v '.pyc' || echo "No real artifact references leaked"

# Forbidden import grep
grep -rn 'from.*training\|import.*training' src/bremen/api/ --include='*.py' || echo "No training imports in API"

# Logging budget check (approximate — count lines containing 'bremen\.' in .py files)
grep -rn '"bremen\.' src/bremen/ --include='*.py' | wc -l
```

## 18. Logging Budget

### Startup / model load success path: **6–10 events**

| Event | Count |
|-------|-------|
| `bremen.startup.begin` | 1 |
| `bremen.cli.serve.dispatch` | 1 |
| `bremen.server.starting` | 1 |
| `bremen.server.started` | 1 |
| `bremen.model.config.detected` | 1 |
| `bremen.model.artifact.stage.start` | 1 |
| `bremen.model.artifact.stage.success` | 1 |
| `bremen.model.checksum.verify.success` | 1 |
| `bremen.model.load.success` | 1 |
| `bremen.model.validation.success` | 1 |
| `bremen.model.ready` | 1 |
| **Total** | **~11** |

If local file (no staging): subtract 2 → **~9**.

### Model load failure path: **4–8 events**

| Event | Count |
|-------|-------|
| `bremen.startup.begin` | 1 |
| `bremen.cli.serve.dispatch` | 1 |
| `bremen.server.starting` | 1 |
| `bremen.model.config.detected` | 1 |
| Stage start/failure | 1–2 |
| Checksum verify failure | 1 |
| `bremen.model.not_ready` | 1 |
| **Total** | **~7–9** |

If config missing early: **~3–4** (startup → cli → server → config missing → not_ready).

### Prediction success path: **3–5 stage-level events**

| Event | Count |
|-------|-------|
| `bremen.prediction.request.accepted` | 1 |
| `bremen.prediction.preflight.completed` | 1 |
| `bremen.prediction.preprocessing.completed` | 1 |
| `bremen.prediction.inference.success` | 1 |
| `bremen.prediction.completed` | 1 |
| **Total** | **~5** |

### Prediction failure path: **2–4 events**

| Event | Count |
|-------|-------|
| `bremen.prediction.request.accepted` | 1 |
| Stage failure (one of preflight/preprocessing/inference) | 1 |
| `bremen.prediction.failed` | 1 |
| **Total** | **~3** |

If model not ready: **1 event** (`bremen.prediction.request.rejected`).

### Health/version routes: **0 per-request events**

No log events for normal health checks. Deliberate exclusion to prevent noise.

### Total events for a single startup + prediction call: **~16–20** maximum.

This budget ensures CloudWatch log volume stays minimal and operators can quickly scan through a startup + one prediction sequence.

## 19. Block-Yourself Conditions

Block implementation if:

- [ ] Logs require real AWS calls (S3 download, S3 client) — tests must use fake/injectable clients.
- [ ] Logs expose `patient_id`, patient metadata, or any patient-identifying information.
- [ ] Logs expose raw H5 arrays, feature values, or model coefficients.
- [ ] Logs expose `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `Authorization` header, or full request body.
- [ ] Logs expose full local developer paths (`/Users/...`).
- [ ] Logs expose full raw S3 URI beyond `uri_scheme=s3`.
- [ ] Logs are added broadly without observability justification (any addition must answer the 5 questions from the objective).
- [ ] Logs change inference behavior (math, feature schema, model package format).
- [ ] Logs change training code.
- [ ] Logs add a heavy dependency (e.g., JSON logging library, structured logging framework, APM agent).
- [ ] Tests need real cloud services, real H5 files, or real model artifacts.
- [ ] Implementation cannot keep event count within the defined budget.

## 20. Rollback Plan

Revert PR 0041 by reverting the merge commit:

```
git revert -m 1 <merge-commit-sha>
```

After revert:
- Runtime behavior returns to PR 0040 behavior exactly.
- `logging_config.py` is removed.
- `__main__.py` removes `configure_logging()` call — original `print()` statements remain.
- `model_state.py` and `model_artifacts.py` revert to pre-existing `_logger.warning`/`_logger.error` calls (these still exist, they just had no effect without `configure_logging()`).
- `inference_handler.py` reverts stage boundary logs.
- Test file `test_bremen_logging.py` is removed.
- Existing test suites pass without any changes to model loading or inference.

No rollback risk to:
- Model loading or inference behavior (logging is read-only).
- Feature schema (no changes).
- Model package format (no changes).
- Training code (no changes).
- API contract (no changes).

## 21. Follow-up PR Recommendation

PR 0042 may add:
- App Runner smoke runbook with log event reference (documenting which events to look for in CloudWatch during startup failure scenarios).
- Safe diagnostic fields in health/model-version responses (e.g., `startup_stage`, `failure_reason`) for cases where logs are not immediately accessible.

These are separate from PR 0041, which focuses exclusively on logs.

## 22. Implementation Agent Assignment

Implementation agent: coder
