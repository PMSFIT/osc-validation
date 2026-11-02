from pathlib import Path
from typing import Callable
import logging

from osi_utilities import ChannelSpecification
import pytest

from osc_validation.assertions import assert_no_osc_engine_errors
from osc_validation.cases.triggers.simulation_time.case import (
    prepare_simulation_time_trigger_case,
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
@pytest.mark.validation_feature("SimulationTimeCondition")
@pytest.mark.parametrize("moving_object_id", [1, 2])
@pytest.mark.parametrize("ego_object_id", [1])
@pytest.mark.parametrize("init_pose_object_id", [2])
@pytest.mark.parametrize("trigger_delay", [10.0])
@pytest.mark.parametrize(
    "activation_frame_offset", [0]
)  # The trigger should activate immediately when the simulation time condition is met
@pytest.mark.parametrize(
    "max_alignment_lag_frames", [2]
)  # Allows small simulator-dependent differences in the frame where triggered actions become visible after condition activation.
@pytest.mark.parametrize("rate", [0.05])
@pytest.mark.parametrize("tolerance", [2e-1])
def test_simulation_time_start_trigger_delays_actor_trajectory(
    scenario_contract,
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
    moving_object_id: int,
    ego_object_id: int,
    init_pose_object_id: int,
    trigger_delay: float,
    activation_frame_offset: int,
    max_alignment_lag_frames: int,
    rate: float,
    tolerance: float,
):
    """
    OpenSCENARIO feature: StartTrigger using SimulationTimeCondition.

    Validates delayed Event StartTrigger (SimulationTimeCondition) behavior
    using trajectory alignment similarity.
    """

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    case = prepare_simulation_time_trigger_case(
        contract=scenario_contract,
        osi_trace=osi_trace,
        odr_file=odr_file,
        output_dir=tmp_path,
        moving_object_id=moving_object_id,
        ego_object_id=ego_object_id,
        init_pose_object_id=init_pose_object_id,
        trigger_delay=trigger_delay,
        activation_frame_offset=activation_frame_offset,
    )
    osc_path = case.xosc_path

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_simulation_time_start_trigger.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for simulation-time start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)

    assert_osi_compliance(
        channel_spec=tool_trace_channel_spec,
        result_file=tmp_path / "qc_result_trigger_delay.xqar",
        output_config=tmp_path / "qc_config_trigger_delay.xml",
    )

    scoring_start_time_s = case.activation_time_s + rate
    area, cl, mae, _best_lag_frames = TrajectoryAlignmentSimilarityMetric().compute(
        reference_channel_spec=case.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        result_file=tmp_path
        / f"trajectory_alignment_similarity_report_{moving_object_id}.txt",
        start_time=scoring_start_time_s,
        time_tolerance=0.01,
        lag_scan_max_frames=max_alignment_lag_frames,
    )

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
