import pytest
import os
import datetime
import pathlib
from osc_validation import __version__ as osc_validation_version
from osc_validation.tools.esmini import ESMini
from osc_validation.tools.gtgen_cli import GTGen_Simulator


def pytest_report_header(config):
    return [
        f"Validation Suite: OSC Validation Suite {osc_validation_version}",
        f"Validation Suite Path: {pathlib.Path(__file__).parent}",
        f"Validated Tool: {config.getoption('--tool')}",
        f"Tool Path: {config.getoption('--toolpath')}",
        f"Validation Run Start Time: {datetime.datetime.now().astimezone().isoformat()}",
    ]


def pytest_addoption(parser):
    group = parser.getgroup("OSC Validation Suite")
    group.addoption(
        "--tool", action="store", default="ESMini", help="Tool to Validate: ESMini, GTGen"
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
    tool_name = request.config.getoption("--tool")

    if tool_name == "ESMini":
        tool = ESMini(request.config.getoption("--toolpath"))
    elif tool_name == "GTGen":
        tool = GTGen_Simulator(request.config.getoption("--toolpath"))
    else:
        tool = None

    if tool:
        yield tool.run
    else:
        raise ValueError("Tool not found")
