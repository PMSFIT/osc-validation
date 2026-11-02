import math

import pytest
from osi_utilities import ChannelSpecification, open_channel

from osc_validation.features.trajectory.models import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from osc_validation.features.trajectory.reference import (
    build_trajectory_sensor_view,
    sample_trajectory,
)
from osc_validation.features.trajectory.teleport.reference import (
    FollowTrajectoryTeleportReferenceRequest,
    build_follow_trajectory_teleport_reference_trace,
)


@pytest.mark.parametrize(
    "mode, time_s, expected_x, expected_y",
    [
        ("linear_position", 0.0, 0.0, 0.0),
        ("linear_position", 1.0, 5.0, 0.0),
        ("linear_position", 2.0, 10.0, 0.0),
        ("linear_position", 3.0, 10.0, 5.0),
        ("linear_position", 4.0, 10.0, 10.0),
        # First segment: a=5 m/s², final speed=10 m/s.
        # Second segment: a=-5 m/s², so its first second covers 7.5 m.
        ("constant_acceleration_from_initial_speed", 1.0, 2.5, 0.0),
        ("constant_acceleration_from_initial_speed", 3.0, 10.0, 7.5),
        ("constant_acceleration_from_initial_speed", 4.0, 10.0, 10.0),
    ],
)
def test_sampling_has_explicit_policy_and_preserves_segment_boundaries(
    mode, time_s, expected_x, expected_y
):
    vertices = [
        TrajectoryInterpolationVertex(0.0, 0.0, 0.0, 0.0),
        TrajectoryInterpolationVertex(2.0, 10.0, 0.0, 0.0),
        TrajectoryInterpolationVertex(4.0, 10.0, 10.0, 0.0),
    ]
    pose = sample_trajectory(
        vertices, time_s, interpolation_mode=mode, initial_speed_mps=0.0
    )
    assert (pose.time_s, pose.x, pose.y) == pytest.approx(
        (time_s, expected_x, expected_y)
    )


@pytest.mark.parametrize("time_s", [-0.1, 2.1])
def test_sampling_rejects_times_outside_trajectory(time_s):
    with pytest.raises(ValueError, match="outside the trajectory"):
        sample_trajectory(
            [
                TrajectoryInterpolationVertex(0.0, 0.0, 0.0, 0.0),
                TrajectoryInterpolationVertex(2.0, 10.0, 0.0, 0.0),
            ],
            time_s,
            interpolation_mode="linear_position",
            initial_speed_mps=0.0,
        )


def test_osi_construction_rotates_center_and_normalizes_timestamp():
    pose = TrajectoryInterpolationVertex(0.0, 10.0, 20.0, 3.0, yaw=math.pi / 2)
    actor = TrajectoryInterpolationActor(
        entity_ref="Actor", object_id=7, vertices=[pose], bounding_box_center_x=2.0
    )
    message = build_trajectory_sensor_view(
        actor=actor, pose=pose, timestamp_s=1.9999999996, host_vehicle_id=9
    )
    obj = message.global_ground_truth.moving_object[0]
    assert (
        obj.base.position.x,
        obj.base.position.y,
        obj.base.position.z,
    ) == pytest.approx((10.0, 22.0, 3.0))
    for container in (message, message.global_ground_truth):
        assert (container.timestamp.seconds, container.timestamp.nanos) == (2, 0)
        assert container.host_vehicle_id.value == 9
        assert container.version.version_major > 0
    assert obj.id.value == 7
    assert not obj.base.HasField("velocity")
    assert not obj.base.HasField("acceleration")


def test_teleport_holds_init_pose_then_uses_linear_trajectory(tmp_path):
    actor = TrajectoryInterpolationActor(
        entity_ref="Ego",
        object_id=3,
        vertices=[
            TrajectoryInterpolationVertex(0.0, 0.0, 0.0, 0.0),
            TrajectoryInterpolationVertex(2.0, 10.0, 0.0, 0.0),
        ],
    )
    channel = build_follow_trajectory_teleport_reference_trace(
        FollowTrajectoryTeleportReferenceRequest(
            output_channel_spec=ChannelSpecification(
                path=tmp_path / "teleport.mcap", message_type="SensorView"
            ),
            actor=actor,
            init_pose=TrajectoryInterpolationVertex(0.0, -10.0, 4.0, 0.0),
            action_start_time_s=1.0,
            stop_time_s=2.0,
            sample_period_s=0.5,
        )
    )
    with open_channel(channel) as reader:
        messages = list(reader)
    positions = [m.global_ground_truth.moving_object[0].base.position for m in messages]
    assert [p.x for p in positions] == pytest.approx([-10.0, -10.0, 5.0, 7.5, 10.0])
    assert [p.y for p in positions] == pytest.approx([4.0, 4.0, 0.0, 0.0, 0.0])
    assert all(m.host_vehicle_id.value == 3 for m in messages)
