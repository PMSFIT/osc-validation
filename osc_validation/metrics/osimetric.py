from osi_utilities import ChannelSpecification


class OSIMetric:
    """
    Base class for validation metrics.
    This class can be extended to implement specific validation metrics.
    """

    def __init__(self, name: str):
        self.name = name

    def compute(
        self,
        reference_channel_spec: ChannelSpecification,
        tool_channel_spec: ChannelSpecification,
    ):
        raise NotImplementedError("Subclasses should implement this method.")

    def __str__(self):
        return f"ValidationMetric(name={self.name})"
