import logging
import os
from pathlib import Path
from osc_validation.tools.osctool import OSCTool
from osc_validation.utils.esminigt2sv import gt2sv
from osc_validation.utils.osi_channel_specification import OSIChannelSpecification, TraceFileFormat
from osc_validation.utils.utils import crop_trace


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

    def run(self, osc_path: Path, odr_path: Path, osi_output_spec: OSIChannelSpecification, log_path: Path=None, rate=0.05) -> OSIChannelSpecification:
        """
        Executes the esmini tool with the provided OpenSCENARIO, OpenDRIVE, and OSI file paths, processes the output, and returns the path to the output OSI trace.
        
        Args:
            osc_path (Path or str): Path to the OpenSCENARIO (.osc) file.
            odr_path (Path or str): Path to the OpenDRIVE (.xodr) file.
            osi_path (OSIChannelSpecification): OSI channel specification of the output trace.
            log_path (Path, optional): Path to the directory where logs will be stored. If None, logs will not be saved but printed to stdout.
            rate (float, optional): Fixed timestep rate for the simulation. Defaults to 0.05.
        Returns:
            OSIChannelSpecification: Specification of the output OSI channel.
        """
        osi_gt_spec = osi_output_spec.with_name_suffix("_esmini_gt").with_trace_file_format(TraceFileFormat.SINGLE_CHANNEL).with_message_type("GroundTruth")
        cmd = [
            self.tool_path,
            "--osc", str(osc_path),
            "--osi_file", str(osi_gt_spec.path),
            "--ground_plane",
            "--fixed_timestep", str(rate)
        ]
        if log_path is not None:
            cmd.extend(["--disable_stdout", "--logfile_path", str(log_path / "esmini.log")])
        
        logging.info(f"Running esmini with command: \'{" ".join(map(str, cmd))}\'")
        os.system(" ".join(map(str, cmd)))
        logging.info(f"Esmini temp output: {osi_gt_spec}")

        osi_sv_spec = osi_output_spec.with_name_suffix("_converted_to_sv").with_trace_file_format(TraceFileFormat.SINGLE_CHANNEL).with_message_type("SensorView")
        gt2sv(gt_channel_spec=osi_gt_spec, sv_channel_spec=osi_sv_spec)
        logging.info(f"gt2sv temp output: {osi_sv_spec}")

        # Crop the trace to remove the first 0.3 seconds
        tool_trace_cropped_channel = crop_trace(
            input_channel_spec=osi_sv_spec,
            output_channel_spec=osi_output_spec,
            start_time=0.3
        )

        logging.info(f"Cropped trace output: {tool_trace_cropped_channel}")
        return tool_trace_cropped_channel
