# Implementation Report — PR0099H: Patient names in Patients List and accordion pipeline steps

## Files Changed

| File | Change |
|------|--------|
| `src/bremen/api/server.py` | Added `_patient_name_cache` dict; catalog listing extracts patient_name from H5 on cache miss |
| `src/bremen/control_room_ui.py` | Accordion pipeline with clickable expandable rows; updated CSS |
| `tests/test_bremen_control_room.py` | 33 new tests in TestPR0099HPatientNameAndAccordion |

## 0099E Reuse Check

**Helper found:** `extract_patient_display_name(h5_path)` in `src/bremen/api/job_api_handler.py` (line 364)

**Location:** `src/bremen/api/job_api_handler.py`

**Reused:** Yes. server.py imports and calls `extract_patient_display_name` from job_api_handler. No second parallel implementation was written.

## Cache Implementation

Module-level `_patient_name_cache` dict in server.py:

```python
_patient_name_cache: dict[tuple[str, str, int], str | None] = {}
```

**Key shape:** `(bucket, object_key, size_bytes) -> patient_name | None`

**Trade-off accepted:** Changed file with different size refreshes cache. Same-size replacement could be stale. Acceptable for static demo fixtures.

**Behavior:**
- Cache miss → stage/download H5 via `stage_h5_input()`, extract via `extract_patient_display_name()`
- Cache hit → return cached value immediately
- Cache `None` → prevents repeated reads for broken/missing patient_name
- Never fails the whole listing because one file failed

## Field Name Used

Response fields in GET /demo/api/h5/containers:
- `patient_display_name`: real safe patient label or empty string
- `display_name`: `patient_display_name or filename` (primary display)
- `filename`: original safe filename (secondary metadata)
- `stable_source_key`: deterministic hash for cross-listing identity

No field-name collision with existing `source_display_name` semantics.

## Fallback-on-Failure

- Missing patient_name → cache `None`, display_name = filename
- Empty patient_name → cache `None`, display_name = filename
- Unsafe patient_name (s3://, /tmp/, slash, too long) → cache `None`, display_name = filename
- Read failure (exception) → cache `None`, display_name = filename
- No raw exception text in response

## Patients List Primary/Secondary Display

**When patient_display_name exists:**
- Primary: `patient_display_name` (e.g., "Nova_257")
- Secondary: `filename · size · date`

**When patient_display_name absent:**
- Primary: filename (existing behavior)
- Secondary: `size · date` (existing behavior)

No empty placeholder title. No UUID as primary when filename exists.

## Accordion Pipeline Structure

Each pipeline row converted from flat layout to accordion:

**Collapsed (default):**
```
[icon] Stage Label  [chevron ▶]  [duration]
```

**Expanded (on click):**
```
[icon] Stage Label  [chevron ▼]  [duration]
  Caption text here
```

**Structure:**
```html
<div class="cr-stage" id="stage-input">
  <div class="cr-stage-header" role="button" tabindex="0" 
       aria-expanded="false" aria-label="Request accepted"
       onclick="toggleStage(this)" onkeydown="toggleStageKey(event,this)">
    <span class="cr-stage-icon pending">●</span>
    <span class="cr-stage-label">Request accepted</span>
    <span class="cr-stage-chevron">▶</span>
    <span class="cr-stage-dur"></span>
  </div>
  <div class="cr-stage-body" style="display:none">
    <span class="cr-stage-caption">Request received</span>
  </div>
</div>
```

## Keyboard Accessibility

- `role="button"` on stage headers
- `tabindex="0"` for keyboard focus
- `aria-expanded="false"` reflects collapsed state
- `aria-label` names the stage
- `onkeydown="toggleStageKey(event,this)"` handles Enter/Space
- Focus style: `outline: 2px solid var(--accent)`

## Caption Text Preserved

All 15 short captions preserved exactly from PR0099G:
- Request received, Scan normalized, Workflow selected, Package checked, Model loaded, Adapter applied, Contract checked, Measurements arranged, Features calculated, Feature schema checked, Score produced, Output checked, Threshold applied, Report created, Run finished

Long explanation text preserved as `title` attribute on stage headers.

## Expanded Font Size Token

Expanded body uses `font-size: var(--fs-13)` — readable body font, not tiny caption font.

## PR0099B/0099C/0099D/0099E/0099F/0099G Preservation

- PR0099B: `run_workflow_request(job_id=...)` preserved
- PR0099C: 4 stage events, trace finalization, tiny score <0.001, 15/15 summary
- PR0099D: rerun guard, delete report, analyzed rows
- PR0099E: Patient Reports heading, failed-job gating, patient_display_name
- PR0099F: failed terminal state, hasSeenFailure, no Open report for failed
- PR0099G: stable_source_key, already-analyzed copy, short captions

## Tests Added

33 new tests in `TestPR0099HPatientNameAndAccordion`:

0099E reuse (2):
1. `test_reuses_extract_patient_display_name`
2. `test_server_imports_extract_patient_display_name`

Patient name cache (8):
3. `test_patient_name_cache_exists`
4. `test_patient_name_extraction_from_h5`
5. `test_patient_name_bytes_decodes`
6. `test_missing_patient_name_returns_empty`
7. `test_unsafe_patient_name_returns_empty`
8. `test_extraction_failure_does_not_raise`
9. `test_cache_hit_avoids_repeated_extraction`
10. `test_cache_none_prevents_repeated_reads`

Response field (1):
11. `test_response_field_patient_display_name`

Patients List (3):
12. `test_patients_list_uses_patient_name_as_primary`
13. `test_patients_list_filename_as_secondary`
14. `test_patients_list_fallback_to_filename`

Accordion (12):
15. `test_all_15_pipeline_rows_exist`
16. `test_all_15_rows_have_accordion_content`
17. `test_captions_collapsed_by_default`
18. `test_aria_expanded_exists`
19. `test_keyboard_toggle_support`
20. `test_role_button_on_headers`
21. `test_toggle_stage_function_exists`
22. `test_chevron_affordance_exists`
23. `test_stage_order_preserved`
24. `test_terminal_summary_preserved`
25. `test_caption_text_preserved`
26. `test_readable_font_size_in_body`

No container copy (3):
27. `test_no_container_copy_in_ui`
28. `test_patient_reports_heading_present`
29. `test_job_history_heading_absent`

Preservation (4):
30. `test_pr0099d_rerun_guard_preserved`
31. `test_pr0099c_tiny_score_preserved`
32. `test_pr0099e_failed_job_gating_preserved`
33. `test_pr0099g_stable_source_key_preserved`

## Validation

| Command | Result |
|---------|--------|
| `python -m compileall src tests` | PASS |
| `pytest` (full suite) | 2585 passed, 11 skipped, 0 failed |
| `git diff --check` | Clean |
| Patient name cache exists | CONFIRMED |
| extract_patient_display_name reused | CONFIRMED |
| 15 accordion rows | CONFIRMED |
| aria-expanded present | CONFIRMED |
| keyboard toggle support | CONFIRMED |
| No container(s)/Container: | CONFIRMED |
| Patient Reports heading | CONFIRMED |
| No forbidden files changed | CONFIRMED |

## Blockers

None.

## Warnings

- Patient name extraction requires downloading H5 from S3 on first cache miss. For 100 containers, this could add latency on first listing. Subsequent listings use cache.
- Cache is process-level and resets on server restart. Acceptable for demo.
- Cache key uses (bucket, object_key, size_bytes). Same-size file replacement won't refresh cache until restart.

## Next Required Action

Human review and commit.
