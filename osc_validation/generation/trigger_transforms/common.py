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


def get_moving_objects(message):
    if hasattr(message, "global_ground_truth"):
        return message.global_ground_truth.moving_object
    if hasattr(message, "moving_object"):
        return message.moving_object
    return []


def find_moving_object(message, object_id: int):
    moving_objects = get_moving_objects(message)
    for mo in moving_objects:
        if mo.id.value == object_id:
            return mo
    return None
