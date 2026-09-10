# PR0141 — Aramina target-side compatibility diagnostics

Research draft / technical verification only. Requires radiologist review.
This document describes technical request failures, not clinical validity.

Branch: `0141-aramina-target-side-compatibility-diagnostics`
Base: `main` after PR0140 / PR206 (`befa917`).

---

## 1. Files changed

Runtime / API:

| File | Change |
| --- | --- |
| `src/bremen/api/workflow_aramina.py` | Fixed failure taxonomy, per-boundary translation, `AraminaWorkflowError.stage`, `_safe_release_tag`, empty-profile rejection |
| `src/bremen/api/workflow_provider.py` | `WorkflowResult.failure_stage` (default `None`) |
| `src/bremen/api/aramina_api_errors.py` | `unsupported_input_details` now emits exact stage, reason code, detail, remediation, sanitized `safe_details` |
| `src/bremen/api/aramina_preprocessing.py` | `preprocessing_release_tag()` allowlisted helper |
| `src/bremen/api/job_api_handler.py` | Side-aware rerun guard, `target_side` in `input_summary` and job summaries, stage-aware failure details |
| `src/bremen/api/fastapi_app.py` | Side-aware rerun guard and side-aware 409 payload |

Tests:

| File | Change |
| --- | --- |
| `tests/test_aramina_workflow_runtime.py` | 8 existing assertions updated to the new taxonomy; 30 new PR0141 tests |
| `tests/test_catalog_api_multi_model.py` | 5 new PR0141 taxonomy/leak tests |

Project memory:

| File | Change |
| --- | --- |
| `.project-memory/pr/0141-.../COMPATIBILITY_DIAGNOSTICS.md` | This document |
| `.project-memory/pr/0141-.../COMPATIBILITY_MATRIX_SMOKE.sh` | Production matrix smoke script |

Not changed: `aramina_preprocess_worker.py` (its allowlisted diagnostics were
already sufficient), `job_models.py` (the existing `failure_details` dict
already carries the new fields), `source_registry.py`, `control_room_ui.py`.

---

## 2. Failure taxonomy

Public top-level failure code is unchanged: **`ARAMINA_UNSUPPORTED_INPUT`**.

`failure_stage` is now the exact safe runtime boundary, drawn from a closed
allowlist. The previous generic `input_contract` label is no longer emitted.

| `failure_stage` | Boundary that failed |
| --- | --- |
| `preprocessing_contract` | Artifact-declared preprocessing / isolated worker |
| `h5_patient_contract` | Staged H5 does not belong to the requested patient, or its bytes changed after normalization |
| `target_side_contract` | Requested side has no usable measurements, or target measurements carry QC flags |
| `profile_matrix_contract` | Target measurements do not form a valid matrix (empty, non-finite, ragged) |
| `lr1_contract` | LR1 `predict_proba` raised, or its output was out of contract |
| `symmetry_contract` | Paired target/contralateral symmetry features could not be computed |
| `final_dataframe_contract` | Final feature table could not be built with the declared columns |
| `final_model_contract` | Final `predict_proba` raised, or its output was out of contract |
| `report_contract` | Report payload could not be constructed |
| `unknown_input_contract` | Any other input-contract failure, and the collapse target for unknown stages |

Each stage has fixed public `failure_detail` and `remediation` text. Neither is
derived from exception contents.

`failure_reason_code` is `ARAMINA_UNSUPPORTED_INPUT_<STAGE_UPPER>`.

### Safe details

`safe_details` includes only sanitized values, and omits optional fields
entirely when unknown:

- `patient_display_name`, `requested_patient_id` — short opaque IDs only, else `redacted`
- `target_side` — `left` / `right` only, else empty
- `model_id`, `model_version` — short opaque IDs only, else `redacted`
- `resolved_container_id` — sanitized basename only; dropped if it contains a path, scheme, or free-form text
- `available_sides` — allowlisted side labels only
- `measurement_count` — non-negative integer only
- `preprocessing_release` — `v0.1.7-beta` or `v0.1.9-beta` only

Never exposed: S3 bucket/key/path, filesystem path, traceback, raw exception
text, stdout/stderr, env vars, tokens/secrets, artifact checksums or private
metadata, patient measurement arrays.

---

## 3. Before / after API examples

### Before (PR0140)

```json
{
  "workflow_runs": {
    "aramina": {
      "status": "failed",
      "failure": "ARAMINA_UNSUPPORTED_INPUT",
      "failure_stage": "input_contract",
      "failure_detail": "Selected H5 could not be used for the requested Aramina patient and target side.",
      "safe_details": {
        "patient_display_name": "Nova_379",
        "target_side": "left",
        "model_version": "0.2.12-beta"
      }
    }
  }
}
```

`input_contract` was a public category, not the failing step. It did not
distinguish preprocessing, patient identity, side availability, profile
matrix, LR1, symmetry, final DataFrame, final model, or report.

### After (PR0141)

```json
{
  "workflow_runs": {
    "aramina": {
      "status": "failed",
      "failure": "ARAMINA_UNSUPPORTED_INPUT",
      "failure_stage": "target_side_contract",
      "failure_reason_code": "ARAMINA_UNSUPPORTED_INPUT_TARGET_SIDE_CONTRACT",
      "failure_detail": "No usable measurements were available for the requested target side.",
      "remediation": "The selected container has no usable measurements for the requested target_side. Retry with the other side, or select a container that contains the requested side.",
      "safe_details": {
        "patient_display_name": "Nova_379",
        "requested_patient_id": "Nova_379",
        "target_side": "left",
        "model_id": "aramina-target-breast-risk",
        "model_version": "0.2.12-beta",
        "resolved_container_id": "Nova_379.h5",
        "available_sides": ["right"],
        "measurement_count": 3,
        "preprocessing_release": "v0.1.7-beta"
      }
    }
  }
}
```

The example above is illustrative of the response shape. The exact stage for
Nova_379 / Nova_384 is not asserted here — see section 6.

### Preserved PR0140 behavior

| Condition | HTTP | Code | Unchanged |
| --- | --- | --- | --- |
| Missing/blank `patient_id` or `target_side` | 400 | `ARAMINA_INVALID_REQUEST` | yes |
| Unknown/consumed/expired `source_id` | 400 | `SOURCE_ERROR` + `SOURCE_ID_NOT_AVAILABLE` | yes |
| Requested patient differs from H5 metadata | 400 | `ARAMINA_PATIENT_MISMATCH` | yes |
| Invalid free-form values | — | not echoed | yes |

---

## 4. Rerun / duplicate guard findings

### Before

`_find_existing_completed_report(source_key, workflow_id, model_id)` matched
only source + workflow + model. `target_side` was **not** part of the identity.

This was a confirmed defect for Aramina: `target_side` is explicit inference
input, so a completed left-side report blocked a right-side run for the same
source and model. The 409 body also carried no side information, so a client
could not tell why it was blocked.

Bremen was unaffected because Bremen has no `target_side`.

### After

`target_side` **was added** to the duplicate identity.

```python
def _find_existing_completed_report(
    source_key: str,
    workflow_id: str,
    model_id: str,
    target_side: str = "",
) -> tuple[str, str] | None:
    ...
    # Side-aware identity: only enforced when a side is requested.
    if target_side and isk.get("target_side", "") != target_side:
        continue
```

- **Aramina**: the caller passes the normalized requested side, so left and
  right are distinct identities. A completed left run no longer blocks a right
  run.
- **Bremen**: the caller passes `""`. An empty requested side matches any
  stored side, so the original source + workflow + model identity is preserved
  exactly. Bremen behavior is unchanged.

`target_side` is now recorded in `input_summary` (empty for Bremen) and exposed
in `list_analysis_jobs` summaries, so clients can distinguish sides.

The 409 body now includes `existing_target_side` and `requested_target_side`.
Because the full fix was implemented, no deferral is needed.

**Not fixed in this PR:** the Control Room UI still keys
`analyzedSourceKeys[sk][mid]` without side, so the UI may still show a source as
"already analyzed" for the opposite side. That is display-only and is deferred
to a later UI PR, per PLAN.txt.

---

## 5. How to run the production matrix smoke

```bash
BASE_URL=https://<host> \
  ./.project-memory/pr/0141-aramina-target-side-compatibility-diagnostics/COMPATIBILITY_MATRIX_SMOKE.sh
```

With auth enabled:

```bash
BASE_URL=https://<host> AUTH_TOKEN=<bearer> \
  ./.project-memory/pr/0141-aramina-target-side-compatibility-diagnostics/COMPATIBILITY_MATRIX_SMOKE.sh
```

The script:

- resolves `model_id` from `/demo/api/models` by `model_version`
- fetches a **fresh** `source_id` from `/demo/api/h5/containers` before every POST
- runs all 12 combinations: 0.2.12 and 0.2.13 against Nova_214, Nova_227, and
  Nova_379 / Nova_384, each on left and right
- captures HTTP status, `job_id`, `overall_status`, `workflow_status`,
  `failure`, `failure_stage`, `failure_reason_code`, `failure_detail`,
  `remediation`, `model_version`, `report_status`, resolved
  `patient_display_name`, resolved `container_id`, `target_side`,
  `safe_details`, and the `runtime.workflow.failed` event reason
- writes a sanitized report to `COMPATIBILITY_MATRIX_RESULT.txt`

It prints only sanitized public fields and never prints bucket, key, path,
token, or raw response bodies.

---

## 6. What remains unknown

- **The exact stage for Nova_379 left and Nova_384 right is not established by
  this PR.** The taxonomy now makes the answer observable, but the production
  matrix has not been run from this environment. Run the smoke script to obtain
  it.
- The most likely candidates are `target_side_contract` (no usable rows for the
  requested side) and `preprocessing_contract` (artifact preprocessing rejects
  the container). This is a hypothesis, not a finding.
- Production input byte identity, deployed dependency versions, and the
  container build were not verified here.
- The Control Room UI still collapses left/right for the "already analyzed"
  indicator (display-only, deferred).
- `report_contract` is wired but not exercised by a test, because the report
  payload is built inline and no safe injection point exists without changing
  scoring structure.

---

## 7. Scoring / preprocessing / artifact statement

**No scoring, threshold, model artifact, or preprocessing-version change was
made.**

- No model artifact was added, removed, or modified.
- No threshold value was changed.
- No scoring or feature mathematics was changed. `aramina_symmetry.py` is
  untouched.
- No preprocessing version was changed. The isolated environments still select
  `v0.1.7-beta` and `v0.1.9-beta` exactly as before; `preprocessing_release_tag()`
  is a read-only allowlisted accessor added for diagnostics.
- No external Aramina package dependency, provider URL, or HTTP path was added.
- No dummy, uniform, or fake probability fallback was introduced.

Two minimal adapter corrections were made, both required for correct failure
attribution rather than for scoring:

1. `_build_profile_matrix` now rejects an empty intensity row. Previously an
   empty profile produced a `(1, 0)` matrix that passed matrix construction and
   failed later inside LR1, misattributing a profile-matrix failure to the
   scorer. This changes no successful path.
2. `_validate_aramina_source` failures are now translated to
   `h5_patient_contract` instead of falling through to the generic bucket. This
   changes only the reported category, not the outcome.

---

## 8. Validation

Run on this branch:

```
python -m compileall -q src tests
pytest -q tests/test_aramina_workflow_runtime.py
pytest -q tests/test_bremen_model_requirements_api.py tests/test_catalog_api_multi_model.py
pytest -q
git diff --check
```

Results are recorded in the implementation report. Full `pytest -q` must pass
before READY.
