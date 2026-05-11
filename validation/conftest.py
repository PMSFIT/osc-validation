import pytest


@pytest.hookimpl(optionalhook=True)
def pytest_html_report_title(report):
    report.title = "OSC Validation Report"
