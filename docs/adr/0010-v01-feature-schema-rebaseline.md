# ADR-0010: v0.1 Feature Schema Rebaseline

**Status**: Accepted

## Context

The delivered v0.1 model package (`bremen_mri_triage_logreg_v0_1_model_package.joblib`)
defines the runtime feature schema for Bremen v0.1. The model was produced by an
external data scientist (Kubytskyi) using the portable logistic regression format
(plain Python dict/list/float — no sklearn objects).

### Delivered model facts

| Field | Value |
|-------|-------|
| model_version | `bremen_mri_triage_logreg_v0_1` |
| Filename | `bremen_mri_triage_logreg_v0_1_model_package.joblib` |
| SHA-256 | `sha256:8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e` |
| Format | `portable_logreg` |
| Threshold | `0.3640352477169748` |
| threshold_version | `v0.1` |
| OOF AUC | 0.443 |
| Train-all AUC | 0.646 |
| Sensitivity at threshold | 0.966 |
| Specificity at threshold | 0.024 |
| Feature count | 15 concrete columns (listed below) |

### Delivered v0.1 feature schema (exact order, exact casing)

```text
1.  weightedrms1
2.  sigma_l1
3.  sigma_r1
4.  mahalanobis1
5.  weightedrms2
6.  sigma_l2
7.  sigma_r2
8.  mahalanobis2
9.  peak14_intensity
10. mean_peak_value_raw
11. wasserstein_distance_muLR
12. cosine_distance_full_q2
13. wasserstein_distance_full_q2
14. meanrms1
15. meanrms2
```

### Relationship to earlier architecture work

- **ADR-0001 (Bremen feature families)**: The seven feature families named in
  ADR-0001 (`sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`,
  `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`) remain Bremen's
  product identity anchors. The v0.1 model's concrete 15-column schema extends
  (does not replace) these families by adding variants (`sigma_r1`, `sigma_r2`,
  `weightedrms2`, `meanrms1`), additional profile-derived features
  (`peak14_intensity`, `mean_peak_value_raw`), and additional distance metrics
  (`wasserstein_distance_muLR`, `cosine_distance_full_q2`).

- **PR 0038 preprocessing bridge**: Implemented a 7-feature bridge assumption
  using the original uppercase-M `Mahalanobis1/2` naming. This was a planning
  placeholder. The delivered model uses lowercase `mahalanobis1/2`.

- **Schema rebaseline**: Runtime v0.1 follows the delivered model package
  schema. The preprocessing bridge is updated from the 7-feature assumption
  to the 15-column concrete v0.1 schema.

## Decisions

1. **Runtime v0.1 uses the delivered model package schema as the source of
   truth.** The 15-column feature list above is enforced by the preprocessing
   bridge and validated against the model's `feature_columns` during inference.

2. **Previous 7-feature assumption is superseded for v0.1.** The old 7-feature
   `BREMEN_FEATURE_COLUMNS` constant is removed. The new
   `BREMEN_V01_FEATURE_COLUMNS` (15 columns, lowercase `mahalanobis1/2`) is the
   runtime schema.

3. **Feature casing follows the model package.** `mahalanobis1` and
   `mahalanobis2` are lowercase. Earlier ADRs used uppercase `Mahalanobis1/2` —
   those remain correct for product identity but do not define the runtime
   schema.

4. **Model is a runnable research baseline.** The OOF AUC is weak (0.443).
   Deployment goal is end-to-end pipeline proof, not clinical validation.

5. **First deployment goal is end-to-end pipeline proof** — demonstrate that
   H5 → preflight → feature extraction → inference → prediction JSON works
   from a single command, with no clinical validation claim.

6. **Future model versions may have different feature schemas.** The runtime
   shall follow the model package contract (manifest + feature_columns), not a
   pre-declared feature list.

## Open questions

- Role of `sigma_r1`/`sigma_r2` vs `sigma_l1`/`sigma_l2` (both are
  sigma-RMS variants with different normalisation assumptions).
- Clinical meaning and validation of `peak14_intensity` and
  `mean_peak_value_raw` — these may be data-quality dependent.

## Safety

- No clinical validation claim.
- No claim that model replaces MRI, biopsy, radiologist, or clinician.
- Weak OOF AUC is disclosed.
- The triage recommendation output (`MRI_RECOMMENDED` / `MRI_RULE_OUT`) is a
  decision-support label, not a clinical order.
- Passing preflight means structural H5 acceptance only, not clinical
  suitability.
