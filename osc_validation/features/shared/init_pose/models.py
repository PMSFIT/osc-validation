from dataclasses import dataclass
from pathlib import Path

from osi_utilities import ChannelSpecification


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
    source_reference_channel_spec: ChannelSpecification
    output_xosc_path: Path
    output_reference_channel_spec: ChannelSpecification
    spec: InitPoseTransformSpec


@dataclass(frozen=True)
class InitPoseTransformResult:
    xosc_path: Path
    reference_channel_spec: ChannelSpecification


def _validate_overrides(overrides: list[InitPoseOverride]) -> None:
    if not overrides:
        raise ValueError("Init pose transform requires at least one override.")

    object_ids = [override.object_id for override in overrides]
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("Init pose overrides must use unique object_id values.")

    entity_refs = [override.entity_ref for override in overrides]
    if len(entity_refs) != len(set(entity_refs)):
        raise ValueError("Init pose overrides must use unique entity_ref values.")
