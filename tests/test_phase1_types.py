"""Integration tests: Phase 1 — Shared Types & Constants (F01-F04).

Each test captures the CURRENT behavior of osc_validation utilities,
then verifies the SDK produces identical results. After migration,
these tests validate nothing is broken.
"""

import pytest
from pathlib import Path

# ===========================================================================
# F01: TraceFileFormat enum parity
# ===========================================================================


class TestF01TraceFileFormat:
    """Verify SDK TraceFileFormat has same members and values as osc_validation."""

    def test_enum_members_match(self):
        from osc_validation.utils.osi_channel_specification import TraceFileFormat as OldTFF
        from osi_utilities.tracefile._types import TraceFileFormat as SdkTFF

        assert OldTFF.SINGLE_CHANNEL.value == SdkTFF.SINGLE_CHANNEL.value
        assert OldTFF.MULTI_CHANNEL.value == SdkTFF.MULTI_CHANNEL.value

    def test_enum_member_count(self):
        from osc_validation.utils.osi_channel_specification import TraceFileFormat as OldTFF
        from osi_utilities.tracefile._types import TraceFileFormat as SdkTFF

        assert len(OldTFF) == len(SdkTFF)


# ===========================================================================
# F02: parse_osi_trace_filename parity
# ===========================================================================


class TestF02ParseOsiTraceFilename:
    """Verify SDK parse_osi_trace_filename returns identical results."""

    VALID_FILENAMES = [
        "20240101T120000Z_sv_3.7.0_5.29.0_100_test.osi",
        "20230615T093045Z_gt_3.6.0_4.25.0_50_mydata.osi",
        "20250101T000000Z_svc_3.8.0_5.30.0_1_config.osi",
        "20240701T180000Z_sd_3.7.0_5.29.0_200_sensor.osi",
    ]

    INVALID_FILENAMES = [
        "random_file.osi",
        "not_a_trace.mcap",
        "missing_timestamp_sv_3.7.0_5.29.0_100_test.osi",
    ]

    @pytest.mark.parametrize("filename", VALID_FILENAMES)
    def test_valid_filename_parity(self, filename):
        from osc_validation.utils.osi_channel_specification import parse_osi_trace_filename as old_parse
        from osi_utilities.tracefile._types import parse_osi_trace_filename as sdk_parse

        old_result = old_parse(filename)
        sdk_result = sdk_parse(filename)

        assert old_result["message_type"] == sdk_result["message_type"]
        assert old_result["osi_version"] == sdk_result["osi_version"]
        assert old_result["protobuf_version"] == sdk_result["protobuf_version"]
        assert old_result["number_of_frames"] == sdk_result["number_of_frames"]
        assert old_result["custom_trace_name"] == sdk_result["custom_trace_name"]
        assert old_result["timestamp"] == sdk_result["timestamp"]

    @pytest.mark.parametrize("filename", INVALID_FILENAMES)
    def test_invalid_filename_both_return_empty(self, filename):
        from osc_validation.utils.osi_channel_specification import parse_osi_trace_filename as old_parse
        from osi_utilities.tracefile._types import parse_osi_trace_filename as sdk_parse

        assert old_parse(filename) == {}
        assert sdk_parse(filename) == {}

    def test_message_type_map_parity(self):
        """SDK _SHORT_CODE_TO_MESSAGE_TYPE matches osc_validation MESSAGE_TYPE_MAP."""
        from osc_validation.utils.osi_channel_specification import MESSAGE_TYPE_MAP as old_map
        from osi_utilities.tracefile._types import _SHORT_CODE_TO_MESSAGE_TYPE as sdk_map

        assert old_map == sdk_map


# ===========================================================================
# F03: Format mapping (FormatMapper deleted, now using SDK directly)
# ===========================================================================


class TestF03FormatMapping:
    """Verify format mapping via SDK get_trace_file_format."""

    EXTENSIONS = [".osi", ".xz", ".lzma", ".mcap"]

    @pytest.mark.parametrize("ext", EXTENSIONS)
    def test_extension_mapping(self, ext):
        from osi_utilities.tracefile._types import get_trace_file_format, TraceFileFormat

        fmt = get_trace_file_format(Path(f"test{ext}"))
        assert isinstance(fmt, TraceFileFormat)

    def test_unsupported_extension_raises(self):
        from osi_utilities.tracefile._types import get_trace_file_format

        with pytest.raises(ValueError, match="Unsupported"):
            get_trace_file_format(Path("test.csv"))

    def test_reverse_lookup(self):
        from osc_validation.utils.osi_channel_specification import _FORMAT_TO_EXT, TraceFileFormat

        assert _FORMAT_TO_EXT[TraceFileFormat.SINGLE_CHANNEL] == ".osi"
        assert _FORMAT_TO_EXT[TraceFileFormat.MULTI_CHANNEL] == ".mcap"


# ===========================================================================
# F04: _build_file_descriptor_set parity
# ===========================================================================


class TestF04BuildFileDescriptorSet:
    """Verify SDK build_file_descriptor_set works for OSI message types."""

    def test_fds_for_sensor_view(self):
        from osi3 import osi_sensorview_pb2
        from osi_utilities.tracefile._mcap_utils import build_file_descriptor_set

        fds = build_file_descriptor_set(osi_sensorview_pb2.SensorView)
        assert len(fds.file) > 0
        assert fds.SerializeToString()

    def test_fds_for_ground_truth(self):
        from osi3 import osi_groundtruth_pb2
        from osi_utilities.tracefile._mcap_utils import build_file_descriptor_set

        fds = build_file_descriptor_set(osi_groundtruth_pb2.GroundTruth)
        assert len(fds.file) > 0
        assert fds.SerializeToString()
