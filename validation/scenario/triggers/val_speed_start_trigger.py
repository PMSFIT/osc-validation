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
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric
from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader


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


def _max_speed_for_object(channel_spec: OSIChannelSpecification, object_id: int) -> float:
    with OSIChannelReader.from_osi_channel_specification(channel_spec) as reader:
        max_speed = 0.0
        for msg in reader.get_messages():
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


@pytest.mark.trajectory
@pytest.mark.parametrize("moving_object_id", [2])           # moving object to be evaluated for trigger activation and trajectory alignment
@pytest.mark.parametrize("trigger_object_id", [1])          # moving object to be triggered for speed trigger condition
@pytest.mark.parametrize("trigger_speed_mps", [50 / 3.6])   # triggering speed of the triggered object
@pytest.mark.parametrize("activation_frame_offset", [1])    # It takes one frame for the triggered event to activate after the speed threshold is crossed
@pytest.mark.parametrize("rate", [0.05])
@pytest.mark.parametrize("tolerance", [0.25])
def test_speed_start_trigger_activates_target_actor(
    osi_trace: Path,
    odr_file: Path,
    yaml_ruleset: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_speed_mps: float,
    activation_frame_offset: int,
    rate: float,
    tolerance: float,
):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    raw_reference_channel_spec = OSIChannelSpecification(osi_trace, message_type="SensorView")
    reference_trace_channel_spec = build_trace_with_calculated_kinematics(
        input_channel_spec=raw_reference_channel_spec,
        output_channel_spec=OSIChannelSpecification(
            path=tmp_path / "reference_with_kinematics.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Reference trace with calculated velocity and acceleration for speed trigger validation"
            },
        ),
    )

    osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / "osi2osc_speed_start_trigger.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=OSIChannelSpecification(
                path=tmp_path / "reference_speed_start_trigger_comparison.mcap",
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
                activation_frame_offset=activation_frame_offset,
            ),
        )
    )
    osc_path = transform_result.xosc_path

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=OSIChannelSpecification(
            path=tmp_path / "tool_trace_speed_start_trigger.mcap",
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
        result_file=tmp_path / "trajectory_alignment_similarity_report_speed_start_trigger.txt",
        time_tolerance=0.01,
        lag_scan_max_frames=2,
    )

    assert abs(best_lag_frames) <= 2
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
