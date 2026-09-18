"""Safe error categories retained for legacy HTTP error translation."""


class PreprocessingBridgeError(Exception):
    """Base exception for preprocessing bridge errors."""


class PreflightNotPassedError(PreprocessingBridgeError):
    """Preflight must pass before the bridge can run."""


class FeatureSchemaMismatchError(PreprocessingBridgeError):
    """Feature schema does not match expected columns or order."""
