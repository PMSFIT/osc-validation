import logging
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import pytest

from osc_validation.dataproviders import BuiltinDataProvider, DownloadDataProvider
from osc_validation.generation import osi2osc
from osc_validation.metrics.trajectory_similarity import TrajectorySimilarityMetric
from osc_validation.utils.osi_channel_specification import OSIChannelSpecification


@pytest.fixture(
    scope="module",
    params=[
        "https://github.com/lichtblick-suite/asam-osi-converter/raw/refs/heads/main/example-data/disappearingVehicle.mcap"
    ],
)
def osi_trace(request):
    uri = request.param
    filename = Path(urlparse(uri).path).name
    base_path = Path("download")
    provider = DownloadDataProvider(uri=uri, base_path=base_path)
    yield provider.ensure_data_path(filename)
    provider.cleanup()


@pytest.fixture(
    scope="module",
    params=["xodr_example/map.xodr"],
)
def odr_file(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.mark.parametrize("moving_object_id", [1])
def test_trajectory_remote(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    moving_object_id: int,
    tolerance=1e-1,
):
    """
    Validates that a tool-generated trajectory closely matches the original OSI trace
    for a given moving object, using similarity metrics within a specified tolerance.

    Args:
        osi_trace (Path): Path to the original OSI trace file (pytest module fixture).
        odr_file (Path): Path to the OpenDRIVE (.odr) file (pytest module fixture).
        yaml_ruleset (Path): Path to the YAML ruleset for OSITrace quality checks (pytest module fixture).
        generate_tool_trace (Callable): Function to generate an OSI trace from an OpenSCENARIO file (pytest session fixture).
        tmp_path (Path): Temporary directory for intermediate files (built-in pytest fixture).
        moving_object_id (int): ID of the moving object (in the reference trace) selected for trajectory comparison (pytest parameter).
        tolerance (float, optional): Maximum allowed value for similarity metrics. Defaults to 1e-6.
    Raises:
        AssertionError: If any similarity metric exceeds the specified tolerance.
    """

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Generate the OpenSCENARIO file from the reference OSI trace
    reference_trace_channel_spec = OSIChannelSpecification(
        osi_trace, message_type="SensorView"
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
        osi_output_spec=OSIChannelSpecification(
            path=tmp_path / "tool_trace.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for validation"
            },
        ),
        log_path=tmp_path,
        rate=0.05,
    )

    # Calculate trajectory similarity metrics
    trajectory_similarity_metric = TrajectorySimilarityMetric(
        name="TrajectorySimilarityMetric", plot_path=tmp_path
    )
    (area, cl, mae) = trajectory_similarity_metric.compute(
        reference_channel_spec=reference_trace_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        start_time=3,
        end_time=10.0,
        result_file=tmp_path / f"trajectory_similarity_report.txt",
        time_tolerance=0.01,
    )

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
