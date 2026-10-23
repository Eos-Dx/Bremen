"""IR-03 reproducible plugin-wheel and release-assembly tests.

These tests use synthetic inputs only: no real model artifact, no H5 fixture
and no network access.  Real-artifact parity lives in
``tests/test_ir03_parity.py`` and in the project-memory evidence.
"""

from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from bremen.contracts.inference_release import validate_release_manifest
from bremen.ml_plugin.variants import VARIANTS, VariantSpec
from bremen.release_build.assemble import (
    _aux_lock,
    _lock_lines,
    assemble_release,
)
from bremen.release_build.wheel import (
    PLUGIN_REQUIRES_DIST,
    build_plugin_wheel,
    plugin_package_files,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _fake_wheelhouse(tmp_path: Path) -> Path:
    """Create a wheelhouse containing one placeholder wheel per requirement.

    Only filenames and bytes matter for lock hash generation; the lock builder
    never inspects wheel contents.
    """
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    from bremen.release_build.assemble import _MAIN_TRANSITIVE

    for requirement in tuple(PLUGIN_REQUIRES_DIST) + _MAIN_TRANSITIVE:
        name, _, version = requirement.partition("==")
        normalized = name.lower().replace("-", "_").replace(".", "_")
        (wheelhouse / f"{normalized}-{version}-py3-none-any.whl").write_bytes(
            f"{name}=={version}".encode()
        )
    return wheelhouse


def test_lock_lines_require_a_hash_for_every_requirement(tmp_path):
    wheelhouse = _fake_wheelhouse(tmp_path)
    (wheelhouse / "numpy-2.5.4-py3-none-any.whl").unlink()
    with pytest.raises(ValueError, match="no wheel hash"):
        _lock_lines(("numpy==2.5.4",), wheelhouse)


def test_lock_lines_reject_missing_wheelhouse():
    with pytest.raises(ValueError, match="no wheel hash"):
        _lock_lines(("numpy==2.5.4",), None)


def test_aux_lock_rejects_missing_wheelhouse():
    with pytest.raises(ValueError, match="auxiliary wheelhouse is required"):
        _aux_lock("unused-python", None, release_tag="v0.1.7-beta")


def test_main_lock_is_fully_hash_pinned(tmp_path):
    wheelhouse = _fake_wheelhouse(tmp_path)
    from bremen.release_build.assemble import _MAIN_TRANSITIVE

    lock = _lock_lines(tuple(PLUGIN_REQUIRES_DIST) + _MAIN_TRANSITIVE, wheelhouse)
    for line in lock.splitlines():
        assert "--hash=sha256:" in line, line
    assert "scikit-learn==1.9.0 --hash=sha256:" in lock
    assert "scikit-learn==1.9.1" not in lock



def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=").decode("ascii")


def test_plugin_wheel_is_byte_reproducible(tmp_path):
    first = build_plugin_wheel(tmp_path / "one", source_root=SRC)
    second = build_plugin_wheel(tmp_path / "two", source_root=SRC)
    assert first.sha256 == second.sha256
    assert first.path.read_bytes() == second.path.read_bytes()
    assert first.members == second.members


def test_plugin_wheel_contains_only_allowed_packages(tmp_path):
    result = build_plugin_wheel(tmp_path, source_root=SRC)
    with zipfile.ZipFile(result.path) as archive:
        names = archive.namelist()
    assert "bremen/ml_plugin/entrypoint.py" in names
    assert "bremen/contracts/inference_release.py" in names
    assert "bremen/model_packages/bremen_v01/runtime.py" in names
    assert "bremen/model_packages/aramina_v0213/inference.py" in names
    assert "bremen/model_packages_bridge.py" in names
    assert not any(name.startswith("bremen/platform/") for name in names)
    assert not any(name.startswith("bremen/api/") for name in names)
    assert not any("/__pycache__/" in name for name in names)


def test_plugin_wheel_metadata_and_entrypoint(tmp_path):
    result = build_plugin_wheel(tmp_path, source_root=SRC)
    with zipfile.ZipFile(result.path) as archive:
        metadata = archive.read(
            "bremen_ml_plugin-0.1.0.dist-info/METADATA"
        ).decode("utf-8")
        entry_points = archive.read(
            "bremen_ml_plugin-0.1.0.dist-info/entry_points.txt"
        ).decode("utf-8")
    assert "Name: bremen-ml-plugin" in metadata
    assert "Requires-Python: >=3.13,<3.14" in metadata
    assert "Requires-Dist: numpy==2.5.4" in metadata
    assert "Requires-Dist: pandas==3.0.6" in metadata
    assert "Requires-Dist: scikit-learn==1.9.0" in metadata
    assert "bremen-ml-worker = bremen.ml_plugin.entrypoint:main" in entry_points


def test_plugin_wheel_record_is_valid(tmp_path):
    result = build_plugin_wheel(tmp_path, source_root=SRC)
    with zipfile.ZipFile(result.path) as archive:
        record = archive.read(
            "bremen_ml_plugin-0.1.0.dist-info/RECORD"
        ).decode("utf-8")
        entries: dict[str, tuple[str, str]] = {}
        for line in record.splitlines():
            name, digest, size = line.rsplit(",", 2)
            entries[name] = (digest, size)
        assert entries["bremen_ml_plugin-0.1.0.dist-info/RECORD"] == ("", "")
        for name in archive.namelist():
            if name.endswith("/RECORD"):
                continue
            payload = archive.read(name)
            digest, size = entries[name]
            assert digest == f"sha256={_record_hash(payload)}"
            assert size == str(len(payload))


def test_plugin_package_files_are_sorted_and_explicit():
    files = plugin_package_files(SRC)
    names = [name for name, _ in files]
    assert names == sorted(names)
    assert len(names) == len(set(names))


def _synthetic_variant(checksum: str) -> VariantSpec:
    return VariantSpec(
        key="synthetic",
        release_id="synthetic-release",
        workflow_id="bremen",
        runtime_kind="bremen",
        model_id="synthetic-model",
        model_version="0.0.0-synthetic",
        feature_schema_version="v0.1",
        artifact_type="bremen.joblib.model_package",
        artifact_filename="model.joblib",
        artifact_checksum=checksum,
        requires_raw_container=True,
        preprocessing_release="none",
        threshold_source="artifact.portable_logreg.threshold_applied",
    )


def _synthetic_artifact(tmp_path: Path, payload: bytes) -> tuple[Path, str]:
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    checksum = hashlib.sha256(payload).hexdigest()
    (artifact_dir / "model.joblib").write_bytes(payload)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "model_id": "synthetic-model",
                "model_version": "0.0.0-synthetic",
                "model_checksum": checksum,
                "model_filename": "model.joblib",
                "artifact_type": "bremen.joblib.model_package",
            }
        ),
        encoding="utf-8",
    )
    return artifact_dir, checksum


def test_release_assembly_produces_valid_manifest(tmp_path, monkeypatch):
    payload = b"synthetic-artifact-bytes"
    artifact_dir, checksum = _synthetic_artifact(tmp_path, payload)
    monkeypatch.setitem(VARIANTS, "synthetic", _synthetic_variant(checksum))

    summary = assemble_release(
        variant="synthetic",
        artifact_dir=str(artifact_dir),
        output_dir=str(tmp_path / "release"),
        source_root=str(SRC),
        wheelhouse=str(_fake_wheelhouse(tmp_path)),
        commit="a" * 40,
        source_repository="https://example.invalid/synthetic",
    )
    release_dir = Path(summary["output_dir"])
    manifest = json.loads((release_dir / "manifest.json").read_text())
    validated = validate_release_manifest(manifest)
    assert validated.release_id == "synthetic-release"
    assert validated.model.model_id == "synthetic-model"
    assert validated.entrypoint.module == "bremen.ml_plugin.entrypoint"
    assert validated.entrypoint.callable == "main"
    assert validated.scientific_metadata.artifact_checksum == checksum
    assert validated.compatibility.worker_protocol_version == "bremen.worker.v1"
    assert validated.build.commit == "a" * 40
    assert summary["manifest_sha256"] == hashlib.sha256(
        (release_dir / "manifest.json").read_bytes()
    ).hexdigest()

    # Every declared file exists at its relative path with the declared size/hash.
    for ref in validated.files:
        path = release_dir / ref.relative_path
        assert path.is_file(), ref.relative_path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ref.sha256
        assert path.stat().st_size == ref.size_bytes

    # No release descriptor may embed a machine-local absolute path.
    runtime_config = json.loads(
        (release_dir / "configs" / "runtime.json").read_text()
    )
    for value in runtime_config["preprocessing_environment"].values():
        assert not value.startswith("/"), value
    for value in manifest["environments"].values():
        assert "python_executable" not in value

    assert (release_dir / "model" / "model.joblib").read_bytes() == payload
    assert any(ref.role == "plugin_wheel" for ref in validated.files)
    assert any(ref.role == "model_artifact" for ref in validated.files)
    assert any(ref.role == "requirements_lock" for ref in validated.files)
    assert any(ref.role == "provenance" for ref in validated.files)
    assert validated.golden_tests[0].relative_path == "golden_tests/cases.json"

    # Dependency wheels are release-bound, declared and hash-verified.
    wheel_refs = [ref for ref in validated.files if ref.role == "dependency_wheel"]
    assert wheel_refs
    for ref in wheel_refs:
        path = release_dir / ref.relative_path
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ref.sha256
        assert ref.size_bytes == path.stat().st_size


def test_release_assembly_embeds_wheels_and_golden_fixtures(tmp_path, monkeypatch):
    payload = b"synthetic-artifact-bytes"
    artifact_dir, checksum = _synthetic_artifact(tmp_path, payload)
    monkeypatch.setitem(VARIANTS, "synthetic", _synthetic_variant(checksum))
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "case.h5").write_bytes(b"fixture-bytes")
    from bremen.release_build import assemble as assemble_module

    monkeypatch.setitem(
        assemble_module._GOLDEN_CASES,
        "synthetic",
        [
            {
                "case_id": "synthetic-case",
                "fixture": "case.h5",
                "expected": {
                    "status": "ok",
                    "probability": 0.5,
                    "threshold_applied": 0.4,
                    "prediction": 1,
                },
            }
        ],
    )

    summary = assemble_release(
        variant="synthetic",
        artifact_dir=str(artifact_dir),
        output_dir=str(tmp_path / "release"),
        source_root=str(SRC),
        wheelhouse=str(_fake_wheelhouse(tmp_path)),
        fixtures_root=str(fixtures),
        commit="a" * 40,
        source_repository="https://example.invalid/synthetic",
    )
    release_dir = Path(summary["output_dir"])
    manifest = json.loads((release_dir / "manifest.json").read_text())

    wheel_refs = [ref for ref in manifest["files"] if ref["role"] == "dependency_wheel"]
    assert wheel_refs
    for ref in wheel_refs:
        assert ref["relative_path"].startswith("wheelhouse/main/")
        assert ref["size_bytes"] > 0
        assert (release_dir / ref["relative_path"]).is_file()
    golden_refs = [
        ref for ref in manifest["golden_tests"] if ref["role"] == "golden_fixture"
    ]
    assert [ref["relative_path"] for ref in golden_refs] == [
        "golden_tests/fixtures/case.h5"
    ]
    assert golden_refs[0]["size_bytes"] == len(b"fixture-bytes")
    assert golden_refs[0]["sha256"] == hashlib.sha256(b"fixture-bytes").hexdigest()
    cases = json.loads((release_dir / "golden_tests" / "cases.json").read_text())
    assert cases["cases"][0]["fixture_release_path"] == (
        "golden_tests/fixtures/case.h5"
    )


def test_release_assembly_rejects_tampered_artifact(tmp_path, monkeypatch):
    payload = b"synthetic-artifact-bytes"
    artifact_dir, checksum = _synthetic_artifact(tmp_path, payload)
    monkeypatch.setitem(VARIANTS, "synthetic", _synthetic_variant(checksum))
    (artifact_dir / "model.joblib").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        assemble_release(
            variant="synthetic",
            artifact_dir=str(artifact_dir),
            output_dir=str(tmp_path / "release"),
            source_root=str(SRC),
            wheelhouse=str(_fake_wheelhouse(tmp_path)),
            commit="a" * 40,
        )


def test_release_assembly_requires_explicit_commit(tmp_path, monkeypatch):
    payload = b"synthetic-artifact-bytes"
    artifact_dir, checksum = _synthetic_artifact(tmp_path, payload)
    monkeypatch.setitem(VARIANTS, "synthetic", _synthetic_variant(checksum))
    monkeypatch.setattr(
        "bremen.release_build.assemble._git", lambda *args, **kwargs: None,
    )
    with pytest.raises(RuntimeError, match="commit"):
        assemble_release(
            variant="synthetic",
            artifact_dir=str(artifact_dir),
            output_dir=str(tmp_path / "release"),
            source_root=str(SRC),
            wheelhouse=str(_fake_wheelhouse(tmp_path)),
        )
