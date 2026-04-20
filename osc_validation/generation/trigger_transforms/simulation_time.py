from pathlib import Path

from lxml import etree

from osi_utilities import ChannelSpecification, open_channel, open_channel_writer
from osc_validation.utils.utils import timestamp_float_to_osi
from ..init_transforms.models import InitPoseOverride
from .common import find_moving_object

from .models import (
    SimulationTimeTriggerSpec,
    TriggerTransformRequest,
    TriggerTransformResult,
)


def apply_simulation_time_start_trigger_to_all_events(
    source_xosc_path: Path,
    output_xosc_path: Path,
    trigger_delay: float,
    trigger_rule: str = "greaterThan",
) -> Path:
    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()
    events = root.findall(".//Event")
    for idx, event in enumerate(events):
        existing_start = event.find("StartTrigger")
        if existing_start is not None:
            event.remove(existing_start)

        xml_start_trigger = etree.SubElement(event, "StartTrigger")
        xml_condition_group = etree.SubElement(xml_start_trigger, "ConditionGroup")
        xml_condition = etree.SubElement(
            xml_condition_group,
            "Condition",
            name=f"event_start_trigger_condition_{idx}",
            delay="0",
            conditionEdge="rising",
        )
        xml_by_value = etree.SubElement(xml_condition, "ByValueCondition")
        etree.SubElement(
            xml_by_value,
            "SimulationTimeCondition",
            value=str(trigger_delay),
            rule=trigger_rule,
        )

    tree.write(
        str(output_xosc_path), encoding="utf-8", xml_declaration=True, pretty_print=True
    )
    return output_xosc_path


def build_delayed_comparison_trace(
    input_channel_spec: ChannelSpecification,
    output_channel_spec: ChannelSpecification,
    trigger_delay: float,
    trigger_rule: str = "greaterThan",
    activation_frame_offset: int = 0,
    pre_trigger_hold_overrides: list[InitPoseOverride] | None = None,
) -> ChannelSpecification:
    if trigger_delay < 0:
        raise ValueError("trigger_delay must be >= 0.")
    if activation_frame_offset < 0:
        raise ValueError("activation_frame_offset must be >= 0.")

    supported_rules = {
        "greaterThan",
        "greaterOrEqual",
        "lessThan",
        "lessOrEqual",
        "equalTo",
        "notEqualTo",
    }
    if trigger_rule not in supported_rules:
        raise ValueError(
            f"Unsupported trigger_rule '{trigger_rule}'. Supported: {sorted(supported_rules)}"
        )

    def _is_condition_true(t_rel: float) -> bool:
        if trigger_rule == "greaterThan":
            return t_rel > trigger_delay
        if trigger_rule == "greaterOrEqual":
            return t_rel >= trigger_delay
        if trigger_rule == "lessThan":
            return t_rel < trigger_delay
        if trigger_rule == "lessOrEqual":
            return t_rel <= trigger_delay
        if trigger_rule == "equalTo":
            return t_rel == trigger_delay
        if trigger_rule == "notEqualTo":
            return t_rel != trigger_delay
        return False

    with open_channel(input_channel_spec) as reader:
        input_messages = list(reader)
        if not input_messages:
            raise RuntimeError("Input trace has no messages.")

    input_timestamps = [
        msg.timestamp.seconds + msg.timestamp.nanos / 1e9 for msg in input_messages
    ]
    start = input_timestamps[0]
    stop = input_timestamps[-1]
    if len(input_timestamps) < 2 or input_timestamps[1] <= input_timestamps[0]:
        raise RuntimeError("Could not determine valid input trace step size.")

    if trigger_delay >= (stop - start):
        raise ValueError("trigger_delay exceeds or equals the available input trace duration.")

    first_msg = input_messages[0]
    activation_index = next(
        (idx for idx, ts in enumerate(input_timestamps) if _is_condition_true(ts - start)),
        None,
    )
    if activation_index is None:
        raise RuntimeError(
            f"Simulation-time condition not reached: rule={trigger_rule}, value={trigger_delay}s."
        )
    shifted_start_index = activation_index + activation_frame_offset

    with open_channel_writer(output_channel_spec) as writer:
        for output_index, output_time in enumerate(input_timestamps):
            t_rel = output_time - start
            condition_true = _is_condition_true(t_rel)
            if condition_true:
                source_index = output_index - shifted_start_index
                if source_index < 0:
                    source_index = 0
                if source_index >= len(input_messages):
                    source_index = len(input_messages) - 1
                source_msg = input_messages[source_index]
                msg_copy = type(source_msg)()
                msg_copy.CopyFrom(source_msg)
            else:
                msg_copy = type(first_msg)()
                msg_copy.CopyFrom(first_msg)
                if pre_trigger_hold_overrides:
                    for override in pre_trigger_hold_overrides:
                        moving_object = find_moving_object(msg_copy, override.object_id)
                        if moving_object is None:
                            raise KeyError(
                                f"Moving object ID {override.object_id} not found while applying pre-trigger hold override."
                            )
                        moving_object.base.position.x = override.x
                        moving_object.base.position.y = override.y
                        moving_object.base.position.z = override.z
                        moving_object.base.orientation.yaw = override.yaw
                        moving_object.base.orientation.pitch = override.pitch
                        moving_object.base.orientation.roll = override.roll

            ts = timestamp_float_to_osi(output_time)
            msg_copy.timestamp.seconds = ts.seconds
            msg_copy.timestamp.nanos = ts.nanos
            writer.write_message(msg_copy)

        return writer.get_channel_specification()


class SimulationTimeTriggerTransformer:
    @staticmethod
    def apply(request: TriggerTransformRequest) -> TriggerTransformResult:
        if not isinstance(request.spec, SimulationTimeTriggerSpec):
            raise TypeError(
                "SimulationTimeTriggerTransformer requires SimulationTimeTriggerSpec."
            )

        xosc_path = apply_simulation_time_start_trigger_to_all_events(
            source_xosc_path=request.source_xosc_path,
            output_xosc_path=request.output_xosc_path,
            trigger_delay=request.spec.trigger_delay,
            trigger_rule=request.spec.trigger_rule,
        )
        reference_channel_spec = build_delayed_comparison_trace(
            input_channel_spec=request.source_reference_channel_spec,
            output_channel_spec=request.output_reference_channel_spec,
            trigger_delay=request.spec.trigger_delay,
            trigger_rule=request.spec.trigger_rule,
            activation_frame_offset=request.spec.activation_frame_offset,
            pre_trigger_hold_overrides=request.init_pose_overrides,
        )
        return TriggerTransformResult(
            xosc_path=xosc_path,
            reference_channel_spec=reference_channel_spec,
        )
