"""Case preparation for time to collision triggers."""

from pathlib import Path

from osi_utilities import ChannelSpecification, open_channel

from osc_validation.features.shared.init_pose.models import InitPoseOverride
from osc_validation.features.triggers.models import (
    TriggerCaseResult,
    TimeToCollisionPositionTriggerSpec,
    TriggerTransformRequest,
)
from osc_validation.features.triggers.transform import apply_trigger_transform
from .transform import find_ttc_position_activation_point
from osc_validation.generation.osi2osc import osi2osc
from osc_validation.reference.trace_kinematics import (
    build_trace_with_calculated_kinematics,
)
from osc_validation.versioning import ScenarioContract


def _get_object_position_at_last_frame(
    channel_spec: ChannelSpecification, object_id: int
) -> tuple[float, float, float]:
    with open_channel(channel_spec) as reader:
        messages = list(reader)
        if not messages:
            raise RuntimeError("Input trace has no messages.")
        last = messages[-1]
        moving_objects = (
            last.global_ground_truth.moving_object
            if hasattr(last, "global_ground_truth")
            else last.moving_object
        )
        target = next((mo for mo in moving_objects if mo.id.value == object_id), None)
        if target is None:
            raise KeyError(f"Object ID {object_id} not found in last frame.")
        return (
            target.base.position.x,
            target.base.position.y,
            target.base.position.z,
        )


def prepare_time_to_collision_trigger_case(
    *,
    contract: ScenarioContract,
    osi_trace: Path,
    odr_file: Path,
    output_dir: Path,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_ttc_s: float,
    activation_frame_offset: int,
) -> TriggerCaseResult:
    raw_reference_channel_spec = ChannelSpecification(
        osi_trace, message_type="SensorView"
    )
    reference_trace_channel_spec = build_trace_with_calculated_kinematics(
        input_channel_spec=raw_reference_channel_spec,
        output_channel_spec=ChannelSpecification(
            path=output_dir / "reference_with_kinematics_for_ttc.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Reference trace with calculated velocity and acceleration for TTC trigger validation"
            },
        ),
    )
    target_position_x, target_position_y, target_position_z = (
        _get_object_position_at_last_frame(
            reference_trace_channel_spec, trigger_object_id
        )
    )
    osc_path = osi2osc(
        contract=contract,
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=output_dir / "osi2osc_ttc_start_trigger.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=output_dir / "reference_ttc_start_trigger_comparison.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace with TTC start trigger applied"
                },
            ),
            spec=TimeToCollisionPositionTriggerSpec(
                trigger_entity_ref="Ego",
                target_event_name=f"osi_moving_object_{moving_object_id}_maneuver_event",
                condition_name=f"ttc_trigger_object{moving_object_id}_start",
                trigger_ttc_s=trigger_ttc_s,
                trigger_object_id=trigger_object_id,
                triggered_object_id=moving_object_id,
                target_position_x=target_position_x,
                target_position_y=target_position_y,
                target_position_z=target_position_z,
                trigger_rule="lessOrEqual",
                activation_frame_offset=activation_frame_offset,
            ),
            init_pose_policy="explicit_overrides",  # need explicit override because osi2osc default init position (0,0,0) is not on road (gtgen doesn't support placing objects outside of road)
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
    activation_time_s = find_ttc_position_activation_point(
        input_channel_spec=reference_trace_channel_spec,
        trigger_object_id=trigger_object_id,
        target_position_x=target_position_x,
        target_position_y=target_position_y,
        trigger_ttc_s=trigger_ttc_s,
        trigger_rule="lessOrEqual",
    ).time_s
    return TriggerCaseResult(
        osc_path, transform_result.reference_channel_spec, activation_time_s
    )
