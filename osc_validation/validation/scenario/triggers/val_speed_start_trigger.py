import logging
from pathlib import Path
from typing import Callable

import pytest
from osi_utilities import ChannelSpecification

from osc_validation.assertions import assert_no_osc_engine_errors

from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric
from osc_validation.features.triggers.speed.case import prepare_speed_trigger_case


@pytest.fixture(
    scope="module",
    params=[
        "simple_trajectories/20240603T152322.095000Z_sv_370_3200_618_dronetracker_135_swerve.mcap"
    ],
)
def osi_trace(request, builtin_data_path):
    provider = BuiltinDataProvider(builtin_data_path)
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.fixture(scope="module")
def odr_file(request):
    return request.getfixturevalue("osi_trace").with_suffix(".xodr")


@pytest.mark.osc_versions("1.3.0", "1.3.1", "1.4.0")
@pytest.mark.validation_category("trigger")
@pytest.mark.validation_feature("SpeedCondition")
def test_speed_start_trigger_activates_target_actor(
    scenario_contract,
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
):
    """
    OpenSCENARIO feature: StartTrigger using SpeedCondition with a rising edge.

    Activates a target actor when the trigger object's speed crosses the configured
    threshold upward. The post-activation trajectory is compared with a reference
    trace that includes calculated kinematics.
    """

    # Score after activation plus a guard interval, allowing two frames of lag.
    max_alignment_lag_frames = 2
    tolerance = 0.25
    logging.getLogger().setLevel(logging.INFO)
    case_name = "speed_start_trigger"
    case = prepare_speed_trigger_case(
        contract=scenario_contract,
        osi_trace=osi_trace,
        odr_file=odr_file,
        output_dir=tmp_path,
        case_name=case_name,
        moving_object_id=2,
        trigger_object_id=1,
        trigger_speed_mps=50 / 3.6,
        condition_edge="rising",
        condition_delay_s=0.0,
        activation_frame_offset=1,
    )
    tool_trace = generate_tool_trace(
        osc_path=case.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / f"tool_trace_{case_name}.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for speed start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=0.05,
    )
    assert_no_osc_engine_errors(tool_trace)
    assert_osi_compliance(
        tool_trace,
        result_file=tmp_path / f"qc_result_{case_name}.xqar",
    )
    scoring_start_time_s = case.activation_time_s + 0.0 + 0.05
    area, cl, mae, best_lag_frames = TrajectoryAlignmentSimilarityMetric().compute(
        reference_channel_spec=case.reference_channel_spec,
        tool_channel_spec=tool_trace,
        moving_object_id=2,
        result_file=tmp_path
        / f"trajectory_alignment_similarity_report_{case_name}.txt",
        start_time=scoring_start_time_s,
        time_tolerance=0.01,
        lag_scan_max_frames=max_alignment_lag_frames,
    )

    assert abs(best_lag_frames) <= max_alignment_lag_frames
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance


@pytest.mark.osc_versions("1.3.0", "1.3.1", "1.4.0")
@pytest.mark.validation_category("trigger")
@pytest.mark.validation_feature("SpeedCondition")
def test_speed_start_trigger_condition_edge_none_activates_when_initially_true(
    scenario_contract,
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
):
    """
    OpenSCENARIO feature: SpeedCondition with conditionEdge set to none.

    Checks that a speed condition can activate when it is already true at the start
    of the scenario. The trigger threshold is zero, so activation depends on the
    condition state rather than an edge transition.
    """

    # Score after activation plus a guard interval, allowing two frames of lag.
    max_alignment_lag_frames = 2
    tolerance = 0.25
    logging.getLogger().setLevel(logging.INFO)
    case_name = "speed_start_trigger_none_edge"
    case = prepare_speed_trigger_case(
        contract=scenario_contract,
        osi_trace=osi_trace,
        odr_file=odr_file,
        output_dir=tmp_path,
        case_name=case_name,
        moving_object_id=2,
        trigger_object_id=1,
        trigger_speed_mps=0.0,
        condition_edge="none",
        condition_delay_s=0.0,
        activation_frame_offset=1,
    )
    tool_trace = generate_tool_trace(
        osc_path=case.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / f"tool_trace_{case_name}.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for speed start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=0.05,
    )
    assert_no_osc_engine_errors(tool_trace)
    assert_osi_compliance(
        tool_trace,
        result_file=tmp_path / f"qc_result_{case_name}.xqar",
    )
    scoring_start_time_s = case.activation_time_s + 0.0 + 0.05
    area, cl, mae, best_lag_frames = TrajectoryAlignmentSimilarityMetric().compute(
        reference_channel_spec=case.reference_channel_spec,
        tool_channel_spec=tool_trace,
        moving_object_id=2,
        result_file=tmp_path
        / f"trajectory_alignment_similarity_report_{case_name}.txt",
        start_time=scoring_start_time_s,
        time_tolerance=0.01,
        lag_scan_max_frames=max_alignment_lag_frames,
    )

    assert abs(best_lag_frames) <= max_alignment_lag_frames
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance


@pytest.mark.osc_versions("1.3.0", "1.3.1", "1.4.0")
@pytest.mark.validation_category("trigger")
@pytest.mark.validation_feature("SpeedCondition")
def test_speed_start_trigger_condition_edge_falling_activates(
    scenario_contract,
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
):
    """
    OpenSCENARIO feature: SpeedCondition with conditionEdge set to falling.

    Activates a target actor when the triggering object's speed crosses the
    configured threshold downward. The resulting trajectory is compared with the
    expected triggered reference behavior.
    """

    # Score after activation plus a guard interval, allowing two frames of lag.
    max_alignment_lag_frames = 2
    tolerance = 0.25
    logging.getLogger().setLevel(logging.INFO)
    case_name = "speed_start_trigger_falling_edge"
    case = prepare_speed_trigger_case(
        contract=scenario_contract,
        osi_trace=osi_trace,
        odr_file=odr_file,
        output_dir=tmp_path,
        case_name=case_name,
        moving_object_id=2,
        trigger_object_id=1,
        trigger_speed_mps=20 / 3.6,
        condition_edge="falling",
        condition_delay_s=0.0,
        activation_frame_offset=1,
    )
    tool_trace = generate_tool_trace(
        osc_path=case.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / f"tool_trace_{case_name}.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for speed start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=0.05,
    )
    assert_no_osc_engine_errors(tool_trace)
    assert_osi_compliance(
        tool_trace,
        result_file=tmp_path / f"qc_result_{case_name}.xqar",
    )
    scoring_start_time_s = case.activation_time_s + 0.0 + 0.05
    area, cl, mae, best_lag_frames = TrajectoryAlignmentSimilarityMetric().compute(
        reference_channel_spec=case.reference_channel_spec,
        tool_channel_spec=tool_trace,
        moving_object_id=2,
        result_file=tmp_path
        / f"trajectory_alignment_similarity_report_{case_name}.txt",
        start_time=scoring_start_time_s,
        time_tolerance=0.01,
        lag_scan_max_frames=max_alignment_lag_frames,
    )

    assert abs(best_lag_frames) <= max_alignment_lag_frames
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
