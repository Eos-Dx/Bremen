"""Tests for the Bremen demo readiness capture module.

Covers:
- DEMO_CAPTURE_VERSION constant
- build_capture_manifest() shape and invariants
- write_demo_capture() writes 3 files
- File content validation (JSON, pretty text, manifest)
- Directory creation
- FileExistsError when capture_dir is a file
- FileExistsError when output files exist
- No Aramis references
- No clinical/replacement claims (except safe negation)
- JSON serializability
- Import/dependency safety
"""

from __future__ import annotations

import ast
import json
import os
import tempfile
from pathlib import Path

import pytest

from bremen.demo_capture import (
    DEMO_CAPTURE_VERSION,
    FILE_SUMMARY,
    FILE_EVIDENCE,
    FILE_MANIFEST,
    build_capture_manifest,
    write_demo_capture,
)

MODULE_PATH = Path(__file__).parents[1] / "src" / "bremen" / "demo_capture.py"


# ===================================================================
# Helpers
# ===================================================================


def _make_result() -> dict:
    """Return a sample demo-run result dict for testing."""
    return {
        "technical_demo_only": True,
        "base_url": "http://127.0.0.1:52731",
        "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "status": "pass",
        "checks": {
            "health": "pass",
            "model_version": "pass",
        },
        "health": {
            "status": "ok",
            "model_ready": True,
            "service": "bremen",
            "version": "v0.1",
        },
        "model_version": {
            "model_configured": True,
            "model_status": "ready",
            "model_version": "smoke-v0.1",
        },
        "prediction": {
            "status": "not_available",
            "reason": "Prediction check was skipped.",
        },
        "evidence": {
            "technical_demo_only": True,
            "product": "Bremen",
            "product_question": "Should patient continue to MRI?",
            "disclaimer": "Test disclaimer.",
            "evidence_version": "v0.1",
            "scenario_id": "bremen_demo_v1",
            "safety_notes": [
                "Technical product demo only — not a clinical result.",
            ],
        },
        "warnings": [],
        "timestamp": "2026-07-15T10:00:00",
    }


def _make_pretty_text() -> str:
    """Return sample pretty text for capture testing."""
    return (
        "BREMEN PRODUCT DEMO\n"
        "Technical demo only — not a clinical result.\n"
        "\n"
        "Status: PASS\n"
        "This is a technical product demo.\n"
    )


def _file_list() -> list[dict[str, str]]:
    """Return the standard file list for manifest testing."""
    return [
        {"filename": FILE_SUMMARY, "description": "Pretty text summary"},
        {"filename": FILE_EVIDENCE, "description": "Evidence/result JSON"},
        {"filename": FILE_MANIFEST, "description": "Capture metadata"},
    ]


# ===================================================================
# Class 1: Constants
# ===================================================================


class TestCaptureVersion:
    def test_demo_capture_version_is_non_empty_string(self):
        """DEMO_CAPTURE_VERSION is a non-empty string."""
        assert isinstance(DEMO_CAPTURE_VERSION, str)
        assert len(DEMO_CAPTURE_VERSION) > 0

    def test_file_constants_are_non_empty_strings(self):
        """File name constants are non-empty strings."""
        for fname in (FILE_SUMMARY, FILE_EVIDENCE, FILE_MANIFEST):
            assert isinstance(fname, str)
            assert len(fname) > 0


# ===================================================================
# Class 2: build_capture_manifest
# ===================================================================


class TestBuildCaptureManifest:
    def test_manifest_is_dict(self):
        """build_capture_manifest returns a dict."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert isinstance(manifest, dict)

    def test_manifest_has_all_required_fields(self):
        """Manifest contains all expected keys."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        expected_keys = {
            "demo_capture_version",
            "generated_at_utc",
            "technical_demo_only",
            "product",
            "status",
            "request_id",
            "files",
            "safety_notes",
        }
        assert expected_keys <= set(manifest.keys()), (
            f"Missing keys: {expected_keys - set(manifest.keys())}"
        )

    def test_technical_demo_only_is_true(self):
        """technical_demo_only is True."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert manifest["technical_demo_only"] is True

    def test_product_is_bremen(self):
        """Product is 'Bremen'."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert manifest["product"] == "Bremen"

    def test_status_from_result(self):
        """Status is taken from result dict."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert manifest["status"] == "pass"

    def test_status_reflects_failure(self):
        """Status from a fail result is 'fail'."""
        result = _make_result()
        result["status"] = "fail"
        manifest = build_capture_manifest(result, _file_list())
        assert manifest["status"] == "fail"

    def test_request_id_from_result(self):
        """request_id is taken from result dict."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert manifest["request_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_files_listed(self):
        """Files list contains all 3 expected filenames."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert len(manifest["files"]) == 3
        filenames = [f["filename"] for f in manifest["files"]]
        assert FILE_SUMMARY in filenames
        assert FILE_EVIDENCE in filenames
        assert FILE_MANIFEST in filenames

    def test_safety_notes_is_non_empty_list(self):
        """safety_notes is a non-empty list of strings."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert isinstance(manifest["safety_notes"], list)
        assert len(manifest["safety_notes"]) > 0
        for note in manifest["safety_notes"]:
            assert isinstance(note, str)
            assert len(note) > 0

    def test_accepts_explicit_generated_at_utc(self):
        """Accepts explicit generated_at_utc for determinism."""
        result = _make_result()
        fixed_ts = "2026-01-01T00:00:00"
        manifest = build_capture_manifest(
            result, _file_list(), generated_at_utc=fixed_ts
        )
        assert manifest["generated_at_utc"] == fixed_ts

    def test_default_generated_at_utc_is_string(self):
        """Default generated_at_utc is a non-empty string."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert isinstance(manifest["generated_at_utc"], str)
        assert len(manifest["generated_at_utc"]) > 0

    def test_demo_capture_version_constant(self):
        """demo_capture_version matches the module constant."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        assert manifest["demo_capture_version"] == DEMO_CAPTURE_VERSION

    def test_manifest_is_json_serializable(self):
        """Manifest is JSON-serializable."""
        result = _make_result()
        manifest = build_capture_manifest(result, _file_list())
        json_str = json.dumps(manifest)
        assert isinstance(json_str, str)
        assert len(json_str) > 0


# ===================================================================
# Class 3: write_demo_capture — basic file creation
# ===================================================================


class TestWriteDemoCaptureBasic:
    def test_writes_three_files(self, tmp_path: Path):
        """write_demo_capture writes 3 files to capture_dir."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        manifest = write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        # Verify files exist
        dir_path = Path(capture_dir)
        assert (dir_path / FILE_SUMMARY).exists()
        assert (dir_path / FILE_EVIDENCE).exists()
        assert (dir_path / FILE_MANIFEST).exists()
        # Verify manifest is returned
        assert isinstance(manifest, dict)
        assert manifest["demo_capture_version"] == DEMO_CAPTURE_VERSION

    def test_creates_directory(self, tmp_path: Path):
        """Creates the capture directory if it doesn't exist."""
        result = _make_result()
        capture_dir = str(tmp_path / "new" / "capture" / "dir")
        assert not Path(capture_dir).exists()
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        assert Path(capture_dir).is_dir()

    def test_summary_contains_pretty_text(self, tmp_path: Path):
        """Summary file contains the provided pretty text."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        pretty = _make_pretty_text()
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=pretty,
        )
        content = (Path(capture_dir) / FILE_SUMMARY).read_text(encoding="utf-8")
        assert "BREMEN PRODUCT DEMO" in content
        assert "Technical demo only" in content

    def test_evidence_json_is_valid(self, tmp_path: Path):
        """Evidence JSON file parses correctly."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        content = (Path(capture_dir) / FILE_EVIDENCE).read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["technical_demo_only"] is True
        assert parsed["status"] == "pass"
        assert parsed["request_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_evidence_contains_technical_demo_only(self, tmp_path: Path):
        """Evidence JSON contains technical_demo_only."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        content = (Path(capture_dir) / FILE_EVIDENCE).read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["technical_demo_only"] is True

    def test_manifest_is_valid_json(self, tmp_path: Path):
        """Manifest JSON parses and validates shape."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        content = (Path(capture_dir) / FILE_MANIFEST).read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["technical_demo_only"] is True
        assert parsed["product"] == "Bremen"
        assert len(parsed["files"]) == 3
        assert len(parsed["safety_notes"]) > 0

    def test_returns_manifest(self, tmp_path: Path):
        """Returns the manifest dict."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        manifest = write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        assert manifest["technical_demo_only"] is True
        assert manifest["demo_capture_version"] == DEMO_CAPTURE_VERSION


# ===================================================================
# Class 4: write_demo_capture — fallback without pretty
# ===================================================================


class TestWriteDemoCaptureFallback:
    def test_writes_without_pretty_text(self, tmp_path: Path):
        """Works when pretty_text is None — writes fallback summary."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=None,
        )
        # Files should still be written
        assert (Path(capture_dir) / FILE_SUMMARY).exists()
        assert (Path(capture_dir) / FILE_EVIDENCE).exists()
        assert (Path(capture_dir) / FILE_MANIFEST).exists()

    def test_fallback_summary_contains_bremen(self, tmp_path: Path):
        """Fallback summary contains Bremen identity and safety."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=None,
        )
        content = (Path(capture_dir) / FILE_SUMMARY).read_text(encoding="utf-8")
        assert "BREMEN PRODUCT DEMO" in content
        assert "Technical demo only" in content
        assert "Bremen" in content
        assert "Not clinically validated" in content


# ===================================================================
# Class 5: FileExistsError checks
# ===================================================================


class TestFileExistsError:
    def test_raises_when_capture_dir_is_file(self, tmp_path: Path):
        """Raises FileExistsError when capture_dir is a regular file."""
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("I am a file")
        result = _make_result()
        with pytest.raises(FileExistsError, match="exists as a file"):
            write_demo_capture(
                result=result,
                capture_dir=str(file_path),
                pretty_text=_make_pretty_text(),
            )

    def test_raises_when_output_files_exist(self, tmp_path: Path):
        """Raises FileExistsError when output files already exist."""
        capture_dir = tmp_path / "capture"
        capture_dir.mkdir()
        (capture_dir / FILE_SUMMARY).write_text("existing content")
        result = _make_result()
        with pytest.raises(FileExistsError, match="already exist"):
            write_demo_capture(
                result=result,
                capture_dir=str(capture_dir),
                pretty_text=_make_pretty_text(),
            )

    def test_no_error_when_dir_exists_but_empty(self, tmp_path: Path):
        """No error when capture_dir exists but is empty."""
        capture_dir = tmp_path / "capture"
        capture_dir.mkdir()
        result = _make_result()
        # Should not raise
        manifest = write_demo_capture(
            result=result,
            capture_dir=str(capture_dir),
            pretty_text=_make_pretty_text(),
        )
        assert isinstance(manifest, dict)


# ===================================================================
# Class 6: No Aramis references
# ===================================================================


class TestNoAramisReferences:
    def test_no_aramis_in_capture_files(self, tmp_path: Path):
        """Capture files do not contain Aramis strings."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        dir_path = Path(capture_dir)
        for fname in (FILE_SUMMARY, FILE_EVIDENCE, FILE_MANIFEST):
            content = (dir_path / fname).read_text(encoding="utf-8").lower()
            for pattern in ("aramis", "m2q", "benign vs cancer"):
                assert pattern not in content, (
                    f"{fname} contains prohibited pattern: {pattern}"
                )

    def test_no_aramis_in_module_source(self):
        """Module source does not contain Aramis references."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "Aramis" not in source
        assert "aramis" not in source


# ===================================================================
# Class 7: No clinical/replacement claims
# ===================================================================


class TestNoClinicalReplacementLanguage:
    def test_no_clinical_claims_in_capture_files(self, tmp_path: Path):
        """Capture files do not contain clinical claims (except safe negation)."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        dir_path = Path(capture_dir)
        for fname in (FILE_SUMMARY, FILE_EVIDENCE, FILE_MANIFEST):
            content = (dir_path / fname).read_text(encoding="utf-8").lower()
            # Safe negation is allowed in safety notes
            assert "replaces mri" not in content
            assert "replaces biopsy" not in content
            assert "replaces radiologist" not in content
            assert "replaces clinician" not in content

    def test_safety_notes_use_negation(self, tmp_path: Path):
        """Safety notes use negation language, not claims."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        content = (Path(capture_dir) / FILE_MANIFEST).read_text(encoding="utf-8")
        assert "Does not replace MRI" in content
        assert "Not clinically validated" in content


# ===================================================================
# Class 8: JSON serializability
# ===================================================================


class TestJsonSerializable:
    def test_evidence_json_parses(self, tmp_path: Path):
        """Evidence JSON can be parsed with json.loads."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        content = (Path(capture_dir) / FILE_EVIDENCE).read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_manifest_json_parses(self, tmp_path: Path):
        """Manifest JSON can be parsed with json.loads."""
        result = _make_result()
        capture_dir = str(tmp_path / "capture")
        write_demo_capture(
            result=result,
            capture_dir=capture_dir,
            pretty_text=_make_pretty_text(),
        )
        content = (Path(capture_dir) / FILE_MANIFEST).read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)


# ===================================================================
# Class 9: Determinism
# ===================================================================


class TestDeterminism:
    def test_manifest_deterministic_with_fixed_timestamp(self):
        """Manifest is deterministic with fixed generated_at_utc."""
        result = _make_result()
        fixed_ts = "2026-01-01T00:00:00"
        m1 = build_capture_manifest(
            result, _file_list(), generated_at_utc=fixed_ts
        )
        m2 = build_capture_manifest(
            result, _file_list(), generated_at_utc=fixed_ts
        )
        assert m1 == m2


# ===================================================================
# Class 10: Import/dependency safety
# ===================================================================


class TestImportSafety:
    def test_no_h5_references(self):
        """Module does not reference h5, hdf5, or h5py."""
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        assert ".h5" not in source
        assert ".hdf5" not in source
        assert "h5py" not in source

    def test_no_joblib_or_pickle(self):
        """Module does not reference joblib or pickle."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "joblib" not in source.lower()
        assert "pickle" not in source

    def test_no_boto3_or_requests(self):
        """Module does not import boto3, requests, httpx."""
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in (
                        "boto3", "requests", "httpx", "botocore"
                    ), f"Module imports {name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                assert top not in (
                    "boto3", "requests", "httpx", "botocore"
                ), f"Module imports {module}"
