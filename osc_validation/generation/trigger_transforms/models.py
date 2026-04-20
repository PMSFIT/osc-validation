from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Union

from osi_utilities import ChannelSpecification
from ..init_transforms.models import InitPoseOverride


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
    condition_delay_s: float = 0.0
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
    condition_delay_s: float = 0.0
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
    """
    Request for applying a trigger transform to matching XOSC and OSI outputs.

    Init pose fields are optional pre-pass controls:
    - `init_pose_policy="keep"` leaves XOSC init poses unchanged and ignores
      `init_pose_overrides`, `init_pose_entity_refs`, and
      `init_pose_close_threshold_m`.
    - `init_pose_policy="from_trajectory_start"` builds init pose overrides
      from each selected entity's first trajectory point. `init_pose_entity_refs`
      can restrict this to specific OpenSCENARIO entity refs; `None` means all
      init entities.
    - `init_pose_policy="close_to_trajectory_start"` builds init pose overrides
      near each selected entity's first trajectory point using
      `init_pose_close_threshold_m`; `None` means 0.5 m.
    - `init_pose_policy="explicit_overrides"` applies `init_pose_overrides`
      directly and requires at least one override.

    Implementation detail: `apply_trigger_transform` resolves the effective
    XOSC init poses into pre-trigger hold overrides, then forwards those to
    concrete trigger transformers through `init_pose_overrides` with
    `init_pose_policy="keep"`. The source reference trace is not pre-edited;
    trigger-specific trace builders use the overrides only for pre-trigger hold
    frames and keep the original trace frames as trajectory source data.
    """

    source_xosc_path: Path
    source_reference_channel_spec: ChannelSpecification
    output_xosc_path: Path
    output_reference_channel_spec: ChannelSpecification
    spec: TriggerTransformSpec
    init_pose_policy: Literal[
        "keep",
        "from_trajectory_start",
        "close_to_trajectory_start",
        "explicit_overrides",
    ] = "keep"
    init_pose_overrides: list[InitPoseOverride] | None = None
    init_pose_entity_refs: list[str] | None = None
    init_pose_close_threshold_m: float | None = None


@dataclass(frozen=True)
class TriggerTransformResult:
    xosc_path: Path
    reference_channel_spec: ChannelSpecification
