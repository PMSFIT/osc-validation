from pathlib import Path


class OSCTool:
    def __init__(self, tool_path=None):
        self.tool_path = Path(tool_path) if tool_path else None

    def run(self, osc_path, odr_path, osi_path):
        """
        Executes the OpenSCENARIO XML engine with the specified input files and parameters.
        Args:
            osc_path (str): Path to the OpenSCENARIO (.xosc) file.
            odr_path (str): Path to the OpenDRIVE (.xodr) file.
            osi_path (str): Path for the output OSI SensorView file.
        Returns:
            str: Path for the output OSI SensorView file.
        """
        raise NotImplementedError("This method must be implemented by the subclass.")
