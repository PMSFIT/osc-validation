import pytest

from tests.conftest import _make_sensor_view

from osc_validation.generation.trigger_transforms.common import evaluate_condition_edge
from osc_validation.generation.trigger_transforms.speed import (
    _find_speed_activation_index_from_messages,
)


def _speed_messages(speeds_mps: list[float]):
    messages = []
    for index, speed in enumerate(speeds_mps):
        msg = _make_sensor_view(index * 0.1, obj_id=1)
        moving_object = msg.global_ground_truth.moving_object[0]
        moving_object.base.velocity.x = speed
        moving_object.base.velocity.y = 0.0
        messages.append(msg)
    return messages


@pytest.mark.parametrize(
    ("previous_value", "current_value", "condition_edge", "expected"),
    [
        (None, True, "none", True),
        (None, True, "rising", False),
        (False, True, "rising", True),
        (True, False, "falling", True),
        (False, True, "risingOrFalling", True),
        (True, True, "risingOrFalling", False),
    ],
)
def test_evaluate_condition_edge(
    previous_value,
    current_value,
    condition_edge,
    expected,
):
    assert (
        evaluate_condition_edge(previous_value, current_value, condition_edge)
        is expected
    )


def test_evaluate_condition_edge_rejects_unknown_edge():
    with pytest.raises(ValueError, match="Unsupported condition_edge"):
        evaluate_condition_edge(False, True, "unknown")


def test_speed_condition_edge_none_can_activate_at_first_frame():
    activation_index = _find_speed_activation_index_from_messages(
        messages=_speed_messages([5.0, 6.0, 7.0]),
        trigger_object_id=1,
        trigger_speed_mps=5.0,
        trigger_rule="greaterOrEqual",
        condition_edge="none",
    )

    assert activation_index == 0


def test_speed_condition_edge_rising_requires_false_to_true_transition():
    activation_index = _find_speed_activation_index_from_messages(
        messages=_speed_messages([4.0, 4.0, 6.0]),
        trigger_object_id=1,
        trigger_speed_mps=5.0,
        trigger_rule="greaterOrEqual",
        condition_edge="rising",
    )

    assert activation_index == 2


def test_speed_condition_edge_rising_does_not_activate_when_initially_true():
    with pytest.raises(RuntimeError, match="condition_edge=rising"):
        _find_speed_activation_index_from_messages(
            messages=_speed_messages([6.0, 6.0, 6.0]),
            trigger_object_id=1,
            trigger_speed_mps=5.0,
            trigger_rule="greaterOrEqual",
            condition_edge="rising",
        )


def test_speed_condition_edge_falling_requires_true_to_false_transition():
    activation_index = _find_speed_activation_index_from_messages(
        messages=_speed_messages([6.0, 6.0, 4.0]),
        trigger_object_id=1,
        trigger_speed_mps=5.0,
        trigger_rule="greaterOrEqual",
        condition_edge="falling",
    )

    assert activation_index == 2


def test_speed_condition_edge_rising_or_falling_requires_any_transition():
    activation_index = _find_speed_activation_index_from_messages(
        messages=_speed_messages([4.0, 6.0]),
        trigger_object_id=1,
        trigger_speed_mps=5.0,
        trigger_rule="greaterOrEqual",
        condition_edge="risingOrFalling",
    )

    assert activation_index == 1
