from pathlib import Path

from lxml import etree

from ..xosc_builders import (
    WorldPosition,
    XoscHeader,
    XoscVehicle,
    append_simulation_time_stop_trigger,
    append_vehicle,
    append_world_position,
    build_open_scenario_root,
    write_xosc_tree,
)
from .models import InitActionActor, InitActionsXoscRequest, InitActionsXoscResult


def _float(value: float) -> str:
    return str(float(value))


def _build_vehicle(actor: InitActionActor) -> etree._Element:
    return append_vehicle(
        etree.Element("ScenarioObject"),
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


def _append_world_position(xml_position: etree._Element, actor: InitActionActor) -> None:
    append_world_position(
        xml_position,
        WorldPosition(
            x=actor.x,
            y=actor.y,
            z=actor.z,
            h=actor.yaw,
            p=actor.pitch,
            r=actor.roll,
        ),
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

    xml_root, xml_entities, xml_storyboard = build_open_scenario_root(
        XoscHeader(
            author="OSC Validation InitActions Oracle",
            description="InitActions validation scenario",
        ),
        request.road_network_path,
    )

    for actor in request.actors:
        xml_scenario_object = etree.SubElement(
            xml_entities, "ScenarioObject", name=actor.entity_ref
        )
        xml_scenario_object.append(_build_vehicle(actor))

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

    append_simulation_time_stop_trigger(xml_storyboard, request.stop_time_s)

    write_xosc_tree(request.output_xosc_path, xml_root)
    return InitActionsXoscResult(xosc_path=request.output_xosc_path)
