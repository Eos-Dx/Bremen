# PR 0072 — Plan Canonical H5 Normalizer and Runtime Wiring

Author: plan
Mode: planning only
Branch: 0072-canonical-h5-normalizer-and-runtime-wiring

## Objective

Fix the confirmed runtime defect where `run_inference(h5_path)` (called by `/demo/api/h5/analyze`) fails for any H5 that does not contain `/scans/target`, because `run_h5_preflight()` falls into the legacy hardcoded path when no explicit `target_scan_ref`/`control_scan_ref` are provided.

The fix: make `run_h5_preflight()` use `detect_layout()` for ALL inputs — not just when explicit refs are provided. The detected adapter provides the canonical context (pairing, group paths, side metadata, measurement counts) regardless of the input H5 layout. This normalizes all supported layouts into a single internal contract before preprocessing and inference.

Three supported layouts:
1. **Bremen-native** (`/scans/target`, `/scans/contralateral`) — existing `CanonicalH5LayoutAdapter`
2. **Legacy/synthetic session** (`/session/sets/set_NNN_sample_main`, `contralateral_set_NNN`) — `SessionLayoutH5Adapter` (PR0071)
3. **Matador raw acquisition** (calibration groups, raw 2D measurements) — new `MatadorRawH5Adapter`

No physical H5 repacking. No derived H5 cache. No new API endpoints. No new dependencies.

## Current runtime defect (confirmed)

- `/demo/api/h5/analyze` calls `run_inference(h5_path)` without `target_scan_ref`/`control_scan_ref`
- `run_inference()` calls `run_h5_preflight(h5_path, target_scan_ref=None, control_scan_ref=None)`
- `run_h5_preflight()` has TWO paths:
  - **With refs** (lines 210-257): uses `detect_layout()` + adapter → works for session layout
  - **Without refs** (lines 260+): hardcoded `/scans/target` → fails for session layout
- Session layout H5s fall into the legacy path and raise `H5ContainerError("Missing /scans/target group")`
- Demo route emits premature `preprocessing_started` and `model_inference_started` events before preflight actually passes

## Required reads — observed facts

### `src/bremen/api/preflight.py`
- `run_h5_preflight()` — two paths: (1) adapter-based with refs, (2) legacy without refs.
- `_get_scan_side_and_measurements(f, scan_label)` — hardcodes `/scans/{target|contralateral}` path.
- `_check_top_level_structure()` — currently a no-op (always passes).
- `PreflightResult` — has `metadata` dict that can carry `layout_name`, `target_group_path`, `control_group_path`.

### `src/bremen/api/inference_handler.py`
- `run_inference()` calls `run_h5_preflight()` then `run_preprocessing_bridge()` with `preflight_result`.
- Does NOT pass explicit refs when called from `/demo/api/h5/analyze`.

### `src/bremen/api/preprocessing_bridge.py`
- `run_preprocessing_bridge()` accepts `preflight_result` and `layout_context`.
- When `preflight_result.metadata.layout_name` is set (non-canonical), it builds a context from metadata.
- This already supports adapter-resolved group paths via `H5PredictionContext`.

### `src/bremen/api/h5_layouts.py`
- `H5LayoutAdapter` protocol with `detect()` and `resolve_prediction_context()`.
- Three adapters registered: `CanonicalH5LayoutAdapter`, `CalibrationSampleH5LayoutAdapter`, `SessionLayoutH5Adapter`.
- `detect_layout(h5_file)` iterates registered adapters and returns first match.

### `src/bremen/api/server.py`
- `_handle_demo_h5_analyze()` emits events in sequence, but currently emits `preprocessing_started` and `model_inference_started` BEFORE `run_inference()` is called — these are premature.

### Tests
- 1334 tests pass.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/api/preflight.py`** — MODIFY. Refactor `run_h5_preflight()` to use `detect_layout()` for ALL inputs (not just when refs provided). Pass layout context through `PreflightResult.metadata`.

2. **`src/bremen/api/preprocessing_bridge.py`** — MODIFY. Ensure `build_feature_table()` can read from adapter-resolved group paths for ALL non-canonical layouts, not just `calibration_sample`.

3. **`src/bremen/api/inference_handler.py`** — MODIFY. Pass adapter-resolved context through. Ensure event lifecycle is truthful.

4. **`src/bremen/api/server.py`** — MODIFY. Fix premature event emission in `_handle_demo_h5_analyze()`.

5. **`src/bremen/api/h5_layouts.py`** — MODIFY. Add `MatadorRawH5Adapter` for Matador raw acquisition layout.

6. **`tests/test_bremen_h5_layouts.py`** — MODIFY. Add Matador raw adapter tests.

7. **`tests/test_bremen_api_server.py`** — MODIFY. Add controlled HTTP tests for all three layouts (Bremen-native, session, Matador raw).

**Allowed only if needed**:
- `src/bremen/api/preprocessing_bridge.py` — if the feature extraction needs changes for Matador raw integration output
- `tests/test_bremen_preprocessing_bridge.py` — if bridge tests need updating for adapter-resolved layouts

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

## Exact implementation scope

### 1. Refactor `run_h5_preflight()` — universal adapter-based path

**Current**: Two disjoint paths (adapter with refs, legacy `/scans/target` without refs).

**Required**: Single unified path that uses `detect_layout()` for all inputs.

```python
def run_h5_preflight(h5_path, *, target_scan_ref=None, control_scan_ref=None):
    # Open H5
    f = h5py.File(h5_path, "r")

    # Detect layout (uses adapter registry)
    from bremen.api.h5_layouts import detect_layout, H5LayoutAdapter
    adapter = detect_layout(f)

    if adapter is None:
        raise H5ContainerError("Unsupported H5 layout: no adapter matched")

    # Resolve context with optional refs
    ctx = adapter.resolve_prediction_context(f, target_scan_ref or "", control_scan_ref or "")

    # Collect reasons
    reasons = []
    reasons.append(PreflightReason(check="container_structure", passed=True, message=f"Layout: {adapter.name}"))
    # ... additional validations from ctx ...

    return PreflightResult(
        passed=all(r.passed for r in reasons),
        status="passed" if all(r.passed for r in reasons) else "failed",
        reasons=reasons,
        patient_id=ctx.patient_identifier,
        patient_identifier_source=ctx.patient_identifier_source,
        metadata_fallback_used=ctx.metadata_fallback_used,
        target_side=ctx.target_side,
        contralateral_side=ctx.control_side,
        target_measurement_count=ctx.target_measurement_count or 0,
        contralateral_measurement_count=ctx.control_measurement_count or 0,
        metadata={
            "layout_name": ctx.layout_name,
            "target_group_path": ctx.target_group_path,
            "control_group_path": ctx.control_group_path,
            "target_scan_ref": target_scan_ref,
            "control_scan_ref": control_scan_ref,
        },
    )
```

This eliminates the legacy `/scans/target` hardcoded path. All layouts go through their adapter.

**Backward compatibility**: The `CanonicalH5LayoutAdapter` returns `target_group_path=/scans/target` and `control_group_path=/scans/contralateral` — identical to what the legacy path hardcoded. The `_get_scan_side_and_measurements` function is no longer called by `run_h5_preflight` but can remain for backward-compatible test access.

**Why this works**: The `CanonicalH5LayoutAdapter.detect()` returns True for `/scans/target/measurements` H5 files. The `SessionLayoutH5Adapter.detect()` returns False for those (it checks `/session/sets`). The detection order ensures canonical is checked first, so native layout still works.

### 2. Fix preprocessing bridge for all adapter-resolved layouts

**Current**: `run_preprocessing_bridge()` builds a `layout_context` only for `layout_name == "calibration_sample"`.

**Required**: Build `layout_context` for all non-canonical layouts (including `session_layout` and `matador_raw`).

```python
if resolved_context is None and preflight_result is not None:
    meta = preflight_result.metadata or {}
    layout_name = meta.get("layout_name")
    if layout_name and layout_name != "canonical":
        resolved_context = H5PredictionContext(
            layout_name=layout_name,
            target_scan_ref=meta.get("target_scan_ref", ""),
            control_scan_ref=meta.get("control_scan_ref", ""),
            target_group_path=meta.get("target_group_path", ""),
            control_group_path=meta.get("control_group_path", ""),
            target_side=preflight_result.target_side,
            control_side=preflight_result.contralateral_side,
            patient_identifier=preflight_result.patient_id or "",
            patient_identifier_source=preflight_result.patient_identifier_source,
            metadata_fallback_used=preflight_result.metadata_fallback_used,
            target_measurement_count=preflight_result.target_measurement_count,
            control_measurement_count=preflight_result.contralateral_measurement_count,
            adapter_metadata={},
        )
```

This ensures session and Matador layouts get the same layout-aware extraction as calibration layout.

### 3. Fix premature event emission in `_handle_demo_h5_analyze()`

**Current** (server.py): Events `preprocessing_started` and `model_inference_started` are appended BEFORE `run_inference()` is called. These are premature — if `run_inference()` fails during preflight, the events are still in the response.

**Required**: Remove premature events. Let `run_inference()` handle its own event lifecycle. After `run_inference()` returns, the events array in the handler should only contain events that actually completed before the API call.

The simplest fix: remove the `preprocessing_started` and `model_inference_started` events from the handler. If `run_inference()` succeeds, add a single `completed` event. If it fails, `run_inference()` raises an exception, and the `except` handler adds the failure event. The handler should NOT add events that haven't actually happened yet.

```python
# Remove these from before the try block:
# events.append({"event": "preprocessing_started", ...})
# events.append({"event": "model_inference_started", ...})

try:
    result = run_inference(str(staged_path))
    events.append({"event": "completed", "timestamp": _now(), "detail": "Analysis complete"})
    # ... build response with events and result ...
except (RuntimeError, ValueError, KeyError, TypeError) as exc:
    err_str = str(exc).lower()
    # Classify and add failure event
except Exception:
    _log.exception(...)
    events.append({"event": "inference_failed", ...})
```

### 4. `MatadorRawH5Adapter` — Matador raw acquisition layout adapter

Add a new adapter for Matador raw acquisition H5 containers. Detection based on structural evidence:

```python
class MatadorRawH5Adapter(H5LayoutAdapter):
    """Adapter for Matador raw acquisition H5 containers.

    Detects H5 files with calibration groups and raw measurement data.
    Uses existing trusted XRD preprocessing for 2D→1D integration.
    """

    name = "matador_raw"

    def detect(self, h5_file: h5py.File) -> bool:
        # Must not claim canonical or session layouts
        if "/scans/target/measurements" in h5_file:
            return False
        if "/session/sets" in h5_file:
            return False
        # Must have calibration data AND raw measurements
        has_calib = any(key.startswith("calib") or "calibration" in key.lower() for key in h5_file.keys())
        has_measurements = any("measurement" in key.lower() for key in h5_file.keys())
        return has_calib and has_measurements
```

**Important**: This adapter is a STRUCTURAL ADAPTER only — it detects the layout, pairs measurements, and resolves the prediction context. The actual 2D→1D integration is done by the existing `xrd_preprocessing` library (called during `build_feature_table()` or in the preprocessing bridge).

**Adapter behavior**:
- Discovers raw measurements and calibration data
- Pairs bilateral measurements by position
- Resolves side/position metadata from measurement metadata
- Returns `H5PredictionContext` with adapter metadata noting the layout
- Does NOT call `xrd_preprocessing` — the integration happens during preprocessing (bridge)

**Preprocessing bridge integration**: When `layout_name == "matador_raw"`, the bridge calls the existing XRD preprocessing integration to convert 2D arrays to q/i profiles, then applies the same feature extraction as other layouts.

### 5. Event life cycle fix

Truthful event sequence for ALL layouts:

```
request_received → container_selected → h5_staging_started → h5_staging_completed
→ h5_preflight_started → h5_preflight_completed
→ preprocessing_started → preprocessing_completed
→ model_inference_started → model_inference_completed
→ completed
```

Events are emitted by the stages that actually complete. No premature events.

### 6. Tests

**Controlled HTTP tests** (3 success tests + failure tests):

**Test A — Bremen-native**: 
- Create temp H5 with `/scans/target/measurements`, `/scans/contralateral/measurements`, `/patient/id`, sides
- POST `/demo/api/h5/analyze` with staged temp path
- Expect `completed` + result

**Test B — Session layout**:
- Create temp H5 with `/session/sets/set_001_sample_main/integration/q,i` and `/session/sets/contralateral_set_001_sample_main/integration/q,i`
- No explicit target/control refs
- POST `/demo/api/h5/analyze`
- Expect `completed` + result
- Verify no `/scans/target` fallback

**Test C — Matador raw layout**:
- Create temp H5 with calibration groups and raw 2D measurement arrays
- POST `/demo/api/h5/analyze`
- Expect `completed` + result (with appropriate mocks for external XRD integration library)

**Failure tests**:
- Unknown layout → `h5_preflight_failed`
- Missing session contralateral pair → `h5_preflight_failed`
- Missing Matador calibration → `h5_preflight_failed`
- No premature `preprocessing_started`/`model_inference_started` after preflight failure
- No patient identifiers in responses/logs
- No clinical labels as targets

## Non-goals

- No physical H5 repacking or rewriting
- No derived H5 cache
- No new API endpoints
- No new dependencies
- No approximate/naive radial integration algorithm
- No fabricated success for Matador if `xrd_preprocessing` cannot integrate
- No persisted Matador→Bremen artifacts
- No changes to `/health`, `/model/version`, `/predictions`
- No UI redesign

## Safety boundaries

- No runtime training
- No unsafe model deserialization
- No H5 mutation
- No raw patient data in API/UI/logs
- No clinical labels as prediction targets
- No Aramis product dependency
- `technical_demo_only: true`
- No clinical diagnosis/replacement claims

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only
git diff --stat

# Compile and test
python -m compileall src tests

# Layout adapter tests
python -m pytest -q tests/test_bremen_h5_layouts.py

# Preflight tests
python -m pytest -q tests/test_bremen_h5_preflight.py

# Preprocessing bridge tests
python -m pytest -q tests/test_bremen_preprocessing_bridge.py

# Inference integration tests
python -m pytest -q tests/test_bremen_inference_integration.py

# API server tests (controlled HTTP tests)
python -m pytest -q tests/test_bremen_api_server.py

# Demo UI tests
python -m pytest -q tests/test_bremen_demo_ui.py

# Demo smoke/run/capture tests
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q tests/test_bremen_demo_capture.py

# Full suite
python -m pytest -q

# CLI help
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
```

### Forbidden-pattern grep checks

```bash
# premature events
grep -n "preprocessing_started\|model_inference_started" src/bremen/api/server.py src/bremen/api/inference_handler.py || true
# Expected: only in actual stage completion contexts, not emitted before execution

# XRD integration boundary
grep -n "xrd.preprocessing\|xrd_preprocessing\|integrat" src/bremen tests || true
# Expected: only in Matador adapter or preprocessing bridge, not duplicated

# No clinical/product target labels
grep -R -I -n "biopsy\|birads\|target_side\|BENIGN\|CANCER\|Aramis\|aramis" src/bremen tests || true
# Expected: only in test assertions verifying absence or structural fixture context

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" src/bremen tests || true

# Forbidden files
git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training \
  requirements.txt pyproject.toml config/training frontend web ui \
  package.json package-lock.json yarn.lock pnpm-lock.yaml tests/data docs ROADMAP.md

# No model artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true

find . -name ".DS_Store" -print
```

## Platform safety decisions

| Decision | Value |
|----------|-------|
| Universal preflight | `detect_layout()` for ALL inputs, not just explicit refs |
| Legacy path removal | Legacy `/scans/target` hardcoded path removed from `run_h5_preflight()` |
| Canonical context | `H5PredictionContext` from detected adapter for all layouts |
| Bridge context | All non-canonical layouts get `layout_context` in bridge |
| Event lifecycle | No premature events — events reflect actual completed stages |
| Matador raw adapter | Structural only — integration via `xrd_preprocessing` in bridge |
| New dependencies | None |
| H5 repacking | None |

## Implementation scope

**Files to modify** (7 total):
1. `src/bremen/api/preflight.py` — MODIFY (unify `run_h5_preflight` to use detect_layout always)
2. `src/bremen/api/preprocessing_bridge.py` — MODIFY (support all non-canonical layouts)
3. `src/bremen/api/inference_handler.py` — MODIFY (if needed for context propagation)
4. `src/bremen/api/server.py` — MODIFY (fix premature events)
5. `src/bremen/api/h5_layouts.py` — MODIFY (add `MatadorRawH5Adapter`)
6. `tests/test_bremen_h5_layouts.py` — MODIFY (Matador adapter tests)
7. `tests/test_bremen_api_server.py` — MODIFY (3 controlled HTTP tests + failure tests)

## Files read

- `ROADMAP.md`, `docs/api_contract.md`, `docs/architecture.md`
- `docs/adr/0003`, `0007`, `0008`, `0012`
- `src/bremen/__main__.py`, `demo_smoke.py`, `demo_run.py`, `demo_capture.py`, `demo_ui.py`, `demo_evidence.py`, `demo_config.py`
- `src/bremen/api/server.py`, `app.py`, `preflight.py`, `h5_layouts.py`, `inference_handler.py`, `preprocessing_bridge.py`, `model_state.py`
- `tests/test_bremen_h5_layouts.py`, `test_bremen_api_server.py`, `test_bremen_demo_ui.py`, `test_bremen_demo_smoke.py`, `test_bremen_demo_run.py`, `test_bremen_demo_capture.py`
- `.project-memory/project_contract.yml`, `AGENTS.md`

## Boundary confirmations

- confirm: one PR planned for runtime wiring and in-memory normalization: yes
- confirm: no physical H5 repacking planned: yes
- confirm: no derived H5 cache planned: yes
- confirm: automatic layout detection planned: yes
- confirm: one canonical context planned: yes
- confirm: native layout preserved: yes
- confirm: session layout wired into run_inference without explicit refs: yes
- confirm: Matador raw adapter planned: yes
- confirm: existing trusted XRD integration reused: yes
- confirm: no approximate radial integration planned: yes
- confirm: source H5 remains immutable: yes
- confirm: correct event ordering planned: yes
- confirm: three controlled HTTP success tests planned: yes
- confirm: no fake success planned: yes
- confirm: no clinical/product labels used as target: yes
- confirm: no patient identifiers exposed: yes
- confirm: no Aramis runtime/product dependency: yes
- confirm: no persisted Matador/Bremen derived artifact: yes
- confirm: no React/package/dependency/startup/infra changes: yes
- confirm: no unsafe model loading: yes
- confirm: implementation assigned to coder: yes
- confirm: no git mutation commands run: yes
