import math
from dataclasses import dataclass

from osi3 import osi_sensorview_pb2, osi_version_pb2
from osi_utilities import ChannelSpecification, open_channel_writer


@dataclass(frozen=True)
class InitActionReferenceActor:
    object_id: int
    x: float
    y: float
    z: float
    yaw: float
    pitch: float = 0.0
    roll: float = 0.0
    speed_mps: float | None = None
    length: float = 4.5
    width: float = 1.8
    height: float = 1.5


@dataclass(frozen=True)
class InitActionReferenceRequest:
    output_channel_spec: ChannelSpecification
    actors: list[InitActionReferenceActor]
    duration_s: float
    sample_period_s: float
    host_vehicle_id: int | None = None


def _get_osi_version():
    return osi_version_pb2.DESCRIPTOR.GetOptions().Extensions[
        osi_version_pb2.current_interface_version
    ]


def _set_timestamp(message, timestamp_s: float) -> None:
    seconds = int(timestamp_s)
    nanos = int(round((timestamp_s - seconds) * 1e9))
    if nanos == 1_000_000_000:
        seconds += 1
        nanos = 0
    message.timestamp.seconds = seconds
    message.timestamp.nanos = nanos


def _build_sensor_view(
    actors: list[InitActionReferenceActor],
    timestamp_s: float,
    host_vehicle_id: int | None,
) -> osi_sensorview_pb2.SensorView:
    sensor_view = osi_sensorview_pb2.SensorView()
    sensor_view.version.CopyFrom(_get_osi_version())
    _set_timestamp(sensor_view, timestamp_s)
    sensor_view.global_ground_truth.version.CopyFrom(_get_osi_version())
    _set_timestamp(sensor_view.global_ground_truth, timestamp_s)
    sensor_view.sensor_id.value = 42

    if host_vehicle_id is not None:
        sensor_view.host_vehicle_id.value = host_vehicle_id
        sensor_view.global_ground_truth.host_vehicle_id.value = host_vehicle_id

    for actor in actors:
        speed = actor.speed_mps if actor.speed_mps is not None else 0.0
        vx = math.cos(actor.yaw) * speed
        vy = math.sin(actor.yaw) * speed
        center_dx = math.cos(actor.yaw) * actor.length * 0.5
        center_dy = math.sin(actor.yaw) * actor.length * 0.5

        moving_object = sensor_view.global_ground_truth.moving_object.add()
        moving_object.id.value = actor.object_id
        moving_object.base.position.x = actor.x + center_dx + vx * timestamp_s
        moving_object.base.position.y = actor.y + center_dy + vy * timestamp_s
        moving_object.base.position.z = actor.z + actor.height * 0.5
        moving_object.base.orientation.yaw = actor.yaw
        moving_object.base.orientation.pitch = actor.pitch
        moving_object.base.orientation.roll = actor.roll
        moving_object.base.dimension.length = actor.length
        moving_object.base.dimension.width = actor.width
        moving_object.base.dimension.height = actor.height
        moving_object.base.velocity.x = vx
        moving_object.base.velocity.y = vy
        moving_object.base.velocity.z = 0.0
        moving_object.base.acceleration.x = 0.0
        moving_object.base.acceleration.y = 0.0
        moving_object.base.acceleration.z = 0.0
        moving_object.type = 2
        moving_object.vehicle_classification.type = 4

    return sensor_view


def build_init_actions_reference_trace(
    request: InitActionReferenceRequest,
) -> ChannelSpecification:
    if not request.actors:
        raise ValueError("At least one actor is required.")
    if request.duration_s <= 0.0:
        raise ValueError("duration_s must be > 0.0.")
    if request.sample_period_s <= 0.0:
        raise ValueError("sample_period_s must be > 0.0.")

    frame_count = int(round(request.duration_s / request.sample_period_s)) + 1
    with open_channel_writer(request.output_channel_spec) as writer:
        for frame_index in range(frame_count):
            timestamp_s = frame_index * request.sample_period_s
            writer.write_message(
                _build_sensor_view(
                    actors=request.actors,
                    timestamp_s=timestamp_s,
                    host_vehicle_id=request.host_vehicle_id,
                )
            )
        return writer.get_channel_specification()
