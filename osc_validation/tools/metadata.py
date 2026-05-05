"""
Metadata keys used by tool wrappers.

These values are runtime annotations on returned ChannelSpecification objects.
They are not guaranteed to be persisted in trace files, especially for
single-channel trace formats. Consumers should use them on the returned object
from a tool run before reconstructing a ChannelSpecification from disk.
"""

OSC_ENGINE_ERRORS_METADATA_KEY = "osc_validation.tool.osc_engine_errors"
