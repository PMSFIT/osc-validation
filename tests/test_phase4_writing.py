"""Integration tests: Phase 4 — Writing (F17-F22).

Tests verify ChannelWriter, MCAPTraceFileWriter, BinaryTraceFileWriter,
and OSIChannelWriter writing behaviour using SDK classes.
"""

import struct
import logging
import lzma
import pytest
from pathlib import Path

import google.protobuf

from tests.conftest import _make_sensor_view, _get_osi_version

from osc_validation.utils.osi_reader import OSIChannelReader as ChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter as ChannelWriter
from osi_utilities.tracefile._types import (
    ChannelSpecification,
    MESSAGE_TYPE_TO_CLASS_NAME,
)


def _osi_version_str():
    v = _get_osi_version()
    return f"{v.version_major}.{v.version_minor}.{v.version_patch}"


def _default_file_metadata():
    return {
        "version": "1.0.0",
        "min_osi_version": _osi_version_str(),
        "max_osi_version": _osi_version_str(),
        "min_protobuf_version": google.protobuf.__version__,
        "max_protobuf_version": google.protobuf.__version__,
    }


def _default_channel_metadata():
    return {
        "net.asam.osi.trace.channel.osi_version": _osi_version_str(),
        "net.asam.osi.trace.channel.protobuf_version": google.protobuf.__version__,
    }


# ===========================================================================
# F17: Binary write — OSITraceWriterSingle
# ===========================================================================


class TestF17BinaryWrite:
    """Verify binary .osi writing."""

    def test_single_write_creates_file(self, tmp_path):
        path = tmp_path / "output.osi"
        writer = ChannelWriter.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        )
        msg = _make_sensor_view(0.0)
        writer.write(msg)
        writer.close()
        assert path.exists()
        assert path.stat().st_size > 0

    def test_single_write_message_count(self, tmp_path):
        path = tmp_path / "output.osi"
        writer = ChannelWriter.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        )
        for i in range(5):
            writer.write(_make_sensor_view(i * 0.1))
        assert writer.written_count == 5
        writer.close()

    def test_single_write_binary_format(self, tmp_path):
        """Verify 4-byte LE length prefix + serialized bytes."""
        from osi_utilities.tracefile.binary_writer import BinaryTraceFileWriter

        path = tmp_path / "output.osi"
        writer = BinaryTraceFileWriter()
        writer.open(path)
        msg = _make_sensor_view(1.0)
        writer.write_message(msg)
        writer.close()

        data = path.read_bytes()
        expected_payload = msg.SerializeToString()
        expected_len = struct.pack("<L", len(expected_payload))
        assert data == expected_len + expected_payload

    def test_single_write_readback(self, tmp_path, sample_sensor_views):
        """Write with ChannelWriter, read back with ChannelReader, verify."""
        path = tmp_path / "roundtrip.osi"
        writer = ChannelWriter.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        )
        for msg in sample_sensor_views:
            writer.write(msg)
        writer.close()

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        )
        read_msgs = list(reader.get_messages())
        assert len(read_msgs) == 5
        for orig, read in zip(sample_sensor_views, read_msgs):
            assert orig.SerializeToString() == read.SerializeToString()
        reader.close()

    def test_single_bad_extension_raises(self, tmp_path):
        with pytest.raises(ValueError, match="extension"):
            ChannelWriter.from_specification(
                ChannelSpecification(
                    path=tmp_path / "bad.xyz", message_type="SensorView"
                )
            )

    def test_writer_message_type_map_covers_all(self):
        """Verify writer's message type resolution covers all expected types."""
        _NAME_TO_MESSAGE_TYPE = {v: k for k, v in MESSAGE_TYPE_TO_CLASS_NAME.items()}

        expected = {
            "SensorView",
            "SensorViewConfiguration",
            "GroundTruth",
            "HostVehicleData",
            "SensorData",
            "TrafficCommand",
            "TrafficCommandUpdate",
            "TrafficUpdate",
            "MotionRequest",
            "StreamingUpdate",
        }
        assert set(_NAME_TO_MESSAGE_TYPE.keys()) == expected


# ===========================================================================
# F18: Binary write — compression
# ===========================================================================


class TestF18BinaryCompression:
    """Verify .osi.xz compressed writing."""

    def test_compress_creates_file(self, tmp_path):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_writer import OSIChannelWriter

        path = tmp_path / "output.osi.xz"
        spec = ChannelSpecification(path=path, message_type="SensorView")
        writer = OSIChannelWriter.from_osi_channel_specification(spec)
        msg = _make_sensor_view(0.0)
        writer.write(msg)
        writer.close()
        assert path.exists()

    def test_compress_stores_lzma_payload(self, tmp_path):
        path = tmp_path / "output.osi.xz"
        msg = _make_sensor_view(0.0)
        with ChannelWriter.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        ) as writer:
            writer.write(msg)

        data = path.read_bytes()
        (payload_size,) = struct.unpack("<L", data[:4])
        payload = data[4 : 4 + payload_size]
        assert lzma.decompress(payload) == msg.SerializeToString()

    def test_compress_bad_extension_raises(self, tmp_path):
        """Verify unsupported file extension raises ValueError."""
        with pytest.raises(ValueError):
            ChannelWriter.from_specification(
                ChannelSpecification(
                    path=tmp_path / "output.csv", message_type="SensorView"
                )
            )


# ===========================================================================
# F19: MCAP write — OSITraceWriterMulti
# ===========================================================================


class TestF19McapWrite:
    """Verify MCAP writing with MCAPTraceFileWriter and ChannelWriter."""

    def test_multi_construct(self, tmp_path):
        from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter

        path = tmp_path / "output.mcap"
        writer = MCAPTraceFileWriter()
        writer.open(path, _default_file_metadata())
        writer.close()
        assert path.exists()

    def test_multi_write_and_readback(self, tmp_path, sample_sensor_views):
        from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter
        from osi3.osi_sensorview_pb2 import SensorView

        path = tmp_path / "output.mcap"
        writer = MCAPTraceFileWriter()
        writer.open(path, _default_file_metadata())
        writer.add_channel("SVTopic", SensorView, _default_channel_metadata())
        for msg in sample_sensor_views:
            writer.write_message(msg, "SVTopic")
        assert writer.written_count == 5
        writer.close()

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=path, topic="SVTopic")
        )
        read_msgs = list(reader.get_messages())
        assert len(read_msgs) == 5
        for orig, read in zip(sample_sensor_views, read_msgs):
            assert orig.SerializeToString() == read.SerializeToString()
        reader.close()

    def test_multi_bad_extension_raises(self, tmp_path):
        with pytest.raises(ValueError, match="extension"):
            ChannelWriter.from_specification(
                ChannelSpecification(
                    path=tmp_path / "bad.xyz", message_type="SensorView"
                )
            )

    def test_multi_existing_file_raises(self, tmp_path):
        path = tmp_path / "exists.mcap"
        path.write_bytes(b"data")
        with pytest.raises(ValueError, match="already exists"):
            ChannelWriter.from_specification(
                ChannelSpecification(path=path, message_type="SensorView")
            )

    def test_multi_duplicate_topic_raises(self, tmp_path):
        from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter
        from osi3.osi_sensorview_pb2 import SensorView

        path = tmp_path / "dup.mcap"
        writer = MCAPTraceFileWriter()
        writer.open(path, _default_file_metadata())
        writer.add_channel("SVTopic", SensorView, _default_channel_metadata())
        with pytest.raises(RuntimeError, match="already exists"):
            writer.add_channel("SVTopic", SensorView, _default_channel_metadata())
        writer.close()

    def test_multi_no_message_type_raises(self, tmp_path):
        path = tmp_path / "nomt.mcap"
        with pytest.raises(ValueError, match="[Mm]essage type"):
            ChannelWriter.from_specification(ChannelSpecification(path=path))

    def test_multi_write_bad_topic_raises(self, tmp_path):
        from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter
        from osi3.osi_sensorview_pb2 import SensorView

        path = tmp_path / "badtopic.mcap"
        writer = MCAPTraceFileWriter()
        writer.open(path, _default_file_metadata())
        writer.add_channel("SVTopic", SensorView, _default_channel_metadata())
        result = writer.write_message(_make_sensor_view(0.0), "WrongTopic")
        assert not result
        writer.close()

    def test_multi_context_manager(self, tmp_path):
        path = tmp_path / "ctx.mcap"
        spec = ChannelSpecification(
            path=path,
            message_type="SensorView",
            topic="T",
            metadata=_default_channel_metadata(),
        )
        with ChannelWriter.from_specification(spec) as writer:
            writer.write(_make_sensor_view(0.0))
        assert path.exists()

    def test_multi_get_channel_metadata(self, tmp_path):
        from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter
        from osi3.osi_sensorview_pb2 import SensorView

        path = tmp_path / "meta.mcap"
        chan_meta = _default_channel_metadata()
        writer = MCAPTraceFileWriter()
        writer.open(path, _default_file_metadata())
        writer.add_channel("T", SensorView, chan_meta)
        # Read back channel metadata via ChannelWriter wrapping
        spec = ChannelSpecification(
            path=tmp_path / "meta2.mcap",
            message_type="SensorView",
            topic="T",
            metadata=chan_meta,
        )
        cw = ChannelWriter.from_specification(spec)
        retrieved = cw.get_channel_metadata()
        assert (
            retrieved["net.asam.osi.trace.channel.osi_version"]
            == chan_meta["net.asam.osi.trace.channel.osi_version"]
        )
        cw.close()
        writer.close()

    def test_multi_add_channel_path_mismatch_raises(self, tmp_path):
        """Verify ChannelWriter validates extension-based format."""
        with pytest.raises(ValueError, match="extension"):
            ChannelWriter.from_specification(
                ChannelSpecification(
                    path=tmp_path / "different.xyz", message_type="SensorView"
                )
            )


# ===========================================================================
# F20: MCAP write — metadata validation
# ===========================================================================


class TestF20MetadataValidation:
    """Verify metadata validation warnings."""

    def test_validate_file_metadata_warns_missing_required(self, tmp_path, caplog):
        from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter

        path = tmp_path / "warn.mcap"
        incomplete_meta = {"version": "1.0.0"}
        writer = MCAPTraceFileWriter()
        with caplog.at_level(logging.WARNING):
            writer.open(path, incomplete_meta)
        assert any("net.asam.osi.trace" in r.message for r in caplog.records)
        writer.close()

    def test_validate_channel_metadata_warns_missing_required(self, tmp_path, caplog):
        from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter
        from osi3.osi_sensorview_pb2 import SensorView

        path = tmp_path / "chanwarn.mcap"
        writer = MCAPTraceFileWriter()
        writer.open(path, _default_file_metadata())
        with caplog.at_level(logging.WARNING):
            writer.add_channel("T", SensorView, {})
        assert any("channel" in r.message.lower() for r in caplog.records)
        writer.close()


# ===========================================================================
# F21: MCAP write — OSI version enforcement
# ===========================================================================


class TestF21VersionEnforcement:
    """Verify version mismatch raises ValueError on write."""

    def test_version_mismatch_raises(self, tmp_path):
        path = tmp_path / "vermis.mcap"
        spec = ChannelSpecification(
            path=path,
            message_type="SensorView",
            topic="T",
            metadata={
                "net.asam.osi.trace.channel.osi_version": "99.99.99",
                "net.asam.osi.trace.channel.protobuf_version": google.protobuf.__version__,
            },
        )
        writer = ChannelWriter.from_specification(spec)
        msg = _make_sensor_view(0.0)
        with pytest.raises(ValueError, match="does not match"):
            writer.write(msg)
        writer.close()

    def test_version_autofill_on_first_write(self, tmp_path, caplog):
        path = tmp_path / "autofill.mcap"
        spec = ChannelSpecification(
            path=path,
            message_type="SensorView",
            topic="T",
            metadata={
                "net.asam.osi.trace.channel.protobuf_version": google.protobuf.__version__
            },
        )
        writer = ChannelWriter.from_specification(spec)
        msg = _make_sensor_view(0.0)
        with caplog.at_level(logging.INFO):
            writer.write(msg)
        # Should have autofilled the version
        meta = writer.get_channel_metadata()
        assert "net.asam.osi.trace.channel.osi_version" in meta
        assert meta["net.asam.osi.trace.channel.osi_version"] == _osi_version_str()
        writer.close()

    def test_protobuf_version_mismatch_warns(self, tmp_path, caplog):
        path = tmp_path / "pbwarn.mcap"
        spec = ChannelSpecification(
            path=path,
            message_type="SensorView",
            topic="T",
            metadata={
                "net.asam.osi.trace.channel.osi_version": _osi_version_str(),
                "net.asam.osi.trace.channel.protobuf_version": "0.0.0",
            },
        )
        writer = ChannelWriter.from_specification(spec)
        msg = _make_sensor_view(0.0)
        with caplog.at_level(logging.WARNING):
            writer.write(msg)
        assert any("protobuf" in r.message.lower() for r in caplog.records)
        writer.close()


# ===========================================================================
# F22: OSIChannelWriter facade
# ===========================================================================


class TestF22WriterFacade:
    """Verify OSIChannelWriter facade for both .osi and .mcap."""

    def test_from_spec_osi(self, tmp_path, sample_sensor_views):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_writer import OSIChannelWriter

        path = tmp_path / "facade.osi"
        spec = ChannelSpecification(
            path=path,
            message_type="SensorView",
        )
        with OSIChannelWriter.from_osi_channel_specification(spec) as writer:
            for msg in sample_sensor_views:
                writer.write(msg)

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        )
        read_msgs = list(reader.get_messages())
        assert len(read_msgs) == 5
        reader.close()

    def test_from_spec_mcap(self, tmp_path, sample_sensor_views):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_writer import OSIChannelWriter

        path = tmp_path / "facade.mcap"
        spec = ChannelSpecification(
            path=path,
            message_type="SensorView",
            topic="SVTopic",
            metadata=_default_channel_metadata(),
        )
        with OSIChannelWriter.from_osi_channel_specification(spec) as writer:
            for msg in sample_sensor_views:
                writer.write(msg)

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=path, topic="SVTopic")
        )
        read_msgs = list(reader.get_messages())
        assert len(read_msgs) == 5
        reader.close()

    def test_facade_write_delegates(self, tmp_path):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_writer import OSIChannelWriter

        path = tmp_path / "delegate.osi"
        spec = ChannelSpecification(path=path, message_type="SensorView")
        writer = OSIChannelWriter.from_osi_channel_specification(spec)
        writer.write(_make_sensor_view(0.0))
        writer.close()
        assert path.stat().st_size > 0

    def test_facade_get_channel_specification(self, tmp_path):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_writer import OSIChannelWriter

        path = tmp_path / "spec_out.osi"
        spec = ChannelSpecification(path=path, message_type="SensorView")
        writer = OSIChannelWriter.from_osi_channel_specification(spec)
        writer.write(_make_sensor_view(0.0))
        out_spec = writer.get_channel_specification()
        assert out_spec.path == path
        assert out_spec.message_type == "SensorView"
        writer.close()

    def test_facade_context_manager(self, tmp_path):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_writer import OSIChannelWriter

        path = tmp_path / "ctx.osi"
        spec = ChannelSpecification(path=path, message_type="SensorView")
        with OSIChannelWriter.from_osi_channel_specification(spec) as writer:
            writer.write(_make_sensor_view(0.0))
        assert path.exists()
