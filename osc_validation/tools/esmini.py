import logging
import os
from pathlib import Path

from osc_validation.tools.osctool import OSCTool
from osc_validation.utils.esminigt2sv import gt2sv
from osc_validation.utils.osi_channel_specification import (
    OSIChannelSpecValidator,
    OSIChannelSpecification,
    TraceFileFormat,
)
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter


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
            osi_output_spec (OSIChannelSpecification): Requested OSI channel specification of the output trace.
                Allowed message types are "GroundTruth" and "SensorView"; If none given, it will output a SensorView trace.
            log_path (Path, optional): Path to the directory where logs will be stored. If None, logs will not be saved but printed to stdout.
            rate (float, optional): Fixed timestep rate for the simulation. Defaults to 0.05.
        Returns:
            OSIChannelSpecification: Specification of the output OSI channel.
        Raises:
            InvalidSpecificationError: If the requested OSI output specification is invalid or unsupported.
            FileNotFoundError: If the esmini tool is not found at the specified path.
            RuntimeError: If the trace could not be generated.
        """

        # Check if the requested output specification is supported
        requested_spec_validator = OSIChannelSpecValidator(allowed_message_types=["GroundTruth", "SensorView"])
        requested_spec_validator(osi_output_spec)

        # Run esmini and generate the ground truth trace
        osi_esmini_gt_spec = osi_output_spec.with_name_suffix("_esmini_gt").with_trace_file_format(TraceFileFormat.SINGLE_CHANNEL).with_message_type("GroundTruth")

        cmd = [
            self.tool_path,
            "--headless",
            "--osc", str(osc_path),
            "--osi_file", str(osi_esmini_gt_spec.path),
            "--ground_plane",
            "--fixed_timestep", str(rate),
            "--osi_static_reporting 2" # report static data at every step
        ]

        if log_path is not None:
            cmd.extend(["--logfile_path", str(log_path / "esmini.log")])
        
        cmd_str = " ".join(map(str, cmd))
        logging.info(f"Running esmini with command: \'{cmd_str}\'")
        os.system(cmd_str)
        if not osi_esmini_gt_spec.exists():
            raise RuntimeError(f"ESMini trace could not be generated. Check the tool's logs for more details.")
        logging.info(f"Esmini temp output: {osi_esmini_gt_spec}")

        # Convert the ground truth trace to SensorView if requested
        output_spec = None
        if osi_output_spec.message_type == "SensorView" or osi_output_spec.message_type is None:
            output_spec = gt2sv(gt_channel_spec=osi_esmini_gt_spec, sv_channel_spec=osi_output_spec)
            logging.info(f"gt2sv output: {output_spec}")
        elif osi_output_spec.message_type == "GroundTruth":
            if osi_output_spec.trace_file_format != osi_esmini_gt_spec.trace_file_format:
                reader = OSIChannelReader.from_osi_channel_specification(osi_esmini_gt_spec)
                writer = OSIChannelWriter.from_osi_channel_specification(osi_output_spec)
                with reader as channel_reader, writer as channel_writer:
                    for msg in channel_reader:
                        channel_writer.write(msg)
                output_spec = writer.get_channel_specification()
            else:
                output_spec = osi_esmini_gt_spec.rename_to(osi_output_spec.path) # rename source file to output original esmini ground truth trace without modification

        logging.info(f"Output trace specification: {output_spec}")
        
        return output_spec
