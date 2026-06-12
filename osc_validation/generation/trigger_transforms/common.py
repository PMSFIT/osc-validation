from dataclasses import dataclass
from typing import Literal

from ...utils.utils import find_moving_object, get_moving_objects


ConditionEdge = Literal["falling", "none", "rising", "risingOrFalling"]


@dataclass(frozen=True)
class ActivationPoint:
    index: int
    time_s: float


def evaluate_rule(lhs: float, rhs: float, rule: str) -> bool:
    if rule == "greaterThan":
        return lhs > rhs
    if rule == "greaterOrEqual":
        return lhs >= rhs
    if rule == "lessThan":
        return lhs < rhs
    if rule == "lessOrEqual":
        return lhs <= rhs
    if rule == "equalTo":
        return lhs == rhs
    if rule == "notEqualTo":
        return lhs != rhs
    raise ValueError(f"Unsupported rule '{rule}'.")


def evaluate_condition_edge(
    previous_value: bool | None,
    current_value: bool,
    condition_edge: ConditionEdge,
) -> bool:
    if condition_edge == "none":
        return current_value
    if previous_value is None:
        return False
    if condition_edge == "rising":
        return not previous_value and current_value
    if condition_edge == "falling":
        return previous_value and not current_value
    if condition_edge == "risingOrFalling":
        return previous_value != current_value
    raise ValueError(f"Unsupported condition_edge '{condition_edge}'.")


def validate_condition_edge(condition_edge: ConditionEdge) -> None:
    evaluate_condition_edge(None, False, condition_edge)
