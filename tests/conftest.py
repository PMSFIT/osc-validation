"""Shared fixtures for SDK integration tests."""

import pytest

from osi3 import (
    osi_sensorview_pb2,
    osi_groundtruth_pb2,
    osi_version_pb2,
)


def _get_osi_version():
    """Get the current OSI interface version."""
    return osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
        osi_version_pb2.current_interface_version
    ]


def _make_sensor_view(
    timestamp_s: float, obj_id: int = 1
) -> osi_sensorview_pb2.SensorView:
    """Create a SensorView message with a moving object."""
    sv = osi_sensorview_pb2.SensorView()
    sv.version.CopyFrom(_get_osi_version())
    sv.timestamp.seconds = int(timestamp_s)
    sv.timestamp.nanos = int((timestamp_s - int(timestamp_s)) * 1e9)
    sv.sensor_id.value = 42
    mo = sv.global_ground_truth.moving_object.add()
    mo.id.value = obj_id
    mo.base.position.x = timestamp_s * 10.0
    mo.base.position.y = 5.0
    mo.base.position.z = 0.0
    mo.base.orientation.yaw = 0.1
    mo.base.orientation.pitch = 0.0
    mo.base.orientation.roll = 0.0
    mo.base.dimension.length = 4.5
    mo.base.dimension.width = 1.8
    mo.base.dimension.height = 1.5
    sv.global_ground_truth.host_vehicle_id.value = obj_id
    sv.host_vehicle_id.value = obj_id
    return sv


def _make_ground_truth(
    timestamp_s: float, obj_id: int = 1
) -> osi_groundtruth_pb2.GroundTruth:
    """Create a GroundTruth message with a moving object."""
    gt = osi_groundtruth_pb2.GroundTruth()
    gt.version.CopyFrom(_get_osi_version())
    gt.timestamp.seconds = int(timestamp_s)
    gt.timestamp.nanos = int((timestamp_s - int(timestamp_s)) * 1e9)
    gt.host_vehicle_id.value = obj_id
    mo = gt.moving_object.add()
    mo.id.value = obj_id
    mo.base.position.x = timestamp_s * 10.0
    mo.base.position.y = 5.0
    mo.base.position.z = 0.0
    mo.base.orientation.yaw = 0.1
    return gt


@pytest.fixture
def sample_sensor_views():
    """5 SensorView messages at 0.0s, 0.1s, 0.2s, 0.3s, 0.4s."""
    return [_make_sensor_view(i * 0.1) for i in range(5)]


@pytest.fixture
def sample_ground_truths():
    """5 GroundTruth messages at 0.0s, 0.1s, 0.2s, 0.3s, 0.4s."""
    return [_make_ground_truth(i * 0.1) for i in range(5)]
