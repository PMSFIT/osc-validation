from pathlib import Path
import sys
import tempfile
import types

import pytest

import osc_validation.pytest_plugin as plugin


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
