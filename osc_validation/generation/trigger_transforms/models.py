from dataclasses import dataclass
from pathlib import Path
from typing import Union

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification


@dataclass(frozen=True)
class SimulationTimeTriggerSpec:
    trigger_delay: float
    trigger_rule: str = "greaterThan"
    activation_frame_offset: int = 0


@dataclass(frozen=True)
class TraveledDistanceTriggerSpec:
    trigger_entity_ref: str
    target_event_name: str
    condition_name: str
    trigger_distance_m: float
    trigger_object_id: int
    triggered_object_id: int
    trigger_rule: str = "greaterThan"
    activation_frame_offset: int = 1


@dataclass(frozen=True)
class SpeedTriggerSpec:
    trigger_entity_ref: str
    target_event_name: str
    condition_name: str
    trigger_speed_mps: float
    trigger_object_id: int
    triggered_object_id: int
    trigger_rule: str = "greaterThan"
    activation_frame_offset: int = 1


@dataclass(frozen=True)
class TimeToCollisionPositionTriggerSpec:
    trigger_entity_ref: str
    target_event_name: str
    condition_name: str
    trigger_ttc_s: float
    trigger_object_id: int
    triggered_object_id: int
    target_position_x: float
    target_position_y: float
    target_position_z: float = 0.0
    trigger_rule: str = "lessOrEqual"
    activation_frame_offset: int = 1


@dataclass(frozen=True)
class DistancePositionTriggerSpec:
    trigger_entity_ref: str
    target_event_name: str
    condition_name: str
    trigger_distance_m: float
    trigger_object_id: int
    triggered_object_id: int
    target_position_x: float
    target_position_y: float
    target_position_z: float = 0.0
    relative_distance_type: str = "euclidianDistance"
    trigger_rule: str = "lessOrEqual"
    activation_frame_offset: int = 1


TriggerTransformSpec = Union[
    SimulationTimeTriggerSpec,
    TraveledDistanceTriggerSpec,
    SpeedTriggerSpec,
    TimeToCollisionPositionTriggerSpec,
    DistancePositionTriggerSpec,
]


@dataclass(frozen=True)
class TriggerTransformRequest:
    source_xosc_path: Path
    source_reference_channel_spec: OSIChannelSpecification
    output_xosc_path: Path
    output_reference_channel_spec: OSIChannelSpecification
    spec: TriggerTransformSpec


@dataclass(frozen=True)
class TriggerTransformResult:
    xosc_path: Path
    reference_channel_spec: OSIChannelSpecification
