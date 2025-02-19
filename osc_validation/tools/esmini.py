import os
from osc_validation.tools.osctool import OSCTool
from osc_validation.utils.esminigt2sv import gt2sv


class ESMini(OSCTool):
    """
    This class serves as a tool for interacting with the esmini simulation environment.
    """

    def __init__(self, tool_path=None):
        if not tool_path:
            tool_path = "esmini"
        if not os.path.exists(tool_path):
            raise FileNotFoundError(f"esmini not found at path: {tool_path}")
        super().__init__(tool_path)

    def run(self, osc_path, odr_path, osi_path, rate=0.05):
        os.system(
            f"{self.tool_path} --osc {osc_path} --osi_file {osi_path}_gt --ground_plane --fixed_timestep {rate}"
        )
        gt2sv(osi_path.with_suffix(".osi_gt"), osi_path)
        return osi_path
