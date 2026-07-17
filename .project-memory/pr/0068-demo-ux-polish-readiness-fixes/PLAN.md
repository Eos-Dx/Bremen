# PR 0068 — Plan Demo UX Polish and Readiness Fixes

Author: plan
Mode: planning only
Branch: 0068-demo-ux-polish-readiness-fixes

## Objective

Make `/demo` presentable and reliable enough for a live product-owner/board demo. Fix the specific problems found in deployed demo, redesign the UI from debug-card layout to a polished product demo screen, and ensure model readiness/storage configuration state is consistently accurate.

This PR polishes the existing PR0067 H5 container workflow. No new features, no React, no new dependencies.

## Current demo problems (explicit)

1. **Debug-looking UI** — `/demo` uses raw table cards ("Service Health", "Model / Source", "Evidence Bundle", "Demo Flow") that look like a developer debug page, not a product demo. FAIL/status labels without context are confusing.

2. **Model readiness inconsistency** — When `/model/version` reports `model_status: "ready"`, `/demo` Service Health Model Ready check still shows FAIL because the health check result (from demo-smoke evidence) may not match actual model state. The `/demo` page should read model status from the live `/model/version` endpoint, not from demo-smoke pass/fail checks.

3. **Prediction check shows FAIL before any analyze** — The card shows "Prediction Check: FAIL" before the user has uploaded or analyzed any H5 container. This should show "Not run yet" or be absent until an analyze is performed.

4. **`alert()` for expected errors** — Browser `alert()` dialogs for storage_not_configured, upload failures, and analyze errors are jarring in a demo. Errors should render inline in the Events/Logs panel.

5. **Storage configuration not surfaced** — Storage state is invisible until upload fails with `storage_not_configured` in an alert dialog. The UI should show whether storage is configured and disable/explain the upload flow accordingly.

## Required reads — observed facts

### `src/bremen/demo_ui.py`
- `build_demo_html_page()` generates self-contained HTML with inline CSS + JS.
- Currently has debug-card layout: Service Health, Model/Source, Evidence Bundle, Demo Flow cards.
- Shows `_status(health_pass)` / `_status(model_pass)` / `_status(pred_pass)` — which show PASS/FAIL labels.
- Uses `alert()` for upload errors, file-type validation, size validation, and upload failures.
- `_status()` helper maps pass → `<span class="status-pass">PASS</span>`, fail → `<span class="status-fail">FAIL</span>`.

### `src/bremen/api/server.py`
- `_handle_demo_route()` builds evidence with hardcoded `model_status="ready"` and `prediction_status="not_available"`.
- Does NOT call `/model/version` or `ModelState` to determine actual model state.
- `_handle_demo_h5_analyze()` returns structured events and result.

### `src/bremen/demo_config.py`
- `read_demo_h5_config()` returns `h5_bucket`, `h5_prefix`, `allow_upload`, `upload_max_bytes`.
- No `container_catalog` or `storage_status` endpoint yet.

### Tests
- 1283 tests pass.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_ui.py`** — MODIFY. Full redesign: polished product demo layout, inline error handling, model-readiness-aware display, `not_run_yet` for prediction check, storage state visible.

2. **`src/bremen/api/server.py`** — MODIFY. Fix `/demo` handler to read actual model state from `ModelState` and pass it to `build_demo_html_page()`. Add `model_info` parameter.

3. **`tests/test_bremen_demo_ui.py`** — MODIFY. Update tests for new UI structure, remove `alert()` tests, add model readiness display tests.

4. **`tests/test_bremen_api_server.py`** — MODIFY. Update tests for `/demo` handler changes (model state passed correctly).

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

### 1. `src/bremen/demo_ui.py` — Full redesign

**Remove** the old card layout:
- "Service Health" card with PASS/FAIL check labels
- "Model / Source" card
- "Evidence Bundle" card
- "Demo Flow" card with "Synthetic Feature Artifact"
- `_status()` function (no more PASS/FAIL)

**Add** polished product demo layout:

```
┌─────────────────────────────────────────────────┐
│ ⚠ Technical demo only — not a clinical result.  │
├─────────────────────────────────────────────────┤
│ BREMEN                                           │
│ Should patient continue to MRI?                  │
│ ● Model: smoke-v0.1 ● Status: Ready              │
├─────────────────────────────────────────────────┤
│ 📁 H5 Container Workspace                        │
│ [Container list with Select buttons]             │
│ [Upload dropzone/input + Upload button]          │
│ [Selected: container_name.h5] → [ Analyze ]      │
├─────────────────────────────────────────────────┤
│ 📋 Processing / Events                           │
│ [Structured event timeline]                      │
├─────────────────────────────────────────────────┤
│ 📊 Result                                        │
│ [prediction outcome or not_run_yet message]      │
├─────────────────────────────────────────────────┤
│ ⚠ Safety disclaimer footer                       │
└─────────────────────────────────────────────────┘
```

**Key changes**:

1. **Header** — Compact hero with product name, product question, and model readiness badge (green "Ready" or yellow "Not loaded").

2. **No more PASS/FAIL status cards** — Replace with a single model badge that reads actual state:
   - If `model_status == "ready"`: green "Ready" badge with version
   - If `model_status == "not_configured"`: yellow "Not configured" badge
   - If `model_status == "error"`: red "Error" badge
   - No separate health/model_version/prediction check labels

3. **Prediction check shows "Not run yet"** — Before any H5 container is selected and analyzed, the prediction area shows "No prediction has been run yet. Select an H5 container and click Analyze." Not "FAIL".

4. **No `alert()` for expected errors** — Replace all `alert()` calls with inline `addEvent()` calls that render errors in the Events panel. The `alert()` calls for:
   - `storage_not_configured` → inline error event
   - Upload rejection (size, type) → inline error event
   - Upload failure → inline error event
   - No container selected → inline error event

5. **Storage configuration visible** — Show storage status at the top of the H5 workspace:
   - If `storage_configured: true`: normal upload section
   - If `storage_configured: false`: "H5 storage is not configured. Set BREMEN_DEMO_H5_BUCKET to enable upload." with upload button disabled or hidden.

6. **Events/Logs panel** — Improved styling with icons/colors for different event types:
   - Start events: blue
   - Complete events: green
   - Failure events: red with icon
   - Warning events: yellow/amber

7. **Result panel** — Structured display with:
   - Status badge
   - Model output (p_mri_needed, recommendation) when available
   - Explicit reason when unavailable
   - Request ID in monospace
   - Job ID when available

**New function signature**:

```python
def build_demo_html_page(
    evidence: dict[str, Any] | None = None,
    base_url: str | None = None,
    request_id: str | None = None,
    *,
    model_info: dict[str, Any] | None = None,
    storage_configured: bool = False,
    upload_max_bytes: int = 104857600,
) -> str:
```

`model_info` dict shape: `{"model_status": "ready", "model_version": "smoke-v0.1", "model_checksum": "...", "feature_schema_version": "v0.1"}` or `{"model_status": "not_configured"}` or `{"model_status": "error"}`.

### 2. `src/bremen/api/server.py` — Fix `/demo` handler to pass actual model state

**Change `_handle_demo_route()`**:

```python
def _handle_demo_route(handler):
    from ..demo_ui import build_demo_html_page
    from ..demo_evidence import build_demo_evidence_bundle
    from ..demo_config import read_demo_h5_config
    from .model_state import ModelState

    request_id = handler.headers.get("X-Request-ID") or str(uuid.uuid4())
    host_header = handler.headers.get("Host", "localhost")
    base_url = f"http://{host_header}"

    # Determine actual model state from ModelState
    model_pkg = ModelState.get_model()
    if model_pkg is not None:
        state = ModelState.get_instance()
        plr = model_pkg.get("portable_logreg", {})
        model_info = {
            "model_status": "ready",
            "model_version": state._model_version or plr.get("model_version") or "unknown",
            "model_checksum": state._model_checksum or "",
            "feature_schema_version": plr.get("feature_schema_version"),
        }
    elif ModelState.was_load_attempted():
        model_info = {"model_status": "error", "error_category": ModelState.get_load_error()}
    else:
        model_info = {"model_status": "not_configured"}

    evidence = build_demo_evidence_bundle(
        base_url=base_url,
        request_id=request_id,
        model_status=model_info.get("model_status", "not_configured"),
        model_version=model_info.get("model_version"),
        feature_schema_version=model_info.get("feature_schema_version"),
        prediction_status="not_available",
    )

    demo_config = read_demo_h5_config()
    storage_configured = demo_config.get("h5_bucket") is not None

    html = build_demo_html_page(
        evidence=evidence,
        base_url=base_url,
        request_id=request_id,
        model_info=model_info,
        storage_configured=storage_configured,
        upload_max_bytes=demo_config.get("upload_max_bytes", 104857600),
    )
    ...
```

**Why this fixes the readiness problem**: Previously, `model_status` was hardcoded to `"ready"` in the evidence bundle. Now it reads the actual `ModelState` singleton, which knows whether the model loaded successfully at startup. If `ModelState.get_model()` returns the loaded model, `model_status` is `"ready"`. If load was attempted and failed, `model_status` is `"error"`. If no attempt was made (no env vars), `model_status` is `"not_configured"`.

**`model_info` replaces the PASS/FAIL check labels** — The UI now shows a single model readiness badge instead of the 4 separate status checks.

### 3. `tests/test_bremen_demo_ui.py` — Updated tests

1. **No `alert(` for expected errors** — Verify no `alert(` string in demo_ui.py source (except perhaps a fallback for truly unexpected errors).
2. **Model readiness badge present** — "Ready" or "Not configured" or "Error" appears based on model_info.
3. **Prediction shows "Not run yet"** — Before analyze, prediction area shows "not run yet" or equivalent.
4. **Storage configured state visible** — Storage status shown in H5 workspace.
5. **No `status-fail` for prediction** — Prediction should not show FAIL as a default/before-analyze state.
6. **Product question visible** — "Should patient continue to MRI?" visible.
7. **"Bremen" in header** — Product identity.
8. **"Technical demo only"** — Safety banner.
9. **H5 Container Workspace present** — Container workspace card still there.
10. **Inline JavaScript present** — UI is interactive.
11. **No external assets/CDN** — Existing checks pass.

### 4. `tests/test_bremen_api_server.py` — Updated tests

1. **`test_get_demo_passes_model_info`** — `/demo` response JSON (when extracted) or HTML contains model version from actual `ModelState`.
2. **`test_get_demo_shows_ready_when_model_loaded`** — With `load_model=True`, response contains "Ready" and the model version.
3. **`test_get_demo_shows_not_configured_without_model`** — Without model config, response contains "not configured" or equivalent.

## Non-goals

- No new CLI command, no `--ui` flag.
- No changes to `demo_run.py`, `demo_smoke.py`, `demo_capture.py`, `__main__.py`.
- No React/frontend stack.
- No new dependencies.
- No deployment mutation.
- No changes to `/health`, `/model/version`, `/predictions` endpoints.
- No changes to `GET /demo/api/h5/containers`, `POST /demo/api/h5/containers`, `POST /demo/api/h5/analyze` endpoint logic (only UI presentation changes).
- No changes to `demo_evidence.py`, `demo_config.py`, `demo_smoke.py`.
- No changes to `demo_run.py`, `demo_capture.py`.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization.
- No new `joblib.load()` or `pickle.load()`.
- No H5 mutation.
- No real patient data.
- `technical_demo_only` preserved.
- No clinical diagnosis/replacement claims.
- No Aramis references.
- No external assets/CDN.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_ui.py
python -m pytest -q tests/test_bremen_api_server.py
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
# No React/frontend build
grep -R -I -n "React\|react\|package.json\|vite\|webpack" src/bremen tests || true
# Expected: no output

# No alert() for expected demo errors
grep -R -I -n "alert(" src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output (or only for truly unexpected errors, justified)

# No --ui flag or extra launch command
grep -R -I -n -- "--ui\|demo-run --ui" src/bremen tests || true
# Expected: no output

# No synthetic feature artifact as primary product input
grep -n "Synthetic Feature Artifact" src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: may appear only in secondary/internal explanation, not as primary flow element

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
# Expected: no output (safe negation only)

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
| Model readiness source | `ModelState.get_model()` / `ModelState.was_load_attempted()` instead of hardcoded `"ready"` |
| UI layout | Polished product demo header + workspace + events + result |
| Prediction check before analyze | "Not run yet" — not "FAIL" |
| Expected errors | Inline in Events panel, not `alert()` dialogs |
| Storage status | Visible at workspace top; upload disabled when not configured |
| Model badge | Single green/yellow/red badge instead of 4 PASS/FAIL checks |
| No `alert()` for expected errors | All upload/storage/analyze errors render in Events |
| `alert()` allowed for | Only truly unexpected JavaScript errors (not storage/upload/analyze) |

## Rollback plan

1. **Revert `src/bremen/demo_ui.py`** — restore to pre-PR0068 state.
2. **Revert `src/bremen/api/server.py`** — revert `_handle_demo_route()` changes.
3. **Revert test files** — revert `test_bremen_demo_ui.py` and `test_bremen_api_server.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 4 files changed (allowed list). No forbidden files. |
| **UI drift** | Polished product demo layout. No debug cards. No `alert()` for expected errors. |
| **Readiness drift** | Model state from `ModelState`, not hardcoded. Prediction shows "Not run yet". |
| **No React** | No React, package.json, vite, webpack. |
| **Safety drift** | No unsafe deserialization, no H5 mutation, no clinical claims. |
| **Test drift** | Updated UI tests + server tests. Existing 1283 tests pass unchanged. |
| **Validation drift** | All validation checks pass. No `alert()` for expected errors. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan adds React or a frontend build tool.
- Plan adds `--ui` or another launch command.
- Plan requires new dependencies.
- Plan keeps debug-card "FAIL" for prediction before analyze.
- Plan keeps `alert()` for expected storage/upload/analyze errors.
- Plan requires deployment mutation.
- Plan weakens Bremen safety language.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| UI redesign | Full polished product demo layout. No debug cards. |
| Model state source | `ModelState` singleton — reads actual loaded/error/not_configured state |
| Prediction before analyze | "Not run yet" — not "FAIL" |
| Error handling | Inline events, not `alert()` dialogs |
| Storage status | Visible at workspace top |
| `alert()` usage | None for expected demo errors |
| React | No — time is short, self-contained HTML/CSS/JS is faster |
| Existing endpoints | Unchanged |

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

- `.project-memory/pr/0068-demo-ux-polish-readiness-fixes/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0068 planned as demo UX polish and readiness fixes: yes
- confirm: full `/demo` redesign planned: yes
- confirm: no React planned for this PR: yes
- confirm: no package manager files planned: yes
- confirm: storage_not_configured inline handling planned: yes
- confirm: upload errors rendered inline, not alert-only: yes
- confirm: model readiness consistency planned: yes
- confirm: model_status ready displays ready in `/demo`: yes
- confirm: prediction check before Analyze shows not run yet, not FAIL: yes
- confirm: H5 container workspace remains product input: yes
- confirm: upload/select/analyze workflow preserved: yes
- confirm: logs/events/result UI improved: yes
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
