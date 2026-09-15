"""Aramina v0.2.13 inference-complete model package (PR0156).

One clear runtime entry point implementing Model Runtime Contract v1
(``bremen.model_runtime.ModelRuntime``):

- ``AraminaRuntime`` — requirements / validate / predict over the checksum-
  verified Aramina training artifact pipeline (PR0137 science, PR0153B
  contract; unchanged in PR0156 apart from ownership).

The package owns the complete model-specific inference contract: artifact
interpretation (with the pickle compatibility bridge), prediction-preprocessing
release selection and execution, target-side measurement processing, LR1
scoring, logit aggregation, symmetry features, final-model execution, the
model-owned threshold, safe model diagnostics (private trace allowlists and the
public ``ARAMINA_*`` failure taxonomy), release identity/provenance and the
model-declared input contract.

Platform code should import the runtime entry point here (or ``.runtime``)
rather than the internal scientific modules (``inference``, ``preprocessing``,
``symmetry``, ``artifact_compat``).  Release contract constants and reference
identity live in ``.manifest``.

The existing artifact format (joblib/sklearn training artifact) is retained as
is: this package standardizes ownership, not artifact format.

No HTTP, jobs, reports, auth, S3 credentials or frontend coupling in this
package.  Research decision support requiring radiologist review.
"""
from __future__ import annotations

from bremen.model_packages.aramina_v0213 import manifest
from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError
from bremen.model_packages.aramina_v0213.runtime import AraminaRuntime

PACKAGE_ID = "aramina_v0213"
MODEL_CONTRACT_VERSION = "aramina_v0213.inference_package.v1"

__all__ = [
    "AraminaRuntime",
    "AraminaWorkflowError",
    "MODEL_CONTRACT_VERSION",
    "PACKAGE_ID",
    "manifest",
]
