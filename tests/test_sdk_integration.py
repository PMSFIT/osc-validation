"""Integration tests verifying osc_validation features backed by the SDK."""

import tempfile
from pathlib import Path

import pytest
from osi3.osi_sensorview_pb2 import SensorView
from osi3.osi_groundtruth_pb2 import GroundTruth

from osc_validation.utils.osi_reader import OSIChannelReader as ChannelReader


class _TimestampValue:
    def __init__(self, seconds: int, nanos: int):
        self.seconds = seconds
        self.nanos = nanos


def _seconds_to_timestamp(seconds: float) -> _TimestampValue:
    whole_seconds = int(seconds)
    nanos = int(round((seconds - whole_seconds) * 1e9))
    if nanos == 1_000_000_000:
        whole_seconds += 1
        nanos = 0
    return _TimestampValue(whole_seconds, nanos)


def _make_sv(seconds: int, nanos: int = 0) -> SensorView:
    sv = SensorView()
    sv.timestamp.seconds = seconds
    sv.timestamp.nanos = nanos
    sv.version.version_major = 3
    sv.version.version_minor = 7
    sv.version.version_patch = 0
    return sv


def _make_gt(seconds: int, nanos: int = 0) -> GroundTruth:
    gt = GroundTruth()
    gt.timestamp.seconds = seconds
    gt.timestamp.nanos = nanos
    gt.version.version_major = 3
    gt.version.version_minor = 7
    gt.version.version_patch = 0
    return gt


@pytest.fixture()
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _write_binary(path, msgs):
    from osi_utilities.tracefile.binary_writer import BinaryTraceFileWriter

    writer = BinaryTraceFileWriter()
    writer.open(path)
    for m in msgs:
        writer.write_message(m)
    writer.close()


def _write_mcap(path, msgs, topic="sv"):
    from osi_utilities.tracefile.mcap_writer import MCAPTraceFileWriter

    writer = MCAPTraceFileWriter()
    writer.open(path, {})
    writer.add_channel(topic, type(msgs[0]))
    for m in msgs:
        writer.write_message(m, topic)
    writer.close()


# ===========================================================================
# timestamp conversion interoperability
# ===========================================================================


class TestTimestampIntegration:
    """Test timestamp helpers used alongside the SDK."""

    def test_seconds_to_timestamp_basic(self):
        ts = _seconds_to_timestamp(1.5)
        assert ts.seconds == 1
        assert ts.nanos == 500_000_000

    def test_seconds_to_timestamp_zero(self):
        ts = _seconds_to_timestamp(0.0)
        assert ts.seconds == 0
        assert ts.nanos == 0

    def test_roundtrip(self):
        from osi_utilities.tracefile.timestamp import timestamp_to_seconds

        original = 3.14159
        ts = _seconds_to_timestamp(original)
        msg = SensorView()
        msg.timestamp.seconds = ts.seconds
        msg.timestamp.nanos = ts.nanos
        back = timestamp_to_seconds(msg)
        assert abs(back - original) < 1e-6


# ===========================================================================
# compute_channel_info via compatibility reader
# ===========================================================================


class TestChannelInfoIntegration:
    def test_binary_channel_info(self, tmp_dir):
        path = tmp_dir / "trace.osi"
        _write_binary(path, [_make_sv(i) for i in range(5)])

        from osi_utilities.tracefile._types import ChannelSpecification

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=path, message_type="SensorView")
        )
        info = reader.get_channel_info()
        assert info["start"] == 0.0
        assert info["stop"] == 4.0
        assert info["total_steps"] == 5
        assert info["osi_version"] == "3.7.0"
        reader.close()

    def test_mcap_channel_info(self, tmp_dir):
        path = tmp_dir / "trace.mcap"
        _write_mcap(path, [_make_sv(i) for i in range(3)], topic="sv")

        from osi_utilities.tracefile._types import ChannelSpecification

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=path, topic="sv")
        )
        info = reader.get_channel_info()
        assert info["start"] == 0.0
        assert info["stop"] == 2.0
        assert info["total_steps"] == 3
        assert "message_type" in info
        reader.close()

    def test_channel_reader_channel_info(self, tmp_dir):
        path = tmp_dir / "trace.osi"
        _write_binary(path, [_make_sv(i) for i in range(4)])

        from osc_validation.utils.osi_reader import OSIChannelReader
        from osi_utilities import ChannelSpecification

        spec = ChannelSpecification(path=path, message_type="SensorView")
        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            info = reader.get_channel_info()
        assert info["total_steps"] == 4

    def test_compressed_binary_channel_info(self, tmp_dir):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_writer import OSIChannelWriter

        path = tmp_dir / "trace.osi.xz"
        spec = ChannelSpecification(path=path, message_type="SensorView")
        with OSIChannelWriter.from_osi_channel_specification(spec) as writer:
            for i in range(4):
                writer.write(_make_sv(i))

        with ChannelReader.from_specification(spec) as reader:
            info = reader.get_channel_info()
        assert info["start"] == 0.0
        assert info["stop"] == 3.0
        assert info["total_steps"] == 4


# ===========================================================================
# Format converter compatibility wrapper
# ===========================================================================


class TestFormatConverterIntegration:
    def test_binary_to_mcap(self, tmp_dir):
        src = tmp_dir / "source.osi"
        _write_binary(src, [_make_sv(i) for i in range(3)])

        from osc_validation.utils.osi_format_converter import convert
        from osi_utilities import ChannelSpecification

        in_spec = ChannelSpecification(path=src, message_type="SensorView")
        dst = tmp_dir / "dest.mcap"
        out_spec = ChannelSpecification(path=dst, message_type="SensorView", topic="sv")
        result = convert(in_spec, out_spec)
        assert result.path.exists()

        from osc_validation.utils.osi_reader import OSIChannelReader

        with ChannelReader.from_osi_channel_specification(result) as reader:
            msgs = list(reader)
        assert len(msgs) == 3

    def test_mcap_to_binary(self, tmp_dir):
        src = tmp_dir / "source.mcap"
        _write_mcap(src, [_make_sv(i) for i in range(3)], topic="sv")

        from osc_validation.utils.osi_format_converter import convert
        from osi_utilities import ChannelSpecification

        in_spec = ChannelSpecification(path=src, message_type="SensorView", topic="sv")
        dst = tmp_dir / "dest.osi"
        out_spec = ChannelSpecification(path=dst, message_type="SensorView")
        result = convert(in_spec, out_spec)
        assert result.path.exists()

        from osc_validation.utils.osi_reader import OSIChannelReader

        with ChannelReader.from_osi_channel_specification(result) as reader:
            msgs = list(reader)
        assert len(msgs) == 3

    def test_compressed_binary_to_mcap(self, tmp_dir):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_format_converter import convert
        from osc_validation.utils.osi_writer import OSIChannelWriter

        src = tmp_dir / "source.osi.xz"
        in_spec = ChannelSpecification(path=src, message_type="SensorView")
        with OSIChannelWriter.from_osi_channel_specification(in_spec) as writer:
            for i in range(3):
                writer.write(_make_sv(i))

        dst = tmp_dir / "dest.mcap"
        out_spec = ChannelSpecification(path=dst, message_type="SensorView", topic="sv")
        result = convert(in_spec, out_spec)
        assert result.path.exists()

        with ChannelReader.from_osi_channel_specification(result) as reader:
            msgs = list(reader)
        assert len(msgs) == 3


# ===========================================================================
# crop_trace compatibility wrapper
# ===========================================================================


class TestCropTraceIntegration:
    """Test SDK crop_trace that replaces osc_validation crop_trace."""

    def test_crop_with_interval(self, tmp_dir):
        src = tmp_dir / "source.osi"
        _write_binary(src, [_make_sv(i) for i in range(10)])

        from osi_utilities import ChannelSpecification
        from osc_validation.utils.utils import crop_trace

        in_spec = ChannelSpecification(path=src, message_type="SensorView")
        dst = tmp_dir / "cropped.osi"
        out_spec = ChannelSpecification(path=dst, message_type="SensorView")
        result = crop_trace(in_spec, out_spec, start_time=3.0, end_time=7.0)

        from osc_validation.utils.osi_reader import OSIChannelReader

        with OSIChannelReader.from_osi_channel_specification(
            ChannelSpecification(path=result.path, message_type="SensorView")
        ) as reader:
            msgs = list(reader)
        assert len(msgs) == 5  # seconds 3, 4, 5, 6, 7

    def test_crop_no_bounds(self, tmp_dir):
        src = tmp_dir / "source.osi"
        _write_binary(src, [_make_sv(i) for i in range(5)])

        from osi_utilities import ChannelSpecification
        from osc_validation.utils.utils import crop_trace

        in_spec = ChannelSpecification(path=src, message_type="SensorView")
        dst = tmp_dir / "cropped.osi"
        out_spec = ChannelSpecification(path=dst, message_type="SensorView")
        crop_trace(in_spec, out_spec)

        from osc_validation.utils.osi_reader import OSIChannelReader

        with OSIChannelReader.from_osi_channel_specification(
            ChannelSpecification(path=dst, message_type="SensorView")
        ) as reader:
            msgs = list(reader)
        assert len(msgs) == 5

    def test_crop_start_only(self, tmp_dir):
        src = tmp_dir / "source.osi"
        _write_binary(src, [_make_sv(i) for i in range(5)])

        from osi_utilities import ChannelSpecification
        from osc_validation.utils.utils import crop_trace

        in_spec = ChannelSpecification(path=src, message_type="SensorView")
        dst = tmp_dir / "cropped.osi"
        out_spec = ChannelSpecification(path=dst, message_type="SensorView")
        crop_trace(in_spec, out_spec, start_time=2.0)

        from osc_validation.utils.osi_reader import OSIChannelReader

        with OSIChannelReader.from_osi_channel_specification(
            ChannelSpecification(path=dst, message_type="SensorView")
        ) as reader:
            msgs = list(reader)
        assert len(msgs) == 3  # seconds 2, 3, 4

    def test_crop_compressed_binary(self, tmp_dir):
        from osi_utilities import ChannelSpecification
        from osc_validation.utils.osi_writer import OSIChannelWriter
        from osc_validation.utils.utils import crop_trace

        src = tmp_dir / "source.osi.xz"
        in_spec = ChannelSpecification(path=src, message_type="SensorView")
        with OSIChannelWriter.from_osi_channel_specification(in_spec) as writer:
            for i in range(10):
                writer.write(_make_sv(i))

        dst = tmp_dir / "cropped.osi"
        out_spec = ChannelSpecification(path=dst, message_type="SensorView")
        crop_trace(in_spec, out_spec, start_time=3.0, end_time=7.0)

        with ChannelReader.from_osi_channel_specification(out_spec) as reader:
            msgs = list(reader)
        assert len(msgs) == 5


# ===========================================================================
# Reader/Writer round-trip through OSIChannelReader/Writer
# ===========================================================================


class TestReaderWriterIntegration:
    def test_binary_roundtrip_via_channel_api(self, tmp_dir):
        """Write via OSIChannelWriter, read via OSIChannelReader."""
        from osc_validation.utils.osi_reader import OSIChannelReader
        from osc_validation.utils.osi_writer import OSIChannelWriter
        from osi_utilities import ChannelSpecification

        path = tmp_dir / "trace.osi"
        spec = ChannelSpecification(path=path, message_type="SensorView")
        with OSIChannelWriter.from_osi_channel_specification(spec) as writer:
            for i in range(5):
                writer.write(_make_sv(i))

        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            msgs = list(reader)
        assert len(msgs) == 5
        for i, msg in enumerate(msgs):
            assert msg.timestamp.seconds == i

    def test_mcap_roundtrip_via_channel_api(self, tmp_dir):
        from osc_validation.utils.osi_reader import OSIChannelReader
        from osc_validation.utils.osi_writer import OSIChannelWriter
        from osi_utilities import ChannelSpecification

        path = tmp_dir / "trace.mcap"
        spec = ChannelSpecification(path=path, message_type="SensorView", topic="sv")
        with OSIChannelWriter.from_osi_channel_specification(spec) as writer:
            for i in range(5):
                writer.write(_make_sv(i))

        with OSIChannelReader.from_osi_channel_specification(spec) as reader:
            msgs = list(reader)
        assert len(msgs) == 5
