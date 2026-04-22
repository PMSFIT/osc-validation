from pathlib import Path
import math
import re

from lxml import etree

from osi_utilities import ChannelSpecification, open_channel, open_channel_writer

from ..trigger_transforms.common import find_moving_object
from .models import (
    InitPoseOverride,
    InitPoseTransformSpec,
    InitPoseTransformRequest,
    InitPoseTransformResult,
)


def compute_close_to_trajectory_start_xy(
    init_x: float,
    init_y: float,
    start_x: float,
    start_y: float,
    threshold_m: float,
) -> tuple[float, float]:
    """
    Compute a target XY position near trajectory start at a fixed radial offset.

    The returned point is exactly `threshold_m` away from `(start_x, start_y)`,
    placed in the direction from trajectory start to the current init position
    `(init_x, init_y)`.

    Edge case:
    - If init and trajectory start are identical, the direction is defined as
      +X, so the result becomes `(start_x + threshold_m, start_y)`.

    Args:
        init_x: Current init X coordinate.
        init_y: Current init Y coordinate.
        start_x: Trajectory start X coordinate.
        start_y: Trajectory start Y coordinate.
        threshold_m: Required radial distance from trajectory start. Must be > 0.

    Returns:
        Tuple `(target_x, target_y)` representing the computed init XY.
    """
    if threshold_m <= 0.0:
        raise ValueError("threshold_m must be > 0.0.")

    dx = init_x - start_x
    dy = init_y - start_y
    distance_xy = math.hypot(dx, dy)
    if distance_xy == 0.0:
        unit_x, unit_y = 1.0, 0.0
    else:
        unit_x = dx / distance_xy
        unit_y = dy / distance_xy
    target_x = start_x + unit_x * threshold_m
    target_y = start_y + unit_y * threshold_m
    return target_x, target_y


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


def build_init_pose_overrides_from_trajectory_start(
    source_xosc_path: Path,
    input_channel_spec: ChannelSpecification,
    entity_refs: list[str] | None = None,
) -> list[InitPoseOverride]:
    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()

    init_privates = root.findall(".//Init//Private")
    if entity_refs is None:
        selected_entity_refs = [private.get("entityRef") for private in init_privates]
    else:
        selected_entity_refs = entity_refs

    with open_channel(input_channel_spec) as reader:
        first_msg = next(iter(reader), None)
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


def build_init_pose_overrides_from_close_to_trajectory_start(
    source_xosc_path: Path,
    input_channel_spec: ChannelSpecification,
    threshold_m: float,
    entity_refs: list[str] | None = None,
) -> list[InitPoseOverride]:
    init_overrides = build_init_pose_overrides_from_xosc_init(
        source_xosc_path=source_xosc_path,
        input_channel_spec=input_channel_spec,
        entity_refs=entity_refs,
    )
    trajectory_start_overrides = build_init_pose_overrides_from_trajectory_start(
        source_xosc_path=source_xosc_path,
        input_channel_spec=input_channel_spec,
        entity_refs=entity_refs,
    )
    trajectory_start_overrides_by_entity_ref = {
        override.entity_ref: override for override in trajectory_start_overrides
    }

    overrides: list[InitPoseOverride] = []
    for init_override in init_overrides:
        trajectory_start_override = trajectory_start_overrides_by_entity_ref[
            init_override.entity_ref
        ]
        target_x, target_y = compute_close_to_trajectory_start_xy(
            init_x=init_override.x,
            init_y=init_override.y,
            start_x=trajectory_start_override.x,
            start_y=trajectory_start_override.y,
            threshold_m=threshold_m,
        )
        overrides.append(
            InitPoseOverride(
                entity_ref=init_override.entity_ref,
                object_id=init_override.object_id,
                x=target_x,
                y=target_y,
                z=trajectory_start_override.z,
                yaw=trajectory_start_override.yaw,
                pitch=trajectory_start_override.pitch,
                roll=trajectory_start_override.roll,
            )
        )

    _validate_overrides(overrides)
    return overrides


def build_init_pose_overrides_from_xosc_init(
    source_xosc_path: Path,
    input_channel_spec: ChannelSpecification,
    entity_refs: list[str] | None = None,
) -> list[InitPoseOverride]:
    tree = etree.parse(str(source_xosc_path))
    root = tree.getroot()

    init_privates = root.findall(".//Init//Private")
    if entity_refs is None:
        selected_entity_refs = [private.get("entityRef") for private in init_privates]
    else:
        selected_entity_refs = entity_refs

    with open_channel(input_channel_spec) as reader:
        first_msg = next(iter(reader), None)
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
    source_reference_channel_spec: ChannelSpecification,
    output_xosc_path: Path,
    output_reference_channel_spec: ChannelSpecification,
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

                    moving_object.base.position.x = override.x
                    moving_object.base.position.y = override.y
                    moving_object.base.position.z = override.z
                    moving_object.base.orientation.yaw = override.yaw
                    moving_object.base.orientation.pitch = override.pitch
                    moving_object.base.orientation.roll = override.roll

            writer.write_message(msg_copy)

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
