"""Explicit legacy canonical adapter. Never used for raw-capable Bremen packages.

Aramina still checks canonical QC before its artifact-owned raw preprocessing.
Keep this behavior until independent raw-only scientific parity is established.
"""

import logging
import h5py
from bremen.platform.sources.legacy_layouts import detect_layout
from bremen.contracts.canonical_input import CanonicalXRDCase, validate_canonical_case

_log = logging.getLogger(__name__)


def normalize_legacy_input(
    h5_path: str,
    *,
    request_id: str = "",
    workflow_id: str = "",
) -> CanonicalXRDCase:
    """Open H5, detect layout, normalize to canonical.

    No patient identifiers are stored in the canonical case.
    The source H5 is opened read-only and not modified.
    """
    with h5py.File(h5_path, "r") as h5_file:
        adapter = detect_layout(h5_file)
        normalizer = adapter.normalize_to_canonical
        if workflow_id == "bremen":
            normalizer = getattr(adapter, "normalize_bremen_to_canonical", normalizer)
        case = normalizer(h5_file)

    _log.debug(
        "runtime.normalization.layout_detected\t"
        "stage=normalization\tstatus=layout_detected\t"
        "layout=%s\tlayout_version=%s\trequest_id=%s",
        case.source_layout,
        case.source_layout_version,
        request_id,
    )

    # Validate the canonical case
    validate_canonical_case(case)

    return case


# ---------------------------------------------------------------------------
