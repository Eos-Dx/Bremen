"""FastAPI release readiness checks.

Verifies that the project is ready for FastAPI as the default runtime
without starting any servers or making any network calls.

Run from the project root::

    python scripts/check_fastapi_release_readiness.py

Exits 0 if all checks pass, 1 if any check fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
MAIN_MODULE = ROOT / "src" / "bremen" / "__main__.py"
FASTAPI_SERVER = ROOT / "src" / "bremen" / "api" / "fastapi_server.py"
GUARD_FILE = ROOT / "tests" / "test_bremen_no_server_spawning_tests.py"

errors: list[str] = []


def check(description: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    msg = f"  [{status}] {description}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    if not ok:
        errors.append(description)


def main() -> int:
    print("FastAPI release readiness checks")
    print("=" * 40)

    # 1. Default backend resolves to fastapi
    from bremen.__main__ import resolve_backend

    check(
        "Default backend is fastapi",
        resolve_backend(None, None) == "fastapi",
        f"got {resolve_backend(None, None)!r}",
    )

    # 2. --backend http still available
    check(
        "--backend http resolves to http",
        resolve_backend("http", None) == "http",
    )

    # 3. --backend fastapi works
    check(
        "--backend fastapi resolves to fastapi",
        resolve_backend("fastapi", None) == "fastapi",
    )

    # 4. serve-fastapi command exists in parser
    from bremen.__main__ import build_parser

    parser = build_parser()
    args = parser.parse_args(["serve-fastapi"])
    check(
        "serve-fastapi command exists",
        args.command == "serve-fastapi" and args._cmd_handler == "serve_fastapi",
    )

    # 5. FastAPI factory target
    from bremen.api.fastapi_server import _FACTORY_TARGET

    check(
        "FastAPI factory target is correct",
        _FACTORY_TARGET == "bremen.api.fastapi_app:create_fastapi_app",
        f"got {_FACTORY_TARGET!r}",
    )

    # 6. Dockerfile/ENTRYPOINT/CMD do not force legacy backend
    if DOCKERFILE.exists():
        docker_content = DOCKERFILE.read_text(encoding="utf-8")
        lines = docker_content.splitlines()
        entrypoint_line = ""
        cmd_line = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("ENTRYPOINT "):
                entrypoint_line = stripped
            elif stripped.startswith("CMD "):
                cmd_line = stripped

        # The Dockerfile should use "serve" without explicit --backend http
        docker_ok = "--backend" not in cmd_line or "--backend" not in docker_content.split("ENTRYPOINT")[0] if "ENTRYPOINT" in docker_content else True
        # Simpler check: CMD should not force --backend http
        no_legacy_override = "serve" in cmd_line and "--backend http" not in cmd_line
        check(
            "Dockerfile does not force legacy backend",
            no_legacy_override,
            f"CMD: {cmd_line!r}",
        )
    else:
        check("Dockerfile does not force legacy backend", True, "no Dockerfile (skipped)")

    # 7. Zero-server guard file exists
    check(
        "Zero-server guard test file exists",
        GUARD_FILE.exists(),
        str(GUARD_FILE),
    )

    # 8. Legacy http.server fallback still importable
    from bremen.api.server import run_server as _legacy_rs

    check("Legacy run_server is importable", callable(_legacy_rs))

    # 9. FastAPI run_fastapi_server still importable
    from bremen.api.fastapi_server import run_fastapi_server as _fastapi_rs

    check("FastAPI run_fastapi_server is importable", callable(_fastapi_rs))

    # 10. --backend http parser still works
    args_http = parser.parse_args(["serve", "--backend", "http"])
    check(
        "serve --backend http parser works",
        args_http.command == "serve" and args_http.backend == "http",
    )

    # 11. serve parser default backend is None (resolves to fastapi)
    args_default = parser.parse_args(["serve"])
    check(
        "serve default --backend is None (resolves to fastapi)",
        args_default.backend is None,
        f"got {args_default.backend!r}",
    )

    print("=" * 40)
    if errors:
        print(f"FAILED: {len(errors)} check(s) failed")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
