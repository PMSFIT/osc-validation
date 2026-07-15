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
    FollowTrajectoryFutureTimeReferenceCaseSpec,
    build_follow_trajectory_future_time_reference_case,
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
                time_s=4.0,
                x=-285.0,
                y=-60.0,
                z=0.0,
            ),
            TrajectoryInterpolationVertex(
                time_s=6.0,
                x=-275.0,
                y=-60.0,
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
        yaw=-0.1,
    )


@pytest.mark.validation_category("trajectory")
@pytest.mark.validation_feature("FollowTrajectoryAction TimeReference")
def test_follow_trajectory_future_time_reference_continues_init_speed_until_first_vertex(
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
):
    """
    OpenSCENARIO feature: FollowTrajectoryAction, position mode, absolute future TimeReference.

    Validates that a FollowTrajectoryAction with position mode and an absolute
    TimeReference at the beginning of the trajectory continues at the initial
    speed until the first trajectory vertex time is reached, even if the initial
    pose is off the trajectory. This checks the position-mode branch for an
    absolute future TimeReference; it does not cover relative TimeReference
    settings or followingMode="follow".

    Validates parts of the edge case specified in OpenSCENARIO v1.4.0, section
    6.9.2.
    """

    rate = 1.0
    init_speed_mps = 4.0
    actor = _actor()
    case_result = build_follow_trajectory_future_time_reference_case(
        FollowTrajectoryFutureTimeReferenceCaseSpec(
            output_xosc_path=tmp_path / "follow_trajectory_future_time_reference.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_follow_trajectory_future_time_reference.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace for FollowTrajectoryAction future TimeReference validation"
                },
            ),
            actor=actor,
            init_pose=_off_trajectory_init_pose(),
            init_speed_mps=init_speed_mps,
            action_start_time_s=0.0,
            stop_time_s=6.0,
            sample_period_s=rate,
            road_network_path=odr_file,
            host_vehicle_id=actor.object_id,
        )
    )

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=case_result.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_follow_trajectory_future_time_reference.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool trace for FollowTrajectoryAction future TimeReference validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)
    assert_osi_compliance(
        tool_trace_channel_spec,
        result_file=tmp_path / "qc_result_follow_trajectory_future_time_reference.xqar",
    )

    full_trace_result = ObjectStateMetric().compute(
        reference_channel_spec=case_result.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=actor.object_id,
        match_mode="closest_initial_xy",
        ignore_first_speed_sample=True,
    )
    assert full_trace_result.sample_count == 7, "Full trace should have 7 samples at 1 Hz from 0s to 6s inclusive"
    assert full_trace_result.max_time_error <= 0.01, "Full trace should have max time error <= 0.01s"
    assert full_trace_result.max_xy_error < 0.1, "Full trace should have max XY error < 0.1m"
    assert full_trace_result.max_yaw_error < 0.01, "Full trace should have max yaw error < 0.01 rad"
    assert full_trace_result.max_pitch_error < 0.01, "Full trace should have max pitch error < 0.01 rad"
    assert full_trace_result.max_roll_error < 0.01, "Full trace should have max roll error < 0.01 rad"
    assert full_trace_result.max_dimension_error < 0.01, "Full trace should have max dimension error < 0.01m"

    pre_teleport_result = ObjectStateMetric().compute(
        reference_channel_spec=case_result.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=actor.object_id,
        match_mode="closest_initial_xy",
        ignore_first_speed_sample=True,
        time_range_s=(0.0, 1.0),
    )
    assert pre_teleport_result.sample_count == 2, "Pre-teleport section should have 2 samples"
    assert pre_teleport_result.max_xy_error < 0.1, "Pre-teleport section should have max XY error < 0.1m"
    assert pre_teleport_result.max_planar_speed_error < 0.75, "Pre-teleport section should have max planar speed error < 0.75 m/s"

    teleport_result = ObjectStateMetric().compute(
        reference_channel_spec=case_result.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=actor.object_id,
        match_mode="closest_initial_xy",
        ignore_first_speed_sample=True,
        time_range_s=(4.0, 4.0),
    )
    assert teleport_result.sample_count == 1, "Teleport frame should have 1 sample at the teleport time"
    assert teleport_result.max_xy_error < 0.1, "Teleport frame should have max XY error < 0.1m"
