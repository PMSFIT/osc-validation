from osi_utilities import ChannelSpecification

from osc_validation.tools.metadata import OSC_ENGINE_ERRORS_METADATA_KEY


def assert_no_osc_engine_errors(channel_spec: ChannelSpecification) -> None:
    errors = channel_spec.metadata.get(OSC_ENGINE_ERRORS_METADATA_KEY)
    assert not errors, f"Tool reported OSC engine errors:\n{errors}"
