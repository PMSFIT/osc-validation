from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lxml import etree


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
    xml_vehicle = etree.SubElement(
        xml_scenario_object,
        "Vehicle",
        name=f"{actor.entity_ref}_vehicle",
        vehicleCategory=actor.vehicle_category,
    )
    xml_bounding_box = etree.SubElement(xml_vehicle, "BoundingBox")
    etree.SubElement(
        xml_bounding_box,
        "Center",
        x=_float(actor.bounding_box_center_x),
        y=_float(actor.bounding_box_center_y),
        z=_float(actor.bounding_box_center_z),
    )
    etree.SubElement(
        xml_bounding_box,
        "Dimensions",
        height=_float(actor.height),
        length=_float(actor.length),
        width=_float(actor.width),
    )
    etree.SubElement(
        xml_vehicle,
        "Performance",
        maxAcceleration="4.0",
        maxDeceleration="9.0",
        maxSpeed="250.0",
    )
    xml_axles = etree.SubElement(xml_vehicle, "Axles")
    etree.SubElement(
        xml_axles,
        "FrontAxle",
        maxSteering="0.5",
        positionX="2.7",
        positionZ="0.4",
        trackWidth="1.63",
        wheelDiameter="0.8",
    )
    etree.SubElement(
        xml_axles,
        "RearAxle",
        maxSteering="0.0",
        positionX="0.0",
        positionZ="0.4",
        trackWidth="1.63",
        wheelDiameter="0.8",
    )
    etree.SubElement(xml_vehicle, "Properties")


def _append_world_position(
    xml_position: etree._Element,
    vertex: TrajectoryInterpolationVertex,
) -> None:
    etree.SubElement(
        xml_position,
        "WorldPosition",
        x=_float(vertex.x),
        y=_float(vertex.y),
        z=_float(vertex.z),
        h=_float(vertex.yaw),
        p=_float(vertex.pitch),
        r=_float(vertex.roll),
    )


def _append_init_pose(
    xml_actions: etree._Element,
    actor: TrajectoryInterpolationActor,
) -> None:
    xml_private = etree.SubElement(xml_actions, "Private", entityRef=actor.entity_ref)
    xml_private_action = etree.SubElement(xml_private, "PrivateAction")
    xml_teleport_action = etree.SubElement(xml_private_action, "TeleportAction")
    xml_position = etree.SubElement(xml_teleport_action, "Position")
    _append_world_position(xml_position, actor.vertices[0])


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

    xml_root = etree.Element("OpenSCENARIO")
    xml_file_header = etree.SubElement(
        xml_root,
        "FileHeader",
        revMajor="1",
        revMinor="3",
        date=datetime.today().strftime("%Y-%m-%dT%H:%M:%S"),
        author="OSC Validation Trajectory Interpolation Oracle",
        description="Trajectory interpolation validation scenario",
    )
    etree.SubElement(xml_file_header, "License", name="", resource="")
    etree.SubElement(xml_root, "CatalogLocations")
    xml_road_network = etree.SubElement(xml_root, "RoadNetwork")
    if request.road_network_path is not None:
        etree.SubElement(
            xml_road_network,
            "LogicFile",
            filepath=str(request.road_network_path),
        )

    xml_entities = etree.SubElement(xml_root, "Entities")
    xml_scenario_object = etree.SubElement(
        xml_entities,
        "ScenarioObject",
        name=request.actor.entity_ref,
    )
    _append_vehicle(xml_scenario_object, request.actor)

    xml_storyboard = etree.SubElement(xml_root, "Storyboard")
    xml_init = etree.SubElement(xml_storyboard, "Init")
    xml_actions = etree.SubElement(xml_init, "Actions")
    _append_init_pose(xml_actions, request.actor)

    xml_story = etree.SubElement(xml_storyboard, "Story", name="Story1")
    _append_trajectory_action(xml_story, request.actor)

    xml_stop_trigger = etree.SubElement(xml_storyboard, "StopTrigger")
    xml_condition_group = etree.SubElement(xml_stop_trigger, "ConditionGroup")
    xml_condition = etree.SubElement(
        xml_condition_group,
        "Condition",
        name="End",
        delay="0.0",
        conditionEdge="rising",
    )
    xml_by_value_condition = etree.SubElement(xml_condition, "ByValueCondition")
    etree.SubElement(
        xml_by_value_condition,
        "SimulationTimeCondition",
        value=_float(request.stop_time_s),
        rule="greaterOrEqual",
    )

    xml_tree = etree.ElementTree(xml_root)
    xml_tree.write(
        str(request.output_xosc_path),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )
    return TrajectoryInterpolationXoscResult(xosc_path=request.output_xosc_path)
