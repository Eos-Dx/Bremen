"""IR-07 evidence script: real ReleaseCache.install() for all five rebuilt
IR-07 releases, each exercising every golden case through the real Worker
subprocess with BREMEN_FEATURE_LIBRARY_BACKEND=xrd_inference_features set by
ml_plugin.release.apply_feature_library_backend. install() succeeding proves
_smoke_golden's full expected-result comparison passed for every case using
the external feature backend (release_cache.py: _smoke -> _smoke_golden).

Not a pytest test; manual evidence-collection script. Safe to delete after
capture.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from bremen.platform.models.release_cache import ReleaseCache  # noqa: E402

VARIANTS = ["a1", "a2", "b1", "b2", "b3"]


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, *_args, **_kwargs) -> bytes:
        return self._payload


def main() -> None:
    results = {}
    venv_python = str(ROOT / ".venv" / "bin" / "python")
    for key in VARIANTS:
        release_dir = Path(f"/tmp/ir07/releases/{key}")
        manifest_bytes = (release_dir / "manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        s3_prefix = f"releases/{manifest['release_id']}/"

        class LocalS3:
            def get_object(self, Bucket: str, Key: str):  # noqa: N803
                if Key == "manifest.json":
                    return {"Body": _Body(manifest_bytes)}
                relative = Key[len(s3_prefix):] if Key.startswith(s3_prefix) else Key
                path = release_dir / relative
                if not path.is_file():
                    raise FileNotFoundError(Key)
                return {"Body": _Body(path.read_bytes())}

        class Entry:
            model_id = manifest["model"]["model_id"]
            model_version = manifest["model"]["model_version"]

            @staticmethod
            def get_runtime_release():
                return {
                    "schema_version": "bremen.inference-release.v1",
                    "release_id": manifest["release_id"],
                    "manifest_key": "manifest.json",
                    "manifest_sha256": manifest_sha,
                }

        cache_root = tempfile.mkdtemp(prefix=f"ir07-cache-{key}-")
        cache = ReleaseCache(
            root=cache_root,
            catalog_uri="s3://ir07-bucket/",
            s3_client=LocalS3(),
            python_executable=venv_python,
        )
        try:
            installed = cache.install(Entry())
            results[key] = {
                "status": "READY",
                "release_id": installed.release_id,
                "manifest_sha256": installed.manifest_sha256,
                "feature_library": manifest.get("feature_library"),
            }
            print(f"{key}: READY (all golden cases passed via real Worker + ReleaseCache)")
        except Exception as exc:  # noqa: BLE001 - evidence script, report and continue
            results[key] = {"status": "FAILED", "error": repr(exc)}
            print(f"{key}: FAILED -- {exc!r}")
        finally:
            shutil.rmtree(cache_root, ignore_errors=True)

    print()
    print(json.dumps(results, indent=2))
    out_path = Path(__file__).parent / "_five_release_parity_result.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
