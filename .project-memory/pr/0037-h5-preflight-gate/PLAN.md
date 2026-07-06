# PR 0037 — Plan H5 Preflight Gate and Historical H5 Artifact Cleanup

Author: plan
Mode: planning only
Branch: 0037-h5-preflight-gate

## Objective

Implement a strict H5 preflight gate that validates target/control structural and metadata constraints before any preprocessing or inference, and clean up the historically tracked real H5 artifact inherited from the Aramis fork. This is the second step on the critical path to Bremen's first working prediction.

## Critical path context

Bremen roadmap was redefined on 2026-07-06. Completed: PR 0036 (v0.1 model package infrastructure). Next: PR 0037 (this PR) → PR 0038 (preprocessing) → PR 0039 (inference/first prediction).

## Historical tracked H5 cleanup

The repository historically tracked this real H5 subset:
- `tests/data/aramis_real_h5_subset_20260128_5_patients.h5`

On this branch, the file has already been removed from git tracking (visible in `git status --short` as `D tests/data/aramis_real_h5_subset_20260128_5_patients.h5`). This is a pre-existing cleanup delta, not a blocker.

**External copy**: `../bremen-private-artifacts/h5/aramis_real_h5_subset_20260128_5_patients.h5` (outside repo). Human-verified SHA-256: `0bda036f08b057d992b329f6bd6834b3bb52cb74b1f3fca3efb08dda5edf655a`.

## External H5 artifact policy

- The external H5 subset is available only as a local opt-in smoke/schema reference.
- Default tests use synthetic H5 files created under `tmp_path`.
- CI must not require the external H5 subset.
- The external H5 subset must not be copied into `tests/data`.
- The external H5 subset must not be committed.
- The external H5 subset must not be used as clinical validation evidence.
- Optional real-subset smoke uses `BREMEN_H5_PREFLIGHT_SMOKE_PATH` and skips when the variable is absent.
- No raw scan arrays may be extracted into repo artifacts.

## Artifact guard plan

The `.gitignore` already has artifact guard entries (`*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz` — present on lines 16-29). No `.gitignore` changes needed.

## Required reads — observed facts

### `.project-memory/project_contract.yml`
- Invariants: H5 metadata validation required before prediction. Target/control same-patient, opposite-side requirements.

### `ROADMAP.md`
- PR 0037 described as "H5/preflight metadata gate: target/control consistency and H5 metadata validation."

### `docs/architecture.md`
- "Online Prediction Runtime Workflow" includes H5 inspect gate before preprocessing.
- Mandatory safety invariants include target/control role validation.

### `h5py`
- Already a declared dependency in both `requirements.txt` (`>=3.12`) and `pyproject.toml` (`>=3.10`).

### `.gitignore`
- Already has artifact guard entries for all prohibited artifact types.

### Existing tests
- `tests/data/` directory exists with `README.md`.
- No other test data files beyond the removed H5.

## H5 schema assumption

Without assuming the exact real H5 layout (the external copy is outside the repo), the preflight gate must support a minimal schema. The synthetic test schema is:

```
/patient/id               -> str
/scans/target/side        -> str ("L" or "R")
/scans/target/measurements -> array of measurement arrays
/scans/target/metadata/snr -> float (optional)
/scans/contralateral/side -> str ("L" or "R")
/scans/contralateral/measurements -> array
/scans/contralateral/metadata/snr -> float (optional)
```

This is sufficient for the required validation logic. The real H5 may have additional fields; the preflight gate should accept well-formed H5 files with these minimum paths and gracefully handle extra paths.

## Preflight validation scope

Required validations:

| Validation | Failure behavior |
|-----------|-----------------|
| Target and contralateral scans belong to the same patient | Fail closed — `H5PatientMismatchError` |
| Target and contralateral sides are opposite | Fail closed — `H5SideMismatchError` |
| Required metadata fields exist (patient/id, target/side, target/measurements, contralateral/side, contralateral/measurements) | Fail closed — `H5MetadataError` |
| Minimum measurement count exists per scan/side (>= 1) | Fail closed — `H5MeasurementError` |
| SNR/QC thresholds if present — evaluated, warning if below threshold | Warning (not fail) — `H5QualityError` warnings |
| Unknown/optional metadata missing | Warning, not silent pass |
| Malformed H5 structure (cannot read expected paths) | Fail closed — `H5ContainerError` |
| Empty measurement arrays | Fail closed — `H5MeasurementError` |
| Mismatched patient IDs | Fail closed — `H5PatientMismatchError` |
| Same-side target/contralateral | Fail closed — `H5SideMismatchError` |
| Missing contralateral entirely | Fail closed — `H5ContainerError` with explicit message |

No preprocessing or feature computation in PR 0037.

## Public code API plan

**File**: `src/bremen/api/preflight.py`

### Typed exceptions

```python
class H5PreflightError(Exception):
    """Base exception for H5 preflight failures."""

class H5ContainerError(H5PreflightError):
    """Container cannot be read or required paths are missing."""

class H5MetadataError(H5PreflightError):
    """Required metadata fields missing or invalid."""

class H5PatientMismatchError(H5PreflightError):
    """Target and contralateral do not belong to the same patient."""

class H5SideMismatchError(H5PreflightError):
    """Target and contralateral sides are not opposite."""

class H5MeasurementError(H5PreflightError):
    """Measurement data is missing or below minimum count."""

class H5QualityError(H5PreflightError):
    """Quality metrics below threshold (warning)."""
```

### Result types

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PreflightReason:
    """A single preflight check result."""
    check: str          # Name of the check
    passed: bool        # True if check passed
    message: str        # Human-readable description
    detail: Any = None  # Optional structured detail


@dataclass
class PreflightResult:
    """Structured result of an H5 preflight."""
    status: str                        # "passed" | "failed" | "warning"
    passed: bool                       # True if all mandatory checks passed
    reasons: list[PreflightReason]     # Individual check results
    warnings: list[str]                # Non-blocking warnings
    patient_id: str | None
    target_side: str | None
    contralateral_side: str | None
    target_measurement_count: int | None
    contralateral_measurement_count: int | None
    metadata: dict[str, Any]           # Safe metadata summary
    qc_flags: list[str]                # Quality flags from snap checks


class PreflightStatus:
    """Constants for preflight status values."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
```

### Public functions

```python
def run_h5_preflight(h5_path: str | Path) -> PreflightResult:
    """Run full H5 preflight on a target/control H5 container.

    Validates:
    - Container structure
    - Same patient
    - Opposite sides
    - Required metadata
    - Minimum measurement counts
    - SNR/QC thresholds (if present)

    Returns a PreflightResult. Raises H5PreflightError subclasses
    on structural failure.

    Does NOT read raw scan arrays for any purpose other than
    counting measurements. Does NOT preprocess. Does NOT load
    models. Does NOT infer.
    """

def inspect_h5_container(h5_path: str | Path) -> dict[str, Any]:
    """Inspect H5 structure at path level only.

    Returns a dict of path -> type/shape for the expected
    container structure. Does NOT load raw scan arrays.
    """

def validate_same_patient(h5_file) -> PreflightReason:
    """Check patient/id matches between target and contralateral."""

def validate_opposite_sides(h5_file) -> PreflightReason:
    """Check target and contralateral side values are opposite."""

def validate_required_metadata(h5_file) -> PreflightReason:
    """Check required metadata fields exist and are non-empty."""

def validate_measurement_counts(h5_file, min_count: int = 1) -> PreflightReason:
    """Check measurement count per scan/side meets minimum."""

def validate_snr_thresholds(h5_file, min_snr: float | None = None) -> PreflightReason:
    """Check SNR/QC thresholds if present. Warning only."""
```

## Result contract

`PreflightResult` fields:

| Field | Type | Description |
|-------|------|-------------|
| `status` | str | `"passed"`, `"failed"`, or `"warning"` |
| `passed` | bool | True if all mandatory checks passed |
| `reasons` | list[PreflightReason] | Each check result |
| `warnings` | list[str] | Non-blocking warnings |
| `patient_id` | str or None | Patient identifier from H5 |
| `target_side` | str or None | Target breast side |
| `contralateral_side` | str or None | Contralateral breast side |
| `target_measurement_count` | int or None | Number of target measurements |
| `contralateral_measurement_count` | int or None | Number of contralateral measurements |
| `metadata` | dict | Safe metadata summary (no raw scan data) |
| `qc_flags` | list[str] | Quality flags |

**Result must NOT include raw scan data.**

## Dependency strategy

`h5py` is already declared in both `requirements.txt` and `pyproject.toml`. No dependency changes needed.

## Test plan

**File**: `tests/test_bremen_h5_preflight.py`

### Default synthetic tests (always run)

1. `test_valid_synthetic_h5_passes` — Create synthetic H5 with valid target/contralateral, verify `PreflightResult.passed == True`.
2. `test_patient_mismatch_fails` — Target and contralateral have different patient IDs, verify `H5PatientMismatchError`.
3. `test_same_side_fails` — Both sides set to "L", verify `H5SideMismatchError`.
4. `test_missing_contralateral_fails` — No contralateral scan group, verify `H5ContainerError`.
5. `test_missing_required_metadata_fails` — Remove `patient/id`, verify `H5MetadataError`.
6. `test_low_measurement_count_fails` — Set target measurements to empty array, verify `H5MeasurementError`.
7. `test_low_snr_adds_warning` — Set SNR below threshold, verify warning in `warnings` but `passed == True` (non-blocking).
8. `test_malformed_container_fails_closed` — Corrupted H5 or non-H5 file, verify `H5ContainerError`.
9. `test_result_excludes_raw_measurements` — Verify `PreflightResult.metadata` does not contain measurement arrays.
10. `test_no_preprocessing_inference_model_loading` — Verify importing `preflight` does not import training/inference/model modules.
11. `test_exception_hierarchy` — Verify `H5PatientMismatchError` is subclass of `H5PreflightError`, which is subclass of `Exception`.

### Optional real subset smoke tests (opt-in)

12. `test_real_subset_schema_inspection` — Skipped unless `BREMEN_H5_PREFLIGHT_SMOKE_PATH` is set. Opens the file, inspects schema/metadata only. Does not assert clinical validity.

```python
@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="BREMEN_H5_PREFLIGHT_SMOKE_PATH not set — skipping real subset smoke",
)
def test_real_subset_schema_inspection():
    h5_path = os.environ["BREMEN_H5_PREFLIGHT_SMOKE_PATH"]
    result = run_h5_preflight(h5_path)
    assert result is not None
    # Inspect metadata only — no clinical assertions
```

## Runtime/API boundary

- PR 0037 does NOT wire into `POST /predictions`.
- PR 0037 does NOT change prediction route behavior.
- PR 0037 does NOT load models or run inference.
- PR 0037 does NOT preprocess feature data.
- PR 0037 does NOT integrate with Matador.
- PR 0037 does NOT produce clinical reports.
- PR 0037 does NOT change runtime configuration.

## Non-goals

- No preprocessing or feature computation.
- No inference or model loading.
- No prediction route changes.
- No Matador integration.
- No clinical report.
- No runtime config changes.
- No real H5 committed or copied into repo.
- No derived H5/array artifacts committed.
- No dependency changes (h5py already present).
- No `.gitignore` changes (already guarded).
- No training pipeline changes.
- No model package changes.

## Allowed implementation files

1. `src/bremen/api/preflight.py` — NEW
2. `tests/test_bremen_h5_preflight.py` — NEW
3. Deletion of `tests/data/aramis_real_h5_subset_20260128_5_patients.h5` from git tracking (already done on this branch)

## Forbidden files

- Any new real `*.h5`, `*.hdf5`, `*.joblib`, `*.pkl`, `*.npy`, `*.npz`
- Copying external H5 into `tests/data`
- Committing derived H5/array artifacts
- `src/bremen/api/inference.py` or any inference module
- `src/bremen/api/preprocessing_bridge.py`
- `src/bremen/model_loader.py`, `model_package.py`
- `src/bremen/training/**`
- `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`, `.project-memory/project_contract.yml`
- Terraform files, `.github/**`, Dockerfiles
- `requirements.txt`, `pyproject.toml` (no dependency changes)
- `.gitignore` (already has artifact guards)

## Validation checklist

```bash
# 1-3) Baseline
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Compile check
python -m compileall src tests

# 5-6) Preflight tests and identity test
python -m pytest -q tests/test_bremen_h5_preflight.py
python -m pytest -q tests/test_bremen_import_identity.py

# 7-8) Preflight API references present
grep -R "run_h5_preflight\|PreflightResult\|H5PreflightError\|H5PatientMismatchError\|H5SideMismatchError" src/bremen/api tests 2>/dev/null || true

# 9) Real-subset smoke opt-in
grep -R "BREMEN_H5_PREFLIGHT_SMOKE_PATH\|skipif\|real_subset" tests/test_bremen_h5_preflight.py 2>/dev/null || true

# 10) No inference/training/model loading in preflight
grep -R "predict_proba\|model_loader\|load_model\|run_training_from_config\|bremen.training" src/bremen/api/preflight.py tests/test_bremen_h5_preflight.py 2>/dev/null || true

# 11-12) No tracked H5/model artifacts
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"
find . -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) -not -path "./.git/*" -not -path "./venv/*" -print

# 13) No forbidden file changes
git diff --name-only -- docs/adr ROADMAP.md docs/architecture.md src/bremen/model_loader.py src/bremen/model_package.py src/bremen/training infra .github Dockerfile Dockerfile.training requirements.txt pyproject.toml .gitignore
# Must return nothing

# 14) Full test suite
python -m pytest -q
```

## Rollback plan

1. **Revert `src/bremen/api/preflight.py`** — delete.
2. **Revert `tests/test_bremen_h5_preflight.py`** — delete.
3. No other files affected (H5 cleanup was already done on this branch).

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `preflight.py` and `test_bremen_h5_preflight.py` changed. |
| **H5 cleanup drift** | H5 file already removed from tracking. `.gitignore` already has artifact guards. |
| **Preflight scope drift** | All 11 required validations listed. No preprocessing/inference/model loading. |
| **Result contract drift** | All required fields present. No raw scan data in result. |
| **Dependency drift** | No change to dependency files. `h5py` already available. |
| **Test drift** | 11 synthetic + 1 optional real-subset smoke. |
| **Runtime boundary drift** | Not wired into predictions. No model loading. No inference. |
| **Clinical claims drift** | Preflight is structural acceptance only, not clinical validity. |
| **Validation drift** | All validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Real H5 remains tracked after implementation.
- External H5 is required in CI.
- Uploaded patient data must be copied into repo.
- Preprocessing or feature extraction is required.
- Inference or model loading is required.
- Model package changes are required.
- Prediction route behavior must change.
- Clinical claims are needed.
- `h5py` is missing and dependency change is required.
- Synthetic H5 cannot model required gate behavior.
- Cleanup requires rewriting git history.

## Follow-up PR 0038 summary

PR 0038 — Preprocessing Bridge. Connect approved preprocessing path using the preflight gate result, without training or clinical claims.

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0037-h5-preflight-gate/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0037-h5-preflight-gate/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after precommit-review.

## Files read

- `.project-memory/project_contract.yml`
- `.project-memory/pr/0036-model-v01-package-publication/PLAN.md`
- `.project-memory/pr/0036-model-v01-package-publication/reviews/precommit-review.yml`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-two-image-build-training-pipeline-separation.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `src/bremen/model_package.py`
- `src/bremen/model_loader.py`
- `src/bremen/config.py`
- `src/bremen/__main__.py`
- Existing API/runtime files
- Existing tests
- `.gitignore`
- `requirements.txt`
- `pyproject.toml`

## Files written

- `.project-memory/pr/0037-h5-preflight-gate/PLAN.md` (this file)

## Files intentionally ignored

- All runtime source files not in allowed set.
- All training pipeline files.
- All docs, ADR, and roadmap files.
- Any H5/HDF5 or model artifact files (venv contents excluded).

## Boundary confirmations

- confirm: branch is `0037-h5-preflight-gate`: yes
- confirm: historical H5 file already removed from git tracking: yes
- confirm: `.gitignore` already has artifact guards: yes
- confirm: `h5py` already declared as dependency: yes
- confirm: no dependency changes needed: yes
- confirm: no implementation files edited during planning: yes
- confirm: no inference/model loading/preprocessing planned: yes
- confirm: no prediction route behavior changes planned: yes
- confirm: no clinical claims planned: yes
- confirm: no real H5/data access in CI planned: yes
- confirm: preflight is structural acceptance only: yes
- confirm: no git mutation commands run: yes
