import pytest

from lxml import etree

from osc_validation.generation.xosc_builders import (
    WorldPosition,
    Orientation,
    RoadPosition,
    LanePosition,
    append_position,
    append_teleport_private_action,
    XoscVehicle,
    append_simulation_time_condition,
    append_simulation_time_stop_trigger,
    append_vehicle,
    append_world_position,
    replace_start_trigger,
)


def test_append_vehicle_includes_standard_children():
    parent = etree.Element("ScenarioObject")

    append_vehicle(
        parent,
        XoscVehicle(
            name="Ego_vehicle",
            category="car",
            center_x="1.0",
            center_y="0.0",
            center_z="0.5",
            height="1.5",
            length="4.5",
            width="1.8",
        ),
    )

    vehicle = parent.find("Vehicle")
    assert vehicle is not None
    assert vehicle.find("BoundingBox") is not None
    assert vehicle.find("Performance") is not None
    assert vehicle.find("Axles/FrontAxle") is not None
    assert vehicle.find("Axles/RearAxle") is not None
    assert vehicle.find("Properties") is not None


def test_append_world_position_serializes_values_as_floats():
    parent = etree.Element("Position")

    world_position = append_world_position(
        parent,
        WorldPosition(x=1, y="2", z=3.25, h=0, p="0.5", r=-1),
    )

    assert world_position.attrib == {
        "x": "1.0",
        "y": "2.0",
        "z": "3.25",
        "h": "0.0",
        "p": "0.5",
        "r": "-1.0",
    }


def test_append_simulation_time_stop_trigger_shape():
    storyboard = etree.Element("Storyboard")

    append_simulation_time_stop_trigger(storyboard, 4)

    condition = storyboard.find(".//StopTrigger/ConditionGroup/Condition")
    simulation_time = storyboard.find(".//StopTrigger//SimulationTimeCondition")
    assert condition is not None
    assert condition.get("name") == "End"
    assert condition.get("delay") == "0.0"
    assert condition.get("conditionEdge") == "rising"
    assert simulation_time is not None
    assert simulation_time.get("value") == "4.0"
    assert simulation_time.get("rule") == "greaterOrEqual"


def test_replace_start_trigger_removes_existing_start_trigger():
    event = etree.Element("Event")
    etree.SubElement(event, "StartTrigger").set("old", "true")

    replace_start_trigger(
        event,
        lambda condition_group: append_simulation_time_condition(
            condition_group,
            condition_name="start",
            trigger_delay=1.5,
            trigger_rule="greaterThan",
        ),
    )

    start_triggers = event.findall("StartTrigger")
    assert len(start_triggers) == 1
    assert start_triggers[0].get("old") is None
    simulation_time = event.find(".//SimulationTimeCondition")
    assert simulation_time is not None
    assert simulation_time.get("value") == "1.5"


@pytest.mark.parametrize(
    "position, tag, attributes",
    [
        (
            RoadPosition("road", 20, 2),
            "RoadPosition",
            {"roadId": "road", "s": "20.0", "t": "2.0"},
        ),
        (
            LanePosition("road", 1, 20, -4),
            "LanePosition",
            {"roadId": "road", "laneId": "1", "s": "20.0", "offset": "-4.0"},
        ),
    ],
)
def test_teleport_road_lane_position_omits_orientation(position, tag, attributes):
    parent = etree.Element("Actions")
    append_teleport_private_action(parent, "Ego", position)
    container = parent.find("Private/PrivateAction/TeleportAction/Position")
    assert len(container) == 1
    assert container[0].tag == tag
    assert dict(container[0].attrib) == attributes
    assert container.find(".//Orientation") is None


@pytest.mark.parametrize("position_type", [RoadPosition, LanePosition])
@pytest.mark.parametrize("orientation_type", ["relative", "absolute"])
@pytest.mark.parametrize("as_float", [True, False])
def test_road_lane_orientation_serialization(position_type, orientation_type, as_float):
    orientation = Orientation(h="3.14", p="0", r="-0.25", type=orientation_type)
    position = (
        RoadPosition("1", "20", "2", orientation)
        if position_type is RoadPosition
        else LanePosition("1", "-1", "20", "0", orientation)
    )
    parent = etree.Element("Position")
    element = append_position(parent, position, as_float=as_float)
    assert len(element) == 1
    assert element[0].tag == "Orientation"
    assert dict(element[0].attrib) == {
        "type": orientation_type,
        "h": "3.14",
        "p": "0.0" if as_float else "0",
        "r": "-0.25",
    }
    assert element.get("s") == ("20.0" if as_float else "20")
