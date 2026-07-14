# PR 0028 — Plan Controlled Model Loading Boundary

Author: plan
Mode: planning only
Branch: 0028-controlled-model-loading-boundary

## Objective

Add a controlled, local-only model loading boundary that proves Bremen can cross the dangerous model deserialization boundary only after existing model package manifest/checksum validation succeeds. This is the first PR to introduce `joblib.load()` in a controlled, post-validation context — isolated, test-covered, and not reachable from any API request handler or inference path.

## Required reads — observed facts

### `.project-memory/project_contract.yml`
- Invariant: "Joblib model packages are controlled artifacts; joblib must be loaded only from checksum-verified model packages."
- This PR implements that invariant concretely.

### Dependency/deserialization facts (from grep commands)

```
--- joblib in requirements.txt ---
requirements.txt:6:joblib>=1.4

--- joblib in pyproject.toml ---
pyproject.toml:16:  "joblib>=1.4",

--- joblib/pickle in model_package.py ---
(NOTHING — no imports, no load calls)

--- load_ functions in model_package.py ---
(NOTHING — no load_ function exists)

--- validate_model_package references ---
model_package.py:243:def validate_model_package(package_dir)
test_bremen_model_package.py:45:    validate_model_package,
(test file uses it extensively)
```

**Key conclusion**: `joblib` IS already approved (in both dependency files). `model_package.py` has validation only — `validate_model_package()` does manifest + checksum + path safety checks but explicitly avoids any deserialization (`no joblib import`, `no pickle import`, `no joblib.load()`). There is no `load_` function in the module. A new `model_loader.py` is needed for the controlled load boundary.

### `src/bremen/model_package.py`
- `validate_model_package()`: validates manifest JSON → required fields → path traversal prevention → artifact exists → SHA-256 checksum match. Returns the validated manifest dict.
- `summarize_model_package()`: calls `validate_model_package()` then returns a `ModelPackageSummary` dataclass (safe metadata, no clinical data).
- `ModelPackageSummary`: includes `model_path` (resolved path to the artifact file), `model_version`, `model_checksum`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`.
- No `joblib` or `pickle` imports. No deserialization.

### `src/bremen/api/model_source.py` (PR 0027)
- `derive_model_source()` returns metadata-only dict from `CloudConfig`. Reports `model_configured=True` or `False` and `model_status`.
- All content fields (`model_checksum`, `feature_schema_version`, etc.) are `None` on both configured and not-configured states — no manifest has been read.
- PR 0028 does not change this module.

### PR 0013 plan (original model package design intent)
- `model_package.py` was designed as validation-only.
- The plan always anticipated a separate loading step in a later PR.
- This PR is that later PR.

## Confirmation: PR 0027 is present

```
test -f src/bremen/api/model_source.py  ->  present
```

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Design decision: `model_loader.py` is new

`model_package.py` has validation only. There is no `load_` function, no `joblib` import, no deserialization. A new `src/bremen/model_loader.py` module is required for the controlled load boundary. It will compose existing `validate_model_package()` from `model_package.py` with an injected deserializer.

## Composite package compatibility

The current manifest contract expects a single `model_filename`. This is a current limitation of the manifest schema — it was designed for a single joblib artifact.

PR 0028 must NOT hardcode a classifier-only assumption. The loader should:
1. Accept a model package directory (validated by `model_package` module).
2. Deserialize whatever artifact `model_filename` points to — no assumption about whether it's a classifier, a feature-extractor reference object, or a composite.
3. Return a `LoadedModelPackage` that holds the deserialized object and its summary metadata.
4. The caller decides what to do with the deserialized object — the loader just provides a safe, validated path to it.

This keeps the API compatible with future composite packages (e.g., a model package directory containing `classifier.joblib` + `reference_stats.joblib` + a manifest that references both) without requiring manifest schema changes in this PR.

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`src/bremen/model_loader.py`** — NEW. Controlled deserialization boundary.
2. **`tests/test_bremen_model_loader.py`** — NEW. Focused tests for the loader boundary.

**Default: do NOT modify `src/bremen/api/app.py`.** This PR is about the local loading boundary only. No API route behavior changes. No model loading during request handling. No prediction pipeline integration.

**If app.py is strictly needed for an additive metadata-only hook** (e.g., to surface `model_loaded=False` in the `/model/version` response to distinguish "env configured but no package loaded" from "package loaded and ready"), the coder must:
- Disclose the exact reason in precommit-review.
- The change must be additive metadata-only.
- No route behavior change.
- No model loading during request handling.
- No `/predictions` behavior change.
- Must be pre-approved by the PLAN.md allowing it.

This PLAN.md does NOT allow app.py changes by default. The current `derive_model_source()` already reports `configured=True` when env is set — that's sufficient for PR 0027 stage. PR 0028 is about the loading boundary only.

## Forbidden files

- `ROADMAP.md`, `README.md`, `docs/**`, `.github/**`, `infra/**`
- `Dockerfile`, `.dockerignore`, `requirements.txt`, `pyproject.toml`
- `config/**`, `examples/**`, `agents/**`
- `src/bremen/modeling.py`, `src/bremen/pipelines.py`, `src/bremen/api/server.py`
- `src/bremen/api/schemas.py`
- `src/bremen/model_package.py` (reused, not modified)
- `src/bremen/api/app.py` (discouraged; only allowed with strict additive metadata-only justification)
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `.DS_Store`, `__pycache__/**`

## Exact implementation scope

### 1. `src/bremen/model_loader.py` — Controlled deserialization boundary

A new module that composes existing `validate_model_package()` with an injected deserializer.

```python
"""Controlled, local-only model loading boundary.

Composes existing ``validate_model_package()`` from ``model_package.py``
with an injected deserializer.  Deserialization happens ONLY after
validation succeeds.

Security boundaries:
- Validation must pass before deserialization is attempted.
- Deserializer is injected (default: ``joblib.load``).
- No inference, no H5 reads, no network calls.
- Module-level import of ``joblib`` is allowed only inside the
  default loader function; the module itself does not import joblib
  at the top level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .model_package import (
    ModelPackageError,
    ModelPackageSummary,
    summarize_model_package,
    validate_model_package,
)


@dataclass(frozen=True)
class LoadedModelPackage:
    """Result of a validated and deserialised model load.

    Attributes
    ----------
    summary : Safe metadata from the manifest (no clinical data).
    model : The deserialised model object.  Type depends on what was
        serialised — may be a classifier, a feature-extractor with
        reference statistics, or a composite container.
    warnings : Tuple of non-fatal warnings raised during loading.
    """

    summary: ModelPackageSummary
    model: Any
    warnings: tuple[str, ...] = field(default_factory=tuple)


def load_model_package(
    package_dir: str | Path,
    *,
    deserializer: Callable[[str | Path], Any] | None = None,
) -> LoadedModelPackage:
    """Validate and load a model package.

    This is the ONLY place in Bremen that composes validation and
    deserialisation into a single gated step.

    Parameters
    ----------
    package_dir : Directory containing a validated model package
        (``manifest.json`` + artifact file).
    deserializer : Callable that accepts a ``str | Path`` and returns
        the deserialised object.  Defaults to ``joblib.load``.
        Must be injectable for testing — tests MUST use a safe
        deserializer (e.g., a lambda that returns a simple sentinel),
        never ``joblib.load`` on real model artifacts.

    Returns
    -------
    A ``LoadedModelPackage`` with validated metadata and the
    deserialised model.

    Raises
    ------
    ModelPackageError
        If validation fails (any subclass: NotFound, Manifest,
        Checksum, Security).  Deserialisation is NOT attempted.
    """
    if deserializer is None:
        from joblib import load as _joblib_load  # noqa: PLC0415

        deserializer = _joblib_load

    # Step 1: Validate (checksum, manifest, path safety)
    manifest = validate_model_package(package_dir)
    summary = summarize_model_package(package_dir)

    # Step 2: Deserialize (only after validation succeeds)
    model = deserializer(str(summary.model_path))

    return LoadedModelPackage(
        summary=summary,
        model=model,
    )
```

**Key design decisions:**

| Decision | Value |
|----------|-------|
| Where is `joblib.load()`? | Inside a default-argument closure in `load_model_package()`. Injected via `deserializer` parameter. The import of `joblib` is the only `joblib` import in the entire codebase's API surface. |
| Validation before deserialization? | **Yes** — `validate_model_package()` is called first and raises on failure. `summarize_model_package()` also calls validate internally (it calls `validate_model_package()` first). |
| Can the deserializer be overridden? | **Yes** — tests must inject a safe lambda (e.g., `lambda p: {"loaded": p}`) and NEVER call joblib.load on real artifacts. |
| What does `model` hold? | Whatever the artifact file contains — could be a classifier, a reference-statistics object, or a composite. No assumption about type. |
| `joblib` import scope? | Inside the `if deserializer is None` branch only, lazily. Top-level `import joblib` is NOT present. |
| Inference routing? | None. The loader returns a deserialized object. Callers decide what to do with it. |
| Compatible with composite packages? | Yes — `model` is `Any`. If a future composite package contains multiple artifacts, the loader already accepts any type. The limitation (single model_filename) is in the manifest schema, not in this loader. |

### 2. `tests/test_bremen_model_loader.py` — Loader tests

Test scenarios (all use injected safe deserializer, never real `joblib.load`):

1. **Valid package loads successfully** — Create a valid package via existing `_make_package` helper, inject a deserializer that returns `{"type": "model"}`, verify `LoadedModelPackage` returned with correct `summary.model_version` and `model.attribute` matching the injected value.
2. **Validation failure prevents deserialization** — Create a package with a bad checksum, inject a deserializer that would raise an error IF called, verify `ModelPackageChecksumError` is raised and the injected deserializer is never invoked.
3. **Missing manifest prevents deserialization** — Create a directory without manifest, inject a sentinel-raising deserializer, verify `ModelPackageNotFoundError` without calling the deserializer.
4. **Path traversal prevents deserialization** — Package with traversal `model_filename`, verify `ModelPackageSecurityError` without calling deserializer.
5. **Default deserializer is joblib.load** — Verify that `load_model_package.__defaults__` or inspection shows the default `deserializer` is `joblib.load`. (This proves the deserializer relationship without actually calling it.)
6. **Import safety** — `import bremen.model_loader` does not trigger `import joblib` at module level. Verify via `sys.modules` check that `joblib` is not loaded after importing `model_loader`.
7. **No `joblib.load()` at top level** — AST check that `model_loader.py` does not import `joblib` at module top level (only inside the default-argument fallback).
8. **No inference or prediction code** — Grep for `predict`, `infer`, `train`, `h5py`, `boto3`, `requests`, `httpx` — must be absent.
9. **No H5/HDF5 references** in the new module or test file.
10. **No changes to `model_package.py`** — Verify via `git diff --name-only`.

## Non-goals

- No inference or prediction routing.
- No training.
- No model loading from S3/AWS/network (local only).
- No H5/HDF5 reads.
- No preprocessing bridge.
- No Matador integration.
- No API route behavior change.
- No model loading during request handling.
- No `/predictions` behavior change.
- No `app.py` changes by default.
- No changes to `model_package.py`.
- No changes to dependency files.
- No Docker/Terraform/CI changes.
- No clinical claims.

## Safety boundaries

This PR must ensure:
- **Validation before deserialization**: `validate_model_package()` is always called before any deserializer. The existing SHA-256 checksum, path traversal prevention, and manifest validation all gate the load.
- **Validation failure blocks load**: If any `ModelPackageError` subclass is raised, the deserializer is never invoked.
- **Deserializer is injectable**: Tests use safe sentinel deserializers, never real joblib.load.
- **joblib import is lazy**: Inside the default-argument fallback only, not at module top level.
- **No inference**: The loader returns a deserialized object; it does not call `.predict()`, `.transform()`, or any other method on it.
- **No S3/AWS/network**: Local filesystem only.
- **No clinical output**: The `LoadedModelPackage.model` is typed as `Any` — no assumption about its content or purpose.
- **Composite package compatible**: `model: Any` — no hardcoded classifier-only assumption.

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_model_loader.py
python -m pytest -q tests/test_bremen_model_package.py
python -m pytest -q tests/test_bremen_api_model_source.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_api_server.py
python -m bremen --help
python -m bremen serve --help
python -m pytest -q
```

### Required forbidden-pattern grep checks

```bash
# No AWS/H5/AI/network in new loader or tests
grep -R "boto3\|botocore\|h5py\|\.h5\|\.hdf5" src/bremen tests/test_bremen_model_loader.py || true

# No HTTP/network libraries
grep -R "requests\|httpx\|urllib.request" src/bremen tests/test_bremen_model_loader.py || true

# No prohibited clinical claims
grep -R "diagnos\|clinical validation\|replace MRI\|replace biopsy" src/bremen tests/test_bremen_model_loader.py || true

# No predict/infer/train
grep -R "def predict\|\\.predict(" src/bremen tests/test_bremen_model_loader.py || true
```

### Critical: joblib/pickle hit review

```bash
grep -R "joblib.load\|import joblib\|pickle.load\|import pickle" src/bremen tests || true
```

Every hit must be direct-read reviewed. An acceptable hit is:
- `model_loader.py`: `from joblib import load as _joblib_load` — inside the default-argument fallback, isolated to one controlled loader function, called only after `validate_model_package()` success, never during request handling.
- Any `test_bremen_model_loader.py` hit: must be an assertion about the default being `joblib.load`, not an actual call to it.
- Any hit in `test_bremen_model_package.py`: must be an AST-scoped check that `model_package.py` does NOT import joblib (existing negative test, acceptable).
- Any hit from the test helper that imports `joblib` for AST-based safety checking: acceptable as existing test infrastructure.

## Rollback plan

1. **Revert `src/bremen/model_loader.py`** — delete.
2. **Revert `tests/test_bremen_model_loader.py`** — delete.
3. No other files affected. The `model_package.py` module is untouched.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `model_loader.py` and `test_bremen_model_loader.py` changed. |
| **Load boundary drift** | `validate_model_package()` called before any deserialization. Deserializer is injected. Validation failure prevents deserialization. |
| **joblib import drift** | Only inside default-argument fallback, not at module top level. Tests use injected safe deserializer. |
| **Composite compatibility drift** | `model: Any` — no classifier-only assumption. Manifest schema limitation documented as current. |
| **app.py drift** | Not modified by default. No API route changes. No model loading during request handling. |
| **Safety drift** | No inference, training, H5 reads, AWS calls, clinical claims. |
| **Test drift** | 10 scenarios. Injected deserializer proves validation-before-load. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. Direct-read review of joblib hits confirms safety. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- PR 0027 source metadata (`model_source.py`) is not present on this branch.
- Implementation requires dependency changes.
- Implementation requires Docker, Terraform, AWS, GitHub Actions, or deployment changes.
- Implementation requires S3 reads, H5 reads, preprocessing, prediction integration, or inference.
- Implementation cannot prove validation-before-deserialization.
- Implementation duplicates existing `model_package.py` load/checksum logic instead of reusing it.
- Implementation hardcodes a classifier-only package assumption (must use `Any` for `model`).
- Implementation cannot stay within the allowed files.
- `model_loader.py` imports `joblib` at the top level (outside the default-argument fallback).

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0028-controlled-model-loading-boundary/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0028-controlled-model-loading-boundary/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Decisions summary

| Decision | Value |
|----------|-------|
| Module name | `src/bremen/model_loader.py` (new). `model_package.py` is not modified. |
| Relationship to model_package.py | `model_loader.py` imports and calls `validate_model_package()` and `summarize_model_package()`. Does NOT reimplement validation. |
| joblib import location | Inside `load_model_package()` default-argument fallback: `from joblib import load as _joblib_load`. NOT at module top level. |
| Deserializer injection | `load_model_package(..., deserializer=None)` defaults to `joblib.load`. Tests MUST override with a safe lambda. |
| Validation gates deserialization | `validate_model_package()` called first; raises on any failure. Deserializer never invoked if validation fails. |
| Model type | `Any` — compatible with future classifier, reference-stats, or composite packages. |
| app.py changes | **Not allowed by default.** No API route changes. No model loading during request handling. |
| Composite support | Loader supports it (`model: Any`). Manifest schema limitation (single model_filename) is documented as current. |
| Testing | 10 scenarios. Injected safe deserializer proves validation-before-load. No real joblib.load in tests. |

## Files read

- `.project-memory/project_contract.yml`
- `.project-memory/pr/0013-model-package-contract/PLAN.md`
- `.project-memory/pr/0013-model-package-contract/reviews/precommit-review.yml`
- `.project-memory/pr/0027-model-package-source-integration/PLAN.md`
- `.project-memory/pr/0027-model-package-source-integration/reviews/precommit-review.yml`
- `src/bremen/model_package.py`
- `src/bremen/api/model_source.py`
- `tests/test_bremen_model_package.py`
- `tests/test_bremen_api_model_source.py`
- `requirements.txt`
- `pyproject.toml`

## Files written

- `.project-memory/pr/0028-controlled-model-loading-boundary/PLAN.md` (this file)

## Files intentionally ignored

- All source files not in the allowed set (`app.py`, `server.py`, `__main__.py`, etc.)
- All test files not in the allowed set (existing tests not modified)
- All documentation, infrastructure, and dependency files

## Boundary confirmations

- confirm: PR 0027 source metadata (`model_source.py`) confirmed present on branch: yes
- confirm: `model_package.py` has NO load function; `model_loader.py` is needed: yes
- confirm: no dependency changes planned: yes
- confirm: no S3/AWS/network calls planned: yes
- confirm: no model loading from API routes planned (app.py unchanged): yes
- confirm: no inference/training planned: yes
- confirm: no H5/HDF5 reads planned: yes
- confirm: validation-before-deserialization enforced: yes
- confirm: deserializer is injectable for safe testing: yes
- confirm: `joblib` import is lazy (inside function, not module top-level): yes
- confirm: `model: Any` — no classifier-only assumption: yes
- confirm: no clinical claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
