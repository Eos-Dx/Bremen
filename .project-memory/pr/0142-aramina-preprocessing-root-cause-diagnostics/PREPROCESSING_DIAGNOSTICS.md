# PR0142 — Aramina preprocessing root-cause diagnostics

Research draft / technical verification only. Requires radiologist review.
This document describes technical request failures, not clinical validity.

Branch: `0142-aramina-preprocessing-root-cause-diagnostics`
Base: `main` after PR0141 (`712b4e4`).

---

## 1. Files changed

Runtime diagnostics:

| File | Change |
| --- | --- |
| `src/bremen/api/aramina_preprocessing.py` | Allowlists, `safe_preprocessing_diagnostic()`, `AraminaPreprocessingError`, worker-spawn and output-parse boundaries |
| `src/bremen/api/workflow_aramina.py` | Carries the allowlisted diagnostic on `AraminaWorkflowError` and `WorkflowResult` |
| `src/bremen/api/workflow_provider.py` | `WorkflowResult.preprocessing_diagnostic` (default `None`) |
| `src/bremen/api/aramina_api_errors.py` | Merges the subdiagnostic into `safe_details` for `preprocessing_contract` only |
| `src/bremen/api/job_api_handler.py` | Passes the subdiagnostic into `failure_details` |

Tests:

| File | Change |
| --- | --- |
| `tests/test_aramina_workflow_runtime.py` | 1 existing assertion updated; 40 new PR0142 tests |

Project memory:

| File | Change |
| --- | --- |
| `.project-memory/pr/0142-.../PREPROCESSING_DIAGNOSTICS.md` | This document |
| `.project-memory/pr/0142-.../PREPROCESSING_ROOT_CAUSE_SMOKE.sh` | Deployed root-cause smoke |

Not changed: `aramina_preprocess_worker.py` (its allowlisted diagnostic was
already correct), `fastapi_app.py`, `job_models.py`, `source_registry.py`,
`control_room_ui.py`.

---

## 2. Exact diagnostic path implemented

Before PR0142 the worker's `diagnostic` dict was parsed, logged, and then
**discarded** — only a fixed `ValueError("Aramina preprocessing failed")`
propagated. The public failure could therefore only say
`preprocessing_contract`.

The path is now:

```
aramina_preprocess_worker.py
  prints {"error": ..., "diagnostic": {stage, exception_class, transformer}}
        |
        v
aramina_preprocessing.preprocess_aramina()
  parses stdout -> safe_preprocessing_diagnostic() -> AraminaPreprocessingError
        |
        v
workflow_aramina._prepare_features()
  except AraminaPreprocessingError -> AraminaWorkflowError(
      "ARAMINA_UNSUPPORTED_INPUT", "preprocessing_contract",
      original_exception_class, exc.diagnostic)
        |
        v
workflow_aramina.AraminaWorkflowProvider.execute()
  WorkflowResult(failure_stage="preprocessing_contract",
                 preprocessing_diagnostic={...})
        |
        v
job_api_handler.create_analysis_job()
  unsupported_input_details(..., preprocessing_diagnostic=...)
        |
        v
aramina_api_errors.unsupported_input_details()
  re-sanitizes, then merges into failure_details["safe_details"]
```

Three new boundaries were also added in `preprocess_aramina`:

- worker spawn failure (missing interpreter, timeout, OS error) → `worker_process`
- unparseable worker stdout → `worker_output`
- empty worker rows → `worker_empty_output`

Previously the first two raised a bare `ValueError` with no stage.

---

## 3. Before / after response examples

### Before (PR0141)

```json
{
  "workflow_runs": {
    "aramina": {
      "status": "failed",
      "failure": "ARAMINA_UNSUPPORTED_INPUT",
      "failure_stage": "preprocessing_contract",
      "failure_reason_code": "ARAMINA_UNSUPPORTED_INPUT_PREPROCESSING_CONTRACT",
      "failure_detail": "Artifact-declared preprocessing did not produce usable measurements.",
      "remediation": "The selected H5 could not be preprocessed with the model's declared preprocessing contract. Verify the container layout and required measurement metadata, then retry with a fresh source_id.",
      "safe_details": {
        "patient_display_name": "Nova_379",
        "requested_patient_id": "Nova_379",
        "target_side": "left",
        "model_id": "aramina-target-breast-risk",
        "model_version": "0.2.12-beta",
        "resolved_container_id": "Nova_379.h5"
      }
    }
  }
}
```

The failure was correctly localized to preprocessing, but not to a stage.

### After (PR0142)

```json
{
  "workflow_runs": {
    "aramina": {
      "status": "failed",
      "failure": "ARAMINA_UNSUPPORTED_INPUT",
      "failure_stage": "preprocessing_contract",
      "failure_reason_code": "ARAMINA_UNSUPPORTED_INPUT_PREPROCESSING_CONTRACT",
      "failure_detail": "Artifact-declared preprocessing did not produce usable measurements.",
      "remediation": "The selected H5 could not be preprocessed with the model's declared preprocessing contract. Verify the container layout and required measurement metadata, then retry with a fresh source_id.",
      "safe_details": {
        "patient_display_name": "Nova_379",
        "requested_patient_id": "Nova_379",
        "target_side": "left",
        "model_id": "aramina-target-breast-risk",
        "model_version": "0.2.12-beta",
        "resolved_container_id": "Nova_379.h5",
        "preprocessing_stage": "worker_pipeline_execution",
        "preprocessing_exception_class": "ValueError",
        "preprocessing_transformer": "PatientSpecimenValidityFilter",
        "preprocessing_release": "v0.1.7-beta",
        "preprocessing_reason_code": "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED"
      }
    }
  }
}
```

The stage, exception class, transformer, and release values above are
**illustrative of the response shape**. They are not a finding — see section 6.

---

## 4. Exact public / private boundary

**Public (allowlisted, safe to expose):**

- `failure` = `ARAMINA_UNSUPPORTED_INPUT` (unchanged)
- `failure_stage` = `preprocessing_contract` (unchanged)
- `failure_reason_code` = `ARAMINA_UNSUPPORTED_INPUT_PREPROCESSING_CONTRACT` (unchanged)
- `failure_detail`, `remediation` — fixed text per stage
- `safe_details.preprocessing_stage`
- `safe_details.preprocessing_exception_class`
- `safe_details.preprocessing_transformer`
- `safe_details.preprocessing_release`
- `safe_details.preprocessing_reason_code`

**Private (never exposed):**

- S3 bucket, key, or URI
- filesystem path, H5 path, worker script path
- worker stdout / stderr
- traceback
- raw exception message
- environment variable names or values
- tokens, secrets, credentials
- artifact checksum or private artifact metadata
- patient measurement arrays
- DataFrame row contents
- `q_range` / `radial_profile_data` values

The worker already redirects stdout/stderr into in-memory buffers and emits
only the three allowlisted diagnostic keys. `safe_preprocessing_diagnostic`
re-sanitizes at every hop, so a caller cannot inject an unallowlisted value
through the exception path.

---

## 5. Exact allowlists

**`preprocessing_stage`** (anything else → `worker_process`):

```
worker_imports
worker_config
worker_pipeline_build
worker_pipeline_execution
worker_output
worker_empty_output
worker_process
```

**`preprocessing_exception_class`** (anything else → `redacted`):

```
ValueError  TypeError  KeyError  IndexError  AttributeError
ImportError  ModuleNotFoundError  RuntimeError  OSError  MemoryError
```

**`preprocessing_transformer`** — the existing `_DIAGNOSTIC_TRANSFORMERS`
allowlist in `aramina_preprocess_worker.py` (anything else → `redacted`):

```
H5PoniGeometryCalculatorTransformer  H5SessionSelectorTransformer
H5ToDataFrameTransformer  ProductColumnBuilder  ColumnValueFilter
GroupValueFilter  ProductStatusGroupFilter  PairedGroupFilter
FaultyPixelDetector  ConstantQRangeTransformer  AzimuthalIntegration
SNRTransformer  SNRFilter  PatientSpecimenValidityFilter
QRangeValueNormalizer  RadialProfileValueFilter  KeepColumnsTransformer
```

**`preprocessing_release`** (anything else → `redacted`):

```
v0.1.7-beta
v0.1.9-beta
```

**`preprocessing_reason_code`** — derived only from the allowlisted stage:

| Stage | Reason code |
| --- | --- |
| `worker_imports` | `ARAMINA_PREPROCESSING_WORKER_IMPORTS_FAILED` |
| `worker_config` | `ARAMINA_PREPROCESSING_CONFIG_FAILED` |
| `worker_pipeline_build` | `ARAMINA_PREPROCESSING_PIPELINE_BUILD_FAILED` |
| `worker_pipeline_execution` | `ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED` |
| `worker_output` | `ARAMINA_PREPROCESSING_OUTPUT_FAILED` |
| `worker_empty_output` | `ARAMINA_PREPROCESSING_EMPTY_OUTPUT` |
| `worker_process` | `ARAMINA_PREPROCESSING_PROCESS_FAILED` |

The subdiagnostic is attached **only** when `failure_stage` is
`preprocessing_contract`. Every other failure stage is unchanged.

---

## 6. How to run the smoke

```bash
BASE_URL=https://<host> \
  ./.project-memory/pr/0142-aramina-preprocessing-root-cause-diagnostics/PREPROCESSING_ROOT_CAUSE_SMOKE.sh
```

With auth enabled:

```bash
BASE_URL=https://<host> AUTH_TOKEN=<bearer> \
  ./.project-memory/pr/0142-aramina-preprocessing-root-cause-diagnostics/PREPROCESSING_ROOT_CAUSE_SMOKE.sh
```

The script runs the four deployed checks:

- `0.2.12` + `Nova_379` + `left`
- `0.2.12` + `Nova_379` + `right`
- `0.2.13` + `Nova_384` + `left`
- `0.2.13` + `Nova_384` + `right`

It resolves `model_id` from `/demo/api/models`, fetches a **fresh** `source_id`
from `/demo/api/h5/containers` before every POST, and prints HTTP status,
`job_id`, `overall_status`, `failure`, `failure_stage`, `failure_reason_code`,
`preprocessing_stage`, `preprocessing_exception_class`,
`preprocessing_transformer`, `preprocessing_release`,
`preprocessing_reason_code`, and `remediation`. Output is written to
`PREPROCESSING_ROOT_CAUSE_RESULT.txt`.

---

## 7. Was the Nova_379 / Nova_384 root cause established locally?

**No.** The diagnostic path is now proven by tests, but the live root cause was
not established from this environment:

- No deployed instance was reachable, so the smoke was not run.
- No production logs were available.
- The real Aramina artifacts and the Nova_379 / Nova_384 H5 containers were not
  available locally, so the isolated worker could not be executed against them.

What **is** established locally:

- The worker's failure JSON is now propagated end-to-end to the public
  `safe_details` (proven by tests).
- Every allowlist boundary behaves correctly for unknown, malformed, and
  hostile values (proven by tests).
- The public failure code and stage are unchanged (proven by tests).

Running the smoke script against the deployment will produce the exact
`preprocessing_stage` and `preprocessing_transformer` for each of the four
combinations.

---

## 8. What remains unknown without live deploy / logs

- The exact `preprocessing_stage` for Nova_379 and Nova_384.
- The exact rejecting transformer, if any.
- Whether the two patients fail for the same reason or different reasons.
- Whether the failure is container-specific (missing metadata, unsupported
  layout) or artifact-version-specific.
- Whether the isolated worker environments in the deployed image match the
  pinned `v0.1.7-beta` / `v0.1.9-beta` versions.
- Whether the deployed image was rebuilt after PR0139 added the isolated
  environments.

---

## 9. Behavior-change statement

**No scoring, threshold, model artifact, or preprocessing-version change was
made.**

- No model artifact was added, removed, or modified.
- No threshold value was changed.
- No scoring or feature mathematics was changed.
- No preprocessing version was changed. The isolated environments still select
  `v0.1.7-beta` and `v0.1.9-beta` exactly as before.
- No external Aramina package dependency, provider URL, or HTTP path was added.
- No dummy, uniform, or fake fallback was introduced.
- No frontend or async/job-lifecycle change was made.

Two behavior changes are limited to failure reporting:

1. `preprocess_aramina` now raises `AraminaPreprocessingError` (a `ValueError`
   subclass) instead of a bare `ValueError`. The message is a fixed safe string
   in all cases; previously two paths leaked a descriptive internal message
   (`"Missing artifact preprocessing pipeline"`,
   `"Unsupported artifact preprocessing release"`). Both are now fixed text.
2. Worker spawn failures and unparseable worker output now map to
   `worker_process` / `worker_output` instead of an unclassified error.

Successful preprocessing is unchanged.

---

## 10. Validation

Run on this branch:

```
python -m compileall -q src tests
pytest -q tests/test_aramina_workflow_runtime.py
pytest -q tests/test_catalog_api_multi_model.py
pytest -q
git diff --check
```

Results are recorded in the implementation report. Full `pytest -q` must pass
before READY.
