"""Assemble one local, self-contained IR-03 Model Release directory.

The release contains the IR-02 manifest, the reproducible plugin wheel, the
checksum-verified model artifact, release configs, hash-locked dependency
requirements, explicit provenance and golden-test descriptors.

Nothing is published.  ``s3_key`` values are the intended immutable object
keys for a later publication step; this builder writes only local files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bremen.contracts.inference_release import (
    SCHEMA_ID,
    validate_release_manifest,
)
from bremen.contracts.worker_protocol import PROTOCOL_ID
from bremen.ml_plugin import PLUGIN_DISTRIBUTION, PLUGIN_VERSION
from bremen.ml_plugin.variants import VARIANTS, VariantSpec, variant_spec
from bremen.release_build.provenance import (
    capture_environment_closure,
    capture_preprocessing_provenance,
    KNOWN_PREPROCESSING_COMMITS,
)
from bremen.release_build.wheel import PLUGIN_REQUIRES_DIST, build_plugin_wheel

__all__ = ["assemble_release", "main"]

_GOLDEN_SCHEMA = "bremen.golden-cases.v1"
_BUILD_SCHEMA = "bremen.release-build.v1"

#: Full observed main-environment closure (direct + transitive).
_MAIN_TRANSITIVE = (
    "python-dateutil==2.9.0.post0",
    "six==1.17.0",
    "threadpoolctl==3.7.0",
    "packaging==26.3",
    "cloudpickle==3.1.2",
    "narwhals==2.27.1",
)

_GOLDEN_CASES: dict[str, list[dict[str, Any]]] = {
    "a1": [
        {
            "case_id": "a1-nova214-left",
            "fixture": "eoscloud-staging/cabce03d-f9c4-43db-91d1-aec20007ee18.h5",
            "patient_id": "Nova_214",
            "target_side": "left",
            "expected": {
                "status": "ok",
                "risk_probability": 0.8693870739736473,
                "decision_threshold": 0.24665932038818544,
                "target_class_risk_level": 1,
            },
        },
        {
            "case_id": "a1-nova376-left-preprocessing-failure",
            "fixture": "Nova_376.h5",
            "patient_id": "Nova_376",
            "target_side": "left",
            "expected": {
                "status": "error",
                "error_code": "QC_FAILED",
                "safe_reason": "ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract",
                "preprocessing_release": "v0.1.7-beta",
            },
        },
    ],
    "a2": [
        {
            "case_id": "a2-nova214-left",
            "fixture": "eoscloud-staging/cabce03d-f9c4-43db-91d1-aec20007ee18.h5",
            "patient_id": "Nova_214",
            "target_side": "left",
            "expected": {
                "status": "ok",
                "risk_probability": 0.8693870739736473,
                "decision_threshold": 0.24665932038818544,
                "target_class_risk_level": 1,
            },
        },
        {
            "case_id": "a2-nova376-left-preprocessing-failure",
            "fixture": "Nova_376.h5",
            "patient_id": "Nova_376",
            "target_side": "left",
            "expected": {
                "status": "error",
                "error_code": "QC_FAILED",
                "safe_reason": "ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract",
                "preprocessing_release": "v0.1.9-beta",
            },
        },
    ],
    "b1": [
        {
            "case_id": "b1-benign",
            "fixture": "benign_one_patient.h5",
            "expected": {
                "status": "ok",
                "probability": 0.8524639494195422,
                "threshold_applied": 0.3640352477169748,
                "prediction": 1,
            },
        },
        {
            "case_id": "b1-nova376",
            "fixture": "Nova_376.h5",
            "expected": {
                "status": "ok",
                "probability": 0.5677291934209037,
                "threshold_applied": 0.3640352477169748,
                "prediction": 1,
            },
        },
        {
            "case_id": "b1-cancer-qc",
            "fixture": "cancer_one_patient.h5",
            "expected": {
                "status": "error",
                "error_code": "QC_FAILED",
                "safe_reason": "raw_peak_gate_failed",
            },
        },
    ],
    "b2": [
        {
            "case_id": "b2-benign",
            "fixture": "benign_one_patient.h5",
            "expected": {
                "status": "ok",
                "probability": 0.7726940329943811,
                "threshold_applied": 0.3585907282566089,
                "prediction": 1,
            },
        },
        {
            "case_id": "b2-cancer-qc",
            "fixture": "cancer_one_patient.h5",
            "expected": {
                "status": "error",
                "error_code": "QC_FAILED",
                "safe_reason": "raw_peak_gate_failed",
            },
        },
    ],
    "b3": [
        {
            "case_id": "b3-benign",
            "fixture": "benign_one_patient.h5",
            "expected": {
                "status": "ok",
                "probability": 0.6848549443589647,
                "threshold_applied": 0.4130396520921527,
                "prediction": 1,
            },
        },
        {
            "case_id": "b3-atypical-shape",
            "fixture": "atypical_one_patient.h5",
            "expected": {
                "status": "error",
                "error_code": "INPUT_INVALID",
                "safe_reason": "requires_exactly_3_left_3_right",
            },
        },
    ],
}


@dataclass(frozen=True)
class AuxEnvironment:
    release_tag: str
    python_executable: str


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, data: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return _sha256_bytes(text.encode("utf-8"))


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=root, text=True, capture_output=True, check=False,
        )
    except Exception:
        return None
    if completed.returncode:
        return None
    return completed.stdout.strip() or None


def _artifact_files(spec: VariantSpec, artifact_dir: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"artifact manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model_id") != spec.model_id:
        raise ValueError(f"{spec.key}: artifact model_id does not match release spec")
    if manifest.get("model_checksum") != spec.artifact_checksum:
        raise ValueError(f"{spec.key}: artifact checksum does not match release spec")
    if manifest.get("model_filename") != spec.artifact_filename:
        raise ValueError(f"{spec.key}: artifact filename does not match release spec")
    artifact_path = artifact_dir / spec.artifact_filename
    if not artifact_path.is_file():
        raise FileNotFoundError(f"artifact missing: {artifact_path}")
    actual = _sha256_file(artifact_path)
    if actual != spec.artifact_checksum:
        raise ValueError(f"{spec.key}: artifact bytes failed checksum verification")
    return artifact_path, manifest


def _artifact_config_hash(spec: VariantSpec, artifact_path: Path) -> str:
    if spec.preprocessing_release == "none":
        return ""
    from bremen.model_packages_bridge import load_staged_artifact

    if spec.runtime_kind == "aramina":
        from bremen.model_packages.aramina_v0213.artifact_compat import (
            ensure_compatibility_bridge,
        )

        ensure_compatibility_bridge()
    package = load_staged_artifact(str(artifact_path), spec.artifact_checksum)
    config_yaml = package.get("prediction_preprocessing_yaml") if isinstance(package, dict) else None
    if not isinstance(config_yaml, str) or not config_yaml.strip():
        raise ValueError(f"{spec.key}: artifact has no prediction preprocessing config")
    return _sha256_bytes(config_yaml.encode("utf-8"))


def _feature_order_hash(spec: VariantSpec) -> str:
    if spec.runtime_kind == "aramina":
        from bremen.model_packages.aramina_v0213 import manifest as aramina_manifest

        columns = list(aramina_manifest.FINAL_FEATURE_COLUMNS)
    else:
        from bremen.model_packages.bremen_v01.features import FEATURE_COLS

        columns = list(FEATURE_COLS)
    return _sha256_bytes(json.dumps(columns).encode("utf-8"))


def _wheel_paths_by_hash(wheelhouse: Path | None) -> dict[str, Path]:
    """Map every wheel SHA-256 in a local wheelhouse to its path."""
    mapping: dict[str, Path] = {}
    if wheelhouse is None:
        return mapping
    for wheel in sorted(wheelhouse.glob("*.whl")):
        mapping[_sha256_file(wheel)] = wheel
    return mapping


def _copy_lock_wheels(
    lock_text: str, source: Path | None, destination: Path,
) -> list[Path]:
    """Copy exactly the wheels referenced by a hash-locked file.

    The lock is the authoritative closure; every referenced hash must exist
    as a real wheel or assembly fails.  Returns the copied paths.
    """
    available = _wheel_paths_by_hash(source)
    copied: list[Path] = []
    seen: set[str] = set()
    for line in lock_text.splitlines():
        for digest in re.findall(r"--hash=sha256:([a-f0-9]{64})", line):
            if digest in seen:
                continue
            wheel = available.get(digest)
            if wheel is None:
                raise ValueError(
                    f"hash-locked wheel {digest} is not present in {source}"
                )
            seen.add(digest)
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / wheel.name
            shutil.copyfile(wheel, target)
            copied.append(target)
    return copied


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def _wheel_hashes(wheelhouse: Path | None) -> dict[tuple[str, str], list[str]]:
    """Map every ``(normalized name, version)`` to its wheel SHA-256s."""
    hashes: dict[tuple[str, str], list[str]] = {}
    if wheelhouse is None:
        return hashes
    for wheel in sorted(wheelhouse.glob("*.whl")):
        parts = wheel.name.split("-")
        if len(parts) < 5:  # name-version-build?-python-abi-platform
            continue
        key = (_normalize_name(parts[0]), parts[1])
        hashes.setdefault(key, []).append(_sha256_file(wheel))
    return hashes


def _lock_lines(
    requirements: tuple[str, ...], wheelhouse: Path | None,
) -> str:
    """Emit a fully hash-pinned lock, or fail closed.

    Every requirement must resolve to at least one actual wheel in the local
    wheelhouse so the lock is installable with
    ``--no-index --only-binary=:all: --require-hashes``.
    """
    available = _wheel_hashes(wheelhouse)
    lines: list[str] = []
    for requirement in requirements:
        name, _, version = requirement.partition("==")
        hashes = available.get((_normalize_name(name), version), [])
        if not hashes:
            raise ValueError(
                f"no wheel hash available for {requirement!r} in {wheelhouse}"
            )
        for digest in hashes:
            lines.append(f"{name}=={version} --hash=sha256:{digest}")
    return "\n".join(lines) + "\n"


def _aux_lock(
    python_executable: str, wheelhouse: Path | None,
    *, release_tag: str,
) -> str:
    if wheelhouse is None:
        raise ValueError(
            f"an auxiliary wheelhouse is required to hash-lock {release_tag}"
        )
    closure = capture_environment_closure(python_executable)
    requirements = tuple(
        f"{item['name']}=={item['version']}" for item in closure
    )
    return _lock_lines(requirements, wheelhouse)


def _required_aux_tags(spec: VariantSpec) -> tuple[str, ...]:
    if spec.preprocessing_release == "none":
        return ()
    return (spec.preprocessing_release,)


def _golden_files(
    spec: VariantSpec, fixtures_root: Path, release_root: Path,
) -> tuple[dict[str, Any], list[Path]]:
    """Copy every golden fixture into the release and describe the cases.

    Golden inputs are part of the release closure: a missing fixture fails
    assembly rather than producing a release that cannot be smoke-verified.
    """
    cases = []
    copied: list[Path] = []
    for case in _GOLDEN_CASES.get(spec.key, []):
        entry = dict(case)
        fixture_path = fixtures_root / case["fixture"]
        if not fixture_path.is_file():
            raise FileNotFoundError(f"golden fixture missing: {fixture_path}")
        relative = f"golden_tests/fixtures/{case['fixture']}"
        target = release_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture_path, target)
        copied.append(target)
        entry["fixture_release_path"] = relative
        entry["fixture_sha256"] = _sha256_file(target)
        cases.append(entry)
    return (
        {
            "schema_version": _GOLDEN_SCHEMA,
            "release_id": spec.release_id,
            "cases": cases,
        },
        copied,
    )


def _file_ref(
    *, role: str, relative_path: str, release_id: str, path: Path,
    require_size: bool = True,
) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "role": role,
        "relative_path": relative_path,
        "s3_key": f"releases/{release_id}/{relative_path}",
        "sha256": _sha256_file(path),
    }
    if require_size:
        ref["size_bytes"] = path.stat().st_size
    return ref


def _compatibility() -> dict[str, Any]:
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "abi": str(sysconfig.get_config_var("SOABI") or "unknown"),
        "os": platform.system().lower() or "unknown",
        "arch": platform.machine() or "unknown",
        "worker_protocol_version": PROTOCOL_ID,
        "native_libraries": [],
    }


def assemble_release(
    *,
    variant: str,
    artifact_dir: str,
    output_dir: str,
    source_root: str | None = None,
    wheelhouse: str | None = None,
    fixtures_root: str | None = None,
    aux_environments: dict[str, str] | None = None,
    aux_wheelhouses: dict[str, str] | None = None,
    aux_source_commits: dict[str, str] | None = None,
    commit: str | None = None,
    source_repository: str | None = None,
) -> dict[str, Any]:
    """Build one local release directory and return its evidence summary."""
    spec = variant_spec(variant)
    artifact_root = Path(artifact_dir).resolve()
    release_root = Path(output_dir).resolve()
    release_root.mkdir(parents=True, exist_ok=True)
    wheelhouse_path = Path(wheelhouse).resolve() if wheelhouse else None
    fixtures_path = Path(fixtures_root).resolve() if fixtures_root else None

    artifact_path, artifact_manifest = _artifact_files(spec, artifact_root)

    repo_root = Path(__file__).resolve().parents[3]
    commit_value = commit or _git(repo_root, "rev-parse", "HEAD")
    if not commit_value:
        raise RuntimeError(
            "no source commit available; refusing to fabricate build provenance"
        )
    repository = source_repository or _git(repo_root, "remote", "get-url", "origin") or "local-workspace"

    # Plugin wheel (deterministic).
    plugin_dir = release_root / "plugin"
    wheel = build_plugin_wheel(
        plugin_dir, source_root=source_root,
    )

    # Artifact + configs.
    model_dir = release_root / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    local_artifact = model_dir / spec.artifact_filename
    shutil.copyfile(artifact_path, local_artifact)
    (release_root / "configs").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact_root / "manifest.json", release_root / "configs" / "artifact_manifest.json")

    # Auxiliary preprocessing environments (observed exact closures).
    required_tags = _required_aux_tags(spec)
    aux = dict(aux_environments or {})
    for tag in required_tags:
        if tag not in aux:
            raise RuntimeError(f"missing pinned auxiliary environment for {tag}")
    provenance_dir = release_root / "provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)
    aux_locks: dict[str, str] = {}
    aux_wheels: dict[str, list[Path]] = {}
    aux_provenance: dict[str, dict[str, Any]] = {}
    aux_commits = dict(aux_source_commits or {})
    aux_wheelhouse_paths = dict(aux_wheelhouses or {})
    for tag in required_tags:
        executable = aux[tag]
        record = capture_preprocessing_provenance(
            executable, tag, source_commit=aux_commits.get(tag),
        )
        provenance_name = f"xrd-preprocessing-{tag}.json"
        _write_json(provenance_dir / provenance_name, record)
        aux_provenance[tag] = record
        lock_name = f"aux-{tag}.lock"
        (release_root / "requirements").mkdir(parents=True, exist_ok=True)
        aux_lock_path = release_root / "requirements" / lock_name
        aux_lock_path.write_text(
            _aux_lock(
                executable,
                Path(aux_wheelhouse_paths[tag]).resolve()
                if tag in aux_wheelhouse_paths else None,
                release_tag=tag,
            ),
            encoding="utf-8",
        )
        aux_locks[tag] = lock_name
        aux_wheels[tag] = _copy_lock_wheels(
            aux_lock_path.read_text(encoding="utf-8"),
            Path(aux_wheelhouse_paths[tag]).resolve()
            if tag in aux_wheelhouse_paths else None,
            release_root / "wheelhouse" / "aux" / tag,
        )

    # Main lock (hash-locked when a local wheelhouse is supplied).
    main_requirements = tuple(PLUGIN_REQUIRES_DIST) + _MAIN_TRANSITIVE
    main_lock_path = release_root / "requirements" / "main.lock"
    main_lock_path.parent.mkdir(parents=True, exist_ok=True)
    main_lock_text = _lock_lines(main_requirements, wheelhouse_path)
    main_lock_path.write_text(main_lock_text, encoding="utf-8")
    main_wheels = _copy_lock_wheels(
        main_lock_text, wheelhouse_path, release_root / "wheelhouse" / "main",
    )

    # Golden fixtures are copied into the release so READY never depends on an
    # external fixture directory.
    if fixtures_path is None and _GOLDEN_CASES.get(spec.key):
        raise RuntimeError("golden fixtures are required for this release")
    if fixtures_path is not None:
        golden, golden_copies = _golden_files(spec, fixtures_path, release_root)
    else:
        golden, golden_copies = (
            {
                "schema_version": _GOLDEN_SCHEMA,
                "release_id": spec.release_id,
                "cases": [],
            },
            [],
        )
    _write_json(release_root / "golden_tests" / "cases.json", golden)

    # Release runtime config.
    preprocessing_environment: dict[str, str] = {}
    if spec.preprocessing_release != "none":
        tag = spec.preprocessing_release
        if spec.runtime_kind == "aramina":
            variable = (
                "BREMEN_ARAMINA_PREPROCESS_019_PYTHON"
                if tag == "v0.1.9-beta" else "BREMEN_ARAMINA_PREPROCESS_PYTHON"
            )
            preprocessing_environment[variable] = f"@aux/{tag}"
            preprocessing_environment["BREMEN_ARAMINA_PREPROCESS_PROVENANCE"] = (
                f"@release/provenance/xrd-preprocessing-{tag}.json"
            )
        else:
            preprocessing_environment["BREMEN_PREPROCESS_PYTHON"] = f"@aux/{tag}"
            preprocessing_environment["BREMEN_PREPROCESS_PROVENANCE"] = (
                f"@release/provenance/xrd-preprocessing-{tag}.json"
            )

    runtime_config = {
        "schema_version": "bremen.ml-plugin.runtime.v1",
        "release_id": spec.release_id,
        "variant": spec.key,
        "workflow_id": spec.workflow_id,
        "artifact": {
            "relative_path": f"model/{spec.artifact_filename}",
            "sha256": spec.artifact_checksum,
            "model_id": spec.model_id,
            "model_version": spec.model_version,
        },
        "preprocessing_environment": preprocessing_environment,
    }
    _write_json(release_root / "configs" / "runtime.json", runtime_config)

    build_record = {
        "schema_version": _BUILD_SCHEMA,
        "release_id": spec.release_id,
        "variant": spec.key,
        "source_repository": repository,
        "source_commit": commit_value,
        "plugin_distribution": PLUGIN_DISTRIBUTION,
        "plugin_version": PLUGIN_VERSION,
        "plugin_wheel_sha256": wheel.sha256,
        "artifact_sha256": spec.artifact_checksum,
        "artifact_filename": spec.artifact_filename,
        "artifact_manifest": artifact_manifest,
        "main_lock_sha256": _sha256_file(main_lock_path),
        "aux_locks": {
            tag: _sha256_file(release_root / "requirements" / name)
            for tag, name in aux_locks.items()
        },
        "main_wheel_count": len(main_wheels),
        "aux_wheel_counts": {tag: len(items) for tag, items in aux_wheels.items()},
        "aux_provenance": aux_provenance,
        "known_preprocessing_commits": KNOWN_PREPROCESSING_COMMITS,
        "hash_locked_main": wheelhouse_path is not None,
        "hash_locked_aux": bool(aux_locks),
        "built_by": "bremen.release_build.assemble",
    }
    _write_json(provenance_dir / "build.json", build_record)

    # Manifest v1.
    files = [
        _file_ref(
            role="plugin_wheel", relative_path=f"plugin/{wheel.path.name}",
            release_id=spec.release_id, path=wheel.path,
        ),
        _file_ref(
            role="model_artifact",
            relative_path=f"model/{spec.artifact_filename}",
            release_id=spec.release_id, path=local_artifact,
        ),
        _file_ref(
            role="config", relative_path="configs/runtime.json",
            release_id=spec.release_id, path=release_root / "configs" / "runtime.json",
        ),
        _file_ref(
            role="config", relative_path="configs/artifact_manifest.json",
            release_id=spec.release_id, path=release_root / "configs" / "artifact_manifest.json",
        ),
        _file_ref(
            role="requirements_lock", relative_path="requirements/main.lock",
            release_id=spec.release_id, path=main_lock_path,
        ),
        _file_ref(
            role="provenance", relative_path="provenance/build.json",
            release_id=spec.release_id, path=provenance_dir / "build.json",
        ),
    ]
    for tag, lock_name in aux_locks.items():
        files.append(
            _file_ref(
                role="requirements_lock_aux",
                relative_path=f"requirements/{lock_name}",
                release_id=spec.release_id,
                path=release_root / "requirements" / lock_name,
            )
        )
        files.append(
            _file_ref(
                role="provenance",
                relative_path=f"provenance/xrd-preprocessing-{tag}.json",
                release_id=spec.release_id,
                path=provenance_dir / f"xrd-preprocessing-{tag}.json",
            )
        )

    for wheel_path in main_wheels:
        files.append(
            _file_ref(
                role="dependency_wheel",
                relative_path=f"wheelhouse/main/{wheel_path.name}",
                release_id=spec.release_id,
                path=wheel_path,
            )
        )
    for tag, wheels in aux_wheels.items():
        for wheel_path in wheels:
            files.append(
                _file_ref(
                    role="dependency_wheel_aux",
                    relative_path=f"wheelhouse/aux/{tag}/{wheel_path.name}",
                    release_id=spec.release_id,
                    path=wheel_path,
                )
            )

    environments: dict[str, Any] = {
        "main": {
            "requirements_lock_sha256": _sha256_file(main_lock_path),
            "python_version": platform.python_version(),
        }
    }
    for tag, lock_name in aux_locks.items():
        environments[
            f"preprocess_{tag.replace('.', '_').replace('-', '_')}"
        ] = {
            "requirements_lock_sha256": _sha256_file(
                release_root / "requirements" / lock_name
            ),
            "environment_ref": f"@aux/{tag}",
            "preprocessing_release": tag,
        }

    golden_tests = [
        _file_ref(
            role="golden_cases", relative_path="golden_tests/cases.json",
            release_id=spec.release_id,
            path=release_root / "golden_tests" / "cases.json",
        )
    ]
    for fixture_path in golden_copies:
        golden_tests.append(
            _file_ref(
                role="golden_fixture",
                relative_path=str(fixture_path.relative_to(release_root)),
                release_id=spec.release_id,
                path=fixture_path,
            )
        )

    manifest = {
        "schema_version": SCHEMA_ID,
        "release_id": spec.release_id,
        "model": {
            "model_id": spec.model_id,
            "model_version": spec.model_version,
            "workflow_id": spec.workflow_id,
            "artifact_identity": f"sha256:{spec.artifact_checksum}",
        },
        "compatibility": _compatibility(),
        "entrypoint": {
            "module": "bremen.ml_plugin.entrypoint",
            "callable": "main",
        },
        "files": files,
        "environments": environments,
        "scientific_metadata": {
            "preprocessing_release": (
                "none" if spec.preprocessing_release == "none"
                else f"xrd-preprocessing@{spec.preprocessing_release}"
            ),
            "artifact_checksum": spec.artifact_checksum,
            "threshold_source": spec.threshold_source,
            "feature_order_hash": _feature_order_hash(spec),
            "config_hash": _artifact_config_hash(spec, local_artifact),
        },
        "golden_tests": golden_tests,
        "build": {
            "source_repository": repository,
            "commit": commit_value[:40],
            "build_id": f"ir03-{spec.key}-{commit_value[:12]}",
            "provenance_reference": "provenance/build.json",
        },
    }
    validate_release_manifest(manifest)
    manifest_sha = _write_json(release_root / "manifest.json", manifest)

    summary = {
        "schema_version": "bremen.release-build-summary.v1",
        "release_id": spec.release_id,
        "variant": spec.key,
        "manifest_sha256": manifest_sha,
        "plugin_wheel": {
            "filename": wheel.path.name,
            "sha256": wheel.sha256,
            "size_bytes": wheel.size_bytes,
        },
        "artifact_sha256": spec.artifact_checksum,
        "model_id": spec.model_id,
        "model_version": spec.model_version,
        "dependencies": {
            "main": list(main_requirements),
            "aux": {
                tag: record["version"] for tag, record in aux_provenance.items()
            },
        },
        "provenance": aux_provenance,
        "golden_cases": golden["cases"],
        "output_dir": str(release_root),
    }
    _write_json(release_root / "release.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble one IR-03 local Model Release")
    parser.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-root", default=None)
    parser.add_argument("--wheelhouse", default=None)
    parser.add_argument("--fixtures", default=None)
    parser.add_argument(
        "--aux-python", action="append", default=[],
        metavar="RELEASE_TAG=PYTHON",
        help="pinned auxiliary environment interpreter (repeatable)",
    )
    parser.add_argument(
        "--aux-source-commit", action="append", default=[],
        metavar="RELEASE_TAG=COMMIT",
        help=(
            "explicit source commit of the wheelhouse-built preprocessing "
            "wheel (required when the installed wheel has no VCS metadata)"
        ),
    )
    parser.add_argument(
        "--aux-wheelhouse", action="append", default=[],
        metavar="RELEASE_TAG=WHEELHOUSE",
        help=(
            "local wheelhouse holding every wheel of that auxiliary "
            "environment (required to hash-lock it)"
        ),
    )
    parser.add_argument("--commit", default=None)
    parser.add_argument("--source-repository", default=None)
    args = parser.parse_args(argv)

    aux: dict[str, str] = {}
    for item in args.aux_python:
        tag, _, executable = item.partition("=")
        if not tag or not executable:
            parser.error("--aux-python must be RELEASE_TAG=PYTHON")
        aux[tag] = executable
    aux_commits: dict[str, str] = {}
    for item in args.aux_source_commit:
        tag, _, commit_value = item.partition("=")
        if not tag or not commit_value:
            parser.error("--aux-source-commit must be RELEASE_TAG=COMMIT")
        aux_commits[tag] = commit_value
    aux_wheelhouses: dict[str, str] = {}
    for item in args.aux_wheelhouse:
        tag, _, wheelhouse = item.partition("=")
        if not tag or not wheelhouse:
            parser.error("--aux-wheelhouse must be RELEASE_TAG=WHEELHOUSE")
        aux_wheelhouses[tag] = wheelhouse

    summary = assemble_release(
        variant=args.variant,
        artifact_dir=args.artifact_dir,
        output_dir=args.output_dir,
        source_root=args.source_root,
        wheelhouse=args.wheelhouse,
        fixtures_root=args.fixtures,
        aux_environments=aux,
        aux_wheelhouses=aux_wheelhouses,
        aux_source_commits=aux_commits,
        commit=args.commit,
        source_repository=args.source_repository,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
