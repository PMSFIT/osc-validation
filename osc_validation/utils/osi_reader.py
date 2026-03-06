"""OSI channel reader — thin project wrapper over SDK ChannelReader."""

from pathlib import Path

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification
from osi_utilities.tracefile.channel_reader import ChannelReader


class OSIChannelReader(ChannelReader):
    """Project-specific reader that accepts :class:`OSIChannelSpecification`.

    Inherits all behaviour from :class:`ChannelReader` and adds a
    backward-compatible factory method plus an override of
    ``get_channel_specification`` to return an ``OSIChannelSpecification``.
    """

    @classmethod
    def from_osi_channel_specification(
        cls, osi_channel_spec: OSIChannelSpecification
    ) -> "OSIChannelReader":
        """Create from an :class:`OSIChannelSpecification`."""
        base = ChannelReader.from_specification(osi_channel_spec)
        # Re-brand as OSIChannelReader while sharing the internal state
        reader = cls.__new__(cls)
        reader.__dict__.update(base.__dict__)
        return reader

    def get_channel_specification(self) -> OSIChannelSpecification:
        spec = super().get_channel_specification()
        return OSIChannelSpecification(
            path=spec.path,
            message_type=spec.message_type,
            topic=spec.topic,
        )
