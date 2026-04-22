from .models import (
    DistancePositionTriggerSpec,
    SimulationTimeTriggerSpec,
    SpeedTriggerSpec,
    TimeToCollisionPositionTriggerSpec,
    TraveledDistanceTriggerSpec,
    TriggerTransformRequest,
    TriggerTransformResult,
)
from .distance_to_position import (
    DistancePositionTriggerTransformer,
    apply_distance_position_start_trigger,
    build_distance_position_triggered_comparison_trace,
)
from .simulation_time import (
    SimulationTimeTriggerTransformer,
    apply_simulation_time_start_trigger_to_all_events,
    build_delayed_comparison_trace,
)
from ..trace_kinematics import build_trace_with_calculated_kinematics
from .speed import (
    SpeedTriggerTransformer,
    apply_speed_start_trigger,
    build_speed_triggered_comparison_trace,
)
from .time_to_collision import (
    TimeToCollisionPositionTriggerTransformer,
    apply_time_to_collision_position_start_trigger,
    build_ttc_position_triggered_comparison_trace,
)
from .traveled_distance import (
    TraveledDistanceTriggerTransformer,
    apply_traveled_distance_start_trigger,
    build_traveled_distance_triggered_comparison_trace,
)

TRANSFORMER_BY_SPEC_TYPE = {
    SimulationTimeTriggerSpec: SimulationTimeTriggerTransformer,
    TraveledDistanceTriggerSpec: TraveledDistanceTriggerTransformer,
    SpeedTriggerSpec: SpeedTriggerTransformer,
    TimeToCollisionPositionTriggerSpec: TimeToCollisionPositionTriggerTransformer,
    DistancePositionTriggerSpec: DistancePositionTriggerTransformer,
}


def apply_trigger_transform(request: TriggerTransformRequest) -> TriggerTransformResult:
    """
    Apply a trigger transform consistently to both OSC and reference OSI outputs.

    Contract:
    - `request.source_xosc_path` should be an OpenSCENARIO generated from
      `request.source_reference_channel_spec` via `osi2osc` (same source trace).
      This keeps OSC trigger edits and reference-trace trigger edits aligned.

    Limitation:
    - Entity/event matching currently relies on the implicit naming convention
      produced by `osi2osc` (e.g. `Ego`, `osi_moving_object_<id>`,
      `<entity_ref>_maneuver_event`). The transform does not perform full
      semantic cross-validation between OSC names and OSI object IDs.

    Optional pre-pass:
    - `request.init_pose_policy` can stage an init-pose transform before the
      trigger transform:
      - `keep`: no init-pose changes (default)
      - `from_trajectory_start`: set init poses to trajectory start points
      - `explicit_overrides`: apply `request.init_pose_overrides`
    """
    source_xosc_path = request.source_xosc_path
    source_reference_channel_spec = request.source_reference_channel_spec
    pre_trigger_hold_overrides = request.pre_trigger_hold_overrides

    if request.init_pose_policy != "keep":
        from ..init_transforms import (
            apply_init_pose_from_trajectory_start_to_xosc,
            apply_init_pose_overrides_to_xosc,
            build_init_pose_overrides_from_trajectory_start,
        )

        staged_xosc_path = request.output_xosc_path.with_name(
            f"{request.output_xosc_path.stem}_init_stage{request.output_xosc_path.suffix}"
        )

        if request.init_pose_policy == "from_trajectory_start":
            pre_trigger_hold_overrides = build_init_pose_overrides_from_trajectory_start(
                source_xosc_path=request.source_xosc_path,
                input_channel_spec=request.source_reference_channel_spec,
                entity_refs=request.init_pose_entity_refs,
            )
            source_xosc_path = apply_init_pose_from_trajectory_start_to_xosc(
                source_xosc_path=request.source_xosc_path,
                output_xosc_path=staged_xosc_path,
                entity_refs=request.init_pose_entity_refs,
            )
        elif request.init_pose_policy == "explicit_overrides":
            if not request.init_pose_overrides:
                raise ValueError(
                    "init_pose_overrides must be provided when init_pose_policy='explicit_overrides'."
                )
            pre_trigger_hold_overrides = request.init_pose_overrides
            source_xosc_path = apply_init_pose_overrides_to_xosc(
                source_xosc_path=request.source_xosc_path,
                output_xosc_path=staged_xosc_path,
                overrides=request.init_pose_overrides,
            )
        else:
            raise ValueError(
                f"Unsupported init_pose_policy '{request.init_pose_policy}'."
            )

    if pre_trigger_hold_overrides is None:
        from ..init_transforms import build_init_pose_overrides_from_xosc_init

        pre_trigger_hold_overrides = build_init_pose_overrides_from_xosc_init(
            source_xosc_path=source_xosc_path,
            input_channel_spec=source_reference_channel_spec,
        )

    transformer = TRANSFORMER_BY_SPEC_TYPE.get(type(request.spec))
    if transformer is None:
        raise TypeError(f"Unsupported trigger transform spec type: {type(request.spec)!r}")
    return transformer.apply(
        TriggerTransformRequest(
            source_xosc_path=source_xosc_path,
            source_reference_channel_spec=source_reference_channel_spec,
            output_xosc_path=request.output_xosc_path,
            output_reference_channel_spec=request.output_reference_channel_spec,
            spec=request.spec,
            init_pose_policy="keep",
            pre_trigger_hold_overrides=pre_trigger_hold_overrides,
        )
    )


__all__ = [
    "DistancePositionTriggerSpec",
    "SimulationTimeTriggerSpec",
    "SpeedTriggerSpec",
    "TimeToCollisionPositionTriggerSpec",
    "TraveledDistanceTriggerSpec",
    "TriggerTransformRequest",
    "TriggerTransformResult",
    "apply_trigger_transform",
    "apply_distance_position_start_trigger",
    "apply_simulation_time_start_trigger_to_all_events",
    "apply_speed_start_trigger",
    "apply_time_to_collision_position_start_trigger",
    "apply_traveled_distance_start_trigger",
    "build_delayed_comparison_trace",
    "build_distance_position_triggered_comparison_trace",
    "build_speed_triggered_comparison_trace",
    "build_ttc_position_triggered_comparison_trace",
    "build_trace_with_calculated_kinematics",
    "build_traveled_distance_triggered_comparison_trace",
]
