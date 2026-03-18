from pathlib import Path

from osi_utilities import ChannelSpecification


class OSCTool:
    def __init__(self, tool_path=None):
        self.tool_path = Path(tool_path) if tool_path else None

    def get_version(self) -> list[str]:
        return ["unknown version"]

    def run(
        self, osc_path: Path, odr_path: Path, osi_output_spec: ChannelSpecification
    ) -> ChannelSpecification:
        """
        Executes the OpenSCENARIO XML engine with the specified input files and parameters.
        Args:
            osc_path (Path): Path to the OpenSCENARIO (.xosc) file.
            odr_path (Path): Path to the OpenDRIVE (.xodr) file.
            osi_output_spec (ChannelSpecification): Requested OSI channel specification of the output trace.
        Returns:
            ChannelSpecification: The OSI channel specification for the output trace.
        """
        raise NotImplementedError("This method must be implemented by the subclass.")
