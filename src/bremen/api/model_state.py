"""Startup model loading and state management.

Reads ``BREMEN_MODEL_URI``, ``BREMEN_MODEL_VERSION``, ``BREMEN_MODEL_CHECKSUM``
from environment variables.  Loads the model package exactly once at startup
(not per request).

For local/testing: supports ``file://`` URIs and plain filesystem paths.
For S3: detects ``s3://`` — download is NOT implemented in this PR
(PR 0039); the service logs a clear message and marks model not ready.

Checksum verification happens before ``joblib.load()``.
"""

from __future__ import annotations

import hashlib
import os
import logging
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_ENV_URI = "BREMEN_MODEL_URI"
_ENV_VERSION = "BREMEN_MODEL_VERSION"
_ENV_CHECKSUM = "BREMEN_MODEL_CHECKSUM"


class ModelState:
    """Startup model loading and state management.

    Singleton — model is loaded exactly once at startup.
    """

    _instance: ModelState | None = None

    def __init__(self) -> None:
        self._model_package: dict[str, Any] | None = None
        self._model_version: str | None = None
        self._model_checksum: str | None = None
        self._loaded: bool = False

    @classmethod
    def get_instance(cls) -> ModelState:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def load_at_startup(
        cls,
        model_uri: str | None = None,
        model_version: str | None = None,
        model_checksum: str | None = None,
    ) -> bool:
        """Load model package at startup.

        Reads from env vars if not explicitly provided.
        Verifies SHA-256 checksum before ``joblib.load()``.

        Parameters
        ----------
        model_uri : Path or URI to the model joblib file.  Supports
            ``file://`` and plain filesystem paths.
        model_version : Model version string.
        model_checksum : SHA-256 hex digest (with or without ``sha256:`` prefix).

        Returns
        -------
        ``True`` if model loaded successfully.
        """
        state = cls.get_instance()

        # Read from env if not provided
        if model_uri is None:
            model_uri = os.environ.get(_ENV_URI, "")
        if model_version is None:
            model_version = os.environ.get(_ENV_VERSION, "")
        if model_checksum is None:
            model_checksum = os.environ.get(_ENV_CHECKSUM, "")

        if not model_uri:
            _logger.warning(
                "bremen.model.config.missing\t"
                "stage=config\tstatus=missing\t"
                "reason=model_uri_not_set\t"
                "env_var=%s",
                _ENV_URI,
            )
            _logger.warning(
                "bremen.model.not_ready\t"
                "stage=startup\tstatus=completed\t"
                "model_ready=false\t"
                "reason=model_uri_not_set",
            )
            return False

        # --- Discover and log config state ---
        uri_scheme = "missing"
        if str(model_uri).startswith("s3://"):
            uri_scheme = "s3"
        elif str(model_uri).startswith("file://"):
            uri_scheme = "file"
        elif str(model_uri):
            uri_scheme = "local"

        checksum_present = bool(model_checksum)
        staging_dir_source = "default"
        if os.environ.get("BREMEN_MODEL_STAGING_DIR"):
            staging_dir_source = "config"

        _logger.info(
            "bremen.model.config.read\t"
            "stage=config\tstatus=read\t"
            "uri_scheme=%s\t"
            "model_version=%s\t"
            "checksum_present=%s\t"
            "checksum_algorithm=sha256\t"
            "staging_dir_source=%s",
            uri_scheme,
            model_version or "",
            str(checksum_present).lower(),
            staging_dir_source,
        )

        if model_uri and model_checksum:
            _logger.info(
                "bremen.model.config.detected\t"
                "stage=config\tstatus=detected\t"
                "uri_scheme=%s\t"
                "model_version=%s\t"
                "checksum_present=%s",
                uri_scheme,
                model_version or "",
                str(checksum_present).lower(),
            )

        # S3 download using stage_model_artifact
        if str(model_uri).startswith("s3://"):
            from ..model_artifacts import stage_model_artifact  # noqa: PLC0415

            try:
                staged_path = stage_model_artifact(
                    uri=str(model_uri),
                    expected_checksum=model_checksum,
                )
            except ValueError as exc:
                _logger.error(
                    "bremen.model.artifact.stage.failure\t"
                    "stage=staging\tstatus=failed\t"
                    "exception_class=%s\t"
                    "safe_reason=%s",
                    type(exc).__name__,
                    str(exc).split(".")[0][:200] if str(exc) else "unknown",
                )
                _logger.warning(
                    "bremen.model.not_ready\t"
                    "stage=startup\tstatus=completed\t"
                    "model_ready=false\t"
                    "reason=s3_staging_failure",
                )
                return False

            # Resolve the staged path for checksum verification below
            model_path = str(staged_path)
            model_file = Path(model_path)
        else:
            # Resolve filesystem path (support file:// prefix)
            model_path = str(model_uri)
            if model_path.startswith("file://"):
                model_path = model_path[len("file://"):]

            model_file = Path(model_path)
            if not model_file.exists():
                _logger.error(
                    "bremen.model.artifact.stage.failure\t"
                    "stage=staging\tstatus=failed\t"
                    "reason=local_file_not_found",
                )
                _logger.warning(
                    "bremen.model.not_ready\t"
                    "stage=startup\tstatus=completed\t"
                    "model_ready=false\t"
                    "reason=local_file_not_found",
                )
                return False

        # Verify checksum (strip "sha256:" prefix if present)
        expected_hash = model_checksum
        if expected_hash.startswith("sha256:"):
            expected_hash = expected_hash[len("sha256:"):]

        if expected_hash:
            _logger.debug(
                "bremen.model.checksum.verify.start\t"
                "stage=checksum\tstatus=started\t"
                "checksum_algorithm=sha256",
            )
            computed = _compute_file_sha256(model_file)
            if computed != expected_hash:
                _logger.error(
                    "bremen.model.checksum.verify.failure\t"
                    "stage=checksum\tstatus=failed\t"
                    "reason=checksum_mismatch\t"
                    "model_file=%s",
                    model_file.name,
                )
                _logger.warning(
                    "bremen.model.not_ready\t"
                    "stage=startup\tstatus=completed\t"
                    "model_ready=false\t"
                    "reason=checksum_mismatch",
                )
                return False
            _logger.info(
                "bremen.model.checksum.verify.success\t"
                "stage=checksum\tstatus=completed\t"
                "checksum_algorithm=sha256",
            )
        else:
            _logger.warning(
                "bremen.model.checksum.verify.skipped\t"
                "stage=checksum\tstatus=skipped\t"
                "reason=checksum_env_not_set\t"
                "env_var=%s",
                _ENV_CHECKSUM,
            )

        # Load model using joblib (controlled load boundary)
        from joblib import load as _joblib_load  # noqa: PLC0415

        _logger.debug(
            "bremen.model.load.start\t"
            "stage=load\tstatus=started\t"
            "model_file=%s",
            model_file.name,
        )
        try:
            package = _joblib_load(model_file)
        except Exception as exc:
            _logger.error(
                "bremen.model.load.failure\t"
                "stage=load\tstatus=failed\t"
                "exception_class=%s\t"
                "safe_reason=%s",
                type(exc).__name__,
                str(exc).split(".")[0][:200] if str(exc) else "unknown",
            )
            _logger.warning(
                "bremen.model.not_ready\t"
                "stage=startup\tstatus=completed\t"
                "model_ready=false\t"
                "reason=joblib_load_failure",
            )
            return False

        _logger.info(
            "bremen.model.load.success\t"
            "stage=load\tstatus=completed\t"
            "model_file=%s\t"
            "size_bytes=%s",
            model_file.name,
            str(model_file.stat().st_size),
        )

        if not isinstance(package, dict):
            _logger.error(
                "bremen.model.validation.failure\t"
                "stage=validation\tstatus=failed\t"
                "reason=not_a_dict\t"
                "actual_type=%s",
                type(package).__name__,
            )
            _logger.warning(
                "bremen.model.not_ready\t"
                "stage=startup\tstatus=completed\t"
                "model_ready=false\t"
                "reason=package_not_dict",
            )
            return False

        _logger.info(
            "bremen.model.validation.success\t"
            "stage=validation\tstatus=completed\t"
            "artifact_type=%s",
            package.get("portable_logreg", {}).get(
                "feature_columns", "unknown"
            ),
        )

        state._model_package = package
        state._model_version = model_version or ""
        state._model_checksum = model_checksum or ""
        state._loaded = True

        _logger.info(
            "bremen.model.ready\t"
            "stage=startup\tstatus=completed\t"
            "model_ready=true\t"
            "model_version=%s\t"
            "size_bytes=%s",
            state._model_version,
            str(model_file.stat().st_size),
        )
        return True

    @classmethod
    def get_model(cls) -> dict[str, Any] | None:
        """Get the loaded model package.

        Returns ``None`` if model is not loaded or not ready.
        """
        state = cls.get_instance()
        if not state._loaded:
            return None
        return state._model_package

    @classmethod
    def is_ready(cls) -> bool:
        """Returns ``True`` if model is loaded and ready for inference."""
        state = cls.get_instance()
        return state._loaded

    @classmethod
    def reset_for_tests(cls) -> None:
        """Reset singleton for isolated test execution."""
        cls._instance = None


def _compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
