"""
Pytest plugin for the OSC Validation Suite.

Loaded by the packaged validation suite and by the ``osc-validate`` wrapper so
that OSC Validation Suite options, hooks, and fixtures are available only for
validation runs.

Responsibilities
----------------
* Register CLI options (``--tool``, ``--toolpath``, ``--test-profile``).
* Initialise the tool under test and expose it via the ``generate_tool_trace``
  session fixture.
* Apply xfail markers from an optional test-profile file.
* Add validation metadata to the pytest report header.

Presentation hooks that are specific to the built-in validation suite (e.g.
``pytest_html_report_title``) live in
``osc_validation/validation/scenario/conftest.py`` where conftest scoping
keeps them from affecting unrelated pytest sessions.
"""

import datetime
import pathlib

import pytest

from osc_validation import __version__ as osc_validation_version
from osc_validation.test_profile import load_test_profile
from osc_validation.tools.esmini import ESMini
from osc_validation.tools.gtgen_cli import GTGen_Simulator
from osc_validation.tools.osc_simulator import OscSimulator


class UnknownToolError(ValueError):
    pass


def _make_tool(config):
    tool_name = config.getoption("--tool")
    toolpath = config.getoption("--toolpath")

    if tool_name == "ESMini":
        return ESMini(toolpath)
    elif tool_name == "GTGen":
        return GTGen_Simulator(toolpath)
    elif tool_name == "OscSimulator":
        return OscSimulator(toolpath)
    raise UnknownToolError(f"Unknown tool: {tool_name}")


def pytest_addoption(parser):
    group = parser.getgroup("OSC Validation Suite")
    group.addoption(
        "--tool",
        action="store",
        help="Tool to Validate: ESMini, GTGen, OscSimulator",
    )
    group.addoption(
        "--toolpath",
        action="store",
        default=None,
        metavar="PATH",
        help="Path to the tool to validate",
    )
    group.addoption(
        "--test-profile",
        action="store",
        default=None,
        metavar="PATH",
        help="Path to a TOML test profile file declaring expected failures for this run",
    )


def pytest_configure(config):
    """Register markers and initialise the tool when ``--tool`` is provided."""
    config.addinivalue_line(
        "markers", "trajectory: trajectory-specific tests"
    )
    config.addinivalue_line(
        "markers",
        "xfail_from_profile: xfail mark applied via --test-profile config",
    )

    config._osc_validation_run_start_time = datetime.datetime.now().astimezone()
    config._osc_tool = None
    config._osc_tool_version = None
    config._osc_test_profile = None

    tool_name = config.getoption("--tool")
    if tool_name is None or config.option.collectonly:
        return

    try:
        tool = _make_tool(config)
    except (UnknownToolError, FileNotFoundError) as exc:
        raise pytest.UsageError(str(exc)) from exc
    config._osc_tool = tool
    config._osc_tool_version = tool.get_version()

    profile_path = config.getoption("--test-profile")
    if profile_path is not None:
        try:
            config._osc_test_profile = load_test_profile(profile_path)
        except (FileNotFoundError, ValueError) as exc:
            raise pytest.UsageError(str(exc)) from exc

    metadata_key = _get_pytest_metadata_key()
    if metadata_key is not None:
        metadata = config.stash[metadata_key]
        for key, value in _validation_metadata(config).items():
            metadata[key] = value


def _get_pytest_metadata_key():
    try:
        from pytest_metadata.plugin import metadata_key
    except ImportError:
        return None
    return metadata_key


def _validation_metadata(config):
    tool = getattr(config, "_osc_tool", None)
    resolved_tool_path = getattr(tool, "tool_path", config.getoption("--toolpath"))
    run_start_time = getattr(
        config,
        "_osc_validation_run_start_time",
        datetime.datetime.now().astimezone(),
    )
    return {
        "Validation Suite": f"OSC Validation Suite {osc_validation_version}",
        "Validation Suite Path": str(pathlib.Path(__file__).parent),
        "Validated Tool": config.getoption("--tool"),
        "Tool Path": str(resolved_tool_path),
        "Tool Version": getattr(config, "_osc_tool_version", "unknown version"),
        "Validation Run Start Time": run_start_time.isoformat(),
    }


def pytest_report_header(config):
    if getattr(config, "_osc_tool", None) is None:
        return
    metadata = _validation_metadata(config)
    return [f"{key}: {value}" for key, value in metadata.items()]


def pytest_collection_modifyitems(config, items):
    profile = getattr(config, "_osc_test_profile", None)
    if profile is None:
        return
    for item in items:
        entry = profile.xfail_for(item.nodeid)
        if entry is not None:
            marker = pytest.mark.xfail(
                reason=entry.reason,
                strict=entry.strict,
            )
            item.add_marker(marker, append=False)


@pytest.fixture(scope="session")
def generate_tool_trace(request):
    """
    Yields the run method of the initialized tool specified by the pytest
    options ``--tool`` and ``--toolpath``.
    The run method returns the path to the tool-generated OSI trace file.
    """
    tool = request.config._osc_tool
    if tool is None:
        pytest.fail(
            "No tool configured. Pass --tool (and optionally --toolpath) "
            "to specify the tool under test."
        )
    yield tool.run
