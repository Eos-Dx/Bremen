"""Guardrail tests for container dependency hygiene (PR 0021).

Verifies:
- requirements.txt does not contain /Users/ (local macOS home paths)
- requirements.txt does not contain /home/ (local Linux home paths)
- requirements.txt does not contain -e  (editable local paths)
- requirements.txt does not contain local machine paths to container
- If container Git dependency exists, it references github.com/Eos-Dx/container.git
- If container Git dependency exists, it uses feat/v0_3-eoscan-session-container
- ROADMAP.md still has G-DEP-1
- G-DEP-1 remains OPEN (not marked DECIDED)
- No source/API/model code is touched by this PR
- No H5/HDF5/model artifacts are introduced
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
ROADMAP = ROOT / "ROADMAP.md"


# ---------------------------------------------------------------------------
# requirements.txt local-path absence
# ---------------------------------------------------------------------------


def test_no_users_path():
    """requirements.txt must not contain any /Users/ local paths."""
    content = REQUIREMENTS.read_text(encoding="utf-8")
    assert "/Users/" not in content, (
        "requirements.txt contains a /Users/ local path"
    )


def test_no_home_path():
    """requirements.txt must not contain any /home/ local paths."""
    content = REQUIREMENTS.read_text(encoding="utf-8")
    assert "/home/" not in content, (
        "requirements.txt contains a /home/ local path"
    )


def test_no_editable_local_path():
    """requirements.txt must not contain editable absolute-local paths."""
    content = REQUIREMENTS.read_text(encoding="utf-8")
    assert "-e " not in content, (
        "requirements.txt contains an editable (-e) path"
    )


def test_no_local_container_path():
    """requirements.txt must not reference a local container directory."""
    content = REQUIREMENTS.read_text(encoding="utf-8")
    for prohibited in ["/Users/sad/dev/container", "/home/"]:
        assert prohibited not in content, (
            f"requirements.txt contains prohibited path: {prohibited}"
        )


# ---------------------------------------------------------------------------
# Container git dependency
# ---------------------------------------------------------------------------


def test_container_git_url_if_present():
    """If requirements.txt has a container dep, it must use github.com."""
    content = REQUIREMENTS.read_text(encoding="utf-8")
    if "container" not in content.lower():
        pytest.skip("No container dependency in requirements.txt")

    assert "github.com/Eos-Dx/container.git" in content, (
        "Container dependency must reference github.com/Eos-Dx/container.git"
    )


def test_container_uses_immutable_tag():
    """Container dependency must use immutable v0.3.0 tag — G-DEP-1 is CLOSED."""
    content = REQUIREMENTS.read_text(encoding="utf-8")
    if "container" not in content.lower():
        pytest.skip("No container dependency in requirements.txt")

    assert "v0.3.0" in content, (
        "Container dependency must use v0.3.0 tag, not feature branch"
    )


def test_container_not_pinned_to_main():
    """Container dependency must not be re-pinned to main."""
    content = REQUIREMENTS.read_text(encoding="utf-8")
    if "container" not in content.lower():
        pytest.skip("No container dependency in requirements.txt")

    lines = [
        line.strip()
        for line in content.splitlines()
        if "container" in line.lower()
    ]
    for line in lines:
        assert "@main" not in line, (
            f"Container dependency must not be re-pinned to main: {line}"
        )


# ---------------------------------------------------------------------------
# G-DEP-1 boundary
# ---------------------------------------------------------------------------


def test_g_dep_1_still_present():
    """ROADMAP.md must still reference G-DEP-1."""
    content = ROADMAP.read_text(encoding="utf-8")
    assert "G-DEP-1" in content, (
        "ROADMAP.md must still contain G-DEP-1"
    )


def test_g_dep_1_is_closed():
    """G-DEP-1 must be CLOSED — feature branch merged, v0.3.0 tag exists."""
    content = ROADMAP.read_text(encoding="utf-8")
    # Find the Decision Gate Register row for G-DEP-1 and check it has CLOSED
    found_gate = False
    found_closed = False
    for line in content.splitlines():
        if "G-DEP-1" in line:
            found_gate = True
            if "CLOSED" in line:
                found_closed = True
    assert found_gate, "G-DEP-1 not found in ROADMAP.md"
    assert found_closed, "G-DEP-1 is not marked CLOSED in ROADMAP.md"


# ---------------------------------------------------------------------------
# Scope boundary
# ---------------------------------------------------------------------------


def test_no_h5_model_artifacts_introduced():
    """No new H5/HDF5/model artifacts should exist at repo root level."""
    root_files = list(ROOT.glob("*.h5"))
    root_files += list(ROOT.glob("*.hdf5"))
    root_files += list(ROOT.glob("*.joblib"))
    root_files += list(ROOT.glob("*.pkl"))
    root_files += list(ROOT.glob("*.npy"))
    root_files += list(ROOT.glob("*.npz"))
    # The only allowed data file is the pre-existing test fixture
    allowed = {ROOT / "tests" / "data" / "aramis_real_h5_subset_20260128_5_patients.h5"}
    found = set(root_files)
    unexpected = found - allowed
    assert not unexpected, (
        f"Unexpected model/data artifacts at root: {unexpected}"
    )
