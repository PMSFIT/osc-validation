from pathlib import Path
import shlex

import pytest

from osi_utilities import ChannelSpecification

import osc_validation.tools.esmini as esmini_module
import osc_validation.tools.gtgen_cli as gtgen_module
from osc_validation.tools.esmini import ESMini
from osc_validation.tools.gtgen_cli import GTGen_Simulator
from osc_validation.utils.osi_reader import OSIChannelReader
from tests.conftest import _make_ground_truth, _make_sensor_view, _write_binary_trace


def _write_trace_from_command(command: str, output_flag: str, messages) -> Path:
    parts = shlex.split(command)
    output_path = Path(parts[parts.index(output_flag) + 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_binary_trace(output_path, messages)
    return output_path


def test_esmini_get_version_uses_helper(monkeypatch):
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: type("R", (), {"stdout": "esmini 1.2.3", "stderr": ""})(),
    )

    tool = ESMini("/usr/bin/true")
    assert tool.get_version() == ["esmini 1.2.3"]


def test_esmini_run_sensorview_output_builds_command_and_converts(
    tmp_path, monkeypatch
):
    commands = []

    def _fake_system(command: str) -> int:
        commands.append(command)
        _write_trace_from_command(
            command,
            "--osi_file",
            [_make_ground_truth(0.0), _make_ground_truth(0.1)],
        )
        return 0

    monkeypatch.setattr(esmini_module.os, "system", _fake_system)

    tool = ESMini("/usr/bin/true")
    output_spec = ChannelSpecification(
        path=tmp_path / "tool_trace.mcap",
        message_type="SensorView",
        topic="sv",
    )
    result = tool.run(
        osc_path=tmp_path / "scenario.xosc",
        odr_path=tmp_path / "map.xodr",
        osi_output_spec=output_spec,
        log_path=tmp_path,
        rate=0.05,
    )

    assert result.path == output_spec.path
    assert result.message_type == "SensorView"
    assert output_spec.path.exists()
    assert "--headless" in commands[0]
    assert "--fixed_timestep 0.05" in commands[0]
    assert "--logfile_path" in commands[0]

    with OSIChannelReader.from_osi_channel_specification(result) as reader:
        assert len(list(reader)) == 2


def test_esmini_run_groundtruth_same_format_renames_temp_trace(tmp_path, monkeypatch):
    captured_temp_paths = []

    def _fake_system(command: str) -> int:
        temp_path = _write_trace_from_command(
            command,
            "--osi_file",
            [_make_ground_truth(0.0), _make_ground_truth(0.1)],
        )
        captured_temp_paths.append(temp_path)
        return 0

    monkeypatch.setattr(esmini_module.os, "system", _fake_system)

    tool = ESMini("/usr/bin/true")
    output_spec = ChannelSpecification(
        path=tmp_path / "tool_trace.osi",
        message_type="GroundTruth",
    )
    result = tool.run(
        osc_path=tmp_path / "scenario.xosc",
        odr_path=tmp_path / "map.xodr",
        osi_output_spec=output_spec,
    )

    assert result.path == output_spec.path
    assert output_spec.path.exists()
    assert not captured_temp_paths[0].exists()


def test_esmini_run_groundtruth_different_format_converts_trace(tmp_path, monkeypatch):
    def _fake_system(command: str) -> int:
        _write_trace_from_command(
            command,
            "--osi_file",
            [_make_ground_truth(0.0), _make_ground_truth(0.1)],
        )
        return 0

    monkeypatch.setattr(esmini_module.os, "system", _fake_system)

    tool = ESMini("/usr/bin/true")
    output_spec = ChannelSpecification(
        path=tmp_path / "tool_trace.mcap",
        message_type="GroundTruth",
        topic="gt",
    )
    result = tool.run(
        osc_path=tmp_path / "scenario.xosc",
        odr_path=tmp_path / "map.xodr",
        osi_output_spec=output_spec,
    )

    assert result.path == output_spec.path
    with OSIChannelReader.from_osi_channel_specification(result) as reader:
        messages = list(reader)
    assert len(messages) == 2


def test_esmini_run_rejects_invalid_message_type(tmp_path):
    tool = ESMini("/usr/bin/true")

    with pytest.raises(ValueError, match="OSI message type is not allowed"):
        tool.run(
            osc_path=tmp_path / "scenario.xosc",
            odr_path=tmp_path / "map.xodr",
            osi_output_spec=ChannelSpecification(
                path=tmp_path / "trace.osi",
                message_type="TrafficUpdate",
            ),
        )


def test_esmini_run_raises_when_temp_trace_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(esmini_module.os, "system", lambda command: 0)

    tool = ESMini("/usr/bin/true")
    with pytest.raises(RuntimeError, match="ESMini trace could not be generated"):
        tool.run(
            osc_path=tmp_path / "scenario.xosc",
            odr_path=tmp_path / "map.xodr",
            osi_output_spec=ChannelSpecification(
                path=tmp_path / "trace.osi",
                message_type="GroundTruth",
            ),
        )


def test_gtgen_get_version_uses_helper(monkeypatch):
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: type("R", (), {"stdout": "gtgen 4.5.6", "stderr": ""})(),
    )

    tool = GTGen_Simulator("/usr/bin/true")
    assert tool.get_version() == ["gtgen 4.5.6"]


def test_gtgen_run_builds_command_and_converts_trace(tmp_path, monkeypatch):
    commands = []

    def _fake_system(command: str) -> int:
        commands.append(command)
        _write_trace_from_command(
            command,
            "--output-trace",
            [_make_sensor_view(0.0), _make_sensor_view(0.1)],
        )
        return 0

    monkeypatch.setattr(gtgen_module.os, "system", _fake_system)

    tool = GTGen_Simulator("/usr/bin/true")
    output_spec = ChannelSpecification(
        path=tmp_path / "gtgen_trace.mcap",
        message_type="SensorView",
        topic="sv",
    )
    result = tool.run(
        osc_path=tmp_path / "scenario.xosc",
        odr_path=tmp_path / "map.xodr",
        osi_output_spec=output_spec,
        log_path=tmp_path,
        rate=0.05,
    )

    assert result.path == output_spec.path
    assert "--gtgen-data ./GTGEN_DATA" in commands[0]
    assert "--step-size-ms 50.0" in commands[0]
    assert "--log-file-dir" in commands[0]

    with OSIChannelReader.from_osi_channel_specification(result) as reader:
        assert len(list(reader)) == 2


def test_gtgen_run_rejects_invalid_message_type(tmp_path):
    tool = GTGen_Simulator("/usr/bin/true")

    with pytest.raises(ValueError, match="OSI message type is not allowed"):
        tool.run(
            osc_path=tmp_path / "scenario.xosc",
            odr_path=tmp_path / "map.xodr",
            osi_output_spec=ChannelSpecification(
                path=tmp_path / "trace.osi",
                message_type="GroundTruth",
            ),
        )


def test_gtgen_run_raises_when_temp_trace_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(gtgen_module.os, "system", lambda command: 0)

    tool = GTGen_Simulator("/usr/bin/true")
    output_spec = ChannelSpecification(
        path=tmp_path / "trace.osi",
        message_type="SensorView",
    )
    suffixes = "".join(output_spec.path.suffixes)
    base_name = (
        output_spec.path.name.removesuffix(suffixes)
        if suffixes
        else output_spec.path.name
    )
    expected_temp_path = output_spec.path.with_name(f"{base_name}_gtgen.osi")

    with pytest.raises(RuntimeError, match="GTGen trace could not be generated"):
        tool.run(
            osc_path=tmp_path / "scenario.xosc",
            odr_path=tmp_path / "map.xodr",
            osi_output_spec=output_spec,
        )

    assert not expected_temp_path.exists()
