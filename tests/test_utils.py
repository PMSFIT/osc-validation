"""Tests for project utility functions."""

import math

import pytest

from osi_utilities import ChannelSpecification, open_channel, open_channel_writer

from osc_validation.utils.utils import (
    crop_trace,
    get_all_moving_object_ids,
    get_trajectory_by_moving_object_id,
    rotatePointZYX,
)
from tests.conftest import _make_sensor_view


def test_get_all_moving_object_ids(tmp_path):
    messages = []
    for index in range(3):
        sensor_view = _make_sensor_view(index * 0.1, obj_id=1)
        moving_object = sensor_view.global_ground_truth.moving_object.add()
        moving_object.id.value = 2
        moving_object.base.position.x = 100.0
        messages.append(sensor_view)

    path = tmp_path / "multi_mo.osi"
    with open_channel_writer(
        ChannelSpecification(path=path, message_type="SensorView")
    ) as writer:
        for msg in messages:
            writer.write_message(msg)

    ids = get_all_moving_object_ids(
        ChannelSpecification(path=path, message_type="SensorView")
    )
    assert set(ids) == {1, 2}


def test_get_trajectory_by_moving_object_id(tmp_path):
    messages = [_make_sensor_view(index * 0.1, obj_id=1) for index in range(5)]
    path = tmp_path / "traj.osi"
    with open_channel_writer(
        ChannelSpecification(path=path, message_type="SensorView")
    ) as writer:
        for msg in messages:
            writer.write_message(msg)

    trajectory = get_trajectory_by_moving_object_id(
        ChannelSpecification(path=path, message_type="SensorView"),
        1,
    )

    assert len(trajectory) == 5
    assert "timestamp" in trajectory.columns
    assert "x" in trajectory.columns
    assert "y" in trajectory.columns
    assert trajectory.attrs.get("id") == 1


def test_get_trajectory_with_interval(tmp_path):
    messages = [_make_sensor_view(index * 0.1, obj_id=1) for index in range(10)]
    path = tmp_path / "traj_interval.osi"
    with open_channel_writer(
        ChannelSpecification(path=path, message_type="SensorView")
    ) as writer:
        for msg in messages:
            writer.write_message(msg)

    trajectory = get_trajectory_by_moving_object_id(
        ChannelSpecification(path=path, message_type="SensorView"),
        1,
        start_time=0.2,
        end_time=0.5,
    )

    assert len(trajectory) == 4


def test_crop_trace(tmp_path, sample_sensor_views):
    in_path = tmp_path / "full.osi"
    with open_channel_writer(
        ChannelSpecification(path=in_path, message_type="SensorView")
    ) as writer:
        for msg in sample_sensor_views:
            writer.write_message(msg)
    out_path = tmp_path / "cropped.osi"

    crop_trace(
        ChannelSpecification(path=in_path, message_type="SensorView"),
        ChannelSpecification(path=out_path, message_type="SensorView"),
    )

    with open_channel(
        ChannelSpecification(path=out_path, message_type="SensorView")
    ) as reader:
        cropped = list(reader)
    assert len(cropped) == 5


def test_crop_trace_with_interval(tmp_path):
    messages = [_make_sensor_view(index * 0.1) for index in range(10)]
    in_path = tmp_path / "full.osi"
    with open_channel_writer(
        ChannelSpecification(path=in_path, message_type="SensorView")
    ) as writer:
        for msg in messages:
            writer.write_message(msg)
    out_path = tmp_path / "cropped.osi"

    crop_trace(
        ChannelSpecification(path=in_path, message_type="SensorView"),
        ChannelSpecification(path=out_path, message_type="SensorView"),
        start_time=0.2,
        end_time=0.5,
    )

    with open_channel(
        ChannelSpecification(path=out_path, message_type="SensorView")
    ) as reader:
        cropped = list(reader)
    assert len(cropped) == 4


def test_rotate_point_zyx_identity():
    rx, ry, rz = rotatePointZYX(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    assert rx == pytest.approx(1.0)
    assert ry == pytest.approx(0.0)
    assert rz == pytest.approx(0.0)


def test_rotate_point_zyx_90_yaw():
    rx, ry, rz = rotatePointZYX(1.0, 0.0, 0.0, math.pi / 2, 0.0, 0.0)

    assert rx == pytest.approx(0.0, abs=1e-10)
    assert ry == pytest.approx(1.0, abs=1e-10)
    assert rz == pytest.approx(0.0, abs=1e-10)
