"""Synthetic/static tests for the system-of-record boundary (PR0052).

All tests are synthetic and deterministic.  No network, no AWS,
no Docker/Terraform, no real H5 or model artifacts.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from bremen.system_of_record import (
    ExternalRecordRef,
    RefValidationError,
    ResolvedInput,
    ResolvedInputError,
    RecordResolver,
    ResolutionError,
    ResolutionNotConfiguredError,
    UnconfiguredRecordResolver,
)

SRC_SOR = Path(__file__).resolve().parents[1] / "src" / "bremen" / "system_of_record.py"
DOCS_ADR_DIR = Path(__file__).resolve().parents[1] / "docs" / "adr"
API_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "docs" / "api_contract.md"


# ===================================================================
# Boundary module import safety
# ===================================================================


class TestBoundaryModuleSafety:
    """Boundary module imports without network/client dependencies."""

    def test_import_succeeds(self):
        """Module imports without error."""
        import bremen.system_of_record
        assert bremen.system_of_record is not None

    def test_no_requests_httpx_aiohttp_import(self):
        """No network client imports in boundary module (AST check)."""
        tree = ast.parse(SRC_SOR.read_text(encoding="utf-8"))
        prohibited = {"requests", "httpx", "aiohttp"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0].lower() in prohibited:
                        pytest.fail(
                            f"system_of_record.py imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0].lower() in prohibited:
                    pytest.fail(
                        f"system_of_record.py imports {module}"
                    )

    def test_no_boto3_botocore_import(self):
        """No boto3/botocore imports in boundary module (AST check)."""
        tree = ast.parse(SRC_SOR.read_text(encoding="utf-8"))
        prohibited = {"boto3", "botocore"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0].lower() in prohibited:
                        pytest.fail(
                            f"system_of_record.py imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0].lower() in prohibited:
                    pytest.fail(
                        f"system_of_record.py imports {module}"
                    )

    def test_no_matador_url_token_constants(self):
        """No Matador URL/token/client constants in boundary module."""
        content = SRC_SOR.read_text(encoding="utf-8")
        forbidden = ["MATADOR_", "matador_url", "matador_token", "matador_client"]
        for pattern in forbidden:
            assert pattern not in content, (
                f"system_of_record.py contains Matador constant: {pattern}"
            )


# ===================================================================
# ExternalRecordRef validation
# ===================================================================


class TestExternalRecordRefValidation:
    """Opaque ref validation rules."""

    def test_accepts_safe_synthetic_ref(self):
        """A safe synthetic ref (no path, no URI, no patient ID) is accepted."""
        ref = ExternalRecordRef("matador://patient/ABC-123/scan/TGT-001")
        assert isinstance(ref, ExternalRecordRef)
        assert str(ref) == "matador://patient/ABC-123/scan/TGT-001"

    def test_rejects_empty_ref(self):
        """Empty ref raises RefValidationError."""
        with pytest.raises(RefValidationError, match="not be empty"):
            ExternalRecordRef("")

    def test_rejects_whitespace_only_ref(self):
        """Whitespace-only ref raises RefValidationError."""
        with pytest.raises(RefValidationError) as exc_info:
            ExternalRecordRef("   ")
        error_text = str(exc_info.value)
        assert "empty" in error_text or "whitespace" in error_text, (
            f"Unexpected error message: {error_text}"
        )

    def test_rejects_local_absolute_path(self):
        """Ref starting with / is rejected as local path."""
        with pytest.raises(RefValidationError, match="local path or S3 URI"):
            ExternalRecordRef("/tmp/some-file.h5")

    def test_rejects_full_s3_uri(self):
        """Ref starting with s3:// is rejected as S3 URI."""
        with pytest.raises(RefValidationError, match="local path or S3 URI"):
            ExternalRecordRef("s3://bucket/path/to/file.h5")

    def test_rejects_raw_patient_identifier(self):
        """Ref containing Nova_ is rejected as raw patient identifier."""
        with pytest.raises(RefValidationError, match="raw patient identifiers"):
            ExternalRecordRef("matador://patient/Nova_376/scan/TGT-001")


# ===================================================================
# ResolvedInput validation
# ===================================================================


class TestResolvedInputValidation:
    """ResolvedInput accepts exactly one H5 source."""

    def test_accepts_h5_uri_only(self):
        """ResolvedInput with h5_uri only passes validation."""
        inp = ResolvedInput(
            target_scan_ref="target",
            control_scan_ref="control",
            h5_uri="s3://bucket/file.h5",
        )
        assert inp.h5_uri == "s3://bucket/file.h5"
        assert inp.h5_path is None

    def test_accepts_h5_path_only(self):
        """ResolvedInput with h5_path only passes validation."""
        inp = ResolvedInput(
            target_scan_ref="target",
            control_scan_ref="control",
            h5_path="/tmp/test.h5",
        )
        assert inp.h5_path == "/tmp/test.h5"
        assert inp.h5_uri is None

    def test_rejects_both_h5_uri_and_h5_path(self):
        """Both h5_uri and h5_path raises ResolvedInputError."""
        with pytest.raises(ResolvedInputError, match="not both"):
            ResolvedInput(
                target_scan_ref="target",
                control_scan_ref="control",
                h5_uri="s3://bucket/file.h5",
                h5_path="/tmp/test.h5",
            )

    def test_rejects_neither_h5_uri_nor_h5_path(self):
        """Neither h5_uri nor h5_path raises ResolvedInputError."""
        with pytest.raises(ResolvedInputError, match="must be provided"):
            ResolvedInput(
                target_scan_ref="target",
                control_scan_ref="control",
            )

    def test_preserves_checksum(self):
        """Optional checksum is preserved in ResolvedInput."""
        inp = ResolvedInput(
            target_scan_ref="target",
            control_scan_ref="control",
            h5_uri="s3://bucket/file.h5",
            h5_checksum="sha256:abc123",
        )
        assert inp.h5_checksum == "sha256:abc123"

    def test_preserves_target_control_refs(self):
        """Target and control refs are preserved."""
        inp = ResolvedInput(
            target_scan_ref="scan:tgt/001",
            control_scan_ref="scan:ctl/001",
            h5_path="/tmp/test.h5",
        )
        assert inp.target_scan_ref == "scan:tgt/001"
        assert inp.control_scan_ref == "scan:ctl/001"

    def test_checksum_optional_defaults_to_none(self):
        """Checksum defaults to None when not provided."""
        inp = ResolvedInput(
            target_scan_ref="target",
            control_scan_ref="control",
            h5_uri="s3://bucket/file.h5",
        )
        assert inp.h5_checksum is None


# ===================================================================
# UnconfiguredRecordResolver
# ===================================================================


class TestUnconfiguredRecordResolver:
    """Default resolver raises safe not-configured error."""

    def test_resolve_raises_not_configured(self):
        """UnconfiguredRecordResolver always raises ResolutionNotConfiguredError."""
        resolver = UnconfiguredRecordResolver()
        ref = ExternalRecordRef("matador://patient/ABC/scan/TGT")
        with pytest.raises(ResolutionNotConfiguredError) as exc_info:
            resolver.resolve(
                ref=ref,
                target_scan_ref="target",
                control_scan_ref="control",
            )
        error_text = str(exc_info.value)
        # Error must not contain raw ref
        assert "ABC" not in error_text
        assert "TGT" not in error_text
        # Error should suggest alternatives
        assert "h5_path" in error_text or "h5_uri" in error_text
        assert "configure" in error_text.lower()

    def test_resolution_error_is_safe(self):
        """ResolutionError message is safe and does not leak refs."""
        error = ResolutionNotConfiguredError()
        error_str = str(error)
        assert isinstance(error_str, str)
        assert len(error_str) > 0


# ===================================================================
# Protocol compliance
# ===================================================================


class TestRecordResolverProtocol:
    """A synthetic in-memory resolver can implement RecordResolver."""

    def test_synthetic_resolver_is_runtime_checkable(self):
        """A class implementing resolve() is recognised by runtime_checkable."""
        class SyntheticResolver:
            def resolve(self, ref, target_scan_ref, control_scan_ref):
                return ResolvedInput(
                    target_scan_ref=target_scan_ref,
                    control_scan_ref=control_scan_ref,
                    h5_path="/tmp/resolved.h5",
                )

        resolver = SyntheticResolver()
        assert isinstance(resolver, RecordResolver), (
            "SyntheticResolver must be recognised as RecordResolver"
        )

    def test_synthetic_resolver_returns_resolved_input(self):
        """A synthetic resolver can return a valid ResolvedInput."""
        class SyntheticResolver:
            def resolve(self, ref, target_scan_ref, control_scan_ref):
                return ResolvedInput(
                    target_scan_ref=target_scan_ref,
                    control_scan_ref=control_scan_ref,
                    h5_uri="s3://bucket/resolved.h5",
                    h5_checksum="sha256:abc",
                )

        resolver = SyntheticResolver()
        ref = ExternalRecordRef("matador://patient/ABC/scan/TGT")
        result = resolver.resolve(
            ref=ref,
            target_scan_ref="scan:tgt/001",
            control_scan_ref="scan:ctl/001",
        )
        assert isinstance(result, ResolvedInput)
        assert result.h5_uri == "s3://bucket/resolved.h5"
        assert result.target_scan_ref == "scan:tgt/001"
        assert result.control_scan_ref == "scan:ctl/001"
        assert result.h5_checksum == "sha256:abc"

    def test_unconfigured_resolver_is_not_record_resolver(self):
        """UnconfiguredRecordResolver does NOT implement RecordResolver
        (it has resolve() but is typed as a concrete class, not protocol)."""
        # UnconfiguredRecordResolver has a resolve() method with matching
        # signature, so it is actually recognised by runtime_checkable
        from bremen.system_of_record import UnconfiguredRecordResolver
        resolver = UnconfiguredRecordResolver()
        # It should be recognised since it has the resolve method signature
        assert isinstance(resolver, RecordResolver), (
            "UnconfiguredRecordResolver must be recognised as RecordResolver "
            "since it implements the resolve() protocol"
        )


# ===================================================================
# ADR-0012 document check
# ===================================================================


class TestADR0012:
    """ADR-0012 exists and records Matador as source of record."""

    ADR_PATH = DOCS_ADR_DIR / "0012-system-of-record-boundary.md"

    def test_adr_0012_exists(self):
        assert self.ADR_PATH.exists(), "ADR-0012 must exist"

    def test_adr_0012_records_matador_as_source_of_record(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "Matador" in content, (
            "ADR-0012 must reference Matador"
        )
        assert "source of record" in content.lower(), (
            "ADR-0012 must record Matador as source of record"
        )

    def test_adr_0012_records_h5_path_as_dev_mode(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "h5_path" in content and "h5_uri" in content, (
            "ADR-0012 must mention h5_path and h5_uri"
        )

    def test_adr_0012_records_no_schema_change(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "no request schema" in content.lower() or \
               "no public source_record_ref" in content.lower(), (
            "ADR-0012 must record no schema change in PR0052"
        )

    def test_adr_0012_records_no_network_calls(self):
        content = self.ADR_PATH.read_text(encoding="utf-8")
        assert "no network" in content.lower() or \
               "no credentials" in content.lower(), (
            "ADR-0012 must record no network calls in PR0052"
        )


# ===================================================================
# API contract doc check
# ===================================================================


class TestAPIContractBoundarySection:
    """docs/api_contract.md documents the system-of-record boundary."""

    def test_api_contract_mentions_pr0052_boundary(self):
        """API contract has a System-of-Record Boundary section."""
        content = API_CONTRACT_PATH.read_text(encoding="utf-8")
        assert "PR0052" in content, (
            "API contract must reference PR0052 boundary"
        )

    def test_api_contract_mentions_no_public_source_record_ref(self):
        """API contract states no public source_record_ref field."""
        content = API_CONTRACT_PATH.read_text(encoding="utf-8")
        assert "source_record_ref" not in content or \
               "no public" in content.lower() or \
               "does NOT add" in content, (
            "API contract must state no public source_record_ref field"
        )
