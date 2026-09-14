# ADR-0016: Model Runtime Contract v1

Status: Accepted

Context

Bremen Platform historically contained model-specific scientific feature-engineering logic.

This produced training-serving divergence because platform code reconstructed preprocessing and feature semantics separately from the code used to train or validate models.

The Bremen 3x3 investigation demonstrated this concretely: the previous runtime selected a first LEFT and first RIGHT measurement, while the authoritative training contract consumed all six measurements and used both per-side means and replicate variation.

PR0151 froze the authoritative Bremen training contract.

PR0152 implemented that contract behind a dedicated BremenRuntime boundary and reduced workflow_bremen.py to orchestration responsibilities.

Decision

Bremen Platform adopts Model Runtime Contract v1.

The platform owns orchestration and product infrastructure.

Each model runtime owns its complete model-specific scientific inference behavior.

WorkflowProvider MUST NOT implement model-specific scientific feature engineering.

The semantic runtime boundary consists of:

- requirements()
- validate(model_input)
- predict(model_input)

This ADR defines semantic responsibilities, not a mandatory Python class or framework implementation.

BremenRuntime from PR0152 is the first reference implementation.

Aramina is the next compatibility target and must be adapted without changing its established scientific behavior.

Consequences

Positive:

- scientific inference remains with the team and release that owns the model
- training-serving parity becomes testable as a model-release responsibility
- platform code no longer needs to reconstruct model features
- future model versions can change preprocessing without embedding their mathematics into workflow providers
- model packaging frameworks such as MLflow can later be adopted without redefining ownership

Costs:

- ML/model teams must deliver inference-complete releases rather than estimator-only artifacts
- existing models may require adapters or repackaging
- version/provenance discipline becomes stricter
- migration must preserve existing API and report contracts

Alternatives considered

Keep scientific inference in WorkflowProvider.
Rejected because this reproduces model science inside the platform and has already caused training-serving skew.

Rewrite Bremen Platform around MLflow or another framework.
Rejected as the immediate solution because framework adoption does not by itself correct the ownership boundary and would unnecessarily replace working product infrastructure.

Use a dedicated model runtime boundary without immediately adopting a framework.
Accepted.

Framework position

MLflow PyFunc, Model Registry, BentoML, KServe, or another mechanism may later package or serve model runtimes.

Framework selection is a separate decision from Model Runtime Contract v1.

Migration

PR0152: Bremen scientific runtime boundary established.

PR0153: common runtime contract introduced at platform integration level.

Future PR: Bremen runtime packaged as an inference-complete model release.

Future PR: evaluate MLflow or equivalent packaging and registry mechanisms.

Compatibility

This decision does not authorize changes to existing public API field names, report envelopes, authentication, job lifecycle, model thresholds, or scientific formulas.

Existing model-specific failure codes may remain externally stable while adapters map them to the ownership categories defined by Model Runtime Contract v1.
