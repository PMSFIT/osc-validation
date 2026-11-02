"""Case preparation for simulation time triggers."""

from pathlib import Path

from osi_utilities import ChannelSpecification

from osc_validation.cases.shared.init_pose import InitPoseOverride
from osc_validation.cases.triggers.models import (
    TriggerCaseResult,
    SimulationTimeTriggerSpec,
    TriggerTransformRequest,
)
from osc_validation.cases.triggers.transform import apply_trigger_transform
from osc_validation.generation.osi2osc import osi2osc
from osc_validation.versioning import ScenarioContract


def prepare_simulation_time_trigger_case(
    *,
    contract: ScenarioContract,
    osi_trace: Path,
    odr_file: Path,
    output_dir: Path,
    moving_object_id: int,
    ego_object_id: int,
    init_pose_object_id: int,
    trigger_delay: float,
    activation_frame_offset: int,
) -> TriggerCaseResult:
    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type="SensorView"
    )
    osc_path = osi2osc(
        contract=contract,
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=output_dir / "osi2osc_simulation_time_start_trigger.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=output_dir
                / f"reference_delayed_comparison_{moving_object_id}.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Delayed reference trace for trigger delay validation"
                },
            ),
            spec=SimulationTimeTriggerSpec(
                trigger_delay=trigger_delay,
                trigger_rule="greaterOrEqual",
                activation_frame_offset=activation_frame_offset,
            ),
            init_pose_policy="explicit_overrides",  # need explicit override because osi2osc default init position (0,0,0) is not on road (gtgen doesn't support placing objects outside of road)
            init_pose_overrides=[
                InitPoseOverride(
                    entity_ref="Ego",
                    object_id=ego_object_id,
                    x=-290.0,
                    y=-60.0,
                    z=0.7015,
                    yaw=0.0,
                    pitch=0.0,
                    roll=0.0,
                ),
                InitPoseOverride(
                    entity_ref=f"osi_moving_object_{init_pose_object_id}",
                    object_id=init_pose_object_id,
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
    activation_time_s = trigger_delay
    return TriggerCaseResult(
        osc_path, transform_result.reference_channel_spec, activation_time_s
    )
