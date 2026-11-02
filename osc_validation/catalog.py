"""Build a static validation catalog with ``python -m osc_validation.catalog``."""

import argparse
import html
import inspect
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

import pytest

from osc_validation import __version__ as osc_validation_version
from osc_validation.versioning import OscVersion


SUITE = Path(__file__).resolve().parent / "validation"


class CatalogCollector:
    """Read final collected items after version and exploratory selection."""

    def __init__(self):
        self.tests = {}

    def pytest_collection_finish(self, session):
        for item in session.items:
            path = Path(item.path).resolve().relative_to(SUITE).as_posix()
            suffix = item.nodeid.split("::", 1)[1]
            name = suffix.rsplit("::", 1)[0] + "::" if "::" in suffix else ""
            name += item.originalname
            key = f"{path}::{name}"
            if key not in self.tests:

                def marker_value(marker_name):
                    marker = item.get_closest_marker(marker_name)
                    return (
                        str(marker.args[0])
                        if marker and marker.args
                        else "Uncategorized"
                    )

                self.tests[key] = {
                    "id": key,
                    "path": path,
                    "line": item.location[1] + 1,
                    "description": inspect.getdoc(item.obj)
                    or "No description provided.",
                    "category": marker_value("validation_category"),
                    "feature": marker_value("validation_feature"),
                    "kind": (
                        "exploratory"
                        if item.get_closest_marker("exploratory")
                        else "conformance"
                    ),
                    "cases": [],
                }
            self.tests[key]["cases"].append(
                {
                    "id": f"{path}::{suffix}",
                    "version": str(item.callspec.params["osc_version"]),
                    "parameters": {
                        name: value if isinstance(value, str) else repr(value)
                        for name, value in item.callspec.params.items()
                        if name != "osc_version"
                    },
                    "parameter_keys": {
                        name: f"{type(value).__module__}.{type(value).__qualname__}:{value!r}"
                        for name, value in item.callspec.params.items()
                        if name != "osc_version"
                    },
                }
            )


def collect_tests():
    collector = CatalogCollector()
    args = [
        str(SUITE),
        "-c",
        str(SUITE / "pytest.ini"),
        "--collect-only",
        "-q",
        "--include-exploratory",
        "-o",
        "addopts=",
        "-p",
        "no:cacheprovider",
    ]
    for version in OscVersion:
        args.extend(["--osc-version", version.value])
    # Environment-specific pytest options must not silently narrow the catalog.
    previous = os.environ.pop("PYTEST_ADDOPTS", None)
    try:
        result = pytest.main(args, plugins=[collector])
    finally:
        if previous is not None:
            os.environ["PYTEST_ADDOPTS"] = previous
    if result != pytest.ExitCode.OK or not collector.tests:
        raise RuntimeError(
            f"Validation collection failed (pytest exit code {int(result)})."
        )
    return sorted(collector.tests.values(), key=lambda test: test["id"])


def source_revision():
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=SUITE.parent.parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def parameter_combinations(cases):
    """Group actual collected combinations, independently of the version axis."""
    combinations = {}
    occurrences = {}
    for case in cases:
        parameters = case.get("parameters", {})
        # Pytest may renumber parameter indices across versions. Match values and
        # their occurrence within each version to preserve duplicate scenarios.
        signature = tuple(sorted(case.get("parameter_keys", parameters).items()))
        occurrence_key = (case["version"], signature)
        occurrence = occurrences.get(occurrence_key, 0)
        occurrences[occurrence_key] = occurrence + 1
        key = (signature, occurrence)
        if key not in combinations:
            combinations[key] = {"parameters": parameters, "cases": []}
        combinations[key]["cases"].append(case)
    return list(combinations.values())


def render_parameter_matrix(combinations):
    escape = html.escape
    names = sorted({name for combo in combinations for name in combo["parameters"]})
    if len(combinations) == 1 and not names:
        return ""
    constants = {
        name: combinations[0]["parameters"][name]
        for name in names
        if all(name in combo["parameters"] for combo in combinations)
        and len({combo["parameters"][name] for combo in combinations}) == 1
    }
    varying = [name for name in names if name not in constants]
    fixed = ""
    if constants:
        fixed = (
            '<p class="parameter-label">Fixed parameters</p><dl class="parameter-constants">'
            + "".join(
                f"<div><dt><code>{escape(name)}</code></dt><dd><code>{escape(value)}</code></dd></div>"
                for name, value in constants.items()
            )
            + "</dl>"
        )
    headers = "".join(
        f'<th scope="col"><code>{escape(name)}</code></th>' for name in varying
    )
    rows = []
    for number, combo in enumerate(combinations, start=1):
        versions = sorted({case["version"] for case in combo["cases"]})
        values = "".join(
            f'<td><code>{escape(combo["parameters"].get(name, "—"))}</code></td>'
            for name in varying
        )
        rows.append(
            f'<tr class="parameter-row" data-versions="{escape(" ".join(versions), quote=True)}">'
            f'<th scope="row" class="combination-index">{number}</th>{values}</tr>'
        )
    return (
        f'<details class="parameter-details"><summary>Parameter combinations (<span class="combination-count">{len(combinations)}</span>)</summary>'
        f'{fixed}<div class="table-scroll" tabindex="0" role="region" aria-label="Parameter combinations">'
        f'<table><thead><tr><th scope="col" class="combination-index">Combination</th>{headers}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></details>'
    )


def render_catalog(tests, repository, revision):
    escape = html.escape
    sections = []
    for index, test in enumerate(tests, start=1):
        combinations = parameter_combinations(test["cases"])
        combination_numbers = {
            case["id"]: number
            for number, combo in enumerate(combinations, start=1)
            for case in combo["cases"]
        }
        versions = sorted({case["version"] for case in test["cases"]})
        title = test["id"].rsplit("::", 1)[-1].removeprefix("test_").replace("_", " ")
        title = title[:1].upper() + title[1:]
        version_badges = "".join(
            f'<span class="version-badge">{escape(v)}</span>' for v in versions
        )
        description = "".join(
            f'<p>{escape(" ".join(paragraph.split()))}</p>'
            for paragraph in re.split(r"\n\s*\n", test["description"].strip())
            if paragraph.strip()
        )
        source = (
            f"{repository.rstrip('/')}/blob/{quote(revision if revision != 'unknown' else 'HEAD', safe='')}/"
            f"osc_validation/validation/{quote(test['path'])}#L{test['line']}"
        )
        case_ids = []
        for case in test["cases"]:
            case_ids.append(
                f'<li data-version="{escape(case["version"], quote=True)}">'
                f'<span class="command-version">Combination {combination_numbers[case["id"]]} · OSC {escape(case["version"])}</span>'
                f'<code>{escape(case["id"])}</code> <button type="button" class="copy">Copy</button></li>'
            )
        sections.append(
            f'<article data-category="{escape(test["category"], quote=True)}" '
            f'data-feature="{escape(test["feature"], quote=True)}" '
            f'data-kind="{test["kind"]}" data-versions="{escape(" ".join(versions), quote=True)}">'
            f'<div class="card-heading"><p class="feature">{escape(test["feature"])}</p>'
            f'<span class="test-index">{index:02d}</span></div>'
            f"<h2>{escape(title)}</h2>"
            f'<p class="badges"><span class="kind {test["kind"]}">{test["kind"]}</span>'
            f'<span class="category-badge">{escape(test["category"].replace("_", " "))}</span></p>'
            f'<div class="description">{description}</div>'
            f'<div class="card-footer"><div class="version-list"><span class="version-label">OpenSCENARIO versions:</span>'
            f'<span class="tooltip"><button type="button" class="tooltip-trigger" aria-label="About OpenSCENARIO versions" aria-describedby="version-help-{index}">?</button>'
            f'<span class="tooltip-text" role="tooltip" id="version-help-{index}">Releases covered by this test’s scenario and expected behavior.</span></span>{version_badges}</div>'
            f'<span class="case-count">{len(combinations)} combinations · {len(test["cases"])} versioned cases</span></div>'
            f'<p class="source"><a href="{escape(source, quote=True)}">{escape(test["id"])}</a></p>'
            f"{render_parameter_matrix(combinations)}"
            f"<details><summary>Test IDs</summary>"
            f'<div class="generic-test-id"><span class="command-version">All parameter combinations</span>'
            f'<code>{escape(test["id"])}</code> <button type="button" class="copy">Copy</button></div>'
            f'<ul>{"".join(case_ids)}</ul></details></article>'
        )

    def options(values):
        return "".join(
            f'<option value="{escape(v, quote=True)}">{escape(v)}</option>'
            for v in sorted(values)
        )

    template = Path(__file__).with_suffix(".html").read_text(encoding="utf-8")
    replacements = {
        "REVISION": escape(revision),
        "PACKAGE_VERSION": escape(osc_validation_version),
        "DEFINITION_COUNT": str(len(tests)),
        "CASE_COUNT": str(sum(len(t["cases"]) for t in tests)),
        "VERSION_COUNT": str(len({c["version"] for t in tests for c in t["cases"]})),
        "FEATURE_COUNT": str(len({t["feature"] for t in tests})),
        "VERSIONS": options({c["version"] for t in tests for c in t["cases"]}),
        "CATEGORIES": options({t["category"] for t in tests}),
        "FEATURES": "".join(
            f'<button type="button" class="filter-badge" data-feature="{escape(feature, quote=True)}" '
            f'aria-pressed="true">{escape(feature)}</button>'
            for feature in sorted({t["feature"] for t in tests})
        ),
        "TESTS": "\n".join(sections),
    }
    # One pass avoids interpreting placeholder-like text in test descriptions.
    return re.sub(r"@@(\w+)@@", lambda match: replacements[match[1]], template)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/_build/catalog"))
    parser.add_argument(
        "--repository", default="https://github.com/PMSFIT/osc-validation"
    )
    parser.add_argument("--revision", default=None, help="Source commit used for links")
    args = parser.parse_args()
    tests = collect_tests()
    page = render_catalog(tests, args.repository, args.revision or source_revision())
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "index.html"
    destination.write_text(page, encoding="utf-8")
    print(f"Wrote {len(tests)} test definitions to {destination}")


if __name__ == "__main__":
    main()
