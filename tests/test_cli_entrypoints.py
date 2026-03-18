from pathlib import Path
import importlib

from osi_utilities import ChannelSpecification

import osc_validation.metrics.trajectory_similarity as trajectory_similarity_module
import osc_validation.utils.esminigt2sv as esminigt2sv_module
import osc_validation.utils.osi_format_converter as osi_format_converter_module
import osc_validation.utils.strip_sensorview as strip_sensorview_module
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter
from tests.conftest import _make_ground_truth, _make_sensor_view, _write_binary_trace

osi2osc_module = importlib.import_module("osc_validation.generation.osi2osc")


def _write_sensorview_trace(path: Path, positions: list[float]) -> None:
    messages = []
    for index, x in enumerate(positions):
        sensor_view = _make_sensor_view(index * 0.1, obj_id=1)
        moving_object = sensor_view.global_ground_truth.moving_object[0]
        moving_object.base.position.x = x
        moving_object.base.position.y = 1.0
        moving_object.base.dimension.length = 4.5
        moving_object.base.dimension.width = 1.8
        moving_object.base.dimension.height = 1.5
        moving_object.vehicle_classification.type = 4
        messages.append(sensor_view)
    _write_binary_trace(path, messages)


def test_osi2osc_main_writes_scenario(tmp_path, monkeypatch):
    trace_path = tmp_path / "input.osi"
    _write_sensorview_trace(trace_path, [0.0, 1.0])
    output_path = tmp_path / "scenario.xosc"

    monkeypatch.setattr(
        osi2osc_module.sys,
        "argv",
        ["osi2osc", str(trace_path), "SensorView", str(output_path)],
    )

    assert osi2osc_module.main() == 0
    assert output_path.exists()


def test_osi_format_converter_main_converts_compressed_trace_to_mcap(
    tmp_path, monkeypatch
):
    input_path = tmp_path / "input.osi.xz"
    input_spec = ChannelSpecification(path=input_path, message_type="SensorView")
    with OSIChannelWriter.from_osi_channel_specification(input_spec) as writer:
        for index in range(3):
            writer.write(_make_sensor_view(index * 0.1))

    output_path = tmp_path / "output.mcap"
    monkeypatch.setattr(
        osi_format_converter_module,
        "Path",
        Path,
    )
    monkeypatch.setattr(
        osi_format_converter_module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "input": str(input_path),
                "type": "SensorView",
                "output": str(output_path),
                "input_topic": None,
                "output_topic": "sv",
            },
        )(),
    )

    osi_format_converter_module.main()

    with OSIChannelReader.from_osi_channel_specification(
        ChannelSpecification(path=output_path, topic="sv")
    ) as reader:
        assert len(list(reader)) == 3


def test_esminigt2sv_main_converts_groundtruth_trace(tmp_path, monkeypatch):
    input_path = tmp_path / "input.osi"
    _write_binary_trace(input_path, [_make_ground_truth(0.0), _make_ground_truth(0.1)])
    output_path = tmp_path / "output.osi"

    monkeypatch.setattr(
        esminigt2sv_module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {"groundtruth": str(input_path), "sensorview": str(output_path)},
        )(),
    )

    esminigt2sv_module.main()

    with OSIChannelReader.from_osi_channel_specification(
        ChannelSpecification(path=output_path, message_type="SensorView")
    ) as reader:
        assert len(list(reader)) == 2


def test_strip_sensorview_main_strips_lane_boundary(tmp_path, monkeypatch):
    input_path = tmp_path / "input.osi"
    output_path = tmp_path / "output.osi"
    sensor_view = _make_sensor_view(0.0)
    sensor_view.global_ground_truth.lane_boundary.add().id.value = 10
    _write_binary_trace(input_path, [sensor_view])

    monkeypatch.setattr(
        strip_sensorview_module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "sensorview_in": str(input_path),
                "sensorview_out": str(output_path),
                "lane_boundary": True,
                "reference_line": False,
                "logical_lane": False,
                "logical_lane_boundary": False,
                "lane": False,
                "environmental_conditions": False,
            },
        )(),
    )

    strip_sensorview_module.main()

    with OSIChannelReader.from_osi_channel_specification(
        ChannelSpecification(path=output_path, message_type="SensorView")
    ) as reader:
        messages = list(reader)
    assert len(messages[0].global_ground_truth.lane_boundary) == 0


def test_trajectory_similarity_main_writes_plot(tmp_path, monkeypatch):
    reference_path = tmp_path / "reference.osi"
    tool_path = tmp_path / "tool.osi"
    _write_sensorview_trace(reference_path, [0.0, 1.0, 2.0])
    _write_sensorview_trace(tool_path, [0.0, 1.0, 2.0])

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        trajectory_similarity_module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "reference_sv": str(reference_path),
                "tool_sv": str(tool_path),
                "moving_object_id": "1",
                "reference_topic": None,
                "tool_topic": None,
                "plot": True,
                "start_time": None,
                "end_time": None,
            },
        )(),
    )

    trajectory_similarity_module.main()

    assert (tmp_path / "trajectory_similarity_1.png").exists()
