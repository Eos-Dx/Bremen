"""Local Model Release descriptor loading for the standalone plugin.

A release directory is self-contained::

    manifest.json
    configs/runtime.json
    plugin/<plugin wheel>
    model/<artifact>
    requirements/<locks>
    provenance/<records>
    golden_tests/<descriptors>

This module reads only that directory.  It performs no S3 access, no catalog
lookup, no installation and no path discovery outside the release root.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from bremen.ml_plugin.errors import PluginReleaseError

__all__ = [
    "ALLOWED_PREPROCESSING_ENV_VARS",
    "AUX_ENV_ROOT_ENV",
    "FEATURE_LIBRARY_BACKEND_ENV",
    "ReleaseConfig",
    "apply_feature_library_backend",
    "apply_preprocessing_environment",
    "load_release_config",
    "manifest_digest",
]

RUNTIME_CONFIG_SCHEMA = "bremen.ml-plugin.runtime.v1"

#: Root that holds materialized auxiliary environments when a release
#: directory itself does not contain ``aux/<tag>/bin/python``.  This is a
#: logical, machine-relative location supplied by the caller/IR-04 installer;
#: release descriptors never embed absolute interpreter paths.
AUX_ENV_ROOT_ENV = "BREMEN_IR03_AUX_ENV_ROOT"

_AUX_TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

#: Only the established pinned preprocessing interpreter variables may be set
#: from a release config.  A release can never inject arbitrary process state.
ALLOWED_PREPROCESSING_ENV_VARS = frozenset({
    "BREMEN_PREPROCESS_PYTHON",
    "BREMEN_ARAMINA_PREPROCESS_PYTHON",
    "BREMEN_ARAMINA_PREPROCESS_019_PYTHON",
    "BREMEN_PREPROCESS_PROVENANCE",
    "BREMEN_ARAMINA_PREPROCESS_PROVENANCE",
})

#: IR-07: set only inside the release Worker process, only when this
#: release's manifest declares a ``feature_library`` block, to select the
#: standalone xrd_inference_features backend at the scientific runtime
#: boundary (``bremen_v01.runtime`` / ``aramina_v0213.inference``). Never set
#: for legacy (pre-IR-07) releases or the in-process legacy execution path,
#: which keeps computing features through the embedded modules unchanged.
FEATURE_LIBRARY_BACKEND_ENV = "BREMEN_FEATURE_LIBRARY_BACKEND"
_ALLOWED_FEATURE_LIBRARY_BACKENDS = frozenset({"xrd_inference_features"})


@dataclass(frozen=True)
class ReleaseConfig:
    release_dir: str
    release_id: str
    variant: str
    artifact_relative_path: str
    artifact_sha256: str
    preprocessing_environment: Mapping[str, str] = field(default_factory=dict)
    manifest_sha256: str = ""
    feature_library_backend: str = ""

    @property
    def artifact_path(self) -> str:
        return _safe_join(self.release_dir, self.artifact_relative_path)


def _safe_join(root: str, relative_path: str) -> str:
    if not isinstance(relative_path, str) or not relative_path:
        raise PluginReleaseError("invalid_release_relative_path")
    if relative_path.startswith(("/", "\\")) or "\\" in relative_path:
        raise PluginReleaseError("invalid_release_relative_path")
    segments = relative_path.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise PluginReleaseError("invalid_release_relative_path")
    candidate = os.path.join(root, *segments)
    root_real = os.path.realpath(root)
    candidate_real = os.path.realpath(candidate)
    if os.path.commonpath([root_real, candidate_real]) != root_real:
        raise PluginReleaseError("release_path_escaped_root")
    return candidate


def _read_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except Exception:
        raise PluginReleaseError("release_json_unreadable") from None


def manifest_digest(release_dir: str) -> str:
    """SHA-256 over the exact manifest bytes (the release digest binding)."""
    manifest_path = os.path.join(release_dir, "manifest.json")
    try:
        with open(manifest_path, "rb") as stream:
            return hashlib.sha256(stream.read()).hexdigest()
    except Exception:
        raise PluginReleaseError("release_manifest_missing") from None


def load_release_config(release_dir: str) -> ReleaseConfig:
    if not os.path.isdir(release_dir):
        raise PluginReleaseError("release_directory_missing")
    data = _read_json(os.path.join(release_dir, "configs", "runtime.json"))
    if not isinstance(data, Mapping):
        raise PluginReleaseError("runtime_config_invalid")
    if data.get("schema_version") != RUNTIME_CONFIG_SCHEMA:
        raise PluginReleaseError("runtime_config_schema_unsupported")
    release_id = data.get("release_id")
    variant = data.get("variant")
    artifact = data.get("artifact")
    if not isinstance(release_id, str) or not release_id:
        raise PluginReleaseError("runtime_config_invalid")
    if not isinstance(variant, str) or not variant:
        raise PluginReleaseError("runtime_config_invalid")
    if not isinstance(artifact, Mapping):
        raise PluginReleaseError("runtime_config_invalid")
    relative_path = artifact.get("relative_path")
    sha256 = artifact.get("sha256")
    if not isinstance(relative_path, str) or not relative_path:
        raise PluginReleaseError("runtime_config_invalid")
    if (
        not isinstance(sha256, str)
        or len(sha256) != 64
        or any(character not in "0123456789abcdef" for character in sha256)
    ):
        raise PluginReleaseError("runtime_config_invalid")

    environment_raw = data.get("preprocessing_environment", {})
    if not isinstance(environment_raw, Mapping):
        raise PluginReleaseError("runtime_config_invalid")
    environment: dict[str, str] = {}
    for key, value in environment_raw.items():
        if key not in ALLOWED_PREPROCESSING_ENV_VARS:
            raise PluginReleaseError("unsupported_preprocessing_environment_variable")
        if not isinstance(value, str) or not value:
            raise PluginReleaseError("runtime_config_invalid")
        environment[key] = value

    feature_library_backend = data.get("feature_library_backend", "")
    if feature_library_backend and (
        not isinstance(feature_library_backend, str)
        or feature_library_backend not in _ALLOWED_FEATURE_LIBRARY_BACKENDS
    ):
        raise PluginReleaseError("unsupported_feature_library_backend")

    return ReleaseConfig(
        release_dir=os.path.realpath(release_dir),
        release_id=release_id,
        variant=variant,
        artifact_relative_path=relative_path,
        artifact_sha256=sha256,
        preprocessing_environment=environment,
        manifest_sha256=manifest_digest(release_dir),
        feature_library_backend=feature_library_backend or "",
    )


def _resolve_aux_interpreter(release_dir: str, tag: str) -> str:
    """Resolve ``@aux/<tag>`` to an interpreter at use time.

    Preference order: ``<release>/aux/<tag>/bin/python`` (a release that ships
    its own environment) then ``$BREMEN_IR03_AUX_ENV_ROOT/<tag>/bin/python``
    (a materialized environment outside the release).  No descriptor value is
    rewritten, so a copied or reconstructed release resolves without edits.
    """
    if not _AUX_TAG_PATTERN.match(tag):
        raise PluginReleaseError("invalid_auxiliary_environment_tag")
    candidates = [os.path.join(release_dir, "aux", tag, "bin", "python")]
    aux_root = os.environ.get(AUX_ENV_ROOT_ENV, "")
    if aux_root:
        candidates.append(os.path.join(aux_root, tag, "bin", "python"))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    raise PluginReleaseError("auxiliary_environment_missing")


def apply_preprocessing_environment(config: ReleaseConfig) -> None:
    """Set the release's pinned preprocessing interpreters for this process.

    Descriptor values are portable: ``@aux/<tag>`` selects an auxiliary
    environment relative to the release or ``BREMEN_IR03_AUX_ENV_ROOT``, and
    ``@release/<path>`` selects a file inside the release.  Absolute paths are
    rejected so a release cannot silently depend on one machine.  Only the
    established variable names are accepted, and no other process state is
    touched.
    """
    for key, value in config.preprocessing_environment.items():
        if value.startswith("@aux/"):
            os.environ[key] = _resolve_aux_interpreter(
                config.release_dir, value.removeprefix("@aux/")
            )
            continue
        if value.startswith("@release/"):
            os.environ[key] = _safe_join(
                config.release_dir, value.removeprefix("@release/")
            )
            continue
        raise PluginReleaseError("preprocessing_reference_must_be_release_relative")


def apply_feature_library_backend(config: ReleaseConfig) -> None:
    """Select the external feature backend for this Worker process only.

    Sets ``BREMEN_FEATURE_LIBRARY_BACKEND`` exactly when this release's
    manifest declared a ``feature_library`` block; a release built before
    IR-07 has ``feature_library_backend == ""`` and this is a no-op, so the
    scientific runtime boundary keeps using the embedded implementation
    unchanged. No other process state is touched.
    """
    if not config.feature_library_backend:
        return
    os.environ[FEATURE_LIBRARY_BACKEND_ENV] = config.feature_library_backend
