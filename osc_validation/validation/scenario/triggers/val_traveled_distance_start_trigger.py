from pathlib import Path
from typing import Callable
import logging

from osi_utilities import ChannelSpecification
import pytest

from osc_validation.assertions import assert_no_osc_engine_errors
from osc_validation.features.triggers.traveled_distance.case import (
    prepare_traveled_distance_trigger_case,
)
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric


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
@pytest.mark.validation_feature("TraveledDistanceCondition")
@pytest.mark.parametrize(
    "moving_object_id", [2]
)  # moving object to be evaluated for trigger activation and trajectory alignment
@pytest.mark.parametrize(
    "trigger_object_id", [1]
)  # moving object to be triggered for traveled distance trigger condition
@pytest.mark.parametrize("trigger_distance_m", [55.0])
@pytest.mark.parametrize(
    "activation_frame_offset", [1]
)  # It should take one frame for the triggered event to activate after the distance threshold is crossed
@pytest.mark.parametrize("rate", [0.05])
@pytest.mark.parametrize("tolerance", [0.2])
def test_traveled_distance_start_trigger_activates_target_actor(
    scenario_contract,
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_distance_m: float,
    activation_frame_offset: int,
    rate: float,
    tolerance: float,
):
    """
    OpenSCENARIO feature: StartTrigger using TraveledDistanceCondition.

    Activates a target actor once the triggering object has traveled the configured
    distance. The post-trigger trajectory is compared with a transformed reference
    trace after the trigger edge.
    """

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    case = prepare_traveled_distance_trigger_case(
        contract=scenario_contract,
        osi_trace=osi_trace,
        odr_file=odr_file,
        output_dir=tmp_path,
        moving_object_id=moving_object_id,
        trigger_object_id=trigger_object_id,
        trigger_distance_m=trigger_distance_m,
        activation_frame_offset=activation_frame_offset,
    )
    osc_path = case.xosc_path

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_traveled_distance_start_trigger.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for traveled-distance start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)
    assert_osi_compliance(
        tool_trace_channel_spec,
        result_file=tmp_path / "qc_result_traveled_distance_start_trigger.xqar",
    )

    scoring_start_time_s = case.activation_time_s + rate
    area, cl, mae, best_lag_frames = TrajectoryAlignmentSimilarityMetric().compute(
        reference_channel_spec=case.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        result_file=tmp_path / "trajectory_alignment_similarity_report.txt",
        start_time=scoring_start_time_s,
        time_tolerance=0.01,
        lag_scan_max_frames=2,
    )

    assert abs(best_lag_frames) <= 2
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
