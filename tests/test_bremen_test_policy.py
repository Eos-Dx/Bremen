"""Policy enforcement tests for Bremen test-design standards.

This file enforces rules defined in
``.project-memory/TEST_DESIGN_STANDARD.md`` and
``.project-memory/AGENT_TEST_DEBUGGING_RULES.md``.

All tests here are AST-based or text-based checks that verify test files
comply with design policies.  No production code is imported.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent

# ===================================================================
# Forbidden patterns for production smoke tests
# ===================================================================

SMOKE_TEST_PATH = TESTS_DIR / "test_bremen_production_smoke.py"

# Exact strings that must NOT appear in the production smoke test
FORBIDDEN_SUBSTRINGS = [
    "HTTPServer",
    "BaseHTTPRequestHandler",
    "threading.Thread",
    "socket.",
    "http.client",
    "serve_forever",
    "time.sleep",
    "_find_free_port",
]

# Pattern: function calls that suggest a real network server is started
FORBIDDEN_CALLS_RE = re.compile(
    r"\b(HTTPServer|serve_forever|_find_free_port)\b"
)


# ===================================================================
# Helpers
# ===================================================================


def _read_smoke_test() -> str:
    """Return the full source text of the production smoke test."""
    return SMOKE_TEST_PATH.read_text(encoding="utf-8")


def _strip_docstring(source: str) -> str:
    """Remove the module-level docstring (first triple-quoted block)."""
    # Find the first triple-quote
    start = source.find('"""')
    if start == -1:
        return source
    # Find the closing triple-quote
    end = source.find('"""', start + 3)
    if end == -1:
        return source
    # Return everything after the docstring
    return source[end + 3:]


# ===================================================================
# Test: forbidden server/network patterns in production smoke test
# ===================================================================


class TestProductionSmokeNoServerPatterns:
    """test_bremen_production_smoke.py must not contain server/network
    patterns that belong only in dedicated server tests."""

    def test_no_httpserver_reference(self):
        source = _read_smoke_test()
        # The docstring may mention HTTPServer as a disclaimer ("No HTTPServer").
        # Check for actual usage: import, instantiation, or subclassing.
        # Remove the docstring zone (first triple-quoted block) before checking.
        body = _strip_docstring(source)
        assert "HTTPServer" not in body, (
            "HTTPServer must not appear in production smoke test body"
        )

    def test_no_basehttprequesthandler_reference(self):
        source = _strip_docstring(_read_smoke_test())
        assert "BaseHTTPRequestHandler" not in source, (
            "BaseHTTPRequestHandler must not appear in production smoke test"
        )

    def test_no_threading_thread_reference(self):
        source = _strip_docstring(_read_smoke_test())
        assert "threading.Thread" not in source, (
            "threading.Thread must not appear in production smoke test"
        )

    def test_no_socket_reference(self):
        source = _strip_docstring(_read_smoke_test())
        assert "socket." not in source, (
            "socket. must not appear in production smoke test"
        )

    def test_no_http_client_reference(self):
        source = _strip_docstring(_read_smoke_test())
        assert "http.client" not in source, (
            "http.client must not appear in production smoke test"
        )

    def test_no_serve_forever_reference(self):
        source = _strip_docstring(_read_smoke_test())
        assert "serve_forever" not in source, (
            "serve_forever must not appear in production smoke test"
        )

    def test_no_time_sleep_reference(self):
        source = _strip_docstring(_read_smoke_test())
        assert "time.sleep" not in source, (
            "time.sleep must not appear in production smoke test"
        )

    def test_no_find_free_port_reference(self):
        source = _strip_docstring(_read_smoke_test())
        assert "_find_free_port" not in source, (
            "_find_free_port must not appear in production smoke test"
        )

    def test_no_forbidden_calls_via_regex(self):
        """Verify no forbidden function calls appear using regex.

        Catches concatenated or dynamically constructed references
        that exact-substring checks might miss.
        """
        source = _strip_docstring(_read_smoke_test())
        matches = FORBIDDEN_CALLS_RE.findall(source)
        assert len(matches) == 0, (
            f"Found forbidden call patterns: {matches}"
        )


# ===================================================================
# Test: AST-based check for forbidden imports in production smoke test
# ===================================================================


class TestProductionSmokeASTImports:
    """AST-level check that the smoke test does not import forbidden
    modules at the top level."""

    FORBIDDEN_MODULES = {
        "http.server": "HTTPServer/BaseHTTPRequestHandler",
        "threading": "threading.Thread",
        "socket": "socket.*",
        "http.client": "HTTPConnection/HTTPResponse",
    }

    def _get_top_level_imports(self) -> list[str]:
        """Return list of module names imported at top level."""
        source = SMOKE_TEST_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def test_no_forbidden_imports(self):
        imports = self._get_top_level_imports()
        for mod, desc in self.FORBIDDEN_MODULES.items():
            mod_root = mod.split(".")[0]
            for imp in imports:
                imp_root = imp.split(".")[0]
                if imp_root == mod_root:
                    pytest.fail(
                        f"Smoke test imports {imp} ({desc}) which is "
                        f"forbidden by TEST_DESIGN_STANDARD.md Rule 2"
                    )


# ===================================================================
# Test: production smoke test docstring declares in-process pattern
# ===================================================================


class TestProductionSmokeDocstringPolicy:
    """The module-level docstring of the production smoke test must
    declare that it uses in-process calls (not server/network)."""

    def test_module_docstring_declares_in_process(self):
        """The first 10 lines of the smoke test should contain
        keywords indicating in-process testing."""
        source = _read_smoke_test()
        # Check the docstring area — must reference in-process or in-process
        first_500 = source[:500]
        assert (
            "in-process" in first_500.lower()
            or "in process" in first_500.lower()
        ), (
            "Module docstring should declare in-process testing pattern, "
            "found: " + first_500.split('"""')[1][:100] if '"""' in first_500
            else "no docstring found"
        )

    def test_module_docstring_no_server_terms(self):
        """The module docstring must not claim it starts a server.

        The docstring may say "No HTTPServer" as a disclaimer.
        It must not say "starts an HTTPServer" or "serve_forever".
        """
        source = _read_smoke_test()
        first_500 = source[:500]
        # Allowed: "No HTTPServer" disclaimer
        # Forbidden: positive claims of server usage
        positive_terms = ["starts an HTTPServer", "starts HTTPServer",
                          "serve_forever in production",
                          "starts a real HTTPServer"]
        for term in positive_terms:
            assert term not in first_500.lower(), (
                f"Docstring must not positively claim server usage: {term}"
            )


# ===================================================================
# Test: TEST_DESIGN_STANDARD.md exists and has required sections
# ===================================================================


class TestTestDesignStandardDocument:
    """Verify .project-memory/TEST_DESIGN_STANDARD.md exists and
    covers required topics."""

    STANDARD_PATH = (
        Path(__file__).resolve().parents[1]
        / ".project-memory"
        / "TEST_DESIGN_STANDARD.md"
    )

    def test_standard_exists(self):
        assert self.STANDARD_PATH.exists(), (
            "TEST_DESIGN_STANDARD.md must exist"
        )

    def test_standard_covers_in_process_rule(self):
        content = self.STANDARD_PATH.read_text(encoding="utf-8")
        assert "in-process" in content.lower(), (
            "TEST_DESIGN_STANDARD.md must mention in-process rule"
        )

    def test_standard_covers_server_tools_rule(self):
        content = self.STANDARD_PATH.read_text(encoding="utf-8")
        assert "HTTPServer" in content, (
            "TEST_DESIGN_STANDARD.md must mention HTTPServer"
        )

    def test_standard_covers_dedicated_server_tests(self):
        content = self.STANDARD_PATH.read_text(encoding="utf-8")
        assert "dedicated server tests" in content.lower(), (
            "TEST_DESIGN_STANDARD.md must mention dedicated server tests"
        )


# ===================================================================
# Test: AGENT_TEST_DEBUGGING_RULES.md has required new rules
# ===================================================================


class TestAgentDebuggingRulesUpdated:
    """Verify AGENT_TEST_DEBUGGING_RULES.md contains the new
    protocol-violation and anti-loop rules."""

    RULES_PATH = (
        Path(__file__).resolve().parents[1]
        / ".project-memory"
        / "AGENT_TEST_DEBUGGING_RULES.md"
    )

    def test_rules_exists(self):
        assert self.RULES_PATH.exists()

    def test_protocol_violation_rule_exists(self):
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "protocol-violation" in content.lower() or \
               "Protocol-violation" in content, (
            "Must contain the protocol-violation stop-and-report rule"
        )

    def test_anti_loop_escalation_mentions_three_attempts(self):
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "3 failed attempts" in content or \
               "three failed attempts" in content.lower() or \
               "3 unsuccessful attempts" in content, (
            "Anti-loop rule must mention 3 failed attempts threshold"
        )

    def test_anti_loop_escalation_mentions_20_minutes(self):
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "20 minutes" in content, (
            "Anti-loop rule must mention 20-minute threshold"
        )

    def test_forbid_regex_mass_rewrites(self):
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "regex" in content.lower() and \
               "mass" in content.lower(), (
            "Must forbid regex mass rewrites"
        )

    def test_forbid_sleep_retry_loops(self):
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "sleep" in content or "retry" in content, (
            "Must forbid sleep/retry loops"
        )

    def test_forbid_deleting_assertions(self):
        content = self.RULES_PATH.read_text(encoding="utf-8")
        assert "deleting" in content.lower() or \
               "delete" in content.lower(), (
            "Must forbid deleting assertions to make tests pass"
        )
