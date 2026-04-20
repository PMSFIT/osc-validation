import logging
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import pytest

from osc_validation.dataproviders import BuiltinDataProvider, DownloadDataProvider
from osc_validation.generation import (
    DistancePositionTriggerSpec,
    TriggerTransformRequest,
    apply_trigger_transform,
    osi2osc,
)
from osc_validation.generation.init_transforms.models import InitPoseOverride
from osc_validation.generation.trigger_transforms.distance_to_position import find_distance_position_activation_point
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric
from osi_utilities import ChannelSpecification


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
def osi_trace(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.fixture(
    scope="module",
    params=[
        "https://raw.githubusercontent.com/OpenSimulationInterface/qc-osi-trace/refs/heads/main/qc_ositrace/checks/osirules/rulesyml/osi_3_7_0.yml"
    ],
)
def yaml_ruleset(request):
    uri = request.param
    filename = Path(urlparse(uri).path).name
    base_path = Path("download/osirules")
    provider = DownloadDataProvider(uri=uri, base_path=base_path)
    yield provider.ensure_data_path(filename)
    provider.cleanup()


@pytest.fixture(scope="module")
def odr_file(request):
    return request.getfixturevalue("osi_trace").with_suffix(".xodr")


def _run_distance_longitudinal_start_trigger_case(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    condition_delay_s: float = 0.0,
    moving_object_id: int = 2,
    trigger_object_id: int = 1,
    trigger_distance_m: float = 10.0,
    post_trigger_guard_time_s: float = 0.05,   # Tolerance parameter to account for small discrepancies in the exact activation point of the trigger
    max_alignment_lag_frames: int = 1,         # Maximum lag (+/-) between the tool trajectory and reference trajectory to still be considered valid
    rate: float = 0.05,
    tolerance: float = 0.1,
):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    reference_trace_channel_spec = ChannelSpecification(osi_trace, message_type="SensorView")
    activation_frame_offset = 1                 # Number of frames for the triggered event to activate after the distance threshold is crossed
    target_position_x, target_position_y, target_position_z = (
        -275.37930040547195,
        -52.90668516705058,
        0.29707853723620486,
    )
    case_name = "distance_longitudinal_start_trigger"
    if condition_delay_s > 0:
        case_name = f"{case_name}_delay_{condition_delay_s:g}s"

    osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / f"osi2osc_{case_name}.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path
                / f"reference_{case_name}_comparison.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": (
                        "Reference trace with longitudinal distance start trigger applied"
                    )
                },
            ),
            spec=DistancePositionTriggerSpec(
                trigger_entity_ref="Ego",
                target_event_name=f"osi_moving_object_{moving_object_id}_maneuver_event",
                condition_name=f"distance_longitudinal_trigger_object{moving_object_id}_start",
                trigger_distance_m=trigger_distance_m,
                trigger_object_id=trigger_object_id,
                triggered_object_id=moving_object_id,
                target_position_x=target_position_x,
                target_position_y=target_position_y,
                target_position_z=target_position_z,
                relative_distance_type="longitudinal",
                trigger_rule="lessOrEqual",
                condition_delay_s=condition_delay_s,
                activation_frame_offset=activation_frame_offset,
            ),
            init_pose_policy="explicit_overrides", # need explicit override because osi2osc default init position (0,0,0) is not on road (gtgen doesn't support placing objects outside of road)
            init_pose_overrides=[
                InitPoseOverride(
                    entity_ref="Ego",
                    object_id=trigger_object_id,
                    x=-290.0,
                    y=-60.0,
                    z=0.7015,
                    yaw=0.0,
                    pitch=0.0,
                    roll=0.0,
                ),
                InitPoseOverride(
                    entity_ref=f"osi_moving_object_{moving_object_id}",
                    object_id=moving_object_id,
                    x=-280.0,
                    y=-55.0,
                    z=0.7015,
                    yaw=0.0,
                    pitch=0.0,
                    roll=0.0,
                ),
            ],
        )
    )
    osc_path = transform_result.xosc_path

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

    metric = TrajectoryAlignmentSimilarityMetric()
    reference_triggered_channel_spec = transform_result.reference_channel_spec

    area, cl, mae, best_lag_frames = metric.compute(
        reference_channel_spec=reference_triggered_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        result_file=tmp_path
        / f"trajectory_alignment_similarity_report_{case_name}.txt",
        start_time=find_distance_position_activation_point(
            input_channel_spec=reference_trace_channel_spec,
            trigger_object_id=trigger_object_id,
            trigger_distance_m=trigger_distance_m,
            trigger_rule="lessOrEqual",
            target_position_x=target_position_x,
            target_position_y=target_position_y,
            relative_distance_type="longitudinal"
        ).time_s + condition_delay_s + post_trigger_guard_time_s,
        time_tolerance=0.01,
        lag_scan_max_frames=max_alignment_lag_frames,
    )

    assert abs(best_lag_frames) <= max_alignment_lag_frames
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance


@pytest.mark.trajectory
def test_distance_longitudinal_start_trigger_activates_target_actor(
    osi_trace: Path,
    odr_file: Path,
    yaml_ruleset: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
):
    _run_distance_longitudinal_start_trigger_case(
        osi_trace=osi_trace,
        odr_file=odr_file,
        generate_tool_trace=generate_tool_trace,
        tmp_path=tmp_path,
    )
