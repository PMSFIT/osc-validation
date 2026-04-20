from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter


def _get_moving_objects(message):
    if hasattr(message, "global_ground_truth"):
        return message.global_ground_truth.moving_object
    if hasattr(message, "moving_object"):
        return message.moving_object
    return []


def _find_moving_object(message, object_id: int):
    moving_objects = _get_moving_objects(message)
    for mo in moving_objects:
        if mo.id.value == object_id:
            return mo
    return None


def _derive_first_order(values: list[tuple[float, float, float]], timestamps: list[float]):
    count = len(values)
    if count == 0:
        return []
    out = [(0.0, 0.0, 0.0)]
    for idx in range(1, count):
        dt = timestamps[idx] - timestamps[idx - 1]
        if dt <= 0:
            raise RuntimeError("Non-increasing timestamps encountered while deriving kinematics.")
        x0, y0, z0 = values[idx - 1]
        x1, y1, z1 = values[idx]
        out.append(((x1 - x0) / dt, (y1 - y0) / dt, (z1 - z0) / dt))
    return out


def build_trace_with_calculated_kinematics(
    input_channel_spec: OSIChannelSpecification,
    output_channel_spec: OSIChannelSpecification,
) -> OSIChannelSpecification:
    """
    Create a copy of the input trace where all moving objects have derived
    base.velocity and base.acceleration values populated from positions over time.

    Derivation scheme (causal):
    - Velocity is derived from position using backward differences:
      v[i] = (p[i] - p[i-1]) / (t[i] - t[i-1]) for i >= 1.
    - Acceleration is derived from velocity using backward differences:
      a[i] = (v[i] - v[i-1]) / (t[i] - t[i-1]) for i >= 1.
    - First frame is initialized to zero:
      v[0] = (0,0,0), a[0] = (0,0,0).
    """
    with OSIChannelReader.from_osi_channel_specification(input_channel_spec) as reader:
        input_messages = list(reader.get_messages())
        if not input_messages:
            raise RuntimeError("Input trace has no messages.")

    timestamps = [
        msg.timestamp.seconds + msg.timestamp.nanos / 1e9 for msg in input_messages
    ]
    object_ids = [mo.id.value for mo in _get_moving_objects(input_messages[0])]
    if not object_ids:
        raise RuntimeError("No moving objects found in input trace.")

    positions_by_id: dict[int, list[tuple[float, float, float]]] = {obj_id: [] for obj_id in object_ids}
    for msg in input_messages:
        for obj_id in object_ids:
            mo = _find_moving_object(msg, obj_id)
            if mo is None:
                raise KeyError(f"Moving object ID {obj_id} missing in one or more frames.")
            positions_by_id[obj_id].append(
                (mo.base.position.x, mo.base.position.y, mo.base.position.z)
            )

    velocities_by_id: dict[int, list[tuple[float, float, float]]] = {}
    accelerations_by_id: dict[int, list[tuple[float, float, float]]] = {}
    for obj_id in object_ids:
        velocities = _derive_first_order(positions_by_id[obj_id], timestamps)
        accelerations = _derive_first_order(velocities, timestamps)
        velocities_by_id[obj_id] = velocities
        accelerations_by_id[obj_id] = accelerations

    with OSIChannelWriter.from_osi_channel_specification(output_channel_spec) as writer:
        for frame_index, src_msg in enumerate(input_messages):
            msg_copy = type(src_msg)()
            msg_copy.CopyFrom(src_msg)
            for mo in _get_moving_objects(msg_copy):
                obj_id = mo.id.value
                vx, vy, vz = velocities_by_id[obj_id][frame_index]
                ax, ay, az = accelerations_by_id[obj_id][frame_index]
                mo.base.velocity.x = vx
                mo.base.velocity.y = vy
                mo.base.velocity.z = vz
                mo.base.acceleration.x = ax
                mo.base.acceleration.y = ay
                mo.base.acceleration.z = az
            writer.write(msg_copy)

        return writer.get_channel_specification()
