from pathlib import Path
from typing import Callable

import pytest

from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.generation import osi2osc
from osc_validation.metrics.trajectory_similarity import TrajectorySimilarityMetric
from osc_validation.utils.osi_reader import OSIChannelReader, OSITraceReaderMulti
from osc_validation.utils.utils import crop_trace


@pytest.fixture(
    scope="module",
    params=["simple_trajectories/sv_trace1.osi", "simple_trajectories/sv_trace2.osi"],
)
def osi_trace(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.fixture(scope="module")
def odr_file(request):
    return request.getfixturevalue("osi_trace").with_suffix(".odr")


@pytest.mark.parametrize("moving_object_id", [1, 2, 3])
def test_trajectory(osi_trace: Path, odr_file: Path, generate_tool_trace: Callable, tmp_path: Path, moving_object_id: int, tolerance=1e-1):
    """
    Validates that a tool-generated trajectory closely matches the original OSI trace
    for a given moving object, using similarity metrics within a specified tolerance.

    Args:
        osi_trace (Path): Path to the original OSI trace file (pytest module fixture).
        odr_file (Path): Path to the OpenDRIVE (.odr) file (pytest module fixture).
        generate_tool_trace (Callable): Function to generate an OSI trace from an OpenSCENARIO file (pytest session fixture).
        tmp_path (Path): Temporary directory for intermediate files (built-in pytest fixture).
        moving_object_id (int): ID of the moving object to compare in the traces (pytest parameter).
        tolerance (float, optional): Maximum allowed value for similarity metrics. Defaults to 1e-6.
    Raises:
        AssertionError: If any similarity metric exceeds the specified tolerance.
    """
    # load the OSI trace
    reference_trace = OSIChannelReader.from_osi_binary(osi_trace, type_name="SensorView")

    # generate the OpenSCENARIO file from the OSI trace
    osi2osc(reference_trace, tmp_path / "osi2osc.xosc")

    # use OpenSCENARIO file to generate the osi trace with the tool
    tool_trace_path = generate_tool_trace(
        osc_path = tmp_path / "osi2osc.xosc",
        odr_path = odr_file,
        osi_path = tmp_path / "tool_trace.osi",
        rate = 0.05
    )

    tool_trace = OSIChannelReader.from_osi_binary(tool_trace_path, type_name="SensorView")

    # post-process the tool trace to match the reference trace (create a cropped mcap trace)
    tool_trace_cropped_path = crop_trace(
        input_trace=tool_trace,
        output_trace_path=tool_trace_path.with_name(tool_trace_path.stem + ".cropped" + ".mcap"),
        start_time=0.3
        )
    tool_trace_cropped = OSIChannelReader.from_osi_mcap(
        trace_reader_multi=OSITraceReaderMulti(tool_trace_cropped_path),
        topic=tool_trace.get_topic_name()
        )
    
    # calculate similarity metrics
    trajectory_similarity_metric = TrajectorySimilarityMetric(name="TrajectorySimilarityMetric", plot=False)
    (area, cl, mae, report) = trajectory_similarity_metric.compute(
        reference_trace=reference_trace,
        tool_trace=tool_trace_cropped,
        moving_object_id=moving_object_id,
        )
    
    reference_trace.close()
    tool_trace.close()
    tool_trace_cropped.close()

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
