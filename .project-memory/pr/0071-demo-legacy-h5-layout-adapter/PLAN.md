# PR 0071 — Plan Demo Legacy/Synthetic H5 Layout Adapter

Author: plan
Mode: planning only
Branch: 0071-demo-legacy-h5-layout-adapter

## Objective

Add a third `H5LayoutAdapter` implementation for legacy/synthetic diffraction H5 containers that use a `session/sets/*` structure (not the Bremen-native `/scans/target` layout). This enables demo ingestion of the two existing H5 files (`cancer_one_patient.h5`, `benign_one_patient.h5`) stored in S3 under `s3://matur-misc-uk/bremen/prediction-inputs/smoke/v0.1/`.

Product framing: This is a Bremen ingestion-boundary adapter for a legacy/synthetic diffraction H5 session layout. It is NOT Aramis integration. No Aramis product labels, targets, biopsy metadata, or benign/cancer classifications are used as Bremen prediction targets.

The existing `CalibrationSampleH5LayoutAdapter` already handles the metadata/context resolution for multi-sample calibration layouts. However, the synthetic one-patient session-layout H5 files do NOT use calibration groups — they use a flat `session/sets/*` structure.

## Confirmed H5 structure (synthetic session layout)

```
/session/
  /sample/patient_name  (e.g., "patient_cancer_001")
  /sets/set_001_sample_main/
    /integration/q  (shape: (2000,))
    /integration/i  (shape: (2000,))
  /sets/contralateral_set_001_sample_main/
    /integration/q  (shape: (2000,))
    /integration/i  (shape: (2000,))
```

No `/scans/target`. No `/scans/contralateral`. No `/calib_*` groups.

## Existing adapter protocol

The `H5LayoutAdapter` abstract class at `src/bremen/api/h5_layouts.py:53` requires:
- `detect(h5_file: h5py.File) -> bool`
- `resolve_prediction_context(h5_file, target_scan_ref, control_scan_ref) -> H5PredictionContext`

Currently registered: `CanonicalH5LayoutAdapter` and `CalibrationSampleH5LayoutAdapter`.

## Required reads — observed facts

### `src/bremen/api/h5_layouts.py`
- `H5LayoutAdapter` abstract class with `detect()` and `resolve_prediction_context()`.
- `register_adapter(adapter)` and `detect_layout(h5_file)` — adapter registry pattern.
- `_BUILTIN_ADAPTERS` list (populated at import time via module-level setup).
- `CanonicalH5LayoutAdapter` — for `/scans/target` layout.
- `CalibrationSampleH5LayoutAdapter` — for `/calib_*` layout.

### `src/bremen/api/preflight.py`
- `run_h5_preflight(h5_path)` — calls `detect_layout()` then `adapter.resolve_prediction_context()`.
- `inspect_h5_container(h5_path)` — reads basic metadata.
- `H5PredictionContext` dataclass — requires `layout_name`, `target_scan_ref`, `control_scan_ref`, `target_group_path`, `control_group_path`, `target_side`, `control_side`, `patient_identifier`, etc.

### `src/bremen/api/preprocessing_bridge.py`
- `run_preprocessing_bridge(h5_path, layout_category, target_scan_ref, control_scan_ref)` — reads target/control integration arrays from the H5 group paths returned by the layout adapter.
- Needs `target_group_path` and `control_group_path` to locate the integration arrays.

### Tests
- 286 key tests pass.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/api/h5_layouts.py`** — MODIFY. Add `SessionLayoutH5Adapter` class implementing the `H5LayoutAdapter` protocol for `session/sets/*` structure.

2. **`tests/test_bremen_h5_layouts.py`** — MODIFY. Add tests for `SessionLayoutH5Adapter`.

**Allowed only if repository inspection proves necessary**:
- `src/bremen/api/preprocessing_bridge.py` — only if the preprocessing bridge needs changes to handle the session-layout integration arrays correctly.
- `src/bremen/api/preflight.py` — only if `run_h5_preflight` or `inspect_h5_container` needs changes.
- `src/bremen/api/server.py` — only if analyze event labels need adjustment.

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

### 1. `SessionLayoutH5Adapter` — New adapter class

Add to `src/bremen/api/h5_layouts.py`:

```python
class SessionLayoutH5Adapter(H5LayoutAdapter):
    """Adapter for legacy/synthetic session-layout diffraction H5 containers.

    Detects H5 files with ``/session/sets`` structure containing paired
    ``set_NNN_sample_main`` and ``contralateral_set_NNN_sample_main``
    groups with ``integration/q`` and ``integration/i`` datasets.

    This adapter does NOT use Aramis product labels, biopsy metadata,
    or clinical classifications as Bremen prediction targets.
    """

    name = "session_layout"

    def detect(self, h5_file: h5py.File) -> bool:
        # Must NOT claim canonical or calibration layouts
        if "/scans/target/measurements" in h5_file:
            return False
        # Must have session/sets
        if "/session/sets" not in h5_file:
            return False
        # Verify at least one target-contralateral pair exists
        try:
            groups = list(h5_file["/session/sets"].keys())
        except Exception:
            return False
        for key in groups:
            if key.startswith("set_") and "_sample_main" in key:
                # Check for matching contralateral
                contra_key = f"contralateral_{key}"
                if contra_key in groups:
                    # Verify integration arrays exist
                    return True
        return False

    def resolve_prediction_context(
        self,
        h5_file: h5py.File,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> H5PredictionContext:
        from .preflight import (
            H5MetadataError,
            H5ContainerError,
            H5SideMismatchError,
            H5PatientMismatchError,
            resolve_patient_metadata,
        )

        # Validate refs
        t_ref = _validate_ref(target_scan_ref, "target_scan_ref")
        c_ref = _validate_ref(control_scan_ref, "control_scan_ref")

        # If explicit refs provided, use them; otherwise find first pair
        sets_group = h5_file["/session/sets"]
        group_keys = list(sets_group.keys())

        target_path: str | None = None
        control_path: str | None = None

        if t_ref and c_ref:
            # Use explicitly provided refs
            if t_ref in group_keys:
                target_path = f"/session/sets/{t_ref}"
            if c_ref in group_keys:
                control_path = f"/session/sets/{c_ref}"
        else:
            # Find first valid pair
            for key in sorted(group_keys):
                if key.startswith("set_") and "_sample_main" in key:
                    contra_key = f"contralateral_{key}"
                    if contra_key in group_keys:
                        target_path = f"/session/sets/{key}"
                        control_path = f"/session/sets/{contra_key}"
                        t_ref = key
                        c_ref = contra_key
                        break

        if not target_path or not control_path:
            raise H5ContainerError(
                "No valid target-controllateral pair found in "
                "/session/sets"
            )

        # Validate integration arrays exist and have correct shape
        for path, label in [(target_path, "target"), (control_path, "control")]:
            for arr_name in ("integration/q", "integration/i"):
                arr_full = f"{path}/{arr_name}"
                if arr_full not in h5_file:
                    raise H5ContainerError(
                        f"Missing {arr_full} for {label} scan"
                    )
                arr = h5_file[arr_full][:]
                if not isinstance(arr, (list, tuple)) or len(arr) == 0:
                    raise H5ContainerError(
                        f"Empty or invalid {arr_full} for {label} scan"
                    )

        # Validate q axes compatibility
        target_q = h5_file[f"{target_path}/integration/q"][:]
        control_q = h5_file[f"{control_path}/integration/q"][:]
        if len(target_q) != len(control_q):
            raise H5ContainerError(
                "Target and control q-axis lengths do not match"
            )
        # Validate q values are compatible (similar range)
        import numpy as np
        if np.max(np.abs(target_q - control_q)) > 0.01:
            raise H5ContainerError(
                "Target and control q-axes are not compatible for "
                "Bremen feature computation"
            )

        # Patient metadata
        try:
            patient_meta = resolve_patient_metadata(h5_file)
        except Exception:
            patient_meta = None

        # Side metadata — read from sample_type/side if available
        # Use safe defaults: "target" / "contralateral"
        # This adapter intentionally does NOT use biopsy/birads/target_side
        # labels as prediction targets.
        target_side: str | None = None
        control_side: str | None = None
        try:
            target_sample_type = _read_sample_metadata_str(
                h5_file, f"{target_path}/../sample/sample_type"
            )
            if target_sample_type:
                target_side = _breast_type_to_side(target_sample_type)
        except Exception:
            pass
        try:
            control_sample_type = _read_sample_metadata_str(
                h5_file, f"{control_path}/../sample/sample_type"
            )
            if control_sample_type:
                control_side = _breast_type_to_side(control_sample_type)
        except Exception:
            pass

        # Measurement count from integration arrays
        target_count = len(h5_file[f"{target_path}/integration/i"][:])
        control_count = len(h5_file[f"{control_path}/integration/i"][:])

        return H5PredictionContext(
            layout_name=self.name,
            target_scan_ref=t_ref,
            control_scan_ref=c_ref,
            target_group_path=target_path,
            control_group_path=control_path,
            target_side=target_side,
            control_side=control_side,
            patient_identifier=(
                patient_meta.patient_identifier if patient_meta else "unknown"
            ),
            patient_identifier_source=(
                patient_meta.patient_identifier_source
                if patient_meta
                else "session_layout"
            ),
            metadata_fallback_used=(
                patient_meta.fallback_used if patient_meta else True
            ),
            target_measurement_count=target_count,
            control_measurement_count=control_count,
            adapter_metadata={
                "layout_name": self.name,
                "pairing_method": "set_contralateral_index",
            },
        )
```

### 2. Register the adapter

At module level or in the setup code, add:

```python
register_adapter(SessionLayoutH5Adapter())
```

The existing `_BUILTIN_ADAPTERS` is populated at import time. Add the registration near the existing adapter registrations (at the end of the file or in a module-level initialization function).

### 3. Tests

Add tests in `tests/test_bremen_h5_layouts.py`:

1. **detect returns True for valid session layout** — Create temp H5 with `/session/sets/set_001_sample_main/integration/q` and `/session/sets/contralateral_set_001_sample_main/integration/i`, verify `detect()` returns True.

2. **detect returns False for canonical layout** — H5 with `/scans/target/measurements` returns False.

3. **detect returns False for missing session/sets** — H5 without session structure returns False.

4. **detect returns False for missing contralateral pair** — Only `set_001_sample_main` without contralateral returns False.

5. **resolve_prediction_context finds first pair** — With multiple set_* groups, picks the first valid pair (sorted).

6. **resolve_prediction_context validates integration arrays** — Missing `integration/q` raises `H5ContainerError`.

7. **resolve_prediction_context validates q-axis compatibility** — Mismatched q lengths raise `H5ContainerError`.

8. **resolve_prediction_context returns correct H5PredictionContext** — Verify layout_name, group paths, patient_identifier.

9. **Explicit refs override auto-pairing** — If `target_scan_ref` and `control_scan_ref` are provided, those specific keys are used.

10. **No raw patient identifiers in test output** — Sanitization check.

11. **No biopsy/birads/target_side/BENIGN/CANCER used as target** — Verify adapter metadata does not use these as prediction targets.

### 4. Preprocessing bridge compatibility (check only)

Verify that `run_preprocessing_bridge()` in `preprocessing_bridge.py` can handle the `target_group_path` and `control_group_path` returned by the new adapter. The bridge reads integration arrays at `{group_path}/integration/i` and uses the `q` arrays for normalization. Since the session layout uses the same `integration/i` and `integration/q` structure as the canonical groups, the bridge should work without changes.

If the bridge requires changes, the plan allows minimal modifications.

## Non-goals

- No Aramis product labels as prediction targets.
- No clinical diagnosis claims.
- No fake successful prediction.
- No UI redesign.
- No React.
- No new dependencies.
- No committed H5 files.
- No deployment mutation.
- No changes to Bremen clinical question.
- No changes to `/scans/target` path for canonical layout.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization.
- No H5 mutation.
- No raw patient data in API/UI/logs.
- No biopsy/birads/target_side/BENIGN/CANCER labels used as Bremen prediction targets.
- No Aramis product labels used.
- `technical_demo_only: true` preserved.
- No clinical diagnosis/replacement claims.
- No fake success.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only
git diff --stat

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_h5_layouts.py
python -m pytest -q tests/test_bremen_h5_preflight.py
python -m pytest -q tests/test_bremen_preprocessing_bridge.py
python -m pytest -q tests/test_bremen_inference_integration.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_demo_ui.py
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
```

### Forbidden-pattern grep checks

```bash
# No Aramis dependency/product labels — check session layout adapter only
grep -R -I -n "biopsy\|birads\|target_side\|BENIGN\|CANCER\|Aramis\|aramis" \
  src/bremen/api/h5_layouts.py tests/test_bremen_h5_layouts.py || true
# Expected: only in test assertion strings verifying absence, or in sample_type metadata reading
# For detection only (not as prediction target)

# No raw patient identifiers exposed in API/UI/logs
grep -R -I -n "patient_name\|patientId\|specimenId\|sample_name" \
  src/bremen/api/h5_layouts.py tests/test_bremen_h5_layouts.py || true
# Expected: only in structural context (e.g., /session/sample/patient_name path)

# No clinical/replacement claims
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output (safe negation only)

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no new unsafe loading

# No React/frontend build
grep -R -I -n "React\|react\|package.json\|vite\|webpack" src/bremen tests || true
# Expected: no output

# No alert() for expected errors
grep -R -I -n "alert(" src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No --ui flag
grep -R -I -n -- "--ui\|demo-run --ui" src/bremen tests || true
# Expected: no output

# No external assets/CDN
grep -R -I -n "https://\|http://.*cdn\|unpkg\|jsdelivr\|googleapis\|fontawesome" \
  src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# Forbidden files unchanged
git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training \
  requirements.txt pyproject.toml config/training frontend web ui \
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
| Adapter name | `SessionLayoutH5Adapter` |
| Detection trigger | `/session/sets` with paired `set_NNN_sample_main` + `contralateral_set_NNN_sample_main` |
| Pairing method | Shared NNN index between `set_NNN_sample_main` and `contralateral_set_NNN_sample_main` |
| Integration arrays | `integration/q` (q-axis) and `integration/i` (intensity) in each pair group |
| Q-axis validation | Length match + `np.max(np.abs(diff)) <= 0.01` |
| Side metadata | From `sample/sample_type` → breast type → side (not hardcoded clinical labels) |
| No target labels | `target_side`, `biopsy`, `birads` not used as Bremen prediction target |
| Patient metadata | From `/session/sample/patient_name` via `resolve_patient_metadata()` |
| Registration | Added to `_BUILTIN_ADAPTERS` list alongside existing adapters |
| New dependencies | None |

## Rollback plan

1. **Revert `src/bremen/api/h5_layouts.py`** — remove `SessionLayoutH5Adapter` class and its registration.
2. **Revert test files** — revert `test_bremen_h5_layouts.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only allowed files changed. No forbidden files. |
| **Adapter drift** | Implements `H5LayoutAdapter` protocol. No `/scans/target` requirement. |
| **No Aramis drift** | No biopsy/birads/BENIGN/CANCER labels as prediction targets. No Aramis product labels. |
| **No React** | No React, package.json, vite, webpack. |
| **Safety drift** | No unsafe deserialization, no H5 mutation, no clinical claims. |
| **Test drift** | 11+ layout tests + existing 286 tests pass unchanged. |
| **Validation drift** | All validation checks pass. No forbidden pattern matches. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan uses Aramis product labels, biopsy, birads, BENIGN/CANCER as Bremen prediction target.
- Plan adds Aramis as a product dependency.
- Plan requires committed H5 files.
- Plan requires new dependencies.
- Plan adds React, `--ui`, or deployment mutation.
- Plan weakens Bremen safety language.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| New adapter | `SessionLayoutH5Adapter` in `h5_layouts.py` |
| Detection | `/session/sets` with paired `set_NNN_sample_main` + `contralateral_set_NNN_sample_main` |
| Integration path | `integration/q` and `integration/i` |
| Q-axis validation | Length match + range compatibility |
| Side/patient metadata | From H5 structure (not clinical labels) |
| Pairing | By shared NNN index, first pair by sort order if no explicit refs |
| Target labels | Not used as prediction targets |
| Bremen question | Unchanged — "Should patient continue to MRI?" |

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
- `src/bremen/api/preprocessing_bridge.py`
- `src/bremen/api/model_state.py`
- `tests/test_bremen_h5_layouts.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_demo_ui.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_demo_run.py`
- `tests/test_bremen_demo_capture.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0071-demo-legacy-h5-layout-adapter/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0071 planned as legacy/synthetic H5 ingestion-boundary adapter: yes
- confirm: no Aramis product dependency planned: yes
- confirm: legacy session/sets layout detection planned: yes
- confirm: set/contralateral pairing planned: yes
- confirm: integration q/i normalization planned: yes
- confirm: `/scans/target` preserved for Bremen-native path: yes
- confirm: `/scans/target` not required for legacy session layout: yes
- confirm: side/problem metadata not used as Bremen target: yes
- confirm: biopsy/birads/status labels not used as Bremen target: yes
- confirm: raw patient metadata not exposed: yes
- confirm: H5 files not mutated: yes
- confirm: no committed H5/HDF5 files planned: yes
- confirm: event ordering fix planned: yes
- confirm: preflight failures stop before preprocessing/model events: yes
- confirm: successful model_inference_completed path targeted: yes
- confirm: no fake success planned: yes
- confirm: PR0068/0069/0070 UI preserved: yes
- confirm: no React planned: yes
- confirm: no package manager files planned: yes
- confirm: no new dependencies planned: yes
- confirm: no new startup command planned: yes
- confirm: no `--ui` flag planned: yes
- confirm: no root `/` demo page planned: yes
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: no unsafe model loading planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
