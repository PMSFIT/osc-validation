import logging
from pathlib import Path
from typing import Callable

import pytest

from osi_utilities import MessageType
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.generation import osi2osc
from osc_validation.metrics.trajectory_similarity import TrajectorySimilarityMetric
from osi_utilities import ChannelSpecification


@pytest.fixture(
    scope="module",
    params=[
        "simple_trajectories/20240603T152322.095000Z_sv_370_3200_618_dronetracker_135_swerve.mcap"
    ],
)
def osi_trace(request, builtin_data_path):
    provider = BuiltinDataProvider(builtin_data_path)
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.fixture(scope="module")
def odr_file(request):
    return request.getfixturevalue("osi_trace").with_suffix(".xodr")


@pytest.mark.validation_category("trajectory")
@pytest.mark.validation_feature("FollowTrajectoryAction")
@pytest.mark.parametrize("moving_object_id", [1, 2])
def test_trajectory_and_osi_compliance(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_trace_compliance: Callable,
    tmp_path: Path,
    moving_object_id: int,
    tolerance=1e-1,
):
    """
    OpenSCENARIO feature: generated FollowTrajectoryAction replay from an OSI trace.

    Validates that a tool-generated trajectory closely matches the original OSI trace
    for a given moving object, using similarity metrics within a specified tolerance.

    Also runs qc_osi_trace on the tool-generated trace and checks if it complies with
    the OSI 3.7.0 ruleset.
    """

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Generate the OpenSCENARIO file from the reference OSI trace
    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type=MessageType.SENSOR_VIEW
    )
    osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / "osi2osc.xosc",
        path_xodr=odr_file,
    )

    # Use the OpenSCENARIO and OpenDRIVE file fixtures to generate the tool trace with the specified format and rate
    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace.mcap",
            message_type=MessageType.SENSOR_VIEW,
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for validation"
            },
        ),
        log_path=tmp_path,
        rate=0.05,
    )

    assert_osi_trace_compliance(
        channel_spec=tool_trace_channel_spec,
        result_file=tmp_path / "qc_result.xqar",
        output_config=tmp_path / "qc_config.xml",
    )

    # Calculate trajectory similarity metrics
    trajectory_similarity_metric = TrajectorySimilarityMetric(
        name="TrajectorySimilarityMetric", plot_path=tmp_path
    )
    (area, cl, mae) = trajectory_similarity_metric.compute(
        reference_channel_spec=reference_trace_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        start_time=0.0,
        end_time=19.95,
        result_file=tmp_path / f"trajectory_similarity_report.txt",
        time_tolerance=0.01,
    )

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
