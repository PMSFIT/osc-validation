import logging
from pathlib import Path
from osi3trace.osi_trace import OSITrace

from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader

from osc_validation.utils.osi_channel_specification import (
    OSIChannelSpecification,
    TraceFileFormat,
)


class OSITraceReaderBase:
    def __init__(self, path):
        """
        Args:
            path (str): The file path to the OSI trace file.
        """
        self.path = path

    def get_file_metadata(self):
        """Returns the file metadata of the trace."""
        raise NotImplementedError()

    def get_available_topics(self):
        """Returns a list of available topics in the trace."""
        raise NotImplementedError()

    def get_channel_metadata(self, topic: str):
        """Returns the channel metadata for a given topic."""
        raise NotImplementedError()

    def _retrieve_channel_info_from_data(self, topic: str):
        channel_info = {}
        start = None
        stop = None
        total_steps = 0
        step_acc = 0
        prev_timestamp = None
        for message in self.get_messages(topic):
            if hasattr(message, "version"):
                osi_version = f"{message.version.version_major}.{message.version.version_minor}.{message.version.version_patch}"
            timestamp = message.timestamp.seconds + message.timestamp.nanos / 1e9
            step = timestamp - prev_timestamp if prev_timestamp is not None else None
            step_acc = step_acc + step if step is not None else step_acc
            if start is None:
                start = timestamp
            stop = timestamp
            total_steps += 1
            prev_timestamp = timestamp
        step_size_avg = step_acc / (total_steps - 1) if total_steps > 1 else 0
        channel_info["start"] = start
        channel_info["stop"] = stop
        channel_info["step_size_avg"] = step_size_avg
        channel_info["total_steps"] = total_steps
        channel_info["osi_version"] = osi_version
        return channel_info

    def get_channel_info(self, topic: str):
        """Returns channel information as a dictionary containing start
        timestamp, stop timestamp, average step size, total number of steps, OSI
        version and OSI top-level message type."""
        raise NotImplementedError()

    def get_message_type(self, topic: str):
        """Returns the OSI message type for a given topic."""
        raise NotImplementedError()

    def get_messages(self, topic: str):
        """Returns an iterator over messages contained in the trace."""
        raise NotImplementedError()

    def close(self):
        """Closes the trace reader."""
        raise NotImplementedError()

    def print_summary(self, topic: str):
        """Prints various information about a channel."""

        channel_info = self.get_channel_info(topic)

        summary_lines = [
            ("File path", self.path),
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


class OSITraceReaderMulti(OSITraceReaderBase):
    """OSI multi-trace reader."""

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
        return [channel.topic for channel in self._summary.channels.values()]

    def get_channel_metadata(self, topic):
        for channel in self._summary.channels.values():
            if channel.topic == topic:
                return channel.metadata
        return None

    def get_channel_info(self, topic):
        channel_info = self._retrieve_channel_info_from_data(topic=topic)
        for channel in self._summary.channels.values():
            if channel.topic == topic:
                schema = self._summary.schemas[channel.schema_id]
                if schema.name.startswith("osi3."):
                    channel_info["message_type"] = schema.name[len("osi3.") :]
                else:
                    raise ValueError(
                        f"Schema name '{schema.name}' does not start with 'osi3.'"
                    )
                break
        return channel_info

    def get_message_type(self, topic: str):
        for channel in self._summary.channels.values():
            if channel.topic == topic:
                schema = self._summary.schemas[channel.schema_id]
                if schema.name.startswith("osi3."):
                    return schema.name[len("osi3.") :]
                else:
                    raise ValueError(
                        f"Schema name '{schema.name}' does not start with 'osi3.'"
                    )
        return None

    def get_messages(self, topic):
        if topic not in self.get_available_topics():
            raise ValueError(
                "Topic '"
                + topic
                + "' not found in MCAP file '"
                + self.path
                + "'. Available topics: "
                + str(self.get_available_topics())
            )
        for message in self.mcap_reader.iter_decoded_messages(topics=[topic]):
            yield message.decoded_message

    def close(self):
        """Closes the MCAP file reader."""
        self._file.close()
        logging.info(
            f"{self.__class__.__name__}: Closed OSI MCAP trace file '{self.path}'."
        )


class OSITraceAdapter(OSITraceReaderBase):
    """Adapter that wraps an OSITrace and mimics a multi-channel interface while ignoring topic input."""

    def __init__(self, path: Path, message_type: str, cache_messages=False):
        super().__init__(path)
        self.trace = OSITrace(
            path=str(path), type_name=message_type, cache_messages=cache_messages
        )
        self.topic_placeholder = self.path.stem
        self.message_type = message_type  # OSITrace is single-channel, so only one message type is possible.

    def get_file_metadata(self):
        return {}

    def get_available_topics(self):
        return [self.topic_placeholder]

    def get_channel_metadata(self, topic):
        return {}

    def get_channel_info(self, topic):
        """Traverse the trace to get trace information (start timestamp, stop
        timestamp, average step size, total steps)."""
        channel_info = self._retrieve_channel_info_from_data(topic=topic)
        return channel_info

    def get_message_type(self, topic: str):
        return self.message_type

    def get_messages(self, topic: str):
        self.trace.restart()
        for msg in self.trace:
            yield msg

    def close(self):
        """Closes the OSITrace instance."""
        self.trace.close()
        logging.info(
            f"{self.__class__.__name__}: Closed OSI binary trace file '{self.path}'."
        )


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
    def from_osi_single_trace(cls, path, message_type, cache_messages=False):
        fake_multi = OSITraceAdapter(
            path=path, message_type=message_type, cache_messages=cache_messages
        )
        return cls(source=fake_multi, topic=fake_multi.get_available_topics()[0])

    @classmethod
    def from_osi_multi_trace(cls, trace_reader_multi, topic):
        if topic not in trace_reader_multi.get_available_topics():
            raise ValueError("Topic '" + topic + "' not found in MCAP file.")
        return cls(source=trace_reader_multi, topic=topic)

    @classmethod
    def from_osi_channel_specification(cls, osi_channel_spec: OSIChannelSpecification):
        if not osi_channel_spec.path.exists():
            raise FileNotFoundError(
                f"OSI trace file '{osi_channel_spec.path}' does not exist."
            )

        source = None
        message_type = None
        topic = None

        trace_file_format = osi_channel_spec.trace_file_format

        if trace_file_format == TraceFileFormat.SINGLE_CHANNEL:
            if osi_channel_spec.message_type is None:
                raise ValueError(
                    f"Could not automatically detect message type from '{osi_channel_spec.path}'. Please specify the message type explicitly."
                )
            else:
                message_type = osi_channel_spec.message_type
            return cls.from_osi_single_trace(
                path=osi_channel_spec.path,
                message_type=message_type,
                cache_messages=True,
            )

        elif trace_file_format == TraceFileFormat.MULTI_CHANNEL:
            source = OSITraceReaderMulti(osi_channel_spec.path)
            if osi_channel_spec.topic is None:
                available_topics = source.get_available_topics()
                if not available_topics:
                    raise ValueError(
                        f"No topics found in MCAP file '{osi_channel_spec.path}'."
                    )
                topic = available_topics[0]
                logging.info(
                    f"No topic specified, using first available topic '{topic}' from MCAP file '{osi_channel_spec.path}'."
                )
            else:
                if osi_channel_spec.topic not in source.get_available_topics():
                    raise ValueError(
                        f"Topic '{osi_channel_spec.topic}' not found in MCAP file '{osi_channel_spec.path}'. Available topics: {source.get_available_topics()}"
                    )
                topic = osi_channel_spec.topic
                pass
            if osi_channel_spec.message_type is None:
                pass  # infer the message type from the channel metadata automatically
            else:
                source_message_type = source.get_message_type(topic)
                if source_message_type != osi_channel_spec.message_type:
                    raise ValueError(
                        f"Channel '{topic}' in MCAP file '{osi_channel_spec.path}' has message type '{source_message_type}', but '{osi_channel_spec.message_type}' was requested."
                    )
            return cls.from_osi_multi_trace(source, topic)

        else:
            raise ValueError(f"Unsupported trace file format: {trace_file_format}")

    def get_source_path(self):
        return self.source.path

    def get_channel_specification(self):
        return OSIChannelSpecification(
            path=Path(self.get_source_path()),
            message_type=self.source.get_channel_metadata(self.topic).get(
                "message_type", {}
            ),
            topic=self.topic,
        )

    def get_topic_name(self):
        return self.topic

    def get_file_metadata(self):
        return self.source.get_file_metadata()

    def get_channel_metadata(self):
        return self.source.get_channel_metadata(topic=self.topic)

    def get_channel_info(self):
        return self.source.get_channel_info(topic=self.topic)

    def get_message_type(self):
        return self.source.get_message_type(topic=self.topic)

    def print_summary(self):
        return self.source.print_summary(topic=self.topic)

    def get_messages(self):
        return self.source.get_messages(topic=self.topic)

    def close(self):
        return self.source.close()

    def __iter__(self):
        return self.get_messages()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
