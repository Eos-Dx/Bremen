"""IR-07 evidence script: real ReleaseCache.install() of a rebuilt b2 release,
proving the feature-library wheel installs into the release-owned venv and
that the Worker imports xrd_inference_features from THAT venv, not the repo
checkout / parent interpreter / system site-packages.

Not a pytest test (kept out of tests/ deliberately: it shells real pip/venv
and depends on local /tmp build evidence from this session) -- run manually
during IR-07 evidence collection. Safe to delete after evidence capture.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from bremen.platform.models.release_cache import ReleaseCache  # noqa: E402

RELEASE_DIR = Path("/tmp/ir07/releases/b2")
MANIFEST = json.loads((RELEASE_DIR / "manifest.json").read_text())
MANIFEST_BYTES = (RELEASE_DIR / "manifest.json").read_bytes()
MANIFEST_SHA = hashlib.sha256(MANIFEST_BYTES).hexdigest()


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, *_args, **_kwargs) -> bytes:
        return self._payload


_S3_PREFIX = f"releases/{MANIFEST['release_id']}/"


class LocalS3:
    """Serves get_object(Bucket, Key) from the real built release directory."""

    def __init__(self, release_dir: Path) -> None:
        self.release_dir = release_dir

    def get_object(self, Bucket: str, Key: str):  # noqa: N803
        if Key == "manifest.json":
            return {"Body": _Body(MANIFEST_BYTES)}
        relative = Key[len(_S3_PREFIX):] if Key.startswith(_S3_PREFIX) else Key
        path = self.release_dir / relative
        if not path.is_file():
            raise FileNotFoundError(Key)
        return {"Body": _Body(path.read_bytes())}


class Entry:
    model_id = MANIFEST["model"]["model_id"]
    model_version = MANIFEST["model"]["model_version"]

    @staticmethod
    def get_runtime_release():
        return {
            "schema_version": "bremen.inference-release.v1",
            "release_id": MANIFEST["release_id"],
            "manifest_key": "manifest.json",
            "manifest_sha256": MANIFEST_SHA,
        }


def main() -> None:
    cache_root = tempfile.mkdtemp(prefix="ir07-cache-")
    venv_python = str(ROOT / ".venv" / "bin" / "python")
    cache = ReleaseCache(
        root=cache_root,
        catalog_uri="s3://ir07-bucket/",
        s3_client=LocalS3(RELEASE_DIR),
        python_executable=venv_python,
    )
    installed = cache.install(Entry())
    print("INSTALLED:", installed)

    digest = MANIFEST_SHA
    main_env_python = Path(cache_root) / digest / "env" / "bin" / "python"
    assert main_env_python.is_file(), f"missing {main_env_python}"

    proof = subprocess.run(
        [
            str(main_env_python), "-c",
            "import xrd_inference_features, json, pathlib;"
            "print(json.dumps({'file': str(pathlib.Path(xrd_inference_features.__file__).resolve())}))",
        ],
        capture_output=True, text=True, check=False,
    )
    print("WORKER IMPORT STDOUT:", proof.stdout.strip())
    print("WORKER IMPORT STDERR:", proof.stderr.strip())
    assert proof.returncode == 0
    resolved = json.loads(proof.stdout.strip())["file"]
    resolved_path = Path(resolved)
    assert str(resolved_path).startswith(str((Path(cache_root) / digest).resolve())), (
        f"xrd_inference_features resolved OUTSIDE the release env: {resolved_path}"
    )
    assert "site-packages" in str(resolved_path)
    print("PROOF OK: xrd_inference_features resolves inside the release-owned venv:")
    print(" ", resolved_path)

    shutil.rmtree(cache_root, ignore_errors=True)


if __name__ == "__main__":
    main()
