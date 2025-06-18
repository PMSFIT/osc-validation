import os
from osc_validation.tools.osctool import OSCTool


class GTGen_Simulator(OSCTool):
    """
    This class serves as a tool for interacting with the gtgen simulator via gtgen_cli.
    """

    def __init__(self, tool_path=None):
        if not tool_path:
            tool_path = "gtgen_cli"
        if not os.path.exists(tool_path):
            raise FileNotFoundError(f"gtgen_cli not found at path: {tool_path}")
        super().__init__(tool_path)

    def run(self, osc_path, odr_path, osi_path, rate=None):
        """
        Executes the gtgen_cli tool with the specified input files and parameters.
        Args:
            osc_path (str): Path to the OpenSCENARIO (.xosc) file.
            odr_path (str): Path to the OpenDRIVE (.xodr) file.
            osi_path (str): Path for the output OSI SensorView file.
            rate (float, optional): Step size in seconds.
        Returns:
            str: Path for the output OSI SensorView file.
        """

        cmd = [
            self.tool_path,
            "-s", osc_path,
            "--odr", odr_path,
            "--output-trace", osi_path
        ]

        if rate is not None:
            cmd.extend(["--step-size-ms", str(rate * 1000)])

        os.system(" ".join(map(str, cmd)))
        return osi_path
