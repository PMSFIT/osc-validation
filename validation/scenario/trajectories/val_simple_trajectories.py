import pytest
import os
import pathlib
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.utils import gt2sv
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


def test_trajectory(osi_trace, odr_file, generate_tool_trace, tmp_path, tolerance=1e-6):
    osi2osc(osi_trace, tmp_path / "osi2osc.xosc")
    tool_trace = generate_tool_trace(
        tmp_path / "osi2osc.xosc", odr_file, tmp_path / "tool_trace.osi"
    )
    (area, cl, mae) = calculate_similarity(osi_trace, tool_trace, plot=False)
    print(area, cl, mae)

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
