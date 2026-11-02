"""XOSC init-pose edits and override discovery for recorded replay cases."""

from pathlib import Path
import re
from lxml import etree
from osi_utilities import ChannelSpecification, open_channel
from osc_validation.utils.utils import compute_close_to_trajectory_start_xy
from .models import InitPoseOverride, _validate_overrides


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
            first_msg.host_vehicle_id.value
            if hasattr(first_msg, "host_vehicle_id")
            else None
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
