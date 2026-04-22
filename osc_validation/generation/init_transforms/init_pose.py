from pathlib import Path
import re

from lxml import etree

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter

from ..trigger_transforms.common import find_moving_object
from .models import (
    InitPoseOverride,
    InitPoseTransformSpec,
    InitPoseTransformRequest,
    InitPoseTransformResult,
)


def _validate_overrides(overrides: list[InitPoseOverride]) -> None:
    if not overrides:
        raise ValueError("Init pose transform requires at least one override.")

    object_ids = [override.object_id for override in overrides]
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("Init pose overrides must use unique object_id values.")

    entity_refs = [override.entity_ref for override in overrides]
    if len(entity_refs) != len(set(entity_refs)):
        raise ValueError("Init pose overrides must use unique entity_ref values.")


def apply_init_pose_overrides_to_xosc(
    source_xosc_path: Path,
    output_xosc_path: Path,
    overrides: list[InitPoseOverride],
) -> Path:
    _validate_overrides(overrides)

    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()

    for override in overrides:
        world_position = root.find(
            f".//Init//Private[@entityRef='{override.entity_ref}']//TeleportAction//Position//WorldPosition"
        )
        if world_position is None:
            raise RuntimeError(
                f"Could not find Init/TeleportAction/WorldPosition for entityRef='{override.entity_ref}' in '{source_xosc_path}'."
            )

        world_position.set("x", str(override.x))
        world_position.set("y", str(override.y))
        world_position.set("z", str(override.z))
        world_position.set("h", str(override.yaw))
        world_position.set("p", str(override.pitch))
        world_position.set("r", str(override.roll))

    tree.write(
        str(output_xosc_path), encoding="utf-8", xml_declaration=True, pretty_print=True
    )
    return output_xosc_path


def apply_init_pose_from_trajectory_start_to_xosc(
    source_xosc_path: Path,
    output_xosc_path: Path,
    entity_refs: list[str] | None = None,
) -> Path:
    """
    Set each selected Init TeleportAction pose to the first point of the
    entity's embedded FollowTrajectoryAction polyline.

    Limitation:
    - This relies on the naming convention produced by `osi2osc` where the
      event name is `<entity_ref>_maneuver_event`.
    """
    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()

    init_privates = root.findall(".//Init//Private")
    if entity_refs is None:
        selected_entity_refs = [private.get("entityRef") for private in init_privates]
    else:
        selected_entity_refs = entity_refs

    for entity_ref in selected_entity_refs:
        if not entity_ref:
            continue

        init_world_position = root.find(
            f".//Init//Private[@entityRef='{entity_ref}']//TeleportAction//Position//WorldPosition"
        )
        if init_world_position is None:
            raise RuntimeError(
                f"Could not find Init/TeleportAction/WorldPosition for entityRef='{entity_ref}' in '{source_xosc_path}'."
            )

        trajectory_start_world_position = root.find(
            f".//Event[@name='{entity_ref}_maneuver_event']//FollowTrajectoryAction//TrajectoryRef//Trajectory//Shape//Polyline//Vertex[1]//Position//WorldPosition"
        )
        if trajectory_start_world_position is None:
            raise RuntimeError(
                f"Could not find first trajectory vertex for entityRef='{entity_ref}' in '{source_xosc_path}'."
            )

        for attr in ("x", "y", "z", "h", "p", "r"):
            value = trajectory_start_world_position.get(attr)
            if value is None:
                raise RuntimeError(
                    f"Trajectory start WorldPosition for entityRef='{entity_ref}' is missing attribute '{attr}'."
                )
            init_world_position.set(attr, value)

    tree.write(
        str(output_xosc_path), encoding="utf-8", xml_declaration=True, pretty_print=True
    )
    return output_xosc_path


def build_init_pose_overrides_from_trajectory_start(
    source_xosc_path: Path,
    input_channel_spec: OSIChannelSpecification,
    entity_refs: list[str] | None = None,
) -> list[InitPoseOverride]:
    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()

    init_privates = root.findall(".//Init//Private")
    if entity_refs is None:
        selected_entity_refs = [private.get("entityRef") for private in init_privates]
    else:
        selected_entity_refs = entity_refs

    with OSIChannelReader.from_osi_channel_specification(input_channel_spec) as reader:
        first_msg = next(reader.get_messages(), None)
        if first_msg is None:
            raise RuntimeError("Input trace has no messages.")
        host_vehicle_id = (
            first_msg.host_vehicle_id.value if hasattr(first_msg, "host_vehicle_id") else None
        )

    overrides: list[InitPoseOverride] = []
    for entity_ref in selected_entity_refs:
        if not entity_ref:
            continue

        trajectory_start_world_position = root.find(
            f".//Event[@name='{entity_ref}_maneuver_event']//FollowTrajectoryAction//TrajectoryRef//Trajectory//Shape//Polyline//Vertex[1]//Position//WorldPosition"
        )
        if trajectory_start_world_position is None:
            raise RuntimeError(
                f"Could not find first trajectory vertex for entityRef='{entity_ref}' in '{source_xosc_path}'."
            )

        if entity_ref == "Ego":
            if host_vehicle_id is None:
                raise RuntimeError(
                    "Could not resolve object_id for entityRef='Ego' because host_vehicle_id is missing in input trace."
                )
            object_id = int(host_vehicle_id)
        else:
            match = re.fullmatch(r"osi_moving_object_(\d+)", entity_ref)
            if match is None:
                raise RuntimeError(
                    f"Could not resolve object_id from entityRef='{entity_ref}'."
                )
            object_id = int(match.group(1))

        overrides.append(
            InitPoseOverride(
                entity_ref=entity_ref,
                object_id=object_id,
                x=float(trajectory_start_world_position.get("x")),
                y=float(trajectory_start_world_position.get("y")),
                z=float(trajectory_start_world_position.get("z")),
                yaw=float(trajectory_start_world_position.get("h")),
                pitch=float(trajectory_start_world_position.get("p")),
                roll=float(trajectory_start_world_position.get("r")),
            )
        )

    _validate_overrides(overrides)
    return overrides


def build_init_pose_overrides_from_xosc_init(
    source_xosc_path: Path,
    input_channel_spec: OSIChannelSpecification,
    entity_refs: list[str] | None = None,
) -> list[InitPoseOverride]:
    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()

    init_privates = root.findall(".//Init//Private")
    if entity_refs is None:
        selected_entity_refs = [private.get("entityRef") for private in init_privates]
    else:
        selected_entity_refs = entity_refs

    with OSIChannelReader.from_osi_channel_specification(input_channel_spec) as reader:
        first_msg = next(reader.get_messages(), None)
        if first_msg is None:
            raise RuntimeError("Input trace has no messages.")
        host_vehicle_id = (
            first_msg.host_vehicle_id.value
            if hasattr(first_msg, "host_vehicle_id")
            else None
        )

    overrides: list[InitPoseOverride] = []
    for entity_ref in selected_entity_refs:
        if not entity_ref:
            continue

        init_world_position = root.find(
            f".//Init//Private[@entityRef='{entity_ref}']//TeleportAction//Position//WorldPosition"
        )
        if init_world_position is None:
            raise RuntimeError(
                f"Could not find Init/TeleportAction/WorldPosition for entityRef='{entity_ref}' in '{source_xosc_path}'."
            )

        if entity_ref == "Ego":
            if host_vehicle_id is None:
                raise RuntimeError(
                    "Could not resolve object_id for entityRef='Ego' because host_vehicle_id is missing in input trace."
                )
            object_id = int(host_vehicle_id)
        else:
            match = re.fullmatch(r"osi_moving_object_(\d+)", entity_ref)
            if match is None:
                raise RuntimeError(
                    f"Could not resolve object_id from entityRef='{entity_ref}'."
                )
            object_id = int(match.group(1))

        overrides.append(
            InitPoseOverride(
                entity_ref=entity_ref,
                object_id=object_id,
                x=float(init_world_position.get("x")),
                y=float(init_world_position.get("y")),
                z=float(init_world_position.get("z")),
                yaw=float(init_world_position.get("h")),
                pitch=float(init_world_position.get("p")),
                roll=float(init_world_position.get("r")),
            )
        )

    _validate_overrides(overrides)
    return overrides


def apply_init_pose_from_trajectory_start_transform(
    source_xosc_path: Path,
    source_reference_channel_spec: OSIChannelSpecification,
    output_xosc_path: Path,
    output_reference_channel_spec: OSIChannelSpecification,
    entity_refs: list[str] | None = None,
) -> InitPoseTransformResult:
    overrides = build_init_pose_overrides_from_trajectory_start(
        source_xosc_path=source_xosc_path,
        input_channel_spec=source_reference_channel_spec,
        entity_refs=entity_refs,
    )
    return apply_init_pose_transform(
        InitPoseTransformRequest(
            source_xosc_path=source_xosc_path,
            source_reference_channel_spec=source_reference_channel_spec,
            output_xosc_path=output_xosc_path,
            output_reference_channel_spec=output_reference_channel_spec,
            spec=InitPoseTransformSpec(overrides=overrides),
        )
    )


def build_init_pose_overridden_reference_trace(
    input_channel_spec: OSIChannelSpecification,
    output_channel_spec: OSIChannelSpecification,
    overrides: list[InitPoseOverride],
) -> OSIChannelSpecification:
    _validate_overrides(overrides)
    overrides_by_object_id = {override.object_id: override for override in overrides}

    with OSIChannelReader.from_osi_channel_specification(input_channel_spec) as reader:
        input_messages = list(reader.get_messages())
        if not input_messages:
            raise RuntimeError("Input trace has no messages.")

    with OSIChannelWriter.from_osi_channel_specification(output_channel_spec) as writer:
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

                    moving_object.base.position.x = override.x
                    moving_object.base.position.y = override.y
                    moving_object.base.position.z = override.z
                    moving_object.base.orientation.yaw = override.yaw
                    moving_object.base.orientation.pitch = override.pitch
                    moving_object.base.orientation.roll = override.roll

            writer.write(msg_copy)

        return writer.get_channel_specification()


def apply_init_pose_transform(
    request: InitPoseTransformRequest,
) -> InitPoseTransformResult:
    xosc_path = apply_init_pose_overrides_to_xosc(
        source_xosc_path=request.source_xosc_path,
        output_xosc_path=request.output_xosc_path,
        overrides=request.spec.overrides,
    )
    reference_channel_spec = build_init_pose_overridden_reference_trace(
        input_channel_spec=request.source_reference_channel_spec,
        output_channel_spec=request.output_reference_channel_spec,
        overrides=request.spec.overrides,
    )
    return InitPoseTransformResult(
        xosc_path=xosc_path,
        reference_channel_spec=reference_channel_spec,
    )
