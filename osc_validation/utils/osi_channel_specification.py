from osi_utilities import ChannelSpecification
from pathlib import Path


def with_name_suffix(spec: ChannelSpecification, suffix: str) -> ChannelSpecification:
    new_name = spec.path.stem + suffix + spec.path.suffix
    return ChannelSpecification(
        path=spec.path.with_name(new_name),
        message_type=spec.message_type,
        topic=spec.topic,
        metadata=dict(spec.metadata),
    )


def rename_to(spec: ChannelSpecification, new_path: Path) -> ChannelSpecification:
    if not (spec.path.exists() and spec.path.is_file()):
        raise FileNotFoundError(f"Cannot rename: file does not exist at {spec.path}")
    spec.path.rename(new_path)
    return ChannelSpecification(
        path=new_path,
        message_type=spec.message_type,
        topic=spec.topic,
        metadata=dict(spec.metadata),
    )


class InvalidSpecificationError(Exception):
    pass


class OSIChannelSpecValidator:
    def __init__(
        self,
        allowed_message_types=None,
        require_message_type=False,
        require_topic=False,
        require_metadata_keys=None,
    ):
        self.allowed_message_types = allowed_message_types
        self.require_message_type = require_message_type
        self.require_topic = require_topic
        self.require_metadata_keys = require_metadata_keys or []

    def __call__(self, spec: ChannelSpecification):
        if (
            self.allowed_message_types
            and spec.message_type not in self.allowed_message_types
            and spec.message_type is not None
        ):
            raise InvalidSpecificationError(
                f"OSI message type is not allowed: {spec.message_type}"
            )
        if self.require_message_type and not spec.message_type:
            raise InvalidSpecificationError("OSI message type is required.")
        if self.require_topic and not spec.topic:
            raise InvalidSpecificationError("Topic is required.")
        for key in self.require_metadata_keys:
            if key not in spec.metadata:
                raise InvalidSpecificationError(f"Missing required metadata key: {key}")
