import math
from pathlib import Path

from lxml import etree

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter

from .common import evaluate_rule, find_moving_object
from .models import (
    DistancePositionTriggerSpec,
    TriggerTransformRequest,
    TriggerTransformResult,
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
) -> Path:
    if trigger_distance_m < 0:
        raise ValueError("trigger_distance_m must be >= 0.")
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
    input_channel_spec: OSIChannelSpecification,
    output_channel_spec: OSIChannelSpecification,
    trigger_object_id: int,
    triggered_object_id: int,
    trigger_distance_m: float,
    trigger_rule: str,
    target_position_x: float,
    target_position_y: float,
    relative_distance_type: str = "euclidianDistance",
    activation_frame_offset: int = 1,
) -> OSIChannelSpecification:
    if trigger_distance_m < 0:
        raise ValueError("trigger_distance_m must be >= 0.")
    if activation_frame_offset < 0:
        raise ValueError("activation_frame_offset must be >= 0.")
    if relative_distance_type not in ("euclidianDistance", "longitudinal"):
        raise ValueError(
            "relative_distance_type must be one of {'euclidianDistance', 'longitudinal'}."
        )

    with OSIChannelReader.from_osi_channel_specification(input_channel_spec) as reader:
        input_messages = list(reader.get_messages())
        if not input_messages:
            raise RuntimeError("Input trace has no messages.")

    activation_index = None
    for idx, msg in enumerate(input_messages):
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
            activation_index = idx
            break

    if activation_index is None:
        raise RuntimeError(
            f"Distance position condition not reached: object {trigger_object_id}, rule={trigger_rule}, value={trigger_distance_m}m."
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
    with OSIChannelWriter.from_osi_channel_specification(output_channel_spec) as writer:
        for output_index, src_msg in enumerate(input_messages):
            msg_copy = type(src_msg)()
            msg_copy.CopyFrom(src_msg)
            out_trg_obj = find_moving_object(msg_copy, triggered_object_id)
            if out_trg_obj is None:
                raise KeyError(
                    f"Triggered object ID {triggered_object_id} not found in output frame."
                )

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
            writer.write(msg_copy)

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
            activation_frame_offset=request.spec.activation_frame_offset,
        )
        return TriggerTransformResult(
            xosc_path=xosc_path,
            reference_channel_spec=reference_channel_spec,
        )
