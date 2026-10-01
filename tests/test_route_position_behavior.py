from math import atan, pi, hypot
from lxml import etree
import pytest
from osi_utilities import ChannelSpecification, open_channel, open_channel_writer
from osc_validation.generation.xosc_builders import FromLaneCoordinates, FromRoadCoordinates, Orientation, RoutePosition, append_position
from osc_validation.validation.scenario.positions.val_route_position import CASES, CROSS_LANE_CASES, ExpectedPose, classify, inline_route
from osc_validation.reference import (
    InitActionReferenceActor,
    InitActionReferenceRequest,
    build_init_actions_reference_trace,
)


def _reference(path, candidate):
    return build_init_actions_reference_trace(
        InitActionReferenceRequest(
            output_channel_spec=ChannelSpecification(
                path=path, message_type="SensorView"
            ),
            actors=[
                InitActionReferenceActor(
                    object_id=1,
                    x=candidate.x,
                    y=candidate.y,
                    z=0,
                    yaw=candidate.yaw,
                    bounding_box_center_x=0,
                    bounding_box_center_y=0,
                    bounding_box_center_z=0,
                )
            ],
            duration_s=0.5,
            sample_period_s=0.05,
        )
    )

@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("coordinates,tag,attrs", [(FromRoadCoordinates(20, -1), "FromRoadCoordinates", {"pathS":"20.0", "t":"-1.0"}), (FromLaneCoordinates(20, 1, -1), "FromLaneCoordinates", {"pathS":"20.0", "laneId":"1", "laneOffset":"-1.0"})])
@pytest.mark.parametrize("orientation", [None, Orientation()])
def test_inline_route_serialization(reverse, coordinates, tag, attrs, orientation):
    element = append_position(etree.Element("Position"), RoutePosition(inline_route(reverse), coordinates, orientation))
    assert [child.tag for child in element] == (["RouteRef", "InRoutePosition"] if orientation is None else ["RouteRef", "Orientation", "InRoutePosition"])
    route = element.find("RouteRef/Route")
    assert route.get("closed") == "false"
    waypoints = route.findall("Waypoint")
    assert [float(w.find("Position/RoadPosition").get("s")) for w in waypoints] == ([90, 10] if reverse else [10, 90])
    assert all(float(w.find("Position/RoadPosition").get("t")) == -1 for w in waypoints)
    assert dict(element.find(f"InRoutePosition/{tag}").attrib) == attrs

def test_matrix_and_expected_geometry():
    assert len(CASES) == len({case.id for case in CASES}) == 20
    assert all(isinstance(case.expected_pose, ExpectedPose) for case in CASES)
    for case in CASES:
        p = case.expected_pose; reverse = case.id.startswith("reverse-"); x = 70 if reverse else 30
        coordinates = case.position.in_route_position
        offset = coordinates.t if isinstance(coordinates, FromRoadCoordinates) else coordinates.lane_offset
        assert offset in ({-10, 10} if case in CROSS_LANE_CASES else {0, -2, 2})
        if "-road-" in case.id:
            assert p.x == x
            assert p.y == (-case.position.in_route_position.t if reverse else case.position.in_route_position.t)
            assert p.yaw == (pi if reverse else 0)
        else:
            lane = case.position.in_route_position.lane_id
            offset = case.position.in_route_position.lane_offset
            center_y = lane * (16 if reverse else 8)
            dx, dy = p.x - x, p.y - center_y
            assert p.yaw == pytest.approx(lane * atan(.2))
            assert hypot(dx, dy) == pytest.approx(abs(offset))
            assert dx + lane * .2 * dy == pytest.approx(0)
            assert dy * offset >= 0
            if offset:
                assert hypot(dx, p.y - (center_y + offset)) > .1
                assert hypot(dx, p.y - (center_y + offset)) == pytest.approx(.1970752359 * abs(offset))

@pytest.mark.parametrize("case", CROSS_LANE_CASES, ids=lambda case: case.id)
def test_cross_lane_offset_keeps_referenced_lane_heading(case, tmp_path):
    pose = case.expected_pose
    lane = case.position.in_route_position.lane_id
    # The target lies inside the opposite lane at its actual road s (= world x).
    assert 0 < -lane * pose.y < 4 + .4 * pose.x
    assert pose.x == pytest.approx(31.9611613514)
    assert pose.y == pytest.approx(-lane * 1.8058067569)
    assert pose.yaw == pytest.approx(lane * atan(.2))
    assert case.position.orientation is None
    reference = _reference(tmp_path / "reference.mcap", pose)
    classify(reference, pose, reference)
    wrong_lane_pose = ExpectedPose(pose.x, pose.y, -lane * atan(.2))
    measured = _reference(tmp_path / "wrong_lane.mcap", wrong_lane_pose)
    with pytest.raises(AssertionError, match="yaw error=0.3948"):
        classify(measured, pose, reference)

def test_direct_comparison_reports_expected_and_measured_pose(tmp_path):
    trace = _reference(tmp_path / "measured.mcap", ExpectedPose(25, 7, .5))
    reference = _reference(tmp_path / "reference.mcap", ExpectedPose(30, 0, 0))
    with pytest.raises(AssertionError, match="Initial="):
        classify(trace, ExpectedPose(30, 0, 0), reference)
    assert {path.name for path in tmp_path.iterdir()} == {"measured.mcap", "reference.mcap"}

@pytest.mark.parametrize("corruption", ["empty", "time", "id"])
def test_invalid_traces_fail(tmp_path, corruption):
    trace = _reference(tmp_path / "measured.mcap", ExpectedPose(20, 0, 0))
    reference = _reference(tmp_path / "reference.mcap", ExpectedPose(20, 0, 0))
    with open_channel(trace) as reader: messages = list(reader)
    if corruption == "empty": messages = []
    elif corruption == "time": messages[1].timestamp.CopyFrom(messages[0].timestamp)
    else: messages[1].global_ground_truth.moving_object[0].id.value = 99
    with open_channel_writer(trace) as writer:
        for message in messages: writer.write_message(message)
    with pytest.raises((ValueError, RuntimeError, KeyError)):
        classify(trace, ExpectedPose(20, 0, 0), reference)
