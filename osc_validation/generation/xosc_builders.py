from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from lxml import etree


@dataclass(frozen=True)
class XoscHeader:
    rev_major: int | str = 1
    rev_minor: int | str = 3
    author: str = ""
    description: str = ""
    license_name: str = ""
    license_resource: str = ""


@dataclass(frozen=True)
class XoscVehicle:
    name: str
    category: str
    center_x: float | str
    center_y: float | str
    center_z: float | str
    height: float | str
    length: float | str
    width: float | str
    max_acceleration: str = "4.0"
    max_deceleration: str = "9.0"
    max_speed: str = "250.0"
    front_max_steering: str = "0.5"
    front_position_x: str = "2.7"
    front_position_z: str = "0.4"
    front_track_width: str = "1.63"
    front_wheel_diameter: str = "0.8"
    rear_max_steering: str = "0.0"
    rear_position_x: str = "0.0"
    rear_position_z: str = "0.4"
    rear_track_width: str = "1.63"
    rear_wheel_diameter: str = "0.8"
    include_properties: bool = True


@dataclass(frozen=True)
class WorldPosition:
    x: float | str
    y: float | str
    z: float | str
    h: float | str = 0.0
    p: float | str = 0.0
    r: float | str = 0.0


ElementBuilder = Callable[[etree._Element], etree._Element]


def _float(value: float | str) -> str:
    return str(float(value))


def _string(value: float | str) -> str:
    return str(value)


def write_xosc_tree(path: Path | str, root: etree._Element) -> None:
    etree.ElementTree(root).write(
        str(path), encoding="utf-8", xml_declaration=True, pretty_print=True
    )


def build_open_scenario_root(
    header: XoscHeader,
    road_network_path: Path | str | None,
) -> tuple[etree._Element, etree._Element, etree._Element]:
    root = etree.Element("OpenSCENARIO")
    file_header = etree.SubElement(
        root,
        "FileHeader",
        revMajor=str(header.rev_major),
        revMinor=str(header.rev_minor),
        date=datetime.today().strftime("%Y-%m-%dT%H:%M:%S"),
        author=header.author,
        description=header.description,
    )
    etree.SubElement(
        file_header,
        "License",
        name=header.license_name,
        resource=header.license_resource,
    )
    etree.SubElement(root, "CatalogLocations")
    road_network = etree.SubElement(root, "RoadNetwork")
    if road_network_path is not None:
        etree.SubElement(road_network, "LogicFile", filepath=str(road_network_path))
    entities = etree.SubElement(root, "Entities")
    storyboard = etree.SubElement(root, "Storyboard")
    return root, entities, storyboard


def append_vehicle(parent: etree._Element, vehicle: XoscVehicle) -> etree._Element:
    xml_vehicle = etree.SubElement(
        parent,
        "Vehicle",
        name=vehicle.name,
        vehicleCategory=vehicle.category,
    )
    bounding_box = etree.SubElement(xml_vehicle, "BoundingBox")
    etree.SubElement(
        bounding_box,
        "Center",
        x=_string(vehicle.center_x),
        y=_string(vehicle.center_y),
        z=_string(vehicle.center_z),
    )
    etree.SubElement(
        bounding_box,
        "Dimensions",
        height=_string(vehicle.height),
        length=_string(vehicle.length),
        width=_string(vehicle.width),
    )
    etree.SubElement(
        xml_vehicle,
        "Performance",
        maxAcceleration=vehicle.max_acceleration,
        maxDeceleration=vehicle.max_deceleration,
        maxSpeed=vehicle.max_speed,
    )
    axles = etree.SubElement(xml_vehicle, "Axles")
    etree.SubElement(
        axles,
        "FrontAxle",
        maxSteering=vehicle.front_max_steering,
        positionX=vehicle.front_position_x,
        positionZ=vehicle.front_position_z,
        trackWidth=vehicle.front_track_width,
        wheelDiameter=vehicle.front_wheel_diameter,
    )
    etree.SubElement(
        axles,
        "RearAxle",
        maxSteering=vehicle.rear_max_steering,
        positionX=vehicle.rear_position_x,
        positionZ=vehicle.rear_position_z,
        trackWidth=vehicle.rear_track_width,
        wheelDiameter=vehicle.rear_wheel_diameter,
    )
    if vehicle.include_properties:
        etree.SubElement(xml_vehicle, "Properties")
    return xml_vehicle


def append_world_position(
    parent: etree._Element,
    position: WorldPosition,
    *,
    as_float: bool = True,
) -> etree._Element:
    serialize = _float if as_float else _string
    return etree.SubElement(
        parent,
        "WorldPosition",
        x=serialize(position.x),
        y=serialize(position.y),
        z=serialize(position.z),
        h=serialize(position.h),
        p=serialize(position.p),
        r=serialize(position.r),
    )


def append_teleport_private_action(
    parent: etree._Element,
    entity_ref: str,
    position: WorldPosition,
    *,
    as_float: bool = True,
) -> etree._Element:
    private = etree.SubElement(parent, "Private", entityRef=entity_ref)
    private_action = etree.SubElement(private, "PrivateAction")
    teleport_action = etree.SubElement(private_action, "TeleportAction")
    xml_position = etree.SubElement(teleport_action, "Position")
    append_world_position(xml_position, position, as_float=as_float)
    return private


def append_simulation_time_stop_trigger(
    storyboard: etree._Element,
    stop_time_s: float | str,
    *,
    condition_name: str = "End",
    delay: str = "0.0",
    rule: str = "greaterOrEqual",
    as_float: bool = True,
) -> etree._Element:
    stop_trigger = etree.SubElement(storyboard, "StopTrigger")
    condition_group = etree.SubElement(stop_trigger, "ConditionGroup")
    condition = etree.SubElement(
        condition_group,
        "Condition",
        name=condition_name,
        delay=delay,
        conditionEdge="rising",
    )
    by_value_condition = etree.SubElement(condition, "ByValueCondition")
    etree.SubElement(
        by_value_condition,
        "SimulationTimeCondition",
        value=(_float(stop_time_s) if as_float else _string(stop_time_s)),
        rule=rule,
    )
    return stop_trigger


def replace_start_trigger(
    event: etree._Element,
    condition_builder: ElementBuilder,
) -> etree._Element:
    old_start = event.find("StartTrigger")
    if old_start is not None:
        event.remove(old_start)

    start_trigger = etree.SubElement(event, "StartTrigger")
    condition_group = etree.SubElement(start_trigger, "ConditionGroup")
    condition_builder(condition_group)
    return start_trigger


def append_speed_condition(
    condition_group: etree._Element,
    *,
    condition_name: str,
    trigger_entity_ref: str,
    trigger_speed_mps: float,
    trigger_rule: str,
    condition_edge: str,
    condition_delay_s: float,
) -> etree._Element:
    condition = _append_entity_condition(
        condition_group,
        condition_name=condition_name,
        trigger_entity_ref=trigger_entity_ref,
        delay=str(condition_delay_s),
        condition_edge=condition_edge,
    )
    entity_condition = condition.find(".//EntityCondition")
    etree.SubElement(
        entity_condition,
        "SpeedCondition",
        value=str(trigger_speed_mps),
        rule=trigger_rule,
    )
    return condition


def append_distance_to_position_condition(
    condition_group: etree._Element,
    *,
    condition_name: str,
    trigger_entity_ref: str,
    trigger_distance_m: float,
    trigger_rule: str,
    target_position: WorldPosition,
    relative_distance_type: str,
    condition_delay_s: float,
) -> etree._Element:
    condition = _append_entity_condition(
        condition_group,
        condition_name=condition_name,
        trigger_entity_ref=trigger_entity_ref,
        delay=str(condition_delay_s),
        condition_edge="rising",
    )
    entity_condition = condition.find(".//EntityCondition")
    distance_condition = etree.SubElement(
        entity_condition,
        "DistanceCondition",
        value=str(trigger_distance_m),
        rule=trigger_rule,
        freespace="false",
        coordinateSystem="entity",
        relativeDistanceType=relative_distance_type,
    )
    xml_position = etree.SubElement(distance_condition, "Position")
    append_world_position(xml_position, target_position, as_float=False)
    return condition


def append_time_to_collision_position_condition(
    condition_group: etree._Element,
    *,
    condition_name: str,
    trigger_entity_ref: str,
    trigger_ttc_s: float,
    trigger_rule: str,
    target_position: WorldPosition,
) -> etree._Element:
    condition = _append_entity_condition(
        condition_group,
        condition_name=condition_name,
        trigger_entity_ref=trigger_entity_ref,
        delay="0",
        condition_edge="rising",
    )
    entity_condition = condition.find(".//EntityCondition")
    ttc_condition = etree.SubElement(
        entity_condition,
        "TimeToCollisionCondition",
        value=str(trigger_ttc_s),
        rule=trigger_rule,
        freespace="false",
        coordinateSystem="entity",
        relativeDistanceType="euclidianDistance",
    )
    ttc_target = etree.SubElement(ttc_condition, "TimeToCollisionConditionTarget")
    xml_position = etree.SubElement(ttc_target, "Position")
    append_world_position(xml_position, target_position, as_float=False)
    return condition


def append_simulation_time_condition(
    condition_group: etree._Element,
    *,
    condition_name: str,
    trigger_delay: float,
    trigger_rule: str,
    delay: str = "0",
    condition_edge: str = "rising",
) -> etree._Element:
    condition = etree.SubElement(
        condition_group,
        "Condition",
        name=condition_name,
        delay=delay,
        conditionEdge=condition_edge,
    )
    by_value = etree.SubElement(condition, "ByValueCondition")
    etree.SubElement(
        by_value,
        "SimulationTimeCondition",
        value=str(trigger_delay),
        rule=trigger_rule,
    )
    return condition


def append_traveled_distance_condition(
    condition_group: etree._Element,
    *,
    condition_name: str,
    trigger_entity_ref: str,
    trigger_distance_m: float,
) -> etree._Element:
    condition = _append_entity_condition(
        condition_group,
        condition_name=condition_name,
        trigger_entity_ref=trigger_entity_ref,
        delay="0",
        condition_edge="rising",
    )
    entity_condition = condition.find(".//EntityCondition")
    etree.SubElement(
        entity_condition,
        "TraveledDistanceCondition",
        value=str(trigger_distance_m),
    )
    return condition


def append_storyboard_element_state_condition(
    condition_group: etree._Element,
    *,
    condition_name: str,
    storyboard_element_type: str,
    storyboard_element_ref: str,
    delay: str = "0",
    condition_edge: str = "rising",
) -> etree._Element:
    condition = etree.SubElement(
        condition_group,
        "Condition",
        name=condition_name,
        delay=delay,
        conditionEdge=condition_edge,
    )
    by_value = etree.SubElement(condition, "ByValueCondition")
    etree.SubElement(
        by_value,
        "StoryboardElementStateCondition",
        storyboardElementType=storyboard_element_type,
        storyboardElementRef=storyboard_element_ref,
        state="completeState",
    )
    return condition


def _append_entity_condition(
    condition_group: etree._Element,
    *,
    condition_name: str,
    trigger_entity_ref: str,
    delay: str,
    condition_edge: str,
) -> etree._Element:
    condition = etree.SubElement(
        condition_group,
        "Condition",
        name=condition_name,
        delay=delay,
        conditionEdge=condition_edge,
    )
    by_entity_condition = etree.SubElement(condition, "ByEntityCondition")
    triggering_entities = etree.SubElement(
        by_entity_condition,
        "TriggeringEntities",
        triggeringEntitiesRule="any",
    )
    etree.SubElement(triggering_entities, "EntityRef", entityRef=trigger_entity_ref)
    etree.SubElement(by_entity_condition, "EntityCondition")
    return condition
