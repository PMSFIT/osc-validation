import math
from pathlib import Path

from lxml import etree

from osi_utilities import ChannelSpecification, open_channel, open_channel_writer
from ..init_transforms.models import InitPoseOverride

from .common import evaluate_rule, find_moving_object
from .models import (
    TraveledDistanceTriggerSpec,
    TriggerTransformRequest,
    TriggerTransformResult,
)


def apply_traveled_distance_start_trigger(
    source_xosc_path: Path,
    output_xosc_path: Path,
    trigger_entity_ref: str,
    target_event_name: str,
    condition_name: str,
    trigger_distance_m: float,
) -> Path:
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
        delay="0",
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
    etree.SubElement(
        xml_entity_condition,
        "TraveledDistanceCondition",
        value=str(trigger_distance_m),
    )

    tree.write(
        str(output_xosc_path), encoding="utf-8", xml_declaration=True, pretty_print=True
    )
    return output_xosc_path


def build_traveled_distance_triggered_comparison_trace(
    input_channel_spec: ChannelSpecification,
    output_channel_spec: ChannelSpecification,
    trigger_object_id: int,
    triggered_object_id: int,
    trigger_distance_m: float,
    trigger_rule: str = "greaterThan",
    activation_frame_offset: int = 1,
    pre_trigger_hold_overrides: list[InitPoseOverride] | None = None,
) -> ChannelSpecification:
    if trigger_distance_m < 0:
        raise ValueError("trigger_distance_m must be >= 0.")
    if activation_frame_offset < 0:
        raise ValueError("activation_frame_offset must be >= 0.")

    with open_channel(input_channel_spec) as reader:
        input_messages = list(reader)
        if not input_messages:
            raise RuntimeError("Input trace has no messages.")

    trigger_positions = []
    for msg in input_messages:
        trigger_obj = find_moving_object(msg, trigger_object_id)
        if trigger_obj is None:
            raise KeyError(
                f"Trigger object ID {trigger_object_id} not found in one or more frames."
            )
        trigger_positions.append((trigger_obj.base.position.x, trigger_obj.base.position.y))

    cumulative_distance = 0.0
    activation_index = None
    for idx in range(1, len(trigger_positions)):
        x0, y0 = trigger_positions[idx - 1]
        x1, y1 = trigger_positions[idx]
        cumulative_distance += math.hypot(x1 - x0, y1 - y0)
        if evaluate_rule(cumulative_distance, trigger_distance_m, trigger_rule):
            activation_index = idx
            break

    if activation_index is None:
        raise RuntimeError(
            f"Traveled distance condition not reached: object {trigger_object_id}, rule={trigger_rule}, value={trigger_distance_m}m."
        )
    shifted_start_index = activation_index + activation_frame_offset

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


class TraveledDistanceTriggerTransformer:
    @staticmethod
    def apply(request: TriggerTransformRequest) -> TriggerTransformResult:
        if not isinstance(request.spec, TraveledDistanceTriggerSpec):
            raise TypeError(
                "TraveledDistanceTriggerTransformer requires TraveledDistanceTriggerSpec."
            )

        xosc_path = apply_traveled_distance_start_trigger(
            source_xosc_path=request.source_xosc_path,
            output_xosc_path=request.output_xosc_path,
            trigger_entity_ref=request.spec.trigger_entity_ref,
            target_event_name=request.spec.target_event_name,
            condition_name=request.spec.condition_name,
            trigger_distance_m=request.spec.trigger_distance_m,
        )
        reference_channel_spec = build_traveled_distance_triggered_comparison_trace(
            input_channel_spec=request.source_reference_channel_spec,
            output_channel_spec=request.output_reference_channel_spec,
            trigger_object_id=request.spec.trigger_object_id,
            triggered_object_id=request.spec.triggered_object_id,
            trigger_distance_m=request.spec.trigger_distance_m,
            trigger_rule=request.spec.trigger_rule,
            activation_frame_offset=request.spec.activation_frame_offset,
            pre_trigger_hold_overrides=request.init_pose_overrides,
        )
        return TriggerTransformResult(
            xosc_path=xosc_path,
            reference_channel_spec=reference_channel_spec,
        )
