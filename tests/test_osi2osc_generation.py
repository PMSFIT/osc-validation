from pathlib import Path

from lxml import etree
import pytest

from osi_utilities import ChannelSpecification, open_channel_writer

from osc_validation.generation.osi2osc import (
    OSI2OSCMovingObject,
    osi2osc,
    parse_moving_objects,
)
from tests.conftest import _make_ground_truth, _make_sensor_view


def _configure_vehicle(moving_object, obj_id: int, x: float, y: float) -> None:
    moving_object.id.value = obj_id
    moving_object.base.position.x = x
    moving_object.base.position.y = y
    moving_object.base.position.z = 0.0
    moving_object.base.orientation.yaw = 0.1 * obj_id
    moving_object.base.orientation.pitch = 0.0
    moving_object.base.orientation.roll = 0.0
    moving_object.base.dimension.length = 4.5
    moving_object.base.dimension.width = 1.8
    moving_object.base.dimension.height = 1.5
    moving_object.vehicle_classification.type = 4  # car


def _make_sensor_view_frame(
    timestamp_s: float,
    host_vehicle_id: int,
    ego_x: float,
    other_x: float,
):
    sensor_view = _make_sensor_view(timestamp_s, obj_id=2)
    sensor_view.host_vehicle_id.value = host_vehicle_id
    sensor_view.global_ground_truth.host_vehicle_id.value = host_vehicle_id

    ego = sensor_view.global_ground_truth.moving_object[0]
    _configure_vehicle(ego, obj_id=2, x=ego_x, y=1.0)

    other = sensor_view.global_ground_truth.moving_object.add()
    _configure_vehicle(other, obj_id=1, x=other_x, y=5.0)
    return sensor_view


def _make_ground_truth_frame(
    timestamp_s: float,
    host_vehicle_id: int,
    ego_x: float,
    other_x: float,
):
    ground_truth = _make_ground_truth(timestamp_s, obj_id=2)
    ground_truth.host_vehicle_id.value = host_vehicle_id

    ego = ground_truth.moving_object[0]
    _configure_vehicle(ego, obj_id=2, x=ego_x, y=1.0)

    other = ground_truth.moving_object.add()
    _configure_vehicle(other, obj_id=1, x=other_x, y=5.0)
    return ground_truth


def test_parse_moving_objects_sensorview(tmp_path):
    trace_path = tmp_path / "sensorview_trace.osi"
    with open_channel_writer(
        ChannelSpecification(path=trace_path, message_type="SensorView")
    ) as writer:
        writer.write_message(
            _make_sensor_view_frame(0.0, host_vehicle_id=2, ego_x=10.0, other_x=0.0)
        )
        writer.write_message(
            _make_sensor_view_frame(0.1, host_vehicle_id=2, ego_x=11.0, other_x=1.0)
        )

    objects = parse_moving_objects(
        ChannelSpecification(path=trace_path, message_type="SensorView"),
        host_vehicle_id=2,
    )

    assert {obj.id for obj in objects} == {1, 2}
    ego = next(obj for obj in objects if obj.id == 2)
    other = next(obj for obj in objects if obj.id == 1)
    assert ego.entity_ref == "Ego"
    assert other.entity_ref == "osi_moving_object_1"
    assert ego.trajectory["x"].tolist() == [10.0, 11.0]
    assert other.trajectory["x"].tolist() == [0.0, 1.0]


def test_parse_moving_objects_groundtruth(tmp_path):
    trace_path = tmp_path / "groundtruth_trace.osi"
    with open_channel_writer(
        ChannelSpecification(path=trace_path, message_type="GroundTruth")
    ) as writer:
        writer.write_message(
            _make_ground_truth_frame(0.0, host_vehicle_id=2, ego_x=10.0, other_x=0.0)
        )
        writer.write_message(
            _make_ground_truth_frame(0.1, host_vehicle_id=2, ego_x=11.0, other_x=1.0)
        )

    objects = parse_moving_objects(
        ChannelSpecification(path=trace_path, message_type="GroundTruth"),
        host_vehicle_id=2,
    )

    assert {obj.id for obj in objects} == {1, 2}
    ego = next(obj for obj in objects if obj.id == 2)
    assert ego.entity_ref == "Ego"
    assert ego.trajectory["timestamp"].tolist() == [0.0, 0.1]


def test_osi2osc_generates_expected_structure(tmp_path):
    trace_path = tmp_path / "input_trace.osi"
    with open_channel_writer(
        ChannelSpecification(path=trace_path, message_type="SensorView")
    ) as writer:
        writer.write_message(
            _make_sensor_view_frame(0.0, host_vehicle_id=2, ego_x=10.0, other_x=0.0)
        )
        writer.write_message(
            _make_sensor_view_frame(0.1, host_vehicle_id=2, ego_x=11.0, other_x=1.0)
        )
    xodr_path = tmp_path / "map.xodr"
    xodr_path.write_text("dummy map", encoding="utf-8")
    xosc_path = tmp_path / "scenario.xosc"

    result = osi2osc(
        ChannelSpecification(path=trace_path, message_type="SensorView"),
        xosc_path,
        xodr_path,
    )

    tree = etree.parse(str(result))
    scenario_objects = tree.findall(".//Entities/ScenarioObject")
    private_actions = tree.findall(".//Storyboard/Init/Actions/Private")
    trajectories = tree.findall(".//Trajectory")
    stop_condition = tree.find(".//StopTrigger//SimulationTimeCondition")
    logic_file = tree.find(".//RoadNetwork/LogicFile")

    assert [obj.get("name") for obj in scenario_objects] == [
        "Ego",
        "osi_moving_object_1",
    ]
    assert [action.get("entityRef") for action in private_actions] == [
        "Ego",
        "osi_moving_object_1",
    ]
    assert len(trajectories) == 2
    assert all(len(trajectory.findall(".//Vertex")) == 2 for trajectory in trajectories)
    assert stop_condition is not None
    assert stop_condition.get("value") == "0.1"
    assert logic_file is not None
    assert logic_file.get("filepath") == str(xodr_path)


def test_osi2osc_without_matching_host_vehicle_keeps_generic_names(tmp_path):
    trace_path = tmp_path / "gt_trace.osi"
    with open_channel_writer(
        ChannelSpecification(path=trace_path, message_type="GroundTruth")
    ) as writer:
        writer.write_message(
            _make_ground_truth_frame(0.0, host_vehicle_id=99, ego_x=10.0, other_x=0.0)
        )
        writer.write_message(
            _make_ground_truth_frame(0.1, host_vehicle_id=99, ego_x=11.0, other_x=1.0)
        )
    xosc_path = tmp_path / "scenario.xosc"

    result = osi2osc(
        ChannelSpecification(path=trace_path, message_type="GroundTruth"),
        xosc_path,
    )

    tree = etree.parse(str(result))
    scenario_objects = tree.findall(".//Entities/ScenarioObject")
    assert [obj.get("name") for obj in scenario_objects] == [
        "osi_moving_object_2",
        "osi_moving_object_1",
    ]


def test_osi2osc_rejects_empty_trace(tmp_path):
    trace_path = tmp_path / "empty.osi"
    with open_channel_writer(
        ChannelSpecification(path=trace_path, message_type="SensorView")
    ):
        pass

    with pytest.raises(ValueError, match="is empty"):
        osi2osc(
            ChannelSpecification(path=trace_path, message_type="SensorView"),
            tmp_path / "scenario.xosc",
        )


def test_build_osc_scenario_object_rejects_unmapped_vehicle_type():
    moving_object = OSI2OSCMovingObject(
        id="1",
        length_static=4.5,
        width_static=1.8,
        height_static=1.5,
        type=0,
        vehicle_type=0,
    )

    with pytest.raises(
        AssertionError, match="Missing OSI2OSC mapping for vehicle category."
    ):
        moving_object.build_osc_scenario_object()
