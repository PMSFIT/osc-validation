from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InitActionActor:
    entity_ref: str
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
    vehicle_category: str = "car"


@dataclass(frozen=True)
class InitActionsXoscRequest:
    output_xosc_path: Path
    actors: list[InitActionActor]
    stop_time_s: float
    road_network_path: Path | None = None
    include_teleport_actions: bool = True


@dataclass(frozen=True)
class InitActionsXoscResult:
    xosc_path: Path
