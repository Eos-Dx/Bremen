"""Bremen model packages (PR0154).

Inference-complete model releases.  Each subpackage owns one model release's
complete scientific inference contract (requirements, validation,
preprocessing, features, estimator execution, threshold, provenance) and
exposes one runtime entry point implementing
``bremen.model_runtime.ModelRuntime`` (Model Runtime Contract v1).

Bremen Platform depends on the common contract and on these package entry
points.  It must not import package-internal scientific helpers directly.

The contract module (``bremen.model_runtime``) stays platform-owned; the
science inside these packages does not depend on platform orchestration,
HTTP, jobs, reports, auth or storage.
"""
