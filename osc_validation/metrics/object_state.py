import math
from dataclasses import dataclass
from typing import Literal

from osi_utilities import ChannelSpecification, open_channel

from osc_validation.metrics.osimetric import OSIMetric
from osc_validation.utils.utils import timestamp_osi_to_float


ObjectMatchMode = Literal["same_id", "closest_initial_xy"]


@dataclass(frozen=True)
class ObjectStateMetricResult:
    reference_object_id: int
    tool_object_id: int
    sample_count: int
    max_xy_error: float
    max_planar_speed_error: float
    max_time_error: float


def _moving_objects(message):
    if hasattr(message, "global_ground_truth"):
        return message.global_ground_truth.moving_object
    return message.moving_object


def _find_moving_object(message, object_id: int):
    return next(
        (obj for obj in _moving_objects(message) if obj.id.value == object_id), None
    )


def _read_messages(channel_spec: ChannelSpecification) -> list:
    with open_channel(channel_spec) as reader:
        return list(reader)


class ObjectStateMetric(OSIMetric):
    """
    Compares per-frame OSI MovingObject state for one reference object.

    This metric intentionally uses simple state deltas instead of curve-shape
    metrics, so it also works for stationary or near-stationary traces.
    """

    def __init__(self, name: str = "ObjectStateMetric"):
        super().__init__(name)

    def compute(
        self,
        reference_channel_spec: ChannelSpecification,
        tool_channel_spec: ChannelSpecification,
        moving_object_id: int,
        match_mode: ObjectMatchMode = "closest_initial_xy",
        ignore_first_speed_sample: bool = False,
    ) -> ObjectStateMetricResult:
        reference_messages = _read_messages(reference_channel_spec)
        tool_messages = _read_messages(tool_channel_spec)
        if not reference_messages:
            raise RuntimeError("Reference trace has no messages.")
        if not tool_messages:
            raise RuntimeError("Tool trace has no messages.")
        if len(reference_messages) != len(tool_messages):
            raise ValueError(
                "Reference and tool traces must contain the same number of frames."
            )

        tool_object_id = self._resolve_tool_object_id(
            reference_messages=reference_messages,
            tool_messages=tool_messages,
            moving_object_id=moving_object_id,
            match_mode=match_mode,
        )

        max_xy_error = 0.0
        max_planar_speed_error = 0.0
        max_time_error = 0.0
        for sample_index, (reference_msg, tool_msg) in enumerate(
            zip(reference_messages, tool_messages)
        ):
            reference_time = timestamp_osi_to_float(reference_msg.timestamp)
            tool_time = timestamp_osi_to_float(tool_msg.timestamp)
            max_time_error = max(max_time_error, abs(reference_time - tool_time))

            reference_object = _find_moving_object(reference_msg, moving_object_id)
            tool_object = _find_moving_object(tool_msg, tool_object_id)
            if reference_object is None:
                raise KeyError(
                    f"Moving object ID {moving_object_id} not found in reference trace."
                )
            if tool_object is None:
                raise KeyError(
                    f"Moving object ID {tool_object_id} not found in tool trace."
                )

            max_xy_error = max(
                max_xy_error,
                math.hypot(
                    tool_object.base.position.x - reference_object.base.position.x,
                    tool_object.base.position.y - reference_object.base.position.y,
                ),
            )
            if ignore_first_speed_sample and sample_index == 0:
                continue
            reference_speed = math.hypot(
                reference_object.base.velocity.x,
                reference_object.base.velocity.y,
            )
            tool_speed = math.hypot(
                tool_object.base.velocity.x,
                tool_object.base.velocity.y,
            )
            max_planar_speed_error = max(
                max_planar_speed_error,
                abs(tool_speed - reference_speed),
            )

        return ObjectStateMetricResult(
            reference_object_id=moving_object_id,
            tool_object_id=tool_object_id,
            sample_count=len(reference_messages),
            max_xy_error=max_xy_error,
            max_planar_speed_error=max_planar_speed_error,
            max_time_error=max_time_error,
        )

    def _resolve_tool_object_id(
        self,
        reference_messages: list,
        tool_messages: list,
        moving_object_id: int,
        match_mode: ObjectMatchMode,
    ) -> int:
        if match_mode == "same_id":
            return moving_object_id
        if match_mode != "closest_initial_xy":
            raise ValueError(f"Unsupported match_mode '{match_mode}'.")

        reference_object = _find_moving_object(reference_messages[0], moving_object_id)
        if reference_object is None:
            raise KeyError(
                f"Moving object ID {moving_object_id} not found in reference trace."
            )

        tool_objects = list(_moving_objects(tool_messages[0]))
        if not tool_objects:
            raise KeyError("Tool trace contains no moving objects in the first frame.")

        return min(
            tool_objects,
            key=lambda obj: math.hypot(
                obj.base.position.x - reference_object.base.position.x,
                obj.base.position.y - reference_object.base.position.y,
            ),
        ).id.value
