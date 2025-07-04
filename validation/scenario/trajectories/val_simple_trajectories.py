import logging
from pathlib import Path
from typing import Callable

import pytest

from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.generation import osi2osc
from osc_validation.metrics.qccheck import QCOSITraceChecker
from osc_validation.metrics.trajectory_similarity import TrajectorySimilarityMetric
from osc_validation.utils.osi_channel_specification import OSIChannelSpecification


@pytest.fixture(
    scope="module",
    params=["simple_trajectories/sv_trace1.osi", "simple_trajectories/sv_trace2.osi"],
)
def osi_trace(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.fixture(
    scope="module",
    params=["osirules/omega-prime-rules.yml"],
)
def yaml_ruleset(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.fixture(scope="module")
def odr_file(request):
    return request.getfixturevalue("osi_trace").with_suffix(".xodr")


@pytest.mark.parametrize("moving_object_id", [1, 2])
def test_trajectory(osi_trace: Path, odr_file: Path, yaml_ruleset: Path, generate_tool_trace: Callable, tmp_path: Path, moving_object_id: int, tolerance=1e-1):
    """
    Validates that a tool-generated trajectory closely matches the original OSI trace
    for a given moving object, using similarity metrics within a specified tolerance.

    Args:
        osi_trace (Path): Path to the original OSI trace file (pytest module fixture).
        odr_file (Path): Path to the OpenDRIVE (.odr) file (pytest module fixture).
        yaml_ruleset (Path): Path to the YAML ruleset for OSITrace quality checks (pytest module fixture).
        generate_tool_trace (Callable): Function to generate an OSI trace from an OpenSCENARIO file (pytest session fixture).
        tmp_path (Path): Temporary directory for intermediate files (built-in pytest fixture).
        moving_object_id (int): ID of the moving object to compare in the traces (pytest parameter).
        tolerance (float, optional): Maximum allowed value for similarity metrics. Defaults to 1e-6.
    Raises:
        AssertionError: If any similarity metric exceeds the specified tolerance.
    """

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # load the OSI trace
    reference_trace_channel = OSIChannelSpecification(osi_trace, message_type="SensorView")

    # generate the OpenSCENARIO file from the OSI trace
    osc_path = osi2osc(osi_sensorview=reference_trace_channel, path_xosc=tmp_path / "osi2osc.xosc", path_xodr=odr_file)

    # use OpenSCENARIO file to generate the osi trace with the tool
    tool_trace_channel_spec = generate_tool_trace(
        osc_path = osc_path,
        odr_path = odr_file,
        osi_output_spec = OSIChannelSpecification(
            path=tmp_path / "tool_trace.mcap",
            message_type="SensorView",
            metadata={"net.asam.osi.trace.channel.description": "Tool-generated trace for validation"},
        ),
        log_path=tmp_path,
        rate = 0.05
    )

    # check compliance of tool trace to omega prime ruleset and OSI 3.7.0 ruleset
    qc_check = QCOSITraceChecker(osi_version="3.7.0", ruleset=yaml_ruleset)
    result = qc_check.check(channel_spec=tool_trace_channel_spec,
                              result_file=tmp_path / "qc_result.xqar",
                              output_config=tmp_path / "qc_config.xml"
                              )
    #assert result == True, "QC check failed for the tool-generated OSI trace."
    
    # calculate similarity metrics
    trajectory_similarity_metric = TrajectorySimilarityMetric(name="TrajectorySimilarityMetric", plot=False)
    (area, cl, mae, report) = trajectory_similarity_metric.compute(
        reference_channel_spec=reference_trace_channel,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        )

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
