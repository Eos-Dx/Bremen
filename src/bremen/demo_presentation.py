"""Bremen demo presentation formatter.

Produces stable, deterministic plain-text presentation output from
a Bremen demo-run result dict.  Suitable for product-owner demos,
operator checks, release-walkthrough output, and future Model Ops
console content.

No colors, no terminal codes, no HTML, no deployment assumptions.

Standard library only — no third-party dependencies.

Safety
------
- No model loading or deserialization.
- No H5 reads or writes.
- No AWS/S3/network calls.
- No clinical diagnosis or replacement claims.
- ``technical_demo_only`` prominent in output header and footer.
"""

from __future__ import annotations

from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Section separator constants
# ---------------------------------------------------------------------------

_HEADER_SEPARATOR = "=" * 79
_SECTION_WIDTH = 79
_INDENT = "  "

# ---------------------------------------------------------------------------
# Value formatting helpers
# ---------------------------------------------------------------------------


def _fmt(key: str, value: object, indent: int = 0) -> str:
    """Format a key-value pair as a line.

    Parameters
    ----------
    key : The label string.
    value : The value to format.
    indent : Number of additional indentation levels (each 2 spaces).

    Returns
    -------
    A single formatted line.
    """
    prefix = _INDENT * indent
    return f"{prefix}{key:<14}: {value}"


def _fmt_pass_fail(value: str) -> str:
    """Format a pass/fail check value with visual indicator."""
    if value == "pass":
        return "PASS"
    if value == "fail":
        return "FAIL"
    return value.upper() if value else "?"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_pretty(result: Mapping[str, Any]) -> str:
    """Format a demo-run result dict as a plain-text presentation.

    Parameters
    ----------
    result : A dict from ``run_demo()`` or ``run_demo_smoke()``.
        Must contain at minimum ``technical_demo_only`` and
        ``status`` keys.

    Returns
    -------
    A multi-line plain-text string suitable for printing to a
    terminal or log file.

    Raises
    ------
    TypeError
        If *result* is not a mapping.
    """
    if not isinstance(result, Mapping):
        raise TypeError("result must be a Mapping")

    lines: list[str] = []

    # ---- Header ----
    lines.append(_HEADER_SEPARATOR)
    lines.append(f"{_INDENT}BREMEN PRODUCT DEMO")
    lines.append(
        f"{_INDENT}Technical demo only — not a clinical result."
    )
    lines.append(_HEADER_SEPARATOR)
    lines.append("")

    # ---- Overview ----
    status = str(result.get("status", "?")).upper()
    checks = result.get("checks", {})
    checks_str = "  ".join(
        f"{k}: {_fmt_pass_fail(v)}"
        for k, v in sorted(checks.items())
    )
    lines.append(_fmt("Product", "Bremen"))
    lines.append(
        _fmt("Question", "Should patient continue to MRI?")
    )
    lines.append(
        _fmt("Base URL", result.get("base_url", "N/A"))
    )
    lines.append(
        _fmt("Request ID", result.get("request_id", "N/A"))
    )
    lines.append(
        _fmt("Total Status", f"{status}  [{checks_str}]")
    )
    lines.append("")

    # ---- Health section ----
    lines.append(_format_section_header("Health"))
    health = result.get("health", {})
    if health.get("error"):
        lines.append(_fmt("Error", health["error"]))
    else:
        lines.append(
            _fmt("Status", health.get("status", "N/A"))
        )
        model_ready = health.get("model_ready")
        if model_ready is not None:
            lines.append(_fmt("Model Ready", "yes" if model_ready else "no"))
        lines.append(
            _fmt("Service", health.get("service", "N/A"))
        )
        lines.append(
            _fmt("Version", health.get("version", "N/A"))
        )
    lines.append("")

    # ---- Model / Version section ----
    lines.append(_format_section_header("Model / Version"))
    mv = result.get("model_version", {})
    if mv.get("error"):
        lines.append(_fmt("Error", mv["error"]))
    else:
        lines.append(
            _fmt("Status", mv.get("model_status", "N/A"))
        )
        lines.append(
            _fmt("Version", mv.get("model_version", "N/A"))
        )
        checksum = mv.get("model_checksum")
        if checksum:
            # Show abbreviated checksum for readability
            short = f"{checksum[:4]}...{checksum[-4:]}"
            lines.append(_fmt("Checksum", short))
        lines.append(
            _fmt("Feature Schema",
                 mv.get("feature_schema_version", "N/A"))
        )
    lines.append("")

    # ---- Prediction section ----
    lines.append(_format_section_header("Prediction"))
    pred = result.get("prediction", {})
    pred_status = pred.get("status", "N/A")
    lines.append(_fmt("Status", pred_status))
    if pred.get("reason"):
        lines.append(_fmt("Reason", pred["reason"]))
    if pred.get("job_id"):
        lines.append(_fmt("Job ID", pred["job_id"]))
    if pred.get("poll_status"):
        lines.append(_fmt("Poll Status", pred["poll_status"]))
    if pred.get("qc_status"):
        lines.append(_fmt("QC Status", pred["qc_status"]))
    if pred.get("decision_support"):
        ds = pred["decision_support"]
        if ds.get("p_mri_needed") is not None:
            lines.append(
                _fmt("p_mri_needed",
                     f"{ds['p_mri_needed']:.3f}")
            )
        if ds.get("triage_recommendation"):
            lines.append(
                _fmt("Recommendation",
                     ds["triage_recommendation"])
            )
    if pred.get("http_status"):
        lines.append(
            _fmt("HTTP Status", str(pred["http_status"]))
        )
    if pred.get("error"):
        lines.append(_fmt("Error", pred["error"]))
    lines.append("")

    # ---- Evidence Bundle section ----
    lines.append(_format_section_header("Evidence Bundle"))
    evidence = result.get("evidence", {})
    if evidence:
        lines.append(
            _fmt("Version", evidence.get("evidence_version", "N/A"))
        )
        lines.append(
            _fmt("Scenario", evidence.get("scenario_id", "N/A"))
        )
        safety_notes = evidence.get("safety_notes", [])
        if safety_notes:
            lines.append(_fmt("Safety Notes", ""))
            for i, note in enumerate(safety_notes, 1):
                # Wrap long notes for readability
                if len(note) > 70:
                    # Split into two lines at a natural break
                    mid = note.rfind(" ", 0, 65)
                    if mid < 30:
                        mid = note.rfind(",", 0, 65)
                    if mid >= 30:
                        lines.append(
                            f"{_INDENT}  {i}. {note[:mid]}"
                        )
                        lines.append(
                            f"{_INDENT}     {note[mid+1:]}"
                        )
                    else:
                        lines.append(f"{_INDENT}  {i}. {note}")
                else:
                    lines.append(f"{_INDENT}  {i}. {note}")
    else:
        lines.append(
            _fmt("Status", "not available")
        )
    lines.append("")

    # ---- Warnings section ----
    lines.append(_format_section_header("Warnings"))
    warnings = result.get("warnings", [])
    if warnings:
        for w in warnings:
            lines.append(f"{_INDENT}- {w}")
    else:
        lines.append(f"{_INDENT}(none)")
    lines.append("")

    # ---- Footer ----
    lines.append(_HEADER_SEPARATOR)
    lines.append(
        "  This is a technical product demo. Not a clinical result."
    )
    lines.append(
        "  Not clinically validated. Does not replace MRI, biopsy,"
    )
    lines.append(
        "  radiologist, clinician, or clinical judgment."
    )
    lines.append(_HEADER_SEPARATOR)

    return "\n".join(lines)


def format_pretty_header(result: Mapping[str, Any]) -> str:
    """Return just the header section of the pretty output.

    Parameters
    ----------
    result : A demo-run result dict.

    Returns
    -------
    The header section as a plain-text string.
    """
    if not isinstance(result, Mapping):
        raise TypeError("result must be a Mapping")

    lines: list[str] = []
    lines.append(_HEADER_SEPARATOR)
    lines.append(f"{_INDENT}BREMEN PRODUCT DEMO")
    lines.append(
        f"{_INDENT}Technical demo only — not a clinical result."
    )
    lines.append(_HEADER_SEPARATOR)
    return "\n".join(lines)


def format_pretty_footer(result: Mapping[str, Any]) -> str:
    """Return just the footer section of the pretty output.

    Parameters
    ----------
    result : A demo-run result dict (used for context but currently
        the footer is static).

    Returns
    -------
    The footer section as a plain-text string.
    """
    lines: list[str] = []
    lines.append(_HEADER_SEPARATOR)
    lines.append(
        "  This is a technical product demo. Not a clinical result."
    )
    lines.append(
        "  Not clinically validated. Does not replace MRI, biopsy,"
    )
    lines.append(
        "  radiologist, clinician, or clinical judgment."
    )
    lines.append(_HEADER_SEPARATOR)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_section_header(title: str) -> str:
    """Format a section header line.

    Returns
    -------
    A line like "  -- Title -----------------------------------------------"
    """
    prefix = f"{_INDENT}-- {title} "
    # Fill remaining space with dashes
    fill_width = _SECTION_WIDTH - len(prefix)
    if fill_width < 1:
        fill_width = 1
    return f"{prefix}{'-' * fill_width}"
