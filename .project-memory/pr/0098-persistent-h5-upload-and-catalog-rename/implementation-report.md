# Implementation Report — PR0098: Persistent H5 upload and Patients List rename

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/control_room_ui.py` | Switched upload endpoint, updated success/failure handling, renamed heading |
| `tests/test_bremen_control_room.py` | Added 8 PR0098 tests for upload endpoint, success/failure, and heading |
| `tests/test_bremen_launch_flow.py` | Updated upload test assertion message |
| `tests/test_bremen_launch_flow.js` | Updated JS test mock from /demo/api/stage to /demo/api/h5/containers |
| `tests/test_bremen_data_selection.py` | Updated dead-code check test |

## Upload Endpoint Switch

`handleFileSelect()` now posts to `/demo/api/h5/containers` (persistent S3-backed) instead of `/demo/api/stage` (ephemeral local staging).

Before: `fetch(baseUrl+'/demo/api/stage', {method:'POST', body:file, headers:headers})`
After: `fetch(baseUrl+'/demo/api/h5/containers', {method:'POST', body:file, headers:headers})`

## Success Path

On `data.status === "uploaded"`:
- `selectedSource = {type: "container", id: data.id, filename: data.filename, size: data.size_bytes, stale: false}`
- Status text: "Uploaded: <filename>"
- State: ready_to_submit
- Calls `loadContainerCatalog()` to refresh the patient list
- Calls `updateReadiness()`

## Catalog Refresh Call

After successful upload, `loadContainerCatalog()` is called to refresh the patient list so the newly uploaded patient appears in the list immediately.

## Failure Path

On upload failure:
- `selectedSource = null` (always cleared)
- `setState("idle")`
- Status text: error-specific message
- Old dead code (`SOURCE_ERROR`, `MISSING_SOURCE` error_code checks) removed

Failure handling:
- `data.status === "storage_not_configured"` → "H5 storage not configured."
- `data.status === "upload_disabled"` → "Uploads are currently disabled."
- `data.error` present → "Upload failed: <error>"
- Otherwise → "Upload failed"
- Network error → "Upload failed"

## Heading Rename

- "Container Catalog" → "Patients List" (line 822)
- "Refresh Catalog" → "Refresh Patients"
- Only in `src/bremen/control_room_ui.py` (confirmed: not in start_page_ui.py)

## startAnalysis Container Branch Compatibility

`startAnalysis()` already has `selectedSource.type === "container"` branch that sends `body.source_id = selectedSource.id`. Since uploads now use `type: "container"` with the persistent S3-backed id, the existing analyze path works without changes.

## Tests Added

8 new tests in `TestPR0098PersistentUpload`:
1. `test_handle_file_select_posts_to_persistent_endpoint` — verifies fetch targets /demo/api/h5/containers
2. `test_successful_upload_selects_container_type_source` — verifies type='container' and data.id
3. `test_successful_upload_calls_load_container_catalog` — verifies catalog refresh
4. `test_upload_failure_clears_selected_source` — verifies selectedSource=null, state=idle, dead code removed
5. `test_patients_list_heading_present` — verifies "Patients List" in page
6. `test_container_catalog_heading_removed` — verifies "Container Catalog" not in page
7. `test_refresh_patients_button_text` — verifies "Refresh Patients" button

Updated 1 existing test:
- `test_selection_kept_after_typed_error` — updated to check for selectedSource=null instead of dead SOURCE_ERROR code

Updated JS test:
- `test_launch_flow.js` test 7 — updated mock from /demo/api/stage to /demo/api/h5/containers, upload_id to source_id

Updated Python test:
- `test_launch_flow.py` — updated assertion message

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest tests/test_bremen_control_room.py` | 76 passed |
| `pytest` (full suite) | 2276 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| handleFileSelect targets /demo/api/h5/containers | CONFIRMED |
| No /demo/api/stage in control_room_ui.py | CONFIRMED |
| "Patients List" heading present | CONFIRMED |
| "Container Catalog" heading removed | CONFIRMED |

## Blockers

None.

## Warnings

None.

## Next Required Action

Human review and commit.
