"""Bremen demo Model Playground page.

Serves the full standalone playground as a packaged, sanitized HTML asset.
The asset keeps the original three-tab interactive sandbox structure, but
does not expose production artifact identifiers or learned production
parameters.
"""

from __future__ import annotations

from pathlib import Path


_PLAYGROUND_HTML = Path(__file__).with_name("model_playground_page.html")


def build_model_playground_page(*, unlisted_preview: bool = False) -> str:
    """Build the full sanitized Model Playground HTML page.

    Parameters
    ----------
    unlisted_preview:
        Marks the same sandbox page as an unlisted preview route.  This is not
        authentication and must not be used for private model material.
    """
    html = _PLAYGROUND_HTML.read_text(encoding="utf-8")
    if unlisted_preview:
        notice = (
            '<div class="sandbox-notice" style="background:#eef6fb;'
            'border:1px solid #bfd5e2;color:#173f52;padding:12px;'
            'border-radius:9px;margin:0 0 14px;font-size:13px;'
            'line-height:1.45"><strong>Unlisted preview link.</strong> '
            "This is still an unauthenticated sandbox endpoint, so it serves "
            "the same sanitized page as the public playground.</div>"
        )
        html = html.replace('<div class="shell">', f'<div class="shell">{notice}', 1)
    return html
