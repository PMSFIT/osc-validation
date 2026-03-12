import subprocess
from pathlib import Path
from typing import Collection

from osi_utilities import ChannelSpecification


def validate_output_spec(
    spec: ChannelSpecification, allowed_message_types: Collection[str]
) -> None:
    if spec.message_type is not None and spec.message_type not in allowed_message_types:
        raise ValueError(f"OSI message type is not allowed: {spec.message_type}")


def single_channel_temp_spec(
    output_spec: ChannelSpecification, name_suffix: str, message_type: str
) -> ChannelSpecification:
    suffixes = "".join(output_spec.path.suffixes)
    base_name = (
        output_spec.path.name.removesuffix(suffixes)
        if suffixes
        else output_spec.path.name
    )
    return ChannelSpecification(
        path=output_spec.path.with_name(f"{base_name}{name_suffix}.osi"),
        message_type=message_type,
        topic=output_spec.topic,
        metadata=dict(output_spec.metadata),
    )


def rename_trace(
    source_spec: ChannelSpecification, destination_path: Path
) -> ChannelSpecification:
    if not source_spec.path.exists():
        raise FileNotFoundError(
            f"Cannot rename: file does not exist at {source_spec.path}"
        )
    source_spec.path.rename(destination_path)
    return ChannelSpecification(
        path=destination_path,
        message_type=source_spec.message_type,
        topic=source_spec.topic,
        metadata=dict(source_spec.metadata),
    )


def get_tool_version(tool_path: Path) -> list[str]:
    cmd = [str(tool_path), "--version"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stdout = (res.stdout or "").strip()
    text_out = stdout if stdout else "unknown version"
    return [line.strip() for line in text_out.splitlines() if line.strip()]
