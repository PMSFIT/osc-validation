import logging
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import pytest

from osc_validation.dataproviders import BuiltinDataProvider, DownloadDataProvider
from osc_validation.generation import (
    DistancePositionTriggerSpec,
    TriggerTransformRequest,
    apply_trigger_transform,
    osi2osc,
)
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric
from osc_validation.utils.osi_channel_specification import OSIChannelSpecification


@pytest.fixture(
    scope="module",
    params=[
        "simple_trajectories/20240603T152322.095000Z_sv_370_3200_618_dronetracker_135_swerve.mcap"
    ],
)
def osi_trace(request):
    provider = BuiltinDataProvider()
    yield provider.ensure_data_path(request.param)
    provider.cleanup()


@pytest.fixture(
    scope="module",
    params=[
        "https://raw.githubusercontent.com/OpenSimulationInterface/qc-osi-trace/refs/heads/main/qc_ositrace/checks/osirules/rulesyml/osi_3_7_0.yml"
    ],
)
def yaml_ruleset(request):
    uri = request.param
    filename = Path(urlparse(uri).path).name
    base_path = Path("download/osirules")
    provider = DownloadDataProvider(uri=uri, base_path=base_path)
    yield provider.ensure_data_path(filename)
    provider.cleanup()


@pytest.fixture(scope="module")
def odr_file(request):
    return request.getfixturevalue("osi_trace").with_suffix(".xodr")


@pytest.mark.trajectory
@pytest.mark.parametrize("moving_object_id", [2])
@pytest.mark.parametrize("trigger_object_id", [1])
@pytest.mark.parametrize("trigger_distance_m", [10.0])
@pytest.mark.parametrize("activation_frame_offset", [1])
@pytest.mark.parametrize("rate", [0.05])
@pytest.mark.parametrize("tolerance", [0.1])
def test_distance_euclidian_start_trigger_activates_target_actor(
    osi_trace: Path,
    odr_file: Path,
    yaml_ruleset: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_distance_m: float,
    activation_frame_offset: int,
    rate: float,
    tolerance: float,
):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    reference_trace_channel_spec = OSIChannelSpecification(osi_trace, message_type="SensorView")
    target_position_x, target_position_y, target_position_z = (-275.37930040547195, -52.90668516705058, 0.29707853723620486)

    osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / "osi2osc_distance_euclidian_start_trigger.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=OSIChannelSpecification(
                path=tmp_path / "reference_distance_euclidian_start_trigger_comparison.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace with euclidian distance start trigger applied"
                },
            ),
            spec=DistancePositionTriggerSpec(
                trigger_entity_ref="Ego",
                target_event_name=f"osi_moving_object_{moving_object_id}_maneuver_event",
                condition_name=f"distance_euclidian_trigger_object{moving_object_id}_start",
                trigger_distance_m=trigger_distance_m,
                trigger_object_id=trigger_object_id,
                triggered_object_id=moving_object_id,
                target_position_x=target_position_x,
                target_position_y=target_position_y,
                target_position_z=target_position_z,
                relative_distance_type="euclidianDistance",
                trigger_rule="lessOrEqual",
                activation_frame_offset=activation_frame_offset,
            ),
        )
    )
    osc_path = transform_result.xosc_path

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=OSIChannelSpecification(
            path=tmp_path / "tool_trace_distance_euclidian_start_trigger.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for euclidian distance start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )

    metric = TrajectoryAlignmentSimilarityMetric()
    reference_triggered_channel_spec = transform_result.reference_channel_spec

    area, cl, mae, best_lag_frames = metric.compute(
        reference_channel_spec=reference_triggered_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        result_file=tmp_path
        / "trajectory_alignment_similarity_report_distance_euclidian_start_trigger.txt",
        time_tolerance=0.01,
        lag_scan_max_frames=2,
    )

    assert abs(best_lag_frames) <= 2
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
