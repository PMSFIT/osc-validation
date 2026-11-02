"""Prepare the generated scenario and reference for a speed-trigger check."""

from pathlib import Path

from osi_utilities import ChannelSpecification

from osc_validation.features.triggers.models import (
    TriggerCaseResult,
    SpeedTriggerSpec,
    TriggerTransformRequest,
)
from osc_validation.features.triggers.transform import apply_trigger_transform
from .transform import find_speed_activation_point
from osc_validation.generation.osi2osc import osi2osc
from osc_validation.reference.trace_kinematics import (
    build_trace_with_calculated_kinematics,
)
from osc_validation.versioning import ScenarioContract


def prepare_speed_trigger_case(
    *,
    contract: ScenarioContract,
    osi_trace: Path,
    odr_file: Path,
    output_dir: Path,
    case_name: str,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_speed_mps: float,
    condition_edge: str,
    condition_delay_s: float,
    activation_frame_offset: int,
) -> TriggerCaseResult:
    source = build_trace_with_calculated_kinematics(
        input_channel_spec=ChannelSpecification(osi_trace, message_type="SensorView"),
        output_channel_spec=ChannelSpecification(
            path=output_dir / f"reference_with_kinematics_{case_name}.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Reference trace with calculated velocity and acceleration for speed trigger validation"
            },
        ),
    )
    xosc_path = osi2osc(
        contract=contract,
        osi_trace_spec=source,
        path_xosc=output_dir / f"osi2osc_{case_name}.xosc",
        path_xodr=odr_file,
    )
    result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=xosc_path,
            source_reference_channel_spec=source,
            output_xosc_path=xosc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=output_dir / f"reference_{case_name}_comparison.mcap",
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
                condition_edge=condition_edge,
                condition_delay_s=condition_delay_s,
                activation_frame_offset=activation_frame_offset,
            ),
            init_pose_policy="close_to_trajectory_start",
        )
    )
    activation = find_speed_activation_point(
        input_channel_spec=source,
        trigger_object_id=trigger_object_id,
        trigger_speed_mps=trigger_speed_mps,
        trigger_rule="greaterOrEqual",
        condition_edge=condition_edge,
    )
    return TriggerCaseResult(
        result.xosc_path, result.reference_channel_spec, activation.time_s
    )
