"""Static tests for the converter preprocessing boundary specification (PR 0056).

All tests are static/text-only.  No network, AWS, Docker, Terraform,
App Runner, real H5, real model artifact, or credentials.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC_DOC = ROOT / "docs" / "converter_preprocessing_boundary.md"
PR0055_CONTRACT = ROOT / "docs" / "product_input_pipeline_contract.md"


def _read_spec() -> str:
    return SPEC_DOC.read_text(encoding="utf-8")


def _read_pr0055_contract() -> str:
    return PR0055_CONTRACT.read_text(encoding="utf-8")


# ===================================================================
# Class A: TestDocumentExists
# ===================================================================


class TestDocumentExists:
    def test_document_exists(self):
        """Converter boundary spec document is a file."""
        assert SPEC_DOC.is_file(), (
            "docs/converter_preprocessing_boundary.md not found"
        )


# ===================================================================
# Class B: TestBoundaryDefinition
# ===================================================================


class TestBoundaryDefinition:
    def test_defines_converter_boundary(self):
        """Boundary spec defines converter / Preprosync / preprocessing
        boundary with purpose and scope."""
        content = _read_spec()
        # Converter boundary defined
        assert "converter" in content.lower(), (
            "Spec must mention converter"
        )
        # Purpose section exists
        assert "Purpose" in content, (
            "Spec must have Purpose section"
        )
        # Scope section exists
        assert "Scope" in content, (
            "Spec must have Scope section"
        )

    def test_specification_only_not_implementation(self):
        """Boundary spec states it is specification/contract only,
        not implementation."""
        content = _read_spec().lower()
        assert "not an implementation" in content or \
               "not implemented" in content or \
               "specification" in content, (
            "Spec must state it is not an implementation"
        )


# ===================================================================
# Class C: TestCandidateInputForms
# ===================================================================


class TestCandidateInputForms:
    def test_geoframe_as_candidate(self):
        """GeoFrame described as candidate input form."""
        content = _read_spec().lower()
        assert "geoframe" in content, (
            "Spec must mention GeoFrame"
        )
        assert "candidate" in content or "requires" in content, (
            "Spec must describe GeoFrame as candidate/requires verification"
        )

    def test_protobuf_as_candidate(self):
        """Protobuf described as candidate input form."""
        content = _read_spec().lower()
        assert "protobuf" in content, (
            "Spec must mention protobuf"
        )
        assert "candidate" in content or "requires" in content, (
            "Spec must describe protobuf as candidate/requires verification"
        )

    def test_preprosync_as_candidate(self):
        """Preprosync described as candidate input form."""
        content = _read_spec().lower()
        assert "preprosync" in content, (
            "Spec must mention Preprosync"
        )
        assert "candidate" in content or "requires" in content, (
            "Spec must describe Preprosync as candidate/requires verification"
        )


# ===================================================================
# Class D: TestOutputContract
# ===================================================================


class TestOutputContract:
    def test_output_requires_canonical_bremen_input_package(self):
        """Output contract requires canonical Bremen input package."""
        content = _read_spec().lower()
        assert "canonical bremen input package" in content or \
               "canonical h5" in content, (
            "Spec must require canonical Bremen input package"
        )

    def test_output_requires_h5_compatibility(self):
        """Output contract requires H5/preflight/layout compatibility."""
        content = _read_spec().lower()
        assert "h5" in content or "hdf5" in content, (
            "Spec must require H5/HDF5 format"
        )
        assert "preflight" in content, (
            "Spec must mention preflight compatibility"
        )
        assert "layout" in content, (
            "Spec must mention layout compatibility"
        )

    def test_output_requires_explicit_refs(self):
        """Output contract requires explicit target/control refs."""
        content = _read_spec()
        assert "target_scan_ref" in content, (
            "Spec must require target_scan_ref"
        )
        assert "control_scan_ref" in content, (
            "Spec must require control_scan_ref"
        )

    def test_output_compatible_with_runtime_input_modes(self):
        """Output contract requires compatibility with h5_path/h5_uri
        runtime input modes."""
        content = _read_spec()
        assert "h5_path" in content, (
            "Spec must document h5_path compatibility"
        )
        assert "h5_uri" in content, (
            "Spec must document h5_uri compatibility"
        )


# ===================================================================
# Class E: TestExplicitRefsRequired
# ===================================================================


class TestExplicitRefsRequired:
    def test_target_and_control_refs_required(self):
        """Boundary spec states target_scan_ref and control_scan_ref
        are required at submit time."""
        content = _read_spec().lower()
        assert "required" in content, (
            "Spec must state refs are required"
        )
        assert "submit time" in content or \
               "passed alongside" in content or \
               "not embedded" in content, (
            "Spec must state refs are passed at submit time"
        )


# ===================================================================
# Class F: TestRuntimeModesPreserved
# ===================================================================


class TestRuntimeModesPreserved:
    def test_h5_path_preserved(self):
        """Boundary spec documents h5_path as preserved runtime mode."""
        content = _read_spec()
        assert "h5_path" in content, (
            "Spec must document h5_path"
        )

    def test_h5_uri_preserved(self):
        """Boundary spec documents h5_uri as preserved runtime mode."""
        content = _read_spec()
        assert "h5_uri" in content, (
            "Spec must document h5_uri"
        )


# ===================================================================
# Class G: TestRuntimeSchemaNotChanged
# ===================================================================


class TestRuntimeSchemaNotChanged:
    def test_runtime_request_schema_not_changed(self):
        """Boundary spec states runtime request schema is unchanged."""
        content = _read_spec().lower()
        assert "no runtime api change" in content or \
               "request schema" in content or \
               "unchanged" in content, (
            "Spec must state runtime request schema is not changed"
        )


# ===================================================================
# Class H: TestRuntimeNotConverter
# ===================================================================


class TestRuntimeNotConverter:
    def test_runtime_not_converter(self):
        """Boundary spec states runtime does NOT become the converter
        service."""
        content = _read_spec().lower()
        assert "does not become the converter" in content or \
               "separate component outside the runtime" in content or \
               "not part of the bremen runtime" in content, (
            "Spec must state runtime is not the converter"
        )


# ===================================================================
# Class I: TestRuntimeNotTrain
# ===================================================================


class TestRuntimeNotTrain:
    def test_runtime_does_not_train(self):
        """Boundary spec states runtime does NOT train."""
        content = _read_spec().lower()
        assert "does not train" in content or \
               "no runtime training" in content or \
               "runtime does not train" in content, (
            "Spec must state runtime does not train"
        )


# ===================================================================
# Class J: TestNoConverterImplementation
# ===================================================================


class TestNoConverterImplementation:
    def test_no_converter_implementation(self):
        """Boundary spec states PR0056 does not implement converter code."""
        content = _read_spec().lower()
        assert "pr0056" in content and "no" in content, (
            "Spec must state PR0056 does not implement converter"
        )
        assert "no converter implementation" in content or \
               "not an implementation" in content or \
               "no converter code" in content, (
            "Spec must explicitly state no converter implementation"
        )


# ===================================================================
# Class K: TestMatadorFutureWork
# ===================================================================


class TestMatadorFutureWork:
    def test_matador_is_future_work(self):
        """Boundary spec states Matador is future work."""
        content = _read_spec().lower()
        assert "matador" in content, (
            "Spec must mention Matador"
        )
        assert "future" in content or \
               "not implemented" in content or \
               "not yet implemented" in content, (
            "Spec must state Matador is future/not yet implemented"
        )


# ===================================================================
# Class L: TestFastAPIDeferred
# ===================================================================


class TestFastAPIDeferred:
    def test_fastapi_deferred(self):
        """Boundary spec states FastAPI is deferred."""
        content = _read_spec().lower()
        assert "fastapi" in content, (
            "Spec must mention FastAPI"
        )
        assert "deferred" in content or "no fastapi" in content, (
            "Spec must state FastAPI is deferred"
        )


# ===================================================================
# Class M: TestNoDemoOnlyFork
# ===================================================================


class TestNoDemoOnlyFork:
    def test_no_demo_only_code_path(self):
        """Boundary spec states no demo-only converter code path."""
        content = _read_spec().lower()
        assert "no separate demo-only" in content or \
               "no demo-only" in content or \
               "same converter boundary" in content or \
               "same converter contract" in content, (
            "Spec must state no demo-only code path"
        )


# ===================================================================
# Class N: TestDecisionSupportOutputPath
# ===================================================================


class TestDecisionSupportOutputPath:
    def test_decision_support_report_is_output(self):
        """Boundary spec documents decision_support_report as the
        final output path."""
        content = _read_spec().lower()
        assert "decision_support_report" in content or \
               "decision-support report" in content, (
            "Spec must document decision_support_report output"
        )


# ===================================================================
# Class O: TestNonLeakageRules
# ===================================================================


class TestNonLeakageRules:
    def test_non_leakage_rules_present(self):
        """Boundary spec includes non-leakage rules."""
        content = _read_spec().lower()
        assert "non-leakage" in content or \
               "must not contain" in content or \
               "not contain" in content, (
            "Spec must include non-leakage rules"
        )

    def test_prohibits_raw_patient_identifiers(self):
        """Non-leakage rules prohibit raw patient identifiers."""
        content = _read_spec().lower()
        assert "patient identifier" in content or \
               "patient id" in content, (
            "Spec must prohibit raw patient identifiers"
        )

    def test_prohibits_full_s3_uris(self):
        """Non-leakage rules prohibit full S3 URIs."""
        content = _read_spec().lower()
        assert "s3://" in content or "s3 uri" in content, (
            "Spec must reference S3 URI prohibition"
        )

    def test_prohibits_secrets(self):
        """Non-leakage rules prohibit secrets/credentials."""
        content = _read_spec().lower()
        assert "credential" in content or \
               "access key" in content or \
               "account id" in content or \
               "secret" in content, (
            "Spec must prohibit secrets/credentials"
        )


# ===================================================================
# Class P: TestNoDiagnosis
# ===================================================================


class TestNoDiagnosis:
    def test_no_diagnosis_claim(self):
        """Boundary spec states no diagnosis."""
        content = _read_spec().lower()
        assert "no diagnosis" in content or \
               "not a diagnosis" in content or \
               "not diagnose" in content, (
            "Spec must state no diagnosis"
        )


# ===================================================================
# Class Q: TestNoClinicalValidation
# ===================================================================


class TestNoClinicalValidation:
    def test_no_clinical_validation_claim(self):
        """Boundary spec states no clinical validation."""
        content = _read_spec().lower()
        assert "no clinical validation" in content or \
               "not clinically validated" in content, (
            "Spec must state no clinical validation"
        )


# ===================================================================
# Class R: TestNoReplacement
# ===================================================================


class TestNoReplacement:
    def test_no_replacement_of_clinical_judgment(self):
        """Boundary spec states no replacement of MRI, biopsy,
        radiologist, clinician, or clinical judgment."""
        content = _read_spec().lower()
        assert "does not replace" in content or \
               "no replacement" in content, (
            "Spec must state no replacement of clinical judgment"
        )


# ===================================================================
# Class S: TestNoRealArtifacts
# ===================================================================


class TestNoRealArtifacts:
    def test_no_real_artifact_references(self):
        """Boundary spec does not contain real artifact file references."""
        content = _read_spec()
        forbidden_ext = [
            ".hdf5", ".joblib", ".pkl", ".npy",
            ".npz", ".parquet", ".pb",
        ]
        for ext in forbidden_ext:
            assert ext not in content, (
                f"Spec must not contain {ext} reference"
            )


# ===================================================================
# Class T: TestNoSecretsOrIdentifiers
# ===================================================================


class TestNoSecretsOrIdentifiers:
    def test_no_full_s3_uri_with_real_bucket_key(self):
        """Spec does NOT contain a real s3://bucket/key string."""
        content = _read_spec()
        s3_matches = re.findall(r's3://\S+', content)
        for match in s3_matches:
            cleaned = match.rstrip(").,'`")
            if "${" in cleaned:
                continue
            if cleaned.startswith("s3://bucket"):
                continue
            pytest.fail(
                f"Spec contains non-placeholder S3 URI: {match}"
            )

    def test_no_raw_checksum_in_document(self):
        """Spec does NOT contain a 64-character hex string."""
        content = _read_spec()
        hex64 = re.findall(
            r'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])',
            content,
        )
        assert len(hex64) == 0, (
            f"Spec contains {len(hex64)} raw 64-char hex strings"
        )

    def test_no_access_keys_in_document(self):
        """Spec does NOT contain AKIA in unsafe contexts.

        AKIA may appear in negation/prohibition context
        (e.g., output contract listing what must NOT be present).
        """
        content = _read_spec()
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'AKIA' in line:
                lower = line.lower()
                safe = any(kw in lower for kw in [
                    'not contain', 'must not', 'prohibited',
                    'no raw', 'non-leakage', 'do not',
                    'free of',
                ])
                assert safe, (
                    f"AKIA at line {i} not in safe negation context: "
                    f"{line.strip()[:80]}"
                )

    def test_no_registry_url_in_document(self):
        """Spec does NOT contain dkr.ecr pattern."""
        content = _read_spec()
        assert "dkr.ecr" not in content, (
            "Spec must not contain dkr.ecr pattern"
        )

    def test_no_raw_patient_identifiers_in_document(self):
        """Spec does NOT contain Nova_ patterns in non-negation context."""
        content = _read_spec()
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
                    f"Nova_ at line {i} not in safe negation context: "
                    f"{line.strip()[:80]}"
                )

    def test_no_local_machine_paths_in_document(self):
        """Spec does NOT contain /Users/ or /home/ in non-negation context."""
        content = _read_spec()
        lines = content.split('\n')
        for path_pattern in ["/Users/", "/home/"]:
            for i, line in enumerate(lines):
                if path_pattern in line:
                    lower = line.lower()
                    safe = any(kw in lower for kw in [
                        'not contain', 'must not', 'prohibited',
                        'no raw', 'non-leakage', 'do not',
                        'local-machine', 'local machine',
                        'local absolute paths',
                    ])
                    assert safe, (
                        f"{path_pattern} at line {i} not in safe "
                        f"negation context: {line.strip()[:80]}"
                    )

    def test_no_account_ids_in_document(self):
        """Spec does NOT contain AWS account ID patterns."""
        content = _read_spec()
        twelve_digits = re.findall(r'\b\d{12}\b', content)
        assert len(twelve_digits) == 0, (
            f"Spec contains {len(twelve_digits)} 12-digit numbers"
        )

    def test_no_secret_access_key_in_document(self):
        """Spec does NOT contain SECRET_ACCESS_KEY in unsafe contexts.

        SECRET_ACCESS_KEY may appear in negation/prohibition context
        (e.g., output contract listing what must NOT be present).
        """
        content = _read_spec()
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'SECRET_ACCESS_KEY' in line:
                lower = line.lower()
                safe = any(kw in lower for kw in [
                    'not contain', 'must not', 'prohibited',
                    'no raw', 'non-leakage', 'do not',
                    'free of',
                ])
                assert safe, (
                    f"SECRET_ACCESS_KEY at line {i} not in safe "
                    f"negation context: {line.strip()[:80]}"
                )


# ===================================================================
# Class U: TestCrossReferences
# ===================================================================


class TestCrossReferences:
    def test_boundary_spec_references_pr0055_contract(self):
        """Boundary spec cross-references the PR0055 product input
        pipeline contract."""
        content = _read_spec()
        assert "product_input_pipeline_contract.md" in content or \
               "PR0055" in content, (
            "Spec must reference PR0055 contract"
        )

    def test_pr0055_contract_links_to_boundary_spec(self):
        """PR0055 contract links to the converter boundary spec."""
        content = _read_pr0055_contract()
        assert "converter_preprocessing_boundary.md" in content, (
            "PR0055 contract must link to converter_preprocessing_boundary.md"
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
        prohibited_imports = [
            "boto3", "requests", "httpx", "urllib",
            "docker", "terraform",
        ]
        for imp in prohibited_imports:
            assert imp not in import_text, (
                f"Test file must not import {imp}"
            )
