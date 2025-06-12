""" OSI3 Trace Tools

(C) 2018-2025 PMSF IT Consulting Pierre R. Mai

This file provides classes or functions to read or write OSI trace files.
"""

import struct

import lzma

import osc_validation

import osi3
from osi3trace.osi_trace import OSITrace

from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader
from mcap.writer import Writer
from mcap.well_known import MessageEncoding

from google.protobuf.descriptor import FileDescriptor
from google.protobuf.descriptor_pb2 import FileDescriptorSet


class TraceReader:
    """ OSI trace file decoder wrapper base class. """

    def __init__(self, path):
        self.path = path
        self.start = None
        self.stop = None
        self.step_size_avg = None
        self.total_steps = None
        self.osi_version = None
        self.message_type_name = None

    def get_messages(self, *args, **kwargs):
        """ Returns an iterator over messages contained in the trace. """

        raise NotImplementedError()
    
    def get_trace_info(self, *args, **kwargs):
        """ Traverse the trace to get trace information (start timestamp, stop
        timestamp, average step size, total steps). """

        if all(var is not None for var in (self.start, self.stop, self.step_size_avg, self.total_steps)):
            return self.start, self.stop, self.step_size_avg, self.total_steps
        start = None
        stop = None
        total_steps = 0
        step_acc = 0
        prev_timestamp = None
        for message in self.get_messages(*args, **kwargs):
            if self.osi_version is None and hasattr(message, 'version'):
                self.osi_version = f"{message.version.version_major}.{message.version.version_minor}.{message.version.version_patch}"
            timestamp = message.timestamp.seconds + message.timestamp.nanos / 1e9
            step = timestamp - prev_timestamp if prev_timestamp is not None else None
            step_acc = step_acc + step if step is not None else step_acc
            if start is None:
                start = timestamp
            stop = timestamp
            total_steps += 1
            prev_timestamp = timestamp
        self.start, self.stop, self.step_size_avg, self.total_steps = start, stop, step_acc / (total_steps-1), total_steps
        return self.start, self.stop, self.step_size_avg, self.total_steps
    
    def print_summary(self, *args, **kwargs):
        """ Prints various information about the trace. """

        self.start, self.stop, self.avg_step_size, self.total_steps = self.get_trace_info(*args, **kwargs)
        print(f"Trace info ({self.path}):")
        print(f"OSI version:\t\t{self.osi_version} (Installed: {osi3.__version__})")
        print(f"OSI trace type:\t\t{self.message_type_name}")
        print(f"Start:\t\t\t{self.start}s")
        print(f"Stop:\t\t\t{self.stop}s")
        print(f"Average Step Size:\t{round(self.avg_step_size, 9)}s")
        print(f"Total Steps:\t\t{self.total_steps}")
        print()


class TraceReaderBinary(TraceReader):
    """ Wrapper for OSITrace decoder class. """

    def __init__(self, path, message_type, cache_messages=False):
        super().__init__(path)
        self.message_type = f"{message_type.DESCRIPTOR.file.package}.{message_type.DESCRIPTOR.name}"
        self.trace = OSITrace(path, message_type.DESCRIPTOR.name, cache_messages)

    def get_trace_info(self):
        return super().get_trace_info()
    
    def print_summary(self):
        return super().print_summary()

    def get_messages(self):
        return self.trace.get_messages()
    
    def get_messages_in_index_range(self, begin, end):
        return self.trace.get_messages_in_index_range(begin, end)
    

class TraceReaderMcap(TraceReader):
    """ Wrapper for Mcap decoder. """

    def __init__(self, path):
        super().__init__(path)
        self.file = open(self.path, "rb")
        self.mcap_reader = make_reader(self.file, decoder_factories=[DecoderFactory()])

    def print_summary(self, topic):
        super().print_summary(topic=topic)
        print("Available channels/topics:")
        for id, channel in self.mcap_reader.get_summary().channels.items():
            schema_name = self.mcap_reader.get_summary().schemas[channel.schema_id].name
            print(f" - Channel ID: {id}, Topic: {channel.topic}, Schema: {schema_name}, Message Encoding: {channel.message_encoding}")
        print()

    def get_trace_info(self, topic):
        if self.message_type_name is None:
            for id, channel in self.mcap_reader.get_summary().channels.items():
                if channel.topic == topic:
                    schema = self.mcap_reader.get_summary().schemas[channel.schema_id]
                    self.message_type_name = schema.name
                    break
        return super().get_trace_info(topic=topic)

    def get_available_topics(self):
        return [channel.topic for id, channel in self.mcap_reader.get_summary().channels.items()]
    
    def get_file_metadata(self):
        metadata = []
        for metadata_entry in self.mcap_reader.iter_metadata():
            metadata.append(metadata_entry)
        return metadata
    
    def get_channel_metadata(self, topic):
        for id, channel in self.mcap_reader.get_summary().channels.items():
            if channel.topic == topic:
                return channel.metadata
        return None

    def get_messages(self, topic):
        if topic not in self.get_available_topics():
            raise Exception("Topic '"+topic+"' not found in MCAP file '"+self.path+"'. Available topics: "+str(self.get_available_topics()))
        for message in self.mcap_reader.iter_decoded_messages(topics=[topic]):
            yield message.decoded_message


class TraceWriter:
    """ OSI trace file encoder wrapper base class. """

    def __init__(self, path):
        self.path = path

    def write(self, message, *args, **kwargs):
        raise NotImplementedError()
    
    def close(self):
        raise NotImplementedError()
    

class TraceWriterBinary(TraceWriter):
    def __init__(self, path, message_type, compress=False):
        """
        Args:
            path (str): The file path where the data will be written.
                        Must have '.osi' extension for uncompressed files or '.osi.xz' for compressed files.
            message_type: The protobuf message type to be written to the file.
            compress (bool, optional): Indicates whether the file should be compressed. Defaults to False.
        Raises:
            ValueError: If `compress` is True and the file path does not end with '.osi.xz'.
            ValueError: If `compress` is False and the file path does not end with '.osi'.
        """

        super().__init__(path)
        self.message_type_name = message_type.DESCRIPTOR.name
        self.compress = compress
        if self.compress:
            if not self.path.endswith(".osi.xz"):
                raise ValueError(f"Invalid file path: '{self.path}'. File extension must be '.osi.xz' for compressed OSI binary files.")
        else:
            if not self.path.endswith(".osi"):
                raise ValueError(f"Invalid file path: '{self.path}'. File extension must be '.osi' for OSI binary files.")
        self.file = open(self.path, "wb")
        self.size = 0
        self.size_uncompressed = 0
        self.written_message_count = 0

    def write(self, message):
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
        """ Closes OSI binary file and prints writing status. """

        if self.compress:
            compression_ratio_str =  "; Compression ratio: "+str(round(self.size_uncompressed/self.size, 2))
        else:
            compression_ratio_str = "; no compression"
        print(f"{self.__class__.__name__}: Wrote {self.written_message_count} {self.message_type_name} messages to OSI binary file '{self.path}' ({round(self.size/1024/1024, 2)}MB{compression_ratio_str}).")
        self.file.close()


class TraceWriterMcap(TraceWriter):
    def __init__(self, path, net_asam_osi_metadata):
        """
        Args:
            path (str): The file path where the MCAP file will be written. 
                        Must have a '.mcap' extension.
            net_asam_osi_metadata (dict): Metadata for the 'net.asam.osi.trace' 
                                           to be added to the MCAP file.

        Raises:
            ValueError: If the provided file path does not have a '.mcap' extension.
        """
        
        super().__init__(path)
        self.net_asam_osi_metadata = net_asam_osi_metadata
        self.active_channels = {}
        self.channel_metadata = {}

        if not self.path.endswith(".mcap"):
            raise ValueError(f"Invalid file path: '{self.path}'. File extension must be '.mcap' for MCAP files.")

        self.mcap_writer = Writer(output=path,)

        self.mcap_writer.start(profile="osi2mcap", library=f"osc_validation {osc_validation.__version__}")

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
            message: The message object to be written. It must have a `timestamp` attribute
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
        """ Closes the TraceWriterMcap instance and finalizes the writing process. """
        active_channels_list = ", ".join(self.active_channels.keys())
        print(f"{self.__class__.__name__}: Wrote {self.written_message_count} messages to the channel(s) [{active_channels_list}] to '{self.path}'.")
        self.mcap_writer.finish()