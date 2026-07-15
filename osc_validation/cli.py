"""Command line wrapper for running the installed validation suite."""

import argparse
from pathlib import Path
import subprocess
import sys


def _validation_dir() -> Path:
    return Path(__file__).resolve().parent / "validation"


def _resolve_from_cwd(path: str) -> str:
    return str(Path(path).resolve())


def _resolve_wrapper_module(value: str) -> str:
    wrapper_path = Path(value)
    if wrapper_path.suffix == ".py" or wrapper_path.exists():
        return _resolve_from_cwd(value)
    return value


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="osc-validate",
        description="Run the installed OSC validation suite.",
    )
    parser.add_argument(
        "--tool",
        required=True,
        metavar="TOOL",
        help=(
            "Tool to validate. Built-in tools: ESMini, GTGen, OscSimulator. "
            "Other tools require --tool-wrapper-module."
        ),
    )
    parser.add_argument(
        "--tool-wrapper-module",
        default=None,
        metavar="MODULE_OR_PATH",
        help=(
            "Python module name or .py file path providing "
            "create_tool(toolpath) for a custom tool wrapper."
        ),
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
    parser.add_argument(
        "--junitxml",
        default=None,
        metavar="PATH",
        help="Write a JUnit XML report to PATH.",
    )
    parser.add_argument(
        "--assert-osi-compliance",
        action="store_true",
        default=False,
        help="Enable OSI compliance assertions at test case call sites.",
    )
    parser.add_argument(
        "--assert-osi-compliance-version",
        default=None,
        metavar="VERSION",
        help="Default OSI version for OSI compliance assertions.",
    )
    ruleset_group = parser.add_mutually_exclusive_group()
    ruleset_group.add_argument(
        "--assert-osi-compliance-ruleset",
        default=None,
        metavar="PATH",
        help="Default OSI ruleset YAML file for OSI compliance assertions.",
    )
    ruleset_group.add_argument(
        "--assert-osi-compliance-ruleset-preset",
        choices=["omega-prime"],
        default=None,
        metavar="PRESET",
        help="Use a named OSI ruleset preset for OSI compliance assertions.",
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
    if args.tool_wrapper_module is not None:
        pytest_args.extend(
            ["--tool-wrapper-module", _resolve_wrapper_module(args.tool_wrapper_module)]
        )
    if args.test_profile is not None:
        pytest_args.extend(["--test-profile", _resolve_from_cwd(args.test_profile)])
    if args.html is not None:
        pytest_args.extend(
            [f"--html={_resolve_from_cwd(args.html)}", "--self-contained-html"]
        )
    if args.junitxml is not None:
        pytest_args.append(f"--junitxml={_resolve_from_cwd(args.junitxml)}")
    if args.assert_osi_compliance:
        pytest_args.append("--assert-osi-compliance")
    if args.assert_osi_compliance_version is not None:
        pytest_args.extend(
            ["--assert-osi-compliance-version", args.assert_osi_compliance_version]
        )
    if args.assert_osi_compliance_ruleset is not None:
        pytest_args.extend(
            [
                "--assert-osi-compliance-ruleset",
                _resolve_from_cwd(args.assert_osi_compliance_ruleset),
            ]
        )
    if args.assert_osi_compliance_ruleset_preset is not None:
        pytest_args.extend(
            [
                "--assert-osi-compliance-ruleset-preset",
                args.assert_osi_compliance_ruleset_preset,
            ]
        )

    return pytest_args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    validation_dir = _validation_dir()
    if (
        not (validation_dir / "pytest.ini").exists()
        or not (validation_dir / "scenario").exists()
    ):
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
