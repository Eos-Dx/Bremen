"""Bremen demo readiness capture module.

Writes a reusable demo readiness packet from a demo-run result dict
to a specified directory.  Produces three files:

- ``bremen-demo-summary.txt`` — Pretty presentation text.
- ``bremen-demo-evidence.json`` — Validated evidence/result JSON.
- ``bremen-demo-manifest.json`` — Capture metadata (always last, atomic).

All files include ``technical_demo_only``, Bremen identity, safety notes.

Standard library only — no third-party dependencies.

Safety
------
- No model loading or deserialization.
- No network calls.
- No H5 reads or writes.
- No clinical diagnosis or replacement claims.
- ``technical_demo_only: true`` in every capture file.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_CAPTURE_VERSION = "v0.1"

# Default filenames
FILE_SUMMARY = "bremen-demo-summary.txt"
FILE_EVIDENCE = "bremen-demo-evidence.json"
FILE_MANIFEST = "bremen-demo-manifest.json"

# File descriptions for manifest
_FILE_DESCRIPTIONS: dict[str, str] = {
    FILE_SUMMARY: "Pretty text summary",
    FILE_EVIDENCE: "Evidence/result JSON",
    FILE_MANIFEST: "Capture metadata",
}

# Safety notes used in manifest
_DEFAULT_SAFETY_NOTES: list[str] = [
    "Technical product demo only — not a clinical result.",
    "Not clinically validated.",
    "Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.",
    "All clinical decisions must be made by qualified clinicians.",
]

# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------


def build_capture_manifest(
    result: dict[str, Any],
    files: list[dict[str, str]],
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build a demo capture manifest dict.

    Parameters
    ----------
    result : The demo-run result dict.
    files : A list of dicts with ``filename`` and ``description`` keys.
    generated_at_utc : Explicit ISO-8601 UTC timestamp for determinism
        in tests.  If ``None``, uses the current time.

    Returns
    -------
    A manifest dict with ``demo_capture_version``, ``generated_at_utc``,
    ``technical_demo_only``, ``product``, ``status``, ``request_id``,
    ``files``, and ``safety_notes``.
    """
    if generated_at_utc is None:
        generated_at_utc = datetime.now(timezone.utc).isoformat()

    return {
        "demo_capture_version": DEMO_CAPTURE_VERSION,
        "generated_at_utc": generated_at_utc,
        "technical_demo_only": True,
        "product": "Bremen",
        "status": result.get("status", "fail"),
        "request_id": result.get("request_id"),
        "files": list(files),
        "safety_notes": list(_DEFAULT_SAFETY_NOTES),
    }


# ---------------------------------------------------------------------------
# Fallback summary text (used when --pretty was not provided)
# ---------------------------------------------------------------------------


def _build_fallback_summary(result: dict[str, Any]) -> str:
    """Build a minimal safe summary text when ``--pretty`` was not used.

    Parameters
    ----------
    result : The demo-run result dict.

    Returns
    -------
    A plain-text summary with Bremen identity, status, and safety notice.
    """
    status = str(result.get("status", "?")).upper()
    request_id = result.get("request_id", "N/A")
    base_url = result.get("base_url", "N/A")
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  BREMEN PRODUCT DEMO — CAPTURE SUMMARY")
    lines.append("  Technical demo only — not a clinical result.")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Product       : Bremen")
    lines.append(f"  Status        : {status}")
    lines.append(f"  Base URL      : {base_url}")
    lines.append(f"  Request ID    : {request_id}")
    lines.append("")
    lines.append("-" * 60)
    lines.append(
        "  This is a technical product demo. Not a clinical result."
    )
    lines.append(
        "  Not clinically validated. Does not replace MRI, biopsy,"
    )
    lines.append(
        "  radiologist, clinician, or clinical judgment."
    )
    lines.append("-" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------


def write_demo_capture(
    result: dict[str, Any],
    capture_dir: str,
    *,
    pretty_text: str | None = None,
) -> dict[str, Any]:
    """Write the demo readiness capture files to *capture_dir*.

    Creates three files in *capture_dir*:

    - ``bremen-demo-summary.txt`` — Pretty text or fallback summary.
    - ``bremen-demo-evidence.json`` — Full result dict as JSON.
    - ``bremen-demo-manifest.json`` — Capture metadata (written last
      to reduce the chance of an incomplete set).

    Parameters
    ----------
    result : The demo-run result dict.
    capture_dir : Directory path to write files into.  Created
        (including parents) if it does not exist.
    pretty_text : Optional pre-formatted pretty text.  If ``None``,
        a minimal fallback summary is written.

    Returns
    -------
    The manifest dict (which was also written to
    ``bremen-demo-manifest.json``).

    Raises
    ------
    FileExistsError
        If *capture_dir* exists as a regular file, or if any of the
        three output files already exist in the directory.
    OSError
        If directory creation or file writing fails.
    """
    dir_path = Path(capture_dir)

    # Check if capture_dir exists as a file
    if dir_path.exists() and not dir_path.is_dir():
        raise FileExistsError(
            f"Capture directory path exists as a file: {capture_dir}"
        )

    # Check for existing output files before creating directory
    existing_files: list[str] = []
    for fname in (FILE_SUMMARY, FILE_EVIDENCE, FILE_MANIFEST):
        if (dir_path / fname).exists():
            existing_files.append(fname)
    if existing_files:
        raise FileExistsError(
            f"Output files already exist in {capture_dir}: "
            f"{', '.join(existing_files)}. "
            f"Remove the directory or files first."
        )

    # Create directory (including parents)
    dir_path.mkdir(parents=True, exist_ok=True)

    # ---- Write summary ----
    text = pretty_text if pretty_text else _build_fallback_summary(result)
    (dir_path / FILE_SUMMARY).write_text(text, encoding="utf-8")

    # ---- Write evidence JSON ----
    evidence_json = json.dumps(
        result, indent=2, ensure_ascii=False, default=str
    )
    (dir_path / FILE_EVIDENCE).write_text(evidence_json, encoding="utf-8")

    # ---- Build and write manifest (last — atomic signal) ----
    file_list = [
        {"filename": fname, "description": _FILE_DESCRIPTIONS[fname]}
        for fname in (FILE_SUMMARY, FILE_EVIDENCE, FILE_MANIFEST)
    ]
    manifest = build_capture_manifest(result, file_list)
    manifest_json = json.dumps(
        manifest, indent=2, ensure_ascii=False, default=str
    )
    (dir_path / FILE_MANIFEST).write_text(manifest_json, encoding="utf-8")

    return manifest
