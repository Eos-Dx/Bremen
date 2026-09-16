# Model Package Scientific Ownership

## Status

Architecture rule for Bremen Platform model integration.

This rule applies to Bremen, Aramina, and future models.

## Decision

**A model package owns the complete scientific transformation from its supported raw input to its structured model result. Bremen Platform owns orchestration around that transformation.**

The platform is intentionally a thin model client.

It must not independently reproduce preprocessing, feature engineering, eligibility rules, or scientific metadata extraction that belong to the selected model.

## Why this boundary exists

Duplicating model science in the serving platform creates two implementations of one scientific contract:

```text
science/model implementation
platform reimplementation
```

Those implementations can silently diverge while continuing to produce syntactically valid results.

The platform may then:

- apply different preprocessing;
- construct different features;
- make a different eligibility decision;
- report metadata with different semantics;
- produce a different model input than the one used to train or validate the artifact.

The safe design has one scientific source of truth: the model package.

## Required execution shape

```text
                    Bremen Platform

source_id
   |
   v
resolve / materialize raw source
   |
   v
select model package
   |
   +---------------------------------------------+
                                                 |
                                                 v
                                   Model package / runtime
                                   -----------------------
                                   validate model input
                                   parse supported raw input
                                   run preprocessing
                                   apply scientific corrections
                                   construct profiles/features
                                   apply model gates
                                   run estimator
                                   extract source metadata
                                   return normalized result
                                                 |
   +---------------------------------------------+
   |
   v
generic Standard Result mapper
   |
   v
job / report / API response
```

## What the platform owns

The platform owns generic infrastructure and lifecycle concerns:

- authentication and authorization;
- model catalog routing;
- source registration;
- source identity;
- source storage access;
- raw source materialization;
- generic provenance such as source checksum or size when appropriate;
- job creation;
- execution lifecycle;
- timeouts and resource controls;
- events;
- reports;
- public API contracts;
- canonical result mapping.

These concerns do not require knowledge of model science.

## What the model package owns

A model package owns all model-specific interpretation of its input, including:

- supported H5/container layout;
- supported compatibility adapters;
- preprocessing dependency/version;
- preprocessing configuration;
- calibration and physical corrections;
- measurement selection and grouping;
- geometry and integration;
- normalization;
- scientific profiles;
- feature engineering;
- eligibility/gating;
- estimator execution;
- model-specific output semantics;
- model-relevant source metadata;
- model method metadata;
- model performance metadata supplied by the artifact/package.

The package may internally use isolated environments or subprocess workers where its dependency versions differ from the platform environment.

Those implementation details remain package concerns.

## Metadata is part of model interpretation

Source metadata is not automatically generic merely because it originates in an H5 file.

For example, a field exposed publicly as:

```text
hardware_version
```

may have a model-specific authoritative source and interpretation.

Therefore generic platform code must not infer canonical Standard Result fields from arbitrary H5 paths.

The package performs any required source-specific interpretation and returns canonical metadata to the runtime contract.

Example normalized output:

```python
{
    "result": {...},

    "source_metadata": {
        "patient_age": ...,
        "scan_date_time": ...,
        "operator_id": ...,
        "hardware_version": ...,
        "eoscan_version": ...,
    },

    "model_metadata": {
        "model_method": ...,
    },

    "model_metrics": {
        "sensitivity": ...,
        "specificity": ...,
    },
}
```

The Standard Result mapper translates this normalized output into the public Standard Model Result contract.

It does not reinterpret the raw source.

## Requirements are model-owned

The platform may expose:

```text
GET  /models/{model_id}/requirements
POST /models/{model_id}/requirements/validate
```

but the scientific requirements behind these endpoints are declared by the selected model/package.

The platform is responsible for safely exposing and orchestrating those requirements, not authoring them.

This preserves the same ownership rule before execution and during execution.

## Forensic evidence: Bremen Nova_378

The Bremen paper-reference investigation on 2026-09-16 demonstrated a concrete failure mode caused by duplicating preprocessing semantics.

Authoritative source:

```text
bremen-training-pipeline
commit c98a950d3fbf0db72d87f2ecd977d80fe35da9e4
```

Artifact:

```text
bremen_paper_reference_symmetry_logreg
version 0.2.0-paper-reference
SHA256 65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0
```

The artifact declares:

```text
raw_peak_gate = 0.6
```

A forensic copy of `Nova_378.h5`, with only the missing container identity attributes added for compatibility with the authoritative reader, produced exactly six authoritative preprocessing rows:

```text
3 LEFT
3 RIGHT
```

The authoritative preprocessing applied thickness adjustment.

Its six raw-peak values were:

```text
Right P1  0.3635513484477997
Right P2  0.3559076786041260
Right P3  0.4989819526672363
Left  P1  0.4220002889633179
Left  P2  0.4592023789882660
Left  P3  0.6773958802223206
```

Therefore:

```text
mean_peak_value_raw = 0.46283992131551105
```

and the authoritative model rejects the case because:

```text
0.46283992131551105 < 0.6
```

Reconstructing the same profiles before the authoritative thickness correction produced:

```text
mean = 0.2829194790228839
```

The existing platform path produced a value around `0.295` for the same case.

The final eligibility decision happened to agree, but the scientific intermediate did not.

This matters because an input nearer the `0.6` boundary could produce a different eligibility decision.

The correct response is therefore **not** to reproduce the Bremen thickness correction in generic platform preprocessing.

The correct response is to stop treating generic platform preprocessing as the scientific source of truth and let the Bremen package execute its authoritative preprocessing.

## Consequences

1. Existing platform-owned model science is technical debt and should be moved behind package boundaries progressively.
2. Generic platform modules must become thinner, not smarter about model internals.
3. Model packages may use different preprocessing releases without forcing one global scientific environment.
4. Standard Result metadata must originate from package-normalized output.
5. A future model should integrate without adding its scientific vocabulary to generic platform code.
6. Scientific parity tests belong at the model-package boundary.
7. Platform tests should test orchestration and contract translation rather than duplicate scientific formulas.

## Review invariant

A code review should flag a change when generic platform code learns a new model-specific scientific concept.

Examples include adding to generic API/runner/mapper code:

```text
/session/sample/...
PONI semantics
sample thickness correction
q=13..14.8
mean_peak_value_raw
Bremen-specific 3x3 processing
Aramina-specific symmetry formulas
model-specific feature aliases
```

Such additions normally belong in the model package.

The review question is:

> Could a third model be added without teaching the generic platform its scientific internals?

If the answer is no, the package/platform boundary should be reconsidered.
