from dataclasses import dataclass
from pathlib import Path
from typing import Literal


SequencingLevel = Literal["event", "maneuver", "maneuver_group", "act", "story"]


@dataclass(frozen=True)
class TrajectorySequencingTransformSpec:
    entity_ref: str
    segment_count: int
    sequencing_level: SequencingLevel


@dataclass(frozen=True)
class TrajectorySequencingTransformRequest:
    source_xosc_path: Path
    output_xosc_path: Path
    spec: TrajectorySequencingTransformSpec


@dataclass(frozen=True)
class TrajectorySequencingTransformResult:
    xosc_path: Path
