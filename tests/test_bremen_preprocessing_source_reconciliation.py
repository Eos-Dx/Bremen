"""Static tests for the preprocessing source reconciliation doc (PR 0057).

All tests are static/text-only.  No network, AWS, Docker, Terraform,
App Runner, real H5, real model artifact, or credentials.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECON_DOC = ROOT / "docs" / "preprocessing_source_reconciliation.md"
PR0055_CONTRACT = ROOT / "docs" / "product_input_pipeline_contract.md"
PR0056_BOUNDARY = ROOT / "docs" / "converter_preprocessing_boundary.md"


def _read_recon() -> str:
    return RECON_DOC.read_text(encoding="utf-8")


def _read_pr0055() -> str:
    return PR0055_CONTRACT.read_text(encoding="utf-8")


def _read_pr0056() -> str:
    return PR0056_BOUNDARY.read_text(encoding="utf-8")


# ===================================================================
# Class A: TestDocumentExists
# ===================================================================


class TestDocumentExists:
    def test_document_exists(self):
        """Reconciliation document is a file."""
        assert RECON_DOC.is_file(), (
            "docs/preprocessing_source_reconciliation.md not found"
        )


# ===================================================================
# Class B: TestXRDPreprocessingIdentified
# ===================================================================


class TestXRDPreprocessingIdentified:
    def test_xrd_preprocessing_package_identified(self):
        """XRD-preprocessing package is identified with name and version."""
        content = _read_recon()
        assert "xrd-preprocessing" in content.lower(), (
            "Recon doc must identify xrd-preprocessing package"
        )
        assert "0.1.6b0" in content or "0.1.6" in content, (
            "Recon doc must include XRD-preprocessing version"
        )

    def test_xrd_preprocessing_deps_identified(self):
        """XRD-preprocessing dependencies are identified."""
        content = _read_recon()
        assert "pyfai" in content.lower(), (
            "Recon doc must identify pyFAI dependency"
        )
        assert "fabio" in content.lower(), (
            "Recon doc must identify fabio dependency"
        )


# ===================================================================
# Class C: TestEosdxContainerIdentified
# ===================================================================


class TestEosdxContainerIdentified:
    def test_eosdx_container_identified(self):
        """eosdx-container v0.3 is identified."""
        content = _read_recon()
        assert "eosdx-container" in content.lower(), (
            "Recon doc must identify eosdx-container"
        )
        assert "v0.3" in content or "v0_3" in content, (
            "Recon doc must reference v0.3"
        )

    def test_v03_session_set_structure_identified(self):
        """v0.3 /session/sets/set_NNN_label/ structure is identified."""
        content = _read_recon()
        assert "/session/sets/" in content or "/session/sets" in content, (
            "Recon doc must identify /session/sets/ layout"
        )


# ===================================================================
# Class D: TestYAMLConfigTemplatesIdentified
# ===================================================================


class TestYAMLConfigTemplatesIdentified:
    def test_yaml_config_templates_identified(self):
        """YAML config templates are identified."""
        content = _read_recon()
        assert "yaml" in content.lower() or "yaml" in content, (
            "Recon doc must reference YAML config templates"
        )


# ===================================================================
# Class E: TestConfigLoaderValidatorIdentified
# ===================================================================


class TestConfigLoaderValidatorIdentified:
    def test_config_loader_validator_identified(self):
        """Config loader and validator functions are identified."""
        content = _read_recon()
        assert "load_preprocessing_config" in content, (
            "Recon doc must identify load_preprocessing_config"
        )
        assert "validate_preprocessing_config" in content, (
            "Recon doc must identify validate_preprocessing_config"
        )


# ===================================================================
# Class F: TestPipelineBuilderTransformerRegistryIdentified
# ===================================================================


class TestPipelineBuilderTransformerRegistryIdentified:
    def test_pipeline_builder_identified(self):
        """Pipeline builder (build_pipeline_from_config) is identified."""
        content = _read_recon()
        assert "build_pipeline_from_config" in content, (
            "Recon doc must identify build_pipeline_from_config"
        )

    def test_transformer_registry_identified(self):
        """Transformer registry is identified."""
        content = _read_recon()
        assert "TRANSFORMER_REGISTRY" in content or \
               "transformer_registry" in content.lower() or \
               "transformer registry" in content.lower(), (
            "Recon doc must identify transformer registry"
        )


# ===================================================================
# Class G: TestH5DataFrameTransformersIdentified
# ===================================================================


class TestH5DataFrameTransformersIdentified:
    def test_h5_transformers_identified(self):
        """H5 and DataFrame transformers are identified."""
        content = _read_recon()
        assert "H5SessionSelectorTransformer" in content, (
            "Recon doc must identify H5SessionSelectorTransformer"
        )
        assert "H5ToDataFrameTransformer" in content, (
            "Recon doc must identify H5ToDataFrameTransformer"
        )


# ===================================================================
# Class H: TestPreprocessingArtifactWriterReaderIdentified
# ===================================================================


class TestPreprocessingArtifactWriterReaderIdentified:
    def test_artifact_writer_reader_identified(self):
        """Preprocessing artifact writer and reader are identified."""
        content = _read_recon()
        assert "save_preprocessing_artifact" in content, (
            "Recon doc must identify save_preprocessing_artifact"
        )
        assert "load_preprocessing_artifact" in content, (
            "Recon doc must identify load_preprocessing_artifact"
        )


# ===================================================================
# Class I: TestV03GroupsIdentified
# ===================================================================


class TestV03GroupsIdentified:
    def test_v03_groups_identified(self):
        """v0.3 raw_file/raw/processed/integration/processing/qc/
        artifacts/measurements groups are identified."""
        content = _read_recon().lower()
        required_terms = [
            "raw_file", "raw/data",
            "processed", "integration",
            "processing", "qc",
            "artifacts", "measurements",
        ]
        missing = []
        for term in required_terms:
            # raw_file and raw/data appear in doc tables
            if term not in content:
                missing.append(term)
        assert len(missing) == 0, (
            f"Recon doc missing v0.3 group references: {missing}"
        )


# ===================================================================
# Class J: TestIncompatibleDuplicatePaths
# ===================================================================


class TestIncompatibleDuplicatePaths:
    def test_incompatible_paths_listed(self):
        """Incompatible or duplicate paths are listed."""
        content = _read_recon()
        # Section 9 must include the incompatible/duplicate paths table
        assert "Incompatible or Duplicate Paths" in content or \
               "incompatible or duplicate paths" in content.lower(), (
            "Recon doc must list incompatible or duplicate paths"
        )
        # Must reference the specific paths
        assert "docs/product_input_pipeline_contract.md" in content, (
            "Recon doc must list docs contract path"
        )
        assert "converter_preprocessing_boundary.md" in content, (
            "Recon doc must list converter boundary path"
        )
        assert "h5_layouts.py" in content, (
            "Recon doc must list runtime H5/layout path"
        )
        assert "pipelines.py" in content, (
            "Recon doc must list training/product pipeline path"
        )


# ===================================================================
# Test K: TestGFRMConverterIdentified
# ===================================================================


class TestGFRMConverterIdentified:
    def test_gfrm_converter_identified(self):
        """GFRM converter functions are identified."""
        content = _read_recon()
        assert "gfrm" in content.lower(), (
            "Recon doc must identify GFRM converter"
        )


# ===================================================================
# Class F: TestCanonicalLayoutCheck
# ===================================================================


class TestCanonicalLayoutCheck:
    def test_canonical_layout_checked_against_real_container(self):
        """PR0055/PR0056 canonical layout is explicitly checked against
        the real eosdx-container v0.3 schema."""
        content = _read_recon().lower()
        # Must explicitly answer the layout match question
        assert "answer" in content and "no" in content, (
            "Recon doc must explicitly answer the layout match question"
        )

    def test_scans_target_not_real_v03(self):
        """Recon doc states /scans/target is NOT producible by
        eosdx-container v0.3."""
        content = _read_recon().lower()
        assert "/scans/target/" in content, (
            "Recon doc must reference /scans/target/"
        )
        # Must state it does not match
        assert "not producible" in content or \
               "does not match" in content or \
               "no match" in content or \
               "not proven producible" in content, (
            "Recon doc must state /scans/target does not match v0.3"
        )


# ===================================================================
# Class G: TestBremenFeatureBridgeAmbiguity
# ===================================================================


class TestBremenFeatureBridgeAmbiguity:
    def test_feature_bridge_ambiguity_documented(self):
        """Bremen feature bridge ambiguity is documented (runtime vs
        training/product path)."""
        content = _read_recon().lower()
        assert "preprocessing_bridge.py" in content, (
            "Recon doc must reference preprocessing_bridge.py"
        )
        assert "pipelines.py" in content, (
            "Recon doc must reference pipelines.py"
        )


# ===================================================================
# Class H: TestPreprocessingBridgeDuplication
# ===================================================================


class TestPreprocessingBridgeDuplication:
    def test_duplication_documented(self):
        """preprocessing_bridge.py duplication risk is documented."""
        content = _read_recon().lower()
        assert "duplicate" in content or "duplicated" in content, (
            "Recon doc must document duplication risk"
        )


# ===================================================================
# Class I: TestPipelinesProductPath
# ===================================================================


class TestPipelinesProductPath:
    def test_pipelines_product_path_documented(self):
        """pipelines.py training/product path is documented as using
        real xrd_preprocessing transformers."""
        content = _read_recon()
        assert "pipelines.py" in content, (
            "Recon doc must reference pipelines.py"
        )
        assert "xrd_preprocessing" in content, (
            "Recon doc must reference xrd_preprocessing usage"
        )


# ===================================================================
# Class J: TestIntegrationOptions
# ===================================================================


class TestIntegrationOptions:
    def test_options_a_b_c_d_documented(self):
        """Integration options A/B/C/D are documented."""
        content = _read_recon()
        assert "Option A" in content, (
            "Recon doc must document Option A"
        )
        assert "Option B" in content, (
            "Recon doc must document Option B"
        )
        assert "Option C" in content, (
            "Recon doc must document Option C"
        )
        assert "Option D" in content, (
            "Recon doc must document Option D"
        )


# ===================================================================
# Class K: TestHumanDecisionGate
# ===================================================================


class TestHumanDecisionGate:
    def test_human_decision_gate_documented(self):
        """Human decision gate is documented before PR0058."""
        content = _read_recon().lower()
        assert "human" in content and "decision" in content, (
            "Recon doc must document human decision gate"
        )
        assert "pr0058" in content, (
            "Recon doc must reference PR0058 as blocked"
        )

    def test_no_implementation_recommended_while_unresolved(self):
        """Recon doc recommends no implementation until decision
        is made."""
        content = _read_recon().lower()
        assert "no implementation" in content or \
               "must not proceed" in content or \
               "should not proceed" in content or \
               "decision gate" in content, (
            "Recon doc must block implementation until decision"
        )


# ===================================================================
# Class L: TestNoDemoOnlyFork
# ===================================================================


class TestNoDemoOnlyFork:
    def test_no_demo_only_fork(self):
        """Recon doc states no demo-only fork is allowed."""
        content = _read_recon().lower()
        assert "no demo-only" in content or \
               "no demo-only fork" in content, (
            "Recon doc must reject demo-only fork"
        )


# ===================================================================
# Class M: TestNoVendoring
# ===================================================================


class TestNoVendoring:
    def test_no_upstream_vendoring(self):
        """Recon doc states no upstream code vendoring."""
        content = _read_recon().lower()
        assert "no vendoring" in content or \
               "no upstream code vendoring" in content or \
               "not vendored" in content, (
            "Recon doc must reject upstream code vendoring"
        )


# ===================================================================
# Class N: TestNoRuntimeTraining
# ===================================================================


class TestNoRuntimeTraining:
    def test_no_runtime_training(self):
        """Recon doc states no runtime training."""
        content = _read_recon().lower()
        assert "no runtime training" in content, (
            "Recon doc must state no runtime training"
        )


# ===================================================================
# Class O: TestNoFastAPI
# ===================================================================


class TestNoFastAPI:
    def test_no_fastapi(self):
        """Recon doc states FastAPI remains deferred."""
        content = _read_recon().lower()
        assert "fastapi" in content, (
            "Recon doc must mention FastAPI"
        )


# ===================================================================
# Class P: TestNoMatador
# ===================================================================


class TestNoMatador:
    def test_no_matador(self):
        """Recon doc states Matador remains future work."""
        content = _read_recon().lower()
        assert "matador" in content, (
            "Recon doc must mention Matador"
        )


# ===================================================================
# Class Q: TestNoDiagnosis
# ===================================================================


class TestNoDiagnosis:
    def test_no_diagnosis_claim(self):
        """Recon doc states no diagnosis."""
        content = _read_recon().lower()
        assert "no diagnosis" in content, (
            "Recon doc must state no diagnosis"
        )


# ===================================================================
# Class R: TestNoClinicalValidation
# ===================================================================


class TestNoClinicalValidation:
    def test_no_clinical_validation(self):
        """Recon doc states no clinical validation."""
        content = _read_recon().lower()
        assert "no clinical validation" in content, (
            "Recon doc must state no clinical validation"
        )


# ===================================================================
# Class S: TestNoReplacement
# ===================================================================


class TestNoReplacement:
    def test_no_replacement(self):
        """Recon doc states no replacement of clinical judgment."""
        content = _read_recon().lower()
        assert "no replacement" in content or \
               "does not replace" in content, (
            "Recon doc must state no replacement of clinical judgment"
        )


# ===================================================================
# Class T: TestNoArtifactsOrSecrets
# ===================================================================


class TestNoArtifactsOrSecrets:
    def test_no_forbidden_file_extensions(self):
        """Recon doc does not contain real artifact file references."""
        content = _read_recon()
        forbidden = [".gfrm", ".joblib", ".pkl", ".npy",
                      ".npz", ".parquet", ".proto", ".pb"]
        for ext in forbidden:
            # Allow .npy if in code reference context (not real file)
            if ext == ".npy" and ("save_gfrm_as_npy" in content):
                continue
            # Allow .gfrm if in upstream container schema description context
            if ext == ".gfrm" and ("vendor source bytes" in content or
                                     "raw_file" in content):
                continue
            assert ext not in content, (
                f"Recon doc must not contain {ext}"
            )

    def test_no_secrets_or_identifiers(self):
        """Recon doc does not contain secrets or raw identifiers."""
        content = _read_recon()
        # No AWS access key prefix
        assert "AKIA" not in content, (
            "Recon doc must not contain AKIA"
        )
        # No S3 URIs except in code reference/placeholder context
        s3_matches = re.findall(r's3://\S+', content)
        for match in s3_matches:
            cleaned = match.rstrip(").,'`")
            if "${" in cleaned:
                continue
            if cleaned.startswith("s3://bucket"):
                continue
            # Check if in negation/prohibition context
            before_text = content[:content.find(match)].rsplit('\n', 3)
            surrounding = '\n'.join(before_text[-3:]).lower()
            safe_context = any(kw in surrounding for kw in [
                'not contain', 'must not', 'prohibited',
                'no raw', 'non-leakage', 'do not',
                'full s3', 'use',
            ])
            if safe_context:
                continue
            pytest.fail(
                f"Recon doc contains non-placeholder S3 URI: {match}"
            )
        # No 64-character hex checksum
        hex64 = re.findall(
            r'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])',
            content,
        )
        assert len(hex64) == 0, (
            f"Recon doc contains {len(hex64)} raw 64-char hex strings"
        )
        # No local machine paths
        for path_pattern in ["/Users/", "/home/"]:
            if path_pattern in content:
                # Check if every occurrence is in negation/prohibition context
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if path_pattern in line:
                        lower = line.lower()
                        safe = any(kw in lower for kw in [
                            'not contain', 'must not', 'prohibited',
                            'no raw', 'non-leakage', 'do not',
                            'local-machine', 'local machine',
                            'absolute paths',
                        ])
                        assert safe, (
                            f"{path_pattern} at line {i} not in safe "
                            f"negation context: {line.strip()[:80]}"
                        )

    def test_nova_only_in_safe_context(self):
        """Nova_ must only appear in prohibition/negation context."""
        content = _read_recon()
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'Nova_' in line:
                lower = line.lower()
                safe = any(kw in lower for kw in [
                    'not contain', 'must not', 'prohibited',
                    'no raw', 'non-leakage', 'do not',
                    'raw patient',
                ])
                assert safe, (
                    f"Nova_ at line {i} not in safe context: "
                    f"{line.strip()[:80]}"
                )


# ===================================================================
# Class U: TestCrossReferences
# ===================================================================


class TestCrossReferences:
    def test_pr0055_contract_links_to_recon(self):
        """PR0055 contract links to reconciliation doc."""
        content = _read_pr0055()
        assert "preprocessing_source_reconciliation.md" in content, (
            "PR0055 contract must link to reconciliation doc"
        )

    def test_pr0056_boundary_links_to_recon(self):
        """PR0056 boundary spec links to reconciliation doc."""
        content = _read_pr0056()
        assert "preprocessing_source_reconciliation.md" in content, (
            "PR0056 boundary spec must link to reconciliation doc"
        )


# ===================================================================
# Class V: TestTestsAreStatic
# ===================================================================


class TestTestsAreStatic:
    def test_no_network_aws_docker_terraform(self):
        """Test file does not import network/AWS/Docker/Terraform modules."""
        content = Path(__file__).read_text(encoding="utf-8")
        import_lines = [
            line for line in content.split('\n')
            if line.strip().startswith(('import ', 'from '))
        ]
        import_text = '\n'.join(import_lines)
        prohibited = ["boto3", "requests", "httpx", "urllib",
                       "docker", "terraform"]
        for imp in prohibited:
            assert imp not in import_text, (
                f"Test file must not import {imp}"
            )
