"""Tests for runtime/training separation.

Verifies that runtime modules do not import training,
and that training CLI/runtime CLI are separated.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
RUNTIME_DOCKERFILE = ROOT / "Dockerfile"


def _read_dockerfile() -> str:
    return RUNTIME_DOCKERFILE.read_text(encoding="utf-8")


class TestRuntimeImport:
    def test_runtime_does_not_import_training(self):
        """Importing runtime modules does not import bremen.training."""
        # Import all runtime-exposed modules
        import importlib

        for mod_name in [
            "bremen.__main__",
            "bremen.model_package",
            "bremen.model_loader",
            "bremen.config",
        ]:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        # Clear any prior training import
        if "bremen.training" in sys.modules:
            del sys.modules["bremen.training"]

        # Import a representative set of runtime modules
        for mod_name in [
            "bremen.__main__",
            "bremen.model_package",
            "bremen.model_loader",
            "bremen.config",
        ]:
            importlib.import_module(mod_name)

        assert "bremen.training" not in sys.modules, (
            "Runtime import of bremen.__main__ triggered bremen.training import"
        )


class TestRuntimeDockerfile:
    def test_runtime_dockerfile_does_not_mention_training(self):
        """Runtime Dockerfile must not reference training."""
        content = _read_dockerfile()
        assert "training" not in content, (
            "Runtime Dockerfile must not reference training"
        )
        assert "train_classifier" not in content, (
            "Runtime Dockerfile must not reference train_classifier"
        )

    def test_runtime_dockerfile_does_not_mention_dockerfile_training(self):
        """Runtime Dockerfile must not reference Dockerfile.training."""
        content = _read_dockerfile()
        assert "Dockerfile.training" not in content, (
            "Runtime Dockerfile must not reference Dockerfile.training"
        )


class TestCliSeparation:
    def test_training_cli_help_works(self):
        """Training CLI --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen.training.train_classifier", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Training CLI --help failed: {result.stderr}"
        )
        assert "--config" in result.stdout

    def test_runtime_cli_does_not_show_training(self):
        """Runtime CLI --help does not show training commands."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "--help"],
            capture_output=True,
            text=True,
        )
        assert "training" not in result.stdout, (
            "Runtime CLI must not show training commands"
        )
