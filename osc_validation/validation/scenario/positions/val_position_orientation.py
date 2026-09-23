"""Issue #614: default and relative headings use the road or lane s-axis.

The flat RHT road runs along world +x. Four-meter lanes have centers at
y=-2 (lane -1, +s driving) and y=2 (lane +1, -s driving).
Both lane s-axes point along world +x, irrespective of driving direction.
OpenSCENARIO XML 1.3.1 section 6.3.3 defines the lane s-axis in the
direction of the road s-axis; LanePosition measures relative heading from
that lane-axis tangent and treats omitted orientation as relative zero.
See https://publications.pages.asam.net/standards/ASAM_OpenSCENARIO/ASAM_OpenSCENARIO_XML/v1.3.1/06_general_concepts/06_03_coordinate_systems.html

On this constant-width straight map, road and lane tangents coincide. These
cases detect an incorrect driving-direction flip, but do not distinguish
road-reference-line tangents from lane-centerline tangents.
Expected world poses below are explicit, independent of any map resolver.
The plus-s/minus-s case IDs describe traffic direction, not lane-axis direction.
"""

from math import pi
from pathlib import Path
from typing import Callable

import pytest
from osi_utilities import ChannelSpecification

from osc_validation.assertions import assert_no_osc_engine_errors
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.generation.xosc_builders import (
    LanePosition,
    Orientation,
    RoadPosition,
)
from osc_validation.metrics import ObjectStateMetric
from osc_validation.oracles import (
    InitActionCaseSpec,
    InitActionOracleActor,
    build_init_teleport_action_case,
)


@pytest.fixture(scope="module")
def odr_file(builtin_data_path):
    provider = BuiltinDataProvider(builtin_data_path)
    yield provider.ensure_data_path("positions/straight_opposing.xodr")
    provider.cleanup()


@pytest.mark.validation_category("position")
@pytest.mark.validation_feature("RoadPosition / LanePosition orientation")
@pytest.mark.parametrize(
    "position, expected_x, expected_y, expected_yaw",
    [
        # Road position: omitted orientation faces +X (yaw 0).
        pytest.param(RoadPosition("1", 20, 2), 20, 2, 0, id="road-omitted"),
        # Lane -1, traffic +s: omitted orientation faces +X (yaw 0).
        pytest.param(LanePosition("1", -1, 20), 20, -2, 0, id="lane-plus-s-omitted"),
        # Lane +1, traffic -s: omitted orientation still faces +X (yaw 0).
        pytest.param(LanePosition("1", 1, 20), 20, 2, 0, id="lane-minus-s-omitted"),
        # Road position: relative h=0 follows road +s, facing +X.
        pytest.param(
            RoadPosition("1", 20, 2, Orientation(h=0)),
            20,
            2,
            0,
            id="road-relative-zero",
        ),
        # Road position: relative h=pi reverses road +s, facing -X.
        pytest.param(
            RoadPosition("1", 20, 2, Orientation(h=pi)),
            20,
            2,
            pi,
            id="road-relative-pi",
        ),
        # Lane -1, traffic +s: relative h=0 faces +X, with traffic.
        pytest.param(
            LanePosition("1", -1, 20, orientation=Orientation(h=0)),
            20,
            -2,
            0,
            id="lane-plus-s-relative-zero",
        ),
        # Lane -1, traffic +s: relative h=pi faces -X, against traffic.
        pytest.param(
            LanePosition("1", -1, 20, orientation=Orientation(h=pi)),
            20,
            -2,
            pi,
            id="lane-plus-s-relative-pi",
        ),
        # Lane +1, traffic -s: relative h=0 faces +X, against traffic.
        pytest.param(
            LanePosition("1", 1, 20, orientation=Orientation(h=0)),
            20,
            2,
            0,
            id="lane-minus-s-relative-zero",
        ),
        # Lane +1, traffic -s: relative h=pi faces -X, with traffic.
        pytest.param(
            LanePosition("1", 1, 20, orientation=Orientation(h=pi)),
            20,
            2,
            pi,
            id="lane-minus-s-relative-pi",
        ),
        # Road position: absolute h=0.5 sets world yaw to 0.5 radians.
        pytest.param(
            RoadPosition("1", 20, 2, Orientation(h=0.5, type="absolute")),
            20,
            2,
            0.5,
            id="road-absolute",
        ),
        # Lane +1, traffic -s: absolute h=0.5 sets world yaw to 0.5 radians.
        pytest.param(
            LanePosition("1", 1, 20, orientation=Orientation(h=0.5, type="absolute")),
            20,
            2,
            0.5,
            id="lane-minus-s-absolute",
        ),
        # Lane +1, offset -4: crosses into lane -1 at y=-2; yaw remains 0.
        # Parallel lane axes mean this cannot identify which tangent was used.
        pytest.param(
            LanePosition("1", 1, 20, offset=-4),
            20,
            -2,
            0,
            id="lane-offset-crosses-center",
        ),
    ],
)
def test_init_position_world_orientation(
    position,
    expected_x: float,
    expected_y: float,
    expected_yaw: float,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
):
    """Init TeleportAction must use the road or referenced lane s-axis tangent."""
    rate = 0.05
    case = build_init_teleport_action_case(
        InitActionCaseSpec(
            output_xosc_path=tmp_path / "position.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference.mcap",
                message_type="SensorView",
            ),
            actors=[
                InitActionOracleActor(
                    entity_ref="Ego",
                    object_id=1,
                    x=expected_x,
                    y=expected_y,
                    z=0,
                    yaw=expected_yaw,
                    bounding_box_center_x=2,
                    bounding_box_center_y=0,
                    bounding_box_center_z=0.75,
                    position=position,
                )
            ],
            duration_s=0.5,
            sample_period_s=rate,
            road_network_path=odr_file,
        )
    )
    tool_trace = generate_tool_trace(
        osc_path=case.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool.mcap",
            message_type="SensorView",
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace)
    assert_osi_compliance(tool_trace, result_file=tmp_path / "qc_result.xqar")
    result = ObjectStateMetric().compute(
        reference_channel_spec=case.reference_channel_spec,
        tool_channel_spec=tool_trace,
        moving_object_id=1,
        match_mode="closest_initial_xy",
        ignore_first_speed_sample=True,
    )
    assert result.max_time_error <= 0.01
    assert result.max_xy_error < 0.1
    assert result.max_yaw_error < 0.01
