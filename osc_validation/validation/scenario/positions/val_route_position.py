"""Validate the selected interpretation of RoutePosition placement."""

from dataclasses import dataclass
from math import atan, isfinite, pi, sqrt

import pytest
from osi_utilities import ChannelSpecification, open_channel

from osc_validation.assertions import assert_no_osc_engine_errors
from osc_validation.dataproviders import BuiltinDataProvider
from osc_validation.generation.xosc_builders import (
    FromLaneCoordinates,
    FromRoadCoordinates,
    Orientation,
    RoadPosition,
    Route,
    RoutePosition,
)
from osc_validation.metrics import ObjectStateMetric
from osc_validation.oracles import (
    InitActionCaseSpec,
    InitActionOracleActor,
    build_init_teleport_action_case,
)
from osc_validation.utils.utils import timestamp_osi_to_float


@dataclass(frozen=True)
class ExpectedPose:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class BehaviorCase:
    id: str
    position: RoutePosition
    expected_pose: ExpectedPose


def inline_route(reverse):
    heading = pi if reverse else 0
    waypoints = (90, 10) if reverse else (10, 90)
    return Route(
        "reverse" if reverse else "forward",
        tuple(
            RoadPosition("1", s, -1, Orientation(h=heading, type="absolute"))
            for s in waypoints
        ),
    )


def _case(reverse, alternative, offset=0):
    lane = {"road": None, "lane-minus-one": -1, "lane-plus-one": 1}[alternative]
    coordinates = (
        FromRoadCoordinates(20, offset)
        if lane is None
        else FromLaneCoordinates(20, lane, offset)
    )
    x = 70 if reverse else 30
    if lane is None:
        # Interpret relative orientation and t in the route's directed frame.
        yaw = pi if reverse else 0
        px, py = x, -offset if reverse else offset
    else:
        slope = lane * 0.2
        y, yaw = lane * (2 + 0.2 * x), atan(slope)
        px = x - offset * slope / sqrt(1.04)
        py = y + offset / sqrt(1.04)
    direction = "reverse" if reverse else "forward"
    suffix = f"-offset-{offset:+d}" if offset else ""
    return BehaviorCase(
        f"{direction}-{alternative}-{suffix}",
        RoutePosition(inline_route(reverse), coordinates),
        ExpectedPose(px, py, yaw),
    )


CROSS_LANE_CASES = (
    _case(False, "lane-plus-one", -10),
    _case(False, "lane-minus-one", 10),
)


CASES = tuple(
    _case(reverse, alternative, offset)
    for reverse in (False, True)
    for alternative in ("road", "lane-minus-one", "lane-plus-one")
    for offset in (0, -2, 2)
) + CROSS_LANE_CASES


def _measured_poses(trace):
    poses = []
    object_id = None
    with open_channel(trace) as reader:
        for message in reader:
            objects = (
                message.global_ground_truth.moving_object
                if hasattr(message, "global_ground_truth")
                else message.moving_object
            )
            if len(objects) != 1:
                raise ValueError("Expected exactly one moving object in every frame")
            obj = objects[0]
            if object_id is not None and obj.id.value != object_id:
                raise ValueError("Moving object ID changed during trace")
            object_id = obj.id.value
            pose = dict(
                time=timestamp_osi_to_float(message.timestamp),
                x=obj.base.position.x,
                y=obj.base.position.y,
                z=obj.base.position.z,
                yaw=obj.base.orientation.yaw,
                pitch=obj.base.orientation.pitch,
                roll=obj.base.orientation.roll,
            )
            if not all(isfinite(value) for value in pose.values()):
                raise ValueError("Non-finite measured pose or timestamp")
            if poses and pose["time"] <= poses[-1]["time"]:
                raise ValueError("Trace timestamps must strictly increase")
            poses.append(pose)
    if not poses:
        raise ValueError("Empty measured trace")
    return poses[0], poses[-1]


def classify(trace, expected_pose, reference):
    """Compare the measured trace directly with the one expected pose."""
    initial, final = _measured_poses(trace)
    result = ObjectStateMetric().compute(reference, trace, moving_object_id=1,
        match_mode="closest_initial_xy", ignore_first_speed_sample=True)
    assert (result.sample_count > 0 and result.max_time_error <= 0.01
            and result.max_xy_error < 0.1 and result.max_yaw_error < 0.01), (
        "Measured RoutePosition behavior did not match expected pose.\n"
        f"Initial={initial}\nFinal={final}\nExpected={expected_pose}\n"
        f"time error={result.max_time_error:.4f} s, xy error={result.max_xy_error:.4f} m, "
        f"yaw error={result.max_yaw_error:.4f} rad"
    )


@pytest.fixture(scope="module")
def odr_file(builtin_data_path):
    provider = BuiltinDataProvider(builtin_data_path)
    yield provider.ensure_data_path("positions/straight_varying_width.xodr")
    provider.cleanup()


@pytest.mark.validation_category("position")
@pytest.mark.validation_feature("RoutePosition reference and orientation behavior")
@pytest.mark.parametrize("behavior", CASES, ids=lambda case: case.id)
def test_route_position_behavior(
    behavior,
    odr_file,
    generate_tool_trace,
    assert_osi_compliance,
    tmp_path,
):
    """Check observed behavior against the selected expected pose."""
    candidate = behavior.expected_pose
    case = build_init_teleport_action_case(
        InitActionCaseSpec(
            output_xosc_path=tmp_path / "route_position.xosc",
            output_reference_channel_spec=ChannelSpecification(
                path=tmp_path / "reference.mcap", message_type="SensorView"
            ),
            actors=[
                InitActionOracleActor(
                    entity_ref="Ego",
                    object_id=1,
                    x=candidate.x,
                    y=candidate.y,
                    z=0,
                    yaw=candidate.yaw,
                    bounding_box_center_x=0,
                    bounding_box_center_y=0,
                    bounding_box_center_z=0,
                    position=behavior.position,
                )
            ],
            duration_s=0.5,
            sample_period_s=0.05,
            road_network_path=odr_file,
        )
    )
    trace = generate_tool_trace(
        osc_path=case.xosc_path,
        odr_path=odr_file,
        osi_output_spec=ChannelSpecification(
            path=tmp_path / "tool.mcap", message_type="SensorView"
        ),
        log_path=tmp_path,
        rate=0.05,
    )
    assert_no_osc_engine_errors(trace)
    assert_osi_compliance(trace, result_file=tmp_path / "qc_result.xqar")
    classify(trace, behavior.expected_pose, case.reference_channel_spec)
