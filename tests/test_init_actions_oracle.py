import math

from lxml import etree
from osi_utilities import ChannelSpecification, open_channel

from osc_validation.oracles import (
    InitActionCaseSpec,
    InitActionOracleActor,
    build_init_speed_action_case,
    build_init_teleport_action_case,
)
from osc_validation.utils.utils import rotatePointZYX


def _actor(speed_mps: float | None = None) -> InitActionOracleActor:
    return InitActionOracleActor(
        entity_ref="Ego",
        object_id=1,
        x=-290.0,
        y=-60.0,
        z=0.7015,
        yaw=0.25,
        pitch=0.1,
        roll=-0.05,
        speed_mps=speed_mps,
        bounding_box_center_x=1.8,
        bounding_box_center_y=0.2,
        bounding_box_center_z=0.6,
    )


def test_init_teleport_action_case_generates_xosc_and_stationary_reference(tmp_path):
    result = build_init_teleport_action_case(
        InitActionCaseSpec(
            output_xosc_path=tmp_path / "init_teleport.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_init_teleport.mcap",
                message_type="SensorView",
            ),
            actors=[_actor(speed_mps=3.0)],
            duration_s=0.1,
            sample_period_s=0.05,
        )
    )

    tree = etree.parse(str(result.xosc_path))
    private = tree.find(".//Storyboard/Init/Actions/Private[@entityRef='Ego']")
    speed_action = tree.find(".//Storyboard/Init/Actions//SpeedAction")
    world_position = private.find(".//TeleportAction//WorldPosition")
    bounding_box_center = tree.find(".//ScenarioObject[@name='Ego']//BoundingBox/Center")
    story = tree.find(".//Storyboard/Story")

    assert private is not None
    assert speed_action is None
    assert story is None
    assert bounding_box_center is not None
    assert bounding_box_center.get("x") == "1.8"
    assert bounding_box_center.get("y") == "0.2"
    assert bounding_box_center.get("z") == "0.6"
    assert world_position.get("x") == "-290.0"
    assert world_position.get("y") == "-60.0"
    assert world_position.get("z") == "0.7015"
    assert world_position.get("h") == "0.25"
    assert world_position.get("p") == "0.1"
    assert world_position.get("r") == "-0.05"

    with open_channel(result.reference_channel_spec) as reader:
        messages = list(reader)

    assert len(messages) == 3
    assert messages[1].timestamp.nanos == 50_000_000
    assert messages[1].global_ground_truth.timestamp.nanos == 50_000_000
    first_object = messages[0].global_ground_truth.moving_object[0]
    last_object = messages[-1].global_ground_truth.moving_object[0]
    center_dx, center_dy, center_dz = rotatePointZYX(1.8, 0.2, 0.6, 0.25, 0.1, -0.05)
    assert math.isclose(first_object.base.position.x, -290.0 + center_dx)
    assert math.isclose(first_object.base.position.y, -60.0 + center_dy)
    assert math.isclose(first_object.base.position.z, 0.7015 + center_dz)
    assert first_object.base.position.x == last_object.base.position.x
    assert first_object.base.position.y == last_object.base.position.y
    assert first_object.base.position.z == last_object.base.position.z
    assert first_object.base.velocity.x == 0.0


def test_init_speed_action_case_generates_speed_action_and_moving_reference(tmp_path):
    speed_mps = 4.0
    result = build_init_speed_action_case(
        InitActionCaseSpec(
            output_xosc_path=tmp_path / "init_speed.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_init_speed.mcap",
                message_type="SensorView",
            ),
            actors=[_actor(speed_mps=speed_mps)],
            duration_s=0.1,
            sample_period_s=0.05,
        )
    )

    tree = etree.parse(str(result.xosc_path))
    speed_action = tree.find(".//Storyboard/Init/Actions//SpeedAction")
    absolute_target_speed = tree.find(".//AbsoluteTargetSpeed")

    assert speed_action is not None
    assert absolute_target_speed is not None
    assert absolute_target_speed.get("value") == "4.0"

    with open_channel(result.reference_channel_spec) as reader:
        messages = list(reader)

    first_object = messages[0].global_ground_truth.moving_object[0]
    last_object = messages[-1].global_ground_truth.moving_object[0]
    expected_dx = math.cos(0.25) * speed_mps * 0.1
    assert math.isclose(
        last_object.base.position.x - first_object.base.position.x,
        expected_dx,
        abs_tol=1e-12,
    )
    assert math.isclose(last_object.base.velocity.x, math.cos(0.25) * speed_mps)
