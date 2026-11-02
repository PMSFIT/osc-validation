"""Case preparation for distance to position triggers."""

from pathlib import Path

from osi_utilities import ChannelSpecification

from osc_validation.features.shared.init_pose.models import InitPoseOverride
from osc_validation.features.triggers.models import (
    TriggerCaseResult,
    DistancePositionTriggerSpec,
    TriggerTransformRequest,
)
from osc_validation.features.triggers.transform import apply_trigger_transform
from osc_validation.generation.osi2osc import osi2osc
from osc_validation.versioning import ScenarioContract

from .transform import find_distance_position_activation_point


def prepare_distance_longitudinal_trigger_case(
    *,
    contract: ScenarioContract,
    osi_trace: Path,
    odr_file: Path,
    output_dir: Path,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_distance_m: float,
    activation_frame_offset: int,
    condition_delay_s: float,
    target_position_x: float,
    target_position_y: float,
    target_position_z: float,
    case_name: str,
) -> TriggerCaseResult:
    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type="SensorView"
    )
    osc_path = osi2osc(
        contract=contract,
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=output_dir / f"osi2osc_{case_name}.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=output_dir / f"reference_{case_name}_comparison.mcap",
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
    activation_time_s = find_distance_position_activation_point(
        input_channel_spec=reference_trace_channel_spec,
        trigger_object_id=trigger_object_id,
        trigger_distance_m=trigger_distance_m,
        trigger_rule="lessOrEqual",
        target_position_x=target_position_x,
        target_position_y=target_position_y,
        relative_distance_type="longitudinal",
    ).time_s
    return TriggerCaseResult(
        osc_path, transform_result.reference_channel_spec, activation_time_s
    )


def prepare_distance_euclidian_trigger_case(
    *,
    contract: ScenarioContract,
    osi_trace: Path,
    odr_file: Path,
    output_dir: Path,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_distance_m: float,
    activation_frame_offset: int,
    target_position_x: float,
    target_position_y: float,
    target_position_z: float,
) -> TriggerCaseResult:
    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type="SensorView"
    )
    osc_path = osi2osc(
        contract=contract,
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=output_dir / "osi2osc_distance_euclidian_start_trigger.xosc",
        path_xodr=odr_file,
        init_pose_policy="close_to_trajectory_start",
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=output_dir
                / "reference_distance_euclidian_start_trigger_comparison.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace with euclidian distance start trigger applied"
                },
            ),
            spec=DistancePositionTriggerSpec(
                trigger_entity_ref="Ego",
                target_event_name=f"osi_moving_object_{moving_object_id}_maneuver_event",
                condition_name=f"distance_euclidian_trigger_object{moving_object_id}_start",
                trigger_distance_m=trigger_distance_m,
                trigger_object_id=trigger_object_id,
                triggered_object_id=moving_object_id,
                target_position_x=target_position_x,
                target_position_y=target_position_y,
                target_position_z=target_position_z,
                relative_distance_type="euclidianDistance",
                trigger_rule="lessOrEqual",
                activation_frame_offset=activation_frame_offset,
            ),
        )
    )
    osc_path = transform_result.xosc_path
    activation_time_s = find_distance_position_activation_point(
        input_channel_spec=reference_trace_channel_spec,
        trigger_object_id=trigger_object_id,
        trigger_distance_m=trigger_distance_m,
        trigger_rule="lessOrEqual",
        target_position_x=target_position_x,
        target_position_y=target_position_y,
        relative_distance_type="euclidianDistance",
    ).time_s
    return TriggerCaseResult(
        osc_path, transform_result.reference_channel_spec, activation_time_s
    )
