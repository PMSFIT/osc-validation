"""Coordinate scenario and reference init-pose transforms."""

from pathlib import Path
from osi_utilities import ChannelSpecification
from .models import (
    InitPoseTransformSpec,
    InitPoseTransformRequest,
    InitPoseTransformResult,
)
from .generation import (
    apply_init_pose_overrides_to_xosc,
    build_init_pose_overrides_from_trajectory_start,
)
from .reference import build_init_pose_overridden_reference_trace


def apply_init_pose_from_trajectory_start_transform(
    source_xosc_path: Path,
    source_reference_channel_spec: ChannelSpecification,
    output_xosc_path: Path,
    output_reference_channel_spec: ChannelSpecification,
    entity_refs: list[str] | None = None,
) -> InitPoseTransformResult:
    overrides = build_init_pose_overrides_from_trajectory_start(
        source_xosc_path=source_xosc_path,
        input_channel_spec=source_reference_channel_spec,
        entity_refs=entity_refs,
    )
    return apply_init_pose_transform(
        InitPoseTransformRequest(
            source_xosc_path=source_xosc_path,
            source_reference_channel_spec=source_reference_channel_spec,
            output_xosc_path=output_xosc_path,
            output_reference_channel_spec=output_reference_channel_spec,
            spec=InitPoseTransformSpec(overrides=overrides),
        )
    )


def apply_init_pose_transform(
    request: InitPoseTransformRequest,
) -> InitPoseTransformResult:
    xosc_path = apply_init_pose_overrides_to_xosc(
        source_xosc_path=request.source_xosc_path,
        output_xosc_path=request.output_xosc_path,
        overrides=request.spec.overrides,
    )
    reference_channel_spec = build_init_pose_overridden_reference_trace(
        input_channel_spec=request.source_reference_channel_spec,
        output_channel_spec=request.output_reference_channel_spec,
        overrides=request.spec.overrides,
    )
    return InitPoseTransformResult(
        xosc_path=xosc_path,
        reference_channel_spec=reference_channel_spec,
    )
