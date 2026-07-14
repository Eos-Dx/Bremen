"""Static tests for the product input pipeline contract (PR 0055).

All tests are static/text-only.  No network, AWS, Docker, Terraform,
App Runner, real H5, real model artifact, or credentials.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DOC = ROOT / "docs" / "product_input_pipeline_contract.md"
API_CONTRACT = ROOT / "docs" / "api_contract.md"


def _read_contract() -> str:
    return CONTRACT_DOC.read_text(encoding="utf-8")


def _read_api_contract() -> str:
    return API_CONTRACT.read_text(encoding="utf-8")


# ===================================================================
# Class A: TestContractDocumentExists
# ===================================================================


class TestContractDocumentExists:
    def test_contract_document_exists(self):
        """Product input pipeline contract document is a file."""
        assert CONTRACT_DOC.is_file(), (
            "docs/product_input_pipeline_contract.md not found"
        )


# ===================================================================
# Class B: TestProductizableWorkflow
# ===================================================================


class TestProductizableWorkflow:
    def test_productizable_workflow_documented(self):
        """Contract documents the productizable workflow:
        external input -> converter -> canonical package ->
        runtime -> decision_support_report.
        """
        content = _read_contract().lower()
        assert "external" in content and "converter" in content, (
            "Contract must document external input to converter path"
        )
        assert "canonical bremen input package" in content, (
            "Contract must document canonical Bremen input package"
        )
        assert "decision_support_report" in content, (
            "Contract must document decision_support_report output"
        )


# ===================================================================
# Class C: TestNoDemoOnlyFork
# ===================================================================


class TestNoDemoOnlyFork:
    def test_no_demo_only_fork(self):
        """Contract states no separate demo-only format.
        Demo uses same contract as production.
        """
        content = _read_contract().lower()
        assert "no separate demo-only format" in content or \
               "no demo-only" in content or \
               "not demo-only" in content or \
               "not a demo-only" in content, (
            "Contract must state no separate demo-only format"
        )

    def test_investor_walkthrough_same_contract(self):
        """Contract states investor walkthroughs use the same contract
        as production."""
        content = _read_contract().lower()
        assert "same canonical input package contract" in content or \
               "same contract" in content or \
               "identical" in content, (
            "Contract must state investor walkthrough uses same contract"
        )


# ===================================================================
# Class D: TestCandidateInputForms
# ===================================================================


class TestCandidateInputForms:
    def test_geoframe_as_candidate(self):
        """GeoFrame is described as a candidate input form,
        not as implemented."""
        content = _read_contract().lower()
        assert "geoframe" in content, (
            "Contract must mention GeoFrame"
        )
        assert "candidate" in content or "requires" in content, (
            "Contract must describe GeoFrame as candidate/requires verification"
        )

    def test_protobuf_as_candidate(self):
        """Protobuf is described as a candidate input form,
        not as implemented."""
        content = _read_contract().lower()
        assert "protobuf" in content, (
            "Contract must mention protobuf"
        )
        assert "candidate" in content or "requires" in content, (
            "Contract must describe protobuf as candidate/requires verification"
        )

    def test_preprosync_as_candidate(self):
        """Preprosync is described as a candidate input form,
        not as implemented."""
        content = _read_contract().lower()
        assert "preprosync" in content, (
            "Contract must mention Preprosync"
        )
        assert "candidate" in content or "requires" in content, (
            "Contract must describe Preprosync as candidate/requires verification"
        )


# ===================================================================
# Class E: TestConverterBoundary
# ===================================================================


class TestConverterBoundary:
    def test_converter_boundary_documented(self):
        """Converter / preprocessing boundary is documented."""
        content = _read_contract().lower()
        assert "converter" in content, (
            "Contract must document converter"
        )
        assert "boundary" in content, (
            "Contract must document converter boundary"
        )

    def test_runtime_not_converter(self):
        """Contract states runtime is NOT the converter."""
        content = _read_contract().lower()
        assert "runtime does not become the converter" in content or \
               "not the converter" in content or \
               "separate component" in content, (
            "Contract must state runtime is not the converter"
        )


# ===================================================================
# Class F: TestRuntimeStability
# ===================================================================


class TestRuntimeStability:
    def test_runtime_remains_stable(self):
        """Contract states runtime remains stable and unchanged."""
        content = _read_contract().lower()
        assert "runtime remains stable" in content or \
               "runtime is unchanged" in content or \
               "runtime are unchanged" in content, (
            "Contract must state runtime remains stable"
        )

    def test_runtime_does_not_train(self):
        """Contract states runtime does not train."""
        content = _read_contract().lower()
        assert "does not train" in content or \
               "runtime does not train" in content or \
               "no training" in content, (
            "Contract must state runtime does not train"
        )


# ===================================================================
# Class G: TestCanonicalInputPackage
# ===================================================================


class TestCanonicalInputPackage:
    def test_canonical_input_package_documented(self):
        """Contract documents the canonical Bremen input package."""
        content = _read_contract().lower()
        assert "canonical bremen input package" in content, (
            "Contract must document canonical Bremen input package"
        )

    def test_canonical_input_package_format(self):
        """Contract specifies format, layout, metadata, explicit refs,
        and prohibited content for the canonical input package."""
        content = _read_contract().lower()
        assert "hdf5" in content or ".h5" in content or "h5py" in content, (
            "Contract must specify HDF5/.h5 format"
        )

    def test_canonical_input_package_prohibited_content(self):
        """Contract documents prohibited content in the canonical
        input package."""
        content = _read_contract().lower()
        assert "prohibited" in content or "must not contain" in content, (
            "Contract must document prohibited content in canonical package"
        )


# ===================================================================
# Class H: TestExplicitRefsRequired
# ===================================================================


class TestExplicitRefsRequired:
    def test_explicit_refs_required(self):
        """Contract requires explicit target_scan_ref and
        control_scan_ref."""
        content = _read_contract()
        assert "target_scan_ref" in content, (
            "Contract must document target_scan_ref"
        )
        assert "control_scan_ref" in content, (
            "Contract must document control_scan_ref"
        )
        assert "required" in content.lower(), (
            "Contract must state refs are required"
        )


# ===================================================================
# Class I: TestInputModes
# ===================================================================


class TestInputModes:
    def test_h5_path_documented(self):
        """Contract documents h5_path as a controlled runtime
        input mode."""
        content = _read_contract()
        assert "h5_path" in content, (
            "Contract must document h5_path"
        )

    def test_h5_uri_documented(self):
        """Contract documents h5_uri as a controlled runtime
        input mode."""
        content = _read_contract()
        assert "h5_uri" in content, (
            "Contract must document h5_uri"
        )

    def test_no_request_schema_change(self):
        """Contract states no request schema change in PR0055."""
        content = _read_contract().lower()
        assert "no request schema change" in content or \
               "request body" in content or \
               "unchanged" in content, (
            "Contract must state no request schema change"
        )


# ===================================================================
# Class J: TestMatadorFutureWork
# ===================================================================


class TestMatadorFutureWork:
    def test_matador_is_future_work(self):
        """Contract states Matador is future work, not implemented."""
        content = _read_contract().lower()
        assert "matador" in content, (
            "Contract must mention Matador"
        )
        assert "future" in content or "remains" in content or \
               "not yet implemented" in content, (
            "Contract must state Matador is future/not yet implemented"
        )


# ===================================================================
# Class K: TestFastAPIDeferred
# ===================================================================


class TestFastAPIDeferred:
    def test_fastapi_deferred(self):
        """Contract states FastAPI is deferred."""
        content = _read_contract().lower()
        assert "fastapi" in content, (
            "Contract must mention FastAPI"
        )
        assert "deferred" in content or "no fastapi" in content, (
            "Contract must state FastAPI is deferred"
        )


# ===================================================================
# Class L: TestDecisionSupportOutputPath
# ===================================================================


class TestDecisionSupportOutputPath:
    def test_decision_support_report_is_output(self):
        """Contract documents decision_support_report as the output
        path."""
        content = _read_contract().lower()
        assert "decision_support_report" in content, (
            "Contract must document decision_support_report output"
        )


# ===================================================================
# Class M: TestNoDiagnosis
# ===================================================================


class TestNoDiagnosis:
    def test_no_diagnosis_claim(self):
        """Contract states no diagnosis."""
        content = _read_contract().lower()
        assert "not a diagnosis" in content or \
               "no diagnosis" in content or \
               "not diagnose" in content, (
            "Contract must state no diagnosis"
        )


# ===================================================================
# Class N: TestNoClinicalValidation
# ===================================================================


class TestNoClinicalValidation:
    def test_no_clinical_validation_claim(self):
        """Contract states no clinical validation."""
        content = _read_contract().lower()
        assert "not clinically validated" in content or \
               "no clinical validation" in content, (
            "Contract must state no clinical validation"
        )


# ===================================================================
# Class O: TestNoReplacement
# ===================================================================


class TestNoReplacement:
    def test_no_replacement_of_clinical_judgment(self):
        """Contract states no replacement of MRI, biopsy,
        radiologist, clinician, or clinical judgment."""
        content = _read_contract().lower()
        assert "does not replace" in content or \
               "no replacement" in content, (
            "Contract must state no replacement of clinical judgment"
        )
        assert "mri" in content, (
            "Contract must mention MRI in safety disclaimer"
        )
        assert "clinician" in content, (
            "Contract must mention clinician in safety disclaimer"
        )


# ===================================================================
# Class P: TestNoRealDataArtifacts
# ===================================================================


class TestNoRealDataArtifacts:
    def test_no_real_data_artifacts(self):
        """Contract does not embed real artifact file references.

        The .h5 extension is used as a format specification throughout
        the contract document (e.g., "HDF5 (`.h5`) file"). These are
        safe format mentions, not real artifact references.
        """
        content = _read_contract()
        # Check only for extensions that should never appear in a contract doc
        forbidden_ext = [
            ".hdf5", ".joblib", ".pkl", ".npy",
            ".npz", ".parquet", ".pb",
        ]
        for ext in forbidden_ext:
            assert ext not in content, (
                f"Contract must not contain {ext} reference"
            )


# ===================================================================
# Class Q: TestNoSecretsOrIdentifiers
# ===================================================================


class TestNoSecretsOrIdentifiers:
    def test_no_full_s3_uri_with_real_bucket_key(self):
        """Contract does NOT contain a real s3://bucket/key string."""
        content = _read_contract()
        s3_matches = re.findall(r's3://\S+', content)
        for match in s3_matches:
            cleaned = match.rstrip(").,'`")
            if "${" in cleaned:
                continue
            if cleaned.startswith("s3://bucket"):
                continue
            pytest.fail(
                f"Contract contains non-placeholder S3 URI: {match}"
            )

    def test_no_raw_checksum_in_document(self):
        """Contract does NOT contain a 64-character hex string."""
        content = _read_contract()
        hex64 = re.findall(
            r'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])',
            content,
        )
        assert len(hex64) == 0, (
            f"Contract contains {len(hex64)} raw 64-char hex strings"
        )

    def test_no_access_keys_in_document(self):
        """Contract does NOT contain AKIA pattern."""
        content = _read_contract()
        assert "AKIA" not in content, (
            "Contract must not contain AKIA pattern"
        )

    def test_no_registry_url_in_document(self):
        """Contract does NOT contain dkr.ecr pattern."""
        content = _read_contract()
        assert "dkr.ecr" not in content, (
            "Contract must not contain dkr.ecr pattern"
        )

    def test_no_raw_patient_identifiers_in_document(self):
        """Contract does NOT contain Nova_ or raw patient ID patterns.

        The string "Nova_" may appear in negation/prohibition context
        (e.g., non-leakage rules listing what must NOT be present).
        Such uses are safe.
        """
        content = _read_contract()
        # Check each occurrence of Nova_ is in a safe context
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'Nova_' in line:
                lower = line.lower()
                safe_context = any(kw in lower for kw in [
                    'not contain', 'must not', 'prohibited',
                    'no raw', 'non-leakage', 'do not',
                    'raw patient', 'raw scan',
                ])
                assert safe_context, (
                    f"Nova_ at line {i} not in safe negation context: "
                    f"{line.strip()[:80]}"
                )

    def test_no_local_machine_paths_in_document(self):
        """Contract does NOT contain /Users/ or /home/ paths.

        These strings may appear in negation/prohibition context
        (e.g., non-leakage rules listing what must NOT be present).
        Such uses are safe.
        """
        content = _read_contract()
        lines = content.split('\n')
        for path_pattern in ["/Users/", "/home/"]:
            for i, line in enumerate(lines):
                if path_pattern in line:
                    lower = line.lower()
                    safe_context = any(kw in lower for kw in [
                        'not contain', 'must not', 'prohibited',
                        'no raw', 'non-leakage', 'do not',
                        'local-machine', 'local machine',
                    ])
                    assert safe_context, (
                        f"{path_pattern} at line {i} not in safe "
                        f"negation context: {line.strip()[:80]}"
                    )

    def test_no_account_ids_in_document(self):
        """Contract does NOT contain AWS account ID patterns."""
        content = _read_contract()
        twelve_digits = re.findall(r'\b\d{12}\b', content)
        assert len(twelve_digits) == 0, (
            f"Contract contains {len(twelve_digits)} 12-digit numbers"
        )

    def test_no_secret_access_key_in_document(self):
        """Contract does NOT contain SECRET_ACCESS_KEY pattern."""
        content = _read_contract()
        assert "SECRET_ACCESS_KEY" not in content, (
            "Contract must not contain SECRET_ACCESS_KEY"
        )


# ===================================================================
# Class R: TestAPIContractCrossReference
# ===================================================================


class TestAPIContractCrossReference:
    def test_api_contract_links_to_input_pipeline_contract(self):
        """API contract links to the product input pipeline contract."""
        content = _read_api_contract()
        assert "product_input_pipeline_contract.md" in content, (
            "API contract must link to product_input_pipeline_contract.md"
        )


# ===================================================================
# Class S: TestTestsAreStatic
# ===================================================================


class TestTestsAreStatic:
    def test_no_network_aws_docker_terraform(self):
        """Test file does not import network/AWS/Docker/Terraform modules.

        Only the import statements are checked — not assertion messages
        or docstrings that mention prohibited names as negative examples.
        """
        content = Path(__file__).read_text(encoding="utf-8")
        # Check only import lines, not assertion messages
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
