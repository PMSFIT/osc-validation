import logging
from pathlib import Path

from osc_validation.utils.osi_channel_specification import (
    OSIChannelSpecification,
    TraceFileFormat,
)

from osi_utilities.tracefile.binary_reader import BinaryTraceFileReader
from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader
from osi_utilities.tracefile._types import MessageType, MESSAGE_TYPE_TO_CLASS_NAME

_NAME_TO_MESSAGE_TYPE = {v: k for k, v in MESSAGE_TYPE_TO_CLASS_NAME.items()}


def _retrieve_channel_info_from_data(get_messages_fn):
    """Compute channel info by iterating all messages from the given callable."""
    start = None
    stop = None
    total_steps = 0
    step_acc = 0
    prev_timestamp = None
    osi_version = None
    for message in get_messages_fn():
        if hasattr(message, "version"):
            osi_version = f"{message.version.version_major}.{message.version.version_minor}.{message.version.version_patch}"
        timestamp = (
            message.timestamp.seconds * 1_000_000_000 + message.timestamp.nanos
        ) / 1_000_000_000
        step = timestamp - prev_timestamp if prev_timestamp is not None else None
        step_acc = step_acc + step if step is not None else step_acc
        if start is None:
            start = timestamp
        stop = timestamp
        total_steps += 1
        prev_timestamp = timestamp
    step_size_avg = step_acc / (total_steps - 1) if total_steps > 1 else 0
    return {
        "start": start,
        "stop": stop,
        "step_size_avg": step_size_avg,
        "total_steps": total_steps,
        "osi_version": osi_version,
    }


class OSITraceReaderBase:
    """Abstract base for trace readers."""

    def __init__(self, path):
        self.path = path

    def get_file_metadata(self):
        raise NotImplementedError()

    def get_available_topics(self):
        raise NotImplementedError()

    def get_channel_metadata(self, topic: str):
        raise NotImplementedError()

    def get_channel_info(self, topic: str):
        raise NotImplementedError()

    def get_message_type(self, topic: str):
        raise NotImplementedError()

    def get_messages(self, topic: str):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def print_summary(self, topic: str):
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
    """OSI multi-trace reader backed by SDK MCAPTraceFileReader."""

    def __init__(self, path):
        super().__init__(path)
        self._sdk = MCAPTraceFileReader()
        if not self._sdk.open(Path(str(path))):
            raise ValueError(f"Failed to open MCAP file '{path}'")

    def get_file_metadata(self):
        return self._sdk.get_file_metadata()

    def get_available_topics(self):
        return self._sdk.get_available_topics()

    def get_channel_metadata(self, topic):
        return self._sdk.get_channel_metadata(topic)

    def get_channel_info(self, topic):
        channel_info = _retrieve_channel_info_from_data(
            lambda: self.get_messages(topic)
        )
        msg_type = self._sdk.get_message_type_for_topic(topic)
        if msg_type is not None:
            channel_info["message_type"] = MESSAGE_TYPE_TO_CLASS_NAME[msg_type]
        else:
            raise ValueError(f"Could not determine message type for topic '{topic}'")
        return channel_info

    def get_message_type(self, topic: str):
        msg_type = self._sdk.get_message_type_for_topic(topic)
        if msg_type is not None:
            return MESSAGE_TYPE_TO_CLASS_NAME[msg_type]
        return None

    def get_messages(self, topic):
        if topic not in self.get_available_topics():
            raise ValueError(
                f"Topic '{topic}' not found in MCAP file '{self.path}'. "
                f"Available topics: {self.get_available_topics()}"
            )
        self._sdk.set_topics([topic])
        while True:
            result = self._sdk.read_message()
            if result is None:
                break
            yield result.message

    def close(self):
        self._sdk.close()
        logging.info(
            f"{self.__class__.__name__}: Closed OSI MCAP trace file '{self.path}'."
        )


class OSITraceAdapter(OSITraceReaderBase):
    """Adapter using SDK BinaryTraceFileReader, mimics multi-channel interface for single-channel binary files."""

    def __init__(self, path: Path, message_type: str, cache_messages=False):
        super().__init__(path)
        self.topic_placeholder = Path(str(path)).stem
        self.message_type = message_type
        self._msg_type_enum = _NAME_TO_MESSAGE_TYPE.get(
            message_type, MessageType.UNKNOWN
        )
        self._path = Path(str(path))
        self._cache_messages = cache_messages
        self._cached_messages = None

    def get_file_metadata(self):
        return {}

    def get_available_topics(self):
        return [self.topic_placeholder]

    def get_channel_metadata(self, topic):
        return {}

    def get_channel_info(self, topic):
        return _retrieve_channel_info_from_data(lambda: self.get_messages(topic))

    def get_message_type(self, topic: str):
        return self.message_type

    def get_messages(self, topic: str):
        if self._cache_messages and self._cached_messages is not None:
            yield from self._cached_messages
            return

        reader = BinaryTraceFileReader(message_type=self._msg_type_enum)
        if not reader.open(self._path):
            raise ValueError(f"Failed to open binary trace file '{self._path}'")
        try:
            messages = []
            while True:
                result = reader.read_message()
                if result is None:
                    break
                if self._cache_messages:
                    messages.append(result.message)
                yield result.message
            if self._cache_messages:
                self._cached_messages = messages
        finally:
            reader.close()

    def close(self):
        """Closes the adapter."""
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
