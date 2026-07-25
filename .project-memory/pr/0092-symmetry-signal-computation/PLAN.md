# PR0092 Plan — Real Symmetry Difference-Level Computation

**Branch**: `0092-symmetry-signal-computation`  
**Status**: Planning  
**Agent role**: plan

---

## 1. Precondition verification

```
HEAD:   43fb7d361209c521d6a85cb7de23be77515ed982
Branch: 0092-symmetry-signal-computation (verified ✓)
Status: clean — only untracked .project-memory/pr/0092-symmetry-signal-computation/
```

Branch matches. All precondition checks passed.

---

## 2. Required reads — evidence summary

### 2.1 `src/bremen/api/preprocessing_bridge.py` (full read)

**`BREMEN_V01_FEATURE_COLUMNS`** (line 35):

```
weightedrms1, sigma_l1, sigma_r1, mahalanobis1,
weightedrms2, sigma_l2, sigma_r2, mahalanobis2,
peak14_intensity, mean_peak_value_raw,
wasserstein_distance_muLR, cosine_distance_full_q2,
wasserstein_distance_full_q2,
meanrms1, meanrms2
```

**`build_feature_table()`** (line 245) iterates all 15 columns, calling each helper.

All helpers are pure numpy functions taking `(target: np.ndarray, contralateral: np.ndarray)` — the mean profiles of target and control sides.

### 2.2 `src/bremen/api/decision_support.py` (full read)

`build_decision_support_report()` produces a v0.1 safe dict with sections:
`report_schema_version`, `intended_use`, `limitations`, `model_metadata`,
`input_summary`, `prediction_summary`, `decision_support`.

No `symmetry_signals` field exists yet. No internal-report builder exists here.

### 2.3 `src/bremen/api/report_bremen.py` (full read)

`BremenReportProvider._build_report()` produces a v0.2 report envelope with
payload sections: `analysis_summary`, `mri_continuation_assessment`,
`score_and_threshold`, `measurement_qc_summary`,
`supporting_technical_evidence`, `model_identity`, `feature_schema_identity`,
`workflow_readiness`, `limitations`, `technical_demo_only_disclaimer`,
`audit_information`.

No `symmetry_signal_detail` field exists yet.

### 2.4 `docs/api_contract.md` (full read)

Decision-support report contract (v0.1) and Bremen report contract (v0.2)
defined. No symmetry signals section. The plan will extend the contract
after implementation.

### 2.5 `.project-memory/project_contract.yml` (full read)

Eleven safety invariants listed. Section 21 / public demo safety boundary
is not a separate section but is woven into the invariants. Key relevant
invariants:

- "Bremen must never be described or marketed as a standalone diagnostic system."
- "Clinical/report wording must remain supplementary decision-support language only."
- "Feature schema must be explicit and must match the model package schema before inference."

### 2.6 `AGENTS.md` (full read)

Product intent for Bremen: MRI-continuation decision support. Pipeline
discipline, release language rules, and MLflow requirements documented.

### 2.7 Report reference artifacts

**Not present in the repository.** Files searched:
- `bremen_external_report.yaml` — not found
- `bremen_internal_report.yaml` — not found
- `Bremen_External_Report_SAMPLE.pdf` — not found
- `Bremen_Internal_Report_SAMPLE.pdf` — not found

The only references to these filenames are in the task prompt itself.

**Warning**: PR0093 must be given the report artifacts before rendering work
starts. PR0092 must not depend on them.

---

## 3. Feature-to-signal mapping — verified from source

### 3.1 Classification by computational logic

Every feature in the 15-column schema is computed from **both** `target_mean`
and `contralateral_mean` profile arrays. There are zero raw per-side features
that require a runtime delta computation. However, the computational *nature*
of each feature differs:

| Feature | Helper | Takes both sides? | Computational nature | Signal family |
|---------|--------|--------------------|---------------------|---------------|
| `weightedrms1` | `_weighted_rms_difference` | Yes | Intensity-weighted RMS of difference | Weighted Asymmetry |
| `sigma_l1` | `_sigma_rms` → `mean(abs(diff))` | Yes | Mean absolute diff (L1) | Difference Magnitude |
| `sigma_r1` | `_sigma_rms_r` → `mean(abs(diff))/RMS` | Yes | Normalised mean abs dev | Difference Magnitude |
| `mahalanobis1` | `_mahalanobis_difference` → `sqrt(mean(diff²/var))` | Yes | Variance-normalised RMS | Statistical Shape Deviation |
| `weightedrms2` | `_weighted_rms_difference_v2` | Yes | sqrt-intensity-weighted RMS | Weighted Asymmetry |
| `sigma_l2` | `_sigma_rms` → `sqrt(mean(diff²))` | Yes | RMS of diff (L2) | Difference Magnitude |
| `sigma_r2` | `_sigma_rms_r` → `RMS` | Yes | RMS of diff (same as sigma_l2) | Difference Magnitude |
| `mahalanobis2` | `_mahalanobis_difference` → `mean(abs(diff)/std)` | Yes | Std-normalised mean abs | Statistical Shape Deviation |
| `peak14_intensity` | `_peak14_intensity` `(abs(t[14])+abs(c[14]))/2` | Yes | Combined bilateral peak intensity | Profile Intensity |
| `mean_peak_value_raw` | `_mean_peak_value_raw` → mean(top-5 of each) | Yes | Combined bilateral top-5 mean | Profile Intensity |
| `wasserstein_distance_muLR` | `_wasserstein_mulr` → `sum(weight*abs(diff))` | Yes | Weighted L1 divergence | Distributional Divergence |
| `cosine_distance_full_q2` | `_cosine_distance` → `1-dot(t_norm,c_norm)` | Yes | Cosine distance | Distributional Divergence |
| `wasserstein_distance_full_q2` | `_profile_wasserstein` → Wasserstein-1 | Yes | Earth-mover distance | Distributional Divergence |
| `meanrms1` | `_mean_rms1` → `mean(abs(diff))` | Yes | Mean absolute diff (same as sigma_l1) | Difference Magnitude |
| `meanrms2` | `_rms_difference` → `sqrt(mean(diff²))` | Yes | RMS diff (same as sigma_l2/meanrms2) | Difference Magnitude |

### 3.2 Deduplication note

`sigma_l1` and `meanrms1` are identical (`mean(abs(diff))`).  
`sigma_l2`, `sigma_r2`, and `meanrms2` are identical (`sqrt(mean(diff²))`).

These computational duplicates exist in the 15-column model package schema.
The signal grouping must not double-count them. The plan maps duplicate
features to the same signal.

### 3.3 Proposed signal grouping

Five signal families emerge from real computational logic (not mockup):

| Signal label (external) | Feature-family names (internal) | Features involved | Rationale from code |
|---|---|---|---|
| `profile_difference_magnitude` | sigma_l1, sigma_l2, sigma_r1, sigma_r2, meanrms1, meanrms2 | 6 features (3 unique) | All measure raw magnitude of the target-control difference |
| `weighted_profile_asymmetry` | weightedrms1, weightedrms2 | 2 features | Both weight the difference by profile intensity |
| `statistical_shape_deviation` | mahalanobis1, mahalanobis2 | 2 features | Both normalise diff by variance/std of the paired profiles |
| `distributional_divergence` | wasserstein_distance_full_q2, wasserstein_distance_muLR, cosine_distance_full_q2 | 3 features | All compare the distributional shape of the two profiles |
| `bilateral_profile_intensity` | peak14_intensity, mean_peak_value_raw | 2 features | Both are combined magnitude across both sides (not differences) |

These groupings are based on reading the actual computation in
`preprocessing_bridge.py` lines 621–940. They are not derived from any
mockup or illustrative example.

### 3.4 Why `bilateral_profile_intensity` is a separate signal

`peak14_intensity` and `mean_peak_value_raw` compute the **average** of
target and control absolute intensities at specific positions. They do not
compute a difference or distance between the two sides. Including them in a
"difference" signal would be misleading. They represent the overall profile
strength, which may be clinically relevant for interpreting whether
difference metrics are reliable (e.g., low intensity → unreliable
differences).

---

## 4. Reference statistics artifact — does not exist

### 4.1 Search results

Searched the entire repository (excluding `.git` and `venv`) for:
- `reference_statistic*` — no matches
- `percentile*` in src/docs — no matches  
- `ref_stats*` — no matches  
- `symmetry_signal*` in src — no matches (only in `difference_level`, `not_available` usage in unrelated server paths)
- `*reference*` files in project root — no relevant matches

**Conclusion**: No reference-statistics artifact exists in the repository.

### 4.2 Required action

The plan defines **two implementation phases**:

**Phase 1 (this PR — PR0092)**: Fail-closed `not_available` implementation.
All five signals return `difference_level: "not_available"` with a safe note.
The loading infrastructure for the artifact is built and tested, but the
artifact itself is not yet required.

**Phase 2 (follow-up PR, after artifact delivery)**: Wire real
percentile-position bucketing once Slava delivers the safe aggregate
reference-statistics artifact.

### 4.3 Expected artifact shape

The artifact must be a small JSON file with this shape:

```json
{
  "artifact_type": "bremen_reference_statistics",
  "artifact_version": "0.1.0",
  "schema_version": "v1",
  "created_at": "<ISO-8601 UTC>",
  "source_training_run": "<mlflow_run_id or model_version>",
  "signals": {
    "profile_difference_magnitude": {
      "feature_family": ["sigma_l1", "sigma_l2", "sigma_r1", "sigma_r2", "meanrms1", "meanrms2"],
      "percentile_bounds": {
        "small": 0.33,
        "moderate": 0.67
      }
    },
    "weighted_profile_asymmetry": {
      "feature_family": ["weightedrms1", "weightedrms2"],
      "percentile_bounds": {
        "small": 0.33,
        "moderate": 0.67
      }
    },
    "statistical_shape_deviation": {
      "feature_family": ["mahalanobis1", "mahalanobis2"],
      "percentile_bounds": {
        "small": 0.33,
        "moderate": 0.67
      }
    },
    "distributional_divergence": {
      "feature_family": ["wasserstein_distance_full_q2", "wasserstein_distance_muLR", "cosine_distance_full_q2"],
      "percentile_bounds": {
        "small": 0.33,
        "moderate": 0.67
      }
    },
    "bilateral_profile_intensity": {
      "feature_family": ["peak14_intensity", "mean_peak_value_raw"],
      "percentile_bounds": {
        "small": 0.33,
        "moderate": 0.67
      }
    }
  }
}
```

Constraints:
- Contains NO per-patient rows, raw training feature values, or raw H5 data.
- `percentile_bounds` defines the upper-bound cutoff for `small` and `moderate`.
  Features at or below `percentile_bounds.small` → `small`.
  Features between `small` and `moderate` → `moderate`.
  Features above `moderate` → `larger`.
- Must include `artifact_type`, `artifact_version`, `source_training_run` for provenance.
- Must be versioned and checksummed.

### 4.4 Artifact location

The reference statistics artifact should live **alongside the model catalog
manifests**, loaded as a separate controlled artifact at startup. It must NOT
be embedded in the model package itself (model package is for inference only).
It must NOT be stored in source control.

Recommended path:
- Stored in the same S3 prefix as model catalog manifests
- Referenced by a new environment variable `BREMEN_REFERENCE_STATISTICS_URI` (or similar)
- Loaded and validated at startup as a controlled artifact
- Checksum-verified before use

Alternatively, if Slava prefers to embed it in a future model package
extension, that is acceptable provided the loading path is explicit and
controlled.

---

## 5. Bucketing method

### 5.1 Method

**Percentile-position bucketing against a safe aggregate training-cohort
reference distribution.**

- For each signal, the aggregate reference distribution provides percentile
  cutoffs (e.g., 33rd and 67th percentile) computed from the training cohort.
- At runtime, the feature values are compared against these cutoffs to
  determine the `difference_level` bucket.
- No raw feature values or raw deltas are exposed in output.

### 5.2 Per-signal aggregation

For signals with multiple features (e.g. `profile_difference_magnitude` has
6 features, 3 unique), the aggregation strategy is:
1. For each feature in the signal, compute a per-feature `difference_level`.
2. Aggregate to signal-level `difference_level` using the **most extreme**
   (highest) level across its features.

This is conservative and safety-preserving: if any one feature indicates
`larger` asymmetry, the signal reports `larger`.

### 5.3 Justification

Percentile-position bucketing is:
- **Deterministic**: same features → same bucket, given the same artifact.
- **Safe**: no raw values, no thresholds, no coefficients exposed.
- **Clinically interpretable**: "this patient's asymmetry is larger than X% of
  the reference cohort" is plain-language compatible.
- **Training-coherent**: uses the same population distribution that the model
  was trained on.

### 5.4 Aramis constraint

Aramis may be used only as a design pattern for percentile-against-reference-population
logic. No Aramis data, Aramis thresholds, Aramis labels, or Aramis clinical
wording may be reused.

---

## 6. Output wiring plan

### 6.1 Data flow

```
build_feature_table() → 15-feature dict
    ↓ (new function in decision_support.py or new symmetry module)
compute_symmetry_signals(
    feature_values: dict[str, float],
    reference_statistics: dict | None,
    feature_to_signal_map: dict
) → dict
    ↓
build_decision_support_report() extended:
    "symmetry_signals": { ... }   ← external-safe
    ↓
BremenReportProvider._build_report() extended:
    "supporting_technical_evidence" → "symmetry_signal_detail": { ... }
```

### 6.2 External report target field

Added to `build_decision_support_report()` output under a new top-level key:

```json
"symmetry_signals": {
    "schema_status": "populated",
    "measurement_summary": "Asymmetry assessment computed from 5 signal families across 15 features.",
    "signals": [
        {
            "label": "Profile difference magnitude",
            "difference_level": "moderate"
        },
        {
            "label": "Weighted profile asymmetry",
            "difference_level": "small"
        },
        {
            "label": "Statistical shape deviation",
            "difference_level": "not_available"
        },
        {
            "label": "Distributional divergence",
            "difference_level": "larger"
        },
        {
            "label": "Bilateral profile intensity",
            "difference_level": "small"
        }
    ],
    "note": "Reference statistics: training cohort v0.1. Symmetry assessment is decision-support only."
}
```

**Allowed `difference_level` values**: `"small"`, `"moderate"`, `"larger"`, `"not_available"`.

**Allowed `schema_status`**: `"populated"`, `"unavailable"`, `"error"`.

External output includes ONLY:
- `schema_status` (str)
- `measurement_summary` (str) — fixed safe text
- `signals` (list) — each with `label` (plain-language, clinician-facing) and `difference_level` (one of the four allowed values)
- `note` (str)

External output must NOT include:
- Raw feature values
- Raw deltas
- Percentile cutoffs
- Reference-statistic values
- Feature-family names
- Feature counts
- Full checksum
- Raw target/control refs
- Patient names
- PHI
- Raw H5 paths
- Raw S3 paths
- Model internals
- Coefficients
- Exception text

### 6.3 Internal report target field

Added to `BremenReportProvider._build_report()` payload under
`"supporting_technical_evidence"`:

```json
"supporting_technical_evidence": {
    "symmetry_signal_detail": {
        "schema_status": "populated",
        "measurement_summary": "Asymmetry assessment computed from 5 signal families across 15 features.",
        "signals": [
            {
                "label": "Profile difference magnitude",
                "feature_family": ["sigma_l1", "sigma_l2", "sigma_r1", "sigma_r2", "meanrms1", "meanrms2"],
                "difference_level": "moderate"
            },
            {
                "label": "Weighted profile asymmetry",
                "feature_family": ["weightedrms1", "weightedrms2"],
                "difference_level": "small"
            }
        ],
        "checksum_prefix": "a1b2c3d4",
        "reference_artifact_version": "0.1.0",
        "note": "Reference statistics: training cohort v0.1."
    }
}
```

Internal output includes additionally:
- `feature_family` (list of feature names per signal)
- `checksum_prefix` (first 8 hex chars of the reference statistics artifact checksum — not the full checksum)
- `reference_artifact_version` (str)

Internal output must still NOT include:
- Raw feature values
- Raw deltas
- Percentile cutoffs
- Full checksum
- Raw target/control refs
- Patient names
- PHI
- Raw H5 paths
- Raw S3 paths
- Model internals
- Coefficients
- Exception text

### 6.4 Internal report builder confirmation

An internal-report builder exists: `BremenReportProvider._build_report()` in
`src/bremen/api/report_bremen.py`. It produces the v0.2 envelope with a
`payload` dict. The `symmetry_signal_detail` field plugs into the existing
`supporting_technical_evidence` section.

No separate internal-report function is needed; the v0.2 report envelope's
payload already supports the required detail level.

### 6.5 No changes to POST /predictions schema

The symmetry signals are added as a field within the existing
`decision_support_report` dict, which is already a field in the
`CompletedResult` and `PredictionStatusResponse`. No new top-level fields
are added to POST /predictions.

---

## 7. `not_available` behavior

### 7.1 When to emit `not_available`

| Condition | Signal-level behavior | `schema_status` | `note` |
|-----------|----------------------|-----------------|--------|
| Reference statistics artifact not configured | All signals → `not_available` | `"unavailable"` | "Reference statistics not configured" |
| Artifact configured but not yet loaded | All signals → `not_available` | `"unavailable"` | "Reference statistics not yet loaded" |
| Artifact loaded but checksum invalid | All signals → `not_available` | `"error"` | "Reference statistics checksum mismatch" |
| Artifact loaded but signal not found in artifact | That signal → `not_available` | `"populated"` | "Reference statistics unavailable for this signal" |
| Feature values present but out of distribution | That signal → `not_available` | `"populated"` | "Signal could not be assessed" |

### 7.2 Safety rules

- Do NOT default to `small` when reference stats are missing.
- Do NOT infer from score.
- Do NOT hide the signal silently — every signal is always present in the
  list with its `difference_level`.
- Do NOT show example data, placeholder values, or fabricated cutoffs.

### 7.3 Allowed labels only

The `difference_level` field in every output path must emit exactly one of:
- `"small"`
- `"moderate"`
- `"larger"`
- `"not_available"`

No floats, no raw values, no custom strings, no null.

---

## 8. Files for future implementation

### 8.1 Allowed files (verified from source)

| File | Purpose |
|------|---------|
| `src/bremen/api/decision_support.py` | Extend `build_decision_support_report()` to add `symmetry_signals` field. Add `compute_symmetry_signals()` or import from a new helper module. |
| `src/bremen/api/report_bremen.py` | Extend `BremenReportProvider._build_report()` to add `symmetry_signal_detail` in `supporting_technical_evidence`. |
| `src/bremen/api/preprocessing_bridge.py` | Only if absolutely necessary for exposing a helper — no semantics changes. The feature-to-signal map and raw feature values are already accessible from the computed feature dict. Likely no changes needed. |
| `src/bremen/api/model_catalog.py` or `model_registry.py` | Only if reference statistics loading is added to startup. Minimal change. |
| `docs/api_contract.md` | Document new `symmetry_signals` and `symmetry_signal_detail` fields. |
| `tests/test_bremen_decision_support.py` | New test class for symmetry signals (file doesn't exist yet — create it). |
| `tests/test_bremen_preprocessing_bridge.py` | New tests if preprocessing bridge exposes helpers for symmetry computation. |
| `.project-memory/pr/0092-symmetry-signal-computation/implementation-report.md` | Implementation report. |

### 8.2 New file: `src/bremen/api/symmetry_signals.py` (recommended)

A new module that contains:
- `FEATURE_TO_SIGNAL_MAP` — the verified feature-to-signal mapping
- `compute_symmetry_signals()` — pure function that takes feature values dict
  and reference statistics, returns safe external and internal dicts
- `_load_reference_statistics()` — controlled loading with checksum verification
- `_percentile_bucket()` — the bucketing logic (percentile-position)
- `_format_external_signals()` — safe external output builder
- `_format_internal_detail()` — safe internal output builder

This keeps concern separation clean: `decision_support.py` imports from
`symmetry_signals.py` rather than containing symmetry logic.

### 8.3 Files that must NOT be modified

All of:
- `report_ui.py`, `control_room_ui.py`, `start_page_ui.py` — no UI files
- Any HTML/CSS/PDF files — no rendering
- `Dockerfile`, `requirements.txt`, `pyproject.toml` — no dependency changes
- `ROADMAP.md` — no roadmap editing
- Any Aramis files — no Aramis work
- Any model artifacts — no inspection
- Any private H5 data — no inspection

---

## 9. Test plan

### 9.1 Test file

New file: `tests/test_bremen_symmetry_signals.py`
(Or `tests/test_bremen_decision_support.py` if kept co-located. Prefer
separate file for concern separation.)

### 9.2 Required tests

| # | Test | Priority |
|---|------|----------|
| 1 | `test_symmetry_signals_present_when_ref_stats_valid` — When reference statistics are valid and loaded, `symmetry_signals` exists in report with `schema_status: "populated"` and populated `signals` list. | Required |
| 2 | `test_not_available_when_ref_stats_missing` — When reference statistics is `None`, all signals emit `difference_level: "not_available"`, `schema_status: "unavailable"`. | Required |
| 3 | `test_not_available_when_signal_missing_from_artifact` — When one signal is absent from the loaded artifact, that signal emits `"not_available"` with a safe note. | Required |
| 4 | `test_no_raw_feature_values_in_external` — External `symmetry_signals` dict contains no raw feature values, raw deltas, percentile cutoffs, or reference-statistic values. | Required |
| 5 | `test_no_raw_feature_values_in_internal` — Internal `symmetry_signal_detail` contains no raw feature values, raw deltas, percentile cutoffs, full checksums, or raw target/control refs. | Required |
| 6 | `test_feature_to_signal_mapping_matches_code` — The mapping in `FEATURE_TO_SIGNAL_MAP` matches the actual 15 columns from `BREMEN_V01_FEATURE_COLUMNS`. Every feature is mapped to exactly one signal. | Required |
| 7 | `test_no_mockup_values_used` — No hardcoded example values from sample reports appear in the output (test greps for known sample values). | Required |
| 8 | `test_backward_compatible_decision_support` — Existing `decision_support_report` fields (`report_schema_version`, `intended_use`, `limitations`, `model_metadata`, `input_summary`, `prediction_summary`, `decision_support`) remain unchanged. | Required |
| 9 | `test_decision_vocabulary_unchanged` — Decision vocabulary (CONTINUE_MRI, MRI_REVIEW_DEFER, recommendation labels) is not modified. | Required |
| 10 | `test_predictions_schema_unchanged` — POST /predictions request/response schema is unchanged. Existing tests pass. | Required |
| 11 | `test_no_rendering_routes` — No new rendering routes or PDF behavior introduced. | Required |
| 12 | `test_difference_level_only_allowed_values` — Every `difference_level` value in output is in `{"small", "moderate", "larger", "not_available"}`. | Required |
| 13 | `test_signal_labels_stable` — Signal labels in external output are stable strings (not generated from feature names). | Recommended |
| 14 | `test_checksum_prefix_not_full` — Internal output `checksum_prefix` is at most 8 characters (first 8 hex chars), never the full checksum. | Required |

### 9.3 Existing tests must continue passing

```
python -m pytest -q tests/test_bremen_decision_support_output.py -v
python -m pytest -q tests/test_bremen_preprocessing_bridge.py -v
```

---

## 10. Validation plan

### 10.1 Pre-validation checks

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only
```

### 10.2 Compile and lint

```bash
python -m compileall src tests
```

### 10.3 Test execution

```bash
python -m pytest -q tests/test_bremen_symmetry_signals.py -v
python -m pytest -q tests/test_bremen_decision_support_output.py -v
python -m pytest -q tests/test_bremen_preprocessing_bridge.py -v
# If catalog/reference artifact loading changed:
python -m pytest -q tests/test_catalog_api_multi_model.py -v
# Full suite:
python -m pytest -q
```

### 10.4 Safety greps

```bash
# Check all output paths use only allowed difference_level values
grep -rn "difference_level" src/bremen/ tests/

# Check no float/raw values are emitted in difference_level
# (Manual review of every output path)

# Check reference statistics / percentile cutoff references
grep -rn "reference_statistics\|percentile_cutoff\|cutoff" src/bremen/ tests/

# Verify no sample/mockup artifact dependency
grep -rn "Bremen_External_Report_SAMPLE\|Bremen_Internal_Report_SAMPLE\|hardcoded\|example" src/bremen/ tests/ || true

# Check no unsafe public exposure
grep -rn "raw_feature\|feature_value\|model_checksum\|manifest_key\|s3://\|arn:aws" src/bremen/ tests/ || true
```

### 10.5 Manual confirmations

1. Every `difference_level` output path emits only: `small`, `moderate`, `larger`, `not_available`.
2. Cutoffs are loaded from a controlled artifact, never hardcoded.
3. No runtime dependency on sample/mockup artifacts.
4. No raw feature values or deltas in external output.
5. No raw feature values, deltas, or cutoffs in internal output.
6. POST /predictions schema is unchanged.
7. Decision vocabulary is unchanged.
8. No rendering or PDF changes.

---

## 11. Non-goals — explicitly excluded

- No rendering (HTML/CSS/PDF).
- No PDF export.
- No report page UI.
- No React.
- No frontend framework.
- No new public route.
- No new POST /predictions schema fields.
- No fabricated thresholds.
- No raw feature values in output.
- No percentile cutoffs in output.
- No Aramis data reuse.
- No mockup/example values.
- No change to inference semantics.
- No change to preprocessing semantics.
- No change to model catalog discovery.
- No change to thresholds or decision vocabulary.
- No weakening of safety language.
- No changes to dependencies (requirements.txt, pyproject.toml, Dockerfile).
- No changes to CI/CD.
- No changes to model artifacts.

---

## 12. Implementation sequence (for coder)

### Step 1: Create `src/bremen/api/symmetry_signals.py`

- Define `FEATURE_TO_SIGNAL_MAP` with the verified mapping from §3.3.
- Define `SIGNAL_LABELS` mapping signal keys to plain-language labels.
- Define `ALLOWED_DIFFERENCE_LEVELS = {"small", "moderate", "larger", "not_available"}`.
- Implement `_percentile_bucket(value, bounds)` — pure function.
  - Returns `"not_available"` if bounds is `None` or value is non-finite.
  - Returns `"small"` if value ≤ `bounds.small`.
  - Returns `"moderate"` if value ≤ `bounds.moderate`.
  - Returns `"larger"` if value > `bounds.moderate`.
- Implement `_aggregate_signal_level(per_feature_levels)` — uses most extreme.
- Implement `compute_symmetry_signals(feature_values, ref_stats)`.
  - If `ref_stats` is `None` → all `not_available`, `schema_status: "unavailable"`.
  - If `ref_stats` is invalid → all `not_available`, `schema_status: "error"`.
  - Otherwise → compute per-signal, per-feature bucketing, aggregate.
- Implement `_format_external(symmetry_result)` — safe external dict.
- Implement `_format_internal(symmetry_result, ref_checksum_prefix)` — safe internal dict.
- Implement `_validate_reference_statistics(artifact)` — schema validation.

### Step 2: Extend `src/bremen/api/decision_support.py`

- Add `from .symmetry_signals import compute_symmetry_signals, _format_external`.
- In `build_decision_support_report()`, after existing sections, add:
  ```python
  symmetry_result = compute_symmetry_signals(feature_values, ref_stats)
  result["symmetry_signals"] = _format_external(symmetry_result)
  ```
- `feature_values` must be passed in — this is the first time the decision
  support report needs access to feature values. **They are not stored in
  the report output**, only used for bucketing.
- Add `feature_values: dict[str, float] | None = None` parameter to
  `build_decision_support_report()`.
- Add `ref_stats: dict | None = None` parameter.
- Keep backward compatibility: when both are `None`, `symmetry_signals` is
  added with `schema_status: "unavailable"`.

### Step 3: Extend `src/bremen/api/report_bremen.py`

- In `_build_report()`, check if `workflow_result` contains symmetry signal detail.
- Add to `supporting_technical_evidence` dict:
  ```python
  if "symmetry_signal_detail" in workflow_result:
      payload["supporting_technical_evidence"]["symmetry_signal_detail"] = (
          workflow_result["symmetry_signal_detail"]
      )
  ```

### Step 4: Update `src/bremen/api/feature_artifact_prediction.py`

- In `run_feature_artifact_prediction()`, compute symmetry signals from the
  validated artifact's feature values.
- Add `symmetry_signals` to `decision_support` dict.
- Add `symmetry_signal_detail` to result if internal detail is needed.

### Step 5: Update calling paths

- `inference_handler.py` and `app.py` call `build_decision_support_report()`.
  Pass `feature_values` from the preprocessing result.
- `inference_handler.py` already runs preprocessing bridge, so the feature
  dict is available after preprocessing.

### Step 6: Reference statistics loading (startup)

- Add a startup loading function in `symmetry_signals.py` or `model_catalog.py`.
- Environment variable: `BREMEN_REFERENCE_STATISTICS_URI` (S3 URI).
- Validate artifact shape with `_validate_reference_statistics()`.
- Store in a module-level variable or singleton.
- Until the artifact exists, the loader returns `None` → all `not_available`.

### Step 7: Tests

- Create `tests/test_bremen_symmetry_signals.py` with all required tests (§9).
- No changes to existing test files unless a helper signature changes.

### Step 8: Update docs

- `docs/api_contract.md`: Add `symmetry_signals` and `symmetry_signal_detail` sections.

---

## 13. Blockers

### Blocker 1: No reference-statistics artifact exists

**Status**: Confirmed absent.  
**Plan**: Implement fail-closed `not_available` path in PR0092. Obtain the
real aggregate reference-statistics artifact from Slava as a precondition
for Phase 2 (follow-up PR).

### Blocker 2: Report reference artifacts not in repository

**Status**: Confirmed absent.  
**Impact**: No impact on PR0092. PR0093 must be given the report artifacts
before rendering work starts. PR0092 produces only backend data.

---

## 14. Warnings

### Warning 1: BREMEN_V01_FEATURE_COLUMNS contains duplicate computations

`sigma_l1` == `meanrms1`, and `sigma_l2` == `sigma_r2` == `meanrms2`. The
feature-to-signal mapping maps them to the same signal but must handle the
duplication correctly — either by de-duplicating or by aggregating
conservatively (most extreme level wins, duplicates produce the same level).

### Warning 2: `build_decision_support_report()` currently has no access to feature values

The function takes `inference_result: dict` which contains no feature values.
Adding `feature_values` parameter is a signature extension. This must be
backward compatible — existing callers pass `None` and get
`schema_status: "unavailable"`.

### Warning 3: `feature_artifact_prediction.py` needs symmetry signal wiring

The feature artifact prediction flow (`run_feature_artifact_prediction()`)
already has access to feature values. It must also compute symmetry signals
for consistency. This is covered in Step 4.

### Warning 4: The five signal categories from the mockup were illustrative

The signal grouping in this plan (§3.3) is derived from real source code
analysis, not from any mockup YAML. PR0093 must use the real signal labels
defined here, not the mockup labels.

---

## 15. Summary of decisions

| Decision | Value | Justification |
|----------|-------|---------------|
| Feature-to-signal map origin | Real code analysis of `preprocessing_bridge.py` | All 15 features verified against actual computation logic |
| Signal count | 5 | Natural grouping by computational family; duplicates collapsed |
| Reference stats loading | Startup, separate from model package | Controlled artifact boundary, not inference |
| Bucketing method | Percentile-position against training-cohort reference | Safe, deterministic, training-coherent |
| Artifact location | S3 alongside model catalog manifests | Controlled, checksummed, versioned |
| Phase 1 behavior | All `not_available` | Fail-closed until artifact exists |
| External output location | `symmetry_signals` in `decision_support_report` | Backward compatible, additive |
| Internal output location | `supporting_technical_evidence.symmetry_signal_detail` in v0.2 report envelope | Existing report provider |
| New module needed | `src/bremen/api/symmetry_signals.py` | Clean concern separation |
| No UI changes | Confirmed | PR0093 will handle rendering |

---

## 16. Next required action

Implementation agent: **coder**

TASK COMPLETE
BLOCKERS
1. No reference-statistics artifact exists in repository. PR0092 implements fail-closed `not_available` path. Phase 2 (real bucketing) requires Slava to deliver the aggregate reference-statistics JSON artifact.

WARNINGS
1. `BREMEN_V01_FEATURE_COLUMNS` contains computational duplicates (sigma_l1==meanrms1, sigma_l2==sigma_r2==meanrms2). Feature-to-signal map must handle deduplication.
2. `build_decision_support_report()` does not currently accept feature values. Signature must be extended with backward-compatible `None` defaults.
3. `feature_artifact_prediction.py` must also compute symmetry signals for consistency.
4. Report reference artifacts (bremen_external_report.yaml, etc.) are not in the repository. PR0093 must be given these before rendering work.

FILES CHANGED
- `.project-memory/pr/0092-symmetry-signal-computation/PLAN.md` (this file — planning only)

REFERENCE STATISTICS SOURCE
- Does not exist in repository.
- Phase 1 (PR0092): fail-closed `not_available` for all signals.
- Phase 2 (follow-up PR): requires Slava to deliver safe aggregate reference-statistics JSON artifact.
- Expected location: S3 alongside model catalog manifests, referenced by `BREMEN_REFERENCE_STATISTICS_URI`.

VERIFIED FEATURE-TO-SIGNAL MAPPING
- Source file: `src/bremen/api/preprocessing_bridge.py` lines 245–330 (build_feature_table) and lines 621–940 (all 15 helpers).
- All 15 features are computed from both target_mean and contralateral_mean — zero raw per-side features.
- Five natural signal families identified from computational logic (see §3.3).
- Duplicate computations (sigma_l1==meanrms1, sigma_l2==sigma_r2==meanrms2) confirmed and handled.

BUCKETING METHOD
- Percentile-position bucketing against a safe aggregate training-cohort reference distribution.
- Cutoffs come from the reference-statistics artifact (not invented).
- Per-signal aggregation: most extreme (highest) level across features.
- Decision vocabulary unchanged. No Aramis data reused.

OUTPUT WIRING PLAN
- External: `symmetry_signals` in `decision_support_report` (extends `build_decision_support_report()`).
- Internal: `supporting_technical_evidence.symmetry_signal_detail` in `BremenReportProvider._build_report()` payload.
- POST /predictions schema unchanged.
- No new public routes.

NOT_AVAILABLE BEHAVIOR
- Exhaustive conditions defined (§7.1).
- All signals always present in output list.
- `not_available` does not default to `small`, does not infer from score, does not hide silently.
- Four allowed values only: `small`, `moderate`, `larger`, `not_available`.

SAFETY CONFIRMATION
- No raw feature values, raw deltas, percentile cutoffs, full checksums, PHI, model internals, or S3 paths in any output.
- Decision vocabulary unchanged.
- Inference/preprocessing semantics unchanged.
- POST /predictions schema unchanged.
- No rendering, PDF, or frontend changes.

TEST PLAN
- 14 required tests defined (§9.2).
- New test file: `tests/test_bremen_symmetry_signals.py`.
- Existing tests must continue passing.

VALIDATION PLAN
- Pre-validation: `git rev-parse`, `git branch`, `git status`, `git diff`.
- `python -m compileall src tests`.
- Targeted test execution + full `python -m pytest -q`.
- Safety greps for `difference_level`, `reference_statistics`, sample artifacts, raw exposure.
- Manual confirmation of every output path.

NON-GOALS CONFIRMED
No rendering, PDF export, report UI, React, frontend, new routes, schema changes, fabricated thresholds, raw values, cutoffs, Aramis data, mockup values, inference/preprocessing/catalog changes, dependency changes, CI/CD changes, or model artifact changes.

STOP CONDITIONS CONFIRMED
- Branch matches 0092-symmetry-signal-computation ✓
- BREMEN_V01_FEATURE_COLUMNS found ✓
- decision_support report builder found ✓
- Feature-to-signal mapping verified from source ✓
- No fabricated thresholds — fail-closed not_available path defined ✓
- No raw feature values/deltas/cutoffs exposed ✓
- No rendering/PDF work required ✓
- No private H5/model artifact inspection required ✓
- No Aramis work required ✓
- No inference/preprocessing semantics changes ✓
- No /demo safety weakening ✓

NEXT REQUIRED ACTION
Implementation agent: coder — proceed with Steps 1–8 as defined in §12.
