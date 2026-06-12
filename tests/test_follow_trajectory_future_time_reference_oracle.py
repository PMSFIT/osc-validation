import math

from lxml import etree
from osi_utilities import ChannelSpecification, open_channel

from osc_validation.generation import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from osc_validation.oracles import (
    FollowTrajectoryFutureTimeReferenceCaseSpec,
    build_follow_trajectory_future_time_reference_case,
)


def test_future_time_reference_case_generates_speed_action_and_delayed_teleport_reference(
    tmp_path,
):
    actor = TrajectoryInterpolationActor(
        entity_ref="Ego",
        object_id=1,
        vertices=[
            TrajectoryInterpolationVertex(time_s=2.0, x=-285.0, y=-60.0, z=0.0),
            TrajectoryInterpolationVertex(time_s=4.0, x=-275.0, y=-60.0, z=0.0),
        ],
    )
    result = build_follow_trajectory_future_time_reference_case(
        FollowTrajectoryFutureTimeReferenceCaseSpec(
            output_xosc_path=tmp_path / "future_time_reference.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_future_time_reference.mcap",
                message_type="SensorView",
            ),
            actor=actor,
            init_pose=TrajectoryInterpolationVertex(
                time_s=0.0,
                x=-300.0,
                y=-60.0,
                z=0.0,
            ),
            init_speed_mps=4.0,
            action_start_time_s=0.0,
            stop_time_s=4.0,
            sample_period_s=1.0,
        )
    )

    tree = etree.parse(str(result.xosc_path))
    speed_action = tree.find(".//Storyboard/Init/Actions//SpeedAction")
    absolute_target_speed = tree.find(".//AbsoluteTargetSpeed")
    simulation_time_condition = tree.find(".//Event/StartTrigger//SimulationTimeCondition")
    timing = tree.find(".//FollowTrajectoryAction/TimeReference/Timing")
    following_mode = tree.find(".//TrajectoryFollowingMode")
    vertices = tree.findall(".//Polyline/Vertex")

    assert speed_action is not None
    assert absolute_target_speed is not None
    assert absolute_target_speed.get("value") == "4.0"
    assert simulation_time_condition is not None
    assert simulation_time_condition.get("value") == "0.0"
    assert timing is not None
    assert timing.get("domainAbsoluteRelative") == "absolute"
    assert timing.get("offset") == "0.0"
    assert timing.get("scale") == "1.0"
    assert following_mode is not None
    assert following_mode.get("followingMode") == "position"
    assert vertices[0].get("time") == "2.0"

    with open_channel(result.reference_channel_spec) as reader:
        messages = list(reader)

    xs = [
        message.global_ground_truth.moving_object[0].base.position.x
        for message in messages
    ]
    speeds = [
        math.hypot(
            message.global_ground_truth.moving_object[0].base.velocity.x,
            message.global_ground_truth.moving_object[0].base.velocity.y,
        )
        for message in messages
    ]

    assert xs == [-300.0, -296.0, -285.0, -280.0, -275.0]
    assert speeds[1] == 4.0
    assert speeds[2] == 11.0
