import logging
from pathlib import Path
from typing import Callable

import pytest

from osi_utilities import ChannelSpecification, MessageType
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.generation import (
    TrajectorySequencingTransformRequest,
    TrajectorySequencingTransformSpec,
    apply_trajectory_sequencing_transform,
    osi2osc,
)
from osc_validation.metrics.trajectory_similarity import TrajectorySimilarityMetric

from validation.scenario.assertions import assert_no_osc_engine_errors


@pytest.fixture(
    scope="module",
    params=[
        "simple_trajectories/20240603T152322.095000Z_sv_370_3200_618_dronetracker_135_swerve.mcap"
    ],
)
def osi_trace(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.fixture(scope="module")
def odr_file(request):
    return request.getfixturevalue("osi_trace").with_suffix(".xodr")


@pytest.mark.trajectory
@pytest.mark.parametrize(
    "sequencing_level",
    ["event", "maneuver", "maneuver_group", "act", "story"],
)
def test_split_ego_trajectory_preserves_reference_motion(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    sequencing_level: str,
    entity_ref: str = "Ego",
    moving_object_id: int = 1,
    segment_count: int = 2,
    rate: float = 0.05,
    tolerance: float = 0.1,
):
    """
    Validates that splitting one actor trajectory into sequential OpenSCENARIO
    elements preserves the same replayed trajectory.
    """

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type=MessageType.SENSOR_VIEW
    )
    base_osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / "osi2osc_sequencing_base.xosc",
        path_xodr=odr_file,
        init_pose_policy="close_to_trajectory_start",
    )
    transform_result = apply_trajectory_sequencing_transform(
        TrajectorySequencingTransformRequest(
            source_xosc_path=base_osc_path,
            output_xosc_path=tmp_path / f"osi2osc_split_{sequencing_level}.xosc",
            spec=TrajectorySequencingTransformSpec(
                entity_ref=entity_ref,
                segment_count=segment_count,
                sequencing_level=sequencing_level,
            ),
        )
    )

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=transform_result.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / f"tool_trace_split_{sequencing_level}.mcap",
            message_type=MessageType.SENSOR_VIEW,
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for trajectory sequencing validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)

    metric = TrajectorySimilarityMetric(
        name="TrajectorySimilarityMetric", plot_path=tmp_path
    )
    area, cl, mae = metric.compute(
        reference_channel_spec=reference_trace_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        result_file=tmp_path
        / f"trajectory_similarity_report_split_{sequencing_level}.txt",
        time_tolerance=0.01,
    )

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
