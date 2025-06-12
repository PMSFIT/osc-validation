from pathlib import Path


class OSIVisualizationTool:
    def __init__(self, tool_path=None):
        self.tool_path = Path(tool_path) if tool_path else None

    def run(self, osi_path):
        raise NotImplementedError("This method must be implemented by the subclass.")
