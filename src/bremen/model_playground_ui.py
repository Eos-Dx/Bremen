"""Bremen demo Model Playground pages."""

from __future__ import annotations

from pathlib import Path


_PUBLIC_PLAYGROUND_HTML = Path(__file__).with_name("model_playground_page.html")
_PRIVATE_PLAYGROUND_HTML = Path(__file__).with_name(
    "model_playground_private_page.html"
)


def build_model_playground_page() -> str:
    """Build the full sanitized Model Playground HTML page.

    This public page is adapted for the Bremen demo navigation and avoids
    exposing raw artifact hashes, production coefficients, thresholds, or
    model/joblib internals.
    """
    return _PUBLIC_PLAYGROUND_HTML.read_text(encoding="utf-8")


def build_model_playground_private_page() -> str:
    """Build the unlisted standalone playground copy.

    The route that serves this page is intentionally not linked from public
    navigation.  It is still unauthenticated URL knowledge, not real access
    control.
    """
    return _PRIVATE_PLAYGROUND_HTML.read_text(encoding="utf-8")
