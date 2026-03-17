from pathlib import Path

import pytest
from osi_utilities import ChannelSpecification

from osc_validation.utils.tool_helpers import (
    rename_trace,
    single_channel_temp_spec,
    validate_output_spec,
)


def test_validate_output_spec_rejects_invalid_message_type():
    spec = ChannelSpecification(path=Path("trace.osi"), message_type="InvalidType")

    with pytest.raises(ValueError, match="OSI message type is not allowed"):
        validate_output_spec(spec, {"SensorView", "GroundTruth"})


def test_single_channel_temp_spec_preserves_metadata_and_topic(tmp_path):
    output_spec = ChannelSpecification(
        path=tmp_path / "trace.osi.xz",
        message_type="SensorView",
        topic="sv",
        metadata={"source": "test"},
    )

    temp_spec = single_channel_temp_spec(output_spec, "_temp", "GroundTruth")

    assert temp_spec.path == tmp_path / "trace_temp.osi"
    assert temp_spec.message_type == "GroundTruth"
    assert temp_spec.topic == "sv"
    assert temp_spec.metadata == {"source": "test"}


def test_rename_trace_moves_file_and_preserves_spec(tmp_path):
    source_path = tmp_path / "source.osi"
    source_path.write_bytes(b"trace-data")
    source_spec = ChannelSpecification(
        path=source_path,
        message_type="GroundTruth",
        topic="gt",
        metadata={"source": "test"},
    )

    destination_path = tmp_path / "renamed.osi"
    renamed_spec = rename_trace(source_spec, destination_path)

    assert not source_path.exists()
    assert destination_path.exists()
    assert renamed_spec.path == destination_path
    assert renamed_spec.message_type == "GroundTruth"
    assert renamed_spec.topic == "gt"
    assert renamed_spec.metadata == {"source": "test"}
