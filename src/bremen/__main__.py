"""Unified command-line entrypoint for Bremen product workflows.

Bremen — XRD-based ML decision-support workflow foundation.
Not a diagnostic replacement.
"""

from __future__ import annotations

import argparse


BUILTIN_COMMANDS = ("preprocess", "serve", "demo_smoke", "demo_run")
STUB_COMMANDS = ("preflight", "run", "report")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands (no heavy imports)."""
    parser = argparse.ArgumentParser(
        prog="bremen",
        description=(
            "XRD-based ML decision-support workflow foundation. "
            "Not a diagnostic replacement."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Real command: preprocess ---
    _add_preprocess_subcommand(subparsers)

    # --- Stub commands for future workflow stages ---
    _add_stub_command(
        subparsers,
        "preflight",
        "Run safety preflight checks (not yet implemented).",
        "Planned for a future PR.",
    )
    _add_stub_command(
        subparsers,
        "run",
        "Run Bremen analysis workflow (not yet implemented).",
        "Planned for a future PR.",
    )
    _add_stub_command(
        subparsers,
        "report",
        "Generate decision-support report (not yet implemented).",
        "Planned for a future PR.",
    )

    # --- Serve command: HTTP server ---
    _add_serve_subcommand(subparsers)

    # --- Demo smoke command ---
    _add_demo_smoke_subcommand(subparsers)

    # --- Demo run command ---
    _add_demo_run_subcommand(subparsers)

    return parser


def _add_preprocess_subcommand(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Add the 'preprocess' subcommand (imports heavy dependencies lazily)."""
    from pathlib import Path

    preprocess = subparsers.add_parser(
        "preprocess",
        help="Build a Bremen preprocessing DataFrame from a YAML config.",
    )
    preprocess.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to Bremen preprocessing YAML.",
    )
    preprocess.set_defaults(_cmd_handler="preprocess")


def _add_stub_command(
    subparsers: argparse._SubParsersAction,
    name: str,
    help_text: str,
    deferral_note: str,
) -> None:
    """Add a stub subcommand that prints a deferral message."""
    cmd = subparsers.add_parser(name, help=help_text)
    cmd.set_defaults(
        _cmd_handler="stub", _stub_name=name, _stub_note=deferral_note
    )


def _handle_preprocess(args: argparse.Namespace) -> int:
    """Execute the preprocess command (lazy import)."""
    from .pipelines import run_preprocessing_from_config  # noqa: PLC0415

    df = run_preprocessing_from_config(args.config)
    print(f"rows={len(df)}")
    print(f"columns={len(df.columns)}")
    print(f"config={args.config}")
    return 0


def _handle_stub(args: argparse.Namespace) -> int:
    """Print a deferral message for stub commands."""
    print(f"'{args._stub_name}' is not yet implemented.")
    print(args._stub_note)
    return 1


def main(argv: list[str] | None = None) -> int:
    from .logging_config import configure_logging, get_logger  # noqa: PLC0415

    configure_logging()
    _log = get_logger(__name__)
    _log.info("bremen.startup.begin\tstage=startup\tstatus=started")

    import sys
    parser = build_parser()
    if argv is None and len(sys.argv) == 1:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler = getattr(args, "_cmd_handler", None)
    if handler == "preprocess":
        return _handle_preprocess(args)
    if handler == "serve":
        return _handle_serve(args)
    if handler == "demo_smoke":
        return _handle_demo_smoke(args)
    if handler == "demo_run":
        return _handle_demo_run(args)
    if handler == "stub":
        return _handle_stub(args)

    parser.print_help()
    return 0


def _add_serve_subcommand(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Add the 'serve' subcommand (lazy import of http.server)."""
    serve = subparsers.add_parser(
        "serve",
        help="Start the Bremen HTTP API server (dev/smoke mode).",
    )
    serve.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1).",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number to listen on (default: 8000).",
    )
    serve.set_defaults(_cmd_handler="serve")


def _handle_serve(args: argparse.Namespace) -> int:
    """Start the Bremen HTTP API server (blocking, dev/smoke mode)."""
    from .api.server import run_server  # noqa: PLC0415
    from .logging_config import get_logger  # noqa: PLC0415

    _log = get_logger(__name__)
    _log.info(
        "bremen.cli.serve.dispatch\t"
        "stage=startup\tstatus=started\t"
        "host=%s\tport=%s",
        args.host, args.port,
    )

    print(f"Starting Bremen API server at http://{args.host}:{args.port}")
    print("Dev/smoke mode only. Not for production use.")
    run_server(host=args.host, port=args.port)
    return 0


def _add_demo_smoke_subcommand(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Add the 'demo-smoke' subcommand (no heavy imports)."""
    demo = subparsers.add_parser(
        "demo-smoke",
        help="Run production demo smoke checks against a running Bremen service.",
    )
    demo.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="Base URL of the Bremen HTTP service (default: http://127.0.0.1:8000).",
    )
    demo.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30).",
    )
    demo.add_argument(
        "--skip-prediction",
        action="store_true",
        help="Skip the prediction check.",
    )
    demo.set_defaults(_cmd_handler="demo_smoke")


def _handle_demo_smoke(args: argparse.Namespace) -> int:
    """Run the demo smoke checks against a running Bremen service."""
    from .demo_smoke import main as demo_main  # noqa: PLC0415

    cli_args = [
        f"--base-url={args.base_url}",
        f"--timeout={args.timeout}",
    ]
    if args.skip_prediction:
        cli_args.append("--skip-prediction")

    return demo_main(cli_args)

def _add_demo_run_subcommand(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Add the 'demo-run' subcommand (no heavy imports)."""
    demo_run = subparsers.add_parser(
        "demo-run",
        help=(
            "One-command demo: start local server, run smoke checks, "
            "produce evidence bundle."
        ),
    )
    demo_run.add_argument(
        "--base-url",
        type=str,
        default=None,
        help=(
            "Base URL of an already-running Bremen service. "
            "If not provided, starts a local server."
        ),
    )
    demo_run.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds (default: 30).",
    )
    demo_run.add_argument(
        "--skip-prediction",
        action="store_true",
        help="Skip the prediction check.",
    )
    demo_run.add_argument(
        "--pretty",
        action="store_true",
        help="Print a formatted plain-text presentation summary.",
    )
    demo_run.set_defaults(_cmd_handler="demo_run")


def _handle_demo_run(args: argparse.Namespace) -> int:
    """Run the one-command demo."""
    from .demo_run import main as demo_run_main  # noqa: PLC0415

    cli_args = [f"--timeout={args.timeout}"]
    if args.base_url:
        cli_args.append(f"--base-url={args.base_url}")
    if args.skip_prediction:
        cli_args.append("--skip-prediction")
    if args.pretty:
        cli_args.append("--pretty")
    return demo_run_main(cli_args)


if __name__ == "__main__":
    raise SystemExit(main())
