"""Integration tests: Phase 5 — Higher-level Operations (F23-F26).

Tests verify format converter, esminigt2sv, strip_sensorview,
and utils.py domain functions using SDK reader/writer classes.
"""

import struct
import math
import pytest
from pathlib import Path

import google.protobuf

from tests.conftest import (
    _make_sensor_view,
    _make_ground_truth,
    _write_binary_trace,
    _get_osi_version,
)

from osi_utilities.tracefile.channel_reader import ChannelReader
from osi_utilities.tracefile._types import ChannelSpecification


def _osi_version_str():
    v = _get_osi_version()
    return f"{v.version_major}.{v.version_minor}.{v.version_patch}"


def _default_channel_metadata():
    return {
        "net.asam.osi.trace.channel.osi_version": _osi_version_str(),
        "net.asam.osi.trace.channel.protobuf_version": google.protobuf.__version__,
    }


# ===========================================================================
# F23: osi_format_converter.convert()
# ===========================================================================


class TestF23FormatConverter:
    """Verify format conversion between .osi and .mcap."""

    def test_osi_to_mcap(self, tmp_path, sample_sensor_views):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.osi_format_converter import convert

        osi_path = tmp_path / "input_sv.osi"
        _write_binary_trace(osi_path, sample_sensor_views)

        mcap_path = tmp_path / "output_sv.mcap"
        input_spec = OSIChannelSpecification(
            path=osi_path, message_type="SensorView",
        )
        output_spec = OSIChannelSpecification(
            path=mcap_path, message_type="SensorView", topic="SVTopic",
            metadata=_default_channel_metadata(),
        )
        result_spec = convert(input_spec, output_spec)
        assert mcap_path.exists()
        assert result_spec.path == mcap_path

        # Read back and verify content
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=mcap_path, topic="SVTopic")
        )
        read_msgs = list(reader.get_messages())
        assert len(read_msgs) == 5
        for orig, read in zip(sample_sensor_views, read_msgs):
            assert orig.SerializeToString() == read.SerializeToString()
        reader.close()

    def test_mcap_to_osi(self, mcap_sv_trace, tmp_path, sample_sensor_views):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.osi_format_converter import convert

        osi_path = tmp_path / "output_sv.osi"
        input_spec = OSIChannelSpecification(
            path=mcap_sv_trace, message_type="SensorView", topic="SensorViewTopic",
        )
        output_spec = OSIChannelSpecification(
            path=osi_path, message_type="SensorView",
        )
        result_spec = convert(input_spec, output_spec)
        assert osi_path.exists()

        # Read back and verify content
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=osi_path, message_type="SensorView")
        )
        read_msgs = list(reader.get_messages())
        assert len(read_msgs) == 5
        for orig, read in zip(sample_sensor_views, read_msgs):
            assert orig.SerializeToString() == read.SerializeToString()
        reader.close()

    def test_roundtrip_osi_mcap_osi(self, tmp_path, sample_sensor_views):
        """osi -> mcap -> osi, verify messages identical to original."""
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.osi_format_converter import convert

        osi_1 = tmp_path / "step1.osi"
        _write_binary_trace(osi_1, sample_sensor_views)

        mcap = tmp_path / "step2.mcap"
        osi_2 = tmp_path / "step3.osi"

        convert(
            OSIChannelSpecification(path=osi_1, message_type="SensorView"),
            OSIChannelSpecification(
                path=mcap, message_type="SensorView", topic="T",
                metadata=_default_channel_metadata(),
            ),
        )
        convert(
            OSIChannelSpecification(path=mcap, message_type="SensorView", topic="T"),
            OSIChannelSpecification(path=osi_2, message_type="SensorView"),
        )

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=osi_2, message_type="SensorView")
        )
        roundtrip_msgs = list(reader.get_messages())
        assert len(roundtrip_msgs) == 5
        for orig, rt in zip(sample_sensor_views, roundtrip_msgs):
            assert orig.SerializeToString() == rt.SerializeToString()
        reader.close()


# ===========================================================================
# F24: esminigt2sv.gt2sv()
# ===========================================================================


class TestF24EsminiGt2Sv:
    """Verify esmini GT to SV conversion."""

    def test_gt2sv_message_count(self, tmp_path, sample_ground_truths):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.esminigt2sv import gt2sv

        gt_path = tmp_path / "input_gt.osi"
        _write_binary_trace(gt_path, sample_ground_truths)
        sv_path = tmp_path / "output_sv.osi"

        gt_spec = OSIChannelSpecification(path=gt_path, message_type="GroundTruth")
        sv_spec = OSIChannelSpecification(path=sv_path, message_type="SensorView")
        gt2sv(gt_spec, sv_spec)

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=sv_path, message_type="SensorView")
        )
        sv_msgs = list(reader.get_messages())
        assert len(sv_msgs) == 5
        reader.close()

    def test_gt2sv_sensor_id(self, tmp_path, sample_ground_truths):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.esminigt2sv import gt2sv

        gt_path = tmp_path / "input_gt.osi"
        _write_binary_trace(gt_path, sample_ground_truths)
        sv_path = tmp_path / "output_sv.osi"

        gt2sv(
            OSIChannelSpecification(path=gt_path, message_type="GroundTruth"),
            OSIChannelSpecification(path=sv_path, message_type="SensorView"),
        )

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=sv_path, message_type="SensorView")
        )
        for msg in reader.get_messages():
            assert msg.sensor_id.value == 10000
        reader.close()

    def test_gt2sv_mounting_position(self, tmp_path, sample_ground_truths):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.esminigt2sv import gt2sv

        gt_path = tmp_path / "input_gt.osi"
        _write_binary_trace(gt_path, sample_ground_truths)
        sv_path = tmp_path / "output_sv.osi"

        gt2sv(
            OSIChannelSpecification(path=gt_path, message_type="GroundTruth"),
            OSIChannelSpecification(path=sv_path, message_type="SensorView"),
        )

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=sv_path, message_type="SensorView")
        )
        for msg in reader.get_messages():
            assert msg.mounting_position.position.x == 0
            assert msg.mounting_position.position.y == 0
            assert msg.mounting_position.position.z == 0
        reader.close()

    def test_gt2sv_version_stamped(self, tmp_path, sample_ground_truths):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.esminigt2sv import gt2sv

        gt_path = tmp_path / "input_gt.osi"
        _write_binary_trace(gt_path, sample_ground_truths)
        sv_path = tmp_path / "output_sv.osi"

        gt2sv(
            OSIChannelSpecification(path=gt_path, message_type="GroundTruth"),
            OSIChannelSpecification(path=sv_path, message_type="SensorView"),
        )

        version = _get_osi_version()
        reader = ChannelReader.from_specification(
            ChannelSpecification(path=sv_path, message_type="SensorView")
        )
        for msg in reader.get_messages():
            assert msg.version.version_major == version.version_major
            assert msg.version.version_minor == version.version_minor
            assert msg.version.version_patch == version.version_patch
        reader.close()

    def test_gt2sv_host_vehicle_id_copied(self, tmp_path, sample_ground_truths):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.esminigt2sv import gt2sv

        gt_path = tmp_path / "input_gt.osi"
        _write_binary_trace(gt_path, sample_ground_truths)
        sv_path = tmp_path / "output_sv.osi"

        gt2sv(
            OSIChannelSpecification(path=gt_path, message_type="GroundTruth"),
            OSIChannelSpecification(path=sv_path, message_type="SensorView"),
        )

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=sv_path, message_type="SensorView")
        )
        for i, msg in enumerate(reader.get_messages()):
            assert msg.host_vehicle_id.value == sample_ground_truths[i].host_vehicle_id.value
        reader.close()

    def test_gt2sv_ground_truth_embedded(self, tmp_path, sample_ground_truths):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.esminigt2sv import gt2sv

        gt_path = tmp_path / "input_gt.osi"
        _write_binary_trace(gt_path, sample_ground_truths)
        sv_path = tmp_path / "output_sv.osi"

        gt2sv(
            OSIChannelSpecification(path=gt_path, message_type="GroundTruth"),
            OSIChannelSpecification(path=sv_path, message_type="SensorView"),
        )

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=sv_path, message_type="SensorView")
        )
        sv_msgs = list(reader.get_messages())
        for i, sv in enumerate(sv_msgs):
            gt = sample_ground_truths[i]
            assert len(sv.global_ground_truth.moving_object) == len(gt.moving_object)
            for sv_mo, gt_mo in zip(sv.global_ground_truth.moving_object, gt.moving_object):
                assert sv_mo.id.value == gt_mo.id.value
                assert sv_mo.base.position.x == pytest.approx(gt_mo.base.position.x)
        reader.close()


# ===========================================================================
# F25: strip_sensorview
# ===========================================================================


class TestF25StripSensorView:
    """Verify field stripping from SensorView traces."""

    def _make_sv_with_gt_fields(self, timestamp_s):
        """Create a SensorView with populated ground truth fields."""
        from osi3 import osi_sensorview_pb2

        sv = _make_sensor_view(timestamp_s)
        lb = sv.global_ground_truth.lane_boundary.add()
        lb.id.value = 100
        lane = sv.global_ground_truth.lane.add()
        lane.id.value = 200
        return sv

    def test_strip_lane_boundary(self, tmp_path):
        from osc_validation.utils.strip_sensorview import strip
        import argparse

        in_path = tmp_path / "in.osi"
        out_path = tmp_path / "out.osi"
        msgs = [self._make_sv_with_gt_fields(i * 0.1) for i in range(3)]
        _write_binary_trace(in_path, msgs)

        args = argparse.Namespace(
            lane_boundary=True, reference_line=False, logical_lane=False,
            logical_lane_boundary=False, lane=False, environmental_conditions=False,
        )
        strip(in_path, out_path, args)

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=out_path, message_type="SensorView")
        )
        for msg in reader.get_messages():
            assert len(msg.global_ground_truth.lane_boundary) == 0
            # lane should be preserved
            assert len(msg.global_ground_truth.lane) > 0
        reader.close()

    def test_strip_lane(self, tmp_path):
        from osc_validation.utils.strip_sensorview import strip
        import argparse

        in_path = tmp_path / "in.osi"
        out_path = tmp_path / "out.osi"
        msgs = [self._make_sv_with_gt_fields(i * 0.1) for i in range(3)]
        _write_binary_trace(in_path, msgs)

        args = argparse.Namespace(
            lane_boundary=False, reference_line=False, logical_lane=False,
            logical_lane_boundary=False, lane=True, environmental_conditions=False,
        )
        strip(in_path, out_path, args)

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=out_path, message_type="SensorView")
        )
        for msg in reader.get_messages():
            assert len(msg.global_ground_truth.lane) == 0
            # lane_boundary should be preserved
            assert len(msg.global_ground_truth.lane_boundary) > 0
        reader.close()

    def test_strip_preserves_other_fields(self, tmp_path):
        from osc_validation.utils.strip_sensorview import strip
        import argparse

        in_path = tmp_path / "in.osi"
        out_path = tmp_path / "out.osi"
        msgs = [self._make_sv_with_gt_fields(i * 0.1) for i in range(3)]
        _write_binary_trace(in_path, msgs)

        args = argparse.Namespace(
            lane_boundary=True, reference_line=False, logical_lane=False,
            logical_lane_boundary=False, lane=False, environmental_conditions=False,
        )
        strip(in_path, out_path, args)

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=out_path, message_type="SensorView")
        )
        for msg in reader.get_messages():
            # moving objects should be preserved
            assert len(msg.global_ground_truth.moving_object) > 0
            assert msg.sensor_id.value == 42
        reader.close()

    def test_strip_reference_line(self, tmp_path):
        from osc_validation.utils.strip_sensorview import strip
        import argparse

        in_path = tmp_path / "in.osi"
        out_path = tmp_path / "out.osi"
        sv = _make_sensor_view(0.0)
        rl = sv.global_ground_truth.reference_line.add()
        rl.id.value = 300
        _write_binary_trace(in_path, [sv])

        args = argparse.Namespace(
            lane_boundary=False, reference_line=True, logical_lane=False,
            logical_lane_boundary=False, lane=False, environmental_conditions=False,
        )
        strip(in_path, out_path, args)

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=out_path, message_type="SensorView")
        )
        for msg in reader.get_messages():
            assert len(msg.global_ground_truth.reference_line) == 0
        reader.close()

    def test_strip_environmental_conditions(self, tmp_path):
        from osc_validation.utils.strip_sensorview import strip
        import argparse

        in_path = tmp_path / "in.osi"
        out_path = tmp_path / "out.osi"
        sv = _make_sensor_view(0.0)
        sv.global_ground_truth.environmental_conditions.atmospheric_pressure = 101325.0
        _write_binary_trace(in_path, [sv])

        args = argparse.Namespace(
            lane_boundary=False, reference_line=False, logical_lane=False,
            logical_lane_boundary=False, lane=False, environmental_conditions=True,
        )
        strip(in_path, out_path, args)

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=out_path, message_type="SensorView")
        )
        for msg in reader.get_messages():
            assert msg.global_ground_truth.environmental_conditions.atmospheric_pressure == 0.0
        reader.close()


# ===========================================================================
# F26: utils.py domain functions
# ===========================================================================


class TestF26UtilsDomain:
    """Verify domain-specific utility functions."""

    def test_timestamp_osi_to_float(self):
        from osi3 import osi_common_pb2
        from osc_validation.utils.utils import timestamp_osi_to_float

        ts = osi_common_pb2.Timestamp()
        ts.seconds = 10
        ts.nanos = 500000000
        assert timestamp_osi_to_float(ts) == pytest.approx(10.5)

    def test_timestamp_osi_to_float_zero(self):
        from osi3 import osi_common_pb2
        from osc_validation.utils.utils import timestamp_osi_to_float

        ts = osi_common_pb2.Timestamp()
        assert timestamp_osi_to_float(ts) == 0.0

    def test_timestamp_float_to_osi(self):
        from osc_validation.utils.utils import timestamp_float_to_osi

        ts = timestamp_float_to_osi(10.5)
        assert ts.seconds == 10
        assert ts.nanos == 500000000

    def test_timestamp_float_to_osi_zero(self):
        from osc_validation.utils.utils import timestamp_float_to_osi

        ts = timestamp_float_to_osi(0.0)
        assert ts.seconds == 0
        assert ts.nanos == 0

    def test_timestamp_roundtrip(self):
        from osi3 import osi_common_pb2
        from osc_validation.utils.utils import timestamp_osi_to_float, timestamp_float_to_osi

        original = osi_common_pb2.Timestamp()
        original.seconds = 42
        original.nanos = 123456789

        float_val = timestamp_osi_to_float(original)
        roundtrip = timestamp_float_to_osi(float_val)
        assert roundtrip.seconds == original.seconds
        assert roundtrip.nanos == pytest.approx(original.nanos, abs=1)

    def test_get_all_moving_object_ids(self, tmp_path):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.utils import get_all_moving_object_ids

        # Create trace with 2 different moving objects
        from tests.conftest import _make_sensor_view
        msgs = []
        for i in range(3):
            sv = _make_sensor_view(i * 0.1, obj_id=1)
            mo2 = sv.global_ground_truth.moving_object.add()
            mo2.id.value = 2
            mo2.base.position.x = 100.0
            msgs.append(sv)

        path = tmp_path / "multi_mo.osi"
        _write_binary_trace(path, msgs)

        spec = OSIChannelSpecification(path=path, message_type="SensorView")
        ids = get_all_moving_object_ids(spec)
        assert set(ids) == {1, 2}

    def test_get_trajectory_by_moving_object_id(self, tmp_path):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.utils import get_trajectory_by_moving_object_id

        msgs = [_make_sensor_view(i * 0.1, obj_id=1) for i in range(5)]
        path = tmp_path / "traj.osi"
        _write_binary_trace(path, msgs)

        spec = OSIChannelSpecification(path=path, message_type="SensorView")
        traj = get_trajectory_by_moving_object_id(spec, 1)
        assert len(traj) == 5
        assert "timestamp" in traj.columns
        assert "x" in traj.columns
        assert "y" in traj.columns
        assert traj.attrs.get("id") == 1

    def test_get_trajectory_with_interval(self, tmp_path):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.utils import get_trajectory_by_moving_object_id

        msgs = [_make_sensor_view(i * 0.1, obj_id=1) for i in range(10)]
        path = tmp_path / "traj_interval.osi"
        _write_binary_trace(path, msgs)

        spec = OSIChannelSpecification(path=path, message_type="SensorView")
        traj = get_trajectory_by_moving_object_id(spec, 1, start_time=0.2, end_time=0.5)
        assert len(traj) == 4  # timestamps 0.2, 0.3, 0.4, 0.5

    def test_crop_trace(self, tmp_path, sample_sensor_views):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.utils import crop_trace

        in_path = tmp_path / "full.osi"
        _write_binary_trace(in_path, sample_sensor_views)
        out_path = tmp_path / "cropped.osi"

        crop_trace(
            OSIChannelSpecification(path=in_path, message_type="SensorView"),
            OSIChannelSpecification(path=out_path, message_type="SensorView"),
        )

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=out_path, message_type="SensorView")
        )
        cropped = list(reader.get_messages())
        assert len(cropped) == 5  # no interval = all messages
        reader.close()

    def test_crop_trace_with_interval(self, tmp_path):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
        from osc_validation.utils.utils import crop_trace

        msgs = [_make_sensor_view(i * 0.1) for i in range(10)]
        in_path = tmp_path / "full.osi"
        _write_binary_trace(in_path, msgs)
        out_path = tmp_path / "cropped.osi"

        crop_trace(
            OSIChannelSpecification(path=in_path, message_type="SensorView"),
            OSIChannelSpecification(path=out_path, message_type="SensorView"),
            start_time=0.2,
            end_time=0.5,
        )

        reader = ChannelReader.from_specification(
            ChannelSpecification(path=out_path, message_type="SensorView")
        )
        cropped = list(reader.get_messages())
        assert len(cropped) == 4  # 0.2, 0.3, 0.4, 0.5
        reader.close()

    def test_rotate_point_zyx_identity(self):
        from osc_validation.utils.utils import rotatePointZYX

        rx, ry, rz = rotatePointZYX(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert rx == pytest.approx(1.0)
        assert ry == pytest.approx(0.0)
        assert rz == pytest.approx(0.0)

    def test_rotate_point_zyx_90_yaw(self):
        from osc_validation.utils.utils import rotatePointZYX

        rx, ry, rz = rotatePointZYX(1.0, 0.0, 0.0, math.pi / 2, 0.0, 0.0)
        assert rx == pytest.approx(0.0, abs=1e-10)
        assert ry == pytest.approx(1.0, abs=1e-10)
        assert rz == pytest.approx(0.0, abs=1e-10)

    def test_rotate_point_xyz_identity(self):
        from osc_validation.utils.utils import rotatePointXYZ

        rx, ry, rz = rotatePointXYZ(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert rx == pytest.approx(1.0)
        assert ry == pytest.approx(0.0)
        assert rz == pytest.approx(0.0)

    def test_rotate_point_xyz_90_yaw(self):
        from osc_validation.utils.utils import rotatePointXYZ

        rx, ry, rz = rotatePointXYZ(1.0, 0.0, 0.0, math.pi / 2, 0.0, 0.0)
        assert rx == pytest.approx(0.0, abs=1e-10)
        assert ry == pytest.approx(1.0, abs=1e-10)
        assert rz == pytest.approx(0.0, abs=1e-10)
