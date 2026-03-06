"""OSI channel writer — thin project wrapper over SDK ChannelWriter.

Keeps LZMA compression support (.osi.xz) locally since the SDK does not
handle compressed binary traces. All other writing delegates to the SDK.
"""

import logging
import lzma
from pathlib import Path
import struct

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification

from osi_utilities.tracefile.channel_writer import ChannelWriter


class _LZMABinaryWriter:
    """Compressed binary writer for .osi.xz files (SDK gap)."""

    def __init__(self, path: Path):
        if "".join(path.suffixes) != ".osi.xz":
            raise ValueError(
                f"Invalid file path: '{path}'. Must be '.osi.xz' for compressed binary."
            )
        self._path = path
        self._file = open(path, "wb")
        self._written_count = 0
        self._size = 0
        self._size_uncompressed = 0

    def write_message(self, message, topic=""):
        buf = message.SerializeToString()
        len_uncompressed = len(buf)
        buf = lzma.compress(buf)
        self._file.write(struct.pack("<L", len(buf)))
        self._file.write(buf)
        self._written_count += 1
        self._size += len(buf)
        self._size_uncompressed += len_uncompressed

    def close(self):
        ratio = (
            str(round(self._size_uncompressed / self._size, 2))
            if self._size > 0
            else "N/A"
        )
        logging.info(
            "Wrote %d messages to '%s' (%sMB; compression ratio: %s).",
            self._written_count,
            self._path,
            round(self._size / 1024 / 1024, 2),
            ratio,
        )
        self._file.close()


class OSIChannelWriter(ChannelWriter):
    """Project-specific writer that accepts :class:`OSIChannelSpecification`.

    Inherits all behaviour from :class:`ChannelWriter` (including ASAM OSI
    version enforcement for MCAP) and adds LZMA compression support.
    """

    @classmethod
    def from_osi_channel_specification(
        cls, osi_channel_spec: OSIChannelSpecification
    ) -> "OSIChannelWriter":
        """Create from an :class:`OSIChannelSpecification`.

        Handles ``.osi.xz`` compressed binary locally; delegates ``.osi``
        and ``.mcap`` to the SDK ``ChannelWriter``.
        """
        suffixes = "".join(osi_channel_spec.path.suffixes)
        if suffixes == ".osi.xz":
            lzma_writer = _LZMABinaryWriter(osi_channel_spec.path)
            # For .osi.xz, stem gives "trace.osi" — strip both suffixes
            stem = Path(osi_channel_spec.path.stem).stem
            topic = osi_channel_spec.topic or stem
            message_type = osi_channel_spec.message_type or "Unknown"
            writer = cls.__new__(cls)
            writer._writer = lzma_writer
            writer._topic = topic
            writer._message_type = message_type
            writer._written_count = 0
            writer._path = osi_channel_spec.path
            writer._channel_metadata = None
            return writer

        base = ChannelWriter.from_specification(osi_channel_spec)
        writer = cls.__new__(cls)
        writer.__dict__.update(base.__dict__)
        return writer

    def get_channel_specification(self) -> OSIChannelSpecification:
        spec = super().get_channel_specification()
        return OSIChannelSpecification(
            path=spec.path,
            message_type=spec.message_type,
            topic=spec.topic,
            metadata=spec.metadata,
        )
