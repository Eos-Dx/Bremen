# ADR-0014: Bremen Six-Measurement Product Input Contract

**Status**: Proposed  
**Date**: 2026-09-12

**Related spike**: [Architecture Spike: Six-Measurement Bremen Inference and Model-Owned Runtime](../architecture_spike_six_measurement_and_model_owned_inference.md)  
**Related review**: [Architecture Review Reconciliation: Model Boundary and Technical Debt](../architecture_review_model_boundary_and_technical_debt.md)

## Context

The Bremen product input is expected to contain six measurements total: three LEFT and three RIGHT. A five-measurement container is defective input.

The canonical runtime retains all measurements, but the current `BremenProvider.build_features()` selects the first LEFT and first RIGHT profiles before computing features. Therefore the current provider does not use the full normal product input.

Training/preprocessing code in the repository contains a different pattern: aggregate all profiles within each side using a mean profile, then compute bilateral features from LEFT/RIGHT side aggregates.

The deployed model lineage has not yet been proven tightly enough to authorize a production mathematical change solely from this evidence.

## Proposed decision

For the next Bremen inference contract version:

1. A normal Bremen product case MUST contain exactly 6 measurements total.
2. It MUST contain exactly 3 LEFT and exactly 3 RIGHT measurements.
3. Any other measurement count/distribution, including 5 total measurements, MUST fail input/model eligibility validation before inference.
4. All six accepted measurements MUST participate in model input construction; runtime MUST NOT select one measurement merely because it appears first.
5. LEFT and RIGHT measurements MUST remain separate through side-level aggregation and bilateral feature computation.
6. The exact side-aggregation and q-alignment rule MUST be owned by an authoritative model/training contract.
7. Repository evidence currently favors arithmetic mean profiles per side, but this MUST be confirmed against the deployed model lineage and golden parity fixtures before production activation.
8. Input ordering MUST NOT affect features, probability, or decision.
9. Position/measurement-set semantics, if scientifically meaningful, MUST be explicit in the model/input contract rather than inferred from incidental file order.

## Required evidence before acceptance

- exact model checksum/release traced to its training/preprocessing run;
- representative 3 LEFT + 3 RIGHT fixture(s);
- q-grid compatibility/alignment rule;
- all 15 runtime features compared against reference output within an explicit tolerance;
- probability/decision parity;
- permutation-invariance test;
- malformed count/distribution rejection tests.

## Non-goals

This proposed ADR does not:

- implement aggregation;
- choose interpolation behavior;
- retrain a model;
- change the 15-feature schema;
- change public API/report fields;
- authorize 1+1 inference as a normal product path;
- define Aramina measurement semantics;
- define a 12-measurement contract.

## Consequences if accepted

- Measurement-count validation becomes a product contract rather than a best-effort compatibility heuristic.
- The current first-profile selection path must be removed/replaced for normal Bremen inference.
- A model release that cannot demonstrate six-measurement parity cannot be considered scientifically aligned with the stated product input contract.
- Five-measurement containers fail closed rather than degrading silently.
- The ML/model owner must provide the authoritative six-measurement aggregation/preprocessing semantics and golden reference evidence.
