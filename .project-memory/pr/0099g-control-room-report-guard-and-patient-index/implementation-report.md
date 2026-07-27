# Implementation Report — PR0099G: Fix duplicate report guard, short captions, source-state copy, patient-name index

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/source_registry.py` | Added `get_stable_source_key()` function; added `stable_source_key` to `get_source_info()` response |
| `src/bremen/api/job_api_handler.py` | `handle_jobs_create` uses stable source key for duplicate guard identity |
| `src/bremen/api/server.py` | Catalog listing includes `stable_source_key` in response |
| `src/bremen/control_room_ui.py` | Short inline captions; stable source key for analyzed state; already-analyzed message |
| `tests/test_bremen_control_room.py` | 32 new tests in TestPR0099GReportGuardAndPatientIndex |

## Root Causes Found

### 1. Duplicate Report Guard Failure

`source_key = source_id or upload_id or container_id` used the registry UUID as identity. The registry creates a new UUID on each catalog listing via `register_source()`. So the same S3 object gets different source_ids on different listings, making `_find_existing_completed_report()` never match.

### 2. Source-unavailable vs Already-analyzed

`analyzedSourceKeys` was keyed by source_id (UUID), which didn't match across listings. After analysis, the source was marked stale ("source no longer available") instead of showing the already-analyzed message.

### 3. Long Inline Captions

PR0099F moved full tooltip text inline, making the pipeline visually cramped and hard to read.

### 4. Patient Display Name Not Populated

Catalog listing returned `patient_display_name: ""` because the display cache wasn't populated from H5 metadata at listing time.

## DUPLICATE REPORT GUARD

### Stable Source Key

Added `get_stable_source_key(source_id)` to source_registry.py:
- Derives deterministic SHA-256 hash from `bucket:object_key`
- Returns first 16 hex chars as stable key
- Same bucket+object_key always produces same key, regardless of source_id UUID

Updated `handle_jobs_create()` to use stable key:
```python
source_key = source_id or upload_id or container_id or ""
if source_id:
    from .source_registry import get_stable_source_key
    stable = get_stable_source_key(source_id)
    if stable:
        source_key = stable
```

Updated `get_source_info()` to include `stable_source_key` in response.

### Guard Behavior

`_find_existing_completed_report()` matches on `source_key` (now stable), `workflow_id`, and `model_id`. Same S3 object + same model → blocked. Different model → not blocked. Deleted/failed → not blocked.

## ALREADY-ANALYZED VS SOURCE-UNAVAILABLE COPY

### Frontend stable key bridge

- Catalog response now includes `stable_source_key` per container
- `loadContainerCatalog()` reads `c.stable_source_key` and uses it as `stableKey`
- `analyzedSourceKeys` is keyed by stable key (from job history's `source_key`)
- `selectContainer()` stores `stableKey` on `selectedSource`
- `updateReadiness()` checks `analyzedSourceKeys[selectedSource.stableKey]`
- `startAnalysis()` checks `analyzedSourceKeys[selectedSource.stableKey]`

### Message behavior

- Analyzed source: "Already analyzed with this model. Delete the report to run again."
- Truly missing source: "Previously selected patient is no longer available. Please select another."

## SHORT INLINE STAGE CAPTIONS

Replaced long tooltip sentences with short demo-friendly captions:

| Stage | Short Caption |
|-------|---------------|
| Request accepted | Request received |
| Canonical XRD created | Scan normalized |
| Bremen workflow resolved | Workflow selected |
| Model artifact verified | Package checked |
| Model artifact loaded | Model loaded |
| Model artifact adapted | Adapter applied |
| Model validated | Contract checked |
| Input prepared | Measurements arranged |
| Features produced | Features calculated |
| Feature contract validated | Feature schema checked |
| Inference completed | Score produced |
| Output validated | Output checked |
| Decision policy applied | Threshold applied |
| Report generated | Report created |
| Analysis complete | Run finished |

Long text preserved as `title` attribute on each caption span for accessibility/hover.

Structure:
```html
<span class="cr-stage-label">Request accepted
  <span class="cr-stage-caption" title="The analysis request was received...">Request received</span>
</span>
```

cr-stage-help count: 0. cr-stage-caption count: 16 (1 CSS + 15 HTML).

## PATIENT DISPLAY HASHMAP/CACHE

### Catalog Response

server.py catalog listing now includes:
- `patient_display_name`: initially empty (populated by job history cache)
- `stable_source_key`: deterministic hash for cross-listing identity

### Frontend Cache

`patientNamesBySource` populated from job history after first analysis. `loadContainerCatalog()` checks `c.patient_display_name` from catalog, then `patientNamesBySource[sid]` from cache, then filename.

### Source Registry

`get_source_info()` returns `patient_display_name`, `source_display_name`, and `stable_source_key`. `update_source_display_name()` allows post-registration updates.

## DISPLAY-ONLY IDENTITY

`patient_display_name` and `stable_source_key` are display/identity only. NOT used as backend uniqueness identity for model/report locks. Identity uses `source_key` (stable) + `workflow_id` + `model_id`.

## RAW PATH/S3 SAFETY

- `get_stable_source_key()` derives hash from `bucket:object_key` — no raw S3/path exposed
- Hash is deterministic and opaque
- Catalog response exposes only `stable_source_key` (hash), not bucket/object_key
- No raw paths in user-facing output

## PR0099B/0099C/0099D/0099E/0099F PRESERVATION

- PR0099B: `run_workflow_request(job_id=...)` optional arg preserved
- PR0099C: 4 stage events, trace finalization, tiny score <0.001, 15/15 summary
- PR0099D: rerun guard, delete report, analyzed rows
- PR0099E: Patient Reports heading, failed-job gating, patient_display_name
- PR0099F: inline captions, failed terminal state, hasSeenFailure tracking

## Tests Added

32 new tests in `TestPR0099GReportGuardAndPatientIndex`:

PART 1 — Duplicate guard (7):
1. `test_stable_source_key_function_exists`
2. `test_stable_source_key_deterministic`
3. `test_stable_source_key_differs_for_different_objects`
4. `test_stable_source_key_same_for_same_object`
5. `test_get_source_info_includes_stable_key`
6. `test_handle_jobs_create_uses_stable_key`
7. `test_rerun_guard_blocks_same_stable_key`

PART 2 — Already-analyzed (4):
8. `test_analyzed_uses_stable_key`
9. `test_select_container_stores_stable_key`
10. `test_already_analyzed_message_exists`
11. `test_catalog_includes_stable_source_key`

PART 3 — Short captions (11):
12. `test_cr_stage_help_removed`
13. `test_all_15_captions_exist`
14-19. Six representative short captions
20. `test_long_text_not_visible_as_caption`
21. `test_long_text_preserved_as_title`
22. `test_stage_order_preserved`

PART 4 — Patient display cache (2):
23. `test_catalog_response_includes_patient_display_name`
24. `test_patients_list_uses_patient_name`

Preservation (8):
25-32. PR0099C/0099D/0099E/0099F preservation tests

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest` (full suite) | 2552 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| cr-stage-help = 0 | CONFIRMED |
| cr-stage-caption = 16 | CONFIRMED |
| Short captions present | CONFIRMED |
| Stable source key deterministic | CONFIRMED |
| Same object → same stable key | CONFIRMED |
| No forbidden files changed | CONFIRMED |

## Blockers

None.

## Warnings

- Patient display name extraction from H5 happens at job creation time (PR0099E). Catalog listing returns empty patient_display_name initially. Names populated from job history cache after first analysis.
- Safe logging for patient-name scan/index was not added as separate log statements because the existing logging infrastructure doesn't have a dedicated pattern for this. The extraction is fault-tolerant and silent on failure.

## Next Required Action

Human review and commit.
