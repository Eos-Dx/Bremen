"""Release-build provenance capture.

Provenance is captured from observed distribution metadata at build time; it
is never inferred from a version string or fabricated.  When VCS metadata is
absent, ``source_commit`` is recorded as ``null`` and callers must decide
whether that is acceptable for the release they are building.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

__all__ = [
    "KNOWN_PREPROCESSING_COMMITS",
    "capture_environment_closure",
    "capture_preprocessing_provenance",
]

#: Established source-commit requirements.  The v0.1.7-beta tag moved during
#: IR-01; the artifact provenance pin (and the Bremen worker's historical
#: check) require this exact commit.  The v0.1.9-beta commit is the observed
#: value for that tag at build time and is recorded, not invented.
KNOWN_PREPROCESSING_COMMITS: dict[str, str] = {
    "v0.1.7-beta": "45d5568248e9774b7938a36e028d80e72b130b19",
    "v0.1.9-beta": "88dcaa277c5a0d4be2ab637bc5827a14bd106bea",
}

_EXCLUDED_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})

_CAPTURE_SCRIPT = r"""
import json
from importlib.metadata import distributions
items = []
for dist in distributions():
    name = (dist.metadata.get("Name") or "").strip()
    if not name:
        continue
    items.append({"name": name, "version": dist.version})
print(json.dumps(sorted(items, key=lambda item: item["name"].lower())))
"""

_PROVENANCE_SCRIPT = r"""
import json
from importlib.metadata import distribution
dist = distribution("xrd-preprocessing")
direct = {}
try:
    direct = json.loads(dist.read_text("direct_url.json") or "{}")
except Exception:
    direct = {}
print(json.dumps({
    "distribution": "xrd-preprocessing",
    "version": dist.version,
    "url": direct.get("url"),
    "vcs": (direct.get("vcs_info") or {}).get("vcs"),
    "source_commit": (direct.get("vcs_info") or {}).get("commit_id"),
    "requested_revision": (direct.get("vcs_info") or {}).get("requested_revision"),
}))
"""


def capture_environment_closure(python_executable: str) -> list[dict[str, str]]:
    """Read the exact installed distribution closure of one interpreter."""
    completed = subprocess.run(
        [python_executable, "-I", "-c", _CAPTURE_SCRIPT],
        text=True, capture_output=True, check=False, timeout=120,
    )
    if completed.returncode:
        raise RuntimeError(
            f"could not inspect environment {python_executable!r}"
        )
    items = json.loads(completed.stdout)
    return [
        item for item in items
        if item["name"].lower() not in _EXCLUDED_DISTRIBUTIONS
    ]


def capture_preprocessing_provenance(
    python_executable: str, release_tag: str,
    *, source_commit: str | None = None,
) -> dict[str, Any]:
    """Capture explicit preprocessing provenance suitable for wheel installs.

    ``direct_url.json`` is only one observation source.  A wheel-based install
    has no VCS metadata, so the release build may supply the source commit it
    actually built the wheel from (``source_commit``).  That value is checked
    against the established commit map before it is recorded; it is never
    invented.  The resulting record travels with the release.
    """
    completed = subprocess.run(
        [python_executable, "-I", "-c", _PROVENANCE_SCRIPT],
        text=True, capture_output=True, check=False, timeout=120,
    )
    if completed.returncode:
        raise RuntimeError(
            f"could not inspect xrd-preprocessing in {python_executable!r}"
        )
    observed = json.loads(completed.stdout)
    expected_commit = KNOWN_PREPROCESSING_COMMITS.get(release_tag)
    observed_commit = observed.get("source_commit")
    captured_via = "importlib.metadata direct_url.json"
    if observed_commit is None and source_commit:
        if expected_commit and source_commit != expected_commit:
            raise RuntimeError(
                f"explicit {release_tag} source commit does not satisfy the "
                f"established requirement {expected_commit}"
            )
        observed_commit = source_commit
        captured_via = "explicit build input (wheelhouse source commit)"
    if expected_commit and observed_commit and observed_commit != expected_commit:
        raise RuntimeError(
            f"{release_tag} source commit does not satisfy the established "
            f"requirement {expected_commit}"
        )
    if release_tag == "v0.1.7-beta" and observed_commit != expected_commit:
        raise RuntimeError(
            "v0.1.7-beta requires its established source commit; refusing to "
            "record a missing or different provenance"
        )
    return {
        "schema_version": "bremen.preprocessing-provenance.v1",
        "release_tag": release_tag,
        "distribution": observed["distribution"],
        "version": observed["version"],
        "source_repository": observed.get("url"),
        "source_commit": observed_commit,
        "requested_revision": observed.get("requested_revision"),
        "captured_via": captured_via,
        "hash_locked_wheel": observed.get("vcs") is None,
    }


def read_installed_provenance(path: str) -> dict[str, Any]:
    """Read an explicit provenance record shipped with a release."""
    with open(path, "r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError("provenance record must be a JSON object")
    return data
