import logging
from pathlib import Path
from typing import Callable

import pytest

from osc_validation.dataproviders import BuiltinDataProvider, DownloadZIPDataProvider
from osc_validation.generation import osi2osc
from osc_validation.metrics.trajectory_similarity import TrajectorySimilarityMetric
from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.utils import get_all_moving_object_ids


ZIP_URI = "https://github.com/thomassedlmayer/example-files-zip/raw/refs/heads/main/example-mcaps.zip"

# Map each file to the object IDs to be tested
ZIP_CONTENTS_TO_IDS = {
    # "nurbs_road.mcap": [14],
    "disappearing_vehicle.mcap": [1],
    "nurbs_trajectory.mcap": [10],
}


@pytest.fixture(scope="module")
def zip_provider():
    """
    Downloads and extracts the ZIP once per module, then yields the zip data provider.
    """
    base_path = Path("download-zip")
    provider = DownloadZIPDataProvider(uri=ZIP_URI, base_path=base_path)

    provider.download()
    yield provider
    provider.cleanup()


@pytest.fixture(
    scope="module",
    params=[
        (filename, obj_id)
        for filename, ids in ZIP_CONTENTS_TO_IDS.items()
        for obj_id in ids
    ],
    ids=lambda p: f"{Path(p[0]).stem}-moving_object_id{p[1]}",
)
def osi_trace_with_ids(request, zip_provider):
    """
    Yields a tuple of an OSI trace file path (from the extracted ZIP) and a list
    of corresponding object IDs to be tested.
    """
    filename, obj_id = request.param
    mcap_path = zip_provider.ensure_data_path(filename)
    yield mcap_path, obj_id


@pytest.fixture(
    scope="module",
    params=["xodr_example/map.xodr"],
)
def odr_file(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


def test_trajectory_remote_zip(
    osi_trace_with_ids: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    tolerance=1e-1,
):
    """
    Validates that a tool-generated trajectory closely matches the original OSI trace
    for a specific moving object, using trajectory similarity metrics within a specified tolerance.

    Args:
        osi_trace_with_ids (tuple[Path, int]): A tuple containing:
            - Path to the original OSI trace file (.mcap), provided by the fixture.
            - Moving object ID to test within that trace file.
        odr_file (Path): Path to the OpenDRIVE (.odr) file (pytest fixture).
        generate_tool_trace (Callable): Function to generate an OSI trace from an OpenSCENARIO file (pytest session fixture).
        tmp_path (Path): Temporary directory for intermediate files (built-in pytest fixture).
        tolerance (float, optional): Maximum allowed value for similarity metrics (area, CL, MAE). Defaults to 0.1.

    Raises:
        AssertionError: If any trajectory similarity metric (area, cross-length, MAE) exceeds the specified tolerance.
    """

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    osi_trace, moving_object_id = osi_trace_with_ids

    # Generate the OpenSCENARIO file from the reference OSI trace
    reference_trace_channel_spec = OSIChannelSpecification(
        osi_trace, message_type="SensorView"
    )

    object_ids = get_all_moving_object_ids(reference_trace_channel_spec)
    if moving_object_id not in object_ids:
        pytest.skip(
            f"Object ID {moving_object_id} not found in {osi_trace.name}. Available ids: {str(object_ids)}"
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
