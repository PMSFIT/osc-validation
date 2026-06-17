import html
import inspect

import pytest

pytest_plugins = ["osc_validation.pytest_plugin"]


@pytest.hookimpl(optionalhook=True)
def pytest_html_report_title(report):
    report.title = "OSC Validation Report"


def _marker_value(item: pytest.Item, marker_name: str) -> str:
    marker = item.get_closest_marker(marker_name)
    if marker is None or not marker.args:
        return ""
    return str(marker.args[0])


def _test_description(item: pytest.Item) -> str:
    test_object = getattr(item, "obj", None)
    if test_object is None:
        return ""
    return inspect.getdoc(test_object) or ""


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    report.validation_category = _marker_value(item, "validation_category")
    report.validation_feature = _marker_value(item, "validation_feature")

    description = _test_description(item)

    pytest_html = item.config.pluginmanager.getplugin("html")
    if pytest_html is None:
        return

    extras = getattr(report, "extras", [])
    tmp_path = item.funcargs.get("tmp_path")
    if tmp_path is not None:
        resolved_tmp_path = tmp_path.resolve()
        escaped_tmp_path = html.escape(str(resolved_tmp_path))
        escaped_tmp_path_uri = html.escape(resolved_tmp_path.as_uri(), quote=True)
        extras.append(
            pytest_html.extras.html(
                "<div><strong>Pytest temp directory</strong><br>"
                f'<a href="{escaped_tmp_path_uri}">{escaped_tmp_path}</a></div>'
            )
        )

    if description:
        escaped_description = html.escape(description).replace("\n", "<br>")
        extras.append(
            pytest_html.extras.html(
                f"<div><strong>Validation description</strong><br>{escaped_description}</div>"
            )
        )
    report.extras = extras


@pytest.hookimpl(optionalhook=True)
def pytest_html_results_table_header(cells):
    cells.insert(2, "<th>Validation Category</th>")
    cells.insert(3, "<th>OpenSCENARIO Feature</th>")


@pytest.hookimpl(optionalhook=True)
def pytest_html_results_table_row(report, cells):
    category = html.escape(getattr(report, "validation_category", ""))
    feature = html.escape(getattr(report, "validation_feature", ""))
    cells.insert(2, f"<td>{category}</td>")
    cells.insert(3, f"<td>{feature}</td>")
