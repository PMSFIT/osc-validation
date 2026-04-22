import logging
import math
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import pytest

from osc_validation.dataproviders import BuiltinDataProvider, DownloadDataProvider
from osc_validation.generation import (
    SpeedTriggerSpec,
    TriggerTransformRequest,
    apply_trigger_transform,
    build_trace_with_calculated_kinematics,
    osi2osc,
)
from osc_validation.generation.trigger_transforms.speed import find_speed_activation_point
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric
from osi_utilities import ChannelSpecification, open_channel


"""
Lichtblick User Script:

import { Input, Message } from "./types";

type Output = {
  speed: number;
  max_speed: number;
};

export const inputs = ["tool_trace_speed_start_trigger"];

export const output = "tool";
let maxSpeed = 0;

export default function script(
  event: Input<"tool_trace_speed_start_trigger">,
): Output {
  const obj = event.message.global_ground_truth.moving_object?.[0];

  if (!obj?.base?.velocity) {
    return { speed: 0, max_speed: maxSpeed };
  }

  const v = obj.base.velocity;

  const speed = Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z) * 3.6;

  // update max
  if (speed > maxSpeed) {
    maxSpeed = speed;
  }

  return {
    speed: speed,
    max_speed: maxSpeed,
  };
}

"""


"""
Lichtblick User Script:

import { Input, Message } from "./types";

type Output = {
  speed: number;
  max_speed: number;
};

export const inputs = ["tool_trace_speed_start_trigger"];

export const output = "tool";
let maxSpeed = 0;

export default function script(
  event: Input<"tool_trace_speed_start_trigger">,
): Output {
  const obj = event.message.global_ground_truth.moving_object?.[0];

  if (!obj?.base?.velocity) {
    return { speed: 0, max_speed: maxSpeed };
  }

  const v = obj.base.velocity;

  const speed = Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z) * 3.6;

  // update max
  if (speed > maxSpeed) {
    maxSpeed = speed;
  }

  return {
    speed: speed,
    max_speed: maxSpeed,
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


def _max_speed_for_object(channel_spec: ChannelSpecification, object_id: int) -> float:
    with open_channel(channel_spec) as reader:
        max_speed = 0.0
        for msg in reader:
            moving_objects = (
                msg.global_ground_truth.moving_object
                if hasattr(msg, "global_ground_truth")
                else msg.moving_object
            )
            target = next((mo for mo in moving_objects if mo.id.value == object_id), None)
            if target is None:
                raise KeyError(f"Object ID {object_id} not found in one or more frames.")
            speed = math.hypot(target.base.velocity.x, target.base.velocity.y)
            if speed > max_speed:
                max_speed = speed
        return max_speed


def _run_speed_start_trigger_case(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    condition_delay_s: float = 0.0,
    moving_object_id: int = 2,                  # Moving object to be evaluated for trigger activation and trajectory alignment by this test case
    trigger_object_id: int = 1,                 # Triggering object whose speed is evaluated against the trigger condition
    trigger_speed_mps: float = 50 / 3.6,        # Triggering speed
    post_trigger_guard_time_s: float = 0.05,    # Tolerance parameter to account for small scenario engine discrepancies in the exact activation point of the trigger
    max_alignment_lag_frames: int = 1,          # Maximum lag (+/-) between the tool trajectory and reference trajectory to still be considered valid
    rate: float = 0.05,
    tolerance: float = 0.25,
):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    activation_frame_offset = 1                 # Number of frames for the triggered event to activate after the speed threshold is crossed in the reference trace
    case_name = "speed_start_trigger"
    if condition_delay_s > 0:
        case_name = f"{case_name}_delay_{condition_delay_s:g}s"

    raw_reference_channel_spec = ChannelSpecification(osi_trace, message_type="SensorView")
    reference_trace_channel_spec = build_trace_with_calculated_kinematics(
        input_channel_spec=raw_reference_channel_spec,
        output_channel_spec=ChannelSpecification(
            path=tmp_path / f"reference_with_kinematics_{case_name}.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Reference trace with calculated velocity and acceleration for speed trigger validation"
            },
        ),
    )

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
                path=tmp_path / f"reference_{case_name}_comparison.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace with speed start trigger applied"
                },
            ),
            spec=SpeedTriggerSpec(
                trigger_entity_ref="Ego",
                target_event_name=f"osi_moving_object_{moving_object_id}_maneuver_event",
                condition_name=f"speed_trigger_object{moving_object_id}_start",
                trigger_speed_mps=trigger_speed_mps,
                trigger_object_id=trigger_object_id,
                triggered_object_id=moving_object_id,
                trigger_rule="greaterOrEqual",
                condition_delay_s=condition_delay_s,
                activation_frame_offset=activation_frame_offset,
            ),
            init_pose_policy="close_to_trajectory_start", # place at initial trajectory position to prevent unintended large initial speed through teleportation
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
                "net.asam.osi.trace.channel.description": "Tool-generated trace for speed start trigger validation"
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
        result_file=tmp_path / f"trajectory_alignment_similarity_report_{case_name}.txt",
        start_time=find_speed_activation_point(
            input_channel_spec=reference_trace_channel_spec,
            trigger_object_id=trigger_object_id,
            trigger_speed_mps=trigger_speed_mps,
            trigger_rule="greaterOrEqual",
        ).time_s + condition_delay_s + post_trigger_guard_time_s,
        time_tolerance=0.01,
        lag_scan_max_frames=max_alignment_lag_frames,
    )

    assert abs(best_lag_frames) <= max_alignment_lag_frames
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance


@pytest.mark.trajectory
def test_speed_start_trigger_activates_target_actor(
    osi_trace: Path,
    odr_file: Path,
    yaml_ruleset: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
):
    _run_speed_start_trigger_case(
        osi_trace=osi_trace,
        odr_file=odr_file,
        generate_tool_trace=generate_tool_trace,
        tmp_path=tmp_path,
    )
