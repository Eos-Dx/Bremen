"""Verified local Model Release cache (IR-04).

Resolves the catalog-owned ``runtime_release`` reference, fetches the immutable
release objects from S3, verifies them, installs them offline into
digest-qualified environments, and writes a READY marker only after a smoke
validation succeeds.

Boundaries:

- Installation is separate from activation.  Nothing here switches a catalog
  pointer or changes which runtime serves a request; the legacy runtime stays
  authoritative.
- Only the trusted catalog reference is accepted.  There is no API for
  arbitrary buckets, keys, or ``latest`` resolution.
- Only manifests and files declared by the verified manifest are fetched.
- The Harness never imports ML plugin code: the plugin runs only as a
  subprocess, through the documented entrypoint module.

Cache layout (``root`` is configured by ``BREMEN_RELEASE_CACHE_ROOT``)::

    <root>/.locks/<digest>.lock          inter-process install lock
    <root>/.staging-<digest>-<token>/    in-progress download/verification
    <root>/<digest>/release/             verified release directory (IR-03 layout)
    <root>/<digest>/release/aux/<tag>/   auxiliary preprocessing environments
    <root>/<digest>/env/                 main inference environment
    <root>/<digest>/READY                atomic READY marker (written last)

A directory without a valid ``READY`` marker is never executable; completing a
virtualenv at its final path (rather than moving it) keeps interpreter paths
valid.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math as _math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from bremen.contracts.inference_release import (
    SCHEMA_ID,
    validate_release_manifest,
)
from bremen.contracts.worker_protocol import PROTOCOL_ID

__all__ = [
    "DEFAULT_MAX_CACHE_BYTES",
    "InstalledRelease",
    "ReleaseCache",
    "ReleaseCacheError",
    "ReleaseReference",
]

READY_MARKER = "READY"
MANIFEST_FILENAME = "manifest.json"
RELEASE_DIRNAME = "release"
MAIN_ENV_DIRNAME = "env"
STAGING_PREFIX = ".staging-"
LOCK_DIRNAME = ".locks"
READY_SCHEMA = "bremen.release-ready.v1"

MAX_MANIFEST_BYTES = 1_048_576
DEFAULT_MAX_CACHE_BYTES = 8 * 1024**3
INSTALL_BUDGET_FACTOR = 3.0  # venv + wheels expand beyond the declared bytes
INSTALL_TIMEOUT_SECONDS = 1800
SMOKE_TIMEOUT_SECONDS = 600

_DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_AUX_REF_PATTERN = re.compile(r"^@aux/([A-Za-z0-9][A-Za-z0-9._-]{0,63})$")

# Environment configuration (simple, explicit, no new config layer).
ENV_CACHE_ROOT = "BREMEN_RELEASE_CACHE_ROOT"
ENV_CACHE_MAX_BYTES = "BREMEN_RELEASE_CACHE_MAX_BYTES"
ENV_CATALOG_URI = "BREMEN_MODEL_CATALOG_URI"

# Child processes never inherit credentials or unrelated platform state.
_ALLOWED_CHILD_ENV = (
    "PATH", "HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "LC_CTYPE",
    "SYSTEMROOT",
)


class Runner(Protocol):
    def __call__(
        self, command: Sequence[str], cwd: str, timeout: int,
        env: Mapping[str, str],
    ) -> Any: ...


class ReleaseCacheError(Exception):
    """Fail-closed release resolution/installation error.

    ``category`` is a fixed identifier; the message never contains object
    bodies, credentials, patient data or tracebacks.
    """

    def __init__(self, category: str, detail: str = "") -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"{category}: {detail}" if detail else category)


@dataclass(frozen=True)
class ReleaseReference:
    """The already-validated catalog-owned ``runtime_release`` reference."""

    model_id: str
    release_id: str
    manifest_key: str
    manifest_sha256: str

    @property
    def digest(self) -> str:
        return self.manifest_sha256


@dataclass(frozen=True)
class InstalledRelease:
    """A READY local release."""

    release_id: str
    model_id: str
    manifest_sha256: str
    release_dir: str
    main_python: str
    manifest: Mapping[str, Any]

    @property
    def digest(self) -> str:
        return self.manifest_sha256


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _default_cache_root() -> str:
    return os.path.join(tempfile.gettempdir(), "bremen-release-cache")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ReleaseCacheError("invalid_configuration", name) from None
    if value <= 0:
        raise ReleaseCacheError("invalid_configuration", name)
    return value


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class ReleaseCache:
    """Verified, digest-qualified local release cache."""

    def __init__(
        self,
        root: str | None = None,
        *,
        catalog_uri: str | None = None,
        s3_client: Any = None,
        max_cache_bytes: int | None = None,
        python_executable: str | None = None,
        free_space_factor: float = INSTALL_BUDGET_FACTOR,
        runner: Runner | None = None,
    ) -> None:
        self.root = os.path.realpath(
            root or os.environ.get(ENV_CACHE_ROOT) or _default_cache_root()
        )
        self.catalog_uri = (
            catalog_uri
            if catalog_uri is not None
            else os.environ.get(ENV_CATALOG_URI, "")
        )
        if not isinstance(self.catalog_uri, str) or not self.catalog_uri:
            raise ReleaseCacheError("invalid_configuration", "catalog_uri")
        # Reuse the established catalog URI semantics; the bucket is never a
        # per-call or per-request choice.
        from bremen.platform.models.discovery import _validate_catalog_uri  # noqa: PLC0415

        try:
            self.bucket, self.catalog_prefix = _validate_catalog_uri(self.catalog_uri)
        except ValueError:
            raise ReleaseCacheError("invalid_configuration", "catalog_uri") from None
        self._s3_client = s3_client
        self.max_cache_bytes = (
            max_cache_bytes
            if max_cache_bytes is not None
            else _env_int(ENV_CACHE_MAX_BYTES, DEFAULT_MAX_CACHE_BYTES)
        )
        if (
            not isinstance(free_space_factor, (int, float))
            or isinstance(free_space_factor, bool)
            or not _math.isfinite(float(free_space_factor))
            or float(free_space_factor) <= 0
        ):
            raise ReleaseCacheError("invalid_configuration", "free_space_factor")
        self.python_executable = python_executable or sys.executable
        self.free_space_factor = float(free_space_factor)
        self._runner = runner or _run_command

    # -- public API ------------------------------------------------------

    def resolve(self, entry: Any) -> ReleaseReference:
        """Read the catalog-owned reference and verify its identity fields."""
        reference_raw = (
            entry.get_runtime_release()
            if hasattr(entry, "get_runtime_release")
            else None
        )
        if not isinstance(reference_raw, Mapping):
            raise ReleaseCacheError("release_reference_missing")
        allowed = {"schema_version", "release_id", "manifest_key", "manifest_sha256"}
        if set(reference_raw) != allowed:
            raise ReleaseCacheError("release_reference_invalid")
        if reference_raw.get("schema_version") != SCHEMA_ID:
            raise ReleaseCacheError("release_reference_invalid", "schema_version")
        release_id = reference_raw.get("release_id")
        manifest_key = reference_raw.get("manifest_key")
        manifest_sha256 = reference_raw.get("manifest_sha256")
        model_id = getattr(entry, "model_id", None)
        if not isinstance(release_id, str) or not release_id:
            raise ReleaseCacheError("release_reference_invalid", "release_id")
        if not isinstance(manifest_key, str) or not manifest_key:
            raise ReleaseCacheError("release_reference_invalid", "manifest_key")
        if manifest_key.startswith("/") or ".." in manifest_key.split("/"):
            raise ReleaseCacheError("release_reference_invalid", "manifest_key")
        if "\n" in manifest_key or "\r" in manifest_key:
            raise ReleaseCacheError("release_reference_invalid", "manifest_key")
        # The key must stay beneath the trusted catalog prefix.  The prefix is
        # normalized with a trailing "/", so this is a whole-path-prefix check
        # that cannot be satisfied by a lookalike sibling ("catalog-evil/").
        if self.catalog_prefix and not manifest_key.startswith(self.catalog_prefix):
            raise ReleaseCacheError("release_reference_invalid", "manifest_key")
        if not isinstance(manifest_sha256, str) or not _DIGEST_PATTERN.match(
            manifest_sha256
        ):
            raise ReleaseCacheError("release_reference_invalid", "manifest_sha256")
        if not isinstance(model_id, str) or not model_id:
            raise ReleaseCacheError("release_reference_invalid", "model_id")
        return ReleaseReference(
            model_id=model_id,
            release_id=release_id,
            manifest_key=manifest_key,
            manifest_sha256=manifest_sha256,
        )

    def install(
        self, entry: Any, *, protected_digests: Sequence[str] = (),
    ) -> InstalledRelease:
        """Install (or reuse) the release referenced by ``entry``.

        Returns only after the release is READY.  Raises
        ``ReleaseCacheError`` when any verification, compatibility, install or
        smoke step fails; in that case no READY marker exists.
        """
        reference = self.resolve(entry)
        ready = self.read_ready(reference.digest)
        if ready is not None:
            return self._installed(reference, ready)

        digest = reference.digest
        manifest_bytes = self._fetch_manifest(reference)
        manifest_document = self._parse_manifest(manifest_bytes, reference)
        self._check_identity(manifest_document, reference, entry)
        self._check_compatibility(manifest_document)

        self._admit(manifest_document)
        self.evict(protected_digests=tuple(protected_digests) + (digest,))

        with self._install_lock(digest):
            ready = self.read_ready(digest)
            if ready is not None:
                return self._installed(reference, ready)

            staging = os.path.join(self.root, f"{STAGING_PREFIX}{digest}-{uuid.uuid4().hex[:8]}")
            final_dir = os.path.join(self.root, digest)
            # A directory without a valid READY marker is never executable;
            # remove leftover partial work before installing at its final path.
            if os.path.isdir(final_dir):
                shutil.rmtree(final_dir, ignore_errors=True)
            os.makedirs(staging, mode=0o700)
            try:
                self._download_release(manifest_document, manifest_bytes, staging)
                self._install_environments(manifest_document, staging, final_dir)
                self._smoke(
                    manifest_document, manifest_bytes, final_dir, reference.model_id,
                )
                marker = self._ready_marker(reference, manifest_document)
                _write_atomic_json(os.path.join(final_dir, READY_MARKER), marker)
            except BaseException:
                shutil.rmtree(staging, ignore_errors=True)
                shutil.rmtree(final_dir, ignore_errors=True)
                raise
            shutil.rmtree(staging, ignore_errors=True)

        ready = self.read_ready(digest)
        if ready is None:  # pragma: no cover - defensive
            raise ReleaseCacheError("ready_marker_missing")
        return self._installed(reference, ready)

    def read_ready(self, digest: str) -> dict[str, Any] | None:
        """Return the validated READY marker, or ``None`` when not READY."""
        if not isinstance(digest, str) or not _DIGEST_PATTERN.match(digest):
            return None
        path = os.path.join(self.root, digest, READY_MARKER)
        try:
            with open(path, "r", encoding="utf-8") as stream:
                marker = json.load(stream)
        except Exception:
            return None
        if not isinstance(marker, Mapping):
            return None
        if marker.get("schema_version") != READY_SCHEMA:
            return None
        if marker.get("manifest_sha256") != digest:
            return None
        if not isinstance(marker.get("release_id"), str) or not marker["release_id"]:
            return None
        if not isinstance(marker.get("model_id"), str) or not marker["model_id"]:
            return None
        if not isinstance(marker.get("main_python"), str):
            return None
        main_python = marker["main_python"]
        if os.path.realpath(main_python) != os.path.realpath(
            os.path.join(self.root, digest, MAIN_ENV_DIRNAME, "bin", "python")
        ):
            return None
        if not os.path.isfile(main_python):
            return None
        if not os.path.isdir(os.path.join(self.root, digest, RELEASE_DIRNAME)):
            return None
        # Warm reuse is also an LRU touch.
        with contextlib.suppress(OSError):
            os.utime(path, None)
        return dict(marker)

    def evict(self, *, protected_digests: Sequence[str] = ()) -> list[str]:
        """Remove inactive, unreferenced, non-running cache entries.

        Only entries with a valid READY marker are considered, oldest READY
        access time first.  Protected digests, the digest being installed and
        anything without a READY marker (in-progress work) are never removed.
        """
        self._cleanup_staging()
        protected = set(protected_digests)
        entries: list[tuple[float, str, int]] = []
        total = 0
        if not os.path.isdir(self.root):
            return []
        for name in os.listdir(self.root):
            if not _DIGEST_PATTERN.match(name):
                continue
            path = os.path.join(self.root, name)
            if not os.path.isdir(path):
                continue
            size = _tree_size(path)
            total += size
            if name in protected:
                continue
            if not os.path.isfile(os.path.join(path, READY_MARKER)):
                continue
            try:
                age = os.stat(os.path.join(path, READY_MARKER)).st_mtime
            except OSError:
                continue
            entries.append((age, name, size))
        removed: list[str] = []
        if total <= self.max_cache_bytes:
            return removed
        for _age, name, size in sorted(entries):
            if total <= self.max_cache_bytes:
                break
            if name in protected:
                continue
            shutil.rmtree(os.path.join(self.root, name), ignore_errors=True)
            total -= size
            removed.append(name)
        return removed

    # -- fetch / verify --------------------------------------------------

    def _client(self) -> Any:
        if self._s3_client is None:
            from boto3 import client as _client  # noqa: PLC0415

            self._s3_client = _client("s3")
        return self._s3_client

    def _fetch_manifest(self, reference: ReleaseReference) -> bytes:
        try:
            response = self._client().get_object(
                Bucket=self.bucket, Key=reference.manifest_key
            )
            body = response["Body"].read(MAX_MANIFEST_BYTES + 1)
        except ReleaseCacheError:
            raise
        except Exception:
            raise ReleaseCacheError("manifest_missing") from None
        if not isinstance(body, (bytes, bytearray)):
            raise ReleaseCacheError("manifest_invalid")
        if len(body) > MAX_MANIFEST_BYTES:
            raise ReleaseCacheError("manifest_too_large")
        if hashlib.sha256(bytes(body)).hexdigest() != reference.manifest_sha256:
            raise ReleaseCacheError("manifest_digest_mismatch")
        return bytes(body)

    @staticmethod
    def _parse_manifest(body: bytes, reference: ReleaseReference) -> dict[str, Any]:
        try:
            document = json.loads(body)
        except Exception:
            raise ReleaseCacheError("manifest_invalid") from None
        try:
            validate_release_manifest(document)
        except Exception:
            raise ReleaseCacheError("manifest_invalid") from None
        if document["release_id"] != reference.release_id:
            raise ReleaseCacheError("release_identity_mismatch", "release_id")
        return document

    @staticmethod
    def _check_identity(
        manifest: Mapping[str, Any], reference: ReleaseReference, entry: Any,
    ) -> None:
        model = manifest["model"]
        if model["model_id"] != reference.model_id:
            raise ReleaseCacheError("release_identity_mismatch", "model_id")
        entry_model_id = getattr(entry, "model_id", None)
        if entry_model_id is not None and entry_model_id != reference.model_id:
            raise ReleaseCacheError("release_identity_mismatch", "catalog_model_id")
        entry_version = getattr(entry, "model_version", None)
        if entry_version and entry_version != model["model_version"]:
            raise ReleaseCacheError("release_identity_mismatch", "model_version")

    def _download_release(
        self, manifest: Mapping[str, Any], manifest_bytes: bytes, staging: str,
    ) -> None:
        declared: list[Mapping[str, Any]] = list(manifest["files"]) + list(
            manifest["golden_tests"]
        )
        seen: set[str] = set()
        for ref in declared:
            relative = ref["relative_path"]
            if relative in seen:
                raise ReleaseCacheError("duplicate_release_path", relative)
            seen.add(relative)
            target = _safe_join(staging, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            self._download_object(ref["s3_key"], target)
            _verify_file(target, ref, require_size=ref.get("size_bytes") is not None)
        # Keep the exact verified manifest bytes inside the release directory.
        with open(os.path.join(staging, MANIFEST_FILENAME), "wb") as stream:
            stream.write(manifest_bytes)

    def _download_object(self, key: str, target: str) -> None:
        try:
            response = self._client().get_object(Bucket=self.bucket, Key=key)
            payload = response["Body"].read()
        except Exception:
            raise ReleaseCacheError("release_object_missing") from None
        if not isinstance(payload, (bytes, bytearray)):
            raise ReleaseCacheError("release_object_missing")
        with open(target, "wb") as stream:
            stream.write(payload)
    # -- compatibility / admission ---------------------------------------

    def _check_compatibility(self, manifest: Mapping[str, Any]) -> None:
        expected = manifest["compatibility"]
        import platform  # noqa: PLC0415
        import sysconfig  # noqa: PLC0415

        soabi = str(sysconfig.get_config_var("SOABI") or "")
        actual = {
            "python_implementation": platform.python_implementation(),
            "abi": soabi,
            "os": platform.system().lower(),
            "arch": platform.machine(),
        }
        for field, value in actual.items():
            if expected[field] != value:
                raise ReleaseCacheError("incompatible_host", field)
        expected_version = tuple(
            int(part) for part in str(expected["python_version"]).split(".")[:2]
        )
        if expected_version != tuple(sys.version_info[:2]):
            raise ReleaseCacheError("incompatible_host", "python_version")
        if expected["worker_protocol_version"] != PROTOCOL_ID:
            raise ReleaseCacheError("incompatible_host", "worker_protocol_version")

    def _admit(self, manifest: Mapping[str, Any]) -> None:
        declared = 0
        for ref in list(manifest["files"]) + list(manifest["golden_tests"]):
            size = ref.get("size_bytes")
            if (
                not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
            ):
                raise ReleaseCacheError("manifest_invalid", "size_bytes")
            declared += size
        if declared > self.max_cache_bytes:
            raise ReleaseCacheError("insufficient_cache_budget")
        need = int(declared * self.free_space_factor) + 16 * 1024**2
        probe = self.root
        while not os.path.isdir(probe):
            parent = os.path.dirname(probe)
            if parent == probe:
                raise ReleaseCacheError("insufficient_disk")
            probe = parent
        free = shutil.disk_usage(probe).free
        if free < need:
            raise ReleaseCacheError("insufficient_disk")

    # -- install ---------------------------------------------------------

    def _install_environments(
        self, manifest: Mapping[str, Any], staging: str, final_dir: str,
    ) -> None:
        os.makedirs(final_dir, mode=0o700)
        release_dir = os.path.join(final_dir, RELEASE_DIRNAME)
        shutil.move(staging, release_dir)

        main_wheelhouse, aux_wheelhouses = self._verify_wheel_closure(
            release_dir, manifest,
        )

        main_python = self._create_environment(
            os.path.join(final_dir, MAIN_ENV_DIRNAME)
        )
        self._pip_install(
            main_python,
            os.path.join(release_dir, "requirements", "main.lock"),
            main_wheelhouse,
        )
        plugin_wheel = _role_path(manifest, "plugin_wheel")
        self._pip_install_wheel(
            main_python, os.path.join(release_dir, plugin_wheel)
        )

        for name, spec in manifest["environments"].items():
            if name == "main":
                continue
            reference = spec.get("environment_ref")
            match = _AUX_REF_PATTERN.match(reference or "")
            if match is None:
                # The release contract cannot express a safe aux environment.
                raise ReleaseCacheError("invalid_runtime_configuration", name)
            tag = match.group(1)
            if tag not in aux_wheelhouses:
                raise ReleaseCacheError("wheel_closure_incomplete", tag)
            aux_python = self._create_environment(
                os.path.join(release_dir, "aux", tag)
            )
            lock_relative = spec.get("requirements_lock_relative_path") or (
                f"requirements/aux-{tag}.lock"
            )
            lock_path = _safe_join(release_dir, lock_relative)
            if not os.path.isfile(lock_path):
                raise ReleaseCacheError("missing_requirements_lock", tag)
            self._pip_install(aux_python, lock_path, aux_wheelhouses[tag])

        self._validate_runtime_configuration(release_dir, manifest)

    @staticmethod
    def _verify_wheel_closure(
        release_dir: str, manifest: Mapping[str, Any],
    ) -> tuple[str, dict[str, str]]:
        """Require exactly the manifest-declared wheels for each environment.

        Returns ``(main_wheelhouse, {tag: wheelhouse})``.  Any undeclared wheel
        file, or a declared wheel absent from disk, fails closed.
        """
        declared = {
            ref["relative_path"]: ref
            for ref in manifest["files"]
            if ref["role"] in {"dependency_wheel", "dependency_wheel_aux"}
        }
        if not declared:
            raise ReleaseCacheError("wheel_closure_incomplete", "no_wheels_declared")
        main_dir = os.path.join(release_dir, "wheelhouse", "main")
        if not os.path.isdir(main_dir) or not os.listdir(main_dir):
            raise ReleaseCacheError("wheel_closure_incomplete", "main")
        aux_root = os.path.join(release_dir, "wheelhouse", "aux")
        aux_dirs: dict[str, str] = {}
        if os.path.isdir(aux_root):
            for tag in sorted(os.listdir(aux_root)):
                path = os.path.join(aux_root, tag)
                if os.path.isdir(path):
                    aux_dirs[tag] = path

        found: set[str] = set()
        for path in [main_dir, *aux_dirs.values()]:
            for name in sorted(os.listdir(path)):
                if not name.endswith(".whl"):
                    raise ReleaseCacheError("wheel_closure_incomplete", name)
                relative = os.path.relpath(os.path.join(path, name), release_dir)
                relative = relative.replace(os.sep, "/")
                ref = declared.get(relative)
                if ref is None:
                    raise ReleaseCacheError("undeclared_wheel", relative)
                if _sha256_path(os.path.join(path, name)) != ref["sha256"]:
                    raise ReleaseCacheError("release_file_checksum_mismatch", relative)
                found.add(relative)
        missing = set(declared) - found
        if missing:
            raise ReleaseCacheError(
                "wheel_closure_incomplete", sorted(missing)[0]
            )

        for lock_relative, wheelhouse in (
            ("requirements/main.lock", main_dir),
            *((f"requirements/aux-{tag}.lock", path) for tag, path in aux_dirs.items()),
        ):
            lock_path = os.path.join(release_dir, lock_relative)
            if not os.path.isfile(lock_path):
                raise ReleaseCacheError("missing_requirements_lock", lock_relative)
            available = {
                _sha256_path(os.path.join(wheelhouse, name))
                for name in os.listdir(wheelhouse)
            }
            with open(lock_path, "r", encoding="utf-8") as stream:
                for line in stream:
                    for digest in re.findall(r"--hash=sha256:([a-f0-9]{64})", line):
                        if digest not in available:
                            raise ReleaseCacheError(
                                "wheel_closure_incomplete", lock_relative
                            )
        return main_dir, aux_dirs

    def _create_environment(self, target: str) -> str:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        completed = self._runner(
            [self.python_executable, "-m", "venv", target],
            os.path.dirname(target),
            INSTALL_TIMEOUT_SECONDS,
            _restricted_environment(),
        )
        if getattr(completed, "returncode", 1) != 0:
            raise ReleaseCacheError("environment_install_failed", "venv")
        python = os.path.join(target, "bin", "python")
        if not os.path.isfile(python):
            raise ReleaseCacheError("environment_install_failed", "interpreter")
        return python

    def _pip_install(self, python: str, lock_path: str, wheelhouse: str) -> None:
        completed = self._runner(
            [
                python, "-m", "pip", "install",
                "--no-index", "--only-binary=:all:", "--require-hashes",
                "--disable-pip-version-check", "--no-input",
                "--find-links", wheelhouse,
                "-r", lock_path,
            ],
            os.path.dirname(lock_path),
            INSTALL_TIMEOUT_SECONDS,
            _restricted_environment(),
        )
        if getattr(completed, "returncode", 1) != 0:
            raise ReleaseCacheError("offline_install_failed", os.path.basename(lock_path))

    def _pip_install_wheel(self, python: str, wheel_path: str) -> None:
        completed = self._runner(
            [
                python, "-m", "pip", "install",
                "--no-index", "--no-deps", "--no-input",
                "--disable-pip-version-check",
                "--force-reinstall",
                wheel_path,
            ],
            os.path.dirname(wheel_path),
            INSTALL_TIMEOUT_SECONDS,
            _restricted_environment(),
        )
        if getattr(completed, "returncode", 1) != 0:
            raise ReleaseCacheError("offline_install_failed", "plugin_wheel")

    @staticmethod
    def _validate_runtime_configuration(
        release_dir: str, manifest: Mapping[str, Any],
    ) -> None:
        path = os.path.join(release_dir, "configs", "runtime.json")
        try:
            with open(path, "r", encoding="utf-8") as stream:
                config = json.load(stream)
        except Exception:
            raise ReleaseCacheError("invalid_runtime_configuration") from None
        if not isinstance(config, Mapping):
            raise ReleaseCacheError("invalid_runtime_configuration")
        if config.get("schema_version") != "bremen.ml-plugin.runtime.v1":
            raise ReleaseCacheError("invalid_runtime_configuration", "schema_version")
        if config.get("release_id") != manifest["release_id"]:
            raise ReleaseCacheError("invalid_runtime_configuration", "release_id")
        artifact = config.get("artifact")
        if not isinstance(artifact, Mapping):
            raise ReleaseCacheError("invalid_runtime_configuration", "artifact")
        if artifact.get("relative_path") != _role_path(manifest, "model_artifact"):
            raise ReleaseCacheError("invalid_runtime_configuration", "artifact_path")
        if artifact.get("sha256") != manifest["scientific_metadata"]["artifact_checksum"]:
            raise ReleaseCacheError("invalid_runtime_configuration", "artifact_sha256")
        environment = config.get("preprocessing_environment", {})
        if not isinstance(environment, Mapping):
            raise ReleaseCacheError("invalid_runtime_configuration", "environment")
        for value in environment.values():
            if not isinstance(value, str) or value.startswith("/"):
                raise ReleaseCacheError("invalid_runtime_configuration", "environment")
        for name in manifest["environments"]:
            if name == "main":
                continue
            reference = manifest["environments"][name].get("environment_ref")
            if not any(
                isinstance(value, str) and value == reference
                for value in environment.values()
            ):
                raise ReleaseCacheError("invalid_runtime_configuration", name)

    # -- smoke -----------------------------------------------------------

    def _smoke(
        self, manifest: Mapping[str, Any], manifest_bytes: bytes, final_dir: str,
        model_id: str,
    ) -> None:
        release_dir = os.path.join(final_dir, RELEASE_DIRNAME)
        main_python = os.path.join(final_dir, MAIN_ENV_DIRNAME, "bin", "python")
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        job_dir = tempfile.mkdtemp(prefix="bremen-release-smoke-")
        try:
            result = self._run_entrypoint(
                main_python, release_dir, job_dir, digest, model_id,
                operation="requirements", payload={},
            )
            if result.get("status") != "ok":
                raise ReleaseCacheError("smoke_failed", "requirements")
            self._smoke_golden(
                manifest, main_python, release_dir, digest, model_id,
            )
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

    def _smoke_golden(
        self, manifest: Mapping[str, Any], main_python: str, release_dir: str,
        digest: str, model_id: str,
    ) -> None:
        """Run every manifest golden case and compare its full expected result.

        Golden inputs are release files, so a missing case fixture is an
        install failure.  READY is never written without passing every case.
        """
        cases_path = os.path.join(
            release_dir, _role_path(manifest, "golden_cases", "golden_tests")
        )
        try:
            with open(cases_path, "r", encoding="utf-8") as stream:
                cases = json.load(stream).get("cases", [])
        except Exception:
            raise ReleaseCacheError("smoke_failed", "golden_descriptor") from None
        if not isinstance(cases, list) or not cases:
            raise ReleaseCacheError("smoke_failed", "golden_cases_missing")
        declared_fixtures = {
            ref["relative_path"]
            for ref in manifest["golden_tests"]
            if ref["role"] == "golden_fixture"
        }
        for case in cases:
            relative = case.get("fixture_release_path")
            if not isinstance(relative, str) or relative not in declared_fixtures:
                raise ReleaseCacheError(
                    "smoke_failed", str(case.get("case_id", "golden_case"))
                )
            fixture = _safe_join(release_dir, relative)
            if not os.path.isfile(fixture):
                raise ReleaseCacheError(
                    "smoke_failed", str(case.get("case_id", "golden_fixture"))
                )
            job_dir = tempfile.mkdtemp(prefix="bremen-release-golden-")
            try:
                shutil.copyfile(fixture, os.path.join(job_dir, "input.h5"))
                payload: dict[str, Any] = {
                    "workflow_id": manifest["model"]["workflow_id"],
                    "container_path": "input.h5",
                    "parameters": {},
                }
                for field in ("patient_id", "target_side"):
                    if case.get(field):
                        payload[field] = case[field]
                result = self._run_entrypoint(
                    main_python, release_dir, job_dir, digest, model_id,
                    operation="predict", payload=payload,
                )
                _verify_golden_case(case, result)
            finally:
                shutil.rmtree(job_dir, ignore_errors=True)

    def _run_entrypoint(
        self, python: str, release_dir: str, job_dir: str, digest: str,
        model_id: str, *, operation: str, payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        request = {
            "protocol": PROTOCOL_ID,
            "request_id": f"smoke-{operation}",
            "operation": operation,
            "model_id": model_id,
            "release_digest": digest,
            "payload": dict(payload),
        }
        with open(os.path.join(job_dir, "request.json"), "w", encoding="utf-8") as stream:
            json.dump(request, stream)
        completed = self._runner(
            [
                python, "-m", "bremen.ml_plugin.entrypoint",
                "--release-dir", release_dir, "--job-dir", job_dir,
            ],
            job_dir,
            SMOKE_TIMEOUT_SECONDS,
            _restricted_environment(),
        )
        if getattr(completed, "returncode", 1) != 0:
            raise ReleaseCacheError("smoke_failed", operation)
        try:
            with open(os.path.join(job_dir, "result.json"), "r", encoding="utf-8") as stream:
                return json.load(stream)
        except Exception:
            raise ReleaseCacheError("smoke_failed", "result_missing") from None

    # -- READY / lock / helpers ------------------------------------------

    def _ready_marker(
        self, reference: ReleaseReference, manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        final_dir = os.path.join(self.root, reference.digest)
        return {
            "schema_version": READY_SCHEMA,
            "release_id": reference.release_id,
            "model_id": reference.model_id,
            "model_version": manifest["model"]["model_version"],
            "manifest_sha256": reference.digest,
            "plugin_wheel_sha256": next(
                ref["sha256"] for ref in manifest["files"]
                if ref["role"] == "plugin_wheel"
            ),
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "main_python": os.path.join(final_dir, MAIN_ENV_DIRNAME, "bin", "python"),
            "release_dir": os.path.join(final_dir, RELEASE_DIRNAME),
            "cache_layout": 1,
        }

    def _installed(
        self, reference: ReleaseReference, marker: Mapping[str, Any],
    ) -> InstalledRelease:
        release_dir = os.path.join(self.root, reference.digest, RELEASE_DIRNAME)
        with open(os.path.join(release_dir, MANIFEST_FILENAME), encoding="utf-8") as stream:
            manifest = json.load(stream)
        return InstalledRelease(
            release_id=reference.release_id,
            model_id=reference.model_id,
            manifest_sha256=reference.digest,
            release_dir=release_dir,
            main_python=str(marker["main_python"]),
            manifest=manifest,
        )

    @contextlib.contextmanager
    def _install_lock(self, digest: str):
        try:
            import fcntl  # noqa: PLC0415
        except ImportError:  # pragma: no cover - non-POSIX host
            raise ReleaseCacheError("lock_unsupported") from None
        lock_dir = os.path.join(self.root, LOCK_DIRNAME)
        os.makedirs(lock_dir, mode=0o700, exist_ok=True)
        path = os.path.join(lock_dir, f"{digest}.lock")
        handle = open(path, "a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            with contextlib.suppress(Exception):
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def _cleanup_staging(self) -> None:
        if not os.path.isdir(self.root):
            return
        for name in os.listdir(self.root):
            if not name.startswith(STAGING_PREFIX):
                continue
            path = os.path.join(self.root, name)
            try:
                if time.time() - os.stat(path).st_mtime > 3600:
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                continue


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def _sha256_path(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_join(root: str, relative_path: str) -> str:
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or relative_path.startswith(("/", "\\"))
        or "\\" in relative_path
    ):
        raise ReleaseCacheError("unsafe_release_path", relative_path)
    segments = relative_path.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise ReleaseCacheError("unsafe_release_path", relative_path)
    candidate = os.path.join(root, *segments)
    root_real = os.path.realpath(root)
    if os.path.commonpath([root_real, os.path.realpath(candidate)]) != root_real:
        raise ReleaseCacheError("unsafe_release_path", relative_path)
    return candidate


def _verify_file(path: str, ref: Mapping[str, Any], *, require_size: bool) -> None:
    with open(path, "rb") as stream:
        payload = stream.read()
    expected_size = ref.get("size_bytes")
    if require_size and isinstance(expected_size, int) and len(payload) != expected_size:
        raise ReleaseCacheError("release_file_size_mismatch", ref["relative_path"])
    if hashlib.sha256(payload).hexdigest() != ref["sha256"]:
        raise ReleaseCacheError("release_file_checksum_mismatch", ref["relative_path"])


def _role_path(
    manifest: Mapping[str, Any], role: str, collection: str = "files",
) -> str:
    for ref in manifest[collection]:
        if ref["role"] == role:
            return ref["relative_path"]
    raise ReleaseCacheError("invalid_runtime_configuration", role)


def _tree_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def _write_atomic_json(path: str, payload: Mapping[str, Any]) -> None:
    directory = os.path.dirname(path)
    handle, temporary = tempfile.mkstemp(prefix=".ready-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def _run_command(
    command: Sequence[str], cwd: str, timeout: int,
    env: Mapping[str, str] | None = None,
) -> Any:
    return subprocess.run(
        list(command), cwd=cwd, text=True, capture_output=True,
        timeout=timeout, check=False,
        env=dict(env) if env is not None else _restricted_environment(),
    )


def _restricted_environment() -> dict[str, str]:
    """Minimal child-process environment: no AWS or platform secrets.

    Credential-bearing variables (AWS_*, BOTO*, PYTHONPATH, ...) are omitted
    entirely rather than filtered from an inherited copy.
    """
    environment = {
        key: os.environ[key] for key in _ALLOWED_CHILD_ENV if key in os.environ
    }
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PIP_NO_INPUT"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return environment


def _verify_golden_case(
    case: Mapping[str, Any], result: Mapping[str, Any],
) -> None:
    """Compare a golden case result to its release-bound expected values."""
    case_id = str(case.get("case_id", "golden_case"))
    expected = case.get("expected") or {}
    if result.get("status") != expected.get("status"):
        raise ReleaseCacheError("smoke_failed", case_id)
    if expected.get("status") == "error":
        error = result.get("error") or {}
        if error.get("code") != expected.get("error_code"):
            raise ReleaseCacheError("smoke_failed", case_id)
        if "safe_reason" in expected and (
            error.get("safe_reason") != expected["safe_reason"]
        ):
            raise ReleaseCacheError("smoke_failed", case_id)
        return

    payload = (result.get("payload") or {}).get("result") or {}
    for field in (
        "probability", "risk_probability",
        "threshold_applied", "decision_threshold",
        "prediction", "target_class_risk_level",
    ):
        if field not in expected:
            continue
        if payload.get(field) != expected[field]:
            raise ReleaseCacheError("smoke_failed", case_id)
