import pytest
import os
import datetime
import pathlib
from osc_validation import __version__ as osc_validation_version
from osc_validation.tools.esmini import ESMini


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
        "--tool", action="store", default="ESMini", help="Tool to Validate: ESMini"
    )
    group.addoption(
        "--toolpath",
        action="store",
        default=None,
        help="Path to the tool to validate",
    )


@pytest.fixture(scope="session")
def generate_tool_trace(request):
    tool = (
        ESMini(request.config.getoption("--toolpath"))
        if request.config.getoption("--tool") == "ESMini"
        else None
    )

    if tool:
        yield tool.run
    else:
        raise ValueError("Tool not found")
