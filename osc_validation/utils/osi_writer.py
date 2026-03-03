import logging
import lzma
from pathlib import Path
import struct

import google
import google.protobuf

from osc_validation.utils.osi_channel_specification import (
    OSIChannelSpecification,
    TraceFileFormat,
)

from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter
from osi_utilities.tracefile._types import MessageType, MESSAGE_TYPE_TO_CLASS_NAME, _get_message_class

_NAME_TO_MESSAGE_TYPE = {v: k for k, v in MESSAGE_TYPE_TO_CLASS_NAME.items()}


class OSITraceWriterBase:
    def __init__(self, path: Path):
        self.path = path

    def write(self, message, topic):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def get_channel_metadata(self, topic: str) -> dict:
        raise NotImplementedError()


class OSITraceWriterMulti(OSITraceWriterBase):
    """MCAP writer backed by SDK MCAPTraceFileWriter, with version enforcement."""

    def __init__(self, path: Path, net_asam_osi_metadata: dict):
        super().__init__(path)
        self.net_asam_osi_metadata = net_asam_osi_metadata
        self.active_channels = {}
        self.channel_metadata = {}

        if self.path.suffix != ".mcap":
            raise ValueError(
                f"Invalid file path: '{self.path}'. File extension must be '.mcap' for MCAP files."
            )
        if self.path.exists():
            raise ValueError(
                f"File '{self.path}' already exists. Appending to an existing file is not supported. Please specify a new path or delete the existing file before writing."
            )

        self._sdk_writer = MCAPTraceFileWriter()
        if not self._sdk_writer.open(self.path, net_asam_osi_metadata):
            raise RuntimeError(f"Failed to open MCAP writer for '{self.path}'")

        self.written_message_count = 0

    def add_osi_channel(
        self, osi_channel_spec: OSIChannelSpecification
    ) -> OSIChannelSpecification:
        if osi_channel_spec.path != self.path:
            raise ValueError(
                f"Channel path '{osi_channel_spec.path}' does not match the MCAP writer path '{self.path}'. Please ensure the channel is added to the correct MCAP writer."
            )
        if osi_channel_spec.topic in self.active_channels:
            raise ValueError(
                f"Channel with topic '{osi_channel_spec.topic}' already exists in the MCAP writer. Please use a unique topic name for each channel."
            )
        if osi_channel_spec.message_type is None:
            raise ValueError(
                f"Channel message type is not set. Please specify a valid message type for the channel."
            )

        if osi_channel_spec.topic is None:
            osi_channel_spec.autofill_topic()
            logging.info(
                f"Channel topic is not specified. Automatically setting topic to '{osi_channel_spec.topic}'."
            )

        metadata = (
            {} if osi_channel_spec.metadata is None else osi_channel_spec.metadata
        )
        message_class = _get_message_class(_NAME_TO_MESSAGE_TYPE[osi_channel_spec.message_type])
        self._sdk_writer.add_channel(osi_channel_spec.topic, message_class, metadata)
        self.active_channels[osi_channel_spec.topic] = True
        self.channel_metadata[osi_channel_spec.topic] = metadata

        return osi_channel_spec

    def write(self, message: google.protobuf.message.Message, topic: str):
        if topic not in self.active_channels:
            raise ValueError(
                f"Topic '{topic}' not found in writing channels. Available topics: {list(self.active_channels.keys())}"
            )

        channel_metadata = self.channel_metadata[topic]
        channel_osi_version = channel_metadata.get(
            "net.asam.osi.trace.channel.osi_version"
        )
        if channel_osi_version:
            major, minor, patch = map(int, channel_osi_version.split("."))
            if (
                message.version.version_major != major
                or message.version.version_minor != minor
                or message.version.version_patch != patch
            ):
                raise ValueError(
                    f"Message version ({message.version.version_major}.{message.version.version_minor}.{message.version.version_patch}) does not match channel OSI version ({channel_osi_version})."
                )
        else:
            logging.info(
                f"Channel '{topic}' does not specify an OSI version in its metadata. Writing version {message.version.version_major}.{message.version.version_minor}.{message.version.version_patch} into metadata."
            )
            self.channel_metadata[topic][
                "net.asam.osi.trace.channel.osi_version"
            ] = f"{message.version.version_major}.{message.version.version_minor}.{message.version.version_patch}"

        channel_protobuf_version = channel_metadata.get(
            "net.asam.osi.trace.channel.protobuf_version"
        )
        if channel_protobuf_version:
            if google.protobuf.__version__ != channel_protobuf_version:
                logging.warning(
                    f"Specified protobuf library version ({google.protobuf.__version__}) does not match channel protobuf version ({channel_protobuf_version}). Overwriting channel metadata with current protobuf version."
                )
        else:
            logging.info(
                f"Channel '{topic}' does not specify a protobuf version in its metadata. Writing version {google.protobuf.__version__} into metadata."
            )
        self.channel_metadata[topic][
            "net.asam.osi.trace.channel.protobuf_version"
        ] = google.protobuf.__version__

        self._sdk_writer.write_message(message, topic)
        self.written_message_count += 1

    def close(self):
        active_channels_list = ", ".join(self.active_channels.keys())
        logging.info(
            f"{self.__class__.__name__}: Wrote {self.written_message_count} messages to the channel(s) [{active_channels_list}] to '{self.path}'."
        )
        self._sdk_writer.close()

    def get_channel_metadata(self, topic: str) -> dict:
        return self.channel_metadata.get(topic, {})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class OSITraceWriterSingle(OSITraceWriterBase):
    def __init__(self, path: Path, message_type: str, compress=False):
        """
        Args:
            path (Path): The file path where the data will be written.
                        Must have '.osi' extension for uncompressed files or '.osi.xz' for compressed files.
            message_type (str): The protobuf message type name to be written to the file (e.g. SensorView).
            compress (bool, optional): Indicates whether the file should be compressed. Defaults to False.
        Raises:
            ValueError: If `compress` is True and the file path does not end with '.osi.xz'.
            ValueError: If `compress` is False and the file path does not end with '.osi'.
        """

        super().__init__(path)
        self.message_type = message_type
        self.compress = compress
        if self.compress:
            if "".join(self.path.suffixes) != ".osi.xz":
                raise ValueError(
                    f"Invalid file path: '{self.path}'. File extension must be '.osi.xz' for compressed OSI binary files."
                )
        else:
            if not self.path.suffix == ".osi":
                raise ValueError(
                    f"Invalid file path: '{self.path}'. File extension must be '.osi' for OSI binary files."
                )
        self.file = open(self.path, "wb")
        self.size = 0
        self.size_uncompressed = 0
        self.written_message_count = 0

    def write(self, message: google.protobuf.message.Message, topic: str):
        buf = message.SerializeToString()
        len_uncompressed = len(buf)
        if self.compress:
            buf = lzma.compress(buf)
        self.file.write(struct.pack("<L", len(buf)))
        self.file.write(buf)
        self.written_message_count = self.written_message_count + 1
        self.size = self.size + len(buf)
        self.size_uncompressed = self.size_uncompressed + len_uncompressed

    def close(self):
        """Closes OSI single-channel file and logs writing status."""

        if self.compress:
            compression_ratio_str = "; Compression ratio: " + str(
                round(self.size_uncompressed / self.size, 2)
            )
        else:
            compression_ratio_str = "; no compression"
        logging.info(
            f"{self.__class__.__name__}: Wrote {self.written_message_count} {self.message_type} messages to OSI single-channel file '{self.path}' ({round(self.size/1024/1024, 2)}MB{compression_ratio_str})."
        )
        self.file.close()

    def get_channel_metadata(self, topic: str):
        return {}


class OSIChannelWriter:
    def __init__(self, source: OSITraceWriterBase, topic: str, message_type: str):
        self.source = source
        self.topic = topic
        self.message_type = message_type

    @classmethod
    def from_osi_single(
        cls, trace_writer_single: OSITraceWriterSingle, topic: str, message_type: str
    ):
        """
        Creates an OSIChannelWriter instance from an existing OSITraceWriterSingle.

        Args:
            trace_writer_single (OSITraceWriterSingle): An instance of OSITraceWriterSingle to be written to.
            topic (str): The topic name to which messages will be written.
            message_type (str): The OSI message type expected in the channel (e.g. SensorView).
        """
        return cls(source=trace_writer_single, topic=topic, message_type=message_type)

    @classmethod
    def from_osi_multi(
        cls, trace_writer_multi: OSITraceWriterMulti, topic: str, message_type: str
    ):
        """
        Creates an OSIChannelWriter instance from an existing MCAP writer.

        Args:
            trace_writer_multi (OSITraceWriterMulti): An instance of OSITraceWriterMulti to be written to.
            topic (str): The topic name to which messages will be written.
            message_type (str): The OSI message type expected in the channel (e.g. SensorView).

        Returns:
            OSIChannelWriter: An instance of OSIChannelWriter initialized with the given MCAP writer and topic.
        """
        return cls(source=trace_writer_multi, topic=topic, message_type=message_type)

    @classmethod
    def from_osi_channel_specification(cls, osi_channel_spec: OSIChannelSpecification):
        """
        Creates an OSIChannelWriter instance from an OSIChannelSpecification.
        Note that this method does not support writing multiple channels to a single multi-channel file; Use `from_osi_multi` for that purpose.

        Args:
            osi_channel_spec (OSIChannelSpecification): The specification of the OSI channel.

        Returns:
            OSIChannelWriter: An instance of OSIChannelWriter initialized with the given specification.

        Raises:
            ValueError: If trace file format is not supported.
        """
        trace_file_format = osi_channel_spec.trace_file_format
        if trace_file_format == TraceFileFormat.MULTI_CHANNEL:
            source = OSITraceWriterMulti(
                osi_channel_spec.path, osi_channel_spec.metadata
            )
            osi_channel_spec_out = source.add_osi_channel(osi_channel_spec)
        elif trace_file_format == TraceFileFormat.SINGLE_CHANNEL:
            source = OSITraceWriterSingle(
                osi_channel_spec.path, osi_channel_spec.message_type
            )
            osi_channel_spec_out = osi_channel_spec
        else:
            raise ValueError(f"Unsupported trace file format: {trace_file_format}")
        return cls(
            source=source,
            topic=osi_channel_spec_out.topic,
            message_type=osi_channel_spec_out.message_type,
        )

    def write(self, message):
        self.source.write(message, self.topic)

    def close(self):
        self.source.close()

    def get_channel_specification(self) -> OSIChannelSpecification:
        return OSIChannelSpecification(
            path=self.source.path,
            message_type=self.message_type,
            topic=self.topic,
            metadata=self.source.get_channel_metadata(self.topic),
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
