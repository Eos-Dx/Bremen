"""Safe failure vocabulary for the standalone ML plugin boundary.

Every failure is represented by a fixed code and a fixed (or allowlisted)
safe reason.  Exception text, paths, artifact internals, patient data and
tracebacks never cross the plugin boundary.
"""

from __future__ import annotations

__all__ = [
    "ALLOWED_INPUT_LAYOUTS",
    "PluginArtifactError",
    "PluginError",
    "PluginInputError",
    "PluginReleaseError",
]

#: H5 layouts the standalone canonicalizer supports.  ``matador_raw`` remains
#: unsupported by this release (documented limitation); B2/B3 do not require
#: canonicalization because their own preprocessing consumes the raw H5.
ALLOWED_INPUT_LAYOUTS = frozenset(
    {"canonical", "calibration_sample", "session_layout"}
)


class PluginError(Exception):
    """Base class for safe, fixed-reason plugin failures."""

    code = "PLUGIN_ERROR"

    def __init__(self, safe_reason: str = "") -> None:
        self.safe_reason = str(safe_reason or self.code)
        super().__init__(self.code)


class PluginReleaseError(PluginError):
    """The local Model Release directory is missing or malformed."""

    code = "RELEASE_INVALID"


class PluginArtifactError(PluginError):
    """The release artifact failed checksum or contract validation."""

    code = "ARTIFACT_INVALID"


class PluginInputError(PluginError):
    """The staged input/request could not be normalized safely."""

    code = "INPUT_INVALID"

    def __init__(self, safe_reason: str = "input_invalid") -> None:
        super().__init__(safe_reason)
