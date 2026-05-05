import logging
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import pytest

from osc_validation.dataproviders import BuiltinDataProvider, DownloadDataProvider
from osc_validation.generation import (
    TraveledDistanceTriggerSpec,
    TriggerTransformRequest,
    apply_trigger_transform,
    find_traveled_distance_activation_point,
    osi2osc,
)
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric
from osi_utilities import ChannelSpecification

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
@pytest.mark.parametrize("moving_object_id", [2])           # moving object to be evaluated for trigger activation and trajectory alignment
@pytest.mark.parametrize("trigger_object_id", [1])          # moving object to be triggered for traveled distance trigger condition
@pytest.mark.parametrize("trigger_distance_m", [55.0])
@pytest.mark.parametrize("activation_frame_offset", [1])    # It should take one frame for the triggered event to activate after the distance threshold is crossed
@pytest.mark.parametrize("rate", [0.05])
@pytest.mark.parametrize("tolerance", [0.2])
def test_traveled_distance_start_trigger_activates_target_actor(
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

    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type="SensorView"
    )
    osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / "osi2osc_traveled_distance_start_trigger.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_traveled_distance_trigger_comparison.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace with traveled distance trigger applied"
                },
            ),
            spec=TraveledDistanceTriggerSpec(
                trigger_entity_ref="Ego",
                target_event_name=f"osi_moving_object_{moving_object_id}_maneuver_event",
                condition_name=f"distance_trigger_object{moving_object_id}_start",
                trigger_distance_m=trigger_distance_m,
                trigger_object_id=trigger_object_id,
                triggered_object_id=moving_object_id,
                trigger_rule="greaterOrEqual",
                activation_frame_offset=activation_frame_offset,
            ),
            init_pose_policy="close_to_trajectory_start",
        )
    )
    osc_path = transform_result.xosc_path

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_traveled_distance_start_trigger.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for traveled-distance start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )

    metric = TrajectoryAlignmentSimilarityMetric()
    delayed_reference_channel_spec = transform_result.reference_channel_spec

    area, cl, mae, _best_lag_frames = metric.compute(
        reference_channel_spec=delayed_reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        result_file=tmp_path / "trajectory_alignment_similarity_report.txt",
        # Start after the trigger edge because OpenSCENARIO does not mandate
        # whether the first trajectory point is applied in the activation frame.
        start_time=find_traveled_distance_activation_point(
            input_channel_spec=reference_trace_channel_spec,
            trigger_object_id=trigger_object_id,
            trigger_distance_m=trigger_distance_m,
            trigger_rule="greaterOrEqual",
        ).time_s + rate,
        time_tolerance=0.01,
        lag_scan_max_frames=1,
    )

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
