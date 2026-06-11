import math
from dataclasses import dataclass
from typing import Literal

from osi3 import osi_sensorview_pb2, osi_version_pb2
from osi_utilities import ChannelSpecification, open_channel_writer

from osc_validation.generation import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from osc_validation.utils.utils import rotatePointZYX

TrajectoryInterpolationReferenceMode = Literal[
    "linear_position",
    "constant_acceleration_from_initial_speed",
]


@dataclass(frozen=True)
class TrajectoryInterpolationReferenceRequest:
    output_channel_spec: ChannelSpecification
    actor: TrajectoryInterpolationActor
    sample_period_s: float
    host_vehicle_id: int | None = None
    interpolation_mode: TrajectoryInterpolationReferenceMode = "linear_position"
    initial_speed_mps: float = 0.0


def _get_osi_version():
    return osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
        osi_version_pb2.current_interface_version
    ]


def _set_timestamp(message, timestamp_s: float) -> None:
    seconds = int(timestamp_s)
    nanos = int(round((timestamp_s - seconds) * 1e9))
    if nanos == 1_000_000_000:
        seconds += 1
        nanos = 0
    message.timestamp.seconds = seconds
    message.timestamp.nanos = nanos


def _interpolate(
    start: TrajectoryInterpolationVertex,
    end: TrajectoryInterpolationVertex,
    timestamp_s: float,
    interpolation_mode: TrajectoryInterpolationReferenceMode,
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
        acceleration_mps2 = 2.0 * (
            arc_length - initial_speed_mps * duration_s
        ) / duration_s**2
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
    interpolation_mode: TrajectoryInterpolationReferenceMode,
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
        acceleration_mps2 = 2.0 * (
            arc_length - initial_speed_mps * duration_s
        ) / duration_s**2
        return arc_length, initial_speed_mps, acceleration_mps2
    raise ValueError(f"Unsupported interpolation_mode '{interpolation_mode}'.")


def _active_segment(
    vertices: list[TrajectoryInterpolationVertex],
    timestamp_s: float,
    interpolation_mode: TrajectoryInterpolationReferenceMode,
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


def _build_sensor_view(
    actor: TrajectoryInterpolationActor,
    timestamp_s: float,
    host_vehicle_id: int | None,
    interpolation_mode: TrajectoryInterpolationReferenceMode,
    initial_speed_mps: float,
) -> osi_sensorview_pb2.SensorView:
    start, end, segment_initial_speed_mps = _active_segment(
        actor.vertices,
        timestamp_s,
        interpolation_mode,
        initial_speed_mps,
    )
    vertex = _interpolate(
        start,
        end,
        timestamp_s,
        interpolation_mode,
        segment_initial_speed_mps,
    )
    dx = end.x - start.x
    dy = end.y - start.y
    dz = end.z - start.z
    arc_length, segment_speed_mps, acceleration_mps2 = _segment_kinematics(
        start,
        end,
        interpolation_mode,
        segment_initial_speed_mps,
    )
    speed_mps = segment_speed_mps + acceleration_mps2 * (timestamp_s - start.time_s)

    if arc_length == 0.0:
        ux = uy = uz = 0.0
    else:
        ux = dx / arc_length
        uy = dy / arc_length
        uz = dz / arc_length
    vx = ux * speed_mps
    vy = uy * speed_mps
    vz = uz * speed_mps
    center_dx, center_dy, center_dz = rotatePointZYX(
        actor.bounding_box_center_x,
        actor.bounding_box_center_y,
        actor.bounding_box_center_z,
        vertex.yaw,
        vertex.pitch,
        vertex.roll,
    )

    sensor_view = osi_sensorview_pb2.SensorView()
    sensor_view.version.CopyFrom(_get_osi_version())
    _set_timestamp(sensor_view, timestamp_s)
    sensor_view.global_ground_truth.version.CopyFrom(_get_osi_version())
    _set_timestamp(sensor_view.global_ground_truth, timestamp_s)
    sensor_view.sensor_id.value = 42

    if host_vehicle_id is not None:
        sensor_view.host_vehicle_id.value = host_vehicle_id
        sensor_view.global_ground_truth.host_vehicle_id.value = host_vehicle_id

    moving_object = sensor_view.global_ground_truth.moving_object.add()
    moving_object.id.value = actor.object_id
    moving_object.base.position.x = vertex.x + center_dx
    moving_object.base.position.y = vertex.y + center_dy
    moving_object.base.position.z = vertex.z + center_dz
    moving_object.base.orientation.yaw = vertex.yaw
    moving_object.base.orientation.pitch = vertex.pitch
    moving_object.base.orientation.roll = vertex.roll
    moving_object.base.dimension.length = actor.length
    moving_object.base.dimension.width = actor.width
    moving_object.base.dimension.height = actor.height
    moving_object.base.velocity.x = vx
    moving_object.base.velocity.y = vy
    moving_object.base.velocity.z = vz
    moving_object.base.acceleration.x = ux * acceleration_mps2
    moving_object.base.acceleration.y = uy * acceleration_mps2
    moving_object.base.acceleration.z = uz * acceleration_mps2
    moving_object.type = 2
    moving_object.vehicle_classification.type = 4
    return sensor_view


def build_trajectory_interpolation_reference_trace(
    request: TrajectoryInterpolationReferenceRequest,
) -> ChannelSpecification:
    actor = request.actor
    if len(actor.vertices) < 2:
        raise ValueError("At least two trajectory vertices are required.")
    if request.sample_period_s <= 0.0:
        raise ValueError("sample_period_s must be > 0.0.")

    for previous, current in zip(actor.vertices, actor.vertices[1:]):
        if previous.time_s >= current.time_s:
            raise ValueError("Trajectory vertex times must be strictly increasing.")

    start = actor.vertices[0]
    end = actor.vertices[-1]
    duration_s = end.time_s - start.time_s
    frame_count_float = duration_s / request.sample_period_s
    frame_count = int(round(frame_count_float)) + 1
    if not math.isclose(frame_count_float, round(frame_count_float), abs_tol=1e-9):
        raise ValueError("sample_period_s must divide the trajectory duration exactly.")

    with open_channel_writer(request.output_channel_spec) as writer:
        for frame_index in range(frame_count):
            timestamp_s = start.time_s + frame_index * request.sample_period_s
            writer.write_message(
                _build_sensor_view(
                    actor=actor,
                    timestamp_s=timestamp_s,
                    host_vehicle_id=request.host_vehicle_id,
                    interpolation_mode=request.interpolation_mode,
                    initial_speed_mps=request.initial_speed_mps,
                )
            )
        return writer.get_channel_specification()
