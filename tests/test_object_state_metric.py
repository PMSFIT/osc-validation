import math

import pytest
from osi_utilities import ChannelSpecification, open_channel_writer

from tests.conftest import _make_sensor_view

from osc_validation.metrics import ObjectStateMetric


def _write_trace(
    path,
    object_id: int,
    xs: list[float],
    yaw: float = 0.25,
    pitch: float = 0.1,
    roll: float = -0.05,
    length: float = 4.5,
    width: float = 1.8,
    height: float = 1.5,
):
    with open_channel_writer(
        ChannelSpecification(path=path, message_type="SensorView")
    ) as writer:
        for index, x in enumerate(xs):
            msg = _make_sensor_view(index * 0.1, obj_id=object_id)
            moving_object = msg.global_ground_truth.moving_object[0]
            moving_object.base.position.x = x
            moving_object.base.position.y = 2.0
            moving_object.base.velocity.x = 10.0
            moving_object.base.velocity.y = 0.0
            moving_object.base.orientation.yaw = yaw
            moving_object.base.orientation.pitch = pitch
            moving_object.base.orientation.roll = roll
            moving_object.base.dimension.length = length
            moving_object.base.dimension.width = width
            moving_object.base.dimension.height = height
            writer.write_message(msg)


def test_object_state_metric_matches_closest_initial_object(tmp_path):
    reference_path = tmp_path / "reference.osi"
    tool_path = tmp_path / "tool.osi"
    _write_trace(reference_path, object_id=1, xs=[0.0, 1.0, 2.0])
    _write_trace(tool_path, object_id=99, xs=[0.1, 1.1, 2.1])

    result = ObjectStateMetric().compute(
        reference_channel_spec=ChannelSpecification(
            reference_path, message_type="SensorView"
        ),
        tool_channel_spec=ChannelSpecification(tool_path, message_type="SensorView"),
        moving_object_id=1,
    )

    assert result.reference_object_id == 1
    assert result.tool_object_id == 99
    assert result.sample_count == 3
    assert result.max_xy_error < 0.11
    assert result.max_planar_speed_error == 0.0
    assert result.max_time_error == 0.0
    assert result.max_yaw_error == 0.0
    assert result.max_pitch_error == 0.0
    assert result.max_roll_error == 0.0
    assert result.max_orientation_error == 0.0
    assert result.max_length_error == 0.0
    assert result.max_width_error == 0.0
    assert result.max_height_error == 0.0
    assert result.max_dimension_error == 0.0


def test_object_state_metric_wraps_orientation_error(tmp_path):
    reference_path = tmp_path / "reference.osi"
    tool_path = tmp_path / "tool.osi"
    _write_trace(reference_path, object_id=1, xs=[0.0], yaw=math.pi - 0.01)
    _write_trace(tool_path, object_id=1, xs=[0.0], yaw=-math.pi + 0.01)

    result = ObjectStateMetric().compute(
        reference_channel_spec=ChannelSpecification(
            reference_path, message_type="SensorView"
        ),
        tool_channel_spec=ChannelSpecification(tool_path, message_type="SensorView"),
        moving_object_id=1,
        match_mode="same_id",
    )

    assert result.max_yaw_error == pytest.approx(0.02)
    assert result.max_pitch_error == 0.0
    assert result.max_roll_error == 0.0
    assert result.max_orientation_error == pytest.approx(0.02)


def test_object_state_metric_filters_by_reference_time_range(tmp_path):
    reference_path = tmp_path / "reference.osi"
    tool_path = tmp_path / "tool.osi"
    _write_trace(reference_path, object_id=1, xs=[0.0, 0.0, 0.0])
    _write_trace(tool_path, object_id=1, xs=[10.0, 0.05, 10.0])

    result = ObjectStateMetric().compute(
        reference_channel_spec=ChannelSpecification(
            reference_path, message_type="SensorView"
        ),
        tool_channel_spec=ChannelSpecification(tool_path, message_type="SensorView"),
        moving_object_id=1,
        match_mode="same_id",
        time_range_s=(0.09, 0.11),
    )

    assert result.sample_count == 1
    assert result.max_xy_error == pytest.approx(0.05)


def test_object_state_metric_reports_dimension_errors(tmp_path):
    reference_path = tmp_path / "reference.osi"
    tool_path = tmp_path / "tool.osi"
    _write_trace(
        reference_path,
        object_id=1,
        xs=[0.0],
        length=4.5,
        width=1.8,
        height=1.5,
    )
    _write_trace(
        tool_path,
        object_id=1,
        xs=[0.0],
        length=4.7,
        width=1.7,
        height=1.55,
    )

    result = ObjectStateMetric().compute(
        reference_channel_spec=ChannelSpecification(
            reference_path, message_type="SensorView"
        ),
        tool_channel_spec=ChannelSpecification(tool_path, message_type="SensorView"),
        moving_object_id=1,
        match_mode="same_id",
    )

    assert result.max_length_error == pytest.approx(0.2)
    assert result.max_width_error == pytest.approx(0.1)
    assert result.max_height_error == pytest.approx(0.05)
    assert result.max_dimension_error == pytest.approx(0.2)
