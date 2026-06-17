from pathlib import Path
from typing import Callable

import pytest
from osi_utilities import ChannelSpecification

from osc_validation.assertions import assert_no_osc_engine_errors
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.generation import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from osc_validation.metrics import ObjectStateMetric
from osc_validation.oracles import (
    FollowTrajectoryTeleportCaseSpec,
    build_follow_trajectory_teleport_case,
)


@pytest.fixture(scope="module")
def odr_file(builtin_data_path):
    provider = BuiltinDataProvider(builtin_data_path)
    yield provider.ensure_data_path("xodr_example/map.xodr")
    provider.cleanup()


def _actor() -> TrajectoryInterpolationActor:
    return TrajectoryInterpolationActor(
        entity_ref="Ego",
        object_id=1,
        vertices=[
            TrajectoryInterpolationVertex(
                time_s=0.0,
                x=-290.0,
                y=-60.0,
                z=0.0,
            ),
            TrajectoryInterpolationVertex(
                time_s=2.0,
                x=-285.0,
                y=-60.0,
                z=0.0,
            ),
            TrajectoryInterpolationVertex(
                time_s=4.0,
                x=-285.0,
                y=-55.0,
                z=0.0,
            ),
        ],
    )


def _off_trajectory_init_pose() -> TrajectoryInterpolationVertex:
    return TrajectoryInterpolationVertex(
        time_s=0.0,
        x=-300.0,
        y=-60.0,
        z=0.0,
    )


@pytest.mark.validation_category("trajectory")
@pytest.mark.validation_feature("FollowTrajectoryAction TimeReference")
@pytest.mark.parametrize(
    ("case_name", "action_start_time_s"),
    [
        ("exact_trajectory_point", 2.0),
        ("between_trajectory_points", 1.0),
    ],
)
def test_follow_trajectory_position_mode_teleports_to_current_trajectory_time(
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    case_name: str,
    action_start_time_s: float,
):
    """
    OpenSCENARIO feature: FollowTrajectoryAction, position mode, absolute TimeReference.

    Validates that a FollowTrajectoryAction with Position mode and an absolute
    TimeReference at the beginning of the trajectory teleports the actor to the
    correct trajectory position when the action starts later, even if the
    initial pose is off the trajectory. This checks both an exact trajectory
    point timestamp and a timestamp interpolated between trajectory vertices.

    Validates parts of the edge case specified in OpenSCENARIO v1.4.0, section
    6.9.3.
    """

    rate = 1.0
    actor = _actor()
    case_result = build_follow_trajectory_teleport_case(
        FollowTrajectoryTeleportCaseSpec(
            output_xosc_path=tmp_path / f"follow_trajectory_teleport_{case_name}.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / f"reference_follow_trajectory_teleport_{case_name}.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace for FollowTrajectoryAction teleport validation"
                },
            ),
            actor=actor,
            init_pose=_off_trajectory_init_pose(),
            action_start_time_s=action_start_time_s,
            stop_time_s=4.0,
            sample_period_s=rate,
            road_network_path=odr_file,
            host_vehicle_id=actor.object_id,
        )
    )

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=case_result.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / f"tool_trace_follow_trajectory_teleport_{case_name}.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool trace for FollowTrajectoryAction teleport validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)

    metric_result = ObjectStateMetric().compute(
        reference_channel_spec=case_result.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=actor.object_id,
        match_mode="closest_initial_xy",
        ignore_first_speed_sample=True,
    )
    assert metric_result.sample_count == 5, "Trace should have 5 samples at 1 Hz from 0s to 4s inclusive"
    assert metric_result.max_time_error <= 0.01, "Trace should have max time error <= 0.01s"
    assert metric_result.max_xy_error < 0.1, "Trace should have max XY error < 0.1m"
    assert metric_result.max_yaw_error < 0.01, "Trace should have max yaw error < 0.01 rad"
    assert metric_result.max_pitch_error < 0.01, "Trace should have max pitch error < 0.01 rad"
    assert metric_result.max_roll_error < 0.01, "Trace should have max roll error < 0.01 rad"
    assert metric_result.max_dimension_error < 0.01, "Trace should have max dimension error < 0.01m"
