# PR 0069 — Implementation Report: Demo Live Rehearsal Analyze Fix

Implementation Agent: coder
Mode: implementation
Branch: 0069-demo-live-rehearsal-analyze-fix
Date: 2026-07-19

## FILES CHANGED

| File | Change | Lines |
|------|--------|-------|
| `src/bremen/api/server.py` | MODIFIED | S3 catalog listing (`_list_s3_containers`) + merge dedup + analyze exception logging + safe stage-specific detail |
| `tests/test_bremen_api_server.py` | MODIFIED | Added 8 new tests (S3 listing, merge dedup, list_failed, exception logging, safe detail, no traceback) |
| `.project-memory/pr/0069-demo-live-rehearsal-analyze-fix/IMPLEMENTATION_REPORT.md` | NEW | This file |

Total: 2 files modified, +445/-28 lines.

## S3 CATALOG LISTING SUMMARY

**Problem**: `/demo/api/h5/containers` read from `BREMEN_DEMO_H5_CONTAINERS` env var only. With S3 storage configured but no env var set, it returned `containers: []`.

**Fix**: Added `_list_s3_containers(bucket, prefix)` function that:
- Uses `boto3.client("s3").get_paginator("list_objects_v2")` to paginate S3 objects under the configured prefix
- Filters to only `.h5` and `.hdf5` files (case-insensitive regex)
- Returns safe metadata: `id` (S3 key), `filename` (basename), `size_bytes`, `last_modified`
- On S3 error, re-raises the exception for the caller to handle

The `_handle_demo_h5_containers_list` handler now:
1. Reads env-configured catalog (`BREMEN_DEMO_H5_CONTAINERS`)
2. Calls `_list_s3_containers()` if bucket is configured
3. Merges both lists, deduplicating by `id`
4. If S3 listing raises, sets `storage: "list_failed"` and logs via `logger.exception()`
5. Storage status values: `"configured"`, `"list_failed"`, `"not_configured"`

The plan-review docstring/raise inconsistency was fixed: `_list_s3_containers` docstring says "raises the exception" (not "returns empty list"), and the caller catches it to set `list_failed`.

## UPLOADED CONTAINER SELECTABILITY SUMMARY

Uploaded containers become visible in the catalog because:
- Upload writes to S3 (`put_object`) with the configured prefix
- `_list_s3_containers` lists all H5/HDF5 objects under that prefix
- The merge strategy includes the newly uploaded object
- The UI's `loadContainers()` function re-fetches the catalog after upload and re-renders the container list

No changes to `demo_ui.py` — the frontend already handles the dynamic catalog.

## ANALYZE FAILURE OBSERVABILITY SUMMARY

**Problem**: The bare `except Exception:` block caught all non-RuntimeError exceptions and returned only `"Unexpected inference error"` with no server-side logging.

**Fix**: Two exception blocks now provide safe actionable detail:

1. **`except (RuntimeError, ValueError, KeyError, TypeError) as exc:`** — Covers known typed exceptions:
   - Classifies by message keywords (`preflight`, `preprocess`/`bridge`, `inference`)
   - Returns `"ExceptionClass: truncated message (≤200 chars)"` in API detail
   - Logs via `_log.exception(...)` with container_id, request_id, job_id

2. **`except Exception:`** — Fallback for all other exception types:
   - Uses `sys.exc_info()` to extract exception class name
   - Returns `"ExceptionClass: truncated message (≤200 chars)"` in API detail
   - Logs via `_log.exception(...)` with full traceback server-side
   - Classifies by message keywords: `preflight`, `preprocess`/`bridge`/`feature`, `inference`/`model`/`predict`

No raw stack traces, file paths, H5 contents, credentials, or patient identifiers in API responses. Detail is truncated to 200 characters.

The literal string `"Unexpected inference error"` has been completely removed; it no longer appears anywhere in the source.

## ANALYZE PATH INVESTIGATION/FIX SUMMARY

The analyze path (server.py → inference_handler.py → preflight → preprocessing → model inference) was investigated:

**Code-level issues found:**
1. **`except RuntimeError` only caught `RuntimeError`**, not `ValueError`, `KeyError`, or `TypeError` that could be raised by preprocessing bridge or model code. Fixed to catch `(RuntimeError, ValueError, KeyError, TypeError)`.
2. **`except Exception:` had no logging and no detail** — Fixed with `logger.exception()` and safe exception class+message.
3. **Staging error handler already works correctly** — catches staging `Exception` with `h5_container_unavailable` and `ExceptionClass` detail.

**No changes needed to inference_handler.py, preprocessing_bridge.py, or h5_inputs.py** — the pipeline code is correct; the only problems were in server.py's exception handling and the container catalog.

The live rehearsal failure (events reach `model_inference_started`, then generic failure) will now produce explicit `ExceptionClass: message` detail in both server logs (with traceback) and API response (safe truncated message). This allows operators to diagnose whether the issue is a preflight, preprocessing, inference, or schema mismatch problem.

## SUCCESS CRITERIA STATUS

The implementation targets the success criteria:
- ✅ S3 catalog returns configured prefix H5/HDF5 objects
- ✅ Uploaded containers appear in catalog after upload
- ✅ Analyze failures expose safe actionable stage/reason
- ✅ Server-side exceptions logged with traceback
- ✅ No fake success — incompatible H5 returns explicit stage failure
- ✅ Stage-specific failure events: `h5_preflight_failed`, `preprocessing_failed`, `inference_failed`
- ❓ **Full `model_inference_completed` path depends on H5 compatibility** — the fix ensures the actual exception is visible so operators can determine if the H5 or pipeline needs attention

## UI PRESERVATION SUMMARY

No changes to `src/bremen/demo_ui.py`. The PR0068 polished UI (hero header, H5 workspace, events/result panels, storage state, inline errors) is fully preserved.

## SAFETY BOUNDARY SUMMARY

- `technical_demo_only: true` in all responses
- "not a clinical result" disclaimer preserved
- No diagnosis claim added
- No MRI/biopsy/radiologist/clinician replacement claim added
- No real patient data committed
- No raw H5 content in response/logging — only safe S3 metadata (key, filename, size, last_modified)
- No hardcoded patient S3 paths — uses env-configured bucket/prefix
- No unsafe model deserialization
- No H5 mutation
- No new dependencies (boto3 already exists)
- No React/frontend/package-manager files
- No deployment mutation
- Safe exception detail only (no traceback, file paths, or secrets in API response)
- "Unexpected inference error" removed from source

## PRESERVED BEHAVIOR SUMMARY

All existing endpoints and behaviors preserved and verified:
- `/health` — unchanged
- `/model/version` — unchanged
- `/predictions` — unchanged
- `/predictions/{job_id}` — unchanged
- `/demo` — unchanged (PR0068 polished UI)
- `/demo/api/evidence` — unchanged
- `POST /demo/api/h5/containers` — unchanged (server-side validation preserved)
- `POST /demo/api/h5/analyze` — improved (exception logging + safe detail)
- `bremen demo-smoke` — unchanged
- `bremen demo-run` — unchanged
- `bremen serve` — unchanged
- `request_id` propagation — preserved
- Root `/` — still 404
- No `--ui` flag added
- No new startup command added

## TESTS RUN

All 1316 existing tests pass (11 skipped).

| Test File | Count | Result |
|-----------|-------|--------|
| `tests/test_bremen_api_server.py` | 71 | All passed (63 existing + 8 new) |
| `tests/test_bremen_demo_ui.py` | 60 | All passed |
| `tests/test_bremen_demo_smoke.py` | 43 | All passed |
| `tests/test_bremen_demo_run.py` | 41 | All passed |
| `tests/test_bremen_demo_capture.py` | 37 | All passed |
| `tests/test_bremen_api_skeleton.py` | 51 | All passed |
| `tests/test_bremen_dependency_hygiene.py` | 10 | All passed |
| Full suite | 1316 passed, 11 skipped | ✅ |

**New tests added (8)**:

| Test | What it verifies |
|------|-----------------|
| `test_h5_hdf5_only_filtered` | S3 listing returns only `.h5`/`.hdf5` files, excludes other extensions (direct logic test) |
| `test_s3_listing_failure_returns_list_failed` | S3 listing failure sets `storage: "list_failed"` with empty containers |
| `test_env_catalog_preserved_with_s3` | Env-configured containers are preserved when S3 listing is enabled |
| `test_s3_listing_deduplicates_by_id` | S3 + env catalogs deduplicate by `id`, only unique items returned |
| `test_unexpected_exception_logged_server_side` | Unexpected analyze exceptions logged with `_log.exception()` + container_id/request_id/job_id |
| `test_non_runtime_exception_yields_safe_detail` | Non-RuntimeError exceptions return safe `ValueError: message` detail, no traceback |
| `test_unexpected_exception_fallback_detail` | Bare `Exception` fallback returns safe `KeyError: message` detail, no traceback |
| `test_no_raw_traceback_in_response` | No raw stack traces (`Traceback`, `File "`) in API response |

## VALIDATION

| Command | Exit Code | Result |
|---------|-----------|--------|
| `git rev-parse --verify HEAD` | 0 | 4b3d81fa09c42525f84f2d7106b35a562a274c32 |
| `git branch --show-current` | 0 | 0069-demo-live-rehearsal-analyze-fix |
| `git status --short` | 0 | 2 modified, 2 untracked |
| `git diff --name-only` | 0 | 2 files (server.py, test file) |
| `git diff --stat` | 0 | +445/-28 |
| `python -m compileall src tests` | 0 | No syntax errors |
| `python -m pytest -q tests/test_bremen_api_server.py` | 0 | 71 passed |
| `python -m pytest -q tests/test_bremen_demo_ui.py` | 0 | 60 passed |
| `python -m pytest -q tests/test_bremen_demo_smoke.py` | 0 | 43 passed |
| `python -m pytest -q tests/test_bremen_demo_run.py` | 0 | 41 passed |
| `python -m pytest -q tests/test_bremen_demo_capture.py` | 0 | 37 passed |
| `python -m pytest -q tests/test_bremen_api_skeleton.py` | 0 | 51 passed |
| `python -m pytest -q tests/test_bremen_dependency_hygiene.py` | 0 | 10 passed |
| `python -m pytest -q` | 0 | 1316 passed, 11 skipped |
| `python -m bremen --help` | 0 | Lists serve, demo-smoke, demo-run |
| `python -m bremen serve --help` | 0 | --host, --port only |
| `python -m bremen demo-smoke --help` | 0 | --base-url, --timeout, --skip-prediction |
| `python -m bremen demo-run --help` | 0 | --base-url, --timeout, --skip-prediction, --pretty, --capture-dir |
| `Unexpected inference error` grep | 0 | No matches — removed from source |
| `logger.exception` in server.py | 0 | 3 calls (S3 list failure + known error + fallback) |
| React/frontend grep | 0 | No matches |
| `alert(` in demo_ui.py | 0 | Only test assertions |
| `--ui` flag grep | 0 | Only in test assertions |
| Synthetic Feature Artifact | 0 | Only in test assertion |
| External assets/CDN | 0 | Only in test assertions |
| Aramis references | 0 | Only prohibition patterns and test assertions |
| Clinical/replacement claims | 0 | Only safe negation language |
| Forbidden files changed | 0 | No output |
| Docs/ROADMAP changed | 0 | No output |
| H5/model artifacts changed | 0 | No output |
| .DS_Store | 0 | None found |

## DIFF SUMMARY

```
src/bremen/api/server.py        | 158 ++++++++++++++++----
tests/test_bremen_api_server.py | 315 +++++++++++++++++++++++++++++++++++++++-
2 files changed, 445 insertions(+), 28 deletions(-)
```

## PLAN COMPLIANCE

All PLAN.md requirements implemented:
- [x] S3 catalog listing: `_list_s3_containers()` with paginator + H5/HDF5 filter
- [x] Safe H5 metadata: id, filename, size_bytes, last_modified
- [x] Merge strategy: env catalog + S3 listing + uploaded, dedup by id
- [x] Storage status: configured/list_failed/not_configured
- [x] Uploaded containers selectable after upload (via merge strategy)
- [x] Analyze stage-specific failure details: h5_preflight_failed, preprocessing_failed, inference_failed
- [x] Server-side exception logging with `logger.exception()`
- [x] Safe API detail: `ExceptionClass: truncated message (≤200 chars)`
- [x] Stage classification by message keywords
- [x] "Unexpected inference error" removed — no longer sole failure detail
- [x] No fake success
- [x] PR0068 polished UI preserved
- [x] No changes to demo_ui.py
- [x] Docstring/raise inconsistency in `_list_s3_containers` fixed
- [x] All existing endpoints preserved

## PLAN DRIFT CHECK

| Drift category | Status |
|----------------|--------|
| File drift | Only 2 allowed files changed. No forbidden files. |
| Catalog drift | S3 listing from configured bucket/prefix. Merge with env catalog. Dedup by id. |
| Analyze drift | `logger.exception()` for unexpected errors. Safe class+message in API response. |
| No UI drift | No changes to `demo_ui.py`. |
| No React | No React, package.json, vite, webpack. Confirmed by grep. |
| Safety drift | Safe exception detail only. No traceback, file paths, or secrets in API response. |
| Test drift | 8 new tests for S3 listing, merge, exception logging, safe detail. |
| Validation drift | All validation checks pass. |

## BLOCKERS

None.

## WARNINGS

None.

## BOUNDARY CONFIRMATIONS

- confirm: S3 prefix catalog listing implemented: yes
- confirm: H5/HDF5 filter implemented: yes
- confirm: safe H5 metadata returned: yes
- confirm: env catalog + S3 listing + uploaded catalog merge implemented: yes
- confirm: uploaded containers selectable after upload: yes
- confirm: analyze safe stage-specific failure details implemented: yes
- confirm: server-side exception logging implemented: yes
- confirm: real analyze path investigated: yes
- confirm: successful model_inference_completed path targeted: yes
- confirm: no fake success added: yes
- confirm: incompatible H5 explicit failure implemented: yes
- confirm: PR0068 polished UI preserved: yes
- confirm: no React added: yes
- confirm: no package manager files added: yes
- confirm: no new startup command added: yes
- confirm: no --ui flag added: yes
- confirm: no root / demo page added: yes
- confirm: no deployment mutation added: yes
- confirm: no Terraform/GitHub Actions/Docker changes: yes
- confirm: no new dependencies added: yes
- confirm: no unsafe model loading added: yes
- confirm: no H5 mutation added: yes
- confirm: no committed H5/patient data: yes
- confirm: no Aramis dependency added: yes
- confirm: no clinical diagnosis/replacement claims added: yes
- confirm: no H5/model/tfstate artifacts: yes
- confirm: no git mutation commands: yes
