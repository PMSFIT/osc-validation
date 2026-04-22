from dataclasses import dataclass
from pathlib import Path

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification


@dataclass(frozen=True)
class InitPoseOverride:
    entity_ref: str
    object_id: int
    x: float
    y: float
    z: float
    yaw: float
    pitch: float = 0.0
    roll: float = 0.0


@dataclass(frozen=True)
class InitPoseTransformSpec:
    overrides: list[InitPoseOverride]


@dataclass(frozen=True)
class InitPoseTransformRequest:
    source_xosc_path: Path
    source_reference_channel_spec: OSIChannelSpecification
    output_xosc_path: Path
    output_reference_channel_spec: OSIChannelSpecification
    spec: InitPoseTransformSpec


@dataclass(frozen=True)
class InitPoseTransformResult:
    xosc_path: Path
    reference_channel_spec: OSIChannelSpecification
