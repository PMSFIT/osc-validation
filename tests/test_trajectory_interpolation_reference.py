import math

from osi_utilities import ChannelSpecification, open_channel

from osc_validation.generation import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from osc_validation.reference import (
    TrajectoryInterpolationReferenceRequest,
    build_trajectory_interpolation_reference_trace,
)


def _actor() -> TrajectoryInterpolationActor:
    return TrajectoryInterpolationActor(
        entity_ref="Ego",
        object_id=1,
        vertices=[
            TrajectoryInterpolationVertex(0.0, 0.0, 0.0, 0.0),
            TrajectoryInterpolationVertex(2.0, 10.0, 0.0, 0.0),
        ],
    )


def _bent_actor() -> TrajectoryInterpolationActor:
    return TrajectoryInterpolationActor(
        entity_ref="Ego",
        object_id=1,
        vertices=[
            TrajectoryInterpolationVertex(0.0, 0.0, 0.0, 0.0),
            TrajectoryInterpolationVertex(2.0, 10.0, 0.0, 0.0),
            TrajectoryInterpolationVertex(4.0, 10.0, 10.0, 0.0),
        ],
    )


def _objects(channel_spec):
    with open_channel(channel_spec) as reader:
        messages = list(reader)
    return [
        message.global_ground_truth.moving_object[0]
        for message in messages
    ]


def test_linear_reference_interpolates_each_segment(tmp_path):
    channel_spec = build_trajectory_interpolation_reference_trace(
        TrajectoryInterpolationReferenceRequest(
            output_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_linear_bend.mcap",
                message_type="SensorView",
            ),
            actor=_bent_actor(),
            sample_period_s=1.0,
            interpolation_mode="linear_position",
        )
    )

    objects = _objects(channel_spec)
    assert len(objects) == 5
    assert math.isclose(objects[0].base.position.x, 0.0)
    assert math.isclose(objects[0].base.position.y, 0.0)
    assert math.isclose(objects[1].base.position.x, 5.0)
    assert math.isclose(objects[1].base.position.y, 0.0)
    assert math.isclose(objects[2].base.position.x, 10.0)
    assert math.isclose(objects[2].base.position.y, 0.0)
    assert math.isclose(objects[3].base.position.x, 10.0)
    assert math.isclose(objects[3].base.position.y, 5.0)
    assert math.isclose(objects[4].base.position.x, 10.0)
    assert math.isclose(objects[4].base.position.y, 10.0)


def test_constant_acceleration_reference_carries_speed_between_segments(tmp_path):
    channel_spec = build_trajectory_interpolation_reference_trace(
        TrajectoryInterpolationReferenceRequest(
            output_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_constant_acceleration_bend.mcap",
                message_type="SensorView",
            ),
            actor=_bent_actor(),
            sample_period_s=1.0,
            interpolation_mode="constant_acceleration_from_initial_speed",
            initial_speed_mps=0.0,
        )
    )

    objects = _objects(channel_spec)
    assert len(objects) == 5
    assert math.isclose(objects[1].base.position.x, 2.5)
    assert math.isclose(objects[1].base.position.y, 0.0)
    assert math.isclose(objects[2].base.velocity.x, 7.5)
    assert math.isclose(objects[2].base.velocity.y, 0.0)
    assert math.isclose(objects[3].base.position.x, 10.0)
    assert math.isclose(objects[3].base.position.y, 7.5)
    assert math.isclose(objects[3].base.velocity.x, 0.0)
    assert math.isclose(objects[3].base.velocity.y, 7.5)


def test_constant_acceleration_reference_uses_initial_speed_formula(tmp_path):
    channel_spec = build_trajectory_interpolation_reference_trace(
        TrajectoryInterpolationReferenceRequest(
            output_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_constant_acceleration.mcap",
                message_type="SensorView",
            ),
            actor=_actor(),
            sample_period_s=1.0,
            interpolation_mode="constant_acceleration_from_initial_speed",
            initial_speed_mps=2.0,
        )
    )

    with open_channel(channel_spec) as reader:
        messages = list(reader)

    objects = [
        message.global_ground_truth.moving_object[0]
        for message in messages
    ]
    assert len(objects) == 3
    assert math.isclose(objects[0].base.position.x, 0.0)
    assert math.isclose(objects[1].base.position.x, 3.5)
    assert math.isclose(objects[2].base.position.x, 10.0)
    assert math.isclose(objects[0].base.velocity.x, 0.0)
    assert math.isclose(objects[1].base.velocity.x, 3.5)
    assert math.isclose(objects[2].base.velocity.x, 6.5)
    assert math.isclose(objects[0].base.acceleration.x, 0.0)


def test_reference_rejects_non_increasing_vertex_times(tmp_path):
    actor = TrajectoryInterpolationActor(
        entity_ref="Ego",
        object_id=1,
        vertices=[
            TrajectoryInterpolationVertex(0.0, 0.0, 0.0, 0.0),
            TrajectoryInterpolationVertex(2.0, 10.0, 0.0, 0.0),
            TrajectoryInterpolationVertex(2.0, 10.0, 10.0, 0.0),
        ],
    )

    try:
        build_trajectory_interpolation_reference_trace(
            TrajectoryInterpolationReferenceRequest(
                output_channel_spec=ChannelSpecification(
                    path=tmp_path / "reference_bad_times.mcap",
                    message_type="SensorView",
                ),
                actor=actor,
                sample_period_s=1.0,
            )
        )
    except ValueError as error:
        assert str(error) == "Trajectory vertex times must be strictly increasing."
    else:
        raise AssertionError("Expected ValueError")


def test_constant_acceleration_reference_rejects_zero_length_segment(tmp_path):
    actor = TrajectoryInterpolationActor(
        entity_ref="Ego",
        object_id=1,
        vertices=[
            TrajectoryInterpolationVertex(0.0, 0.0, 0.0, 0.0),
            TrajectoryInterpolationVertex(2.0, 10.0, 0.0, 0.0),
            TrajectoryInterpolationVertex(4.0, 10.0, 0.0, 0.0),
        ],
    )

    try:
        build_trajectory_interpolation_reference_trace(
            TrajectoryInterpolationReferenceRequest(
                output_channel_spec=ChannelSpecification(
                    path=tmp_path / "reference_zero_length.mcap",
                    message_type="SensorView",
                ),
                actor=actor,
                sample_period_s=1.0,
                interpolation_mode="constant_acceleration_from_initial_speed",
            )
        )
    except ValueError as error:
        assert (
            str(error)
            == "Constant-acceleration interpolation requires a non-zero arc length."
        )
    else:
        raise AssertionError("Expected ValueError")
