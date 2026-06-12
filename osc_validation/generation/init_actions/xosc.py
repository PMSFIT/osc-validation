from datetime import datetime
from pathlib import Path

from lxml import etree

from .models import InitActionActor, InitActionsXoscRequest, InitActionsXoscResult


def _float(value: float) -> str:
    return str(float(value))


def _build_vehicle(actor: InitActionActor) -> etree._Element:
    xml_vehicle = etree.Element(
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
    return xml_vehicle


def _append_world_position(xml_position: etree._Element, actor: InitActionActor) -> None:
    etree.SubElement(
        xml_position,
        "WorldPosition",
        x=_float(actor.x),
        y=_float(actor.y),
        z=_float(actor.z),
        h=_float(actor.yaw),
        p=_float(actor.pitch),
        r=_float(actor.roll),
    )


def _append_teleport_action(
    xml_private: etree._Element, actor: InitActionActor
) -> None:
    xml_private_action = etree.SubElement(xml_private, "PrivateAction")
    xml_teleport_action = etree.SubElement(xml_private_action, "TeleportAction")
    xml_position = etree.SubElement(xml_teleport_action, "Position")
    _append_world_position(xml_position, actor)


def _append_add_entity_action(
    xml_actions: etree._Element, actor: InitActionActor
) -> None:
    xml_global_action = etree.SubElement(xml_actions, "GlobalAction")
    xml_entity_action = etree.SubElement(
        xml_global_action, "EntityAction", entityRef=actor.entity_ref
    )
    xml_add_entity_action = etree.SubElement(xml_entity_action, "AddEntityAction")
    xml_position = etree.SubElement(xml_add_entity_action, "Position")
    _append_world_position(xml_position, actor)


def _append_speed_action(xml_private: etree._Element, actor: InitActionActor) -> None:
    if actor.speed_mps is None:
        return
    if actor.speed_mps < 0.0:
        raise ValueError("speed_mps must be >= 0.0.")

    xml_private_action = etree.SubElement(xml_private, "PrivateAction")
    xml_longitudinal_action = etree.SubElement(xml_private_action, "LongitudinalAction")
    xml_speed_action = etree.SubElement(xml_longitudinal_action, "SpeedAction")
    etree.SubElement(
        xml_speed_action,
        "SpeedActionDynamics",
        dynamicsDimension="time",
        dynamicsShape="step",
        value="0.0",
    )
    xml_speed_action_target = etree.SubElement(xml_speed_action, "SpeedActionTarget")
    etree.SubElement(
        xml_speed_action_target,
        "AbsoluteTargetSpeed",
        value=_float(actor.speed_mps),
    )


def build_init_actions_xosc(request: InitActionsXoscRequest) -> InitActionsXoscResult:
    if not request.actors:
        raise ValueError("At least one actor is required.")
    if request.stop_time_s <= 0.0:
        raise ValueError("stop_time_s must be > 0.0.")

    xml_root = etree.Element("OpenSCENARIO")
    xml_file_header = etree.SubElement(
        xml_root,
        "FileHeader",
        revMajor="1",
        revMinor="3",
        date=datetime.today().strftime("%Y-%m-%dT%H:%M:%S"),
        author="OSC Validation InitActions Oracle",
        description="InitActions validation scenario",
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
    for actor in request.actors:
        xml_scenario_object = etree.SubElement(
            xml_entities, "ScenarioObject", name=actor.entity_ref
        )
        xml_scenario_object.append(_build_vehicle(actor))

    xml_storyboard = etree.SubElement(xml_root, "Storyboard")
    xml_init = etree.SubElement(xml_storyboard, "Init")
    xml_actions = etree.SubElement(xml_init, "Actions")
    for actor in request.actors:
        if request.include_add_entity_actions:
            _append_add_entity_action(xml_actions, actor)

    for actor in request.actors:
        if not request.include_teleport_actions and actor.speed_mps is None:
            continue
        xml_private = etree.SubElement(
            xml_actions, "Private", entityRef=actor.entity_ref
        )
        if request.include_teleport_actions:
            _append_teleport_action(xml_private, actor)
        _append_speed_action(xml_private, actor)

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
    return InitActionsXoscResult(xosc_path=request.output_xosc_path)
