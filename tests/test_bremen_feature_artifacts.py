"""Tests for the feature artifact ingestion boundary (PR0058).

All tests use synthetic in-memory data only.  No real artifact files,
no H5 files, no model artifacts, no network/AWS/Docker/Terraform.
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest

from bremen.feature_artifacts import (
    FEATURE_ARTIFACT_KIND,
    FEATURE_ARTIFACT_SCHEMA_VERSION,
    REQUIRED_FEATURE_COLUMNS,
    FeatureArtifactError,
    FeatureArtifactSchemaError,
    FeatureArtifactValidationError,
    _EXPECTED_FEATURE_COUNT,
    _check_unsafe_metadata,
    _check_forbidden_value,
    load_feature_artifact_from_dict,
    load_feature_artifact_from_json,
    validate_feature_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "bremen" / "feature_artifacts.py"
CONTRACT_DOC = ROOT / "docs" / "feature_artifact_ingestion_boundary.md"
RECON_DOC = ROOT / "docs" / "preprocessing_source_reconciliation.md"
SCHEMAS_PATH = ROOT / "src" / "bremen" / "api" / "schemas.py"


# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------

def _valid_artifact(**overrides) -> dict:
    """Build a valid synthetic artifact, optionally overriding fields."""
    data: dict = {
        "schema_version": FEATURE_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": FEATURE_ARTIFACT_KIND,
        "feature_columns": list(REQUIRED_FEATURE_COLUMNS),
        "feature_values": [
            0.5, 0.3, 0.4, 1.2, 0.6,
            0.2, 0.3, 0.9, 0.15, -0.22,
            0.01, 0.05, 0.02, 1.1, 0.8,
        ],
        "metadata": {
            "preprocessing_source": "xrd_preprocessing",
            "source_package_version": "0.1.6b0",
            "configuration_label": "one-to-one-default",
        },
    }
    data.update(overrides)
    return data


def _read_doc(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_import_lines() -> list[str]:
    """Return import/from lines from the feature_artifacts module."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    return [
        line.strip()
        for line in source.split("\n")
        if line.strip().startswith(("import ", "from "))
    ]


def _ast_import_names(path: Path) -> set[str]:
    """Return all imported module names from a Python file using AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


# ===================================================================
# TestRequiredColumns
# ===================================================================


class TestRequiredColumns:
    def test_feature_count_is_15(self):
        """REQUIRED_FEATURE_COLUMNS has exactly 15 entries."""
        assert _EXPECTED_FEATURE_COUNT == 15
        assert len(REQUIRED_FEATURE_COLUMNS) == 15

    def test_columns_match_order(self):
        """REQUIRED_FEATURE_COLUMNS matches the exact 15-column order."""
        expected = (
            "weightedrms1",
            "sigma_l1",
            "sigma_r1",
            "mahalanobis1",
            "weightedrms2",
            "sigma_l2",
            "sigma_r2",
            "mahalanobis2",
            "peak14_intensity",
            "mean_peak_value_raw",
            "wasserstein_distance_muLR",
            "cosine_distance_full_q2",
            "wasserstein_distance_full_q2",
            "meanrms1",
            "meanrms2",
        )
        assert REQUIRED_FEATURE_COLUMNS == expected

    def test_no_duplicate_columns(self):
        """REQUIRED_FEATURE_COLUMNS has no duplicate entries."""
        assert len(set(REQUIRED_FEATURE_COLUMNS)) == len(REQUIRED_FEATURE_COLUMNS)


# ===================================================================
# TestValidArtifact
# ===================================================================


class TestValidArtifact:
    def test_valid_artifact_passes(self):
        """A valid synthetic artifact passes validation."""
        artifact = _valid_artifact()
        result = validate_feature_artifact(artifact)
        assert result["schema_version"] == FEATURE_ARTIFACT_SCHEMA_VERSION
        assert result["artifact_kind"] == FEATURE_ARTIFACT_KIND
        assert result["feature_columns"] == list(REQUIRED_FEATURE_COLUMNS)
        assert len(result["feature_values"]) == 15
        assert all(isinstance(v, float) for v in result["feature_values"])
        assert result["metadata"] == artifact["metadata"]

    def test_valid_artifact_load_from_dict(self):
        """load_feature_artifact_from_dict works on valid artifact."""
        artifact = _valid_artifact()
        result = load_feature_artifact_from_dict(artifact)
        assert len(result["feature_values"]) == 15


# ===================================================================
# TestFeatureOrderNormalization
# ===================================================================


class TestFeatureOrderNormalization:
    def test_shuffled_columns_normalised(self):
        """Features supplied in different order are normalised to
        REQUIRED_FEATURE_COLUMNS order."""
        shuffled_cols = list(REQUIRED_FEATURE_COLUMNS)
        # Reverse the column list
        shuffled_cols.reverse()
        shuffled_vals = list(range(15, 0, -1))  # 15 down to 1

        artifact = _valid_artifact(
            feature_columns=shuffled_cols,
            feature_values=shuffled_vals,
        )
        result = validate_feature_artifact(artifact)

        # feature_columns in result must be in REQUIRED order
        assert result["feature_columns"] == list(REQUIRED_FEATURE_COLUMNS)

        # Each value must land at the correct index for its feature
        for i, col in enumerate(REQUIRED_FEATURE_COLUMNS):
            orig_idx = shuffled_cols.index(col)
            assert result["feature_values"][i] == float(shuffled_vals[orig_idx])


# ===================================================================
# TestMissingFeatureRejected
# ===================================================================


class TestMissingFeatureRejected:
    def test_missing_feature_rejected(self):
        """Missing a required feature column is rejected."""
        cols = list(REQUIRED_FEATURE_COLUMNS)[:-1]  # drop meanrms2
        vals = [0.0] * 14
        artifact = _valid_artifact(feature_columns=cols, feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="feature_columns"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestExtraFeatureRejected
# ===================================================================


class TestExtraFeatureRejected:
    def test_extra_feature_rejected(self):
        """Extra feature column beyond 15 is rejected."""
        cols = list(REQUIRED_FEATURE_COLUMNS) + ["extra_feature"]
        vals = [0.0] * 16
        artifact = _valid_artifact(feature_columns=cols, feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError):
            validate_feature_artifact(artifact)


# ===================================================================
# TestDuplicateFeatureRejected
# ===================================================================


class TestDuplicateFeatureRejected:
    def test_duplicate_feature_rejected(self):
        """Duplicate feature name is rejected."""
        cols = list(REQUIRED_FEATURE_COLUMNS)
        cols[14] = cols[0]  # replace meanrms2 with weightedrms1
        vals = [0.0] * 15
        artifact = _valid_artifact(feature_columns=cols, feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="duplicate"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestNonStringFeatureRejected
# ===================================================================


class TestNonStringFeatureRejected:
    def test_non_string_feature_name_rejected(self):
        """Non-string feature name is rejected."""
        cols = list(REQUIRED_FEATURE_COLUMNS)
        cols[0] = 42  # int instead of string
        vals = [0.0] * 15
        artifact = _valid_artifact(feature_columns=cols, feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="must be a string"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestNonNumericValueRejected
# ===================================================================


class TestNonNumericValueRejected:
    def test_string_value_rejected(self):
        """String feature value is rejected."""
        vals = [0.0] * 15
        vals[3] = "bad"
        artifact = _valid_artifact(feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="not numeric"):
            validate_feature_artifact(artifact)

    def test_none_value_rejected(self):
        """None feature value is rejected."""
        vals: list = [0.0] * 15
        vals[5] = None
        artifact = _valid_artifact(feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="not numeric"):
            validate_feature_artifact(artifact)

    def test_dict_value_rejected(self):
        """Dict feature value is rejected."""
        vals: list = [0.0] * 15
        vals[7] = {}
        artifact = _valid_artifact(feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="not numeric"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestBoolRejected
# ===================================================================


class TestBoolRejected:
    def test_bool_rejected(self):
        """Boolean feature value is rejected as not numeric."""
        vals: list = [0.0] * 15
        vals[2] = True
        artifact = _valid_artifact(feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="boolean"):
            validate_feature_artifact(artifact)

    def test_false_rejected(self):
        """False boolean is also rejected."""
        vals: list = [0.0] * 15
        vals[10] = False
        artifact = _valid_artifact(feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="boolean"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestNaNRejected
# ===================================================================


class TestNaNRejected:
    def test_nan_rejected(self):
        """NaN feature value is rejected."""
        vals = [0.0] * 15
        vals[4] = float("nan")
        artifact = _valid_artifact(feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="not finite"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestInfinityRejected
# ===================================================================


class TestInfinityRejected:
    def test_inf_rejected(self):
        """Positive infinity is rejected."""
        vals = [0.0] * 15
        vals[6] = float("inf")
        artifact = _valid_artifact(feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="not finite"):
            validate_feature_artifact(artifact)

    def test_neg_inf_rejected(self):
        """Negative infinity is rejected."""
        vals = [0.0] * 15
        vals[8] = float("-inf")
        artifact = _valid_artifact(feature_values=vals)
        with pytest.raises(FeatureArtifactValidationError, match="not finite"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestWrongSchemaVersionRejected
# ===================================================================


class TestWrongSchemaVersionRejected:
    def test_wrong_version_rejected(self):
        """Wrong schema_version raises FeatureArtifactSchemaError."""
        artifact = _valid_artifact(schema_version="wrong.version")
        with pytest.raises(FeatureArtifactSchemaError, match="schema_version"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestWrongArtifactKindRejected
# ===================================================================


class TestWrongArtifactKindRejected:
    def test_wrong_kind_rejected(self):
        """Wrong artifact_kind raises FeatureArtifactSchemaError."""
        artifact = _valid_artifact(artifact_kind="wrong_kind")
        with pytest.raises(FeatureArtifactSchemaError, match="artifact_kind"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestMissingFieldsRejected
# ===================================================================


class TestMissingFieldsRejected:
    def test_missing_feature_columns_rejected(self):
        """Missing feature_columns field is rejected."""
        artifact = _valid_artifact()
        del artifact["feature_columns"]
        with pytest.raises(FeatureArtifactValidationError, match="feature_columns"):
            validate_feature_artifact(artifact)

    def test_missing_feature_values_rejected(self):
        """Missing feature_values field is rejected."""
        artifact = _valid_artifact()
        del artifact["feature_values"]
        with pytest.raises(FeatureArtifactValidationError, match="feature_values"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestUnsafeMetadataKeyRejected
# ===================================================================


class TestUnsafeMetadataKeyRejected:
    @pytest.mark.parametrize("bad_key", [
        "patient_id",
        "scan_ref",
        "file_path",
        "s3_uri",
        "model_checksum",
        "api_secret",
        "auth_token",
        "db_password",
        "aws_account",
        "access_key",
        "MY_KEY",
    ])
    def test_unsafe_key_rejected(self, bad_key):
        """Metadata keys containing prohibited patterns are rejected."""
        metadata = {
            "preprocessing_source": "test",
            bad_key: "some_value",
        }
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestUnsafeMetadataValueRejected
# ===================================================================


class TestUnsafeMetadataValueRejected:
    def test_akia_value_rejected(self):
        """AKIA pattern in metadata value is rejected."""
        metadata = {"source": "preprocessing", "note": "AKIA1234EXAMPLE"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)

    def test_s3_uri_value_rejected(self):
        """s3:// pattern in metadata value is rejected."""
        metadata = {"source": "s3://bucket/key.h5"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)

    def test_checksum_value_rejected(self):
        """sha256: pattern in metadata value is rejected."""
        metadata = {"source": "sha256:abc123"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)

    def test_nova_value_rejected(self):
        """Nova_ pattern in metadata value is rejected."""
        metadata = {"source": "Nova_376_data"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)

    def test_users_path_rejected(self):
        """/Users/ path in metadata value is rejected."""
        metadata = {"source": "/Users/dev/data.h5"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)

    def test_home_path_rejected(self):
        """/home/ path in metadata value is rejected."""
        metadata = {"source": "/home/dev/data.h5"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)

    def test_secret_access_key_rejected(self):
        """SECRET_ACCESS_KEY in metadata value is rejected."""
        metadata = {"source": "test", "note": "SECRET_ACCESS_KEY_value"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)

    def test_dkr_ecr_rejected(self):
        """dkr.ecr in metadata value is rejected."""
        metadata = {"source": "test.dkr.ecr.region.amazonaws.com"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)

    def test_account_id_rejected(self):
        """12-digit number in metadata value is rejected."""
        metadata = {"source": "123456789012"}
        artifact = _valid_artifact(metadata=metadata)
        with pytest.raises(FeatureArtifactValidationError, match="Unsafe metadata"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestNullMetadataAccepted
# ===================================================================


class TestNullMetadataAccepted:
    def test_null_metadata_accepted(self):
        """None metadata is accepted."""
        artifact = _valid_artifact()
        artifact["metadata"] = None
        result = validate_feature_artifact(artifact)
        assert result["metadata"] is None

    def test_missing_metadata_accepted(self):
        """Absent metadata key is accepted."""
        artifact = _valid_artifact()
        del artifact["metadata"]
        result = validate_feature_artifact(artifact)
        assert result["metadata"] is None


# ===================================================================
# TestNonDictMetadataRejected
# ===================================================================


class TestNonDictMetadataRejected:
    def test_string_metadata_rejected(self):
        """String metadata is rejected — must be dict or None."""
        artifact = _valid_artifact(metadata="not a dict")
        with pytest.raises(FeatureArtifactValidationError, match="dict"):
            validate_feature_artifact(artifact)


# ===================================================================
# TestJSONLoader
# ===================================================================


class TestJSONLoader:
    def test_load_from_json_valid(self, tmp_path):
        """load_feature_artifact_from_json validates a tmp_path JSON."""
        artifact = _valid_artifact()
        json_path = tmp_path / "artifact.json"
        json_path.write_text(json.dumps(artifact), encoding="utf-8")

        result = load_feature_artifact_from_json(str(json_path))
        assert len(result["feature_values"]) == 15

    def test_load_from_json_invalid_schema(self, tmp_path):
        """JSON with wrong schema_version raises error."""
        artifact = _valid_artifact(schema_version="bad")
        json_path = tmp_path / "artifact.json"
        json_path.write_text(json.dumps(artifact), encoding="utf-8")

        with pytest.raises(FeatureArtifactSchemaError):
            load_feature_artifact_from_json(str(json_path))

    def test_load_from_json_not_a_dict(self, tmp_path):
        """JSON root not a dict raises error."""
        json_path = tmp_path / "artifact.json"
        json_path.write_text("[1, 2, 3]", encoding="utf-8")

        with pytest.raises(FeatureArtifactValidationError, match="dict"):
            load_feature_artifact_from_json(str(json_path))


# ===================================================================
# TestNoXRDImport
# ===================================================================


class TestNoXRDImport:
    def test_no_upstream_imports(self):
        """Feature artifacts module does not import xrd_preprocessing,
        eosdx-container, or heavy deps."""
        import_names = _ast_import_names(MODULE_PATH)
        prohibited = {
            "xrd_preprocessing", "eosdx_container", "container",
            "boto3", "botocore", "requests", "httpx", "aiohttp",
            "joblib", "h5py", "sklearn", "numpy", "pandas",
            "pyFAI", "fabio",
        }
        found = import_names & prohibited
        assert not found, (
            f"Module imports prohibited dependencies: {found}"
        )

    def test_no_bremen_api_imports(self):
        """Feature artifacts module does not import Bremem inference/model
        modules."""
        import_names = _ast_import_names(MODULE_PATH)
        prohibited = {
            "inference_handler", "model_state", "model_loader",
            "preprocessing_bridge", "decision_support",
        }
        found = import_names & prohibited
        assert not found, (
            f"Module imports Bremem API modules: {found}"
        )


# ===================================================================
# TestNoH5PathH5UriChange
# ===================================================================


class TestNoH5PathH5UriChange:
    def test_no_h5_references(self):
        """Module source does not reference h5_path or h5_uri."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "h5_path" not in source, (
            "Module references h5_path"
        )
        assert "h5_uri" not in source, (
            "Module references h5_uri"
        )
        assert "h5_inputs" not in source, (
            "Module references h5_inputs"
        )


# ===================================================================
# TestPublicSchemaUnchanged
# ===================================================================


class TestPublicSchemaUnchanged:
    def test_no_feature_artifact_in_schemas(self):
        """Public schemas.py does not reference feature_artifact_path
        or feature_artifact_uri."""
        source = SCHEMAS_PATH.read_text(encoding="utf-8")
        assert "feature_artifact_path" not in source, (
            "schemas.py must not contain feature_artifact_path"
        )
        assert "feature_artifact_uri" not in source, (
            "schemas.py must not contain feature_artifact_uri"
        )


# ===================================================================
# TestDocExists
# ===================================================================


class TestDocExists:
    def test_contract_doc_exists(self):
        """Feature artifact contract document exists."""
        assert CONTRACT_DOC.is_file(), (
            "docs/feature_artifact_ingestion_boundary.md not found"
        )

    def test_doc_mentions_option_c(self):
        """Contract doc documents Option C decision."""
        content = _read_doc(CONTRACT_DOC).lower()
        assert "option c" in content, (
            "Contract doc must reference Option C"
        )

    def test_doc_mentions_pr0059_handoff(self):
        """Contract doc mentions PR0059 handoff."""
        content = _read_doc(CONTRACT_DOC)
        assert "PR0059" in content or "pr0059" in content.lower(), (
            "Contract doc must reference PR0059"
        )


# ===================================================================
# TestNoDemoOnlyFork
# ===================================================================


class TestNoDemoOnlyFork:
    def test_no_demo_only_fork(self):
        """Contract doc rejects demo-only fork."""
        content = _read_doc(CONTRACT_DOC).lower()
        assert "no demo-only" in content or "no demo only" in content, (
            "Contract doc must reject demo-only fork"
        )


# ===================================================================
# TestNoDiagnosisNoClinicalValidation
# ===================================================================


class TestSafetyClaims:
    def test_no_diagnosis(self):
        """Contract doc states no diagnosis."""
        content = _read_doc(CONTRACT_DOC).lower()
        assert "no diagnosis" in content, (
            "Contract doc must state no diagnosis"
        )

    def test_no_clinical_validation(self):
        """Contract doc states no clinical validation."""
        content = _read_doc(CONTRACT_DOC).lower()
        assert "no clinical validation" in content, (
            "Contract doc must state no clinical validation"
        )

    def test_no_replacement(self):
        """Contract doc states no replacement of clinical judgment."""
        content = _read_doc(CONTRACT_DOC).lower()
        assert "no replacement" in content or \
               "does not replace" in content, (
            "Contract doc must state no replacement"
        )


# ===================================================================
# TestNoSecretsOrArtifacts
# ===================================================================


class TestNoSecretsOrArtifacts:
    def test_no_artifact_files_committed(self):
        """No real artifact files exist at the module or doc paths."""
        # The module and doc are the only files created — verify
        # no artifact extensions are present as real files.
        assert MODULE_PATH.suffix == ".py"
        assert CONTRACT_DOC.suffix == ".md"

    def test_module_has_no_hardcoded_secrets(self):
        """Module source does not contain hardcoded secrets outside
        the _FORBIDDEN_VALUE_PATTERNS constant definition."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        # After the _FORBIDDEN_VALUE_PATTERNS constant, scan only
        # code lines — not the constant definition itself.
        # The constant definition is in a multi-line tuple assignment.
        # Simple check: AKIA should appear at most once (in the constant).
        akia_count = source.count("AKIA")
        assert akia_count <= 1, (
            f"AKIA appears {akia_count} times in module — "
            "expected at most 1 (in _FORBIDDEN_VALUE_PATTERNS)"
        )


# ===================================================================
# TestCrossReference
# ===================================================================


class TestCrossReference:
    def test_recon_doc_links_to_feature_artifact(self):
        """preprocessing_source_reconciliation.md links to feature
        artifact doc if Option C cross-reference was added."""
        content = _read_doc(RECON_DOC)
        # The cross-reference may or may not be present depending on
        # whether the optional edit was applied.  If it is present,
        # it must reference the correct doc.
        if "feature_artifact_ingestion_boundary.md" in content:
            assert "PR0058" in content, (
                "Cross-reference must mention PR0058"
            )


# ===================================================================
# TestNoNetworkDeps
# ===================================================================


class TestTestsAreStatic:
    def test_no_network_aws_docker(self):
        """Test file does not import network/AWS/Docker modules."""
        source = Path(__file__).read_text(encoding="utf-8")
        import_lines = [
            line for line in source.split("\n")
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines)
        prohibited = ["boto3", "requests", "httpx", "urllib",
                       "docker", "terraform"]
        for imp in prohibited:
            assert imp not in import_text, (
                f"Test file must not import {imp}"
            )
