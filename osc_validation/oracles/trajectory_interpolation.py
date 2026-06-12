from dataclasses import dataclass
from pathlib import Path

from osi_utilities import ChannelSpecification

from osc_validation.generation import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationXoscRequest,
    build_trajectory_interpolation_xosc,
)
from osc_validation.reference import (
    TrajectoryInterpolationReferenceMode,
    TrajectoryInterpolationReferenceRequest,
    build_trajectory_interpolation_reference_trace,
)


@dataclass(frozen=True)
class TrajectoryInterpolationCaseSpec:
    output_xosc_path: Path
    output_reference_channel_spec: ChannelSpecification
    actor: TrajectoryInterpolationActor
    stop_time_s: float
    sample_period_s: float
    road_network_path: Path | None = None
    host_vehicle_id: int | None = None
    interpolation_mode: TrajectoryInterpolationReferenceMode = "linear_position"
    initial_speed_mps: float = 0.0


@dataclass(frozen=True)
class TrajectoryInterpolationCaseResult:
    xosc_path: Path
    reference_channel_spec: ChannelSpecification


def build_trajectory_interpolation_case(
    spec: TrajectoryInterpolationCaseSpec,
) -> TrajectoryInterpolationCaseResult:
    xosc_result = build_trajectory_interpolation_xosc(
        TrajectoryInterpolationXoscRequest(
            output_xosc_path=spec.output_xosc_path,
            actor=spec.actor,
            stop_time_s=spec.stop_time_s,
            road_network_path=spec.road_network_path,
        )
    )
    reference_channel_spec = build_trajectory_interpolation_reference_trace(
        TrajectoryInterpolationReferenceRequest(
            output_channel_spec=spec.output_reference_channel_spec,
            actor=spec.actor,
            sample_period_s=spec.sample_period_s,
            host_vehicle_id=(
                spec.host_vehicle_id
                if spec.host_vehicle_id is not None
                else spec.actor.object_id
            ),
            interpolation_mode=spec.interpolation_mode,
            initial_speed_mps=spec.initial_speed_mps,
        )
    )
    return TrajectoryInterpolationCaseResult(
        xosc_path=xosc_result.xosc_path,
        reference_channel_spec=reference_channel_spec,
    )
