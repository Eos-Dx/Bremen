# PR 0070 — Plan Demo H5 Preflight and UI Error Fix

Author: plan
Mode: planning only
Branch: 0070-demo-h5-preflight-and-ui-error-fix

## Objective

Fix the two specific blocker issues found during live demo rehearsal, enabling the demo Analyze path to move past H5 preflight for the `benign_one_patient.h5` layout and preventing the UI error rendering from crashing.

**Issue 1**: H5 preflight failure — `run_h5_preflight()` → `resolve_patient_metadata()` → `_walk_for_patient_name()` raises `KeyError: 'Unable to synchronously open object (component not found)'` for the calibration layout H5 file `benign_one_patient.h5`.

**Issue 2**: UI crash — `Cannot set properties of null (setting 'textContent')` — caused by JavaScript trying to set `textContent` on `request-id-display` which does not exist in the HTML template.

## Confirmed evidence

- `/model/version` is ready ✓
- S3 demo storage is configured ✓
- `/demo/api/h5/containers` now lists S3 H5 containers ✓ (PR0069)
- H5 staging from S3 works ✓
- Browser Analyze reaches `h5_staging_completed` ✓
- `benign_one_patient.h5` fails locally at `run_h5_preflight()` with `KeyError: component not found` in `_walk_for_patient_name` ✗
- H5 structure includes `session/sample/patient_name` and integration paths ✗
- UI reports `Cannot set properties of null (setting 'textContent')` ✗

## Required reads — observed facts

### `src/bremen/api/preflight.py`
- `resolve_patient_metadata(h5_file)` — primary path `/patient/id`, fallback `_walk_for_patient_name()`.
- `_walk_for_patient_name(obj, prefix)` recursively iterates `obj.keys()`, constructs absolute path `prefix/key`, accesses `obj[path]`, recurses into groups.
- The recursive call `_walk_for_patient_name(item, path)` passes `item` (a `h5py.Group`) as `obj` and `path` (an absolute path like `/session`) as `prefix`.
- Inside the recursive call, `path = f"{prefix}/{key}"` generates paths like `/session/sample`, then `obj[path]` accesses the sub-group `h5_file["/session"]["/session/sample"]`. In h5py, indexing a group with an absolute path re-opens from the root, which should still work. However, if the H5 file has a specific structure where intermediate groups use different naming (e.g., `sessions/` plural vs `session/` singular), the traversal might work but the group object passed recursively might have stale state.

### `src/bremen/api/h5_layouts.py`
- `CalibrationSampleH5LayoutAdapter` detects layout via `/calib_*` groups with `sample/patient_name` and `sample/sample_type`, with no `/scans/target/measurements`.
- `CanonicalH5LayoutAdapter` detects via `/scans/target/measurements`.

### `src/bremen/demo_ui.py`
- Line 193: `document.getElementById('selected-container-name').textContent = filename` — element exists (line 473).
- Line 282: `document.getElementById('request-id-display').textContent = data.request_id` — element does **NOT** exist in the HTML template.
- Lines 84–99: CSS selectors for `#selected-container-name`, `#analyze-btn`, `#request-id-display` (CSS only, no HTML for `request-id-display`).
- The `selectContainer()` function (line 191) references `selected-container-name` and `selected-container-display` — both exist in HTML template (lines 471–474).

### `src/bremen/api/inference_handler.py`
- `run_inference(h5_path)` — calls `run_h5_preflight()`.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/api/preflight.py`** — MODIFY. Fix `_walk_for_patient_name()` to use safe H5 traversal without raising `KeyError` for calibration-style nested layouts.

2. **`src/bremen/demo_ui.py`** — MODIFY. Fix UI crash:
   - Add missing `request-id-display` element to the HTML template, OR
   - Guard the `textContent` assignment with a null check.
   - Remove CSS for `request-id-display` if it references a non-existent element.

3. **`tests/test_bremen_api_server.py`** — MODIFY. Add tests for `resolve_patient_metadata` with nested calibration layout, verify no `KeyError`.

4. **`tests/test_bremen_demo_ui.py`** — MODIFY. Add test for null-safe DOM element access.

**Allowed only if justified by repository inspection**:
- `src/bremen/api/h5_layouts.py` — only if the layout detection or adapter needs to match the traversal fix.
- Additional test file for H5 preflight if tests are better factored separately.

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

### 1. Fix `_walk_for_patient_name` — safe H5 traversal

**Current code** (lines 142–148 of `preflight.py`):

```python
def _walk_for_patient_name(obj: Any, prefix: str) -> None:
    for key in obj.keys():
        path = f"{prefix}/{key}" if prefix else f"/{key}"
        item = obj[path]
        if isinstance(item, h5py.Group):
            _walk_for_patient_name(item, path)
        elif path.endswith("/sample/patient_name"):
            ...
```

**Problem**: When `obj` is a sub-group (e.g., `h5_file["/session"]`) and `prefix` is an absolute path (e.g., `"/session"`), `obj[path]` accesses `h5_file["/session"]["/session/sample"]`. This should work in standard h5py, but the specific H5 file `benign_one_patient.h5` may have a structure where the group name has special characters, or the intermediate groups have unexpected structure that causes `obj[path]` to fail.

**Fix approach**: Use `obj.get(key)` or `obj[key]` with relative keys instead of absolute path reconstruction:

```python
def _walk_for_patient_name(obj: Any, prefix: str) -> None:
    for key in obj.keys():
        path = f"{prefix}/{key}" if prefix else f"/{key}"
        try:
            item = obj[key]  # Use relative key, not absolute path
        except KeyError:
            # Fallback to absolute path if relative fails
            try:
                item = obj[path]
            except KeyError:
                continue
        if isinstance(item, h5py.Group):
            _walk_for_patient_name(item, path)
        elif path.endswith("/sample/patient_name"):
            ...
```

Or more simply, use `h5_file.visititems()` which is the standard h5py approach for recursive traversal:

```python
def _walk_for_patient_name(obj: h5py.File, prefix: str) -> None:
    # visititems visits all objects recursively with relative names
    def visitor(name: str, item: h5py.Dataset | h5py.Group) -> None:
        if name.endswith("/sample/patient_name"):
            try:
                raw = item[()]
                if isinstance(raw, bytes):
                    val = raw.decode("utf-8")
                else:
                    val = str(raw)
                val_stripped = val.strip()
                if val_stripped:
                    patient_names.append(val_stripped)
                    patient_paths.append(f"/{name}")
            except Exception:
                pass

    obj.visititems(visitor)
```

The `visititems` approach is safer because:
- It uses h5py's own traversal mechanism — no manual path construction.
- It handles nested groups correctly regardless of naming conventions.
- It visits all objects recursively without risk of `KeyError` from manual path reconstruction.
- It's the standard h5py approach for tree traversal.

**Required**: 
- Fix the traversal to not raise `KeyError: component not found`.
- Must work for calibration layout (`/calib_*/sample_*/sample/patient_name`).
- Must work for canonical layout (`/scans/target/`, `/scans/contralateral/`).
- No raw patient data in logs.
- No H5 mutation.

### 2. Fix metadata ambiguity / repeated identical values

The current code (line 175) raises `H5MetadataError("Ambiguous sample patient_name metadata")` if `len(distinct_values) > 1`. For multi-sample calibration H5 files, the same patient name may appear in multiple samples. This should be accepted, not treated as ambiguous.

**Fix**: If all distinct patient name values are identical after stripping, accept the common value:

```python
distinct_values = set(patient_names)
if len(distinct_values) == 1:
    resolved_value = distinct_values.pop()
elif len(distinct_values) == 0:
    raise H5MetadataError("Missing patient identifier metadata")
else:
    # Multiple distinct values — only ambiguous if more than one unique value
    if len(distinct_values) > 1:
        raise H5MetadataError("Ambiguous sample patient_name metadata")
```

But actually, `set()` by definition has only unique values, so `len(distinct_values) > 1` already handles this correctly. The issue is that `visititems` will find ALL matching paths including duplicate patient_names. If all have the same value, `distinct_values` will have size 1 and it works. If there are genuinely different values, it correctly raises ambiguity.

The fix for `visititems` should handle this correctly — but we should verify there's no bug in the existing set logic.

### 3. Fix UI null `textContent` error

**Current code** (line 282 of `demo_ui.js`):

```javascript
document.getElementById('request-id-display').textContent = data.request_id;
```

**Problem**: `request-id-display` element does not exist in the HTML template.

**Fix option A** (preferred): Guard the DOM access with a null check:

```javascript
var ridEl = document.getElementById('request-id-display');
if (ridEl) ridEl.textContent = data.request_id;
```

**Fix option B**: Add the missing element to the HTML template in `renderResult()` area.

**Preferred**: Option A + add the missing CSS removal. Simpler, less risk of layout regression.

Also check: CSS for `request-id-display` at line 96 references it — verify that's harmless (CSS for a non-existent element causes no errors).

### 4. Stage classification — ensure preflight failures surface as `h5_preflight_failed`

The PR0069 fix already added `logger.exception()` and keyword-based stage classification. However, verify that `run_inference()` → `run_h5_preflight()` → `KeyError` is caught by the `except Exception:` block and classified correctly.

The keyword `preflight` should be in the exception message from `run_h5_preflight()`. If the KeyError is raised before `run_h5_preflight()` wraps it in a `RuntimeError` with "preflight" in the message, the classification may fall through to the generic fallback. The fix to the traversal should eliminate the `KeyError` at the source. If any `KeyError` remains for other reasons, the `except Exception:` handler in server.py should classify it as `inference_failed` (since the message won't contain "preflight" keywords for a raw `KeyError`).

After fixing the traversal, this should no longer be an issue — `resolve_patient_metadata` will either succeed or raise `H5MetadataError` (which is likely caught by `run_h5_preflight` and wrapped as `RuntimeError` with "preflight" in the message).

### 5. Analyze completion target

Target path for `benign_one_patient.h5`:
1. `h5_staging_completed` ✓ (already works)
2. `h5_preflight_completed` — after traversal fix
3. `preprocessing_started` / `preprocessing_completed` — should proceed
4. `model_inference_started` / `model_inference_completed` — should proceed if model is loaded
5. `completed` — result present

The plan targets this path. If preprocessing/model inference fails after the preflight fix, the failure must be classified as the correct stage-specific error. No fake success.

## Non-goals

- No new CLI command, no `--ui` flag.
- No changes to `__main__.py`, `demo_run.py`, `demo_smoke.py`, `demo_capture.py`.
- No React/frontend stack.
- No new dependencies.
- No deployment mutation.
- No changes to `/health`, `/model/version`, `/predictions` endpoints.
- No changes to S3 catalog listing (PR0069 changes preserved).
- No committed H5 files.
- No raw patient data in logs or responses.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization.
- No new `joblib.load()` or `pickle.load()`.
- No H5 mutation — H5 files read-only.
- No real patient data committed.
- No raw patient data in logs or API responses — patient identifier is used for metadata resolution only, not logged.
- `technical_demo_only: true` in all responses.
- No clinical diagnosis/replacement claims.
- No Aramis references.
- No new dependencies.

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
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
```

### Forbidden-pattern grep checks

```bash
# "component not found" or "Unable to synchronously open object" — expected fixed
grep -R -I -n "component not found\|Unable to synchronously open object" src/bremen tests || true
# Expected: no output (test assertions verifying fix are allowed)

# "Cannot set properties of null" or "textContent" — expected guarded
grep -n "textContent" src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: only in guarded form (if/&&) or existing safe usage

# No alert() for expected errors
grep -R -I -n "alert(" src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No React/frontend build
grep -R -I -n "React\|react\|package.json\|vite\|webpack" src/bremen tests || true
# Expected: no output

# No --ui flag
grep -R -I -n -- "--ui\|demo-run --ui" src/bremen tests || true
# Expected: no output

# No clinical/replacement claims
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output (safe negation only)

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no new unsafe loading

# Forbidden files unchanged
git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training \
  requirements.txt pyproject.toml frontend web ui \
  package.json package-lock.json yarn.lock pnpm-lock.yaml tests/data docs ROADMAP.md
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
| H5 traversal | Use `h5py.File.visititems()` — standard, safe, no manual path construction |
| KeyError handling | Eliminate root cause via better traversal; no new try/except to hide bugs |
| Metadata ambiguity | Accept repeated identical patient_name values; raise on genuinely conflicting values |
| UI null fix | Guard `textContent` assignment with null check (Option A) |
| Stage classification | `h5_preflight_failed` for preflight issues — verified after traversal fix |
| New dependencies | None |
| Committed H5 | None |

## Rollback plan

1. **Revert `src/bremen/api/preflight.py`** — restore `_walk_for_patient_name` to previous implementation.
2. **Revert `src/bremen/demo_ui.py`** — restore UI textContent assignments.
3. **Revert test files** — revert `test_bremen_api_server.py` and `test_bremen_demo_ui.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 4 files changed (allowed list). No forbidden files. |
| **Preflight drift** | Use `visititems` for safe traversal. No KeyError for valid layouts. |
| **UI drift** | Guard textContent with null check. No crash on missing elements. |
| **Stage drift** | Preflight failures surface as `h5_preflight_failed`. |
| **No React** | No React, package.json, vite, webpack. |
| **Safety drift** | No unsafe deserialization, no H5 mutation, no clinical claims. |
| **Test drift** | New preflight + UI tests. Existing tests pass unchanged. |
| **Validation drift** | All validation checks pass. No `textContent` on null. No KeyError. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan adds React or a frontend build tool.
- Plan adds `--ui` or another launch command.
- Plan requires new dependencies.
- Plan fails to fix the `KeyError` for calibration layout H5.
- Plan keeps the UI crash (`textContent on null`) unfixed.
- Plan requires deployment mutation.
- Plan weakens Bremen safety language.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Traversal fix | `visititems` — h5py standard recursive visitor. |
| UI fix | Guard `textContent` with null check. |
| Metadata ambiguity | Accept repeated identical values; reject genuinely conflicting. |
| Stage classification | `h5_preflight_failed` for preflight issues. |
| New dependencies | None. |
| UI crash fix | Add null guard, no HTML change needed. |

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
- `src/bremen/api/preflight.py`
- `src/bremen/api/h5_layouts.py`
- `src/bremen/api/inference_handler.py`
- `src/bremen/api/model_state.py`
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

- `.project-memory/pr/0070-demo-h5-preflight-and-ui-error-fix/PLAN.md` (this file)

## Boundary confirmations

- confirm: local preflight KeyError planned for fix: yes
- confirm: H5 traversal planned without invalid nested re-indexing: yes (use visititems)
- confirm: canonical patient metadata behavior planned: yes
- confirm: genuine metadata conflict remains safe failure: yes
- confirm: h5_preflight_failed classification planned: yes
- confirm: Analyze path targeted beyond preflight: yes
- confirm: no fake success planned: yes
- confirm: UI null textContent error planned for fix: yes
- confirm: PR0068/0069 demo UI/catalog behavior preserved: yes
- confirm: no React planned: yes
- confirm: no package manager files planned: yes
- confirm: no new dependencies planned: yes
- confirm: no deployment mutation planned: yes
- confirm: no unsafe model loading planned: yes
- confirm: no H5 mutation planned: yes
- confirm: no committed H5/patient data planned: yes
- confirm: no Aramis dependency planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
