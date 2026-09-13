# Architecture Spike: Six-Measurement Bremen Inference and Model-Owned Runtime

**Status**: Discussion / proposed direction  
**Date**: 2026-09-12  
**Runtime changes authorized by this document**: None  
**Related ADRs**: ADR-0014 (six-measurement input contract), ADR-0015 (model-owned inference boundary)  
**Related review**: `architecture_review_model_boundary_and_technical_debt.md`

## 1. Why this spike exists

A concrete Bremen inference defect and a broader architecture review point to the same ownership problem.

1. Bremen product containers are expected to contain exactly six breast measurements: three LEFT and three RIGHT. A five-measurement container is defective input. The current `BremenProvider.build_features()` does not consume all six measurements; it selects the first LEFT and first RIGHT profile and computes the 15-feature vector from that pair.
2. Model-specific preprocessing and feature mathematics have gradually moved into Bremen Platform runtime code. This makes the platform responsible for scientific/model behavior that should normally be versioned and released with the model.
3. An architecture review independently reached the same higher-level conclusion: the main leverage is not a greenfield framework rewrite, but a firm model/platform boundary in which model-owned scientific inference logic ships as tested, versioned code with the model release.

This spike records the evidence, the immediate six-measurement strategy, and a proposed migration toward inference-complete model releases (MLflow PyFunc or an equivalent packaging boundary) without rewriting Bremen Platform from scratch.

This is an architecture spike, not an implementation authorization. It must not be read as approval to change aggregation mathematics, retrain a model, or change the public API without the corresponding implementation/review work.

## 2. Reconciliation with the architecture review

The architecture review is directionally aligned with this spike, especially on three points:

- Bremen Platform contains scientific feature-engineering logic that should be model-owned.
- MLflow/BentoML can improve packaging, registry, signatures, and dependency capture, but a framework alone does not fix scientific logic living on the wrong side of the boundary.
- A full rewrite is not justified by the identified defects; the preferred direction is an incremental boundary correction, with registry/framework work pursued separately when useful.

Two review statements require clarification before they are treated as current project facts.

### 2.1 Bremen measurement wording

For this project record, the product-owner clarification is authoritative: the normal Bremen container contains **six total measurements: 3 LEFT + 3 RIGHT**. Five total measurements are defective. Any earlier wording that can be read as "3 fixed + 3 targeted per breast" must not be used to infer 12 measurements without a separate product decision.

### 2.2 Aramina symmetry finding is snapshot-sensitive

The architecture review records an earlier observation that an Aramina symmetry function accepted contralateral measurements but did not use them numerically. That observation must not be carried forward as an active bug without revision provenance.

In the current repository snapshot reviewed for this spike, `src/bremen/api/aramina_symmetry.py::symmetry_features()` builds both `mu_target` and `mu_contralateral` and uses both sides in Wasserstein, weighted RMS, and peak-delta calculations. Therefore:

- the earlier Aramina finding is retained as historical/snapshot-specific evidence of boundary risk;
- it is **not** listed here as a confirmed defect in the current snapshot;
- if the older implementation matters, identify the exact commit/branch before opening a fix.

The Bremen first-measurement issue remains independently confirmed in the current snapshot.

## 3. Product clarification: the valid Bremen input is 3 + 3

The product-owner clarification for Bremen is:

- a valid product container contains **exactly 6 measurements**;
- exactly **3 measurements belong to LEFT**;
- exactly **3 measurements belong to RIGHT**;
- a container with 5 measurements is defective and must not be treated as a normal inference case;
- the purpose of repeated measurements is to contribute repeated information, not to let runtime choose one profile by incidental container ordering.

The canonical runtime representation already preserves all measurements in `CanonicalXRDCase.measurements`; therefore the data are available to the workflow. The loss happens later in the Bremen provider.

## 4. Confirmed current Bremen behavior

`src/bremen/api/workflow_bremen.py` currently reduces a side to one profile using list position:

```python
left_ms = [m for m in measurements if getattr(m, "side", "") == "LEFT"]
right_ms = [m for m in measurements if getattr(m, "side", "") == "RIGHT"]

target = left_ms[0].intensity
control = right_ms[0].intensity
```

The feature engine then computes the Bremen feature vector from those two one-dimensional arrays.

Consequences for a valid six-measurement product container:

```text
LEFT  = L1, L2, L3
RIGHT = R1, R2, R3

current runtime input to feature engine = one LEFT profile + one RIGHT profile
unused by that calculation             = four remaining profiles
```

The choice is deterministic when H5/canonical ordering is deterministic, but it is **not selected by a scientific/model rule**. Reordering equivalent measurements can therefore change which physical measurement is used.

The existing compatibility check is not a sufficient product contract because it detects only a subset of multi-position cases based on position-token shape. The product rule is measurement-count based: 3 LEFT + 3 RIGHT is normal input.

## 5. Evidence for side-level aggregation already present in the repository

There are two important reference paths in the repository.

### 5.1 Training pipeline

`src/bremen/training/pipeline.py::_sk_target_contralateral_symmetry_features()` extracts all target and control profiles for a patient and then computes:

```python
t_mean = np.mean(np.array(t_profiles), axis=0)
c_mean = np.mean(np.array(c_profiles), axis=0)
```

The bilateral feature families are calculated from `t_mean` versus `c_mean`.

### 5.2 Preprocessing bridge

`src/bremen/api/preprocessing_bridge.py` also collects all target and contralateral profiles and computes:

```python
t_mean = np.mean(np.array(target_profiles), axis=0)
c_mean = np.mean(np.array(contralateral_profiles), axis=0)
```

It then computes the 15-feature Bremen dictionary from the two side means.

This is strong evidence that **side-level mean profiles** were an intended Bremen computation pattern.

It is not, by itself, sufficient proof that the currently deployed model artifact was trained from exactly this 15-feature path and exactly the same six-measurement protocol. Before changing production inference, model lineage must be demonstrated with a golden-reference comparison.

## 6. What must happen to use all six measurements now

The lowest-risk route is to keep the deployed model input dimensionality unchanged (15 features) and make all six measurements contribute before those features are computed.

Proposed processing shape:

```text
6 canonical measurements
        |
        +--> validate exactly 3 LEFT
        |
        +--> validate exactly 3 RIGHT
        |
        +--> validate profile/q-grid compatibility
        |
        +--> LEFT side aggregation  --> one LEFT representative profile
        |
        +--> RIGHT side aggregation --> one RIGHT representative profile
        |
        +--> existing Bremen 15-feature computation
        |
        +--> existing model artifact, only if lineage/parity is proven
```

### 6.1 Do not average all six together

LEFT and RIGHT must remain separate because Bremen features are bilateral target/control comparisons. Any aggregation is performed **within a side**, never across both sides.

### 6.2 Candidate rule supported by repository evidence

The existing training and preprocessing reference code supports:

```text
LEFT representative profile  = arithmetic mean of the three LEFT profiles
RIGHT representative profile = arithmetic mean of the three RIGHT profiles
```

This is the preferred candidate only if deployed-model lineage/parity confirms that the artifact expects this computation.

### 6.3 q-axis/profile compatibility is a required gate

`CanonicalXRDMeasurement` preserves a separate `q` axis for every measurement. Taking an element-wise mean is only valid if the three profiles on a side are represented on a compatible grid.

Before production implementation, verify on real six-measurement containers:

- all six arrays have the expected lengths;
- q axes are identical, or the authoritative preprocessing pipeline defines an alignment/interpolation rule;
- no runtime-only interpolation is invented merely to make arrays fit;
- all six measurements pass existing finite/structural QC.

If q grids differ and no authoritative alignment rule exists, inference must stop rather than silently interpolate.

## 7. Six-measurement implementation gates

No production change should be made until these gates are satisfied.

### Gate M6-1 — input contract proof

For the Bremen product path, confirm with representative production containers that the expected normal shape is:

```text
measurement_count = 6
left_measurement_count = 3
right_measurement_count = 3
```

Any other count is invalid for this contract version.

### Gate M6-2 — model lineage proof

Identify the exact training/release path that produced the deployed model package. Establish whether its input features were produced from per-side means of all three measurements.

Evidence may be:

- training run artifact/config;
- versioned preprocessing artifact;
- MLflow run provenance;
- golden patient feature table;
- reproducible training commit + config + model checksum.

### Gate M6-3 — numerical parity fixture

For one or more approved six-measurement fixtures:

1. compute reference features through the authoritative training/preprocessing path;
2. compute runtime candidate features;
3. compare all 15 features within an explicitly chosen tolerance;
4. compare probability and final decision;
5. require parity before release.

### Gate M6-4 — order invariance

Permuting L1/L2/L3 or R1/R2/R3 in the input ordering must not change side aggregation, features, probability, or decision.

### Gate M6-5 — malformed-count rejection

At minimum, regression coverage must prove rejection of:

- 2 LEFT + 3 RIGHT;
- 3 LEFT + 2 RIGHT;
- 2 LEFT + 4 RIGHT;
- 4 LEFT + 2 RIGHT;
- 6 measurements on only one side;
- 5 measurements total;
- 7+ measurements unless a future contract version explicitly supports them.

## 8. What if lineage shows the model was not trained on side means?

Then the current artifact is not suitable for honest six-measurement inference merely by changing runtime aggregation.

The correct action would be to create a new model release whose training pipeline consumes the six-measurement contract explicitly. Options such as mean, median, weighted aggregation, position-specific features, or a larger feature vector become **model-design choices owned by the ML team**.

Changing from 15 existing features to position-specific or 45+ features would require a new trained artifact and model version; the current estimator cannot consume a different feature schema without retraining.

## 9. The deeper architecture issue

The six-measurement defect is a symptom of a broader ownership problem.

Today Bremen Platform contains model-specific knowledge such as:

- profile selection;
- side aggregation decisions;
- Bremen 15-feature mathematics;
- imputation/scaling details;
- logistic-regression execution details;
- thresholds/decision projection;
- workflow-specific preprocessing/runtime integration.

As a result, a backend/platform change can alter the effective scientific model even when the model artifact itself has not changed. That is a training-serving skew risk.

## 10. Existing project history already points to a better boundary

The repository already contains prior work toward the correct separation:

- ADR-0007 separates application image lifecycle from controlled model-package lifecycle.
- ADR-0008 separates offline training from runtime.
- `docs/preprocessing_source_reconciliation.md` identifies duplicate feature computation as an integration risk.
- the feature-artifact path establishes a model-only runtime option using precomputed features.
- PR0075 created a workflow-provider abstraction but also duplicated the Bremen feature engine inside `workflow_bremen.py`.
- PR0075's own plan explicitly states that P1/P2/P3 handling must come from an authoritative training policy and forbids arbitrary selection/averaging without evidence.

Therefore the proposed migration is not a rejection of the existing project. It is a continuation of architectural intentions that were only partially completed.

## 11. Proposed target: inference-complete model releases

Bremen Platform should orchestrate a model but should not reproduce its scientific feature engineering.

Target conceptual boundary:

```text
Bremen Platform
  - authentication
  - source/container registration
  - job lifecycle
  - model selection/registry
  - async/retry/idempotency
  - audit/events
  - storage
  - public report envelope
  - safe error/redaction policy
                |
                v
        Model Runtime Contract
                |
                v
Model-owned inference release
  - model-specific input validation
  - measurement aggregation
  - preprocessing
  - feature construction
  - estimator
  - model-specific postprocessing
  - dependencies
  - golden parity tests
```

The model team owns the behavior from a canonical/model input through model output. The platform owns the lifecycle around that execution.

## 12. What a framework helps with — and what it does not

A framework such as MLflow or BentoML can help with:

- model versioning/registry;
- model signatures and input/output schema declaration;
- dependency/environment capture;
- standard packaging/loading conventions;
- model release provenance.

It does **not** decide scientifically correct aggregation, symmetry, preprocessing, or feature formulas. Packaging `left_ms[0]` inside MLflow would merely version the same wrong behavior more cleanly.

Therefore the primary decision is the **boundary rule**, not the framework brand.

## 13. Options from the architecture review

### Option A — full rewrite onto MLflow/BentoML-style infrastructure

What it gains:
- a more standard serving/catalog foundation;
- easier familiarity for future ML/platform engineers.

What it costs:
- rebuilds product-specific auth, jobs, Control Room/UI, reports, safety/redaction, deployment integration, and a large existing test surface;
- still requires the same scientific-domain corrections;
- creates substantial migration risk without directly addressing the root cause.

**Recommendation**: not justified by the defects found.

### Option B — targeted registry/versioning replacement

Replace or augment manual S3 model discovery/manifest handling with MLflow Model Registry or an equivalent registry, while preserving the platform and WorkflowProvider seam.

What it gains:
- standardized signatures/versioning;
- better dependency/provenance capture;
- less custom registry/catalog code.

What it does not fix:
- scientific logic on the platform side of the boundary.

**Recommendation**: useful, but orthogonal. Can run in parallel after/with the boundary work.

### Option C — adopt and enforce the model-owned inference boundary

Every model release becomes a self-contained callable from declared model input to structured model output, with feature engineering/domain logic owned and tested by the originating ML/science team.

Existing Bremen Platform APIs, jobs, reports, auth, storage, and WorkflowProvider orchestration remain.

**Recommendation**: preferred architecture transition because it directly addresses the root cause without a rewrite.

### Option D — separate model-serving services later

BentoML, KServe, or another remote-serving layer may become appropriate when independent scaling, strong dependency/resource isolation, or separate deployment ownership warrants it.

**Recommendation**: defer until there is a concrete operational requirement.

Options B and C are compatible and may proceed on independent timelines.

## 14. Ownership after the transition

| Concern | Bremen Platform team | ML/model team |
|---|---:|---:|
| Authentication/API | Owns | No |
| Container/source lifecycle | Owns | Defines required model input metadata |
| Job lifecycle/idempotency | Owns | No |
| Audit/events/redaction | Owns | Supplies safe model diagnostics contract |
| Public report envelope | Owns | Supplies model output fields |
| Measurement count/model eligibility | Enforces declared contract | Owns declaration |
| 3+3 aggregation | Must not invent | Owns |
| q-grid/model preprocessing | Must not invent | Owns |
| Feature engineering | Must not duplicate | Owns |
| Estimator and threshold | Executes package contract | Owns |
| Golden inference fixtures | Runs as acceptance gate | Produces/owns reference |
| Training lineage | Consumes provenance | Owns |

This increases responsibility for ML engineers intentionally: scientific/model behavior belongs at the model release boundary rather than in general backend code.

## 15. Suggested migration sequence

### Phase 0 — document and prove current behavior

- Keep public API unchanged.
- Record exact 3+3 product invariant.
- Capture six-measurement golden fixtures.
- Resolve deployed-model lineage.

### Phase 1 — honest six-measurement Bremen inference

If lineage confirms side-mean aggregation:

- require exactly 3 LEFT + 3 RIGHT;
- aggregate all three profiles per side using the authoritative method;
- compute the existing 15 features from side aggregates;
- prove order invariance and reference parity;
- keep the deployed model only if parity proves it is the matching artifact.

If lineage does not confirm this, train/release a new six-measurement model rather than inventing runtime behavior.

### Phase 2 — define Model Runtime Contract v1

Define a stable model-owned invocation boundary with:

- input schema/signature;
- output schema;
- model-specific validation response;
- version/provenance;
- technical failure mapping;
- deterministic golden tests.

Do not expose platform storage/auth/job concepts inside the model package.

### Phase 3 — package Bremen inference completely

Move into the Bremen model release:

- 3+3 validation semantics;
- q-grid handling;
- side aggregation;
- 15-feature construction;
- scaling/imputation;
- estimator;
- model-specific postprocessing.

Run old/new paths in parity/shadow mode before cutover.

### Phase 4 — move Aramina to the same ownership principle

Keep Aramina scientifically separate. Its inference-complete release owns its own preprocessing and features. Bremen Platform only invokes its declared runtime contract.

### Phase 5 — optional registry/serving evolution

Adopt MLflow Model Registry, BentoML, KServe, or another component only where its concrete capability reduces custom platform work or provides needed isolation/scaling.

## 16. Acceptance criteria for the architectural transition

The transition is successful when:

1. Bremen Platform no longer contains model-specific feature formulas for models that have migrated.
2. A model release can reproduce its training/reference output from a declared input fixture without platform-specific scientific code.
3. Six-measurement Bremen input uses all three LEFT and all three RIGHT measurements according to the versioned model contract.
4. Input ordering does not change a prediction.
5. A defective five-measurement Bremen container is rejected before model inference.
6. Model changes can be released/versioned without editing platform feature mathematics.
7. Existing external job/report API contracts remain compatible unless explicitly versioned.

## 17. Open decisions

The following must be resolved before implementation:

- Does the exact deployed Bremen model checksum trace to the side-mean 15-feature preprocessing path?
- Are all six q grids identical after the authoritative preprocessing step?
- Are the three measurements per side exchangeable replicates, or do positions carry distinct scientific semantics that must be preserved?
- If positions are semantically distinct, does the existing model already encode that elsewhere, or is a new model release required?
- What numerical tolerance constitutes training-serving parity?
- Which packaging mechanism is selected for Model Runtime Contract v1: MLflow PyFunc, equivalent Python package, or isolated process/container?
- Does the current container schema represent side/measurement-set semantics strongly enough for the 3+3 contract, or is schema evolution required?
- Who owns the model migration timeline, and can it proceed in parallel with upcoming data collection?

Until these are answered, no runtime mathematical change is authorized by this document.

## 18. Immediate project record

This spike establishes the following project-level statement:

> Bremen's normal product input is six measurements (3 LEFT + 3 RIGHT). The current workflow provider does not consume all six in its feature path. The project will first establish authoritative six-measurement parity, then move model-specific inference logic toward model-owned, inference-complete releases while retaining Bremen Platform as the orchestration/API layer. Framework adoption is a supporting mechanism, not the architectural objective itself.
