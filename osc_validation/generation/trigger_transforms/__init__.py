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
    """
    transformer = TRANSFORMER_BY_SPEC_TYPE.get(type(request.spec))
    if transformer is None:
        raise TypeError(f"Unsupported trigger transform spec type: {type(request.spec)!r}")
    return transformer.apply(request)


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
