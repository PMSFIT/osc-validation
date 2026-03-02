"""Integration tests: Phase 2 — Channel Specification (F05-F09).

Tests capture CURRENT behavior of OSIChannelSpecification and related classes.
"""

import pytest
from pathlib import Path


# ===========================================================================
# F05: OSIChannelSpecification core fields
# ===========================================================================


class TestF05ChannelSpecCoreFields:
    """Verify core fields and properties work identically."""

    def test_construction_defaults(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=Path("test.osi"))
        assert spec.path == Path("test.osi")
        assert spec.message_type is None
        assert spec.topic is None
        assert spec.metadata == {}

    def test_construction_with_values(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(
            path=Path("test.mcap"),
            message_type="SensorView",
            topic="my_topic",
            metadata={"key": "value"},
        )
        assert spec.message_type == "SensorView"
        assert spec.topic == "my_topic"
        assert spec.metadata == {"key": "value"}

    def test_trace_file_format_osi(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            TraceFileFormat,
        )

        spec = OSIChannelSpecification(path=Path("test.osi"))
        assert spec.trace_file_format == TraceFileFormat.SINGLE_CHANNEL

    def test_trace_file_format_mcap(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            TraceFileFormat,
        )

        spec = OSIChannelSpecification(path=Path("test.mcap"))
        assert spec.trace_file_format == TraceFileFormat.MULTI_CHANNEL

    def test_trace_file_format_xz(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            TraceFileFormat,
        )

        spec = OSIChannelSpecification(path=Path("test.xz"))
        assert spec.trace_file_format == TraceFileFormat.SINGLE_CHANNEL

    def test_exists_false_for_nonexistent(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=Path("/nonexistent/test.osi"))
        assert spec.exists() is False

    def test_exists_true_for_real_file(self, binary_sv_trace):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=binary_sv_trace)
        assert spec.exists() is True

    def test_autofill_topic(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=Path("my_trace.osi"))
        assert spec.topic is None
        spec.autofill_topic()
        assert spec.topic == "my_trace"

    def test_autofill_topic_preserves_existing(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=Path("my_trace.osi"), topic="keep_me")
        spec.autofill_topic()
        assert spec.topic == "keep_me"


# ===========================================================================
# F06: try_autodetect_message_type
# ===========================================================================


class TestF06AutodetectMessageType:
    """Test message type autodetection from filename and MCAP schema."""

    def test_autodetect_from_osi_convention_filename(self, tmp_path):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        path = tmp_path / "20240101T120000Z_sv_3.7.0_5.29.0_100_test.osi"
        path.write_bytes(b"")  # empty file, only filename matters
        spec = OSIChannelSpecification(path=path)
        assert spec.message_type is None
        result = spec.try_autodetect_message_type()
        assert result is True
        assert spec.message_type == "SensorView"

    def test_autodetect_already_set(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(
            path=Path("test.osi"), message_type="GroundTruth"
        )
        result = spec.try_autodetect_message_type()
        assert result is True
        assert spec.message_type == "GroundTruth"

    def test_autodetect_fails_for_unknown_filename(self, tmp_path):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        path = tmp_path / "random_name.osi"
        path.write_bytes(b"")
        spec = OSIChannelSpecification(path=path)
        result = spec.try_autodetect_message_type()
        assert result is False
        assert spec.message_type is None

    def test_autodetect_from_mcap(self, mcap_sv_trace):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=mcap_sv_trace)
        result = spec.try_autodetect_message_type()
        assert result is True
        assert spec.message_type == "SensorView"


# ===========================================================================
# F07: Builder methods
# ===========================================================================


class TestF07BuilderMethods:
    """Test with_message_type, with_topic, with_trace_file_format."""

    def test_with_message_type(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=Path("test.osi"), topic="t1")
        new_spec = spec.with_message_type("GroundTruth")
        assert new_spec.message_type == "GroundTruth"
        assert new_spec.path == spec.path
        assert new_spec.topic == spec.topic
        # original unchanged
        assert spec.message_type is None

    def test_with_topic(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(
            path=Path("test.mcap"), message_type="SensorView"
        )
        new_spec = spec.with_topic("new_topic")
        assert new_spec.topic == "new_topic"
        assert new_spec.message_type == "SensorView"

    def test_with_trace_file_format_to_mcap(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            TraceFileFormat,
        )

        spec = OSIChannelSpecification(
            path=Path("test.osi"), message_type="SensorView"
        )
        new_spec = spec.with_trace_file_format(TraceFileFormat.MULTI_CHANNEL)
        assert new_spec.path.suffix == ".mcap"
        assert new_spec.message_type == "SensorView"

    def test_with_trace_file_format_to_osi(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            TraceFileFormat,
        )

        spec = OSIChannelSpecification(
            path=Path("test.mcap"), message_type="SensorView"
        )
        new_spec = spec.with_trace_file_format(TraceFileFormat.SINGLE_CHANNEL)
        assert new_spec.path.suffix == ".osi"


# ===========================================================================
# F08: Extension methods (rename_to, with_name, with_name_suffix)
# ===========================================================================


class TestF08ExtensionMethods:
    """Test osc_validation-specific extension methods NOT in SDK."""

    def test_with_name(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(
            path=Path("/data/original.osi"), message_type="SensorView"
        )
        new_spec = spec.with_name("renamed.osi")
        assert new_spec.path == Path("/data/renamed.osi")
        assert new_spec.message_type == "SensorView"

    def test_with_name_suffix(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(
            path=Path("/data/trace.osi"), message_type="SensorView"
        )
        new_spec = spec.with_name_suffix("_cropped")
        assert new_spec.path == Path("/data/trace_cropped.osi")

    def test_rename_to(self, binary_sv_trace, tmp_path):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=binary_sv_trace, message_type="SensorView")
        new_path = tmp_path / "renamed.osi"
        new_spec = spec.rename_to(new_path)
        assert new_spec.path == new_path
        assert new_path.exists()
        assert not binary_sv_trace.exists()

    def test_rename_to_nonexistent_raises(self):
        from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

        spec = OSIChannelSpecification(path=Path("/nonexistent.osi"))
        with pytest.raises(FileNotFoundError):
            spec.rename_to(Path("/other.osi"))


# ===========================================================================
# F09: OSIChannelSpecValidator
# ===========================================================================


class TestF09SpecValidator:
    """Test OSIChannelSpecValidator rules."""

    def test_allowed_message_types_pass(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            OSIChannelSpecValidator,
        )

        validator = OSIChannelSpecValidator(
            allowed_message_types=["SensorView", "GroundTruth"]
        )
        spec = OSIChannelSpecification(
            path=Path("test.osi"), message_type="SensorView"
        )
        validator(spec)  # should not raise

    def test_allowed_message_types_fail(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            OSIChannelSpecValidator,
            InvalidSpecificationError,
        )

        validator = OSIChannelSpecValidator(
            allowed_message_types=["SensorView"]
        )
        spec = OSIChannelSpecification(
            path=Path("test.osi"), message_type="GroundTruth"
        )
        with pytest.raises(InvalidSpecificationError, match="not allowed"):
            validator(spec)

    def test_require_message_type(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            OSIChannelSpecValidator,
            InvalidSpecificationError,
        )

        validator = OSIChannelSpecValidator(require_message_type=True)
        spec = OSIChannelSpecification(path=Path("test.osi"))
        with pytest.raises(InvalidSpecificationError, match="required"):
            validator(spec)

    def test_require_topic(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            OSIChannelSpecValidator,
            InvalidSpecificationError,
        )

        validator = OSIChannelSpecValidator(require_topic=True)
        spec = OSIChannelSpecification(path=Path("test.mcap"))
        with pytest.raises(InvalidSpecificationError, match="required"):
            validator(spec)

    def test_require_metadata_keys(self):
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            OSIChannelSpecValidator,
            InvalidSpecificationError,
        )

        validator = OSIChannelSpecValidator(
            require_metadata_keys=["net.asam.osi.trace.channel.osi_version"]
        )
        spec = OSIChannelSpecification(path=Path("test.mcap"), metadata={})
        with pytest.raises(InvalidSpecificationError, match="Missing"):
            validator(spec)

    def test_none_message_type_passes_allowed_check(self):
        """If message_type is None, allowed_message_types check should pass."""
        from osc_validation.utils.osi_channel_specification import (
            OSIChannelSpecification,
            OSIChannelSpecValidator,
        )

        validator = OSIChannelSpecValidator(
            allowed_message_types=["SensorView"]
        )
        spec = OSIChannelSpecification(path=Path("test.osi"))
        validator(spec)  # should not raise
