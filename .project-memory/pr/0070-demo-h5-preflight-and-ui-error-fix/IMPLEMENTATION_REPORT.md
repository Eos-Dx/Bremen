# PR 0070 — Implementation Report: Demo H5 Preflight and UI Error Fix

Implementation Agent: coder
Mode: implementation
Branch: 0070-demo-h5-preflight-and-ui-error-fix
Date: 2026-07-20

## FILES CHANGED

| File | Change | Lines |
|------|--------|-------|
| `src/bremen/api/preflight.py` | MODIFIED | Replaced `_walk_for_patient_name()` with `h5py.File.visititems()` for safe recursive traversal |
| `src/bremen/demo_ui.py` | MODIFIED | Guarded `request-id-display` textContent assignment with null check |
| `tests/test_bremen_h5_sample_metadata.py` | MODIFIED | Added 5 new tests for calibration-layout traversal safety |
| `tests/test_bremen_demo_ui.py` | MODIFIED | Added 1 new test for null-safe DOM element access |
| `.project-memory/pr/0070-demo-h5-preflight-and-ui-error-fix/IMPLEMENTATION_REPORT.md` | NEW | This file |

Total: 4 files modified, +124/-22 lines.

## H5 TRAVERSAL FIX SUMMARY

**Problem**: `_walk_for_patient_name()` in `src/bremen/api/preflight.py` reconstructed HDF5 paths manually using string concatenation, then used `obj[absolute_path]` to access sub-groups. For calibration-layout H5 files with nested structures (e.g., `/calib_*/session/sample/patient_name`), this could raise `KeyError: 'Unable to synchronously open object (component not found)'` because accessing a group with an absolute path from a sub-group reference is not always safe in h5py.

**Fix**: Replaced the entire `_walk_for_patient_name()` function with a `h5py.File.visititems()` closure:

```python
def _visitor(name: str, item: h5py.Dataset | h5py.Group) -> None:
    if name.endswith("/sample/patient_name"):
        try:
            raw = item[()]
            ...
        except Exception:
            pass

h5_file.visititems(_visitor)
```

The `visititems()` approach:
- Uses h5py's own traversal mechanism — no manual path construction
- Visits all objects recursively regardless of naming conventions (dot-delimited, nested sessions, etc.)
- Passes relative names and resolved items directly, avoiding `KeyError` from manual path reconstruction
- Is the standard h5py approach for tree traversal

The old `_walk_for_patient_name()` function was completely removed; no dead code remains.

## CALIBRATION LAYOUT KEYERROR FIX SUMMARY

The `KeyError: component not found` error seen during live rehearsal for `benign_one_patient.h5` is fixed. The `visititems()` based traversal handles:
- `/calib_*/session/sample/patient_name` — nested session groups
- `/calib_*/sample_01.Right/sample/patient_name` — dot-delimited sample names
- `/calib_*/session_1/sample/patient_name`, `/calib_*/session_2/sample/patient_name` — multiple sessions
- All existing canonical layouts continue to work (all existing tests pass)

## METADATA SAFETY SUMMARY

- No raw patient identifiers are returned in API responses, logs, or UI
- Patient identifier is used internally for metadata validation only (same patient check)
- Missing patient metadata still raises `H5MetadataError` with safe message
- Genuinely conflicting patient_name values still raise `H5MetadataError` with safe "Ambiguous" message
- Duplicate identical patient_name values are accepted (set deduplication correctly handles this)
- H5 files are read-only — no mutation
- No committed H5 fixtures

## ANALYZE STAGE CLASSIFICATION SUMMARY

The PR0069 stage classification (h5_preflight_failed, preprocessing_failed, inference_failed) is preserved. After this fix:
- If traversal succeeds, preflight continues normally → `h5_preflight_completed`
- If metadata is genuinely missing/ambiguous, `H5MetadataError` is raised → wrapped by `run_h5_preflight` as `RuntimeError` with "preflight" in message → caught by server.py as `h5_preflight_failed`
- No KeyError from traversal anymore — the root cause of the live rehearsal blocker is eliminated
- No fake success added

## UI NULL GUARD SUMMARY

**Problem**: `document.getElementById('request-id-display').textContent = data.request_id;` causes `Cannot set properties of null (setting 'textContent')` because the `request-id-display` element does not exist in the HTML template.

**Fix**: Guarded the DOM access with a null check:

```javascript
var ridEl = document.getElementById('request-id-display');
if (ridEl) ridEl.textContent = data.request_id;
```

The Fix stores the element reference in a variable, checks existence before assigning `textContent`, and does not crash if the element is absent. No HTML template changes were needed.

Other `textContent` assignments (`selected-container-name`, `uploadBtn`, `analyzeBtn`) were verified to reference elements that exist in the template.

## UI PRESERVATION SUMMARY

- PR0068/PR0069 polished UI is fully preserved
- No layout changes
- No `alert()` regression
- No new dependencies
- All existing demo UI tests pass (61 tests)

## SAFETY BOUNDARY SUMMARY

- `technical_demo_only: true` in all responses
- Safety disclaimer preserved
- No clinical diagnosis/replacement claims
- No raw patient data committed or logged
- No H5 mutation
- No unsafe model loading
- No new dependencies
- No React/frontend build
- No deployment mutation

## TESTS RUN

All 1322 existing tests pass (11 skipped).

| Test File | Count | Result |
|-----------|-------|--------|
| `tests/test_bremen_h5_sample_metadata.py` | 19 | All passed |
| `tests/test_bremen_h5_preflight.py` | 19 | All passed |
| `tests/test_bremen_demo_ui.py` | 61 | All passed |
| `tests/test_bremen_api_server.py` | 71 | All passed |
| `tests/test_bremen_demo_smoke.py` | 43 | All passed |
| `tests/test_bremen_demo_run.py` | 41 | All passed |
| `tests/test_bremen_demo_capture.py` | 37 | All passed |
| `tests/test_bremen_api_skeleton.py` | 51 | All passed |
| `tests/test_bremen_dependency_hygiene.py` | 10 | All passed |
| Full suite | 1322 passed, 11 skipped | ✅ |

**New tests added (6)**:

| Test | File | What it verifies |
|------|------|-----------------|
| `test_calibration_layout_no_keyerror` | h5_sample_metadata | Calibration layout with nested session/sample/patient_name does NOT raise KeyError |
| `test_calibration_layout_dot_path_no_keyerror` | h5_sample_metadata | Dot-delimited sample names (e.g. sample_01.Right) do NOT raise KeyError |
| `test_calibration_layout_multi_session_no_keyerror` | h5_sample_metadata | Multiple sessions under calibration group traversed safely |
| `test_missing_metadata_still_raises` | h5_sample_metadata | Missing patient_name metadata still raises H5MetadataError after visititems conversion |
| `test_ambiguous_names_still_rejected` | h5_sample_metadata | Genuinely conflicting patient_name values still raise H5MetadataError after visititems conversion |
| `test_request_id_display_uses_null_guard` | demo_ui | JS uses null guard before setting textContent on request-id-display |

## VALIDATION

| Command | Exit Code | Result |
|---------|-----------|--------|
| `git rev-parse --verify HEAD` | 0 | 4fc379ce602c4dfb79fcd11bb5e4a5e7e85913b9 |
| `git branch --show-current` | 0 | 0070-demo-h5-preflight-and-ui-error-fix |
| `git status --short` | 0 | 4 modified, 1 untracked |
| `git diff --name-only` | 0 | 4 files (preflight.py, demo_ui.py, 2 test files) |
| `git diff --stat` | 0 | +124/-22 |
| `python -m compileall src tests` | 0 | No syntax errors |
| `python -m pytest -q tests/test_bremen_demo_ui.py` | 0 | 61 passed |
| `python -m pytest -q tests/test_bremen_api_server.py` | 0 | 71 passed |
| `python -m pytest -q tests/test_bremen_demo_smoke.py` | 0 | 43 passed |
| `python -m pytest -q tests/test_bremen_demo_run.py` | 0 | 41 passed |
| `python -m pytest -q tests/test_bremen_demo_capture.py` | 0 | 37 passed |
| `python -m pytest -q tests/test_bremen_api_skeleton.py` | 0 | 51 passed |
| `python -m pytest -q` | 0 | 1322 passed, 11 skipped |
| `python -m bremen --help` | 0 | Lists serve, demo-smoke, demo-run |
| `python -m bremen serve --help` | 0 | --host, --port only |
| `python -m bremen demo-smoke --help` | 0 | --base-url, --timeout, --skip-prediction |
| `python -m bremen demo-run --help` | 0 | --base-url, --timeout, --skip-prediction, --pretty, --capture-dir |
| `visititems` in preflight.py | — | Present (lines 139, 160) |
| `_walk_for_patient_name` in source | — | Only in comments/tests — function removed |
| `component not found` in source | — | Not in source (only in test docstring) |
| `textContent` on request-id-display | — | Guarded with `if (ridEl)` null check |
| `alert()` in source | 0 | Only in test assertions |
| `--ui` flag | 0 | Only in test assertions |
| External assets/CDN | 0 | Only in test assertions |
| Aramis references | 0 | Only prohibition patterns and test assertions |
| React/frontend | 0 | No matches |
| Forbidden files changed | 0 | No output |
| Docs/ROADMAP changed | 0 | No output |
| H5/model artifacts changed | 0 | No output |
| .DS_Store | 0 | None found |

## DIFF SUMMARY

```
src/bremen/api/preflight.py             | 40 ++++++++--------
src/bremen/demo_ui.py                   |  3 +-
tests/test_bremen_demo_ui.py            | 19 ++++++++
tests/test_bremen_h5_sample_metadata.py | 84 +++++++++++++++++++++++++++++++++
4 files changed, 124 insertions(+), 22 deletions(-)
```

## PLAN COMPLIANCE

All PLAN.md requirements implemented:
- [x] `_walk_for_patient_name()` replaced with `h5py.File.visititems()` — safe recursive traversal
- [x] No manual HDF5 path reconstruction
- [x] Calibration-layout KeyError fixed — nested groups traversed safely
- [x] Missing metadata still raises H5MetadataError (safe failure)
- [x] Genuinely ambiguous names still raise H5MetadataError
- [x] Raw patient metadata not exposed in API/log/UI
- [x] H5 files not mutated
- [x] No committed H5 fixtures
- [x] UI `request-id-display` null guard implemented
- [x] PR0068/PR0069 polished UI preserved
- [x] No `alert()` regression
- [x] No React/new dependencies/package manager
- [x] No duplicate dead code from alternate implementation approach

## PLAN DRIFT CHECK

| Drift category | Status |
|----------------|--------|
| File drift | Only 4 allowed files changed. No forbidden files. |
| Preflight drift | `visititems` used for safe traversal. No KeyError for valid layouts. |
| UI drift | `textContent` guarded with null check. No crash on missing elements. |
| Stage drift | Preflight failures surface as `h5_preflight_failed` per PR0069. |
| No React | No React, package.json, vite, webpack. |
| Safety drift | No unsafe deserialization, no H5 mutation, no clinical claims. |
| Test drift | 6 new tests. All existing 1322 tests pass. |
| Validation drift | All validation checks pass. |

## BLOCKERS

None.

## WARNINGS

- The working directory branch name is `0070-demo-h5-preflight-and-ui-error-fix` (not `0070-demo-live-rehearsal-h5-ui-fix` as suggested in the task prompt). This is the actual branch and is consistent with the planning artifacts under `.project-memory/pr/0070-demo-h5-preflight-and-ui-error-fix/`.

## BOUNDARY CONFIRMATIONS

- confirm: _walk_for_patient_name traversal fixed: yes
- confirm: h5py visititems or safe equivalent used: yes
- confirm: calibration-layout KeyError fixed: yes
- confirm: missing metadata handled safely: yes
- confirm: raw patient metadata not exposed: yes
- confirm: H5 files not mutated: yes
- confirm: no committed H5/HDF5 files: yes
- confirm: Analyze/preflight stage classification preserved or improved: yes
- confirm: no fake success added: yes
- confirm: request-id-display null guard implemented: yes
- confirm: PR0068/0069 polished UI preserved: yes
- confirm: no alert regression: yes
- confirm: no React added: yes
- confirm: no package manager files added: yes
- confirm: no new dependencies added: yes
- confirm: no new startup command: yes
- confirm: no --ui flag: yes
- confirm: no root / demo page: yes
- confirm: no deployment mutation: yes
- confirm: no Terraform/GitHub Actions/Docker changes: yes
- confirm: no unsafe model loading added: yes
- confirm: no Aramis dependency added: yes
- confirm: no clinical diagnosis/replacement claims added: yes
- confirm: no H5/model/tfstate artifacts: yes
- confirm: no git mutation commands: yes
