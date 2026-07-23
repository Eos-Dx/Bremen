"""JavaScript parse validation for Control Room page.

Extracts JavaScript from the rendered GET /demo page and validates
it with an actual JavaScript parser (Node.js --check).

This is NOT a source-grep assertion. It renders the real HTML page
via build_control_room_page(), extracts the <script> content, and
parses it with Node.js.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import os
import re

import pytest


def _extract_control_room_js() -> str:
    """Render the Control Room page and extract the JavaScript."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from bremen.control_room_ui import build_control_room_page

    html = build_control_room_page(base_url="http://localhost:8000")
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    if not m:
        raise AssertionError("No <script> tag found in rendered Control Room HTML")
    return m.group(1)


def _node_available() -> bool:
    """Check if Node.js is available."""
    try:
        subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class TestControlRoomJavaScriptParse:
    """JavaScript parse validation using Node.js parser."""

    def test_js_parses_with_node(self):
        """Extracted JavaScript parses without syntax errors."""
        js = _extract_control_room_js()
        assert len(js) > 0, "JavaScript content must not be empty"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False
        ) as f:
            f.write(js)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["node", "--check", tmp_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert result.returncode == 0, (
                f"JavaScript parse failed:\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        finally:
            os.unlink(tmp_path)

    def test_single_init_call(self):
        """JavaScript contains exactly one init() call (not duplicated)."""
        js = _extract_control_room_js()
        # Count lines containing 'init()' but not 'function init()'
        init_calls = 0
        for line in js.split("\n"):
            stripped = line.strip()
            if stripped == "init();":
                init_calls += 1
        assert init_calls == 1, (
            f"Expected exactly 1 init() call, found {init_calls}. "
            "Duplicated init() prevents proper initialization."
        )

    def test_single_iife_closure(self):
        """JavaScript contains exactly one IIFE closure (})())."""
        js = _extract_control_room_js()
        closures = 0
        for line in js.split("\n"):
            stripped = line.strip()
            if stripped == "})();":
                closures += 1
        assert closures == 1, (
            f"Expected exactly 1 IIFE closure, found {closures}. "
            "Duplicated IIFE closure causes SyntaxError."
        )

    def test_iife_structure_valid(self):
        """JavaScript IIFE structure is valid: (function(){...})() with init inside."""
        js = _extract_control_room_js()
        # The IIFE should start with (function(){ and end with })();
        # init() should be inside the IIFE (before })())
        iife_start = js.find("(function(){")
        iife_end = js.rfind("})();")
        assert iife_start >= 0, "IIFE start '(function(){{' not found"
        assert iife_end > iife_start, "IIFE end '}})();' not found or before start"

        # init() should be between IIFE start and end
        init_pos = js.rfind("init();", iife_start, iife_end)
        assert init_pos > iife_start, (
            "init() must be inside the IIFE, not outside. "
            "An init() outside the IIFE causes ReferenceError at runtime."
        )

    def test_no_init_outside_iife(self):
        """No init() call exists outside the IIFE closure."""
        js = _extract_control_room_js()
        iife_end = js.rfind("})();")
        after_iife = js[iife_end + 5:]  # After the IIFE closure
        # Check for init() in the remaining content (should only be </script>)
        assert "init()" not in after_iife, (
            "init() found outside IIFE. This would cause ReferenceError "
            "because init is defined inside the IIFE scope."
        )

    def test_required_functions_defined(self):
        """All required Control Room functions are defined in the JS."""
        js = _extract_control_room_js()
        required = [
            "function init()",
            "function loadContainerCatalog()",
            "function selectContainer",
            "function handleFileSelect",
            "function loadModelCatalog()",
            "function onModelSelect",
            "function updateReadiness()",
            "function startAnalysis()",
            "function loadJobHistory()",
            "function openJob",
            "function toggleAutoScroll",
            "function filterEvents",
        ]
        for func in required:
            assert func in js, f"Required function not found: {func}"

    def test_window_exports_present(self):
        """All required functions are exported to window for inline onclick."""
        js = _extract_control_room_js()
        exports = [
            "window.loadContainerCatalog",
            "window.selectContainer",
            "window.handleFileSelect",
            "window.loadModelCatalog",
            "window.onModelSelect",
            "window.updateReadiness",
            "window.startAnalysis",
            "window.loadJobHistory",
            "window.openJob",
            "window.toggleAutoScroll",
            "window.filterEvents",
        ]
        for exp in exports:
            assert exp in js, f"Required window export not found: {exp}"
