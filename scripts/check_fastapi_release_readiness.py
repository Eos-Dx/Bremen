"""FastAPI release readiness checks.

Verifies that the project is ready for FastAPI as the default runtime
without starting any servers or making any network calls.

Run from the project root::

    python scripts/check_fastapi_release_readiness.py

Exits 0 if all checks pass, 1 if any check fails.
"""

from __future__ import annotations

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

    # 1. The single serve command is FastAPI/ASGI.
    from bremen.__main__ import build_parser

    parser = build_parser()
    args = parser.parse_args(["serve"])
    check(
        "serve command exists and has no backend selector",
        args.command == "serve" and args._cmd_handler == "serve" and not hasattr(args, "backend"),
    )

    # 5. FastAPI factory target
    from bremen.api.fastapi_server import _FACTORY_TARGET

    check(
        "FastAPI factory target is correct",
        _FACTORY_TARGET == "bremen.api.http.app:create_app",
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

    # 8. FastAPI run_fastapi_server remains importable
    from bremen.api.fastapi_server import run_fastapi_server as _fastapi_rs

    check("FastAPI run_fastapi_server is importable", callable(_fastapi_rs))

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
