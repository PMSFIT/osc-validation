import pytest

pytest_plugins = ["osc_validation.pytest_plugin"]


@pytest.hookimpl(optionalhook=True)
def pytest_html_report_title(report):
    report.title = "OSC Validation Report"
