"""Exercise the real collector and the generated commands without an engine."""

import os
from pathlib import Path
import subprocess
import sys

from lxml import html

from osc_validation.catalog import (
    parameter_combinations,
    render_catalog,
    render_parameter_matrix,
)


ROOT = Path(__file__).resolve().parents[1]


def test_catalog_collects_all_versions_and_generates_copyable_test_ids(tmp_path):
    output = tmp_path / "catalog"
    env = {**os.environ, "PYTEST_ADDOPTS": "-k no_such_test"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "osc_validation.catalog",
            "--output",
            str(output),
            "--revision",
            "abc123",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    page = html.fromstring((output / "index.html").read_text(encoding="utf-8"))
    articles = page.xpath("//article")
    assert articles
    assert all(a.xpath(".//li") for a in articles)
    assert {li.get("data-version") for li in page.xpath("//li")} == {
        "1.3.0",
        "1.3.1",
        "1.4.0",
    }
    assert len({a.xpath(".//a/text()")[0] for a in articles}) == len(articles)
    assert all("/blob/abc123/" in a.get("href") for a in page.xpath("//article//a"))
    dimensions = next(
        a
        for a in articles
        if "test_vehicle_dimensions_match_reference" in a.xpath(".//a/text()")[0]
    )
    rows = dimensions.xpath('.//tr[@class="parameter-row"]')
    assert len(rows) == 2  # Two object IDs, each expanded over three versions.
    assert [row.xpath("./td/code/text()") for row in rows] == [["1"], ["2"]]
    assert all(row.get("data-versions") == "1.3.0 1.3.1 1.4.0" for row in rows)
    assert dimensions.xpath('.//dl[@class="parameter-constants"]//dt/code/text()') == [
        "osi_trace"
    ]
    assert "osc_version" not in dimensions.xpath(".//table//th/code/text()")
    assert [
        header.text_content() for header in dimensions.xpath(".//table/thead//th")
    ] == ["Combination", "moving_object_id"]
    teleport = next(
        a
        for a in articles
        if "test_follow_trajectory_position_mode_teleports_to_current_trajectory_time"
        in a.xpath(".//a/text()")[0]
    )
    assert [
        row.xpath("./td/code/text()")
        for row in teleport.xpath('.//tr[@class="parameter-row"]')
    ] == [
        ["2.0", "exact_trajectory_point"],
        ["1.0", "between_trajectory_points"],
    ]  # Paired parameters produce two combinations, not a Cartesian product of four.
    exploratory = page.xpath('//article[@data-kind="exploratory"]')
    assert exploratory
    generic_id = dimensions.xpath('.//div[@class="generic-test-id"]/code/text()')[0]
    assert generic_id == dimensions.xpath(".//a/text()")[0]
    assert "[" not in generic_id
    # IDs remain relative to the validation suite, as collected by pytest and
    # accepted in test profiles. An exact ID must recollect exactly one case.
    item = exploratory[0].xpath(".//li")[0]
    test_id = item.xpath("./code/text()")[0]
    assert test_id.startswith("scenario/")
    check = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "osc_validation/validation/" + test_id,
            "--osc-version",
            item.get("data-version"),
            "--include-exploratory",
            "--collect-only",
            "-q",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        text=True,
        capture_output=True,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert "1 test collected" in check.stdout
    generic_check = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "osc_validation/validation/" + generic_id,
            "--collect-only",
            "-q",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        text=True,
        capture_output=True,
    )
    assert generic_check.returncode == 0, generic_check.stdout + generic_check.stderr
    assert "2 tests collected" in generic_check.stdout


def test_catalog_escapes_metadata_and_ids():
    test = {
        "id": "scenario/val_demo.py::test_demo",
        "path": "scenario/val_demo.py",
        "line": 12,
        "description": '<script>alert("unsafe")</script>\n@@TOTAL@@\r\n  \r\nSecond\nparagraph.',
        "category": 'category"<&',
        "feature": "<feature>",
        "kind": "conformance",
        "cases": [{"id": "scenario/val_demo.py::test_demo[a&b]", "version": "1.4.0"}],
    }
    page = html.fromstring(
        render_catalog([test], "https://github.com/example/repo", "abc")
    )
    assert page.xpath('//div[@class="description"]/p/text()') == [
        '<script>alert("unsafe")</script> @@TOTAL@@',
        "Second paragraph.",
    ]
    assert not page.xpath("//article//script")
    assert page.xpath("//article/@data-category") == [test["category"]]
    assert "a&b" in page.xpath("//li/code/text()")[0]


def test_parameter_matrix_preserves_sparse_versions_and_duplicate_values():
    cases = [
        {
            "parameters": {"mode": "same label"},
            "version": "1.3.1",
        },
        {
            "parameters": {"mode": "same label"},
            "version": "1.4.0",
        },
        {
            "parameters": {"mode": "same label"},
            "version": "1.4.0",
        },
    ]
    page = html.fromstring(render_parameter_matrix(parameter_combinations(cases)))
    rows = page.xpath('.//tr[@class="parameter-row"]')
    assert [row.get("data-versions") for row in rows] == ["1.3.1 1.4.0", "1.4.0"]
    assert page.xpath('.//dl[@class="parameter-constants"]//dd/code/text()') == [
        "same label"
    ]
