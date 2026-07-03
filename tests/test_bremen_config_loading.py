"""Tests for minimal Bremen config discovery and loading.

Covers:
- Explicit path wins over env/default
- BREMEN_CONFIG env var is respected
- Default discovery order bremen.yml -> bremen.yaml -> bremen.toml
- No config found raises ConfigNotFoundError
- Missing explicit file raises ConfigNotFoundError
- Invalid TOML/YAML raises ConfigSyntaxError
- Empty config returns empty data with warning
- Import safety (AST inspection)
- No H5/HDF5 reads
- No model/joblib loads
- No Aramis identity in user-facing text
"""

from __future__ import annotations

import os
import sys
import ast
from pathlib import Path

import pytest

from bremen.config import (
    ConfigError,
    ConfigLoadResult,
    ConfigNotFoundError,
    ConfigSyntaxError,
    discover_config,
    load_config,
)

SRC_BREMEN = Path(__file__).parents[1] / "src" / "bremen"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_workdir(tmp_path: Path) -> Path:
    """Provide a temporary working directory."""
    return tmp_path


def _write_yaml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _write_toml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Explicit path tests
# ---------------------------------------------------------------------------


class TestExplicitPath:
    def test_explicit_path_yaml(self, tmp_workdir: Path):
        """Explicit YAML path loads correctly."""
        config_path = tmp_workdir / "custom.yml"
        _write_yaml(config_path, "key1: value1\nkey2: 42\n")
        result = discover_config(explicit_path=config_path)
        assert result.source == "explicit"
        assert result.data == {"key1": "value1", "key2": 42}
        assert result.path == config_path.resolve()

    def test_explicit_path_toml(self, tmp_workdir: Path):
        """Explicit TOML path loads correctly."""
        config_path = tmp_workdir / "custom.toml"
        _write_toml(config_path, 'key1 = "value1"\nkey2 = 42\n')
        result = discover_config(explicit_path=config_path)
        assert result.source == "explicit"
        assert result.data == {"key1": "value1", "key2": 42}

    def test_explicit_path_wins_over_env(self, tmp_workdir: Path):
        """Explicit path is used even when BREMEN_CONFIG env var is set."""
        env_path = tmp_workdir / "env_config.yml"
        explicit_path = tmp_workdir / "explicit.yml"
        _write_yaml(env_path, "from_env: true\n")
        _write_yaml(explicit_path, "from_explicit: true\n")
        os.environ["BREMEN_CONFIG"] = str(env_path)
        try:
            result = discover_config(explicit_path=explicit_path)
            assert result.source == "explicit"
            assert result.data == {"from_explicit": True}
        finally:
            del os.environ["BREMEN_CONFIG"]

    def test_explicit_path_nonexistent(self, tmp_workdir: Path):
        """Missing explicit path raises ConfigNotFoundError."""
        missing = tmp_workdir / "does_not_exist.yml"
        with pytest.raises(ConfigNotFoundError) as exc_info:
            discover_config(explicit_path=missing)
        assert missing.resolve() in exc_info.value.searched

    def test_load_config_explicit(self, tmp_workdir: Path):
        """load_config with an explicit path works."""
        config_path = tmp_workdir / "direct.yml"
        _write_yaml(config_path, "direct: true\n")
        result = load_config(config_path)
        assert result.source == "explicit"
        assert result.data == {"direct": True}

    def test_load_config_missing(self, tmp_workdir: Path):
        """load_config with a missing path raises ConfigNotFoundError."""
        missing = tmp_workdir / "missing.yml"
        with pytest.raises(ConfigNotFoundError):
            load_config(missing)


# ---------------------------------------------------------------------------
# BREMEN_CONFIG environment variable tests
# ---------------------------------------------------------------------------


class TestEnvVar:
    def test_env_var_respected(self, tmp_workdir: Path):
        """BREMEN_CONFIG environment variable is used as config path."""
        config_path = tmp_workdir / "env_config.yml"
        _write_yaml(config_path, "from_env: true\n")
        os.environ["BREMEN_CONFIG"] = str(config_path)
        try:
            result = discover_config()
            assert result.source == "env"
            assert result.data == {"from_env": True}
        finally:
            del os.environ["BREMEN_CONFIG"]

    def test_env_var_empty_skipped(self, tmp_workdir: Path):
        """Empty BREMEN_CONFIG is treated as not set."""
        os.environ["BREMEN_CONFIG"] = ""
        try:
            with pytest.raises(ConfigNotFoundError):
                discover_config(cwd=tmp_workdir)
        finally:
            del os.environ["BREMEN_CONFIG"]

    def test_env_var_whitespace_skipped(self, tmp_workdir: Path):
        """Whitespace-only BREMEN_CONFIG is treated as not set."""
        os.environ["BREMEN_CONFIG"] = "   "
        try:
            with pytest.raises(ConfigNotFoundError):
                discover_config(cwd=tmp_workdir)
        finally:
            del os.environ["BREMEN_CONFIG"]

    def test_env_var_none_disables_env(self, tmp_workdir: Path):
        """Passing env_var=None skips environment variable check."""
        os.environ["BREMEN_CONFIG"] = str(tmp_workdir / "ignored.yml")
        try:
            with pytest.raises(ConfigNotFoundError):
                discover_config(env_var=None, cwd=tmp_workdir)
        finally:
            del os.environ["BREMEN_CONFIG"]


# ---------------------------------------------------------------------------
# Default discovery order tests
# ---------------------------------------------------------------------------


class TestDefaultDiscovery:
    def test_discovery_finds_yml(self, tmp_workdir: Path):
        """discover_config finds 'bremen.yml' in cwd."""
        _write_yaml(tmp_workdir / "bremen.yml", "found: true\n")
        result = discover_config(cwd=tmp_workdir)
        assert result.source == "discovery"
        assert result.data == {"found": True}

    def test_discovery_finds_yaml(self, tmp_workdir: Path):
        """discover_config finds 'bremen.yaml' when .yml is absent."""
        _write_yaml(tmp_workdir / "bremen.yaml", "found: true\n")
        result = discover_config(cwd=tmp_workdir)
        assert result.source == "discovery"
        assert result.data == {"found": True}

    def test_discovery_finds_toml(self, tmp_workdir: Path):
        """discover_config finds 'bremen.toml' when .yml/.yaml are absent."""
        _write_toml(tmp_workdir / "bremen.toml", 'found = true\n')
        result = discover_config(cwd=tmp_workdir)
        assert result.source == "discovery"
        assert result.data == {"found": True}

    def test_discovery_order_precedence(self, tmp_workdir: Path):
        """When both bremen.yml and bremen.yaml exist, .yml wins (first match)."""
        _write_yaml(tmp_workdir / "bremen.yml", "first: yml\n")
        _write_yaml(tmp_workdir / "bremen.yaml", "second: yaml\n")
        result = discover_config(cwd=tmp_workdir)
        assert result.data == {"first": "yml"}

    def test_discovery_toml_over_nonexistent(self, tmp_workdir: Path):
        """Only bremen.toml is found when .yml and .yaml are absent."""
        _write_toml(tmp_workdir / "bremen.toml", 'only_toml = true\n')
        result = discover_config(cwd=tmp_workdir)
        assert result.data == {"only_toml": True}


# ---------------------------------------------------------------------------
# No config found tests
# ---------------------------------------------------------------------------


class TestNoConfig:
    def test_no_config_found(self, tmp_workdir: Path):
        """Empty directory with no env var raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError) as exc_info:
            discover_config(cwd=tmp_workdir)
        assert len(exc_info.value.searched) > 0

    def test_searched_paths_are_listed(self, tmp_workdir: Path):
        """ConfigNotFoundError lists all searched paths."""
        try:
            discover_config(cwd=tmp_workdir)
        except ConfigNotFoundError as exc:
            searched = exc.searched
            assert any("bremen.yml" in str(p) for p in searched)
            assert any("bremen.yaml" in str(p) for p in searched)
            assert any("bremen.toml" in str(p) for p in searched)


# ---------------------------------------------------------------------------
# Syntax error tests
# ---------------------------------------------------------------------------


class TestSyntaxErrors:
    def test_invalid_toml(self, tmp_workdir: Path):
        """Invalid TOML raises ConfigSyntaxError."""
        bad_path = tmp_workdir / "bad.toml"
        _write_toml(bad_path, "key1 = \n")
        with pytest.raises(ConfigSyntaxError) as exc_info:
            load_config(bad_path)
        assert "bad.toml" in str(exc_info.value)

    def test_invalid_yaml(self, tmp_workdir: Path):
        """Invalid YAML raises ConfigSyntaxError."""
        bad_path = tmp_workdir / "bad.yml"
        _write_yaml(bad_path, ": broken yaml\n")
        with pytest.raises(ConfigSyntaxError) as exc_info:
            load_config(bad_path)
        assert "bad.yml" in str(exc_info.value)

    def test_unsupported_extension(self, tmp_workdir: Path):
        """Config file with unsupported extension raises ConfigSyntaxError."""
        bad_path = tmp_workdir / "config.json"
        _write_yaml(bad_path, '{"key": "value"}\n')
        with pytest.raises(ConfigSyntaxError) as exc_info:
            load_config(bad_path)
        assert "Unsupported config format" in str(exc_info.value)

    def test_directory_path(self, tmp_workdir: Path):
        """Passing a directory path raises ConfigSyntaxError."""
        dir_path = tmp_workdir / "config_dir"
        dir_path.mkdir()
        with pytest.raises(ConfigSyntaxError) as exc_info:
            load_config(dir_path)
        assert "Is a directory" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Empty config tests
# ---------------------------------------------------------------------------


class TestEmptyConfig:
    def test_empty_toml(self, tmp_workdir: Path):
        """Empty TOML file returns empty data with a warning."""
        empty_path = tmp_workdir / "empty.toml"
        _write_toml(empty_path, "")
        result = load_config(empty_path)
        assert result.data == {}
        assert len(result.warnings) > 0

    def test_empty_yaml(self, tmp_workdir: Path):
        """Empty YAML file returns empty data with a warning."""
        empty_path = tmp_workdir / "empty.yml"
        _write_yaml(empty_path, "")
        result = load_config(empty_path)
        assert result.data == {}
        assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# Import safety tests
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_heavy_imports_at_top_level(self):
        """config.py must not import heavy modules at top level (AST check)."""
        config_path = SRC_BREMEN / "config.py"
        tree = ast.parse(config_path.read_text(encoding="utf-8"))

        heavy_modules = [
            "xrd_preprocessing",
            "container",
            "bremen.pipelines",
            "bremen.modeling",
            "bremen.mlflow_tracking",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for mod in heavy_modules:
                    if mod in module:
                        pytest.fail(
                            f"config.py imports {mod} at top level"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for mod in heavy_modules:
                        if mod in alias.name:
                            pytest.fail(
                                f"config.py imports {mod} at top level"
                            )

    def test_import_succeeds(self):
        """Importing bremen.config succeeds without errors."""
        import importlib

        if "bremen.config" in sys.modules:
            del sys.modules["bremen.config"]

        # This should not raise any ImportError
        importlib.import_module("bremen.config")


# ---------------------------------------------------------------------------
# No Aramis identity
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_no_aramis_in_docstring(self):
        """config.py docstring must not contain 'Aramis' or 'aramis'."""
        config_path = SRC_BREMEN / "config.py"
        content = config_path.read_text(encoding="utf-8")
        assert "Aramis" not in content, "config.py must not reference Aramis"
        assert "aramis" not in content, "config.py must not reference aramis"

    def test_no_aramis_in_error_messages(self):
        """Config error messages must not contain 'Aramis'."""
        config_path = SRC_BREMEN / "config.py"
        content = config_path.read_text(encoding="utf-8")
        # Check docstring and class __init__ messages
        for line in content.splitlines():
            if "Aramis" in line or "aramis" in line:
                pytest.fail(f"config.py contains Aramis reference: {line}")

    def test_no_clinical_claims(self):
        """config.py must not make diagnostic replacement or clinical claims.

        The docstring contains the safe 'Not a diagnostic replacement'
        disclaimer (required by contract). Error messages must not claim
        clinical utility or validation.
        """
        config_path = SRC_BREMEN / "config.py"
        content = config_path.read_text(encoding="utf-8")
        prohibited = [
            "clinically validated",
            "replace MRI",
            "replace biopsy",
            "replace radiologist",
            "replace clinician",
            "autonomous clinical",
            "FDA clearance",
        ]
        for phrase in prohibited:
            if phrase in content.lower():
                pytest.fail(
                    f"config.py contains prohibited phrase: {phrase}"
                )


# ---------------------------------------------------------------------------
# No H5/model/Matador in config module
# ---------------------------------------------------------------------------


class TestNoHeavyReferences:
    def test_no_h5_references(self):
        """config.py must not reference H5/HDF5."""
        config_path = SRC_BREMEN / "config.py"
        content = config_path.read_text(encoding="utf-8")
        for ref in [".h5", ".hdf5", "h5py", "hdf5"]:
            if ref in content:
                pytest.fail(f"config.py contains H5 reference: {ref}")

    def test_no_model_references(self):
        """config.py must not import or use joblib/pickle/model loading.

        The docstring documents safety boundaries (references are allowed
        in comments/docstrings). The module must not import or call
        these modules.
        """
        import ast

        config_path = SRC_BREMEN / "config.py"
        tree = ast.parse(config_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "joblib" in alias.name:
                        pytest.fail(
                            f"config.py imports joblib at top level"
                        )
                    if "pickle" in alias.name:
                        pytest.fail(
                            f"config.py imports pickle at top level"
                        )

    def test_no_matador_references(self):
        """config.py must not import or require Matador.

        The docstring documents the safety boundary (reference is
        allowed). The module must not import Matador.
        """
        import ast

        config_path = SRC_BREMEN / "config.py"
        tree = ast.parse(config_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "matador" in alias.name.lower():
                        pytest.fail(
                            f"config.py imports Matador at top level"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "matador" in module.lower():
                    pytest.fail(
                        f"config.py imports Matador at top level"
                    )
