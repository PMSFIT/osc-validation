from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from .xosc_builders import (
    WorldPosition,
    XoscHeader,
    XoscVehicle,
    append_simulation_time_stop_trigger,
    append_teleport_private_action,
    append_vehicle,
    append_world_position,
    build_open_scenario_root,
    write_xosc_tree,
)

@dataclass(frozen=True)
class TrajectoryInterpolationVertex:
    time_s: float
    x: float
    y: float
    z: float
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0


@dataclass(frozen=True)
class TrajectoryInterpolationActor:
    entity_ref: str
    object_id: int
    vertices: list[TrajectoryInterpolationVertex]
    bounding_box_center_x: float = 0.0
    bounding_box_center_y: float = 0.0
    bounding_box_center_z: float = 0.0
    length: float = 4.5
    width: float = 1.8
    height: float = 1.5
    vehicle_category: str = "car"


@dataclass(frozen=True)
class TrajectoryInterpolationXoscRequest:
    output_xosc_path: Path
    actor: TrajectoryInterpolationActor
    stop_time_s: float
    road_network_path: Path | None = None


@dataclass(frozen=True)
class TrajectoryInterpolationXoscResult:
    xosc_path: Path


def _float(value: float) -> str:
    return str(float(value))


def _validate_actor(actor: TrajectoryInterpolationActor) -> None:
    if len(actor.vertices) < 2:
        raise ValueError("At least two trajectory vertices are required.")
    for previous, current in zip(actor.vertices, actor.vertices[1:]):
        if previous.time_s >= current.time_s:
            raise ValueError("Trajectory vertex times must be strictly increasing.")


def _append_vehicle(
    xml_scenario_object: etree._Element,
    actor: TrajectoryInterpolationActor,
) -> None:
    append_vehicle(
        xml_scenario_object,
        XoscVehicle(
            name=f"{actor.entity_ref}_vehicle",
            category=actor.vehicle_category,
            center_x=_float(actor.bounding_box_center_x),
            center_y=_float(actor.bounding_box_center_y),
            center_z=_float(actor.bounding_box_center_z),
            height=_float(actor.height),
            length=_float(actor.length),
            width=_float(actor.width),
        ),
    )


def _append_world_position(
    xml_position: etree._Element,
    vertex: TrajectoryInterpolationVertex,
) -> None:
    append_world_position(
        xml_position,
        WorldPosition(
            x=vertex.x,
            y=vertex.y,
            z=vertex.z,
            h=vertex.yaw,
            p=vertex.pitch,
            r=vertex.roll,
        ),
    )


def _append_init_pose(
    xml_actions: etree._Element,
    actor: TrajectoryInterpolationActor,
) -> None:
    vertex = actor.vertices[0]
    append_teleport_private_action(
        xml_actions,
        actor.entity_ref,
        WorldPosition(
            x=vertex.x,
            y=vertex.y,
            z=vertex.z,
            h=vertex.yaw,
            p=vertex.pitch,
            r=vertex.roll,
        ),
    )


def _append_trajectory_action(
    xml_story: etree._Element,
    actor: TrajectoryInterpolationActor,
) -> None:
    xml_act = etree.SubElement(xml_story, "Act", name=f"{actor.entity_ref}_act")
    xml_maneuver_group = etree.SubElement(
        xml_act,
        "ManeuverGroup",
        name=f"{actor.entity_ref}_maneuver_group",
        maximumExecutionCount="1",
    )
    xml_actors = etree.SubElement(
        xml_maneuver_group,
        "Actors",
        selectTriggeringEntities="false",
    )
    etree.SubElement(xml_actors, "EntityRef", entityRef=actor.entity_ref)
    xml_maneuver = etree.SubElement(
        xml_maneuver_group,
        "Maneuver",
        name=f"{actor.entity_ref}_maneuver",
    )
    xml_event = etree.SubElement(
        xml_maneuver,
        "Event",
        name=f"{actor.entity_ref}_trajectory_event",
        priority="override",
    )
    xml_action = etree.SubElement(
        xml_event,
        "Action",
        name=f"{actor.entity_ref}_trajectory_action",
    )
    xml_private_action = etree.SubElement(xml_action, "PrivateAction")
    xml_routing_action = etree.SubElement(xml_private_action, "RoutingAction")
    xml_follow_trajectory_action = etree.SubElement(
        xml_routing_action,
        "FollowTrajectoryAction",
    )
    xml_trajectory_ref = etree.SubElement(
        xml_follow_trajectory_action,
        "TrajectoryRef",
    )
    xml_time_reference = etree.SubElement(
        xml_follow_trajectory_action,
        "TimeReference",
    )
    etree.SubElement(
        xml_time_reference,
        "Timing",
        domainAbsoluteRelative="relative",
        offset="0.0",
        scale="1.0",
    )
    etree.SubElement(
        xml_follow_trajectory_action,
        "TrajectoryFollowingMode",
        followingMode="position",
    )

    xml_trajectory = etree.SubElement(
        xml_trajectory_ref,
        "Trajectory",
        closed="false",
        name=f"{actor.entity_ref}_trajectory",
    )
    xml_shape = etree.SubElement(xml_trajectory, "Shape")
    xml_polyline = etree.SubElement(xml_shape, "Polyline")
    for vertex in actor.vertices:
        xml_vertex = etree.SubElement(
            xml_polyline,
            "Vertex",
            time=_float(vertex.time_s),
        )
        xml_position = etree.SubElement(xml_vertex, "Position")
        _append_world_position(xml_position, vertex)


def build_trajectory_interpolation_xosc(
    request: TrajectoryInterpolationXoscRequest,
) -> TrajectoryInterpolationXoscResult:
    _validate_actor(request.actor)
    if request.stop_time_s < request.actor.vertices[-1].time_s:
        raise ValueError("stop_time_s must be at or after the last vertex time.")

    xml_root, xml_entities, xml_storyboard = build_open_scenario_root(
        XoscHeader(
            author="OSC Validation Trajectory Interpolation Oracle",
            description="Trajectory interpolation validation scenario",
        ),
        request.road_network_path,
    )

    xml_scenario_object = etree.SubElement(
        xml_entities,
        "ScenarioObject",
        name=request.actor.entity_ref,
    )
    _append_vehicle(xml_scenario_object, request.actor)

    xml_init = etree.SubElement(xml_storyboard, "Init")
    xml_actions = etree.SubElement(xml_init, "Actions")
    _append_init_pose(xml_actions, request.actor)

    xml_story = etree.SubElement(xml_storyboard, "Story", name="Story1")
    _append_trajectory_action(xml_story, request.actor)

    append_simulation_time_stop_trigger(xml_storyboard, request.stop_time_s)

    write_xosc_tree(request.output_xosc_path, xml_root)
    return TrajectoryInterpolationXoscResult(xosc_path=request.output_xosc_path)
