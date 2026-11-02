import math
from dataclasses import dataclass

from osi3 import osi_sensorview_pb2
from osi_utilities import ChannelSpecification, open_channel_writer

from osc_validation.features.trajectory.models import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from osc_validation.features.trajectory.reference import (
    build_trajectory_sensor_view,
    sample_trajectory,
)


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
        raise ValueError(
            "action_start_time_s must be at or after the first vertex time."
        )
    if request.action_start_time_s > request.actor.vertices[-1].time_s:
        raise ValueError(
            "action_start_time_s must be at or before the last vertex time."
        )
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
    return build_trajectory_sensor_view(
        actor=actor,
        pose=init_pose,
        timestamp_s=timestamp_s,
        host_vehicle_id=host_vehicle_id,
    )


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
                message = build_trajectory_sensor_view(
                    actor=request.actor,
                    pose=sample_trajectory(
                        request.actor.vertices,
                        timestamp_s,
                        interpolation_mode="linear_position",
                        initial_speed_mps=0.0,
                    ),
                    timestamp_s=timestamp_s,
                    host_vehicle_id=host_vehicle_id,
                )
            writer.write_message(message)
        return writer.get_channel_specification()
