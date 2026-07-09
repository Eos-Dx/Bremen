"""System-of-record boundary skeleton for future Matador integration.

PR0052 introduces a safe typed seam for future Matador/system-of-record
integration.  No network, no credentials, no real adapter.

Current request modes (``h5_path``, ``h5_uri``) remain supported and
unchanged.  This module is a future integration boundary — the runtime
does not yet use ``RecordResolver`` for request processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Opaque external record reference
# ---------------------------------------------------------------------------


class ExternalRecordRef(str):
    """An opaque system-of-record reference string.

    Validation rules:
    - Must not be empty.
    - Must not be a local absolute filesystem path (``/``-prefixed).
    - Must not be a full S3 URI (``s3://``-prefixed).
    - Must not contain obvious raw patient identifiers (``Nova_`` prefix).
    """

    def __new__(cls, value: str) -> ExternalRecordRef:
        _validate_ref(value)
        return super().__new__(cls, value)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class RefValidationError(ValueError):
    """Raised when an external record reference is invalid."""


FORBIDDEN_REF_PREFIXES = (
    "/",    # absolute local path
    "s3:/",  # S3 URI (s3://)
)

FORBIDDEN_REF_PATTERNS = (
    "Nova_",
)


def _validate_ref(ref: str) -> None:
    """Validate a record reference string.

    Raises
    ------
    RefValidationError
        If the ref is empty, an absolute local path, an S3 URI, or
        contains a forbidden pattern.
    """
    if not ref:
        raise RefValidationError("Record ref must not be empty")

    ref_stripped = ref.strip()

    if not ref_stripped:
        raise RefValidationError("Record ref must not be whitespace-only")

    for prefix in FORBIDDEN_REF_PREFIXES:
        if ref_stripped.startswith(prefix):
            raise RefValidationError(
                f"Record ref must not be a local path or S3 URI"
            )

    for pattern in FORBIDDEN_REF_PATTERNS:
        if pattern in ref_stripped:
            raise RefValidationError(
                "Record ref must not contain raw patient identifiers"
            )


# ---------------------------------------------------------------------------
# Resolved input
# ---------------------------------------------------------------------------


@dataclass
class ResolvedInput:
    """The result of resolving a system-of-record reference.

    Exactly one of ``h5_uri`` or ``h5_path`` must be provided.
    """

    target_scan_ref: str
    control_scan_ref: str
    h5_uri: str | None = None
    h5_path: str | None = None
    h5_checksum: str | None = None

    def __post_init__(self) -> None:
        _validate_resolved_input(
            h5_uri=self.h5_uri,
            h5_path=self.h5_path,
        )


class ResolvedInputError(ValueError):
    """Raised when ``ResolvedInput`` has invalid source configuration."""


def _validate_resolved_input(
    h5_uri: str | None,
    h5_path: str | None,
) -> None:
    """Validate that exactly one H5 source is provided."""
    if h5_uri is not None and h5_path is not None:
        raise ResolvedInputError(
            "Exactly one of h5_uri or h5_path must be provided, not both"
        )
    if h5_uri is None and h5_path is None:
        raise ResolvedInputError(
            "Either h5_uri or h5_path must be provided"
        )


# ---------------------------------------------------------------------------
# Record resolver protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RecordResolver(Protocol):
    """Protocol for resolving a system-of-record ref to a ResolvedInput.

    Implementations may be:
    - ``UnconfiguredRecordResolver`` (current stub)
    - Future Matador resolver (not implemented in PR0052)
    - In-memory test resolver
    """

    def resolve(
        self,
        ref: ExternalRecordRef,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> ResolvedInput:
        """Resolve a system-of-record ref to a concrete input.

        Parameters
        ----------
        ref : Opaque record reference (validated).
        target_scan_ref : Target scan reference.
        control_scan_ref : Control scan reference.

        Returns
        -------
        A ``ResolvedInput`` with exactly one H5 source.

        Raises
        ------
        ResolutionNotConfiguredError
            If the resolver is not configured (e.g., no Matador client
            available).
        ResolutionError
            If resolution fails for any other reason.
        """
        ...


# ---------------------------------------------------------------------------
# Safe resolution errors
# ---------------------------------------------------------------------------


class ResolutionError(RuntimeError):
    """Base error for record resolution failures."""

    def __str__(self) -> str:
        """Return a safe message without raw refs."""
        return str(self.args[0]) if self.args else "Record resolution failed"


class ResolutionNotConfiguredError(ResolutionError):
    """Raised when no resolver is configured (e.g., Matador not set up)."""

    def __str__(self) -> str:
        """Return a safe message explaining the resolver is not configured."""
        return (
            "System-of-record resolver is not configured. "
            "Use h5_path or h5_uri for direct input, or configure "
            "the Matador resolver for source-of-record ownership."
        )


# ---------------------------------------------------------------------------
# Unconfigured resolver (default)
# ---------------------------------------------------------------------------


class UnconfiguredRecordResolver:
    """Default resolver that always raises ``ResolutionNotConfiguredError``.

    This is the production default until a Matador resolver is implemented
    and configured.  It ensures that any accidental use of
    system-of-record resolution before Matador integration is caught
    with a safe error.
    """

    def resolve(
        self,
        ref: ExternalRecordRef,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> ResolvedInput:
        """Always raises ``ResolutionNotConfiguredError``."""
        raise ResolutionNotConfiguredError()
