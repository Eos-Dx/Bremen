"""Validated request metadata carried from HTTP to application services."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisParameters:
    """Validated inbound request for Aramina provider contract.

    All fields are frozen after creation.  No raw paths, S3 keys,
    checksums, tokens, passwords, or model internals are stored.
    """

    container_id: str
    source_id: str
    patient_id: str
    target_side: str  # Normalized to lowercase: "left" or "right"
    analysis_author: str = ""
    prediction_comment: str = ""
