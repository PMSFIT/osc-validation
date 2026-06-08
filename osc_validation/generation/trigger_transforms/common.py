from dataclasses import dataclass

from ...utils.utils import find_moving_object, get_moving_objects


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


