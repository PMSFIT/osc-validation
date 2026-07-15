from pathlib import Path
from typing import Callable

import pytest
from osi_utilities import ChannelSpecification, MessageType

from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.generation import osi2osc
from osc_validation.metrics import ObjectStateMetric


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


@pytest.mark.validation_category("object_state")
@pytest.mark.validation_feature("Vehicle dimensions")
@pytest.mark.parametrize("moving_object_id", [1, 2])
def test_vehicle_dimensions_match_reference(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
    moving_object_id: int,
    tolerance: float = 0.1,
):
    """
    OpenSCENARIO feature: vehicle/object geometry emitted from scenario entities.

    Converts a reference OSI trace to OpenSCENARIO and checks that replayed vehicle
    dimensions match the source objects. The validation compares length, width, and
    height for the tested moving objects.
    """

    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type=MessageType.SENSOR_VIEW
    )
    osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / "osi2osc_dimensions.xosc",
        path_xodr=odr_file,
    )

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_dimensions.mcap",
            message_type=MessageType.SENSOR_VIEW,
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for vehicle dimension validation"
            },
        ),
        log_path=tmp_path,
        rate=0.05,
    )
    assert_osi_compliance(
        tool_trace_channel_spec,
        result_file=tmp_path / f"qc_result_vehicle_dimensions_{moving_object_id}.xqar",
    )

    result = ObjectStateMetric().compute(
        reference_channel_spec=reference_trace_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        match_mode="closest_initial_xy",
    )

    assert result.max_length_error < tolerance
    assert result.max_width_error < tolerance
    assert result.max_height_error < tolerance
