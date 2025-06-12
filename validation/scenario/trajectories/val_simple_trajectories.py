import pytest
import os
import pathlib
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.utils.utils import crop_trace
from osc_validation.generation import osi2osc
from osc_validation.metrics.trajectory_similarity import calculate_similarity


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
def test_trajectory(osi_trace, odr_file, generate_tool_trace, tmp_path, moving_object_id, tolerance=1e-6):
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
    # generate the OpenSCENARIO file from the OSI trace
    osi2osc(osi_trace, tmp_path / "osi2osc.xosc")

    # use OpenSCENARIO file to generate the osi trace with the tool
    tool_trace = generate_tool_trace(
        osc_path = tmp_path / "osi2osc.xosc",
        odr_path = odr_file,
        osi_path = tmp_path / "tool_trace.osi",
        rate = 0.05
    )

    # post-process the tool trace to match the reference trace
    tool_trace_cropped = tool_trace.with_name(tool_trace.stem + ".cropped" + tool_trace.suffix)
    tool_trace_cropped = crop_trace(tool_trace, tool_trace_cropped, 0.3)

    # calculate similarity metrics
    (area, cl, mae, report) = calculate_similarity(osi_trace, tool_trace_cropped, moving_object_id, plot=False)

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
