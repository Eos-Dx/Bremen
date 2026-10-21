"""Inference Release manifest contract v1 (``bremen.inference-release.v1``) — IR-02.

Defines the immutable Model Release manifest schema described by
``docs/inference-releases/architecture-and-contract.md``: release identity,
model identity, runtime compatibility, an allowlisted entrypoint, the files
that make up the release (wheels, artifacts, config, provenance), per-release
environments, scientific provenance metadata, golden-test references, and
build provenance.

This module validates a manifest dict into a structured, typed shape and
rejects anything unsafe: unknown/unsupported schema versions, malformed
SHA-256 digests, absolute paths, ``..`` traversal, duplicate release files,
and unsafe entrypoints. It performs no I/O, no S3 access, no installation,
and no activation — see IR-02 PLAN and the coder task's NON-GOALS.

Dependency direction (enforced by
``tests/test_inference_release_contract.py``): this module must not import
``bremen.platform``, ``bremen.model_packages``, ``boto3``, ``fastapi``, or any
model-specific scientific implementation. It may import the sibling
``bremen.contracts.worker_protocol`` module only for its protocol-identity
constant (``PROTOCOL_ID``), which a release's declared compatibility must
match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from bremen.contracts.worker_protocol import PROTOCOL_ID as _WORKER_PROTOCOL_ID

__all__ = [
    "SCHEMA_ID",
    "InferenceReleaseContractError",
    "InferenceReleaseManifest",
    "ReleaseBuild",
    "ReleaseCompatibility",
    "ReleaseEntrypoint",
    "ReleaseFileRef",
    "ReleaseModelIdentity",
    "ReleaseScientificMetadata",
    "validate_release_manifest",
]

SCHEMA_ID = "bremen.inference-release.v1"

_IDENTITY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_ENTRYPOINT_MODULE_PATTERN = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$"
)
_ENTRYPOINT_CALLABLE_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
_ENVIRONMENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

_REQUIRED_TOP_LEVEL_FIELDS = (
    "schema_version",
    "release_id",
    "model",
    "compatibility",
    "entrypoint",
    "files",
    "environments",
    "scientific_metadata",
    "golden_tests",
    "build",
)
_ALLOWED_TOP_LEVEL_FIELDS = frozenset(_REQUIRED_TOP_LEVEL_FIELDS)


class InferenceReleaseContractError(ValueError):
    """Fail-closed validation failure for ``bremen.inference-release.v1``."""


# ---------------------------------------------------------------------------
# Structured manifest shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseFileRef:
    """One file role declared by a release (a wheel, artifact, config, or
    provenance record for ``files``; a fixture/expected-output pair for
    ``golden_tests``).
    """

    role: str
    relative_path: str
    s3_key: str
    sha256: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class ReleaseModelIdentity:
    """``model`` block: existing model_id, model version, workflow family
    and artifact identity.
    """

    model_id: str
    model_version: str
    workflow_id: str
    artifact_identity: str


@dataclass(frozen=True)
class ReleaseCompatibility:
    """``compatibility`` block: Python implementation/version/ABI,
    OS/architecture, required native libraries, worker protocol version.
    """

    python_implementation: str
    python_version: str
    abi: str
    os: str
    arch: str
    worker_protocol_version: str
    native_libraries: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReleaseEntrypoint:
    """``entrypoint`` block: an allowlisted module from the installed ML
    plugin wheel; no shell command.
    """

    module: str
    callable: str = ""


@dataclass(frozen=True)
class ReleaseScientificMetadata:
    """``scientific_metadata`` block: preprocessing release/commit,
    feature-order/config hashes, artifact checksum and threshold source.
    """

    preprocessing_release: str
    artifact_checksum: str
    threshold_source: str
    feature_order_hash: str = ""
    config_hash: str = ""


@dataclass(frozen=True)
class ReleaseBuild:
    """``build`` block: source repository and full commit, build identity
    and provenance reference.
    """

    source_repository: str
    commit: str
    build_id: str
    provenance_reference: str = ""


@dataclass(frozen=True)
class InferenceReleaseManifest:
    """A fully validated ``bremen.inference-release.v1`` manifest."""

    schema_version: str
    release_id: str
    model: ReleaseModelIdentity
    compatibility: ReleaseCompatibility
    entrypoint: ReleaseEntrypoint
    files: tuple[ReleaseFileRef, ...]
    environments: Mapping[str, Mapping[str, Any]]
    scientific_metadata: ReleaseScientificMetadata
    golden_tests: tuple[ReleaseFileRef, ...]
    build: ReleaseBuild


# ---------------------------------------------------------------------------
# Field-level validators
# ---------------------------------------------------------------------------


def _require_dict(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InferenceReleaseContractError(f"{field_name} must be a JSON object")
    return value


def _require_list(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise InferenceReleaseContractError(f"{field_name} must be a JSON array")
    return value


def _require_str(value: Any, *, field_name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise InferenceReleaseContractError(f"{field_name} must be a string")
    if not allow_empty and not value.strip():
        raise InferenceReleaseContractError(f"{field_name} must not be empty")
    return value


def _require_sha256(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256_HEX_PATTERN.match(value):
        raise InferenceReleaseContractError(
            f"{field_name} must be a lowercase 64-character hex SHA-256 digest"
        )
    return value


def _require_identity(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not _IDENTITY_PATTERN.match(value):
        raise InferenceReleaseContractError(f"{field_name} is not a valid identity string")
    return value


def _validate_relative_path(value: Any, *, field_name: str) -> str:
    """Reject absolute paths, ``..`` traversal, backslashes, and empty paths."""
    if not isinstance(value, str) or not value:
        raise InferenceReleaseContractError(f"{field_name} must be a non-empty string")
    if value.startswith("/") or value.startswith("\\"):
        raise InferenceReleaseContractError(f"{field_name} must be a relative path: {value!r}")
    if ":" in value:
        raise InferenceReleaseContractError(f"{field_name} must not contain a drive/scheme: {value!r}")
    if "\\" in value:
        raise InferenceReleaseContractError(f"{field_name} must use '/' separators: {value!r}")
    segments = value.split("/")
    if any(seg in ("", "..", ".") for seg in segments):
        raise InferenceReleaseContractError(
            f"{field_name} must not contain '..', '.', or empty segments: {value!r}"
        )
    return value


def _validate_s3_key(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise InferenceReleaseContractError(f"{field_name} must be a non-empty string")
    if value.startswith("/"):
        raise InferenceReleaseContractError(f"{field_name} must not start with '/': {value!r}")
    if ".." in value.split("/"):
        raise InferenceReleaseContractError(f"{field_name} must not contain '..': {value!r}")
    if "\n" in value or "\r" in value:
        raise InferenceReleaseContractError(f"{field_name} must not contain control characters")
    return value


def _validate_file_ref(data: Any, *, field_name: str) -> ReleaseFileRef:
    body = _require_dict(data, field_name=field_name)
    role = _require_str(body.get("role"), field_name=f"{field_name}.role")
    relative_path = _validate_relative_path(
        body.get("relative_path"), field_name=f"{field_name}.relative_path"
    )
    s3_key = _validate_s3_key(body.get("s3_key"), field_name=f"{field_name}.s3_key")
    sha256 = _require_sha256(body.get("sha256"), field_name=f"{field_name}.sha256")
    size_bytes = body.get("size_bytes")
    if size_bytes is not None:
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise InferenceReleaseContractError(
                f"{field_name}.size_bytes must be a non-negative integer"
            )
    extra = set(body) - {"role", "relative_path", "s3_key", "sha256", "size_bytes"}
    if extra:
        raise InferenceReleaseContractError(
            f"{field_name} has unsupported fields: {sorted(extra)}"
        )
    return ReleaseFileRef(
        role=role, relative_path=relative_path, s3_key=s3_key, sha256=sha256,
        size_bytes=size_bytes,
    )


def _validate_file_list(
    data: Any, *, field_name: str, require_size: bool = False,
) -> tuple[ReleaseFileRef, ...]:
    items = _require_list(data, field_name=field_name)
    if not items:
        raise InferenceReleaseContractError(f"{field_name} must not be empty")
    refs: list[ReleaseFileRef] = []
    for index, item in enumerate(items):
        ref = _validate_file_ref(item, field_name=f"{field_name}[{index}]")
        if require_size and ref.size_bytes is None:
            raise InferenceReleaseContractError(
                f"{field_name}[{index}].size_bytes is required"
            )
        refs.append(ref)
    return tuple(refs)


def _validate_no_duplicate_paths(
    files: Sequence[ReleaseFileRef], golden_tests: Sequence[ReleaseFileRef],
) -> None:
    """Reject duplicate ``relative_path`` values across files and golden_tests.

    A release's files and golden-test fixtures land in one release
    directory layout; two entries claiming the same relative path is an
    unsafe/ambiguous release regardless of which list they came from.
    """
    seen: dict[str, str] = {}
    for label, refs in (("files", files), ("golden_tests", golden_tests)):
        for ref in refs:
            existing = seen.get(ref.relative_path)
            if existing is not None:
                raise InferenceReleaseContractError(
                    f"Duplicate relative_path {ref.relative_path!r} in "
                    f"{label} (already used by {existing})"
                )
            seen[ref.relative_path] = label


def _validate_model(data: Any) -> ReleaseModelIdentity:
    body = _require_dict(data, field_name="model")
    allowed = {"model_id", "model_version", "workflow_id", "artifact_identity"}
    extra = set(body) - allowed
    if extra:
        raise InferenceReleaseContractError(f"model has unsupported fields: {sorted(extra)}")
    return ReleaseModelIdentity(
        model_id=_require_identity(body.get("model_id"), field_name="model.model_id"),
        model_version=_require_str(body.get("model_version"), field_name="model.model_version"),
        workflow_id=_require_identity(body.get("workflow_id"), field_name="model.workflow_id"),
        artifact_identity=_require_str(
            body.get("artifact_identity"), field_name="model.artifact_identity"
        ),
    )


def _validate_compatibility(data: Any) -> ReleaseCompatibility:
    body = _require_dict(data, field_name="compatibility")
    allowed = {
        "python_implementation", "python_version", "abi", "os", "arch",
        "worker_protocol_version", "native_libraries",
    }
    extra = set(body) - allowed
    if extra:
        raise InferenceReleaseContractError(
            f"compatibility has unsupported fields: {sorted(extra)}"
        )
    worker_protocol_version = _require_str(
        body.get("worker_protocol_version"), field_name="compatibility.worker_protocol_version"
    )
    if worker_protocol_version != _WORKER_PROTOCOL_ID:
        raise InferenceReleaseContractError(
            f"compatibility.worker_protocol_version must be {_WORKER_PROTOCOL_ID!r}, "
            f"got {worker_protocol_version!r}"
        )
    native_libraries_raw = body.get("native_libraries", [])
    native_libraries_seq = _require_list(native_libraries_raw, field_name="compatibility.native_libraries")
    native_libraries = tuple(
        _require_str(lib, field_name=f"compatibility.native_libraries[{i}]")
        for i, lib in enumerate(native_libraries_seq)
    )
    return ReleaseCompatibility(
        python_implementation=_require_str(
            body.get("python_implementation"), field_name="compatibility.python_implementation"
        ),
        python_version=_require_str(body.get("python_version"), field_name="compatibility.python_version"),
        abi=_require_str(body.get("abi"), field_name="compatibility.abi"),
        os=_require_str(body.get("os"), field_name="compatibility.os"),
        arch=_require_str(body.get("arch"), field_name="compatibility.arch"),
        worker_protocol_version=worker_protocol_version,
        native_libraries=native_libraries,
    )


def _validate_entrypoint(data: Any) -> ReleaseEntrypoint:
    body = _require_dict(data, field_name="entrypoint")
    allowed = {"module", "callable"}
    extra = set(body) - allowed
    if extra:
        raise InferenceReleaseContractError(f"entrypoint has unsupported fields: {sorted(extra)}")
    module = body.get("module")
    if (
        not isinstance(module, str)
        or not module
        or not _ENTRYPOINT_MODULE_PATTERN.match(module)
        or "/" in module
        or "\\" in module
        or module.startswith(".")
        or module.endswith(".")
    ):
        raise InferenceReleaseContractError(
            f"entrypoint.module must be a dotted Python module path; no shell "
            f"command, path separator, or leading/trailing dot: {module!r}"
        )
    callable_name = body.get("callable", "")
    if callable_name and not _ENTRYPOINT_CALLABLE_PATTERN.match(callable_name):
        raise InferenceReleaseContractError(
            f"entrypoint.callable must be a plain Python identifier: {callable_name!r}"
        )
    return ReleaseEntrypoint(module=module, callable=callable_name or "")


def _validate_environments(data: Any) -> Mapping[str, Mapping[str, Any]]:
    body = _require_dict(data, field_name="environments")
    if "main" not in body:
        raise InferenceReleaseContractError("environments must declare a 'main' environment")
    validated: dict[str, Mapping[str, Any]] = {}
    for name, spec in body.items():
        if not isinstance(name, str) or not _ENVIRONMENT_NAME_PATTERN.match(name):
            raise InferenceReleaseContractError(f"environments has an invalid environment name: {name!r}")
        spec_body = _require_dict(spec, field_name=f"environments.{name}")
        requirements_lock_sha256 = spec_body.get("requirements_lock_sha256")
        if requirements_lock_sha256 is not None:
            _require_sha256(
                requirements_lock_sha256,
                field_name=f"environments.{name}.requirements_lock_sha256",
            )
        validated[name] = dict(spec_body)
    return validated


def _validate_scientific_metadata(data: Any) -> ReleaseScientificMetadata:
    body = _require_dict(data, field_name="scientific_metadata")
    allowed = {
        "preprocessing_release", "artifact_checksum", "threshold_source",
        "feature_order_hash", "config_hash",
    }
    extra = set(body) - allowed
    if extra:
        raise InferenceReleaseContractError(
            f"scientific_metadata has unsupported fields: {sorted(extra)}"
        )
    return ReleaseScientificMetadata(
        preprocessing_release=_require_str(
            body.get("preprocessing_release"), field_name="scientific_metadata.preprocessing_release"
        ),
        artifact_checksum=_require_sha256(
            body.get("artifact_checksum"), field_name="scientific_metadata.artifact_checksum"
        ),
        threshold_source=_require_str(
            body.get("threshold_source"), field_name="scientific_metadata.threshold_source"
        ),
        feature_order_hash=str(body.get("feature_order_hash", "")),
        config_hash=str(body.get("config_hash", "")),
    )


def _validate_build(data: Any) -> ReleaseBuild:
    body = _require_dict(data, field_name="build")
    allowed = {"source_repository", "commit", "build_id", "provenance_reference"}
    extra = set(body) - allowed
    if extra:
        raise InferenceReleaseContractError(f"build has unsupported fields: {sorted(extra)}")
    commit = body.get("commit")
    if not isinstance(commit, str) or not _COMMIT_PATTERN.match(commit):
        raise InferenceReleaseContractError(
            f"build.commit must be a 7-40 character lowercase hex git commit SHA: {commit!r}"
        )
    return ReleaseBuild(
        source_repository=_require_str(
            body.get("source_repository"), field_name="build.source_repository"
        ),
        commit=commit,
        build_id=_require_str(body.get("build_id"), field_name="build.build_id"),
        provenance_reference=str(body.get("provenance_reference", "")),
    )


# ---------------------------------------------------------------------------
# Top-level validation entry point
# ---------------------------------------------------------------------------


def validate_release_manifest(data: Mapping[str, Any]) -> InferenceReleaseManifest:
    """Validate a raw manifest dict against ``bremen.inference-release.v1``.

    Fail-closed: unknown/missing top-level fields, an unsupported
    ``schema_version``, malformed identities/digests, absolute paths,
    ``..`` traversal, duplicate release files, and unsafe entrypoints are
    all rejected with ``InferenceReleaseContractError``.
    """
    if not isinstance(data, Mapping):
        raise InferenceReleaseContractError("manifest must be a JSON object")

    unknown = set(data) - _ALLOWED_TOP_LEVEL_FIELDS
    if unknown:
        raise InferenceReleaseContractError(f"manifest has unsupported fields: {sorted(unknown)}")

    missing = [f for f in _REQUIRED_TOP_LEVEL_FIELDS if f not in data]
    if missing:
        raise InferenceReleaseContractError(f"manifest missing required fields: {missing}")

    schema_version = data["schema_version"]
    if schema_version != SCHEMA_ID:
        raise InferenceReleaseContractError(
            f"Unsupported schema_version: {schema_version!r}; expected {SCHEMA_ID!r}"
        )

    release_id = _require_identity(data["release_id"], field_name="release_id")
    model = _validate_model(data["model"])
    compatibility = _validate_compatibility(data["compatibility"])
    entrypoint = _validate_entrypoint(data["entrypoint"])
    files = _validate_file_list(data["files"], field_name="files", require_size=True)
    environments = _validate_environments(data["environments"])
    scientific_metadata = _validate_scientific_metadata(data["scientific_metadata"])
    golden_tests = _validate_file_list(data["golden_tests"], field_name="golden_tests")
    build = _validate_build(data["build"])

    _validate_no_duplicate_paths(files, golden_tests)

    return InferenceReleaseManifest(
        schema_version=schema_version,
        release_id=release_id,
        model=model,
        compatibility=compatibility,
        entrypoint=entrypoint,
        files=files,
        environments=environments,
        scientific_metadata=scientific_metadata,
        golden_tests=golden_tests,
        build=build,
    )
