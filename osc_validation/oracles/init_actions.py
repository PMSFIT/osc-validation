from dataclasses import dataclass
from pathlib import Path

from osi_utilities import ChannelSpecification

from osc_validation.generation.init_actions import (
    InitActionActor,
    InitActionsXoscRequest,
    build_init_actions_xosc,
)
from osc_validation.reference import (
    InitActionReferenceActor,
    InitActionReferenceRequest,
    build_init_actions_reference_trace,
)


@dataclass(frozen=True)
class InitActionOracleActor:
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


@dataclass(frozen=True)
class InitActionCaseSpec:
    output_xosc_path: Path
    output_reference_channel_spec: ChannelSpecification
    actors: list[InitActionOracleActor]
    duration_s: float
    sample_period_s: float
    road_network_path: Path | None = None
    host_vehicle_id: int | None = None


@dataclass(frozen=True)
class InitActionCaseResult:
    xosc_path: Path
    reference_channel_spec: ChannelSpecification


def _to_generation_actor(actor: InitActionOracleActor) -> InitActionActor:
    return InitActionActor(
        entity_ref=actor.entity_ref,
        object_id=actor.object_id,
        x=actor.x,
        y=actor.y,
        z=actor.z,
        yaw=actor.yaw,
        pitch=actor.pitch,
        roll=actor.roll,
        speed_mps=actor.speed_mps,
        length=actor.length,
        width=actor.width,
        height=actor.height,
    )


def _to_reference_actor(actor: InitActionOracleActor) -> InitActionReferenceActor:
    return InitActionReferenceActor(
        object_id=actor.object_id,
        x=actor.x,
        y=actor.y,
        z=actor.z,
        yaw=actor.yaw,
        pitch=actor.pitch,
        roll=actor.roll,
        speed_mps=actor.speed_mps,
        length=actor.length,
        width=actor.width,
        height=actor.height,
    )


def _build_init_action_case(spec: InitActionCaseSpec) -> InitActionCaseResult:
    if not spec.actors:
        raise ValueError("At least one actor is required.")

    xosc_result = build_init_actions_xosc(
        InitActionsXoscRequest(
            output_xosc_path=spec.output_xosc_path,
            actors=[_to_generation_actor(actor) for actor in spec.actors],
            stop_time_s=spec.duration_s,
            road_network_path=spec.road_network_path,
        )
    )
    reference_channel_spec = build_init_actions_reference_trace(
        InitActionReferenceRequest(
            output_channel_spec=spec.output_reference_channel_spec,
            actors=[_to_reference_actor(actor) for actor in spec.actors],
            duration_s=spec.duration_s,
            sample_period_s=spec.sample_period_s,
            host_vehicle_id=(
                spec.host_vehicle_id
                if spec.host_vehicle_id is not None
                else spec.actors[0].object_id
            ),
        )
    )
    return InitActionCaseResult(
        xosc_path=xosc_result.xosc_path,
        reference_channel_spec=reference_channel_spec,
    )


def build_init_teleport_action_case(spec: InitActionCaseSpec) -> InitActionCaseResult:
    actors = [
        InitActionOracleActor(
            entity_ref=actor.entity_ref,
            object_id=actor.object_id,
            x=actor.x,
            y=actor.y,
            z=actor.z,
            yaw=actor.yaw,
            pitch=actor.pitch,
            roll=actor.roll,
            speed_mps=None,
            length=actor.length,
            width=actor.width,
            height=actor.height,
        )
        for actor in spec.actors
    ]
    return _build_init_action_case(
        InitActionCaseSpec(
            output_xosc_path=spec.output_xosc_path,
            output_reference_channel_spec=spec.output_reference_channel_spec,
            actors=actors,
            duration_s=spec.duration_s,
            sample_period_s=spec.sample_period_s,
            road_network_path=spec.road_network_path,
            host_vehicle_id=spec.host_vehicle_id,
        )
    )


def build_init_speed_action_case(spec: InitActionCaseSpec) -> InitActionCaseResult:
    if not any(actor.speed_mps is not None for actor in spec.actors):
        raise ValueError("At least one actor must define speed_mps for a speed case.")
    return _build_init_action_case(spec)
