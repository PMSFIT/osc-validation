import shutil
from pathlib import Path

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification


class OSCTool:
    def __init__(self, tool_path=None):
        self.tool_path = Path(tool_path) if tool_path else None

    @staticmethod
    def resolve_tool_path(tool_path, default_tool_name: str) -> Path:
        if not tool_path:
            tool_path = default_tool_name

        tool_path = Path(tool_path)
        if tool_path.exists():
            return tool_path

        resolved_tool_path = shutil.which(str(tool_path))
        if resolved_tool_path:
            return Path(resolved_tool_path)

        raise FileNotFoundError(
            f"{default_tool_name} not found at path or on PATH: {tool_path}"
        )

    def get_version(self) -> list[str]:
        return ["unknown version"]

    def run(
        self, osc_path: Path, odr_path: Path, osi_output_spec: OSIChannelSpecification
    ) -> OSIChannelSpecification:
        """
        Executes the OpenSCENARIO XML engine with the specified input files and parameters.
        Args:
            osc_path (Path): Path to the OpenSCENARIO (.xosc) file.
            odr_path (Path): Path to the OpenDRIVE (.xodr) file.
            osi_output_spec (OSIChannelSpecification): Requested OSI channel specification of the output trace.
        Returns:
            OSIChannelSpecification: The OSI channel specification for the output trace.
        """
        raise NotImplementedError("This method must be implemented by the subclass.")
