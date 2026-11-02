"""Case preparation for traveled distance triggers."""

from pathlib import Path

from osi_utilities import ChannelSpecification

from osc_validation.features.triggers.models import (
    TriggerCaseResult,
    TraveledDistanceTriggerSpec,
    TriggerTransformRequest,
)
from osc_validation.features.triggers.transform import apply_trigger_transform
from .transform import find_traveled_distance_activation_point
from osc_validation.generation.osi2osc import osi2osc
from osc_validation.versioning import ScenarioContract


def prepare_traveled_distance_trigger_case(
    *,
    contract: ScenarioContract,
    osi_trace: Path,
    odr_file: Path,
    output_dir: Path,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_distance_m: float,
    activation_frame_offset: int,
) -> TriggerCaseResult:
    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type="SensorView"
    )
    osc_path = osi2osc(
        contract=contract,
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=output_dir / "osi2osc_traveled_distance_start_trigger.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=output_dir / "reference_traveled_distance_trigger_comparison.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace with traveled distance trigger applied"
                },
            ),
            spec=TraveledDistanceTriggerSpec(
                trigger_entity_ref="Ego",
                target_event_name=f"osi_moving_object_{moving_object_id}_maneuver_event",
                condition_name=f"distance_trigger_object{moving_object_id}_start",
                trigger_distance_m=trigger_distance_m,
                trigger_object_id=trigger_object_id,
                triggered_object_id=moving_object_id,
                trigger_rule="greaterOrEqual",
                activation_frame_offset=activation_frame_offset,
            ),
            init_pose_policy="close_to_trajectory_start",
        )
    )
    osc_path = transform_result.xosc_path
    activation_time_s = find_traveled_distance_activation_point(
        input_channel_spec=reference_trace_channel_spec,
        trigger_object_id=trigger_object_id,
        trigger_distance_m=trigger_distance_m,
        trigger_rule="greaterOrEqual",
    ).time_s
    return TriggerCaseResult(
        osc_path, transform_result.reference_channel_spec, activation_time_s
    )
