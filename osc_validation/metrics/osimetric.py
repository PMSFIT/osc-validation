from osc_validation.utils.osi_channel_specification import OSIChannelSpecification


class OSIMetric:
    """
    Base class for validation metrics.
    This class can be extended to implement specific validation metrics.
    """
    def __init__(self, name: str):
        self.name = name

    def compute(self, reference_channel_spec: OSIChannelSpecification, tool_channel_spec: OSIChannelSpecification):
        raise NotImplementedError("Subclasses should implement this method.")

    def __str__(self):
        return f"ValidationMetric(name={self.name})"
