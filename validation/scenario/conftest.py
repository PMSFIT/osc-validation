import pytest
import datetime
import pathlib

from osc_validation import __version__ as osc_validation_version
from osc_validation.tools.esmini import ESMini
from osc_validation.tools.gtgen_cli import GTGen_Simulator


class UnknownToolError(ValueError):
    pass


def _make_tool(config):
    tool_name = config.getoption("--tool")
    toolpath = config.getoption("--toolpath")

    if tool_name == "ESMini":
        return ESMini(toolpath)
    elif tool_name == "GTGen":
        return GTGen_Simulator(toolpath)
    raise UnknownToolError(f"Unknown tool: {tool_name}")


def pytest_configure(config):
    try:
        tool = _make_tool(config)
    except (UnknownToolError, FileNotFoundError) as exc:
        raise pytest.UsageError(str(exc)) from exc
    config._osc_tool = tool
    config._osc_tool_version = tool.get_version()
    config._osc_validation_run_start_time = datetime.datetime.now().astimezone()

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
    metadata = _validation_metadata(config)
    return [
        f"{key}: {value}"
        for key, value in metadata.items()
    ]


def pytest_html_report_title(report):
    report.title = "OSC Validation Report"


def pytest_addoption(parser):
    group = parser.getgroup("OSC Validation Suite")
    group.addoption(
        "--tool",
        action="store",
        default="ESMini",
        help="Tool to Validate: ESMini, GTGen",
    )
    group.addoption(
        "--toolpath",
        action="store",
        default=None,
        help="Path to the tool to validate",
    )


@pytest.fixture(scope="session")
def generate_tool_trace(request):
    """
    Yields the run method of the initialized tool specified by the pytest
    options ``--tool`` and ``--toolpath``.
    The run method returns the path to the tool-generated OSI trace file.
    """
    yield request.config._osc_tool.run
