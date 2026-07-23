"""Executable Control Room launch flow behavioral tests.

Renders the real Control Room HTML, extracts its JavaScript, and
executes it in Node.js with a minimal deterministic DOM, fetch,
EventSource, and event-listener harness.

This replaces the source-grep assertions that were previously used.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import re
import json


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
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


JS_EXTRACT_PATH = "/tmp/cr_js_extracted.js"


class TestControlRoomLaunchFlow:
    """Executable behavioral tests for Control Room launch flow.

    These tests render the real Control Room HTML, extract the JavaScript,
    and execute it in Node.js with a minimal deterministic DOM harness.
    """

    def test_js_parses_with_node(self):
        """JavaScript extracted from rendered page parses without errors."""
        if not _node_available():
            pytest.skip("Node.js not available")

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

    def test_launch_flow_executes(self):
        """Full launch flow executes in Node.js with DOM harness."""
        if not _node_available():
            pytest.skip("Node.js not available")

        # Extract JS and write to temp file
        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        # Path to the Node.js test script
        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )
        assert os.path.exists(test_script), (
            f"Node.js test script not found: {test_script}"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Print output for debugging
        print("\n--- Node.js test output ---")
        print(result.stdout)
        if result.stderr:
            print("--- stderr ---")
            print(result.stderr)
        print("--- end ---")

        assert result.returncode == 0, (
            f"Launch flow test failed (exit code {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    def test_launch_flow_catalog_selection(self):
        """Catalog selection flow: load, click, verify state."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check for specific test results in output
        output = result.stdout
        assert "PASS: init() ran and catalog items rendered" in output, (
            "Catalog load test did not pass"
        )
        assert "PASS: Click catalog row selects source and updates state" in output, (
            "Catalog click test did not pass"
        )
        assert "PASS: Analyze button becomes enabled after valid selection" in output, (
            "Analyze enable test did not pass"
        )

    def test_launch_flow_job_payload(self):
        """Job payload correctness: workflow_id, source_id, model_id, no h5_path."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: Analyze sends correct payload" in output, (
            "Job payload test did not pass"
        )
        assert "PASS: Upload path sends upload_id instead of source_id" in output, (
            "Upload payload test did not pass"
        )
        assert "PASS: Duplicate Analyze activation creates exactly one request" in output, (
            "Duplicate prevention test did not pass"
        )

    def test_launch_flow_keyboard_selection(self):
        """Keyboard catalog selection works."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: Keyboard Enter key selects catalog item" in output, (
            "Keyboard selection test did not pass"
        )

    def test_launch_flow_stale_source(self):
        """Missing selection becomes stale and disables Analyze."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: Missing selection becomes stale and disables Analyze" in output, (
            "Stale source test did not pass"
        )

    def test_launch_flow_no_model(self):
        """No-model state disables Analyze."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: No-model state disables Analyze" in output, (
            "No-model test did not pass"
        )

    def test_launch_flow_multi_model(self):
        """Multiple-model state requires explicit selection."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: Multiple-model state requires explicit selection" in output, (
            "Multi-model test did not pass"
        )

    def test_launch_flow_workflow_compat(self):
        """Aramis/incompatible containers are excluded."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: All server containers are rendered without frontend filtering" in output, (
            "Workflow compat test did not pass"
        )

    def test_launch_flow_state_transitions(self):
        """State transitions follow correct sequence."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: State transitions follow correct sequence" in output, (
            "State transition test did not pass"
        )

    def test_launch_flow_catalog_refresh(self):
        """Catalog refresh preserves valid selection."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: Catalog refresh preserves valid selection" in output, (
            "Catalog refresh test did not pass"
        )

    def test_launch_flow_no_dual_payload(self):
        """Payload never contains both source_id and upload_id."""
        if not _node_available():
            pytest.skip("Node.js not available")

        js = _extract_control_room_js()
        with open(JS_EXTRACT_PATH, "w") as f:
            f.write(js)

        test_script = os.path.join(
            os.path.dirname(__file__), "test_bremen_launch_flow.js"
        )

        result = subprocess.run(
            ["node", test_script, JS_EXTRACT_PATH],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout
        assert "PASS: Payload never contains both source_id and upload_id" in output, (
            "Dual payload test did not pass"
        )


import pytest  # noqa: E402 (imported at end for isort compatibility)
