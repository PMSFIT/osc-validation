import math

import pytest

from tests.conftest import _make_sensor_view

from osc_validation.generation.init_transforms import InitPoseOverride
from osc_validation.generation.init_transforms.init_pose import (
    apply_init_pose_override_to_reference_object,
)


def test_apply_init_pose_override_to_reference_object_restores_center_z():
    msg = _make_sensor_view(0.0, obj_id=1)
    moving_object = msg.global_ground_truth.moving_object[0]
    moving_object.base.dimension.height = 1.472

    apply_init_pose_override_to_reference_object(
        moving_object,
        InitPoseOverride(
            entity_ref="Ego",
            object_id=1,
            x=-290.0,
            y=-60.0,
            z=0.0,
            yaw=0.0,
        ),
    )

    assert moving_object.base.position.x == pytest.approx(-290.0)
    assert moving_object.base.position.y == pytest.approx(-60.0)
    assert moving_object.base.position.z == pytest.approx(0.736)


def test_apply_init_pose_override_to_reference_object_restores_rotated_xy_offset():
    msg = _make_sensor_view(0.0, obj_id=1)
    moving_object = msg.global_ground_truth.moving_object[0]
    moving_object.base.dimension.height = 2.0
    moving_object.vehicle_attributes.bbcenter_to_rear.x = -1.0
    moving_object.vehicle_attributes.bbcenter_to_rear.y = 0.0

    apply_init_pose_override_to_reference_object(
        moving_object,
        InitPoseOverride(
            entity_ref="Ego",
            object_id=1,
            x=10.0,
            y=20.0,
            z=0.0,
            yaw=math.pi / 2,
        ),
    )

    assert moving_object.base.position.x == pytest.approx(10.0)
    assert moving_object.base.position.y == pytest.approx(21.0)
    assert moving_object.base.position.z == pytest.approx(1.0)
    assert moving_object.base.orientation.yaw == pytest.approx(math.pi / 2)
