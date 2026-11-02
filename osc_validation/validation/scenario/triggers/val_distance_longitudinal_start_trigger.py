from pathlib import Path
from typing import Callable
import logging

from osi_utilities import ChannelSpecification
import pytest

from osc_validation.assertions import assert_no_osc_engine_errors
from osc_validation.cases.triggers.distance_to_position.case import (
    prepare_distance_longitudinal_trigger_case,
)
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric


""" 
Lichtblick User Script:

import { Input, Message } from "./types";

type Output = {
  x1: number;
  x2: number;
  distance: number;
};

export const inputs = ["<INSERT_TOOL_TRACE_TOPIC_NAME>"];

export const output = "test_topic";

let x1 = 0;
let x2 = -275.37930040547195; // Hardcoded target_position_x used in the trigger spec of the test.

export default function script(
  event: Input<"<INSERT_TOOL_TRACE_TOPIC_NAME>">,
): Output {
  const msg = event.message;
  const obj1 = msg.global_ground_truth.moving_object?.[0];
  x1 = obj1.base.position.x;

  return {
    x1: x1,
    x2: x2,
    distance: x2 - x1,
  };
}

"""


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
@pytest.mark.validation_feature("DistanceCondition longitudinal")
def test_distance_longitudinal_start_trigger_activates_target_actor(
    scenario_contract,
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
):
    """
    OpenSCENARIO feature: DistanceCondition with relativeDistanceType longitudinal.

    Activates a target actor when the ego object is within the configured
    longitudinal distance of a target position. The target actor's post-trigger
    trajectory is compared with the transformed reference trace.
    """

    condition_delay_s = 0.0
    moving_object_id = 2
    trigger_object_id = 1
    trigger_distance_m = 10.0
    post_trigger_guard_time_s = 0.05
    max_alignment_lag_frames = 2
    rate = 0.05
    tolerance = 0.1
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    activation_frame_offset = 1  # Number of frames for the triggered event to activate after the distance threshold is crossed
    target_position_x, target_position_y, target_position_z = (
        -275.37930040547195,
        -52.90668516705058,
        0.29707853723620486,
    )
    case_name = "distance_longitudinal_start_trigger"
    if condition_delay_s > 0:
        case_name = f"{case_name}_delay_{condition_delay_s:g}s"
    case = prepare_distance_longitudinal_trigger_case(
        contract=scenario_contract,
        osi_trace=osi_trace,
        odr_file=odr_file,
        output_dir=tmp_path,
        moving_object_id=moving_object_id,
        trigger_object_id=trigger_object_id,
        trigger_distance_m=trigger_distance_m,
        activation_frame_offset=activation_frame_offset,
        condition_delay_s=condition_delay_s,
        target_position_x=target_position_x,
        target_position_y=target_position_y,
        target_position_z=target_position_z,
        case_name=case_name,
    )
    osc_path = case.xosc_path

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / f"tool_trace_{case_name}.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for longitudinal distance start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)
    assert_osi_compliance(
        tool_trace_channel_spec,
        result_file=tmp_path / f"qc_result_{case_name}.xqar",
    )

    scoring_start_time_s = (
        case.activation_time_s + condition_delay_s + post_trigger_guard_time_s
    )
    area, cl, mae, best_lag_frames = TrajectoryAlignmentSimilarityMetric().compute(
        reference_channel_spec=case.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
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
