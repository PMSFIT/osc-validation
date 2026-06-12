import math
from dataclasses import dataclass

from osi3 import osi_sensorview_pb2
from osi_utilities import ChannelSpecification, open_channel_writer

from osc_validation.generation import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from osc_validation.reference.trajectory_interpolation import (
    _build_sensor_view,
    _get_osi_version,
    _set_timestamp,
)
from osc_validation.utils.utils import rotatePointZYX


@dataclass(frozen=True)
class FollowTrajectoryTeleportReferenceRequest:
    output_channel_spec: ChannelSpecification
    actor: TrajectoryInterpolationActor
    init_pose: TrajectoryInterpolationVertex
    action_start_time_s: float
    stop_time_s: float
    sample_period_s: float
    host_vehicle_id: int | None = None


def _validate_request(request: FollowTrajectoryTeleportReferenceRequest) -> None:
    if len(request.actor.vertices) < 2:
        raise ValueError("At least two trajectory vertices are required.")
    if request.sample_period_s <= 0.0:
        raise ValueError("sample_period_s must be > 0.0.")
    for previous, current in zip(request.actor.vertices, request.actor.vertices[1:]):
        if previous.time_s >= current.time_s:
            raise ValueError("Trajectory vertex times must be strictly increasing.")
    if request.action_start_time_s < request.actor.vertices[0].time_s:
        raise ValueError("action_start_time_s must be at or after the first vertex time.")
    if request.action_start_time_s > request.actor.vertices[-1].time_s:
        raise ValueError("action_start_time_s must be at or before the last vertex time.")
    if request.stop_time_s < request.actor.vertices[-1].time_s:
        raise ValueError("stop_time_s must be at or after the last vertex time.")

    frame_count_float = request.stop_time_s / request.sample_period_s
    if not math.isclose(frame_count_float, round(frame_count_float), abs_tol=1e-9):
        raise ValueError("sample_period_s must divide stop_time_s exactly.")


def _build_init_pose_sensor_view(
    actor: TrajectoryInterpolationActor,
    init_pose: TrajectoryInterpolationVertex,
    timestamp_s: float,
    host_vehicle_id: int | None,
) -> osi_sensorview_pb2.SensorView:
    center_dx, center_dy, center_dz = rotatePointZYX(
        actor.bounding_box_center_x,
        actor.bounding_box_center_y,
        actor.bounding_box_center_z,
        init_pose.yaw,
        init_pose.pitch,
        init_pose.roll,
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
    moving_object.base.position.x = init_pose.x + center_dx
    moving_object.base.position.y = init_pose.y + center_dy
    moving_object.base.position.z = init_pose.z + center_dz
    moving_object.base.orientation.yaw = init_pose.yaw
    moving_object.base.orientation.pitch = init_pose.pitch
    moving_object.base.orientation.roll = init_pose.roll
    moving_object.base.dimension.length = actor.length
    moving_object.base.dimension.width = actor.width
    moving_object.base.dimension.height = actor.height
    moving_object.type = 2
    moving_object.vehicle_classification.type = 4
    return sensor_view


def build_follow_trajectory_teleport_reference_trace(
    request: FollowTrajectoryTeleportReferenceRequest,
) -> ChannelSpecification:
    _validate_request(request)

    frame_count = int(round(request.stop_time_s / request.sample_period_s)) + 1
    host_vehicle_id = (
        request.host_vehicle_id
        if request.host_vehicle_id is not None
        else request.actor.object_id
    )

    with open_channel_writer(request.output_channel_spec) as writer:
        for frame_index in range(frame_count):
            timestamp_s = frame_index * request.sample_period_s
            if timestamp_s < request.action_start_time_s:
                message = _build_init_pose_sensor_view(
                    actor=request.actor,
                    init_pose=request.init_pose,
                    timestamp_s=timestamp_s,
                    host_vehicle_id=host_vehicle_id,
                )
            else:
                message = _build_sensor_view(
                    actor=request.actor,
                    timestamp_s=timestamp_s,
                    host_vehicle_id=host_vehicle_id,
                    interpolation_mode="linear_position",
                    initial_speed_mps=0.0,
                )
            writer.write_message(message)
        return writer.get_channel_specification()
