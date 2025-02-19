from pathlib import Path


class OSCTool:
    def __init__(self, tool_path=None):
        self.tool_path = Path(tool_path) if tool_path else None

    def run(self, osc_path, odr_path, osi_path):
        raise NotImplementedError("This method must be implemented by the subclass.")
