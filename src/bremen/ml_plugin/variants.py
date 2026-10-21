"""The five verified IR-03 model variants and their standalone runtimes.

Each spec pins the exact existing model identity, artifact checksum and
artifact filename observed in IR-01.  Nothing here re-declares scientific
parameters: the runtime, thresholds, preprocessing YAML and estimators all come
from the unchanged model packages and the checksum-verified artifact.

B1, B2 and B3 are independent artifacts.  B2 and B3 are explicitly separate
specs (different model IDs, checksums and preprocessing YAML) and are never
treated as interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Mapping

from bremen.ml_plugin.errors import PluginArtifactError, PluginReleaseError

__all__ = [
    "ArtifactEntry",
    "VARIANTS",
    "VariantSpec",
    "load_runtime",
    "variant_spec",
]


@dataclass(frozen=True)
class VariantSpec:
    """Immutable identity of one verified model release variant."""

    key: str
    release_id: str
    workflow_id: str
    runtime_kind: str  # "bremen" | "aramina"
    model_id: str
    model_version: str
    feature_schema_version: str
    artifact_type: str
    artifact_filename: str
    artifact_checksum: str
    requires_raw_container: bool
    preprocessing_release: str
    threshold_source: str
    notes: tuple[str, ...] = field(default_factory=tuple)


VARIANTS: dict[str, VariantSpec] = {
    "a1": VariantSpec(
        key="a1",
        release_id="aramina-target-breast-risk-0-2-12-beta-9bb9111",
        workflow_id="aramina",
        runtime_kind="aramina",
        model_id="aramina_target_breast_risk_0_2_12-beta_9bb911189af6",
        model_version="0.2.12-beta",
        feature_schema_version="aramina_target_breast_risk_v0.2",
        artifact_type="aramina.joblib.model_package",
        artifact_filename="model.joblib",
        artifact_checksum="9bb911189af6e1bd954d21765cbc97c4a57fcf7884657c4b22518f280103e11d",
        requires_raw_container=False,
        preprocessing_release="v0.1.7-beta",
        threshold_source="artifact.models[*].thresholds.threshold_target",
        notes=("explicit target_side; LR1/LR2 chain preserved",),
    ),
    "a2": VariantSpec(
        key="a2",
        release_id="aramina-target-breast-risk-0-2-13-beta-f5e4a04",
        workflow_id="aramina",
        runtime_kind="aramina",
        model_id="aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11",
        model_version="0.2.13-beta",
        feature_schema_version="aramina_target_breast_risk_v0.2",
        artifact_type="aramina.joblib.model_package",
        artifact_filename="model.joblib",
        artifact_checksum="f5e4a04cad11d78ac1e057ede2eac9e2137a8a38f5f22d8ca408bb44c9447e8b",
        requires_raw_container=False,
        preprocessing_release="v0.1.9-beta",
        threshold_source="artifact.models[*].thresholds.threshold_target",
        notes=("explicit target_side; LR1/LR2 chain preserved",),
    ),
    "b1": VariantSpec(
        key="b1",
        release_id="bremen-mri-triage-logreg-v0-1",
        workflow_id="bremen",
        runtime_kind="bremen",
        model_id="bremen-mri-triage-logreg-v0-1",
        model_version="bremen_mri_triage_logreg_v0_1",
        feature_schema_version="v0.1",
        artifact_type="bremen.joblib.model_package",
        artifact_filename="bremen_mri_triage_logreg_v0_1_model_package.joblib",
        artifact_checksum="8ed0a7c52577c72725c052fbdd3a91b60d1f9eb3f02747fe6e4a7b82d712628e",
        requires_raw_container=False,
        preprocessing_release="none",
        threshold_source="artifact.portable_logreg.threshold_applied",
        notes=(
            "legacy integrated-profile path; artifact threshold is authoritative",
            "manifest threshold_value is a placeholder and is never used",
        ),
    ),
    "b2": VariantSpec(
        key="b2",
        release_id="bremen-paper-reference-v0-2-0",
        workflow_id="bremen",
        runtime_kind="bremen",
        model_id="bremen-paper-reference-v0-2-0",
        model_version="0.2.0-paper-reference",
        feature_schema_version="v0.1",
        artifact_type="bremen.joblib.model_package",
        artifact_filename="model.joblib",
        artifact_checksum="65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0",
        requires_raw_container=True,
        preprocessing_release="v0.1.7-beta",
        threshold_source="artifact.portable_logreg.threshold_applied",
        notes=("artifact-owned raw H5 preprocessing",),
    ),
    "b3": VariantSpec(
        key="b3",
        release_id="bremen-v0-2-0-symmetry-candidate",
        workflow_id="bremen",
        runtime_kind="bremen",
        model_id="bremen-v0-2-0-symmetry-candidate",
        model_version="bremen_mri_triage_symmetry_logreg_0_2_0-research",
        feature_schema_version="v0.1",
        artifact_type="bremen.joblib.model_package",
        artifact_filename="model.joblib",
        artifact_checksum="971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4",
        requires_raw_container=True,
        preprocessing_release="v0.1.7-beta",
        threshold_source="artifact.portable_logreg.threshold_applied",
        notes=(
            "independent artifact; not equivalent to B2",
            "exploratory proxy label — not clinically reviewed",
        ),
    ),
}


def variant_spec(key: str) -> VariantSpec:
    try:
        return VARIANTS[key]
    except KeyError:
        raise PluginReleaseError("unknown_variant") from None


class ArtifactEntry:
    """Minimal carrier for the Aramina package's established loader contract.

    The Aramina inference package expects the platform catalog entry shape
    (``artifact_type``, ``_artifact_path``, ``_checksum``, ``model_version``).
    This standalone release entry supplies exactly those values from the
    release descriptor; it provides no discovery or catalog behavior.
    """

    def __init__(
        self, spec: VariantSpec, artifact_path: str, checksum: str,
    ) -> None:
        self.artifact_type = spec.artifact_type
        self._artifact_path = artifact_path
        self._checksum = checksum
        self.model_id = spec.model_id
        self.model_version = spec.model_version
        self.feature_schema_version = spec.feature_schema_version


def _load_package(artifact_path: str, checksum: str) -> Any:
    from bremen.model_packages_bridge import load_staged_artifact

    try:
        return load_staged_artifact(artifact_path, checksum)
    except ValueError:
        raise PluginArtifactError("artifact_integrity_failed") from None
    except Exception:
        raise PluginArtifactError("unsupported_artifact") from None


def load_runtime(
    spec: VariantSpec,
    *,
    artifact_path: str,
    checksum: str | None = None,
) -> Any:
    """Load one release artifact and construct its unchanged scientific runtime.

    The checksum is required to match the release descriptor's pinned artifact
    identity before deserialization.  No platform catalog, S3 or discovery
    code participates.
    """
    expected = checksum or spec.artifact_checksum
    if expected != spec.artifact_checksum:
        raise PluginArtifactError("artifact_identity_mismatch")

    if spec.runtime_kind == "bremen":
        package = _load_package(artifact_path, expected)
        from bremen.model_packages.bremen_v01 import BremenRuntime

        runtime = BremenRuntime(package)
        if not runtime.model_ready():
            raise PluginArtifactError("model_not_ready")
        return runtime

    if spec.runtime_kind == "aramina":
        from bremen.model_packages.aramina_v0213.artifact_compat import (
            ensure_compatibility_bridge,
        )

        ensure_compatibility_bridge()
        entry = ArtifactEntry(spec, artifact_path, expected)
        # Validate/load through the package's unchanged controlled loader.
        from bremen.model_packages.aramina_v0213.inference import (
            _load_selected_artifact,
        )

        try:
            _load_selected_artifact(entry)
        except Exception:
            raise PluginArtifactError("unsupported_artifact") from None
        from bremen.model_packages.aramina_v0213 import AraminaRuntime

        return AraminaRuntime(entry=entry)

    raise PluginReleaseError("unknown_runtime_kind")


def build_model_input(
    spec: VariantSpec,
    *,
    release_dir: str,
    job_dir: str,
    payload: Mapping[str, Any],
) -> SimpleNamespace:
    """Build the existing ``ModelInput`` carrier from explicit request metadata.

    ``container_path`` is always the staged ``<job>/input.h5`` path; the IR-02
    request validator has already required the wire value to be exactly
    ``input.h5``.  B2/B3 use only that path.  B1 and Aramina additionally
    require the canonical case, normalized by the plugin's neutral adapter.
    """
    from bremen.contracts.model_runtime import ModelInput

    container_path = _staged_input_path(job_dir)
    canonical = None
    measurements: tuple[Any, ...] = ()
    if spec.workflow_id in {"bremen"} and not spec.requires_raw_container:
        from bremen.ml_plugin.canonical import canonical_case_from_h5

        canonical = canonical_case_from_h5(container_path, workflow_id="bremen")
        measurements = tuple(canonical.measurements)
    elif spec.workflow_id == "aramina":
        from bremen.ml_plugin.canonical import canonical_case_from_h5

        canonical = canonical_case_from_h5(container_path, workflow_id="aramina")
        measurements = tuple(canonical.measurements)

    parameters = payload.get("parameters", {})
    return ModelInput(
        workflow_id=spec.workflow_id,
        measurements=measurements,
        canonical=canonical,
        patient_id=str(payload.get("patient_id", "") or ""),
        target_side=str(payload.get("target_side", "") or ""),
        container_path=container_path,
        parameters=dict(parameters) if isinstance(parameters, Mapping) else {},
    )


def _staged_input_path(job_dir: str) -> str:
    import os

    candidate = os.path.join(job_dir, "input.h5")
    if os.path.islink(candidate):
        raise PluginReleaseError("staged_input_must_not_be_a_symlink")
    if not os.path.isfile(candidate):
        raise PluginReleaseError("staged_input_missing")
    if os.path.realpath(candidate) != os.path.join(
        os.path.realpath(job_dir), "input.h5"
    ):
        raise PluginReleaseError("staged_input_escaped_job_directory")
    return candidate
