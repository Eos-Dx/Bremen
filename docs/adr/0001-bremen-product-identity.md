# ADR-0001: Bremen Product Identity

**Status**: Accepted

## Identity statement

Bremen is the active product identity for this repository.

"Bremen Assembly plan v1" is the authoritative product identity reference (not the Aramis-inherited text currently in `README.md`, `docs/roadmap.md`, or `docs/machine_learning_concept.md`).

## Clinical question

The exact clinical question, quoted verbatim from `docs/product_development_rules.md`:

> "Should patient continue to MRI?"

## Classification task

- Task: healthy vs. disease (NORMAL vs. BENIGN+CANCER).
- Explicitly stated as distinct from a malignant-vs-benign task.

## Contrast with Aramis

- Explicit statement: This is NOT Aramis's malignant-vs-benign classification (BI-RADS 3/4 → biopsy decision).

## Bremen feature-family anchors

The seven Bremen feature-family anchors, named exactly:

1. `sigma_l1`
2. `sigma_l2`
3. `Mahalanobis1`
4. `Mahalanobis2`
5. `wasserstein_distance_full_q2`
6. `meanrms2`
7. `weightedrms1`

## Contrast with Aramis feature families

Explicit contrast with Aramis's feature families, presented as a paired table tied to the product identity statement:

| Bremen family | Aramis family |
|---|---|
| `sigma_l1`, `sigma_l2` | complete azimuthal integration (components approach) |
| `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1` | cosine asymmetry distance (symmetry approach) |

These families implement Bremen's own healthy-vs-disease symmetry/distance approach and are not interchangeable with Aramis's azimuthal-integration/cosine-asymmetry approach.

## Product description

- Bremen is an XRD-based ML decision-support workflow for patients referred to MRI after suspicious mammography findings (dense breast / low-efficacy mammography).
- Bremen is not a diagnostic replacement.
- Bremen must not claim clinical validation.
- Bremen must not replace MRI, biopsy, radiologists, clinicians, or clinical judgment.

## Architecture constraints

- Runtime Bremen service must not train models.
- Matador is the system of record for measurements and prediction results.
- Platform APIs must not depend on local machine paths.
