from pathlib import Path

import pytest

from osi_utilities import ChannelSpecification, open_channel_writer

from osc_validation.metrics.trajectory_similarity import TrajectorySimilarityMetric
from tests.conftest import _make_sensor_view


def _write_sensorview_trace(
    path: Path, positions_by_object: dict[int, list[float]]
) -> ChannelSpecification:
    frame_count = len(next(iter(positions_by_object.values())))
    with open_channel_writer(
        ChannelSpecification(path=path, message_type="SensorView")
    ) as writer:
        for frame_index in range(frame_count):
            sensor_view = _make_sensor_view(frame_index * 0.1, obj_id=1)
            sensor_view.global_ground_truth.ClearField("moving_object")
            sensor_view.global_ground_truth.host_vehicle_id.value = 1
            sensor_view.host_vehicle_id.value = 1
            for obj_id, positions in positions_by_object.items():
                moving_object = sensor_view.global_ground_truth.moving_object.add()
                moving_object.id.value = obj_id
                moving_object.base.position.x = positions[frame_index]
                moving_object.base.position.y = float(obj_id)
                moving_object.base.position.z = 0.0
                moving_object.base.orientation.yaw = 0.0
                moving_object.base.orientation.pitch = 0.0
                moving_object.base.orientation.roll = 0.0
                moving_object.base.dimension.length = 4.5
                moving_object.base.dimension.width = 1.8
                moving_object.base.dimension.height = 1.5
            writer.write_message(sensor_view)
    return ChannelSpecification(path=path, message_type="SensorView")


def test_trajectory_similarity_metric_writes_report_and_plot(tmp_path):
    reference_spec = _write_sensorview_trace(
        tmp_path / "reference.osi",
        {1: [0.0, 1.0, 2.0]},
    )
    tool_spec = _write_sensorview_trace(
        tmp_path / "tool.osi",
        {1: [0.0, 1.0, 2.0], 2: [100.0, 101.0, 102.0]},
    )
    result_file = tmp_path / "similarity.txt"

    metric = TrajectorySimilarityMetric(name="TrajectorySimilarity", plot_path=tmp_path)
    area, curve_length, mae = metric.compute(
        reference_channel_spec=reference_spec,
        tool_channel_spec=tool_spec,
        moving_object_id=1,
        result_file=result_file,
    )

    assert area == pytest.approx(0.0)
    assert curve_length == pytest.approx(0.0)
    assert mae == pytest.approx(0.0)
    assert result_file.exists()
    assert "Similarity Measures" in result_file.read_text(encoding="utf-8")
    assert (tmp_path / "trajectory_similarity_1.png").exists()


def test_trajectory_similarity_metric_rejects_missing_reference_object(tmp_path):
    reference_spec = _write_sensorview_trace(
        tmp_path / "reference.osi",
        {1: [0.0, 1.0, 2.0]},
    )
    tool_spec = _write_sensorview_trace(
        tmp_path / "tool.osi",
        {1: [0.0, 1.0, 2.0]},
    )

    metric = TrajectorySimilarityMetric()
    with pytest.raises(KeyError, match="Moving object ID 99 not found"):
        metric.compute(
            reference_channel_spec=reference_spec,
            tool_channel_spec=tool_spec,
            moving_object_id=99,
        )


def test_trajectory_similarity_metric_rejects_short_trajectories(tmp_path):
    reference_spec = _write_sensorview_trace(
        tmp_path / "reference.osi",
        {1: [0.0]},
    )
    tool_spec = _write_sensorview_trace(
        tmp_path / "tool.osi",
        {1: [0.0]},
    )

    metric = TrajectorySimilarityMetric()
    with pytest.raises(ValueError, match="at least 2 points"):
        metric.compute(
            reference_channel_spec=reference_spec,
            tool_channel_spec=tool_spec,
            moving_object_id=1,
        )


def test_trajectory_similarity_metric_rejects_length_mismatch(tmp_path):
    reference_spec = _write_sensorview_trace(
        tmp_path / "reference.osi",
        {1: [0.0, 1.0, 2.0]},
    )
    tool_spec = _write_sensorview_trace(
        tmp_path / "tool.osi",
        {1: [0.0, 1.0]},
    )

    metric = TrajectorySimilarityMetric()
    with pytest.raises(ValueError, match="same number of points"):
        metric.compute(
            reference_channel_spec=reference_spec,
            tool_channel_spec=tool_spec,
            moving_object_id=1,
        )
