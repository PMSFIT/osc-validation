"""Trajectory reference sampling and OSI message construction.

Kinematics for output traces are calculated separately from sampled positions.
"""

import math
from typing import Literal

from osi3 import osi_sensorview_pb2, osi_version_pb2

from osc_validation.utils.utils import rotatePointZYX

from osc_validation.features.trajectory.models import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)

TrajectorySamplingMode = Literal[
    "linear_position",
    "constant_acceleration_from_initial_speed",
]


def _interpolate(
    start: TrajectoryInterpolationVertex,
    end: TrajectoryInterpolationVertex,
    timestamp_s: float,
    interpolation_mode: TrajectorySamplingMode,
    initial_speed_mps: float,
) -> TrajectoryInterpolationVertex:
    duration_s = end.time_s - start.time_s
    elapsed_s = timestamp_s - start.time_s
    if interpolation_mode == "linear_position":
        ratio = elapsed_s / duration_s
    elif interpolation_mode == "constant_acceleration_from_initial_speed":
        arc_length = math.dist((start.x, start.y, start.z), (end.x, end.y, end.z))
        if arc_length == 0.0:
            raise ValueError(
                "Constant-acceleration interpolation requires a non-zero arc length."
            )
        acceleration_mps2 = (
            2.0 * (arc_length - initial_speed_mps * duration_s) / duration_s**2
        )
        distance_s = (
            initial_speed_mps * elapsed_s + 0.5 * acceleration_mps2 * elapsed_s**2
        )
        ratio = distance_s / arc_length
    else:
        raise ValueError(f"Unsupported interpolation_mode '{interpolation_mode}'.")

    return TrajectoryInterpolationVertex(
        time_s=timestamp_s,
        x=start.x + (end.x - start.x) * ratio,
        y=start.y + (end.y - start.y) * ratio,
        z=start.z + (end.z - start.z) * ratio,
        yaw=start.yaw + (end.yaw - start.yaw) * ratio,
        pitch=start.pitch + (end.pitch - start.pitch) * ratio,
        roll=start.roll + (end.roll - start.roll) * ratio,
    )


def _segment_kinematics(
    start: TrajectoryInterpolationVertex,
    end: TrajectoryInterpolationVertex,
    interpolation_mode: TrajectorySamplingMode,
    initial_speed_mps: float,
) -> tuple[float, float, float]:
    duration_s = end.time_s - start.time_s
    arc_length = math.dist((start.x, start.y, start.z), (end.x, end.y, end.z))
    if interpolation_mode == "linear_position":
        return arc_length, arc_length / duration_s, 0.0
    if interpolation_mode == "constant_acceleration_from_initial_speed":
        if arc_length == 0.0:
            raise ValueError(
                "Constant-acceleration interpolation requires a non-zero arc length."
            )
        acceleration_mps2 = (
            2.0 * (arc_length - initial_speed_mps * duration_s) / duration_s**2
        )
        return arc_length, initial_speed_mps, acceleration_mps2
    raise ValueError(f"Unsupported interpolation_mode '{interpolation_mode}'.")


def _active_segment(
    vertices: list[TrajectoryInterpolationVertex],
    timestamp_s: float,
    interpolation_mode: TrajectorySamplingMode,
    initial_speed_mps: float,
) -> tuple[TrajectoryInterpolationVertex, TrajectoryInterpolationVertex, float]:
    segment_initial_speed_mps = initial_speed_mps
    for index, (start, end) in enumerate(zip(vertices, vertices[1:])):
        arc_length, _, acceleration_mps2 = _segment_kinematics(
            start,
            end,
            interpolation_mode,
            segment_initial_speed_mps,
        )
        is_last_segment = index == len(vertices) - 2
        if start.time_s <= timestamp_s and (
            timestamp_s < end.time_s or (is_last_segment and timestamp_s <= end.time_s)
        ):
            return start, end, segment_initial_speed_mps
        if interpolation_mode == "constant_acceleration_from_initial_speed":
            segment_initial_speed_mps += acceleration_mps2 * (end.time_s - start.time_s)
        else:
            segment_initial_speed_mps = arc_length / (end.time_s - start.time_s)
    raise ValueError("timestamp_s is outside the trajectory time range.")


def sample_trajectory(
    vertices: list[TrajectoryInterpolationVertex],
    timestamp_s: float,
    *,
    interpolation_mode: TrajectorySamplingMode,
    initial_speed_mps: float,
) -> TrajectoryInterpolationVertex:
    """Sample a pose within a trajectory, carrying speed across segments.

    Vertices must have strictly increasing times. The final endpoint is included;
    timestamps outside the trajectory are rejected.
    """
    start, end, segment_initial_speed_mps = _active_segment(
        vertices, timestamp_s, interpolation_mode, initial_speed_mps
    )
    return _interpolate(
        start, end, timestamp_s, interpolation_mode, segment_initial_speed_mps
    )


def get_osi_version():
    return osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
        osi_version_pb2.current_interface_version
    ]


def set_timestamp(message, timestamp_s: float) -> None:
    seconds = int(timestamp_s)
    nanos = int(round((timestamp_s - seconds) * 1e9))
    if nanos == 1_000_000_000:
        seconds += 1
        nanos = 0
    message.timestamp.seconds = seconds
    message.timestamp.nanos = nanos


def build_trajectory_sensor_view(
    *,
    actor: TrajectoryInterpolationActor,
    pose: TrajectoryInterpolationVertex,
    timestamp_s: float,
    host_vehicle_id: int | None,
) -> osi_sensorview_pb2.SensorView:
    """Encode one vehicle pose, converting its bounding-box center to world space.

    The caller supplies the sampling time and pose; this function applies no
    motion policy and leaves velocity and acceleration unset.
    The message contains one car and uses sensor ID 42.
    """
    center_dx, center_dy, center_dz = rotatePointZYX(
        actor.bounding_box_center_x,
        actor.bounding_box_center_y,
        actor.bounding_box_center_z,
        pose.yaw,
        pose.pitch,
        pose.roll,
    )

    sensor_view = osi_sensorview_pb2.SensorView()
    sensor_view.version.CopyFrom(get_osi_version())
    set_timestamp(sensor_view, timestamp_s)
    sensor_view.global_ground_truth.version.CopyFrom(get_osi_version())
    set_timestamp(sensor_view.global_ground_truth, timestamp_s)
    sensor_view.sensor_id.value = 42

    if host_vehicle_id is not None:
        sensor_view.host_vehicle_id.value = host_vehicle_id
        sensor_view.global_ground_truth.host_vehicle_id.value = host_vehicle_id

    moving_object = sensor_view.global_ground_truth.moving_object.add()
    moving_object.id.value = actor.object_id
    moving_object.base.position.x = pose.x + center_dx
    moving_object.base.position.y = pose.y + center_dy
    moving_object.base.position.z = pose.z + center_dz
    moving_object.base.orientation.yaw = pose.yaw
    moving_object.base.orientation.pitch = pose.pitch
    moving_object.base.orientation.roll = pose.roll
    moving_object.base.dimension.length = actor.length
    moving_object.base.dimension.width = actor.width
    moving_object.base.dimension.height = actor.height
    moving_object.type = 2
    moving_object.vehicle_classification.type = 4
    return sensor_view
