import logging
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import pytest

from osc_validation.dataproviders import BuiltinDataProvider, DownloadDataProvider
from osc_validation.generation import (
    TimeToCollisionPositionTriggerSpec,
    TriggerTransformRequest,
    apply_trigger_transform,
    build_trace_with_calculated_kinematics,
    osi2osc,
)
from osc_validation.metrics import TrajectoryAlignmentSimilarityMetric
from osi_utilities import ChannelSpecification, open_channel


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


def _get_object_position_at_last_frame(
    channel_spec: ChannelSpecification, object_id: int
) -> tuple[float, float, float]:
    with open_channel(channel_spec) as reader:
        messages = list(reader)
        if not messages:
            raise RuntimeError("Input trace has no messages.")
        last = messages[-1]
        moving_objects = (
            last.global_ground_truth.moving_object
            if hasattr(last, "global_ground_truth")
            else last.moving_object
        )
        target = next((mo for mo in moving_objects if mo.id.value == object_id), None)
        if target is None:
            raise KeyError(f"Object ID {object_id} not found in last frame.")
        return (
            target.base.position.x,
            target.base.position.y,
            target.base.position.z,
        )


@pytest.mark.trajectory
@pytest.mark.parametrize("moving_object_id", [2])
@pytest.mark.parametrize("trigger_object_id", [1])
@pytest.mark.parametrize("trigger_ttc_s", [5.0])
@pytest.mark.parametrize("activation_frame_offset", [1])
@pytest.mark.parametrize("rate", [0.05])
@pytest.mark.parametrize("tolerance", [0.3])
def test_time_to_collision_start_trigger_activates_target_actor(
    osi_trace: Path,
    odr_file: Path,
    yaml_ruleset: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
    moving_object_id: int,
    trigger_object_id: int,
    trigger_ttc_s: float,
    activation_frame_offset: int,
    rate: float,
    tolerance: float,
):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    raw_reference_channel_spec = ChannelSpecification(osi_trace, message_type="SensorView")
    reference_trace_channel_spec = build_trace_with_calculated_kinematics(
        input_channel_spec=raw_reference_channel_spec,
        output_channel_spec=ChannelSpecification(
            path=tmp_path / "reference_with_kinematics_for_ttc.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Reference trace with calculated velocity and acceleration for TTC trigger validation"
            },
        ),
    )

    target_position_x, target_position_y, target_position_z = _get_object_position_at_last_frame(
        reference_trace_channel_spec, trigger_object_id
    )

    osc_path = osi2osc(
        osi_trace_spec=reference_trace_channel_spec,
        path_xosc=tmp_path / "osi2osc_ttc_start_trigger.xosc",
        path_xodr=odr_file,
    )

    transform_result = apply_trigger_transform(
        TriggerTransformRequest(
            source_xosc_path=osc_path,
            source_reference_channel_spec=reference_trace_channel_spec,
            output_xosc_path=osc_path,
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference_ttc_start_trigger_comparison.mcap",
                message_type="SensorView",
                metadata={
                    "net.asam.osi.trace.channel.description": "Reference trace with TTC start trigger applied"
                },
            ),
            spec=TimeToCollisionPositionTriggerSpec(
                trigger_entity_ref="Ego",
                target_event_name=f"osi_moving_object_{moving_object_id}_maneuver_event",
                condition_name=f"ttc_trigger_object{moving_object_id}_start",
                trigger_ttc_s=trigger_ttc_s,
                trigger_object_id=trigger_object_id,
                triggered_object_id=moving_object_id,
                target_position_x=target_position_x,
                target_position_y=target_position_y,
                target_position_z=target_position_z,
                trigger_rule="lessOrEqual",
                activation_frame_offset=activation_frame_offset,
            ),
        )
    )
    osc_path = transform_result.xosc_path

    tool_trace_channel_spec = generate_tool_trace(
        osc_path=osc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool_trace_ttc_start_trigger.mcap",
            message_type="SensorView",
            metadata={
                "net.asam.osi.trace.channel.description": "Tool-generated trace for TTC start trigger validation"
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
        result_file=tmp_path / "trajectory_alignment_similarity_report_ttc_start_trigger.txt",
        time_tolerance=0.01,
        lag_scan_max_frames=2,
    )

    assert abs(best_lag_frames) <= 2
    assert area < tolerance
    assert cl < tolerance
    assert mae < tolerance
