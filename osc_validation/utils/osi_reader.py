""" OSI3 Trace Tools

(C) 2018-2025 PMSF IT Consulting Pierre R. Mai

This file provides classes or functions to read OSI trace files.
"""

from osi3trace.osi_trace import OSITrace

from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader


class OSITraceReaderBase:
    def __init__(self, path):
        """
        Args:
            path (str): The file path to the OSI trace file.
        """
        self.path = path

    def get_file_metadata(self):
        """ Returns the file metadata of the trace. """
        raise NotImplementedError()
    
    def get_available_topics(self):
        """ Returns a list of available topics in the trace. """
        raise NotImplementedError()
    
    def get_channel_metadata(self, topic: str):
        """ Returns the channel metadata for a given topic. """
        raise NotImplementedError()
    
    def _retrieve_channel_info_from_data(self, topic: str):
        channel_info = {}
        start = None
        stop = None
        total_steps = 0
        step_acc = 0
        prev_timestamp = None
        for message in self.get_messages(topic):
            if hasattr(message, 'version'):
                osi_version = f"{message.version.version_major}.{message.version.version_minor}.{message.version.version_patch}"
            timestamp = message.timestamp.seconds + message.timestamp.nanos / 1e9
            step = timestamp - prev_timestamp if prev_timestamp is not None else None
            step_acc = step_acc + step if step is not None else step_acc
            if start is None:
                start = timestamp
            stop = timestamp
            total_steps += 1
            prev_timestamp = timestamp
        step_size_avg = step_acc / (total_steps-1) if total_steps > 1 else 0
        channel_info["start"] = start
        channel_info["stop"] = stop
        channel_info["step_size_avg"] = step_size_avg
        channel_info["total_steps"] = total_steps
        channel_info["osi_version"] = osi_version
        return channel_info

    def get_channel_info(self, topic: str):
        """ Returns channel information as a dictionary containing start
        timestamp, stop timestamp, average step size, total number of steps, OSI
        version and OSI top-level message type. """
        raise NotImplementedError()

    def get_messages(self, topic: str):
        """ Returns an iterator over messages contained in the trace. """
        raise NotImplementedError()
    
    def close(self):
        """ Closes the trace reader. """
        raise NotImplementedError()
    
    def print_summary(self, topic: str):
        """ Prints various information about a channel. """
        
        channel_info = self.get_channel_info(topic)
        
        summary_lines = [
            ("File path", self.path),
            ("OSI version", f"{channel_info["osi_version"]}"),
            ("OSI trace type", channel_info["message_type_name"]),
            ("Start timestamp", f"{channel_info["start"]}s"),
            ("Stop timestamp", f"{channel_info["stop"]}s"),
            ("Average Step Size", f"{round(channel_info["step_size_avg"], 9)}s"),
            ("Total Steps", channel_info["total_steps"]),
        ]

        max_label_len = max(len(label) for label, _ in summary_lines)
        for label, value in summary_lines:
            print(f"{label + ':':<{max_label_len + 2}} {value}")


class OSITraceReaderMulti(OSITraceReaderBase):
    """ OSI multi-trace reader. """

    def __init__(self, path):
        super().__init__(path)
        self._file = open(self.path, "rb")
        self.mcap_reader = make_reader(self._file, decoder_factories=[DecoderFactory()])
        self._summary = self.mcap_reader.get_summary()
    
    def get_file_metadata(self):
        metadata = []
        for metadata_entry in self.mcap_reader.iter_metadata():
            metadata.append(metadata_entry)
        return metadata

    def get_available_topics(self):
        return [channel.topic for id, channel in self._summary.channels.items()]
    
    def get_channel_metadata(self, topic):
        for id, channel in self._summary.channels.items():
            if channel.topic == topic:
                return channel.metadata
        return None

    def get_channel_info(self, topic):
        channel_info = self._retrieve_channel_info_from_data(topic=topic)
        for channel_id, channel in self._summary.channels.items():
            if channel.topic == topic:
                schema = self._summary.schemas[channel.schema_id]
                channel_info["message_type_name"] = schema.name
                break
        return channel_info

    def get_messages(self, topic):
        if topic not in self.get_available_topics():
            raise ValueError("Topic '"+topic+"' not found in MCAP file '"+self.path+"'. Available topics: "+str(self.get_available_topics()))
        for message in self.mcap_reader.iter_decoded_messages(topics=[topic]):
            yield message.decoded_message
    
    def close(self):
        """ Closes the MCAP file reader. """
        self._file.close()
        print(f"{self.__class__.__name__}: Closed OSI MCAP trace file '{self.path}'.")


class OSITraceAdapter(OSITraceReaderBase):
    """Adapter that wraps an OSITrace and mimics a multi-channel interface."""

    def __init__(self, path=None, type_name="SensorView", cache_messages=False):
        super().__init__(path)
        self.trace = OSITrace(path=path, type_name=type_name, cache_messages=cache_messages)
        self.topic_placeholder = "single-channel"
        self._message_type_name = "osi3."+type_name

    def get_topic_placeholder(self):
        """ Returns a placeholder topic name for single-channel traces. """
        return self.topic_placeholder
    
    def get_file_metadata(self, topic):
        raise NotImplementedError(f"{self.__class__.__name__} does not support file metadata.")

    def get_available_topics(self):
        raise NotImplementedError(f"{self.__class__.__name__} does not support channels.")
    
    def get_channel_metadata(self, topic):
        raise NotImplementedError(f"{self.__class__.__name__} does not support channel metadata.")
    
    def get_channel_info(self, topic):
        """ Traverse the trace to get trace information (start timestamp, stop
        timestamp, average step size, total steps). """
        channel_info = self._retrieve_channel_info_from_data(topic=topic)
        channel_info["message_type_name"] = self._message_type_name
        return channel_info

    def get_messages(self, topic: str):
        return self.trace.get_messages()
    
    def close(self):
        """ Closes the OSITrace instance. """
        self.trace.close()
        print(f"{self.__class__.__name__}: Closed OSI binary trace file '{self.path}'.")


class OSIChannelReader:
    """
    OSI channel reader wrapper for accessing a channel from single- or
    multi-channel trace files in a unified way. Passes through applicable
    methods of the underlying trace reader.
    """
    def __init__(self, source: OSITraceReaderBase, topic: str):
        self.source = source
        self.topic = topic

    @classmethod
    def from_osi_binary(cls, path=None, type_name="SensorView", cache_messages=False):
        fake_multi = OSITraceAdapter(path=path, type_name=type_name, cache_messages=cache_messages)
        return cls(source=fake_multi, topic=fake_multi.get_topic_placeholder())
    
    @classmethod
    def from_osi_mcap(cls, trace_reader_multi, topic):
        if topic not in trace_reader_multi.get_available_topics():
            raise ValueError("Topic '"+topic+"' not found in MCAP file.")
        return cls(source=trace_reader_multi, topic=topic)
    
    def get_file_metadata(self):
        return self.source.get_file_metadata()
    
    def get_channel_metadata(self):
        return self.source.get_channel_metadata(topic=self.topic)
    
    def get_channel_info(self):
        return self.source.get_channel_info(topic=self.topic)
    
    def print_summary(self):
        return self.source.print_summary(topic=self.topic)
    
    def get_messages(self):
        return self.source.get_messages(topic=self.topic)
    
    def close(self):
        return self.source.close()
