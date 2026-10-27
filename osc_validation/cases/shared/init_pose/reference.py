"""Apply init-pose expectations to reference OSI objects and traces."""

from osi_utilities import ChannelSpecification, open_channel, open_channel_writer
from osc_validation.utils.utils import find_moving_object, rotatePointZYX
from .models import InitPoseOverride, _validate_overrides


def apply_init_pose_override_to_reference_object(
    moving_object,
    override: InitPoseOverride,
) -> None:
    rx, ry, rz = rotatePointZYX(
        moving_object.vehicle_attributes.bbcenter_to_rear.x,
        moving_object.vehicle_attributes.bbcenter_to_rear.y,
        -moving_object.base.dimension.height / 2,
        override.yaw,
        override.pitch,
        override.roll,
    )
    moving_object.base.position.x = override.x - rx
    moving_object.base.position.y = override.y - ry
    moving_object.base.position.z = override.z - rz
    moving_object.base.orientation.yaw = override.yaw
    moving_object.base.orientation.pitch = override.pitch
    moving_object.base.orientation.roll = override.roll


def build_init_pose_overridden_reference_trace(
    input_channel_spec: ChannelSpecification,
    output_channel_spec: ChannelSpecification,
    overrides: list[InitPoseOverride],
) -> ChannelSpecification:
    _validate_overrides(overrides)
    overrides_by_object_id = {override.object_id: override for override in overrides}

    with open_channel(input_channel_spec) as reader:
        input_messages = list(reader)
        if not input_messages:
            raise RuntimeError("Input trace has no messages.")

    with open_channel_writer(output_channel_spec) as writer:
        for frame_index, src_msg in enumerate(input_messages):
            msg_copy = type(src_msg)()
            msg_copy.CopyFrom(src_msg)

            if frame_index == 0:
                for object_id, override in overrides_by_object_id.items():
                    moving_object = find_moving_object(msg_copy, object_id)
                    if moving_object is None:
                        raise KeyError(
                            f"Moving object ID {object_id} not found in frame 0 while applying init pose override."
                        )

                    apply_init_pose_override_to_reference_object(
                        moving_object, override
                    )

            writer.write_message(msg_copy)

        return writer.get_channel_specification()
