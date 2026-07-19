# PR 0069 — Plan Demo Live Rehearsal Analyze Fix

Author: plan
Mode: planning only
Branch: 0069-demo-live-rehearsal-analyze-fix

## Objective

Fix the three specific blocker issues found during live demo rehearsal so the demo path is complete enough for serious rehearsal and eventual product-owner demo:

1. **Container catalog is empty** — `/demo/api/h5/containers` reads from `BREMEN_DEMO_H5_CONTAINERS` env var only. It must also list `.h5`/`.hdf5` objects from the configured S3 bucket/prefix.
2. **Uploaded containers not visible** — After browser upload to S3, the container is not returned by the list endpoint because the env var isn't updated. The list endpoint must include both env-configured and S3-listed containers.
3. **Analyze failure is opaque** — The `except Exception:` handler in `_handle_demo_h5_analyze` returns only "Unexpected inference error" without logging the exception server-side or exposing safe actionable detail.

No new features. No React. No UI redesign. No new dependencies.

## Live rehearsal evidence (confirmed)

- `/model/version` returns `model_status: "ready"` ✓
- Demo H5 storage configured (`BREMEN_DEMO_H5_BUCKET`) ✓
- Browser upload writes H5 to S3 successfully ✓
- S3 contains H5 objects under `s3://matur-misc-uk/bremen/prediction-inputs/smoke/v0.1/` ✓
- `/demo/api/h5/containers` returns `containers: []` ✗ — env-var only, no S3 listing
- `/demo/api/h5/analyze` can stage/download H5 from S3 ✓
- Analyze events reach: `h5_staging_completed` → `h5_preflight_started` → `preprocessing_started` → `model_inference_started` → `inference_failed` (generic) ✗
- API returns generic `Unexpected inference error` ✗ — no safe stage/reason

## Required reads — observed facts

### `src/bremen/api/server.py`
- `_handle_demo_h5_containers_list()` reads `BREMEN_DEMO_H5_CONTAINERS` env var only. No S3 listing.
- `_handle_demo_h5_containers_upload()` writes to S3 via `boto3.client("s3").put_object()`.
- `_handle_demo_h5_analyze()` has:
  - `except RuntimeError` — catches preflight/preprocessing/inference errors with partial detail
  - `except Exception:` — bare catch, logs nothing, returns only "Unexpected inference error"
- The analyze handler does NOT import `logging` at function scope or call `logger.exception()`.

### `src/bremen/h5_inputs.py`
- `stage_h5_input(h5_uri)` — S3 download via boto3.
- Uses `parse_s3_uri` from `model_artifacts.py`.

### `src/bremen/demo_config.py`
- `read_demo_h5_config()` returns `h5_bucket`, `h5_prefix`, `allow_upload`, `upload_max_bytes`.

### `src/bremen/api/inference_handler.py`
- `run_inference()` — full pipeline: preflight → preprocessing bridge → model inference → evidence.
- Raises `RuntimeError` on preflight failure.
- May raise other exceptions (`ValueError`, `KeyError`, etc.) from preprocessing/model code.

### Tests
- 1308 tests pass. All PR0060–0068 merged.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/api/server.py`** — MODIFY:
   - Fix `_handle_demo_h5_containers_list()` to S3-list containers from configured bucket/prefix.
   - Fix `_handle_demo_h5_analyze()` to log exceptions server-side and return safe actionable detail.
   - Fix `except Exception:` to capture exception class, stage, and safe message.
   - Merge env-configured catalog + S3-listed containers + runtime-uploaded containers.

2. **`tests/test_bremen_api_server.py`** — MODIFY:
   - Add tests for S3 listing mock.
   - Add tests for merged container catalog.
   - Add tests for analyze exception logging and safe detail.
   - Add test for successful mock inference returning expected shape.

**Allowed only if repository inspection proves necessary**:
- `src/bremen/demo_config.py` — MODIFY only if config shape needs extension for S3 listing.
- `src/bremen/api/inference_handler.py` — MODIFY only if the real analyze bug is code-level in the inference/preprocessing pipeline.

## Forbidden files

- `.github/**`, `infra/terraform/**`
- `Dockerfile`, `Dockerfile.training`
- `requirements.txt`, `pyproject.toml`
- `frontend/**`, `web/**`, `ui/**`
- `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `node_modules/**`
- `tests/data/**`
- Any committed `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `tfstate`, `.terraform`
- `config/training/**`, `src/bremen/training/**`
- `docs/**`, `ROADMAP.md`
- Aramis artifacts, model descriptions, feature schemas as dependency

## Exact implementation scope

### 1. Fix `GET /demo/api/h5/containers` — S3 catalog listing

**Current behavior**: Reads `BREMEN_DEMO_H5_CONTAINERS` env var only. If bucket is configured but env var is absent, returns `containers: []`.

**Required behavior**: When `h5_bucket` is configured, list `.h5` and `.hdf5` objects from the configured S3 prefix:

```python
def _list_s3_containers(bucket: str, prefix: str) -> list[dict]:
    """List H5/HDF5 objects under configured S3 prefix.

    Returns a list of container dicts with safe metadata only:
    id (S3 key), filename (basename), size_bytes, last_modified.

    On AccessDenied or other S3 errors, returns empty list and
    sets storage status to ``"list_failed"``.
    """
    import boto3
    import re

    s3 = boto3.client("s3")
    containers = []
    try:
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                filename = key.split("/")[-1] if "/" in key else key
                # Only include H5/HDF5 files
                if not re.search(r"\.h5$|\.hdf5$", key, re.IGNORECASE):
                    continue
                containers.append({
                    "id": key,
                    "filename": filename,
                    "size_bytes": obj.get("Size", 0),
                    "last_modified": obj.get("LastModified", "").isoformat()
                    if hasattr(obj.get("LastModified"), "isoformat") else str(obj.get("LastModified", "")),
                })
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("S3 container listing failed for bucket=%s prefix=%s", bucket, prefix)
        # Return empty list with safe list_failed status
        raise  # Re-raise for the caller to handle

    return containers
```

**Merge strategy** (deduplication by `id`):

```python
# Collect all containers by id to deduplicate
seen_ids = set()
merged = []

# 1. Env-configured catalog
for c in env_containers:
    cid = c.get("id") or c.get("key") or c.get("filename", "")
    if cid not in seen_ids:
        seen_ids.add(cid)
        merged.append(c)

# 2. S3-listed containers
for c in s3_containers:
    cid = c.get("id", "")
    if cid not in seen_ids:
        seen_ids.add(cid)
        merged.append(c)
```

**Storage status values**:
- `"configured"` — bucket set, S3 listing succeeded (even if empty)
- `"list_failed"` — bucket set, S3 listing raised exception
- `"not_configured"` — bucket not set

**Response shape**:

```json
{
    "storage": "configured" | "list_failed" | "not_configured",
    "containers": [...],
    "technical_demo_only": true,
    "request_id": "..."
}
```

### 2. Fix `POST /demo/api/h5/analyze` — Safe failure observability

**Current problem**: The `except Exception:` block catches all non-RuntimeError exceptions with only "Unexpected inference error". No `logger.exception()` call.

**Required fix**:

Replace the bare `except Exception:` with:

```python
except Exception:
    import logging
    _log = logging.getLogger(__name__)
    _log.exception(
        "bremen.demo.analyze.failed\t"
        "stage=analyze\tstatus=failed\t"
        "container_id=%s\trequest_id=%s\tjob_id=%s",
        container_id, request_id, job_id,
    )
    # Determine safe stage class name
    exc_info = sys.exc_info()
    exc_class = exc_info[1].__class__.__name__
    exc_msg = str(exc_info[1])[:200] if str(exc_info[1]) else "No details"

    # Classify by exception type and message keywords
    err_str = exc_msg.lower()
    if "preflight" in err_str:
        event_name = "h5_preflight_failed"
        status_msg = "h5_preflight_failed"
    elif "preprocess" in err_str or "bridge" in err_str or "feature" in err_str:
        event_name = "preprocessing_failed"
        status_msg = "preprocessing_failed"
    elif "inference" in err_str or "model" in err_str or "predict" in err_str:
        event_name = "inference_failed"
        status_msg = "inference_failed"
    else:
        event_name = "inference_failed"
        status_msg = "inference_failed"

    events.append({
        "event": event_name,
        "timestamp": _now(),
        "detail": f"{exc_class}: {exc_msg}",
    })
```

This ensures:
- Every exception is logged server-side with `logger.exception()` (includes traceback)
- The API response includes the exception class name and a safe truncated message
- Stage classification works for common exception types (not just `RuntimeError`)
- No raw stack trace, file paths, H5 content, or secrets in the API response

**Also fix the `except RuntimeError`** block to catch `Exception` rather than just `RuntimeError`, since `ValueError`, `KeyError`, etc. may be raised during preprocessing/inference:

```python
except (RuntimeError, ValueError, KeyError, TypeError) as exc:
    err_str = str(exc).lower()
    # ... existing stage classification ...
    _log.exception("bremen.demo.analyze.known_error\tstage=%s", status_msg)
```

### 3. Fix real analyze path if code-level issue

The implementation agent must investigate and fix if the actual bug is code-level in the inference/preprocessing pipeline. Known failure trace from rehearsal: events reach `model_inference_started`, then fail.

**Potential failure classes to investigate** (in order):
1. Does `run_inference()` accept just `h5_path` (no explicit refs) and handle the canonical layout? — Check `run_inference()` signature and default behavior.
2. Is the H5 at the configured S3 path compatible with the Bremen preprocessing pipeline? — Check if it's a canonical or calibration-sample layout.
3. Does the preprocessing bridge raise an unhandled exception (not `RuntimeError`)? — The bare `except Exception` catches it but provides no detail.
4. Is there a schema mismatch between preprocessing output and model feature columns?

**The implementation should**:
1. First fix the exception logging (section 2 above) so the actual error is visible in server logs.
2. Run a test with a known-good synthetic H5 to verify the pipeline works.
3. If the pipeline fails with a code-level bug, fix it in `inference_handler.py` or `preprocessing_bridge.py` as needed.
4. If the H5 is genuinely incompatible, ensure the API returns a safe actionable reason like `preprocessing_failed: H5 layout not supported` instead of generic "Unexpected inference error".

**Success target**: For at least one demo H5 (e.g., `bremen/prediction-inputs/smoke/v0.1/aramis_real_h5_subset_20260128_5_patients.h5`), Analyse should return events including `model_inference_completed` and a result.

### 4. No changes to `demo_ui.py`

The UI already handles container display, selection, analyze, events, and result panels. The fixes in this PR are all backend (S3 listing, exception logging, error detail). No UI changes needed.

## Non-goals

- No new CLI command, no `--ui` flag.
- No UI redesign or polish (PR0068 already completed).
- No changes to `demo_ui.py`, `demo_run.py`, `demo_smoke.py`, `demo_capture.py`, `__main__.py`.
- No React/frontend stack.
- No new dependencies.
- No deployment mutation.
- No changes to `/health`, `/model/version`, `/predictions` endpoints.
- No changes to upload endpoint (already works).
- No committed H5 files.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization — uses existing `ModelState` and `run_inference()`.
- No new `joblib.load()` or `pickle.load()`.
- No H5 mutation — H5 files read-only during staging/inference.
- No real patient data committed.
- Raw H5 contents not in response or logs — only key, filename, size, last_modified.
- No hardcoded patient S3 paths — uses env-configured bucket/prefix.
- `technical_demo_only: true` in all responses.
- Exception logging is server-side only. API responses receive safe truncated exception class + message (≤200 chars), no traceback, no file paths, no secrets.
- No clinical diagnosis/replacement claims.
- No Aramis references.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_demo_ui.py
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q tests/test_bremen_demo_capture.py
python -m pytest -q tests/test_bremen_api_skeleton.py
if test -f tests/test_bremen_dependency_hygiene.py; then \
  python -m pytest -q tests/test_bremen_dependency_hygiene.py; \
else echo "SKIP missing tests/test_bremen_dependency_hygiene.py"; fi
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
```

### Forbidden-pattern grep checks

```bash
# "Unexpected inference error" — allowed only as fallback, not sole detail
grep -R -I -n "Unexpected inference error" src/bremen tests || true
# Expected: may appear as fallback string only

# logger.exception or exc_info=True for analyze unexpected errors
grep -R -I -n "logger.exception\|exc_info=True" src/bremen/api/server.py || true
# Expected: server-side logging for unexpected analyze failures

# No React/frontend build
grep -R -I -n "React\|react\|package.json\|vite\|webpack" src/bremen tests || true
# Expected: no output

# No alert() for expected errors
grep -R -I -n "alert(" src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No --ui flag
grep -R -I -n -- "--ui\|demo-run --ui" src/bremen tests || true
# Expected: no output

# No synthetic feature artifact as primary product input
grep -n "Synthetic Feature Artifact" src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: not primary flow

# No external assets/CDN
grep -R -I -n "https://\|http://.*cdn\|unpkg\|jsdelivr\|googleapis\|fontawesome" \
  src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No Aramis dependency or product labels
grep -R -I -n "Aramis\|aramis\|M2Q\|BENIGN vs CANCER" \
  src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output

# No clinical/replacement claims
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no new unsafe loading

# Forbidden files unchanged
git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training \
  requirements.txt pyproject.toml config/training frontend web ui \
  package.json package-lock.json yarn.lock pnpm-lock.yaml tests/data

# Docs/ROADMAP unchanged
git diff --name-only -- docs ROADMAP.md
# Expected: no output

# No model/data artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true
# Expected: no output

# No .DS_Store
find . -name ".DS_Store" -print
```

## Platform safety decisions

| Decision | Value |
|----------|-------|
| S3 listing method | `boto3.client("s3").get_paginator("list_objects_v2")` — existing boto3 dependency. |
| Filter | Only `.h5` and `.hdf5` files. Case-insensitive regex. |
| Safe metadata | `id` (key), `filename` (basename), `size_bytes`, `last_modified`. |
| Merge strategy | Env catalog + S3 list + uploaded — deduplicated by `id`. |
| Storage status | `configured`, `list_failed`, `not_configured`. |
| Exception logging | `logger.exception()` for all unexpected analyze errors. |
| Safe API detail | `ExceptionClass: truncated message (≤200 chars)`. No traceback, no file paths, no secrets. |
| Stage classification | Keywords in exception message: `preflight`, `preprocess`/`bridge`/`feature`, `inference`/`model`/`predict`. |
| UI changes | None. |
| New dependencies | None. boto3 already exists. |

## Rollback plan

1. **Revert `src/bremen/api/server.py`** — revert `_handle_demo_h5_containers_list()` and `_handle_demo_h5_analyze()` changes.
2. **Revert test files** — revert `test_bremen_api_server.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 2 files changed (or 3 if inference handler fix needed). No forbidden files. |
| **Catalog drift** | S3 listing from configured bucket/prefix. Merge with env catalog. Dedup by id. |
| **Analyze drift** | `logger.exception()` for unexpected errors. Safe class+message in API response. |
| **No UI drift** | No changes to `demo_ui.py`. |
| **No React** | No React, package.json, vite, webpack. |
| **Safety drift** | No unsafe deserialization, no H5 mutation, no clinical claims. Safe exception detail only. |
| **Test drift** | 5+ new tests. Existing 1308 tests pass unchanged. |
| **Validation drift** | All validation checks pass. `logger.exception` present. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan adds React or a frontend build tool.
- Plan adds `--ui` or another launch command.
- Plan requires new dependencies.
- Plan modifies `demo_ui.py` (not needed).
- Plan keeps "Unexpected inference error" as sole failure detail without logging.
- Plan fails to add `logger.exception()` for unexpected analyze errors.
- Plan fails to merge S3-listed containers into the catalog.
- Plan requires deployment mutation.
- Plan weakens Bremen safety language.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| S3 listing | Use `list_objects_v2` paginator with `.h5`/`.hdf5` filter |
| Catalog merge | Env var list + S3 list + uploaded — dedup by `id` |
| Storage status | `configured` / `list_failed` / `not_configured` |
| Analyze exception handling | `logger.exception()` + safe `Class: message(≤200)` in API |
| Exception type coverage | `RuntimeError`, `ValueError`, `KeyError`, `TypeError`, plus bare `Exception` fallback |
| Stage keyword classification | `preflight`, `preprocess`/`bridge`/`feature`, `inference`/`model`/`predict` |
| UI changes | None |
| Inference handler changes | Only if code-level bug found |
| New dependencies | None |

## Files read

- `ROADMAP.md`
- `docs/api_contract.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `docs/adr/0012-system-of-record-boundary.md`
- `src/bremen/__main__.py`
- `src/bremen/demo_smoke.py`
- `src/bremen/demo_run.py`
- `src/bremen/demo_capture.py`
- `src/bremen/demo_ui.py`
- `src/bremen/demo_evidence.py`
- `src/bremen/demo_config.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `src/bremen/api/model_state.py`
- `src/bremen/api/inference_handler.py`
- `src/bremen/api/preprocessing_bridge.py`
- `src/bremen/h5_inputs.py`
- `src/bremen/model_artifacts.py`
- `tests/test_bremen_demo_ui.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_demo_run.py`
- `tests/test_bremen_demo_capture.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_dependency_hygiene.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0069-demo-live-rehearsal-analyze-fix/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0069 planned as final live rehearsal analyze fix: yes
- confirm: S3 prefix catalog listing planned: yes
- confirm: uploaded containers selectable after upload planned: yes
- confirm: analyze safe stage-specific failure details planned: yes
- confirm: server-side exception logging planned: yes
- confirm: real analyze path investigation planned: yes
- confirm: successful model_inference_completed path targeted: yes
- confirm: no fake success planned: yes
- confirm: incompatible H5 explicit failure planned: yes
- confirm: PR0068 polished UI preserved: yes
- confirm: no React planned: yes
- confirm: no package manager files planned: yes
- confirm: no new startup command planned: yes
- confirm: no `--ui` flag planned: yes
- confirm: no root `/` demo page planned: yes
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: no new dependencies planned: yes
- confirm: no unsafe model loading planned: yes
- confirm: no H5 mutation planned: yes
- confirm: no committed H5/patient data planned: yes
- confirm: no Aramis dependency planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
