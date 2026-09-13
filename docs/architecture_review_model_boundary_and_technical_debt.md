# Architecture Review Reconciliation: Model Boundary and Technical Debt

**Status**: Team discussion / reconciled project note  
**Date**: 2026-09-12  
**Purpose**: Preserve architecture-review findings while reconciling them with the current repository snapshot and the product clarification that Bremen normal input is exactly 3 LEFT + 3 RIGHT.

## 1. Executive summary

The architecture review correctly identifies a structural problem: Bremen Platform currently contains scientific/model-specific inference logic that is better owned, tested, and versioned by the teams that produce the models.

The review also correctly separates two questions that should not be conflated:

1. **Where should scientific inference logic live?**  
   Preferred answer: in a model-owned, inference-complete release behind a stable platform boundary.

2. **Which framework should package/register/serve that release?**  
   MLflow, BentoML, or another framework may help, but framework selection is secondary to fixing the ownership boundary.

A greenfield rewrite is not recommended. The existing Bremen Platform contains valuable product infrastructure — authentication, jobs, reports, events, UI/Control Room, storage boundaries, safety/redaction rules, deployment, and a large test suite — that is orthogonal to model-serving packaging.

## 2. Findings retained as current

### 2.1 Bremen first-pair selection is confirmed

The current Bremen provider contains first-item selection equivalent to:

```python
target = left_ms[0].intensity
control = right_ms[0].intensity
```

For the clarified product contract of exactly 3 LEFT + 3 RIGHT measurements, this means four normal measurements do not participate in that feature calculation.

This is a real runtime/model-contract problem. It should be resolved using authoritative training/model evidence, not by an arbitrary platform-side aggregation choice.

### 2.2 The framework question is secondary to the boundary question

The review's strongest architectural conclusion is retained:

- registries/signatures/environment capture are useful framework capabilities;
- they do not decide scientifically correct preprocessing or aggregation;
- the high-leverage change is to make each model release self-contained from declared model input to structured model output.

### 2.3 Full rewrite is not justified

The identified defects do not justify replacing the entire Bremen product platform. A rewrite would recreate substantial working product infrastructure while still requiring the scientific/model semantics to be fixed.

## 3. Findings that require snapshot provenance

### 3.1 Historical Aramina provider wiring

The review records a period when a real `AraminaWorkflowProvider` existed but the orchestrator registered an old scaffold provider. The review also states this wiring issue was later fixed.

Treat this as historical architecture evidence, not a current open defect, unless a regression is reproduced in the current branch.

### 3.2 Aramina symmetry observation

The review records an earlier implementation in which contralateral measurements allegedly affected only `symmetry_available` while numerical symmetry values were target-only.

That statement conflicts with the current repository snapshot reviewed on 2026-09-12. Current `src/bremen/api/aramina_symmetry.py::symmetry_features()` computes side means for both target and contralateral data and uses both sides in the numerical core metrics.

Therefore the project record should say:

- this was either an older implementation, a different file/path, or a different snapshot;
- it is useful evidence of why model-owned scientific logic matters;
- it is not a confirmed current bug until the exact reviewed commit is identified.

## 4. Product clarification that supersedes ambiguous wording

For Bremen, the normal input contract discussed here is:

```text
6 measurements total
3 LEFT
3 RIGHT
```

Five measurements total are defective input.

Do not infer a 12-measurement contract from wording such as "3 fixed + 3 targeted per breast" without a separate product decision. If measurement positions have distinct semantics, that must be represented explicitly in the authoritative model/input contract.

## 5. Architecture options

### Option A — full rewrite onto a new serving framework

Not recommended for the problems identified. It replaces a large amount of working product infrastructure and does not automatically fix misplaced scientific logic.

### Option B — targeted registry/versioning modernization

Potentially useful. MLflow Model Registry or an equivalent can reduce custom catalog/versioning/signature/dependency work. This can be pursued independently.

### Option C — model-owned inference boundary

Recommended. Each model team delivers a self-contained callable release containing its own validation, preprocessing, aggregation, feature engineering, estimator, model-specific postprocessing, dependencies, and golden reference tests.

Bremen Platform retains API/auth/jobs/storage/events/reports/orchestration and enforces the declared model contract.

### Option D — separate model-serving services later

Consider BentoML/KServe or another remote serving layer only when independent scaling, dependency isolation, or separate deployment ownership becomes a concrete requirement.

## 6. Implication for ML/model engineers

This transition intentionally increases responsibility on the model-producing team.

A model handoff should no longer be only an estimator file plus prose describing preprocessing. A release should include the executable scientific inference path and the evidence needed to prove training-serving parity.

That is not moving a platform bug to another team; it is assigning scientific behavior to the team with the knowledge and evidence required to own it.

## 7. Immediate Bremen 3+3 work before any framework migration

The near-term model question must be resolved independently of MLflow adoption:

1. prove the deployed artifact's training/preprocessing lineage;
2. validate real normal containers are exactly 3 LEFT + 3 RIGHT;
3. determine q-grid compatibility/alignment semantics;
4. compare candidate side aggregation with authoritative reference features;
5. require all 15 features, probability, and final decision to match within an explicit tolerance;
6. prove order invariance;
7. reject malformed counts rather than silently degrade.

Repository evidence currently favors per-side arithmetic mean profiles, but production activation requires lineage/parity proof.

## 8. Open cross-team questions

- Are the three measurements per side interchangeable replicates or semantically distinct positions?
- Does the current H5/container schema encode side and measurement-set semantics strongly enough for the normal 3+3 contract?
- If `sample_type` or equivalent metadata is session-level rather than measurement-level, what schema change is required?
- Which ML/model team owns the authoritative Bremen aggregation contract and golden fixtures?
- Does model-boundary migration run in parallel with prospective data collection, or block it?
- Is MLflow Model Registry needed immediately, or can the boundary rule be enforced first with the existing registry?

## 9. Recommended project decision sequence

1. Accept/adjust ADR-0014 for the six-measurement Bremen input contract.
2. Resolve six-measurement training-serving parity before changing runtime mathematics.
3. Accept/adjust ADR-0015 for the model-owned inference boundary.
4. Define Model Runtime Contract v1.
5. Migrate one model (preferably Bremen) into an inference-complete release and shadow-test it.
6. Decide whether MLflow registry/pyfunc, an equivalent package, or stronger service isolation is required based on actual operational needs.

The key decision is not "use MLflow". The key decision is: **Bremen Platform orchestrates models; model releases own scientific inference semantics.**
