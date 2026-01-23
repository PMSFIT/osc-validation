from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
from typing import Optional
from enum import Enum
import re


class TraceFileFormat(Enum):
    SINGLE_CHANNEL = 1
    MULTI_CHANNEL = 2


class FormatMapper:
    def __init__(self):
        self.ext_to_format = {
            ".osi": TraceFileFormat.SINGLE_CHANNEL,
            ".xz": TraceFileFormat.SINGLE_CHANNEL,
            ".lzma": TraceFileFormat.SINGLE_CHANNEL,
            ".mcap": TraceFileFormat.MULTI_CHANNEL,
        }
        self.format_to_ext = {}
        for ext, fmt in self.ext_to_format.items():
            if fmt not in self.format_to_ext:
                self.format_to_ext[fmt] = ext

    def get_format(self, extension: str) -> TraceFileFormat:
        return self.ext_to_format[extension.lower()]

    def get_extension(self, file_format: TraceFileFormat) -> str:
        return self.format_to_ext[file_format]


MESSAGE_TYPE_MAP = {
    "sv": "SensorView",
    "svc": "SensorViewConfiguration",
    "gt": "GroundTruth",
    "hvd": "HostVehicleData",
    "sd": "SensorData",
    "tc": "TrafficCommand",
    "tcu": "TrafficCommandUpdate",
    "tu": "TrafficUpdate",
    "mr": "MotionRequest",
    "su": "StreamingUpdate",
}


def parse_osi_trace_filename(filename: str) -> dict:
    """
    Parses an OSI trace filename according to the 2.2.6.2 OSI naming convention.

    Format:
        <timestamp>_<type>_<osi-version>_<protobuf-version>_<number-of-frames>_<custom-trace-name>.osi

    Returns:
        A dict containing:
            - timestamp (datetime)
            - message_type (str)
            - osi_version (str)
            - protobuf_version (str)
            - number_of_frames (int)
            - custom_trace_name (str)
        Or None if parsing fails.
    """
    pattern = re.compile(
        r"""
        ^
        (?P<timestamp>\d{8}T\d{6}Z)
        _
        (?P<message_type>sv|svc|gt|hvd|sd|tc|tcu|tu|mr|su)
        _
        (?P<osi_version>[^_]+)
        _
        (?P<protobuf_version>[^_]+)
        _
        (?P<number_of_frames>\d+)
        _
        (?P<custom_trace_name>[^.]+)
        \.osi$
        """,
        re.VERBOSE,
    )

    match = pattern.match(filename)
    if not match:
        return {}

    try:
        timestamp = datetime.strptime(match.group("timestamp"), "%Y%m%dT%H%M%SZ")

        return {
            "timestamp": timestamp,
            "message_type": MESSAGE_TYPE_MAP.get(match.group("message_type")),
            "osi_version": match.group("osi_version"),
            "protobuf_version": match.group("protobuf_version"),
            "number_of_frames": int(match.group("number_of_frames")),
            "custom_trace_name": match.group("custom_trace_name"),
        }
    except Exception as e:
        logging.warning(f"Error while parsing filename {filename}: {e}")
        return {}


@dataclass
class OSIChannelSpecification:
    """
    Specification for an OSI channel.
    Args:
        path (Path): The path to the file containing the OSI channel data.
        message_type (str, optional): The OSI message type expected in the channel.
            If None, a trace file reader will rely on the file's specification if available.
        topic (str, optional): The topic name of the channel.
            If None, first or only channel found in the file is used for reading.
            If the source file is a single channel file, the topic parameter is ignored.
        metadata (dict, optional): Additional metadata for the OSI channel.
            If None, the metadata defaults to an empty dictionary.
            Single-channel files do not support storing metadata.
    """

    path: Path
    message_type: Optional[str] = None
    topic: Optional[str] = None
    metadata: Optional[dict] = field(default_factory=dict)

    _format_mapper: FormatMapper = field(
        default_factory=FormatMapper, init=False, repr=False, compare=False
    )

    @property
    def trace_file_format(self) -> TraceFileFormat:
        return self._format_mapper.get_format(self.path.suffix)

    def try_autodetect_message_type(self) -> bool:
        """
        Attempts to detect and set the message type from the file name or content.
        Returns:
            bool: True if detection was successful and sets self.message_type.
                  False if detection failed and leaves self.message_type unchanged.
        """
        if self.message_type is not None:
            return True

        format = self.trace_file_format
        detected_type = None
        if format == TraceFileFormat.MULTI_CHANNEL:
            from osc_validation.utils.osi_reader import OSIChannelReader

            with OSIChannelReader.from_osi_channel_specification(
                self
            ) as channel_reader:
                detected_type = channel_reader.get_message_type()
        elif format == TraceFileFormat.SINGLE_CHANNEL:
            detected_type = parse_osi_trace_filename(self.path.name).get(
                "message_type", None
            )

        if detected_type is not None:
            self.message_type = detected_type
            return True
        return False

    def autofill_topic(self) -> None:
        """
        Sets the topic to the file name without the extension if not already set.
        """
        if self.topic is None:
            self.topic = self.path.stem

    def exists(self) -> bool:
        """
        Checks if the file specified by the path exists.
        Returns:
            bool: True if the file exists, False otherwise.
        """
        return self.path.exists() and self.path.is_file()

    def rename_to(self, new_path: Path) -> "OSIChannelSpecification":
        """
        Renames the OSI channel's source file to a new path.
        Args:
            new_path (Path): The new path to rename the file to.
        Returns:
            OSIChannelSpecification: A new instance with the updated path.
        Raises:
            FileNotFoundError: If the file does not exist at the current path.
            OSError: If the rename operation fails.
        """
        if not self.exists():
            raise FileNotFoundError(
                f"Cannot rename: file does not exist at {self.path}"
            )
        try:
            self.path.rename(new_path)
        except OSError as e:
            raise OSError(f"Failed to rename '{self.path}' to '{new_path}': {e}") from e
        return OSIChannelSpecification(
            path=new_path,
            message_type=self.message_type,
            topic=self.topic,
            metadata=self.metadata,
        )

    def with_name(self, new_name: str) -> "OSIChannelSpecification":
        new_path = self.path.with_name(new_name)
        return OSIChannelSpecification(
            path=new_path,
            message_type=self.message_type,
            topic=self.topic,
            metadata=self.metadata,
        )

    def with_name_suffix(self, suffix: str) -> "OSIChannelSpecification":
        new_name = self.path.stem + suffix + self.path.suffix
        new_path = self.path.with_name(new_name)
        return OSIChannelSpecification(
            path=new_path,
            message_type=self.message_type,
            topic=self.topic,
            metadata=self.metadata,
        )

    def with_trace_file_format(
        self, trace_file_format: TraceFileFormat
    ) -> "OSIChannelSpecification":
        return OSIChannelSpecification(
            path=self.path.with_suffix(FormatMapper().get_extension(trace_file_format)),
            message_type=self.message_type,
            topic=self.topic,
            metadata=self.metadata,
        )

    def with_message_type(self, message_type: str) -> "OSIChannelSpecification":
        return OSIChannelSpecification(
            path=self.path,
            message_type=message_type,
            topic=self.topic,
            metadata=self.metadata,
        )

    def with_topic(self, topic: str) -> "OSIChannelSpecification":
        return OSIChannelSpecification(
            path=self.path,
            message_type=self.message_type,
            topic=topic,
            metadata=self.metadata,
        )

    def __str__(self):
        return f"OSIChannelSpecification(path={self.path}, message_type={self.message_type}, topic={self.topic}, metadata={self.metadata})"


class InvalidSpecificationError(Exception):
    pass


class OSIChannelSpecValidator:
    def __init__(
        self,
        allowed_message_types=None,
        require_message_type=False,
        require_topic=False,
        require_metadata_keys=None,
    ):
        self.allowed_message_types = allowed_message_types
        self.require_message_type = require_message_type
        self.require_topic = require_topic
        self.require_metadata_keys = require_metadata_keys or []

    def __call__(self, spec: OSIChannelSpecification):
        if (
            self.allowed_message_types
            and spec.message_type not in self.allowed_message_types
            and spec.message_type is not None
        ):
            raise InvalidSpecificationError(
                f"OSI message type is not allowed: {spec.message_type}"
            )
        if self.require_message_type and not spec.message_type:
            raise InvalidSpecificationError("OSI message type is required.")
        if self.require_topic and not spec.topic:
            raise InvalidSpecificationError("Topic is required.")
        for key in self.require_metadata_keys:
            if key not in spec.metadata:
                raise InvalidSpecificationError(f"Missing required metadata key: {key}")
