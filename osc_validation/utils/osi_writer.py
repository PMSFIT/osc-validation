"""OSI channel writer compatibility wrapper over the current SDK writers.

Keeps LZMA compression support (.osi.xz) locally since the SDK does not
handle compressed binary traces.
"""

from __future__ import annotations

import logging
import lzma
from pathlib import Path
import struct

import google.protobuf
from osi_utilities.tracefile._types import ChannelSpecification
from osi_utilities.tracefile.binary_writer import BinaryTraceFileWriter
from osi_utilities.tracefile.mcap_writer import (
    MCAPTraceFileWriter,
    prepare_required_file_metadata,
)

logger = logging.getLogger(__name__)

OSI_VERSION_METADATA_KEY = "net.asam.osi.trace.channel.osi_version"
PROTOBUF_VERSION_METADATA_KEY = "net.asam.osi.trace.channel.protobuf_version"


def _normalize_specification(
    channel_spec: ChannelSpecification,
) -> ChannelSpecification:
    return ChannelSpecification(
        path=Path(channel_spec.path),
        message_type=channel_spec.message_type,
        topic=channel_spec.topic,
        metadata=dict(getattr(channel_spec, "metadata", {}) or {}),
    )


def _single_channel_topic_name(path: Path) -> str:
    if "".join(path.suffixes).lower().endswith(".osi.xz"):
        return Path(path.stem).stem
    return path.stem


def _message_version_string(message) -> str | None:
    if hasattr(message, "version"):
        return (
            f"{message.version.version_major}."
            f"{message.version.version_minor}."
            f"{message.version.version_patch}"
        )
    return None


class _LZMABinaryWriter:
    """Compressed binary writer for .osi.xz files (SDK gap)."""

    def __init__(self, path: Path):
        if "".join(path.suffixes).lower() != ".osi.xz":
            raise ValueError(
                f"Invalid file path: '{path}'. Must be '.osi.xz' for compressed binary."
            )
        self._path = path
        self._file = open(path, "wb")
        self._written_count = 0
        self._size = 0
        self._size_uncompressed = 0

    def write_message(self, message, topic="") -> bool:
        buf = message.SerializeToString()
        len_uncompressed = len(buf)
        buf = lzma.compress(buf)
        self._file.write(struct.pack("<L", len(buf)))
        self._file.write(buf)
        self._written_count += 1
        self._size += len(buf)
        self._size_uncompressed += len_uncompressed
        return True

    def close(self) -> None:
        ratio = (
            str(round(self._size_uncompressed / self._size, 2))
            if self._size > 0
            else "N/A"
        )
        logging.info(
            "Wrote %d messages to '%s' (%sMB; compression ratio: %s).",
            self._written_count,
            self._path,
            round(self._size / 1024 / 1024, 2),
            ratio,
        )
        self._file.close()

    @property
    def written_count(self) -> int:
        return self._written_count


class OSIChannelWriter:
    """Project-specific writer facade with the historic ChannelWriter API."""

    def __init__(self, writer, channel_spec: ChannelSpecification) -> None:
        self._writer = writer
        self._channel_spec = channel_spec
        self._channel_metadata = dict(channel_spec.metadata)
        self._channel_registered = False

    @classmethod
    def from_specification(
        cls, channel_spec: ChannelSpecification
    ) -> "OSIChannelWriter":
        spec = _normalize_specification(channel_spec)
        suffixes = "".join(spec.path.suffixes).lower()

        if suffixes == ".osi.xz":
            resolved_spec = ChannelSpecification(
                path=spec.path,
                message_type=spec.message_type,
                topic=spec.topic or _single_channel_topic_name(spec.path),
                metadata=dict(spec.metadata),
            )
            return cls(_LZMABinaryWriter(spec.path), resolved_spec)

        if spec.path.suffix.lower() == ".osi":
            writer = BinaryTraceFileWriter()
            if not writer.open(spec.path):
                raise ValueError(
                    f"Failed to open binary OSI writer for '{spec.path}'. Check extension and path."
                )
            resolved_spec = ChannelSpecification(
                path=spec.path,
                message_type=spec.message_type,
                topic=spec.topic or _single_channel_topic_name(spec.path),
                metadata=dict(spec.metadata),
            )
            return cls(writer, resolved_spec)

        if spec.path.suffix.lower() == ".mcap":
            if spec.path.exists():
                raise ValueError(f"Output file '{spec.path}' already exists.")
            if spec.message_type is None:
                raise ValueError("OSI message type is required for MCAP writing.")
            writer = MCAPTraceFileWriter()
            if not writer.open(spec.path, prepare_required_file_metadata()):
                raise ValueError(f"Failed to open MCAP writer for '{spec.path}'.")
            resolved_spec = ChannelSpecification(
                path=spec.path,
                message_type=spec.message_type,
                topic=spec.topic or spec.path.stem,
                metadata=dict(spec.metadata),
            )
            return cls(writer, resolved_spec)

        raise ValueError(
            f"Unsupported trace file extension for writing: '{spec.path.suffix}'."
        )

    @classmethod
    def from_osi_channel_specification(
        cls, osi_channel_spec: ChannelSpecification
    ) -> "OSIChannelWriter":
        return cls.from_specification(osi_channel_spec)

    def __enter__(self) -> "OSIChannelWriter":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def _ensure_message_type(self, message) -> None:
        actual_message_type = message.DESCRIPTOR.name
        if self._channel_spec.message_type is None:
            self._channel_spec = self._channel_spec.with_message_type(
                actual_message_type
            )
            return
        if self._channel_spec.message_type != actual_message_type:
            raise ValueError(
                f"Configured message type '{self._channel_spec.message_type}' does not "
                f"match protobuf message type '{actual_message_type}'."
            )

    def _ensure_mcap_channel(self, message) -> None:
        if (
            not isinstance(self._writer, MCAPTraceFileWriter)
            or self._channel_registered
        ):
            return

        message_version = _message_version_string(message)
        if message_version is not None:
            configured_version = self._channel_metadata.get(OSI_VERSION_METADATA_KEY)
            if configured_version is None:
                logger.info(
                    "Auto-filling channel OSI version metadata with %s.",
                    message_version,
                )
                self._channel_metadata[OSI_VERSION_METADATA_KEY] = message_version
            elif configured_version != message_version:
                raise ValueError(
                    f"Configured OSI version '{configured_version}' does not match "
                    f"message version '{message_version}'."
                )

        configured_pb_version = self._channel_metadata.get(
            PROTOBUF_VERSION_METADATA_KEY
        )
        if configured_pb_version is None:
            self._channel_metadata[PROTOBUF_VERSION_METADATA_KEY] = (
                google.protobuf.__version__
            )
        elif configured_pb_version != google.protobuf.__version__:
            logger.warning(
                "Configured protobuf version '%s' does not match installed protobuf "
                "version '%s'.",
                configured_pb_version,
                google.protobuf.__version__,
            )

        self._writer.add_channel(
            self._channel_spec.topic,
            type(message),
            self._channel_metadata,
        )
        self._channel_registered = True

    def write(self, message) -> bool:
        self._ensure_message_type(message)
        self._ensure_mcap_channel(message)
        success = self._writer.write_message(message, self._channel_spec.topic or "")
        if not success:
            raise RuntimeError(
                f"Failed to write message to '{self._channel_spec.path}'."
            )
        return True

    def write_message(self, message, topic="") -> bool:
        return self.write(message)

    @property
    def written_count(self) -> int:
        return getattr(self._writer, "written_count", 0)

    def get_channel_metadata(self) -> dict:
        return dict(self._channel_metadata)

    def get_channel_specification(self) -> ChannelSpecification:
        return ChannelSpecification(
            path=self._channel_spec.path,
            message_type=self._channel_spec.message_type,
            topic=self._channel_spec.topic,
            metadata=dict(self._channel_metadata),
        )

    def close(self) -> None:
        self._writer.close()
