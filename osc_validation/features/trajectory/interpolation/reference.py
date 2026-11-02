import math
from dataclasses import dataclass

from osi_utilities import ChannelSpecification, open_channel_writer

from osc_validation.features.trajectory.models import (
    TrajectoryInterpolationActor,
)
from osc_validation.features.trajectory.reference import (
    build_trajectory_sensor_view,
    TrajectorySamplingMode as TrajectoryInterpolationReferenceMode,
    sample_trajectory,
)
from osc_validation.reference.trace_kinematics import (
    build_trace_with_calculated_kinematics,
)
from osc_validation.utils.osi_channel_specification import with_name_suffix


@dataclass(frozen=True)
class TrajectoryInterpolationReferenceRequest:
    output_channel_spec: ChannelSpecification
    actor: TrajectoryInterpolationActor
    sample_period_s: float
    host_vehicle_id: int | None = None
    interpolation_mode: TrajectoryInterpolationReferenceMode = "linear_position"
    initial_speed_mps: float = 0.0


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

    pose_channel_spec = with_name_suffix(request.output_channel_spec, "_poses")
    with open_channel_writer(pose_channel_spec) as writer:
        for frame_index in range(frame_count):
            timestamp_s = start.time_s + frame_index * request.sample_period_s
            writer.write_message(
                build_trajectory_sensor_view(
                    actor=actor,
                    pose=sample_trajectory(
                        actor.vertices,
                        timestamp_s,
                        interpolation_mode=request.interpolation_mode,
                        initial_speed_mps=request.initial_speed_mps,
                    ),
                    timestamp_s=timestamp_s,
                    host_vehicle_id=request.host_vehicle_id,
                )
            )
        pose_channel_spec = writer.get_channel_specification()

    return build_trace_with_calculated_kinematics(
        input_channel_spec=pose_channel_spec,
        output_channel_spec=request.output_channel_spec,
    )
