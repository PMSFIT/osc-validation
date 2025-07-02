import logging
import lzma
from pathlib import Path
import struct
import osc_validation

from mcap.writer import Writer
from mcap.well_known import MessageEncoding

import google
from google.protobuf.descriptor import FileDescriptor
from google.protobuf.descriptor_pb2 import FileDescriptorSet

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification, TraceFileFormat

from osi3 import (
    osi_sensorview_pb2,
    osi_sensordata_pb2,
    osi_groundtruth_pb2,
    osi_hostvehicledata_pb2,
    osi_trafficcommand_pb2,
    osi_trafficcommandupdate_pb2,
    osi_trafficupdate_pb2,
    osi_motionrequest_pb2,
    osi_streamingupdate_pb2,
    osi_sensorviewconfiguration_pb2,
)


MESSAGE_TYPE_MAP = {
    osi_sensorview_pb2.SensorView.DESCRIPTOR.name: osi_sensorview_pb2.SensorView,
    osi_sensorviewconfiguration_pb2.SensorViewConfiguration.DESCRIPTOR.name: osi_sensorviewconfiguration_pb2.SensorViewConfiguration,
    osi_groundtruth_pb2.GroundTruth.DESCRIPTOR.name: osi_groundtruth_pb2.GroundTruth,
    osi_hostvehicledata_pb2.HostVehicleData.DESCRIPTOR.name: osi_hostvehicledata_pb2.HostVehicleData,
    osi_sensordata_pb2.SensorData.DESCRIPTOR.name: osi_sensordata_pb2.SensorData,
    osi_trafficcommand_pb2.TrafficCommand.DESCRIPTOR.name: osi_trafficcommand_pb2.TrafficCommand,
    osi_trafficcommandupdate_pb2.TrafficCommandUpdate.DESCRIPTOR.name: osi_trafficcommandupdate_pb2.TrafficCommandUpdate,
    osi_trafficupdate_pb2.TrafficUpdate.DESCRIPTOR.name: osi_trafficupdate_pb2.TrafficUpdate,
    osi_motionrequest_pb2.MotionRequest.DESCRIPTOR.name: osi_motionrequest_pb2.MotionRequest,
    osi_streamingupdate_pb2.StreamingUpdate.DESCRIPTOR.name: osi_streamingupdate_pb2.StreamingUpdate,
}


class OSITraceWriterBase:
    def __init__(self, path: Path):
        self.path = path

    def write(self, message, topic):
        raise NotImplementedError()
    
    def close(self):
        raise NotImplementedError()


class OSITraceWriterMulti(OSITraceWriterBase):
    def __init__(self, path: Path, net_asam_osi_metadata: dict):
        """
        Args:
            path (Path): The file path where the MCAP file will be written. 
                         Must have a '.mcap' extension.
            net_asam_osi_metadata (dict): Metadata for the 'net.asam.osi.trace' 
                                          to be added to the MCAP file.

        Raises:
            ValueError: If the provided file path does not have a '.mcap' extension.
            ValueError: If the file already exists, as appending to an existing file is not supported.
        """

        super().__init__(path)
        self.net_asam_osi_metadata = net_asam_osi_metadata
        self.active_channels = {}
        self.channel_metadata = {}

        if self.path.suffix != ".mcap":
            raise ValueError(f"Invalid file path: '{self.path}'. File extension must be '.mcap' for MCAP files.")
        if self.path.exists():
            raise ValueError(f"File '{self.path}' already exists. Appending to an existing file is not supported. Please specify a new path or delete the existing file before writing.")

        self.mcap_writer = Writer(output=str(self.path),)

        self.mcap_writer.start(library=f"osc_validation {osc_validation.__version__}")

        self.validate_file_metadata(net_asam_osi_metadata)
        self.mcap_writer.add_metadata(
            name="net.asam.osi.trace", 
            data=net_asam_osi_metadata
        )
        self.written_message_count = 0

    def validate_file_metadata(self, osi_metadata):
        """ Validate 'net.asam.osi.trace' metadata completeness. """

        required_keys = {
            "version", "min_osi_version", "max_osi_version",
            "min_protobuf_version", "max_protobuf_version",
        }
        recommended_keys = {
            "zero_time", "creation_time", "description",
            "authors", "data_sources"
        }
        missing_required_keys = required_keys - osi_metadata.keys()
        missing_recommended_keys = recommended_keys - osi_metadata.keys()
        if missing_required_keys:
            logging.warning(f"Missing mandatory 'net.asam.osi.trace' metadata for compliance with OSI MCAP trace file format: {', '.join(missing_required_keys)}")
        if missing_recommended_keys:
            logging.info(f"Missing recommended 'net.asam.osi.trace' metadata: {', '.join(missing_recommended_keys)}")

    def validate_channel_metadata(self, channel_metadata):
        """ Validate 'net.asam.osi.trace.channel' metadata completeness. """

        required_keys = {
            "net.asam.osi.trace.channel.osi_version",
            "net.asam.osi.trace.channel.protobuf_version"
        }
        missing_required_keys = required_keys - channel_metadata.keys()
        recommended_keys = {
            "net.asam.osi.trace.channel.description"
        }
        missing_recommended_keys = recommended_keys - channel_metadata.keys()
        if missing_required_keys:
            logging.warning(f"Missing mandatory 'net.asam.osi.trace.channel' metadata for compliance with OSI MCAP trace file format: {', '.join(missing_required_keys)}")
        if missing_recommended_keys:
            logging.info(f"Missing recommended 'net.asam.osi.trace.channel' metadata: {', '.join(missing_recommended_keys)}")

    def add_osi_channel(self, osi_channel_spec: OSIChannelSpecification) -> OSIChannelSpecification:
        """
        Adds an OSI (Open Simulation Interface) channel to the MCAP writer. This
        method validates the provided channel metadata, builds a file descriptor
        set for the given message type, registers the schema with the MCAP
        writer, and then registers the channel with the specified topic (or
        auto-generated topic if not given), message encoding, schema ID, and
        metadata.
        Args:
            osi_channel_spec (OSIChannelSpecification): Specification of the OSI channel to be added.
        Raises:
            ValueError: If channel specification path does not match the MCAP writer path.
            ValueError: If the channel topic already exists in the active channels.
            ValueError: If the channel message type is not set.
        """

        if osi_channel_spec.path != self.path:
            raise ValueError(f"Channel path '{osi_channel_spec.path}' does not match the MCAP writer path '{self.path}'. Please ensure the channel is added to the correct MCAP writer.")
        if osi_channel_spec.topic in self.active_channels:
            raise ValueError(f"Channel with topic '{osi_channel_spec.topic}' already exists in the MCAP writer. Please use a unique topic name for each channel.")
        if osi_channel_spec.message_type is None:
            raise ValueError(f"Channel message type is not set. Please specify a valid message type for the channel.")
        
        if osi_channel_spec.topic is None:
            osi_channel_spec.autofill_topic()
            logging.info(f"Channel topic is not specified. Automatically setting topic to '{osi_channel_spec.topic}'.")

        metadata = {} if osi_channel_spec.metadata is None else osi_channel_spec.metadata
        self.validate_channel_metadata(metadata)
        file_descriptor_set = self._build_file_descriptor_set(MESSAGE_TYPE_MAP[osi_channel_spec.message_type])
        schema_id = self.mcap_writer.register_schema(
            name=f"osi3.{osi_channel_spec.message_type}",
            encoding=MessageEncoding.Protobuf,
            data=file_descriptor_set.SerializeToString(),
        )
        channel_id = self.mcap_writer.register_channel(
            topic=osi_channel_spec.topic,
            message_encoding=MessageEncoding.Protobuf,
            schema_id=schema_id,
            metadata=metadata,
        )
        self.active_channels[osi_channel_spec.topic] = channel_id
        self.channel_metadata[osi_channel_spec.topic] = metadata

        return osi_channel_spec

    def _build_file_descriptor_set(self, message_class) -> FileDescriptorSet:
        file_descriptor_set = FileDescriptorSet()
        seen_dependencies = set()

        def append_file_descriptor(file_descriptor: FileDescriptor):
            for dep in file_descriptor.dependencies:
                if dep.name not in seen_dependencies:
                    seen_dependencies.add(dep.name)
                    append_file_descriptor(dep)
            file_descriptor.CopyToProto(file_descriptor_set.file.add())

        append_file_descriptor(message_class.DESCRIPTOR.file)
        return file_descriptor_set

    def write(self, message: google.protobuf.message.Message, topic: str):
        """
        Writes a message to the specified topic channel in the MCAP writer.
        Args:
            message: The OSI protobuf message object to be written. It must have a `timestamp` attribute
                     with `seconds` and `nanos` properties, and a `SerializeToString` method.
            topic (str): The topic name to which the message should be written.
        Raises:
            ValueError: If the specified topic is not found in the active channels.
            ValueError: If the message OSI version is not equivalent to the channel's OSI version specified in the channel metadata.
        """

        if topic not in self.active_channels:
            raise ValueError(f"Topic '{topic}' not found in writing channels. Available topics: {list(self.active_channels.keys())}")
        
        channel_metadata = self.channel_metadata[topic]
        channel_osi_version = channel_metadata.get("net.asam.osi.trace.channel.osi_version")
        if channel_osi_version:
            major, minor, patch = map(int, channel_osi_version.split("."))
            if (message.version.version_major != major or 
                message.version.version_minor != minor or 
                message.version.version_patch != patch):
                raise ValueError(f"Message version ({message.version.version_major}.{message.version.version_minor}.{message.version.version_patch}) does not match channel OSI version ({channel_osi_version}).")
        else:
            logging.info(f"Channel '{topic}' does not specify an OSI version in its metadata. Writing version {message.version.version_major}.{message.version.version_minor}.{message.version.version_patch} into metadata.")
            self.channel_metadata[topic]["net.asam.osi.trace.channel.osi_version"] = f"{message.version.version_major}.{message.version.version_minor}.{message.version.version_patch}"

        channel_protobuf_version = channel_metadata.get("net.asam.osi.trace.channel.protobuf_version")
        if channel_protobuf_version:
            if google.protobuf.__version__ != channel_protobuf_version:
                logging.warning(f"Specified protobuf library version ({google.protobuf.__version__}) does not match channel protobuf version ({channel_protobuf_version}). Overwriting channel metadata with current protobuf version.")
        else:
            logging.info(f"Channel '{topic}' does not specify a protobuf version in its metadata. Writing version {google.protobuf.__version__} into metadata.")
        self.channel_metadata[topic]["net.asam.osi.trace.channel.protobuf_version"] = google.protobuf.__version__
        
        time = message.timestamp.seconds + message.timestamp.nanos / 1e9
        self.mcap_writer.add_message(
            channel_id=self.active_channels[topic],
            log_time=int(time*1000000000),
            data=message.SerializeToString(),
            publish_time=int(time*1000000000),
        )
        self.written_message_count = self.written_message_count+1

    def close(self):
        """ Closes the TraceWriter instance and finalizes the writing process. """
        active_channels_list = ", ".join(self.active_channels.keys())
        logging.info(f"{self.__class__.__name__}: Wrote {self.written_message_count} messages to the channel(s) [{active_channels_list}] to '{self.path}'.")
        self.mcap_writer.finish()

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
            if not self.path.suffix == ".osi.xz":
                raise ValueError(f"Invalid file path: '{self.path}'. File extension must be '.osi.xz' for compressed OSI binary files.")
        else:
            if not self.path.suffix == ".osi":
                raise ValueError(f"Invalid file path: '{self.path}'. File extension must be '.osi' for OSI binary files.")
        self.file = open(self.path, "wb")
        self.size = 0
        self.size_uncompressed = 0
        self.written_message_count = 0

    def write(self, message, topic):
        buf = message.SerializeToString()
        len_uncompressed = len(buf)
        if self.compress:
            buf = lzma.compress(buf)
        self.file.write(struct.pack("<L", len(buf)))
        self.file.write(buf)
        self.written_message_count = self.written_message_count+1
        self.size = self.size+len(buf)
        self.size_uncompressed = self.size_uncompressed+len_uncompressed

    def close(self):
        """ Closes OSI single-channel file and logs writing status. """

        if self.compress:
            compression_ratio_str =  "; Compression ratio: "+str(round(self.size_uncompressed/self.size, 2))
        else:
            compression_ratio_str = "; no compression"
        logging.info(f"{self.__class__.__name__}: Wrote {self.written_message_count} {self.message_type} messages to OSI single-channel file '{self.path}' ({round(self.size/1024/1024, 2)}MB{compression_ratio_str}).")
        self.file.close()


class OSIChannelWriter:
    def __init__(self, source: OSITraceWriterBase, topic: str, message_type: str):
        self.source = source
        self.topic = topic
        self.message_type = message_type

    @classmethod
    def from_osi_single(cls, trace_writer_single: OSITraceWriterSingle, topic: str, message_type: str):
        """
        Creates an OSIChannelWriter instance from an existing OSITraceWriterSingle.

        Args:
            trace_writer_single (OSITraceWriterSingle): An instance of OSITraceWriterSingle to be written to.
            topic (str): The topic name to which messages will be written.
            message_type (str): The OSI message type expected in the channel (e.g. SensorView).
        """
        return cls(source=trace_writer_single, topic=topic, message_type=message_type)

    @classmethod
    def from_osi_multi(cls, trace_writer_multi: OSITraceWriterMulti, topic: str, message_type: str):
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
            source = OSITraceWriterMulti(osi_channel_spec.path, osi_channel_spec.metadata)
            osi_channel_spec_out = source.add_osi_channel(osi_channel_spec)
        elif trace_file_format == TraceFileFormat.SINGLE_CHANNEL:
            source = OSITraceWriterSingle(osi_channel_spec.path, osi_channel_spec.message_type)
            osi_channel_spec_out = osi_channel_spec
        else:
            raise ValueError(f"Unsupported trace file format: {trace_file_format}")
        return cls(source=source, topic=osi_channel_spec_out.topic, message_type=osi_channel_spec_out.message_type)
        
    def write(self, message):
        self.source.write(message, self.topic)

    def close(self):
        self.source.close()

    def get_channel_specification(self) -> OSIChannelSpecification:
        return OSIChannelSpecification(
            path=self.source.path,
            message_type=self.message_type,
            topic=self.topic,
            metadata=self.source.channel_metadata.get(self.topic, {})
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
