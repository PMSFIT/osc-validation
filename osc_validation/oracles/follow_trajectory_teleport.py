from dataclasses import dataclass
from pathlib import Path

from osi_utilities import ChannelSpecification

from osc_validation.generation import (
    FollowTrajectoryTeleportXoscRequest,
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
    build_follow_trajectory_teleport_xosc,
)
from osc_validation.reference import (
    FollowTrajectoryTeleportReferenceRequest,
    build_follow_trajectory_teleport_reference_trace,
)


@dataclass(frozen=True)
class FollowTrajectoryTeleportCaseSpec:
    output_xosc_path: Path
    output_reference_channel_spec: ChannelSpecification
    actor: TrajectoryInterpolationActor
    init_pose: TrajectoryInterpolationVertex
    action_start_time_s: float
    stop_time_s: float
    sample_period_s: float
    road_network_path: Path | None = None
    host_vehicle_id: int | None = None


@dataclass(frozen=True)
class FollowTrajectoryTeleportCaseResult:
    xosc_path: Path
    reference_channel_spec: ChannelSpecification


def build_follow_trajectory_teleport_case(
    spec: FollowTrajectoryTeleportCaseSpec,
) -> FollowTrajectoryTeleportCaseResult:
    xosc_result = build_follow_trajectory_teleport_xosc(
        FollowTrajectoryTeleportXoscRequest(
            output_xosc_path=spec.output_xosc_path,
            actor=spec.actor,
            init_pose=spec.init_pose,
            action_start_time_s=spec.action_start_time_s,
            stop_time_s=spec.stop_time_s,
            road_network_path=spec.road_network_path,
        )
    )
    reference_channel_spec = build_follow_trajectory_teleport_reference_trace(
        FollowTrajectoryTeleportReferenceRequest(
            output_channel_spec=spec.output_reference_channel_spec,
            actor=spec.actor,
            init_pose=spec.init_pose,
            action_start_time_s=spec.action_start_time_s,
            stop_time_s=spec.stop_time_s,
            sample_period_s=spec.sample_period_s,
            host_vehicle_id=spec.host_vehicle_id,
        )
    )
    return FollowTrajectoryTeleportCaseResult(
        xosc_path=xosc_result.xosc_path,
        reference_channel_spec=reference_channel_spec,
    )
