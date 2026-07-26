# PR0096 — Per-side measurement reliability tier

## TASK COMPLETE

## BLOCKERS

None.

## WARNINGS

- The Internal report score fix (`"score": _get_path(external, "prediction_summary", "p_mri_needed")`) is **not merged**. The grep returned no match. This PR is independent but the code is nearby in `report_ui.py`. The plan accounts for this by placing the new field in `prediction_summary` where the score fix would also go, so there is no merge conflict risk.

## FILES READ

- src/bremen/api/workflow_bremen.py (entire file — PreparedWorkflowInput, prepare_input(), execute(), run_inference())
- src/bremen/api/lifecycle_contracts.py (PreparedWorkflowInput dataclass)
- src/bremen/api/decision_support.py (build_decision_support_report(), current optional params, prediction_summary shape)
- src/bremen/api/feature_artifact_prediction.py (call site of build_decision_support_report())
- src/bremen/api/inference_handler.py (legacy call site of build_decision_support_report())
- src/bremen/api/workflow_orchestrator.py (run_workflow_request(), canonical case creation, provider execution)
- src/bremen/api/app.py (handle_submit_prediction(), how result_dict is built from WorkflowResult.payload, then passed to build_decision_support_report())
- src/bremen/report_ui.py (build_external_report_json(), build_internal_report_json(), Python helpers, JS builders, JS renderers)
- docs/design/BREMEN_DESIGN_SPEC_v1.md (design tokens, layout guidance)
- AGENTS.md (Bremen/Aramis separation, safety constraints)
- .project-memory/project_contract.yml (Bremen safety invariants, source-of-truth order)

## COUNT COMPUTATION PLAN

**Location**: `workflow_bremen.py` → `prepare_input()` method, immediately next to the existing `sides` / `positions` / `measurement_count` computation.

**Method**: The canonical case measurements already have `getattr(m, "side", "?")` accessible. The plan uses the same duck-typing pattern already in use:

```python
left_measurement_count = sum(
    1 for m in measurements if getattr(m, "side", None) == "LEFT"
)
right_measurement_count = sum(
    1 for m in measurements if getattr(m, "side", None) == "RIGHT"
)
```

This is placed right after `positions = {getattr(m, "position", "?") for m in measurements}` and before `measurement_count = len(measurements)`.

**Rationale**: The `prepare_input()` method already iterates over measurements to build the `sides` set. Adding per-side tallies here adds zero additional passes over the data. The existing `getattr(m, "side", "?")` pattern is proven safe for duck-typed input.

**Event emission**: Add `left_measurement_count` and `right_measurement_count` to the event emission `details` dict in `prepare_input()`.

## STORAGE PLAN

**Location**: `lifecycle_contracts.py` → `PreparedWorkflowInput` dataclass.

**Fields to add**:

```python
left_measurement_count: int = 0
right_measurement_count: int = 0
```

**Justification**: `PreparedWorkflowInput` is the contract type returned by `prepare_input()`. Its purpose is to carry prepared input metadata. Per-side counts are a natural extension of the existing `measurement_count`, `side_count`, `position_count` fields. Default values (`0`) ensure backward compatibility for any code constructing this dataclass without the new fields.

**Return statement in prepare_input()**: The two new fields are added to the `PreparedWorkflowInput(...)` constructor call at the end of `prepare_input()`.

## PLUMBING PATH

The real call graph from `prepare_input()` to `build_decision_support_report()` has exactly 4 hops. Every hop and file is cited below.

**Hop 1**: `prepare_input()` → `execute()` (same class, same file)
- File: `src/bremen/api/workflow_bremen.py`
- `prepare_input()` returns `PreparedWorkflowInput` to its caller `execute()`.
- `execute()` currently calls `prepare_input()` for tracing only (line ~590: `self.prepare_input(canonical, context)`).
- The `PreparedWorkflowInput` return value is **discarded** today. The plan changes this: store the return value and extract counts after `run_inference()` returns.

**Hop 2**: `execute()` → `WorkflowResult.payload`
- File: `src/bremen/api/workflow_bremen.py`
- After `run_inference()` returns `WorkflowResult`, `execute()` currently accesses `payload` only for event emission.
- **New code**: After `result = self.run_inference(features)`, add:
  ```python
  if result.payload and result.status == "completed":
      pwi = self.prepare_input(canonical, context)  # already computed; lightweight
      result.payload["left_measurement_count"] = pwi.left_measurement_count
      result.payload["right_measurement_count"] = pwi.right_measurement_count
  ```
  This is safe because `prepare_input()` is idempotent — it only reads attributes and emits events. Re-calling it avoids storing state on the provider instance.

**Alternative (simpler)**: Compute counts directly in `execute()` from `canonical.measurements` without calling `prepare_input()` a second time. This is equally safe because `canonical` is the same object. The plan **prefers direct computation** in `execute()` to avoid a redundant call:

  ```python
  left_count = sum(
      1 for m in getattr(canonical, "measurements", [])
      if getattr(m, "side", None) == "LEFT"
  )
  right_count = sum(
      1 for m in getattr(canonical, "measurements", [])
      if getattr(m, "side", None) == "RIGHT"
  )
  result.payload["left_measurement_count"] = left_count
  result.payload["right_measurement_count"] = right_count
  ```

**Hop 3**: `WorkflowResult.payload` → `result_dict` in `app.py`
- File: `src/bremen/api/app.py`, function `handle_submit_prediction()`, around lines 295-317
- `mw_result = run_workflow_request(...)` returns `MultiWorkflowResult`.
- `wf_result = mw_result.workflows.get(workflow_id)` gives the `WorkflowResult`.
- `payload = wf_result.payload or {}` gives the payload dict.
- Today, `result_dict` is built from specific fields (`prediction_id`, `model_version`, etc.) — NOT the full payload.
- **New code**: Add to the `result_dict`:
  ```python
  "left_measurement_count": payload.get("left_measurement_count", 0),
  "right_measurement_count": payload.get("right_measurement_count", 0),
  ```

**Hop 4**: `result_dict` → `build_decision_support_report()`
- File: `src/bremen/api/app.py`, line 317
- Today: `build_decision_support_report(result_dict, input_mode=..., explicit_refs=..., layout_category=...)`
- **New code**: Pass the counts via `result_dict` (which already contains them). Inside `build_decision_support_report()`, extract them from `inference_result`.

**Alternative to Hop 4**: Add explicit keyword parameters `left_measurement_count` and `right_measurement_count` to `build_decision_support_report()`. Both approaches work. The plan prefers **extracting from inference_result** because it keeps the function signature stable for existing call sites (feature_artifact_prediction.py, inference_handler.py) that will NOT provide counts — they will get `None` and the reliability field will simply be absent.

**Other call sites of build_decision_support_report()**:
- `feature_artifact_prediction.py` line 203: Calls with `prediction_dict` which does NOT have measurement counts. The reliability field will be absent — correct behavior because feature artifacts don't carry measurement objects.
- `inference_handler.py` line 119: Legacy path. The `prediction` dict built there also lacks counts. The field will be absent — correct behavior.
- `app.py` line 317: The MAIN path. Gets counts through the plumbing described above.

## DECISION_SUPPORT_REPORT WIRING PLAN

**File**: `src/bremen/api/decision_support.py`

**Function**: `build_decision_support_report()`

**Changes**:

1. Add a private helper function implementing the exact tier logic from bremen-training-pipeline:

```python
def _compute_measurement_reliability(
    left_measurement_count: int,
    right_measurement_count: int,
) -> dict[str, object] | None:
    """Compute measurement reliability tier from per-side counts.

    Ported verbatim from bremen-training-pipeline.
    """
    left = int(left_measurement_count)
    right = int(right_measurement_count)
    if left >= 3 and right >= 3:
        return {
            "tier": "HIGH_TECHNICAL",
            "reason": "At least three accepted measurements per breast.",
            "left_measurement_count": left,
            "right_measurement_count": right,
        }
    if left >= 2 and right >= 2:
        return {
            "tier": "ACCEPTABLE_TECHNICAL",
            "reason": "At least two accepted measurements per breast.",
            "left_measurement_count": left,
            "right_measurement_count": right,
        }
    return {
        "tier": "LOW_TECHNICAL",
        "reason": "Fewer than two accepted measurements on one breast.",
        "left_measurement_count": left,
        "right_measurement_count": right,
    }
```

2. In the prediction_summary section of `build_decision_support_report()`, after the existing fields:

```python
# --- Measurement reliability (PR0096) ---
left_count = inference_result.get("left_measurement_count")
right_count = inference_result.get("right_measurement_count")
if left_count is not None and right_count is not None:
    reliability = _compute_measurement_reliability(left_count, right_count)
    if reliability is not None:
        prediction_summary["measurement_reliability"] = reliability
```

**Safety**: When `left_measurement_count` or `right_measurement_count` is not provided (None), no `measurement_reliability` key is emitted. This preserves backward compatibility for all existing call sites.

**No change to other parameters**: `input_mode`, `explicit_refs`, `layout_category`, `feature_values`, `ref_stats` — all unchanged.

## JSON CONTRACT PLACEMENT

**Preferred placement**: `prediction_summary.measurement_reliability`

Shape:

```json
{
  "tier": "HIGH_TECHNICAL",
  "reason": "At least three accepted measurements per breast.",
  "left_measurement_count": 3,
  "right_measurement_count": 3
}
```

**Justification**: The measurement reliability tier describes a property of the input measurements that affects prediction quality. It belongs in `prediction_summary` because it is part of the prediction's quality context, not model metadata (which describes the model artifact) and not input_summary (which describes the H5 source). This placement is consistent with `qc_status` and `qc_flags` which also live in `prediction_summary` and describe the quality/trustworthiness dimension of the prediction.

**Alternative considered**: `model_metadata` — rejected because reliability is not a model property.
**Alternative considered**: `input_summary` — rejected because reliability is a derived quality signal, not raw input provenance.
**Alternative considered**: Top-level field — rejected because it breaks the existing report structure pattern.

## INTERNAL REPORT WIRING PLAN

**File**: `src/bremen/report_ui.py`

**Python `build_internal_report_json()`**: The internal report already consumes `prediction_summary` from the external report via `_get_path(external, "prediction_summary", ...)`. The `measurement_reliability` field will flow through automatically because `build_internal_report_json()` receives the full external normalized report dict.

**No Python internal change required** for JSON passthrough. The field is already inside `prediction_summary` on the external dict.

**JavaScript `buildInternalReport()`**: The JS builder already calls `buildExternalReport()` first, then reads `external.prediction_summary`. The `measurement_reliability` field will be present on `external.prediction_summary` when available, and absent otherwise. The JS code is tolerant of missing fields via `_safeDict()` pattern.

**No JS builder change required** for JSON passthrough.

**Internal rendering**: Add a `measurement_reliability` section to the Internal report render function (`renderInternalReport()`). This section is added **only after the data path is proven** (see DATA-FIRST RULE). For PR0096, the implementation must:

1. Verify `measurement_reliability` is present in the JSON response (via automated test or manual curl)
2. THEN add the rendering section

The rendering section is a `renderFieldTable` entry under a new `Measurement Reliability` heading, showing:
- Tier
- Reason
- LEFT count
- RIGHT count

This section should appear after "Decision Policy" and before "Boundary Note".

## EXTERNAL REPORT DISPLAY RECOMMENDATION

**Recommendation**: Defer display to a follow-up PR.

**Justification**: 
1. The DATA-FIRST rule requires proving the reliability tier exists in normalized report data before adding visual emphasis.
2. The External report is the production-facing surface. Premature display before contract stability could mislead consumers.
3. The External report's "assessment hero" and "model table" are focused on the decision (score, threshold, QC). Adding measurement reliability display there would compete with the primary decision-support message.
4. JSON-only emission in PR0096 allows consumers (Internal report, Matador, future UI) to adopt the field at their own pace.

**If display were in scope**: The minimal non-dominant placement would be a single row in the "Model & Provenance" field table:
```
Label: "Measurement Reliability"
Value: "HIGH_TECHNICAL — At least three accepted measurements per breast."
```
This mirrors the `qc_status` display approach (small, non-dominant, factual).

**Safety language for display**: If display were added, the label must read "Measurement Reliability" or "Technical Reliability" — never "Clinical Reliability".

## TIER LOGIC VERBATIM CONFIRMATION

The following is ported verbatim from `bremen-training-pipeline`:

```python
left = int(feature_row["n_left"])
right = int(feature_row["n_right"])
if left >= 3 and right >= 3:
    return "HIGH_TECHNICAL", "At least three accepted measurements per breast."
if left >= 2 and right >= 2:
    return "ACCEPTABLE_TECHNICAL", "At least two accepted measurements per breast."
return "LOW_TECHNICAL", "Fewer than two accepted measurements on one breast."
```

The `_compute_measurement_reliability()` function in `decision_support.py` implements this verbatim with no renames, no paraphrase, and no threshold changes.

## SAFETY

- **No raw measurement values**: Only aggregate counts (int) are stored and transmitted.
- **No raw refs**: The H5 canonical case is accessed for count computation only; ref strings are never extracted.
- **No patient identifiers**: Counts are side-aggregated, not patient-level.
- **Counts are allowed**: They are aggregate counts per side, not raw values, not patient identifiers, not full scan refs.
- **Terminology**: "measurement reliability", "technical reliability", "measurement reliability tier" are the only allowed terms.
- **Prohibited terms**: "clinical reliability", "diagnostic reliability" must never appear.
- **No prediction suppression**: LOW_TECHNICAL does NOT block prediction — it is informational only.
- **No new request fields**: POST /predictions schema unchanged.
- **No Aramis coupling**: All changes are Bremen-only.
- **No symmetry_signals changes**: PR0092 and PR0096 are independent.

## VALIDATION PLAN

Implementation validation commands:

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

python -m compileall src tests

python -m pytest -q tests/test_bremen_workflow_bremen.py -v
python -m pytest -q tests/test_bremen_decision_support.py -v 2>&1 || echo "note if file does not exist"
python -m pytest -q tests/test_bremen_report_ui.py -v
python -m pytest -q

grep -n "HIGH_TECHNICAL\|ACCEPTABLE_TECHNICAL\|LOW_TECHNICAL" src/bremen/api/decision_support.py
grep -n "left_measurement_count\|right_measurement_count" src/bremen/api/lifecycle_contracts.py
grep -n "measurement_reliability" src/bremen/report_ui.py
```

Expected results:
- Compilation succeeds.
- Tests pass.
- Exact tier names (`HIGH_TECHNICAL`, `ACCEPTABLE_TECHNICAL`, `LOW_TECHNICAL`) present in `decision_support.py`.
- Reason strings match training-side source verbatim.
- No symmetry_signals or difference_level changes.
- No Aramis coupling.
- No new request schema fields.

## NAMING GUARD — HARD RULE

Do not add top-level fields named:

- `reliability`
- `reliability_reason`

Those names are ambiguous and conflict with a separate concept in external
scientific-report YAML drafts where "reliability" describes model/scientific
validation maturity (e.g. "Paper-reference train-all reproduction; not
independent clinical validation").

PR0096 reliability means **only** per-side measurement technical reliability
based on LEFT/RIGHT accepted measurement counts.

**Required PR0096 placement**:

```
prediction_summary.measurement_reliability = {
  "tier": "HIGH_TECHNICAL" | "ACCEPTABLE_TECHNICAL" | "LOW_TECHNICAL",
  "reason": "...verbatim measurement-count reason string...",
  "left_measurement_count": <int>,
  "right_measurement_count": <int>
}
```

**Use only these wording variants**:
- measurement reliability
- technical measurement reliability
- measurement reliability tier

**Prohibited wording**:
- clinical reliability
- diagnostic reliability
- model reliability
- scientific reliability

The scientific/model maturity concept must continue to use existing Bremen
fields such as `scientific_certification` / `technical_demo_only` / model
metadata, or a future explicitly named field such as
`model_validation_status` if needed. Do not overload
`measurement_reliability` with model-validation meaning.

**Implementation must check**:
- No variable, function, field, or JSON key named `reliability` at the top
  level of any report dict.
- No variable, function, field, or JSON key named `reliability_reason`.
- The only `reliability`-bearing key in the report JSON is
  `prediction_summary.measurement_reliability`.
- All prose references use "measurement reliability" or "technical
  measurement reliability".

## NON-GOALS CONFIRMED

- No symmetry_signals/difference_level work.
- No reference-statistics work.
- No Aramis coupling.
- No new request fields (POST /predictions schema unchanged).
- No fabricated counts (counts come from real measurement.side values).
- No clinical reliability claims.
- No diagnosis claims.
- No UI-heavy redesign (External display deferred; Internal rendering is small and non-dominant).

## STOP CONDITIONS CONFIRMED

No stop conditions triggered:
- Branch matches: `0096-measurement-reliability-tier` ✓
- Per-side counts can reach `build_decision_support_report()` via 4 safe hops ✓
- No broad refactor required ✓
- No fabricated counts ✓
- No tier name/threshold/reason changes ✓
- No symmetry_signals (PR0092) scope touched ✓
- No Aramis code touched ✓
- No POST /predictions request schema changes ✓
- No clinical reliability claims ✓
- JSON placement decided (prediction_summary.measurement_reliability) ✓

## NEXT REQUIRED ACTION

Implementation by coder agent.

Order of edits (in dependency order):
1. `src/bremen/api/lifecycle_contracts.py` — add `left_measurement_count: int = 0`, `right_measurement_count: int = 0` to `PreparedWorkflowInput`
2. `src/bremen/api/workflow_bremen.py` — add per-side count computation in `prepare_input()`, thread counts into `PreparedWorkflowInput` return, add count extraction in `execute()` after `run_inference()` into `WorkflowResult.payload`
3. `src/bremen/api/decision_support.py` — add `_compute_measurement_reliability()` helper, wire into `build_decision_support_report()` prediction_summary section
4. `src/bremen/api/app.py` — add `left_measurement_count` and `right_measurement_count` to `result_dict` from `payload`
5. `src/bremen/report_ui.py` — Python `build_external_report_json()` (passthrough, no change needed), Python `build_internal_report_json()` (add `_get_path` for measurement_reliability), JS `buildExternalReport()` (add measurement_reliability passthrough), JS `buildInternalReport()` (add measurement_reliability passthrough), JS `renderInternalReport()` (add measurement reliability field table section)
6. Tests for the new code paths

Implementation agent: coder
