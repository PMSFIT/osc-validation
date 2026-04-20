import math
from pathlib import Path

from lxml import etree

from osi_utilities import ChannelSpecification, open_channel, open_channel_writer
from ..init_transforms.models import InitPoseOverride

from .common import ActivationPoint, evaluate_rule, find_moving_object
from .models import (
    DistancePositionTriggerSpec,
    TriggerTransformRequest,
    TriggerTransformResult,
)


def find_distance_position_activation_point(
    input_channel_spec: ChannelSpecification,
    trigger_object_id: int,
    trigger_distance_m: float,
    trigger_rule: str,
    target_position_x: float,
    target_position_y: float,
    relative_distance_type: str = "euclidianDistance",
) -> ActivationPoint:
    """
    Return the first activation point for a DistanceCondition-to-position check.

    The activation point is defined as the earliest frame where the configured
    distance rule evaluates to true for `trigger_object_id` against the target
    position.

    Typical usage:
    - Trigger generation/reference logic to derive a deterministic activation
      frame index.
    - Test-case metric windowing, e.g. start trajectory similarity evaluation
      at `activation_time + guard_time` so only the relevant post-trigger
      interval is scored.
    """
    with open_channel(input_channel_spec) as reader:
        messages = list(reader)
        if not messages:
            raise RuntimeError("Input trace has no messages.")

    activation_index = _find_distance_position_activation_index_from_messages(
        messages=messages,
        trigger_object_id=trigger_object_id,
        trigger_distance_m=trigger_distance_m,
        trigger_rule=trigger_rule,
        target_position_x=target_position_x,
        target_position_y=target_position_y,
        relative_distance_type=relative_distance_type,
    )
    activation_msg = messages[activation_index]
    activation_time = (
        activation_msg.timestamp.seconds + activation_msg.timestamp.nanos / 1e9
    )
    return ActivationPoint(index=activation_index, time_s=activation_time)


def _find_distance_position_activation_index_from_messages(
    messages: list,
    trigger_object_id: int,
    trigger_distance_m: float,
    trigger_rule: str,
    target_position_x: float,
    target_position_y: float,
    relative_distance_type: str = "euclidianDistance",
) -> int:
    if relative_distance_type not in ("euclidianDistance", "longitudinal"):
        raise ValueError(
            "relative_distance_type must be one of {'euclidianDistance', 'longitudinal'}."
        )

    for idx, msg in enumerate(messages):
        trigger_obj = find_moving_object(msg, trigger_object_id)
        if trigger_obj is None:
            raise KeyError(
                f"Trigger object ID {trigger_object_id} not found in one or more frames."
            )
        dx = trigger_obj.base.position.x - target_position_x
        dy = trigger_obj.base.position.y - target_position_y
        if relative_distance_type == "longitudinal":
            yaw = trigger_obj.base.orientation.yaw
            distance = abs(dx * math.cos(yaw) + dy * math.sin(yaw))
        else:
            distance = math.hypot(dx, dy)
        if evaluate_rule(distance, trigger_distance_m, trigger_rule):
            return idx

    raise RuntimeError(
        f"Distance position condition not reached: object {trigger_object_id}, rule={trigger_rule}, value={trigger_distance_m}m."
    )


def apply_distance_position_start_trigger(
    source_xosc_path: Path,
    output_xosc_path: Path,
    trigger_entity_ref: str,
    target_event_name: str,
    condition_name: str,
    trigger_distance_m: float,
    trigger_rule: str,
    target_position_x: float,
    target_position_y: float,
    target_position_z: float = 0.0,
    relative_distance_type: str = "euclidianDistance",
    condition_delay_s: float = 0.0,
) -> Path:
    if trigger_distance_m < 0:
        raise ValueError("trigger_distance_m must be >= 0.")
    if condition_delay_s < 0:
        raise ValueError("condition_delay_s must be >= 0.")
    if relative_distance_type not in ("euclidianDistance", "longitudinal"):
        raise ValueError(
            "relative_distance_type must be one of {'euclidianDistance', 'longitudinal'}."
        )

    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()
    event = root.find(f".//Event[@name='{target_event_name}']")
    if event is None:
        raise RuntimeError(f"Event '{target_event_name}' not found in {source_xosc_path}.")

    old_start = event.find("StartTrigger")
    if old_start is not None:
        event.remove(old_start)

    xml_start_trigger = etree.SubElement(event, "StartTrigger")
    xml_condition_group = etree.SubElement(xml_start_trigger, "ConditionGroup")
    xml_condition = etree.SubElement(
        xml_condition_group,
        "Condition",
        name=condition_name,
        delay=str(condition_delay_s),
        conditionEdge="rising",
    )
    xml_by_entity_condition = etree.SubElement(xml_condition, "ByEntityCondition")
    xml_triggering_entities = etree.SubElement(
        xml_by_entity_condition,
        "TriggeringEntities",
        triggeringEntitiesRule="any",
    )
    etree.SubElement(xml_triggering_entities, "EntityRef", entityRef=trigger_entity_ref)
    xml_entity_condition = etree.SubElement(xml_by_entity_condition, "EntityCondition")
    xml_distance_condition = etree.SubElement(
        xml_entity_condition,
        "DistanceCondition",
        value=str(trigger_distance_m),
        rule=trigger_rule,
        freespace="false",
        coordinateSystem="entity",
        relativeDistanceType=relative_distance_type,
    )
    xml_position = etree.SubElement(xml_distance_condition, "Position")
    etree.SubElement(
        xml_position,
        "WorldPosition",
        x=str(target_position_x),
        y=str(target_position_y),
        z=str(target_position_z),
        h="0.0",
        p="0.0",
        r="0.0",
    )

    tree.write(
        str(output_xosc_path), encoding="utf-8", xml_declaration=True, pretty_print=True
    )
    return output_xosc_path


def build_distance_position_triggered_comparison_trace(
    input_channel_spec: ChannelSpecification,
    output_channel_spec: ChannelSpecification,
    trigger_object_id: int,
    triggered_object_id: int,
    trigger_distance_m: float,
    trigger_rule: str,
    target_position_x: float,
    target_position_y: float,
    relative_distance_type: str = "euclidianDistance",
    condition_delay_s: float = 0.0,
    activation_frame_offset: int = 1,
    pre_trigger_hold_overrides: list[InitPoseOverride] | None = None,
) -> ChannelSpecification:
    if trigger_distance_m < 0:
        raise ValueError("trigger_distance_m must be >= 0.")
    if condition_delay_s < 0:
        raise ValueError("condition_delay_s must be >= 0.")
    if activation_frame_offset < 0:
        raise ValueError("activation_frame_offset must be >= 0.")
    if relative_distance_type not in ("euclidianDistance", "longitudinal"):
        raise ValueError(
            "relative_distance_type must be one of {'euclidianDistance', 'longitudinal'}."
        )

    with open_channel(input_channel_spec) as reader:
        input_messages = list(reader)
        if not input_messages:
            raise RuntimeError("Input trace has no messages.")

    activation_index = _find_distance_position_activation_index_from_messages(
        messages=input_messages,
        trigger_object_id=trigger_object_id,
        trigger_distance_m=trigger_distance_m,
        trigger_rule=trigger_rule,
        target_position_x=target_position_x,
        target_position_y=target_position_y,
        relative_distance_type=relative_distance_type,
    )

    activation_msg = input_messages[activation_index]
    activation_time_s = (
        activation_msg.timestamp.seconds + activation_msg.timestamp.nanos / 1e9
    )
    delayed_activation_time_s = activation_time_s + condition_delay_s
    delayed_activation_index = next(
        (
            idx
            for idx, msg in enumerate(input_messages[activation_index:], activation_index)
            if msg.timestamp.seconds + msg.timestamp.nanos / 1e9
            >= delayed_activation_time_s
        ),
        len(input_messages) - 1,
    )
    shifted_start_index = delayed_activation_index + activation_frame_offset

    triggered_source_states = []
    for msg in input_messages:
        trg_obj = find_moving_object(msg, triggered_object_id)
        if trg_obj is None:
            raise KeyError(
                f"Triggered object ID {triggered_object_id} not found in one or more frames."
            )
        triggered_source_states.append(trg_obj)

    initial_state = triggered_source_states[0]
    hold_override = None
    if pre_trigger_hold_overrides:
        hold_override = next(
            (
                override
                for override in pre_trigger_hold_overrides
                if override.object_id == triggered_object_id
            ),
            None,
        )
    with open_channel_writer(output_channel_spec) as writer:
        for output_index, src_msg in enumerate(input_messages):
            msg_copy = type(src_msg)()
            msg_copy.CopyFrom(src_msg)
            out_trg_obj = find_moving_object(msg_copy, triggered_object_id)
            if out_trg_obj is None:
                raise KeyError(
                    f"Triggered object ID {triggered_object_id} not found in output frame."
                )

            if output_index < shifted_start_index and hold_override is not None:
                out_trg_obj.base.position.x = hold_override.x
                out_trg_obj.base.position.y = hold_override.y
                out_trg_obj.base.position.z = hold_override.z
                out_trg_obj.base.orientation.yaw = hold_override.yaw
                out_trg_obj.base.orientation.pitch = hold_override.pitch
                out_trg_obj.base.orientation.roll = hold_override.roll
            else:
                if output_index < shifted_start_index:
                    state_src = initial_state
                else:
                    state_index = output_index - shifted_start_index + 1
                    if state_index >= len(triggered_source_states):
                        state_index = len(triggered_source_states) - 1
                    state_src = triggered_source_states[state_index]

                out_trg_obj.base.position.x = state_src.base.position.x
                out_trg_obj.base.position.y = state_src.base.position.y
                out_trg_obj.base.position.z = state_src.base.position.z
                out_trg_obj.base.orientation.yaw = state_src.base.orientation.yaw
                out_trg_obj.base.orientation.pitch = state_src.base.orientation.pitch
                out_trg_obj.base.orientation.roll = state_src.base.orientation.roll
            writer.write_message(msg_copy)

        return writer.get_channel_specification()


class DistancePositionTriggerTransformer:
    @staticmethod
    def apply(request: TriggerTransformRequest) -> TriggerTransformResult:
        if not isinstance(request.spec, DistancePositionTriggerSpec):
            raise TypeError(
                "DistancePositionTriggerTransformer requires DistancePositionTriggerSpec."
            )

        xosc_path = apply_distance_position_start_trigger(
            source_xosc_path=request.source_xosc_path,
            output_xosc_path=request.output_xosc_path,
            trigger_entity_ref=request.spec.trigger_entity_ref,
            target_event_name=request.spec.target_event_name,
            condition_name=request.spec.condition_name,
            trigger_distance_m=request.spec.trigger_distance_m,
            trigger_rule=request.spec.trigger_rule,
            target_position_x=request.spec.target_position_x,
            target_position_y=request.spec.target_position_y,
            target_position_z=request.spec.target_position_z,
            relative_distance_type=request.spec.relative_distance_type,
            condition_delay_s=request.spec.condition_delay_s,
        )
        reference_channel_spec = build_distance_position_triggered_comparison_trace(
            input_channel_spec=request.source_reference_channel_spec,
            output_channel_spec=request.output_reference_channel_spec,
            trigger_object_id=request.spec.trigger_object_id,
            triggered_object_id=request.spec.triggered_object_id,
            trigger_distance_m=request.spec.trigger_distance_m,
            trigger_rule=request.spec.trigger_rule,
            target_position_x=request.spec.target_position_x,
            target_position_y=request.spec.target_position_y,
            relative_distance_type=request.spec.relative_distance_type,
            condition_delay_s=request.spec.condition_delay_s,
            activation_frame_offset=request.spec.activation_frame_offset,
            pre_trigger_hold_overrides=request.init_pose_overrides,
        )
        return TriggerTransformResult(
            xosc_path=xosc_path,
            reference_channel_spec=reference_channel_spec,
        )
