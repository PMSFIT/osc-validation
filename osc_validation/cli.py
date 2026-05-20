"""Command line wrapper for running the installed validation suite."""

import argparse
from pathlib import Path
import subprocess
import sys


def _validation_dir() -> Path:
    return Path(__file__).resolve().parent / "validation"


def _resolve_from_cwd(path: str) -> str:
    return str(Path(path).resolve())


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="osc-validate",
        description="Run the installed OSC validation suite.",
    )
    parser.add_argument(
        "--tool",
        required=True,
        choices=["ESMini", "GTGen", "OscSimulator"],
        help="Tool to validate.",
    )
    parser.add_argument(
        "--toolpath",
        default=None,
        help="Path to the tool executable. If omitted, the tool is resolved from PATH.",
    )
    parser.add_argument(
        "--test-profile",
        default=None,
        help="Path to a TOML test profile file declaring expected failures.",
    )
    parser.add_argument(
        "--html",
        default=None,
        metavar="PATH",
        help="Write a self-contained pytest-html report to PATH.",
    )
    return parser.parse_args(argv)


def _pytest_args(args: argparse.Namespace, validation_dir: Path) -> list[str]:
    pytest_args = [
        f"--rootdir={validation_dir}",
        f"--config-file={validation_dir / 'pytest.ini'}",
        "--import-mode=importlib",
        str(validation_dir),
        "--tool",
        args.tool,
    ]

    if args.toolpath is not None:
        pytest_args.extend(["--toolpath", _resolve_from_cwd(args.toolpath)])
    if args.test_profile is not None:
        pytest_args.extend(["--test-profile", _resolve_from_cwd(args.test_profile)])
    if args.html is not None:
        pytest_args.extend(
            [f"--html={_resolve_from_cwd(args.html)}", "--self-contained-html"]
        )

    return pytest_args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    validation_dir = _validation_dir()
    if not (validation_dir / "pytest.ini").exists() or not (
        validation_dir / "scenario"
    ).exists():
        raise FileNotFoundError(
            "Installed validation suite not found at "
            f"'{validation_dir}'. "
            "Install osc-validation from a built wheel/sdist, or place the "
            "validation suite inside the osc_validation package."
        )
    command = [sys.executable, "-m", "pytest", *_pytest_args(args, validation_dir)]
    return subprocess.run(command, check=False, cwd=validation_dir).returncode


if __name__ == "__main__":
    sys.exit(main())
