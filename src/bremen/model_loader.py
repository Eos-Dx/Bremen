"""Controlled, local-only model loading boundary.

Composes existing ``validate_model_package()`` from ``model_package.py``
with an injected deserializer.  Deserialization happens ONLY after
validation succeeds.

Security boundaries:
- Validation must pass before deserialization is attempted.
- Deserializer is injected (default: ``joblib.load``).
- No inference, no H5 reads, no network calls.
- ``joblib`` import is lazy (inside the default-argument fallback
  only), not at module top level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .model_package import (
    ModelPackageError,
    ModelPackageSummary,
    summarize_model_package,
    validate_model_package,
)


@dataclass(frozen=True)
class LoadedModelPackage:
    """Result of a validated and deserialised model load.

    Attributes
    ----------
    summary : Safe metadata from the manifest (no clinical data).
    model : The deserialised model object.  Type depends on what was
        serialised — may be a classifier, a feature-extractor with
        reference statistics, or a composite container.
    warnings : Tuple of non-fatal warnings raised during loading.
    """

    summary: ModelPackageSummary
    model: Any
    warnings: tuple[str, ...] = field(default_factory=tuple)


def load_model_package(
    package_dir: str | Path,
    *,
    deserializer: Callable[[str | Path], Any] | None = None,
) -> LoadedModelPackage:
    """Validate and load a model package.

    This is the ONLY place in Bremen that composes validation and
    deserialisation into a single gated step.

    Parameters
    ----------
    package_dir : Directory containing a validated model package
        (``manifest.json`` + artifact file).
    deserializer : Callable that accepts a ``str | Path`` and returns
        the deserialised object.  Defaults to ``joblib.load``.
        Must be injectable for testing — tests MUST use a safe
        deserializer (e.g., a lambda that returns a simple sentinel),
        never ``joblib.load`` on real model artifacts.

    Returns
    -------
    A ``LoadedModelPackage`` with validated metadata and the
    deserialised model.

    Raises
    ------
    ModelPackageError
        If validation fails (any subclass: NotFound, Manifest,
        Checksum, Security).  Deserialisation is NOT attempted.
    """
    if deserializer is None:
        from joblib import load as _joblib_load  # noqa: PLC0415

        deserializer = _joblib_load

    # Step 1: Validate (checksum, manifest, path safety)
    manifest = validate_model_package(package_dir)
    summary = summarize_model_package(package_dir)

    # Step 2: Deserialize (only after validation succeeds)
    model = deserializer(str(summary.model_path))

    return LoadedModelPackage(
        summary=summary,
        model=model,
    )
