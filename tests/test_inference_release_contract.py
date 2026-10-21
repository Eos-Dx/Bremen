"""Tests for the Inference Release manifest contract v1 (IR-02).

Synthetic manifests only. No real S3 access, no real model artifacts, no
network calls. Validates ``bremen.inference-release.v1`` structural
validation: required/forbidden fields, SHA-256 shape, path-traversal
rejection, duplicate-file rejection, unsafe-entrypoint rejection, and the
module's platform/science independence.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any

import pytest

from bremen.contracts.inference_release import (
    SCHEMA_ID,
    InferenceReleaseContractError,
    InferenceReleaseManifest,
    validate_release_manifest,
)
from bremen.contracts.worker_protocol import PROTOCOL_ID as WORKER_PROTOCOL_ID

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "bremen" / "contracts" / "inference_release.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_manifest(**overrides: Any) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_ID,
        "release_id": "bremen-paper-reference-v0-2-0-rel-20261021",
        "model": {
            "model_id": "bremen-paper-reference-v0-2-0",
            "model_version": "0.2.0-paper-reference",
            "workflow_id": "bremen",
            "artifact_identity": "bremen_paper_reference_symmetry_logreg",
        },
        "compatibility": {
            "python_implementation": "cpython",
            "python_version": "3.13",
            "abi": "cp313",
            "os": "linux",
            "arch": "x86_64",
            "worker_protocol_version": WORKER_PROTOCOL_ID,
            "native_libraries": [],
        },
        "entrypoint": {"module": "bremen_plugin.runtime", "callable": "run"},
        "files": [
            {
                "role": "plugin_wheel",
                "relative_path": "wheels/plugin.whl",
                "s3_key": "releases/r1/plugin.whl",
                "sha256": "a" * 64,
                "size_bytes": 100,
            },
            {
                "role": "artifact",
                "relative_path": "artifacts/model.joblib",
                "s3_key": "releases/r1/model.joblib",
                "sha256": "b" * 64,
                "size_bytes": 200,
            },
        ],
        "environments": {"main": {"requirements_lock_sha256": "c" * 64}},
        "scientific_metadata": {
            "preprocessing_release": "v0.1.7-beta",
            "artifact_checksum": "b" * 64,
            "threshold_source": "paper_train_all_target_sensitivity",
        },
        "golden_tests": [
            {
                "role": "golden_fixture",
                "relative_path": "golden/nova227.json",
                "s3_key": "releases/r1/golden/nova227.json",
                "sha256": "d" * 64,
            },
        ],
        "build": {
            "source_repository": "Eos-Dx/Bremen",
            "commit": "1b08958fe75dda822f02f725e606d5cd4737da0",
            "build_id": "build-1",
        },
    }
    manifest.update(overrides)
    return manifest


def _ast_import_modules(path: Path) -> set[str]:
    """Return every fully-dotted module imported by ``path`` (not just the
    top-level segment), so ``bremen.contracts.worker_protocol`` and
    ``bremen.platform`` are distinguishable.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


# ---------------------------------------------------------------------------
# 1. Valid manifest
# ---------------------------------------------------------------------------


class TestValidManifest:
    def test_valid_manifest_validates(self):
        manifest = validate_release_manifest(_valid_manifest())
        assert isinstance(manifest, InferenceReleaseManifest)
        assert manifest.schema_version == SCHEMA_ID
        assert manifest.release_id == "bremen-paper-reference-v0-2-0-rel-20261021"
        assert manifest.model.model_id == "bremen-paper-reference-v0-2-0"
        assert manifest.compatibility.worker_protocol_version == WORKER_PROTOCOL_ID
        assert manifest.entrypoint.module == "bremen_plugin.runtime"
        assert len(manifest.files) == 2
        assert len(manifest.golden_tests) == 1
        assert manifest.build.commit == "1b08958fe75dda822f02f725e606d5cd4737da0"

    def test_valid_manifest_with_auxiliary_environment(self):
        data = _valid_manifest()
        data["environments"]["aux_preprocess"] = {"requirements_lock_sha256": "e" * 64}
        manifest = validate_release_manifest(data)
        assert "aux_preprocess" in manifest.environments
        assert "main" in manifest.environments

    def test_entrypoint_without_callable(self):
        data = _valid_manifest()
        data["entrypoint"] = {"module": "bremen_plugin.runtime"}
        manifest = validate_release_manifest(data)
        assert manifest.entrypoint.callable == ""

    def test_missing_optional_fields_default_safely(self):
        data = _valid_manifest()
        assert "feature_order_hash" not in data["scientific_metadata"]
        assert "config_hash" not in data["scientific_metadata"]
        manifest = validate_release_manifest(data)
        assert manifest.scientific_metadata.feature_order_hash == ""
        assert manifest.scientific_metadata.config_hash == ""


# ---------------------------------------------------------------------------
# 2. Invalid schema version
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_wrong_schema_version_rejected(self):
        data = _valid_manifest(schema_version="bremen.inference-release.v2")
        with pytest.raises(InferenceReleaseContractError, match="schema_version"):
            validate_release_manifest(data)

    def test_missing_schema_version_rejected(self):
        data = _valid_manifest()
        del data["schema_version"]
        with pytest.raises(InferenceReleaseContractError, match="missing required fields"):
            validate_release_manifest(data)

    def test_unknown_top_level_field_rejected(self):
        data = _valid_manifest()
        data["unexpected_field"] = "x"
        with pytest.raises(InferenceReleaseContractError, match="unsupported fields"):
            validate_release_manifest(data)

    def test_manifest_must_be_object(self):
        with pytest.raises(InferenceReleaseContractError, match="JSON object"):
            validate_release_manifest([])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 3. Invalid SHA-256
# ---------------------------------------------------------------------------


class TestSha256Validation:
    @pytest.mark.parametrize(
        "bad_sha",
        [
            "not-a-hash",
            "A" * 64,  # uppercase rejected
            "a" * 63,  # too short
            "a" * 65,  # too long
            "",
            12345,
        ],
    )
    def test_invalid_file_sha256_rejected(self, bad_sha):
        data = _valid_manifest()
        data["files"][0]["sha256"] = bad_sha
        with pytest.raises(InferenceReleaseContractError, match="sha256"):
            validate_release_manifest(data)

    def test_invalid_artifact_checksum_rejected(self):
        data = _valid_manifest()
        data["scientific_metadata"]["artifact_checksum"] = "zz" * 32
        with pytest.raises(InferenceReleaseContractError, match="artifact_checksum"):
            validate_release_manifest(data)

    def test_invalid_environment_lock_sha256_rejected(self):
        data = _valid_manifest()
        data["environments"]["main"]["requirements_lock_sha256"] = "short"
        with pytest.raises(InferenceReleaseContractError, match="requirements_lock_sha256"):
            validate_release_manifest(data)


# ---------------------------------------------------------------------------
# 4. Path traversal
# ---------------------------------------------------------------------------


class TestPathTraversal:
    @pytest.mark.parametrize(
        "bad_path",
        [
            "../escape.whl",
            "a/../../escape.whl",
            "/absolute/path.whl",
            "a//b.whl",
            "a/./b.whl",
        ],
    )
    def test_relative_path_traversal_rejected(self, bad_path):
        data = _valid_manifest()
        data["files"][0]["relative_path"] = bad_path
        with pytest.raises(InferenceReleaseContractError):
            validate_release_manifest(data)

    def test_s3_key_traversal_rejected(self):
        data = _valid_manifest()
        data["files"][0]["s3_key"] = "releases/../secret/plugin.whl"
        with pytest.raises(InferenceReleaseContractError, match="s3_key"):
            validate_release_manifest(data)

    def test_absolute_s3_key_rejected(self):
        data = _valid_manifest()
        data["files"][0]["s3_key"] = "/releases/plugin.whl"
        with pytest.raises(InferenceReleaseContractError, match="s3_key"):
            validate_release_manifest(data)

    def test_golden_test_path_traversal_rejected(self):
        data = _valid_manifest()
        data["golden_tests"][0]["relative_path"] = "../../escape.json"
        with pytest.raises(InferenceReleaseContractError):
            validate_release_manifest(data)


# ---------------------------------------------------------------------------
# 5. Duplicate release files
# ---------------------------------------------------------------------------


class TestDuplicateFiles:
    def test_duplicate_relative_path_within_files_rejected(self):
        data = _valid_manifest()
        duplicate = dict(data["files"][0])
        duplicate["s3_key"] = "releases/r1/other.whl"
        data["files"].append(duplicate)
        with pytest.raises(InferenceReleaseContractError, match="Duplicate relative_path"):
            validate_release_manifest(data)

    def test_duplicate_relative_path_across_files_and_golden_tests_rejected(self):
        data = _valid_manifest()
        data["golden_tests"][0]["relative_path"] = data["files"][0]["relative_path"]
        with pytest.raises(InferenceReleaseContractError, match="Duplicate relative_path"):
            validate_release_manifest(data)

    def test_empty_files_list_rejected(self):
        data = _valid_manifest(files=[])
        with pytest.raises(InferenceReleaseContractError, match="files"):
            validate_release_manifest(data)


# ---------------------------------------------------------------------------
# 6. Unsafe entrypoint
# ---------------------------------------------------------------------------


class TestUnsafeEntrypoint:
    @pytest.mark.parametrize(
        "bad_module",
        [
            "os.system; rm -rf /",
            "../escape",
            "/usr/bin/python",
            "bremen_plugin/runtime",
            ".bremen_plugin",
            "bremen_plugin.",
            "",
            "bremen plugin",
        ],
    )
    def test_unsafe_entrypoint_module_rejected(self, bad_module):
        data = _valid_manifest()
        data["entrypoint"]["module"] = bad_module
        with pytest.raises(InferenceReleaseContractError, match="entrypoint"):
            validate_release_manifest(data)

    def test_unsafe_entrypoint_callable_rejected(self):
        data = _valid_manifest()
        data["entrypoint"]["callable"] = "run(); import os"
        with pytest.raises(InferenceReleaseContractError, match="callable"):
            validate_release_manifest(data)

    def test_entrypoint_unknown_field_rejected(self):
        data = _valid_manifest()
        data["entrypoint"]["shell_command"] = "rm -rf /"
        with pytest.raises(InferenceReleaseContractError, match="entrypoint"):
            validate_release_manifest(data)


# ---------------------------------------------------------------------------
# Additional structural rejections
# ---------------------------------------------------------------------------


class TestStructuralRejections:
    def test_missing_environments_main_rejected(self):
        data = _valid_manifest()
        data["environments"] = {"aux": {}}
        with pytest.raises(InferenceReleaseContractError, match="main"):
            validate_release_manifest(data)

    def test_wrong_worker_protocol_version_rejected(self):
        data = _valid_manifest()
        data["compatibility"]["worker_protocol_version"] = "bremen.worker.v0"
        with pytest.raises(InferenceReleaseContractError, match="worker_protocol_version"):
            validate_release_manifest(data)

    def test_invalid_commit_rejected(self):
        data = _valid_manifest()
        data["build"]["commit"] = "not-a-sha"
        with pytest.raises(InferenceReleaseContractError, match="commit"):
            validate_release_manifest(data)

    def test_unknown_field_in_model_block_rejected(self):
        data = _valid_manifest()
        data["model"]["extra"] = "x"
        with pytest.raises(InferenceReleaseContractError, match="model has unsupported"):
            validate_release_manifest(data)

    def test_deepcopy_independence(self):
        """Sanity: mutating the input after validation does not affect the
        returned manifest (defensive copying semantics are not required to
        be literal deep copies, but the returned dataclass must be immutable)."""
        data = _valid_manifest()
        manifest = validate_release_manifest(copy.deepcopy(data))
        data["release_id"] = "mutated"
        assert manifest.release_id == "bremen-paper-reference-v0-2-0-rel-20261021"
        with pytest.raises(AttributeError):
            manifest.release_id = "cannot-mutate"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 22. Module remains platform/science independent
# ---------------------------------------------------------------------------


class TestImportBoundary:
    def test_module_imports_no_platform_or_science_code(self):
        modules = _ast_import_modules(MODULE_PATH)
        forbidden_prefixes = (
            "bremen.platform",
            "bremen.model_packages",
            "bremen.api",
            "boto3",
            "botocore",
            "fastapi",
            "uvicorn",
            "joblib",
            "sklearn",
            "h5py",
        )
        for module in modules:
            for prefix in forbidden_prefixes:
                assert not module.startswith(prefix), (
                    f"inference_release.py imports {module!r}, which starts "
                    f"with forbidden prefix {prefix!r}"
                )

    def test_module_only_imports_sibling_contracts_and_stdlib(self):
        modules = _ast_import_modules(MODULE_PATH)
        allowed_bremen_prefixes = ("bremen.contracts",)
        for module in modules:
            if module.startswith("bremen"):
                assert any(module.startswith(p) for p in allowed_bremen_prefixes), (
                    f"inference_release.py imports {module!r}, which is not a "
                    "sibling contracts module"
                )

    def test_module_imports_successfully(self):
        import bremen.contracts.inference_release as mod

        assert mod.SCHEMA_ID == "bremen.inference-release.v1"
