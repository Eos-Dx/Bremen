"""Real H5 subset reader test — superseded by synthetic preflight tests.

The historically tracked real H5 subset has been removed from the
repository (PR 0037 artifact cleanup).  This test now runs as an
optional opt-in smoke test.

Set BREMEN_H5_PREFLIGHT_SMOKE_PATH to the path of the external H5
subset to run this test.  When the env var is absent, the test is
skipped.

This test is superseded by tests/test_bremen_h5_preflight.py which
provides comprehensive synthetic preflight coverage.  No clinical
validation claims are made.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="BREMEN_H5_PREFLIGHT_SMOKE_PATH not set — skipping real subset smoke test",
)


def test_real_subset_schema_inspection():
    """Optional smoke test: inspect real H5 metadata/schema.

    Skips when BREMEN_H5_PREFLIGHT_SMOKE_PATH is not set.
    No clinical validation assertions.
    """
    import h5py  # noqa: PLC0415

    h5_path = Path(os.environ["BREMEN_H5_PREFLIGHT_SMOKE_PATH"])
    assert h5_path.is_file(), f"Real H5 not found: {h5_path}"

    with h5py.File(h5_path, "r") as f:
        # Inspect top-level groups
        top_keys = set(f.keys())
        assert "patient" in top_keys, "Expected /patient group"
        assert "scans" in top_keys, "Expected /scans group"
        assert "target" in f["/scans"], "Expected /scans/target group"
        assert "contralateral" in f["/scans"], "Expected /scans/contralateral group"

        # Read metadata — no clinical assertions
        _patient_id = f["/patient/id"][()].decode("utf-8") if isinstance(
            f["/patient/id"][()], bytes
        ) else str(f["/patient/id"][()])

        _target_side = f["/scans/target/side"][()].decode("utf-8") if isinstance(
            f["/scans/target/side"][()], bytes
        ) else str(f["/scans/target/side"][()])

        _contralateral_side = f["/scans/contralateral/side"][()].decode("utf-8") if isinstance(
            f["/scans/contralateral/side"][()], bytes
        ) else str(f["/scans/contralateral/side"][()])

    # No clinical validity assertion — structural only
    assert isinstance(_patient_id, str)
    assert isinstance(_target_side, str)
    assert isinstance(_contralateral_side, str)
