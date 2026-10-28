from pathlib import Path
from typing import Callable

import pytest
from osi_utilities import ChannelSpecification

from osc_validation.assertions import assert_no_osc_engine_errors
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.cases.shared.trajectory_models import (
    TrajectoryInterpolationActor,
    TrajectoryInterpolationVertex,
)
from osc_validation.metrics import ObjectStateMetric
from osc_validation.cases.interpolation import (
    TrajectoryInterpolationCaseSpec,
    build_trajectory_interpolation_case,
)
from osc_validation.cases.interpolation.reference import (
    TrajectoryInterpolationReferenceMode,
)


@pytest.fixture(scope="module")
def odr_file(builtin_data_path):
    provider = BuiltinDataProvider(builtin_data_path)
    yield provider.ensure_data_path("xodr_example/map.xodr")
    provider.cleanup()


def _actor() -> TrajectoryInterpolationActor:
    return TrajectoryInterpolationActor(
        entity_ref="Ego",
        object_id=1,
        vertices=[
            TrajectoryInterpolationVertex(
                time_s=0.0,
                x=-290.0,
                y=-60.0,
                z=0.0,
            ),
            TrajectoryInterpolationVertex(
                time_s=2.0,
                x=-285.0,
                y=-60.0,
                z=0.0,
            ),
            TrajectoryInterpolationVertex(
                time_s=4.0,
                x=-285.0,
                y=-55.0,
                z=0.0,
            ),
        ],
    )


def _run_interpolation_case(
    scenario_contract,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
    interpolation_mode: TrajectoryInterpolationReferenceMode,
    initial_speed_mps: float,
):
    """Generate and compare one explicitly chosen interpolation expectation."""

    rate = 1.0
    actor = _actor()
    case_name = interpolation_mode
    case_result = build_trajectory_interpolation_case(
        TrajectoryInterpolationCaseSpec(
            contract=scenario_contract,
            output_xosc_path=tmp_path / f"trajectory_interpolation_{case_name}.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / f"reference_trajectory_interpolation_{case_name}.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace for trajectory interpolation validation"
                },
            ),
            actor=actor,
            stop_time_s=4.0,
            sample_period_s=rate,
            road_network_path=odr_file,
            host_vehicle_id=actor.object_id,
            interpolation_mode=interpolation_mode,
            initial_speed_mps=initial_speed_mps,
        )
    )

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=case_result.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / f"tool_trace_trajectory_interpolation_{case_name}.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool trace for trajectory interpolation validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )
    assert_no_osc_engine_errors(tool_trace_channel_spec)
    assert_osi_compliance(
        tool_trace_channel_spec,
        result_file=tmp_path / f"qc_result_trajectory_interpolation_{case_name}.xqar",
    )

    metric_result = ObjectStateMetric().compute(
        reference_channel_spec=case_result.reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=actor.object_id,
        match_mode="closest_initial_xy",
        ignore_first_speed_sample=True,
    )
    assert (
        metric_result.sample_count == 5
    ), "Trace should have 5 samples at 1 Hz from 0s to 4s inclusive"
    assert (
        metric_result.max_time_error <= 0.01
    ), "Trace should have max time error <= 0.01s"
    assert metric_result.max_xy_error < 0.1, "Trace should have max XY error < 0.1m"
    assert (
        metric_result.max_yaw_error < 0.01
    ), "Trace should have max yaw error < 0.01 rad"
    assert (
        metric_result.max_pitch_error < 0.01
    ), "Trace should have max pitch error < 0.01 rad"
    assert (
        metric_result.max_roll_error < 0.01
    ), "Trace should have max roll error < 0.01 rad"
    assert (
        metric_result.max_dimension_error < 0.01
    ), "Trace should have max dimension error < 0.01m"


@pytest.mark.osc_versions("1.4.0")
@pytest.mark.validation_category("trajectory")
@pytest.mark.validation_feature("FollowTrajectoryAction interpolation")
@pytest.mark.parametrize(
    ("interpolation_mode", "initial_speed_mps"),
    [("constant_acceleration_from_initial_speed", 0.0)],
)
def test_timed_polyline_trajectory_interpolation(
    scenario_contract,
    odr_file,
    generate_tool_trace,
    assert_osi_compliance,
    tmp_path,
    interpolation_mode,
    initial_speed_mps,
):
    """Validate the 1.4 default timed-polyline constant-acceleration contract."""
    _run_interpolation_case(
        scenario_contract,
        odr_file,
        generate_tool_trace,
        assert_osi_compliance,
        tmp_path,
        interpolation_mode,
        initial_speed_mps,
    )


@pytest.mark.osc_versions("1.3.0", "1.3.1")
@pytest.mark.exploratory
@pytest.mark.validation_category("trajectory")
@pytest.mark.validation_feature("FollowTrajectoryAction interpolation")
def test_legacy_linear_polyline_interpolation(
    scenario_contract,
    odr_file,
    generate_tool_trace,
    assert_osi_compliance,
    tmp_path,
):
    """Explore linear interpolation; this is not a conformance requirement."""
    _run_interpolation_case(
        scenario_contract,
        odr_file,
        generate_tool_trace,
        assert_osi_compliance,
        tmp_path,
        "linear_position",
        0.0,
    )
