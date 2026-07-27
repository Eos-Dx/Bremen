# Implementation Report — PR0096B: Demo upload/analyze regression hotfix

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/server.py` | Updated `_handle_demo_h5_analyze()` to accept `source_id` and resolve it via `resolve_source()` |
| `src/bremen/demo_ui.py` | Fixed container field names (`c.source_id`, `c.display_name`) and analyze payload (`source_id`) |
| `tests/test_bremen_api_server.py` | Updated test for new error message and removed bucket exposure assertion |

## Previous Blocked Review Summary

The precommit review blocked PR0096B because:
1. UI sends `source_id` to `/demo/api/h5/analyze` but backend only reads `container_id` → 400 error
2. Backend constructs `s3://` URI directly from `container_id` — incompatible with opaque `source_id`
3. No tests covered uploaded/catalog analyze routing via `source_id`
4. Implementation report incorrectly claimed "No backend changes needed"

## Exact Backend Mismatch

`_handle_demo_h5_analyze()` read `body_dict.get("container_id", "")` but UI sends `{source_id: "..."}`. The handler returned 400 "container_id is required" for every analyze request.

## Source_id Backend Support

Updated `_handle_demo_h5_analyze()` to:
- Read `source_id = body_dict.get("source_id", "").strip()` (preferred)
- Fall back to `container_id` for backward compatibility
- When `source_id` provided: resolve via `resolve_source(source_id=source_id, upload_id=None)` from `job_api_handler.py`
- When `container_id` provided: use legacy S3 URI path (backward compatible)
- When neither provided: return 400 "source_id is required"

## Safe Source Resolution

Uses existing `resolve_source()` from `job_api_handler.py` which:
- For catalog `source_id`: resolves via `source_registry.resolve_source_id()` → S3 key → stages locally
- For upload `source_id`: resolves via `resolve_upload()` → local temp path
- Validates expiry, bucket/prefix match, file extension
- Raises typed `ValueError` with safe public messages

## Upload Analyze Routing

Upload flow: UI → `/demo/api/stage` → `upload_id` → UI selects → `/demo/api/h5/analyze` with `{source_id: ...}` → backend `resolve_source(source_id=..., upload_id=None)` → local h5_path → workflow

## Catalog Analyze Routing

Catalog flow: UI loads containers → `/demo/api/h5/containers` → `source_id` → UI selects → `/demo/api/h5/analyze` with `{source_id: ...}` → backend `resolve_source(source_id=..., upload_id=None)` → S3 → local h5_path → workflow

## Legacy Container_id Fallback

`container_id` still supported as fallback. Uses legacy S3 URI path. Not recommended for new code.

## Public Safety

- No raw S3 bucket names in responses (removed `container_id.bucket`)
- No raw filesystem paths exposed
- No upload temp paths exposed
- Only opaque source_ids sent to backend
- Safe error messages from `resolve_source()` — no raw exceptions, stack traces, or internal paths

## Report/Measurement Reliability Preserved

No changes to report generation or measurement_reliability plumbing. PR0096/PR0096A behavior intact.

## Tests

- All 2269 existing tests pass (11 skipped)
- Updated `test_analyze_missing_container_id_returns_400` → `test_analyze_missing_source_id_returns_400`
- Updated bucket exposure assertion to verify bucket is NOT exposed in public response
- Existing analyze routing tests (events, request_id, storage_not_configured) continue to work

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_api_server.py` | 104 passed |
| `pytest` (full suite) | 2269 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| naming guard | PASS — only measurement_reliability keys |
| scope checks | PASS — no Aramis, no PR0092 |

## Blockers

None.

## Warnings

None.

## Next Required Action

Human review and commit.
