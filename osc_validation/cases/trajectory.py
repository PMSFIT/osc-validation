"""Shared trajectory case data, independent of XML and reference algorithms."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrajectoryInterpolationVertex:
    time_s: float
    x: float
    y: float
    z: float
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0


@dataclass(frozen=True)
class TrajectoryInterpolationActor:
    entity_ref: str
    object_id: int
    vertices: list[TrajectoryInterpolationVertex]
    bounding_box_center_x: float = 0.0
    bounding_box_center_y: float = 0.0
    bounding_box_center_z: float = 0.0
    length: float = 4.5
    width: float = 1.8
    height: float = 1.5
    vehicle_category: str = "car"
