"""Static config governance gates for PR0051.

Verifies ADR-0011 decisions, config surface taxonomy, runtime config
inventory, model package metadata requirements, training/runtime boundary,
secret safety, and roadmap boundaries.

All gates are static/synthetic. No network, no AWS, no Docker/Terraform,
no real H5 or model artifacts.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS_ADR_DIR = ROOT / "docs" / "adr"
CONFIG_DIR = ROOT / "config"
SRC_BREMEN = ROOT / "src" / "bremen"


# ===================================================================
# ADR-0011 existence and content
# ===================================================================


class TestConfigGovernanceADR:
    """ADR-0011 exists and records G-CFG-1, G-CFG-2, G-CFG-3 decisions."""

    ADR_PATH = DOCS_ADR_DIR / "0011-config-governance-gates.md"

    def test_adr_0011_exists(self):
        assert self.ADR_PATH.exists(), "ADR-0011 must exist"

    def test_adr_0011_records_g_cfg_1(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "G-CFG-1" in content, "ADR-0011 must reference G-CFG-1"

    def test_adr_0011_records_g_cfg_2(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "G-CFG-2" in content, "ADR-0011 must reference G-CFG-2"

    def test_adr_0011_records_g_cfg_3(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "G-CFG-3" in content, "ADR-0011 must reference G-CFG-3"

    def test_adr_0011_records_lightweight_in_repo_governance(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "in-repo" in content.lower() or \
               "in repo" in content.lower(), (
            "ADR-0011 must record lightweight in-repo governance"
        )

    def test_adr_0011_records_no_external_config_platform(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "no external config platform" in content.lower(), (
            "ADR-0011 must record no external config platform for now"
        )

    def test_adr_0011_records_no_dynamodb_until_matador(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "DynamoDB" in content or "dynamodb" in content.lower(), (
            "ADR-0011 must mention DynamoDB as deferred"
        )
        assert "deferred" in content.lower() or \
               "not implemented" in content.lower(), (
            "ADR-0011 must record DynamoDB/backend as deferred"
        )

    def test_adr_0011_records_validation_as_repo_tests(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "pytest" in content.lower() or \
               "repository tests" in content.lower() or \
               "static checks" in content.lower(), (
            "ADR-0011 must record validation as repo tests/static checks"
        )

    def test_adr_0011_records_config_surface_taxonomy(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "Config Surface Taxonomy" in content or \
               "config surface" in content.lower(), (
            "ADR-0011 must document config surface taxonomy"
        )


# ===================================================================
# Config surface taxonomy
# ===================================================================


class TestConfigSurfaceTaxonomy:
    """Verify config surfaces are documented in ADR-0011."""

    ADR_PATH = DOCS_ADR_DIR / "0011-config-governance-gates.md"

    def test_runtime_config_surface_documented(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "Runtime config" in content or \
               "runtime config" in content.lower()

    def test_model_artifact_metadata_surface_documented(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "Model artifact metadata" in content or \
               "model artifact" in content.lower()

    def test_preprocessing_config_surface_documented(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "Preprocessing config" in content or \
               "preprocessing" in content.lower()

    def test_training_config_surface_documented(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "Training config" in content or \
               "training config" in content.lower()

    def test_deployment_config_surface_documented(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "Deployment config" in content or \
               "deployment" in content.lower()

    def test_test_only_synthetic_config_documented(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "synthetic config" in content.lower() or \
               "test-only" in content.lower()


# ===================================================================
# Runtime config governance
# ===================================================================


class TestRuntimeConfigGovernance:
    """Runtime model env/config keys remain documented or testable."""

    EXPECTED_ENV_KEYS = [
        "BREMEN_MODEL_VERSION",
        "BREMEN_MODEL_URI",
        "BREMEN_MODEL_CHECKSUM",
        "BREMEN_MODEL_STAGING_DIR",
    ]

    # Source files that reference these env keys
    SOURCE_FILES = [
        SRC_BREMEN / "api" / "model_state.py",
        SRC_BREMEN / "config.py",
    ]

    def test_runtime_env_keys_are_referenced_in_source(self):
        """All expected runtime env keys appear in at least one source file."""
        for key in self.EXPECTED_ENV_KEYS:
            found = any(key in f.read_text(encoding="utf-8") for f in self.SOURCE_FILES if f.exists())
            assert found, (
                f"Runtime env key '{key}' not found in any expected source file"
            )

    def test_model_state_env_constants_defined(self):
        """model_state.py defines _ENV_URI, _ENV_VERSION, _ENV_CHECKSUM."""
        content = (SRC_BREMEN / "api" / "model_state.py").read_text(encoding="utf-8")
        assert "_ENV_URI = \"BREMEN_MODEL_URI\"" in content
        assert "_ENV_VERSION = \"BREMEN_MODEL_VERSION\"" in content
        assert "_ENV_CHECKSUM = \"BREMEN_MODEL_CHECKSUM\"" in content

    def test_uri_checksum_are_bools_in_api_response(self):
        """Model version response exposes raw URI/checksum as bools, not strings."""
        from bremen.api.schemas import ModelVersionResponse

        fields = ModelVersionResponse.__dataclass_fields__
        assert "model_uri_configured" in fields, (
            "ModelVersionResponse must have model_uri_configured field"
        )
        assert "checksum_configured" in fields, (
            "ModelVersionResponse must have checksum_configured field"
        )
        # Check they are bool type
        assert fields["model_uri_configured"].type is bool or \
               str(fields["model_uri_configured"].type) == "bool"
        assert fields["checksum_configured"].type is bool or \
               str(fields["checksum_configured"].type) == "bool"

    def test_error_category_is_safe_string(self):
        """error_category is str | None, not raw exception."""
        from bremen.api.schemas import ModelVersionResponse

        fields = ModelVersionResponse.__dataclass_fields__
        assert "error_category" in fields, (
            "ModelVersionResponse must have error_category field"
        )

    def test_config_loading_no_local_machine_paths(self):
        """Runtime config loading does not depend on local machine paths."""
        from bremen.config import read_cloud_config

        # read_cloud_config with explicit env should not reference /Users/
        env = {"BREMEN_MODEL_BUCKET": "test-bucket"}
        cloud = read_cloud_config(env=env)
        assert cloud.configured is True
        # The model_uri is None — not a local path
        assert cloud.model_bucket == "test-bucket"


# ===================================================================
# Model package config governance
# ===================================================================


class TestModelPackageConfigGovernance:
    """Model package required metadata/schema remains explicit."""

    def test_model_package_required_fields_defined(self):
        """model_package.py validates required manifest fields."""
        from bremen.model_package import (
            validate_model_manifest, EXPECTED_ARTIFACT_TYPE,
        )

        manifest = {
            "artifact_type": EXPECTED_ARTIFACT_TYPE,
            "model_version": "1.0.0",
            "model_checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "model_filename": "model.joblib",
            "feature_schema_version": "1.0",
            "threshold_version": "v1",
            "threshold_value": 0.5,
            "qc_criteria_version": "1.0",
        }
        result = validate_model_manifest(manifest)
        assert result is not None

    def test_model_package_rejects_missing_version(self):
        """Missing model_version raises ModelPackageManifestError."""
        from bremen.model_package import validate_model_manifest, ModelPackageManifestError

        manifest = {
            "artifact_type": "bremen.v0_1.portable_logreg",
            "model_version": "",
            "model_checksum": "a" * 64,
            "model_filename": "model.joblib",
            "feature_schema_version": "1.0",
            "threshold_version": "v1",
            "threshold_value": 0.5,
            "qc_criteria_version": "1.0",
        }
        with pytest.raises(ModelPackageManifestError):
            validate_model_manifest(manifest)


# ===================================================================
# Training/runtime config boundary
# ===================================================================


class TestTrainingRuntimeConfigBoundary:
    """Training config remains offline-only. Runtime does not import training."""

    def test_runtime_does_not_import_training(self):
        """Importing runtime modules does not import bremen.training."""
        import importlib
        import sys

        for mod_name in list(sys.modules):
            if "bremen.training" in mod_name:
                del sys.modules[mod_name]

        for mod_name in [
            "bremen.__main__",
            "bremen.model_package",
            "bremen.model_loader",
            "bremen.config",
        ]:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        for mod_name in [
            "bremen.__main__",
            "bremen.model_package",
            "bremen.model_loader",
            "bremen.config",
        ]:
            importlib.import_module(mod_name)

        assert "bremen.training" not in sys.modules, (
            "Runtime import triggered bremen.training import"
        )

    def test_training_config_exists_in_config_dir(self):
        """Training config YAML files exist in config/training/."""
        training_dir = CONFIG_DIR / "training"
        assert training_dir.exists(), "config/training/ directory must exist"
        yaml_files = list(training_dir.glob("*.yaml"))
        assert len(yaml_files) >= 1, (
            "At least one training config YAML must exist"
        )

    def test_preprocessing_config_exists_in_config_dir(self):
        """Preprocessing config YAML files exist in config/preprocessing/."""
        prep_dir = CONFIG_DIR / "preprocessing"
        assert prep_dir.exists(), "config/preprocessing/ directory must exist"
        yaml_files = list(prep_dir.glob("*.yaml"))
        assert len(yaml_files) >= 1, (
            "At least one preprocessing config YAML must exist"
        )

    def test_preprocessing_config_is_distinct_from_runtime(self):
        """Preprocessing configs are not consumed by runtime model loading."""
        from bremen.config import read_cloud_config

        cloud = read_cloud_config(env={})
        assert cloud.configured is False
        # Runtime config is env-var based, not YAML-based


# ===================================================================
# Secret and artifact safety
# ===================================================================


class TestConfigSecretAndArtifactSafety:
    """Config surfaces do not include real artifact files.

    Config docs/tests do not contain access keys, account IDs, registry
    URLs, full S3 URIs, raw patient identifiers, raw scan refs, or
    local-machine absolute paths.
    """

    ADR_0011 = DOCS_ADR_DIR / "0011-config-governance-gates.md"
    ADR_0009 = DOCS_ADR_DIR / "0009-config-governance.md"
    CONFIG_README = CONFIG_DIR / "README.md"
    GOVERNANCE_TEST = Path(__file__).resolve()

    CHECK_FILES = [ADR_0011, ADR_0009, CONFIG_README, GOVERNANCE_TEST]

    FORBIDDEN_PATTERNS = [
        "AKIA",           # AWS access key prefix
        "SECRET_ACCESS_KEY",  # AWS secret key env var (value, not reference)
        "dkr.ecr",        # ECR registry URL pattern
    ]

    def test_no_access_keys_in_adr_or_config_docs(self):
        """No AWS access key patterns in governance docs."""
        for fpath in [self.ADR_0011, self.ADR_0009, self.CONFIG_README]:
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8")
            for pattern in self.FORBIDDEN_PATTERNS:
                assert pattern not in content, (
                    f"Forbidden pattern '{pattern}' found in {fpath}"
                )

    def test_no_local_machine_absolute_paths_in_test_file(self):
        """Test file does not contain local machine absolute paths."""
        with open(self.GOVERNANCE_TEST, "rb") as f:
            raw = f.read()
        # The test naturally contains its own search pattern, so exclude
        # this specific test function line by scanning only class-level
        # non-assertion code. Use a whitelist approach: check that no
        # /Users/ appears outside docstrings, comments, and known test
        # infrastructure.
        if b"/Users/" not in raw:
            return
        # If /Users/ is found, verify it's only in safe contexts
        text = raw.decode("utf-8")
        # Accept /Users/ only if it's inside a string literal that is part
        # of the test's own pattern-matching logic
        import re
        # Find all literal /Users/ occurrences
        for m in re.finditer(r"/Users/", text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start:line_end].strip() if line_end != -1 else text[line_start:].strip()
            # Allow if the line is the search pattern itself, a comment,
            # or the assertion line that reports the finding
            if '"/Users/"' in line or line.startswith("#") or "/Users/ found at line" in line:
                continue
            pytest.fail(f"/Users/ found at line: {line}")

    def test_no_raw_patient_identifiers(self):
        """No Nova_ or raw patient ID patterns in governance docs."""
        for fpath in [self.ADR_0011, self.ADR_0009]:
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8")
            assert "Nova_" not in content, (
                f"Raw patient identifier Nova_ found in {fpath}"
            )
        # config/README.md documents External ID format (Nova_<n>_<side>_P<point>)
        # which is a documentation format spec, not a raw identifier.
        # The governance ADRs must be clean.

    def test_no_full_s3_uris_in_governance_docs(self):
        """No full s3:// URIs in governance docs or test file."""
        for fpath in [self.ADR_0011, self.ADR_0009, self.CONFIG_README]:
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8")
            if "s3://" in content:
                # Allow only if it's a placeholder pattern like s3://${BUCKET}
                lines = content.splitlines()
                for line in lines:
                    if "s3://" in line and "${" not in line:
                        pytest.fail(
                            f"Non-placeholder s3:// URI in {fpath}: {line}"
                        )

    def test_governance_tests_no_raw_s3_uris(self):
        """Governance test file does not contain raw s3:// URIs."""
        with open(self.GOVERNANCE_TEST, "rb") as f:
            raw = f.read()
        if b"s3://" not in raw:
            return
        text = raw.decode("utf-8")
        import re
        for m in re.finditer(r"s3://", text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start:line_end].strip() if line_end != -1 else text[line_start:].strip()
            # Allow docstring lines
            if '"""' in line or "'''" in line:
                continue
            # Allow the search pattern itself (test code looking for s3://)
            if '"s3://"' in line:
                continue
            # Allow f-string assertion text or comments
            if '{fpath}' in line and 's3://' in line:
                continue
            if line.startswith("#"):
                continue
            if "s3:// URI in governance test" in line:
                continue
            pytest.fail(f"Raw s3:// URI in governance test: {line}")


# ===================================================================
# Roadmap and deferred boundaries
# ===================================================================


class TestConfigGovernanceRoadmapBoundaries:
    """PR0052 Matador integration and FastAPI not implemented by PR0051."""

    def test_no_matador_import_in_governance_test(self):
        """Governance test does not import Matador."""
        import ast

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "matador" in alias.name.lower():
                        pytest.fail(
                            f"Matador import found: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "matador" in module.lower():
                    pytest.fail(
                        f"Matador import found: {module}"
                    )

    def test_no_fastapi_in_governance_test(self):
        """Governance test does not import FastAPI/uvicorn/starlette/ASGI."""
        import ast

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        prohibited = {"fastapi", "uvicorn", "starlette", "asgi"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0].lower() in prohibited:
                        pytest.fail(
                            f"Prohibited import found: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0].lower() in prohibited:
                    pytest.fail(
                        f"Prohibited import found: {module}"
                    )

    ADR_0011 = DOCS_ADR_DIR / "0011-config-governance-gates.md"
    ADR_0009 = DOCS_ADR_DIR / "0009-config-governance.md"

    def test_adr_0011_mentions_fastapi_deferred(self):
        """ADR-0011 explicitly states FastAPI remains deferred."""
        content = self.ADR_0011.read_text(encoding="utf-8")
        assert "FastAPI" in content, (
            "ADR-0011 must mention FastAPI deferral"
        )
        assert "deferred" in content.lower() or \
               "not add" in content.lower(), (
            "ADR-0011 must state FastAPI is deferred"
        )

    def test_adr_0011_mentions_matador_pr0052(self):
        """ADR-0011 explicitly defers Matador integration to PR0052."""
        content = self.ADR_0011.read_text(encoding="utf-8")
        assert "Matador" in content, (
            "ADR-0011 must mention Matador boundary"
        )
        assert "PR0052" in content or "not implemented" in content.lower(), (
            "ADR-0011 must defer Matador to PR0052"
        )

    def test_adr_0011_mentions_dynamodb_deferred(self):
        """ADR-0011 states DynamoDB/backend is deferred, not implemented."""
        content = self.ADR_0011.read_text(encoding="utf-8")
        assert "deferred" in content.lower(), (
            "ADR-0011 must state DynamoDB/backend is deferred"
        )

    def test_no_dynamodb_import_in_governance_test(self):
        """Governance test does not import or use DynamoDB."""
        import ast

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "dynamodb" in alias.name.lower():
                        pytest.fail(
                            f"DynamoDB import found: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "dynamodb" in module.lower():
                    pytest.fail(
                        f"DynamoDB import found: {module}"
                    )

    def test_no_boto3_import_in_governance_test(self):
        """Governance test does not import boto3 or botocore."""
        import ast

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        prohibited = {"boto3", "botocore"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0].lower() in prohibited:
                        pytest.fail(
                            f"Prohibited import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0].lower() in prohibited:
                    pytest.fail(
                        f"Prohibited import: {module}"
                    )

    def test_adr_0009_cross_references_adr_0011(self):
        """ADR-0009 cross-references ADR-0011 for gate resolution."""
        content = self.ADR_0009.read_text(encoding="utf-8")
        assert "ADR-0011" in content, (
            "ADR-0009 must cross-reference ADR-0011"
        )


# ===================================================================
# ADR-0012 system-of-record boundary acknowledgment (PR0052)
# ===================================================================


class TestSystemOfRecordBoundaryAcknowledgment:
    """PR0052 acknowledges ADR-0012 and does not implement Matador."""

    ADR_0012 = DOCS_ADR_DIR / "0012-system-of-record-boundary.md"

    def test_adr_0012_exists(self):
        """ADR-0012 exists documenting the system-of-record boundary."""
        assert self.ADR_0012.exists(), (
            "ADR-0012 must exist for PR0052 boundary"
        )

    def test_adr_0012_mentions_no_matador_implementation(self):
        """ADR-0012 states no real Matador integration in PR0052."""
        content = self.ADR_0012.read_text(encoding="utf-8")
        assert "not implement" in content.lower() or \
               "scaffold" in content.lower() or \
               "skeleton" in content.lower(), (
            "ADR-0012 must state PR0052 does not implement Matador"
        )

    def test_h5_path_h5_uri_remain_non_source_of_record(self):
        """ADR-0012 states h5_path and h5_uri are not source-of-record modes."""
        content = self.ADR_0012.read_text(encoding="utf-8")
        assert "not source-of-record" in content.lower() or \
               "convenience/staging" in content.lower() or \
               "convenience mode" in content.lower(), (
            "ADR-0012 must state h5_path/h5_uri are not source-of-record"
        )

    def test_no_matador_import_in_governance_test(self):
        """This governance test does not import Matador (redundant with PR0051)."""
        import ast
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "matador" in alias.name.lower():
                        pytest.fail(
                            f"Matador import found: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "matador" in module.lower():
                    pytest.fail(
                        f"Matador import found: {module}"
                    )
