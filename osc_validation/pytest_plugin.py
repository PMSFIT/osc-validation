"""
Pytest plugin for the OSC Validation Suite.

Loaded by the packaged validation suite and by the ``osc-validate`` wrapper so
that OSC Validation Suite options, hooks, and fixtures are available only for
validation runs.

Responsibilities
----------------
* Register CLI options (``--tool``, ``--toolpath``,
  ``--tool-wrapper-module``, ``--test-profile``).
* Initialise the tool under test and expose it via the ``generate_tool_trace``
  session fixture.
* Expose optional OSI compliance assertions via the
  ``assert_osi_compliance`` session fixture.
* Apply xfail markers from an optional test-profile file.
* Add validation metadata to the pytest report header.

Presentation hooks that are specific to the built-in validation suite (e.g.
``pytest_html_report_title``) live in
``osc_validation/validation/scenario/conftest.py`` where conftest scoping
keeps them from affecting unrelated pytest sessions.
"""

import datetime
import functools
import importlib
import importlib.util
import pathlib
from urllib.parse import urlparse
import sys
import uuid

import pytest
from lxml import etree

from osc_validation import __version__ as osc_validation_version
from osc_validation.assertions import make_assert_osi_compliance
from osc_validation.dataproviders import DownloadDataProvider
from osc_validation.test_profile import load_test_profile
from osc_validation.tools.esmini import ESMini
from osc_validation.tools.gtgen_cli import GTGen_Simulator
from osc_validation.tools.osc_simulator import OscSimulator
from osc_validation.versioning import OscVersion, ScenarioContract

OMEGA_PRIME_OSI_370_RULESET_URL = "https://raw.githubusercontent.com/thomassedlmayer/omega-prime/7ed09192ffeaa12bfab04281d17a5b5dc2702197/docs/osirules/omega-prime-osi_3-7-0.yml"


class UnknownToolError(ValueError):
    pass


class ToolWrapperError(ValueError):
    pass


def _make_tool(config):
    tool_name = config.getoption("--tool")
    toolpath = config.getoption("--toolpath")
    wrapper_module = config.getoption("--tool-wrapper-module")

    if wrapper_module is not None:
        return _make_custom_tool(wrapper_module, toolpath)

    if tool_name == "ESMini":
        return ESMini(toolpath)
    elif tool_name == "GTGen":
        return GTGen_Simulator(toolpath)
    elif tool_name == "OscSimulator":
        return OscSimulator(toolpath)
    raise UnknownToolError(f"Unknown tool: {tool_name}")


def _make_custom_tool(wrapper_module: str, toolpath: str | None):
    module = _load_wrapper_module(wrapper_module)
    create_tool = getattr(module, "create_tool", None)
    if not callable(create_tool):
        raise ToolWrapperError(
            f"Custom tool wrapper module '{wrapper_module}' must define "
            "a callable create_tool(toolpath)."
        )

    try:
        tool = create_tool(toolpath)
    except Exception as exc:
        raise ToolWrapperError(
            f"Custom tool wrapper module '{wrapper_module}' failed while "
            f"creating the tool: {exc}"
        ) from exc

    if not callable(getattr(tool, "run", None)):
        raise ToolWrapperError(
            f"Custom tool wrapper module '{wrapper_module}' returned an object "
            "without a callable run method."
        )
    return tool


def _load_wrapper_module(wrapper_module: str):
    module_path = pathlib.Path(wrapper_module)
    if module_path.suffix == ".py" or module_path.exists():
        return _load_wrapper_module_from_path(module_path, wrapper_module)

    try:
        return importlib.import_module(wrapper_module)
    except Exception as exc:
        raise ToolWrapperError(
            f"Could not import custom tool wrapper module '{wrapper_module}': {exc}"
        ) from exc


def _load_wrapper_module_from_path(module_path: pathlib.Path, wrapper_module: str):
    if not module_path.exists():
        raise ToolWrapperError(
            f"Custom tool wrapper module file does not exist: {wrapper_module}"
        )
    module_name = f"_osc_validation_custom_tool_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ToolWrapperError(
            f"Could not load custom tool wrapper module from file: {wrapper_module}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise ToolWrapperError(
            f"Could not load custom tool wrapper module from file "
            f"'{wrapper_module}': {exc}"
        ) from exc
    return module


def _get_tool_version(tool):
    get_version = getattr(tool, "get_version", None)
    if not callable(get_version):
        return ["unknown version"]
    return get_version()


def pytest_addoption(parser):
    group = parser.getgroup("OSC Validation Suite")
    group.addoption(
        "--osc-version",
        action="append",
        choices=[v.value for v in OscVersion],
        default=None,
        help="OpenSCENARIO XML contract; repeat for a version matrix (default: 1.4.0)",
    )
    group.addoption(
        "--include-exploratory",
        action="store_true",
        default=False,
        help="Include exploratory behavior checks in addition to conformance cases",
    )
    group.addoption(
        "--tool",
        action="store",
        metavar="TOOL",
        help=(
            "Tool to validate. Built-in tools: ESMini, GTGen, OscSimulator. "
            "Other tools require --tool-wrapper-module"
        ),
    )
    group.addoption(
        "--toolpath",
        action="store",
        default=None,
        metavar="PATH",
        help="Path to the tool to validate",
    )
    group.addoption(
        "--tool-wrapper-module",
        action="store",
        default=None,
        metavar="MODULE_OR_PATH",
        help=(
            "Python module name or .py file path providing "
            "create_tool(toolpath) for a custom tool wrapper"
        ),
    )
    group.addoption(
        "--test-profile",
        action="store",
        default=None,
        metavar="PATH",
        help="Path to a TOML test profile file declaring expected failures for this run",
    )
    group.addoption(
        "--assert-osi-compliance",
        action="store_true",
        default=False,
        help="Enable OSI compliance assertions at assert_osi_compliance fixture call sites",
    )
    group.addoption(
        "--assert-osi-compliance-version",
        action="store",
        default=None,
        metavar="VERSION",
        help="Default OSI version for OSI compliance assertions",
    )
    group.addoption(
        "--assert-osi-compliance-ruleset",
        action="store",
        default=None,
        metavar="PATH",
        help="Default OSI ruleset YAML file for OSI compliance assertions",
    )
    group.addoption(
        "--assert-osi-compliance-ruleset-preset",
        action="store",
        default=None,
        metavar="PRESET",
        help="Use a named OSI ruleset preset for OSI compliance assertions",
    )


def pytest_configure(config):
    """Initialise the tool when ``--tool`` is provided."""
    config.addinivalue_line(
        "markers",
        "osc_versions(*versions): explicitly supported OpenSCENARIO XML versions",
    )
    config.addinivalue_line(
        "markers", "exploratory: behavior check excluded from conformance runs"
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
    except (UnknownToolError, ToolWrapperError, FileNotFoundError) as exc:
        raise pytest.UsageError(str(exc)) from exc
    config._osc_tool = tool
    config._osc_tool_version = _get_tool_version(tool)

    profile_path = config.getoption("--test-profile")
    if profile_path is not None:
        try:
            config._osc_test_profile = load_test_profile(profile_path)
        except (FileNotFoundError, ValueError) as exc:
            raise pytest.UsageError(str(exc)) from exc

    metadata_key = _get_pytest_metadata_key()
    if metadata_key is not None and metadata_key in config.stash:
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
        "OpenSCENARIO XML Contracts": ", ".join(
            config.getoption("--osc-version") or ["1.4.0"]
        ),
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


def _download_omega_prime_ruleset(tmp_path_factory):
    uri = OMEGA_PRIME_OSI_370_RULESET_URL
    filename = pathlib.Path(urlparse(uri).path).name
    base_path = tmp_path_factory.mktemp("osirules")
    provider = DownloadDataProvider(uri=uri, base_path=base_path)
    return provider.ensure_data_path(filename)


def pytest_collection_modifyitems(config, items):
    selected, deselected = [], []
    for item in items:
        marker = item.get_closest_marker("osc_versions")
        if marker is not None:
            versions = _declared_versions(marker, item.nodeid)
            version = item.callspec.params["osc_version"]
            item.user_properties.append(("osc_version", str(version)))
            exploratory = item.get_closest_marker("exploratory") is not None
            item.user_properties.append(
                ("expectation_kind", "exploratory" if exploratory else "conformance")
            )
            if version not in versions or (
                exploratory and not config.getoption("--include-exploratory")
            ):
                deselected.append(item)
                continue
        selected.append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
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


def _declared_versions(marker, nodeid):
    if not marker.args or marker.kwargs:
        raise pytest.UsageError(
            f"{nodeid}: osc_versions requires an explicit list of versions"
        )
    try:
        versions = tuple(OscVersion(value) for value in marker.args)
    except ValueError as exc:
        raise pytest.UsageError(
            f"{nodeid}: unsupported OpenSCENARIO version: {exc}"
        ) from exc
    if len(set(versions)) != len(versions):
        raise pytest.UsageError(f"{nodeid}: duplicate osc_versions declaration")
    return versions


def pytest_generate_tests(metafunc):
    markers = list(metafunc.definition.iter_markers("osc_versions"))
    if len(markers) > 1:
        raise pytest.UsageError(
            f"{metafunc.definition.nodeid}: multiple osc_versions declarations"
        )
    marker = markers[0] if markers else None
    is_validation_case = pathlib.Path(str(metafunc.definition.path)).name.startswith(
        "val_"
    )
    if marker is None:
        if is_validation_case or "osc_version" in metafunc.fixturenames:
            raise pytest.UsageError(
                f"{metafunc.definition.nodeid}: missing osc_versions declaration"
            )
        return
    _declared_versions(marker, metafunc.definition.nodeid)
    selected_versions = metafunc.config.getoption("--osc-version") or ["1.4.0"]
    if "osc_version" not in metafunc.fixturenames:
        metafunc.fixturenames.append("osc_version")
    versions = list(dict.fromkeys(selected_versions))
    metafunc.parametrize(
        "osc_version",
        [OscVersion(v) for v in versions],
        indirect=True,
        ids=[f"osc-{v}" for v in versions],
    )


@pytest.fixture
def osc_version(request):
    return request.param


@pytest.fixture
def scenario_contract(osc_version):
    return ScenarioContract(osc_version)


@pytest.fixture(scope="session")
def assert_osi_compliance(request, tmp_path_factory):
    """Assert OSI trace compliance when enabled by an assertion option."""
    ruleset_preset = request.config.getoption("--assert-osi-compliance-ruleset-preset")
    if ruleset_preset not in {None, "omega-prime"}:
        raise pytest.UsageError(
            "Unsupported OSI compliance ruleset preset: "
            f"{ruleset_preset}. Supported presets: omega-prime."
        )

    qc_enabled = request.config.getoption("--assert-osi-compliance") or (
        ruleset_preset is not None
    )
    default_osi_version = request.config.getoption("--assert-osi-compliance-version")
    default_ruleset = request.config.getoption("--assert-osi-compliance-ruleset")

    if ruleset_preset == "omega-prime":
        default_ruleset = _download_omega_prime_ruleset(tmp_path_factory)

    return make_assert_osi_compliance(
        qc_enabled=qc_enabled,
        default_osi_version=default_osi_version,
        default_ruleset=default_ruleset,
    )


@pytest.fixture
def generate_tool_trace(request, scenario_contract):
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

    @functools.wraps(tool.run)
    def run(*args, **kwargs):
        osc_path = kwargs.get("osc_path", args[0] if args else None)
        if osc_path is None:
            raise TypeError("generate_tool_trace requires an osc_path")
        try:
            header = etree.parse(str(osc_path)).find("FileHeader")
        except (OSError, etree.XMLSyntaxError) as exc:
            raise ValueError(
                f"Cannot read OpenSCENARIO file '{osc_path}': {exc}"
            ) from exc
        version = scenario_contract.osc_version
        expected = (str(version.major), str(version.minor))
        actual = (
            (header.get("revMajor"), header.get("revMinor"))
            if header is not None
            else None
        )
        if actual != expected:
            raise ValueError(
                f"OpenSCENARIO header in '{osc_path}' declares {actual}; "
                f"the selected contract is {version}."
            )
        return tool.run(*args, **kwargs)

    return run
