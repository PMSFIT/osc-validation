from pathlib import Path
from typing import Callable

import pytest
from osi_utilities import ChannelSpecification

from osc_validation.assertions import assert_no_osc_engine_errors
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.metrics import ObjectStateMetric
from osc_validation.oracles import (
    InitActionCaseSpec,
    InitActionOracleActor,
    build_init_add_entity_action_case,
    build_init_speed_action_case,
    build_init_teleport_action_case,
)


@pytest.fixture(scope="module")
def odr_file(builtin_data_path):
    provider = BuiltinDataProvider(builtin_data_path)
    yield provider.ensure_data_path("xodr_example/map.xodr")
    provider.cleanup()


def _base_actor(
    speed_mps: float | None = None,
    yaw: float = 0.0,
    pitch: float = 0.0,
    roll: float = 0.0,
) -> InitActionOracleActor:
    return InitActionOracleActor(
        entity_ref="Ego",
        object_id=1,
        x=-290.0,
        y=-60.0,
        z=0.7015,
        yaw=yaw,
        bounding_box_center_x=2.0,
        bounding_box_center_y=0.0,
        bounding_box_center_z=0.75,
        pitch=pitch,
        roll=roll,
        speed_mps=speed_mps,
    )


def _compute_object_state_metric(
    reference_channel_spec: ChannelSpecification,
    tool_channel_spec: ChannelSpecification,
    moving_object_id: int,
):
    return ObjectStateMetric().compute(
        reference_channel_spec=reference_channel_spec,
        tool_channel_spec=tool_channel_spec,
        moving_object_id=moving_object_id,
        match_mode="closest_initial_xy",
        ignore_first_speed_sample=True,
    )


def test_init_teleport_action_places_actor_at_expected_pose(
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
):
    rate = 0.05
    case_result = build_init_teleport_action_case(
        InitActionCaseSpec(
            output_xosc_path=tmp_path / "init_teleport_action.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_init_teleport_action.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace for Init TeleportAction validation"
                },
            ),
            actors=[_base_actor(yaw=0.5, pitch=0.3, roll=-0.2)],
            duration_s=0.5,
            sample_period_s=rate,
            road_network_path=odr_file,
        )
    )

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=case_result.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_init_teleport_action.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool trace for Init TeleportAction validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)

    metric_result = _compute_object_state_metric(
        reference_channel_spec=case_result.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=1,
    )
    assert metric_result.max_time_error <= 0.01
    assert metric_result.max_xy_error < 0.1
    assert metric_result.max_yaw_error < 0.01
    assert metric_result.max_pitch_error < 0.01
    assert metric_result.max_roll_error < 0.01
    assert metric_result.max_orientation_error < 0.01


def test_init_add_entity_action_places_actor_at_expected_pose(
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
):
    rate = 0.05
    case_result = build_init_add_entity_action_case(
        InitActionCaseSpec(
            output_xosc_path=tmp_path / "init_add_entity_action.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_init_add_entity_action.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace for Init AddEntityAction validation"
                },
            ),
            actors=[_base_actor(yaw=0.5, pitch=0.3, roll=-0.2)],
            duration_s=0.5,
            sample_period_s=rate,
            road_network_path=odr_file,
        )
    )

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=case_result.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_init_add_entity_action.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool trace for Init AddEntityAction validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)

    metric_result = _compute_object_state_metric(
        reference_channel_spec=case_result.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=1,
    )
    assert metric_result.max_time_error <= 0.01
    assert metric_result.max_xy_error < 0.1
    assert metric_result.max_yaw_error < 0.01
    assert metric_result.max_pitch_error < 0.01
    assert metric_result.max_roll_error < 0.01
    assert metric_result.max_orientation_error < 0.01


def test_init_speed_action_sets_expected_motion(
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
):
    rate = 0.05
    speed_mps = 5.0
    case_result = build_init_speed_action_case(
        InitActionCaseSpec(
            output_xosc_path=tmp_path / "init_speed_action.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_init_speed_action.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace for Init SpeedAction validation"
                },
            ),
            actors=[_base_actor(speed_mps=speed_mps)],
            duration_s=0.5,
            sample_period_s=rate,
            road_network_path=odr_file,
        )
    )

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=case_result.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_init_speed_action.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool trace for Init SpeedAction validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)

    metric_result = _compute_object_state_metric(
        reference_channel_spec=case_result.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=1,
    )
    assert metric_result.max_time_error <= 0.01
    assert metric_result.max_planar_speed_error < 0.75
