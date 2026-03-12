"""OSI channel reader compatibility wrapper over the current SDK readers."""

from __future__ import annotations

import logging
import lzma
from pathlib import Path
import struct
from typing import IO

from osi_utilities.tracefile._config import (
    BINARY_MESSAGE_LENGTH_PREFIX_SIZE,
    MAX_EXPECTED_MESSAGE_SIZE,
)
from osi_utilities.tracefile._types import (
    ChannelSpecification,
    MESSAGE_TYPE_TO_CLASS_NAME,
    MessageType,
    ReadResult,
    TraceFileFormat,
    _get_message_class,
)
from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader
from osi_utilities.tracefile.reader import TraceFileReader, TraceFileReaderFactory
from osi_utilities.tracefile.timestamp import timestamp_to_seconds

logger = logging.getLogger(__name__)

_MESSAGE_NAME_TO_TYPE = {
    message_name: message_type
    for message_type, message_name in MESSAGE_TYPE_TO_CLASS_NAME.items()
}


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


def _is_lzma_binary_path(path: Path) -> bool:
    return "".join(path.suffixes).lower() == ".osi.xz"


def _message_type_enum(message_type_name: str) -> MessageType:
    try:
        return _MESSAGE_NAME_TO_TYPE[message_type_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported OSI message type: {message_type_name}") from exc


def _message_type_name(message_type: MessageType | None) -> str | None:
    if message_type is None:
        return None
    return MESSAGE_TYPE_TO_CLASS_NAME.get(message_type)


class _LZMABinaryReader(TraceFileReader):
    """Compressed binary reader for .osi.xz files written by the local wrapper."""

    def __init__(self, message_type: MessageType) -> None:
        self._message_type = message_type
        self._message_class: type | None = None
        self._file: IO[bytes] | None = None
        self._has_next = False

    def open(self, path: Path) -> bool:
        if not _is_lzma_binary_path(path):
            logger.error(
                "Compressed binary trace files must have .osi.xz extension, got '%s'",
                "".join(path.suffixes),
            )
            return False

        try:
            self._message_class = _get_message_class(self._message_type)
        except ValueError as exc:
            logger.error("Failed to get message class: %s", exc)
            return False

        try:
            self._file = open(path, "rb")  # noqa: SIM115
        except OSError as exc:
            logger.error("Failed to open compressed trace file '%s': %s", path, exc)
            return False

        self._has_next = self._peek_has_data()
        return True

    def read_message(self) -> ReadResult | None:
        if self._file is None or self._message_class is None:
            return None

        length_bytes = self._file.read(BINARY_MESSAGE_LENGTH_PREFIX_SIZE)
        if not length_bytes:
            self._has_next = False
            return None
        if len(length_bytes) < BINARY_MESSAGE_LENGTH_PREFIX_SIZE:
            raise RuntimeError(
                "Truncated length header in compressed binary trace file."
            )

        (msg_len,) = struct.unpack("<I", length_bytes)
        if msg_len > MAX_EXPECTED_MESSAGE_SIZE:
            raise RuntimeError(
                f"Compressed message size {msg_len} exceeds maximum expected size "
                f"{MAX_EXPECTED_MESSAGE_SIZE}."
            )

        compressed = self._file.read(msg_len)
        if len(compressed) < msg_len:
            raise RuntimeError(
                f"Truncated compressed message body: expected {msg_len} bytes, "
                f"got {len(compressed)}."
            )

        try:
            data = lzma.decompress(compressed)
        except lzma.LZMAError as exc:
            raise RuntimeError(
                f"Failed to decompress LZMA message ({msg_len} bytes): {exc}"
            ) from exc

        message = self._message_class()
        try:
            message.ParseFromString(data)
        except Exception as exc:  # protobuf parsing raises broad exceptions
            raise RuntimeError(
                f"Failed to deserialize protobuf message ({len(data)} bytes): {exc}"
            ) from exc

        self._has_next = self._peek_has_data()
        return ReadResult(message=message, message_type=self._message_type)

    def has_next(self) -> bool:
        return self._has_next

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        self._has_next = False

    def _peek_has_data(self) -> bool:
        if self._file is None:
            return False
        pos = self._file.tell()
        data = self._file.read(1)
        if data:
            self._file.seek(pos)
            return True
        return False


class OSIChannelReader:
    """Project-specific reader facade with the historic ChannelReader API."""

    def __init__(
        self,
        reader: TraceFileReader,
        channel_spec: ChannelSpecification,
    ) -> None:
        self._reader = reader
        self._channel_spec = channel_spec

    @classmethod
    def from_specification(
        cls, channel_spec: ChannelSpecification
    ) -> "OSIChannelReader":
        spec = _normalize_specification(channel_spec)
        suffixes = "".join(spec.path.suffixes).lower()
        if not spec.exists():
            raise FileNotFoundError(f"OSI trace file '{spec.path}' does not exist.")

        if spec.trace_file_format == TraceFileFormat.SINGLE_CHANNEL:
            if spec.message_type is None:
                raise ValueError(
                    "OSI message type must be specified for single-channel traces."
                )
            if suffixes == ".osi.xz":
                reader = _LZMABinaryReader(_message_type_enum(spec.message_type))
                if not reader.open(spec.path):
                    raise RuntimeError(
                        f"Failed to open compressed binary OSI reader for '{spec.path}'."
                    )
            else:
                reader = TraceFileReaderFactory.create_reader(
                    spec.path,
                    message_type=_message_type_enum(spec.message_type),
                )
            topic = spec.topic or _single_channel_topic_name(spec.path)
            resolved_spec = ChannelSpecification(
                path=spec.path,
                message_type=spec.message_type,
                topic=topic,
                metadata=dict(spec.metadata),
            )
            return cls(reader=reader, channel_spec=resolved_spec)

        reader = TraceFileReaderFactory.create_reader(spec.path)
        assert isinstance(reader, MCAPTraceFileReader)

        available_topics = reader.get_available_topics()
        if not available_topics:
            reader.close()
            raise ValueError(f"No topics found in MCAP file '{spec.path}'.")

        topic = spec.topic or available_topics[0]
        if topic not in available_topics:
            reader.close()
            raise ValueError(
                f"Topic '{topic}' not found in MCAP file '{spec.path}'. "
                f"Available topics: {available_topics}"
            )

        detected_message_type = _message_type_name(
            reader.get_message_type_for_topic(topic)
        )
        if spec.message_type is not None and spec.message_type != detected_message_type:
            reader.close()
            raise ValueError(
                f"Specified message type '{spec.message_type}' does not match "
                f"detected message type '{detected_message_type}'."
            )

        reader.set_topics([topic])
        resolved_spec = ChannelSpecification(
            path=spec.path,
            message_type=detected_message_type,
            topic=topic,
            metadata=dict(reader.get_channel_metadata(topic) or spec.metadata),
        )
        return cls(reader=reader, channel_spec=resolved_spec)

    @classmethod
    def from_osi_channel_specification(
        cls, osi_channel_spec: ChannelSpecification
    ) -> "OSIChannelReader":
        return cls.from_specification(osi_channel_spec)

    def __enter__(self) -> "OSIChannelReader":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def __iter__(self) -> "OSIChannelReader":
        return self

    def __next__(self):
        result = self._reader.read_message()
        if result is None:
            raise StopIteration
        return result.message

    def get_messages(self):
        return iter(self)

    def get_source_path(self) -> Path:
        return self._channel_spec.path

    def get_topic_name(self) -> str:
        return self._channel_spec.topic

    def get_message_type(self) -> str | None:
        return self._channel_spec.message_type

    def get_available_topics(self) -> list[str]:
        if isinstance(self._reader, MCAPTraceFileReader):
            return self._reader.get_available_topics()
        return [self.get_topic_name()]

    def get_file_metadata(self):
        if isinstance(self._reader, MCAPTraceFileReader):
            return self._reader.get_file_metadata()
        return {}

    def get_channel_metadata(self):
        if isinstance(self._reader, MCAPTraceFileReader):
            return self._reader.get_channel_metadata(self.get_topic_name()) or {}
        return {}

    def get_channel_specification(self) -> ChannelSpecification:
        return ChannelSpecification(
            path=self._channel_spec.path,
            message_type=self._channel_spec.message_type,
            topic=self._channel_spec.topic,
            metadata=dict(self.get_channel_metadata() or self._channel_spec.metadata),
        )

    def get_channel_info(self) -> dict:
        start = None
        stop = None
        total_steps = 0
        step_acc = 0.0
        prev_timestamp = None
        osi_version = None

        with type(self).from_specification(self.get_channel_specification()) as reader:
            for message in reader.get_messages():
                if hasattr(message, "version"):
                    osi_version = (
                        f"{message.version.version_major}."
                        f"{message.version.version_minor}."
                        f"{message.version.version_patch}"
                    )
                timestamp = timestamp_to_seconds(message)
                if start is None:
                    start = timestamp
                stop = timestamp
                if prev_timestamp is not None:
                    step_acc += timestamp - prev_timestamp
                prev_timestamp = timestamp
                total_steps += 1

        return {
            "start": start,
            "stop": stop,
            "step_size_avg": step_acc / (total_steps - 1) if total_steps > 1 else 0,
            "total_steps": total_steps,
            "osi_version": osi_version,
            "message_type": self.get_message_type(),
        }

    def print_summary(self) -> None:
        channel_info = self.get_channel_info()
        summary_lines = [
            ("File path", self.get_source_path()),
            ("OSI version", channel_info["osi_version"]),
            ("OSI trace type", channel_info["message_type"]),
            ("Start timestamp", f"{channel_info['start']}s"),
            ("Stop timestamp", f"{channel_info['stop']}s"),
            ("Average Step Size", f"{round(channel_info['step_size_avg'], 9)}s"),
            ("Total Steps", channel_info["total_steps"]),
        ]

        max_label_len = max(len(label) for label, _ in summary_lines)
        for label, value in summary_lines:
            print(f"{label + ':':<{max_label_len + 2}} {value}")

    def close(self) -> None:
        self._reader.close()
