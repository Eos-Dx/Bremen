"""Reproducible wheel construction for the standalone XRD feature library (IR-07).

Builds the ``xrd-inference-features`` distribution (``packages/xrd-inference-
features/src/xrd_inference_features``) the exact same deterministic way
``bremen.release_build.wheel`` builds the ML plugin wheel: a hand-written PEP
427 zip with fixed timestamps and sorted members, no build backend, no
network access. Every Model Release independently calls this builder and
binds the resulting wheel into its own release; the library is never shipped
as a shared/global dependency of the Bremen application itself.
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path

from bremen.release_build.wheel import (
    WheelBuildResult,
    _record_hash,
    _zip_info,
)

__all__ = [
    "FEATURE_LIBRARY_DISTRIBUTION",
    "FEATURE_LIBRARY_VERSION",
    "FEATURE_LIBRARY_REQUIRES_DIST",
    "build_feature_library_wheel",
    "feature_library_package_files",
]

#: Must track packages/xrd-inference-features/pyproject.toml exactly.
FEATURE_LIBRARY_DISTRIBUTION = "xrd-inference-features"
FEATURE_LIBRARY_VERSION = "0.1.0"
FEATURE_LIBRARY_REQUIRES_DIST: tuple[str, ...] = (
    "numpy==2.5.4",
    "pandas==3.0.6",
    "scipy==1.18.1",
)

#: <repo>/packages/xrd-inference-features/src
_FEATURE_LIBRARY_SOURCE_ROOT = (
    Path(__file__).resolve().parents[3] / "packages" / "xrd-inference-features" / "src"
)
_EXCLUDED_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache"})


def feature_library_package_files(source_root: Path | None = None) -> list[tuple[str, Path]]:
    """Return ``(archive_name, source_path)`` pairs for the feature-library wheel."""
    root = Path(source_root) if source_root is not None else _FEATURE_LIBRARY_SOURCE_ROOT
    package_dir = root / "xrd_inference_features"
    if not package_dir.is_dir():
        raise FileNotFoundError(f"feature-library package missing: {package_dir}")
    entries: list[tuple[str, Path]] = []
    for source in sorted(package_dir.rglob("*.py")):
        parts = source.relative_to(root).parts
        if any(part in _EXCLUDED_DIR_NAMES for part in parts):
            continue
        entries.append(("/".join(parts), source))
    entries.sort(key=lambda item: item[0])
    return entries


def _dist_info_name() -> str:
    return f"{FEATURE_LIBRARY_DISTRIBUTION.replace('-', '_')}-{FEATURE_LIBRARY_VERSION}.dist-info"


def _metadata() -> bytes:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {FEATURE_LIBRARY_DISTRIBUTION}",
        f"Version: {FEATURE_LIBRARY_VERSION}",
        "Summary: Standalone XRD scientific feature library for Bremen inference releases",
        "Requires-Python: >=3.13,<3.14",
    ]
    lines.extend(f"Requires-Dist: {requirement}" for requirement in FEATURE_LIBRARY_REQUIRES_DIST)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _wheel_metadata() -> bytes:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: bremen-release-build\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")


def _iter_members(source_root: Path):
    for archive_name, source in feature_library_package_files(source_root):
        yield archive_name, source.read_bytes()
    dist_info = _dist_info_name()
    yield f"{dist_info}/METADATA", _metadata()
    yield f"{dist_info}/WHEEL", _wheel_metadata()


def build_feature_library_wheel(
    output_dir: str | os.PathLike[str],
    *,
    source_root: str | os.PathLike[str] | None = None,
) -> WheelBuildResult:
    """Build the deterministic feature-library wheel and return its hash/members."""
    root = Path(source_root) if source_root is not None else _FEATURE_LIBRARY_SOURCE_ROOT
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{FEATURE_LIBRARY_DISTRIBUTION.replace('-', '_')}-"
        f"{FEATURE_LIBRARY_VERSION}-py3-none-any.whl"
    )
    destination = output / filename

    members = list(_iter_members(root))
    record_name = f"{_dist_info_name()}/RECORD"
    record_lines = [
        f"{name},{_record_hash(data)},{len(data)}" for name, data in members
    ]
    record_lines.append(f"{record_name},,")
    record = ("\n".join(record_lines) + "\n").encode("utf-8")
    members.append((record_name, record))

    with zipfile.ZipFile(destination, "w") as archive:
        for name, data in members:
            archive.writestr(_zip_info(name), data)

    payload = destination.read_bytes()
    return WheelBuildResult(
        path=destination,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        members=tuple(name for name, _ in members),
    )
