from pathlib import Path
import sys
import tempfile
import types

import pytest

import osc_validation.pytest_plugin as plugin
from osc_validation.test_profile import Profile, XFailEntry


@pytest.mark.parametrize("selector", ["*", "scenario/*", "osc_validation/validation/*"])
@pytest.mark.parametrize("exception_prefix", ["", "osc_validation/validation/"])
def test_profile_exceptions_veto_raw_and_canonical_ids(selector, exception_prefix):
    relative_path = "scenario/val_example.py"
    canonical_id = f"{relative_path}::test_case[osc-1.4.0-trace.mcap]"
    markers = []
    item = types.SimpleNamespace(
        nodeid=f"osc_validation/validation/{canonical_id}",
        path=Path(plugin.__file__).parent / "validation" / relative_path,
        get_closest_marker=lambda name: None,
        add_marker=lambda marker, **kwargs: markers.append(marker),
    )
    config = FakeConfig()
    config._osc_test_profile = Profile(
        xfails=[
            XFailEntry(
                test=selector,
                reason="unsupported",
                except_patterns=[f"{exception_prefix}{relative_path}::test_case"],
            )
        ]
    )

    plugin.pytest_collection_modifyitems(config, [item])
    assert markers == []

    item.nodeid = item.nodeid.replace("test_case[", "test_other[")
    plugin.pytest_collection_modifyitems(config, [item])
    assert len(markers) == 1
    assert markers[0].name == "xfail"


class FakeConfig:
    def __init__(self, **options):
        self.options = options

    def getoption(self, name):
        return self.options.get(name)


class FakeBuiltInTool:
    def __init__(self, toolpath):
        self.tool_path = Path(toolpath)

    def run(self, osc_path, odr_path, osi_output_spec):
        return osi_output_spec

    def get_version(self):
        return ["fake built-in"]


def _write_temp_module(source: str) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".py",
        prefix="osc_validation_custom_tool_",
        dir=Path.cwd(),
        delete=False,
    ) as temp_file:
        temp_file.write(source)
        return Path(temp_file.name)


def test_make_tool_uses_builtin_dispatch(monkeypatch):
    monkeypatch.setattr(plugin, "ESMini", FakeBuiltInTool)

    tool = plugin._make_tool(
        FakeConfig(
            **{
                "--tool": "ESMini",
                "--toolpath": "C:/tools/esmini.exe",
                "--tool-wrapper-module": None,
            }
        )
    )

    assert isinstance(tool, FakeBuiltInTool)
    assert tool.tool_path == Path("C:/tools/esmini.exe")


def test_make_tool_loads_custom_wrapper_by_import_name(monkeypatch):
    class CustomTool:
        def __init__(self, toolpath):
            self.tool_path = toolpath

        def run(self, osc_path, odr_path, osi_output_spec):
            return osi_output_spec

        def get_version(self):
            return ["custom 1.0"]

    module = types.ModuleType("custom_wrapper")
    module.create_tool = CustomTool
    monkeypatch.setitem(sys.modules, "custom_wrapper", module)

    tool = plugin._make_tool(
        FakeConfig(
            **{
                "--tool": "CustomTool",
                "--toolpath": "C:/tools/custom.exe",
                "--tool-wrapper-module": "custom_wrapper",
            }
        )
    )

    assert tool.tool_path == "C:/tools/custom.exe"
    assert tool.get_version() == ["custom 1.0"]


def test_make_tool_loads_custom_wrapper_by_file_path():
    wrapper = _write_temp_module(
        """
class CustomTool:
    def __init__(self, toolpath):
        self.tool_path = toolpath

    def run(self, osc_path, odr_path, osi_output_spec):
        return osi_output_spec

def create_tool(toolpath):
    return CustomTool(toolpath)
"""
    )

    try:
        tool = plugin._make_tool(
            FakeConfig(
                **{
                    "--tool": "CustomTool",
                    "--toolpath": "C:/tools/custom.exe",
                    "--tool-wrapper-module": str(wrapper),
                }
            )
        )

        assert tool.tool_path == "C:/tools/custom.exe"
        assert plugin._get_tool_version(tool) == ["unknown version"]
    finally:
        wrapper.unlink(missing_ok=True)


def test_custom_wrapper_requires_create_tool():
    wrapper = _write_temp_module("VALUE = 1\n")

    try:
        with pytest.raises(plugin.ToolWrapperError, match="create_tool"):
            plugin._make_tool(
                FakeConfig(
                    **{
                        "--tool": "CustomTool",
                        "--toolpath": None,
                        "--tool-wrapper-module": str(wrapper),
                    }
                )
            )
    finally:
        wrapper.unlink(missing_ok=True)


def test_custom_wrapper_requires_callable_run():
    wrapper = _write_temp_module(
        """
class CustomTool:
    pass

def create_tool(toolpath):
    return CustomTool()
"""
    )

    try:
        with pytest.raises(plugin.ToolWrapperError, match="callable run"):
            plugin._make_tool(
                FakeConfig(
                    **{
                        "--tool": "CustomTool",
                        "--toolpath": None,
                        "--tool-wrapper-module": str(wrapper),
                    }
                )
            )
    finally:
        wrapper.unlink(missing_ok=True)
