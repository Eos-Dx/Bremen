"""Tests for Terraform model package environment variable wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

TERRAFORM = Path(__file__).parents[1] / "infra" / "terraform"


def _read(path: str) -> str:
    return (TERRAFORM / path).read_text(encoding="utf-8")


class TestVariablesExist:
    def test_model_version_variable_exists(self):
        """variables.tf must have model_version variable."""
        content = _read("variables.tf")
        assert 'variable "model_version"' in content

    def test_model_uri_variable_exists(self):
        """variables.tf must have model_uri variable."""
        content = _read("variables.tf")
        assert 'variable "model_uri"' in content

    def test_model_checksum_variable_exists(self):
        """variables.tf must have model_checksum variable."""
        content = _read("variables.tf")
        assert 'variable "model_checksum"' in content


class TestEcsEnvVarsExist:
    def test_ecs_has_bremen_model_version(self):
        """ecs.tf must have BREMEN_MODEL_VERSION env var."""
        content = _read("ecs.tf")
        assert "BREMEN_MODEL_VERSION" in content

    def test_ecs_has_bremen_model_uri(self):
        """ecs.tf must have BREMEN_MODEL_URI env var."""
        content = _read("ecs.tf")
        assert "BREMEN_MODEL_URI" in content

    def test_ecs_has_bremen_model_checksum(self):
        """ecs.tf must have BREMEN_MODEL_CHECKSUM env var."""
        content = _read("ecs.tf")
        assert "BREMEN_MODEL_CHECKSUM" in content


class TestEcsUsesVariableRefs:
    def test_ecs_model_version_uses_var_ref(self):
        """ECS env var value references var.model_version, not a hardcoded string."""
        content = _read("ecs.tf")
        assert "var.model_version" in content

    def test_ecs_model_uri_uses_var_ref(self):
        """ECS env var value references var.model_uri."""
        content = _read("ecs.tf")
        assert "var.model_uri" in content

    def test_ecs_model_checksum_uses_var_ref(self):
        """ECS env var value references var.model_checksum."""
        content = _read("ecs.tf")
        assert "var.model_checksum" in content


class TestAppRunnerEnvVarsExist:
    def test_apprunner_has_bremen_model_version(self):
        """apprunner.tf must have BREMEN_MODEL_VERSION env var."""
        content = _read("apprunner.tf")
        assert "BREMEN_MODEL_VERSION" in content

    def test_apprunner_has_bremen_model_uri(self):
        """apprunner.tf must have BREMEN_MODEL_URI env var."""
        content = _read("apprunner.tf")
        assert "BREMEN_MODEL_URI" in content

    def test_apprunner_has_bremen_model_checksum(self):
        """apprunner.tf must have BREMEN_MODEL_CHECKSUM env var."""
        content = _read("apprunner.tf")
        assert "BREMEN_MODEL_CHECKSUM" in content
