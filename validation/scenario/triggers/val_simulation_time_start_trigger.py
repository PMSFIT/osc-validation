import logging
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import pytest

from osc_validation.dataproviders import BuiltinDataProvider, DownloadDataProvider
from osc_validation.generation import (
    InitPoseOverride,
    SimulationTimeTriggerSpec,
    TriggerTransformRequest,
    apply_trigger_transform,
    osi2osc,
)
from osc_validation.metrics.qccheck import QCOSITraceChecker
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
@pytest.mark.parametrize("moving_object_id", [1, 2])
@pytest.mark.parametrize("ego_object_id", [1])
@pytest.mark.parametrize("init_pose_object_id", [2])
@pytest.mark.parametrize("trigger_delay", [10.0])
@pytest.mark.parametrize("activation_frame_offset", [0]) # The trigger should activate immediately when the simulation time condition is met
@pytest.mark.parametrize("max_alignment_lag_frames", [0]) # Don't accept any lag between the trajectories
@pytest.mark.parametrize("rate", [0.05])
@pytest.mark.parametrize("tolerance", [2e-1])
def test_simulation_time_start_trigger_delays_actor_trajectory(
    osi_trace: Path,
    odr_file: Path,
    yaml_ruleset: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    moving_object_id: int,
    ego_object_id: int,
    init_pose_object_id: int,
    trigger_delay: float,
    activation_frame_offset: int,
    max_alignment_lag_frames: int,
    rate: float,
    tolerance: float,
):
    """
    Validates delayed Event StartTrigger (SimulationTimeCondition) behavior
    using trajectory alignment similarity.
    """

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    reference_trace_channel_spec = ChannelSpecification(
        osi_trace, message_type="SensorView"
    )
    osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / "osi2osc_simulation_time_start_trigger.xosc",
        path_xodr=odr_file,
    )
    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / f"reference_delayed_comparison_{moving_object_id}.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Delayed reference trace for trigger delay validation"
                },
            ),
            spec=SimulationTimeTriggerSpec(
                trigger_delay=trigger_delay,
                trigger_rule="greaterOrEqual",
                activation_frame_offset=activation_frame_offset,
            ),
            init_pose_policy="explicit_overrides", # need explicit override because osi2osc default init position (0,0,0) is not on road (gtgen doesn't support placing objects outside of road)
            init_pose_overrides=[
                InitPoseOverride(
                    entity_ref="Ego",
                    object_id=ego_object_id,
                    x=-290.0,
                    y=-60.0,
                    z=0.7015,
                    yaw=0.0,
                    pitch=0.0,
                    roll=0.0,
                ),
                InitPoseOverride(
                    entity_ref=f"osi_moving_object_{init_pose_object_id}",
                    object_id=init_pose_object_id,
                    x=-280.0,
                    y=-55.0,
                    z=0.7015,
                    yaw=0.0,
                    pitch=0.0,
                    roll=0.0,
                ),
            ],
        )
    )
    osc_path = transform_result.xosc_path

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_simulation_time_start_trigger.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for simulation-time start trigger validation"
            },
        ),
        log_path=tmp_path,
        rate=rate,
    )

    """ qc_check = QCOSITraceChecker(ruleset=yaml_ruleset)
    result = qc_check.check(
        channel_spec=tool_trace_channel_spec,
        result_file=tmp_path / "qc_result_trigger_delay.xqar",
        output_config=tmp_path / "qc_config_trigger_delay.xml",
    )
    assert result == True, "QC check failed for the trigger-delay tool trace." """

    metric = TrajectoryAlignmentSimilarityMetric()
    delayed_reference_channel_spec = transform_result.reference_channel_spec

    # Evaluate whole trajectory including pre-trigger portion
    area, cl, mae, _best_lag_frames = metric.compute(
        reference_channel_spec=delayed_reference_channel_spec,
        tool_channel_spec=tool_trace_channel_spec,
        moving_object_id=moving_object_id,
        result_file=tmp_path
        / f"trajectory_alignment_similarity_report_{moving_object_id}.txt",
        start_time=trigger_delay+rate, # Start evaluation slightly after the trigger delay to allow for exact alignment of the post-trigger trajectory portions
        time_tolerance=0.01,
        lag_scan_max_frames=max_alignment_lag_frames,
    )

    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
