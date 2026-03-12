"""Integration tests: Phase 3 — Reading (F10-F16).

Tests verify ChannelReader, MCAPTraceFileReader,
and OSIChannelReader reading behaviour using SDK classes.
"""

import struct
import pytest
from pathlib import Path

from tests.conftest import _make_sensor_view, _make_ground_truth, _write_binary_trace

from osc_validation.utils.osi_reader import OSIChannelReader as ChannelReader
from osi_utilities.tracefile._types import (
    ChannelSpecification,
    MESSAGE_TYPE_TO_CLASS_NAME,
)


# ===========================================================================
# F10: Binary read — ChannelReader
# ===========================================================================


class TestF10BinaryRead:
    """Verify ChannelReader reads binary .osi files correctly."""

    def test_adapter_construct(self, binary_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        assert reader.get_source_path() == binary_sv_trace
        assert reader.get_message_type() == "SensorView"
        reader.close()

    def test_adapter_get_messages_count(self, binary_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        messages = list(reader.get_messages())
        assert len(messages) == 5
        reader.close()

    def test_adapter_get_messages_content(self, binary_sv_trace, sample_sensor_views):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        messages = list(reader.get_messages())
        for original, read_back in zip(sample_sensor_views, messages):
            assert original.SerializeToString() == read_back.SerializeToString()
        reader.close()

    def test_adapter_get_available_topics(self, binary_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        topic = reader.get_topic_name()
        assert topic == binary_sv_trace.stem
        reader.close()

    def test_adapter_get_message_type(self, binary_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        assert reader.get_message_type() == "SensorView"
        reader.close()

    def test_adapter_get_file_metadata_empty(self, binary_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        assert reader.get_file_metadata() == {}
        reader.close()

    def test_adapter_get_channel_metadata_empty(self, binary_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        assert reader.get_channel_metadata() == {}
        reader.close()

    def test_adapter_get_channel_info(self, binary_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        info = reader.get_channel_info()
        assert info["total_steps"] == 5
        assert info["start"] == pytest.approx(0.0)
        assert info["stop"] == pytest.approx(0.4)
        assert info["step_size_avg"] == pytest.approx(0.1, abs=1e-6)
        reader.close()


# ===========================================================================
# F11: Binary read — edge cases
# ===========================================================================


class TestF11BinaryEdgeCases:
    """Edge cases for binary .osi reading."""

    def test_empty_file_yields_nothing(self, tmp_path):
        path = tmp_path / "empty.osi"
        path.write_bytes(b"")
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        )
        messages = list(reader.get_messages())
        assert len(messages) == 0
        reader.close()

    def test_single_message(self, tmp_path):
        path = tmp_path / "single.osi"
        msg = _make_sensor_view(1.0)
        _write_binary_trace(path, [msg])
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        )
        messages = list(reader.get_messages())
        assert len(messages) == 1
        assert messages[0].SerializeToString() == msg.SerializeToString()
        reader.close()

    def test_ground_truth_read(self, binary_gt_trace, sample_ground_truths):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_gt_trace, message_type="GroundTruth")
        )
        messages = list(reader.get_messages())
        assert len(messages) == 5
        for original, read_back in zip(sample_ground_truths, messages):
            assert original.SerializeToString() == read_back.SerializeToString()
        reader.close()


# ===========================================================================
# F12: MCAP read — MCAPTraceFileReader / ChannelReader
# ===========================================================================


class TestF12McapRead:
    """Verify MCAPTraceFileReader and ChannelReader read MCAP files correctly."""

    def test_multi_construct(self, mcap_sv_trace):
        from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader

        reader = MCAPTraceFileReader()
        assert reader.open(Path(str(mcap_sv_trace)))
        reader.close()

    def test_multi_get_messages_count(self, mcap_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        )
        messages = list(reader.get_messages())
        assert len(messages) == 5
        reader.close()

    def test_multi_get_messages_content(self, mcap_sv_trace, sample_sensor_views):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        )
        messages = list(reader.get_messages())
        for original, read_back in zip(sample_sensor_views, messages):
            assert original.SerializeToString() == read_back.SerializeToString()
        reader.close()

    def test_multi_invalid_topic_raises(self, mcap_sv_trace):
        with pytest.raises(ValueError, match="not found"):
            ChannelReader.from_specification(
                ChannelSpecification(path=mcap_sv_trace, topic="NonExistentTopic")
            )

    def test_multi_close(self, mcap_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        )
        reader.close()
        # No exception on double close expected behavior varies;
        # just verify it ran without error.


# ===========================================================================
# F13: MCAP read — topic listing & metadata
# ===========================================================================


class TestF13McapMetadata:
    """Verify topic listing, channel metadata, file metadata, message type."""

    def test_get_available_topics(self, mcap_sv_trace):
        from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader

        reader = MCAPTraceFileReader()
        reader.open(Path(str(mcap_sv_trace)))
        topics = reader.get_available_topics()
        assert "SensorViewTopic" in topics
        reader.close()

    def test_get_channel_metadata(self, mcap_sv_trace):
        from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader

        reader = MCAPTraceFileReader()
        reader.open(Path(str(mcap_sv_trace)))
        meta = reader.get_channel_metadata("SensorViewTopic")
        assert meta is not None
        assert "net.asam.osi.trace.channel.osi_version" in meta
        assert "net.asam.osi.trace.channel.protobuf_version" in meta
        reader.close()

    def test_get_channel_metadata_missing_topic(self, mcap_sv_trace):
        from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader

        reader = MCAPTraceFileReader()
        reader.open(Path(str(mcap_sv_trace)))
        meta = reader.get_channel_metadata("NonExistent")
        assert meta is None
        reader.close()

    def test_get_file_metadata(self, mcap_sv_trace):
        from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader

        reader = MCAPTraceFileReader()
        reader.open(Path(str(mcap_sv_trace)))
        file_meta = reader.get_file_metadata()
        assert len(file_meta) > 0
        reader.close()

    def test_get_message_type(self, mcap_sv_trace):
        from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader

        reader = MCAPTraceFileReader()
        reader.open(Path(str(mcap_sv_trace)))
        msg_type = reader.get_message_type_for_topic("SensorViewTopic")
        assert msg_type is not None
        assert MESSAGE_TYPE_TO_CLASS_NAME[msg_type] == "SensorView"
        reader.close()

    def test_get_message_type_missing_topic(self, mcap_sv_trace):
        from osi_utilities.tracefile.mcap_reader import MCAPTraceFileReader

        reader = MCAPTraceFileReader()
        reader.open(Path(str(mcap_sv_trace)))
        msg_type = reader.get_message_type_for_topic("NonExistent")
        assert msg_type is None
        reader.close()


# ===========================================================================
# F14: Channel info computation
# ===========================================================================


class TestF14ChannelInfo:
    """Verify channel info computation via ChannelReader.get_channel_info."""

    def test_channel_info_from_mcap(self, mcap_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        )
        info = reader.get_channel_info()
        assert info["total_steps"] == 5
        assert info["start"] == pytest.approx(0.0)
        assert info["stop"] == pytest.approx(0.4)
        assert info["step_size_avg"] == pytest.approx(0.1, abs=1e-6)
        assert "osi_version" in info
        assert "message_type" in info
        assert info["message_type"] == "SensorView"
        reader.close()

    def test_channel_info_from_binary(self, binary_sv_trace):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        )
        info = reader.get_channel_info()
        assert info["total_steps"] == 5
        assert "osi_version" in info
        reader.close()

    def test_print_summary_no_crash(self, mcap_sv_trace, capsys):
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        )
        reader.print_summary()
        captured = capsys.readouterr()
        assert "SensorView" in captured.out
        reader.close()


# ===========================================================================
# F15: OSIChannelReader facade — from_osi_channel_specification
# ===========================================================================


class TestF15ReaderFacade:
    """Verify OSIChannelReader facade for both .osi and .mcap."""

    def test_from_spec_osi(self, binary_sv_trace, sample_sensor_views):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            messages = list(reader)
            assert len(messages) == 5
            for orig, read in zip(sample_sensor_views, messages):
                assert orig.SerializeToString() == read.SerializeToString()

    def test_from_spec_mcap(self, mcap_sv_trace, sample_sensor_views):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(
            path=mcap_sv_trace,
            message_type="SensorView",
            topic="SensorViewTopic",
        )
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            messages = list(reader)
            assert len(messages) == 5
            for orig, read in zip(sample_sensor_views, messages):
                assert orig.SerializeToString() == read.SerializeToString()

    def test_from_spec_mcap_no_topic_uses_first(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace)
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            assert reader.get_topic_name() == "SensorViewTopic"
            messages = list(reader)
            assert len(messages) == 5

    def test_from_spec_osi_xz(self, tmp_path, sample_sensor_views):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader
        from osc_validation.utils.osi_writer import OSIChannelWriter

        spec = ChannelSpecification(
            path=tmp_path / "compressed_trace.osi.xz",
            message_type="SensorView",
        )
        with OSIChannelWriter.from_osi_channel_specification(spec) as writer:
            for message in sample_sensor_views:
                writer.write(message)

        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            messages = list(reader)
            assert len(messages) == len(sample_sensor_views)
            assert reader.get_topic_name() == "compressed_trace"
            for original, read_back in zip(sample_sensor_views, messages):
                assert original.SerializeToString() == read_back.SerializeToString()

    def test_from_spec_mcap_wrong_type_raises(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(
            path=mcap_sv_trace,
            message_type="GroundTruth",
            topic="SensorViewTopic",
        )
        with pytest.raises(ValueError, match="message type"):
            OSIChannelReader.from_osi_channel_specification(spec)

    def test_from_spec_missing_file_raises(self):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(
            path=Path("/nonexistent/file.osi"), message_type="SensorView"
        )
        with pytest.raises(FileNotFoundError):
            OSIChannelReader.from_osi_channel_specification(spec)

    def test_from_spec_osi_no_msg_type_raises(self, binary_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=binary_sv_trace)
        with pytest.raises(ValueError, match="message type"):
            OSIChannelReader.from_osi_channel_specification(spec)

    def test_from_single_trace(self, binary_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        reader = OSIChannelReader.from_osi_channel_specification(spec)
        messages = list(reader)
        assert len(messages) == 5
        reader.close()

    def test_from_multi_trace(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        reader = OSIChannelReader.from_osi_channel_specification(spec)
        messages = list(reader)
        assert len(messages) == 5
        reader.close()

    def test_from_multi_trace_bad_topic_raises(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace, topic="BadTopic")
        with pytest.raises(ValueError, match="not found"):
            OSIChannelReader.from_osi_channel_specification(spec)

    def test_get_source_path(self, binary_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            assert reader.get_source_path() == binary_sv_trace

    def test_get_topic_name(self, binary_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            topic = reader.get_topic_name()
            assert topic is not None

    def test_get_channel_specification(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            out_spec = reader.get_channel_specification()
            assert out_spec.path == mcap_sv_trace
            assert out_spec.topic == "SensorViewTopic"
            assert "net.asam.osi.trace.channel.osi_version" in out_spec.metadata


# ===========================================================================
# F16: OSIChannelReader — context manager & iteration
# ===========================================================================


class TestF16ReaderContextManager:
    """Verify context manager and iteration protocol."""

    def test_context_manager(self, binary_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            count = sum(1 for _ in reader)
        assert count == 5

    def test_iteration_yields_protobuf_messages(self, binary_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader
        from google.protobuf.message import Message

        spec = ChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            for msg in reader:
                assert isinstance(msg, Message)
                assert hasattr(msg, "timestamp")
                assert hasattr(msg, "sensor_id")

    def test_get_messages_returns_iterator(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            msgs = reader.get_messages()
            count = sum(1 for _ in msgs)
        assert count == 5

    def test_get_file_metadata_passthrough(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            meta = reader.get_file_metadata()
            assert len(meta) > 0

    def test_get_channel_metadata_passthrough(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            meta = reader.get_channel_metadata()
            assert "net.asam.osi.trace.channel.osi_version" in meta

    def test_get_channel_info_passthrough(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            info = reader.get_channel_info()
            assert info["total_steps"] == 5

    def test_get_channel_info_compressed_trace(self, tmp_path, sample_sensor_views):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader
        from osc_validation.utils.osi_writer import OSIChannelWriter

        spec = ChannelSpecification(
            path=tmp_path / "compressed_info.osi.xz",
            message_type="SensorView",
        )
        with OSIChannelWriter.from_osi_channel_specification(spec) as writer:
            for message in sample_sensor_views:
                writer.write(message)

        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            info = reader.get_channel_info()
            assert info["start"] == pytest.approx(0.0)
            assert info["stop"] == pytest.approx(0.4)
            assert info["total_steps"] == 5
            assert info["message_type"] == "SensorView"

    def test_get_message_type_passthrough(self, mcap_sv_trace):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_reader import OSIChannelReader

        spec = ChannelSpecification(path=mcap_sv_trace, topic="SensorViewTopic")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            assert reader.get_message_type() == "SensorView"
