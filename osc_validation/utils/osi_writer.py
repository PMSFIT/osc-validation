from pathlib import Path
import osc_validation

from mcap.writer import Writer
from mcap.well_known import MessageEncoding

from google.protobuf.descriptor import FileDescriptor
from google.protobuf.descriptor_pb2 import FileDescriptorSet


class OSITraceWriter:
    def __init__(self, path: Path, net_asam_osi_metadata: dict):
        """
        Args:
            path (str): The file path where the MCAP file will be written. 
                        Must have a '.mcap' extension.
            net_asam_osi_metadata (dict): Metadata for the 'net.asam.osi.trace' 
                                          to be added to the MCAP file.

        Raises:
            ValueError: If the provided file path does not have a '.mcap' extension.
        """

        self.path = path
        self.net_asam_osi_metadata = net_asam_osi_metadata
        self.active_channels = {}
        self.channel_metadata = {}

        if not str(self.path).endswith(".mcap"):
            raise ValueError(f"Invalid file path: '{self.path}'. File extension must be '.mcap' for MCAP files.")

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
            print(f"Warning: Missing mandatory 'net.asam.osi.trace' metadata: {', '.join(missing_required_keys)}")
        if missing_recommended_keys:
            print(f"Warning: Missing recommended 'net.asam.osi.trace' metadata: {', '.join(missing_recommended_keys)}")
    
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
            print(f"Warning: Missing mandatory 'net.asam.osi.trace.channel' metadata: {', '.join(missing_required_keys)}")
        if missing_recommended_keys:
            print(f"Warning: Missing recommended 'net.asam.osi.trace.channel' metadata: {', '.join(missing_recommended_keys)}")

    def add_osi_channel(self, message_type, topic, metadata):
        """
        Adds an OSI (Open Simulation Interface) channel to the MCAP writer.
        This method validates the provided channel metadata, builds a file descriptor
        set for the given message type, registers the schema with the MCAP writer, and
        then registers the channel with the specified topic, message encoding, schema ID,
        and metadata.
        Args:
            message_type: The protobuf message type to be used for the channel.
            topic (str): The topic name for the channel.
            metadata (dict): A dictionary containing metadata for the channel.
        Raises:
            ValueError: If the provided metadata is invalid.
        """

        self.validate_channel_metadata(metadata)
        file_descriptor_set = self._build_file_descriptor_set(message_type)
        schema_id = self.mcap_writer.register_schema(
            name=message_type.DESCRIPTOR.full_name,
            encoding=MessageEncoding.Protobuf,
            data=file_descriptor_set.SerializeToString(),
        )
        channel_id = self.mcap_writer.register_channel(
            topic=topic,
            message_encoding=MessageEncoding.Protobuf,
            schema_id=schema_id,
            metadata=metadata
        )
        self.active_channels[topic] = channel_id
        self.channel_metadata[topic] = metadata
    
    def _build_file_descriptor_set(self, message_class) :
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

    def write(self, message, topic):
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
        print(f"{self.__class__.__name__}: Wrote {self.written_message_count} messages to the channel(s) [{active_channels_list}] to '{self.path}'.")
        self.mcap_writer.finish()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False