# PR 0061 — Plan Bremen Demo Evidence Pack

Author: plan
Mode: planning only
Branch: 0061-bremen-demo-evidence-pack

## Objective

Create a reusable, Bremen-native demo evidence pack that makes the existing PR0060 `demo-smoke` path more meaningful and durable. This evidence pack provides a deterministic synthetic feature artifact contract, a standard evidence bundle structure, and safe, repeatable demo evidence that survives beyond a single demo session.

The PR0060 `demo-smoke` CLI exercises the service. PR0061 adds the **what** — the structured evidence contract that demo-smoke can produce, that product owners can show, and that operators can rely on for release confidence.

The existing service (996 tests pass) already has:
- Full HTTP API with health, model/version, prediction submit/poll
- Model state management with synthetic model loader
- Feature artifact prediction flow (`run_feature_artifact_prediction()`)
- Decision-support report wrapper (`build_decision_support_report()`)
- Structured logging with request_id propagation
- `python -m bremen demo-smoke` CLI command

This PR adds a deterministic evidence layer without changing any of those paths.

## Bremen Product Positioning (non-negotiable)

- **Bremen owns its own clinical question**: "Should patient continue to MRI?"
- **Bremen owns its own target definition**, feature schema (`BREMEN_V01_FEATURE_COLUMNS`, 15-column v0.1), preprocessing boundary, model package, and decision-support output contract.
- **Aramis is sibling provenance/context only.** Aramis is not a dependency, benchmark, benchmark target, comparison baseline, or alignment target for Bremen.
- No Aramis artifact, Aramis model description, Aramis feature schema, or Aramis score may be used as a Bremen dependency.
- The demo evidence pack is for **Bremen product usage only**, not cross-product alignment.

## Required reads — observed facts

### `src/bremen/demo_smoke.py` (PR0060)
- `run_demo_smoke()` calls GET /health, GET /model/version, POST /predictions + poll.
- Returns a dict with `technical_demo_only`, `base_url`, `request_id`, `checks`, `health`, `model_version`, `prediction`, `warnings`, `status`, `timestamp`.
- Prediction check polls for completion and extracts `decision_support` from completed results.
- CLI: `python -m bremen demo-smoke --base-url URL`.

### `src/bremen/api/feature_artifact_prediction.py`
- `run_feature_artifact_prediction(artifact, predictor)` — controlled internal prediction.
- Accepts validated feature artifact dict conforming to `bremen.feature_artifact.v0.1` schema.
- Returns `FeatureArtifactPredictionResult` with decision-support report.

### `src/bremen/api/decision_support.py`
- `build_decision_support_report(inference_result)` — safe report with `intended_use`, `limitations`, `model_metadata`, `input_summary`, `prediction_summary`, `decision_support`.
- `REPORT_SCHEMA_VERSION = "v0.1"`.

### `src/bremen/feature_artifacts.py`
- `validate_feature_artifact()` — validates a dict against the `bremen.feature_artifact.v0.1` schema.
- `REQUIRED_FEATURE_COLUMNS` — 15-column list.
- `build_standard_feature_artifact(feature_values, metadata)` — builds a valid artifact.

### `src/bremen/inference.py`
- `predict_proba_portable(package, feature_vector)` — pure numpy/math inference.
- `validate_portable_logreg_model(package)` — validates model package structure.

### `src/bremen/__main__.py`
- PR0060 `demo-smoke` subcommand already exists.
- Adding a new subcommand follows established pattern.

### `tests/test_bremen_demo_smoke.py`
- 314 lines, covers PR0060 CLI and `run_demo_smoke()`.
- Must remain passing after PR0061.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_evidence.py`** — NEW. Demo evidence pack module with deterministic synthetic payloads, evidence bundle builders, and validators. Stdlib only.
2. **`src/bremen/demo_smoke.py`** — MODIFY. Integrate evidence bundle into demo-smoke output. Minimal change: call `build_demo_evidence_bundle()` before returning.
3. **`tests/test_bremen_demo_evidence.py`** — NEW. Comprehensive tests for the evidence pack.
4. **`tests/test_bremen_demo_smoke.py`** — MODIFY. Add tests verifying evidence bundle in demo-smoke output (or that demo-smoke can optionally include it).

## Forbidden files

- `.github/**`, `infra/terraform/**`
- `Dockerfile`, `Dockerfile.training`
- `requirements.txt`, `pyproject.toml`
- `frontend/**`, `web/**`, `ui/**`
- `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `node_modules/**`
- `tests/data/**`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `tfstate`, `.terraform`
- `config/training/**`
- `src/bremen/training/**`
- `docs/**`, `ROADMAP.md` — no docs-only PR allowed

## Exact implementation scope

### 1. `src/bremen/demo_evidence.py` — Demo evidence pack

A small stdlib-only module. No new dependencies. No network calls. No model loading. No H5 reads.

```python
"""Bremen product demo evidence pack.

Provides deterministic synthetic payloads, evidence bundle structures,
and validation helpers for Bremen product demos and operator smoke checks.

This module is safe to import anywhere — no model loading, no network
calls, no H5 reads, no clinical data.

All outputs include ``technical_demo_only: True`` and the Bremen product
identity disclaimer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
```

**Constants**:

```python
DEMO_EVIDENCE_VERSION = "v0.1"
BREMEN_PRODUCT_NAME = "Bremen"
BREMEN_PRODUCT_QUESTION = "Should patient continue to MRI?"
BREMEN_DEMO_DISCLAIMER = (
    "This is a technical product demo of Bremen's controlled "
    "decision-support workflow. It is not a clinical result. "
    "It is not clinically validated. It does not replace MRI, "
    "biopsy, a radiologist, a clinician, or clinical judgment."
)
```

**`build_demo_feature_artifact_payload()`**:

Returns a deterministic synthetic feature artifact dict conforming to the `bremen.feature_artifact.v0.1` schema (the one validated by `validate_feature_artifact` in `feature_artifacts.py`). The payload should:

- Contain exactly the 15 required feature columns.
- Use stable synthetic values suitable for the built-in synthetic model.
- Include safe synthetic metadata (`preprocessing_source: "demo_evidence_pack"`, `source_package_version: DEMO_EVIDENCE_VERSION`, `configuration_label: "technical_demo_only"`).
- Avoid real patient data, real scan data, clinical values.
- Be deterministic (same output every call for reproducible demos).

The actual feature values should be chosen to produce a known, stable prediction result when run through the synthetic model loaded by `_load_synthetic_model()` in `server.py` (which has `coef=[0.1]*15`, `intercept=0.0`, `threshold=0.5`). Target values: `p_mri_needed ≈ 0.5` (at threshold) or `≈ 0.62` (above threshold) depending on desired demo story.

**`build_demo_evidence_bundle(...)`**:

```python
def build_demo_evidence_bundle(
    *,
    base_url: str | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
    model_status: str | None = None,
    model_version: str | None = None,
    feature_schema_version: str | None = None,
    prediction_status: str | None = None,
    decision_support: dict[str, Any] | None = None,
    checks: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
```

Returns a dict with:

| Field | Type | Always present? |
|-------|------|-----------------|
| `technical_demo_only` | `bool` | Yes — `True` |
| `product` | `str` | Yes — `"Bremen"` |
| `product_question` | `str` | Yes — `"Should patient continue to MRI?"` |
| `disclaimer` | `str` | Yes |
| `evidence_version` | `str` | Yes — `DEMO_EVIDENCE_VERSION` |
| `scenario_id` | `str` | Yes — `"bremen_demo_v1"` |
| `base_url` | `str \| None` | If provided |
| `request_id` | `str \| None` | If provided |
| `job_id` | `str \| None` | If provided |
| `model_status` | `str \| None` | If provided |
| `model_version` | `str \| None` | If provided |
| `feature_schema_version` | `str \| None` | If provided |
| `prediction_status` | `str \| None` | If provided |
| `decision_support` | `dict \| None` | If provided |
| `checks` | `dict \| None` | If provided |
| `warnings` | `list \| None` | If provided |
| `safety_notes` | `list[str]` | Yes |

**`validate_demo_evidence_bundle(bundle: dict) -> dict`**:

Validates that the bundle dict has the required shape:

- `technical_demo_only` must be `True`.
- `product` must be `"Bremen"`.
- `product_question` must be the expected string.
- `evidence_version` must be a non-empty string.
- `safety_notes` must be a non-empty list of strings.
- No diagnosis/replacement language in any field value.
- No Aramis references in any field value.

Returns the validated bundle (pass-through). Raises `ValueError` on validation failure.

**`safety_notes` default content**:

```python
[
    "Technical product demo only — not a clinical result.",
    "Not clinically validated.",
    "Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.",
    "All clinical decisions must be made by qualified clinicians.",
]
```

**Non-negotiable rules in this module**:

- **No Aramis references** — no string `"Aramis"`, `"aramis"`, `"M2Q"`, `"BENIGN vs CANCER"`, or any Aramis product label in any evidence output.
- **No clinical diagnosis language** — no `"diagnosis"`, `"diagnose"`, `"replaces MRI"`, `"replaces biopsy"`, `"replaces radiologist"`, `"replaces clinician"`.
- **No real patient data** — all values are synthetic.
- **No model artifact loading** — the synthetic feature payload is just numbers.
- **No network calls** — pure data transformation.

### 2. `src/bremen/demo_smoke.py` — Evidence bundle integration

Minimal integration: call `build_demo_evidence_bundle()` near the end of `run_demo_smoke()` and include the result in the returned dict.

```python
def run_demo_smoke(...) -> dict:
    # ... existing logic ...
    result = { ... }  # existing result dict
    
    # Add evidence bundle
    from .demo_evidence import build_demo_evidence_bundle
    result["evidence"] = build_demo_evidence_bundle(
        base_url=base_url,
        request_id=request_id,
        job_id=prediction_result.get("job_id"),
        model_status=model_version_result.get("model_status"),
        model_version=model_version_result.get("model_version"),
        feature_schema_version=model_version_result.get("feature_schema_version"),
        prediction_status=prediction_result.get("status"),
        decision_support=prediction_result.get("decision_support"),
        checks=checks,
        warnings=warnings or [],
    )
    return result
```

This is backward-compatible — existing consumers that only look at `status`, `health`, `model_version`, `prediction`, `warnings` will see no change. The `evidence` field is additive.

The existing prediction check already extracts `decision_support` from completed results — that data flows naturally into the evidence bundle.

### 3. `tests/test_bremen_demo_evidence.py` — New tests

Test scenarios:

1. **DEMO_EVIDENCE_VERSION is a non-empty string** — Module constant exists and is valid.
2. **Build synthetic feature payload** — Returns a dict with all required feature columns (15), deterministic values, synthetic metadata.
3. **Synthetic payload passes validate_feature_artifact** — The payload from `build_demo_feature_artifact_payload()` passes the existing `validate_feature_artifact()` from `feature_artifacts.py`.
4. **Synthetic payload produces stable prediction** — When run through the deterministic portable_logreg math (all-coefs=0.1, intercept=0.0, threshold=0.5) produces a known result.
5. **Evidence bundle shape** — `build_demo_evidence_bundle()` returns dict with all required keys.
6. **`technical_demo_only` is True** — Critical invariant.
7. **`product` is "Bremen"** — Product identity invariant.
8. **`product_question` is correct** — Product question invariant.
9. **`safety_notes` is a non-empty list** — Safety invariant.
10. **No Aramis references** — String scan for "Aramis", "aramis", "M2Q", "BENIGN vs CANCER" returns no matches.
11. **No diagnosis/replacement language** — String scan for prohibited patterns returns no matches.
12. **validate_demo_evidence_bundle() passes for valid bundle** — Accepts well-formed bundle.
13. **validate_demo_evidence_bundle() rejects bundle without technical_demo_only** — Raises ValueError.
14. **validate_demo_evidence_bundle() rejects bundle with wrong product** — Raises ValueError.
15. **JSON serializable** — `json.dumps(bundle)` succeeds.
16. **Deterministic output** — Two calls with same arguments produce identical output.
17. **Demo-smoke can include evidence** — When run against a local test server with synthetic model, evidence bundle appears in output.
18. **Evidence bundle in demo-smoke preserves request_id** — request_id in evidence matches top-level request_id.

### 4. `tests/test_bremen_demo_smoke.py` — Updated tests

Add 2–3 test cases verifying that the evidence bundle is present in the demo-smoke output when a running server is available:

- `test_demo_smoke_output_contains_evidence_bundle` — Verify `evidence` key exists in output.
- `test_demo_smoke_evidence_technical_demo_only` — Verify `evidence.technical_demo_only is True`.
- `test_demo_smoke_evidence_product_is_bremen` — Verify `evidence.product == "Bremen"`.

Demote any existing tests that break due to the added `evidence` field (they shouldn't — the field is additive; just verify backward compatibility).

## Non-goals

- No new HTTP routes or API contract changes.
- No model loading changes.
- No H5 reads or writes.
- No AWS/S3 calls.
- No Matador resolver implementation.
- No clinical report template addition.
- No Aramis alignment or cross-product comparison.
- No ensemble planning.
- No deployment mutation (Terraform, Docker, CI/CD).
- No React/frontend.
- No new dependencies.
- No docs/ROADMAP updates.
- No real patient data.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization — demo evidence pack does not touch `joblib.load` or `pickle.load`.
- No new `joblib.load` — the synthetic feature payload is pure dict/list/float data.
- No pickle loading.
- No H5 reads — the evidence pack works with synthetic feature artifacts (numbers only), not H5 files.
- No H5 writes.
- No preprocessing expansion.
- No AWS/S3 network calls.
- No Matador resolver implementation.
- No clinical report template.
- No clinical diagnosis claims.
- `technical_demo_only: true` in every evidence bundle.
- No real patient data, no fabricated clinical evidence.
- **No Aramis references** — zero tolerance for Aramis product labels in Bremen demo evidence.
- **No clinical/replacement language** — zero tolerance for diagnosis, MRI/biopsy/radiologist replacement language.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_evidence.py
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_api_skeleton.py
if test -f tests/test_bremen_feature_artifact_prediction_flow.py; then python -m pytest -q tests/test_bremen_feature_artifact_prediction_flow.py; else echo "SKIP missing tests/test_bremen_feature_artifact_prediction_flow.py"; fi
if test -f tests/test_bremen_decision_support_output.py; then python -m pytest -q tests/test_bremen_decision_support_output.py; else echo "SKIP missing tests/test_bremen_decision_support_output.py"; fi
if test -f tests/test_bremen_dependency_hygiene.py; then python -m pytest -q tests/test_bremen_dependency_hygiene.py; else echo "SKIP missing tests/test_bremen_dependency_hygiene.py"; fi
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
```

### Forbidden-pattern grep checks

```bash
# No Aramis dependency or product labels in Bremen demo evidence
grep -R -I -n "Aramis\|aramis\|M2Q\|BENIGN vs CANCER" \
  src/bremen/demo_evidence.py src/bremen/demo_smoke.py \
  tests/test_bremen_demo_evidence.py tests/test_bremen_demo_smoke.py || true
# Expected: no output

# No clinical/replacement claims in demo evidence
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen/demo_evidence.py src/bremen/demo_smoke.py \
  tests/test_bremen_demo_evidence.py tests/test_bremen_demo_smoke.py || true
# Expected: no output (negative-test assertion strings in tests are allowed with justification)

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen tests/test_bremen_demo_evidence.py tests/test_bremen_demo_smoke.py || true
# Expected: no new unsafe deserialization (pre-existing in modeling.py/mlflow_tracking.py is not in PR scope)

# No H5 dependency in demo evidence pack
grep -R -I -n "\.h5\|\.hdf5\|h5py" \
  src/bremen/demo_evidence.py tests/test_bremen_demo_evidence.py || true
# Expected: no output

# No AWS/network client deps in demo evidence or smoke (stdlib urllib in demo_smoke is allowed)
grep -R -I -n "boto3\|botocore\|requests\|httpx" \
  src/bremen/demo_evidence.py src/bremen/demo_smoke.py \
  tests/test_bremen_demo_evidence.py tests/test_bremen_demo_smoke.py || true
# Expected: no output

# No new web framework
grep -R -I -n "FastAPI\|Flask\|uvicorn\|gunicorn\|starlette\|aiohttp\|django" \
  src tests requirements.txt pyproject.toml || true
# Expected: no output

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
| Synthetic feature payload source | Inline in `demo_evidence.py` — no file reads, no H5, no model artifact. |
| Synthetic feature values | Deterministic. Chosen to produce a stable known prediction with the built-in synthetic model. |
| Evidence bundle shape | Dict with `technical_demo_only`, `product`, `product_question`, `disclaimer`, `evidence_version`, `scenario_id`, and optional contextual fields. |
| `technical_demo_only` | Required `True` in every bundle. |
| `product` | Required `"Bremen"`. |
| `product_question` | Required `"Should patient continue to MRI?"`. |
| Aramis references | **Zero tolerance** — no Aramis strings in any evidence output. |
| Clinical/replacement language | **Zero tolerance** — no diagnosis/replacement strings in any evidence output. |
| Real patient data | **Forbidden** — all values synthetic. |

## Rollback plan

1. **Revert `src/bremen/demo_evidence.py`** — delete.
2. **Revert `src/bremen/demo_smoke.py`** — remove the evidence bundle integration lines.
3. **Revert `tests/test_bremen_demo_evidence.py`** — delete.
4. **Revert `tests/test_bremen_demo_smoke.py`** — remove evidence bundle test cases.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 4 allowed files changed. No forbidden files. |
| **Evidence drift** | Stdlib-only. No model loading. No H5 reads. No network calls. No clinical data. |
| **Demo-smoke drift** | Evidence field is additive — backward compatible. Existing checks/prediction/health behavior unchanged. |
| **Safety drift** | No unsafe deserialization. No H5. No AWS. No clinical claims. `technical_demo_only: true` enforced. |
| **Aramis drift** | Zero Aramis references in evidence output. |
| **Test drift** | 18+ new evidence tests + 2–3 updated demo-smoke tests. Existing tests pass unchanged. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Implementation makes Aramis a dependency, benchmark, or alignment target.
- Implementation introduces Aramis product labels in evidence output.
- Implementation introduces clinical diagnosis or replacement language in evidence output.
- Implementation requires new dependencies.
- Implementation requires Terraform, Docker, GitHub Actions, or deployment changes.
- Implementation adds new HTTP routes or changes the API contract.
- Implementation performs unsafe model deserialization outside the approved `ModelState.load_at_startup()` boundary.
- Implementation reads H5 files or adds new H5 runtime dependency.
- Implementation hardcodes secrets, account IDs, registry URLs, or production URLs.
- Implementation cannot be completed within the allowed files.
- Implementation becomes docs-only.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Evidence module | `src/bremen/demo_evidence.py` — stdlib only. |
| Synthetic feature payload | `build_demo_feature_artifact_payload()` — deterministic, 15-column, passes `validate_feature_artifact()`. |
| Evidence bundle | `build_demo_evidence_bundle()` — structured dict with mandatory `technical_demo_only`, `product`, `product_question`, `safety_notes`. |
| Evidence validator | `validate_demo_evidence_bundle()` — validates shape, product identity, safety disclaimers. |
| Demo-smoke integration | Additive `evidence` field in `run_demo_smoke()` output. Backward-compatible. |
| Product identity | `product: "Bremen"`, `product_question: "Should patient continue to MRI?"`. |
| Aramis | Not referenced, not used, not benchmarked. |
| Clinical claims | None. `technical_demo_only: true`. |
| Dependencies | None new. |

## Files read

- `ROADMAP.md`
- `docs/api_contract.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `src/bremen/__main__.py`
- `src/bremen/demo_smoke.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `src/bremen/api/jobs.py`
- `src/bremen/api/schemas.py`
- `src/bremen/api/model_state.py`
- `src/bremen/api/model_source.py`
- `src/bremen/api/feature_artifact_prediction.py`
- `src/bremen/api/decision_support.py`
- `src/bremen/feature_artifacts.py`
- `src/bremen/inference.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_feature_artifact_prediction_flow.py`
- `tests/test_bremen_decision_support_output.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_dependency_hygiene.py`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `docs/adr/0012-system-of-record-boundary.md`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0061-bremen-demo-evidence-pack/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0061 planned as Bremen-native demo evidence pack: yes
- confirm: Bremen remains independent from Aramis: yes
- confirm: Aramis not used as dependency or benchmark: yes
- confirm: demo evidence is not disposable: yes (reusable module with versioned contract)
- confirm: product-owner demo value planned: yes
- confirm: evidence bundle planned: yes
- confirm: deterministic synthetic Bremen payload planned: yes
- confirm: `technical_demo_only` preserved: yes
- confirm: demo-smoke integration planned: yes (additive `evidence` field)
- confirm: request_id/logging behavior preserved: yes
- confirm: deployed URL compatibility preserved without AWS SDK: yes (via demo-smoke)
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: no React/frontend planned: yes
- confirm: no new dependencies planned: yes
- confirm: no unsafe model loading planned: yes
- confirm: no H5 mutation planned: yes
- confirm: no real patient data planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
