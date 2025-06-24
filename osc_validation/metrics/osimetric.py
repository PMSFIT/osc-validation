from osc_validation.utils.osi_reader import OSIChannelReader


class OSIMetric:
    """
    Base class for validation metrics.
    This class can be extended to implement specific validation metrics.
    """
    def __init__(self, name: str):
        self.name = name

    def compute(self, reference_trace: OSIChannelReader, tool_trace: OSIChannelReader, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")

    def __str__(self):
        return f"ValidationMetric(name={self.name})"
