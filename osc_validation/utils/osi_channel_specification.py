from dataclasses import dataclass
from pathlib import Path

from osi_utilities.tracefile._types import (
    ChannelSpecification,
    TraceFileFormat,
    parse_osi_trace_filename,
    get_trace_file_format,
    _SHORT_CODE_TO_MESSAGE_TYPE as MESSAGE_TYPE_MAP,
    _EXT_TO_FORMAT,
)

_FORMAT_TO_EXT = {
    TraceFileFormat.SINGLE_CHANNEL: ".osi",
    TraceFileFormat.MULTI_CHANNEL: ".mcap",
}


@dataclass
class OSIChannelSpecification(ChannelSpecification):
    """Project extension of SDK ChannelSpecification.

    Inherits path, message_type, topic, metadata fields and common methods
    (trace_file_format, autofill_topic, exists, with_message_type, with_topic,
    with_trace_file_format) from the SDK.

    Adds project-specific file management (rename_to, with_name, with_name_suffix)
    and richer message type auto-detection for MCAP files.
    """

    def try_autodetect_message_type(self) -> bool:
        """Detect message type from filename or, for MCAP, by reading the file."""
        if self.message_type is not None:
            return True

        # Try SDK's filename-based detection first
        if super().try_autodetect_message_type():
            return True

        # For MCAP files, fall back to reading channel metadata
        if self.trace_file_format == TraceFileFormat.MULTI_CHANNEL:
            from osc_validation.utils.osi_reader import OSIChannelReader

            with OSIChannelReader.from_osi_channel_specification(
                self
            ) as channel_reader:
                detected_type = channel_reader.get_message_type()
            if detected_type is not None:
                self.message_type = detected_type
                return True

        return False

    def rename_to(self, new_path: Path) -> "OSIChannelSpecification":
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
        return OSIChannelSpecification(
            path=self.path.with_name(new_name),
            message_type=self.message_type,
            topic=self.topic,
            metadata=self.metadata,
        )

    def with_name_suffix(self, suffix: str) -> "OSIChannelSpecification":
        new_name = self.path.stem + suffix + self.path.suffix
        return OSIChannelSpecification(
            path=self.path.with_name(new_name),
            message_type=self.message_type,
            topic=self.topic,
            metadata=self.metadata,
        )

    # Override SDK builders to preserve OSIChannelSpecification type
    def with_trace_file_format(
        self, trace_file_format: TraceFileFormat
    ) -> "OSIChannelSpecification":
        return OSIChannelSpecification(
            path=self.path.with_suffix(_FORMAT_TO_EXT[trace_file_format]),
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
