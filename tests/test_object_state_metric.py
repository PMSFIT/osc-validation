from osi_utilities import ChannelSpecification, open_channel_writer

from tests.conftest import _make_sensor_view

from osc_validation.metrics import ObjectStateMetric


def _write_trace(path, object_id: int, xs: list[float]):
    with open_channel_writer(
        ChannelSpecification(path=path, message_type="SensorView")
    ) as writer:
        for index, x in enumerate(xs):
            msg = _make_sensor_view(index * 0.1, obj_id=object_id)
            moving_object = msg.global_ground_truth.moving_object[0]
            moving_object.base.position.x = x
            moving_object.base.position.y = 2.0
            moving_object.base.velocity.x = 10.0
            moving_object.base.velocity.y = 0.0
            writer.write_message(msg)


def test_object_state_metric_matches_closest_initial_object(tmp_path):
    reference_path = tmp_path / "reference.osi"
    tool_path = tmp_path / "tool.osi"
    _write_trace(reference_path, object_id=1, xs=[0.0, 1.0, 2.0])
    _write_trace(tool_path, object_id=99, xs=[0.1, 1.1, 2.1])

    result = ObjectStateMetric().compute(
        reference_channel_spec=ChannelSpecification(
            reference_path, message_type="SensorView"
        ),
        tool_channel_spec=ChannelSpecification(tool_path, message_type="SensorView"),
        moving_object_id=1,
    )

    assert result.reference_object_id == 1
    assert result.tool_object_id == 99
    assert result.sample_count == 3
    assert result.max_xy_error < 0.11
    assert result.max_planar_speed_error == 0.0
    assert result.max_time_error == 0.0
