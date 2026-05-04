from pathlib import Path
from typing import Callable

import pytest

from osc_validation.dataproviders import BuiltinDataProvider
from val_distance_longitudinal_start_trigger import _run_distance_longitudinal_start_trigger_case
from val_speed_start_trigger import _run_speed_start_trigger_case


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


@pytest.fixture(scope="module")
def odr_file(request):
    return request.getfixturevalue("osi_trace").with_suffix(".xodr")


@pytest.mark.trajectory
def test_distance_longitudinal_start_trigger_respects_condition_delay(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
):
    _run_distance_longitudinal_start_trigger_case(
        osi_trace=osi_trace,
        odr_file=odr_file,
        generate_tool_trace=generate_tool_trace,
        tmp_path=tmp_path,
        condition_delay_s=1.0,
    )


@pytest.mark.trajectory
def test_speed_start_trigger_respects_condition_delay(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    tmp_path: Path,
):
    _run_speed_start_trigger_case(
        osi_trace=osi_trace,
        odr_file=odr_file,
        generate_tool_trace=generate_tool_trace,
        tmp_path=tmp_path,
        condition_delay_s=1.0,
    )
