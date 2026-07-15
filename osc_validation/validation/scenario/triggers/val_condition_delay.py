from pathlib import Path
from typing import Callable

import pytest

from osc_validation.dataproviders import BuiltinDataProvider
from .val_distance_longitudinal_start_trigger import _run_distance_longitudinal_start_trigger_case
from .val_speed_start_trigger import _run_speed_start_trigger_case


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


@pytest.mark.validation_category("trigger")
@pytest.mark.validation_feature("Condition delay")
def test_distance_longitudinal_start_trigger_respects_condition_delay(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
):
    """
    OpenSCENARIO feature: trigger Condition delay on longitudinal distance conditions.

    Reuses the longitudinal distance trigger case with a one-second conditionDelay.
    The target actor should activate only after the distance condition has held
    through that delay.
    """

    _run_distance_longitudinal_start_trigger_case(
        osi_trace=osi_trace,
        odr_file=odr_file,
        generate_tool_trace=generate_tool_trace,
        assert_osi_compliance=assert_osi_compliance,
        tmp_path=tmp_path,
        condition_delay_s=1.0,
    )


@pytest.mark.validation_category("trigger")
@pytest.mark.validation_feature("Condition delay")
def test_speed_start_trigger_respects_condition_delay(
    osi_trace: Path,
    odr_file: Path,
    generate_tool_trace: Callable,
    assert_osi_compliance: Callable,
    tmp_path: Path,
):
    """
    OpenSCENARIO feature: trigger Condition delay on speed conditions.

    Reuses the speed start trigger setup with a one-second conditionDelay. The
    target actor's trajectory should begin after the delayed activation time, not
    immediately at the threshold crossing.
    """

    _run_speed_start_trigger_case(
        osi_trace=osi_trace,
        odr_file=odr_file,
        generate_tool_trace=generate_tool_trace,
        assert_osi_compliance=assert_osi_compliance,
        tmp_path=tmp_path,
        condition_delay_s=1.0,
    )
