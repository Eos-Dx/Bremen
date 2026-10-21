"""Reproducible wheel construction for the standalone ML plugin.

The plugin wheel is assembled from an explicit allowlist of repository
packages (neutral contracts, scientific model packages, the package bridge and
the plugin module).  It never includes ``bremen.platform``, ``bremen.api`` or
the rest of the application distribution.

The builder writes a PEP 427 wheel directly (a zip with ``.dist-info`` and
``RECORD``) using fixed entry timestamps and sorted members, so identical
sources always produce an identical wheel SHA-256.  No build backend, network
access or dependency resolution is involved.
"""

from __future__ import annotations

import base64
import hashlib
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from bremen.ml_plugin import PLUGIN_DISTRIBUTION, PLUGIN_VERSION

__all__ = [
    "PLUGIN_REQUIRES_DIST",
    "WheelBuildResult",
    "build_plugin_wheel",
    "plugin_package_files",
]

_FIXED_DATE = (2020, 1, 1, 0, 0, 0)
_SOURCE_ROOT = Path(__file__).resolve().parents[2]  # <repo>/src

#: Exact observed runtime closure required by standalone inference.  These are
#: the versions the scientific artifacts and IR-01 baselines were executed
#: with; they are intentionally not loosened for packaging convenience.
PLUGIN_REQUIRES_DIST: tuple[str, ...] = (
    "numpy==2.5.4",
    "pandas==3.0.6",
    "scipy==1.18.1",
    "scikit-learn==1.9.0",
    "joblib==1.6.0",
    "h5py==3.16.0",
    "PyYAML==6.0.3",
)

#: Repository modules intentionally shipped in the plugin wheel.
_PLUGIN_MODULE_PATHS: tuple[str, ...] = (
    "bremen/__init__.py",
    "bremen/model_packages_bridge.py",
)
_PLUGIN_PACKAGE_DIRS: tuple[str, ...] = (
    "bremen/contracts",
    "bremen/model_packages",
    "bremen/ml_plugin",
)
#: Never shipped, even if present under one of the allowlisted directories.
_EXCLUDED_PART_PREFIXES = ("__pycache__",)
_EXCLUDED_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache"})


@dataclass(frozen=True)
class WheelBuildResult:
    path: Path
    sha256: str
    size_bytes: int
    members: tuple[str, ...]


def plugin_package_files(source_root: Path | None = None) -> list[tuple[str, Path]]:
    """Return ``(archive_name, source_path)`` pairs for the plugin wheel."""
    root = Path(source_root) if source_root is not None else _SOURCE_ROOT
    entries: list[tuple[str, Path]] = []
    for relative in _PLUGIN_MODULE_PATHS:
        source = root / relative
        if not source.is_file():
            raise FileNotFoundError(f"plugin source missing: {source}")
        entries.append((relative, source))
    for relative_dir in _PLUGIN_PACKAGE_DIRS:
        directory = root / relative_dir
        if not directory.is_dir():
            raise FileNotFoundError(f"plugin package missing: {directory}")
        for source in sorted(directory.rglob("*.py")):
            parts = source.relative_to(root).parts
            if any(part in _EXCLUDED_DIR_NAMES for part in parts):
                continue
            if any(part.startswith(_EXCLUDED_PART_PREFIXES) for part in parts):
                continue
            entries.append(("/".join(parts), source))
    entries.sort(key=lambda item: item[0])
    return entries


def _dist_info_name() -> str:
    return f"{PLUGIN_DISTRIBUTION.replace('-', '_')}-{PLUGIN_VERSION}.dist-info"


def _metadata() -> bytes:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {PLUGIN_DISTRIBUTION}",
        f"Version: {PLUGIN_VERSION}",
        "Summary: Standalone ML plugin for Bremen inference releases",
        "Requires-Python: >=3.13,<3.14",
    ]
    lines.extend(f"Requires-Dist: {requirement}" for requirement in PLUGIN_REQUIRES_DIST)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _wheel_metadata() -> bytes:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: bremen-release-build\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")


def _entry_points() -> bytes:
    return (
        "[console_scripts]\n"
        "bremen-ml-worker = bremen.ml_plugin.entrypoint:main\n"
    ).encode("utf-8")


def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    encoded = base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=")
    return f"sha256={encoded.decode('ascii')}"


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    info.create_system = 3
    return info


def _iter_members(source_root: Path) -> Iterable[tuple[str, bytes]]:
    for archive_name, source in plugin_package_files(source_root):
        yield archive_name, source.read_bytes()
    dist_info = _dist_info_name()
    yield f"{dist_info}/METADATA", _metadata()
    yield f"{dist_info}/WHEEL", _wheel_metadata()
    yield f"{dist_info}/entry_points.txt", _entry_points()


def build_plugin_wheel(
    output_dir: str | os.PathLike[str],
    *,
    source_root: str | os.PathLike[str] | None = None,
) -> WheelBuildResult:
    """Build the deterministic plugin wheel and return its hash and members."""
    root = Path(source_root) if source_root is not None else _SOURCE_ROOT
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{PLUGIN_DISTRIBUTION.replace('-', '_')}-"
        f"{PLUGIN_VERSION}-py3-none-any.whl"
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
