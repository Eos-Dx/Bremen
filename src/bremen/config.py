"""Minimal Bremen config discovery and loading module.

Bremen — XRD-based ML decision-support workflow foundation.
Not a diagnostic replacement.

Discovery order (deterministic, first-match wins, no merging):
1. explicit path argument
2. BREMEN_CONFIG environment variable
3. cwd/bremen.yml
4. cwd/bremen.yaml
5. cwd/bremen.toml
6. ConfigNotFoundError

This module is import-safe:
- No H5/HDF5 reads
- No model/joblib loads
- No Matador dependency
- No secrets
- No external service calls
- No workflow execution
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigLoadResult:
    """Represents a loaded config file with its metadata.

    Attributes
    ----------
    path : Resolved absolute path to the config file.
    source : 'explicit' | 'env' | 'discovery'
    data : Parsed content as a nested dict.
    warnings : Tuple of warning messages.
    """

    path: Path
    source: str
    data: dict[str, Any]
    warnings: tuple[str, ...] = field(default_factory=tuple)


class ConfigError(Exception):
    """Base exception for config errors."""


class ConfigNotFoundError(ConfigError):
    """No config file found at the specified or discovered paths."""

    def __init__(self, searched: list[Path]) -> None:
        self.searched = searched
        super().__init__(f"No config found. Searched: {searched}")


class ConfigSyntaxError(ConfigError):
    """Config file exists but cannot be parsed."""

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        super().__init__(f"Cannot parse {path}: {detail}")


class CloudConfigError(ConfigError):
    """Cloud/runtime environment configuration is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Cloud config error: {message}")


@dataclass(frozen=True)
class CloudConfig:
    """Runtime/cloud environment configuration.

    All fields are read from environment variables.  No network calls,
    no AWS SDK, no model loading.
    """

    configured: bool
    model_bucket: str | None
    model_prefix: str
    model_version: str | None
    model_manifest_key: str
    service_env: str | None
    aws_region: str | None


# ---------------------------------------------------------------------------
# Public functions (local config)
# ---------------------------------------------------------------------------


def discover_config(
    explicit_path: str | Path | None = None,
    env_var: str | None = "BREMEN_CONFIG",
    cwd: Path | None = None,
) -> ConfigLoadResult:
    """Discover and load a config file using deterministic lookup order.

    Parameters
    ----------
    explicit_path : If provided, use this path directly. Skips all other
        discovery steps.
    env_var : Environment variable name to check for a config path.
        If the variable is unset, empty, or whitespace-only, it is
        treated as not set. Pass ``None`` to skip environment check
        entirely.
    cwd : Working directory for default file discovery. Defaults to
        ``Path.cwd()``.

    Returns
    -------
    ConfigLoadResult with the loaded config metadata.

    Raises
    ------
    ConfigNotFoundError
        If no config file was found at any lookup step.
    ConfigSyntaxError
        If a config file exists but has invalid syntax.
    """
    searched: list[Path] = []

    # 1. Explicit path
    if explicit_path is not None:
        path = Path(explicit_path)
        searched.append(path)
        return _load_from_path(path, source="explicit")

    # 2. BREMEN_CONFIG environment variable
    if env_var is not None:
        env_val = os.environ.get(env_var, "").strip()
        if env_val:
            path = Path(env_val)
            searched.append(path)
            return _load_from_path(path, source="env")

    # 3-5. Default file names in cwd
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    default_names = ["bremen.yml", "bremen.yaml", "bremen.toml"]
    for name in default_names:
        path = cwd / name
        searched.append(path)
        if path.is_file():
            return _load_from_path(path, source="discovery")

    raise ConfigNotFoundError(searched)


def load_config(path: str | Path) -> ConfigLoadResult:
    """Load a config file from an explicit path.

    Supports ``.yml``, ``.yaml``, and ``.toml`` extensions.

    Parameters
    ----------
    path : Filesystem path to the config file.

    Returns
    -------
    ConfigLoadResult with the loaded config metadata.

    Raises
    ------
    ConfigNotFoundError
        If the path does not exist or is not a file.
    ConfigSyntaxError
        If the file cannot be parsed.
    """
    return _load_from_path(Path(path), source="explicit")


# ---------------------------------------------------------------------------
# Cloud / runtime config
# ---------------------------------------------------------------------------


_DEFAULT_PREFIX = "model-packages/"
_DEFAULT_MANIFEST_KEY = "manifest.json"


_ABSOLUTE_PATH_SENTINELS = frozenset({
    "/Users/",
    "/home/",
    "file://",
})


_ENV_BUCKET = "BREMEN_MODEL_BUCKET"
_ENV_PREFIX = "BREMEN_MODEL_PREFIX"
_ENV_VERSION = "BREMEN_MODEL_VERSION"
_ENV_MANIFEST_KEY = "BREMEN_MODEL_MANIFEST_KEY"
_ENV_SERVICE_ENV = "BREMEN_SERVICE_ENV"
_ENV_AWS_REGION = "BREMEN_AWS_REGION"


def read_cloud_config(env: dict[str, str] | None = None) -> CloudConfig:
    """Read runtime/cloud configuration from environment variables.

    Parameters
    ----------
    env : Optional explicit mapping of environment variables.  If
        ``None`` (default), reads from ``os.environ``.  This allows
        testing without mutating the real environment.

    Returns
    -------
    A ``CloudConfig`` dataclass.

    Raises
    ------
    CloudConfigError
        If a required environment variable has an invalid value.

    No network calls.  No AWS SDK.  No model loading.  No H5/HDF5
    reads.
    """
    if env is None:
        env = os.environ  # type: ignore[assignment]

    # --- Bucket (required for being configured) ---
    bucket_raw = env.get(_ENV_BUCKET, "").strip()

    if not bucket_raw:
        return _not_configured()

    _validate_bucket(bucket_raw)

    # --- Prefix ---
    prefix_raw = env.get(_ENV_PREFIX, "").strip()
    if not prefix_raw:
        prefix = _DEFAULT_PREFIX
    else:
        _validate_prefix(prefix_raw)
        prefix = _normalize_prefix(prefix_raw)

    # --- Optional fields ---
    model_version = _non_empty_or_none(env.get(_ENV_VERSION, ""))

    manifest_key_raw = env.get(_ENV_MANIFEST_KEY, "").strip()
    manifest_key = manifest_key_raw if manifest_key_raw else _DEFAULT_MANIFEST_KEY

    service_env = _non_empty_or_none(env.get(_ENV_SERVICE_ENV, ""))
    aws_region = _non_empty_or_none(env.get(_ENV_AWS_REGION, ""))

    return CloudConfig(
        configured=True,
        model_bucket=bucket_raw,
        model_prefix=prefix,
        model_version=model_version,
        model_manifest_key=manifest_key,
        service_env=service_env,
        aws_region=aws_region,
    )


# ---------------------------------------------------------------------------
# Cloud config internal helpers
# ---------------------------------------------------------------------------


def _not_configured() -> CloudConfig:
    """Return a configuration with ``configured=False``."""
    return CloudConfig(
        configured=False,
        model_bucket=None,
        model_prefix=_DEFAULT_PREFIX,
        model_version=None,
        model_manifest_key=_DEFAULT_MANIFEST_KEY,
        service_env=None,
        aws_region=None,
    )


def _validate_bucket(value: str) -> None:
    """Validate that *value* is a valid bucket name (not a URI or path).

    Raises
    ------
    CloudConfigError
        If the value contains ``s3://``, starts with ``/``, or contains
        a local machine path sentinel.
    """
    if value.startswith("s3://"):
        raise CloudConfigError(
            f"BREMEN_MODEL_BUCKET must not be an s3:// URI; "
            f"use bucket name only. Got: {value!r}"
        )

    if value.startswith("/"):
        raise CloudConfigError(
            f"BREMEN_MODEL_BUCKET must not be an absolute path; "
            f"use bucket name only. Got: {value!r}"
        )

    for sentinel in _ABSOLUTE_PATH_SENTINELS:
        if sentinel in value:
            raise CloudConfigError(
                f"BREMEN_MODEL_BUCKET must not contain a local path "
                f"({sentinel}): {value!r}"
            )


def _validate_prefix(value: str) -> None:
    """Validate that *value* is a safe object prefix (not a local path).

    Raises
    ------
    CloudConfigError
        If the value contains a local machine path sentinel (e.g.
        ``/Users/``, ``/home/``, ``file://``).
        Leading slashes are allowed and will be normalised later.
    """
    for sentinel in _ABSOLUTE_PATH_SENTINELS:
        if sentinel in value:
            raise CloudConfigError(
                f"BREMEN_MODEL_PREFIX must not contain a local path "
                f"({sentinel}): {value!r}"
            )


def _normalize_prefix(value: str) -> str:
    """Normalise a prefix into object-prefix style.

    - Removes leading slash.
    - Ensures trailing slash for non-empty values.
    """
    result = value.lstrip("/")
    if result and not result.endswith("/"):
        result += "/"
    return result


def _non_empty_or_none(value: str) -> str | None:
    """Return ``None`` for empty/whitespace strings, else the trimmed value."""
    stripped = value.strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# Internal helpers (local config)
# ---------------------------------------------------------------------------


def _load_from_path(path: Path, *, source: str) -> ConfigLoadResult:
    """Load a config file at *path* and return a ``ConfigLoadResult``.

    This is the single internal entry point for reading and parsing a
    config file.  It handles all supported formats and categorises the
    result (source) determined by the caller.
    """
    resolved = path.resolve()

    if not resolved.exists():
        raise ConfigNotFoundError([resolved])

    if resolved.is_dir():
        raise ConfigSyntaxError(resolved, "Is a directory")

    suffix = resolved.suffix.lower()
    raw = _read_file(resolved)

    if suffix in (".yml", ".yaml"):
        data = _parse_yaml(resolved, raw)
    elif suffix == ".toml":
        data = _parse_toml(resolved, raw)
    else:
        raise ConfigSyntaxError(
            resolved,
            f"Unsupported config format: '{suffix}'. "
            f"Supported: .yml, .yaml, .toml",
        )

    warnings: list[str] = []
    if not data:
        warnings.append(f"Config file is empty: {resolved}")

    return ConfigLoadResult(
        path=resolved,
        source=source,
        data=data,
        warnings=tuple(warnings),
    )


def _read_file(path: Path) -> str:
    """Read a text file, guarding against common encoding errors."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigSyntaxError(
            path, f"Failed to read file: {exc}"
        ) from exc


def _parse_yaml(path: Path, raw: str) -> dict[str, Any]:
    """Parse YAML text using ``yaml.safe_load``."""
    try:
        result = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigSyntaxError(path, str(exc)) from exc

    if result is None:
        return {}
    if not isinstance(result, dict):
        raise ConfigSyntaxError(
            path,
            f"Expected a top-level mapping (dict), got {type(result).__name__}",
        )
    return dict(result)


def _parse_toml(path: Path, raw: str) -> dict[str, Any]:
    """Parse TOML text using ``tomllib`` (Python 3.11+ stdlib)."""
    try:
        result = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigSyntaxError(path, str(exc)) from exc

    if result is None:
        return {}
    return dict(result)
